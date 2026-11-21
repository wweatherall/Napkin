# U01 — Persistent branching history

Codex proposal for H008, 2026-11-21. Based on main 5c0b602 and decisions U01–U03, A23–A25, A28, A31, W13. This is a build specification for review, not a record of newly approved behaviour. Recommendations below that settle an open interaction or retention choice need William's approval before implementation. A32 save generations remains Tentative.

## Outcome and boundaries

Undo moves through saved modelling states without deleting abandoned futures. After undoing C back to A, making D leaves both A→B→C and A→D available. The right panel shows roughly 20 action rows at its initial size, scrolls older steps, and restores a clicked state. Twenty rows is a viewport size, not a retention limit. The FCStd at the normal model path remains the currently saved native model; the journal describes paths to other states, not an alternative geometry engine.

Deliver T35 identities/action boundaries and A31 controller before T36 persistence/panel. U03 merge is a later, explicit operation; no automatic branch merging is in this implementation.

## Existing behaviour to replace or preserve

Verified against viewport/main.gd, viewport/tools/move_tool.gd and worker/replay.py:

- `undo()` removes the last op, bounded by `undo_floor`. `_restore_counters()` scans current ops, which cannot reserve identifiers used only on a discarded future.
- Move `_amend_last_move()` removes and recreates a move under the same op ID. That mutable dictionary must not be shared by retained history versions.
- `Session.sync(ops)` compares canonical op prefixes, undoes the divergent tail, then applies new ops. It rebuilds when the prefix predates `session_base` or the native undo stack is too short. History must not assume the native 20-step stack is durable storage.
- `_states` holds 40 confirmed mesh states keyed by the op-list hash. It is a visual cache, not history retention.
- Replies carry seq; `_on_response` uses the latest seq and dirty flag for successful sync results. Saved notifications currently identify model and rev, not a history node.
- The journal is `shopsketch-journal/0.1`, containing ops, statuses, rev and FCStd hash. FCStd replacement and journal replacement are separate; a matching revision/hash detects a mismatch but does not itself recover the previous pair.
- W13 supplies one writer window per model, with a shared select-based worker serving multiple models. Neither sequence numbers nor revision numbers are globally unique across models or worker restarts.

## Controller ownership and invariants

A31's document controller owns desired node, confirmed node, saved node/generation, request sequence, model identity, current epoch and the complete tree metadata. Tools submit one completed action and optional later amendments. They do not mutate stored nodes or issue sync themselves.

The worker remains the single writer of the model and journal. Tree updates sent by the controller are validated/persisted by that model's Session; do not introduce competing viewport and worker journal writers. W13 routes per-model requests, and every state/cache lookup includes model identity.

Invariants:

1. Node IDs and entity IDs are immutable; no new entity reuses an identifier previously allocated in any retained branch or pending action.
2. An action node represents one atomic user action, which may contain multiple worker ops. Its payload never changes after publication.
3. Every selectable confirmed node has a reproducible base plus canonical op payloads. Cached meshes are optional.
4. A successful save acknowledges the exact node and generation whose FCStd/hash pair landed. A newer desired state does not inherit an older save badge.
5. An old reply cannot alter current geometry, selection, failure messages or save state. Failed responses require the same identity/sequence checks as successes.
6. Restoring a different branch never deletes the branch being left, including after a crash or restart.

## Panel and commands — recommended interaction

Panel rows show a readable action label, optional edited value, state icon/text and branch connectors. Examples: “Move leg · 120 mm”, “Copy rail · 6 copies”, “Cut joint into brace”, “Paint 3 linked boards · White oak”. Use stored stable entity references plus a display-label snapshot; renaming a part must not break history. Internal object names and raw JSON are not the default labels.

The current requested position has a strong marker; the last confirmed row has a distinct check; saved state is a separate badge, not a fifth mutually exclusive execution state. A row can be confirmed but not yet saved. Pending shows progress, failed shows the actual rejection reason and a retry/edit route, without relying on colour alone. No saved badge until both geometry and matching history metadata are durable.

Scrolling over the panel scrolls history, never the model camera. Restore only on a row click or keyboard activation, not hover or scroll. A branch disclosure expands alternative futures without restoring one. Keep a clear current-path indicator when scrolling away from the current row. Resize/collapse is a recommendation; roughly 20 rows remain the initial layout target.

