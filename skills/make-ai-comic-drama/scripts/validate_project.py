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
SPOKEN_MARKERS = (
    "开始说：", "继续说：", "开始内心独白：", "继续内心独白：",
    "开始旁白：", "继续旁白：", "开始画外音：", "继续画外音：",
    "开始系统语音：", "继续系统语音：",
)
BANNED_LANGUAGE_BLOCK_MARKERS = (
    "【连续语言音轨总设定】", "【连续对白音轨总设定】", "音轨覆盖【",
)
GLOBAL_PROMPT_START = "【全局固定画质参数】"
GLOBAL_NEGATIVE_HEADER = "【全局通用负面提示词】"
CAMERA_HEADER = "【摄影机运动总设定】"
SHOT_HEADER_PATTERN = re.compile(
    r"^【\s*(?P<start>\d+(?:\.\d+)?)\s*[-—～~]\s*"
    r"(?P<end>\d+(?:\.\d+)?)\s*秒(?:\s*｜[^】]+)?\s*】",
)
SECTION_HEADER_PATTERN = re.compile(r"^【[^】]+】")
DEFAULT_MAX_SHOT_SECONDS = 6.0
DEFAULT_NORMAL_MIN_EPISODE_SECONDS = 90.0
TIMING_BASES = {"ACTUAL_READ", "ESTIMATED"}
START_MODES = {"ACTION_TRIGGER", "CONTINUE_WITHOUT_RESTART"}
REQUIRED_LANGUAGE_UNIT_FIELDS = (
    "language_id", "speaker", "kind", "full_text", "shot_group_ids",
    "start_trigger", "timing_basis", "spoken_duration_seconds",
    "continuity_requirement", "cross_group_exception",
)
REQUIRED_SEGMENT_FIELDS = (
    "language_id", "segment_index", "text", "start_mode", "start_trigger",
    "spoken_duration_seconds", "timing_basis", "mouth_state", "delivery_continuity",
)

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
    if not str(config.get("global_prompt_profile") or "").strip():
        result.error("project_config.global_prompt_profile不能为空，必须锁定全局控制提示词版本。")

    episode_config = config.get("episode")
    if not isinstance(episode_config, dict):
        result.error("project_config.episode必须是对象。")
    else:
        target_seconds = as_number(episode_config.get("target_seconds"))
        normal_min_seconds = as_number(episode_config.get("normal_min_seconds"))
        max_seconds = as_number(episode_config.get("final_max_seconds"))
        if max_seconds is None or max_seconds <= 0 or max_seconds > 180:
            result.error("episode.final_max_seconds必须大于0且不得超过180。")
        if normal_min_seconds is None or normal_min_seconds <= 0:
            result.error("episode.normal_min_seconds必须是正数，默认使用90。")
        elif max_seconds is not None and normal_min_seconds > max_seconds:
            result.error("episode.normal_min_seconds不得超过final_max_seconds。")
        if target_seconds is not None and (
            target_seconds <= 0
            or (max_seconds is not None and target_seconds > max_seconds)
        ):
            result.error("episode.target_seconds必须留空或位于有效成片时长范围内。")
        if episode_config.get("adaptive_to_script") is not True:
            result.error("episode.adaptive_to_script必须为true，时长目标不得强制凑满。")
        preferred_groups = episode_config.get("preferred_max_shot_groups")
        if preferred_groups is not None and (as_number(preferred_groups) is None or preferred_groups <= 0 or int(preferred_groups) != preferred_groups):
            result.error("episode.preferred_max_shot_groups仅在用户明确要求时填写正整数，否则留空。")
        # Legacy seedance_2_5_preferred_group_seconds is ignored: no separate directing policy.

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
    has_spoken_language: bool,
    result: Result,
) -> None:
    prefix = f"{manifest_path}:{group_label}"
    if not isinstance(shots, list) or not shots:
        result.error(f"{prefix} shots必须是非空数组。")
        return

    previous_end = 0.0
    seen_ids: set[str] = set()
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
        else:
            shot_duration = end - start
            if shot_duration > DEFAULT_MAX_SHOT_SECONDS:
                approved = shot.get("long_take_approved") is True
                reason = str(shot.get("long_take_reason") or "").strip()
                if not approved or not reason:
                    result.error(
                        f"{prefix} 第{index}镜时长{shot_duration:g}秒超过普通单镜6秒上限；"
                        "只有用户或原文明示一镜到底时，才能同时填写"
                        "long_take_approved=true和long_take_reason。"
                    )
        shot_id = str(shot.get("shot_id") or "").strip()
        if not shot_id:
            result.error(f"{prefix} 第{index}镜缺少shot_id。")
        elif shot_id in seen_ids:
            result.error(f"{prefix} shot_id重复：{shot_id}")
        else:
            seen_ids.add(shot_id)
        if not str(shot.get("purpose") or "").strip():
            result.error(f"{prefix} 第{index}镜必须写purpose。")
        if not str(shot.get("existence_reason") or "").strip():
            result.error(f"{prefix} 第{index}镜必须写existence_reason。")
        if not str(shot.get("shot_signature") or "").strip():
            result.error(f"{prefix} 第{index}镜必须写shot_signature，用于跨组和重复镜头检查。")
        if not str(shot.get("primary_subject") or "").strip():
            result.error(f"{prefix} 第{index}镜必须写primary_subject，用于跨组主体检查。")
        if not str(shot.get("framing") or "").strip():
            result.error(f"{prefix} 第{index}镜必须写framing，用于跨组景别检查。")
        if not isinstance(shot.get("spoken_segments"), list):
            result.error(f"{prefix} 第{index}镜spoken_segments必须是数组。")
        if not close(start, previous_end):
            result.error(
                f"{prefix} 第{index}镜时间不连续：应从{previous_end:g}开始，实际{start:g}。"
            )
        previous_end = end

    if has_spoken_language and duration > DEFAULT_MAX_SHOT_SECONDS and len(shots) == 1:
        shot = shots[0] if isinstance(shots[0], dict) else {}
        if not (
            shot.get("long_take_approved") is True
            and str(shot.get("long_take_reason") or "").strip()
        ):
            result.error(
                f"{prefix} 含语言分镜组超过6秒时不能只有一个镜头；"
                "必须拆成正常计时的双人、过肩、近景或反应镜头。"
            )

    if not close(previous_end, duration):
        result.error(
            f"{prefix} 末镜结束时间{previous_end:g}不等于分镜组时长{duration:g}。"
        )

