"""Board-local face references for Napkin stock and extruded/cut boards.

`snapshot()` exports `fitted_end` on fitted boards and `rectangular: False` + `planar_faces` on non-rectangular/cut
boards. `_resolve_face()` stores target plane in target local frame (`SSTargetNormal`, `SSTargetPoint`) and rewrites
`SSFace`. `refit_inputs()` / `refit_changed()` propagate through chains and component families in one pass.
Entry points: snapshot, fitted_face, fitted_end, face_plane, _underlying_plane_fit, _recompute_chain, refit_inputs,
refit_changed, family_bodies."""
import math
import FreeCAD as App
import Part
from common import Frame

V = App.Vector
FACES = ('Left', 'Right', 'Front', 'Back', 'Bottom', 'Top')
MODES = ('Butt to plane', 'Slice at plane', 'Fully reach plane')
FIT_PAUSE_DEG = 2.0


def _unwrap_mirror(board):
    """Step through Part::Mirroring (and mirror-input compounds) to the underlying Part/Link."""
    cur = board
    while getattr(cur, 'TypeId', '') == 'Part::Mirroring':
        s = getattr(cur, 'Source', None)
        if getattr(s, 'SSRole', '') == 'mirror-input' and getattr(s, 'Links', None):
            s = s.Links[0]
        cur = s
    return cur


def _def(board):
    """Return (definition App::Part, world placement) for a plain board, component instance, or mirror, else (None, None)."""
    cur = _unwrap_mirror(board)
    t = getattr(cur, 'TypeId', '')
    if t == 'App::Part':
        return cur, cur.Placement
    if t == 'App::Link':
        dfn = getattr(cur, 'LinkedObject', None)
        if getattr(dfn, 'TypeId', '') == 'App::Part':
            return dfn, cur.Placement
    return None, None


def _target_frame(board):
    """common.Frame mapping world -> target's definition-local frame (through mirrors and component links)."""
    fr = Frame()
    cur = board
    while getattr(cur, 'TypeId', '') == 'Part::Mirroring':
        fr.mirror(cur.Base, cur.Normal)
        s = getattr(cur, 'Source', None)
        if getattr(s, 'SSRole', '') == 'mirror-input' and getattr(s, 'Links', None):
            s = s.Links[0]
        cur = s
    if getattr(cur, 'TypeId', '') == 'App::Link':
        fr.into(cur.Placement)
        cur = getattr(cur, 'LinkedObject', None)
    if getattr(cur, 'TypeId', '') == 'App::Part':
        fr.into(cur.Placement)
    return fr


def _frame_to_world(fr, pt, n):
    """Invert `fr` (definition-local -> world) for a point and unit normal."""
    p = V(pt)
    d = V(n)
    for step in reversed(fr.steps):
        if step[0] == 'mirror':
            p = p - step[2] * (2 * (p - step[1]).dot(step[2]))
            d = d - step[2] * (2 * d.dot(step[2]))
        else:
            inv_p = step[1].inverse()
            p = inv_p.multVec(p)
            d = inv_p.Rotation.multVec(d)
    if d.Length > 1e-12:
        d.normalize()
    return p, d


def _family_bodies(model, dfn, bodies=None):
    """All live body BodyIds whose definition is `dfn`."""
    if dfn is None:
        return []
    if bodies is None:
        bodies = model.bodies()
    if getattr(dfn, 'SSRole', '') == 'body' and getattr(dfn, 'BodyId', ''):
        return [dfn.BodyId] if dfn.BodyId in bodies else []
    return [bid for bid, obj in bodies.items() if _def(obj)[0] == dfn]


def family_bodies(model, board):
    """All live body BodyIds sharing `board`'s definition."""
    dfn, _ = _def(board)
    return _family_bodies(model, dfn)


def _driving_body(model, dfn, tip, bodies, promote=False):
    if getattr(dfn, 'SSRole', '') == 'body' and getattr(dfn, 'BodyId', '') in bodies:
        return dfn
    fam = _family_bodies(model, dfn, bodies)
    if not fam:
        return None
    non_mirror = [bid for bid in fam if getattr(bodies[bid], 'TypeId', '') != 'Part::Mirroring']
    if not non_mirror:
        return dfn if getattr(dfn, 'SSRole', '') in ('source', 'deleted') else None
    src_id = getattr(tip, 'SSSourceBodyId', '')
    if src_id in non_mirror:
        return bodies[src_id]
    src = bodies[non_mirror[0]]
    if promote:
        if 'SSSourceBodyId' not in tip.PropertiesList:
            tip.addProperty('App::PropertyString', 'SSSourceBodyId')
        tip.SSSourceBodyId = src.BodyId
    return src


def _dependent_bodies(dfn, bodies):
    """Live body BodyIds whose feature graph depends on `dfn` (e.g. a flip or mirror of a source/deleted board)."""
    seen = set()
    stack = [dfn]
    out = []
    while stack:
        cur = stack.pop()
        if cur.Name in seen:
            continue
        seen.add(cur.Name)
        for parent in getattr(cur, 'InList', ()):
            if getattr(parent, 'SSRole', '') == 'body' and getattr(parent, 'BodyId', '') in bodies:
                out.append(parent.BodyId)
            elif getattr(parent, 'TypeId', '') != 'App::DocumentObjectGroup':
                stack.append(parent)
    return out


