### H067 — Agent roles: direction from William and request for a transition plan

Author: Codex | Date: 2026-11-22 | Status: open | For: the integrator

References: P16, P24, P28, G11, G12; decision placeholders listed in the response below.

Touches: this handoff and its new decision-log rows only. A communication/design handoff, not a Ready worker implementation job. No queue, role permissions or runtime changes are made by this branch.

Request: William wants to communicate the following discussion to the current integrator so we can start building toward the system. Review it and propose a staged transition with bounded jobs, acceptance criteria and unresolved questions. Preserve the existing workflow until a replacement is explicitly adopted; in particular, this note does not immediately transfer P28's document ownership or replace P16's integrator authority.

## William's stated direction

The integrator is overloaded. Separate responsibilities into worker, integrator, architect, dispatcher/time manager, ideator, and decision partner (William used “decision bot”/“decision maker”; these are working descriptions, not finalized UI names). William retains product and behavior decisions.

- Architect: handles abstractions, the big picture and ARCHITECTURE.md. William explicitly says it should not read code at all. Workers supply abstract structural reports describing how their new code integrates with the existing structure; the architect analyzes those reports.
- Integrator: continues reviewing code and verifies that each worker's structural report matches the implementation. This is the agreed replacement for Codex's initial suggestion of a separate independent reviewer; a new permanent reviewer is not requested.
- Dispatcher/time manager: starts/pauses agents, spins up new sessions and wakes other LLMs. It must also figure out execution order and prioritize the work between approved proposed changes and the architecture that actually exists. William expects much of this could be code, but recognizes that prioritization may require reasoning.
- Ideator: a partner for discussing and developing new ideas with William.
- Decision partner: a sharp reasoning partner for working through decisions with William, with a different, potentially longer-lived working context than the integrator.
- William expects ideator and decision partner to mostly communicate with the architect. He asked whether the architect should also own the agent organization, communication routes and required workflow steps; Codex recommended this division, as described below, but the detailed boundary has not separately been approved.

William's motivation includes reducing the integrator's context and running cost while preserving performance. He suggested that abstract architecture work could require less context than code integration; no measured cost or context-budget claim was established.

## Working design developed in discussion — proposals for review

These details were suggested by Codex; do not silently promote them to William's approved requirements:

1. Architect owns the design of both the application and the agent organization: role boundaries, communication contracts, required workflow stages, structural plans and technical dependencies. Keep application architecture and agent workflow in separate documents so they can be loaded independently. Dispatcher owns live sessions, queue state, delivery, capacity and execution order; William supplies product priorities.
2. Worker submits a structural report before implementation, then amends it at completion. Suggested fields: placement in existing components; responsibilities; interfaces and dependency direction; state ownership/lifecycle/persistence; constraints preserved or changed; one concrete end-to-end example. Integrator verifies the final report against code; architect incorporates verified changes into its documents before merge completion. Define a return path for discrepancies and changed structural plans.
3. Dispatcher could combine a deterministic scheduler with an LLM planner invoked for judgment calls. Schedule only approved work, distinguish planned/in-progress/completed/merged state, and release dependencies according to their actual required milestone. A completed branch does not by itself establish merged architecture.
4. Reduce context through bounded job packets, layered versioned architecture summaries, current decisions separate from history, verified change reports after merges, structured bookkeeping, bounded sessions with restart packets, linked evidence, and targeted requests for missing facts. Architect can request verified implementation facts from worker/integrator without reading code. Decision partner's retained context emphasizes William's goals, preferences, outstanding choices and decision rationale.

## Requested next step for the integrator

Read this against current queue/integration tooling and report a concrete incremental proposal back to William. Identify which existing mechanisms can be reused, which responsibilities/authority documents must change (including P16/P24/P28 and G12 where applicable), and which choices need William's answer before implementation. Assess how the architect's no-code boundary and integrator verification will work without circular approval or excessive handoffs. Do not redesign or interrupt in-flight feature jobs merely on the strength of this note.

Open choices include: final role names and authority; who converts approved direction into bounded executable jobs; precise priority/dependency rules; report schema and review timing; handling stale architecture and incomplete reports; architect document update timing relative to merge; model/session/context budgets; available mechanisms for launching, pausing, resuming and notifying agents; first useful migration step. These are design questions, not claims that current tools support those actions.

Response — Codex, 2026-11-22:
Prepared a durable account of William's stated direction, separated from Codex's proposed details. Branch: codex/agent-role-proposal. Decision placeholders: P29 through P35. Verification: tools/quicktest.sh passed (208 UI checks plus all feature tests); tools/fulltest.sh passed; decision-log sorting and git diff --check passed. The initial quick run found a missing handoff index entry; rebuilt the index and reran successfully. No production code or active workflow changed.

For the integrator: Number the placeholders and list this exchange through the normal handoff tooling when integrating; propose the transition to William before changing existing authorities.
Architecture: No application architecture change in this branch. Future adoption needs an agent-workflow design and explicit ownership updates; current P28 remains in effect.
Result: this commit; quick test and full test passed; recorded agent-role direction and requested an incremental transition plan
