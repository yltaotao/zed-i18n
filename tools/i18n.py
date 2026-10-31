"""Zed 汉化工具。数据只有一个文件：仓库根目录的 zh.json。

日常三条命令：
    python tools/i18n.py add "Learn More" "了解更多" --src D:/zed-upstream
        加一条译文：自动找到源码里哪些文件含这句英文，写进 zh.json

    python tools/i18n.py replace
        把 zh.json 替换进源码（CI 每次构建都跑这条）

    python tools/i18n.py check --src D:/zed-upstream
        校验 zh.json 每条都能在源码里精确命中，且占位符没丢

zh.json 结构：
    {
      "zed/crates/xxx/src/a.rs": {          <- 源码文件（相对仓库根的路径）
        "Learn More": "了解更多",            <- 源码里的字面量: 中文
      }
    }
键必须是源码里的字面量形态（带 \\n 之类的转义），所以不要手写，用 add 生成。
"""

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")


def encode(text: str) -> str:
    """真实文本 -> 源码字面量形态。"""
    return json.dumps(text, ensure_ascii=False)[1:-1]


def read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, data) -> None:
    # 不排序：保留原有键序，新词条追加在末尾，diff 最小
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def resolve(src: Path, rel: str) -> Path:
    """把词典里的路径解析成真实文件。

    词典里的路径带前缀（zed/crates/...）。CI 里源码就在仓库根的 zed/ 下，
    本地校验时 src 直接指向上游源码根，两种布局都支持：先按原路径找，找不到
    就剥掉第一段再找。
    """
    direct = src / rel
    if direct.exists():
        return direct
    _, _, tail = rel.partition("/")
    return src / tail


def cmd_add(args) -> int:
    """把一条译文写进 zh.json：先扫源码，看这句英文出现在哪些文件里。"""
    source = Path(args.src)
    dictionary = Path(args.dictionary)
    crates = source / "crates"
    if not crates.is_dir():
        print(f"ERROR: {source} 下没有 crates/ 目录，--src 要指向上游 zed 源码根目录")
        return 1

    zh = read_json(dictionary, {})
    target = encode(args.english)
    literal = '"' + target + '"'
    chinese = encode(args.chinese)

    if " " not in args.english.strip():
        print("WARN: 单词级词条容易误伤配置键/枚举值，请确认它是界面文案")

    hits = []
    for path in sorted(crates.rglob("*.rs")):
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if literal in content:
            hits.append(f"{args.prefix}/{path.relative_to(source).as_posix()}")

    if not hits:
        print(f'NOT FOUND: no source file contains "{args.english}"')
        return 1

    changed = False
    updated = False
    for rel in hits:
        entry = zh.setdefault(rel, {})
        if entry.get(target) == chinese:
            continue
        updated = updated or target in entry
        entry[target] = chinese
        changed = True

    if not changed:
        print(f'unchanged: "{args.english}" already translated in {len(hits)} file(s)')
        return 0

    write_json(dictionary, zh)
    verb = "updated" if updated else "added"
    print(f'{verb} "{args.english}" -> "{args.chinese}" in {len(hits)} file(s)')
    for rel in hits:
        print("  " + rel)
    print(f"total {sum(len(v) for v in zh.values())} entries, {len(zh)} files")
    return 0


def cmd_replace(args) -> int:
    """把 zh.json 里的中文替换进源码。CI 实际跑的就是这个子命令。"""
    data = read_json(Path(args.dictionary), {})
    root = Path(args.root)
    missing_files = []
    stale = []
    entries = replaced = 0

    for rel, messages in data.items():
        target = resolve(root, rel)
        if not target.exists():
            missing_files.append(rel)
            continue
        # newline="" 保留原文件的换行符，避免 Windows 上 LF 被改成 CRLF
        with open(target, "r", encoding="utf-8", newline="") as f:
            original = f.read()
        text = original
        for literal in sorted(messages, key=len, reverse=True):
            translation = messages[literal]
            if not translation:
                continue
            entries += 1
            pattern = '"' + re.escape(literal) + '"'
            text, count = re.subn(pattern, lambda _m, t=translation: '"' + t + '"', text)
            replaced += count
            if count == 0:
                stale.append(f"{rel}: {literal[:60]}")
        if text != original:
            with open(target, "w", encoding="utf-8", newline="") as f:
                f.write(text)

    print(f"replaced {replaced} occurrences, {entries} entries, {len(data)} files")
    if missing_files:
        print(f"{len(missing_files)} files no longer exist upstream:")
        for item in missing_files[:20]:
            print("  " + item)
    if stale:
        print(f"{len(stale)} entries not found in source (upstream wording changed?):")
        for item in stale[:20]:
            print("  " + item)
    if replaced == 0:
        print("ERROR: nothing was replaced - dictionary keys or checkout path are wrong")
        return 1
    return 0


def cmd_check(args) -> int:
    """校验词典与源码是否严格对得上。"""
    source = Path(args.src)
    zh = read_json(Path(args.dictionary), {})
    hit = miss = placeholder_ok = 0
    placeholder_bad = []

    for rel, messages in zh.items():
        target = resolve(source, rel)
        if not target.exists():
            print(f"missing file: {rel}")
            miss += len(messages)
            continue
        content = target.read_text(encoding="utf-8")
        for literal, chinese in messages.items():
            if ('"' + literal + '"') not in content:
                miss += 1
                continue
            hit += 1
            if len(PLACEHOLDER_RE.findall(literal)) == len(PLACEHOLDER_RE.findall(chinese)):
                placeholder_ok += 1
            else:
                placeholder_bad.append(literal)

    print(f"entries {hit + miss}: matched {hit}, missing {miss}, placeholder ok {placeholder_ok}, bad {len(placeholder_bad)}")
    for literal in placeholder_bad[:5]:
        print(f"  placeholder mismatch: {literal[:60]}")
    return 0 if miss == 0 and not placeholder_bad else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="i18n", description="Zed 汉化工具，数据在 zh.json")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="加一条译文")
    p_add.add_argument("english")
    p_add.add_argument("chinese")
    p_add.add_argument("--src", default=".", help="上游源码目录（含 crates/）")
    p_add.add_argument("--prefix", default="zed", help="写进词典时的路径前缀")
    p_add.add_argument("--dictionary", default="zh.json")
    p_add.set_defaults(func=cmd_add)

    p_replace = sub.add_parser("replace", help="把词典替换进源码（CI 用）")
    p_replace.add_argument("--dictionary", default="zh.json")
    p_replace.add_argument("--root", default=".", help="源码所在目录，词典里的路径相对它")
    p_replace.set_defaults(func=cmd_replace)

    p_check = sub.add_parser("check", help="校验词典能否精确命中源码")
    p_check.add_argument("--src", default=".", help="上游源码目录（含 crates/）")
    p_check.add_argument("--dictionary", default="zh.json")
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