def _active_tips(model, bodies, promote=False):
    """All live PlaneFit tips as (tip, dfn, driving_board, family_ids)."""
    out = []
    for tip in model.doc.Objects:
        if not hasattr(tip, 'SSFitResult') or not tip.SSTargetId:
            continue
        dfn = tip.getParentGeoFeatureGroup()
        if dfn is None:
            continue
        fam = _family_bodies(model, dfn, bodies)
        if not fam:
            if getattr(dfn, 'SSRole', '') in ('source', 'deleted'):
                dep_fam = _dependent_bodies(dfn, bodies)
                if dep_fam:
                    out.append((tip, dfn, dfn, dep_fam))
                    continue
            if promote:
                tip.SSTargetId = ''
                if hasattr(tip, 'SSSourceBodyId'):
                    tip.SSSourceBodyId = ''
            continue
        src = _driving_body(model, dfn, tip, bodies, promote=promote)
        if src is not None:
            out.append((tip, dfn, src, fam))
    return out


def _underlying_extrusion(obj):
    """Walk down Base/Shapes from a tip or boolean feature to its underlying Part::Extrusion, or None."""
    seen = set()
    cur = obj
    while cur is not None and cur.Name not in seen:
        seen.add(cur.Name)
        if getattr(cur, 'TypeId', '') == 'Part::Extrusion':
            return cur
        if hasattr(cur, 'Base'):
            cur = cur.Base
        elif getattr(cur, 'TypeId', '') == 'Part::MultiFuse' and getattr(cur, 'Shapes', None):
            cur = cur.Shapes[0]
        else:
            break
    return None


def _underlying_plane_fit(obj):
    """Walk down Base/Shapes from a tip or boolean feature to its underlying PlaneFit, or None."""
    seen = set()
    cur = obj
    while cur is not None and cur.Name not in seen:
        seen.add(cur.Name)
        if hasattr(cur, 'SSStock'):
            return cur
        if getattr(cur, 'TypeId', '') == 'Part::Mirroring' and getattr(cur, 'Source', None) is not None:
            cur = getattr(cur.Source, 'Tip', None)
        elif hasattr(cur, 'Base'):
            cur = cur.Base
        elif getattr(cur, 'TypeId', '') == 'Part::MultiFuse' and getattr(cur, 'Shapes', None):
            cur = cur.Shapes[0]
        else:
            break
    return None


def _is_straight_extrusion(ext):
    return (getattr(ext, 'TypeId', '') == 'Part::Extrusion'
            and getattr(ext, 'Base', None) is not None
            and not ext.LengthRev.Value and ext.Solid and not ext.Symmetric
            and not ext.TaperAngle.Value and not ext.TaperAngleRev.Value)


def _ortho_axes(direction):
    ref = V(1, 0, 0) if abs(direction.x) < 0.9 else V(0, 1, 0)
    u = direction.cross(ref)
    u.normalize()
    v = direction.cross(u)
    v.normalize()
    return u, v


def stock(board, feature=None):
    if getattr(board, 'TypeId', '') == 'Part::Mirroring':
        return
    dfn, placement = _def(board)
    if dfn is None:
        return
    tip = feature or getattr(dfn, 'Tip', None)
    ext = getattr(tip, 'SSStock', tip)
    if not _is_straight_extrusion(ext) or ext.Base.TypeId != 'Part::Plane':
        return
    base = ext.Base
    pose = placement.multiply(ext.Placement).multiply(base.Placement)
    axes = [pose.Rotation.multVec(v) for v in (V(1,0,0), V(0,1,0), V(0,0,1))]
    direction = placement.Rotation.multVec(ext.Placement.Rotation.multVec(ext.Dir))
    direction.normalize()
    if abs(direction.dot(axes[2])) < 0.999999:
        return
    axes[2] = direction
    return ext, pose.Base, axes, [base.Length.Value, base.Width.Value, ext.LengthFwd.Value]


