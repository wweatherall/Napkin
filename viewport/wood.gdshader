// Wood on a board (T15): the face texture runs along the board's grain; faces the grain runs into show end grain.
// The meshes have no UVs: both maps are laid out from world position along the board's own axes, so a board that
// grows or gets a hole keeps its figure where it was.
// End grain: a band of rings meant to run across the board's width, mirrored at every repeat so the seams meet.
shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D side_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D end_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform vec3 grain = vec3(1.0, 0.0, 0.0);      // world (Godot) direction of the grain
uniform vec3 across = vec3(0.0, 0.0, 1.0);     // world direction across the board's width
uniform float side_size = 0.6;                 // metres the face texture covers
uniform bool side_grain_v = false;             // the face texture's grain runs along its v (else u)
uniform float end_size = 0.175;                // metres the end band covers across the width
uniform float end_aspect = 0.55;               // the end band's height / width
uniform vec2 offset = vec2(0.0);               // per board, so copies don't look stamped
uniform vec4 base_color : source_color = vec4(0.8, 0.65, 0.45, 1.0);

varying vec3 wpos;
varying vec3 wnrm;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

float mirrored(float x) {         // 0 -> 1 -> 0 ...: each repeat is the last one flipped
	return 1.0 - abs(fract(x * 0.5) * 2.0 - 1.0);
}

void fragment() {
	vec3 g = normalize(grain);
	vec3 n = normalize(wnrm);
	vec3 col;
	if (abs(dot(n, g)) > 0.7) {
		vec3 w = normalize(across - g * dot(across, g));
		vec3 t = cross(g, w);
		vec2 p = vec2(dot(wpos, w), dot(wpos, t)) / end_size + offset;
		col = texture(end_tex, vec2(mirrored(p.x), mirrored(p.y / end_aspect))).rgb;
	} else {
		vec3 a = normalize(cross(n, g));
		vec2 p = vec2(dot(wpos, g), dot(wpos, a)) / side_size + offset;
		col = texture(side_tex, side_grain_v ? p.yx : p).rgb;
	}
	ALBEDO = col;
	ROUGHNESS = 0.72;
	SPECULAR = 0.35;
}
