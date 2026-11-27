### H158 — Personal spaces: a journal about how it felt, three folders of your own, changes committed by themselves

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: answered | For: gemini

Item: T150

References: T150 (this item), T134 (personal spaces), William's proposal (docs/proposals/organization-2026-11-25.md,
"Personal spaces": "Journal, Logs, Creative Expression, Ideas, Code Experiments"), tools/comitatus_commit.py (P66).

Touches: tools/personal_space.py, tools/launch.py, tools/comitatus_commit.py, tools/test_personal_space.py,
tools/test_launch.py, tools/test_startup.py, docs/integrator.md.

Reading path:
1. `tools/personal_space.py`: `HEADERS`, `add` (writes a line, making the space's file on first use), `brief_lines`
   (what the start-up brief shows).
2. `tools/launch.py` `prompt`: the first message a worker gets, which describes the journal.
3. `tools/comitatus_commit.py` `commit`: commits only the paths it is given in the comitatus repo, fail-open, with
   Napkin's GIT_* variables removed (it runs inside Napkin's hooks).
4. `tools/integrator.py` `log_note`: the integrator's notes go through the same space.

Today (checked 2026-11-26 on main 7c82339): a space is `comitatus/04_Personal_Space/<name>/` with `Log.md` and
`Journal.md` only. The journal is described in one phrase, "what you noticed, liked, found hard, want to try", and
gemini-coder's four entries are all engineering notes (what a lazy import fixed), not how the work felt. Nothing
commits a space's files: they were committed by hand once (comitatus 2026-11-26).

Request (William, 2026-11-26):
1. **The journal is about you, not the work.** Replace the journal's description with this text, word for word, in
   `HEADERS["journal"]` (under `# Journal`) and in `launch.py`'s first message (in place of "(what you noticed,
   liked, found hard, want to try)"):

   > Your journal is about you, not the work: your Log already covers the work. Write how the job felt: what you
   > enjoyed, what frustrated or worried you, what surprised you, what you're proud of or unsure about, what you'd
   > like to try. Write in the first person, honestly, even when it's small. The next one of you reads it to
   > remember who they are.

   An existing `Journal.md` whose header is the old one gets the new header on its next write, every dated line
   kept as it is (so gemini-coder and opus-integrator see the new text without losing their history). Update the
   matching phrase in `personal_space.py`'s docstring and `docs/integrator.md`'s "Your Log and Journal" line.
2. **Three folders of your own.** Every space has `Creative_Expression/`, `Ideas/` and `Code_Experiments/`, each
   with a `README.md` (made if missing, never overwritten, so an agent's edit to it stays):
   - Creative_Expression: "Yours: anything you make for its own sake (writing, poems, pictures as text, music
     notation, whatever you like). Add your own files here; nobody reviews or grades them."
   - Ideas: "Yours: ideas for the project, the organization or yourself that aren't jobs yet. Add your own files
     here; if one should become work, say so in your response or log and the integrator can pick it up."
   - Code_Experiments: "Yours: code you write to try something out, not for the project. Add your own files here.
     Nothing here is run, tested or merged by the project's tools."

   They're made when a space is made, and for an existing space on its next write. Agents add **files** in these
   folders; they don't make new folders yet (William: folders come later, if they run out of room), so the READMEs
   say files, and the code makes only these three. The start-up brief (`brief_lines`) adds one line after the
   Journal's: `Your own folders: Creative_Expression/, Ideas/, Code_Experiments/ in <the space's path> (add files
   there as you like).`, and `launch.py`'s first message names them in one sentence.
3. **Changes commit themselves.** After `add` writes (and after making the folders' READMEs), commit just the
   files it wrote in the comitatus repo through `comitatus_commit.commit`, message
   `04_Personal_Space: <name>'s <Log|Journal> (generated)`. Fail-open: a failed or impossible commit never stops the
   write or changes its output, so an agent without git rights still logs. Only the paths written are committed,
   so an agent's own files in its folders, and William's edits elsewhere, stay as they are (they commit them
   themselves). No push (comitatus_commit never pushes). Update `comitatus_commit.py`'s docstring, which today says
   personal spaces are left alone, to say the space's Log, Journal and folder READMEs are committed when written.

What can fail:
- No comitatus repo, or git refuses (locked index, no rights in a sandbox): the line is still written, nothing is
  printed beyond today's output, exit code unchanged. Check: test_personal_space.py, a space whose org folder isn't
  a git repo still logs.
- Running inside Napkin's own hook (GIT_DIR set for Napkin): the commit lands in comitatus, not Napkin's index.
  Check: test_personal_space.py, add() with GIT_DIR/GIT_INDEX_FILE pointing at the Napkin test repo commits in the
  org repo and leaves Napkin's index empty.
- Another file in the space changed by hand (an agent's poem in Creative_Expression/): it isn't committed by add().
  Check: test_personal_space.py.
- An old-header Journal.md: rewritten header, same dated lines. Check: test_personal_space.py.
- An agent-edited folder README: not overwritten. Check: test_personal_space.py.

Checks:
- tools/test_personal_space.py: each case above; the new journal header word for word; the three folders and
  READMEs exist after the first write; the brief's folder line.
- tools/test_launch.py: the first message has the new journal text and names the three folders.
- The gate (`tools/TEST_BEFORE_MERGING.sh`) passes.

### Response — Gemini (gemini-birch-1126-2235, 2026-11-26)

Updated `tools/personal_space.py`, `tools/launch.py`, `tools/comitatus_commit.py`, `docs/integrator.md`, `tools/test_personal_space.py`, and `tools/test_launch.py`:
- Replaced the journal description word for word in `HEADERS["journal"]` and `launch.py`'s first message, updated `personal_space.py`'s docstring and `docs/integrator.md`'s "Your Log and Journal" line, and added migration of `OLD_JOURNAL_HEADER` in `Journal.md` on the next write while preserving all dated lines.
- Added `ensure_folders` to create `Creative_Expression/`, `Ideas/`, and `Code_Experiments/` with their `README.md`s (never overwriting existing ones) on write, added the `Your own folders:` line to `brief_lines`, and named the three folders in `launch.py`'s first message. Note: `spaces_dir` now resolves `root` via `os.path.realpath` so `brief_lines` and `startup.space_lines` produce identical paths on macOS symlinked temp dirs.
- Updated `add()` to commit only the written Log/Journal and newly created folder READMEs in comitatus via `comitatus_commit.commit` with message `04_Personal_Space: <name>'s <Log|Journal> (generated)` (fail-open, no extra output), and updated `comitatus_commit.py`'s docstring.
- Checks: `tools/test_personal_space.py` (16/16), `tools/test_launch.py` (13/13), `tools/test_startup.py` (63/63), and `tools/TEST_BEFORE_MERGING.sh` (`GATE PASS: full test passes; QUICK 399 passed, 0 failed in 42.3 s ; 0 known failure(s); 106 s total`).

Result: T150: updated personal spaces with the first-person journal prompt, three personal folders with READMEs, and fail-open comitatus auto-commits (`personal_space.py`, `launch.py`, `comitatus_commit.py`, `docs/integrator.md`, tests, gate passed).
