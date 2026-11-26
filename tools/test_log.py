#!/usr/bin/env python3
"""Checks tools/log.py (T92): add, note and show, on copies of the real decision log in a temporary git
repository (on main, and on a branch). Prints PASS/FAIL per check and one summary line:
LOG TESTS: N passed, M failed."""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import log
import number_ids
import sort_decision_log as s

REPO = os.path.dirname(HERE)
NEW = "-" + "new-"   # written in two halves so number_ids.py never numbers this file's examples
TODAY = "2031-01-02"
RESULTS = []
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, ok):
    RESULTS.append(bool(ok))
    if not ok or VERBOSE:
        print(("PASS " if ok else "FAIL ") + name)


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)


def repo(branch="main"):
    root = tempfile.mkdtemp(prefix="logtest-")
    os.makedirs(os.path.join(root, "docs"))
    os.makedirs(os.path.join(root, "03_Past_Decisions"))
    for rel in (s.LIVE, s.ARCHIVE):
        shutil.copy(os.path.join(REPO, rel), os.path.join(root, rel))
    git(root, "init", "-q", "-b", "main")
    git(root, "add", ".")
    git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "log")
    if branch != "main":
        git(root, "checkout", "-qb", branch)
    return root


def text(root, rel=s.LIVE):
    return open(os.path.join(root, rel), encoding="utf-8").read()


def fails(fn, *args, has=""):
    try:
        fn(*args)
    except log.LogError as e:
        return has in str(e)
    return False


def tidy_ok(root):
    return s.check_files(text(root), text(root, s.ARCHIVE)) == []


def next_number(root, kind):
    hi, width = number_ids.taken(root).get(kind, (0, 2))
    return f"{kind}{hi + 1:0{width}d}"


def show_checks():
    root = repo()
    out = log.show(root, "Snapping")
    check("show subject: that subject's ### group only", out.startswith("### Snapping\n") and "| I19 |" in out
          and "### Measurements" not in out and "## Principles" not in out)
    check("show subject: a unique start of the name, any case", log.show(root, "push") == log.show(root, "Push/Pull"))
    check("show subject: an ambiguous start names the candidates", fails(log.show, root, "m", has="could be"))
    check("show subject: an unknown subject lists the subjects", fails(log.show, root, "Nope", has="Snapping"))
    t = log.show(root, None, True)
    check("show --top: header, Subjects, Principles, stops before ## Decisions",
          t.startswith("# ") and "## Subjects" in t and "| G01 |" in t and "## Decisions" not in t)
    both = log.show(root, "Snapping", True)
    check("show subject --top: the top, then the group", both.startswith(t) and both.endswith(out))
    live = log.show(root, "I19")
    check("show ID in the live file: its row under its header and where it is",
          live.startswith(f"{s.LIVE}: Decisions / Snapping") and "| ID | Decision |" in live and "\n| I19 |" in live)
    check("show ID: the principles it names", "Principles it names:" in live and "\n| G06 |" in live)
    det = log.show(root, "I35")
    check("show ID with details: its ### section follows", "\n### I35\n" in det)
    arch_id = next(s.row_id(l) for l in text(root, s.ARCHIVE).split("\n")
                   if s.row_id(l) and s.where(text(root, s.ARCHIVE), s.row_id(l))[0] == "## Superseded decisions")
    arch = log.show(root, arch_id)
    check("show ID in the archive", arch.startswith(f"{s.ARCHIVE}: Superseded decisions") and f"\n| {arch_id} |" in arch)
    work = log.show(root, "T9")
    check("show a Work list ID", work.startswith(f"{s.LIVE}: Work list") and "\n| T9 |" in work)
    check("show an unknown ID fails", fails(log.show, root, "I999", has="no row I999"))
    check("show without anything fails", fails(log.show, root, None, False))
    shutil.rmtree(root)