def validate_language_units(
    manifest_path: Path,
    groups: list[Any],
    units: Any,
    stage: str,
    result: Result,
) -> None:
    prefix = str(manifest_path)
    if not isinstance(units, list):
        result.error(f"{prefix} language_units必须是数组。")
        return

    group_order: dict[str, int] = {}
    segments_by_unit: dict[str, list[tuple[int, int, dict[str, Any], float]]] = {}
    for group_index, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("shot_group_id") or "").strip()
        if group_id:
            group_order[group_id] = group_index
        for shot_index, shot in enumerate(group.get("shots") or []):
            if not isinstance(shot, dict):
                continue
            start = as_number(shot.get("start_seconds"))
            end = as_number(shot.get("end_seconds"))
            shot_duration = (end - start) if start is not None and end is not None else 0.0
            for segment in shot.get("spoken_segments") or []:
                if not isinstance(segment, dict):
                    result.error(f"{prefix}:{group_id} 第{shot_index + 1}镜语言片段必须是对象。")
                    continue
                unit_id = str(segment.get("language_id") or "").strip()
                segments_by_unit.setdefault(unit_id, []).append(
                    (group_index, shot_index, segment, shot_duration)
                )

    unit_by_id: dict[str, dict[str, Any]] = {}
    for index, unit in enumerate(units, start=1):
        if not isinstance(unit, dict):
            result.error(f"{prefix} 第{index}条language_unit必须是对象。")
            continue
        for field_name in REQUIRED_LANGUAGE_UNIT_FIELDS:
            if field_name not in unit:
                result.error(f"{prefix} 第{index}条language_unit缺少{field_name}。")
        unit_id = str(unit.get("language_id") or "").strip()
        if not unit_id or unit_id in unit_by_id:
            result.error(f"{prefix} 第{index}条language_unit的language_id为空或重复。")
            continue
        unit_by_id[unit_id] = unit

        for field_name in ("speaker", "kind", "full_text", "start_trigger", "continuity_requirement"):
            if not str(unit.get(field_name) or "").strip():
                result.error(f"{prefix} 语言单元{unit_id}的{field_name}不能为空。")
        group_ids = unit.get("shot_group_ids")
        if not isinstance(group_ids, list) or not group_ids:
            result.error(f"{prefix} 语言单元{unit_id}的shot_group_ids必须是非空数组。")
            group_ids = []
        else:
            normalized_ids = [str(item).strip() for item in group_ids]
            if any(not item or item not in group_order for item in normalized_ids):
                result.error(f"{prefix} 语言单元{unit_id}引用不存在的分镜组。")
            if len(set(normalized_ids)) != len(normalized_ids):
                result.error(f"{prefix} 语言单元{unit_id}的shot_group_ids不能重复。")
            group_ids = normalized_ids

        timing_basis = unit.get("timing_basis")
        if timing_basis not in TIMING_BASES:
            result.error(f"{prefix} 语言单元{unit_id}的timing_basis必须是ACTUAL_READ或ESTIMATED。")
        if stage in {"production", "final"} and timing_basis != "ACTUAL_READ":
            result.error(f"{prefix} 语言单元{unit_id}进入生产前必须使用ACTUAL_READ重新校时。")
        unit_duration = as_number(unit.get("spoken_duration_seconds"))
        if unit_duration is None or unit_duration <= 0:
            result.error(f"{prefix} 语言单元{unit_id}的spoken_duration_seconds必须是正数。")

        cross_group = unit.get("cross_group_exception") is True
        if len(group_ids) > 1 and not cross_group:
            result.error(f"{prefix} 语言单元{unit_id}默认不得跨分镜组。")
        if len(group_ids) <= 1 and cross_group:
            result.error(f"{prefix} 语言单元{unit_id}未跨组，不应开启cross_group_exception。")
        if cross_group:
            transition = unit.get("cross_group_transition")
            required = (
                "approved_by", "reason", "from_group_id", "to_group_id",
                "from_shot_signature", "to_shot_signature", "transition_method",
            )
            if not isinstance(transition, dict):
                result.error(f"{prefix} 语言单元{unit_id}跨组时必须填写cross_group_transition。")
            else:
                for field_name in required:
                    if not str(transition.get(field_name) or "").strip():
                        result.error(f"{prefix} 语言单元{unit_id}跨组转场缺少{field_name}。")
                if transition.get("from_shot_signature") == transition.get("to_shot_signature"):
                    result.error(f"{prefix} 语言单元{unit_id}跨组前后不得使用相同镜头签名。")

    for unit_id in segments_by_unit.keys() - unit_by_id.keys():
        if unit_id:
            result.error(f"{prefix} 镜头引用不存在的语言单元：{unit_id}")
        else:
            result.error(f"{prefix} 镜头语言片段缺少language_id。")

    for unit_id, unit in unit_by_id.items():
        records = segments_by_unit.get(unit_id, [])
        if not records:
            result.error(f"{prefix} 语言单元{unit_id}未被任何镜头承载。")
            continue
        records.sort(key=lambda item: (item[0], item[1], item[2].get("segment_index", 0)))
        segments = [item[2] for item in records]
        used_group_ids = []
        for group_index, _, _, _ in records:
            group_id = next((key for key, value in group_order.items() if value == group_index), "")
            if group_id and group_id not in used_group_ids:
                used_group_ids.append(group_id)
        declared_group_ids = [str(item).strip() for item in unit.get("shot_group_ids") or []]
        if used_group_ids != declared_group_ids:
            result.error(f"{prefix} 语言单元{unit_id}实际承载分镜组与shot_group_ids不一致。")

        indexes = [segment.get("segment_index") for segment in segments]
        if indexes != list(range(1, len(segments) + 1)):
            result.error(f"{prefix} 语言单元{unit_id}的segment_index必须从1连续递增且不得重复。")
        joined = "".join(str(segment.get("text") or "") for segment in segments)
        if joined != str(unit.get("full_text") or ""):
            result.error(f"{prefix} 语言单元{unit_id}的逐镜片段无法逐字拼回完整原文。")

        total_spoken = 0.0
        for position, ((_, _, segment, shot_duration)) in enumerate(records, start=1):
            for field_name in REQUIRED_SEGMENT_FIELDS:
                if field_name not in segment:
                    result.error(f"{prefix} 语言单元{unit_id}第{position}片段缺少{field_name}。")
            expected_mode = "ACTION_TRIGGER" if position == 1 else "CONTINUE_WITHOUT_RESTART"
            if segment.get("start_mode") != expected_mode:
                result.error(f"{prefix} 语言单元{unit_id}第{position}片段start_mode必须是{expected_mode}。")
            if not str(segment.get("start_trigger") or "").strip():
                result.error(f"{prefix} 语言单元{unit_id}第{position}片段必须写具体start_trigger。")
            segment_duration = as_number(segment.get("spoken_duration_seconds"))
            if segment_duration is None or segment_duration <= 0:
                result.error(f"{prefix} 语言单元{unit_id}第{position}片段时长必须是正数。")
            else:
                total_spoken += segment_duration
                if segment_duration > shot_duration + 0.01:
                    result.error(f"{prefix} 语言单元{unit_id}第{position}片段时长超过承载镜头时长。")
            basis = segment.get("timing_basis")
            if basis not in TIMING_BASES:
                result.error(f"{prefix} 语言单元{unit_id}第{position}片段timing_basis无效。")
            if stage in {"production", "final"} and basis != "ACTUAL_READ":
                result.error(f"{prefix} 语言单元{unit_id}第{position}片段进入生产前必须使用ACTUAL_READ。")
            for field_name in ("mouth_state", "delivery_continuity"):
                if not str(segment.get(field_name) or "").strip():
                    result.error(f"{prefix} 语言单元{unit_id}第{position}片段缺少{field_name}。")
        unit_duration = as_number(unit.get("spoken_duration_seconds"))
        if unit_duration is not None and not close(total_spoken, unit_duration, tolerance=0.25):
            result.error(f"{prefix} 语言单元{unit_id}的片段时长合计与单元时长不一致。")

