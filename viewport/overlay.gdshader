// Highlights and drafts that lie exactly on a board's face. Each vertex is pulled toward the camera
// along its own line of sight (by OVERLAY_BIAS of its distance): nothing moves on screen, but the
// overlay always wins the depth test against the face beneath it. Rendering only: picking is unaffected.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_mix;

uniform vec4 color : source_color = vec4(0.35, 0.55, 0.95, 0.35);
uniform float bias = 0.001;

void vertex() {
	vec4 v = MODELVIEW_MATRIX * vec4(VERTEX, 1.0);
	v.xyz *= (1.0 - bias);
	POSITION = PROJECTION_MATRIX * v;
}

void fragment() {
	ALBEDO = color.rgb;
	ALPHA = color.a;
}