def add_checks(on_main):
    where = "main" if on_main else "a branch"
    root = repo("main" if on_main else "claude/x")
    want = {k: (next_number(root, k) if on_main else f"{k}{NEW}1") for k in "IGQTA"}
    row = log.add(root, "I", "Boards snap to the grid.", {"subject": "snap", "principles": "G03, G05",
                                                          "why": "Because.", "where": "inference.gd"}, today=TODAY)
    check(f"add a decision on {where}: {want['I']}", row == f"| {want['I']} | Boards snap to the grid. | Active |  "
          f"| Because. | G03, G05 | inference.gd | {TODAY} |")
    check(f"add a decision on {where}: under its subject's group",
          s.where(text(root), want["I"]) == ("## Decisions", "Snapping"))
    check(f"add a decision on {where}: the Subjects index lists it",
          re.search(rf"^\| Snapping \|.*\b{re.escape(want['I'])}\b", text(root), re.M) is not None)
    if not on_main:
        two = log.add(root, "I", "A second one.", {"area": "Output", "principles": "—"}, today=TODAY)
        check("add on a branch: the next placeholder counts the ones already there", two.startswith(f"| I{NEW}2 |"))
    log.add(root, "A", "An architecture rule.", {"subject": "Architecture", "principles": "G12",
                                                "rel": "Refines A02"}, today=TODAY)
    check(f"add another decision kind on {where}", s.where(text(root), want["A"]) == ("## Decisions", "Architecture")
          and "Refines A02" in log.show(root, want["A"]))
    g = log.add(root, "G", "Tools say what they will do.", {}, today=TODAY)
    check(f"add a principle on {where}", s.where(text(root), want["G"]) == ("## Principles", None)
          and g.startswith(f"| {want['G']} | Tools say what they will do. | Active |"))
    q = log.add(root, "Q", "Should arrays wrap?", {"why": "Asked in H0."}, today=TODAY)
    check(f"add a question on {where}", s.where(text(root), want["Q"]) == ("## Open questions", None)
          and q == f"| {want['Q']} | Should arrays wrap? | Open | Asked in H0. |")
    t = log.add(root, "T", "Build the thing.", {"rel": "Q4", "result": "Start here."}, today=TODAY)
    check(f"add a Work list item on {where}", s.where(text(root), want["T"]) == ("## Work list", None)
          and t == f"| {want['T']} | Build the thing. | Open | Q4 | Start here. |")
    check(f"after adding on {where} the log passes sort_decision_log.py --check", tidy_ok(root))
    if on_main:
        lines = text(root).split("\n")
        ids = [s.row_id(l) for l in lines if s.row_id(l) and s.row_id(l).startswith("T")]
        check("add on main: the new row sorts into ID order", ids == sorted(ids, key=lambda x: s.key(f"| {x} |")))
    shutil.rmtree(root)


def error_checks():
    root = repo()
    before = text(root)
    bad = [
        ("a decision without --subject", ("I", "x", {"principles": "G01"}), "--subject"),
        ("a decision without --principles", ("I", "x", {"subject": "Output"}), "--principles"),
        ("a principle that doesn't exist", ("I", "x", {"subject": "Output", "principles": "G99"}), "G99"),
        ("a status the table doesn't allow", ("T", "x", {"status": "Active"}), "isn't one of"),
        ("a '|' in the text", ("T", "a | b", {}), "'|'"),
        ("kind H (handoff entries aren't log rows)", ("H", "x", {}), "kind"),
        ("an option the kind doesn't take", ("T", "x", {"where": "here"}), "--where"),
    ]
    for name, args, has in bad:
        check(f"add refuses {name}", fails(log.add, root, *args, has=has))
    check("a refused add leaves the log as it was", text(root) == before)
    check("an unknown option is refused", fails(log.parse, ["--colour", "red"], has="unknown option"))
    shutil.rmtree(root)


def note_checks():
    root = repo()
    row = log.note(root, "T9", "Note one.")
    check("note: appended to a Work list row's last column", row.startswith("| T9 |") and row.endswith(" Note one. |")
          and s.cells(row)[-1] == "Note one.")
    row = log.note(root, "T9", "Note two.")
    check("note: a second note follows the first", s.cells(row)[-1] == "Note one. Note two.")
    check("note: written to the file", row in text(root).split("\n"))
    full = next(s.row_id(l) for l in text(root).split("\n")
                if s.row_id(l) and s.where(text(root), s.row_id(l))[0] == "## Work list" and s.cells(l)[-1])
    old = s.cells(next(l for l in text(root).split("\n") if s.row_id(l) == full))[-1]
    check("note: kept after the existing result", s.cells(log.note(root, full, "More."))[-1] == old + " More.")
    check("note: a decision isn't a Work list row", fails(log.note, root, "I19", "x", has="under Decisions"))
    check("note: an unknown ID", fails(log.note, root, "T999", "x", has="isn't in the Work list"))
    check("after notes the log passes sort_decision_log.py --check", tidy_ok(root))
    shutil.rmtree(root)