def validate_prompt(
    manifest_path: Path,
    group_label: str,
    group: dict[str, Any],
    shots: Any,
    result: Result,
) -> None:
    prefix = f"{manifest_path}:{group_label}"
    prompt = group.get("clean_prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        result.error(f"{prefix} clean_prompt不能为空。")
        return

    prompt_lines = [line.strip() for line in prompt.splitlines() if line.strip()]
    if not prompt_lines or prompt_lines[0] != GLOBAL_PROMPT_START:
        result.error(f"{prefix} 纯净提示词第一行必须是{GLOBAL_PROMPT_START}。")
    if any(marker in prompt for marker in BANNED_LANGUAGE_BLOCK_MARKERS):
        result.error(f"{prefix} 禁止使用独立计时的连续语言音轨总设定；语言必须写入逐镜。")
    try:
        negative_index = prompt_lines.index(GLOBAL_NEGATIVE_HEADER)
    except ValueError:
        negative_index = -1
        result.error(f"{prefix} 缺少{GLOBAL_NEGATIVE_HEADER}。")
    try:
        camera_index = prompt_lines.index(CAMERA_HEADER)
    except ValueError:
        camera_index = -1
        result.error(f"{prefix} 缺少{CAMERA_HEADER}。")
    bindings = group.get("prompt_asset_bindings")
    if not isinstance(bindings, list) or not bindings:
        result.error(f"{prefix} prompt_asset_bindings必须列出本组实际视频资产绑定。")
        bindings = []
    for binding in bindings:
        binding_text = str(binding or "").strip()
        if not binding_text or "\n" in binding_text or not binding_text.endswith("="):
            result.error(f"{prefix} 资产绑定必须是单行等号槽：{binding!r}")
            continue
        positions = [index for index, line in enumerate(prompt_lines) if line == binding_text]
        if len(positions) != 1:
            result.error(f"{prefix} 资产绑定必须在提示词中原样出现一次：{binding_text}")
            continue
        if camera_index >= 0 and positions[0] >= camera_index:
            result.error(f"{prefix} 资产绑定必须位于{CAMERA_HEADER}之前：{binding_text}")
        if negative_index >= 0 and positions[0] <= negative_index:
            result.error(f"{prefix} 资产绑定必须位于完整全局负面提示词之后：{binding_text}")
    normalized_bindings = [str(binding or "").strip() for binding in bindings]
    if camera_index >= 0 and normalized_bindings:
        binding_start = camera_index - len(normalized_bindings)
        if binding_start < 0 or prompt_lines[binding_start:camera_index] != normalized_bindings:
            result.error(f"{prefix} 资产绑定必须按登记顺序连续排列在{CAMERA_HEADER}正前方。")

    shot_blocks: list[str] = []
    prompt_intervals: list[tuple[float, float]] = []
    current_shot: list[str] | None = None
    for line in prompt.splitlines():
        stripped = line.strip()
        header_match = SHOT_HEADER_PATTERN.match(stripped)
        if header_match:
            if current_shot:
                shot_blocks.append("\n".join(current_shot))
            prompt_intervals.append(
                (float(header_match.group("start")), float(header_match.group("end")))
            )
            current_shot = [line]
            continue
        if current_shot is not None and SECTION_HEADER_PATTERN.match(stripped):
            shot_blocks.append("\n".join(current_shot))
            current_shot = None
        if current_shot is not None:
            current_shot.append(line)
    if current_shot:
        shot_blocks.append("\n".join(current_shot))

    if isinstance(shots, list):
        if len(prompt_intervals) != len(shots):
            result.error(
                f"{prefix} 纯净提示词含{len(prompt_intervals)}个计时镜头，"
                f"但shots登记{len(shots)}个；禁止把多个镜头合并成一个长时间段。"
            )
        else:
            for index, ((prompt_start, prompt_end), shot) in enumerate(
                zip(prompt_intervals, shots), start=1
            ):
                if not isinstance(shot, dict):
                    continue
                shot_start = as_number(shot.get("start_seconds"))
                shot_end = as_number(shot.get("end_seconds"))
                if (
                    shot_start is not None
                    and shot_end is not None
                    and (not close(prompt_start, shot_start) or not close(prompt_end, shot_end))
                ):
                    result.error(
                        f"{prefix} 第{index}个提示词镜头时间"
                        f"{prompt_start:g}～{prompt_end:g}秒与shots登记不一致。"
                    )

    detected_spoken_language = any(marker in prompt for marker in SPOKEN_MARKERS)
    declared_spoken_language = group.get("has_spoken_language") is True
    if detected_spoken_language and not declared_spoken_language:
        result.error(f"{prefix} 提示词含语言内容，但has_spoken_language未标记为true。")
    language_shot_count = 0
    if isinstance(shots, list) and len(shot_blocks) == len(shots):
        for index, (block, shot) in enumerate(zip(shot_blocks, shots), start=1):
            if not isinstance(shot, dict):
                continue
            segments = shot.get("spoken_segments")
            if not isinstance(segments, list):
                continue
            if not segments:
                if any(marker in block for marker in SPOKEN_MARKERS):
                    result.error(f"{prefix} 第{index}镜提示词含语言，但spoken_segments为空。")
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
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                text_value = str(segment.get("text") or "")
                quoted = any(
                    token in block
                    for token in (f"“{text_value}”", f'"{text_value}"', f"「{text_value}」", f"『{text_value}』")
                )
                if text_value and not quoted:
                    result.error(f"{prefix} 第{index}镜未原样写入语言片段：{text_value}")
                trigger = str(segment.get("start_trigger") or "").strip()
                if trigger and trigger not in block:
                    result.error(f"{prefix} 第{index}镜未原样写入语言开始触发：{trigger}")
                if segment.get("start_mode") == "ACTION_TRIGGER":
                    if not any(marker in block for marker in ("开始说：", "开始内心独白：", "开始旁白：", "开始画外音：", "开始系统语音：")):
                        result.error(f"{prefix} 第{index}镜第一语言片段必须明确开始说或开始内心独白。")
                elif segment.get("start_mode") == "CONTINUE_WITHOUT_RESTART":
                    if "无停顿承接上一镜" not in block:
                        result.error(f"{prefix} 第{index}镜后续语言片段必须写明无停顿承接上一镜。")
    if detected_spoken_language and language_shot_count == 0:
        result.error(f"{prefix} 语言内容必须写入带时间区间的小镜头内。")
    if declared_spoken_language and language_shot_count == 0:
        result.error(f"{prefix} has_spoken_language=true但未找到含语言内容的小镜头。")
    if language_shot_count > 0 and not declared_spoken_language:
        result.error(f"{prefix} spoken_segments非空，但has_spoken_language未标记为true。")

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

def validate_group_transitions(
    path: Path,
    groups: list[Any],
    config_model: str,
    result: Result,
) -> None:
    required_transition_fields = (
        "to_group_id",
        "from_shot_signature",
        "from_primary_subject",
        "from_framing",
        "to_shot_signature",
        "to_primary_subject",
        "to_framing",
        "transition_method",
        "continuity_anchor",
    )
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        group_label = str(group.get("shot_group_id") or f"分镜组{index + 1}")
        transition = group.get("exit_transition")
        if index == len(groups) - 1:
            if transition not in (None, {}):
                result.error(f"{path}:{group_label} 末组exit_transition必须为null。")
            continue

        next_group = groups[index + 1]
        if not isinstance(next_group, dict):
            continue
        if not isinstance(transition, dict):
            result.error(f"{path}:{group_label} 非末组必须填写exit_transition。")
            continue
        for field_name in required_transition_fields:
            if not str(transition.get(field_name) or "").strip():
                result.error(f"{path}:{group_label} exit_transition缺少{field_name}。")

        current_shots = group.get("shots") or []
        next_shots = next_group.get("shots") or []
        if not current_shots or not next_shots:
            continue
        last_shot = current_shots[-1] if isinstance(current_shots[-1], dict) else {}
        first_shot = next_shots[0] if isinstance(next_shots[0], dict) else {}
        expected_values = {
            "to_group_id": str(next_group.get("shot_group_id") or ""),
            "from_shot_signature": str(last_shot.get("shot_signature") or ""),
            "from_primary_subject": str(last_shot.get("primary_subject") or ""),
            "from_framing": str(last_shot.get("framing") or ""),
            "to_shot_signature": str(first_shot.get("shot_signature") or ""),
            "to_primary_subject": str(first_shot.get("primary_subject") or ""),
            "to_framing": str(first_shot.get("framing") or ""),
        }
        for field_name, expected in expected_values.items():
            if str(transition.get(field_name) or "") != expected:
                result.error(
                    f"{path}:{group_label} exit_transition.{field_name}必须与实际相邻镜头一致。"
                )

        from_signature = expected_values["from_shot_signature"]
        to_signature = expected_values["to_shot_signature"]
        if from_signature and from_signature == to_signature:
            result.error(f"{path}:{group_label} 尾镜与下一组首镜的镜头签名不得相同。")

        same_subject_closeups = (
            expected_values["from_primary_subject"]
            and expected_values["from_primary_subject"] == expected_values["to_primary_subject"]
            and "特写" in expected_values["from_framing"]
            and "特写" in expected_values["to_framing"]
        )
        if same_subject_closeups:
            approved = transition.get("match_cut_approved") is True
            reason = str(transition.get("match_cut_reason") or "").strip()
            basis = str(transition.get("match_cut_basis") or "").strip()
            if not (approved and reason and basis):
                result.error(
                    f"{path}:{group_label} 默认禁止同一人物特写硬接同一人物特写；"
                    "匹配剪辑例外必须填写批准、理由和可见匹配依据。"
                )

        # Transition evidence is validated above in exit_transition; generated content stays within the current group.

def validate_manifest(
    path: Path,
    config_model: str,
    episode_policy: dict[str, Any],
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
    if not str(manifest.get("duration_planning_reason") or "").strip():
        result.error(f"{path} 必须填写duration_planning_reason说明本集时长依据。")
    normal_min = as_number(episode_policy.get("normal_min_seconds"))
    if (
        planned is not None
        and normal_min is not None
        and planned < normal_min
        and not str(manifest.get("duration_deviation_reason") or "").strip()
    ):
        result.error(
            f"{path} 预计时长低于正常{normal_min:g}秒时必须填写duration_deviation_reason。"
        )
    if overhead is None or overhead < 0:
        result.error(f"{path} timeline_overhead_seconds必须是非负数。")
        overhead = 0.0

    groups = manifest.get("shot_groups")
    if not isinstance(groups, list) or not groups:
        result.error(f"{path} shot_groups必须是非空数组。")
        return

    preferred_group_count = as_number(episode_policy.get("preferred_max_shot_groups"))
    if (
        preferred_group_count is not None
        and len(groups) > int(preferred_group_count)
        and not str(manifest.get("shot_group_count_exception_reason") or "").strip()
    ):
        result.error(
            f"{path} 分镜组数量{len(groups)}超过优先上限{int(preferred_group_count)}，"
            "必须填写shot_group_count_exception_reason。"
        )

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

        shots = group.get("shots")
        has_spoken_language = group.get("has_spoken_language") is True
        validate_shot_timeline(
            path, group_label, duration, shots, has_spoken_language, result
        )
        validate_prompt(path, group_label, group, shots, result)
        if stage in {"production", "final"}:
            validate_assets_for_production(path, group_label, group.get("assets"), result)

    validate_language_units(path, groups, manifest.get("language_units"), stage, result)
    validate_group_transitions(path, groups, config_model, result)

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
        validate_manifest(manifest, model, config.get("episode") or {}, stage, result)
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
