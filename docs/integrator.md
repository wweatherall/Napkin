# The integrator

What only the integrator does. Workers (every other session, Claude or Codex) don't need this page: CLAUDE.md
and BOARD.md are theirs. The shared rules are in BOARD.md's worker steps (Touches, placeholder IDs,
Architecture: lines, the response) and CLAUDE.md (commit trailers); this page says what the integrator does with them.

## The role and the lock
- One Claude session is the integrator (P16), and it holds the lock (`python3 tools/integrator.py status`, P19).
  You're the integrator only if William said so in this session: `python3 tools/integrator.py take <your session
  name>` (refused if another holds it: ask William; after a context clear he says so and you run it with
  `--william`, P19).
- It keeps BOARD.md (nobody else edits it), assigns jobs, reviews, merges into main when it judges a branch good
  enough (review done, full test passes) and pushes main after merging (P16). Other sessions never merge or push.

## The queue watch
- No timed check-ins (P39): run `python3 -u tools/job.py watch --next` with Bash `run_in_background` (not a
  Monitor: it expires every 30 min, and each wake re-reads the whole context); it wakes you
  once on the first new event (a job done, a job stale: its deadline passed, check its branch and worktree; a
  worker waiting on William; a job returned; the queue empty while a worker waits on `take --wait`: check in with William). Start
  it again after each. After a context clear, re-arm it.
- `python3 tools/job.py status` shows the queue; `python3 tools/job.py board` rebuilds the board's job table (the
  commit hook does it on main).

## Review and merge
- Review every done job (Codex's `codex/*` branches too). Read each `Changed from the brief:` line first (P44):
  accept it, or return the job; one that changes what William would notice goes to him (`integrate.py` also stops
  with the merge staged when any response has one, prints them under "for you now:", and records them in the merge
  commit on `--continue`; `--yes` doesn't skip this stop). For a brief with a "What can fail" section, check that each case
  listed there has its named check, and that the check fails without the change where it can (P42). Merge what's good with
  `python3 tools/integrate.py <branch> --as <name> --push` (P20). It runs the gate, `tools/gate.sh` (P18); flags
  files the branch changed outside its job's Touches list; renumbers a PROTOCOL_VERSION bump on top if main moved
  on meanwhile (A35); removes the job's worktree and branch and marks it merged; with --push it stops before
  pushing for you to look (`--yes` goes on).
- Put one that fails review or the gate back with `python3 tools/job.py return <id> "<notes>"`; hand a job to another agent (moving its worktree into `<checkout>-jobs/` if needed) with `python3 tools/job.py reassign <id> --to claude|codex|gemini ["<notes>"]`.
- Placeholder IDs (T74): integrate.py runs `tools/number_ids.py` at merge, giving each I-new-N, T-new-N, H-new-N
  the next free number. It numbers only placeholders that are IDs (a log row, a handoff entry's file or heading, and
  references to them); any other is left and reported as "not numbered: <file>:<line>" (H073). Jobs you write on
  main get numbers the same way: run `python3 tools/number_ids.py`
  (`--dry-run` to look first) before committing.
- Codex records William's decisions in the log itself (P09, AGENTS.md). When integrating its branch, carry over
  only the rows it added or superseded: its copy of the rest may be older than main's.
- Results (T91, P17): integrate.py commits each response's `Result:` line to its Work list row and prints one short line per item plus the commit's oneline; a response without
  one is yours to record. Follow-ups (P26): it copies `Follow-up:` lines into docs/follow-ups.md and prints
  `For the integrator:` lines under "for you now:"; clear a follow-up in the commit that does it.
- Small fixes (P22): merge and push the standing `small-fixes` (and `codex/small-fixes`) branch when the gate
  passes, without asking; list the fixes for William at the end of the session.

## The map (P28)
- `ARCHITECTURE.md` and `docs/protocol.md` are yours. A job with `Architecture:` lines stops at merge with the
  merge staged and prints them: write them in (the reviewer checks prose against code), then
  `integrate.py --continue --as <name> --push`.
- On main the map changes in the same commit as the code. The PR check (`tools/check_architecture.py --range`,
  read as a branch) is an additional omission detector, not a replacement for review.

## Writing jobs
- Write the next jobs as handoff entries (a Status of open is Ready; "queued (after H0NN)" waits), each with its
  Touches list, and keep the board's Order line. Before marking one Ready, compare its Touches with every Ready or
  claimed job's: two whose lists overlap don't run at once (tell William before starting one that does). A
  shared file named with backticked functions after it (`viewport/main.gd (`redo`)`) overlaps only where the
  names meet (P45; the tools check it once T112 is built, until then compare by eye).
- A job meant to share files with another (a trial that merges that job's branch first, like H098 on H093) says
  `| Builds on: H0NN` in its Author line: the queue then doesn't hold it back for that overlap.
- The shared hot spots (the decision log's Work list, the handoff, viewport/main.gd, the map) stay small edits
  made once the work is done.
- A job touching saving, reloading or the worker link gets a "What can fail" section in its brief (P42; the
  entry template has it): you write it, from reading the code, since you aren't the builder.
- A brief that has the worker clear a follow-up lists docs/follow-ups.md on its Touches and asks for it in the
  code commit, before the quick test: `job.py done` reuses a pass only across commits that change the handoff
  (H091's worker found "in your last commit" clashed with both).
- Every rule in a brief says what it's for, in a clause: the invariant it keeps or the case it prevents (P44).
  Before writing a rule that sets one value of a linked pair or group (two angles, a range, a count and its
  list), check the state it leaves the others in. The worker may depart from a rule whose letter defeats its
  purpose, with a `Changed from the brief:` line.
- When a job's blocker merges, recheck its brief against the code before opening it: the blocker may have
  rewritten what the brief describes (H094 and H108 both needed updating after H093). Re-date its "Today", fix what
  moved, and add the blocker's new names to its Touches.
- Make a brief exact: its scope, the exact wording of any message, the cases that must still work (H076 is the
  model; workers said its precision let them build it without guessing). Check every claim it makes about how
  the code works today against the code before marking it Ready: H077's brief stated an order of steps opposite
  to integrate.py's, and the worker had to choose between "no change in behaviour" and the brief.
- A brief whose job has a tricky part gets a `Reading path:` line: the functions to read, in order, to see the
  whole lifetime of what the job moves, and who owns what (T107, dropped in favour of this; H083 is the model).

## Traps seen at merge
- A paused merge (`--continue`) accepts changes only to ARCHITECTURE.md and docs/protocol.md. Folder-guide
  updates a response asks for go in a commit of their own after the merge.
- A branch started from an older main that touches files main changed since: merge main into it in a scratch
  worktree first and integrate that.
- Two jobs that each bump PROTOCOL_VERSION to the same number merge silently: bump the later one by one (A35).
- A merge that brings a new version of a tool integrate.py imports (number_ids, job) runs the old one for that
  merge: check its effect.
- `job.py take` with no job id takes the next Ready job for this session: an integrator never runs it.

