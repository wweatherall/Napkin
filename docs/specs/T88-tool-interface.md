# T88: the interface tools use

Stage 1 proposal for H047, checked against `ce3c7e9` (2026-11-22).
This describes a proposed boundary, not implemented behaviour. T88, A33b and A34
are the authority; existing interaction decisions and op formats stay in force.
No production file changes in this job. The current architecture map remains a
map of the implementation, not this proposal.

## Recommendation

Give each tool `setup(ctx)` with a `ToolContext` from a new
`viewport/tool_context.gd`. It supplies named capabilities with explicit methods,
not Main, raw controllers, scene nodes or mutable dictionaries. Tools keep gesture
state and construct the same op dictionaries. Document owns op edits and IDs;
presenter owns all preview/draft/cache/wave changes; selection owns membership and
context; inference remains the one snapping engine. Main constructs and wires the
objects, dispatches input, and manages the window and worker lifecycle.

Keep the existing tool callbacks (`click`, `release`, `typed`, `reset`, `key`,
`mouse_moved`, `busy`, `in_gesture`, `accepts`, `hint`, `tip`, `vcb_label`,
`vcb_value`) and registry `TOOL` metadata. This is a dependency change, not a
replacement tool framework. Do not turn every `m.*` name into a `ctx.*` property:
that would preserve the same write access under another name.

## Current dependency inventory

