import copy
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('handoff',ROOT/'scripts/validate_prompt_handoff.py')
V=importlib.util.module_from_spec(spec);spec.loader.exec_module(V)
sys.path.pop(0)

def fixture():
    global_text=re.search(r'```text\n(.*?)\n```',(ROOT/'references/global-live-action-period-prompt.md').read_text(encoding='utf-8'),re.S)[1]
    pairs=[('张三','李四',['你为什么','骗我？'],'克制的愤怒','向李四质问隐瞒的原因','语气强硬','右手离开账本，目光看住李四'),('李四','张三',['我怕你','担心。'],'担忧中带着歉意','向张三解释隐瞒的原因','语气轻缓','停止擦桌，抬眼望向张三')]
    plans=[];groups=[];reviews=[]
    for i,(speaker,target,fragments,emotion,purpose,tone,body) in enumerate(pairs,1):
        trigger=('张三放下账本后，' if i==1 else '李四停止擦桌后，')
        carry=f'继承{emotion}和解释意图' if i==2 else f'继承{emotion}和质问意图'
        carry+='，保持上一镜的注视和手部状态'
        prefix=f'{speaker}带着{emotion}，{purpose}，{tone}，{body}；{trigger}{speaker}'
        second=f'{speaker}{carry}，{purpose}，{tone}，{body}，无停顿承接上一镜'
        shot1=f'50mm平视双人中景，摄影机在桌前，取两人腰部以上和桌面，固定；{prefix}开始说：“{fragments[0]}”。{target}听话时嘴唇闭合，呼吸轻缓。'
        shot2=f'50mm说话者胸口以上，摄影机原地保持固定，脸部与肩颈清楚；{second}继续说：“{fragments[1]}”。{target}留在原位听完。'
        header='一' if i==1 else '二'
        group=f'## 分镜组{header} 测试事件{i} 8秒\n```text\n{global_text}\n\n张三=张三音色=\n李四=李四音色=\n古装柜台日景=\n账本=\n抹布=\n【摄影机运动总设定】\n摄影机在柜台南侧，两个镜头固定，由人物表演推进。\n【场景与光影】\n古装柜台日景，窗光来自桌面右侧，背景可辨。\n【起始站位】\n张三在桌左侧面向右侧李四；账本在张三手边，抹布在李四右手。\n【语言连续性总锁】\n本组一句话跨镜不断声，情绪、意图和身体状态继承。\n【0—4秒】：{shot1}视频严禁出现台词、内心独白与系统语音字幕。\n【4—8秒】：{shot2}视频严禁出现台词、内心独白与系统语音字幕。\n```\n'
        if i==1:group+='剪辑衔接：张三问完保持注视，下一组从双人中景接李四停止擦桌后解释，账本与抹布位置继承。\n'
        groups.append(group)
        units=[{'语言单元ID':f'句{i}','类型':'对白','说话人':speaker,'完整原文':''.join(fragments),'逐句表演':dict(zip(V.FIELDS,[emotion,purpose,tone,body])),'建议片段':[{'原文片段':f,'表演承接':carry} for f in fragments]}]
        plans.append({'不可修改原文台词':[{'说话人':speaker,'原文':''.join(fragments)}],'语言单元':units})
        rows=[]
        for si in (1,2):
            evidence=dict(zip(V.FIELDS,[emotion,purpose,tone,body]))
            evidence['触发' if si==1 else '情绪与身体承接']=trigger if si==1 else carry
            rows.append({'shot':si,'speaker':speaker,'evidence':evidence,'timing':{'offset':1 if si==1 else 0,'duration':3 if si==1 else 1.5,'basis':'ESTIMATED'}})
        reviews.append({'utterances':rows})
    doc='# 仿真人两组文字回归样本\n项目时长规划：16秒测试。\n时长例外说明：仅测试交接，不制作整集；无成品资产，时间为估算。\n'+ '\n'.join(groups)
    return doc,{'model_profile':'seedance-2.5','render_mode':'仿真人','aspect_ratio':'9:16','groups':reviews},global_text,plans

class HandoffTests(unittest.TestCase):
    def check(self,doc,record,glob,plans):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'prompt.md';p.write_text(doc,encoding='utf-8')
            return V.validate(p,record,glob,plans)
    def test_valid_full_live_action_two_groups(self):
        self.assertEqual(self.check(*fixture()),[])
    def test_missing_each_performance_item(self):
        for field in V.FIELDS:
            with self.subTest(field=field):
                d,r,g,p=fixture();del r['groups'][0]['utterances'][0]['evidence'][field]
                self.assertTrue(self.check(d,r,g,p))
    def test_emotion_lost_from_actual_prompt(self):
        d,r,g,p=fixture();d=d.replace('克制的愤怒','低声')
        self.assertTrue(self.check(d,r,g,p))
    def test_cross_shot_emotion_inheritance_lost(self):
        d,r,g,p=fixture();del r['groups'][0]['utterances'][1]['evidence']['情绪与身体承接']
        self.assertTrue(self.check(d,r,g,p))
    def test_whole_line_omitted_upstream(self):
        d,r,g,p=fixture();p[0]['语言单元']=[]
        self.assertTrue(self.check(d,r,g,p))
    def test_dialogue_changed(self):
        d,r,g,p=fixture();d=d.replace('骗我？','骗我！')
        self.assertTrue(self.check(d,r,g,p))
    def test_global_all_groups_shortened(self):
        d,r,g,p=fixture();d=d.replace('9:16竖屏全屏构图，','')
        self.assertTrue(self.check(d,r,g,p))
    def test_configuration_aspect_mismatch(self):
        d,r,g,p=fixture();r['aspect_ratio']='16:9'
        self.assertTrue(self.check(d,r,g,p))
    def test_timing_after_trigger_overflows(self):
        d,r,g,p=fixture();r['groups'][0]['utterances'][0]['timing']['offset']=2
        self.assertTrue(self.check(d,r,g,p))
    def test_same_shot_speech_overlap(self):
        d,r,g,p=fixture()
        d=d.replace('\n【4—8秒】：50mm说话者胸口以上','50mm说话者胸口以上',1)
        r['groups'][0]['utterances'][1]['shot']=1
        r['groups'][0]['utterances'][1]['timing']['offset']=2
        self.assertTrue(any('同镜语言重叠' in x for x in self.check(d,r,g,p)))
    def test_unparsed_group(self):
        d,r,g,p=fixture();d+='\n## 分镜组三 坏格式 10秒\n'
        self.assertTrue(self.check(d,r,g,p))
    def test_wrong_speaker(self):
        d,r,g,p=fixture();r['groups'][0]['utterances'][0]['speaker']='李四'
        self.assertTrue(self.check(d,r,g,p))
    def test_repeated_speech(self):
        d,r,g,p=fixture();d=d.replace('开始说：“你为什么”','开始说：“你为什么”开始说：“你为什么”')
        self.assertTrue(self.check(d,r,g,p))
    def test_model_duration_limit(self):
        d,r,g,p=fixture();r['model_profile']='seedance-2.0';d=d.replace('8秒','16秒').replace('【4—8秒】','【4—16秒】')
        self.assertTrue(any('单组上限' in x for x in self.check(d,r,g,p)))

if __name__=='__main__':unittest.main()
