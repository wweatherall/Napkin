# Shop Sketch

A SketchUp-feel modeller over FreeCAD for woodworking: tool-first (no workbenches), fast to draw,
while the model stays a real, editable FreeCAD file with FreeCAD's drawings. Blender is for renders only.
Owner: William (teacher; shop and construction background). He thinks in systems and likes values he can tune.

## Before changing behaviour, read the decision log
`docs/decision-log.md` (P09, P23) is what's live: a Subjects index, Principles, Decisions grouped by subject, Open
questions, Work list, Tunables, Details; `docs/decision-archive.md` is its history (superseded, decided, done), same
IDs. Don't read it whole: start with the top, down to `## Decisions` (~7 KB: the subjects and the principles), then
`python3 tools/log.py show <subject>` for your subject's group and `log.py show <ID>` for one row (its Details and
principles come with it); add rows with `log.py add`, never by hand. Grep both files by ID (a row ending "(Details below.)" has its full text at `### <ID>` in the same file); edit the
live file in the same commit as the change. Keep rows short (the file's header says how). Rule P01: a change that contradicts a logged decision gets a new row naming the old ID, and the old row is
marked Superseded (never deleted). Ask William before countermanding an Active decision.

## Working with William
- He wants a partner working through the Work list one item at a time, so nothing gets missed. Say which item
  you're on; when it's done, end your handoff response with one line, `Result: <commit>; <tests>; <what changed>`;
  integrate.py copies it into the Work list at merge (P17: workers don't edit the Work list; T91).
- Each item on its own branch; commit when its tests pass. The integrator merges into main when it judges a branch
  good enough (review done, full test passes) and pushes main after merging (P16); other sessions never merge or push.
- Quick test after every change; full test when it fails or before a merge. Add a quick-test step per feature.
- New behaviour choices are his: ask (one question at a time, with a recommendation) and log the answer (P01).
- One Work list item at a time: finish it (tests, commit, the result in your handoff, a handoff note if Codex is
  affected) before the next; a worker session takes one job (P-new-1), then a fresh session. The files carry the
  state, not the chat.
- Tests are the project's memory: every behaviour gets a named check, so nobody has to remember how it works.
- Small fixes take the light path (P22, was P08): nothing William would notice changes (or the code is made to do what a
  logged decision says), no protocol, file format, module boundary or saving is touched, and it's ~30 lines or less.
  Commit it on the standing `small-fixes` branch after the quick test (code: `Architecture-Impact: none - <reason>`);
  no Work list row or handoff. The integrator merges and pushes it when the gate passes, without
  asking (P22); list the fixes for William at the end of the session. If a fix grows past that, make it a Work list item.
- FreeCAD 1.1.4 is installed; don't work around bugs that 1.1.4 no longer has. The AppKit rebuild (T25) waits
  for a working prototype.

## Working with Codex (ChatGPT)
- One Claude session is the integrator (P16), and it holds the lock (`python3 tools/integrator.py status`, P19):
  only a session William has named takes it. It assigns jobs on the board, reviews, and merges with
  `python3 tools/integrate.py <branch> --as <name>` (P20), which runs the gate, `tools/gate.sh` (P18).
  A branch that changes a message bumps PROTOCOL_VERSION by one on both sides (A35); if main moved on meanwhile,
  integrate.py renumbers it on top. It also flags files a branch changed outside its job's Touches list.
  Any other session (Claude or Codex) takes the job it's given, works in its own worktree and delivers to the
  integrator; it doesn't merge into main. "Check the board" means: follow `BOARD.md` (P14).
- Codex reads `AGENTS.md` (its instruction file) at the start of each session; keep it in step with this section.
- Nothing notifies either agent of the other's changes. At the start of a session, run `python3 tools/startup.py`
  first, read the handoff and check `git branch -a` for `codex/*` branches with new commits; when you leave Codex
  something, tell William.
- `docs/agent-handoff.md` is the shared scratchpad: its rules and an open list; each open entry is its own file in
  `docs/handoff/` (T77). Read the ones you're picking up. `python3 tools/handoff.py archive H0NN` moves a resolved
  entry whole to `docs/handoff-archive.md` with a one-line index left behind; read the archive only for history.
- New IDs (decisions, Work list items, questions, handoff entries) are placeholders on a branch: I-new-N, T-new-N,
  H-new-N (a new entry is `docs/handoff/H-new-N-slug.md`). The integrator merges with `--no-commit`, runs
  `python3 tools/number_ids.py` (`--dry-run` to look first), then commits; it gives each the next free number (T74).
- Save context: don't read the big shared documents whole. Grep the decision log by ID (`grep "^| I34 " docs/decision-*.md`),
  and read `Codex's suggestions.md`, `FREECAD_FEATURE_MAP.md` and `ARCHITECTURE.md` by section (grep the heading,
  then read that range).
- Jobs run through the queue (P24): a worker runs `python3 tools/job.py take`, works in the worktree it gets, and
  finishes with `python3 tools/job.py done`; the integrator runs `python3 tools/job.py watch` under its watcher and
  reviews each done job; integrate.py also removes a merged job's worktree and branch. Leftovers go in a response
  as `Follow-up:` lines and merge instructions as `For the integrator:` lines; integrate.py copies the first into
  docs/follow-ups.md and prints the second (P26).
- A worker session does one job (P-new-1, replaced P27's 3: context grown over several jobs used up William's usage):
  take, work, done, then stop and tell William you're ready for a /clear (job.py refuses a 2nd; a /clear gives a new
  CLAUDE_CODE_SESSION_ID). With nothing Ready, `job.py take --wait` with `run_in_background` waits up to 20 min.
- A job's scratch files, logs and measurements go in `scratch/` inside its worktree (git ignores it), never in
  /private/tmp or elsewhere: removing the worktree at merge takes them too (P25).
- Codex works on `codex/*` branches in its own worktree, on the files its handoff job lists; review and merge them.
- Work in parallel by files, not topics: every job (Claude's or Codex's) lists in its handoff entry the files it
  expects to touch ("Touches: ..."). Two jobs whose lists overlap don't run at once; tell William before starting
  one. The shared hot spots (the decision log's Work list, the handoff, viewport/main.gd; ARCHITECTURE.md and docs/protocol.md are the integrator's, P28)
  stay small edits made once the work is done; T74–T77 take the rest of the clash out.
- Codex records William's decisions in the log itself (P09, AGENTS.md). When integrating its branch, carry over
  only the rows it added or superseded: its copy of the rest may be older than main's.
- `ARCHITECTURE.md` and `docs/protocol.md` are the integrator's (P28, which replaced William's rule of 2026-11-21):
  a worker doesn't edit them. A job that changes a module, a message or file format, state ownership, or
  saving/recovery writes what it does to them as `Architecture: <what>` lines in its handoff entry; at merge
  integrate.py stops with the merge staged and prints them, the integrator writes them in (the reviewer checks
  prose against code), and `integrate.py --continue` commits and finishes.
