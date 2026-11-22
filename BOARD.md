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
6. Nothing Ready for you? Say so and stop; don't start something that isn't on the board.

## If you're the integrator

You're the integrator only if William said so in this session (P16); a fresh session is a worker. Review every
branch whose job says answered, merge what's good and push main, update the board and the Work list, then write the next jobs
so each agent has one Ready.

## Jobs

| Job | For | Status | Item | Handoff | Waits for |
|---|---|---|---|---|---|
| H039 | Claude | **Ready** | T80: make the full test reliable (the merge gate) | [H039](docs/handoff/H039-t80-flaky-full-test.md) | |
| H038 | Codex | **Ready** | T78: a drawing request during a sync is lost (viewport/document.gd) | [H038](docs/handoff/H038-t78-drawing-request-lost-during-sync.md) | |
| H040 | Codex | **Ready** | T33: small distances: typed values of any size get through | [H040](docs/handoff/H040-t33-small-distances.md) | |
| H041 | either | Queued | T81: the Circle tool (first of the new shapes, I49) | [H041](docs/handoff/H041-circle-tool.md) | H040 (push_tool.gd, worker/push.py) |
| next | Claude | Queued | T70: a late worker reply can't replace a newer state (incl. stale open replies) | written when ready | H038 (document.gd) |
| next | either | Queued | T79: a failed save is forgotten; shutdown waits on a saved revision | written when ready | H038 (document.gd) |
| next | either | Queued | T66: units in the measurements box | written when ready | William: the units preference |

Done since the board started: H033 (T74 + T77), H034 (T76), H035 (T44), T56 (startup report), H036 (T75), H037 (T54).

## Notes

- Codex: two jobs are Ready (H038, H040); they touch different files, so two Codex sessions can take one each.
