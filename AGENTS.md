# Instructions for Codex (and other agents) working on Shop Sketch

Claude also works on this repo; CLAUDE.md is its instruction file and the fullest description of how the app works.
Read it for architecture, conventions and tests.

## At the start of every session

1. Read `docs/agent-handoff.md`, the shared scratchpad between Claude and Codex. It contains open entries only;
   resolved ones are in `docs/handoff-archive.md` (read only when you need history). Look for entries marked
   "For: Codex", and for replies to your entries.
2. Check what changed since your last session: `git log --oneline -15 main`, and `git branch -a` (Claude works on
   feature branches; your work lives on `codex/*` branches).
3. Decisions: `docs/decision-log.md` is a read-only copy of William's live decision log (a claude.ai Sheet only
   Claude can reach). Active decisions win over suggestions. Search it by ID (`grep "^| I34 "`) rather than
   reading it whole. Never edit it: propose changes in the handoff, and Claude records them.

## How to work

- Work in your own git worktree, never by switching branches in /Users/Will/Sites/fretchup (Claude works in that
  checkout). Example: `git worktree add ../fretchup-codex-<job> -b codex/<job> main`.
- Touch only the files your handoff job lists. Don't merge into main or push unless William says so.
- Before handing back, run `tools/quicktest.sh` in your worktree (it uses its own ports).
- Report in the handoff: append a dated, signed response under the entry, with your branch, commit, what you
  verified and what's open. Then set its Status. Archive entries once they're resolved (move them whole to
  handoff-archive.md and leave a one-line index under "Archived").
- Behaviour choices are William's: put questions to him in the handoff, and say them in your chat with him too.

## Nothing notifies the other agent

File changes don't reach Claude by themselves. When you finish a job or leave a question, tell William in your
chat, e.g. "H006 is answered in the handoff, on branch codex/t32-units, for Claude to review", so he can pass
it on.
