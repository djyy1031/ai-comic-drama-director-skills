import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "validate_director_representation.py"
TEMPLATE = ROOT / "assets" / "director-shot-representation.template.json"


class ValidatorTests(unittest.TestCase):
    def run_validator(self, payload):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "director.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

    def test_valid_representation_passes(self):
        data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        data["场景诊断"]["主场景类型"] = "对话与关系"
        data["场景诊断"]["主要剧情功能"] = "改变关系"
        data["场景诊断"]["情绪轨迹"] = "克制到坚定"
        data["镜头设计"][0]["镜头功能"] = "建立关系"
        data["镜头设计"][0]["存在理由"] = "明确两人距离与权力关系"
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_empty_shot_purpose_fails(self):
        data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("镜头功能为空", result.stdout)


if __name__ == "__main__":
    unittest.main()
