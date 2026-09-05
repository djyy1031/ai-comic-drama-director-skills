#!/usr/bin/env python3
import json
import sys
from pathlib import Path


REQUIRED_TOP = [
    "规范版本", "来源锚点", "不可修改剧情事实", "不可修改原文台词",
    "活动资产白名单", "画面内人物白名单", "场景空间地图", "光线与色卡基线", "语言单元",
    "单镜检查", "切镜连续性", "最终裁决",
]
REQUIRED_SHOT = [
    "镜头ID", "时长秒", "活动实体", "画面内人物", "第一帧", "人物空间关系", "道具状态",
    "摄影机", "光线", "动作物理", "语言片段", "入镜状态", "出镜状态",
    "局部修复锁", "问题", "状态",
]
REQUIRED_FIRST_FRAME = ["有效主体", "动作状态", "空间关系可读", "画面目的"]
REQUIRED_PERSON = ["角色标准名称", "世界位置", "画面位置", "身体朝向", "视线目标", "地标距离", "移动方向", "当前表演", "表演依据"]
REQUIRED_CAMERA = ["轴线侧", "朝向", "高度", "距离", "主要运镜", "停止位置", "最终焦点"]
REQUIRED_LIGHT = ["主光来源", "主光方向", "摄影机受光侧", "曝光优先级", "色卡版本"]
REQUIRED_PHYSICS = ["动作原因", "驱动或发力", "接触", "受力结果", "环境反馈"]
REQUIRED_CUT = ["前镜", "后镜", "人物继承", "道具继承", "环境继承", "轴线与屏幕方向", "光线继承", "语言承接", "问题", "状态"]
REQUIRED_UNIT = ["语言单元ID", "类型", "说话人", "完整原文", "所属分镜组", "默认不跨组", "连续要求"]
REQUIRED_SEGMENT = ["语言单元ID", "片段顺序", "原文片段", "开始方式", "开始触发", "语言时长秒", "时长依据", "口型状态", "连续要求"]
TIMING_BASES = {"ACTUAL_READ", "ESTIMATED"}
MAX_NORMAL_SHOT_SECONDS = 6.0


def nonempty(value):
    return bool(str(value or "").strip())


