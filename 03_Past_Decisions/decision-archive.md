# Shop Sketch decision archive

The history half of the decision log (P23): an index of superseded rulings (whose files stay in
`03_Past_Decisions/rulings/<ID>.md`, P01: never deleted), decided questions, done Work list items, and the Details
of those Q/T rows. Same IDs as [decision-log.md](decision-log.md); `tools/sort_decision_log.py` keeps the index
in sync and moves Decided/Done Q/T rows here. Read a ruling with `python3 tools/log.py show I34` (or open
`03_Past_Decisions/rulings/I34.md`).

## Superseded decisions

Kept for history (P01: never deleted). Each names the decision that replaced it.

| ID | Decision | Status |
|---|---|---|
| A01 | The op log (oplog/0.1 JSON) is the source of truth. | Superseded |
| A04 | Each board is its own Part solid (not a PartDesign Body). | Superseded |
| A06a | Prototype the front end as a Blender add-on. | Superseded |
| A11 | Editing a mirrored copy edits its original (mirrored back), so both stay identical, lik... | Superseded |
| A22 | A board is an App::Part container holding its feature chain: Part::Plane (the rectangle... | Superseded |
| A22b | A board is an App::Part container: Part::Plane (the rectangle) → Part::Extrusion (the p... | Superseded |
| A32 | Saving the model and its journal as one generation: the previous complete pair is kept ... | Superseded |
| A33 | Split geometry presentation (drafts, confirmed boards, highlights, waves, caches) and s... | Superseded |
| A37 | Opening a model whose file and journal don't match: the newest file on disk is the mode... | Superseded |
| A38 | When Shop Sketch takes in a FreeCAD edit (opening a file changed outside it, or reloadi... | Superseded |
| I03 | Snapping: corners within 14 px, otherwise a 10 mm grid (G toggles). | Superseded |
| I04 | A rectangle on the ground makes a new board. | Superseded |
| I07 | Cut previews are violet. | Superseded |
| I07a | Cut previews shown in red. | Superseded |
| I12 | Mirror tool (M), after FreeCAD's Part Mirror: click a board; the plane starts parallel ... | Superseded |
| I12b | Mirror is Shift+M (M is Move). | Superseded |
| I13 | A typed mirror distance means: how far the plane sits past the board's outer face on th... | Superseded |
| I26 | Extrude-to-face relationships persist: a push made up to a target face follows that fac... | Superseded |
| I26b | A push or cut made up to a face stays tied to that face until you push that same face a... | Superseded |
| I27 | Through-cuts follow relevant face changes: a feature extruded up to, or cut through, a ... | Superseded |
| I29 | A rectangle started with a click ends with the next click; started with a press-and-dra... | Superseded |
| I39 | An edge midpoint can link a push to an adjacent face. | Superseded |
| I47 | Copying a whole assembly (from outside it) makes a new assembly holding linked copies o... | Superseded |
| I72 | A click that starts a Polygon gesture clears side-count digits typed before it and not ... | Superseded |
| P05 | Interaction principles: immediate and predictable. | Superseded |
| P08 | Small fixes (nothing you'd notice, no protocol / format / boundary / saving change, ~30... | Superseded |
| P11 | Agents work in parallel by files, not topics: each job lists the files it expects to to... | Superseded |
| P12 | One Claude session is the integrator: it keeps the Work list, hands out jobs to other C... | Superseded |
| P13 | One Claude session is the integrator: it keeps the Work list, hands out jobs to other C... | Superseded |
| P27 | A worker session does at most 3 jobs in a row: after job.py done it takes the next Read... | Superseded |
| P30 | The target architect reasons about abstractions and owns the architecture map without r... | Superseded |
| P48 | Trial, from 2026-11-23 for a couple of days: Gemini (neon) is the full integrator in pl... | Superseded |
| P55 | Paths use underscores, and the code base is named after the app: ~/Sites/Organization/0... | Superseded |
| P59 | The first move takes decision-log.md and decision-archive.md into Napkin/02_Past_Decisi... | Superseded |
| W03a | Hard cell-shaped pigment and per-cell flip timing. | Superseded |
| W04a | Wave starts only after FreeCAD confirms. | Superseded |
| W05a | Edits: pigment ripple only; while waiting, an extra amber ring pulses. | Superseded |
| W07a | Wait at 80% of travel, then 60%, with a small pulse. | Superseded |
| W08a | Breathing also pulsed pigment strength and band width. | Superseded |
| W09a | Front clamped at the hold (speed jumps), then one smoothing stage (speed continuous, ac... | Superseded |

## Decided questions

Questions that have their answer; the Notes say where it went.

| # | Question | Status |
|---|---|---|
| Q2 | Next tool: Move/Copy with "/n" divide. | Decided |
| Q3 | Components and materials UI in the viewport. | Decided |
| Q5 | Switch the Godot renderer to Forward+ (Metal on Mac)? | Decided |
| Q6 | Inference beyond corners and grid: midpoints, on-edge, parallel. | Decided |
| Q7 | What should happen to later ops that depend on a rejected op? | Decided |
| Q9 | Mirrored copies: should copying a component across be able to mirror it? | Decided |
| Q10 | Hidden rectangles: if another board hides your rectangle from the camera, Push/Pull gra... | Decided |
| Q11 | Mirror tool: a plane tool you sweep through the planes, with SketchUp's arrow-key axis ... | Decided |
| Q12 | Mirror across any face's plane (not just the X/Y/Z planes), like FreeCAD lets you? | Decided |
| Q13 | Mirror several boards at once (needs a selection tool). | Decided |
| Q15 | Copies of plain boards are independent; only components stay linked. | Decided |
| Q16 | Use the same snapping (midpoints, edges, inference) in Rectangle and Push/Pull? | Decided |
| Q17 | Open existing FreeCAD files in Shop Sketch. | Decided |
| Q18 | FreeCAD's chained cuts slow down with history: on a board with 32 holes the next hole t... | Decided |
| Q19 | Stage 2: watch the file and merge FreeCAD-side changes, transparently or with a merge r... | Decided |
| Q20 | Combine consecutive edits on a board: back-to-back cuts become one Cut with several cut... | Decided |
| Q22 | Idea to explore: make the change pulse wait until the autosave. | Decided |
| Q23 | Idea to explore: enter a part, like entering a SketchUp component, to inspect or manipu... | Decided |
| Q25 | I26: what detaches an extrude-to-face relationship? | Decided |
| Q26 | I27: how does a through-cut stay through after thickness changes, and how does an expli... | Decided |
| Q27 | What happens when a referenced face disappears or splits? | Decided |
| Q28 | Codex suggestion (not approved): highlight the linked instances an edit will affect bef... | Decided |
| Q29 | Codex suggestion (not approved): keep component geometry linkage independent of array p... | Decided |
| Q30 | Codex suggestion (not approved): store grain orientation and physical texture scale rel... | Decided |
| Q31 | Codex suggestion (not approved): explicit material mappings for Godot and Blender, with... | Decided |
| Q36 | Three worker types? | Decided |
| Q37 | App name: Napkin / Napkin CAD, Model It, Modeln, SpeedCAD, Build It, Draw Print Build, ... | Decided |

## Done work

Work list items that are finished (and Split ones whose parts are all done).

| # | Item | Status |
|---|---|---|
| T1 | Mirror fix: component instances mirror through a compound wrapper (FreeCAD 1.1.3 and 1.... | Done |
| T2 | Push/pull computes each boolean twice (a check, then FreeCAD's feature). | Done |
| T3 | Viewport freezes on every confirmed action: it reloads and re-analyses every board (463... | Done |
| T4 | Split the 2,700-line viewport script: tools as their own objects, one shared snapping/i... | Done |
| T5 | Flatten FreeCAD chains: back-to-back cuts on a board become one Cut with several cutter... | Done |
| T6 | Worker lifecycle: the app starts, watches and restarts the FreeCAD worker itself (today... | Done |
| T7 | Trackpad: orbit, pan and pinch-zoom without a middle/right mouse button. | Done |
| T8 | Native shell: a real .app with menus and file dialogs; Metal renderer. | Done |
| T10 | FreeCAD's command-line program keeps only 20 undo steps: the worker's MaxUndoSize = 500... | Done |
| T11 | Lines vanish (grid, axes, edges): 1-pixel GL lines get no anti-aliasing, and lines sit ... | Done |
| T12 | Linked board copies (A22c): Move-copies and arrays of boards become linked instances; w... | Done |
| T13 | Join by default (I04b): a rectangle drawn on a face and pushed out joins that board; B ... | Done |
| T15 | Materials (M03, Q3): wood card library (Wood Handbook numbers, CC0 face and end-grain t... | Done |
| T16 | Rejections take their dependents with them (Q7): one red wave, one message; independent... | Done |
| T19 | Quiet save indicator (Q22): 'saving…' / 'saved' in the status bar; the worker reports w... | Done |
| T20 | Assemblies you can enter (Q23): group boards; double-click to edit inside with the rest... | Done |
| T23 | Zoom too aggressive with a smooth-scrolling mouse (MX Master): zoom by the amount scrol... | Done |
| T24 | Mac-like interface: system font, a segmented tool control, native-looking buttons and s... | Done |
| T26 | Mirror groups (A11b): a mirrored copy and its original form a group you enter by double... | Done |
| T27 | Mirror across the plane of any face of an object (Q12), not just the red/green/blue pla... | Done |
| T28 | Hide and unhide boards (and assemblies), SketchUp style. | Done |
| T29 | Models opened in FreeCAD show everything hidden: Shop Sketch saved without FreeCAD's vi... | Done |
| T30 | Several windows: one FreeCAD worker serves every window, one window per model (W13); Ne... | Done |
| T31 | Redo (Codex S03): redo after undo; Escape cancels the current gesture before leaving an... | Done |
| T32 | Measurements (Codex S04): inches and feet, fractions (3/4", 1-1/2"), mm and decimals, s... | Done |
| T33 | Small distances: typed and snapped values bypass the 0.5 mm accidental-drag filter; mod... | Done |
| T34 | Selection (Codex S01): drag-box selection (window one way, crossing the other), Delete,... | Done |
| T39 | Document controller (A31): move the action list, sync, request tracking and save state ... | Done |
| T40 | Save generations and failure reporting (A32). | Done |
| T41 | Split geometry presentation and selection/context out of main.gd (A33). | Done |
| T42 | Split worker/replay.py (~1,800 lines) into modules: building boards (model.py), one fil... | Done |
| T43 | A short CLAUDE.md in each part's folder (worker/, viewport/, viewport/tools/): what tha... | Done |
| T44 | Write the window ↔ worker protocol down as one document (docs/protocol.md): every comma... | Done |
| T45 | Flaky quick-test step: 'the save indicator says Saving... | Done |
| T46 | Properties panel: select one piece, open Properties, and see and edit its FreeCAD value... | Done |
| T47 | Test runs collide on worker ports: two quick tests at once (Claude's and Codex's) both ... | Done |
| T48 | Scenario test: one worker session builds a busy fixture model (a carcass with panels, h... | Done |
| T49 | Run the tests more in parallel (the Mac has 8 cores; most test time uses one or two). | Done |
| T50 | Worker: replace the star imports (from common import *, from export import *: 19 of 27 ... | Done |
| T51 | Split viewport/tests.gd: quick-test sections and each recorded / targeted suite in thei... | Done |
| T52 | Restructure the decision log so agents read less: superseded rows in their own section,... | Done |
| T53 | Plane fits and face links (I40, I41, I42), ported from Codex's codex/plane-properties (... | Done |
| T54 | Plane fits: re-fit only boards whose source/target stock frame, label or settings chang... | Done |
| T55 | Remove duplicated/stale documentation while retaining the architecture map; leave every... | Done |
| T56 | Add a compact agent startup command: show checkout/worktree status, recent main commits... | Done |
| T57 | Lag at the start of a drag: Rectangle held at its start corner by its own snaps; Push/P... | Done |
| T58 | Copy an assembly into a row (3x, /3): each copy a linked assembly, editable spacing; en... | Done |
| T60 | Chains of face ties: a board tied to a board that is itself tied follows the whole chai... | Done |
| T61 | Face ties on linked copies: ties on a component's definition and its instances (from T14). | Done |
| T62 | Face ties on shapes other than plain rectangular boards (from T14). | Done |
| T64 | Watch the model file and reload FreeCAD's saves automatically, with a wave (from T17). | Done |
| T66 | Lengths shown in the measurements box in your units, display rounding separate from sto... | Done |
| T67 | IDs that never collide across kept history branches (from T35). | Done |
| T70 | A late worker reply can't replace a newer state (from T35). | Done |
| T74 | Decision-log and handoff IDs given at merge: a branch writes placeholders (I-new-N, T-n... | Done |
| T75 | Move keyboard handling and the measurements box out of viewport/main.gd (2,100 lines) i... | Done |
| T76 | Split worker/test_scenario.py into a file per feature, found by name, so two branches a... | Done |
| T77 | Handoff entries that don't conflict: one file per entry (docs/handoff/), with the open ... | Done |
| T78 | Preserve drawing requests made while a sync is in flight; send drawing=true with the ne... | Done |
| T79 | A failed save is forgotten: save_pending logs the error and drops the pending save, and... | Done |
| T80 | The full test fails now and then, on main too: one recorded suite differs, a different ... | Done |
| T81 | Circle tool: centre then radius (typed or dragged), on the ground or a face; push/pull ... | Done |
| T82 | Line tool, closed outlines and split faces (I51): lines that close a loop make a face; ... | Done |
| T83 | Arcs: arc gestures (and rounded corners on outlines), exact in FreeCAD; arcs split face... | Done |
| T85 | Quick test: `[hide] View > Hidden geometry shows it ghosted` fails on every run tonight... | Done |
| T86 | A process outlives the quick test: capturing its output with $(...) sometimes never ret... | Done |
| T87 | Merge automation holes (a Codex review, 2026-11-22): integrate.py staged everything bef... | Done |
| T88 | Narrow main.gd's interface: tools reach into Main for shared state (move_tool.gd uses m. | Done |
| T89 | Integrator checks: a branch's protocol-version bump is renumbered at merge when main bu... | Done |
| T90 | A faster gate: tools/gate.sh runs the quick test then the full test (~3-4 min); merging... | Done |
| T91 | Merge bookkeeping by hand: integrate.py ends with "left for you: the Work list result a... | Done |
| T92 | Decision log rows are added by hand (five on 2026-11-22). | Done |
| T93 | What waits on William is kept by hand in the integrator's note (H050) and goes stale. | Done |
| T94 | Reshape the decision log as P23: the archive file, the subject index and headings, prin... | Done |
| T95 | Tests find themselves: every new test file today adds a line to tools/featuretest.sh an... | Done |
| T96 | The job queue (P24): tools/job.py take / beat / wait / done / watch / status, its state... | Done |
| T97 | Follow-ups land on the integrator's list (P26): 'Follow-up:' and 'For the integrator:' ... | Done |
| T98 | Worker sessions chain jobs (P27): job.py counts jobs per session name (take --session <... | Done |
| T100 | The map is the integrator's (P28): 'Architecture:' lines in a response (beside Follow-u... | Done |
| T101 | Recovery on opening follows A37: the newest file wins; finish a save of ours that stopp... | Done |
| T102 | Guard against running tests in the wrong checkout: quicktest.sh and gate.sh stop when t... | Done |
| T103 | Split integrate.py's main() into named steps (merge, settle conflicts, number IDs, arch... | Done |
| T104 | Make the worker's instructions cheap to read: BOARD.md's worker steps in plain words, r... | Done |
| T105 | job.py done accepts the last quick-test pass when every commit after it changes only th... | Done |
| T106 | The test scripts report progress and keep their output in the job: gate.sh, quicktest.s... | Done |
| T107 | A briefing for each job: job.py take prints, after the job's entry, only the rules that... | Done |
| T109 | Loops of lines and arcs: drawings that meet end to end and close (lines and arcs mixed,... | Done |
| T110 | Test helpers for failure paths: hold a worker reply back, drop and restore the worker l... | Done |
| T112 | Overlap by function (P45, job H115 for Codex): handoff.touches() reads backticked names... | Done |
| T113 | Thin main.gd (~2,130 lines → ~800), behaviour unchanged, one section per job, as filler... | Done |
| T114 | A worker's question doesn't need William's keyboard: scope questions (a file or functio... | Done |
| T115 | Briefs the tools can read: a check when a job is marked Ready that its Touches are full... | Done |
| T116 | Tooling follow-ups: feature-test logs named by folder, so same-named worker and viewpor... | Done |
| T117 | Wire passive job-usage lifecycle hooks (take, done, return, merge) into tools/job.py an... | Done |
| T119 | Role-aware startup report (--role integrator / worker): --role integrator surfaces open... | Done |
| T120 | Briefing-officer startup and read-only queue reads: surface interrupted merges (shopske... | Done |
| T121 | One-step handoff archival (--commit and --push on tools/handoff.py archive with sandbox... | Done |
| T122 | Rectangle after-the-fact typed dimensions: numbers typed right after creating a rectang... | Done |
| T123 | Move array live preview: typing xN / Nx / *N / /N during a Move previews the array befo... | Done |
| T124 | Auto-set document units from first typed length with an explicit unit when the document... | Done |
| T125 | Fix Pull and autosave lag: stop latching TechDraw generation onto every autosave (1.7 s... | Done |
| T126 | Token benchmarker (tools/usage.py): vendor job-usage into tools/, fix AGY transcript pa... | Done |
| T127 | Enter and edit components, and upgrade Codex's Properties window (viewport/property_pan... | Done |
| T128 | Make tools/job.py take robust against parallel Gemini worker session collisions: detect... | Done |
| T129 | Improve tools/usage.py holes diagnostics: strip AGY quoted targets, flag only overlappi... | Done |
| T130 | Auto-unblock queued jobs immediately when their dependency job(s) merge and push. | Done |
| T131 | Quiet-by-default `tools/test_*.py` suites: print only `FAIL` lines and summary by defau... | Done |
| T134 | One start script per agent role that loads its onboarding context (identity, principles... | Done |
| T140 | Decide when and how William's new organization principles take effect, and how they sit... | Done |
| T142 | A Work list item is marked Done automatically when the job (or last of its jobs) that c... | Done |
| T143 | Move tools/usage.py (2,760 lines, token benchmarking) and its tests out of the project'... | Done |
| T144 | Two tool follow-ups: a too-big corner fillet radius says why (H086's follow-up); Polygo... | Done |
| T145 | Go through the ultra review findings (William's /code-review ultra of Gemini's stretch,... | Done |
| T146 | Atomize the principles and past decisions: one file per ruling (G, P and the rest), wri... | Done |
| T147 | Plane fits keep their target and stay correct when boards are cut, flipped, chained or ... | Done |
| T148 | The worker turns off FreeCAD's backup files (CreateBackupFiles) in the shared user pref... | Done |
| T149 | Tools and habits take the organization's names (FOR_<doing>.py; WHEN_<this>_<DO_THAT>.p... | Done |
| T150 | Personal spaces take the rest of the proposal: a journal about how the work felt (not w... | Done |
| T151 | Tests run by what changed: a branch that touches only tools, guides, the log or persona... | Done |
| T154 | Faster tests: cut the waits (the gate's ~100 s, the quick test's viewport lanes, FreeCA... | Done |
| T156 | One personal space per model and job (sonnet-coder, opus-coder, gemini-hydrogen-coder, ... | Done |
| T162 | Fits become their own ops: plane_fit and replace_fit leave property_edit as fit and unf... | Done |

## Details

The full text of long archived decisions; the table row is the summary. Sorted by ID.
