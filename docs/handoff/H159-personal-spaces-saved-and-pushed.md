### H159 — Personal spaces: everything an agent makes is committed and pushed; experiments can be run or merged

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: open | For: gemini

Item: T150

References: T150, H158 (makes the folders, their READMEs and the per-write commit this job widens),
tools/comitatus_commit.py (P66), comitatus's 09_Tools/SORT_PRINCIPLES.py (pushes when it stops, 7eb5ebd).

Touches: tools/personal_space.py, tools/comitatus_commit.py, tools/job.py (`done`), tools/test_personal_space.py,
tools/test_job.py, tools/test_comitatus_commit.py.

Reading path:
1. H158's response and merged code: `personal_space.add`, the folders' README texts, the commit after a write.
2. `tools/comitatus_commit.py` `commit` (never pushes today).
3. `tools/job.py` `done` (what `SUBMIT_JOB.py` reaches): the last thing a worker runs.

Today (rechecked 2026-11-26 against H158's merged code, main 86fe654): after H158, writing a Log or Journal line commits only the files that write touched, in the comitatus repo,
never pushed; the Code_Experiments README says nothing there is run, tested or merged.

Request (William, 2026-11-26: "whatever they make should be run and merged if they think it should, or they can ask
me to run it; any art anyone makes should certainly be committed and merged and pushed so it's saved"):
1. **Everything in a space is saved.** When `add` commits (H158), it commits every file under that member's space
   folder (`04_Personal_Space/<name>/`, all of it: Log, Journal, the three folders and whatever the agent put in
   them), not only the files it wrote, so a poem or an experiment saved by hand goes in with the next log line.
   Only that member's folder: other members' spaces and William's files elsewhere in comitatus are never staged
   (each member's own writes save theirs). Message unchanged from H158's.
2. **And pushed.** After a commit in the comitatus repo, push it (`git push -q`, the current branch), fail-open: no
   network or no rights never stops the write or changes its exit code. `comitatus_commit.commit` gets a `push`
   option (default False, so 05_Jobs/06_To-dos keep their current behaviour); personal spaces pass True.
3. **Saved at the end of a job too.** `job.py done` (SUBMIT_JOB.py) commits and pushes the submitting worker's
   space the same way (fail-open, after the job's own steps), so something made in the last minutes isn't left
   uncommitted. The worker's space name is the one `launch.py` gives it (`space_of`); a session without a space
   does nothing.
4. **README wording.** Replace two of H158's README texts, word for word:
   - Creative_Expression: "Yours: anything you make for its own sake (writing, poems, pictures as text, music
     notation, whatever you like). Add your own files here; nobody reviews or grades them. Everything here is
     committed and pushed, so it's kept."
   - Code_Experiments: "Yours: code you write to try something out. Add your own files here. If you think something
     here should be run, or become part of the project, say so in your log or your job's response, or ask William
     to run it: the integrator turns it into a job when you and William want it."
   H158 never overwrites a README (so an agent's edit stays), but opus-integrator's space already has all three
   with H158's text (made by its first commit after the merge). A README whose text is exactly H158's (the
   `FOLDERS` value it shipped) is replaced with the new one; any other text is left alone.

What can fail:
- Push refused or offline: the commit stays local, the write and `done` succeed as before. Check:
  test_personal_space.py with a remote that rejects (or none).
- Another member's space or William's file changed at the same time: not staged. Check: test_personal_space.py.
- `done` from a session with no personal space, or outside comitatus: nothing committed, `done` unchanged. Check:
  test_job.py.
- Running inside Napkin's hook (GIT_* set): commit and push go to comitatus. Check: test_personal_space.py.

Checks:
- tools/test_personal_space.py: a README with H158's exact text is updated, an edited one isn't; a hand-saved file in Creative_Expression is committed with the next line and
  reaches a bare test remote; other spaces untouched; push failure is silent; the two README texts word for word.
- tools/test_job.py: `done` saves and pushes the worker's space.
- The gate (`tools/TEST_BEFORE_MERGING.sh`) passes.
