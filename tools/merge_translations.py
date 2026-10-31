"""把 TSV 译文合并进词典。

用法:
    python tools/merge_translations.py strings.json zh.json translations.tsv

strings.json        tools/extract.py 的产物（键为源码字面量）
zh.json             现有词典，原地更新
translations.tsv    「英文<TAB>中文」，英文为源码解码后的文本
"""

import json
import sys
from pathlib import Path


def decode(literal: str) -> str | None:
    try:
        return json.loads('"' + literal + '"')
    except Exception:
        return None


def encode(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)[1:-1]


def main() -> int:
    strings = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    zh_path = Path(sys.argv[2])
    zh = json.loads(zh_path.read_text(encoding="utf-8")) if zh_path.exists() else {}

    trans: dict[str, str] = {}
    for line in Path(sys.argv[3]).read_text(encoding="utf-8").splitlines():
        if not line.strip() or "\t" not in line:
            continue
        en, cn = line.split("\t", 1)
        trans[en.strip()] = cn.strip()

    used: set[str] = set()
    added = 0
    for rel, literals in strings.items():
        per_file = zh.setdefault(rel, {})
        for literal in literals:
            if literal in per_file:
                continue
            text = decode(literal)
            if text is None or text not in trans:
                continue
            per_file[literal] = encode(trans[text])
            used.add(text)
            added += 1
        if not per_file:
            del zh[rel]

    zh = {k: v for k, v in sorted(zh.items()) if v}
    zh_path.write_text(json.dumps(zh, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"新增 {added} 条，词条总数 {sum(len(v) for v in zh.values())}，文件 {len(zh)} 个")
    unused = set(trans) - used
    if unused:
        print(f"TSV 里有 {len(unused)} 条未匹配到源码（多半已翻译或拼写不符）：")
        for item in sorted(unused)[:10]:
            print("  " + item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