The tables below cover every distinct `m.<name>` in each tool, including the base.
R = read (including node access), W = write, including mutation through a returned
container or node, C = call (R/C for a nested owner call). A callable may change owner state; C does not mean
pure. Function names in each row are citations in that row's tool file.
`Main` = main.gd itself; `doc`, `sel`, `pres`, `measure`, `infer` = the corresponding
viewport/*.gd owner, reached through main.gd forwarding unless noted. Scene nodes
and materials are currently created/held by Main even where pres manipulates them.
Group labels describe use, not new modules. Empty groups have no dependency.

### `tool.gd`

| Group | Member | Use | Owner today | Functions |
|---|---|---|---|---|
| Measurements | `vcb` | R | measure | `accepts` |

### `paint_tool.gd`

| Group | Member | Use | Owner today | Functions |
|---|---|---|---|---|
| Picking and snapping | `pick` | C | infer (Main forwards) | `click`, `mouse_moved` |
| Drafts and previews | `_tri_mesh` | C | Main | `mouse_moved` |
| Drafts and previews | `overlay` | R/W | Main | `mouse_moved` |
| Selection and context | `unit_of` | C | sel | `click`, `mouse_moved` |
| Selection and context | `unit_tris` | C | Main | `mouse_moved` |
| Materials and paint | `mat_hover` | R | Main | `mouse_moved` |
| Materials and paint | `paint` | C | Main | `click` |
| Materials and paint | `paint_material` | R | Main | `hint` |
| Materials and paint | `wood_library` | R | Main | `hint` |

### `select_tool.gd`

| Group | Member | Use | Owner today | Functions |
|---|---|---|---|---|
| Picking and snapping | `cam` | R | Main | `box_ids` |
| Picking and snapping | `pick` | C | infer (Main forwards) | `click`, `double_click`, `mouse_moved` |
| Drafts and previews | `_tri_mesh` | C | Main | `mouse_moved` |
| Drafts and previews | `add_child` | C | Main | `_show_box` |
| Drafts and previews | `body_tris` | R | pres | `box_ids` |
| Drafts and previews | `overlay` | R/W | Main | `mouse_moved` |
| Selection and context | `enter_context_of` | C | sel | `double_click` |
| Selection and context | `in_context` | C | sel | `box_ids` |
| Selection and context | `is_hidden` | C | sel | `box_ids` |
| Selection and context | `selection` | R | sel | `click` |
| Selection and context | `set_selection` | C | sel | `click`, `release`, `reset` |
| Selection and context | `unit_of` | C | sel | `box_ids`, `click`, `mouse_moved` |
| Selection and context | `unit_tris` | C | Main | `mouse_moved` |
| Materials and paint | `mat_hover` | R | Main | `mouse_moved` |

### `circle_tool.gd`

| Group | Member | Use | Owner today | Functions |
|---|---|---|---|---|
| Picking and snapping | `cam` | R | Main | `_radius_drag` |
| Picking and snapping | `pick` | C | infer (Main forwards) | `click`, `mouse_moved` |
| Picking and snapping | `snap` | C | infer (Main forwards) | `_radius_drag`, `click`, `mouse_moved` |
| Drafts and previews | `_lines` | C | Main | `_radius_drag` |
| Drafts and previews | `_register_rect` | C | pres | `commit_circle` |
| Drafts and previews | `_show_marker` | C | Main | `_radius_drag`, `mouse_moved` |
| Drafts and previews | `_tri_mesh` | C | Main | `_radius_drag` |
| Drafts and previews | `overlay` | R/W | Main | `_radius_drag`, `commit_circle` |
| Drafts and previews | `overlay_lines` | R/W | Main | `_radius_drag`, `commit_circle` |
| Drafts and previews | `pres` | R/C | pres (direct: circle_geometry) | `_radius_drag` |
| Drafts and previews | `rects` | R | pres | `click` |
| Op list and counters | `counters` | R/W | doc | `commit_circle` |
| Op list and counters | `ops` | R/W | doc | `commit_circle` |
| Op list and counters | `sync` | C | doc | `commit_circle` |
| Selection and context | `edit_blocked` | C | sel | `click` |
| Measurements | `_update_vcb` | C | measure | `_radius_drag` |
| Materials and paint | `mat_rect` | R | Main | `_radius_drag` |

### `rect_tool.gd`

| Group | Member | Use | Owner today | Functions |
|---|---|---|---|---|
| Picking and snapping | `cam` | R | Main | `_rect_drag` |
| Picking and snapping | `pick` | C | infer (Main forwards) | `click`, `mouse_moved` |
| Picking and snapping | `snap` | C | infer (Main forwards) | `_rect_drag`, `click`, `mouse_moved` |
| Drafts and previews | `_lines` | C | Main | `_preview_rect` |
| Drafts and previews | `_register_rect` | C | pres | `commit_rect` |
| Drafts and previews | `_show_marker` | C | Main | `_rect_drag`, `mouse_moved` |
| Drafts and previews | `_tri_mesh` | C | Main | `_preview_rect` |
| Drafts and previews | `overlay` | R/W | Main | `_preview_rect`, `commit_rect` |
| Drafts and previews | `overlay_lines` | R/W | Main | `_preview_rect`, `commit_rect` |
| Drafts and previews | `rects` | R | pres | `click` |
| Op list and counters | `counters` | R/W | doc | `commit_rect` |
| Op list and counters | `ops` | R/W | doc | `commit_rect` |
| Op list and counters | `sync` | C | doc | `commit_rect` |
| Selection and context | `edit_blocked` | C | sel | `click` |
| Measurements | `_update_vcb` | C | measure | `_rect_drag` |
| Materials and paint | `mat_rect` | R | Main | `_preview_rect` |

### `push_tool.gd`

| Group | Member | Use | Owner today | Functions |
|---|---|---|---|---|
| Picking and snapping | `cam` | R | Main | `_push_drag`, `_snap_to_face_behind` |
| Picking and snapping | `pick` | C | infer (Main forwards) | `_edge_inference`, `_push_hover` |
| Drafts and previews | `_add_collision` | C | Main | `_add_push_draft` |
| Drafts and previews | `_attach_wave` | C | pres | `commit_push` |
| Drafts and previews | `_base_of` | C | pres | `commit_push` |
| Drafts and previews | `_begin_wave` | C | pres | `commit_push` |
| Drafts and previews | `_lines` | C | Main | `_add_push_draft`, `_preview_push` |
| Drafts and previews | `_show_marker` | C | Main | `_push_drag`, `_snap_to_face_behind` |
| Drafts and previews | `_tri_mesh` | C | Main | `_add_push_draft`, `_choose_face`, `_preview_push`, `_push_hover` |
| Drafts and previews | `add_child` | C | Main | `_choose_face` |
| Drafts and previews | `bodies_root` | R/W | Main | `commit_push` |
| Drafts and previews | `body_edges` | R/W | pres | `_add_push_draft` |
| Drafts and previews | `body_tris` | R/W | pres | `_add_push_draft`, `_depths_behind`, `commit_push`, `coplanar_region` |
| Drafts and previews | `body_verts` | R/W | pres | `_add_push_draft` |
| Drafts and previews | `draft_bboxes` | R/W | Main | `commit_push` |
| Drafts and previews | `drafts` | R/W | pres | `_add_push_draft`, `commit_push` |
| Drafts and previews | `drafts_root` | R/W | Main | `_add_push_draft` |
| Drafts and previews | `marker` | R/W | Main | `_push_drag`, `_push_hover`, `commit_push` |
| Drafts and previews | `overlay` | R/W | Main | `_preview_push`, `_push_hover`, `commit_push` |
| Drafts and previews | `overlay_lines` | R/W | Main | `_preview_push`, `commit_push` |
| Drafts and previews | `rects` | R | pres | `_depths_behind`, `_edge_inference`, `_push_hover`, `click`, `commit_push` |
| Drafts and previews | `stock_frames` | R | pres | `_edge_inference`, `commit_push` |
| Drafts and previews | `test_mode` | R | Main | `commit_push` |
| Op list and counters | `counters` | R/W | doc | `commit_push` |
| Op list and counters | `force_reject_next` | R/W | Main | `commit_push` |
| Op list and counters | `ops` | R/W | doc | `commit_push` |
| Op list and counters | `sync` | C | doc | `commit_push` |
| Selection and context | `context_assembly` | C | sel | `commit_push` |
| Selection and context | `edit_blocked` | C | sel | `click` |
| Selection and context | `new_board` | R | Main | `_edge_inference`, `commit_push` |
| Measurements | `_update_vcb` | C | measure | `_push_drag`, `key` |
| Materials and paint | `mat_cut` | R | Main | `_add_push_draft`, `_preview_push` |
| Materials and paint | `mat_draft` | R | Main | `_add_push_draft`, `_preview_push` |
| Materials and paint | `mat_hover` | R | Main | `_choose_face`, `_preview_push`, `_push_hover` |
| Messages | `_update_tip` | C | Main | `key` |
| Messages | `reject_note` | W | Main | `commit_push` |

### `move_tool.gd`

| Group | Member | Use | Owner today | Functions |
|---|---|---|---|---|
| Picking and snapping | `_cursor_pos` | C | Main | `_commit_cut_move`, `_face_plane_under_cursor`, `commit_mirror`, `commit_move`, `key` |
| Picking and snapping | `grid_snap` | R | Main | `_move_move` |
| Picking and snapping | `pick` | C | infer (Main forwards) | `_face_plane_under_cursor`, `_move_click`, `_move_move` |
| Picking and snapping | `snap` | C | infer (Main forwards) | `_move_click` |
| Drafts and previews | `_add_collision` | C | Main | `commit_mirror`, `commit_move` |
| Drafts and previews | `_attach_wave` | C | pres | `_commit_cut_move`, `commit_mirror`, `commit_move` |
| Drafts and previews | `_base_of` | C | pres | `_commit_cut_move` |
| Drafts and previews | `_begin_wave` | C | pres | `_commit_cut_move`, `commit_mirror`, `commit_move` |
| Drafts and previews | `_cut_at` | C | pres | `_move_click`, `_move_move` |
| Drafts and previews | `_cut_tris` | C | pres | `_move_click`, `_move_move` |
| Drafts and previews | `_draw_guides` | C | Main | `_move_move` |
| Drafts and previews | `_lines` | C | Main | `_commit_cut_move`, `_move_move`, `_preview_mirror_move`, `_preview_mirror_plane`, `_preview_move`, `commit_mirror`, `commit_move` |
| Drafts and previews | `_show_marker` | C | Main | `_preview_mirror_move`, `_preview_mirror_plane` |
| Drafts and previews | `_tri_mesh` | C | Main | `_commit_cut_move`, `_move_move`, `_preview_mirror_move`, `_preview_mirror_plane`, `_preview_move`, `commit_mirror`, `commit_move` |
| Drafts and previews | `bodies_root` | R/W | Main | `_commit_cut_move`, `commit_mirror`, `commit_move` |
| Drafts and previews | `body_edges` | R/W | pres | `commit_mirror`, `commit_move` |
| Drafts and previews | `body_tris` | R/W | pres | `_commit_cut_move`, `_move_click`, `_move_move`, `_preview_move`, `commit_mirror`, `commit_move` |
| Drafts and previews | `body_verts` | R/W | pres | `commit_mirror`, `commit_move` |
| Drafts and previews | `draft_bboxes` | R/W | Main | `commit_mirror`, `commit_move` |
| Drafts and previews | `drafts` | R/W | pres | `_commit_cut_move`, `commit_mirror`, `commit_move` |
| Drafts and previews | `drafts_root` | R/W | Main | `_commit_cut_move`, `commit_mirror`, `commit_move` |
| Drafts and previews | `guides` | R/W | Main | `_commit_cut_move`, `commit_mirror`, `commit_move` |
| Drafts and previews | `marker` | R/W | Main | `_commit_cut_move`, `_move_move`, `commit_mirror`, `commit_move` |
| Drafts and previews | `overlay` | R/W | Main | `_commit_cut_move`, `_move_move`, `_preview_mirror_move`, `_preview_mirror_plane`, `_preview_move`, `commit_mirror`, `commit_move` |
| Drafts and previews | `overlay_lines` | R/W | Main | `_commit_cut_move`, `_move_move`, `_preview_mirror_move`, `_preview_mirror_plane`, `_preview_move`, `commit_mirror`, `commit_move` |
| Drafts and previews | `test_mode` | R | Main | `commit_mirror`, `commit_move` |
| Op list and counters | `counters` | R/W | doc | `_commit_cut_move`, `commit_mirror`, `commit_move` |
| Op list and counters | `ops` | R/W | doc | `_amend_last_move`, `_commit_cut_move`, `commit_mirror`, `commit_move` |
| Op list and counters | `remove_op` | C | doc | `_amend_last_move` |
| Op list and counters | `sync` | C | doc | `_commit_cut_move`, `commit_mirror`, `commit_move` |
| Selection and context | `body_assembly` | R | sel | `_preview_move`, `_whole_assemblies`, `commit_mirror`, `commit_move` |
| Selection and context | `context` | R | sel | `_whole_assemblies`, `commit_mirror`, `commit_move` |
| Selection and context | `sel` | R/C | sel (direct: members_of) | `_preview_move`, `commit_move` |
| Selection and context | `selection` | R | sel | `_move_click` |
| Selection and context | `unit_of` | C | sel | `_move_click` |
| Selection and context | `unit_tris` | C | Main | `_move_click`, `_preview_move` |
| Measurements | `_update_vcb` | C | measure | `_preview_mirror_move`, `_preview_mirror_plane`, `_preview_move`, `key` |
| Materials and paint | `mat_cut` | R | Main | `_commit_cut_move`, `_preview_move` |
| Materials and paint | `mat_cut_hl` | R | Main | `_move_move` |
| Materials and paint | `mat_draft` | R | Main | `_commit_cut_move`, `_preview_mirror_move`, `_preview_mirror_plane`, `_preview_move`, `commit_mirror`, `commit_move` |
| Materials and paint | `mat_hover` | R | Main | `_move_move` |
| Materials and paint | `mat_plane` | R | Main | `_preview_mirror_move`, `_preview_mirror_plane` |
| Messages | `_update_tip` | C | Main | `_commit_cut_move`, `commit_mirror`, `commit_move`, `key` |
| Messages | `reject_note` | W | Main | `commit_mirror`, `commit_move` |

### Dependencies outside the `m.*` spelling

`tool.gd:setup` also reads `viewport.infer` and retains a typed Main reference.
The inherited `accepts` reads `m.vcb` for all six tools, even tools with no typed
operation. Main's `pick`/`snap` simply call inference (`main.gd:pick`, `snap`).

| Tool | Direct inference calls | Static Main dependencies |
|---|---|---|
| paint | none | none |
| select | none | `m2g` |
| circle | `on_grid` | `arr3`, `g2m`, `n_g2m` |
| rect | `on_grid` | `_rect_pts`, `arr3`, `g2m`, `n_g2m`, `plane_basis` |
| push | `point` | `DEFAULT_BASE`, `SNAP_PX`, `_ekey`, `arr3`, `feature_edges`, `m2g`, `prism`, `prism_by`, `unique_verts` |
| move | `axis`, `axis_dest`, `plane_dest`, `point` | `AXIS_COLORS`, `DEFAULT_BASE`, `GRID`, `SNAP_COLORS`, `_axis_vec`, `_mirror_tris`, `arr3`, `clean_normal`, `feature_edges`, `m2g`, `plane_basis`, `reflect_point`, `reflect_tris`, `unique_verts` |

Static citations: select `box_ids`; circle `_radius_drag`, `commit_circle`;
rectangle `click`, `_rect_drag`, `_preview_rect`, `commit_rect`; push
`_snap_to_face_behind`, `coplanar_region`, `_push_drag`, `_push_shape`,
`_preview_push`, `commit_push`, `_add_push_draft`; move `_mirror_axis_and_plane`,
`_face_plane_under_cursor`, `_preview_mirror_move`, `_preview_mirror_plane`,
`commit_mirror_move`, `commit_mirror`, `_move_move`, `_preview_move`,
`commit_move`, `_commit_cut_move`. Inference calls occur in circle `_radius_drag`,
rectangle `_rect_drag`, push `_push_drag`, and move `_move_move`.
`m.pres.circle_geometry` and `m.sel.members_of` are the only nested owner calls in
these tools. Input modifier queries, Geometry2D/3D and tool-local nodes/state are
also dependencies, but do not obtain shared state from Main.

## Proposed surface and implementation owners

All names below are proposed. Each capability is a restricted adapter in
`tool_context.gd`, holding its owner privately. No public `main`, `doc`, `pres`,
`sel`, `measure`, `cam`, `client`, `get_owner` or general-purpose callback escape.
Methods returning dictionaries/arrays return independent snapshots, including
nested containers; mesh arrays are values. No scene nodes or shared Materials
are returned. Tools may mutate only their own state and returned snapshots.
Main wires the adapters once; no new tool requires adding wiring or a switch.

### Picking: `ctx.pick`

Implemented by inference.gd, with a private camera/world dependency supplied at
setup. Move its existing Main reads to explicit presenter/selection/options
queries as part of foundation work; retaining `infer.m` would leave the old
boundary reachable indirectly. Keep all inference algorithms and tolerances.

| Read or call | Contract / source |
|---|---|
| `hit(screen) -> Dictionary` | Current `inference.gd:pick`; same hit keys and ground/profile precedence. |
| `snap(hit, screen) -> Dictionary` | Current `inference.gd:snap`. |
| `on_grid(hit) -> Dictionary` | Current `inference.gd:on_grid`, including disabled-grid behaviour. |
| `point(screen, exclude, plane={}, with_rects=false, not_on={}) -> Dictionary` | Current `inference.gd:point`, same defaults and empty result. |
| `axis(screen, anchor, axes, current) -> int` | Current `inference.gd:axis`, same hysteresis. |
| `axis_dest(screen, ref, axis, exclude="") -> Variant` | Current `inference.gd:axis_dest`, including null. |
| `plane_dest(screen, ref, normal) -> Variant` | Current `inference.gd:plane_dest`, including null. |
| `ray(screen) -> Dictionary` | `{origin, direction}` in model mm/model axes; replaces circle/rect camera calls and push's Godot-space ray algebra with equivalent units. Preserve rounding in `_push_drag`. |
| `project(point) -> Dictionary` | `{screen, behind}` from the private camera; replaces Select and push camera access. |
| `cursor() -> Vector2` | Explicit callable bound to `main.gd:_cursor_pos`; preserves injected test cursor. |
| `grid_enabled() -> bool`, `grid_step() -> float`, `snap_radius() -> float` | Read options/constants; replaces Move's grid-on-face and push's screen-radius reads. |

The last two geometric conversions need equivalence checks on a tilted camera;
they must not introduce new grid or distance rounding.

### Model reads: `ctx.model`

Presenter implements `body_ids() -> Array`, `has_body(id) -> bool`,
`triangles(id) -> PackedVector3Array`, `profile(id) -> Dictionary`,
`stock_frame(id) -> Dictionary`, `unit_triangles(unit) -> PackedVector3Array`,
`cut_at(body, point) -> Dictionary`, `cut_triangles(body, op) -> PackedVector3Array`,
and `circle_geometry(center, normal, radius) -> Dictionary`.
Missing bodies return empty arrays; missing profile/stock frame returns `{}`.
Tools must check presence where today's code uses `has`. Profile snapshots keep
`tris`, `n`, `on`, `pts` and `kind`, and preserve missing `kind` as rectangular.
Sources: `presenter.gd:cut_at`, `cut_tris`, `circle_geometry`, `register_rect`,
`main.gd:unit_tris`; `select_tool.gd:box_ids`, `push_tool.gd:_edge_inference`.
Do not expose mutable maps just to support iteration.

### Selection: `ctx.selection`

Selection implements `ids() -> Array`, `context() -> String`,
`assembly_of(body) -> String`, `members_of(assembly) -> Array`,
`unit_of(body) -> Dictionary`, `in_context(body) -> bool`,
`is_hidden(body) -> bool`, `context_assembly() -> String`,
`edit_blocked(body) -> bool`, `set(ids) -> void`, `enter(body) -> void`.
Keep the existing `edit_blocked` notification through sel.say. `assembly_of`
replaces map indexing; Move's whole-assembly check can gather distinct assembly
IDs from targets and compare `members_of` against targets. Keep its explicit
entered-assembly exclusion. Sources: `selection.gd:unit_of`, `members_of`,
`edit_blocked`, `set_selection`, `enter_context_of`;
`move_tool.gd:_whole_assemblies`, `commit_move`, `commit_mirror`.

### Document: `ctx.document`

Document implements `next_id(prefix) -> String`, `op(id) -> Dictionary`,
`append(op) -> void`, `remove(id, resync=true) -> void`, `sync() -> void`.
`next_id` increments the existing counter and formats exactly as today; it does
not roll back on rejection. Prefixes remain `r`, `pp`, `b`, `mv`, `m`, `a`,
`sm` etc., without a new per-tool registry. `op` returns a deep snapshot of
`document.gd:op_of`; `append` stores a deep copy, does not sync or predict;
`remove` keeps `op_removed`/`removed` signalling and `resync` semantics of
`document.gd:remove_op`; `sync` retains current coalescing and sequence rules.
Sources: `document.gd:restore_counters`, `op_of`, `remove_op`, `sync` and the
commit functions in the inventory. No tool may append to `ops`, edit an op by
alias, or increment counters directly.

Move amendments deliberately retain today's remove-and-recommit sequence:
lookup snapshot, remove (including its current resync), restore memo, append
with the reused ID, predict, sync. Do not quietly replace this with a new atomic
amendment semantic in T88. Test undo/redo and stale replies across that sequence.

### Presentation: `ctx.view`

Presenter owns these commands and all scene/cache writes they cause. Lift the
existing mesh/line/collision helpers out of Main into private presenter helpers;
retain line bias, material choices, collision layers and backface behaviour.

| Command | Payload and effect |
|---|---|
| `preview(tris, style, lines=PackedVector3Array(), line_color=Color(0.6,0.35,0))` | Replaces shared overlay meshes; style is `hover`, `profile`, `draft`, `cut` or `cut_highlight`, mapped to existing materials. Empty arrays clear the corresponding mesh. |
| `clear_preview()` | Clears overlay and outline, not marker/guides/face highlight. |
| `marker(hit)` / `hide_marker()` | Same hit/point/snap payload as `_show_marker`; Move passes its kind as snap, preserving fallback colour. |
| `guides(ref, axis, plane_axis)` / `clear_guides()` | Moves `main.gd:_draw_guides`; same dotted lengths and colours. |
| `selection_box(start, finish)` / `clear_selection_box()` | Presenter owns Panel lifetime; preserve Select's colours, dimensions and ignore-mouse flag. |
| `face_highlight(tris)` / `clear_face_highlight()` | Replaces Push/Pull's separate `face_highlight` node and `m.add_child`. |
| `mirror_preview(tris, corners, axis=-1)` | Presenter builds the extra plane surface and perimeter. Axis colours when axis >= 0, existing oblique colour otherwise; equivalent to Move's two preview functions. |
| `register_profile(op)` | Existing `presenter.gd:register_rect`; works for rect/circle and keeps the current `rect` picking/target path. |
| `present_draft(op, pieces, wave)` | Creates committed draft nodes/collisions, updates prediction caches, consumes the pushed profile draft, hides replaced confirmed bodies, and starts/attaches the wave as specified below. |

`pieces` is an ordered array of `{tris, style, line_color, body_id, replace}`.
`body_id` empty means no collision/cache installation (hole moves); otherwise
install triangles, unique vertices and feature edges together. `replace` hides
that body's confirmed nodes. Store all pieces under op.id; keep push's profile
consumption and `forget_op`/confirmed-draft cleanup compatible with the new root
shape. `wave` is `{origin, tris, is_new, bodies, attach}`; `bodies` is an Array
of IDs, `attach` is `drafts` or `confirmed`. Pushing a new body and moving/copying
boards attach to draft pieces; editing a face or moving a cut attaches to
confirmed nodes with their existing base colours. Preserve the current wave
body sets and origin, including Move arrays' last offset. Capture test bounds
inside presenter when it installs a predicted body. Sources:
`push_tool.gd:_add_push_draft`, `commit_push`; `move_tool.gd:commit_move`,
`commit_mirror`, `_commit_cut_move`; `presenter.gd:begin_wave`, `attach_wave`,
`forget_op`, `drop_confirmed_drafts`. Test the parent/child cleanup change rather
than assuming existing scene-node traversal tolerates a generic draft root.

Keep op construction and source geometry calculations in tools. Presentation
payloads carry predicted geometry, never worker ops or invented region rules.
No tool gets `_tri_mesh`, `_lines`, `_add_collision`, `_base_of`, raw materials,
`add_child`, roots, cache maps, `begin_wave` or `attach_wave` directly.

### Measurements, messages and options: `ctx.ui`

`typed_text() -> String` reads measure.vcb; `refresh_measurements()` calls
measure.update. `refresh_tip(screen)` uses an explicit Main callback to the
current `_update_tip` (it also adds linked-sibling text). `clear_rejection()`
uses an explicit callback clearing Main's reject_note. `new_board() -> bool`
reads the current window option. Arc (T83) added `refresh_hint()` (show the active tool's hint again),
`show_status(text)` (Main's `_say_status`, for an invalid radius) and `tool_active(id) -> bool`. Those callbacks are the complete UI bridge,
not access to Main. Main retains option/menu state and rejection lifecycle;
tools request changes. Sources: `tool.gd:accepts`; `main.gd:_update_tip`,
`_on_sync_failed`; `push_tool.gd:commit_push`, `move_tool.gd:commit_move`.
No new general message API is needed: no tool currently calls `_say_status`
directly, and selection's blocked-edit messages still use its signal.

### Paint: `ctx.paint`

A proposed `viewport/appearance.gd` owns the wood library, paint selection,
`current_name() -> String` and `apply(targets) -> void`. Lift the current
`main.gd:paint` command there, using document.next_id/append/sync and a status
signal connected to Main's `_say_status`. Menus retain their layout in Main
and ask appearance to select a wood; selecting still activates Paint.
This adapter exposes no library map/material resources and preserves the
empty/invalid target checks and existing status text. Keep `_turn_grain` a
keyboard/menu action; it is not a Paint-tool dependency. Main's remaining
wood/render consumers can migrate to this same owner without being given to
tools. Source: `main.gd:_load_wood_library`, `set_paint_material`, `paint`, `_turn_grain`;
`paint_tool.gd:hint`, `click`.

### Static geometry and test-only facilities

Move the exact existing static functions to `viewport/tool_geometry.gd`,
preloaded by tools and by inference/presenter where needed: `m2g`, `g2m`,
`n_g2m`, `arr3`, `clean_normal`, `plane_basis`, `rect_points` (old `_rect_pts`),
`edge_key` (old `_ekey`), `axis_vector` (old `_axis_vec`), `prism`, `prism_by`,
`feature_edges`, `unique_verts`, `reflect_point`, `reflect_tris`,
`mirror_triangles` (old `_mirror_tris`), plus their transitive pure helper
functions such as `r3`. Preserve `arr3`'s current 0.001 rounding; changing it is
outside this refactor. Move rendering constants `DEFAULT_BASE`, `AXIS_COLORS`,
`SNAP_COLORS` to presenter; grid/snap settings to inference's supplied options.
Tool's distance/gesture constants stay in tool.gd. No `preload(main.gd)` remains
in tools or the new context/geometry scripts; avoid global class_name and use
preload/path types as in the folder guide. Main may keep static wrappers while
existing tests/other production consumers migrate.

`force_reject_next`, `test_mode` and `draft_bboxes` are not production tool
capabilities. Move consumes no test flags; presenter records draft bounds in
test mode. The Push rejection hook becomes a private injected pre-append
filter configured only in test setup, preserving its exact one-shot behaviour:
only a Push/Pull op targeting a profile consumes the flag and replaces its
target with `r_missing`. Do not apply that filter to rect/circle ops simply
because they share profile IDs. Keep a test compatibility setter on Main until
`tests/quick/reject.gd` is migrated. Source: `push_tool.gd:commit_push`;
`tests/quick/reject.gd:run`.

## Edit sequence and state writes to remove

Preserve the synchronous sequence used today: validate gesture; clear rejection
where currently done; allocate IDs; construct op; append; register profile or
present draft and wave; clear the tool's gesture/visuals; sync. Paint currently
syncs before its status message; keep that ordering too. No wait for FreeCAD,
no network call from a tool, no protocol/version/op-schema change. Presenter
installs collision and triangle/edge/vertex caches before sync returns so the
next gesture can pick a just-created board. Reset/cancel must clear all
applicable preview channels without deleting a committed draft or wave.

| Existing write | Owner request replacing it |
|---|---|
| counters increments, ops.append; Move's ops scan | document.next_id, append, op snapshot |
| drafts maps/root creation, body_tris/verts/edges writes | view.present_draft, with caches installed together |
| bodies_root visibility and wave material/node edits | view.present_draft; presenter handles confirmed attachments |
| profile draft queue_free/erase | view.present_draft consumes the push target profile |
| overlay/outline mesh, marker transform/material, guides mesh | view preview/marker/guide commands |
| Select Panel and push highlight via Main.add_child | view selection_box / face_highlight |
| draft_bboxes / force_reject_next | presenter test recorder / injected Push-only test filter |
| reject_note | ui.clear_rejection; Main retains rejection handling |

Selection changes already use owner methods. `mat_plane.duplicate()` currently
creates a local copy rather than mutating Main's plane material; it still moves
behind view.mirror_preview to keep rendering resources private. There are no
tool writes to selection/context maps or measurement text today.

## Tests and incremental delivery

Keep Main's existing aliases as compatibility for the test harness and other
production consumers during migration. They are not in ToolContext and are not
an excuse for a migrated tool to retain Main. Examples: `tests/harness.gd:_fresh`
seeds m.ops and calls m.sync; quick tests inspect m.ops, m.tools, geometry,
selection, `draft_bboxes`, `move_state`, `hover` and injected cursor events.
Continue creating real tools from the same registry; direct calls such as
Select.box_ids and push.coplanar_region retain their signatures.
Keep measure_box's stale-value guards (`model`, `seq`, `tool`, gesture `state`)
and keys.gd's busy/in_gesture dispatch intact; this job does not redesign typed
values or tool reset semantics. These modules may still know Main; tools cannot.

Add headless contract checks during implementation for snapshot isolation,
ID sequences, appending without premature sync, remove signalling, and the
one-shot rejection filter. Add equivalence checks for ray/project conversion
and presentation cache/collision installation; use existing named UI checks
for behaviour rather than duplicating whole suites. Extend registry/export
checks to instantiate tools with ToolContext. A source check should reject
`m.*`, Main preload/static calls, raw owner fields and fallback `setup(Main)`
in migrated tools, finally including tool.gd; do not count comments as usage.
The adapter must have an explicit public member allowlist tested against the
listed surface. A thin facade with public raw controllers fails this check.

Each row below is a separate implementation step/commit, with `tools/gate.sh`
passing before proceeding. Run quicktest during development; if it fails, run
fulltest and report the cause. Do not update recorded references for a refactor.
Keep temporary compatibility visible and remove it only after all its consumers
are accounted for. Each step updates ARCHITECTURE.md and the relevant folder
guide for the implemented boundary, not this entire proposal in advance.

| Step | Work and what leaves Main | Checks with special relevance |
|---|---|---|
| 0. Foundation | Introduce context/adapters and pure geometry; implement explicit inference inputs. Main wires dependencies. Private adapters may initially call existing Main helpers through narrowly bound callables; lift each helper/resource body to its owner when its first tool migrates below. Paint ownership moves at step 1. Legacy tools keep their current setup until their step. | Parse all scripts (no preload cycle), controller/selection/registry tests, exported pack registry check, gate; API/snapshot/equivalence checks. |
| 1. Paint | First real context-only tool. Remove paint command/library state from Main into appearance; menu and grain consumers use that owner. Retain needed compatibility aliases. | Paint/family/assembly and wood/grain checks, status wording, gate. |
| 2. Select | Migrate reads to model/selection/pick, move box Panel to presenter. Move unit_tris implementation out of Main (wrapper may stay). | Box direction, crossing triangles, behind-camera points, additive and Esc restoration, context/hidden/deleted cases; gate. |
| 3. Circle | Use ray/snap/model/view/document. Remove tool dependency on Main._register_rect, counters, overlays and mesh helpers; most are still wrappers needed elsewhere. No additional Main body can be deleted safely just because Circle no longer uses it. | Existing circle gesture/unit/exact worker-radius and draft prediction checks, P21; gate. |
| 4. Rectangle | Same profile interface. Move `_rect_pts` body to geometry if not done at step 0; delete only wrappers with no remaining consumers. | Zero-side snap fallback, tilted plane and typed fractional/sub-mm dimensions, gate. |
| 5. Push/Pull | Move committed-draft construction, wave attachments, face-highlight lifetime and Push test hook out of Main/tool writes. Main's draft bounds and rendering aliases can disappear only once Move/tests no longer require them. | New/join/cut/through, exact circles, plane-fit modes and face cycling, rejection/dependent rollback, immediate draft picking, gate. |
| 6. Move | Migrate the largest tool last; rendering/cache/wave work goes through presenter, ops/IDs through document, relationship queries through selection. Move guide/marker bodies out of Main if not already lifted; remove Main preload/setup from base and all tools. | Single/multi move/copy/mirror, row/assembly copy and detachment, cut arrays, amendments, undo/redo, late replies, draft collisions, gate. |
| 7. Consumer cleanup | Audit tests, inference, presenter and panels for every Main forwarding alias. Migrate test fixture setup/inspection through harness helpers using owners, then delete unused tool-era aliases. Keep wrappers still serving real non-tool consumers or give their removal a named follow-on; no claim Main is now only wiring. | Entire gate and exported-app registry check; no baseline changes; source/API checks cover all tools. |

Foundation must not move all six tool implementations in one commit. Introduce a
context-only setup helper alongside legacy setup for staged migration, or pass
legacy Main only to unmigrated tools using an explicit temporary marker checked
by registry tests. Remove the migration marker and fallback at step 6. Main
must never acquire a hard-coded list of migrated tool IDs (A34).

Main will still own worker/window lifecycle, menus, camera navigation, keyboard
and measurements wiring, and rejection coordination. Eliminating tools' reach
into it is measurable; promising a particular line count is not. Main aliases
used by panels/tests and presenter's remaining non-tool callbacks need the
consumer audit before deletion. This spec is not an authorization for unrelated
protocol/save or test-runner changes (H045 owns the latter).

## Where H046 (Line) fits, and open questions

Keep H046 queued through T88 steps 0–6 and their gates; then integrator reviews
that every existing tool uses the boundary and makes H046 Ready. Consumer
cleanup may be a separate assigned job if it does not change the new interface.
Line must use the same context from its first file; it must not restore Main
access. Its implementation can add geometry queries/presentation commands to
their owning capabilities for loose lines/regions, with named tests and a gate;
it must not expose mutable cache maps. The pending H046 spec already assigns
regions.gd to pure region finding, presenter to display, inference to snapping,
and worker to authoritative solid results. Keep that division and P21's area/
bounds comparison. Exact Line-specific payloads belong to H046's design, not
this read-only inventory of today's tools.

No behaviour question for William is forced by the present code. The choices
above are proposed implementation boundaries for integrator review, not new
logged product decisions. H046 still needs William's key and drawing-gesture
answers when it becomes Ready; do not infer those answers from this spec.
