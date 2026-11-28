"""Outputs for the viewport and renders: bodies.json entries, mesh files, model.glb, the TechDraw page.

`board_mesh_file` writes `meshes/<board>-<key>.bin` (packed pos, normal, edges, corners; change with
`presenter.gd:_build_board`). `write_glb` skips hidden boards and writes PBR base-colour materials plus custom
material/node extras (`grain_zup`, `across_zup`) for a Blender consumer.
Entry points: mesh_of, board_mesh_file, write_glb, cuts_of, add_drawing_page."""
import FreeCAD as App
import Part
import hashlib
import json
import os
import struct
import materials as wood
from common import HERE, V


def to_world(model, obj, shape):
    """A shape in a board's own frame, as it appears for this body (instance / mirrored copy)."""
    if model.is_mirror(obj):
        return to_world(model, model.mirror_source(obj), shape).mirror(obj.Base, obj.Normal)
    s = shape.copy()
    s.transformShape(obj.Placement.toMatrix())
    return s


def cuts_of(model, obj):
    """Each cut-out / added piece on a board, one entry per solid (an array gives one per copy)."""
    dfn = model.definition(obj)
    out = []
    for f in getattr(dfn, "Group", []):
        # only cut-outs made from a drawn rectangle (holes, pockets, dados) can be grabbed and moved:
        # a whole face pushed in or out, or an added piece, is the board itself as far as Move is concerned
        if f.TypeId != "Part::Cut" or not getattr(f, "SSOp", ""):
            continue
        for tool in model.tools_of(f):
            if tool is None or tool.Shape.isNull():
                continue
            cutter = tool.Base if model.is_array(tool) else tool
            if getattr(getattr(cutter, "Base", None), "TypeId", "") != "Part::Plane":
                continue
            board_bb = model.world_shape(obj).BoundBox
            for sol in to_world(model, obj, tool.Shape).Solids:
                bb = sol.BoundBox
                if bb.intersect(board_bb):
                    bb = bb.intersected(board_bb)
                out.append({"op": getattr(cutter, "SSOp", "") or f.SSOp, "kind": "cut",
                            "lo": [bb.XMin, bb.YMin, bb.ZMin], "hi": [bb.XMax, bb.YMax, bb.ZMax]})
    return out


def material_of(model, obj):
    return getattr(model.definition(obj), "SSMaterial", "") or ""


def component_of(model, obj):
    if model.is_mirror(obj):
        base = component_of(model, model.mirror_source(obj))
        return f"{base} (mirrored)" if base else None
    return (getattr(obj.LinkedObject, "ComponentName", "") or None) if model.is_instance(obj) else None


# ---------- glTF writer (pure python, flat-shaded, mm -> m, Z-up -> Y-up) ----------
PALETTE = {
    "white oak": (0.78, 0.64, 0.45),
    "western red cedar": (0.66, 0.38, 0.24),
    "": (0.82, 0.80, 0.76),
}


def material_color(key):
    if key in wood.SPECIES:
        return wood.SPECIES[key][10]
    return PALETTE.get(key, (0.7, 0.7, 0.7) if key else PALETTE[""])


_MESH_CACHE = {}


def shape_key(obj):
    """Identity of a board's world geometry, from FreeCAD's own shape handles: it changes exactly
    when a feature recomputes or a placement moves (about 10 us, versus ms for any geometric check)."""
    t = obj.TypeId
    if t == "App::Link":
        lo = obj.LinkedObject
        return ("L", shape_key(lo)[1:] if lo is not None else None, str(obj.Placement))
    if t == "App::Part":
        tip = getattr(obj, "Tip", None)
        return ("P", obj.Name, tip.Name if tip is not None else None,
                tip.Shape.hashCode() if tip is not None else 0, str(obj.Placement))
    shp = getattr(obj, "Shape", None)
    return ("S", obj.Name, shp.hashCode() if shp is not None else 0, str(getattr(obj, "Placement", "")))


_ENTRY_CACHE = {}


