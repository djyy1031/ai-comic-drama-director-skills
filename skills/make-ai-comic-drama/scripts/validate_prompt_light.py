#!/usr/bin/env python3
"""Lightweight text checks, not a certificate of acting or generated video quality."""
import argparse
import json
import re
from pathlib import Path

SHOT = re.compile(r'^\s*(?:\*\*)?【(\d+(?:\.\d+)?)\s*[—–-]\s*(\d+(?:\.\d+)?)秒】(?:\*\*)?[：:]?', re.M)
SUBTITLE = '视频严禁出现台词、内心独白与系统语音字幕。'
ONSET = re.compile(r'(?:第|后)\s*(\d+(?:\.\d+)?)\s*秒[^。\n：:]{0,12}(?:开口|开始说|开始对[^。\n：:]{1,12}说|开始内心独白|开始画外音|开始旁白|开始系统语音)')
EPISODE = re.compile(r'第(\d+)集\s*[｜|]\s*总时长\s*(\d+(?:\.\d+)?)秒\s*[｜|]\s*共\s*(\d+)个分镜组\s*[｜|]\s*各组时长[：:]\s*([^\n]+)')
GROUP = re.compile(r'(?m)^#{1,4}\s*分镜组[^\n]*?(\d+(?:\.\d+)?)秒[^\n]*$')
FENCE = re.compile(r'```text\s*\n(.*?)\n```', re.S)
SECTIONS = ('【摄影机运动总设定】', '【场景与光影】', '【起始站位】', '【语言连续性总锁】')
ASSET = re.compile(r'^[^【\s#][^=\n]{0,80}=[^\n]*$')
FRAMING = re.compile(r'单人|双人|多人|中近景|中全景|中景|近景|特写|全景')
LENS_PREFIX = re.compile(r'^\s*摄影机镜头焦距\s*\d+(?:\.\d+)?\s*(?:mm|毫米)\s*[，,]?\s*', re.I)
CONTINUE_ONSET = re.compile(r'第\s*(\d+(?:\.\d+)?)\s*秒[^。\n：:]{0,12}(?:继续说|继续内心独白|继续画外音|继续旁白|继续系统语音)')
PROMPT_RESIDUE = re.compile(r'\*\*|&#(?:x[0-9a-fA-F]+|\d+);|上一镜|下一镜|待场景图核对|待站位图核对|不能重新抬手')
FACE_DETAIL = re.compile(r'面部|脸部|面容|眼部|眼睛|眼神|眉眼|唇部|嘴唇|鼻尖')
CAMERA_CHOICE = re.compile(r'固定|静止|前移|后退|横移|摇摄|推近|拉远|跟拍|跟随|升降|弧线|环绕|手持|变焦|转焦')

def validate_named_framing(camera, names, tag):
    first_line=next((line.strip() for line in camera.splitlines() if line.strip()), '')
    if not LENS_PREFIX.match(first_line):
        return [tag+'镜头首句须写“摄影机镜头焦距N毫米”，裸写焦距或漏写焦距均不合格']
    opening=LENS_PREFIX.sub('', first_line, count=1).lstrip('，, ')
    framing=FRAMING.search(opening)
    if not framing:
        return []
    before=opening[:framing.start()]
    named=[name for name in names if name in before]
    if not any(opening.startswith(name) for name in names):
        return [tag+'镜头首句须先写被拍人物标准姓名，再写景别；后文补姓名无效']
    if '双人' in opening[:framing.end()] and len(named)<2:
        return [tag+'双人景别须在开头写出两名被拍人物']
    return []

