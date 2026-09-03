#!/usr/bin/env python3
"""AI 漫剧自动检查脚本的共用功能。"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable


Issue = dict[str, Any]


def issue(level: str, code: str, message: str, path: str = "") -> Issue:
    item: Issue = {"level": level, "code": code, "message": message}
    if path:
        item["path"] = path
    return item


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load_project(path: str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("校验数据最外层必须是一个完整项目对象。")
    return data


def run_cli(name: str, validator: Callable[[dict[str, Any]], list[Issue]]) -> None:
    parser = argparse.ArgumentParser(description=name)
    parser.add_argument("project_json", help="结构化校验数据文件路径")
    parser.add_argument("--json", action="store_true", help="输出给程序读取的结构化结果")
    args = parser.parse_args()
    try:
        issues = validator(load_project(args.project_json))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues = [issue("error", "input.invalid", str(exc), args.project_json)]

    errors = sum(item["level"] == "error" for item in issues)
    warnings = sum(item["level"] == "warning" for item in issues)
    result = {"validator": name, "status": "pass" if errors == 0 else "fail", "errors": errors, "warnings": warnings, "issues": issues}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "通过" if result["status"] == "pass" else "未通过"
        print(f"{name}：{status}（{errors} 个错误，{warnings} 个提醒）")
        for item in issues:
            location = f" [{item.get('path')}]" if item.get("path") else ""
            level = "错误" if item["level"] == "error" else "提醒"
            print(f"- {level} {item['code']}{location}：{item['message']}")
    sys.exit(1 if errors else 0)
