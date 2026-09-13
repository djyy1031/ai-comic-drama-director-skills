import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('cast_validator', Path(__file__).parents[1] / 'scripts/validate_prompt_cast.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CastScopeTests(unittest.TestCase):
    def check(self, body, active=None):
        return module.validate('```text\n' + body + '\n```', {
            'known_characters': ['甲', '乙', '丙'],
            'groups': [{'active_characters': ['甲', '乙'] if active is None else active}],
        })

    def test_departed_character_in_negative_instruction_fails(self):
        self.assertTrue(self.check('甲=\n乙=\n丙已经离开，不在画面。'))

    def test_unused_binding_fails(self):
        self.assertTrue(self.check('甲=\n丙=\n甲看向乙。'))

    def test_language_mention_does_not_activate_character(self):
        self.assertEqual(self.check('甲开始说：“等丙回来。”乙抬眼。'), [])

    def test_nested_original_quotes_are_preserved(self):
        self.assertEqual(self.check('甲开始旁白：“乙说“等丙回来”。于是离开。”'), [])

    def test_instruction_after_quote_still_checked(self):
        self.assertTrue(self.check('甲开始说：“等丙回来。”禁止丙入画。'))

    def test_actual_offscreen_speaker_is_allowed(self):
        self.assertEqual(self.check('丙=丙音色=\n丙开始画外音：“停下。”', ['甲', '乙', '丙']), [])

    def test_broken_quote_cannot_hide_later_instructions(self):
        self.assertTrue(self.check('甲开始说：“等候。\n丙不在画面。'))

    def test_count_mismatch_fails(self):
        self.assertTrue(module.validate('```text\n甲\n```', {'known_characters': ['甲'], 'groups': []}))


if __name__ == '__main__':
    unittest.main()
