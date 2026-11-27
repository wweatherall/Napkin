# Shop Sketch decision log

The live half of the decision log (P09, P23): what holds now. Each ruling (principle `G` or decision `A`, `D`, `I`,
`M`, `P`, `U`, `W`, ...) lives in its own file at `03_Past_Decisions/rulings/<ID>.md`, except `Subject: Process`
rulings, which live in `comitatus/03_Past_Decisions/rulings/<ID>.md` (T146); every ruling stays in its folder even
when Superseded (P01). This file keeps generated indexes (`Subjects`, `Principles`, `Decisions`), plus `Open questions`,
`Work list`, `Tunables`, and `Details` (for `Q`/`T`). [decision-archive.md](decision-archive.md) keeps the index of
Superseded rulings, decided questions, and done Work list items. Read a ruling with
`python3 tools/log.py show I34` (or open `03_Past_Decisions/rulings/I34.md`). Before 2026-11-21 it was a claude.ai
Sheet (revision 83 was the last); git history has every earlier export.

tools/sort_decision_log.py keeps it tidy (the pre-commit hook runs it whenever `decision-log.md`,
`decision-archive.md`, or `03_Past_Decisions/rulings/` is committed): ruling rows in tables are moved into
`rulings/<ID>.md`, Q/T tables and Details sort by ID, archival Q/T rows move to the archive with their Details, and
the generated indexes (`Subjects`, `Principles`, `Decisions`, `Superseded decisions`) are rebuilt from the ruling
files. A new decision names a subject from `Subjects` and the principle(s) it follows (`G01 ...`), or `—` if none
fits yet; a new subject is a new row in the `Subjects` index. Its `--check` reports what it can't fix.

New IDs (T74): a branch never takes a number. It writes a placeholder, the kind's letter, "-new-" and its own count
(I-new-N, T-new-N, Q-new-N, H-new-N, G-new-N; examples in prose keep the letter N, a digit makes a placeholder),
and the integrator runs tools/number_ids.py on main at merge, which gives each the next free number across all
files and everywhere it's cited.

tools/log.py (T92) does this bookkeeping: `add <kind> "<text>" --subject S --principles G01` writes a ruling file
(or Q/T row) with the right number or placeholder, dated and indexed (for principles at either level, use
`comitatus/09_Tools/ADD_A_PRINCIPLE.py`); `set <ID> --status S [--where ...] [--rel ...]` updates a ruling's status line without hand-editing; `note T66 "<text>"` appends to a Work list row's last column;
`show <subject|ID>` prints that subject's index + rulings, or an ID's ruling file + named principles (`--top`: this top).

Rule P01: a new decision that contradicts an old one gets a new ruling naming the old ID; the old ruling is marked
`Superseded` (`log.py set <ID> --status Superseded`), never deleted. Ask William before countermanding an Active
decision. Principles follow the same rule, and a group of decisions is folded into its principle only with
William's OK, one group at a time (P23).

## Subjects

One subject per decision; the Decisions column is generated.

| Subject | Covers | Decisions |
|---|---|---|
| Product | What Shop Sketch is for and the feel it aims at. | I01, P04, P51 |
| Architecture | The processes, the worker link, the app and the code's main boundaries. | A02, A03, A06, A08, A09, A27, A29, A30, A31, A33b, A34, A35, A40, W13 |
| Files, saving and undo | The .FCStd model and its journal, saving, opening, undo and redo. | A21, A23, A24, A25, A28, A32, A36, A37, A38, A39, A41, I38, I42, I54, I55, U01, U02, U03 |
| Drawing tools | Rectangle, Circle, Line: how a drawing gesture starts, follows and ends. | I02, I04b, I09, I11, I43, I44, I49, I50, I51, I58, I60, I61, I64, I65, I71, I73 |
| Push/Pull | Extruding, cutting, and fitting a board's end to another board. | I05, I08, I23, I24, I34, I40, I41, I45, I56 |
| Move, copies and arrays | Move, linked copies, arrays, mirrors, components and assemblies. | A10, A11b, A22c, A26, I10, I12c, I13b, I14, I15, I16, I17, I20, I21, I25, I28, I32, I46, I52, I53, I66, I69 |
| Snapping | Points, edges, axes and the grid, shared by every tool. | I03b, I18, I19 |
| Measurements | Typed values, units and the measurements box. | I35, I48, I57, I59, I62, I67, I70 |
| View and look | Camera and input devices, panels, the Mac look, lines, lighting, hiding. | I22, I30, I31, I36, I37, I63, W10, W11, W12, W14 |
| Feedback | The confirmation wave and what colours mean. | I06, W01, W02, W03, W04, W05, W06, W07, W08, W09 |
| Materials | Wood cards, grain and painting. | A05, I33, M01, M02, M03, M04 |
| Output | Drawings, cut lists and renders. | A07, D01, D02, I68, P06 |
| Process | How the agents work, test, merge and record decisions. | P01, P02, P03, P07, P09, P10, P14, P15, P16, P17, P18, P19, P20, P21, P22, P23, P24, P25, P26, P28, P29, P31, P32, P33, P34, P35, P36, P37, P38, P39, P40, P41, P42, P43, P44, P45, P46, P47, P49, P50, P52, P53, P54, P56, P57, P58, P60, P61, P62, P63, P64, P65, P66, P67, P68, P69, P70, P71 |

