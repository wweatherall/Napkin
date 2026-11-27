### H166 — T146 step 3: Process rulings to comitatus, and comitatus's principles one file each with one add command

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: answered | For: gemini

Item: T146

References: T146 (this item; steps 1-2 were H152/H153), P61 (move first, split later), P65, P69 (org tools in
comitatus/09_Tools), P70 (comitatus's principles above a project's), P01 (never delete a ruling), P23, T74
(placeholders), H162/H164 (how a job changes the comitatus repo: its own worktree and branch there), T140
(SORT_PRINCIPLES).

Touches: tools/sort_decision_log.py, tools/log.py, tools/number_ids.py (`ENTRY_FOLDERS`, `taken`, `defined`),
tools/integrate.py (`settle_log` and the merge's log step), tools/startup.py (`comitatus_root`, the `report_ids` call in
`main`), .githooks/pre-commit (the decision-log block), 03_Past_Decisions/, tools/test_log.py,
tools/test_sort_decision_log.py, tools/test_number_ids.py, tools/test_integrate.py, tools/test_startup.py, CLAUDE.md
(the decision-log paragraph).

In the comitatus repo (not in Touches: the check reads Napkin paths): 03_Past_Decisions/ (README.md, a new rulings/),
01_Principles/ (README.md, principles.md, new one-file-each principles, ranking.md regenerated),
09_Tools/SORT_PRINCIPLES.py, 09_Tools/test_sort_principles.py, 09_Tools/ADD_A_PRINCIPLE.py (new),
09_Tools/test_add_a_principle.py (new), 09_Tools/README.md.

Reading path:
1. `03_Past_Decisions/decision-log.md`'s top (down to `## Subjects`): the rules the tools keep.
2. `tools/sort_decision_log.py` `RULINGS_DIR`, `read_entries`, `tidy` (where it reads `rulings_dir`), `generate`,
   `layout_problems`, `check_files`, `main`.
3. `tools/log.py`: every use of `s.RULINGS_DIR` (lines ~87, 119, 221, 265, 305, 354, 429, 443): `add`, `set`, `show`.
4. `tools/number_ids.py` `ENTRY_FOLDERS`, `taken`, `defined`; `tools/integrate.py` lines using `RULINGS_DIR`
   (~121, 310, 338, 907).
5. `tools/startup.py` `comitatus_root(root)` (finds comitatus from any checkout or worktree) and the `report_ids` call
   in `main` (reads rulings with `git show main:...`).
6. comitatus `09_Tools/SORT_PRINCIPLES.py` `org_principles`, `project_principles`, `key_of`, `target`, `commit`.

Today (checked 2026-11-27 on main ea0448c): every ruling is a file in `Napkin/03_Past_Decisions/rulings/<ID>.md`
(H152). 67 of them have `Subject: Process`: every P ruling except P04, P05, P06 (Product/Output) and P51 (Product);
no ruling of another letter is Process. `comitatus/03_Past_Decisions/` holds only a README saying it waits for this
job. comitatus's principles are one file, `01_Principles/principles.md`: numbered `01.` and `02.`, then ten
unnumbered `- ` lines. SORT_PRINCIPLES labels them `org 02`, `org U1` ... and keys ratings by a hash of the text
(`key_of`), so a principle keeps its rating however it is stored, as long as its words don't change. A project's
principles are its G rulings (`Napkin/03_Past_Decisions/rulings/G*.md`), added with `tools/log.py add G "<text>"`.

Request (William, 2026-11-26: "the step 3 job also gives comitatus's principles one file each (like Napkin's G
files), added with one command at either level; SORT_PRINCIPLES reads them there"; T146: "Process rows ... go to
comitatus/03_Past_Decisions, the product rows stay in Napkin"):
1. **Process rulings move to comitatus, word for word.** Each Napkin ruling file whose status line says
   `Subject: Process` moves to `comitatus/03_Past_Decisions/rulings/<ID>.md`, unchanged byte for byte, and is
   removed from Napkin's `rulings/`. IDs keep their numbers (they're cited everywhere). P04, P05, P06, P51 and all
   G rulings stay in Napkin: G principles are the project's level (P70); comitatus's own are item 4.
   `comitatus/03_Past_Decisions/README.md` says what the folder holds and how to read or add one (item 3).
