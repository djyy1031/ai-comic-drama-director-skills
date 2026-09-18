#!/usr/bin/env python3
"""Check source-to-prompt handoff evidence; does not certify acting or generated video."""
import argparse
import json
import math
import re
from pathlib import Path
import validate_prompt_only_markdown as fmt

SPEECH = re.compile(r'(开始|继续)(说|内心独白|画外音|旁白|系统语音)：[“]([^”]*)[”]')
FIELDS = ('情绪', '对象与目的', '语气', '身体配合')
KINDS = {'对白': '说', '内心独白': '内心独白', '画外音': '画外音', '旁白': '旁白', '系统语音': '系统语音'}

def number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)

def validate(document, record, locked_global, plans):
    errors = fmt.validate(document)
    text = document.read_text(encoding='utf-8')
    groups = list(fmt.GROUP_RE.finditer(text))
    if len(re.findall(r'^## 分镜组', text, re.M)) != len(groups):
        errors.append('有分镜组标题未被完整解析')
    if not isinstance(record, dict):
        return errors + ['交接核对必须是对象']
    limits = {'seedance-2.0': 15, 'seedance-2.5': 30}
    limit = limits.get(record.get('model_profile'))
    if limit is None:
        errors.append('必须明确已配置的model_profile')
    for field in ('render_mode', 'aspect_ratio'):
        if not isinstance(record.get(field), str) or not record[field].strip():
            errors.append('配置缺少' + field)
    if record.get('aspect_ratio') and record['aspect_ratio'] not in locked_global:
        errors.append('锁定全局段与画幅不一致')
    if isinstance(plans, dict):
        plans = [plans]
    reviews = record.get('groups')
    if not isinstance(plans, list) or not isinstance(reviews, list) or len(plans) != len(groups) or len(reviews) != len(groups):
        return errors + ['表演方案、交接核对与正文分镜组数量不一致']
    for gi, (match, plan, review) in enumerate(zip(groups, plans, reviews), 1):
        label = f'第{gi}组'
        if not isinstance(plan, dict) or not isinstance(review, dict):
            errors.append(label + '方案或交接记录不是对象'); continue
        _, duration, body = match.groups()
        if limit and float(duration) > limit:
            errors.append(label + '超过当前模型配置单组上限')
        _, actual_global = fmt._asset_block_and_global(body)
        if actual_global != locked_global.strip():
            errors.append(label + '未逐字保留锁定全局段')
        shots = list(fmt.SHOT_RE.finditer(body))
        if len(re.findall(r'^【[0-9]', body, re.M)) != len(shots):
            errors.append(label + '有计时镜头未被解析')
        units = plan.get('语言单元', [])
        if not isinstance(units, list) or any(not isinstance(u, dict) for u in units):
            errors.append(label + '语言单元格式错误'); continue
        frozen = plan.get('不可修改原文台词', [])
        source = [(u.get('说话人'),u.get('完整原文')) for u in units]
        if not isinstance(frozen, list) or any(not isinstance(x,dict) for x in frozen) or source != [(x.get('说话人'),x.get('原文')) for x in frozen]:
            errors.append(label + '语言单元未按顺序完整覆盖冻结台词')
        expected = []
        for unit in units:
            delivery = unit.get('逐句表演', {})
            if not isinstance(delivery,dict) or any(not isinstance(delivery.get(k),str) or not delivery[k].strip() for k in FIELDS):
                errors.append(label + '上游缺少逐句表演四项')
            segments = unit.get('建议片段', [])
            if not isinstance(segments,list) or not segments or any(not isinstance(s,dict) for s in segments):
                errors.append(label + '建议片段无效'); continue
            if ''.join(s.get('原文片段','') for s in segments) != unit.get('完整原文'):
                errors.append(label + '建议片段不能拼回原文')
            for si, seg in enumerate(segments):
                expected.append((unit.get('说话人'), KINDS.get(unit.get('类型')), seg.get('原文片段'), '开始' if si==0 else '继续'))
        actual = []
        for si, shot in enumerate(shots, 1):
            previous_end = 0
            content = shot[3]
            for speech in SPEECH.finditer(content):
                actual.append((si, float(shot[2])-float(shot[1]), content[previous_end:speech.start()], speech))
                previous_end = speech.end()
        rows = review.get('utterances', [])
        if not isinstance(rows,list) or len(rows)!=len(actual) or len(actual)!=len(expected):
            errors.append(label + '实际发声、原文片段与逐句核对数量不一致'); continue
        last_end = {}
        for ui, (exp, actual_item, row) in enumerate(zip(expected,actual,rows),1):
            tag = f'{label}第{ui}段'
            si, duration, prefix, speech = actual_item
            speaker,kind,line,mode = exp
            if not isinstance(row,dict):
                errors.append(tag+'记录必须是对象');continue
            if (speech[1],speech[2],speech[3]) != (mode,kind,line):
                errors.append(tag+'语言类型、顺序或原文不一致')
            if row.get('shot')!=si or row.get('speaker')!=speaker or speaker not in prefix:
                errors.append(tag+'镜头位置或发声人物不一致')
            evidence = row.get('evidence', {})
            if not isinstance(evidence,dict): evidence={}
            required = FIELDS + (('触发',) if mode=='开始' else ('情绪与身体承接',))
            for key in required:
                phrase=evidence.get(key)
                if not isinstance(phrase,str) or not phrase.strip() or phrase not in prefix:
                    errors.append(tag+'正文发声前缺少有效证据：'+key)
            if mode=='继续' and '无停顿承接上一镜' not in prefix:
                errors.append(tag+'续说未明确无停顿承接')
            if kind=='内心独白' and not any(x in prefix for x in ('嘴唇闭合','嘴部闭合','闭口')):
                errors.append(tag+'内心独白缺少闭口说明')
            timing=row.get('timing',{})
            if not isinstance(timing,dict):timing={}
            offset,length=timing.get('offset'),timing.get('duration')
            if not number(offset) or not number(length) or offset<0 or length<=0 or offset+length>duration+1e-6:
                errors.append(tag+'发声时长或触发后可用时间无效')
            else:
                if offset<last_end.get(si,0)-1e-6:
                    errors.append(tag+'同镜语言重叠；需上游明确设计并另行审核')
                last_end[si]=offset+length
            if timing.get('basis') not in ('ESTIMATED','ACTUAL_READ'):
                errors.append(tag+'缺少时长依据')
    return errors

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('document','record','locked_global','performance'):parser.add_argument(arg,type=Path)
    args=parser.parse_args()
    try:
        errors=validate(args.document,json.loads(args.record.read_text(encoding='utf-8-sig')),args.locked_global.read_text(encoding='utf-8-sig'),json.loads(args.performance.read_text(encoding='utf-8-sig')))
    except (OSError,ValueError,TypeError,KeyError) as exc:
        errors=['输入无效：'+str(exc)]
    for error in errors:print('ERROR: '+error)
    if not errors:print('PASS: 提示词交接证据与源文检查通过；表演语义、图文匹配及视频效果仍需实际审核')
    return int(bool(errors))

if __name__=='__main__':raise SystemExit(main())
