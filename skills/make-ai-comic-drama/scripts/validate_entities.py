#!/usr/bin/env python3
"""检查固定编号和互相引用是否正确。"""

from __future__ import annotations

import re
from typing import Any

from _validation_common import Issue, issue, run_cli


ID_RULES = {
    "project_id": r"PRJ-\d{3,}", "episode_id": r"EP-\d{3,}", "scene_id": r"SC-\d{3,}",
    "shot_id": r"SH-\d{3,}", "segment_id": r"SEG-\d{3,}", "character_id": r"CHR-\d{3,}",
    "location_id": r"LOC-\d{3,}", "prop_id": r"PROP-\d{3,}", "costume_id": r"CST-\d{3,}",
    "reference_id": r"REF-\d{3,}",
}


def valid_id(field: str, value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(ID_RULES[field], value) is not None


def collect(items: Any, field: str, path: str, issues: list[Issue]) -> set[str]:
    found: set[str] = set()
    if not isinstance(items, list):
        issues.append(issue("error", "entity.array", f"{path} 必须是列表。", path))
        return found
    for index, item in enumerate(items):
        item_path = f"{path}[{index}].{field}"
        value = item.get(field) if isinstance(item, dict) else None
        if not valid_id(field, value):
            issues.append(issue("error", "entity.id_format", f"编号格式错误或没有填写 {field}：{value!r}。", item_path))
        elif value in found:
            issues.append(issue("error", "entity.duplicate", f"编号 {value} 重复使用。", item_path))
        else:
            found.add(value)
    return found


def require_refs(values: Any, known: set[str], label: str, path: str, issues: list[Issue]) -> None:
    if values is None:
        return
    if not isinstance(values, list):
        issues.append(issue("error", "entity.reference_array", f"{label} 必须是列表。", path))
        return
    for value in values:
        if value not in known:
            issues.append(issue("error", "entity.missing_reference", f"找不到被引用的 {label}：{value!r}。", path))


def validate(data: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    for field in ("project_id", "episode_id"):
        if not valid_id(field, data.get(field)):
            issues.append(issue("error", "entity.root_id", f"{field} 没有填写或格式错误。", field))
    entities = data.get("entities", {})
    if not isinstance(entities, dict):
        return issues + [issue("error", "entity.object", "人物、场景、道具等资料必须是完整记录。", "entities")]
    characters = collect(entities.get("characters", []), "character_id", "entities.characters", issues)
    locations = collect(entities.get("locations", []), "location_id", "entities.locations", issues)
    props = collect(entities.get("props", []), "prop_id", "entities.props", issues)
    costumes = collect(entities.get("costumes", []), "costume_id", "entities.costumes", issues)
    references = collect(entities.get("references", []), "reference_id", "entities.references", issues)
    scenes = collect(data.get("scenes", []), "scene_id", "scenes", issues)
    shots = collect(data.get("shots", []), "shot_id", "shots", issues)
    segments = collect(data.get("segments", []), "segment_id", "segments", issues)

    for index, costume in enumerate(entities.get("costumes", [])):
        if isinstance(costume, dict) and costume.get("character_id") not in characters:
            issues.append(issue("error", "entity.costume_owner", f"服装对应的人物编号不存在：{costume.get('character_id')!r}。", f"entities.costumes[{index}].character_id"))
    for index, scene in enumerate(data.get("scenes", [])):
        if isinstance(scene, dict) and scene.get("location_id") not in locations:
            issues.append(issue("error", "entity.scene_location", f"场次对应的场景编号不存在：{scene.get('location_id')!r}。", f"scenes[{index}].location_id"))
    for index, shot in enumerate(data.get("shots", [])):
        if not isinstance(shot, dict):
            continue
        path = f"shots[{index}]"
        if shot.get("scene_id") not in scenes:
            issues.append(issue("error", "entity.shot_scene", f"镜头对应的场次编号不存在：{shot.get('scene_id')!r}。", f"{path}.scene_id"))
        if shot.get("location_id") not in locations:
            issues.append(issue("error", "entity.shot_location", f"镜头对应的场景编号不存在：{shot.get('location_id')!r}。", f"{path}.location_id"))
        require_refs(shot.get("character_ids", []), characters, "character_id", f"{path}.character_ids", issues)
        require_refs(shot.get("prop_ids", []), props, "prop_id", f"{path}.prop_ids", issues)
        require_refs(shot.get("costume_ids", []), costumes, "costume_id", f"{path}.costume_ids", issues)
        require_refs(shot.get("reference_ids", []), references, "reference_id", f"{path}.reference_ids", issues)
    for index, segment in enumerate(data.get("segments", [])):
        if not isinstance(segment, dict):
            continue
        path = f"segments[{index}]"
        require_refs(segment.get("shot_ids", []), shots, "shot_id", f"{path}.shot_ids", issues)
        require_refs(segment.get("character_reference_ids", []), references, "reference_id", f"{path}.character_reference_ids", issues)
        require_refs(segment.get("scene_reference_ids", []), references, "reference_id", f"{path}.scene_reference_ids", issues)
    return issues


if __name__ == "__main__":
    run_cli("编号和引用检查", validate)
