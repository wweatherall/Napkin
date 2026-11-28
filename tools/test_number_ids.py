#!/usr/bin/env python3
"""Checks tools/number_ids.py (T74) and tools/handoff.py (T77), run by tools/featuretest.sh. Each check builds a
small copy of the docs in a temporary folder. Prints PASS/FAIL per check and one summary line:
ID TESTS: N passed, M failed."""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handoff
import number_ids as n

RESULTS = []
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, ok):
    RESULTS.append(bool(ok))
    if not ok or VERBOSE:
        print(("PASS " if ok else "FAIL ") + name)


LOG = """# log

## Decisions

| ID | Decision |
|---|---|
| A01 | one |
| I48 | forty-eight |

## Superseded decisions

| ID | Decision |
|---|---|
| I47 | old |

## Work list

| # | Item |
|---|---|
| T7 | seven |
| T77 | seventy-seven |

## Details

### I48

text
"""

HANDOFF = f"""# Agent handoff

Rules: write placeholders like I-new-N.

## Open exchanges

{handoff.START}

(none open)

{handoff.END}

## Archived

Full entries in [handoff-archive.md](handoff-archive.md).

- H002 — Old. Resolved: done.
"""

ARCHIVE = "# Agent handoff archive\n\n### H002 — Old\n\nAuthor: Claude | Date: 2026-11-21 | Status: resolved\n"


def entry(hid, subject, status="open", extra=""):
    return f"### {hid} — {subject}\n\nAuthor: Claude | Date: 2026-11-21 | Status: {status}\n\n{extra}"


def tree(files):
    root = tempfile.mkdtemp(prefix="number-ids-")
    base = {"03_Past_Decisions/decision-log.md": LOG, "docs/agent-handoff.md": HANDOFF, "docs/handoff-archive.md": ARCHIVE,
            "docs/handoff/H036-current.md": entry("H036", "Current")}
    base.update(files)
    for rel, text in base.items():
        if text is None:
            continue
        os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
        open(os.path.join(root, rel), "w", encoding="utf-8").write(text)
    if handoff.START in base["docs/agent-handoff.md"]:
        handoff.write_list(root)
    return root


def read(root, rel):
    return open(os.path.join(root, rel), encoding="utf-8").read()


def run(root, dry=False):
    said = []
    got = n.apply(root, dry_run=dry, out=said.append)
    return got, said


# no placeholders: nothing changes
root = tree({})
before = {r: read(root, r) for r in ["03_Past_Decisions/decision-log.md", "docs/agent-handoff.md"]}
got, said = run(root)
check("no placeholders: nothing numbered, nothing changed, it says so",
      got == {} and said == ["no placeholders"] and all(read(root, r) == t for r, t in before.items()))
shutil.rmtree(root)

# two kinds at once, and a placeholder cited in several files
log = LOG.replace("| T77 | seventy-seven |", "| T77 | seventy-seven |\n| T-new-1 | build it, for I-new-1 |")
log = log.replace("| I48 | forty-eight |", "| I48 | forty-eight |\n| I-new-1 | new rule |")
root = tree({"03_Past_Decisions/decision-log.md": log,
             "docs/handoff/H036-current.md": entry("H036", "Current", extra="Logged I-new-1; work in T-new-1.\n"),
             "viewport/tool.gd": "# the rule from I-new-1\n"})
got, said = run(root)
text = read(root, "03_Past_Decisions/decision-log.md")
check("two kinds at once: I-new-1 -> I49, T-new-1 -> T78", got == {"I-new-1": "I49", "T-new-1": "T78"})
check("the log's rows get the numbers", "| I49 | new rule |" in text and "| T78 | build it, for I49 |" in text)
check("a placeholder cited in several files gets one number everywhere",
      "Logged I49; work in T78." in read(root, "docs/handoff/H036-current.md")
      and "the rule from I49" in read(root, "viewport/tool.gd"))
check("no placeholder is left", not any(n.PLACEHOLDER.search(read(root, r)) for r in n.tracked(root)))
check("the report names each placeholder, its number and its files",
      any(s.startswith("I-new-1 -> I49") and "viewport/tool.gd" in s and "03_Past_Decisions/decision-log.md" in s for s in said))
