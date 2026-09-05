#!/usr/bin/env python3
import json
import sys
from pathlib import Path


REQUIRED_TOP = ["规范版本", "来源锚点", "不可修改剧情事实", "不可修改原文台词", "场景诊断", "调用模块", "人物表演方案", "连续性状态", "语言单元", "镜头设计", "镜头执行与连续性检查", "模型适配提醒"]
REQUIRED_DIAGNOSIS = ["主场景类型", "主要剧情功能", "战斗阶段", "情绪轨迹", "视觉优先级", "不可切断单元", "连续性风险"]
REQUIRED_SHOT = ["顺序", "类型", "建议时长秒", "语言片段", "镜头签名", "镜头功能", "存在理由", "主体与变化", "摄影机", "角色表演进程", "入镜状态", "出镜状态"]
REQUIRED_UNIT = ["语言单元ID", "类型", "说话人", "完整原文", "所属分镜组", "默认不跨组", "连续要求"]
REQUIRED_SEGMENT = ["语言单元ID", "片段顺序", "原文片段", "开始方式", "开始触发", "语言时长秒", "时长依据", "口型状态", "连续要求"]
TIMING_BASES = {"ACTUAL_READ", "ESTIMATED"}
DEFAULT_MAX_SHOT_SECONDS = 6.0


def validate(data):
    errors = []
    for key in REQUIRED_TOP:
        if key not in data:
            errors.append(f"缺少顶层字段：{key}")
    for field, expected_source in [
        ("人物表演方案", "$ai-character-performance-assets"),
        ("镜头执行与连续性检查", "$ai-shot-execution-continuity"),
    ]:
        value = data.get(field)
        if not isinstance(value, dict):
            errors.append(f"{field}必须是对象")
            continue
        for key in ["来源", "状态", "摘要"]:
            if not str(value.get(key, "")).strip():
                errors.append(f"{field}缺少有效字段：{key}")
        if value.get("来源") not in {expected_source, "FALLBACK_INTERNAL"}:
            errors.append(f"{field}来源无效：{value.get('来源')}")
        if value.get("状态") != "PASS":
            errors.append(f"{field}未通过，不能进入上游编译")
    diagnosis = data.get("场景诊断", {})
    if not isinstance(diagnosis, dict):
        errors.append("场景诊断必须是对象")
    else:
        for key in REQUIRED_DIAGNOSIS:
            if key not in diagnosis:
                errors.append(f"场景诊断缺少：{key}")
    immutable = set()
    for item in data.get("不可修改原文台词", []):
        if isinstance(item, dict):
            immutable.add((str(item.get("说话人") or "").strip(), str(item.get("原文") or "")))

    units = data.get("语言单元")
    unit_by_id = {}
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
            unit_id = str(unit.get("语言单元ID", "")).strip()
            if not unit_id:
                errors.append(f"第{index}条语言单元ID为空")
            elif unit_id in unit_by_id:
                errors.append(f"语言单元ID重复：{unit_id}")
            else:
                unit_by_id[unit_id] = unit
            speaker = str(unit.get("说话人") or "").strip()
            full_text = str(unit.get("完整原文") or "")
            if immutable and (speaker, full_text) not in immutable:
                errors.append(f"语言单元{unit_id}未原样匹配不可修改原文台词")
            if unit.get("默认不跨组") is not True:
                bridge = unit.get("跨组转场桥")
                if unit.get("跨组明确批准") is not True or not isinstance(bridge, dict):
                    errors.append(f"语言单元{unit_id}跨组时必须有上游批准和跨组转场桥")
                elif (
                    not str(bridge.get("前组尾镜签名") or "").strip()
                    or not str(bridge.get("后组首镜签名") or "").strip()
                    or bridge.get("前组尾镜签名") == bridge.get("后组首镜签名")
                    or not str(bridge.get("转场方法") or "").strip()
                ):
                    errors.append(f"语言单元{unit_id}跨组时必须用不同镜头并写清转场方法")

    shots = data.get("镜头设计")
    collected = {unit_id: [] for unit_id in unit_by_id}
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
            if shot.get("类型") in {"连续语言表演块", "连续语言音轨块"}:
                errors.append(f"第{index}个镜头仍使用已禁用的连续语言块；请改为逐镜原文片段")
            duration = shot.get("建议时长秒")
            if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
                errors.append(f"第{index}个镜头的建议时长秒必须是正数")
            elif duration > DEFAULT_MAX_SHOT_SECONDS:
                if shot.get("长镜头明确批准") is not True or not str(shot.get("长镜头理由", "")).strip():
                    errors.append(f"第{index}个镜头超过6秒，必须明确批准长镜头并填写理由")
            segments = shot.get("语言片段")
            if not isinstance(segments, list):
                errors.append(f"第{index}个镜头的语言片段必须是数组")
                segments = []
            for seg_index, segment in enumerate(segments, start=1):
                if not isinstance(segment, dict):
                    errors.append(f"第{index}个镜头第{seg_index}个语言片段必须是对象")
                    continue
                for key in REQUIRED_SEGMENT:
                    if key not in segment or not str(segment.get(key) or "").strip():
                        errors.append(f"第{index}个镜头第{seg_index}个语言片段缺少：{key}")
                unit_id = str(segment.get("语言单元ID") or "").strip()
                if unit_id not in unit_by_id:
                    errors.append(f"第{index}个镜头引用了不存在的语言单元：{unit_id}")
                else:
                    collected[unit_id].append(segment)
                segment_duration = segment.get("语言时长秒")
                if not isinstance(segment_duration, (int, float)) or isinstance(segment_duration, bool) or segment_duration <= 0:
                    errors.append(f"第{index}个镜头第{seg_index}个语言片段时长必须是正数")
                elif isinstance(duration, (int, float)) and segment_duration > duration:
                    errors.append(f"第{index}个镜头的语言片段时长超过镜头建议时长")
                if segment.get("时长依据") not in TIMING_BASES:
                    errors.append(f"第{index}个镜头第{seg_index}个语言片段时长依据无效")
            order = shot.get("顺序")
            if order in seen:
                errors.append(f"镜头顺序重复：{order}")
            seen.add(order)
            if not str(shot.get("镜头功能", "")).strip():
                errors.append(f"第{index}个镜头的镜头功能为空")
            if not str(shot.get("存在理由", "")).strip():
                errors.append(f"第{index}个镜头的存在理由为空")
        for unit_id, unit in unit_by_id.items():
            segments = sorted(collected[unit_id], key=lambda item: item.get("片段顺序", 0))
            if not segments:
                errors.append(f"语言单元{unit_id}未被任何镜头承载")
                continue
            indexes = [segment.get("片段顺序") for segment in segments]
            if indexes != list(range(1, len(segments) + 1)):
                errors.append(f"语言单元{unit_id}片段顺序必须从1连续递增且不得重复")
            joined = "".join(str(segment.get("原文片段") or "") for segment in segments)
            if joined != str(unit.get("完整原文") or ""):
                errors.append(f"语言单元{unit_id}的逐镜片段无法逐字拼回完整原文")
            for position, segment in enumerate(segments, start=1):
                expected = "动作触发开始" if position == 1 else "无停顿承接"
                if segment.get("开始方式") != expected:
                    errors.append(f"语言单元{unit_id}第{position}片段开始方式必须是{expected}")
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
