extends RefCounted
## Rejection handling: status notes, forced-rejection test hook, and rejection-wave cleanup (`m.rejections`).
## `m.rejections`; main.gd forwards `reject_note`, `last_reject_note`, `force_reject_next`, and `_on_rejected`
## so `history.gd`, tools, and tests don't change.
## Entry points: _on_wave_rejected_done, _on_rejected.

var m                               # main.gd: doc, pres, op_waves
var reject_note := ""
var last_reject_note := ""          # the latest rejection message (kept for tests; the status bar clears on your next action)
var force_reject_next: bool:
	get: return m.pres.draft_tests.reject_next
	set(v): m.pres.draft_tests.reject_next = v


func _init(main = null) -> void:
	m = main


func _on_wave_rejected_done(oid: String) -> void:
	var ids: Array = m.doc.rejected_ids(oid)
	if not ids.is_empty():                              # a rejection: it goes with the actions that built on it
		m.doc.remove_ops(ids)
	else:
		var w: Dictionary = m.op_waves[oid]
		if not w.get("dependent", false) or not m.op_waves.has(w["root"]):
			m.doc.remove_op(oid)                          # ends the wave, frees the draft, resyncs


func _on_rejected(o: Dictionary, w, drop_now: Array) -> void:
	var res: Dictionary = m.doc.reject(o["id"], o.get("message", ""), Time.get_ticks_msec(), func(r): return m.op_waves.has(r), o.get("about", []))
	if res.is_empty(): return
	reject_note = res["note"]
	if not res["joined"]:
		if w != null: w["state"] = "rejected"        # red wave plays, then it goes with its dependents
		else: drop_now.append(o["id"])
		return
	last_reject_note = reject_note
	if w != null:
		w["state"] = "rejected"; w["dependent"] = true; w["root"] = res["root"]
	if not m.op_waves.has(res["root"]):                # its rejection has already played: remove it now
		drop_now.append(o["id"])