check("examples written with N are left alone", "placeholders like I-new-N" in read(root, "docs/agent-handoff.md"))
check("the log is sorted again after numbering", text.index("| I48 ") < text.index("| I49 ")
      and text.index("| T77 ") < text.index("| T78 "))
again, said2 = run(root)
check("a second run finds nothing to do", again == {} and said2 == ["no placeholders"])
shutil.rmtree(root)

# several of one kind, a lettered one, numbers taken in the archive and Superseded
log = LOG.replace("| I48 | forty-eight |", "| I48 | forty-eight |\n| I-new-2 | second |\n| I-new-1 | first |\n"
                  "| I-new-1b | first, b |")
root = tree({"03_Past_Decisions/decision-log.md": log})
got, _ = run(root)
text = read(root, "03_Past_Decisions/decision-log.md")
check("placeholders of one kind are numbered in their own order", got == {"I-new-1": "I49", "I-new-2": "I50"})
check("a lettered placeholder keeps its letter", "| I49b | first, b |" in text)
shutil.rmtree(root)

log = LOG.replace("| I47 | old |", "| I47 | old |\n| I52 | superseded later |").replace("| A01 | one |",
                                                                                         "| A01 | one |\n| A-new-1 | arch |")
root = tree({"03_Past_Decisions/decision-log.md": log, "docs/handoff-archive.md": ARCHIVE + "\n### H040 — Later\n"})
got, _ = run(root)
check("a number taken only in Superseded counts as taken", got["A-new-1"] == "A02" and "I52" in read(root, "03_Past_Decisions/decision-log.md"))
shutil.rmtree(root)

# a new handoff entry: file renamed, heading numbered, padded, open list rebuilt
root = tree({"docs/handoff-archive.md": ARCHIVE + "\n### H040 — Later\n",
             "docs/handoff/H-new-1-new-job.md": entry("H-new-1", "New job", extra="See [H036](H036-current.md).\n")})
check("the open list shows a placeholder entry before it's numbered", "handoff/H-new-1-new-job.md" in read(root, "docs/agent-handoff.md"))
got, said = run(root, dry=True)
check("dry run: reports the number and the rename, changes nothing",
      got == {"H-new-1": "H041"} and any("rename docs/handoff/H-new-1-new-job.md -> docs/handoff/H041-new-job.md" in s for s in said)
      and os.path.exists(os.path.join(root, "docs/handoff/H-new-1-new-job.md")))
got, _ = run(root)
check("next free H counts the archive's headings and pads like H036", got == {"H-new-1": "H041"})
check("the entry's file is renamed and its heading numbered",
      read(root, "docs/handoff/H041-new-job.md").startswith("### H041 — New job")
      and not os.path.exists(os.path.join(root, "docs/handoff/H-new-1-new-job.md")))
listed = read(root, "docs/agent-handoff.md")
check("the open list is rebuilt with the new name, in ID order",
      "[H041 — New job](handoff/H041-new-job.md)" in listed and listed.index("H036-current") < listed.index("H041-new-job"))
shutil.rmtree(root)

# handoff.py: the list, archiving
root = tree({"docs/handoff/H035-protocol.md": entry("H035", "Protocol", "answered").replace(
    "Status: answered", "Status: answered | For: Codex")})
listed = read(root, "docs/agent-handoff.md")
check("the open list has each entry's subject, status and who it's for",
      "- [H035 — Protocol](handoff/H035-protocol.md) — status: answered; for: Codex" in listed
      and "- [H036 — Current](handoff/H036-current.md) — status: open" in listed)
check("rebuilding the list twice changes nothing", handoff.write_list(root) is False)
body = entry("H035", "Protocol", "resolved", "Request: write it.\n\nResolution: merged abc123.\n")
open(os.path.join(root, "docs/handoff/H035-protocol.md"), "w", encoding="utf-8").write(body)
handoff.archive(root, "H035")
arch, listed = read(root, "docs/handoff-archive.md"), read(root, "docs/agent-handoff.md")
check("archive: the entry goes to the archive's bottom word for word", arch.endswith(body.strip("\n") + "\n")
      and arch.index("### H002") < arch.index("### H035"))
