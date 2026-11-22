### H068 — Integrator tooling: three follow-ups from docs/follow-ups.md

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: Claude

References: P20 (integrate.py), P24 (job queue), P26 (follow-ups), T74 (placeholder IDs), T92 (log.py), H060, H063.
William chose this job, 2026-11-22: the first worker started with tools/start_worker.sh (P38), one job a session (P37).

Touches: tools/integrate.py, tools/test_integrate.py, tools/test_follow_ups.py, tools/log.py, tools/test_log.py,
docs/follow-ups.md (remove the three lines this job clears). Not tools/job.py (only if 2 can't be done without it: say
so in your response first), not ARCHITECTURE.md or docs/protocol.md (P28).

Request: fix these three, each with a named check. Nothing William would notice changes.
1. integrate.py takes an answered entry's ID from its file name's first dash (`os.path.basename(rel).split("-")[0]`,
   two places), so an entry still named `H-new-N-slug.md` at merge records its Result and follow-ups as "H"
   (number_ids runs after). Take the ID from the entry's heading, or after numbering, so H-new-N entries get their
   final number (follow-up H060).
2. When the integrator merges a scratch branch (main merged into a job branch first, then that branch integrated),
   integrate.py doesn't mark the original job merged or remove its worktree and branch. Add `--job H0NN` to say which
   job a branch delivers, or notice that the job's branch is fully merged; either is fine, say which (follow-up
   "integrator (2026-11-22)").
3. log.py add: (a) can't add a Tunables row (no kind for it); add one (name, value, what it does, where, decisions),
   following the table's columns (follow-up H063). (b) On a branch it picks the next placeholder by counting
   placeholder IDs anywhere in the text, so a placeholder already named in a doc (e.g. CLAUDE.md says "P-new-1" before
   the row exists) makes it skip to P-new-2. It should count only rows (and Details headings) that define an ID, as
   number_ids.py does; seen three times on 2026-11-22.

Run tests through `python3 tools/job.py run -- <command>` (P40). Checks: the new cases in tools/test_integrate.py /
tools/test_follow_ups.py and tools/test_log.py; quick test.