def validate_full_groups(text, limit):
    errors=[]
    episodes=list(EPISODE.finditer(text))
    if not episodes:
        return ['完整分集缺少“第X集｜总时长X秒｜共X个分镜组｜各组时长：...”基础信息']
    for index, episode in enumerate(episodes):
        number,total_text,count_text,durations_text=episode.groups()
        chunk=text[episode.end():episodes[index+1].start() if index+1<len(episodes) else len(text)]
        groups=list(GROUP.finditer(chunk))
        fences=list(FENCE.finditer(chunk))
        planned=[float(value) for value in re.findall(r'(\d+(?:\.\d+)?)\s*秒',durations_text)]
        actual=[float(group.group(1)) for group in groups]
        label=f'第{number}集'
        if len(groups)!=int(count_text) or len(fences)!=len(groups): errors.append(label+'组数或独立text代码块数量与基础信息不符')
        if len(planned)!=len(groups) or any(abs(a-b)>1e-6 for a,b in zip(planned,actual)):
            errors.append(label+'各组时长列表与分镜组标题不符')
        if abs(sum(actual)-float(total_text))>1e-6: errors.append(label+'总时长不等于各组时长之和')
        for group_index,(heading,fence) in enumerate(zip(groups,fences),1):
            group_label=f'{label}第{group_index}组'
            if fence.start()<heading.end() or (group_index<len(groups) and fence.start()>groups[group_index].start()):
                errors.append(group_label+'代码块未紧随对应分镜组标题')
            body=fence.group(1).strip()
            positions=[body.find(section) for section in SECTIONS]
            if any(pos<0 for pos in positions) or positions!=sorted(positions) or len(set(positions))!=len(positions):
                errors.append(group_label+'缺少四个固定栏目或栏目顺序错误')
                continue
            prefix=body[:positions[0]].strip().splitlines()
            if not prefix: errors.append(group_label+'缺少全局约束与资产绑定')
            else:
                bindings=[]
                for line in reversed(prefix):
                    if ASSET.fullmatch(line.strip()): bindings.append(line.strip())
                    else: break
                if len(bindings)<2: errors.append(group_label+'摄影机栏目之前缺少逐行等号资产绑定（至少角色与场景）')
                if len(prefix)<=len(bindings): errors.append(group_label+'资产绑定之前缺少完整全局约束')
            first_shot=SHOT.search(body)
            end_of_sections=first_shot.start() if first_shot else len(body)
            for section_index,section in enumerate(SECTIONS):
                end=positions[section_index+1] if section_index+1<len(SECTIONS) else end_of_sections
                if not body[positions[section_index]+len(section):end].strip(): errors.append(group_label+section+'内容为空')
            if not first_shot: errors.append(group_label+'缺少逐镜时间段')
            else:
                shots=list(SHOT.finditer(body))
                if abs(float(shots[-1].group(2))-float(heading.group(1)))>1e-6:
                    errors.append(group_label+'末镜结束时间与组时长不符')
                if float(heading.group(1))>limit+1e-6: errors.append(group_label+'组时长超过模型上限')
    return errors

def validate_draft_groups(text, limit, require_groups=False):
    """Check generation boundaries in review drafts without requiring final prompt fields."""
    errors=[]
    groups=list(GROUP.finditer(text))
    if not groups:
        return ['整场审阅草稿缺少独立分镜组标题与组时长'] if require_groups else []
    if SHOT.search(text[:groups[0].start()]):
        errors.append('首个分镜组标题之前存在未归组镜头')
    for index,heading in enumerate(groups):
        label=f'草稿第{index+1}组'
        chunk=text[heading.end():groups[index+1].start() if index+1<len(groups) else len(text)]
        shots=list(SHOT.finditer(chunk))
        duration=float(heading.group(1))
        if not shots:
            errors.append(label+'缺少计时镜头')
            continue
        expected=0.0
        for shot in shots:
            start,end=map(float,shot.groups())
            if abs(start-expected)>1e-6 or end<=start:
                errors.append(label+'镜头须从0秒开始且组内连续计时')
            expected=end
        if abs(expected-duration)>1e-6:
            errors.append(label+'标题时长与末镜结束时间不符')
        if limit is not None and duration>limit+1e-6:
            errors.append(label+'组时长超过模型上限')
    return errors

