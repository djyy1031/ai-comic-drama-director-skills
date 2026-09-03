from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).parents[1]
VALIDATOR = SKILL_ROOT / "scripts" / "validate_scene_family.py"


def valid_package() -> dict:
    return {
        "schema_version": "1.1",
        "project_name": "通用测试",
        "series_color_bible": {
            "version": "1.0",
            "status": "APPROVED",
            "swatches": [{"name": "旧木褐", "hex": "#6F5238", "role": "木结构", "prompt_terms": ["低饱和旧木褐"]}],
            "grade_profile": {
                "saturation": "低饱和",
                "contrast": "中等",
                "black_level": "保留纹理",
                "highlight_temperature": "中性微暖",
                "shadow_tint": "中性略冷",
                "forbidden_casts": ["荧光色"],
            },
        },
        "scene_families": [{
            "asset_id": "农户小院",
            "canonical_name": "农户小院",
            "version": "1.0",
            "base_environment_state": {"state_id": "DAY_CLEAR_BASE", "time": "DAY", "weather": "CLEAR", "source_basis": "DEFAULT_CLEAR_DAY"},
            "visual_dna": {"era_region": "宋代"},
            "spatial_model": {"connections": ["院门通往院内"]},
            "anchor_strategy": {"anchor_type": "院内全景"},
            "assets": [{
                "asset_id": "院内母资产",
                "canonical_name": "院内母资产",
                "asset_type": "ZONE_MASTER",
                "version": "1.0",
                "parent_asset_id": "农户小院",
                "parent_version": "1.0",
                "color_bible_version": "1.0",
                "environment_state_id": "DAY_CLEAR_BASE",
                "scene_content_layers": {"structural_fixed": ["院墙"]},
                "prompt": "宋代农户小院晴朗白天场景。",
            }],
            "generation_batches": [{
                "batch_id": "第一批",
                "scene_family_id": "农户小院",
                "visual_dna_version": "1.0",
                "state_version": "DAY_CLEAR_BASE",
                "generation_mode": "SEPARATE_IMAGES",
                "workflow_mode": "ONE_CLICK_DRAFT_SET",
                "max_outputs": 1,
                "forbid_composite": True,
                "anchor_asset_ids": [],
                "shared_scene_brief": "同一座农户小院",
                "production_ready": False,
                "asset_ids": ["院内母资产"],
            }],
            "environment_variants": [{
                "variant_id": "雨夜",
                "reference_asset_id": "院内母资产",
                "target_time": "NIGHT",
                "target_weather": "RAIN",
                "episode_usage": [12],
                "source_evidence": ["第12集雨夜"],
                "allowed_environment_delta": ["夜间光线", "雨线"],
                "locked_unchanged": ["摄影机", "格局", "物件", "材质"],
                "color_bible_version": "1.0",
                "variant_prompt": "引用院内母资产，只改为雨夜。",
                "status": "PENDING",
            }],
        }],
    }


def run_validator(data: dict) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "package.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            [sys.executable, "-B", str(VALIDATOR), str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )


class ScenePackageValidatorTests(unittest.TestCase):
    def test_accepts_color_day_base_and_episode_variant(self):
        result = run_validator(valid_package())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_night_base_and_missing_episode_usage(self):
        data = valid_package()
        family = data["scene_families"][0]
        family["base_environment_state"]["time"] = "NIGHT"
        family["environment_variants"][0]["episode_usage"] = []
        result = run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("必须为 DAY", result.stdout)
        self.assertIn("episode_usage", result.stdout)


if __name__ == "__main__":
    unittest.main()
