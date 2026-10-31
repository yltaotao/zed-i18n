"""从 Zed 上游源码提取候选 UI 字符串。

用法:
    python tools/extract.py zed strings.json need.json

输入 zed 为上游源码根目录（含 crates/），输出:
    strings.json  {源文件相对路径: {源码字面量: ""}}，字面量保持源码里的转义形态
    need.json     {解码后的英文原文: null}，等待翻译的唯一文本
"""

import json
import re
import sys
from pathlib import Path

STRING_RE = re.compile(r'"((?:[^"\\\n]|\\.){2,200})"')
SKIP_DIRS = {"tests", "benches", "examples", "fixtures", "test_fixtures", "target", ".git"}
PATH_LIKE = re.compile(r"^[A-Za-z0-9_\-/.+]+\.(rs|json|toml|md|png|svg|lock|gz|zip|wasm|txt|yml|yaml)$")
IDENT = re.compile(r"^[a-z0-9_.\-/:]+$")
IDENT_ANY = re.compile(r"^[A-Za-z0-9_\-./:]+$")
CONTROL = re.compile(r"[\u0000-\u0008\u000b-\u001f]")


def decode(literal: str):
    try:
        return json.loads('"' + literal + '"')
    except Exception:
        return None


def encode(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)[1:-1]


def looks_ui(text: str) -> bool:
    if not (3 <= len(text) <= 120):
        return False
    if not re.search(r"[A-Za-z]", text):
        return False
    if CONTROL.search(text):
        return False
    if "://" in text or "::" in text or "=>" in text or "\\u{" in text:
        return False
    if PATH_LIKE.match(text):
        return False
    if IDENT.match(text):
        return False
    if IDENT_ANY.match(text) and " " not in text and text[0].islower():
        return False
    if not (" " in text or text[0].isupper()):
        return False
    if text.count("%") > 2 or text.count("&") > 1:
        return False
    if text.startswith(("#", "(", "[", "{", "/", "*", "@", "=", "-", "_")):
        return False
    if text.endswith(("(", "=>", ",", ":=", "::")):
        return False
    return True


def main() -> int:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "zed")
    out_strings = Path(sys.argv[2] if len(sys.argv) > 2 else "strings.json")
    out_need = Path(sys.argv[3] if len(sys.argv) > 3 else "need.json")
    prefix = sys.argv[4] if len(sys.argv) > 4 else src.name

    crates = src / "crates"
    if not crates.is_dir():
        print(f"找不到 {crates}", file=sys.stderr)
        return 1

    strings: dict[str, dict[str, str]] = {}
    need: dict[str, None] = {}
    for path in sorted(crates.rglob("*.rs")):
        if SKIP_DIRS & set(p.lower() for p in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = prefix + "/" + path.relative_to(src).as_posix()
        found: dict[str, str] = {}
        for match in STRING_RE.finditer(content):
            literal = match.group(1)
            text = decode(literal)
            if text is None or not looks_ui(text):
                continue
            found[literal] = ""
            need.setdefault(text, None)
        if found:
            strings[rel] = found

    out_strings.write_text(json.dumps(strings, ensure_ascii=False, indent=1), encoding="utf-8")
    out_need.write_text(json.dumps(need, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(v) for v in strings.values())
    print(f"文件 {len(strings)} 个，字面量 {total} 条，唯一文本 {len(need)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
