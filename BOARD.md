# Work board

William says "check the board": this file tells each agent what to do next. The integrator (a Claude session in
/Users/Will/Sites/fretchup, P16) keeps it; nobody else edits it.

## If you're not the integrator

1. Read the board from main, not your worktree's copy: `git -C /Users/Will/Sites/fretchup show main:BOARD.md`.
2. Read "Notes" below for anything addressed to you (Claude or Codex) and do it.
3. Take the first job in "Jobs" that's for you, says **Ready**, and nobody has claimed. A job is claimed when a
   branch named after it exists: `git -C /Users/Will/Sites/fretchup branch -a | grep -i <id>` (e.g. h036). The
   branch is the truth even if the board still says Ready.
4. Claim it by making that branch: `git -C /Users/Will/Sites/fretchup worktree add ../fretchup-<id> -b <you>/<id>-<slug> main`
   (`<you>` is `claude` or `codex`, `<id>` lower case, e.g. `claude/h036-keys`). Then read the job's handoff file and do it.
5. When it's done (the handoff rules: tests, response, Status answered), tell William "ready for review: <ID>".
   Your result goes in your handoff response, not the Work list (P17). Don't take the integrator lock.
6. Nothing Ready for you? Say so and stop; don't start something that isn't on the board.

## If you're the integrator

You're the integrator only if William said so in this session (P16) and you hold the lock: `python3
tools/integrator.py take <your session name>` (refused if another holds it: ask William; after a context clear
he says so and you run it with `--william`, P19). Merge with `python3 tools/integrate.py <branch> --as <name>
--push` (P20). Review every
branch whose job says answered, merge what's good and push main, update the board and the Work list, then write the next jobs
so each agent has one Ready.

## Jobs

| Job | For | Status | Item | Handoff | Waits for |
|---|---|---|---|---|---|
| H041 | Codex | Answered: held for the tool registry | T81: the Circle tool (first of the new shapes, I49) | [H041](docs/handoff/H041-circle-tool.md) | |
| next | either | Queued | T79: a failed save is forgotten; shutdown waits on a saved revision | written when ready | T70 (document.gd, main.gd) |
| next | either | Queued | T66: units in the measurements box | written when ready | William: the units preference |

Done since the board started: H033 (T74 + T77), H034 (T76), H035 (T44), T56 (startup report), H036 (T75), H037 (T54), H038 (T78), H039 (T80), H040 (T33), H043 (T85), H044 (T58), H042 (T70).

## Notes

<<<<<<< HEAD
- Codex: H041 (Circle) is finished; it merges once the tool registry (on branch process-upgrade, waiting for
  William) is on main, after you move Circle onto it (a note will say how).
- Claude: nothing Ready right now; T79 (failed saves) is next once its job is written.
=======
- Codex, H041 (Circle): main now has the tool registry (A34). Merge main into your branch, then move your
  main.gd tool-list/toolbar and keys.gd edits into a `TOOL` constant in circle_tool.gd (see viewport/tools/CLAUDE.md
  "Adding a tool"), and your worker op into a `CircleActions` class in worker/circle.py (no model.py edit). Add
  Circle to the pinned lists in viewport/test_tools.gd, viewport/tests/quick/registry.gd and
  worker/scenario/99_op_registry.py. H041's Touches list says so.

- Codex: H041 (the Circle tool) is Ready. Its key is C (I50). H042 is queued behind it, so nothing overlaps H041 now. H044 (T58) is a second Codex job with no files in common with H041 or H043.
- Claude: H043 (the quick test's hide check) is Ready. H042 waits for H041: their files overlap.
>>>>>>> process-upgrade
