import unittest
from test_skill import valid_payload
import test_skill

class DeliveryTests(unittest.TestCase):
    def check_bad(self,data,expected):
        result=test_skill.SkillTests().run_validator(data)
        self.assertEqual(result.returncode,1,result.stdout)
        self.assertIn(expected,result.stdout)
    def test_each_missing_delivery_dimension(self):
        for key in ('情绪','对象与目的','语气','身体配合'):
            with self.subTest(key=key):
                d=valid_payload();del d['语言单元'][0]['逐句表演'][key]
                self.check_bad(d,key)
    def test_missing_continuation(self):
        d=valid_payload();del d['语言单元'][0]['建议片段'][1]['表演承接']
        self.check_bad(d,'表演承接')
    def test_whole_line_missing(self):
        d=valid_payload();d['语言单元']=[]
        self.check_bad(d,'完整覆盖')
    def test_repeated_source_line_not_silently_deduplicated(self):
        d=valid_payload();d['不可修改原文台词']*=2
        self.check_bad(d,'完整覆盖')

if __name__=='__main__':unittest.main()
