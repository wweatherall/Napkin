### H167 — Architecture step 2: ARCHITECTURE.md down to a hand-written core under 8 KB, nothing lost

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: open | For: gemini

Item: T138

References: T138 (this item; step 1 was H165's generated module map), P50 (each code file's header line is its map
line), P28 (ARCHITECTURE.md is the integrator's: this job edits it under this brief, and the integrator reviews it),
P36 (an architect plans from the map without reading code), comitatus principles C06 (one spot per idea) and C07
(token efficiency).

Touches: ARCHITECTURE.md, docs/protocol.md (a new last section only), viewport/ and
worker/ (header comments only, for each a moved fact is about), tools/architecture_map.py (`MAX_SENTENCE_LEN` and
the new size check), tools/test_architecture_map.py.

Reading path:
1. ARCHITECTURE.md's headings (`grep -n "^##" ARCHITECTURE.md`) and the sizes below; then `## Documentation
   ownership` and `## System overview` whole.
2. `## Module map (generated)` (what the generated part already says per file) and `tools/architecture_map.py`'s
   docstring (how a header line becomes a map line).
3. `## Where responsibilities live` (31.5 KB, one row per file): for each row, what it says that the file's map line
   doesn't.

Today (checked 2026-11-27 on main): ARCHITECTURE.md is 91 KB. By section: Where responsibilities live 31.5 KB,
Lifecycle of an edit 12.8, Module map (generated) 9.9, Files, persistence and recovery 8.9, Native model and identity
7.4, Protocol at a glance 6.4, the rest under 2.5 each. The module map lists every file in one line, from the file's
own header. Much of the responsibilities table repeats it at length; the rest are warnings ("X lives here, never in
Y"), entry points and history (T/H numbers).

Request (William, 2026-11-26: compress heavily so the start-up brief can carry the map; 2026-11-27: the proposed
order "looks sound"):
1. **A core under 8 KB, hand-written.** Everything outside the generated module map totals under 8 KB (measure with
   `wc -c` on the file minus the map section; quote both numbers). Keep, short: what the system is (processes and
   the link), who owns which state, the order of steps of an edit, saving and recovery, the constraints worth
   preserving, where to implement a change. One idea in one place: a section that repeats another, or the map,
   goes.
2. **Nothing lost: each removed fact goes to its one right place**, by this rule:
   - about one file (what it does, a warning about it, its entry points): that file's header comment, so it shows
     in the map line or right under it when the file is opened. The map line stays one sentence (raise
     `MAX_SENTENCE_LEN` only if a file truly needs it; say so); further header lines may follow it.
   - about a message or the wire format: a new last section of docs/protocol.md, `## Moved from ARCHITECTURE.md
     (H167)`, word for word; don't edit the rest of that file (William and the integrator are going through it and
     will fold this section in).
   - about a file under tools/ (not in Touches: H168 holds tools/handoff.py): the core if it's about how files work
     together, otherwise a `Follow-up:` line naming the file and the sentence.
   - history only (which job or to-do made it so): dropped; git and the rulings keep it.
   - about how two or more files work together: the core.
   In your response, a table: each removed section or table row, and where its content went (file / section / dropped
   as history).
3. **The map stays generated and checked.** `python3 tools/architecture_map.py --check` passes. Add a check in it that
   the hand-written part stays under 8 KB (a line saying how much over, exit 1), so it can't grow back unnoticed.

Not in this job: the start-up brief carrying the map (next, in startup.py), the current/proposed map with ghosting
(T136), any code change beyond header comments, protocol.md's own structure.

What can fail:
- A warning lost in the cut: every "never", "only", "must" and "don't" sentence in today's ARCHITECTURE.md is found
  again somewhere (the core, a header, protocol.md). Check: list them before you start
  (`grep -n -i "never\|only\|must\|don't" ARCHITECTURE.md > scratch/warnings.txt`) and say for each where it went.
- A header edit that changes code: only comment lines change. Check: `git diff main --stat` lists the files;
  `git diff main -- viewport worker tools | grep "^[-+]" | grep -v "^[-+]\s*#\|^[-+]\s*##\|^[-+]\s*\"\"\"\|^[-+][-+]"`
  shows nothing but docstring text (quote it).
- Links into ARCHITECTURE.md from other files (`grep -rn "ARCHITECTURE.md#" --include=*.md .`): each still resolves,
  or points to where the text went.

Checks:
- `python3 tools/architecture_map.py --check` (with the new size check) and tools/test_architecture_map.py.
- `tools/TEST_BEFORE_MERGING.sh` passes (header comments touch app files, so expect the full scope).
