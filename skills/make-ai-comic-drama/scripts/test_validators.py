#!/usr/bin/env python3
"""四个自动检查脚本的回归测试。"""

from __future__ import annotations

import copy
import unittest

import validate_continuity
import validate_entities
import validate_shot_limits
import validate_timeline


def fixture() -> dict:
    state = {
        "characters": {"CHR-001": {"costume_id": "CST-001", "screen_position": "center", "pose": "standing", "expression": "neutral", "eyeline": "forward", "injury_state": "none"}},
        "props": {"PROP-001": {"holder": "CHR-001", "hand": "right", "position": "waist", "state": "intact"}},
        "location": {"location_id": "LOC-001", "lighting": "day-key-left", "camera_side": "axis-a"},
    }
    return {
        "project_id": "PRJ-001", "episode_id": "EP-001", "episode_target_seconds": 10.0,
        "timeline_tolerance_seconds": 0.01,
        "model_profile": {"model": "已验证模型", "version": "v1", "segment_max_seconds": 10.0, "max_shots_per_segment": 2, "supports_multi_shot": True, "identity_reference_limit": 2, "scene_reference_limit": 1},
        "entities": {
            "characters": [{"character_id": "CHR-001"}], "locations": [{"location_id": "LOC-001"}],
            "props": [{"prop_id": "PROP-001"}], "costumes": [{"costume_id": "CST-001", "character_id": "CHR-001"}],
            "references": [{"reference_id": "REF-001"}],
        },
        "scenes": [{"scene_id": "SC-001", "location_id": "LOC-001"}],
        "shots": [
            {"shot_id": "SH-001", "scene_id": "SC-001", "timeline_in": 0.0, "timeline_out": 5.0, "duration": 5.0, "character_ids": ["CHR-001"], "location_id": "LOC-001", "prop_ids": ["PROP-001"], "costume_ids": ["CST-001"], "reference_ids": ["REF-001"], "start_state": copy.deepcopy(state), "end_state": copy.deepcopy(state)},
            {"shot_id": "SH-002", "scene_id": "SC-001", "timeline_in": 5.0, "timeline_out": 10.0, "duration": 5.0, "character_ids": ["CHR-001"], "location_id": "LOC-001", "prop_ids": ["PROP-001"], "costume_ids": ["CST-001"], "reference_ids": ["REF-001"], "start_state": copy.deepcopy(state), "end_state": copy.deepcopy(state)},
        ],
        "segments": [{"segment_id": "SEG-001", "shot_ids": ["SH-001", "SH-002"], "duration": 10.0, "character_reference_ids": ["REF-001"], "scene_reference_ids": ["REF-001"], "fallback": "动作简化"}],
    }


class ValidatorTests(unittest.TestCase):
    def assert_no_errors(self, issues: list[dict]) -> None:
        self.assertEqual([], [item for item in issues if item["level"] == "error"])

    def test_valid_data(self) -> None:
        data = fixture()
        for validator in (validate_timeline.validate, validate_entities.validate, validate_continuity.validate, validate_shot_limits.validate):
            self.assert_no_errors(validator(copy.deepcopy(data)))

    def test_timeline_error(self) -> None:
        data = fixture(); data["shots"][0]["timeline_in"] = 1.0
        codes = {item["code"] for item in validate_timeline.validate(data)}
        self.assertIn("timeline.start", codes); self.assertIn("timeline.duration_mismatch", codes)

    def test_unknown_id(self) -> None:
        data = fixture(); data["shots"][0]["character_ids"] = ["CHR-999"]
        self.assertIn("entity.missing_reference", {item["code"] for item in validate_entities.validate(data)})

    def test_state_mismatch(self) -> None:
        data = fixture(); first = data["shots"][0]; second = copy.deepcopy(first)
        first["timeline_out"], first["duration"] = 5.0, 5.0
        second["shot_id"], second["timeline_in"], second["duration"] = "SH-002", 5.0, 5.0
        second["start_state"]["props"]["PROP-001"]["hand"] = "left"; data["shots"] = [first, second]
        self.assertIn("continuity.mismatch", {item["code"] for item in validate_continuity.validate(data)})

    def test_model_limit(self) -> None:
        data = fixture(); data["model_profile"]["max_shots_per_segment"] = 1; data["model_profile"]["supports_multi_shot"] = False
        codes = {item["code"] for item in validate_shot_limits.validate(data)}
        self.assertIn("limits.multi_shot_unsupported", codes); self.assertIn("limits.shot_count", codes)

    def test_unapproved_long_shot(self) -> None:
        data = fixture(); first = data["shots"][0]; first["timeline_out"] = 10.0; first["duration"] = 10.0
        data["shots"] = [first]; data["segments"][0]["shot_ids"] = ["SH-001"]
        codes = {item["code"] for item in validate_timeline.validate(data)}
        self.assertIn("timeline.long_shot_unapproved", codes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