check("archive: its file is gone and it leaves the open list",
      not os.path.exists(os.path.join(root, "docs/handoff/H035-protocol.md")) and "H035-protocol" not in listed)
check("archive: one line under Archived, newest first, outcome from its Resolution",
      "- H035 — Protocol. Resolved: merged abc123.\n- H002 — Old." in listed)
shutil.rmtree(root)

# handoff.py split: entries written straight into the handoff move to their own files
inline = HANDOFF.replace(f"{handoff.START}\n\n(none open)\n\n{handoff.END}\n",
                         "### H030 — Tools share one press rule\n\nAuthor: Claude | Date: 2026-11-21 | Status: open\n\n"
                         "Finding: (1) one.\n\n## Jobs\n\nRules: keep.\n\n"
                         "### H033 — T74 + T77: IDs at merge\n\nAuthor: Claude | Date: 2026-11-21 | Status: open | For: Claude\n\n"
                         "Request: do it.\n\nResponse — Codex: done.\n\n")
inline += "\n## Entry template\n\n### H-new-N — Short subject\n"
root = tree({"docs/agent-handoff.md": inline, "docs/handoff/H036-current.md": None})
moved = handoff.split(root)
listed = read(root, "docs/agent-handoff.md")
check("split: each inline entry gets its own file, named from its subject",
      moved == ["H030-tools-share-one-press-rule.md", "H033-t74-t77-ids-at-merge.md"])
check("split: an entry's text moves word for word, responses included",
      read(root, "docs/handoff/H033-t74-t77-ids-at-merge.md") ==
      "### H033 — T74 + T77: IDs at merge\n\nAuthor: Claude | Date: 2026-11-21 | Status: open | For: Claude\n\n"
      "Request: do it.\n\nResponse — Codex: done.\n")
check("split: the rest stays, the template is left, the list appears under Open exchanges",
      "Rules: keep." in listed and "### H-new-N — Short subject" in listed and "### H03" not in listed
      and listed.index("## Open exchanges") < listed.index(handoff.START) < listed.index("handoff/H030-")
      < listed.index("handoff/H033-") < listed.index("## Jobs"))
check("split: a second run moves nothing", handoff.split(root) == [] and read(root, "docs/agent-handoff.md") == listed)
answered = listed.replace("## Jobs", "### H033 — T74 + T77: IDs at merge\n\nAuthor: Claude | Date: 2026-11-21 | Status: "
                          "open | For: Claude\n\nRequest: do it.\n\nResponse — Codex: done.\n\nResponse — Claude: merged.\n\n## Jobs")
open(os.path.join(root, "docs/agent-handoff.md"), "w", encoding="utf-8").write(answered)
check("split: an entry answered inline on an old branch updates its file",
      handoff.split(root) == ["H033-t74-t77-ids-at-merge.md"]
      and read(root, "docs/handoff/H033-t74-t77-ids-at-merge.md").endswith("Response — Claude: merged.\n")
      and read(root, "docs/agent-handoff.md") == listed)
open(os.path.join(root, "docs/agent-handoff.md"), "w", encoding="utf-8").write(answered.replace("Request: do it.", "Request: changed."))
try:
    handoff.split(root)
    refused = False
except SystemExit:
    refused = True
check("split: an inline copy that differs from its file is refused, the file kept", refused
      and "Request: do it." in read(root, "docs/handoff/H033-t74-t77-ids-at-merge.md"))
shutil.rmtree(root)

# H073: only placeholders that are IDs are numbered; an example in prose is left as written and reported
log = LOG.replace("| T77 | seventy-seven |", "| T77 | seventy-seven |\n| T-new-1 | build it, for I-new-1 |")
log = log.replace("| I48 | forty-eight |", "| I48 | forty-eight |\n| I-new-1 | new rule |")
board = "| H-new-1 | Claude | Ready | New job |\n"
root = tree({"03_Past_Decisions/decision-log.md": log,
             "docs/handoff-archive.md": ARCHIVE + "\nRequest: log it as P-new-1 and cite it.\n",
             "docs/handoff/H036-current.md": entry("H036", "Current", extra="Logged I-new-1.\nWrite one like Q-new-2.\n"),
             "docs/handoff/H-new-1-new-job.md": entry("H-new-1", "New job", extra="Work in T-new-1.\n"),
             "BOARD.md": board})
