### H070 — Trim CLAUDE.md and AGENTS.md to what a session needs

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: Claude

References: P23 (the log's live/archive split, same idea), P37-P40, G11. William chose this job, 2026-11-22: every
session reads these at the start, so their length is paid on every job (usage).

Touches: CLAUDE.md, AGENTS.md, BOARD.md (its instructions part only, not the job table). Not the folder guides,
ARCHITECTURE.md or docs/protocol.md.

Request: shorten CLAUDE.md (145 lines) and AGENTS.md (63) by moving what only the integrator needs (merging,
numbering, the map, the lock) into one integrator page (a new docs/integrator.md; H050 points to it) and cutting
repetition (rules said in CLAUDE.md, AGENTS.md and BOARD.md alike: say each once, point to it). Keep every rule
(nothing is dropped, only moved or said once); keep William's "Working with William" section in his words. Say in
your response the line counts before and after and where each moved section went. Check: tools/test_startup.py and
anything that greps these files still pass; quick test. A worker's start (CLAUDE.md, then BOARD.md) must still
be enough to take and finish a job.

#### Response — Claude (worker), 2026-11-22

Branch `claude/h070-trim-instructions`. Nothing dropped: every rule is moved or said once, with a pointer.

Line counts, before → after: CLAUDE.md 145 → 130, AGENTS.md 63 → 35, BOARD.md 69 → 59, new docs/integrator.md 52.
A Claude worker's start (CLAUDE.md + BOARD.md) is 214 → 189 lines; a Codex start (+ AGENTS.md) 277 → 224; the
integrator reads docs/integrator.md as well.

Where each part went:
- CLAUDE.md "Working with Codex": everything only the integrator does (the lock, integrate.py and the gate, the
  PROTOCOL_VERSION renumber and the Touches flags at merge, `--no-commit` + number_ids.py, `job.py watch`, carrying
  over only Codex's own log rows, writing the map at merge and `--continue`, "on main the map changes in the same
  commit", the `--range` PR check) → docs/integrator.md. The worker's take/run/done/one-job steps (P24, P37, the
  20-minute `--wait`) → said once, in BOARD.md. What stays is shared: startup.py, the handoff files, Touches,
  placeholder IDs, the Architecture: lines and A35's bump, the commit trailers, scratch/ (P25), Follow-up / For the
  integrator lines (P26), saving context. Historical asides (T74-T77 "take the rest of the clash out", "replaced
  William's rule of 2026-11-21") cut. Heading now "Working with Codex (ChatGPT) and other sessions".
- "Working with William": unchanged, in his words.
- BOARD.md "If you're the integrator" → docs/integrator.md (the section is now a two-line pointer). The worker
  section gains "you don't merge or push", the Follow-up / For the integrator lines, and P37's reason and the
  `job.py` 2nd-job refusal (from CLAUDE.md). The two Notes repeating step 1's `take --as claude/codex` removed.
- AGENTS.md: the queue steps, dead man's switch, P40, Result/done, P37, scratch/, placeholder numbering, commit
  trailers and the P28 rules now point to BOARD.md and CLAUDE.md; Codex-only rules kept (its worktree only, never
  the main checkout; merge or push only when William asks; merge main daily; every William choice its own row,
  merge main before editing the log; list placeholders; dated, signed response; `codex/small-fixes`; tell William).
- docs/integrator.md also takes P39's watch (`job.py watch --next`, no timed check-ins), P22's small-fixes merge,
  and the memory rule "compare Touches of every Ready/claimed job before marking one Ready".

H050 is archived, so nothing points to docs/integrator.md from there; startup.py's integrator reminder still
names H050 (tools/ is outside Touches).

Tests: quick test, every suite passes except two load-timing ones H069 is fixing, with the load average at ~315
from other jobs: worker/test_outside_save.py 1 failed once (25 of 25 alone) and tools/test_startup.py's 10-second
startup.py timeout ("startup did not finish"; 41 of 41 alone). Nothing greps these files' wording: handoff.py's
TOP set, test_check_architecture.py and test_log.py use the names only; job.py/startup.py read only BOARD.md's
Order line, job table and Notes, all unchanged in form.

Follow-up: startup.py's integrator reminder ("after a clear, re-arm the queue watch ... (H050)") could point to docs/integrator.md instead of the archived H050.
For the integrator: add docs/integrator.md to ARCHITECTURE.md's Documentation ownership table (the integrator's work: lock, queue watch, review, merge, the map).

Result: see branch claude/h070-trim-instructions; quick test passes but for the two H069 load flakes; CLAUDE.md 145→130, AGENTS.md 63→35, BOARD.md 69→59 lines, integrator-only rules moved to new docs/integrator.md
