#!/usr/bin/env python3
import json
import sys
from pathlib import Path


TOP = ["规范版本", "来源", "资产目录", "场景空间锚定", "角色身份锚定", "道具状态锚定", "声音绑定", "剧本资产映射", "最终状态"]
ASSET_TYPES = {"场景", "角色", "道具", "声音"}
CHECK_STATES = {"VERIFIED", "UNVERIFIED", "MISSING", "CONFLICT"}
RESULT_STATES = {"PASS", "ERROR"}
COORDINATES = {"REFERENCE_VIEW_ANCHORED", "WORLD_MAP_VERIFIED"}


def nonempty(value):
    return bool(str(value or "").strip())


def validate(data):
    errors = []
    for key in TOP:
        if key not in data:
            errors.append(f"缺少顶层字段：{key}")

    assets = data.get("资产目录")
    if not isinstance(assets, list) or not assets:
        errors.append("资产目录必须是非空数组")
        assets = []
    names = set()
    statuses = {}
    types = {}
    for index, asset in enumerate(assets, 1):
        if not isinstance(asset, dict):
            errors.append(f"第{index}个资产必须是对象")
            continue
        for key in ["标准名称", "类型", "文件", "检查状态", "证据方式", "可见或可听证据", "不可确认"]:
            if key not in asset:
                errors.append(f"第{index}个资产缺少：{key}")
        name = str(asset.get("标准名称") or "").strip()
        if not name or name in names:
            errors.append(f"第{index}个资产标准名称为空或重复")
        names.add(name)
        asset_type = asset.get("类型")
        if asset_type not in ASSET_TYPES:
            errors.append(f"资产{name}类型无效")
        status = asset.get("检查状态")
        if status not in CHECK_STATES:
            errors.append(f"资产{name}检查状态无效")
        if status == "VERIFIED":
            if not nonempty(asset.get("文件")) or not nonempty(asset.get("证据方式")):
                errors.append(f"已核验资产{name}必须填写文件和证据方式")
            if not isinstance(asset.get("可见或可听证据"), list) or not asset.get("可见或可听证据"):
                errors.append(f"已核验资产{name}必须包含实际证据")
        statuses[name] = status
        types[name] = asset_type

    scenes = data.get("场景空间锚定")
    if not isinstance(scenes, list):
        errors.append("场景空间锚定必须是数组")
        scenes = []
    scene_names = set()
    required_scene = ["场景标准名称", "参考资产", "坐标表达方式", "参考视角说明", "固定结构", "固定陈设", "出入口", "光源", "遮挡", "可用人物区域", "可用摄影机区域", "禁止穿越区域", "不可确认区域", "冲突", "状态"]
    for index, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            errors.append(f"第{index}个场景锚定必须是对象")
            continue
        for key in required_scene:
            if key not in scene:
                errors.append(f"第{index}个场景锚定缺少：{key}")
        name = str(scene.get("场景标准名称") or "").strip()
        scene_names.add(name)
        if name not in names or types.get(name) != "场景":
            errors.append(f"场景锚定{name}未对应场景资产")
        refs = scene.get("参考资产")
        if not isinstance(refs, list) or not refs:
            errors.append(f"场景{name}必须引用实际场景资产")
        elif any(ref not in names for ref in refs):
            errors.append(f"场景{name}引用了目录外资产")
        if scene.get("坐标表达方式") not in COORDINATES:
            errors.append(f"场景{name}坐标表达方式无效")
        if not nonempty(scene.get("参考视角说明")):
            errors.append(f"场景{name}必须说明参考视角")
        if scene.get("状态") not in RESULT_STATES:
            errors.append(f"场景{name}状态无效")
        if scene.get("状态") == "PASS" and scene.get("冲突"):
            errors.append(f"场景{name}存在冲突时不能标记PASS")

    mappings = data.get("剧本资产映射")
    if not isinstance(mappings, list) or not mappings:
        errors.append("剧本资产映射必须是非空数组")
        mappings = []
    for index, mapping in enumerate(mappings, 1):
        if not isinstance(mapping, dict):
            errors.append(f"第{index}条剧本资产映射必须是对象")
            continue
        for key in ["来源锚点", "所需资产", "未解决", "状态"]:
            if key not in mapping:
                errors.append(f"第{index}条剧本资产映射缺少：{key}")
        required = mapping.get("所需资产")
        if not isinstance(required, list) or not required:
            errors.append(f"第{index}条映射的所需资产必须是非空数组")
            required = []
        for name in required:
            if name not in names:
                errors.append(f"第{index}条映射引用目录外资产：{name}")
            elif statuses.get(name) != "VERIFIED":
                errors.append(f"第{index}条映射所需资产未核验：{name}")
        if mapping.get("状态") not in RESULT_STATES:
            errors.append(f"第{index}条映射状态无效")
        if mapping.get("状态") == "PASS" and mapping.get("未解决"):
            errors.append(f"第{index}条映射存在未解决项时不能标记PASS")

    final = data.get("最终状态")
    if final not in RESULT_STATES:
        errors.append("最终状态必须是PASS或ERROR")
    if final == "PASS":
        required_names = {
            name
            for mapping in mappings if isinstance(mapping, dict)
            for name in mapping.get("所需资产", []) if isinstance(mapping.get("所需资产"), list)
        }
        if any(statuses.get(name) != "VERIFIED" for name in required_names):
            errors.append("当前映射所需资产未核验时最终状态不能为PASS")
        if any(isinstance(scene, dict) and scene.get("状态") != "PASS" for scene in scenes):
            errors.append("存在未通过场景锚定时最终状态不能为PASS")
        if any(isinstance(mapping, dict) and mapping.get("状态") != "PASS" for mapping in mappings):
            errors.append("存在未通过剧本映射时最终状态不能为PASS")
    return errors


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print("用法：validate_asset_grounding.py <资产锚定包.json>")
        return 2
    try:
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(f"读取失败：{exc}")
        return 2
    errors = validate(data)
    if errors:
        print("校验失败：")
        for error in errors:
            print(f"- {error}")
        return 1
    print("校验通过：成品资产已完成分镜锚定。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
