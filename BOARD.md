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
| H045 | Claude | **Ready** | T86: a process outlives the quick test (and linked.gd's direct menu call) | [H045](docs/handoff/H045-quick-test-leftover-process.md) | |
| H048 | Claude | **Ready** | T79: a failed save is forgotten (save stays pending, the window is told) | [H048](docs/handoff/H048-t79-failed-save.md) | |
| H047 | Codex | **Ready** | T88 stage 1: the tools' interface to Main (spec only) | [H047](docs/handoff/H047-t88-tool-interface.md) | |
| H049 | either | Queued | T90: a faster gate (measure first) | [H049](docs/handoff/H049-faster-gate.md) | H045 (quicktest.sh) |
| H046 | Codex | Queued | T82: the Line tool, closed outlines and split faces (I51) | [H046](docs/handoff/H046-t82-lines-split-faces.md) | T88 (William: interface first) |
| next | either | Queued | T79: a failed save is forgotten; shutdown waits on a saved revision | written when ready | T70 (document.gd, main.gd) |
| next | either | Queued | T66: units in the measurements box | written when ready | William: the units preference |

Done since the board started: H033 (T74 + T77), H034 (T76), H035 (T44), T56 (startup report), H036 (T75), H037 (T54), H038 (T78), H039 (T80), H040 (T33), H043 (T85), H044 (T58), H042 (T70), H041 (T81, Circle).

## Notes

- Codex: H047 (the tools' interface spec, read-only on code) is Ready. H046 (Lines) waits for T88, William's call.
- Claude: H045 is claimed; H048 (failed saves) is Ready for a second Claude session. It asks William two questions first.
