#!/usr/bin/env python3
"""Validate AI drama project invariants for planning, production, or final delivery."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MODEL_PROFILES = {"seedance-2.0", "seedance-2.5"}
REQUIRED_LANGUAGE_SHOT_SUFFIX = "视频严禁出现台词、内心独白与系统语音字幕。"
AUDIT_KEYS = (
    "script_fidelity",
    "asset_coverage",
    "continuity_generatability",
)
AMBIGUOUS_PATTERN = re.compile(
    r"(?<!其)(?:他|她|它)(?:们|的)?|对方|前者|后者|另一人|那个人|"
    r"这里|那里|该处|这个房间|场景同前|那个东西|桌上的东西"
)
QUOTE_PATTERNS = (
    re.compile(r"“[^”]*”", re.DOTALL),
    re.compile(r'"[^"\n]*"'),
    re.compile(r"「[^」]*」", re.DOTALL),
    re.compile(r"『[^』]*』", re.DOTALL),
)
SPOKEN_MARKERS = ("对话：", "内心独白：", "旁白：", "画外音：", "系统语音：", "系统播报：")
SHOT_HEADER_PATTERN = re.compile(
    r"^【\s*\d+(?:\.\d+)?\s*[-—～~]\s*\d+(?:\.\d+)?\s*秒\s*】",
)
SECTION_HEADER_PATTERN = re.compile(r"^【[^】]+】")


@dataclass
class Result:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_manifests: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def load_json(path: Path, result: Result) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        result.error(f"缺少文件：{path}")
        return None
    except (OSError, json.JSONDecodeError) as exc:
        result.error(f"无法读取JSON：{path}：{exc}")
        return None
    if not isinstance(data, dict):
        result.error(f"JSON顶层必须是对象：{path}")
        return None
    return data


def as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def close(a: float, b: float, tolerance: float = 0.01) -> bool:
    return abs(a - b) <= tolerance


def mask_dialogue_quotes(text: str) -> str:
    masked = text
    for pattern in QUOTE_PATTERNS:
        masked = pattern.sub(lambda match: " " * len(match.group(0)), masked)
    return masked


def validate_config(config: dict[str, Any], result: Result) -> str | None:
    model = config.get("model_profile")
    if model not in MODEL_PROFILES:
        result.error("project_config.model_profile只能是seedance-2.0或seedance-2.5。")
        model = None

    if not str(config.get("render_mode") or "").strip():
        result.error("project_config.render_mode不能为空，必须明确2D、3D或其他视觉形态。")
    aspect_ratio = str(config.get("aspect_ratio") or "").strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?:\d+(?:\.\d+)?", aspect_ratio):
        result.error("project_config.aspect_ratio必须是明确比例，例如9:16或16:9。")
    if not str(config.get("visual_style") or "").strip():
        result.error("project_config.visual_style不能为空，必须填写统一美术风格。")

    episode_config = config.get("episode")
    if not isinstance(episode_config, dict):
        result.error("project_config.episode必须是对象。")
    else:
        max_seconds = as_number(episode_config.get("final_max_seconds"))
        if max_seconds is None or max_seconds <= 0 or max_seconds > 180:
            result.error("episode.final_max_seconds必须大于0且不得超过180。")

    subtitle = config.get("subtitle_policy")
    if not isinstance(subtitle, dict):
        result.error("project_config.subtitle_policy必须是对象。")
    else:
        if subtitle.get("append_to_each_language_shot") is not True:
            result.error("subtitle_policy.append_to_each_language_shot必须为true。")
        if subtitle.get("required_language_shot_suffix") != REQUIRED_LANGUAGE_SHOT_SUFFIX:
            result.error(
                "subtitle_policy.required_language_shot_suffix必须原样为："
                f"{REQUIRED_LANGUAGE_SHOT_SUFFIX}"
            )
        if subtitle.get("generate_dialogue_subtitles") is not False:
            result.error("generate_dialogue_subtitles必须为false。")
    return model


def validate_shot_timeline(
    manifest_path: Path,
    group_label: str,
    duration: float,
    shots: Any,
    result: Result,
) -> None:
    prefix = f"{manifest_path}:{group_label}"
    if not isinstance(shots, list) or not shots:
        result.error(f"{prefix} shots必须是非空数组。")
        return

    previous_end = 0.0
    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            result.error(f"{prefix} 第{index}镜必须是对象。")
            continue
        start = as_number(shot.get("start_seconds"))
        end = as_number(shot.get("end_seconds"))
        if start is None or end is None:
            result.error(f"{prefix} 第{index}镜缺少有效起止时间。")
            continue
        if end <= start:
            result.error(f"{prefix} 第{index}镜结束时间必须大于开始时间。")
        if not str(shot.get("purpose") or "").strip():
            result.error(f"{prefix} 第{index}镜必须写purpose。")
        if not close(start, previous_end):
            result.error(
                f"{prefix} 第{index}镜时间不连续：应从{previous_end:g}开始，实际{start:g}。"
            )
        previous_end = end

    if not close(previous_end, duration):
        result.error(
            f"{prefix} 末镜结束时间{previous_end:g}不等于分镜组时长{duration:g}。"
        )


def validate_prompt(
    manifest_path: Path,
    group_label: str,
    group: dict[str, Any],
    result: Result,
) -> None:
    prefix = f"{manifest_path}:{group_label}"
    prompt = group.get("clean_prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        result.error(f"{prefix} clean_prompt不能为空。")
        return

    shot_blocks: list[str] = []
    current_shot: list[str] | None = None
    for line in prompt.splitlines():
        stripped = line.strip()
        if SHOT_HEADER_PATTERN.match(stripped):
            if current_shot:
                shot_blocks.append("\n".join(current_shot))
            current_shot = [line]
            continue
        if current_shot is not None and SECTION_HEADER_PATTERN.match(stripped):
            shot_blocks.append("\n".join(current_shot))
            current_shot = None
        if current_shot is not None:
            current_shot.append(line)
    if current_shot:
        shot_blocks.append("\n".join(current_shot))

    detected_spoken_language = any(marker in prompt for marker in SPOKEN_MARKERS)
    declared_spoken_language = group.get("has_spoken_language") is True
    if detected_spoken_language and not declared_spoken_language:
        result.error(f"{prefix} 提示词含语言内容，但has_spoken_language未标记为true。")
    language_shot_count = 0
    for index, block in enumerate(shot_blocks, start=1):
        if not any(marker in block for marker in SPOKEN_MARKERS):
            continue
        language_shot_count += 1
        trimmed_block = block.rstrip()
        suffix_start = len(trimmed_block) - len(REQUIRED_LANGUAGE_SHOT_SUFFIX)
        has_separator = suffix_start > 0 and trimmed_block[suffix_start - 1].isspace()
        if not trimmed_block.endswith(REQUIRED_LANGUAGE_SHOT_SUFFIX) or not has_separator:
            result.error(
                f"{prefix} 第{index}个含语言内容镜头必须以固定句结束："
                f"{REQUIRED_LANGUAGE_SHOT_SUFFIX}"
            )
    if detected_spoken_language and language_shot_count == 0:
        result.error(f"{prefix} 语言内容必须写入带时间区间的小镜头内。")
    if declared_spoken_language and language_shot_count == 0:
        result.error(f"{prefix} has_spoken_language=true但未找到含语言内容的小镜头。")

    descriptive_text = mask_dialogue_quotes(prompt)
    match = AMBIGUOUS_PATTERN.search(descriptive_text)
    if match:
        result.error(
            f"{prefix} 执行描述含模糊指代“{match.group(0)}”，必须改为标准名称。"
        )


def validate_assets_for_production(
    manifest_path: Path,
    group_label: str,
    assets: Any,
    result: Result,
) -> None:
    prefix = f"{manifest_path}:{group_label}"
    if assets is None:
        return
    if not isinstance(assets, list):
        result.error(f"{prefix} assets必须是数组。")
        return
    for index, asset in enumerate(assets, start=1):
        if not isinstance(asset, dict):
            result.error(f"{prefix} 第{index}项资产必须是对象。")
            continue
        score = as_number(asset.get("necessity_score"))
        if score is None or score < 0 or score > 3 or not close(score, round(score)):
            result.error(f"{prefix} 第{index}项资产necessity_score必须是0～3整数。")
            continue
        if int(score) == 3 and asset.get("status") != "READY":
            name = asset.get("canonical_name") or asset.get("asset_id") or f"第{index}项"
            result.error(f"{prefix} 必须资产“{name}”尚未READY。")


def validate_sound_plan(
    manifest_path: Path,
    sound_plan: Any,
    final_duration: float,
    result: Result,
) -> None:
    if not isinstance(sound_plan, dict) or sound_plan.get("status") != "READY":
        result.error(f"{manifest_path} final阶段要求sound_plan.status=READY。")
        return
    cues = sound_plan.get("cues")
    if not isinstance(cues, list) or not cues:
        result.error(f"{manifest_path} final阶段要求至少一条声音或静默安排。")
        return
    intervals: list[tuple[float, float]] = []
    for index, cue in enumerate(cues, start=1):
        prefix = f"{manifest_path}:声音项{index}"
        if not isinstance(cue, dict):
            result.error(f"{prefix} 必须是对象。")
            continue
        start = as_number(cue.get("start_seconds"))
        end = as_number(cue.get("end_seconds"))
        if start is None or end is None or start < 0 or end <= start or end > final_duration + 0.01:
            result.error(f"{prefix} 时间必须位于最终成片范围内且结束大于开始。")
        else:
            intervals.append((start, end))
        if not cue.get("sound_type") or not cue.get("purpose"):
            result.error(f"{prefix} 必须写sound_type和purpose。")
        rights = cue.get("rights_status")
        if rights not in {"ORIGINAL", "CONFIRMED", "NOT_APPLICABLE"}:
            result.error(f"{prefix} rights_status必须已确认、原创或不适用。")

    if intervals:
        intervals.sort()
        covered_start, covered_end = intervals[0]
        if not close(covered_start, 0.0):
            result.error(f"{manifest_path} 声音执行表必须从0秒开始覆盖，静默也要记录。")
        for start, end in intervals[1:]:
            if start > covered_end + 0.01:
                result.error(
                    f"{manifest_path} 声音执行表在{covered_end:g}～{start:g}秒存在未规划空缺。"
                )
            covered_end = max(covered_end, end)
        if not close(covered_end, final_duration):
            result.error(
                f"{manifest_path} 声音执行表覆盖到{covered_end:g}秒，"
                f"不等于最终成片{final_duration:g}秒。"
            )


def validate_manifest(
    path: Path,
    config_model: str,
    stage: str,
    result: Result,
) -> None:
    manifest = load_json(path, result)
    if manifest is None:
        return
    result.checked_manifests += 1

    manifest_model = manifest.get("model_profile")
    if manifest_model != config_model:
        result.error(
            f"{path} model_profile={manifest_model!r}与项目配置{config_model!r}不一致。"
        )

    planned = as_number(manifest.get("planned_final_duration_seconds"))
    overhead = as_number(manifest.get("timeline_overhead_seconds"))
    if planned is None or planned <= 0 or planned > 180:
        result.error(f"{path} planned_final_duration_seconds必须大于0且不超过180。")
    if overhead is None or overhead < 0:
        result.error(f"{path} timeline_overhead_seconds必须是非负数。")
        overhead = 0.0

    groups = manifest.get("shot_groups")
    if not isinstance(groups, list) or not groups:
        result.error(f"{path} shot_groups必须是非空数组。")
        return

    group_total = 0.0
    seen_ids: set[str] = set()
    for index, group in enumerate(groups, start=1):
        if not isinstance(group, dict):
            result.error(f"{path} 第{index}个分镜组必须是对象。")
            continue
        group_id = group.get("shot_group_id")
        group_label = str(group_id or f"分镜组{index}")
        if not group_id:
            result.error(f"{path} 第{index}个分镜组缺少shot_group_id。")
        elif group_id in seen_ids:
            result.error(f"{path} shot_group_id重复：{group_id}")
        else:
            seen_ids.add(str(group_id))

        duration = as_number(group.get("duration_seconds"))
        if duration is None or duration <= 0:
            result.error(f"{path}:{group_label} duration_seconds必须大于0。")
            continue
        group_total += duration

        for required_text_field in ("scene_name", "story_event"):
            if not str(group.get(required_text_field) or "").strip():
                result.error(f"{path}:{group_label} 缺少{required_text_field}。")
        start_blocking = group.get("start_blocking")
        if not isinstance(start_blocking, dict):
            result.error(f"{path}:{group_label} start_blocking必须是对象。")
        else:
            for coordinate_field in ("world_coordinates", "screen_coordinates"):
                if not str(start_blocking.get(coordinate_field) or "").strip():
                    result.error(f"{path}:{group_label} start_blocking缺少{coordinate_field}。")

        if config_model == "seedance-2.0" and duration > 15:
            result.error(f"{path}:{group_label} Seedance 2.0分镜组不得超过15秒。")
        if config_model == "seedance-2.5":
            if duration > 30:
                result.error(f"{path}:{group_label} Seedance 2.5分镜组不得超过30秒。")
            if duration < 20 and not str(group.get("duration_exception_reason") or "").strip():
                result.error(
                    f"{path}:{group_label} Seedance 2.5低于20秒时必须说明无法合并的例外原因。"
                )

        validate_shot_timeline(path, group_label, duration, group.get("shots"), result)
        validate_prompt(path, group_label, group, result)
        if stage in {"production", "final"}:
            validate_assets_for_production(path, group_label, group.get("assets"), result)

    if planned is not None and not close(group_total + overhead, planned):
        result.error(
            f"{path} 分镜组总时长{group_total:g}+额外时长{overhead:g}"
            f"不等于预计成片{planned:g}。"
        )

    if stage in {"production", "final"}:
        audits = manifest.get("audits")
        if not isinstance(audits, dict):
            result.error(f"{path} production阶段要求audits对象。")
        else:
            for key in AUDIT_KEYS:
                if audits.get(key) != "PASS":
                    result.error(f"{path} audits.{key}必须为PASS。")
        if manifest.get("production_ready") is not True:
            result.error(f"{path} production_ready必须为true。")

    if stage == "final":
        final_duration = as_number(manifest.get("final_duration_seconds"))
        if final_duration is None or final_duration <= 0 or final_duration > 180:
            result.error(f"{path} final_duration_seconds必须大于0且不超过180。")
        else:
            validate_sound_plan(path, manifest.get("sound_plan"), final_duration, result)
        if manifest.get("final_episode_ready") is not True:
            result.error(f"{path} final_episode_ready必须为true。")


def validate_project(root: Path, stage: str) -> Result:
    result = Result()
    root = root.resolve()
    config = load_json(root / "project_config.json", result)
    if config is None:
        return result
    model = validate_config(config, result)
    if model is None:
        return result

    manifest_root = root / "02_SHOTGROUPS"
    manifests = sorted(manifest_root.glob("**/episode_manifest.json"))
    if not manifests:
        result.error(f"未找到episode_manifest.json：{manifest_root}")
        return result
    for manifest in manifests:
        validate_manifest(manifest, model, stage, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校验AI漫剧项目硬规则。")
    parser.add_argument("project_root", help="包含project_config.json的项目目录。")
    parser.add_argument(
        "--stage",
        choices=("planning", "production", "final"),
        default="planning",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    result = validate_project(Path(args.project_root), args.stage)
    for message in result.errors:
        print(f"ERROR: {message}")
    for message in result.warnings:
        print(f"WARNING: {message}")
    print(
        f"RESULT: {'PASS' if result.ok else 'FAIL'} | "
        f"manifests={result.checked_manifests} errors={len(result.errors)} "
        f"warnings={len(result.warnings)}"
    )
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
