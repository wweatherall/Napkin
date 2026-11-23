### H099 — Job worktrees live in one folder, `<checkout>-jobs/<id>`, so a sandbox can trust just that folder

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: gemini

References: Gemini's feedback, 2026-11-22: each job's worktree is a sibling folder (`/Users/Will/Sites/fretchup-h090`),
outside the main checkout, so its sandbox blocked every command there; William had to give it access outside its
workspace and trust all of ~/Sites. P24 / T102 (the wrong-checkout guard), P25 (scratch/ inside the worktree),
P37.

Touches: tools/job.py (`worktree_for` and the usage text at the top), tools/test_job.py, BOARD.md's worker
steps (only the path in its "If you're not the integrator" paragraph: the integrator normally owns BOARD.md, and
allows this one line). Not integrate.py (it removes the worktree that job.py recorded), not startup.py (it lists
whatever `git worktree list` says), not the standing small-fixes worktree (it stays where it is), not
AGENTS.md / GEMINI.md / CLAUDE.md (they don't name the path; say so if you find one that does).

Today (checked 2026-11-22): `job.py worktree_for(root, jid)` returns
`os.path.join(os.path.dirname(root), f"{os.path.basename(root)}-{jid.lower()}")`, a sibling of the main checkout
(`/Users/Will/Sites/fretchup-h090`). `take` records it in the queue state (`worktree`); a job taken again
(returned, or resumed) uses the recorded path (`prev.get("worktree") or worktree_for(...)`). BOARD.md tells
workers to run `cd /Users/Will/Sites/fretchup-<id> && ...`. The usage text says `makes ../fretchup-<id>`.

Request:
1. `worktree_for(root, jid)` returns `<dirname(root)>/<basename(root)>-jobs/<id lowercase>`
   (`/Users/Will/Sites/fretchup-jobs/h099`). `take` makes the `-jobs` folder if it isn't there. A job whose state
   already records a worktree (H083 today, at `/Users/Will/Sites/fretchup-h083`) keeps it: nothing moves.
2. The usage text and BOARD.md's path line say the new place: `cd /Users/Will/Sites/fretchup-jobs/<id> && ...`.
3. Nothing else changes: branch names, the scratch folder inside the worktree, the wrong-checkout guard
   (quicktest.sh / gate.sh read the recorded worktree: check they don't build the path themselves, and say so).

What can fail (P42: this touches where a job's files live):
- The `-jobs` folder missing: `take` makes it (check: a fresh fixture repo with no `-jobs` folder; `take` works).
- A job taken before this change (its state records the old sibling path): `take` of it again, `done`, `test`
  and `merged` use the recorded path, not the new one (check: a fixture state with an old-style `worktree`).
- The `-jobs` folder left empty after the last job merges: it stays (harmless); `merged` removes only the job's
  own worktree (check: after `merged`, the folder exists and holds nothing of that job).

Cases that must still work: every check in tools/test_job.py and tools/test_integrate.py; the worktree tests
there that call `job.worktree_for` (they follow the function, so they should pass unchanged: say if one needed
editing).

Checks (tools/test_job.py): `worktree_for(root, "H001")` is `<dirname(root)>/<basename(root)>-jobs/h001`; the
three "What can fail" checks above.

For William, after the merge (put it as a "For the integrator:" line too): Gemini's sandbox can then trust only
`/Users/Will/Sites/fretchup` and `/Users/Will/Sites/fretchup-jobs`, with `allowNonWorkspaceAccess` off, in
`~/.gemini/antigravity-cli/settings.json`. Don't edit that file yourself.

Reading path: job.py `worktree_for` → `take` (where the worktree is made and recorded; the `prev` branch for a
job taken again) → `with_job` / `test` / `done` (how the worktree is found from the state) → `merged` (what's
removed) → tools/test_job.py's fixtures (`repo()`, the worktree checks). Who owns what: job.py makes, records and
removes job worktrees; integrate.py and the test scripts only use the recorded path.

Run `python3 tools/test_job.py` and `python3 tools/test_integrate.py` while building, then
`python3 tools/job.py test`. End your response with a Result line; leftovers as Follow-up lines; anything for
the merge as For the integrator lines.
