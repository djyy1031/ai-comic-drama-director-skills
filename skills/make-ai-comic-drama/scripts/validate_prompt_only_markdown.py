#!/usr/bin/env python3
"""Validate a prompt-only storyboard Markdown deliverable."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

GROUP_RE = re.compile(
    r"^## 分镜组([^\n]+?)\s+(\d+(?:\.\d+)?)秒\s*\n\s*```text\n(.*?)\n```",
    flags=re.M | re.S,
)
SHOT_RE = re.compile(r"^【(\d+(?:\.\d+)?)—(\d+(?:\.\d+)?)秒】：(.+)$", flags=re.M)
BINDING_RE = re.compile(r"^[^【\s][^=\n]{0,80}=[^\n]*$")
START_MARKERS = ("开始说：", "开始内心独白：", "开始画外音：", "开始旁白：", "开始系统语音：")
CONTINUE_MARKERS = ("继续说：", "继续内心独白：", "继续画外音：", "继续旁白：", "继续系统语音：")
LANGUAGE_MARKERS = START_MARKERS + CONTINUE_MARKERS
SUBTITLE_SUFFIX = "视频严禁出现台词、内心独白与系统语音字幕。"
BANNED_TRACKS = ("【连续语言音轨总设定】", "【连续对白音轨总设定】", "音轨覆盖")

def _asset_block_and_global(body: str) -> tuple[list[str], str] | tuple[None, None]:
    camera = "【摄影机运动总设定】"
    if body.count(camera) != 1:
        return None, None
    before_camera = body.split(camera, 1)[0]
    lines = before_camera.splitlines()
    cursor = len(lines) - 1
    while cursor >= 0 and not lines[cursor].strip():
        cursor -= 1
    end = cursor
    while cursor >= 0 and BINDING_RE.fullmatch(lines[cursor].strip()):
        cursor -= 1
    bindings = [line.strip() for line in lines[cursor + 1 : end + 1]]
    global_text = "\n".join(lines[: cursor + 1]).strip()
    return bindings, global_text

def validate(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    matches = list(GROUP_RE.finditer(text))
    groups = [match.groups() for match in matches]
    if not groups:
        return ["没有找到“## 分镜组…秒”及其独立 ```text 代码块"]
    if "项目时长规划：" not in text:
        errors.append("文档开头必须写“项目时长规划：”，说明用户软目标与本集实际安排")

    for phrase in BANNED_TRACKS:
        if phrase in text:
            errors.append(f"发现旧式独立音轨写法：{phrase}")

    locked_global: str | None = None
    total_duration = 0.0
    for group_index, (name, duration_text, body) in enumerate(groups, start=1):
        label = f"分镜组{group_index}（{name.strip()}）"
        duration = float(duration_text)
        total_duration += duration
        if not body.startswith("【全局固定画质参数】\n"):
            errors.append(f"{label}：代码块第一行不是【全局固定画质参数】")
        if "【全局通用负面提示词】" not in body:
            errors.append(f"{label}：缺少【全局通用负面提示词】")

        bindings, global_text = _asset_block_and_global(body)
        if bindings is None:
            errors.append(f"{label}：【摄影机运动总设定】必须且只能出现一次")
            continue
        if len(bindings) < 2:
            errors.append(f"{label}：摄影机总设定前至少需要角色/音色与场景等实际资产绑定")
        if any(not BINDING_RE.fullmatch(line) for line in bindings):
            errors.append(f"{label}：资产绑定必须逐行使用“标准名称=”格式")
        if locked_global is None:
            locked_global = global_text
        elif global_text != locked_global:
            errors.append(f"{label}：全局控制提示词与第一组不完全一致，禁止缩写或改写")

        for required in ("【场景与光影】", "【起始站位】", "【语言连续性总锁】"):
            if required not in body:
                errors.append(f"{label}：缺少{required}")

        shots = [(float(start), float(end), content) for start, end, content in SHOT_RE.findall(body)]
        if not shots:
            errors.append(f"{label}：没有找到连续逐镜时间段")
            continue
        if shots[0][0] != 0.0:
            errors.append(f"{label}：第一镜必须从0秒开始")
        for shot_index, (start, end, content) in enumerate(shots, start=1):
            if end <= start:
                errors.append(f"{label}第{shot_index}镜：结束时间必须大于开始时间")
            if shot_index > 1 and start != shots[shot_index - 2][1]:
                errors.append(f"{label}第{shot_index}镜：与上一镜时间不连续")
            if end - start > 6.0 and not (
                "long_take_approved=true" in content and "long_take_reason=" in content
            ):
                errors.append(f"{label}第{shot_index}镜：普通镜头超过6秒且没有明确长镜批准与理由")
            if any(marker in content for marker in LANGUAGE_MARKERS):
                if not content.endswith(SUBTITLE_SUFFIX):
                    errors.append(f"{label}第{shot_index}镜：语言镜必须以固定禁字幕句结束")
            if any(marker in content for marker in START_MARKERS):
                first_marker = min(content.index(marker) for marker in START_MARKERS if marker in content)
                if "后，" not in content[:first_marker]:
                    errors.append(f"{label}第{shot_index}镜：第一次发声前没有明确动作或现场事件触发点")
            if any(marker in content for marker in CONTINUE_MARKERS):
                if "无停顿承接上一镜" not in content:
                    errors.append(f"{label}第{shot_index}镜：续说没有锁定“无停顿承接上一镜”")
        if shots[-1][1] != duration:
            errors.append(f"{label}：末镜结束时间{shots[-1][1]:g}秒与分镜组时长{duration:g}秒不一致")
        if "转场到下一组" in body or "剪辑衔接：" in body:
            errors.append(f"{label}：剪辑衔接必须放在代码块外，正文仅含本组生成内容")
        if group_index < len(groups):
            after_block = text[matches[group_index - 1].end():matches[group_index].start()]
            if not re.search(r"^剪辑衔接：[^\n]+", after_block, flags=re.M):
                errors.append(f"{label}：代码块后必须写“剪辑衔接：”，说明接法、锚点和下一组首镜")

        spoken_fragments = re.findall(
            r"(?:开始|继续)(?:说|内心独白|画外音|旁白|系统语音)：“([^”]*)”",
            body,
        )
        if spoken_fragments and spoken_fragments[-1].endswith(("，", "、", "：", "；")):
            errors.append(f"{label}：最后一个语言片段仍在句中，疑似把同一句拆到下一分镜组")

    if total_duration < 90 and not re.search(r"时长例外说明：\s*\S+", text):
        errors.append("整集低于正常90秒时必须填写“时长例外说明：”")
    if total_duration > 180:
        errors.append("整集总时长不得超过180秒")
    return errors

def main() -> int:
    parser = argparse.ArgumentParser(description="校验仅分镜组提示词 Markdown 文档")
    parser.add_argument("document", type=Path, help="待校验的 Markdown 文档")
    args = parser.parse_args()
    if not args.document.is_file():
        print(f"ERROR: 文件不存在：{args.document}", file=sys.stderr)
        return 2
    errors = validate(args.document)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"PASS: {args.document.name} 的分镜组提示词结构校验通过")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