def mesh_of(bid, obj, model):
    """Tessellate a board only when its world shape changed since the last export."""
    sig = shape_key(obj)
    hit = _MESH_CACHE.get(bid)
    if hit and hit[0] == sig:
        return hit[1]
    verts, tris = model.world_shape(obj).tessellate(0.1)
    pos, nor = [], []
    for a, b, c in tris:
        pa, pb, pc = verts[a], verts[b], verts[c]
        n = (pb - pa).cross(pc - pa)
        n = n.normalize() if n.Length > 1e-12 else V(0, 0, 1)
        for p in (pa, pb, pc):
            pos += [p.x / 1000, p.z / 1000, -p.y / 1000]
            nor += [n.x, n.z, -n.y]
    packed = None
    if pos:
        xs, ys, zs = pos[0::3], pos[1::3], pos[2::3]
        packed = (struct.pack(f"<{len(pos)}f", *pos), struct.pack(f"<{len(nor)}f", *nor), len(pos) // 3,
                  [min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)])
    _MESH_CACHE[bid] = (sig, packed)
    return packed


# ---------- per-board mesh files for the viewport (T3) ----------
_MESH_FILES = {}    # (outdir, board id) -> the file currently describing it


def _pv3(points):
    """Points as a Godot PackedVector3Array in Godot's own binary format (var_to_bytes): the viewport reads
    it with one native call. Type 36, count, then float32 x y z."""
    flat = []
    for p in points:
        flat += (p[0], p[1], p[2])
    return struct.pack("<II", 36, len(points)) + struct.pack(f"<{len(flat)}f", *flat)


def board_mesh_file(bid, obj, model, outdir):
    """The board's file, written only when its shape changed: triangles and normals (model mm, Z-up; listed
    clockwise from outside, as Godot draws front faces), then FreeCAD's own edges and corners for snapping."""
    key = hashlib.sha1(repr(shape_key(obj)).encode()).hexdigest()[:16]
    name = f"{bid}-{key}.bin"
    folder = os.path.join(outdir, "meshes")
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        ws = model.world_shape(obj)
        verts, tris = ws.tessellate(0.1)
        pos, nor = [], []
        for a, b, c in tris:
            pa, pb, pc = verts[a], verts[b], verts[c]
            n = (pb - pa).cross(pc - pa)
            n = n.normalize() if n.Length > 1e-12 else V(0, 0, 1)
            pos += (pa, pc, pb)
            nor += (n, n, n)
        edges = []
        for e in ws.Edges:
            if isinstance(e.Curve, Part.Line) and len(e.Vertexes) == 2:
                pts = [e.Vertexes[0].Point, e.Vertexes[1].Point]
            else:
                pts = e.discretize(Deflection=0.1)
            for i in range(len(pts) - 1):
                edges += (pts[i], pts[i + 1])
        corners = [v.Point for v in ws.Vertexes]
        os.makedirs(folder, exist_ok=True)
        with open(path + ".tmp", "wb") as f:
            f.write(_pv3(pos) + _pv3(nor) + _pv3(edges) + _pv3(corners))
        os.replace(path + ".tmp", path)
    old = _MESH_FILES.get((outdir, bid))
    if old and old != name:
        try:
            os.remove(os.path.join(folder, old))
        except OSError:
            pass
    _MESH_FILES[(outdir, bid)] = name
    return name