- Use `git -c core.hooksPath=.githooks commit ...` to run the tracked architecture check. On a branch, a commit
  changing watched code names its entry, `Architecture-Impact: in the handoff - H0NN` (the entry's Architecture:
  lines in the same commit or earlier); a genuinely non-architectural change uses `Architecture-Impact: none -
  <specific reason>`, which the reviewer verifies. On main the map changes in the same commit. The PR check
  (`--range`, read as a branch) is an additional omission detector, not a replacement for review.

## How it works
Each part has its own guide, loaded when you work in that folder: `worker/CLAUDE.md` (the FreeCAD side: modules,
how a model is built, sync and saving, FreeCAD's traps, worker tests), `viewport/CLAUDE.md` (Godot: drafts,
confirmed meshes, the worker link, typed values, drawing rules, viewport tests) and `viewport/tools/CLAUDE.md`
(the tool interface and how a tool makes an action). ARCHITECTURE.md is the full map and protocol.
- `viewport/` (Godot 4.6) draws every action at once as a draft and sends the op list to the worker; FreeCAD
  catches up and the real mesh replaces the draft, with the confirmation wave (W01–W09).
- `worker/` (inside `freecadcmd`, started by `replay.py`) keeps a live FreeCAD document per model and turns each
  action into native features in one undo transaction (A22, A23). The .FCStd file is the model (A21); the journal
  `<model>.shopsketch.json` sits beside it (A24). One worker serves every window (W13), one window per model.
