#!/usr/bin/env python3
"""The handoff's entries, one file each (T77): docs/handoff/H037-short-slug.md holds one entry, headed
"### H037 — Subject" with the usual Author | Date | Status line. docs/agent-handoff.md keeps the how-to, the rules
and an open list this script builds from the folder, between its two marker lines; don't edit the list by hand.

  python3 tools/handoff.py list            rebuild the open list (tools/number_ids.py does this at every merge)
  python3 tools/handoff.py list --check    exit 1 if the list doesn't match the folder
  python3 tools/handoff.py split           move any entry written straight into docs/agent-handoff.md (a "### H..."
                                           section before "## Archived") into its own file, then rebuild the list;
                                           an entry that has a file and was answered inline (on a branch made
                                           before T77) updates its file, if only responses were added
  python3 tools/handoff.py check [H037 ...]  validate Touches (all open and queued entries by default)
  python3 tools/handoff.py overlaps         list files two open jobs both touch (P11; queued jobs don't count); exit 1 if any
  python3 tools/handoff.py archive H037 [--commit | --push]
                                           move the entry to the bottom of docs/handoff-archive.md, word for word,
                                           and add its line under "Archived" (outcome: its Resolution line); --commit
                                           stages and commits those three files with hooks; --push also pushes main

A new entry on a branch is docs/handoff/H-new-N-slug.md with "### H-new-N — Subject" (N = 1, 2 ...); the
number is given at merge (tools/number_ids.py)."""
import os
import re
import subprocess
import sys
from fnmatch import fnmatchcase

FOLDER = "docs/handoff"
HANDOFF = "docs/agent-handoff.md"
ARCHIVE = "docs/handoff-archive.md"
START = "<!-- open list: built from docs/handoff/ by tools/handoff.py; don't edit by hand -->"
END = "<!-- end of open list -->"
ID = re.compile(r"^H(?:(\d+)|-new-(\d+))")


def order(name):
    m = ID.match(name)
    if not m:
        return (2, 0, name)
    return (0, int(m.group(1)), name) if m.group(1) else (1, int(m.group(2)), name)


def entries(root):
    """[(file name, heading after "### ", {field: value} from the Author line)] in ID order."""
    folder = os.path.join(root, FOLDER)
    out = []
    if not os.path.isdir(folder):
        return out
    for name in sorted((n for n in os.listdir(folder) if n.endswith(".md")), key=order):
        lines = open(os.path.join(folder, name), encoding="utf-8").read().split("\n")
        head = next((l[4:].strip() for l in lines if l.startswith("### ")), name)
        fields = {}
        meta = next((l for l in lines if l.startswith("Author:")), "")
        for part in meta.split(" | "):
            if ":" in part:
                k, v = part.split(":", 1)
                fields[k.strip()] = v.strip()
        out.append((name, head, fields))
    return out


def list_text(root):
    lines = []
    for name, head, f in entries(root):
        extra = f"status: {f.get('Status', '?')}"
        if f.get("For"):
            extra += f"; for: {f['For']}"
        lines.append(f"- [{head}](handoff/{name}) — {extra}")
    return "\n".join(lines) if lines else "(none open)"


def with_list(text, root):
    if START not in text or END not in text:
        raise SystemExit(f"{HANDOFF} has no open-list markers ({START} ... {END})")
    a = text.index(START) + len(START)
    b = text.index(END)
    return text[:a] + "\n\n" + list_text(root) + "\n\n" + text[b:]


def write_list(root):
    path = os.path.join(root, HANDOFF)
    text = open(path, encoding="utf-8").read()
    new = with_list(text, root)
    if new != text:
        open(path, "w", encoding="utf-8").write(new)
    return new != text


def slug(subject):
    words = re.findall(r"[a-z0-9]+", subject.lower())
    return "-".join(words[:6]) or "entry"


