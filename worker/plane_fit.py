"""Board-local face references for rectangular Shop Sketch stock."""
import FreeCAD as App
import Part

V = App.Vector
FACES = ('Left', 'Right', 'Front', 'Back', 'Bottom', 'Top')
MODES = ('Butt to plane', 'Slice at plane', 'Fully reach plane')


def stock(board, feature=None):
    if getattr(board, 'TypeId', '') != 'App::Part':
        return
    tip = feature or getattr(board, 'Tip', None)
    ext = getattr(tip, 'SSStock', tip)
    if getattr(ext, 'TypeId', '') != 'Part::Extrusion' or ext.Base.TypeId != 'Part::Plane':
        return
    base = ext.Base
    pose = board.Placement.multiply(ext.Placement).multiply(base.Placement)
    axes = [pose.Rotation.multVec(v) for v in (V(1,0,0), V(0,1,0), V(0,0,1))]
    direction = board.Placement.Rotation.multVec(ext.Placement.Rotation.multVec(ext.Dir))
    direction.normalize()
    if abs(direction.dot(axes[2])) < 0.999999 or ext.LengthRev.Value or not ext.Solid or ext.Symmetric or ext.TaperAngle.Value or ext.TaperAngleRev.Value:
        return
    axes[2] = direction
    return ext, pose.Base, axes, [base.Length.Value, base.Width.Value, ext.LengthFwd.Value]


def snapshot(board):
    frame = stock(board)
    if not frame:
        return
    ext, origin, axes, sizes = frame
    tip = board.Tip
    return dict(label=board.Label, origin=list(origin), axes=[list(v) for v in axes], sizes=sizes,
                plane=ext.Base.Name, extrusion=ext.Name, fitted=hasattr(tip,'SSStock'),
                reverse=getattr(tip,'SSReverse',False), linked_axis=getattr(tip,'SSAxis',-1), result=getattr(tip,'SSFitResult',''))


def geometry(source, target, axis, face, mode, reverse=False):
    _, origin, axes, sizes = source
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


def update(model, board, tip):
    target = model.bodies().get(tip.SSTargetId)
    src, dst = stock(board, tip), stock(target)
    if not src or not dst or hasattr(target.Tip,'SSStock'):
        tip.SSTargetId = ''
        tip.SSFitResult = 'Reference unavailable · last geometry retained'
        return
    corners, ends, depths = geometry(src,dst,tip.SSAxis,tip.SSFace,tip.SSMode,getattr(tip,"SSReverse",False))
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
    dimension = '%.3g mm' % min(depths) if max(depths)-min(depths)<1e-6 else '%.3g–%.3g mm' % (min(depths),max(depths))
    # Face frame: outward Z, deterministic in-plane X, relative to stock drawing axes.
    i, side = divmod(tip.SSFace,2)
    face_rot = App.Rotation(dst[2][(i+1)%3],V(),dst[2][i]*(1 if side else -1),'ZXY')
    source_rot = App.Rotation(src[2][0],V(),src[2][2],'ZXY')
    yaw,pitch,roll = source_rot.inverted().multiply(face_rot).getYawPitchRoll()
    tip.SSFitResult = '%s → %s face · %s\n%s · X %.1f°  Y %.1f°  Z %.1f°' % (target.Label,FACES[tip.SSFace],MODES[tip.SSMode],dimension,roll,pitch,yaw)


def apply(model, op):
    board, target = model.body(op['body']), model.body(op['target_body'])
    axis, face, mode = (op[k] for k in ('axis','face','fit_mode'))
    if board == target or not stock(board) or not stock(target) or hasattr(target.Tip,'SSStock'):
        raise ValueError('Pick a face on a different rectangular board')
    if axis not in range(3) or face not in range(6) or mode not in range(3):
        raise ValueError('Unknown plane fit')
    geometry(stock(board),stock(target),axis,face,mode,op.get("reverse",False))
    tip = board.Tip
    if not hasattr(tip,'SSStock'):
        tip = model.doc.addObject('Part::Feature','PlaneFit')
        tip.Label = 'Fit to plane'
        tip.addProperty('App::PropertyLink','SSStock')
        tip.SSStock = board.Tip
        for name,typ in [('SSTargetId','String'),('SSAxis','Integer'),('SSFace','Integer'),('SSMode','Integer'),('SSFitResult','String'),('SSFitCorners','VectorList')]:
            tip.addProperty('App::Property'+typ,name)
        model.set_tip(board,tip)
    if "SSReverse" not in tip.PropertiesList:
        tip.addProperty("App::PropertyBool","SSReverse")
    tip.SSReverse = op.get("reverse",False)
    tip.SSTargetId,tip.SSAxis,tip.SSFace,tip.SSMode = target.BodyId,axis,face,mode
    return [board.BodyId]


def resize_face(model, board, normal, distance):
    """Move a complete end of ordinary stock, keeping its opposite end fixed."""
    frame = stock(board)
    if not frame or hasattr(board.Tip, 'SSStock'):
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
        pose.Base = pose.Base + board.Placement.Rotation.inverted().multVec(normal * distance)
        ext.Placement = pose
    setattr(obj, prop, length)
    return True


def replace(model, op):
    """Typing a new length explicitly detaches the current fitted end (I26b)."""
    from length_input import evaluate
    board = model.body(op['body'])
    tip = board.Tip
    if not hasattr(tip, 'SSStock') or op['axis'] != tip.SSAxis:
        raise ValueError('Fit changed. Refresh the properties.')
    length = evaluate(str(op['value']))
    if length <= 1e-6:
        raise ValueError('Enter a positive dimension')
    axis = tip.SSAxis
    ext = tip.SSStock
    obj, prop = [(ext.Base,'Length'), (ext.Base,'Width'), (ext,'LengthFwd')][axis]
    if getattr(tip, 'SSReverse', False):
        _, _, axes, sizes = stock(board)
        shift_world = axes[axis] * (sizes[axis] - length)
        pose = ext.Placement
        pose.Base = pose.Base + board.Placement.Rotation.inverted().multVec(shift_world)
        ext.Placement = pose
    board.Tip = ext
    ext.Visibility = True
    model.doc.removeObject(tip.Name)
    obj.setExpression(prop, None)
    setattr(obj, prop, length)
    return [board.BodyId]
