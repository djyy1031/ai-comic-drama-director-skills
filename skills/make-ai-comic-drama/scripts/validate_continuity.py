#!/usr/bin/env python3
"""检查人物、场景和道具在前后镜头是否接得上。"""

from __future__ import annotations

from typing import Any

from _validation_common import Issue, issue, run_cli


def compare_state(before: Any, after: Any, path: str, issues: list[Issue]) -> None:
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            if key not in before or key not in after:
                issues.append(issue("error", "continuity.missing_field", f"前后镜头只有一边填写了状态 {key!r}。", f"{path}.{key}"))
            else:
                compare_state(before[key], after[key], f"{path}.{key}", issues)
    elif before != after:
        issues.append(issue("error", "continuity.mismatch", f"上一镜结束状态 {before!r}，接不上下一镜开始状态 {after!r}。", path))


def validate_state_coverage(shot: dict[str, Any], index: int, issues: list[Issue]) -> None:
    for state_name in ("start_state", "end_state"):
        state = shot.get(state_name)
        path = f"shots[{index}].{state_name}"
        if not isinstance(state, dict):
            issues.append(issue("error", "continuity.state_object", f"{state_name} 必须填写完整状态。", path))
            continue
        characters = state.get("characters")
        props = state.get("props")
        location = state.get("location")
        if not isinstance(characters, dict) or any(entity_id not in characters for entity_id in shot.get("character_ids", [])):
            issues.append(issue("error", "continuity.character_coverage", "状态记录必须包含这一镜出现的每个人物。", f"{path}.characters"))
        if not isinstance(props, dict) or any(entity_id not in props for entity_id in shot.get("prop_ids", [])):
            issues.append(issue("error", "continuity.prop_coverage", "状态记录必须包含这一镜使用的每个重要道具。", f"{path}.props"))
        if not isinstance(location, dict) or location.get("location_id") != shot.get("location_id"):
            issues.append(issue("error", "continuity.location_coverage", "状态记录里的场景编号必须和镜头场景一致。", f"{path}.location"))


def validate(data: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    shots = data.get("shots", [])
    if not isinstance(shots, list) or not shots:
        return [issue("error", "continuity.no_shots", "镜头列表不能为空。", "shots")]
    usable: list[tuple[int, dict[str, Any]]] = []
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            issues.append(issue("error", "continuity.shot_type", "每个镜头必须是一条完整记录。", f"shots[{index}]"))
            continue
        validate_state_coverage(shot, index, issues)
        usable.append((index, shot))
    usable.sort(key=lambda row: row[1].get("timeline_in", float("inf")))
    for (left_index, left), (right_index, right) in zip(usable, usable[1:]):
        if right.get("continuity_break", False):
            if not str(right.get("continuity_reason", "")).strip():
                issues.append(issue("error", "continuity.break_reason", "如果前后状态故意不接，必须写明换场、时间跳转或其他原因。", f"shots[{right_index}]"))
            continue
        if left.get("scene_id") != right.get("scene_id"):
            continue
        before, after = left.get("end_state"), right.get("start_state")
        if isinstance(before, dict) and isinstance(after, dict):
            compare_state(before, after, f"cut:{left.get('shot_id','?')}->{right.get('shot_id','?')}", issues)
    return issues


if __name__ == "__main__":
    run_cli("前后统一检查", validate)
