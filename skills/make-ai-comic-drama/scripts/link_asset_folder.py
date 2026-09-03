#!/usr/bin/env python3
"""Link an asset folder logically, scan files, and build a review queue."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUPPORTED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif",
    ".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg",
    ".mp4", ".mov", ".mkv", ".webm",
}
COMMON_SUFFIXES = (
    "角色设定", "角色资产图", "场景资产图", "场景母图", "道具资产图", "三视图",
    "正面", "侧面", "背面", "全景", "中景", "近景", "入口向内", "深处向外",
    "最终版", "定稿", "高清", "参考图", "资产",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="接入资产文件夹并生成自动匹配与逐项审核队列。")
    parser.add_argument("--project-root", required=True, help="包含project_config.json的项目目录。")
    parser.add_argument("--asset-folder", required=True, help="用户已制作资产所在文件夹。")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_suffix(text: str) -> str:
    return re.sub(r"[\s_\-—（）()【】\[\].]+", "", text).lower()


def normalize(text: str) -> str:
    value = normalize_suffix(text)
    changed = True
    while changed:
        changed = False
        for suffix in COMMON_SUFFIXES:
            normalized_suffix = normalize_suffix(suffix)
            if value.endswith(normalized_suffix) and len(value) > len(normalized_suffix):
                value = value[: -len(normalized_suffix)]
                changed = True
    return value


def load_assets(project_root: Path) -> list[dict[str, Any]]:
    candidates = [
        project_root / "03_MASTER_ASSETS" / "master_assets.json",
        project_root / "03_MASTER_ASSETS" / "assets.json",
    ]
    for path in candidates:
        if path.is_file():
            data = load_json(path)
            if isinstance(data, dict):
                data = data.get("assets")
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
    raise FileNotFoundError("未找到母资产JSON：03_MASTER_ASSETS/master_assets.json")


def scan_files(folder: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        stat = path.stat()
        files.append({
            "absolute_path": str(path.resolve()),
            "relative_path": str(path.relative_to(folder)),
            "file_name": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": stat.st_size,
            "normalized_stem": normalize(path.stem),
        })
    return files


def match_assets(
    assets: list[dict[str, Any]],
    files: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    review_queue: list[dict[str, Any]] = []
    matched_paths: set[str] = set()
    for asset in assets:
        name = str(asset.get("canonical_name") or "").strip()
        if not name:
            continue
        key = normalize(name)
        exact = [item for item in files if item["normalized_stem"] == key]
        contains = [
            item for item in files
            if item not in exact
            and key
            and (key in item["normalized_stem"] or item["normalized_stem"] in key)
        ]
        candidates = exact or contains
        for item in candidates:
            matched_paths.add(item["absolute_path"])
        if not candidates:
            match_status = "缺失"
        elif len(candidates) == 1:
            match_status = "已匹配"
        else:
            match_status = "多候选"
        review_queue.append({
            "asset_id": asset.get("asset_id"),
            "canonical_name": name,
            "asset_type": asset.get("asset_type"),
            "planned_prompt": asset.get("prompt") or asset.get("notes") or "",
            "match_status": match_status,
            "candidate_files": [item["absolute_path"] for item in candidates],
            "content_review_status": "待逐项审核" if candidates else "缺失",
            "review_evidence": "",
            "issues": [],
            "affected_shot_groups": [],
            "revision_advice": "",
            "may_mark_ready": False,
        })
    unmatched = [item for item in files if item["absolute_path"] not in matched_paths]
    return review_queue, unmatched


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    project_root = Path(args.project_root).expanduser().resolve()
    asset_folder = Path(args.asset_folder).expanduser().resolve()
    if not (project_root / "project_config.json").is_file():
        print("ERROR: 项目目录缺少project_config.json。")
        return 1
    if not asset_folder.is_dir():
        print(f"ERROR: 资产文件夹不存在或不是目录：{asset_folder}")
        return 1
    try:
        assets = load_assets(project_root)
        files = scan_files(asset_folder)
        review_queue, unmatched = match_assets(assets, files)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    output_dir = project_root / "03_MASTER_ASSETS"
    now = datetime.now(timezone.utc).isoformat()
    write_json(output_dir / "asset_sources.json", {
        "schema_version": "1.0",
        "source_folders": [{
            "absolute_path": str(asset_folder),
            "read_only": True,
            "linked_at": now,
        }],
    })
    write_json(output_dir / "asset_folder_index.json", {
        "schema_version": "1.0",
        "scanned_at": now,
        "source_folder": str(asset_folder),
        "supported_file_count": len(files),
        "files": files,
        "unmatched_files": unmatched,
    })
    write_json(output_dir / "asset_review_queue.json", {
        "schema_version": "1.0",
        "created_at": now,
        "source_folder": str(asset_folder),
        "rule": "文件名匹配不等于内容审核通过；逐项审核通过后才能标记制作完成。",
        "summary": {
            "planned_assets": len(review_queue),
            "matched": sum(item["match_status"] == "已匹配" for item in review_queue),
            "multiple_candidates": sum(item["match_status"] == "多候选" for item in review_queue),
            "missing": sum(item["match_status"] == "缺失" for item in review_queue),
            "unmatched_files": len(unmatched),
        },
        "assets": review_queue,
    })
    print(f"资产文件夹已接入（只读）：{asset_folder}")
    print(f"扫描文件：{len(files)}")
    print(f"唯一匹配：{sum(item['match_status'] == '已匹配' for item in review_queue)}")
    print(f"多候选：{sum(item['match_status'] == '多候选' for item in review_queue)}")
    print(f"缺失：{sum(item['match_status'] == '缺失' for item in review_queue)}")
    print(f"未识别文件：{len(unmatched)}")
    print("下一步：逐项读取候选文件并对照剧本与提示词审核；当前没有资产被自动标记为制作完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
