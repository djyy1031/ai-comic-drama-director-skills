from pathlib import Path
import importlib.util
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('light',ROOT/'scripts/validate_prompt_light.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sample=(ROOT/'references/approved-two-shots.md').read_text(encoding='utf-8')

class Regression(unittest.TestCase):
    def check(self,text,**kw):
        return module.validate(text,['方澈','许宁'],30,True,**kw)
    def test_approved(self): self.assertEqual(self.check(sample),[])
    def test_late_onset(self): self.assertTrue(any('超过0.5' in x for x in self.check(sample.replace('第0.2秒开口','第1.2秒开口'))))
    def test_serial_action_despite_timestamp(self):
        self.assertTrue(any('动作完成后' in x for x in self.check(sample.replace('第0.2秒开口','对上视线后，第0.2秒开口'))))
    def test_missing_ambience(self): self.assertTrue(any('缺少独立环境' in x for x in self.check(sample.replace('环境与动作音效：','声音：'))))
    def test_subtitle_inline(self): self.assertTrue(any('独立一行禁字幕' in x for x in self.check(sample.replace('\n\n'+module.SUBTITLE,' '+module.SUBTITLE))))
    def test_camera_without_landmark(self): self.assertTrue(any('模糊机位' in x for x in self.check(sample.replace('摄影机位于书店阅读区入口','摄影机位于参考图前方'))))
    def test_group_limit(self): self.assertTrue(any('超过单组' in x for x in self.check(sample.replace('2.5—5.5秒','3—31秒'))))
    def test_explicit_source_exception(self):
        text=sample.replace('第0.2秒开口','第1.2秒开口')
        self.assertEqual(self.check(text,exceptions={'1':{'source_quote':'她放下杯子后才回答。','reason':'原文明确前置动作'}}),[])
    def test_empty_exception_rejected(self):
        self.assertTrue(self.check(sample.replace('第0.2秒开口','第1.2秒开口'),exceptions={'1':{}}))
    def test_no_voice_not_forced(self):
        text='【0—1秒】\n方澈双手近景，摄影机位于备菜台前朝向砧板平视固定。\n\n方澈切菜。\n\n环境与动作音效：轻微切菜声，低于正常对白。'
        self.assertEqual(self.check(text),[])
    def test_full_group_sound_required(self):
        self.assertIn('缺少整组整体环境音效',module.validate(sample,['方澈','许宁'],30))
    def test_full_group_pass(self):
        text=sample+'\n整体环境音效：厨房底声连续，低于对白，全程无背景音乐。\n'
        self.assertEqual(module.validate(text,['方澈','许宁'],30),[])

if __name__=='__main__': unittest.main()