- **Click a confirmed row:** cancel an unfinished tool gesture, request restoration of that node, show its cached mesh if present, then confirm through FreeCAD. Keep the previous confirmed state recoverable if restoration fails.
- **⌘Z:** if a tool has an uncommitted gesture, cancel that gesture first (recommended); otherwise request the parent action node. At the epoch root/floor, do nothing and explain the boundary.
- **⇧⌘Z:** follow the chosen child on this path. At a fork with no recorded choice, open the branch chooser; do not silently pick whichever branch was newest. Choosing a row records the chosen child along the path.
- **Escape:** first cancel a draft or close the branch chooser; otherwise preserve normal context-exit behaviour. Do not silently rewind a confirmed history restore. A pending restore can be superseded by requesting the previous node; its old reply is ignored. Escape is not worker-process cancellation.
- Toolbar Undo/Redo and Edit-menu commands call the same controller methods. The status bar retains Q22's Saving/Saved feedback, with the saved-node/generation association handled internally.
- A second window opening the same model still focuses its owner under W13. The history panel creates no second editable window or independent writer. Different models have completely separate selected paths.

Failed rows are diagnostic attempts rather than usable geometry states. Retry makes a new attempt/version; never mark a failed row confirmed by rewriting its original payload. Descendants that rely on a failed action cannot be selected as valid model states. Independent later actions can survive only after controller dependency pruning and worker confirmation of the resulting path.

## One undo step and amendments

Tools declare `action_id`, label and their ordered low-level ops. Array creation including all copies, and I34's complete joint including both boards, each become one node/transaction boundary. Grouping is based on the user action, not a time window. A profile completed as a separate action remains its own step; a new joint's internal helper profile is not a separate user step.

A multi-op action needs worker transaction support: opening one FreeCAD transaction per low-level op is insufficient. Add an action-batch adapter around Model.apply, with one outer transaction and rejection of the whole batch if any required op fails. Keep `Session.sync` prefix logic at action boundaries, flattening ops only for legacy-compatible replay. Never leave half a joint after rejection or undo.

Typed corrections create an immutable revision of the same logical action: A→Move(100) becomes A→Move(120), with a new node ID and `amends` reference to the old node. Existing descendants continue to point to Move(100). The UI may collapse superseded leaf revisions beneath one action row (proposal), but must preserve access if a retained branch references them. Do not mutate a dictionary referenced by another branch.

Entity identities can be preserved between revisions of the same logical creation (the same intended board becoming longer). That is not allocation to a different entity. Increasing an array count allocates fresh IDs for new members; removed member IDs remain reserved if count shrinks and are not casually assigned to different members later. Record the logical-member mapping in the action revision. All payload changes create a new canonical hash even when logical action/entity IDs remain unchanged.

## T35 IDs and migration

Recommend UUID identifiers with type prefixes, e.g. `b_<uuid>`, `r_<uuid>`, `op_<uuid>`, `a_<uuid>`, `node_<uuid>`. Use OS-quality random bytes/UUID generation, not timestamps or a counter reconstructed from the current path. Session/model/controller validates collisions against a document-wide registry before accepting a new allocation. Branch-local serial numbers may still be used for friendly labels.

Stable `document_id` survives ordinary saves; Save As should preserve lineage while the new worker session uses its canonical path/lease identity to distinguish writers. Whether Save As starts a fresh lineage is a product question below; do not confuse lineage identity with W13's file ownership.

Migration from journal 0.1:

1. Verify journal rev/hash against the FCStd. If they disagree, use the external-edit/recovery route; do not manufacture a normal linear history from an unverified journal.
2. Preserve every legacy entity and op ID verbatim; native properties and references already use them. Scan all op fields, native BodyId/RectId/SSOp/AssemblyId properties, array new_ids and mirror group IDs to seed the reserved registry.
3. Create a linear node chain with one legacy op per action initially, recording `legacy_grouping_unknown`. Do not guess historical gesture boundaries. Failed statuses become diagnostic records; reproduce the confirmed model using the accepted ops, preserving original records for inspection.
4. Allocate new UUID-form IDs going forward. Update parsers/tests that assume numeric suffixes. Never rewrite all geometry IDs just to modernize the format.
5. Write the migrated journal only after verifying its selected path reproduces the current model (or reference a validated baseline snapshot when external history cannot replay). Keep the old journal as a migration backup. Unknown future format versions are read-only errors, not empty history.

