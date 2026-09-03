#!/usr/bin/env python3
"""检查每次视频生成任务是否超过模型实测上限。"""

from __future__ import annotations

from collections import Counter
from typing import Any

from _validation_common import Issue, is_number, issue, run_cli


def validate(data: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    profile = data.get("model_profile")
    if not isinstance(profile, dict):
        return [issue("error", "limits.profile", "必须填写视频模型的实测能力。", "model_profile")]
    numeric_limits = ("segment_max_seconds", "max_shots_per_segment", "identity_reference_limit", "scene_reference_limit")
    for field in numeric_limits:
        if not is_number(profile.get(field)) or profile[field] < 0:
            issues.append(issue("error", "limits.profile_value", f"模型能力参数 {field} 必须是大于或等于 0 的有效数字。", f"model_profile.{field}"))
    if not isinstance(profile.get("supports_multi_shot"), bool):
        issues.append(issue("error", "limits.multi_shot_flag", "必须明确模型是否支持一次生成多个镜头。", "model_profile.supports_multi_shot"))
    if issues:
        return issues

    shots = data.get("shots", [])
    segments = data.get("segments", [])
    shot_map = {shot.get("shot_id"): shot for shot in shots if isinstance(shot, dict)} if isinstance(shots, list) else {}
    if not isinstance(segments, list) or not segments:
        return [issue("error", "limits.no_segments", "视频生成段列表不能为空。", "segments")]
    usage: Counter[str] = Counter()
    tolerance = data.get("timeline_tolerance_seconds", 0.01)
    tolerance = tolerance if is_number(tolerance) and tolerance >= 0 else 0.01
    for index, segment in enumerate(segments):
        path = f"segments[{index}]"
        if not isinstance(segment, dict):
            issues.append(issue("error", "limits.segment_type", "每个视频生成段必须是一条完整记录。", path))
            continue
        duration = segment.get("duration")
        shot_ids = segment.get("shot_ids")
        character_refs = segment.get("character_reference_ids", [])
        scene_refs = segment.get("scene_reference_ids", [])
        if not is_number(duration) or duration <= 0:
            issues.append(issue("error", "limits.duration", "生成段时长必须大于 0。", f"{path}.duration"))
        elif duration - profile["segment_max_seconds"] > tolerance:
            issues.append(issue("error", "limits.duration_exceeded", f"生成段 {duration} 秒，超过模型实测上限 {profile['segment_max_seconds']} 秒。", f"{path}.duration"))
        if not isinstance(shot_ids, list) or not shot_ids:
            issues.append(issue("error", "limits.shot_ids", "生成段必须包含至少一个镜头编号。", f"{path}.shot_ids"))
            continue
        usage.update(shot_ids)
        if len(shot_ids) > profile["max_shots_per_segment"]:
            issues.append(issue("error", "limits.shot_count", f"这个生成段有 {len(shot_ids)} 个镜头，模型实测最多支持 {profile['max_shots_per_segment']} 个。", f"{path}.shot_ids"))
        if len(shot_ids) > 1 and not profile["supports_multi_shot"]:
            issues.append(issue("error", "limits.multi_shot_unsupported", "模型不支持一次生成多个镜头，请拆开。", f"{path}.shot_ids"))
        if isinstance(duration, (int, float)):
            known = [shot_map[shot_id].get("duration") for shot_id in shot_ids if shot_id in shot_map]
            if len(known) == len(shot_ids) and all(is_number(value) for value in known) and abs(sum(known) - duration) > tolerance:
                issues.append(issue("error", "limits.segment_sum", f"段内镜头相加是 {sum(known):.6f} 秒，与生成段填写的 {duration:.6f} 秒不一致。", path))
        if not isinstance(character_refs, list) or len(set(character_refs)) != len(character_refs):
            issues.append(issue("error", "limits.character_refs", "人物参考图编号不能重复。", f"{path}.character_reference_ids"))
        elif len(character_refs) > profile["identity_reference_limit"]:
            issues.append(issue("error", "limits.character_refs_exceeded", "人物参考图数量超过模型实测上限。", f"{path}.character_reference_ids"))
        if not isinstance(scene_refs, list) or len(set(scene_refs)) != len(scene_refs):
            issues.append(issue("error", "limits.scene_refs", "场景参考图编号不能重复。", f"{path}.scene_reference_ids"))
        elif len(scene_refs) > profile["scene_reference_limit"]:
            issues.append(issue("error", "limits.scene_refs_exceeded", "场景参考图数量超过模型实测上限。", f"{path}.scene_reference_ids"))
        if not str(segment.get("fallback", "")).strip():
            issues.append(issue("error", "limits.fallback", "每个生成段都要写失败时怎样简化。", f"{path}.fallback"))

    for shot_id in shot_map:
        if usage[shot_id] == 0:
            issues.append(issue("error", "limits.unassigned_shot", f"镜头 {shot_id} 没有分配到任何生成段。"))
        elif usage[shot_id] > 1:
            issues.append(issue("error", "limits.duplicate_assignment", f"镜头 {shot_id} 被重复分配到 {usage[shot_id]} 个生成段。"))
    return issues


if __name__ == "__main__":
    run_cli("生成段上限检查", validate)