## Principles

Each states one idea; its file is `03_Past_Decisions/rulings/<ID>.md` (`python3 tools/log.py show G01`). William reviewed and approved them 2026-11-22 (G04 split into G04 and G13).

| ID | Principle | Status |
|---|---|---|
| G01 | Feel first: a draft appears the moment you act and input never waits on FreeCAD; FreeCA... | Active |
| G02 | The .FCStd file is the model: every action becomes ordinary, editable FreeCAD features,... | Active |
| G03 | Work as SketchUp does, and as a Mac app does, unless there's a reason not to; a decisio... | Active |
| G04 | Relationships stay live: copies, arrays, mirrors and fits follow later edits, and you c... | Active |
| G05 | One key per idea, meaning the same thing in every tool. | Active |
| G06 | Typed values follow what you're doing: the direction you drag, and the model's units fo... | Active |
| G07 | One meaning per colour: violet cuts, red rejects, amber is new; nothing else uses them ... | Active |
| G08 | Refer to geometry, never to FreeCAD's internal numbers. | Active |
| G09 | Never lose work: always saved, atomically, and undo crosses sessions without hiding cha... | Active |
| G10 | A rejected action says why and leaves nothing behind. | Active |
| G11 | Nothing rests on memory: every decision is logged, every behaviour has a named test, an... | Active |
| G12 | Work splits by files, and one integrator merges, numbers and keeps the records. | Active |
| G13 | Show what an edit will change before it does. | Active |

## Decisions

Active and Tentative decisions, grouped by subject. A long one has its full text under Details (`### <ID>`).

### Product

| ID | Decision | Status |
|---|---|---|
| I01 | Tool-first, no modes. | Active |
| P04 | Product direction: fast, direct, SketchUp-like modelling with a real, editable FreeCAD ... | Active |
| P51 | The app is named Napkin (replacing the working names Shop Sketch and FretchUp). | Active |

### Architecture

