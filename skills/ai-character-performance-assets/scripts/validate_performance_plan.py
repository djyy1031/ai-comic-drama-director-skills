#!/usr/bin/env python3
import json
import sys
from pathlib import Path


REQUIRED_TOP = [
    "规范版本", "来源锚点", "不可修改剧情事实", "不可修改原文台词",
    "在场角色标准名称", "场景功能", "角色场景计划", "语言单元",
    "表演节拍", "状态继承", "风险与待确认",
]
REQUIRED_CHARACTER = [
    "角色标准名称", "当前目标", "阻碍", "失败代价", "潜台词",
    "身体基线", "实际任务", "地位起点", "地位终点", "听与眼神规则",
]
REQUIRED_UNIT = [
    "语言单元ID", "类型", "说话人", "完整原文", "所属分镜组", "开始触发",
    "时长依据", "语言时长秒", "默认不跨组", "连续要求", "建议片段", "逐句表演",
]
REQUIRED_SEGMENT = ["片段顺序", "原文片段", "开始方式", "开始触发", "声音状态", "表演承接"]
LANGUAGE_KINDS = {"对白", "内心独白", "旁白", "画外音", "系统语音"}
TIMING_BASES = {"ACTUAL_READ", "ESTIMATED"}
REQUIRED_BEAT = [
    "顺序", "触发事实", "当前策略", "主动角色", "目标对象", "语言单元ID",
    "可见行为", "听者反应", "身体任务", "距离或地位变化",
    "入节拍状态", "出节拍状态", "建议承载镜头功能",
]


def nonempty(value):
    return bool(str(value or "").strip())


