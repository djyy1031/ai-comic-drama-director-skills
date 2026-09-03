#!/usr/bin/env python3
"""Initialize a non-destructive AI drama production project."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


DIRECTORIES = [
    "00_INPUT",
    "01_SCRIPT/episodes",
    "01_SCRIPT/director_requests",
    "02_SHOTGROUPS",
    "03_MASTER_ASSETS/characters",
    "03_MASTER_ASSETS/scenes",
    "03_MASTER_ASSETS/props",
    "03_MASTER_ASSETS/ui",
    "03_MASTER_ASSETS/sound",
    "04_MASTER_ASSET_PROMPTS",
    "05_SUB_ASSETS",
    "06_PRODUCTION_TABLES",
    "07_AUDIT/script_fidelity",
    "07_AUDIT/asset_coverage",
    "07_AUDIT/continuity_generatability",
    "08_VIDEO_PACKAGE",
    "09_SOUND",
    "10_FINAL",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="创建AI漫剧生产项目目录。")
    parser.add_argument("--path", required=True, help="项目父目录。")
    parser.add_argument("--name", required=True, help="项目目录和项目名称。")
    parser.add_argument(
        "--model-profile",
        required=True,
        choices=("seedance-2.0", "seedance-2.5"),
        help="选择且只选择一个模型配置。",
    )
    parser.add_argument("--render-mode", required=True, help="必须明确，例如2D或3D。")
    parser.add_argument("--aspect-ratio", required=True, help="必须明确，例如9:16或16:9。")
    parser.add_argument("--visual-style", required=True, help="必须填写可执行的项目统一视觉风格。")
    parser.add_argument("--genre", default="", help="项目主类型。")
    return parser.parse_args()


def validate_project_name(name: str) -> None:
    if not name.strip() or name in {".", ".."}:
        raise ValueError("项目名不能为空或使用点路径。")
    if re.search(r"[\\/:*?\"<>|]", name):
        raise ValueError("项目名包含Windows路径禁用字符。")


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def initialize(args: argparse.Namespace) -> Path:
    validate_project_name(args.name)
    if not str(args.render_mode).strip():
        raise ValueError("render_mode不能为空，必须先确认2D、3D或其他明确视觉形态。")
    if not re.fullmatch(r"\d+(?:\.\d+)?:\d+(?:\.\d+)?", str(args.aspect_ratio).strip()):
        raise ValueError("aspect_ratio必须是明确比例，例如9:16或16:9。")
    if not str(args.visual_style).strip():
        raise ValueError("visual_style不能为空，必须先确认统一美术风格。")
    parent = Path(args.path).expanduser().resolve()
    target = (parent / args.name).resolve()

    if target == Path(target.anchor) or target == Path.home().resolve():
        raise ValueError("拒绝把磁盘根目录或用户主目录作为项目目录。")
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"目标目录非空，拒绝覆盖：{target}")

    target.mkdir(parents=True, exist_ok=True)
    for relative in DIRECTORIES:
        (target / relative).mkdir(parents=True, exist_ok=True)

    config = {
        "schema_version": "1.0",
        "project_name": args.name,
        "model_profile": args.model_profile,
        "render_mode": args.render_mode,
        "aspect_ratio": args.aspect_ratio,
        "visual_style": args.visual_style,
        "genre": {"primary": args.genre, "packs": []},
        "director_knowledge": {
            "preferred_skill": "ai-cinematic-directing-assets",
            "allow_internal_fallback": True,
        },
        "episode": {"target_seconds": None, "final_max_seconds": 180},
        "subtitle_policy": {
            "generate_dialogue_subtitles": False,
            "append_to_each_language_shot": True,
            "required_language_shot_suffix": "视频严禁出现台词、内心独白与系统语音字幕。",
            "allow_story_ui_text": True,
        },
    }
    status = {
        "schema_version": "1.0",
        "project_name": args.name,
        "model_profile": args.model_profile,
        "current_stage": "PROJECT_INITIALIZED",
        "director_library_status": "PENDING",
        "director_representation_version": None,
        "scene_state_ledger_version": None,
        "shotgroup_lock_version": None,
        "master_asset_version": None,
        "last_audit": None,
        "waiting_for": "SCRIPT_INPUT",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    write_json(target / "project_config.json", config)
    write_json(target / "PROJECT_STATUS.json", status)

    skill_root = Path(__file__).resolve().parents[1]
    workbook_template = skill_root / "assets" / "AI漫剧生产信息表模板.xlsx"
    episode_template = (
        skill_root
        / "assets"
        / f"episode-manifest.{args.model_profile}.template.json"
    )
    if workbook_template.is_file():
        shutil.copy2(
            workbook_template,
            target / "06_PRODUCTION_TABLES" / "AI漫剧生产信息表.xlsx",
        )
    if episode_template.is_file():
        shutil.copy2(
            episode_template,
            target / "02_SHOTGROUPS" / "episode_manifest.template.json",
        )
    return target


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    try:
        target = initialize(args)
    except (ValueError, FileExistsError, OSError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"CREATED: {target}")
    print(f"MODEL_PROFILE: {args.model_profile}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
