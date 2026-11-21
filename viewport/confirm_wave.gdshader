// Operation wave. Starts the moment you finish an operation, spreading from the cursor.
// Runs to a hold point and breathes there until FreeCAD answers:
//   accepted -> completes into the real material
//   rejected -> a red wave travels back toward the cursor (new boards fade away; edits get a red ring)
shader_type spatial;
render_mode cull_disabled, depth_prepass_alpha;

uniform vec3 base_color : source_color = vec3(0.82, 0.80, 0.76);
uniform vec3 draft_color : source_color = vec3(0.95, 0.72, 0.30);
uniform vec3 pigment : source_color = vec3(0.36, 0.20, 0.10);
uniform vec3 reject_color : source_color = vec3(0.86, 0.18, 0.13);
uniform vec3 reject_pigment : source_color = vec3(0.42, 0.05, 0.04);
uniform float draft_alpha = 0.55;
uniform float from_draft = 1.0;        // 1 = new board (starts as draft), 0 = edit of an existing board
uniform vec3 origin;                   // world space, metres
uniform float t = 0.0;                 // forward wave time (held by the script while waiting)
uniform float tn = 0.0;                // free-running time: keeps the edge breathing while held
uniform float held = 0.0;              // 0..1 breathing envelope (smoothstep, set by the script)
uniform float bphase = 0.0;            // breathing phase, starts at 0 when the hold begins
uniform float duration = 0.8;
uniform float reach = 0.5;
uniform float reject_t = -1.0;         // seconds since the red return wave started (-1 = none)
uniform float reject_dur = 0.6;
uniform float cell_size = 0.016;
uniform float softness = 0.05;         // metres of blur across the colour front
uniform float pigment_strength = 0.4;

varying vec3 wpos;

vec3 hash3(vec3 p) {
	p = vec3(dot(p, vec3(127.1, 311.7, 74.7)), dot(p, vec3(269.5, 183.3, 246.1)), dot(p, vec3(113.5, 271.9, 124.6)));
	return fract(sin(p) * 43758.5453123);
}

float vnoise(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(mix(hash3(i).x, hash3(i + vec3(1, 0, 0)).x, f.x),
				   mix(hash3(i + vec3(0, 1, 0)).x, hash3(i + vec3(1, 1, 0)).x, f.x), f.y),
			   mix(mix(hash3(i + vec3(0, 0, 1)).x, hash3(i + vec3(1, 0, 1)).x, f.x),
				   mix(hash3(i + vec3(0, 1, 1)).x, hash3(i + vec3(1, 1, 1)).x, f.x), f.y), f.z);
}

float fbm(vec3 p) {
	float a = 0.5;
	float s = 0.0;
	for (int i = 0; i < 4; i++) {
		s += a * vnoise(p);
		p *= 2.03;
		a *= 0.5;
	}
	return s;
}

vec2 voronoi(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	float md = 8.0;
	float id = 0.0;
	for (int z = -1; z <= 1; z++)
	for (int y = -1; y <= 1; y++)
	for (int x = -1; x <= 1; x++) {
		vec3 g = vec3(float(x), float(y), float(z));
		vec3 r = g + hash3(i + g) - f;
		float d = dot(r, r);
		if (d < md) {
			md = d;
			id = hash3(i + g + 17.0).x;
		}
	}
	return vec2(sqrt(md), id);
}

// round, blurry pigment cells (gaussian from the cell centre, not the cell's polygon)
float soft_spots(vec2 v, float band) {
	float rad = mix(0.06, 0.42, band);
	return exp(-(v.x * v.x) / (rad * rad) * 2.0) * band;
}

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	float r = distance(wpos, origin);
	float wob = (fbm(wpos * 9.0 + vec3(0.0, tn * 0.5, tn * 0.2)) - 0.5) * 0.06;
	vec2 v = voronoi(wpos / cell_size);

	// forward wave: one smooth, noise-blurred front (no per-cell mosaic)
	// breathing is done by the script moving t back and forth, so the look never changes
	float front = (t / duration) * (reach + 0.1);
	float d = front - (r + wob);
	float k = smoothstep(-softness * 0.3, softness, d);
	float band = exp(-pow((d + (v.y - 0.5) * 0.02 - 0.02) / 0.035, 2.0));
	float spot = soft_spots(v, band);

	vec3 col = mix(mix(base_color, draft_color, from_draft), base_color, k);
	// edits carry a soft amber band on their front (moving or waiting, same look)
	col = mix(col, draft_color, band * (1.0 - from_draft) * 0.4);
	col = mix(col, pigment, spot * pigment_strength);
	float alpha = mix(mix(1.0, draft_alpha, from_draft), 1.0, smoothstep(0.0, softness, d));

	if (reject_t >= 0.0) {
		float rfront = (reject_t / reject_dur) * (reach + 0.1);
		float dr = rfront - ((reach + 0.05) - r + wob);     // travels inward, toward the cursor
		float kr = smoothstep(-softness * 0.3, softness, dr);
		float bandr = exp(-pow((dr + (v.y - 0.5) * 0.02 - 0.02) / 0.035, 2.0));
		float spotr = soft_spots(v, bandr);
		float red = from_draft > 0.5 ? max(kr * 0.8, bandr * 0.8) : bandr * 0.65;
		col = mix(col, reject_color, red);
		col = mix(col, reject_pigment, spotr * pigment_strength);
		if (from_draft > 0.5) {
			float fade = smoothstep(0.65, 1.0, reject_t / reject_dur);
			alpha = mix(alpha, draft_alpha, kr) * (1.0 - fade);
		}
	}
	ALBEDO = col;
	ALPHA = alpha;
	ROUGHNESS = 0.85;
}