## Storage proposal

Keep the authoritative tree in the existing adjacent journal, introducing `shopsketch-journal/0.2`. Put large optional checkpoints under `<model>.shopsketch-history/`. Moving/copying a model with history must carry its journal and checkpoint directory; ordinary FCStd alone stays usable in FreeCAD but cannot contain all abandoned futures under this proposal.

Suggested logical schema (field names provisional):

```json
{
  "format": "shopsketch-journal/0.2",
  "document_id": "uuid",
  "generation": 42,
  "model_rev": 42,
  "file_sha256": "...",
  "selected_node": "node_D",
  "confirmed_node": "node_D",
  "saved_node": "node_D",
  "epochs": {"epoch_1": {"root": "node_root", "baseline": "checkpoint_hash"}},
  "nodes": {
    "node_D": {
      "parent": "node_A", "epoch": "epoch_1", "action_id": "action_uuid",
      "label": "Move leg", "ops": [], "payload_hash": "...", "amends": null,
      "execution": "confirmed", "created_at": "ISO-8601"
    }
  },
  "preferred_child": {"node_A": "node_D"},
  "reserved_ids": [],
  "checkpoints": {},
  "attempts": []
}
```

Nodes store action deltas once; parent traversal materializes the selected op list. Child indexes may be derived and cached. Validate acyclicity, parent existence, action hashes, unique IDs and epoch membership on load. Never trust paths embedded in a journal to escape its own history directory. Defer multi-parent merge nodes until U03; later merge results can initially be ordinary child actions with separate provenance.

Pending attempts are not saved geometry. If recording them for crash recovery, persist their explicit pending status and last confirmed base; offer retry after restart rather than presenting them as accepted. Keep a confirmed/saved model snapshot even when the selected UI intent is newer. The sample shows the simple fully settled case.

## Checkpoints, retention and A32

A checkpoint is an immutable FCStd, its node ID and canonical path hash, FreeCAD/app format metadata and a content checksum. Save only confirmed states. To accelerate a deep restore, load the nearest valid ancestor checkpoint in a temporary Session and replay the suffix; validate before replacing the active Session. FreeCAD native undo only covers the newly replayed suffix, so keep the checkpoint as the rebuild baseline. Existing `_rebuild()` creates an empty document and must be adapted for this baseline; a checkpoint cannot simply be supplied as another op list.

Initial engineering proposal: checkpoint every 50 confirmed actions and at expensive branch points; tune from measured rebuild latency. Cache budget proposal: 512 MB for redundant checkpoints/meshes, LRU eviction, excluding epoch baselines needed for reproducibility. **Never silently prune history nodes, branches, reserved IDs, or required baselines to meet a cache budget.** If required storage cannot be written, report save failure and preserve the last good generation. User-requested permanent deletion is a separate future feature.

A32 generation saving is the recommended durability prerequisite before shipping persistent branching history. If not approved, document that atomic writes of two separate files do not give the required crash recovery guarantee; do not advertise it as solved.

Suggested generation layout: private immutable generation pairs plus a small atomic current-generation manifest. Write and flush new FCStd and journal, verify their checksums/IDs, flush their directory, then atomically replace the manifest and acknowledge saved(node,generation). Keep at least the prior complete pair. Publish the normal model.FCStd and adjacent journal for interoperability; that public pair can temporarily lag the manifest during a crash. Recovery chooses the latest valid committed pair and repairs the public pair only after checking for external edits. Orphan incomplete generations are never selected merely because their filename has a larger number.

External FreeCAD changes must not be overwritten by automatic repair: compare the public FCStd hash with both known generation exports and the last observed file signature. An unknown hash is external content to preserve, not a failed write to replace. File and directory durability calls, rename semantics and recovery failure paths need real crash-injection tests on macOS; this spec does not establish them.

## External edits and undo floors

An externally changed FCStd establishes a new epoch with an immutable baseline and an undo floor at that baseline. Preserve the old tree under its previous epoch; do not claim it can replay on the modified geometry. Keep the floor as explicit epoch metadata across saves/restarts, rather than clearing it merely because a new journal was saved. The existing save code resets undo_floor; implementing this invariant needs a change there.

