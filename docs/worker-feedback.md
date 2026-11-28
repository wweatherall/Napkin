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
