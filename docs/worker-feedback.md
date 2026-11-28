# Worker feedback

<!-- Recorded by tools/SUBMIT_JOB.py (job.py done). Kept here in full; unread entries appear in the integrator brief. -->

### 2026-11-27 23:23 — H207 (gemini, d07712e4-62f9-467d-a903-9ede5a75b5cc, first submit)
- **How was working on this job in our code base?** Very smooth: the tools/ code is clean, well-factored, and easy to test in isolation with temp git repos and mocked osascript.
- **Any improvements you can think of?** Having tools/handoff.py default to list (or printing a brief one-line usage hint) would save a small round-trip, and letting gate.sh (scope tools) record a tools-scope pass for tools-only jobs would avoid re-running the 36s quick test in SUBMIT_JOB.py.

### 2026-11-27 23:34 — H200 (gemini, 236ebfeb-ace3-4c5e-9c5b-95edf4074893, first submit)
- **How was working on this job in our code base?** The H200 brief was clear and well-scoped, with helpful references to H198/H199 and T159-push-pull.md.
- **Any improvements you can think of?** Listing viewport/document.gd counters and _op_touches or viewport/tests/quick/press.gd in Touches (or noting that new op prefixes require a counters entry in document.gd) would make future op splits even smoother.

### 2026-11-28 00:03 — H201 (gemini, 49f09db2-dcaa-41ac-bfb2-1f0d654f6f45, first submit)
- **How was working on this job in our code base?** Reading docs/proposals/T161-fit-faces.md and I75-I77 upfront made the geometry-only fit model and pause/detach rules crystal clear. Note that tests/op_contracts.json needed no changes since fit has no CONTRACT yet, while viewport/property_panel.gd, viewport/tests/quick/properties.gd, and scenario 97/98/99 needed mechanical P73 updates.
- **Any improvements you can think of?** RECORD_A_DECISION.py could forward 'add tunable' arguments directly to tools/log.py instead of printing usage.

### 2026-11-28 02:15 — H201 (codex, 01a2210d-f942-7420-9648-4a5151725b4e, resubmit)
- **How was the review round: were the return notes clear, and what would have avoided the return?** The return notes were clear and their exact FreeCAD reproduction made verification easy. A resize-after-pocket case in the original matrix would have caught the detach. The review also exposed the first resize after reopen and a cut after rotation as useful regressions.
- **Any improvements you can think of?** Keep GATE_FULL out of the nested tools-scope fixture so an explicitly forced full gate can pass the same checks as an automatically selected full gate.

### 2026-11-28 07:56 — H211 (codex, 01a22258-3cfc-7fa2-8c49-9f4489f9d04a, first submit)
- **How was working on this job in our code base?** The saved model and explicit checks made the bug easy to reproduce. GET_A_JOB claimed H211 on top of H201 before the H211 brief existed on that branch, then failed trying to print it. Merging main into the H211 worktree restored the brief.
- **Any improvements you can think of?** When taking a stacked job, ensure its current brief is present before printing it. In the hopper redraw test, use an isolated queue fixture so another worker writing to the live queue cannot make the merge gate fail.
### 2026-11-28 08:12 — H210 (codex, 01a22279-cf6b-7661-aa86-11c57842643c, first submit)
- **How was working on this job in our code base?** A shifted punctuation key needed both its character and its modifier events to reproduce the app failure.
- **Any improvements you can think of?** For keyboard bugs, include physical modifier events in the baseline and check active and post-click paths separately.
### 2026-11-28 08:05 — H209 (codex, 01a22273-35ee-79f0-ac09-adb534271f8e, first submit)
- **How was working on this job in our code base?** The existing registry check exercised the actual toolbar. Adding a width check made the first layout failure as easy to measure as it was to see in the capture.
- **Any improvements you can think of?** The merge gate already records a clean quick-test pass. The worker checklist could accept that pass in place of asking for a second quick run on the same commit.
### 2026-11-28 08:34 — H202 (codex, 01a22280-8112-77d1-825e-f1ba4a0a07de, first submit)
- **How was working on this job in our code base?** The existing stock and line helpers gave the standalone demo the same visual language as the viewport. The design brief made the comparison easy to verify.
- **Any improvements you can think of?** Consider a gate scope for standalone demos that combines the tools gate with headless scene loads. Adding demo source currently triggers app checks in the ordinary scope resolver.
### 2026-11-28 07:58 — H208 (codex, 01a22259-fffe-7730-ae03-79149a9938c1, first submit)
- **How was working on this job in our code base?** The shared worker test helper covered several direct FreeCAD launches. The floor-copy check exposed an implicit dependency on the desktop backup preference once the suite ran with clean configs.
- **Any improvements you can think of?** Keep test subprocesses behind their shared launch helpers and set any preferences a fixture depends on explicitly.

### 2026-11-28 10:11 — H214 (gemini, fba6d597-0497-4fd3-8e05-be47be972671, first submit)
- **How was working on this job in our code base?** H214 brief was clear and well-scoped; noting that tools/test_inventory.py starts with test_ despite Touches saying it has no test_ prefix, so # runner: none was needed in its header to keep featuretest.sh from running it recursively.
- **Any improvements you can think of?** When a new tools/ script starts with test_ and is not a test file, mention # runner: none in the brief or name it without the test_ prefix.

### 2026-11-28 10:20 — H214 (gemini, ?, resubmit)
- **How was the review round: were the return notes clear, and what would have avoided the return?** The return note was crystal clear and caught two real blind spots (-v for tools/*.py tests and QUICK timing (s): step parsing); resubmission was fast and clean.
- **Any improvements you can think of?** Record quicktest.sh passes automatically for job.py done reuse (just like gate.sh does), so workers don't have to wait for a second quicktest run on submit.

### 2026-11-28 10:31 — H215 (gemini, 6af2a9f7-b0af-486e-b5d4-546a2f71b0a5, first submit)
- **How was working on this job in our code base?** Smooth, well-scoped brief: building on H214's test_inventory.py and featuretest.sh runner discovery made wiring --coverage straightforward, and the 5x slowdown threshold gave a clear target.
- **Any improvements you can think of?** Note in docs/tools README that freecadcmd puts -u/-s flags before the script in sys.argv and runs top-level scripts with __name__ == <stem> rather than __main__, which is useful for any future freecadcmd wrapper.

### 2026-11-28 10:39 — H215 (gemini, ?, resubmit)
- **How was the review round: were the return notes clear, and what would have avoided the return?** Sharp return review: catching the untraced child-process blind spot immediately turned 9 false candidate probes into real coverage (serve.py 6%->89.8%, drawing.py 0%->94.5%, total 80.9%->90.0%).
- **Any improvements you can think of?** Document in tools/README.md that freecadcmd ignores sitecustomize.py on PYTHONPATH, so child FreeCAD tracing works via the FREECAD wrapper that worker/test_link.py already honors.

### 2026-11-28 12:36 — H216 (codex, 01a22319-c293-7210-bf4f-84e0f9b270c9, first submit)
- **How was working on this job in our code base?** The brief gave me three concrete transcript formats and clear checks. Live logs exposed an extra Codex representation and a few ledger matches to integrator sessions. Checking claims, worktree activity, and merge history made those discrepancies traceable.
- **Any improvements you can think of?** Record the confirmed transcript ID and start and end timestamps per job attempt. That would make returned and reassigned jobs easier to measure after queue pruning.
