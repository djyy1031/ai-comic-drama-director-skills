#!/usr/bin/env python3
"""Lightweight text checks, not a certificate of acting or generated video quality."""
import argparse
import json
import re
from pathlib import Path

SHOT = re.compile(r'^\s*(?:\*\*)?【(\d+(?:\.\d+)?)\s*[—–-]\s*(\d+(?:\.\d+)?)秒】(?:\*\*)?[：:]?', re.M)
SUBTITLE = '视频严禁出现台词、内心独白与系统语音字幕。'
ONSET = re.compile(r'(?:第|后)\s*(\d+(?:\.\d+)?)\s*秒[^。\n：:]{0,12}(?:开口|开始说|开始内心独白|开始画外音|开始旁白|开始系统语音)')

def validate(text, names, limit, shots_only=False, exceptions=None):
    errors=[]
    exceptions=exceptions or {}
    shots=list(SHOT.finditer(text))
    if not shots: return ['未找到计时镜头']
    expected=0.0
    for i,m in enumerate(shots):
        number=i+1
        tag=f'镜头{number}'
        start,end=map(float,m.groups())
        if start == 0 and expected > 0: expected=0
        if abs(start-expected)>1e-6 or end<=start: errors.append(tag+'时间不连续或非正时长')
        if end>limit+1e-6: errors.append(tag+'超过单组上限')
        expected=end
        body=text[m.end():shots[i+1].start() if i+1<len(shots) else len(text)].strip()
        # Group tail metadata is not part of the final shot.
        body=re.split(r'(?m)^\s*(?:\*\*)?(?:整体环境音效|剪辑衔接|## 分镜组)',body)[0]
        body=body.replace('**','').strip().strip('`').strip()
        camera=body.split('\n\n')[0]
        if not any(name in camera for name in names): errors.append(tag+'镜头空间段缺少人物姓名/局部归属')
        if '摄影机' not in camera: errors.append(tag+'缺少摄影机位置描述')
        if any(x in camera for x in ('参考图前方','参考图前侧','双手局部近摄，摄影机在水槽前侧固定')):
            errors.append(tag+'使用已确认的模糊机位或无归属局部描述')
        if '环境与动作音效：' not in body: errors.append(tag+'缺少独立环境与动作音效')
        elif not re.search(r'(?m)^环境与动作音效：',body): errors.append(tag+'环境与动作音效须独立成行')
        if not re.search(r'(?:低于|不高于|不盖|不遮|退至|让位|无声|静默)',body):
            errors.append(tag+'缺少声音主次或静默安排')
        has_voice=bool(re.search(r'[：:]\s*[“「]',body))
        if has_voice:
            if not body.endswith('\n'+SUBTITLE): errors.append(tag+'语言镜末尾须独立一行禁字幕句')
            onset=ONSET.search(body)
            continued='无停顿承接上一镜' in body
            reason=exceptions.get(str(number),{})
            justified=isinstance(reason,dict) and bool(reason.get('source_quote','').strip()) and bool(reason.get('reason','').strip())
            if not continued and not onset: errors.append(tag+'缺少明确的本镜开口时间')
            if onset:
                value=float(onset[1])
                if value>=end-start: errors.append(tag+'开口时间不在本镜内')
                if value>0.5 and not justified: errors.append(tag+'开口超过0.5秒且无原文例外')
                if continued and value>0: errors.append(tag+'续说不能重新等待开口')
            # Catch demonstrated serial-action phrasing even when an early timestamp is present.
            if not justified and re.search(r'(?:后停稳|放稳后|完成[^。\n]{0,20}后|放松后|对上视线后|微笑后|转身后|收好手机后)[^。\n]{0,180}(?:开口|开始说)',body):
                errors.append(tag+'疑似动作完成后才开口；须改成同步或核实原文例外')
        if '本镜为剧本必要无声动作或回忆信息' in body: errors.append(tag+'含旧式重复检查话术')
    if not shots_only:
        if not re.search(r'(?m)^\s*(?:\*\*)?整体环境音效：',text): errors.append('缺少整组整体环境音效')
        if not any(x in text for x in ('无背景音乐','禁止背景音乐','禁止出现背景音乐','禁止生成BGM')):
            errors.append('缺少无背景音乐要求')
    return errors

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('document',type=Path)
    p.add_argument('--names',nargs='+',required=True)
    p.add_argument('--max-group-seconds',type=float,required=True)
    p.add_argument('--shots-only',action='store_true')
    p.add_argument('--exceptions',type=Path)
    a=p.parse_args()
    try:
        ex=json.loads(a.exceptions.read_text(encoding='utf-8-sig')) if a.exceptions else {}
        if not isinstance(ex,dict): raise ValueError('例外须为镜头序号到原文证据的对象')
        if a.max_group_seconds<=0: raise ValueError('单组上限必须大于零')
        errors=validate(a.document.read_text(encoding='utf-8-sig'),a.names,a.max_group_seconds,a.shots_only,ex)
    except (OSError,ValueError,TypeError) as exc: errors=[str(exc)]
    for error in errors: print('ERROR: '+error)
    if not errors: print('PASS_TEXT: 可识别文字约束通过；仍需逐镜语义审查，未验证音频或视频。')
    return int(bool(errors))

if __name__=='__main__': raise SystemExit(main())