| ID | Decision | Status |
|---|---|---|
| A02 | FreeCAD runs as a long-running headless worker on localhost (newline JSON over TCP). | Active |
| A03 | Faces are referenced by geometry {body, normal, point}, never by FreeCAD face numbers. | Active |
| A06 | The front end (viewport + tools) is built in Godot 4.6. | Active |
| A08 | Don't port FreeCAD's renderer to Metal/bgfx; design within its limits (few objects, lig... | Active |
| A09 | Model space is Z-up millimetres; Godot is Y-up metres; convert only at the boundary. | Active |
| A27 | Shop Sketch starts its own FreeCAD worker, checks it every second and restarts it if it... | Active |
| A29 | The worker writes a mesh file per changed board (triangles, normals, FreeCAD's exact ed... | Active |
| A30 | Shop Sketch is a Mac app (tools/build_app.sh → dist/Shop Sketch.app) with native menus ... | Active |
| A31 | A document controller owns the model path, the action list, request numbering, worker s... | Active |
| A33b | Split geometry presentation (drafts, confirmed boards, highlights, waves, caches) and s... | Active |
| A34 | Tools and worker actions register themselves: each viewport/tools/*_tool.gd declares a ... | Active |
| A35 | A protocol version: hello carries protocol (an integer, 1 now), defined once on each si... | Active |
| A40 | All tools receive only ToolContext at setup. | Active |
| W13 | One FreeCAD worker serves every window, each on its own document. | Active |

### Files, saving and undo

| ID | Decision | Status |
|---|---|---|
| A21 | The FreeCAD file (.FCStd) is the model. | Active |
| A23 | Each action is one FreeCAD undo transaction. | Active |
| A24 | Autosave is atomic (write a copy, then swap it in) and waits for a ¼-second pause in yo... | Active |
| A25 | Opening a Shop Sketch file adopts its journal, so undo works across sessions. | Active |
| A28 | FreeCAD keeps only 20 undo steps; the 21st undo in a row rebuilds the model from the jo... | Active |
| A32 | Saving the model and its journal as one generation: the previous complete pair is kept ... | Active |
| A36 | When FreeCAD saves a model while Shop Sketch still has actions pending: Shop Sketch sto... | Active |
| A37 | Opening a model whose file and journal don't match: the newest file on disk is the mode... | Active |
| A38 | When Shop Sketch takes in a FreeCAD edit (opening a file changed outside it, or reloadi... | Active |
| A39 | When the actions pending under A36's 'FreeCAD saved this model' question land while it ... | Active |
| A41 | The worker turns off FreeCAD's backup files only for the moment of its own save and the... | Active |
| I38 | Redo: Edit > Redo, ⇧⌘Z or the toolbar button; linear until U01 (a new action ends it). | Active |
| I42 | A board's name in FreeCAD's tree is 'Board 3' for b3 (copies, mirrors and made-unique b... | Active |
| I54 | When a save fails, the save indicator says "Couldn't save: <reason>" (in Saved's place,... | Active |
| I55 | Closing a window whose latest revision isn't saved waits for it; if the save fails, a d... | Active |
| U01 | Undo keeps the paths you leave: a new edit after undoing starts a branch and the old pa... | Active |
| U02 | Branch-safe identities: no new board, rectangle or hole reuses an ID a kept branch uses... | Active |
| U03 | Merging branches, conservatively: an explicit command with a preview that keeps both or... | Active |

### Drawing tools

| ID | Decision | Status |
|---|---|---|
| I02 | Core loop is Rectangle → Push/Pull. | Active |
| I04b | A profile drawn on an existing part's surface joins that part by default when extruded. | Active |
| I09 | A rectangle drawn on a face may overhang the face's edges; the whole rectangle is extru... | Active |
| I11 | Tools act on what you can see when you start. | Active |
| I43 | Rectangle, Push/Pull and Move start on the press and follow the cursor at once. | Active |
| I44 | Drawing a rectangle's second corner ignores a point snap that would leave a side at zer... | Active |
| I49 | Shapes beyond rectangles (Codex S08): Circle first, then Line and closed outlines, then... | Active |
| I50 | The Circle tool's key is C (as in SketchUp); its toolbar segment is "Circle", tooltip "... | Active |
| I51 | Lines split faces (as in SketchUp): a line drawn across a face divides it into regions;... | Active |
| I58 | Line tool: key L. | Active |
| I60 | Arc tool: key A, two kinds; pressing A again while it is active switches between them, ... | Active |
| I61 | An arc started on a corner, where two edges of a face or profile meet, defaults to tang... | Active |
| I64 | Rotated Rectangle and Polygon (T84): pressing R again while Rectangle is active toggles... | Active |
| I65 | Numbers typed after creating a rectangle, before any other action, alter that rectangle... | Active |
| I71 | A corner fillet radius too big for the corner's edges (typed 50r on a corner) leaves th... | Active |
| I73 | Before a Polygon gesture the measurements box is the side count: a number typed there s... | Active |

### Push/Pull

| ID | Decision | Status |
|---|---|---|
| I05 | Pushing an existing face always edits that board, never makes a new one. | Active |
| I08 | FreeCAD rejects a push/pull that does nothing: a cut that doesn't reach the board, a me... | Active |
| I23 | Pushing in snaps to the faces behind (back face, pocket floor), measured through the bo... | Tentative |
| I24 | A cut that ends at the opposite face is a through-cut in FreeCAD: its length is an expr... | Tentative |
| I34 | Pushing a piece toward another has three snaps: first contact, the near surface (scribe... | Active |
| I40 | A push or a Properties dimension made up to another board's face stays tied to that fac... | Active |
| I41 | Pulling into another board's face (Push/Pull or a Properties fit) has three end conditi... | Active |
| I45 | Pushing in snaps to a face behind only when the cursor is nearer to it on screen than t... | Active |
| I56 | In Push/Pull, ⌥ Option is the one key for how the pushed end meets what it hits: on a f... | Active |

### Move, copies and arrays

| ID | Decision | Status |
|---|---|---|
| A10 | Mirrored copies are live FreeCAD Part Mirror features: they follow every later edit of ... | Active |
| A11b | A mirrored copy and its original form a mirror group you enter by double-clicking (like... | Active |
| A22c | As A22b, but copies of boards are linked: a Move-copy or array is a linked instance, so... | Active |
| A26 | A component instance is mirrored through a Part::Compound wrapper between the instance ... | Active |
| I10 | Copies are moved, not mirrored (SketchUp's default). | Active |
| I12c | No separate Mirror tool: in Move, tap Shift to toggle mirror (as Option toggles copy). | Active |
| I13b | A typed mirror distance runs from the face you clicked to the plane. | Active |
| I14 | Move (M), SketchUp style: pick a point, arrows lock axes, click or type a distance. | Active |
| I15 | Shift without copy flips the board itself (keeps its ID); Option + Shift makes a linked... | Active |
| I16 | Axis-locked moves follow the closest point on the locked axis to the cursor; when you'r... | Active |
| I17 | A free move slides on the horizontal plane through the grab point. | Active |
| I20 | Tapping an arrow key cycles: lock to that axis → lock to the plane perpendicular to it ... | Active |
| I21 | Move on a hole's wall grabs the hole (violet): move it on its board, or Option-copy it ... | Active |
| I25 | Arrays and mirrors stay relationships. | Active |
| I28 | Editing a linked component changes its siblings. | Active |
| I32 | An array works like a component you enter: from outside a click picks the whole row; in... | Active |
| I46 | Inside an entered component or array, deleting a member preserves the others; if it was... | Active |
| I52 | Copying a whole assembly makes a new assembly of linked boards; 3x and /3 make rows of ... | Active |
| I53 | Inside an entered assembly row, moving a copied assembly detaches that whole assembly's... | Active |
| I66 | Typing an array count (Nx, xN, *N, /N) during a Move previews the array live before cli... | Active |
| I69 | Double-clicking a linked component (board family) enters and isolates it like an assemb... | Active |

### Snapping

| ID | Decision | Status |
|---|---|---|
| I03b | Rectangle and Push/Pull snap with Move's engine (inference.gd): endpoints, then midpoin... | Tentative |
| I18 | Soft axis inference: drag within 8° of an axis's on-screen direction and the move stick... | Active |
| I19 | Grid snapping snaps the distance travelled, not the position; point snaps (endpoint/mid... | Active |

### Measurements

| ID | Decision | Status |
|---|---|---|
| I35 | In a typed measurement a minus always subtracts (1-1/2" is 1/2 inch); mixed numbers and... | Active |
| I48 | Delete / Backspace belong to the measurements box once you click it or type, even after... | Active |
| I57 | Lengths are shown in the model's units, picked in a Units menu: Feet and inches (8' 3 1... | Active |
| I59 | A bare number typed in the measurements box (no unit) is in the model's display units (... | Active |
| I62 | A model with no units saved in it (made before T66, or its saved value unreadable) open... | Active |
| I67 | A document with no units explicitly set yet (new model or pre-T66 model without saved S... | Active |
| I70 | On a first-ever typed length with no unit suffix (no preferences.json units.default, no... | Active |

### View and look

| ID | Decision | Status |
|---|---|---|
| I22 | Trackpad: two fingers orbit (same speed as a mouse drag), Shift + two fingers pan, pinc... | Tentative |
| I30 | The mouse wheel zooms by how much you scrolled (Godot's scroll amount), not a fixed ste... | Active |
| I31 | Mac-like interface: system font, a segmented-control toolbar, a quiet status bar, a rou... | Tentative |
| I36 | A Properties panel shows FreeCAD's own values for the selected piece and its features; ... | Active |
| I37 | Hide and unhide, SketchUp style: H hides, Shift+H unhides all, View > Hidden geometry g... | Active |
| I63 | Preferences are a JSON file for now (a Mac window later, T111): user://preferences.json... | Active |
| W10 | Lighting toned down (filmic tone mapping, lower sun and ambient). | Active |
| W11 | Highlights and drafts that lie on a face are drawn with a small depth bias in their sha... | Active |
| W12 | Lines are anti-aliased strips a fixed width on screen (edges 1.5 pt, grid 1 pt, axes 1.... | Active |
| W14 | H059 may replace raw IDs with readable board names in main.gd and selection.gd status m... | Active |

### Feedback

| ID | Decision | Status |
|---|---|---|
| I06 | A rejected operation is removed from the op log after its red wave; the reason stays in... | Active |
| W01 | Every push/pull plays a colour wave that starts where the cursor finished the operation. | Active |
| W02 | Cuttlefish look: a noise-wobbled front with pigment cells blooming just ahead of it. | Active |
| W03 | Softer: one smooth, noise-blurred front (~5 cm) and round blurry pigment cells at 40% s... | Active |
| W04 | Wave starts immediately (optimistic). | Active |
| W05 | New boards start translucent amber. | Active |
| W06 | Accepted: the wave completes into the real material. | Active |
| W07 | While waiting, the front breathes: it glides between 30% and 60% of its travel, ~2.6 s ... | Active |
| W08 | Breathing never changes colour or pigment; only the front moves. | Active |
| W09 | Front motion is smooth to the 2nd derivative: position, speed and acceleration are all ... | Active |

### Materials

| ID | Decision | Status |
|---|---|---|
| A05 | Material lives in a metadata field, never in part names. | Active |
| I33 | Turn grain 90° is T, on the board under the cursor (G was already Grid snap). | Tentative |
| M01 | Materials are assigned in Godot and carried through the FreeCAD model into the eventual... | Active |
| M02 | Material handling understands grain direction: material identity and orientation are pr... | Active |
| M03 | Materials are FreeCAD material cards. | Active |
| M04 | Wood data from the Wood Handbook GTR-190 ch. | Active |

### Output

| ID | Decision | Status |
|---|---|---|
| A07 | Blender is used only for final renders. | Active |
| D01 | Shop drawing: A3, 1:10, third-angle projection, overall dimensions, cut list grouped by... | Active |
| D02 | Cut-list sizes are each board's bounding box in its own frame. | Tentative |
| I68 | Automatically created TechDraw drawing pages are deleted after the PDF/SVG drawing is g... | Active |
| P06 | Main output: a buildable design: plans, a render, and possibly a cut list. | Active |

### Process

| ID | Decision | Status |
|---|---|---|
| P01 | This log is the reference. | Active |
| P02 | Test hooks (forced rejection, worker delay_ms, --fxtest/--breathtest) are for testing o... | Active |
| P03 | Recordings use --true-latency: each FreeCAD reply is held until the video clock has run... | Active |
| P07 | Two kinds of test: feature tests check answers against FreeCAD with no window (featuret... | Active |
| P09 | The decision log is docs/decision-log.md in the repo, edited directly by whichever agen... | Active |
| P10 | Give documentation distinct owners and link rather than repeat: architecture owns bound... | Active |
| P14 | The work board: BOARD.md at the top of the repo lists each agent's next job and notes f... | Active |
| P15 | The agent startup report is `python3 tools/startup.py [IDs]`: checkout and worktrees, r... | Active |
| P16 | One Claude session is the integrator: it keeps the Work list and the board, hands out j... | Active |
| P17 | Workers don't edit the Work list: a worker's result goes in its handoff response, and t... | Active |
| P18 | The merge gate is tools/gate.sh: the quick test, then the full test, one verdict. | Active |
| P19 | One integrator at a time, by lock: tools/integrator.py keeps the lock in git's common f... | Active |
| P20 | The integrator merges with tools/integrate.py <branch> --as <name>: merge, settle hando... | Active |
| P21 | Every place the viewport predicts what FreeCAD will compute (lengths today; circles, sp... | Active |
| P22 | Small fixes take P08's light path (nothing you'd notice, no protocol / format / boundar... | Active |
| P23 | The decision log is two files with the same IDs: docs/decision-log.md is what's live (a... | Active |
| P24 | Jobs run through a queue with two buttons: a worker takes a job (its own worktree, bran... | Active |
| P25 | A job's scratch files, logs and measurements go in scratch/ inside its worktree (ignore... | Active |
| P26 | Leftovers reach the integrator's list by themselves: a worker writes each one as its ow... | Active |
| P28 | ARCHITECTURE.md and docs/protocol.md are the integrator's: a worker doesn't edit them; ... | Active |
| P29 | Target agent system separates worker, integrator, architect, dispatcher/time manager, i... | Tentative |
| P31 | Workers must supply an abstract structural report explaining how their new code integra... | Tentative |
| P32 | The integrator verifies worker structural reports against implementation as part of its... | Tentative |
| P33 | The target dispatcher/time manager manages agent starting, pausing and waking, and dete... | Tentative |
| P34 | The ideator is William’s partner for exploring ideas; the decision partner reasons thro... | Tentative |
| P35 | The ideator and decision partner primarily consult the architect for technical structur... | Tentative |
| P36 | The architect plans from the map without reading code: it reads ARCHITECTURE.md and the... | Tentative |
| P37 | A worker session does one job: take, work, done, then it stops and tells you it's ready... | Active |
| P38 | Workers are started in a visible Terminal window with Remote Control, so you can follow... | Active |
| P39 | The integrator has no timed check-ins: it is woken only by the queue, with job.py watch... | Active |
| P40 | A worker deals with its own hung processes; the integrator hears only of a worker that ... | Active |
| P41 | H059 includes the direct ID allocation sites in viewport/tools/, selection.gd and main.... | Active |
| P42 | A brief for a job that touches saving, reloading or the worker link has a 'What can fai... | Active |
| P43 | The integrator doesn't run a light /code-review on every merge; review stays as docs/in... | Active |
| P44 | A brief's rule says what it's for as well as what to do. | Active |
| P45 | Agents work in parallel by files, not topics, as P11 said (each job lists its Touches a... | Active |
| P46 | A worker may update, without asking first, a tools/test_*.py check outside its Touches ... | Active |
| P47 | A worker's question accepts follow-up answers until the worker reads the pending answers. | Active |
| P49 | Once integrator review and tests pass, merge and push without stopping to ask: the inte... | Active |
| P50 | Once T138 is built: each code file carries a one or two sentence description written by... | Tentative |
| P52 | The Gemini-integrator trial (P48) is closed: its work on main is kept, and the integrat... | Active |
| P53 | William's gate on work is choosing which Work list items become jobs; once a job's revi... | Active |
| P54 | The organization is the parent folder (01_Principles ... | Active |
| P56 | The code (viewport/, worker/, tools/, tests/, the .command files) moves into Napkin/05_... | Active |
| P57 | Each code base keeps its own job system (board, briefs, job tools, worktrees) since a j... | Active |
| P58 | Organization is its own git repo with a private GitHub remote the integrator pushes to;... | Active |
| P60 | Code base folders use the Organization's numbers, so a number means the same thing at b... | Active |
| P61 | The first move takes decision-log.md and decision-archive.md into Napkin/03_Past_Decisi... | Active |
| P62 | The Organization repo is named comitatus (private GitHub repo wweatherall/comitatus); t... | Active |
| P63 | Job worktrees live in Organization/08_Code_Bases/.worktrees/<code base>/<id> (hidden, o... | Active |
| P64 | The organization is named comitatus, and so is its folder: ~/Sites/comitatus (was ~/Sit... | Active |
| P65 | Work list items (T) and open questions (Q) become one file each too, like rulings (T146... | Active |
| P66 | Generated files in the comitatus repo (05_Jobs, 06_To-dos, the principles ranking) are ... | Active |
| P67 | A Work list item goes Open -> On the board (H0NN, ...) when a job naming it is written,... | Active |
| P68 | A Work list item is a to-do with a life story: Open -> Picked up (when the integrator t... | Active |
| P69 | The organization's tools live in comitatus/09_Tools (a code base's own stay in its tool... | Active |
| P70 | comitatus's principles (comitatus/01_Principles/principles.md) and the org chart (comit... | Active |
| P71 | Personal time: a coder whose job comes back clean (merged without being returned) may s... | Active |

## Open questions

| # | Question | Status |
|---|---|---|
| Q1 | Add a third smoothing stage to remove the small acceleration corner at the moment FreeC... | Open |
| Q4 | Feel test on your own machine: wave duration, breathing speed, orbit smoothness. | Open |
| Q8 | Cut list for angled cuts (D02). | Parked |
| Q14 | B toggles 'New board', but in SketchUp B is Paint Bucket. | Open |
| Q21 | Revisit drawing generation (plans). | Parked |
| Q24 | Idea to explore: separating solids or 'exploding' parts. | Parked |
| Q32 | Delete / Backspace rules (I48): try them on real hardware and settle them. | Open |
| Q33 | Choose a keyboard shortcut for the Polygon tool (built without a hotkey first, toolbar ... | Open |
| Q34 | Revisit retaining automatically created TechDraw drawing pages inside .FCStd (I68 delet... | Open |
| Q35 | Extruding off a drawing on a board's face (refines I04b): William leans toward making t... | Open |

## Work list

| # | Item | Status |
|---|---|---|
| T9 | Reserve: answer from plain shapes first, let FreeCAD's feature tree catch up when idle. | Open |
| T14 | Face ties (I26b): pushes and cuts made up to a face stay tied to it (FreeCAD expression... | Split |
| T17 | Stage 2 (Q19): watch the model file; reload FreeCAD's saves automatically with a wave; ... | Split |
| T18 | Stage 3 (Q17): open FreeCAD files Shop Sketch didn't make, adopting each solid as a boa... | Open |
| T21 | Exploded view for assembly diagrams (Q24): a separate action, not a model change. | Parked |
| T22 | Drawing flow (Q21): a sheet per part; assembly overview; cut list + material totals; cu... | Parked |
| T25 | Redo the interface in AppKit: real macOS toolbar, controls, measurements field and pane... | Parked |
| T35 | Branch-safe IDs and action boundaries (U02): IDs that never collide across kept branche... | Split |
| T36 | Branching undo history (U01): keep abandoned futures; history panel on the right (~20 s... | Split |
| T37 | Merge branches (U03): explicit command, preview, independent edits first, conflicts fla... | Parked |
| T38 | Push to another piece's surface with a choice of which piece is cut (I34, Codex S17). | Open |
| T59 | Face ties for cuts and pocket floors: a cut or pocket made up to a face stays tied to i... | Open |
| T63 | The colour cue for tied faces (from T14). | Open |
| T65 | When a FreeCAD save dropped Shop Sketch actions, ask: re-apply them on top, or keep Fre... | Parked |
| T68 | One undo step per user action (from T35). | Open |
| T69 | Typed corrections that don't rewrite kept versions (from T35). | Open |
| T71 | History stage 2: keep abandoned futures in memory and show the history panel on the rig... | Open |
| T72 | History stage 3: keep branches across restarts, with checkpoints for old states (from T... | Open |
| T73 | History stage 4: naming branches, comparing them, navigation polish (from T36). | Open |
| T84 | Polygons and rotated rectangles. | Open |
| T99 | Choose the Paint Bucket's key (Q14): B is 'New board' today (I04b) but the Paint Bucket... | Open |
| T108 | Fillet tool: round a board's edges with FreeCAD's own fillet (exact, editable), once ed... | Open |
| T111 | Preferences: a window for the user's settings; first, the default units a new model (or... | Open |
| T118 | 3-Point Circle: draw a circle from three points on its edge (like FreeCAD's 3-point cir... | Open |
| T132 | Integrator startup friction: (1) startup.py brief prints a ready-to-run 'integrator.py ... | Open |
| T133 | Polygon: scrolling the mouse wheel between the centre click and the radius click change... | Open |
| T135 | Reorganize the organization and code-base folders (principles, habits, case law, person... | Open |
| T136 | Self-generated architecture map: current and proposed, unbuilt work ghosted, job-board ... | Open |
| T137 | Decimal commas for European typing of measurements. | Open |
| T138 | Compress ARCHITECTURE.md heavily so the start-up brief can carry the map (about 80 KB t... | On the board (H167) |
| T139 | Rename the app to Napkin: what you see, the built app, folders, and the code and docs t... | Open |
| T141 | William tries the Polygon tool by eye in a rebuilt app (tools/BUILD_THE_APP.sh). | Open |
| T152 | Thin the tests without losing coverage: research how others do it (coverage-guided test... | Open |
| T153 | Generated tests: inputs made fresh each run (a random seed, printed so a failure can be... | Open |
| T155 | Find a home for (or delete) the loose files at Napkin's top level: 'Codex's suggestions... | Open |
| T157 | Replay's reply says cmd sync (protocol finding 6): a consumer matching a reply's cmd to... | Open |
| T158 | The window sends the op list's name nested (oplog.name) but the worker's run_sync reads... | Open |

## Tunables

| Setting | Value | What it does | File | Decision |
|---|---|---|---|---|
| HOLD | 0.6 | Top of the breathing range (fraction of the wave's travel). | viewport/main.gd | W07 |
| BREATH_LO | 0.3 | Bottom of the breathing range. | viewport/main.gd | W07 |
| BREATH_W | 2.4 | Breathing speed in rad/s (2.4 ≈ one glide back and forth every 2.6 s). | viewport/main.gd | W07 |
| SLOW | 0.35 | How far before the hold the front starts slowing (longer = gentler arrival). | viewport/main.gd | W09 |
| TAU | 0.12 | Seconds per smoothing stage while waiting. | viewport/main.gd | W09 |
| TAU_UP | 0.2 | Seconds per smoothing stage when speeding back up after FreeCAD accepts. | viewport/main.gd | W09 |
| LEAD | 0.1 | Seconds of look-ahead; cancels overshoot from the smoothing. | viewport/main.gd | W09 |
| AMP_COMP | 1.11 | Widens the breathing aim so the smoothed front really spans 30–60%. | viewport/main.gd | W09 |
| REJECT_DUR | 0.6 | Seconds for the red rejection wave. | viewport/main.gd | W06 |
| Wave duration | reach ÷ 0.7 m/s, clamped 0.5–1.0 s | How long the front takes to cross a board. | viewport/main.gd _begin_wave() | W01 |
| softness | 0.05 | Width of the blurred colour front, in metres. | viewport/confirm_wave.gdshader | W03 |
| pigment_strength | 0.4 | Darkness of the pigment cells. | viewport/confirm_wave.gdshader | W03 |
| cell_size | 0.016 | Size of the pigment cells, in metres. | viewport/confirm_wave.gdshader | W03 |
| draft_alpha | 0.55 | Opacity of draft (unconfirmed) boards. | viewport/confirm_wave.gdshader | W05 |
| GRID | 10 | Grid snap step, mm. | viewport/inference.gd (main.gd keeps the name) | I03 |
| SNAP_PX | 14 | Corner snap radius on screen, pixels. | viewport/inference.gd (main.gd keeps the name) | I03 |
| Simulator | sim/front_sim.py | Try SLOW/TAU/LEAD/AMP_COMP values without launching Godot. | sim/front_sim.py | W09 |
| INFER_DEG | 8 | Drag within this many degrees of an axis's on-screen direction to stick to it. | viewport/main.gd | I18 |
| RELEASE_DEG | 12 | Angle at which an inferred axis lets go (bigger than INFER_DEG so it doesn't flicker). | viewport/main.gd | I18 |
| EDGE_PX | 8 | On-edge snap radius on screen, pixels. | viewport/main.gd | I18 |
| IDLE_SAVE_S | 0.25 | Seconds of quiet before the worker autosaves. | worker/replay.py serve() | A24 |
| Undo steps | 20 | FreeCAD's undo steps per session (fixed in its command-line program; the old MaxUndoSize = 500 setting had no effect there). Past them, undo rebuilds from the journal. | worker/replay.py (top) | A28 |
| OVERLAY_BIAS | 0.001 | How far highlights, drafts and lines are pulled toward the camera, as a fraction of their distance (invisible; beats flicker). | viewport/main.gd | W11, W12 |
| LINE_PX | 1.5 | Width of board edges, outlines and previews, in points (doubled on a Retina screen). | viewport/main.gd | W12 |
| GRID_LINE_PX | 1 | Width of grid lines, in points. | viewport/main.gd | W12 |
| AXIS_LINE_PX | 1.75 | Width of the red/green/blue axes, in points. | viewport/main.gd | W12 |
| Grid fade | 1.5× → 3.5× the orbit distance (+0.5 / +1.5 m) | Where the grid starts and finishes fading out. | viewport/main.gd _update_camera() | W12 |
| TRACKPAD_PX | 33 | Trackpad speed: 33 makes one finger-pixel turn the view as much as one mouse-pixel. | viewport/main.gd | I22 |
| STATE_CACHE_MAX | 40 | Confirmed model states the viewport remembers for instant undo. | viewport/main.gd | A28 |
| WORKER_MAX_RESTARTS | 5 | Worker restarts allowed in a minute before Shop Sketch gives up and says so. | viewport/main.gd | A27 |
| DRAG_PX | 6 | Rectangle, Push/Pull, Move: the cursor moving this far with the button down makes it a drag (ends on release). | viewport/tools/tool.gd | I43 |
| HOLD_MS | 300 | Rectangle, Push/Pull, Move: a press held this long also counts as a drag. | viewport/tools/tool.gd | I43 |
| ZOOM_STEP | 0.88 | Zoom per notch of a plain mouse wheel (0.88 = 12% closer); smooth-scrolling mice add up to the same per notch. | viewport/main.gd | I30 |
| ZOOM_MAX_STEPS | 3 | One scroll event never zooms more than this many notches. | viewport/main.gd | I30 |
| CLOSE_WAIT_S | 10.0 | Closing a window waits this long (seconds) for FreeCAD to save the latest revision before asking Retry / Close without saving / Cancel. | viewport/main.gd | I55 |
| OUTSIDE_SAVE_WAIT | 10.0 | FreeCAD saved the open model while Shop Sketch had actions on their way: they get this long (seconds) to land before the dialog asks Use FreeCAD's version / Keep Shop Sketch's. | viewport/main.gd | A36 |
| WATCH_S | 0.25 | How often the worker looks at each open model's file for a FreeCAD save (one stat per model); a change must hold still for one look. | worker/serve.py | A36 |
| DEADLINE | 1800 s | The job queue's dead man's switch: a job in progress with no beat (job.py command, commit, test run) for this long is reported stale to the integrator. | tools/job.py | P24 |
| HUNG_AFTER | 600 s | job.py check flags a process from the job's worktree older than this as looking hung (and it no longer counts as a beat). | tools/job.py | P24 |
| WATCH_POLL | 20 s | How often job.py watch looks at the queue, and how often take --wait looks for a job. | tools/job.py | P24, P27 |
| MAX_JOBS | 1 | Jobs one worker session takes before job.py refuses the next and it asks William for a /clear. | tools/job.py | P37 |
| WORKER_WAIT | 1200 s | How long job.py take --wait looks for a Ready job before it stops (exit 1). | tools/job.py | P27 |

## Details
