extends RefCounted
## Confirmation and rejection waves (W01–W09), `pres.waves`: runs the shader wave front on drafts/boards, breathes while FreeCAD works, and finishes or goes red.
##
## Owned and instantiated by presenter.gd, which keeps forwarders for main.gd, save_prompts.gd and tests
## (`op_waves`, `trace_wave`, `trace_rows`, `begin_wave`, `step_waves`).
## Entry points: begin_wave, attach_wave, end_wave, step_waves.

const Geo := preload("res://tool_geometry.gd")
const WAVE := preload("res://confirm_wave.gdshader")
const WAVE_LINES := preload("res://confirm_wave_lines.gdshader")

const HOLD := 0.6          # fraction of the forward wave that runs before FreeCAD must have answered
const REJECT_DUR := 0.6
const SLOW := 0.35         # progress distance over which the front slows into the hold (longer = gentler)
const TAU := 0.12          # seconds, per smoothing stage
const TAU_UP := 0.20       # seconds, per stage, when speeding back up after FreeCAD accepts
const LEAD := 0.10         # seconds of look-ahead in the controller (cancels overshoot from smoothing)
const AMP_COMP := 1.11     # smoothing shrinks the swing about 10%; aim wider so the front really spans BREATH_LO..HOLD
const BREATH_W := 2.4      # rad/s of the breathing (one glide back and forth = 2.6 s)
const BREATH_LO := 0.3     # breathing glides between BREATH_LO and HOLD of the full travel

var pres                   # presenter.gd
var op_waves := {}         # op id -> wave state
var trace_wave := ""       # test hook: record this op's front over time
var trace_rows: Array[String] = []


func _init(p) -> void:
	pres = p


func begin_wave(oid: String, origin_m: Vector3, tris: PackedVector3Array, is_new: bool, body) -> void:
	var og := Geo.m2g(origin_m)
	var reach := 0.0
	for p in tris:
		reach = maxf(reach, Geo.m2g(p).distance_to(og))
	var dur := clampf(reach / 0.7, 0.5, 1.0)
	op_waves[oid] = {"og": og, "reach": reach, "dur": dur, "tn": 0.0,
					 "p": 0.0, "v": 1.0 / dur, "v1": 1.0 / dur,   # progress (0..1), velocity, and the first smoothing stage
					 "hraw": 0.0, "held": 0.0, "t0": 0.0, "bphase": 0.0,
					 "rt": -1.0, "state": "pending", "new": is_new, "body": body if body is String else "",
					 "bodies": [body] if body is String else body, "links": []}


func attach_wave(oid: String, mi: MeshInstance3D, edges: MeshInstance3D, base: Color) -> void:
	var w: Dictionary = op_waves[oid]
	var draft: StandardMaterial3D = pres.m.mat_draft
	var sm := ShaderMaterial.new(); sm.shader = WAVE
	sm.set_shader_parameter("base_color", Color(base.r, base.g, base.b))
	sm.set_shader_parameter("draft_color", Color(draft.albedo_color.r, draft.albedo_color.g, draft.albedo_color.b))
	sm.set_shader_parameter("draft_alpha", draft.albedo_color.a)
	var lm := ShaderMaterial.new(); lm.shader = WAVE_LINES
	lm.set_shader_parameter("width_px", pres.LINE_PX * pres.m.line_scale)
	lm.set_shader_parameter("bias", pres.m.overlay_bias)
	for mat in [sm, lm]:
		mat.set_shader_parameter("origin", w["og"])
		mat.set_shader_parameter("reach", w["reach"])
		mat.set_shader_parameter("duration", w["dur"])
		mat.set_shader_parameter("reject_dur", REJECT_DUR)
		mat.set_shader_parameter("from_draft", 1.0 if w["new"] else 0.0)
	mi.material_override = sm
	if edges != null: edges.material_override = lm
	w["links"].append([mi, edges, sm, lm])
	_push_params(w)


func _push_params(w: Dictionary) -> void:
	var keep := []
	for l in w["links"]:
		if not is_instance_valid(l[0]): continue
		keep.append(l)
		for mat in [l[2], l[3]]:
			mat.set_shader_parameter("t", w["p"] * w["dur"])
			mat.set_shader_parameter("tn", w["tn"])
			mat.set_shader_parameter("reject_t", -1.0 if w["rt"] < 0.0 else smoothstep(0.0, 1.0, w["rt"] / REJECT_DUR) * REJECT_DUR)
			mat.set_shader_parameter("held", w["held"])
			mat.set_shader_parameter("bphase", w["bphase"])
	w["links"] = keep


func end_wave(oid: String) -> void:
	if not op_waves.has(oid): return
	for l in op_waves[oid]["links"]:
		if is_instance_valid(l[0]): l[0].material_override = null
		if is_instance_valid(l[1]): l[1].material_override = null
	op_waves.erase(oid)


func step_waves(delta: float) -> void:
	"""One frame of every wave: run, ease into the hold, breathe while FreeCAD works, finish or go red."""
	for oid in op_waves.keys():
		if not op_waves.has(oid): continue          # removed this frame along with a rejection it built on
		var w: Dictionary = op_waves[oid]
		var v0: float = 1.0 / w["dur"]
		w["tn"] += delta
		var parking: bool = w["state"] == "pending" or (w["state"] == "rejected" and w["rt"] < 0.0)
		var breathing: bool = w["bphase"] > 0.0
		# where the front wants to be: run free, ease to HOLD, then glide between BREATH_LO and HOLD
		var vdes := v0
		if parking:
			var goal: float = HOLD
			if w["state"] == "pending" and breathing:
				var mid := (HOLD + BREATH_LO) * 0.5
				goal = mid + (HOLD - mid) * AMP_COMP * cos(w["bphase"])   # zero slope at the start

			elif w["state"] == "rejected" and breathing:
				goal = w["p"]                                       # rejected mid-breath: settle where it is
			# aim from slightly ahead (LEAD) so the smoothing delay doesn't make it overshoot
			vdes = v0 * clampf((goal - (w["p"] + LEAD * w["v"])) / SLOW, -1.0, 1.0)
		var tau := TAU_UP if w["state"] == "ok" else TAU
		# two smoothing stages: v1 follows the command, v follows v1.
		# speed AND acceleration stay continuous, so there's no corner (no thud) anywhere.
		var k := 1.0 - exp(-delta / tau)
		w["v1"] += (vdes - w["v1"]) * k
		w["v"] += (w["v1"] - w["v"]) * k
		w["p"] += w["v"] * delta
		var stopped: bool = parking and absf(w["v"]) < 0.15 * v0
		if w["state"] == "pending" and (breathing or stopped):
			w["bphase"] += BREATH_W * delta                         # phase clock starts once the front has settled
		if w["state"] == "rejected":
			if w["rt"] >= 0.0 or stopped:
				w["rt"] = maxf(w["rt"], 0.0) + delta     # red wave eases in/out (smoothstep in _push_params)
		_push_params(w)
		if trace_wave != "" and oid == trace_wave:
			trace_rows.append("%.4f,%.6f,%.6f,%.4f,%s" % [w["tn"], w["p"], w["v"], w["reach"], w["state"]])
		if w["state"] == "ok" and w["p"] > 1.25:
			end_wave(oid)
		elif w["state"] == "rejected" and w["rt"] > REJECT_DUR + 0.1:
			pres.wave_rejected_done.emit(oid)        # main removes it, with what built on it
