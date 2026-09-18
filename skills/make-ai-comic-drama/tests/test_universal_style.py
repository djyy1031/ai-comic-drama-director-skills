import copy
import unittest
from test_prompt_handoff import fixture
import test_prompt_handoff as handoff_tests
import test_validator as project_tests
from test_validator import base_config,base_manifest,VALIDATOR

class UniversalStyleTests(unittest.TestCase):
    def test_all_styles_ratios_eras_use_same_handoff_checks(self):
        styles={'仿真人':'自然皮肤与真实布料，真人实拍质感','2D':'手绘线条、稳定造型、分层色块','写实3D':'写实三维材质、明确接触与重心','皮克斯式3D':'风格化比例、清晰表情轮廓与柔和立体材质'}
        for model in ['seedance-2.0','seedance-2.5']:
            for style,description in styles.items():
                for ratio in ['16:9','9:16','1:1']:
                    for era in ['古装','现代']:
                        with self.subTest(model=model,style=style,ratio=ratio,era=era):
                            doc,record,old,plans=fixture()
                            glob=f'【全局固定画质参数】\n{ratio}全屏构图，{era}，{description}。\n【全局通用负面提示词】\n禁止字幕、水印、背景音乐和无因身份漂移。'
                            doc=doc.replace(old,glob).replace('古装柜台日景',era+'柜台日景')
                            record.update(model_profile=model,render_mode=style,aspect_ratio=ratio)
                            checker=handoff_tests.HandoffTests()
                            self.assertEqual(checker.check(doc,record,glob,plans),[])
                            bad=copy.deepcopy(record);del bad['groups'][0]['utterances'][0]['evidence']['情绪']
                            self.assertTrue(any('情绪' in e for e in checker.check(doc,bad,glob,plans)))

    def test_same_short_scene_valid_in_both_models_without_exception(self):
        for model in ['seedance-2.0','seedance-2.5']:
            with self.subTest(model=model):
                checker=project_tests.ValidatorTests()
                result=checker.validate(model,base_manifest(model,15))
                checker.doCleanups()
                self.assertTrue(result.ok,result.errors)

    def test_group_count_preference_optional_and_not_model_specific(self):
        for model in ['seedance-2.0','seedance-2.5']:
            config=base_config(model)
            config['episode']['preferred_max_shot_groups']=None
            config['episode'].pop('seedance_2_5_preferred_group_seconds',None)
            result=VALIDATOR.Result();VALIDATOR.validate_config(config,result)
            self.assertTrue(result.ok,result.errors)

if __name__=='__main__':unittest.main()