def validate(text, names, limit=None, shots_only=False, exceptions=None, require_groups=False):
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
        if limit is not None and end>limit+1e-6: errors.append(tag+'超过单组上限')
        expected=end
        body=text[m.end():shots[i+1].start() if i+1<len(shots) else len(text)].strip()
        # Group tail metadata is not part of the final shot.
        body=re.split(r'(?m)^\s*(?:\*\*)?(?:整体环境音效|剪辑衔接|## 分镜组)',body)[0]
        if PROMPT_RESIDUE.search(body):
            errors.append(tag+'混入格式残留、待核备注或跨镜剪辑指令')
        body=body.replace('**','').strip().strip('`').strip()
        camera=body.split('\n\n')[0]
        if not any(name in camera for name in names): errors.append(tag+'镜头空间段缺少人物姓名/局部归属')
        errors.extend(validate_named_framing(camera,names,tag))
        first_camera_line=next((line.strip() for line in camera.splitlines() if line.strip()), '')
        if not LENS_PREFIX.match(first_camera_line):
            errors.append(tag+'镜头首句须明确“摄影机镜头焦距N毫米”')
        if '特写' in first_camera_line and not FACE_DETAIL.search(first_camera_line.split('特写',1)[0]) and end-start>2+1e-6:
            errors.append(tag+'非脸部特写超过2秒；改用人物或关系镜头承载长段语言')
        if '摄影机' not in camera: errors.append(tag+'缺少摄影机位置描述')
        elif not CAMERA_CHOICE.search(camera): errors.append(tag+'摄影机缺少固定或具体运动选择；焦段和机位不能代替拍法')
        if any(x in camera for x in ('参考图前方','参考图前侧','双手局部近摄，摄影机在水槽前侧固定')):
            errors.append(tag+'使用已确认的模糊机位或无归属局部描述')
        if '环境与动作音效：' not in body: errors.append(tag+'缺少独立环境与动作音效')
        elif not re.search(r'(?m)^环境与动作音效：',body): errors.append(tag+'环境与动作音效须独立成行')
        if not re.search(r'(?:低于|不高于|不盖|不遮|退至|让位|无声|静默|无对白|没有人声|无人说话)',body):
            errors.append(tag+'缺少声音主次或静默安排')
        has_voice=bool(re.search(r'[：:]\s*[“「]',body))
        if has_voice:
            if not body.endswith('\n'+SUBTITLE): errors.append(tag+'语言镜末尾须独立一行禁字幕句')
            onset=ONSET.search(body)
            continued_match=CONTINUE_ONSET.search(body)
            reason=exceptions.get(str(number),{})
            justified=isinstance(reason,dict) and bool(reason.get('source_quote','').strip()) and bool(reason.get('reason','').strip())
            if not continued_match and not onset: errors.append(tag+'缺少明确的本镜开口时间')
            if onset:
                value=float(onset[1])
                if value>=end-start: errors.append(tag+'开口时间不在本镜内')
                if value>0.5 and not justified: errors.append(tag+'开口超过0.5秒且无原文例外')
            if continued_match and float(continued_match[1]) != 0:
                errors.append(tag+'同一句在本镜继续发声必须从第0秒开始')
            # Catch demonstrated serial-action phrasing even when an early timestamp is present.
            if not justified and re.search(r'(?:后停稳|放稳后|完成[^。\n]{0,20}后|放松后|对上视线后|微笑后|转身后|收好手机后)[^。\n]{0,180}(?:开口|开始说)',body):
                errors.append(tag+'疑似动作完成后才开口；须改成同步或核实原文例外')
        if '本镜为剧本必要无声动作或回忆信息' in body: errors.append(tag+'含旧式重复检查话术')
    if shots_only:
        errors.extend(validate_draft_groups(text,limit,require_groups))
    else:
        if limit is None: return errors+['完整组需提供实际模型的单组时长上限']
        errors.extend(validate_full_groups(text,limit))
        if not re.search(r'(?m)^\s*(?:\*\*)?整体环境音效：',text): errors.append('缺少整组整体环境音效')
        if not any(x in text for x in ('无背景音乐','禁止背景音乐','禁止出现背景音乐','禁止生成BGM')):
            errors.append('缺少无背景音乐要求')
    return errors

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('document',type=Path)
    p.add_argument('--names',nargs='+',required=True)
    p.add_argument('--max-group-seconds',type=float)
    p.add_argument('--shots-only',action='store_true')
    p.add_argument('--require-groups',action='store_true',help='整场审阅草稿必须逐组标时长、从0计时')
    p.add_argument('--exceptions',type=Path)
    a=p.parse_args()
    try:
        ex=json.loads(a.exceptions.read_text(encoding='utf-8-sig')) if a.exceptions else {}
        if not isinstance(ex,dict): raise ValueError('例外须为镜头序号到原文证据的对象')
        if a.max_group_seconds is not None and a.max_group_seconds<=0: raise ValueError('单组上限必须大于零')
        errors=validate(a.document.read_text(encoding='utf-8-sig'),a.names,a.max_group_seconds,a.shots_only,ex,a.require_groups)
    except (OSError,ValueError,TypeError) as exc: errors=[str(exc)]
    for error in errors: print('ERROR: '+error)
    if not errors: print('PASS_FORMAT_ONLY: 可识别文字与时间格式通过；未验证资产图、站位、表演节奏、音频或视频。')
    return int(bool(errors))

if __name__=='__main__': raise SystemExit(main())
