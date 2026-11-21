// Edge lines follow the same fronts as confirm_wave.gdshader.
shader_type spatial;
render_mode unshaded, depth_prepass_alpha;

uniform vec3 origin;
uniform float t = 0.0;
uniform float tn = 0.0;
uniform float held = 0.0;
uniform float bphase = 0.0;            // breathing phase, starts at 0 when the hold begins
uniform float duration = 0.8;
uniform float reach = 0.5;
uniform float from_draft = 1.0;
uniform float reject_t = -1.0;
uniform float reject_dur = 0.6;
uniform float softness = 0.05;
uniform vec3 draft_edge : source_color = vec3(0.6, 0.35, 0.0);
uniform vec3 final_edge : source_color = vec3(0.08, 0.08, 0.08);
uniform vec3 reject_edge : source_color = vec3(0.7, 0.08, 0.05);

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	float r = distance(wpos, origin);
	float d = (t / duration) * (reach + 0.1) - r;
	vec3 col = mix(mix(final_edge, draft_edge, from_draft), final_edge, smoothstep(-softness * 0.3, softness, d));
	float alpha = 1.0;
	if (reject_t >= 0.0) {
		float dr = (reject_t / reject_dur) * (reach + 0.1) - ((reach + 0.05) - r);
		float kr = smoothstep(-softness * 0.3, softness, dr);
		float bandr = exp(-pow((dr - 0.02) / 0.035, 2.0));
		col = mix(col, reject_edge, from_draft > 0.5 ? kr : bandr);
		if (from_draft > 0.5) alpha = 1.0 - smoothstep(0.65, 1.0, reject_t / reject_dur);
	}
	ALBEDO = col;
	ALPHA = alpha;
}
