"""Inspectable native properties and journalled edits, shared by the worker and tests."""
import math
import FreeCAD as App

SCALARS = {'App::PropertyLength', 'App::PropertyDistance', 'App::PropertyAngle',
           'App::PropertyFloat', 'App::PropertyFloatConstraint', 'App::PropertyInteger',
           'App::PropertyIntegerConstraint', 'App::PropertyBool', 'App::PropertyString',
           'App::PropertyEnumeration'}
PROTECTED = {'Name', 'Label2', 'Visibility', 'ExpressionEngine', 'Tip', 'Group',
             'BodyId', 'RectId', 'AssemblyId', 'LinkedObject', 'LinkTransform',
             'AttacherEngine', 'AttacherType', 'AttachmentSupport', 'MapMode'}

def related(model, body):
    root = model.body(body)
    found = {}
    def visit(obj):
        if obj is None or obj.Name in found:
            return
        found[obj.Name] = obj
        for child in obj.OutList:
            visit(child)
    visit(root)
    return [o for o in found.values() if not o.TypeId.startswith(('App::Origin', 'App::Line', 'App::Plane', 'App::Point'))]

def expressions(obj):
    return {path.lstrip('.'): text for path, text in getattr(obj, 'ExpressionEngine', [])}

def editable(obj, prop):
    if prop in PROTECTED or prop.startswith('SS'):
        return False
    try:
        if 'ReadOnly' in obj.getEditorMode(prop) or 'ReadOnly' in obj.getPropertyStatus(prop):
            return False
    except (AttributeError, TypeError):
        return False
    return True

def field(obj, name, path, value, kind, writable, exprs, **extra):
    return dict(name=name, path=path, value=value, kind=kind, editable=writable,
                expression=exprs.get(path, ''), **extra)

def describe(obj):
    rows = []
    exprs = expressions(obj)
    for prop in obj.PropertiesList:
        typ = obj.getTypeIdOfProperty(prop)
        val = getattr(obj, prop)
        write = editable(obj, prop)
        if typ == 'App::PropertyPlacement':
            for axis in 'xyz':
                path = prop + '.Base.' + axis
                rows.append(field(obj, prop + ' ' + axis.upper() + ' (local)', path,
                                  str(getattr(val.Base, axis)) + ' mm', 'length', write, exprs))
            rows.append(field(obj, prop + ' rotation', prop + '.Rotation', str(val.Rotation), 'read', False, exprs))
        elif typ == 'App::PropertyVector':
            for axis in 'xyz':
                rows.append(field(obj, prop + '.' + axis, prop + '.' + axis,
                                  str(getattr(val, axis)) + (' mm' if prop in ('Origin', 'Step', 'Span') else ''),
                                  'length' if prop in ('Origin', 'Step', 'Span') else 'number', write, exprs))
        elif typ in SCALARS:
            kind = 'text' if typ == 'App::PropertyString' else 'number'
            if typ in ('App::PropertyLength', 'App::PropertyDistance'): kind = 'length'
            if typ == 'App::PropertyAngle': kind = 'angle'
            if typ == 'App::PropertyBool': kind = 'bool'
            if typ == 'App::PropertyEnumeration': kind = 'enum'
            choices = obj.getEnumerationsOfProperty(prop) if kind == 'enum' else []
            rows.append(field(obj, prop, prop, str(val), kind, write, exprs, choices=choices))
        elif 'PropertyLink' in typ:
            def link_label(x):
                return x.Label + ' (' + x.Name + ')' if hasattr(x, 'Name') else str(x)
            value = ', '.join(link_label(x) for x in val) if isinstance(val, (list, tuple)) else link_label(val)
            rows.append(field(obj, prop, prop, value, 'link', False, exprs))
        else:
            if typ == 'Part::PropertyPartShape':
                value = 'Shape: %d solids, volume %.6g mm³' % (len(val.Solids), val.Volume)
            elif prop == 'ExpressionEngine':
                value = '; '.join(path + ' = ' + expression for path, expression in val)
            else:
                value = str(val)[:1000]
            rows.append(field(obj, prop, prop, value, 'read', False, exprs))
    priority = {'Label': 0, 'Length': 1, 'Width': 2, 'Height': 3, 'LengthFwd': 4, 'LengthRev': 5}
    rows.sort(key=lambda row: (priority.get(row['path'], 10 if row['path'].startswith('Placement.') else 20), row['path']))
    return dict(name=obj.Name, label=obj.Label, type=obj.TypeId, fields=rows)

FACE_NAMES = ['Left', 'Right', 'Front', 'Back', 'Bottom', 'Top']
AXIS_LABELS = ['Length', 'Width', 'Thickness']