got, said = run(root)
check("prose examples: real rows and entries still number (I, T, H)",
      got == {"I-new-1": "I49", "T-new-1": "T78", "H-new-1": "H037"})
check("prose examples: the log rows, the entry and BOARD.md's mention of it are numbered",
      "| I49 | new rule |" in read(root, "03_Past_Decisions/decision-log.md") and "| T78 | build it, for I49 |" in read(root, "03_Past_Decisions/decision-log.md")
      and read(root, "docs/handoff/H037-new-job.md").startswith("### H037 — New job")
      and "Work in T78." in read(root, "docs/handoff/H037-new-job.md") and "| H037 | Claude |" in read(root, "BOARD.md"))
check("prose examples: an example in the archive stays as written",
      "log it as P-new-1 and cite it" in read(root, "docs/handoff-archive.md") and "P01" not in read(root, "docs/handoff-archive.md"))
check("prose examples: an example in a handoff entry stays as written, its real reference numbered",
      "Write one like Q-new-2." in read(root, "docs/handoff/H036-current.md")
      and "Logged I49." in read(root, "docs/handoff/H036-current.md"))
check("prose examples: each one is reported with its file and line",
      any(s.startswith("not numbered: docs/handoff-archive.md:") and "P-new-1" in s for s in said)
      and any(s.startswith("not numbered: docs/handoff/H036-current.md:6") and "Q-new-2" in s for s in said))
shutil.rmtree(root)

root = tree({"docs/handoff-archive.md": ARCHIVE + "\nAn example: I-new-1.\n"})
before = read(root, "docs/handoff-archive.md")
got, said = run(root)
check("only prose examples: nothing numbered, nothing changed, it says so",
      got == {} and said[-1] == "nothing numbered" and read(root, "docs/handoff-archive.md") == before)
shutil.rmtree(root)

# the real docs
real = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
text = read(real, handoff.HANDOFF)
check("docs/agent-handoff.md: the open list matches docs/handoff/",
      handoff.START in text and handoff.with_list(text, real) == text)

# P45 overlap check (handoff.touches / overlaps_in)
A = entry("H041", "Circle", extra="Touches: viewport/tools/circle_tool.gd (new), viewport/main.gd (the tool list only),\n"
          "docs/protocol.md, ARCHITECTURE.md (module rows). Not viewport/document.gd (H042).\n")
B = entry("H042", "Late replies", extra="Touches: viewport/document.gd, viewport/main.gd (`_on_open` only), a new\n"
          "worker/scenario file, docs/protocol.md. Not viewport/tools/* (H041).\n")
C = entry("H043", "Hide check", extra="Touches: viewport/tests/quick/hide.gd. Read-only on presenter.gd and main.gd: H041\n"
          "is changing them.\n")
check("touches reads the paths a job lists, and leaves out its 'Not ...' sentence",
      handoff.touches(B) == {"viewport/document.gd", "viewport/main.gd", "worker/scenario", "docs/protocol.md"})
check("touches leaves out 'Read-only on ...' files", handoff.touches(C) == {"viewport/tests/quick/hide.gd"})
check("touches leaves out a bracketed aside that says what the job stays off",
      handoff.touches("Touches: viewport/a.gd, viewport/b.gd (don't add it to tools/featuretest.sh: H049 owns it), "
                      "viewport/c.gd (not viewport/d.gd).\n") == {"viewport/a.gd", "viewport/b.gd", "viewport/c.gd"})
found = dict(handoff.overlaps_in({"a.md": A, "b.md": B, "c.md": C}))
check("two open jobs that both list main.gd and protocol.md are flagged (the H041/H042 case)",
      found.get("viewport/main.gd") == ["H041", "H042"] and found.get("docs/protocol.md") == ["H041", "H042"])
check("a test-only job beside them isn't flagged", not any("H043" in ids for ids in found.values()))
check("a queued job doesn't count", handoff.overlaps_in({"a.md": A, "b.md": B.replace("Status: open", "Status: queued (after H041)")}) == [])
check("a glob covers the files under it", dict(handoff.overlaps_in({"a.md": A, "d.md": entry("H045", "x",
      extra="Touches: viewport/tools/*.\n")})).get("viewport/tools/circle_tool.gd") == ["H041", "H045"])