Q19's choice to reapply missing Shop Sketch actions creates new action versions on the new baseline and must report failures. It never silently splices two histories. “Keep external version” retains the old epoch as history, without applying it. Recommended UI: older epochs are browseable but restoring one requires an explicit “Restore this older model version” action with a preview, preserving the current epoch first. That cross-epoch restore policy needs William's decision; initial T36 may keep those rows read-only.

## Restoration and transport

1. Record desired node; materialize and validate its path. Increment the controller's sequence and include `(model path/lease, document_id, session incarnation, epoch, node_id, path_hash, seq)` in request identity.
2. Show cached confirmed meshes for that exact path if present; otherwise retain the previous confirmed view with a clear restoring state. Clear stale selection or remap only IDs present on the requested path. Never enable edits against a stale old selection while claiming the new geometry is active.
3. Same epoch/no checkpoint switch: send the branch's op list through existing sync. Deep paths can use the checkpoint adapter described above. New desired nodes supersede old requests; coalesce queued restores to the newest one without killing the shared worker or another model's work.
4. Match the full request identity before applying any successful or failed response. Shared output directories can be overwritten by another queued request: use immutable response manifests/file keys or request-specific output directories, not an unchecked latest bodies.json.
5. On confirmation, update confirmed node and visual caches. Save through the worker and acknowledge the exact node/generation. A saved notice for an older node can mark that node durable but cannot label a newer requested node Saved.
6. On failure, retain the previous confirmed model, flag the attempted restore and offer a return/retry. Worker may have partially applied a legacy op list: restore a known confirmed state before accepting more edits. Multi-op action transactions prevent partial new actions but do not alone make a full branch restore atomic.

Worker restart rotates the session incarnation; pending old replies and caches without matching document identity cannot be accepted. W13's focus/ownership behaviour remains unchanged.

## Acceptance checks

- A→B→C, undo to A, edit D, save/restart: both futures exist; C and D restore identical volumes, transforms, materials, grain, family/array relationships and assemblies to fresh builds.
- Create b3, undo, create another board: IDs differ; repeated undo/redo, crash/restart and amendments never collide. Legacy IDs still resolve after migration.
- Six-copy array and two-board joint each undo in one step; a failed socket rolls back the entire joint.
- Amend a typed move after branching: old branch retains its original value/geometry; active branch has revised value. Shrinking/regrowing an array does not reassign an old member's identity to a different member.
- Restore beyond 20 native undo steps and 40 visual cache states, with and without valid checkpoints. Corrupt checkpoints fall back to a validated ancestor; missing mandatory baseline reports a recoverability error without deleting history.
- Late success, failure and saved messages, model switches, worker restarts and rapid branch clicks never replace a newer desired state. Two model windows using the same seq value remain isolated.
- Crash at every generation write/rename boundary: recover a matching committed pair or preserve/report external content; never report Saved for a half-pair. Disk-full and permission failures retain the prior pair.
- External changes establish a floor that survives autosave/restart. Reapply and keep-external routes preserve prior epochs; undo never reconstructs an external baseline from an empty document.
- Panel scroll never zooms the model; keyboard and toolbar agree; branch disclosure does not restore; selected/focused/current/confirmed/saved states are distinguishable without colour.
- Failed/dependent actions leave a valid model and traceable diagnostics. Reopening a migrated journal is idempotent and preserves the original native model.

## Questions for William, before implementing these choices

1. At an unchosen fork, should Redo open a branch chooser (recommended), or choose the most recently visited child automatically?
2. Should superseded typed corrections appear collapsed beneath one action (recommended), with older versions still accessible?
3. Should the first release allow explicit restoration across an external-FreeCAD-edit boundary, or keep older epochs browseable/read-only until that recovery flow is ready (recommended)?
4. May redundant caches/checkpoints use a 512 MB default budget while required history is never silently deleted? The 50-action checkpoint interval is a tunable starting point, not a user-visible cap.
5. Approve A32 generation saving as a prerequisite for claiming restart/crash-safe branch persistence? The current two-file replacement is insufficient for that guarantee.

These questions do not block this design deliverable. Claude should bring them one at a time when their implementation becomes current work.
