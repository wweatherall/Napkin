"""Board-local face references for rectangular Shop Sketch stock."""
import FreeCAD as App
import Part

V = App.Vector
FACES = ('Left', 'Right', 'Front', 'Back', 'Bottom', 'Top')
MODES = ('Butt to plane', 'Slice at plane', 'Fully reach plane')


def _def(board):
    """Return (definition App::Part, world placement) for a plain board or component instance, else (None, None)."""
    t = getattr(board, 'TypeId', '')
    if t == 'App::Part':
        return board, board.Placement
    if t == 'App::Link':
        dfn = getattr(board, 'LinkedObject', None)
        if getattr(dfn, 'TypeId', '') == 'App::Part':
            return dfn, board.Placement
    return None, None


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
    src_id = getattr(tip, 'SSSourceBodyId', '')
    if src_id in fam:
        return bodies[src_id]
    src = bodies[fam[0]]
    if promote:
        if 'SSSourceBodyId' not in tip.PropertiesList:
            tip.addProperty('App::PropertyString', 'SSSourceBodyId')
        tip.SSSourceBodyId = src.BodyId
    return src


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
            if promote:
                tip.SSTargetId = ''
                if hasattr(tip, 'SSSourceBodyId'):
                    tip.SSSourceBodyId = ''
            continue
        src = _driving_body(model, dfn, tip, bodies, promote=promote)
        if src is not None:
            out.append((tip, dfn, src, fam))
    return out


def stock(board, feature=None):
    dfn, placement = _def(board)
    if dfn is None:
        return
    tip = feature or getattr(dfn, 'Tip', None)
    ext = getattr(tip, 'SSStock', tip)
    if getattr(ext, 'TypeId', '') != 'Part::Extrusion' or ext.Base.TypeId != 'Part::Plane':
        return
    base = ext.Base
    pose = placement.multiply(ext.Placement).multiply(base.Placement)
    axes = [pose.Rotation.multVec(v) for v in (V(1,0,0), V(0,1,0), V(0,0,1))]
    direction = placement.Rotation.multVec(ext.Placement.Rotation.multVec(ext.Dir))
    direction.normalize()
    if abs(direction.dot(axes[2])) < 0.999999 or ext.LengthRev.Value or not ext.Solid or ext.Symmetric or ext.TaperAngle.Value or ext.TaperAngleRev.Value:
        return
    axes[2] = direction
    return ext, pose.Base, axes, [base.Length.Value, base.Width.Value, ext.LengthFwd.Value]


def fitted_face(board):
    """The face index (0..5) of a fitted board's fitted end, or None."""
    dfn, _ = _def(board)
    tip = getattr(dfn, 'Tip', None)
    if not hasattr(tip, 'SSStock'):
        return None
    return 2 * tip.SSAxis + (0 if getattr(tip, 'SSReverse', False) else 1)


def face_plane(target, face):
    """World (point, outward_normal) for `face` of rectangular board `target`, or None.
    Uses `fitted_end(target)` when `face` is `target`'s fitted end; otherwise uses `stock(target)`."""
    frame = stock(target)
    if not frame:
        return None
    if fitted_face(target) == face:
        end = fitted_end(target)
        if end is not None:
            n, pt = end
            return pt, n
    _, origin, axes, sizes = frame
    index, positive = divmod(face, 2)
    normal = axes[index]
    point = origin + normal * sizes[index] if positive else origin
    outward = normal if positive else -normal
    return point, outward


def snapshot(board):
    frame = stock(board)
    if not frame:
        return
    dfn, _ = _def(board)
    ext, origin, axes, sizes = frame
    tip = dfn.Tip
    out = dict(label=board.Label, origin=list(origin), axes=[list(v) for v in axes], sizes=sizes,
               plane=ext.Base.Name, extrusion=ext.Name, fitted=hasattr(tip,'SSStock'),
               reverse=getattr(tip,'SSReverse',False), linked_axis=getattr(tip,'SSAxis',-1), result=getattr(tip,'SSFitResult',''))
    if out['fitted']:
        end = fitted_end(board)
        if end is not None:
            n, pt = end
            out['fitted_end'] = {'face': fitted_face(board), 'normal': list(n), 'point': list(pt)}
    return out


