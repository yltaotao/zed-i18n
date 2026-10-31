"""把词典里的中文替换进 Zed 源码。

用法:
    python replace.py [zh.json]

词典格式 {相对路径: {源码字面量: 中文}}，两边的键和值都是「源码里的转义形态」，
因此匹配是逐字节精确的，不依赖转义还原。
"""

import json
import re
import sys
from pathlib import Path


def main() -> int:
    dict_path = Path(sys.argv[1] if len(sys.argv) > 1 else "zh.json")
    data = json.loads(dict_path.read_text(encoding="utf-8"))

    missing_files: list[str] = []
    entries = replaced = 0

    for rel_path, messages in data.items():
        target = Path(rel_path)
        if not target.exists():
            missing_files.append(rel_path)
            continue

        text = target.read_text(encoding="utf-8")
        for literal in sorted(messages, key=len, reverse=True):
            translation = messages[literal]
            if not translation:
                continue
            entries += 1
            pattern = '"' + re.escape(literal) + '"'
            text, count = re.subn(pattern, lambda _m, t=translation: '"' + t + '"', text)
            replaced += count
        target.write_text(text, encoding="utf-8")

    print(f"替换 {replaced} 处，词条 {entries} 条，文件 {len(data)} 个")
    if missing_files:
        print(f"以下 {len(missing_files)} 个文件在上游已不存在：")
        for item in missing_files:
            print("  " + item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
