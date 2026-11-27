#!/usr/bin/env python3
"""Generate and check the module map in ARCHITECTURE.md from each code file's own header line (T138).

  python3 tools/architecture_map.py          rebuild the marked section in ARCHITECTURE.md
  python3 tools/architecture_map.py --check  exit 1 if any code file lacks a header or the section is stale
"""
import ast
import re
import sys
from pathlib import Path

ARCHITECTURE = "ARCHITECTURE.md"
START = "<!-- module map: built by tools/architecture_map.py; don't edit by hand -->"
END = "<!-- end module map -->"
FOLDERS = ("viewport", "viewport/tools", "worker", "tools")
EXTENSIONS = {".gd", ".py", ".sh"}
WRAPPER_LINE = "`tools/<NAME>.py|.sh` — one named script per action, listed in tools/README.md (H154)"
ALL_CAPS_STEM = re.compile(r"^[A-Z][A-Z0-9_]*$")
MAX_SENTENCE_LEN = 160
MAX_CORE_BYTES = 8 * 1024


def core_bytes(text: str) -> int:
    """Return UTF-8 byte length of ARCHITECTURE.md outside the generated module map."""
    if START not in text or END not in text:
        raise SystemExit(f"{ARCHITECTURE} has no module map markers ({START} ... {END})")
    a = text.index(START)
    b = text.index(END) + len(END)
    return len((text[:a] + text[b:]).encode("utf-8"))


def is_all_caps_wrapper(rel_path: str) -> bool:
    p = Path(rel_path)
    return p.parent.as_posix() == "tools" and bool(ALL_CAPS_STEM.match(p.stem))


def code_files(root: Path) -> list[str]:
    """Return non-test, non-wrapper code files in FOLDERS, grouped by folder and sorted by path."""
    out = []
    for folder in FOLDERS:
        d = root / folder
        if not d.is_dir():
            continue
        items = []
        for f in sorted(d.iterdir(), key=lambda p: p.as_posix()):
            if not f.is_file() or f.suffix not in EXTENSIONS:
                continue
            if f.name.startswith("test_"):
                continue
            rel = f.relative_to(root).as_posix()
            if is_all_caps_wrapper(rel):
                continue
            items.append(rel)
        out.extend(items)
    return out


def _first_sentence(lines: list[str]) -> str:
    para = []
    for line in lines:
        s = line.strip()
        if not s:
            if para:
                break
            continue
        para.append(s)
    if not para:
        return ""
    joined = " ".join(para)
    sentence = re.split(r"\.\s+", joined, maxsplit=1)[0].strip().rstrip(".")
    if len(sentence) > MAX_SENTENCE_LEN:
        sentence = sentence[: MAX_SENTENCE_LEN - 1].rstrip() + "…"
    return sentence


def _parse_gd_header(text: str) -> str:
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s or s == "@tool" or s.startswith("extends ") or s.startswith("class_name "):
            i += 1
            continue
        break
    doc_lines = []
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("##"):
            doc_lines.append(s[2:].strip())
            i += 1
        else:
            break
    return _first_sentence(doc_lines)


def _parse_py_header(text: str, path: str) -> str:
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError:
        return ""
    doc = ast.get_docstring(tree, clean=True)
    if not doc:
        return ""
    return _first_sentence(doc.splitlines())


def _parse_sh_header(text: str) -> str:
    lines = text.splitlines()
    i = 0
    if lines and lines[0].startswith("#!"):
        i = 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    doc_lines = []
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("#"):
            doc_lines.append(s[1:].strip())
            i += 1
        else:
            break
    return _first_sentence(doc_lines)


def parse_header(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".gd":
        return _parse_gd_header(text)
    if path.suffix == ".py":
        return _parse_py_header(text, path.as_posix())
    if path.suffix == ".sh":
        return _parse_sh_header(text)
    return ""


def expected_header_hint(rel_path: str) -> str:
    if rel_path.endswith(".gd"):
        return "add a `## <description>` line after `extends ...`"
    if rel_path.endswith(".py"):
        return 'add a module docstring (`"""<description>"""`) at the top'
    if rel_path.endswith(".sh"):
        return "add a `# <description>` line after the shebang"
    return "add a header comment"


def build_map(root: Path) -> tuple[str, list[str]]:
    """Return (rendered_section_body, missing_header_paths)."""
    by_folder: dict[str, list[str]] = {f: [] for f in FOLDERS}
    missing: list[str] = []
    for rel in code_files(root):
        folder = Path(rel).parent.as_posix()
        sentence = parse_header(root / rel)
        if not sentence:
            missing.append(rel)
            continue
        by_folder[folder].append(f"- `{rel}` — {sentence}")
    if (root / "tools").is_dir():
        by_folder["tools"].append(f"- {WRAPPER_LINE}")
    blocks = ["\n".join(by_folder[f]) for f in FOLDERS if by_folder[f]]
    return "\n\n".join(blocks), missing


def with_map(text: str, body: str) -> str:
    if START not in text or END not in text:
        raise SystemExit(f"{ARCHITECTURE} has no module map markers ({START} ... {END})")
    a = text.index(START) + len(START)
    b = text.index(END)
    return text[:a] + "\n\n" + body + "\n\n" + text[b:]


_MAP_LINE_RE = re.compile(r"^- `([^`]+)`\s+—\s+(.*)$")
_WRAPPER_PATH = "tools/<NAME>.py|.sh"


def _parse_map(text: str) -> dict[str, str]:
    """Extract {rel_path: header_sentence} from ARCHITECTURE.md or a module-map body."""
    if START in text and END in text:
        text = text[text.index(START) + len(START):text.index(END)]
    entries: dict[str, str] = {}
    for line in text.splitlines():
        m = _MAP_LINE_RE.match(line.strip())
        if not m:
            continue
        rel, sentence = m.group(1), m.group(2).strip()
        if rel == _WRAPPER_PATH:
            continue
        entries[rel] = sentence
    return entries


def diff(old_text: str, new_text: str) -> dict[str, list]:
    """Return {'added': [...], 'removed': [...], 'changed': [(path, old, new), ...]} between two module maps."""
    old = _parse_map(old_text)
    new = _parse_map(new_text)
    return {
        "added": sorted(p for p in new if p not in old),
        "removed": sorted(p for p in old if p not in new),
        "changed": [(p, old[p], new[p]) for p in sorted(old) if p in new and old[p] != new[p]],
    }


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    check_only = "--check" in args
    unknown = [a for a in args if a != "--check"]
    if unknown:
        print(f"usage: python3 tools/architecture_map.py [--check]", file=sys.stderr)
        return 2

    root = Path.cwd()
    body, missing = build_map(root)
    if missing:
        for rel in missing:
            print(f"missing header in {rel}: {expected_header_hint(rel)}", file=sys.stderr)
        return 1

    arch_path = root / ARCHITECTURE
    text = arch_path.read_text(encoding="utf-8")
    new_text = with_map(text, body)
    if check_only:
        if new_text != text:
            print(f"{ARCHITECTURE} module map is out of date; run: python3 tools/architecture_map.py", file=sys.stderr)
            return 1
        size = core_bytes(text)
        if size > MAX_CORE_BYTES:
            over = size - MAX_CORE_BYTES
            print(f"{ARCHITECTURE} hand-written core is {over} bytes over the {MAX_CORE_BYTES}-byte limit ({size} B)", file=sys.stderr)
            return 1
        return 0
    if new_text != text:
        arch_path.write_text(new_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