def validate(data):
    errors = []
    for key in REQUIRED_TOP:
        if key not in data:
            errors.append(f"缺少顶层字段：{key}")

    names = data.get("在场角色标准名称")
    if not isinstance(names, list) or not names:
        errors.append("在场角色标准名称必须是非空数组")
        names = []
    else:
        normalized = [str(name).strip() for name in names]
        if any(not name for name in normalized):
            errors.append("在场角色标准名称不能包含空值")
        if len(set(normalized)) != len(normalized):
            errors.append("在场角色标准名称不能重复")
        names = normalized

    if not nonempty(data.get("场景功能")):
        errors.append("场景功能不能为空")

    plans = data.get("角色场景计划")
    planned_names = set()
    if not isinstance(plans, list) or not plans:
        errors.append("角色场景计划必须是非空数组")
    else:
        for index, plan in enumerate(plans, start=1):
            if not isinstance(plan, dict):
                errors.append(f"第{index}条角色场景计划必须是对象")
                continue
            for key in REQUIRED_CHARACTER:
                if key not in plan:
                    errors.append(f"第{index}条角色场景计划缺少：{key}")
                elif not nonempty(plan.get(key)):
                    errors.append(f"第{index}条角色场景计划的{key}不能为空")
            name = str(plan.get("角色标准名称") or "").strip()
            if name and name not in names:
                errors.append(f"角色场景计划出现白名单外角色：{name}")
            if name in planned_names:
                errors.append(f"角色场景计划重复：{name}")
            planned_names.add(name)
        missing_plans = set(names) - planned_names
        for name in sorted(missing_plans):
            errors.append(f"在场角色缺少表演计划：{name}；背景人物也不能木站")

    immutable_dialogue = data.get("不可修改原文台词")
    immutable_pairs = set()
    if isinstance(immutable_dialogue, list):
        for item in immutable_dialogue:
            if isinstance(item, dict):
                immutable_pairs.add((str(item.get("说话人") or "").strip(), str(item.get("原文") or "")))

    units = data.get("语言单元")
    unit_ids = set()
    if not isinstance(units, list):
        errors.append("语言单元必须是数组")
        units = []
    else:
        for index, unit in enumerate(units, start=1):
            if not isinstance(unit, dict):
                errors.append(f"第{index}条语言单元必须是对象")
                continue
            for key in REQUIRED_UNIT:
                if key not in unit:
                    errors.append(f"第{index}条语言单元缺少：{key}")
            unit_id = str(unit.get("语言单元ID") or "").strip()
            speaker = str(unit.get("说话人") or "").strip()
            line = str(unit.get("完整原文") or "")
            if not unit_id or unit_id in unit_ids:
                errors.append(f"第{index}条语言单元的语言单元ID为空或重复")
            unit_ids.add(unit_id)
            if speaker not in names:
                errors.append(f"语言单元出现白名单外说话人：{speaker}")
            if immutable_pairs and (speaker, line) not in immutable_pairs:
                errors.append(f"语言单元未原样匹配不可修改台词：{unit_id}")
            if unit.get("类型") not in LANGUAGE_KINDS:
                errors.append(f"语言单元{unit_id}的类型无效")
            if not nonempty(unit.get("所属分镜组")) or not nonempty(unit.get("开始触发")):
                errors.append(f"语言单元{unit_id}必须写所属分镜组和开始触发")
            if unit.get("时长依据") not in TIMING_BASES:
                errors.append(f"语言单元{unit_id}的时长依据必须是ACTUAL_READ或ESTIMATED")
            duration = unit.get("语言时长秒")
            if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
                errors.append(f"语言单元{unit_id}的语言时长秒必须是正数")
            if unit.get("默认不跨组") is not True:
                errors.append(f"语言单元{unit_id}必须默认不跨组；跨组例外由上游另行批准")
            delivery = unit.get("逐句表演")
            if not isinstance(delivery, dict):
                errors.append(f"语言单元{unit_id}缺少逐句表演对象")
            else:
                for field in ("情绪", "对象与目的", "语气", "身体配合"):
                    if not isinstance(delivery.get(field), str) or not delivery[field].strip():
                        errors.append(f"语言单元{unit_id}逐句表演缺少：{field}")
            segments = unit.get("建议片段")
            if not isinstance(segments, list) or not segments:
                errors.append(f"语言单元{unit_id}的建议片段必须是非空数组")
                continue
            joined = ""
            for seg_index, segment in enumerate(segments, start=1):
                if not isinstance(segment, dict):
                    errors.append(f"语言单元{unit_id}第{seg_index}个建议片段必须是对象")
                    continue
                for key in REQUIRED_SEGMENT:
                    if key not in segment or not nonempty(segment.get(key)):
                        errors.append(f"语言单元{unit_id}第{seg_index}个建议片段缺少：{key}")
                if segment.get("片段顺序") != seg_index:
                    errors.append(f"语言单元{unit_id}的片段顺序必须从1连续递增")
                expected_mode = "动作触发开始" if seg_index == 1 else "无停顿承接"
                if segment.get("开始方式") != expected_mode:
                    errors.append(f"语言单元{unit_id}第{seg_index}片段开始方式必须是{expected_mode}")
                joined += str(segment.get("原文片段") or "")
            if joined != line:
                errors.append(f"语言单元{unit_id}的建议片段无法逐字拼回完整原文")

    expected = [(x.get("说话人"), x.get("原文")) for x in immutable_dialogue if isinstance(x, dict)] if isinstance(immutable_dialogue, list) else []
    actual = [(x.get("说话人"), x.get("完整原文")) for x in units if isinstance(x, dict)]
    if actual != expected:
        errors.append("语言单元必须按顺序完整覆盖冻结台词，不能遗漏、重复或调换")

    beats = data.get("表演节拍")
    used_units = set()
    seen_orders = set()
    if not isinstance(beats, list) or not beats:
        errors.append("表演节拍必须是非空数组")
    else:
        for index, beat in enumerate(beats, start=1):
            if not isinstance(beat, dict):
                errors.append(f"第{index}个表演节拍必须是对象")
                continue
            for key in REQUIRED_BEAT:
                if key not in beat:
                    errors.append(f"第{index}个表演节拍缺少：{key}")
            order = beat.get("顺序")
            if order in seen_orders:
                errors.append(f"表演节拍顺序重复：{order}")
            seen_orders.add(order)
            actor = str(beat.get("主动角色") or "").strip()
            target = str(beat.get("目标对象") or "").strip()
            if actor not in names:
                errors.append(f"第{index}个表演节拍出现白名单外主动角色：{actor}")
            if target and target not in names and target not in {"自己", "无现场对象", "环境"}:
                errors.append(f"第{index}个表演节拍出现白名单外目标对象：{target}")
            for key in ["触发事实", "当前策略", "可见行为", "听者反应", "入节拍状态", "出节拍状态", "建议承载镜头功能"]:
                if not nonempty(beat.get(key)):
                    errors.append(f"第{index}个表演节拍的{key}不能为空")
            unit_id = beat.get("语言单元ID")
            if unit_id not in (None, ""):
                unit_id = str(unit_id).strip()
                if unit_id not in unit_ids:
                    errors.append(f"第{index}个表演节拍引用不存在的语言单元：{unit_id}")
                else:
                    used_units.add(unit_id)
        for unit_id in unit_ids - used_units:
            errors.append(f"语言单元未被任何表演节拍承接：{unit_id}")

    state = data.get("状态继承")
    if not isinstance(state, dict):
        errors.append("状态继承必须是对象")
    else:
        for key in ["入场状态", "本场变化", "出场状态"]:
            if key not in state:
                errors.append(f"状态继承缺少：{key}")
    return errors


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print("用法：validate_performance_plan.py <人物表演方案.json>")
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
    print("校验通过：人物表演方案结构完整。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