def split(root):
    """Move inline "### H..." entries above "## Archived" (but not the template below it) into docs/handoff/;
    put the open-list markers under "## Open exchanges" if they're missing. Returns the files written."""
    path = os.path.join(root, HANDOFF)
    lines = open(path, encoding="utf-8").read().split("\n")
    stop = lines.index("## Archived") if "## Archived" in lines else len(lines)
    keep, written, k = [], [], 0
    while k < len(lines):
        line = lines[k]
        if k < stop and line.startswith("### ") and ID.match(line[4:]):
            j = next((m for m in range(k + 1, len(lines)) if lines[m].startswith("## ") or lines[m].startswith("### ")),
                     len(lines))
            head = line[4:].strip()
            hid = head.split()[0]
            subject = head.split("—", 1)[1] if "—" in head else head[len(hid):]
            name = f"{hid}-{slug(subject)}.md"
            os.makedirs(os.path.join(root, FOLDER), exist_ok=True)
            body = "\n".join(lines[k:j]).strip("\n") + "\n"
            have = [n for n in os.listdir(os.path.join(root, FOLDER)) if n.split("-")[0] == hid and ID.match(hid)
                    and not hid.startswith("H-")]
            if have:
                # a branch made before T77 answered the entry inline: the file plus new responses replaces the file
                name = have[0]
                old = open(os.path.join(root, FOLDER, name), encoding="utf-8").read()
                if not body.startswith(old.rstrip("\n")):
                    raise SystemExit(f"{hid} is in {HANDOFF} and {FOLDER}/{name} differs from it: merge them by hand")
            open(os.path.join(root, FOLDER, name), "w", encoding="utf-8").write(body)
            written.append(name)
            k = j
            continue
        keep.append(line)
        k += 1
    text = "\n".join(keep)
    if written:
        text = re.sub(r"\n{3,}", "\n\n", text)
    if START not in text and "## Open exchanges" in text:
        text = text.replace("## Open exchanges\n", f"## Open exchanges\n\n{START}\n\n{END}\n", 1)
    open(path, "w", encoding="utf-8").write(text)
    write_list(root)
    return written


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def _archive_entry_file(root, hid):
    match = [n for n, _, _ in entries(root) if n.split("-")[0] == hid]
    if len(match) != 1:
        raise SystemExit(f"no single {FOLDER}/{hid}-*.md (found {match})")
    return match[0]