def tunable_checks():
    root = repo()
    row = log.add(root, "tunable", "PROBE_S", {"value": "0.5 s", "does": "How often it looks.",
                                               "where": "tools/x.py", "decision": "P24, P27"})
    lines = text(root).split("\n")
    tun = [t for t in s.tables(lines) if t[3] == "## Tunables"][0]
    check("tunable: the row has the Tunables columns, in order",
          row == "| PROBE_S | 0.5 s | How often it looks. | tools/x.py | P24, P27 |")
    check("tunable: it goes at the end of the Tunables table", lines[tun[2][-1]] == row)
    check("tunable: the log still checks out", tidy_ok(root))
    check("tunable: a name already in the table is refused",
          fails(log.add, root, "tunable", "PROBE_S", {"value": "1", "does": "x", "where": "y", "decision": "P24"},
                has="already"))
    check("tunable: a missing column is refused",
          fails(log.add, root, "tunable", "OTHER", {"value": "1", "does": "x", "where": "y"}, has="--decision"))
    check("tunable: a decision's option is refused",
          fails(log.add, root, "tunable", "OTHER", {"value": "1", "does": "x", "where": "y", "decision": "P24",
                                                     "why": "z"}, has="--why"))
    r = subprocess.run([sys.executable, os.path.join(HERE, "log.py"), "add", "tunable", "CLI_S", "--value", "2",
                        "--does", "From the command line.", "--where", "tools/y.py", "--decision", "P24"],
                       cwd=root, capture_output=True, text=True)
    check("tunable: from the command line", r.returncode == 0 and r.stdout.strip() ==
          "| CLI_S | 2 | From the command line. | tools/y.py | P24 |")
    shutil.rmtree(root)


def placeholder_checks():
    root = repo("claude/ph")
    next_process_id = log.next_id(root, "P", False)
    open(os.path.join(root, "CLAUDE.md"), "w").write(f"Rule {next_process_id} says so (written before its row exists).\n")
    live = text(root).replace("\n## Work list", f"\nSee T{NEW}4 in prose.\n\n## Work list", 1)
    open(os.path.join(root, s.LIVE), "w").write(live)
    git(root, "add", "."); git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "mentions")
    row = log.add(root, "P", "A process rule.", {"subject": "Process", "principles": "—"}, today=TODAY)
    check("placeholder: one only mentioned in another file doesn't count",
          row.startswith(f"| {next_process_id} |"))
    row = log.add(root, "T", "An item.", {"covers": "T9"})
    check("placeholder: one only mentioned in the log's prose doesn't count either", row.startswith(f"| T{NEW}1 |"))
    row = log.add(root, "T", "Another.", {"covers": "T9"})
    check("placeholder: a row that defines one does count", row.startswith(f"| T{NEW}2 |"))
    live = text(root).replace("\n## Details\n", f"\n## Details\n\n### T{NEW}7\n\nLong text.\n", 1)
    open(os.path.join(root, s.LIVE), "w").write(live)
    check("placeholder: so does a ### Details heading", log.next_id(root, "T", False) == f"T{NEW}8")
    shutil.rmtree(root)


def cli_checks():
    root = repo("claude/cli")
    run = lambda *a: subprocess.run([sys.executable, os.path.join(HERE, "log.py"), *a], cwd=root,
                                    capture_output=True, text=True)
    r = run("add", "T", "From the command line.", "--covers", "T9")
    check("command line: add prints the row it wrote", r.returncode == 0 and r.stdout.startswith(f"| T{NEW}1 |"))
    r = run("show", "Nope")
    check("command line: an unknown subject exits 1 with a message", r.returncode == 1 and "no subject" in r.stderr)
    r = run("show", "T9", "--top")
    check("command line: show ID --top", r.returncode == 0 and "## Subjects" in r.stdout and "\n| T9 |" in r.stdout)
    shutil.rmtree(root)


def main():
    show_checks()
    add_checks(True)
    add_checks(False)
    error_checks()
    note_checks()
    tunable_checks()
    placeholder_checks()
    cli_checks()
    passed = sum(RESULTS)
    print(f"LOG TESTS: {passed} passed, {len(RESULTS) - passed} failed")
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
