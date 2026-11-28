# P-new-1 — Jobs run strictly one at a time until William says otherwise: the hopper's pace default...

Status: Active | Subject: Process | Principles: — | Date: 2026-11-27
Replaces / replaced by: Replaces P74's 'questions don't hold the queue' (the rest of P74 stands)
Where in the code: tools/job.py board_pace, _pacing_jobs; docs/integrator.md

Jobs run strictly one at a time until William says otherwise: the hopper's pace defaults to one at a time (a board without a Pace line, or with an unknown one, is one at a time), a job waiting on a question holds the queue like one in progress, and the integrator runs no gate of its own while a job is in progress.

Why: William, 2026-11-27: parallel jobs hammer the computer and cause test failures (the 120 s viewport timeouts at load average 348); 'not forever, we'll figure that out one day, but for right now everything is sequential.'