def geometry(source, target, axis, face, mode, reverse=False, target_plane=None):
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
    if reverse:
        origin = origin + along * sizes[axis]
        along = -along
    denom = along.dot(normal)
    if abs(denom) < 1e-8:
        raise ValueError('Target plane is parallel to this dimension')
    u, v = (axis + 1) % 3, (axis + 2) % 3
    dx, dy = axes[u]*sizes[u], axes[v]*sizes[v]
    corners = [origin, origin+dx, origin+dx+dy, origin+dy]
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
    def frame(obj, feature=None):
        data = stock(obj, feature)
        if not data:
            return None
        dfn, _ = _def(obj)
        ext, origin, axes, sizes = data
        end = fitted_end(obj) if feature is None else None
        end_key = (tuple(end[0]), tuple(end[1])) if end is not None else None
        return (obj.Label, ext.Name, tuple(origin), tuple(tuple(v) for v in axes), tuple(sizes),
                getattr(getattr(dfn, 'Tip', None), 'Name', None), end_key)
    target = bodies.get(tip.SSTargetId)
    return (tip.SSTargetId, tip.SSAxis, tip.SSFace, tip.SSMode, getattr(tip, 'SSReverse', False),
            frame(board, tip), frame(target))


def refit_inputs(model):
    """Transient pre-op input values; nothing cached across undo, rebuild or reopen."""
    bodies = model.bodies()
    return {tip.Name: _inputs(src, tip, bodies)
            for tip, _, src, _ in _active_tips(model, bodies, promote=False)}


def refit_changed(model, before):
    """Update affected fits in topological order, rippling through chains (A <- B <- C) in one pass.

    Updates read stock frames and SSFitCorners rather than recomputed shapes, so the caller can
    recompute the batch once.
    """
    bodies = model.bodies()
    unvisited = _active_tips(model, bodies, promote=True)
    affected = set()
    changed = []
    while unvisited:
        unvisited_ids = {bid for _, _, _, fam in unvisited for bid in fam}
        ready = [item for item in unvisited if item[0].SSTargetId not in unvisited_ids]
        if not ready:
            break  # Defensive cycle guard.
        remaining = [item for item in unvisited if item[0].SSTargetId in unvisited_ids]
        for tip, _, src, fam in ready:
            if tip.SSTargetId in affected or before.get(tip.Name) != _inputs(src, tip, bodies):
                update(model, src, tip)
                affected.update(fam)
                changed.extend(fam)
        unvisited = remaining
    return changed


def update(model, board, tip):
    if not tip.SSTargetId:          # detached (or its target is gone): the shape stays as it is
        return
    target = model.bodies().get(tip.SSTargetId)
    src, dst = stock(board, tip), stock(target)
    if not src or not dst:
        tip.SSTargetId = ''
        tip.SSFitResult = 'Reference unavailable · last geometry retained'
        return
    plane = face_plane(target, tip.SSFace)
    corners, ends, depths = geometry(src, dst, tip.SSAxis, tip.SSFace, tip.SSMode,
                                     getattr(tip, "SSReverse", False), target_plane=plane)
    inv = board.Placement.inverse()
    local = [inv.multVec(p) for p in corners + ends]
    previous = tip.SSFitCorners
    if len(previous) != 8 or any((a-b).Length > 1e-8 for a,b in zip(previous,local)):
        def wire(points):
            return Part.makePolygon(points + points[:1])
        shape = Part.makeLoft([wire(local[:4]),wire(local[4:])],True,True)
        if not shape.isValid() or len(shape.Solids) != 1:
            raise ValueError('Could not make a solid for this fit')
        tip.Shape = shape
        tip.SSFitCorners = local
    dimension = mm(min(depths)) if max(depths)-min(depths)<1e-6 else '%s–%s' % (mm(min(depths)), mm(max(depths)))
    # Face frame: outward Z, deterministic in-plane X, relative to stock drawing axes.
    i, _ = divmod(tip.SSFace, 2)
    outward = plane[1]
    ref_x = dst[2][(i + 1) % 3]
    if abs(ref_x.dot(outward)) > 0.999:
        ref_x = dst[2][(i + 2) % 3]
    face_rot = App.Rotation(ref_x, V(), outward, 'ZXY')
    source_rot = App.Rotation(src[2][0],V(),src[2][2],'ZXY')
    yaw,pitch,roll = source_rot.inverted().multiply(face_rot).getYawPitchRoll()
    tip.SSFitResult = '%s → %s face · %s\n%s · X %.1f°  Y %.1f°  Z %.1f°' % (target.Label,FACES[tip.SSFace],MODES[tip.SSMode],dimension,roll,pitch,yaw)