def _source_frame_and_profile(board, feature=None):
    """Return ((ext, origin, axes, sizes), profile) for plain rectangular stock OR any board with a reachable Part::Extrusion."""
    rect = stock(board, feature)
    if rect is not None:
        return rect, None
    dfn, placement = _def(board)
    if dfn is None:
        return None, None
    tip = feature or getattr(dfn, 'Tip', None)
    base_tip = getattr(tip, 'SSStock', tip)
    ext = _underlying_extrusion(base_tip)
    if not _is_straight_extrusion(ext):
        return None, None
    ext_pose = placement.multiply(ext.Placement)
    direction = ext_pose.Rotation.multVec(ext.Dir)
    direction.normalize()
    base = ext.Base
    if base.TypeId == 'Part::Plane':
        pose = ext_pose.multiply(base.Placement)
        axes = [pose.Rotation.multVec(v) for v in (V(1, 0, 0), V(0, 1, 0))] + [direction]
        if abs(direction.dot(axes[0].cross(axes[1]))) < 0.999999:
            return None, None
        return (ext, pose.Base, axes, [base.Length.Value, base.Width.Value, ext.LengthFwd.Value]), None
    if base.TypeId == 'Sketcher::SketchObject':
        pose = ext_pose.multiply(base.Placement)
        u_ax = pose.Rotation.multVec(V(1, 0, 0))
        v_ax = pose.Rotation.multVec(V(0, 1, 0))
        u_sketch, v_sketch = u_ax, v_ax
        if abs(direction.dot(u_ax.cross(v_ax))) < 0.999:
            u_ax, v_ax = _ortho_axes(direction)
        if len(getattr(base, 'Geometry', [])) == 1 and base.Geometry[0].TypeId == 'Part::GeomCircle':
            g = base.Geometry[0]
            r = g.Radius
            center = pose.multVec(g.Center)
            origin = center - u_ax * r - v_ax * r
            frame = (ext, origin, [u_ax, v_ax, direction], [2 * r, 2 * r, ext.LengthFwd.Value])
            return frame, ('circle', center, u_sketch, v_sketch, r)
    else:
        u_ax, v_ax = _ortho_axes(direction)
    shape = getattr(base, 'Shape', None)
    if shape is None or shape.isNull() or not shape.Edges:
        return None, None
    pts = []
    for edge in shape.Edges:
        for p in edge.discretize(Deflection=0.25):
            pts.append(ext_pose.multVec(p))
    if not pts:
        return None, None
    us = [p.dot(u_ax) for p in pts]
    vs = [p.dot(v_ax) for p in pts]
    ws = [p.dot(direction) for p in pts]
    origin = u_ax * min(us) + v_ax * min(vs) + direction * min(ws)
    sizes = [max(max(us) - min(us), 1e-3), max(max(vs) - min(vs), 1e-3), ext.LengthFwd.Value]
    return (ext, origin, [u_ax, v_ax, direction], sizes), ('points', pts)


def source_frame(board, feature=None):
    """Return (ext, origin, axes, sizes) for plain rectangular stock OR any board with a reachable Part::Extrusion."""
    return _source_frame_and_profile(board, feature)[0]


def fitted_face(board):
    """The face index (0..5) of a fitted board's fitted end, or None."""
    dfn, _ = _def(board)
    tip = getattr(dfn, 'Tip', None)
    if not hasattr(tip, 'SSStock'):
        return None
    return 2 * tip.SSAxis + (0 if getattr(tip, 'SSReverse', False) else 1)


def planar_faces(target):
    """List of world (point, outward_normal) for planar faces of `target`.
    For plain rectangular stock, returns the 6 canonical faces (0..5).
    For non-rectangular or cut boards, returns deduplicated planar faces sorted in definition-local space."""
    frame = stock(target)
    if frame is not None:
        _, origin, axes, sizes = frame
        fe_idx = fitted_face(target)
        fe = fitted_end(target) if fe_idx is not None else None
        out = []
        for face in range(6):
            if fe_idx == face and fe is not None:
                out.append((fe[1], fe[0]))
            else:
                index, positive = divmod(face, 2)
                normal = axes[index]
                point = origin + normal * sizes[index] if positive else origin
                outward = normal if positive else -normal
                out.append((point, outward))
        return out
    if getattr(target, 'TypeId', '') == 'Part::Mirroring':
        shape = getattr(target, 'Shape', None)
        placement = App.Placement()
    else:
        dfn, placement = _def(target)
        tip = getattr(dfn, 'Tip', None)
        shape = getattr(tip, 'Shape', None)
        if dfn is None:
            return []
    if shape is None or shape.isNull():
        return []
    entries = []
    for f in shape.Faces:
        if getattr(f.Surface, 'TypeId', '') != 'Part::GeomPlane':
            continue
        u0, u1, v0, v1 = f.ParameterRange
        um, vm = 0.5 * (u0 + u1), 0.5 * (v0 + v1)
        n_loc = f.normalAt(um, vm)
        n_loc.normalize()
        pt_loc = f.valueAt(um, vm)
        if any(n_loc.dot(en) > 0.9999 and abs((pt_loc - ept).dot(n_loc)) < 1e-4 for _, ept, en in entries):
            continue
        key = (round(n_loc.x, 4), round(n_loc.y, 4), round(n_loc.z, 4), round(pt_loc.dot(n_loc), 4))
        entries.append((key, pt_loc, n_loc))
    entries.sort(key=lambda item: item[0])
    return [(placement.multVec(pt), placement.Rotation.multVec(n).normalize()) for _, pt, n in entries]


def face_plane(target, face):
    """World (point, outward_normal) for `face` of `target`, or None."""
    faces = planar_faces(target)
    if 0 <= face < len(faces):
        return faces[face]
    return None


def _target_local_plane(target, world_point, world_normal):
    """Convert a world (point, normal) to `target`'s definition-local frame."""
    fr = _target_frame(target)
    n_local = fr.dir(world_normal)
    if n_local.Length > 1e-12:
        n_local.normalize()
    return fr.pt(world_point), n_local