def validate(data):
    errors = []
    for key in REQUIRED_TOP:
        if key not in data:
            errors.append(f"缺少顶层字段：{key}")

    whitelist = data.get("活动资产白名单")
    if not isinstance(whitelist, list) or not whitelist:
        errors.append("活动资产白名单必须是非空数组")
        whitelist = []
    whitelist = {str(item).strip() for item in whitelist if str(item).strip()}

    people_whitelist = data.get("画面内人物白名单")
    if not isinstance(people_whitelist, list):
        errors.append("画面内人物白名单必须是数组")
        people_whitelist = []
    people_whitelist = {str(item).strip() for item in people_whitelist if str(item).strip()}
    for name in people_whitelist - whitelist:
        errors.append(f"画面内人物白名单出现活动资产白名单外角色：{name}")

    units = data.get("语言单元")
    unit_by_id = {}
    if not isinstance(units, list):
        errors.append("语言单元必须是数组")
        units = []
    for index, unit in enumerate(units, start=1):
        if not isinstance(unit, dict):
            errors.append(f"第{index}条语言单元必须是对象")
            continue
        for key in REQUIRED_UNIT:
            if key not in unit:
                errors.append(f"第{index}条语言单元缺少：{key}")
        unit_id = str(unit.get("语言单元ID") or "").strip()
        if not unit_id or unit_id in unit_by_id:
            errors.append(f"第{index}条语言单元ID为空或重复")
        else:
            unit_by_id[unit_id] = unit
        if unit.get("默认不跨组") is not True:
            bridge = unit.get("跨组转场桥")
            if unit.get("跨组明确批准") is not True or not isinstance(bridge, dict):
                errors.append(f"语言单元{unit_id}跨组时必须有上游批准和跨组转场桥")
            elif (
                not nonempty(bridge.get("前组尾镜签名"))
                or not nonempty(bridge.get("后组首镜签名"))
                or bridge.get("前组尾镜签名") == bridge.get("后组首镜签名")
                or not nonempty(bridge.get("转场方法"))
            ):
                errors.append(f"语言单元{unit_id}的跨组转场桥必须使用不同镜头并写清转场方法")

    shots = data.get("单镜检查")
    shot_ids = []
    any_dialogue = False
    total_duration = 0.0
    if not isinstance(shots, list) or not shots:
        errors.append("单镜检查必须是非空数组")
        shots = []
    else:
        seen = set()
        for index, shot in enumerate(shots, start=1):
            if not isinstance(shot, dict):
                errors.append(f"第{index}条单镜检查必须是对象")
                continue
            for key in REQUIRED_SHOT:
                if key not in shot:
                    errors.append(f"第{index}条单镜检查缺少：{key}")
            shot_id = str(shot.get("镜头ID") or "").strip()
            if not shot_id or shot_id in seen:
                errors.append(f"第{index}条单镜检查的镜头ID为空或重复")
            seen.add(shot_id)
            shot_ids.append(shot_id)
            duration = shot.get("时长秒")
            if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
                errors.append(f"镜头{shot_id}的时长秒必须是正数")
                duration = 0
            total_duration += float(duration)
            segments = shot.get("语言片段")
            if not isinstance(segments, list):
                errors.append(f"镜头{shot_id}的语言片段必须是数组")
                segments = []
            if segments:
                any_dialogue = True
            for seg_index, segment in enumerate(segments, start=1):
                if not isinstance(segment, dict):
                    errors.append(f"镜头{shot_id}第{seg_index}个语言片段必须是对象")
                    continue
                for key in REQUIRED_SEGMENT:
                    if key not in segment or not nonempty(segment.get(key)):
                        errors.append(f"镜头{shot_id}第{seg_index}个语言片段缺少：{key}")
                unit_id = str(segment.get("语言单元ID") or "").strip()
                if unit_id not in unit_by_id:
                    errors.append(f"镜头{shot_id}引用不存在的语言单元：{unit_id}")
                segment_duration = segment.get("语言时长秒")
                if not isinstance(segment_duration, (int, float)) or isinstance(segment_duration, bool) or segment_duration <= 0:
                    errors.append(f"镜头{shot_id}第{seg_index}个语言片段时长必须是正数")
                elif isinstance(duration, (int, float)) and segment_duration > duration:
                    errors.append(f"镜头{shot_id}的语言片段时长超过镜头可用时长")
                if segment.get("时长依据") not in TIMING_BASES:
                    errors.append(f"镜头{shot_id}第{seg_index}个语言片段时长依据无效")
            if duration > MAX_NORMAL_SHOT_SECONDS:
                if shot.get("长镜头明确批准") is not True or not nonempty(shot.get("长镜头理由")):
                    errors.append(f"镜头{shot_id}超过6秒，必须由上游明确批准长镜头并填写理由")

            entities = shot.get("活动实体")
            if not isinstance(entities, list) or not entities:
                errors.append(f"镜头{shot_id}的活动实体必须是非空数组")
                entities = []
            for entity in entities:
                if str(entity).strip() not in whitelist:
                    errors.append(f"镜头{shot_id}出现白名单外实体：{entity}")

            visible_people = shot.get("画面内人物")
            if not isinstance(visible_people, list):
                errors.append(f"镜头{shot_id}的画面内人物必须是数组")
                visible_people = []
            visible_people = {str(name).strip() for name in visible_people if str(name).strip()}
            for name in visible_people - people_whitelist:
                errors.append(f"镜头{shot_id}出现画面内人物白名单外角色：{name}")
            for name in visible_people:
                if name not in {str(entity).strip() for entity in entities}:
                    errors.append(f"镜头{shot_id}的画面内人物未登记为活动实体：{name}")

            first = shot.get("第一帧")
            if not isinstance(first, dict):
                errors.append(f"镜头{shot_id}的第一帧必须是对象")
            else:
                for key in REQUIRED_FIRST_FRAME:
                    if key not in first or (key != "空间关系可读" and not nonempty(first.get(key))):
                        errors.append(f"镜头{shot_id}的第一帧缺少有效字段：{key}")
                if first.get("空间关系可读") is not True:
                    errors.append(f"镜头{shot_id}第一帧的空间关系不可读")

            people = shot.get("人物空间关系")
            if not isinstance(people, list):
                errors.append(f"镜头{shot_id}的人物空间关系必须是数组")
            else:
                recorded_people = set()
                for p_index, person in enumerate(people, start=1):
                    if not isinstance(person, dict):
                        errors.append(f"镜头{shot_id}第{p_index}个人物空间关系必须是对象")
                        continue
                    for key in REQUIRED_PERSON:
                        if key not in person or not nonempty(person.get(key)):
                            errors.append(f"镜头{shot_id}第{p_index}个人物空间关系缺少：{key}")
                    name = str(person.get("角色标准名称") or "").strip()
                    recorded_people.add(name)
                    if name not in whitelist:
                        errors.append(f"镜头{shot_id}的人物空间关系出现白名单外角色：{name}")
                for name in sorted(visible_people - recorded_people):
                    errors.append(f"镜头{shot_id}的画面内人物{name}缺少空间与表演记录；背景人物也不能木站")
                for name in sorted(recorded_people - visible_people):
                    errors.append(f"镜头{shot_id}记录了未声明入画人物的空间与表演：{name}")

            for section, required in [("摄影机", REQUIRED_CAMERA), ("光线", REQUIRED_LIGHT), ("动作物理", REQUIRED_PHYSICS)]:
                value = shot.get(section)
                if not isinstance(value, dict):
                    errors.append(f"镜头{shot_id}的{section}必须是对象")
                else:
                    for key in required:
                        if key not in value or not nonempty(value.get(key)):
                            errors.append(f"镜头{shot_id}的{section}缺少：{key}")

            for key in ["入镜状态", "出镜状态"]:
                if not isinstance(shot.get(key), dict):
                    errors.append(f"镜头{shot_id}的{key}必须是对象")
            issues = shot.get("问题")
            if not isinstance(issues, list):
                errors.append(f"镜头{shot_id}的问题必须是数组")
            if shot.get("状态") == "PASS" and issues:
                errors.append(f"镜头{shot_id}标记PASS时问题必须为空")

    if any_dialogue and total_duration > MAX_NORMAL_SHOT_SECONDS and len(shots) == 1:
        shot = shots[0] if shots and isinstance(shots[0], dict) else {}
        if not (shot.get("长镜头明确批准") is True and nonempty(shot.get("长镜头理由"))):
            errors.append("含连续对白且总时长超过6秒时不能只有一个镜头")

    collected = {unit_id: [] for unit_id in unit_by_id}
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        for segment in shot.get("语言片段", []):
            if isinstance(segment, dict):
                unit_id = str(segment.get("语言单元ID") or "").strip()
                if unit_id in collected:
                    collected[unit_id].append(segment)
    for unit_id, unit in unit_by_id.items():
        segments = sorted(collected[unit_id], key=lambda item: item.get("片段顺序", 0))
        if not segments:
            errors.append(f"语言单元{unit_id}未被任何镜头承载")
            continue
        indexes = [segment.get("片段顺序") for segment in segments]
        if indexes != list(range(1, len(segments) + 1)):
            errors.append(f"语言单元{unit_id}的片段顺序必须从1连续递增且不得重复")
        joined = "".join(str(segment.get("原文片段") or "") for segment in segments)
        if joined != str(unit.get("完整原文") or ""):
            errors.append(f"语言单元{unit_id}的逐镜片段无法逐字拼回完整原文")
        for position, segment in enumerate(segments, start=1):
            expected = "动作触发开始" if position == 1 else "无停顿承接"
            if segment.get("开始方式") != expected:
                errors.append(f"语言单元{unit_id}第{position}片段开始方式必须是{expected}")

    cuts = data.get("切镜连续性")
    if not isinstance(cuts, list):
        errors.append("切镜连续性必须是数组")
        cuts = []
    expected_pairs = list(zip(shot_ids, shot_ids[1:]))
    actual_pairs = []
    for index, cut in enumerate(cuts, start=1):
        if not isinstance(cut, dict):
            errors.append(f"第{index}条切镜连续性必须是对象")
            continue
        for key in REQUIRED_CUT:
            if key not in cut:
                errors.append(f"第{index}条切镜连续性缺少：{key}")
        pair = (str(cut.get("前镜") or "").strip(), str(cut.get("后镜") or "").strip())
        actual_pairs.append(pair)
        issues = cut.get("问题")
        if not isinstance(issues, list):
            errors.append(f"切点{pair[0]}→{pair[1]}的问题必须是数组")
        if cut.get("状态") == "PASS" and issues:
            errors.append(f"切点{pair[0]}→{pair[1]}标记PASS时问题必须为空")
    if actual_pairs != expected_pairs:
        errors.append("切镜连续性必须逐对覆盖全部相邻镜头，且顺序一致")

    verdict = data.get("最终裁决")
    if not isinstance(verdict, dict):
        errors.append("最终裁决必须是对象")
    else:
        for key in ["状态", "问题", "最早返修位置"]:
            if key not in verdict:
                errors.append(f"最终裁决缺少：{key}")
        if verdict.get("状态") == "PASS":
            if verdict.get("问题"):
                errors.append("最终裁决为PASS时问题必须为空")
            if any(isinstance(shot, dict) and shot.get("状态") != "PASS" for shot in shots):
                errors.append("存在未通过单镜时最终裁决不能为PASS")
            if any(isinstance(cut, dict) and cut.get("状态") != "PASS" for cut in cuts):
                errors.append("存在未通过切点时最终裁决不能为PASS")
    return errors


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print("用法：validate_execution_report.py <镜头执行检查.json>")
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
    print("校验通过：镜头执行与连续性检查完整。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