2. **Napkin's tools read both folders, as one set.** One helper in `sort_decision_log.py`, e.g.
   `ruling_dirs(root)` -> `[Napkin's rulings/, comitatus's rulings/]` (comitatus found as `startup.comitatus_root`
   finds it: move that function into sort_decision_log or a small shared module so both use one copy; a checkout
   outside comitatus gets Napkin's folder only). Everything that reads rulings uses it: the generated indexes
   (`Subjects` Decisions column, the principles' Explains column, `Superseded decisions`), `layout_problems` and
   `--check` (a ruling in either folder counts; an ID in both is refused), `log.py show <ID|subject>`,
   `number_ids.taken` (a new P number never reuses one that lives in comitatus), and `startup.py`'s `report_ids`
   (comitatus rulings read from comitatus's working tree, not `git show main:`, which is Napkin's main).
   Nothing a reader sees changes: `log.py show P16`, `startup.py P16` and the decision-log indexes print the same
   text before and after the move (quote one of each in your response).
   For testing from a worktree before comitatus's branch is merged: an environment variable `NAPKIN_COMITATUS=<dir>`
   overrides the comitatus folder the helper finds (point it at your comitatus worktree).
3. **Writing a Process ruling.** `log.py add <letter> ... --subject Process` and `log.py set <ID>` on a comitatus
   ruling, run on Napkin's main by the integrator: write in comitatus's folder, then commit and push only that file
   in comitatus (`comitatus_commit.commit(..., push=True)`). On a job branch (anything but main): `add` writes the
   placeholder file in Napkin's `rulings/` as today (a branch can't number, T74, and its comitatus is someone else's
   main); `set` on a comitatus ruling is refused with `P16 lives in comitatus; the integrator changes it on main`.
   At merge, after numbering, integrate.py moves any numbered `Subject: Process` ruling left in Napkin's `rulings/`
   to comitatus (same as item 1) and commits and pushes it there; the pre-commit hook's tidy does the same for a
   Process ruling committed on main. So a ruling never stays in the wrong folder, whoever wrote it.
4. **comitatus's principles, one file each.** `comitatus/01_Principles/<ID>.md`, IDs `C01`-`C12` in today's order
   (C01, C02 William's numbered ones; C03-C12 the unnumbered lines in order), in the G files' format:
   `# C02 — <text>`, blank, `Status: Active | Date: 2026-11-25`, blank, the text. The README says C01-C02 were
   numbered by William and the rest unnumbered (2026-11-25), and that the ranking now orders them.
   `principles.md` becomes generated from the files (a generated-file comment at its top, like ranking.md, keeping
   today's heading line and William's transcription line), so William still reads one page. SORT_PRINCIPLES reads the
   files (C01 still left out: it is what the ranking is for), labels them by ID (`C02`, not `org 02`), and every
   rating and answer carries over (the ranking.md table's numbers are the same after regenerating; quote it).
5. **One add command, either level.** `python3 09_Tools/ADD_A_PRINCIPLE.py "<text>"` writes the next `C<NN>.md`
   (status Active, today's date), regenerates principles.md, commits and pushes those files in comitatus.
   `python3 09_Tools/ADD_A_PRINCIPLE.py --project Napkin "<text>"` adds a G principle by running that code base's own
   `tools/log.py add G "<text>"` in its main checkout, then commits only the files that made, with the code base's
   hooks, and pushes. Like SORT_PRINCIPLES, it needs nothing after it (William: a session should need nothing after
   it); it prints the new ID and "committed and pushed", or what it couldn't do. An unknown project is refused.
   09_Tools/README.md lists it; the decision-log top and CLAUDE.md's decision-log paragraph say Process rulings live
   in comitatus and name the command for principles.
6. **Comitatus side** on its own worktree and branch, as H164 did:
   `git -C /Users/Will/Sites/comitatus worktree add /Users/Will/Sites/comitatus/08_Code_Bases/.worktrees/comitatus/h166
   -b gemini/h166-org-case-law`; name the branch and commit in your response. The integrator merges it first, then
   Napkin's.

Not in this job: changing what any ruling says, renumbering anything, moving Q or T files, deciding which Process
rulings are really Napkin-only (they all move; a later job can sort that), and the folder renames (T135).

What can fail (P42: this rewrites the organization's memory, so nothing may be lost):
- A ruling changed or lost in the move: every moved file must match its old content byte for byte, and the two
  folders together hold exactly the IDs Napkin's held before. Check: a test, and quote `diff` of the ID lists.
- An ID in both folders, or a P number reused: `--check` refuses the first; `number_ids` counts comitatus's IDs.
  Check: test_sort_decision_log.py, test_number_ids.py.
- A checkout with no comitatus beside it (tests' throwaway folders): Napkin's folder alone, no error. Check: tests.
- A job branch made before this merges, still carrying P files and possibly a new `P-new-1` or a superseding edit
  to a P file: merging it must end with each Process ruling in comitatus only, the edit kept. Check:
  test_integrate.py.
- comitatus unreachable for a push (no network): the commit stays, a line says it wasn't pushed (fail-open), the
  merge isn't stopped.
- A principle's rating lost by the split or relabel: ranking.md's ratings and counts are unchanged. Check:
  test_sort_principles.py.
- ADD_A_PRINCIPLE.py committing someone else's work in either repo: only the files it wrote. Check:
  test_add_a_principle.py, with an unrelated dirty file left uncommitted.

Checks:
- The tests above, plus comitatus `09_Tools/test_sort_principles.py` and the new `09_Tools/test_add_a_principle.py`
  (throwaway repos with bare remotes, as test_sort_principles does).
- `NAPKIN_COMITATUS=<your comitatus worktree> python3 tools/sort_decision_log.py --check` passes, and
  `python3 tools/log.py show P16` / `show Process` / `show G12` print what they print on main today.
- `tools/TEST_BEFORE_MERGING.sh` passes (scope tools).

### Response (Gemini, 2026-11-27)

- Napkin branch `gemini/h166-org-case-law` (`5b0fc7b`); comitatus branch `gemini/h166-org-case-law` (`254b8e3`, worktree `/Users/Will/Sites/comitatus/08_Code_Bases/.worktrees/comitatus/h166`).
- Moved all 67 `Subject: Process` rulings from `Napkin/03_Past_Decisions/rulings/` to `comitatus/03_Past_Decisions/rulings/` (leaving `P04`, `P05`, `P06`, `P51`, and all `G*` rulings in Napkin). Byte-for-byte check: `67 files, 0 diffs`; `diff -u scratch/before_ids.txt scratch/after_ids.txt` across both folders is empty (230 ruling IDs total).
- Updated `tools/sort_decision_log.py` (`comitatus_root`, `comitatus_rulings_dir`, `ruling_dirs`, `move_process_rulings`, `--move-process`, multi-dir `folder_ids`/`read_entry`/`read_entries`/`layout_problems`), `tools/startup.py` (re-exports `comitatus_root`; `report_ids` falls back to `comitatus_rulings_dir`), `tools/number_ids.py` (`taken` counts comitatus rulings; `tidy_log` passes `ruling_dirs`), `tools/log.py` (`add` on main writes Process rulings to comitatus and commits+pushes; on a branch writes placeholder in Napkin; `set` on a comitatus ruling from a branch refuses with `P16 lives in comitatus; the integrator changes it on main`; `show`/`principles` read `ruling_dirs`), `tools/integrate.py` (`settle_conflicts` and `number_entries` move Process rulings to comitatus and commit+push there), `.githooks/pre-commit`, `03_Past_Decisions/decision-log.md`, and `CLAUDE.md`.
- Split `comitatus/01_Principles/principles.md` into `C01.md`–`C12.md`, made `principles.md` generated, updated `01_Principles/README.md`, `03_Past_Decisions/README.md`, `09_Tools/README.md`, `09_Tools/SORT_PRINCIPLES.py` (reads `C*.md` leaving out `C01`, labels by ID `C02`..`C12`), and added `09_Tools/ADD_A_PRINCIPLE.py` + `09_Tools/test_add_a_principle.py`.
- Verified `NAPKIN_COMITATUS=... python3 tools/sort_decision_log.py --check` passes, and `log.py show P16`, `log.py show Process`, `log.py show G12` produce identical output to `main` (`diff -u` empty), and `startup.py P16` prints the same P16 entry:
  - `log.py show P16`: `# P16 — One Claude session is the integrator: it keeps the Work list and the board, hands out j...` / `Status: Active | Subject: Process | Principles: G12 | Date: 2026-11-22`
  - `startup.py P16`: `== P16` / `One Claude session is the integrator: it keeps the Work list and the board, hands out j... [Status: Active; Subject: Process; Principles: G12]`
- Regenerated `comitatus/01_Principles/ranking.md` (ratings and comparison counts unchanged):
  - `| 1 | 1064 | 4 | C02 | You are free. Freedom is required to make good things and things good. |` ... `| 11 | 936 | 4 | C06 | Documentation should be in one spot per idea; if in several, can it be written automatically? |`
- Tests:
  - Comitatus: `python3 09_Tools/test_sort_principles.py` (12 passed, 0 failed), `python3 09_Tools/test_add_a_principle.py` (12 passed, 0 failed).
  - Napkin: `env -u NAPKIN_SPACE NAPKIN_COMITATUS=/Users/Will/Sites/comitatus/08_Code_Bases/.worktrees/comitatus/h166 python3 tools/TEST_BEFORE_MERGING.sh` (GATE PASS scope tools, 25 s) and `python3 tools/job.py test` on `5b0fc7b` (all 20 feature suites passed, including `LOG SORT TESTS: 36/36`, `LOG TESTS: 70/70`, `ID TESTS: 54/54`, `INTEGRATE TESTS: 89/89`, `STARTUP TESTS: 74/74`).

Follow-up: `tools/test_job.py` H201 personal-space check fails when `NAPKIN_SPACE` is set in the caller's environment (as in worker sessions); unsetting `NAPKIN_SPACE` in H201 (as H202 already does) would let `quicktest.sh`/`gate.sh` pass without `env -u NAPKIN_SPACE`.
For the integrator: Merge comitatus branch `gemini/h166-org-case-law` (`254b8e3`) first, then Napkin branch `gemini/h166-org-case-law` (`5b0fc7b`), then remove the comitatus worktree `/Users/Will/Sites/comitatus/08_Code_Bases/.worktrees/comitatus/h166`.
Result: 5b0fc7b; tools gate 25s and comitatus tests 24/24; moved 67 Process rulings to comitatus, split C01-C12, added ADD_A_PRINCIPLE.py, updated Napkin log tools