def _is_rect_target(target):
    """True if `target` is plain rectangular stock (or a mirror of plain rectangular stock)."""
    if stock(target) is not None:
        return True
    if getattr(target, 'TypeId', '') == 'Part::Mirroring':
        dfn, _ = _def(target)
        return dfn is not None and stock(dfn) is not None
    return False


def _along_dir(board, tip):
    """Unit world direction along the fitted board's fitted axis, from start toward fitted end."""
    src, _ = _source_frame_and_profile(board, tip)
    if not src:
        return None
    along = src[2][tip.SSAxis]
    return -along if getattr(tip, 'SSReverse', False) else along


def _resolve_face(target, tip, along=None):
    """Return (face_index, (world_point, world_normal), state) where state is 'live', 'paused', or 'detached'."""
    if target is None:
        return None, None, 'detached'
    faces = planar_faces(target)
    if not faces:
        return None, None, 'detached'
    n_local = getattr(tip, 'SSTargetNormal', None)
    if n_local is not None and n_local.Length > 1e-6:
        fr = _target_frame(target)
        want_pt, want_n = _frame_to_world(fr, tip.SSTargetPoint, n_local)
        if _is_rect_target(target) and along is not None:
            dot = along.dot(want_n)
            if abs(dot) <= math.sin(math.radians(FIT_PAUSE_DEG)):
                return None, None, 'paused'
            sign = int(getattr(tip, 'SSTargetSign', 0))
            if sign == 0:
                sign = 1 if dot > 0 else -1
            pick_n = want_n if (dot > 0 and sign > 0) or (dot < 0 and sign < 0) else -want_n
            matches = [(i, p) for i, p in enumerate(faces) if p[1].dot(pick_n) > 0.9999]
            if not matches:
                return None, None, 'detached'
            idx, pl = min(matches, key=lambda item: abs((item[1][0] - want_pt).dot(pick_n)))
            return idx, pl, 'live'
        matches = [(i, p) for i, p in enumerate(faces) if p[1].dot(want_n) > 0.9999]
        if not matches:
            return None, None, 'detached'
        ref_pt = want_pt
        is_cut_or_nonrect = stock(target) is None
        if is_cut_or_nonrect:
            t_dfn, _ = _def(target)
            pf_tip = _underlying_plane_fit(getattr(t_dfn, 'Tip', None)) if t_dfn is not None else None
            if pf_tip is not None and len(getattr(pf_tip, 'SSFitCorners', ())) == 8:
                fe = fitted_end(target, pf_tip)
                if fe is not None and fe[0].dot(want_n) > 0.9999:
                    ref_pt = fe[1]
        idx, pl = min(matches, key=lambda item: abs((item[1][0] - ref_pt).dot(want_n)))
        if is_cut_or_nonrect and abs((pl[0] - ref_pt).dot(want_n)) > 0.1:
            return None, None, 'detached'
        return idx, pl, 'live'
    face = int(getattr(tip, 'SSFace', -1))
    if 0 <= face < len(faces):
        return face, faces[face], 'live'
    return None, None, 'detached'


def snapshot(board):
    frame = stock(board)
    dfn, _ = _def(board)
    if dfn is None:
        return
    tip = getattr(dfn, 'Tip', None)
    if frame:
        ext, origin, axes, sizes = frame
        out = dict(label=board.Label, origin=list(origin), axes=[list(v) for v in axes], sizes=sizes,
                   plane=ext.Base.Name, extrusion=ext.Name, fitted=hasattr(tip,'SSStock'),
                   reverse=getattr(tip,'SSReverse',False), linked_axis=getattr(tip,'SSAxis',-1),
                   result=getattr(tip,'SSFitResult',''), rectangular=True)
    else:
        faces = planar_faces(board)
        src = source_frame(board)
        if not faces and not src:
            return
        out = dict(label=board.Label, rectangular=False,
                   planar_faces=[{'point': list(pt), 'normal': list(n)} for pt, n in faces],
                   fitted=hasattr(tip, 'SSStock'), reverse=getattr(tip, 'SSReverse', False),
                   linked_axis=getattr(tip, 'SSAxis', -1), result=getattr(tip, 'SSFitResult', ''),
                   extrusion='')
        if src is not None:
            ext, origin, axes, sizes = src
            out['origin'] = list(origin)
            out['axes'] = [list(v) for v in axes]
            out['sizes'] = sizes
            out['extrusion'] = ext.Name
    if out['fitted']:
        if not getattr(tip, 'SSTargetId', ''):
            out['fit_state'] = 'detached'
        elif getattr(tip, 'SSFitPaused', False):
            out['fit_state'] = 'paused'
        else:
            out['fit_state'] = 'live'
        end = fitted_end(board)
        if end is not None:
            n, pt = end
            if frame:
                fe_face = fitted_face(board)
            else:
                fe_face = next(
                    (i for i, (fpt, fn) in enumerate(faces)
                     if fn.dot(n) > 0.9999 and abs((fpt - pt).dot(n)) < 1e-4),
                    None,
                )
            if fe_face is not None:
                out['fitted_end'] = {'face': fe_face, 'normal': list(n), 'point': list(pt)}
    return out