def write_glb(model, path):
    bin_parts, accessors, views, meshes, nodes, mats = [], [], [], [], [], []
    mat_index = {}
    offset = 0

    def add_view(data, target):
        nonlocal offset
        pad = (-len(data)) % 4
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(data), "target": target})
        bin_parts.append(data + b"\x00" * pad)
        offset += len(data) + pad
        return len(views) - 1

    for bid, obj in model.bodies().items():
        if getattr(obj, "SSHidden", False):
            continue                                  # hidden boards stay out of renders (T28, I37)
        mesh = mesh_of(bid, obj, model)
        if mesh is None:
            continue
        pdata, ndata, count, lo, hi = mesh
        pv = add_view(pdata, 34962)
        accessors.append({"bufferView": pv, "componentType": 5126, "count": count, "type": "VEC3",
                          "min": lo, "max": hi})
        pa_i = len(accessors) - 1
        nv = add_view(ndata, 34962)
        accessors.append({"bufferView": nv, "componentType": 5126, "count": count, "type": "VEC3"})
        na_i = len(accessors) - 1
        m = material_of(model, obj)
        if m not in mat_index:
            r, g, b = material_color(m)
            mat = {"name": m or "unassigned",
                   "pbrMetallicRoughness": {"baseColorFactor": [r, g, b, 1], "metallicFactor": 0, "roughnessFactor": 0.8}}
            if m in wood.SPECIES:                     # for a Blender set-up: the textures and their real size (T15)
                sp = wood.SPECIES[m]
                tdir = os.path.normpath(os.path.join(HERE, "..", "materials", "textures"))
                mat["extras"] = {"wood": sp[0], "texture": os.path.join(tdir, sp[7] + ".jpg"),
                                 "texture_grain_along": sp[8], "texture_size_mm": sp[9],
                                 "end_texture": os.path.join(tdir, m + "_end.jpg"), "end_size_mm": wood.END_SIZE_MM}
            mats.append(mat)
            mat_index[m] = len(mats) - 1
        meshes.append({"name": bid, "primitives": [{"attributes": {"POSITION": pa_i, "NORMAL": na_i},
                                                    "material": mat_index[m]}]})
        nodes.append({"name": bid, "mesh": len(meshes) - 1,
                      "extras": {"body_id": bid, "material": m, "component": component_of(model, obj),
                                 "grain_zup": list(model.grain_world(obj)), "across_zup": list(model.grain_world(obj, "across")),
                                 "state": "confirmed"}})

    tmp = path + ".tmp"
    if not nodes:  # nothing solid yet (e.g. only rectangles): valid, empty glTF
        js = json.dumps({"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": []}]}).encode()
        js += b" " * ((-len(js)) % 4)
        with open(tmp, "wb") as f:
            f.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js)))
            f.write(struct.pack("<I4s", len(js), b"JSON")); f.write(js)
        os.replace(tmp, path)
        return
    gltf = {"asset": {"version": "2.0", "generator": "Napkin worker 0.2"},
            "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}],
            "nodes": nodes, "meshes": meshes, "materials": mats,
            "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": offset}]}
    js = json.dumps(gltf).encode()
    js += b" " * ((-len(js)) % 4)
    binblob = b"".join(bin_parts)
    total = 12 + 8 + len(js) + 8 + len(binblob)
    with open(tmp, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(js), b"JSON")); f.write(js)
        f.write(struct.pack("<I4s", len(binblob), b"BIN\x00")); f.write(binblob)
    os.replace(tmp, path)


# ---------- TechDraw page ----------
def add_drawing_page(doc, objs):
    import TechDraw  # noqa: F401  (registers types)
    import glob
    page = doc.addObject("TechDraw::DrawPage", "Drawing")
    tpl = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
    cands = glob.glob(os.path.join(App.getResourceDir(), "Mod/TechDraw/Templates/**/A3_Landscape_blank.svg"),
                      recursive=True)
    if cands:
        tpl.Template = cands[0]
    page.Template = tpl
    views = {}
    for name, direction, xdir, pos in [
        ("Front", V(0, -1, 0), V(1, 0, 0), (150, 190)),
        ("Top", V(0, 0, 1), V(1, 0, 0), (150, 90)),
        ("Right", V(1, 0, 0), V(0, 1, 0), (330, 190)),
        ("Iso", V(1, -1, 1), V(1, 1, 0), (330, 90)),
    ]:
        v = doc.addObject("TechDraw::DrawViewPart", name)
        page.addView(v)
        v.Source = objs
        v.Direction = direction
        v.XDirection = xdir
        v.Scale = 1.0
        v.X, v.Y = pos
        views[name] = v
    doc.recompute()
    return page, views


def remove_drawing_pages(doc):
    """Drawing pages are regenerated in the saved copy; the live document stays model-only."""
    # Views first, then templates, then pages, by name, skipping any already gone: FreeCAD 1.1.4 deletes a page's
    # views and template along with it, and removing an object that's already deleted crashes FreeCAD (bus error).
    rank = lambda o: 2 if o.TypeId == "TechDraw::DrawPage" else 1 if "Template" in o.TypeId else 0
    doomed = [o.Name for o in sorted((o for o in doc.Objects if o.TypeId.startswith("TechDraw::")), key=rank)]
    for name in doomed:
        if doc.getObject(name) is None:
            continue
        try:
            doc.removeObject(name)
        except Exception:
            pass
    return bool(doomed)