- `sync(ops)`: keep the common prefix, take back the rest with FreeCAD undo, apply new ops (A23).
- Units: model space is Z-up millimetres; Godot is Y-up metres (`m2g` / `g2m`). Faces are referenced by geometry
  `{body, normal, point}`, never by face numbers (A03).

## Run (macOS)
- `tools/build_app.sh` builds `dist/Shop Sketch.app` (A30): a copy of the Godot program runs
  `Resources/Shop Sketch.pck` (`--export-pack`, preset in `viewport/export_presets.cfg`; no export templates needed),
  with `Resources/worker/*.py`, an icon from `tools/icon.svg`, ad-hoc signed. Files next to the viewport are found
  with `_beside_project()` (repo when run from source, bundle Resources in the app).
- The app opens the last model (`user://settings.cfg`), else `~/Documents/Shop Sketch/Untitled.FCStd`; File > New /
  Open call `switch_model()`. Each model's outputs go in `user://out/<name>-<hash>/` (tests keep `--out` as is).
- Renderer: Compatibility (on a Mac it draws through Metal). Forward+ works (`--rendering-method forward_plus`,
  background matched) but hatches edges on thin faces; see Q5.
- `./Start Shop Sketch.command` opens `models/model.FCStd`; the app starts its worker. Worker log: `worker.log`.
- FreeCAD's command-line program: `/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd`
- Godot: `/Applications/Godot.app/Contents/MacOS/Godot`

## Tests
- Two kinds of test (P07): feature tests check Shop Sketch's answers against FreeCAD with no window
  (`tools/featuretest.sh`, ~10 s, all side by side; it finds every `worker/test_*.py`, `tools/test_*.py` and
  `viewport/test_*.gd` itself, T95, `--list` shows them; the folder guides say how); UI tests drive the viewport.
  A new feature gets a numbered file in `worker/scenario/` first (run the feature tests while building it), then a
  quick-test step once its tool exists.
- After every change: `tools/quicktest.sh` (~8 s): the feature tests beside every viewport feature once, in three
  Godot windows side by side (`--quicktest --quick-lane=N`, T49; `--one` for a single window), each step checking its
  own answer. Each window starts its own worker on a port it owns, so test runs never touch a running Shop Sketch
  or each other.
- Before a merge: `tools/gate.sh` (the quick test, then the full test, one verdict; failures listed in
  `tests/known_failures.txt` with their Work list item pass, nothing else, P18).
- When the quick test fails: `tools/fulltest.sh` (~15 s): the six recorded suites compared
  with `tests/reference/` (`tools/compare_suites.py`), the targeted suites, and the feature tests; the suites run in
  four lanes side by side, each with its own worker (T49). Suites run at the
  quick test's pace (`--fast`, same results); `--full-pace` as recorded. After an intended change in behaviour:
  `tools/fulltest.sh --update-reference`.
- Both scripts first run `tools/parsecheck.sh` (every viewport script, side by side, ~1 s); the quick test's Godot run stops
  after 120 s. Which tests exist and what they cover: the folder guides.
- Recordings use `--true-latency` (P03) with Godot's `--write-movie`.

## Known problems / open work
- Q18: FreeCAD booleans slow down along a chain (24 chained cuts: 5 → 358 ms). Done: hole arrays, one boolean
  per run (A22b): hole 48 on a panel is 290 ms (was 4.3 s). In reserve (T9): answer from plain shapes first.
- The work list is the decision log's "Work list" section (T1, T2, ...).
- Q19: stage 2, watch the file and merge FreeCAD-side changes. Q17 / stage 3: adopt solids from files Shop Sketch didn't make.
- Q4: feel test on real hardware. Earlier tuning was judged from software-rendered recordings.

## Conventions
- Where the viewport predicts what FreeCAD will compute (lengths, circles, split-face regions), a test compares the
  two answers, like `tests/length_cases.json` (P21).
- Keep the user-facing feel first: drafts appear instantly. Never block input on FreeCAD.
- Rules for one part live in its guide: drawing and test-mode rules in `viewport/CLAUDE.md`, FreeCAD's traps in
  `worker/CLAUDE.md`, the tool interface in `viewport/tools/CLAUDE.md`. Change them there.