def geometry(source, target, axis, face, mode, reverse=False, target_plane=None, profile=None):
    _, origin, axes, sizes = source
    if target_plane is not None:
        point, normal = target_plane
    else:
        _, point, target_axes, target_sizes = target
        index, positive = divmod(face, 2)
        normal = target_axes[index]
        if positive:
            point = point + normal * target_sizes[index]
    along = axes[axis]
    shift = along * sizes[axis] if reverse else V()
    if reverse:
        origin = origin + shift
        along = -along
    denom = along.dot(normal)
    if abs(denom) < 1e-8:
        raise ValueError('Target plane is parallel to this dimension')
    u, v = (axis + 1) % 3, (axis + 2) % 3
    dx, dy = axes[u]*sizes[u], axes[v]*sizes[v]
    corners = [origin, origin+dx, origin+dx+dy, origin+dy]
    if mode != 1 and profile is not None:
        if profile[0] == 'circle':
            _, center, u_ax, v_ax, r = profile
            d_center = (point - (center + shift)).dot(normal) / denom
            slope = math.hypot(u_ax.dot(normal), v_ax.dot(normal)) / abs(denom)
            depths = [d_center - r * slope, d_center + r * slope]
        else:
            depths = [(point - (p + shift)).dot(normal) / denom for p in profile[1]]
    else:
        depths = [(point-c).dot(normal)/denom for c in corners]
    if min(depths) <= 1e-6:
        raise ValueError('The entire target plane must be ahead of the starting end')
    if mode != 1:
        depths = [min(depths) if mode == 0 else max(depths)] * 4
    ends = [c + along*d for c,d in zip(corners,depths)]
    return corners, ends, depths


def mm(x):
    """A length for the result line: 1050 mm, 302.5 mm (0.1 mm, like the viewport's format_length)."""
    text = '%.1f' % x
    return (text[:-2] if text.endswith('.0') else text) + ' mm'


def _inputs(board, tip, bodies):
    """Comparable fit inputs, including values resolved by FreeCAD expressions and fitted target ends.

    Do not use handler `changed`: native property edits conservatively return every board,
    and expressions can move stock outside the edited board. Shapes need no tessellation here.
    """
    def src_key(obj, feature):
        data = source_frame(obj, feature)
        if not data:
            return None
        dfn, _ = _def(obj)
        ext, origin, axes, sizes = data
        return (obj.Label, ext.Name, tuple(origin), tuple(tuple(v) for v in axes), tuple(sizes),
                getattr(getattr(dfn, 'Tip', None), 'Name', None))

    def dst_key(obj, fit_tip, along):
        if obj is None:
            return None
        if stock(obj) is None:
            from export import shape_key
            return ('shape', obj.Label, shape_key(obj))
        _, plane, state = _resolve_face(obj, fit_tip, along=along)
        p_key = (tuple(plane[0]), tuple(plane[1])) if plane is not None else state
        return ('rect', obj.Label, p_key)

    target = bodies.get(tip.SSTargetId)
    along = _along_dir(board, tip)
    return (tip.SSTargetId, tip.SSAxis, tip.SSFace, tip.SSMode, getattr(tip, 'SSReverse', False),
            src_key(board, tip), dst_key(target, tip, along))


def refit_inputs(model):
    """Transient pre-op input values; nothing cached across undo, rebuild or reopen."""
    bodies = model.bodies()
    return {tip.Name: _inputs(src, tip, bodies)
            for tip, _, src, _ in _active_tips(model, bodies, promote=False)}


def _recompute_chain(target, recomputed):
    """Recompute `target`'s feature chain from its PlaneFit (or Mirroring) up to its Tip, once per pass."""
    dfn, _ = _def(target)
    root = dfn if dfn is not None else target
    if root is None or root.Name in recomputed:
        return
    recomputed.add(root.Name)
    tip = getattr(dfn, 'Tip', None) if dfn is not None else target
    if tip is None:
        return
    chain = []
    seen = set()
    cur = tip
    while cur is not None and cur.Name not in seen:
        seen.add(cur.Name)
        if hasattr(cur, 'SSStock'):
            break
        chain.append(cur)
        if getattr(cur, 'TypeId', '') == 'Part::Mirroring' and getattr(cur, 'Source', None) is not None:
            _recompute_chain(cur.Source, recomputed)
            break
        if hasattr(cur, 'Base'):
            cur = cur.Base
        elif getattr(cur, 'TypeId', '') == 'Part::MultiFuse' and getattr(cur, 'Shapes', None):
            cur = cur.Shapes[0]
        else:
            break
    for obj in reversed(chain):
        obj.recompute()


def refit_changed(model, before):
    """Update affected fits in topological order, rippling through chains (A <- B <- C) in one pass.

    Updates read stock frames and SSFitCorners rather than recomputed shapes, so the caller can
    recompute the batch once.
    """
    bodies = model.bodies()
    unvisited = _active_tips(model, bodies, promote=True)
    affected = set()
    recomputed = set()
    changed = []
    while unvisited:
        unvisited_ids = {bid for _, _, _, fam in unvisited for bid in fam}
        ready = [item for item in unvisited if item[0].SSTargetId not in unvisited_ids]
        if not ready:
            for tip, _, _, _ in unvisited:
                tip.SSFitResult = 'Reference unavailable · last geometry retained'
            break  # Defensive cycle guard.
        remaining = [item for item in unvisited if item[0].SSTargetId in unvisited_ids]
        for tip, _, src, fam in ready:
            if tip.SSTargetId in affected:
                target = bodies.get(tip.SSTargetId)
                if target is not None:
                    _recompute_chain(target, recomputed)
            if tip.SSTargetId in affected or before.get(tip.Name) != _inputs(src, tip, bodies):
                update(model, src, tip)
                affected.update(fam)
                changed.extend(fam)
        unvisited = remaining
    return changed


