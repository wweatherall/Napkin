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
| H051 | Claude | **Ready** | T88 step 0: the tools' interface, foundation | [H051](docs/handoff/H051-t88-step0-foundation.md) | |
| H049 | Codex | **Ready** | T90: a faster gate (measure first) | [H049](docs/handoff/H049-faster-gate.md) | |
| H046 | Codex | Queued | T82: the Line tool, closed outlines and split faces (I51) | [H046](docs/handoff/H046-t82-lines-split-faces.md) | H051 (T88 step 0) |
| H052 | either | Queued | T66: lengths in the model's units (I57, I59) | [H052](docs/handoff/H052-t66-units.md) | T88's tool moves (every tool's vcb_value) |
| next | either | Queued | T88 steps 1-4: Paint, Select, Circle, Rectangle move to ToolContext (one job each) | written when ready | H051 |

Done since the board started: H033 (T74 + T77), H034 (T76), H035 (T44), T56 (startup report), H036 (T75), H037 (T54), H038 (T78), H039 (T80), H040 (T33), H043 (T85), H044 (T58), H042 (T70), H041 (T81, Circle), H045 (T86), H047 (T88 spec), H048 (T79).

## Notes

- Codex: H049 (a faster gate: measure first) is Ready.
- Claude: H051 (T88 step 0) is Ready. William approved the spec; Line (H046) starts after it.