def _preflight_commit(root, entry_name, push=False):
    """Verify git state and .git writability before mutating files so a sandbox retry leaves the tree clean."""
    branch = _git(root, "branch", "--show-current").stdout.strip()
    if push and branch != "main":
        raise SystemExit(f"refused --push: on {branch or '(detached)'!r}, not 'main' (use --commit instead)")
    staged = [l for l in _git(root, "diff", "--cached", "--name-only").stdout.splitlines() if l.strip()]
    if staged:
        raise SystemExit(f"refused --commit: staged changes already present ({', '.join(staged)})")
    targets = [HANDOFF, ARCHIVE, f"{FOLDER}/{entry_name}"]
    if branch == "main" and os.path.exists(os.path.join(root, "BOARD.md")):
        targets.append("BOARD.md")
    dirty = [l for l in _git(root, "status", "--porcelain", "--", *targets).stdout.splitlines() if l.strip()]
    if dirty:
        names = [l[3:] for l in dirty]
        raise SystemExit(f"refused --commit: target files have uncommitted changes ({', '.join(names)})")
    git_dir = _git(root, "rev-parse", "--git-dir").stdout.strip()
    if not git_dir:
        raise SystemExit("cannot commit: not inside a git repository")
    git_dir = git_dir if os.path.isabs(git_dir) else os.path.join(root, git_dir)
    probe = os.path.join(git_dir, f".handoff-write-probe-{os.getpid()}")
    try:
        fd = os.open(probe, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        os.unlink(probe)
    except OSError as exc:
        raise SystemExit(f"cannot commit: .git is not writable ({exc}; re-run outside sandbox)")


def archive(root, hid):
    """Move entry hid (e.g. "H037") to the archive's bottom and index it under "## Archived" (newest first)."""
    entry_name = _archive_entry_file(root, hid)
    path = os.path.join(root, FOLDER, entry_name)
    body = open(path, encoding="utf-8").read().strip("\n")
    head = next(l[4:].strip() for l in body.split("\n") if l.startswith("### "))
    res = [l[len("Resolution:"):].strip() for l in body.split("\n") if l.startswith("Resolution:")]
    outcome = res[-1] if res else "see the archive"
    arch = os.path.join(root, ARCHIVE)
    text = open(arch, encoding="utf-8").read().rstrip("\n")
    open(arch, "w", encoding="utf-8").write(text + "\n\n" + body + "\n")
    hpath = os.path.join(root, HANDOFF)
    lines = open(hpath, encoding="utf-8").read().split("\n")
    a = lines.index("## Archived")
    first = next((k for k in range(a + 1, len(lines)) if lines[k].startswith("- ") or lines[k].startswith("## ")), len(lines))
    lines.insert(first, f"- {head}. Resolved: {outcome}")
    open(hpath, "w", encoding="utf-8").write("\n".join(lines))
    os.remove(path)
    write_list(root)
    return head


def archive_and_commit(root, hid, commit=False, push=False):
    """Archive hid and, when requested, stage+commit with tracked hooks and push main in one step."""
    entry_name = _archive_entry_file(root, hid)
    if commit or push:
        _preflight_commit(root, entry_name, push=push)
    head = archive(root, hid)
    if not (commit or push):
        return head, None, False
    add = _git(root, "add", "--", HANDOFF, ARCHIVE, f"{FOLDER}/{entry_name}")
    if add.returncode != 0:
        raise SystemExit(f"archived {head}, but git add failed: {(add.stderr or add.stdout).strip()}")
    commit_cmd = (["-c", "core.hooksPath=.githooks"] if os.path.isdir(os.path.join(root, ".githooks")) else [])
    commit_cmd += ["commit", "-m", f"Archive {head}"]
    done = _git(root, *commit_cmd)
    if done.returncode != 0:
        raise SystemExit(f"archived {head}, but git commit failed: {(done.stderr or done.stdout).strip()}")
    sha = _git(root, "rev-parse", "--short", "HEAD").stdout.strip()
    if push:
        pushed = _git(root, "push", "-q", "origin", "main")
        if pushed.returncode != 0:
            raise SystemExit(f"archived and committed {sha}, but git push failed: {(pushed.stderr or pushed.stdout).strip()}")
    return head, sha, push


PATH = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)+(?:[\w.*-]+)?|[\w-]+\.(?:md|py|gd|sh|json|cfg|gdshader))(?![\w/])")
TOP = {"ARCHITECTURE.md", "CLAUDE.md", "AGENTS.md", "GEMINI.md", "BOARD.md", "README.txt", "FREECAD_FEATURE_MAP.md"}
SKIP = re.compile(r"^(not |read-only|if |nothing |no )", re.I)
NOT_ASIDE = re.compile(r"\((?:not|don't|do not|never)\b[^()]*\)", re.I)


def touches(body):
    """The paths a job says it will change in its Touches paragraph."""
    return set(touches_named(body))


def _listed_names(text, start):
    """Read backticked identifiers inside the parenthetical directly after a path."""
    opening = re.compile(r"`?\s*\(").match(text, start)
    if not opening:
        return None
    depth = 1
    names = set()
    for token in re.compile(r"`([^`]+)`|[()]").finditer(text, opening.end()):
        name = token.group(1)
        if name is not None:
            if re.fullmatch(r"[A-Za-z_]\w*(?:\(\))?", name):
                names.add(name.removesuffix("()"))
        elif token.group() == "(":
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return names or None
    return None