def apply(model, op):
    board, target = model.body(op['body']), model.body(op['target_body'])
    axis, face, mode = (op[k] for k in ('axis','face','fit_mode'))
    board_dfn, _ = _def(board)
    target_dfn, _ = _def(target)
    if board == target or board_dfn is None or target_dfn is None or board_dfn == target_dfn or not stock(board) or not stock(target):
        raise ValueError('Pick a face on a different rectangular board')
    if axis not in range(3) or face not in range(6) or mode not in range(3):
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
        cur_tip = getattr(cur_dfn, 'Tip', None)
        next_id = getattr(cur_tip, 'SSTargetId', '') if hasattr(cur_tip, 'SSStock') else ''
        cur = bodies.get(next_id) if next_id else None
    geometry(stock(board), stock(target), axis, face, mode, op.get("reverse", False),
             target_plane=face_plane(target, face))
    tip = board_dfn.Tip
    if not hasattr(tip,'SSStock'):
        tip = model.doc.addObject('Part::Feature','PlaneFit')
        tip.Label = 'Fit to plane'
        tip.addProperty('App::PropertyLink','SSStock')
        tip.SSStock = board_dfn.Tip
        for name,typ in [('SSTargetId','String'),('SSAxis','Integer'),('SSFace','Integer'),('SSMode','Integer'),('SSFitResult','String'),('SSFitCorners','VectorList'),('SSSourceBodyId','String')]:
            tip.addProperty('App::Property'+typ,name)
        model.set_tip(board_dfn,tip)
    if "SSReverse" not in tip.PropertiesList:
        tip.addProperty("App::PropertyBool","SSReverse")
    if "SSSourceBodyId" not in tip.PropertiesList:
        tip.addProperty("App::PropertyString","SSSourceBodyId")
    tip.SSReverse = op.get("reverse",False)
    tip.SSSourceBodyId = board.BodyId if board_dfn is not board else ''
    tip.SSTargetId,tip.SSAxis,tip.SSFace,tip.SSMode = target.BodyId,axis,face,mode
    return _family_bodies(model, board_dfn, bodies)


def resize_face(model, board, normal, distance):
    """Move a complete end of ordinary stock, keeping its opposite end fixed."""
    dfn, placement = _def(board)
    frame = stock(board)
    if not frame or hasattr(dfn.Tip, 'SSStock'):
        return False
    ext, _, axes, sizes = frame
    axis = next((i for i,v in enumerate(axes) if abs(v.dot(normal)) > 0.999999), None)
    if axis is None:
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


def fitted_end(board):
    """The fitted end face of a board, in world coordinates: (outward normal, a point on it), or None."""
    dfn, placement = _def(board)
    tip = getattr(dfn, 'Tip', None)
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
    """Put the board's plain extrusion back as its tip with this length along the fitted axis, keeping the
    unfitted end where it is."""
    dfn, placement = _def(board)
    tip = dfn.Tip
    axis = tip.SSAxis
    ext = tip.SSStock
    obj, prop = [(ext.Base,'Length'), (ext.Base,'Width'), (ext,'LengthFwd')][axis]
    if getattr(tip, 'SSReverse', False):
        _, _, axes, sizes = stock(board)
        shift_world = axes[axis] * (sizes[axis] - length)
        pose = ext.Placement
        pose.Base = pose.Base + placement.Rotation.inverted().multVec(shift_world)
        ext.Placement = pose
    dfn.Tip = ext
    ext.Visibility = True
    model.doc.removeObject(tip.Name)
    obj.setExpression(prop, None)
    setattr(obj, prop, length)
