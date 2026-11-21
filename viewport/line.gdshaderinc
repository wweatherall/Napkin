// Shared by every line shader: a segment is drawn as a thin strip facing the camera, a fixed number of
// pixels wide whatever the distance, with a soft edge (anti-aliasing). Plain GL lines are one pixel wide,
// get no anti-aliasing and thin out to nothing at a distance or a shallow angle.
//
// Each segment is 4 vertices: VERTEX = this end, CUSTOM0.xyz = the other end,
// UV.x = which end (0 = A, 1 = B), UV.y = which side of the strip (-1 / +1).
// Like overlay.gdshader, the strip is pulled toward the camera along the line of sight (bias, a fraction
// of its distance), so edges lying on a face, and the axes lying on the grid, always win the depth test.

const float LINE_AA_PX = 1.0;          // width of the soft edge, pixels
const float LINE_NEAR = 0.006;         // clip segments just beyond the camera's near plane (0.005 m)

vec4 line_position(vec3 here, vec3 there, vec2 uv, mat4 modelview, mat4 projection, vec2 viewport,
		float width_px, float bias, out float half_px) {
	vec4 va = modelview * vec4(uv.x < 0.5 ? here : there, 1.0);
	vec4 vb = modelview * vec4(uv.x < 0.5 ? there : here, 1.0);
	// a segment running behind the camera: move its far end onto the near plane (else the strip flips)
	if (va.z > -LINE_NEAR && vb.z <= -LINE_NEAR) va = mix(va, vb, (va.z + LINE_NEAR) / (va.z - vb.z));
	if (vb.z > -LINE_NEAR && va.z <= -LINE_NEAR) vb = mix(vb, va, (vb.z + LINE_NEAR) / (vb.z - va.z));
	va.xyz *= (1.0 - bias);
	vb.xyz *= (1.0 - bias);
	vec4 ca = projection * va;
	vec4 cb = projection * vb;
	vec2 half_vp = viewport * 0.5;
	vec2 sa = ca.xy / ca.w * half_vp;
	vec2 sb = cb.xy / cb.w * half_vp;
	vec2 dir = sb - sa;
	dir = length(dir) > 1e-6 ? normalize(dir) : vec2(1.0, 0.0);
	vec2 perp = vec2(-dir.y, dir.x);
	half_px = width_px * 0.5 + LINE_AA_PX;
	vec4 c = uv.x < 0.5 ? ca : cb;
	vec2 off = perp * uv.y * half_px + dir * (uv.x < 0.5 ? -half_px : half_px) * 0.5;
	c.xy += off / half_vp * c.w;
	return c;
}

// coverage across the strip: 1 in the middle, soft over LINE_AA_PX at the edge
float line_coverage(float side, float half_px, float width_px) {
	float d = abs(side) * half_px;
	return clamp(width_px * 0.5 + 0.5 * LINE_AA_PX - d, 0.0, 1.0);
}