def _sliced_shape(board, base_shape, pt_world, n_world, start_local):
    """Intersect `base_shape` (in board-local coords) with the kept half-space bounded by (pt_world, n_world)."""
    inv = board.Placement.inverse()
    pt_l = inv.multVec(pt_world)
    n_l = inv.Rotation.multVec(n_world)
    n_l.normalize()
    keep_n = n_l if (start_local - pt_l).dot(n_l) >= 0 else -n_l
    u, v = _ortho_axes(keep_n)
    span = max(base_shape.BoundBox.DiagonalLength, 1000.0) * 4.0
    box = Part.makeBox(span, span, span)
    box.Placement = App.Placement(pt_l - u * (span * 0.5) - v * (span * 0.5), App.Rotation(u, v, keep_n, 'ZXY'))
    return base_shape.common(box)


def update(model, board, tip):
    if not tip.SSTargetId:          # detached (or its target is gone): the shape stays as it is
        return
    target = model.bodies().get(tip.SSTargetId)
    src, profile = _source_frame_and_profile(board, tip)
    along = None
    if src:
        along = src[2][tip.SSAxis]
        if getattr(tip, 'SSReverse', False):
            along = -along
    face_idx, plane, state = _resolve_face(target, tip, along=along)
    if state == 'paused':
        if 'SSFitPaused' not in tip.PropertiesList:
            tip.addProperty('App::PropertyBool', 'SSFitPaused')
        tip.SSFitPaused = True
        tip.SSFitResult = '%s → paused' % target.Label
        return
    if not src or plane is None:
        tip.SSTargetId = ''
        tip.SSFitResult = ''
        if 'SSFitPaused' in tip.PropertiesList:
            tip.SSFitPaused = False
        return
    if 'SSFitPaused' in tip.PropertiesList:
        tip.SSFitPaused = False
    n_local = getattr(tip, 'SSTargetNormal', None)
    if n_local is None or n_local.Length <= 1e-6:
        if 'SSTargetNormal' not in tip.PropertiesList:
            tip.addProperty('App::PropertyVector', 'SSTargetNormal')
        if 'SSTargetPoint' not in tip.PropertiesList:
            tip.addProperty('App::PropertyVector', 'SSTargetPoint')
        pt_l, n_l = _target_local_plane(target, plane[0], plane[1])
        tip.SSTargetPoint = pt_l
        tip.SSTargetNormal = n_l
    if 'SSTargetSign' not in tip.PropertiesList:
        tip.addProperty('App::PropertyInteger', 'SSTargetSign')
    if getattr(tip, 'SSTargetSign', 0) == 0 and along is not None:
        tip.SSTargetSign = 1 if along.dot(plane[1]) > 0 else -1
    if stock(target) is not None and n_local is not None and n_local.Length > 1e-6:
        fr = _target_frame(target)
        _, want_n = _frame_to_world(fr, tip.SSTargetPoint, n_local)
        if plane[1].dot(want_n) > 0.9999:
            pt_l, _ = _target_local_plane(target, plane[0], plane[1])
            tip.SSTargetPoint = pt_l
    tip.SSFace = face_idx
    dst = stock(target)
    corners, ends, depths = geometry(src, dst, tip.SSAxis, tip.SSFace, tip.SSMode,
                                     getattr(tip, "SSReverse", False), target_plane=plane, profile=profile)
    inv = board.Placement.inverse()
    local = [inv.multVec(p) for p in corners + ends]
    previous = tip.SSFitCorners
    is_rect = stock(board, tip) is not None
    if len(previous) != 8 or any((a - b).Length > 1e-8 for a, b in zip(previous, local)):
        if is_rect:
            def wire(points):
                return Part.makePolygon(points + points[:1])
            shape = Part.makeLoft([wire(local[:4]), wire(local[4:])], True, True)
        else:
            base_tip = tip.SSStock
            ext = _underlying_extrusion(base_tip)
            target_len = min(depths) if tip.SSMode == 0 else max(depths)
            if getattr(tip, 'SSReverse', False):
                shift_world = src[2][2] * (src[3][2] - target_len)
                pose = ext.Placement
                pose.Base = pose.Base + board.Placement.Rotation.inverted().multVec(shift_world)
                ext.Placement = pose
            ext.LengthFwd = target_len
            ext.recompute()
            if base_tip != ext:
                base_tip.recompute()
            shape = base_tip.Shape if tip.SSMode != 1 else _sliced_shape(board, base_tip.Shape, plane[0], plane[1], local[0])
        if not shape.isValid() or len(shape.Solids) != 1:
            raise ValueError('Could not make a solid for this fit')
        tip.Shape = shape
        tip.SSFitCorners = local
    dimension = mm(min(depths)) if max(depths)-min(depths)<1e-6 else '%s–%s' % (mm(min(depths)), mm(max(depths)))
    # Face frame: outward Z, deterministic in-plane X, relative to stock drawing axes.
    outward = plane[1]
    if dst is not None:
        i, _ = divmod(tip.SSFace, 2)
        ref_x = dst[2][(i + 1) % 3]
        if abs(ref_x.dot(outward)) > 0.999:
            ref_x = dst[2][(i + 2) % 3]
        face_name = FACES[tip.SSFace]
    else:
        ref_x, _ = _ortho_axes(outward)
        face_name = 'Face %d' % (tip.SSFace + 1)
    face_rot = App.Rotation(ref_x, V(), outward, 'ZXY')
    source_rot = App.Rotation(src[2][0],V(),src[2][2],'ZXY')
    yaw,pitch,roll = source_rot.inverted().multiply(face_rot).getYawPitchRoll()
    tip.SSFitResult = '%s → %s face · %s\n%s · X %.1f°  Y %.1f°  Z %.1f°' % (target.Label,face_name,MODES[tip.SSMode],dimension,roll,pitch,yaw)


