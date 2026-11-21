// Lines: board edges, rectangle outlines, previews, guides, the grid and the axes (see line.gdshaderinc).
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_mix, shadows_disabled;

#include "res://line.gdshaderinc"

uniform vec4 color : source_color = vec4(0.08, 0.08, 0.08, 1.0);
uniform float width_px = 1.5;
uniform float bias = 0.001;
uniform float fade_start = 0.0;        // metres from the camera; 0 = no fade (the grid fades out with distance)
uniform float fade_end = 0.0;

varying float side;
varying float half_px;
varying float view_dist;

void vertex() {
	float hp;
	POSITION = line_position(VERTEX, CUSTOM0.xyz, UV, MODELVIEW_MATRIX, PROJECTION_MATRIX, VIEWPORT_SIZE,
			width_px, bias, hp);
	half_px = hp;
	side = UV.y;
	view_dist = -(MODELVIEW_MATRIX * vec4(VERTEX, 1.0)).z;
}

void fragment() {
	float a = color.a * line_coverage(side, half_px, width_px);
	if (fade_end > fade_start) a *= 1.0 - smoothstep(fade_start, fade_end, view_dist);
	ALBEDO = color.rgb;
	ALPHA = a;
}
