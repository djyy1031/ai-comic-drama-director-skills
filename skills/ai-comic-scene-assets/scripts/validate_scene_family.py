#!/usr/bin/env python3
import json
import sys
from pathlib import Path


VALID_TYPES = {
    "SCENE_FAMILY_MASTER",
    "ZONE_MASTER",
    "CAMERA_VIEW",
    "STATE_VARIANT",
    "DETAIL_INSERT",
    "CONTINUITY_MAP",
}
VALID_EVIDENCE = {
    "EXPLICIT",
    "STORY_REQUIRED",
    "PLAUSIBLE_ENRICHMENT",
    "UNKNOWN_OR_FORBIDDEN",
}
VALID_WORKFLOW_MODES = {
    "LOCKED_PRODUCTION",
    "ONE_CLICK_DRAFT_SET",
}


def require(value, label, errors):
    if value in (None, "", [], {}):
        errors.append("缺少或为空：" + label)


def main():
    if len(sys.argv) != 2:
        print("用法：validate_scene_family.py <场景家族包.json>")
        return 2
    path = Path(sys.argv[1])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print("无法读取JSON：" + str(exc))
        return 2

    errors = []
    require(data.get("schema_version"), "schema_version", errors)
    require(data.get("project_name"), "project_name", errors)
    color_bible = data.get("series_color_bible") or {}
    require(color_bible, "series_color_bible", errors)
    color_version = color_bible.get("version")
    require(color_version, "series_color_bible.version", errors)
    require(color_bible.get("status"), "series_color_bible.status", errors)
    swatches = color_bible.get("swatches")
    require(swatches, "series_color_bible.swatches", errors)
    for si, swatch in enumerate(swatches or []):
        prefix = "series_color_bible.swatches[{}]".format(si)
        for key in ("name", "hex", "role", "prompt_terms"):
            require(swatch.get(key), prefix + "." + key, errors)
    grade_profile = color_bible.get("grade_profile") or {}
    require(grade_profile, "series_color_bible.grade_profile", errors)
    for key in (
        "saturation",
        "contrast",
        "black_level",
        "highlight_temperature",
        "shadow_tint",
    ):
        require(grade_profile.get(key), "series_color_bible.grade_profile." + key, errors)
    families = data.get("scene_families")
    require(families, "scene_families", errors)
    all_ids = set()

    for fi, family in enumerate(families or []):
        prefix = "scene_families[{}]".format(fi)
        for key in (
            "asset_id",
            "canonical_name",
            "version",
            "visual_dna",
            "spatial_model",
            "anchor_strategy",
            "base_environment_state",
        ):
            require(family.get(key), prefix + "." + key, errors)
        base_environment = family.get("base_environment_state") or {}
        require(base_environment.get("state_id"), prefix + ".base_environment_state.state_id", errors)
        require(base_environment.get("weather"), prefix + ".base_environment_state.weather", errors)
        require(base_environment.get("source_basis"), prefix + ".base_environment_state.source_basis", errors)
        if base_environment.get("time") != "DAY":
            errors.append(prefix + ".base_environment_state.time 必须为 DAY（白天母资产）")
        family_id = family.get("asset_id")
        if family_id in all_ids:
            errors.append("重复 asset_id：" + str(family_id))
        all_ids.add(family_id)
        for ei, item in enumerate(family.get("evidence", [])):
            if item.get("classification") not in VALID_EVIDENCE:
                errors.append("{}.evidence[{}] 分类无效".format(prefix, ei))
            require(item.get("fact"), "{}.evidence[{}].fact".format(prefix, ei), errors)
        for asset in family.get("assets", []):
            asset_id = asset.get("asset_id")
            if asset_id in all_ids:
                errors.append("重复 asset_id：" + str(asset_id))
            all_ids.add(asset_id)

    for fi, family in enumerate(families or []):
        for ai, asset in enumerate(family.get("assets", [])):
            prefix = "scene_families[{}].assets[{}]".format(fi, ai)
            for key in ("asset_id", "canonical_name", "version", "parent_asset_id", "parent_version"):
                require(asset.get(key), prefix + "." + key, errors)
            require(asset.get("color_bible_version"), prefix + ".color_bible_version", errors)
            require(asset.get("environment_state_id"), prefix + ".environment_state_id", errors)
            if color_version and asset.get("color_bible_version") != color_version:
                errors.append(prefix + ".color_bible_version 与全剧色卡版本不一致")
            base_state_id = (family.get("base_environment_state") or {}).get("state_id")
            if base_state_id and asset.get("environment_state_id") != base_state_id:
                errors.append(prefix + ".environment_state_id 必须继承白天母资产状态")
            require(
                asset.get("scene_content_layers"),
                prefix + ".scene_content_layers",
                errors,
            )
            if asset.get("asset_type") not in VALID_TYPES:
                errors.append(prefix + ".asset_type 无效")
            parent = asset.get("parent_asset_id")
            if parent and parent not in all_ids:
                errors.append(prefix + ".parent_asset_id 不存在：" + str(parent))
            if asset.get("asset_type") != "CONTINUITY_MAP":
                require(asset.get("prompt"), prefix + ".prompt", errors)

        for bi, batch in enumerate(family.get("generation_batches", [])):
            prefix = "scene_families[{}].generation_batches[{}]".format(fi, bi)
            for key in (
                "batch_id",
                "scene_family_id",
                "visual_dna_version",
                "state_version",
                "shared_scene_brief",
                "asset_ids",
            ):
                require(batch.get(key), prefix + "." + key, errors)
            if batch.get("scene_family_id") != family.get("asset_id"):
                errors.append(prefix + ".scene_family_id 与所属场景家族不一致")
            if batch.get("generation_mode") != "SEPARATE_IMAGES":
                errors.append(prefix + ".generation_mode 必须为 SEPARATE_IMAGES")
            workflow_mode = batch.get("workflow_mode")
            if workflow_mode not in VALID_WORKFLOW_MODES:
                errors.append(prefix + ".workflow_mode 无效")
            if batch.get("forbid_composite") is not True:
                errors.append(prefix + ".forbid_composite 必须为 true")
            max_outputs = batch.get("max_outputs")
            if not isinstance(max_outputs, int) or not 1 <= max_outputs <= 10:
                errors.append(prefix + ".max_outputs 必须为1到10")
            batch_asset_ids = batch.get("asset_ids") or []
            if isinstance(max_outputs, int) and len(batch_asset_ids) > max_outputs:
                errors.append(prefix + ".asset_ids 数量超过 max_outputs")
            if len(batch_asset_ids) != len(set(batch_asset_ids)):
                errors.append(prefix + ".asset_ids 存在重复")
            for asset_id in batch_asset_ids:
                if asset_id not in all_ids:
                    errors.append(prefix + ".asset_id 不存在：" + str(asset_id))
            anchor_asset_ids = batch.get("anchor_asset_ids") or []
            for asset_id in anchor_asset_ids:
                if asset_id not in all_ids:
                    errors.append(prefix + ".anchor_asset_id 不存在：" + str(asset_id))
            if workflow_mode == "LOCKED_PRODUCTION" and not anchor_asset_ids:
                errors.append(prefix + ".LOCKED_PRODUCTION 缺少 anchor_asset_ids")
            if workflow_mode == "ONE_CLICK_DRAFT_SET" and batch.get("production_ready") is True:
                errors.append(prefix + ".ONE_CLICK_DRAFT_SET 不能直接标记 production_ready")

        for vi, variant in enumerate(family.get("environment_variants", [])):
            prefix = "scene_families[{}].environment_variants[{}]".format(fi, vi)
            for key in (
                "variant_id",
                "reference_asset_id",
                "target_time",
                "target_weather",
                "episode_usage",
                "source_evidence",
                "allowed_environment_delta",
                "locked_unchanged",
                "color_bible_version",
                "variant_prompt",
                "status",
            ):
                require(variant.get(key), prefix + "." + key, errors)
            reference_asset_id = variant.get("reference_asset_id")
            if reference_asset_id and reference_asset_id not in all_ids:
                errors.append(prefix + ".reference_asset_id 不存在：" + str(reference_asset_id))
            if color_version and variant.get("color_bible_version") != color_version:
                errors.append(prefix + ".color_bible_version 与全剧色卡版本不一致")
            base_environment = family.get("base_environment_state") or {}
            if (
                variant.get("target_time") == base_environment.get("time")
                and variant.get("target_weather") == base_environment.get("weather")
            ):
                errors.append(prefix + " 与白天母资产环境相同，无需重复建立变体")

    if errors:
        print("\n".join("- " + item for item in errors))
        return 1
    print("场景家族包校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
