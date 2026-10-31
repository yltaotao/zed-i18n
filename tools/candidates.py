"""挑出高频界面里尚未翻译的 UI 文案，输出给翻译用。

用法:
    python tools/candidates.py zed zh.json out.tsv [每条最短字符数]

zed      上游源码目录（含 crates/）
zh.json  已翻译的词典，用于排除
out.tsv  输出：每条一行「英文<TAB>建议中文留空」，按界面重要度排序
"""

import json
import re
import sys
from pathlib import Path

HIGH_VALUE = [
    "workspace/", "settings_ui/", "project_panel/", "command_palette", "ui/",
    "agent/", "assistant2/", "editor/", "git_ui/", "terminal_view/", "search/",
    "recent_projects/", "title_bar/", "status_bar/", "extensions_ui/",
    "outline/", "project_symbols/", "file_finder/", "tab_switcher/",
    "welcome/", "onboarding/", "notifications/",
]

UI_TOKENS = (
    "Label::new", "Button::new", "Text::new", "Icon::new", "IconButton", "Tooltip",
    "MenuItem", "menu_item", "ListHeader", "ListItem", "Headline", "Modal",
    "Notification", "notify", "show_error", "set_label", "aria_label", "placeholder",
    "tooltip(", "header(", "title(", "description(", "help(", "subtitle(", "caption(",
    "Dialog", "Banner", "Toast", "empty_state", "Button::label",
)

STRING_RE = re.compile(r'"((?:[^"\\\n]|\\.){2,200})"')
CONTROL = re.compile(r"[\u0000-\u0008\u000b-\u001f]")
PATH_LIKE = re.compile(r"^[A-Za-z0-9_\-/.+]+\.(rs|json|toml|md|png|svg|lock|gz|zip|wasm|txt|yml|yaml)$")
IDENT = re.compile(r"^[a-z0-9_.\-/:]+$")


def decode(literal: str):
    try:
        return json.loads('"' + literal + '"')
    except Exception:
        return None


def acceptable(text: str, min_len: int) -> bool:
    if not (min_len <= len(text) <= 90):
        return False
    if not re.search(r"[A-Za-z]", text) or CONTROL.search(text):
        return False
    if "://" in text or "::" in text or "=>" in text:
        return False
    if PATH_LIKE.match(text) or IDENT.match(text):
        return False
    if not (" " in text or text[0].isupper()):
        return False
    if text.count("%") > 2 or text.startswith(("#", "(", "[", "{", "/", "*", "@", "=")):
        return False
    return True


def main() -> int:
    src = Path(sys.argv[1])
    zh = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    out = Path(sys.argv[3])
    min_len = int(sys.argv[4]) if len(sys.argv) > 4 else 3

    translated = set()
    for entries in zh.values():
        for literal in entries:
            text = decode(literal)
            if text:
                translated.add(text)

    crates = src / "crates"
    buckets: dict[str, dict[str, int]] = {name: {} for name in HIGH_VALUE}
    for path in crates.rglob("*.rs"):
        rel = path.relative_to(crates).as_posix()
        group = next((g for g in HIGH_VALUE if rel.startswith(g)), None)
        if group is None:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in STRING_RE.finditer(content):
            literal = match.group(1)
            line_start = content.rfind("\n", 0, match.start()) + 1
            line_end = content.find("\n", match.end())
            line = content[line_start:line_end if line_end != -1 else len(content)]
            if not any(token in line for token in UI_TOKENS):
                continue
            text = decode(literal)
            if text is None or text in translated or not acceptable(text, min_len):
                continue
            if "\t" in text or "\n" in text:
                continue
            buckets[group][text] = buckets[group].get(text, 0) + 1

    rows, total = [], 0
    for group in HIGH_VALUE:
        for text, count in sorted(buckets[group].items(), key=lambda kv: -kv[1]):
            rows.append(f"{group}\t{count}\t{text}")
            total += 1
    out.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"候选 {total} 条，写入 {out}")
    for group in HIGH_VALUE:
        if buckets[group]:
            print(f"  {group:20s} {len(buckets[group])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
