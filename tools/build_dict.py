"""把提取结果 + 译文合并成 replace.py 可用的词典。

用法:
    python tools/build_dict.py strings.json old-zh.json translations.json zh.new.json

strings.json      tools/extract.py 的产物，键为源码字面量
old-zh.json       旧词典，用于按英文原文回填既有译文
translations.json {英文原文: 中文}，新增词条的译文
输出 zh.new.json   {相对路径: {源码字面量: 转义后的中文}}
"""

import json
import sys
from pathlib import Path


def decode(literal: str):
    try:
        return json.loads('"' + literal + '"')
    except Exception:
        return None


def encode(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)[1:-1]


def main() -> int:
    strings = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    old = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")) if Path(sys.argv[2]).exists() else {}
    trans_path = Path(sys.argv[3])
    trans = json.loads(trans_path.read_text(encoding="utf-8")) if trans_path.exists() else {}
    out_path = Path(sys.argv[4])

    old_map: dict[str, str] = {}
    for entries in old.values():
        for en, zh in entries.items():
            if zh:
                old_map.setdefault(en, zh)

    result: dict[str, dict[str, str]] = {}
    filled = missing = 0
    missing_texts: dict[str, None] = {}
    for rel, literals in strings.items():
        per_file: dict[str, str] = {}
        for literal in literals:
            text = decode(literal)
            if text is None:
                continue
            zh = trans.get(text) or old_map.get(text)
            if zh:
                per_file[literal] = encode(zh)
                filled += 1
            else:
                missing += 1
                missing_texts.setdefault(text, None)
        if per_file:
            result[rel] = per_file

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已译 {filled} 条，缺译 {missing} 条（去重 {len(missing_texts)} 条），文件 {len(result)} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