def _resolve_face_spec(target, face_spec):
    """Resolve a {normal, point} face dict against `target`'s planar_faces."""
    if not isinstance(face_spec, dict) or 'normal' not in face_spec or 'point' not in face_spec:
        raise ValueError('fit face must be {normal, point}')
    want_n = V(face_spec['normal'])
    if want_n.Length <= 1e-9:
        return None, None
    want_n.normalize()
    want_pt = V(face_spec['point'])
    faces = planar_faces(target)
    matches = [(i, p) for i, p in enumerate(faces) if p[1].dot(want_n) > 0.9999]
    if not matches:
        return None, None
    idx, pl = min(matches, key=lambda item: abs((item[1][0] - want_pt).dot(want_n)))
    if abs((pl[0] - want_pt).dot(want_n)) > 0.05:
        return None, None
    return idx, pl


def apply(model, op):
    board, target = model.body(op['body']), model.body(op['target_body'])
    axis, face, mode = (op[k] for k in ('axis','face','fit_mode'))
    board_dfn, _ = _def(board)
    target_dfn, _ = _def(target)
    src, profile = _source_frame_and_profile(board)
    face_idx, t_plane = _resolve_face_spec(target, face)
    if board == target or board_dfn is None or target_dfn is None or board_dfn == target_dfn or not src or t_plane is None:
        raise ValueError('Pick a planar face on a different board')
    is_rect = stock(board) is not None
    if (axis not in range(3) if is_rect else axis != 2) or mode not in range(3):
        raise ValueError('Unknown plane fit')
    # Reject cycles across both plain boards and shared component definitions before mutating anything.
    bodies = model.bodies()
    seen = {board_dfn.Name}
    cur = target
    while cur is not None:
        cur_dfn, _ = _def(cur)
        if cur_dfn is None:
            break
        if cur_dfn.Name in seen:
            raise ValueError('This fit would create a cycle')
        seen.add(cur_dfn.Name)
        cur_tip = _underlying_plane_fit(getattr(cur_dfn, 'Tip', None))
        next_id = getattr(cur_tip, 'SSTargetId', '') if cur_tip is not None else ''
        cur = bodies.get(next_id) if next_id else None
    geometry(src, stock(target), axis, face_idx, mode, op.get("reverse", False), target_plane=t_plane, profile=profile)
    tip = board_dfn.Tip
    if not hasattr(tip,'SSStock'):
        tip = model.doc.addObject('Part::Feature','PlaneFit')
        tip.Label = 'Fit to plane'
        tip.addProperty('App::PropertyLink','SSStock')
        tip.SSStock = board_dfn.Tip
        for name,typ in [('SSTargetId','String'),('SSAxis','Integer'),('SSFace','Integer'),('SSMode','Integer'),('SSFitResult','String'),('SSFitCorners','VectorList'),('SSSourceBodyId','String'),('SSTargetNormal','Vector'),('SSTargetPoint','Vector')]:
            tip.addProperty('App::Property'+typ,name)
        model.set_tip(board_dfn,tip)
    if "SSReverse" not in tip.PropertiesList:
        tip.addProperty("App::PropertyBool","SSReverse")
    if "SSSourceBodyId" not in tip.PropertiesList:
        tip.addProperty("App::PropertyString","SSSourceBodyId")
    if "SSTargetNormal" not in tip.PropertiesList:
        tip.addProperty("App::PropertyVector","SSTargetNormal")
    if "SSTargetPoint" not in tip.PropertiesList:
        tip.addProperty("App::PropertyVector","SSTargetPoint")
    if "SSTargetSign" not in tip.PropertiesList:
        tip.addProperty("App::PropertyInteger","SSTargetSign")
    if "SSFitPaused" not in tip.PropertiesList:
        tip.addProperty("App::PropertyBool","SSFitPaused")
    pt_l, n_l = _target_local_plane(target, t_plane[0], t_plane[1])
    tip.SSTargetPoint = pt_l
    tip.SSTargetNormal = n_l
    along = -src[2][axis] if op.get("reverse", False) else src[2][axis]
    tip.SSTargetSign = 1 if along.dot(t_plane[1]) > 0 else -1
    tip.SSFitPaused = False
    tip.SSReverse = op.get("reverse",False)
    tip.SSSourceBodyId = board.BodyId if board_dfn is not board else ''
    tip.SSTargetId,tip.SSAxis,tip.SSFace,tip.SSMode = target.BodyId,axis,face_idx,mode
    return _family_bodies(model, board_dfn, bodies)


