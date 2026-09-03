#!/usr/bin/env python3
import json
import sys
from pathlib import Path


REQUIRED_TOP = ["规范版本", "来源锚点", "不可修改剧情事实", "不可修改原文台词", "场景诊断", "调用模块", "连续性状态", "镜头设计", "模型适配提醒"]
REQUIRED_DIAGNOSIS = ["主场景类型", "主要剧情功能", "战斗阶段", "情绪轨迹", "视觉优先级", "不可切断单元", "连续性风险"]
REQUIRED_SHOT = ["顺序", "类型", "镜头功能", "存在理由", "主体与变化", "摄影机", "角色表演进程", "入镜状态", "出镜状态"]


def validate(data):
    errors = []
    for key in REQUIRED_TOP:
        if key not in data:
            errors.append(f"缺少顶层字段：{key}")
    diagnosis = data.get("场景诊断", {})
    if not isinstance(diagnosis, dict):
        errors.append("场景诊断必须是对象")
    else:
        for key in REQUIRED_DIAGNOSIS:
            if key not in diagnosis:
                errors.append(f"场景诊断缺少：{key}")
    shots = data.get("镜头设计")
    if not isinstance(shots, list) or not shots:
        errors.append("镜头设计必须是非空数组")
    else:
        seen = set()
        for index, shot in enumerate(shots, start=1):
            if not isinstance(shot, dict):
                errors.append(f"第{index}个镜头必须是对象")
                continue
            for key in REQUIRED_SHOT:
                if key not in shot:
                    errors.append(f"第{index}个镜头缺少：{key}")
            order = shot.get("顺序")
            if order in seen:
                errors.append(f"镜头顺序重复：{order}")
            seen.add(order)
            if not str(shot.get("镜头功能", "")).strip():
                errors.append(f"第{index}个镜头的镜头功能为空")
            if not str(shot.get("存在理由", "")).strip():
                errors.append(f"第{index}个镜头的存在理由为空")
    continuity = data.get("连续性状态", {})
    if isinstance(continuity, dict):
        for key in ["入组状态", "出组状态", "跨组衔接依据"]:
            if key not in continuity:
                errors.append(f"连续性状态缺少：{key}")
    elif "连续性状态" in data:
        errors.append("连续性状态必须是对象")
    return errors


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print("用法：validate_director_representation.py <导演镜头表示.json>")
        return 2
    path = Path(sys.argv[1])
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(f"读取失败：{exc}")
        return 2
    errors = validate(data)
    if errors:
        print("校验失败：")
        for error in errors:
            print(f"- {error}")
        return 1
    print("校验通过：导演镜头表示结构完整。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
