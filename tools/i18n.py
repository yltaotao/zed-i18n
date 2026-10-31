"""Zed 汉化工具（唯一入口，全部功能都在这里）。

三步走：
    python tools/i18n.py extract <上游源码目录> [--prefix zed] [-o strings.json]
        扫源码，把像界面文案的字符串提取出来

    python tools/i18n.py merge [strings.json] [zh.json] [translations.tsv]
        把 translations.tsv 里的新译文合并进 zh.json

    python tools/i18n.py check <上游源码目录> [zh.json]
        校验 zh.json 每一条都能在源码里精确命中，且 {} 占位符没丢

CI 不跑这个文件，它只跑 replace.py（把 zh.json 替换进源码后编译）。
"""

import argparse
import json
import re
from pathlib import Path

STRING_RE = re.compile(r'"((?:[^"\\\n]|\\.){2,200})"')
CONTROL_RE = re.compile(r"[\u0000-\u0008\u000b-\u001f]")
PATH_LIKE_RE = re.compile(
    r"^[A-Za-z0-9_\-/.+]+\.(rs|json|toml|md|png|svg|lock|gz|zip|wasm|txt|yml|yaml)$"
)
LOWER_TOKEN_RE = re.compile(r"^[a-z0-9_.\-/:]+$")
HAN_RE = re.compile(r"[\u4e00-\u9fff]")

# 出现在同一行才算界面文案的构造器，避免把日志、SQL、提示词也翻掉
UI_MARKERS = (
    "Label::new", "Button::new", "Text::new", "Icon::new", "IconButton", "Tooltip",
    "MenuItem", "menu_item", "ListHeader", "ListItem", "Headline", "Modal",
    "Notification", "notify", "show_error", "set_label", "aria_label", "placeholder",
    "tooltip(", "header(", "title(", "description(", "help(", "subtitle(", "caption(",
    "Dialog", "Banner", "Toast", "empty_state", "Button::label",
)


def decode(literal: str):
    """源码里的字面量（含 \\n 这类转义）还原成真实文本。"""
    try:
        return json.loads('"' + literal + '"')
    except Exception:
        return None


def encode(text: str) -> str:
    """真实文本还原成源码里的字面量形态，写回时才能逐字节对上。"""
    return json.dumps(text, ensure_ascii=False)[1:-1]


def read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def looks_like_ui(text: str) -> bool:
    """粗筛：像界面文案，而不是路径、标识符、代码片段。"""
    if not (3 <= len(text) <= 120):
        return False
    if not re.search(r"[A-Za-z]", text) or CONTROL_RE.search(text):
        return False
    if "://" in text or "::" in text or "=>" in text:
        return False
    if PATH_LIKE_RE.match(text) or LOWER_TOKEN_RE.match(text):
        return False
    if not (" " in text or text[0].isupper()):
        return False
    if text.count("%") > 2 or text.startswith(("#", "(", "[", "{", "/", "*", "@", "=")):
        return False
    return True


def scan(src: Path, require_ui_context: bool):
    """遍历 crates/**/*.rs，产出 {(相对路径): {字面量}}。"""
    strings: dict[str, dict[str, str]] = {}
    for path in sorted((src / "crates").rglob("*.rs")):
        if {"tests", "benches", "examples", "fixtures"} & set(p.lower() for p in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        found: dict[str, str] = {}
        for match in STRING_RE.finditer(content):
            literal = match.group(1)
            text = decode(literal)
            if text is None or not looks_like_ui(text):
                continue
            if require_ui_context:
                start = content.rfind("\n", 0, match.start()) + 1
                end = content.find("\n", match.end())
                line = content[start:end if end != -1 else len(content)]
                if not any(marker in line for marker in UI_MARKERS):
                    continue
            found[literal] = ""
        if found:
            strings[path.relative_to(src).as_posix()] = found
    return strings


def cmd_extract(args) -> int:
    strings = scan(Path(args.src), require_ui_context=args.ui_only)
    prefixed = {f"{args.prefix}/{rel}": lits for rel, lits in strings.items()}
    Path(args.output).write_text(json.dumps(prefixed, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(prefixed)} files, {sum(len(v) for v in prefixed.values())} literals -> {args.output}")
    return 0


def cmd_merge(args) -> int:
    strings = read_json(Path(args.strings), {})
    zh_path = Path(args.dictionary)
    zh = read_json(zh_path, {})
    translations = {}
    for line in Path(args.translations).read_text(encoding="utf-8").splitlines():
        if "\t" in line and line.strip():
            english, chinese = line.split("\t", 1)
            translations[english.strip()] = chinese.strip()

    added = 0
    for rel, literals in strings.items():
        per_file = zh.setdefault(rel, {})
        for literal in literals:
            if literal in per_file:
                continue
            text = decode(literal)
            if text and text in translations:
                per_file[literal] = encode(translations[text])
                added += 1
        if not per_file:
            del zh[rel]

    zh = {k: v for k, v in sorted(zh.items()) if v}
    zh_path.write_text(json.dumps(zh, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"added {added}, total {sum(len(v) for v in zh.values())} entries, {len(zh)} files")
    return 0


def cmd_check(args) -> int:
    src = Path(args.src)
    zh = read_json(Path(args.dictionary), {})
    hit = miss = placeholder_ok = 0
    placeholder_bad = []
    for rel, messages in zh.items():
        target = src / rel.split("/", 1)[1]
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
            if literal.count("{}") == chinese.count("{}"):
                placeholder_ok += 1
            else:
                placeholder_bad.append(literal)

    print(f"entries {hit + miss}: matched {hit}, missing {miss}, placeholder ok {placeholder_ok}, bad {len(placeholder_bad)}")
    for literal in placeholder_bad[:5]:
        print(f"  placeholder mismatch: {literal[:60]}")
    return 0 if miss == 0 and not placeholder_bad else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="i18n", description="Zed 汉化工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="扫源码提取候选文案")
    p_extract.add_argument("src", help="上游源码目录")
    p_extract.add_argument("-o", "--output", default="strings.json")
    p_extract.add_argument("--prefix", default="zed", help="写进词典时的路径前缀")
    p_extract.add_argument("--ui-only", action="store_true", help="只保留界面构造器同一行的文案")
    p_extract.set_defaults(func=cmd_extract)

    p_merge = sub.add_parser("merge", help="把 translations.tsv 合并进词典")
    p_merge.add_argument("strings", nargs="?", default="strings.json")
    p_merge.add_argument("dictionary", nargs="?", default="zh.json")
    p_merge.add_argument("translations", nargs="?", default="translations.tsv")
    p_merge.set_defaults(func=cmd_merge)

    p_check = sub.add_parser("check", help="校验词典能否精确命中源码")
    p_check.add_argument("src", help="上游源码目录")
    p_check.add_argument("dictionary", nargs="?", default="zh.json")
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