def resize_face(model, board, normal, distance):
    """Move a complete end of ordinary stock (or extrusion end of a non-rectangular/cut board), keeping its opposite end fixed."""
    dfn, placement = _def(board)
    frame = stock(board)
    is_rect = frame is not None
    if not frame:
        frame = source_frame(board)
    if not frame or hasattr(dfn.Tip, 'SSStock'):
        return False
    ext, _, axes, sizes = frame
    axis = next((i for i,v in enumerate(axes) if abs(v.dot(normal)) > 0.999999), None)
    if axis is None or (not is_rect and axis != 2):
        return False
    length = sizes[axis] + distance
    if length <= 1e-6:
        raise ValueError('The board dimension must stay positive')
    obj, prop = [(ext.Base,'Length'), (ext.Base,'Width'), (ext,'LengthFwd')][axis]
    # Keep an existing expression in the feature tree when adding material to driven stock.
    if any(path.lstrip('.') == prop for path,_ in obj.ExpressionEngine):
        return False
    if axes[axis].dot(normal) < 0:
        pose = ext.Placement
        pose.Base = pose.Base + placement.Rotation.inverted().multVec(normal * distance)
        ext.Placement = pose
    setattr(obj, prop, length)
    return True


def replace(model, op):
    """Typing a new length explicitly detaches the current fitted end (I26b)."""
    from length_input import evaluate
    board = model.body(op['body'])
    dfn, _ = _def(board)
    tip = getattr(dfn, 'Tip', None)
    if not hasattr(tip, 'SSStock') or op['axis'] != tip.SSAxis:
        raise ValueError('Fit changed. Refresh the properties.')
    length = evaluate(str(op['value']))
    if length <= 1e-6:
        raise ValueError('Enter a positive dimension')
    _restore(model, board, length)
    return _family_bodies(model, dfn)


def fitted_end(board, tip=None):
    """The fitted end face of a board, in world coordinates: (outward normal, a point on it), or None."""
    dfn, placement = _def(board)
    tip = tip or getattr(dfn, 'Tip', None)
    if not hasattr(tip, 'SSStock') or len(tip.SSFitCorners) != 8:
        return None
    pts = [placement.multVec(p) for p in tip.SSFitCorners]
    start, end = pts[:4], pts[4:]
    n = (end[1] - end[0]).cross(end[3] - end[0])
    if n.Length < 1e-9:
        return None
    n.normalize()
    middle = lambda ps: sum(ps, V()) * 0.25
    if n.dot(middle(end) - middle(start)) < 0:
        n = -n
    return n, end[0]


def push_fitted_end(model, board, normal, point, distance):
    """Pushing a board's tied end again detaches it (I26b, I40). A square end (Butt / Fully reach) goes back to
    plain stock at its current length and then takes the push, so its dimensions stay editable: True. A sloped end
    (Slice) keeps its shape untied and the push is an ordinary one: False. None: this isn't the tied end."""
    end = fitted_end(board)
    if end is None or end[0].dot(normal) < 0.9999 or abs((point - end[1]).dot(end[0])) > 0.01:
        return None
    dfn, _ = _def(board)
    tip = dfn.Tip
    if tip.SSMode == 1:
        tip.SSTargetId = ''
        tip.SSFitResult = 'Detached · shape kept'
        if hasattr(tip, 'SSSourceBodyId'):
            tip.SSSourceBodyId = ''
        return False
    local = tip.SSFitCorners
    _restore(model, board, (local[4] - local[0]).Length)
    if not resize_face(model, board, normal, distance):
        raise ValueError('Could not push the detached end')
    return True


def _restore(model, board, length):
    """Put the board's plain extrusion (or cut tip) back as its tip with this length along the fitted axis, keeping the
    unfitted end where it is."""
    dfn, placement = _def(board)
    tip = dfn.Tip
    axis = tip.SSAxis
    base_tip = tip.SSStock
    ext = _underlying_extrusion(base_tip)
    obj, prop = [(ext.Base,'Length'), (ext.Base,'Width'), (ext,'LengthFwd')][axis]
    if getattr(tip, 'SSReverse', False):
        _, _, axes, sizes = source_frame(board)
        shift_world = axes[axis] * (sizes[axis] - length)
        pose = ext.Placement
        pose.Base = pose.Base + placement.Rotation.inverted().multVec(shift_world)
        ext.Placement = pose
    dfn.Tip = base_tip
    base_tip.Visibility = True
    model.doc.removeObject(tip.Name)
    obj.setExpression(prop, None)
    setattr(obj, prop, length)
