#!/usr/bin/env python3
"""检查镜头时间和整集总时长。"""

from __future__ import annotations

from typing import Any

from _validation_common import Issue, is_number, issue, run_cli


DEFAULT_MAX_SHOT_SECONDS = 6.0


def validate(data: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    shots = data.get("shots", [])
    tolerance = data.get("timeline_tolerance_seconds", 0.01)
    if not is_number(tolerance) or tolerance < 0:
        issues.append(issue("error", "timeline.tolerance", "时间误差范围必须是大于或等于 0 的数字。"))
        tolerance = 0.01
    if not isinstance(shots, list) or not shots:
        return [issue("error", "timeline.no_shots", "镜头列表不能为空。", "shots")]

    valid: list[tuple[int, dict[str, Any], float, float, float]] = []
    for index, shot in enumerate(shots):
        path = f"shots[{index}]"
        if not isinstance(shot, dict):
            issues.append(issue("error", "timeline.shot_type", "每个镜头必须是一条完整记录。", path))
            continue
        start, end, duration = shot.get("timeline_in"), shot.get("timeline_out"), shot.get("duration")
        if not all(is_number(value) for value in (start, end, duration)):
            issues.append(issue("error", "timeline.numeric", "开始秒数、结束秒数和持续时长必须是有效数字。", path))
            continue
        if start < 0 or end <= start or duration <= 0:
            issues.append(issue("error", "timeline.bounds", "开始秒数不能小于 0，结束秒数必须大于开始秒数，持续时长必须大于 0。", path))
        if abs((end - start) - duration) > tolerance:
            issues.append(issue("error", "timeline.duration_mismatch", f"填写的持续时长 {duration} 秒，与结束减开始得到的 {end-start:.6f} 秒不一致。", path))
        if duration > DEFAULT_MAX_SHOT_SECONDS:
            approved = shot.get("long_take_approved") is True
            reason = str(shot.get("long_take_reason") or "").strip()
            if not approved or not reason:
                issues.append(
                    issue(
                        "error",
                        "timeline.long_shot_unapproved",
                        f"单镜时长 {duration} 秒超过普通镜头6秒上限；只有用户或原文明示一镜到底时，才能同时填写long_take_approved=true和long_take_reason。",
                        path,
                    )
                )
        dialogue_duration = shot.get("dialogue_duration")
        if dialogue_duration is not None and (not is_number(dialogue_duration) or dialogue_duration < 0 or dialogue_duration - duration > tolerance):
            issues.append(issue("error", "timeline.dialogue_overflow", "实测对白时长不能小于 0，也不能超过镜头能容纳的时长。", path))
        valid.append((index, shot, float(start), float(end), float(duration)))

    ordered = sorted(valid, key=lambda row: (row[2], row[3]))
    if [row[0] for row in ordered] != [row[0] for row in valid]:
        issues.append(issue("error", "timeline.order", "镜头必须按时间先后顺序排列。", "shots"))
    if ordered and abs(ordered[0][2]) > tolerance:
        issues.append(issue("error", "timeline.start", "第一个镜头必须从 0 秒开始。", f"shots[{ordered[0][0]}]"))
    for previous, current in zip(ordered, ordered[1:]):
        gap = current[2] - previous[3]
        if gap > tolerance and not previous[1].get("allow_gap_after", False):
            issues.append(issue("error", "timeline.gap", f"镜头 {previous[1].get('shot_id', '?')} 后面出现了没有说明的 {gap:.6f} 秒空白。", f"shots[{current[0]}]"))
        if gap < -tolerance and not previous[1].get("allow_overlap_with_next", False):
            issues.append(issue("error", "timeline.overlap", f"镜头 {previous[1].get('shot_id', '?')} 后面出现了没有说明的 {-gap:.6f} 秒重叠。", f"shots[{current[0]}]"))

    episode_total = data.get("episode_duration_seconds", data.get("episode_target_seconds"))
    if not is_number(episode_total) or episode_total <= 0:
        issues.append(issue("error", "timeline.episode_total", "必须提供大于 0 的整集时长。"))
    else:
        summed = sum(row[4] for row in ordered)
        if abs(summed - episode_total) > tolerance:
            issues.append(issue("error", "timeline.total_mismatch", f"所有镜头相加是 {summed:.6f} 秒，整集要求是 {episode_total:.6f} 秒。"))
        if ordered and abs(ordered[-1][3] - episode_total) > tolerance:
            issues.append(issue("error", "timeline.end_mismatch", f"最后一个镜头结束在 {ordered[-1][3]:.6f} 秒，整集应结束在 {episode_total:.6f} 秒。"))
    return issues


if __name__ == "__main__":
    run_cli("时间轴检查", validate)
