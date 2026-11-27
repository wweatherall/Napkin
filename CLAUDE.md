# Shop Sketch

A SketchUp-feel modeller over FreeCAD for woodworking: tool-first (no workbenches), fast to draw,
while the model stays a real, editable FreeCAD file with FreeCAD's drawings. Blender is for renders only.
Owner: William (teacher; shop and construction background). He thinks in systems and likes values he can tune.

## Before changing behaviour, read the decision log
Each ruling (`G` principle or `A`, `D`, `I`, `M`, `P`, `U`, `W`... decision), Work list item (`T`), and question (`Q`)
lives in its own file under `03_Past_Decisions/` (`rulings/<ID>.md`, `work/<ID>.md`, `questions/<ID>.md`).
`03_Past_Decisions/decision-log.md` (P09, P23, P65) holds the generated indexes (`Subjects`, `Principles`, `Decisions`,
`Open questions`, `Work list`) and the `Tunables` table; `03_Past_Decisions/decision-archive.md` indexes superseded
rulings, decided questions, and done Work list items. Don't read them whole: use `python3 tools/log.py show --top` for
the subjects and principles, `python3 tools/log.py show <subject>` for a subject's rulings, and
`python3 tools/log.py show <ID>` (or read the entry file) for one entry and its principles. Add entries with `log.py add`,
append notes with `log.py note`, and update status with `log.py set`, never by hand. Rule P01: a change that
contradicts a logged decision gets a new ruling naming the old ID, and the old ruling is marked `Superseded` (never
deleted). Ask William before countermanding an Active decision.

## Working with William
- He wants a partner through the Work list one item at a time: say which item you're on, and finish it before the
  next. The files carry the state, not the chat.
- Behaviour choices are his: ask, one question at a time, with a recommendation, and log the answer (P01).
- Tests are the project's memory: every behaviour gets a named check.
- Small fixes (P22): nothing he'd notice changes (or the code is made to do what a logged decision says), no
  protocol, file format, module boundary or saving is touched, ~30 lines or less. Commit on the `small-fixes`
  branch after the quick test (`Architecture-Impact: none - <reason>`), no Work list row or handoff; the
  integrator merges and pushes it when the gate passes. List the fixes for him at the end of the session. Bigger
  becomes a Work list item.
- FreeCAD 1.1.4 is installed: don't work around bugs it no longer has. The AppKit rebuild (T25) waits for a
  working prototype.

## Working with Codex (ChatGPT) and other sessions
- Start every session with `python3 tools/startup.py` (pass `--role integrator` if William named you integrator, or
  `--role worker` for a lean worker brief). Nothing notifies either agent of the other's changes: when
  you leave Codex something, tell William.
- The integrator is the one Claude session William named, holding the lock (P16, P19); only it merges and pushes,
  and its work is in `docs/integrator.md`. Every other session is a worker: "check the board" means follow
  `BOARD.md`. Codex reads `AGENTS.md` and Gemini `GEMINI.md` (AGENTS.md plus its differences); keep them in step.
- Commit with `git -c core.hooksPath=.githooks commit`. Watched code (`tools/check_architecture.py` `watched`):
  the .py, .gd, .godot and .tscn files under worker/ and viewport/, except tests (`test_*`, `tests.gd`,
  `test_load.py`), plus `tools/build_app.sh`. A commit changing watched code says `Architecture-Impact:
  in the handoff - H0NN` (that entry's `Architecture:` lines committed) or `Architecture-Impact: none - <specific
  reason>`, which the reviewer checks.
- Scratch files and logs go in `scratch/` inside your worktree, never /private/tmp (P25).
- Handoff entries: `docs/agent-handoff.md`. Don't read big shared documents whole: read a ruling with
  `python3 tools/log.py show I34` (or `03_Past_Decisions/rulings/I34.md`); read `Codex's suggestions.md`,
  `FREECAD_FEATURE_MAP.md` and `ARCHITECTURE.md` by section.

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
