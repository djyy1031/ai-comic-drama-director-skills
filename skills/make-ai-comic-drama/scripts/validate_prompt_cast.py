"""Check prompt character scope against an independently frozen internal manifest."""
import argparse
import json
import re
from pathlib import Path


def without_language(body):
    """Ignore only quoted original language; preserve nested Chinese quotation marks."""
    pattern = re.compile(r"(?:开始|继续)(?:说|旁白|内心独白|画外音|系统语音)：[“\"]")
    result, cursor = [], 0
    for match in pattern.finditer(body):
        if match.start() < cursor:
            continue
        result.append(body[cursor:match.end()])
        quote = body[match.end() - 1]
        end, depth = match.end(), 1
        while end < len(body) and depth:
            ch = body[end]
            if quote == '"':
                if ch == '"':
                    depth = 0
            elif ch == '“':
                depth += 1
            elif ch == '”':
                depth -= 1
            end += 1
        if depth:
            # Do not silently hide an unterminated quote and all later instructions.
            result.append(body[match.end():])
            return ''.join(result)
        cursor = end
    result.append(body[cursor:])
    return ''.join(result)


def validate(text, manifest):
    bodies = re.findall(r"```text\s*\n(.*?)\n```", text, re.S)
    known = manifest.get('known_characters')
    groups = manifest.get('groups')
    if not isinstance(known, list) or not known or any(not isinstance(n, str) or not n for n in known):
        return ['known_characters 必须为非空人名列表']
    if not isinstance(groups, list) or len(groups) != len(bodies) or not bodies:
        return ['内部人物清单与生成代码块数量不一致']
    errors = []
    for i, (body, entry) in enumerate(zip(bodies, groups), 1):
        active = entry.get('active_characters') if isinstance(entry, dict) else None
        if not isinstance(active, list) or any(n not in known for n in active):
            errors.append(f'第{i}组 active_characters 必须来自已知人物名单')
            continue
        instructions = without_language(body)
        for name in known:
            if name not in active and name in instructions:
                errors.append(f'第{i}组：非参与人物“{name}”泄漏进生成正文；原文语言之外应删除该名字')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document', type=Path)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    try:
        errors = validate(args.document.read_text(encoding='utf-8'), json.loads(args.manifest.read_text(encoding='utf-8')))
    except (OSError, ValueError, AttributeError) as exc:
        print(f'ERROR: {exc}')
        return 2
    for error in errors:
        print('ERROR: ' + error)
    if not errors:
        print('PASS: 人物范围检查通过；仍需人工核对名单与剧情')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