def touches_named(body):
    """Map each Touches path to its named functions or constants, or None for the whole path."""
    lines = body.split("\n")
    k = next((i for i, l in enumerate(lines) if l.startswith("Touches:")), None)
    if k is None:
        return {}
    para = []
    for l in lines[k:]:
        if not l.strip():
            break
        para.append(l)
    text = " ".join(para)[len("Touches:"):]
    text = NOT_ASIDE.sub("", text)      # "(don't add it to tools/x.sh: ...)" names a file the job stays off
    out = {}
    # Keep each sentence's offset so an annotation can extend across a sentence boundary.
    offset = 0
    for sentence in re.split(r"(?<=[.;])(?=\s+[A-Z(])", text):
        if not SKIP.match(sentence.strip()):
            for match in PATH.finditer(sentence):
                path = match.group(1).rstrip(".,;:")
                if "/" not in path and path not in TOP:
                    continue
                name = path.rsplit("/", 1)[-1]
                names = _listed_names(text, offset + match.end()) if "." in name and "*" not in name else None
                if path not in out or names is None:
                    out[path] = names
                elif out[path] is not None:
                    out[path].update(names)
        offset += len(sentence)
    return out


# The linter also sees tokens the overlap parser cannot use, such as bare file names and globs.
TOUCHES_PARAGRAPH = re.compile(r"^Touches:([^\n]*(?:\n(?![^\S\n]*$)[^\n]+)*)", re.M)
TOUCHES_WORD = re.compile(
    r"(?<![\w/.*-])((?:[\w.*-]+/)+[\w.*-]*|[\w.-]+\.(?:gd|py|sh|md|json|tscn|cfg)\b"
    r"|README\.txt\b|[\w.*-]*\*[\w.*-]*)(?![\w/*-]|\.[\w.*-])"
)
NEW_BEFORE = re.compile(r"\ba new\s+`?$", re.I)
NEW_AFTER = re.compile(r"^`?\s*\(new\)", re.I)


def touches_problems(body, exists):
    """Yield (problem, word) pairs from the brief's Touches paragraph."""
    paragraph = TOUCHES_PARAGRAPH.search(body)
    if not paragraph:
        return
    text = NOT_ASIDE.sub("", " ".join(paragraph[1].splitlines()))
    for sentence in re.split(r"(?<=[.;])(?=\s+[A-Z(])", text):
        if SKIP.match(sentence.strip()):
            continue
        for match in TOUCHES_WORD.finditer(sentence):
            word = match[1].rstrip(".")
            if "*" in word:
                yield "glob", word
            elif "/" not in word and word not in TOP:
                yield "bare file name", word
            elif not (
                NEW_BEFORE.search(sentence[:match.start()])
                or NEW_AFTER.match(sentence[match.end():])
                or exists(word)
            ):
                yield "path does not exist", word


def staged_briefs(root):
    """Yield staged handoff text and a predicate for paths in the proposed commit."""
    def git(*args):
        return subprocess.check_output(("git", *args), cwd=root).decode("utf-8")

    changed = git("diff", "--cached", "--no-renames", "--diff-filter=AM", "--name-only", "-z", "--", FOLDER)
    paths = set(git("ls-files", "-z").split("\0"))
    for path in tuple(paths):
        folder = os.path.dirname(path)
        while folder and folder not in paths:
            paths.add(folder)
            folder = os.path.dirname(folder)

    def exists(word):
        return word.rstrip("/") in paths

    for path in changed.split("\0"):
        if os.path.dirname(path) == FOLDER and path.endswith(".md"):
            yield os.path.basename(path), git("show", f":{path}"), exists


def check_touches(root, ids=(), staged=False):
    """Return diagnostics for selected briefs, or for open and queued briefs with no IDs."""
    if staged:
        briefs = staged_briefs(root)
    else:
        def exists(path):
            return os.path.exists(os.path.join(root, path))

        briefs = ((name, open(os.path.join(root, FOLDER, name), encoding="utf-8").read(), exists)
                  for name, _, _ in entries(root))
    problems = []
    for name, body, exists in briefs:
        match = ID.match(name)
        if not match:
            continue
        hid = match[0]
        if ids:
            if hid not in ids:
                continue
        else:
            meta = next((line for line in body.splitlines() if line.startswith("Author:")), "")
            if not re.search(r"(?:^| \| )Status: (?:open|queued)(?=\s|$)", meta):
                continue
        problems.extend(f"{hid}: Touches: {problem}: {word}" for problem, word in touches_problems(body, exists))
    return problems