def named_overlap(first, second):
    return handoff.overlaps_in({
        "a.md": entry("H041", "first", extra=f"Touches: {first}.\n"),
        "b.md": entry("H042", "second", extra=f"Touches: {second}.\n"),
    })


main = "viewport/main.gd"
redo = f"{main} (`redo`)"
asks = f"{main} (`_ask_outside`)"
invalid = f"{main} (`m._update_camera`, `ui_*`, `viewport/ui.gd`)"
nested = f'{main} (the section "x (T6)": `a`, `b`)'
glob = "viewport/*"
ids = ["H041", "H042"]
check("two jobs naming different functions in main.gd can run together", named_overlap(redo, asks) == [])
check("the same function in main.gd overlaps and is named in the report",
      named_overlap(redo, f"{main} (`redo()`)") == [(f"{main} (redo)", ids)])
check("a whole-file touch overlaps a named function in the file",
      named_overlap(main, redo) == [(main, ids)])
check("a glob overlaps a named function as a whole-file touch",
      named_overlap(f"{glob} (`redo`)", asks) == [(main, ids)])
check("member expressions, wildcards and paths in backticks do not name functions",
      handoff.touches_named(f"Touches: {invalid}")[main] is None)
check("backticked names in a nested parenthetical are read through the matching close",
      handoff.touches_named(f"Touches: {nested}") == {main: {"a", "b"}})
check("both declarations of a file count, and a whole-file touch takes precedence",
      handoff.touches_named(f"Touches: {redo}, {asks}") == {main: {"redo", "_ask_outside"}} and
      handoff.touches_named(f"Touches: {redo}, {main}") == {main: None})
check("touches keeps the legacy file paths for named, whole-file, nested, and glob entries",
      all(handoff.touches(f"Touches: {spec}.") == paths for spec, paths in [
          (redo, {main}), (asks, {main}), (main, {main}), (nested, {main}), (glob, {glob}),
          (invalid, {main, "viewport/ui.gd"}),
      ]))
check("a glob with a file extension covers files in its own directory only",
      named_overlap("viewport/tools/*.gd", "viewport/tools/move_tool.gd") ==
      [("viewport/tools/move_tool.gd", ids)] and
      named_overlap("viewport/tools/*.gd", "viewport/tools/sub/x.gd") == [])


# P23: the decision archive's rows count as taken, so a new number never repeats an archived one
root = tree({"03_Past_Decisions/decision-archive.md": "# archive\n\n## Done work\n\n| # | Item | Status |\n|---|---|---|\n| T90 | old | Done |\n",
             "03_Past_Decisions/decision-log.md": LOG.replace("| T77 | seventy-seven |", "| T77 | seventy-seven |\n| T-new-1 | next |"),
             "notes.md": "next: T-new-1\n"})
got, said = run(root)
check("an archived T90 makes the next Work list number T91", got.get("T-new-1") == "T91")
shutil.rmtree(root)

# A branch's rulings/I-new-1.md is renamed to its number and its citations renumbered
root = tree({
    "03_Past_Decisions/rulings/I48.md": "# I48 — Existing.\n\nStatus: Active | Subject: Snapping | Principles: — | Date: 2026-11-21\n",
    "03_Past_Decisions/rulings/I-new-1.md": "# I-new-1 — New rule.\n\nStatus: Active | Subject: Snapping | Principles: — | Date: 2026-11-26\n\nNew rule.\n",
    "notes.md": "follows I-new-1\n",
})
got, said = run(root)
check("a branch's rulings/I-new-1.md is renamed to its number and its citations renumbered",
      got.get("I-new-1") == "I49"
      and not os.path.exists(os.path.join(root, "03_Past_Decisions/rulings/I-new-1.md"))
      and os.path.isfile(os.path.join(root, "03_Past_Decisions/rulings/I49.md"))
      and "# I49 — New rule." in read(root, "03_Past_Decisions/rulings/I49.md")
      and "follows I49" in read(root, "notes.md"))
shutil.rmtree(root)