def _summary(model, body, boards, objs):
    root = model.body(body)
    all_bodies = model.bodies()
    parts = []
    asm = model.assembly_of(root)
    if asm is not None:
        parts.append('Part within ' + asm.Label)
    defn = model.definition(root)
    n_instances = sum(1 for o in all_bodies.values() if model.definition(o).Name == defn.Name)
    if n_instances >= 2:
        parts.append('Linked component (%d instances)' % n_instances)
    context = ' · '.join(parts) if parts else 'Board'

    board = boards.get(body)
    is_fitted = bool(board and board.get('fitted', False))
    has_expr = any(bool(getattr(o, 'ExpressionEngine', [])) for o in objs)
    parametric = is_fitted or has_expr

    dimensions = []
    if board and board.get('rectangular', True):
        linked_axis = board.get('linked_axis', -1)
        tip = getattr(defn, 'Tip', None)
        target_label = ''
        target_face = ''
        offset_mm = 0.0
        if is_fitted and linked_axis >= 0 and tip is not None:
            target_id = getattr(tip, 'SSTargetId', '') or ''
            target_obj = all_bodies.get(target_id)
            target_label = target_obj.Label if target_obj is not None else target_id
            face_idx = int(getattr(tip, 'SSFace', -1))
            if 0 <= face_idx < len(FACE_NAMES):
                target_face = FACE_NAMES[face_idx] + ' face'
            offset_mm = float(getattr(tip, 'SSOffset', 0.0) or 0.0)
        for i, size in enumerate(board['sizes'][:3]):
            linked = (linked_axis == i)
            dimensions.append({
                'axis': i,
                'label': AXIS_LABELS[i],
                'value_mm': float(size),
                'editable': True,
                'linked': linked,
                'target_label': target_label if linked else '',
                'target_face': target_face if linked else '',
                'offset_mm': offset_mm if linked else 0.0,
            })
    else:
        bb = root.Shape.BoundBox
        for i, extent in enumerate([bb.XLength, bb.YLength, bb.ZLength]):
            dimensions.append({
                'axis': i,
                'label': AXIS_LABELS[i],
                'value_mm': float(extent),
                'editable': False,
                'linked': False,
                'target_label': '',
                'target_face': '',
                'offset_mm': 0.0,
            })

    return {
        'label': root.Label,
        'context': context,
        'parametric': parametric,
        'dimensions': dimensions,
    }


def inspect(model, body):
    from plane_fit import snapshot
    boards = {key: info for key, obj in model.bodies().items() if (info := snapshot(obj))}
    objs = related(model, body)
    return dict(body=body, boards=boards, summary=_summary(model, body, boards, objs),
                objects=[describe(o) for o in objs],
                references=[dict(name=o.Name, label=o.Label) for o in model.doc.Objects if hasattr(o, 'Shape')])

def apply(model, op):
    candidates = {o.Name: o for o in related(model, op['body'])}
    obj = candidates.get(op['object'])
    if obj is None:
        raise ValueError('The feature no longer belongs to this piece')
    path = op['property']
    row = next((f for f in describe(obj)['fields'] if f['path'] == path), None)
    if row is None or not row['editable']:
        raise ValueError('This property is read-only')
    # A stale form must not overwrite a changed value or silently remove a new expression.
    expected = op.get('expected')
    if expected is not None and expected != {'value': row['value'], 'expression': row['expression']}:
        raise ValueError('Property changed; refresh before editing it')
    text = str(op['value']).strip()
    if op.get('mode') == 'expression':
        if row['kind'] not in ('number', 'length', 'angle') or not text:
            raise ValueError('Enter a numeric FreeCAD expression')
        obj.setExpression(path, text)
    elif op.get('mode') == 'value':
        if row['kind'] == 'text':
            value = str(op['value'])
        elif row['kind'] == 'bool':
            if text.lower() not in ('true', 'false'): raise ValueError('Use true or false')
            value = text.lower() == 'true'
        elif row['kind'] == 'enum':
            if text not in row['choices']: raise ValueError('Choose a listed value')
            value = text
        elif row['kind'] == 'length':
            from length_input import evaluate
            value = evaluate(text)
        else:
            q = obj.evalExpression(text)
            if hasattr(q, 'Unit'):
                unit = App.Units.Quantity('1 deg').Unit if row['kind'] == 'angle' else App.Units.Quantity('1').Unit
                if q.Unit not in (unit, App.Units.Quantity('1').Unit):
                    raise ValueError('The result has the wrong units')
                value = q.Value
            else:
                value = float(q)
            if not math.isfinite(value): raise ValueError('Enter a finite value')
            typ = obj.getTypeIdOfProperty(path.split('.')[0])
            if 'Integer' in typ:
                if value != int(value): raise ValueError('Enter a whole number')
                value = int(value)
        if row['expression']:
            obj.setExpression(path, None)
        parts = path.split('.')
        if len(parts) == 1:
            setattr(obj, path, value)
        elif len(parts) == 3:  # placement translation; reassign the native Placement
            place = getattr(obj, parts[0])
            vector = place.Base
            setattr(vector, parts[2], value)
            place.Base = vector
            setattr(obj, parts[0], place)
        else:
            vector = getattr(obj, parts[0])
            setattr(vector, parts[1], value)
            setattr(obj, parts[0], vector)
    else:
        raise ValueError('Choose value or expression')
    return list(model.bodies())  # references may update other pieces too