def _covers(a, b):
    """Does path a include path b (equal, a folder of it, or a glob over it)?"""
    if a == b:
        return True
    folder, _, name = a.rpartition("/")
    if "*" in name:
        other_folder, _, other_name = b.rpartition("/")
        return folder == other_folder and fnmatchcase(other_name, name)
    if "." not in name:                       # a folder: worker/scenario, docs/handoff/
        return b.startswith(a.rstrip("/") + "/")
    return False


def shared_touches(a, b):
    """Describe the overlaps between two touches_named maps."""
    out = set()
    for pa, names_a in a.items():
        for pb, names_b in b.items():
            if not (_covers(pa, pb) or _covers(pb, pa)):
                continue
            path = pa if len(pa) >= len(pb) else pb
            if names_a is None or names_b is None:
                out.add(path)
            else:
                out.update(f"{path} ({name})" for name in names_a & names_b)
    return out


def overlaps_in(texts, statuses=("open", "answered")):
    """[(file, [job IDs])] for paths or names two or more open jobs both say they touch (P45). texts: {file name: entry text}.
    Queued jobs don't count: they wait for the job they'd overlap."""
    jobs = {}
    for name, text in texts.items():
        head = next((l[4:].strip() for l in text.split("\n") if l.startswith("### ")), name)
        meta = next((l for l in text.split("\n") if l.startswith("Author:")), "")
        status = next((p.split(":", 1)[1].strip() for p in meta.split(" | ") if p.strip().startswith("Status:")), "")
        if status.split(" ")[0] in statuses:
            jobs[head.split()[0]] = touches_named(text)
    out = {}
    ids = sorted(jobs)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            for shared in shared_touches(jobs[a], jobs[b]):
                out.setdefault(shared, set()).update([a, b])
    return sorted((k, sorted(v)) for k, v in out.items())


def overlaps(root):
    folder = os.path.join(root, FOLDER)
    return overlaps_in({n: open(os.path.join(folder, n), encoding="utf-8").read() for n, _, _ in entries(root)})


def main():
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    args = sys.argv[1:]
    if "-h" in args or "--help" in args:
        print(__doc__)
        return
    if args[:1] == ["list"]:
        if "--check" in args:
            text = open(os.path.join(root, HANDOFF), encoding="utf-8").read()
            if with_list(text, root) != text:
                print(f"{HANDOFF}: the open list doesn't match {FOLDER}/: run python3 tools/handoff.py list")
                sys.exit(1)
        elif write_list(root):
            print(f"rebuilt the open list in {HANDOFF}")
    elif args[:1] == ["check"]:
        staged = args[1:] == ["--staged"]
        problems = check_touches(root, () if staged else args[1:], staged=staged)
        for problem in problems:
            print(problem)
        sys.exit(bool(problems))
    elif args[:1] == ["overlaps"]:
        found = overlaps(root)
        for path, ids in found:
            print(f"{path}: {', '.join(ids)}")
        if not found:
            print("no two open jobs touch the same file")
        sys.exit(1 if found else 0)
    elif args[:1] == ["split"]:
        for name in split(root):
            print(f"moved {name[:-3].split('-')[0]} to {FOLDER}/{name}")
    elif args[:1] == ["archive"] and len(args) >= 2:
        hid, flags = args[1], args[2:]
        if hid.startswith("-") or any(f not in ("--commit", "--push") for f in flags):
            print(__doc__)
            sys.exit(2)
        push = "--push" in flags
        commit = push or "--commit" in flags
        head, sha, pushed = archive_and_commit(root, hid, commit=commit, push=push)
        print(f"archived {head}")
        if sha:
            print(f"committed {sha} Archive {head}")
        if pushed:
            print("pushed main")
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