# Comitatus Process rulings count toward taken() so a new P-new-1 never reuses a P number in comitatus
c_org = os.path.realpath(tempfile.mkdtemp(prefix="numids-org-"))
c_proj = os.path.join(c_org, "08_Code_Bases", "Proj")
os.makedirs(os.path.join(c_org, "03_Past_Decisions", "rulings"))
os.makedirs(os.path.join(c_proj, "03_Past_Decisions", "rulings"))
open(os.path.join(c_org, "03_Past_Decisions", "rulings", "P71.md"), "w").write(
    "# P71 — Org rule.\n\nStatus: Active | Subject: Process | Principles: — | Date: 2026-11-26\n\nOrg rule.\n")
open(os.path.join(c_proj, "03_Past_Decisions", "rulings", "P04.md"), "w").write(
    "# P04 — Proj rule.\n\nStatus: Active | Subject: Product | Principles: — | Date: 2026-11-22\n\nProj rule.\n")
open(os.path.join(c_proj, "03_Past_Decisions", "rulings", "P-new-1.md"), "w").write(
    "# P-new-1 — New rule.\n\nStatus: Active | Subject: Process | Principles: — | Date: 2026-11-27\n\nNew rule.\n")
old_env = os.environ.get("NAPKIN_COMITATUS")
os.environ.pop("NAPKIN_COMITATUS", None)
try:
    got_p, _ = run(c_proj)
    check("taken() counts comitatus's P71 so P-new-1 becomes P72", got_p.get("P-new-1") == "P72")
finally:
    if old_env is not None:
        os.environ["NAPKIN_COMITATUS"] = old_env
shutil.rmtree(c_org)

# H175: history files' already-archived entries are never rewritten, while new entries being archived still number
hist_root = tree({
    "03_Past_Decisions/rulings/I-new-1.md": "# I-new-1 — New rule.\n\nStatus: Active | Subject: Architecture | Principles: — | Date: 2026-11-27\n\nRule.\n",
    "03_Past_Decisions/decision-archive.md": "# Archive\n\n## Decisions\n\n| ID | Decision |\n|---|---|\n| I40 | old rule mentioning I-new-1 |\n| I-new-2 | new archived citing I-new-1 |\n",
    "docs/handoff-archive.md": (
        "# Agent handoff archive\n\n"
        "### H152 — Old brief\n\nAuthor: Claude | Date: 2026-11-26 | Status: resolved\n\nExample: I-new-1.\n\n"
        "### H-new-1 — New entry being archived\n\nAuthor: Claude | Date: 2026-11-27 | Status: resolved\n\nFixes I-new-1.\n"
    ),
})
got_h, _ = run(hist_root)
ha_after = read(hist_root, "docs/handoff-archive.md")
da_after = read(hist_root, "03_Past_Decisions/decision-archive.md")
check("history files keep already-archived placeholders untouched while numbering new entries",
      got_h.get("I-new-1") == "I49" and got_h.get("H-new-1") == "H153" and got_h.get("I-new-2") == "I50"
      and "Example: I-new-1." in ha_after
      and "### H153 — New entry being archived" in ha_after
      and "Fixes I49." in ha_after
      and "| I40 | old rule mentioning I-new-1 |" in da_after
      and "| I50 | new archived citing I49 |" in da_after)
shutil.rmtree(hist_root)

# H220: placeholders inside any tools/test_*.py fixture are left alone when a row defines them
skip_root = tree({
    "03_Past_Decisions/decision-log.md": LOG.replace("| I48 | forty-eight |", "| I48 | forty-eight |\n| I-new-1 | real rule |"),
    "tools/test_other.py": 'FIXTURE = "| I-new-1 | fixture row |"\n',
    "tools/helper.py": '# cites I-new-1\n',
})
got_skip, _ = run(skip_root)
check("placeholders inside tools/test_*.py are left alone while other files are numbered",
      got_skip.get("I-new-1") == "I49"
      and 'FIXTURE = "| I-new-1 | fixture row |"' in read(skip_root, "tools/test_other.py")
      and "# cites I49" in read(skip_root, "tools/helper.py"))
shutil.rmtree(skip_root)

print(f"ID TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
raise SystemExit(0 if all(RESULTS) else 1)   # a failed check fails the run, not only its summary
