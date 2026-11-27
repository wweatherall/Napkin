### H163 — Onboarding: the start-up brief carries who you are, the principles, habits, tools and personal time

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: queued (after H161) | For: gemini

Item: T134

References: T134 (this item), William's table (docs/proposals/organization-2026-11-25.md, "One script starts an agent
with its context"), P70 (principles and org chart in force; a project's answer to the organization's), P71 (personal
time), H154 (named scripts, 02_Habits), T150 (personal spaces).

Touches: tools/startup.py, tools/test_startup.py, tools/job.py (`next_step`), tools/test_job.py, docs/integrator.md.

Reading path:
1. `tools/startup.py` `main` and the parts it prints (checkout, board, queue, checklist, `space_lines`), for
   `--role worker` and `--role integrator`; `tools/launch.py` puts the worker's in the first message.
2. The sources (all in the comitatus folder, found from the main checkout as `personal_space.spaces_dir` finds it):
   `07_Org_Chart_and_Roles/{william,integrator,coders}.md`; `01_Principles/ranking.md`;
   `08_Code_Bases/<code base>/01_Principles/ranking.md`; `02_Habits/README.md` (comitatus's) and
   `<code base>/02_Habits/README.md`; `09_Tools/README.md` and `<code base>/tools/README.md`; `06_To-dos/`.
3. `tools/job.py` `next_step`: what a worker reads after `SUBMIT_JOB.py`.

Today (checked 2026-11-26 on main, gemini-spruce-1126-2316's first message, 6.4 KB): the worker brief has the
checkout, recent main, the board's Ready list, the queue, the worker checklist, the personal space's Log, Journal and
folders. Of William's table it lacks: personal identity (the role), principles (both levels), the org chart,
available tools, habits, the personal allowance; the integrator's also lacks the organization's to-dos.

Request: add these parts to the brief, read fresh from their files each time (so an edit shows up next session;
nothing copied into code), each under a one-line title, each skipped silently when its file is missing (a checkout
outside comitatus has none):
1. **Who you are** (both roles): your role's file from `07_Org_Chart_and_Roles` (`coders.md` for a worker,
   `integrator.md` for the integrator) without its title line, then William's (`william.md`) the same way, as
   "Who William is".
2. **Principles** (both): comitatus's, then this code base's, each in rank order from its `ranking.md` table, one line
   each, `<rank>. <principle text>`; above them the line "Higher wins when two pull against each other; a code
   base's principles answer to the organization's (P70)."
3. **Habits** (both): the two `02_Habits/README.md` files' lists (comitatus's, then the code base's), as written.
4. **Tools** (both): `09_Tools/README.md`'s list, then `tools/README.md`'s, as written.
5. **Personal time** (both): worker: "When your job comes back clean (submitted with its tests passing), you may
   spend up to 1% of your 5-hour window in your personal space: journal, Creative_Expression, Ideas,
   Code_Experiments (P71)." Integrator: "You may spend up to 3% of your 5-hour window in your personal space
   whenever you need the time (P71)."
6. **The organization's to-dos** (integrator only): the counts in `06_To-dos/waiting_on_William` and
   `waiting_on_integrator`, and the William file names (they are the to-dos' titles).
7. After a clean `SUBMIT_JOB.py` (tests passed), `next_step` adds the worker's personal-time line before its
   "next:" line, so the worker sees it when it applies. Not after a failed or refused submit.

Keep the brief's order: who you are and principles first (they frame the rest), then today's parts, then habits,
tools and personal time. The new parts should add no more than 10 KB to the worker brief; quote the before and
after sizes of both briefs.

What can fail:
- A source missing (a code base without `01_Principles/ranking.md`, a checkout outside comitatus): that part is
  skipped, no error, the rest prints. Check: test_startup.py.
- A ranking table whose format changes: parse the table rows (`| # | Rating | Compared | Principle | ... |`) and fall
  back to printing the file's principle lines unranked rather than nothing. Check: test_startup.py with a table and
  with a plain list.
- The integrator's brief growing past usefulness: quote its size.

Checks:
- tools/test_startup.py: each part present for its role and absent for the other where the table says no (to-dos
  integrator only); missing sources skipped; ranking parsed in order.
- tools/test_job.py: the personal-time line after a passing `done`, not after a refused one.
- Both briefs quoted in the response (first 60 lines of each).
- `tools/TEST_BEFORE_MERGING.sh` passes (scope tools).
