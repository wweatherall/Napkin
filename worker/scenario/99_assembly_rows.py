"""T58: linked rows of whole assemblies, editable spacing and member detachment."""
import os
from session import Session
from scenario.context import snap

requires = ()


def run(ctx):
    s = Session(os.path.join(ctx.TESTDIR, 'assembly-rows.FCStd'), fresh=True)
    fresh = None
    check = ctx.check
    base = ctx.FIX + [dict(id='ar-group', type='make_assembly', targets=['bottom', 'shelf'], new_id='ar0')]
    row = dict(id='ar-copy', type='move', targets=['bottom', 'shelf'], copy=True, selection=True,
               vector=[0, 600, 0], count=3, groups={'ar0': ['ar1', 'ar2', 'ar3']},
               new_ids=['bottom1', 'bottom2', 'bottom3', 'shelf1', 'shelf2a', 'shelf3'])
    pairs = [('bottom', ['bottom1', 'bottom2', 'bottom3']), ('shelf', ['shelf1', 'shelf2a', 'shelf3'])]
    try:
        s.sync(base)
        baseline = snap(s)
        for divide in (False, True):
            ops = base + [dict(row, divide=divide)]
            s.sync(ops)
            label = 'assembly /3' if divide else 'assembly 3x'
            check(label + ': accepted in one operation', s.status()[-1]['status'] == 'ok', s.status()[-1])
            state = snap(s)
            check(label + ': each copy is its own two-board assembly', all(
                state['groups'].get('ar' + str(i + 1)) == sorted([pairs[0][1][i], pairs[1][1][i]]) for i in range(3)), state['groups'])
            check(label + ': both boards keep their relative positions', all(
                state['boards'][bid]['box'][1] == baseline['boards'][source]['box'][1] + (200 if divide else 600) * (i + 1)
                for source, copies in pairs for i, bid in enumerate(copies)))
            check(label + ': shape definitions stay linked', all(
                s.model.definition(s.model.body(source)) is s.model.definition(s.model.body(bid))
                for source, copies in pairs for bid in copies))
            master = s.doc.getObject(s.model.body('bottom1').SSArray)
            change = dict(id='ar-spacing', type='property_edit', body='bottom1', object=master.Name,
                          property='Span.y' if divide else 'Step.y', value='900 mm' if divide else '700 mm', mode='value')
            edited = ops + [change]
            s.sync(edited)
            check(label + ': editing native spacing moves both boards together', s.status()[-1]['status'] == 'ok' and all(
                snap(s)['boards'][bid]['box'][1] == baseline['boards'][source]['box'][1] + (300 if divide else 700) * (i + 1)
                for source, copies in pairs for i, bid in enumerate(copies)), s.status()[-1])
            detached = edited + [dict(id='ar-detach', type='move', selection=True, detach=True,
                                     targets=['bottom2', 'shelf2a'], vector=[25, 0, 0])]
            s.sync(detached)
            detached_state = snap(s)
            check(label + ': moving a member detaches its whole assembly', s.status()[-1]['status'] == 'ok'
                  and all(not s.model.body(b).SSArray and detached_state['boards'][b]['box'][0] == baseline['boards'][source]['box'][0] + 25
                          for source, b in [('bottom', 'bottom2'), ('shelf', 'shelf2a')]), s.status()[-1])
            check(label + ': detached member stays linked in shape', all(
                s.model.definition(s.model.body(source)) is s.model.definition(s.model.body(bid))
                for source, bid in [('bottom', 'bottom2'), ('shelf', 'shelf2a')]))
            plane = next(o for o in s.model.definition(s.model.body('shelf2a')).Group if o.TypeId == 'Part::Plane')
            shape_edit = detached + [dict(id='ar-shape', type='property_edit', body='shelf2a', object=plane.Name,
                                          property='Length', value='500 mm', mode='value')]
            s.sync(shape_edit)
            shape = snap(s)
            check(label + ': editing a detached member updates every linked shape', s.status()[-1]['status'] == 'ok'
                  and all(shape['boards'][bid]['vol'] == shape['boards']['shelf']['vol'] for bid in pairs[1][1])
                  and shape['boards']['shelf']['vol'] != baseline['boards']['shelf']['vol'], s.status()[-1])
            s.sync(edited)
            moved = edited + [dict(id='ar-move-row', type='move', selection=True,
                                  targets=['bottom', 'shelf'] + row['new_ids'], vector=[10, 0, 0])]
            before_move = snap(s)
            s.sync(moved)
            check(label + ': moving the whole row moves each board once', s.status()[-1]['status'] == 'ok' and all(
                snap(s)['boards'][bid]['box'][0] == before_move['boards'][bid]['box'][0] + 10
                for bid in ['bottom', 'shelf'] + row['new_ids']), s.status()[-1])
            s.sync(edited)
            expected = snap(s)
            fresh = Session(None)
            fresh.sync(edited)
            check(label + ': live equals fresh build', snap(fresh) == expected)
            fresh.close(); fresh = None
            s.save(); path = s.path; s.close(); s = Session(path)
            check(label + ': reopened model equals live', snap(s) == expected)
            s.sync(base)
            check(label + ': undo row leaves original assembly intact', snap(s) == baseline)
        mirror_row = ctx.FIX + [dict(id='ar-mirrors', type='move', targets=['left', 'right'], selection=True,
                                     copy=True, count=3, vector=[0, 800, 0], groups={'sides': ['mr1', 'mr2', 'mr3']},
                                     new_ids=['ml1', 'ml2', 'ml3', 'mr1', 'mr2', 'mr3'])]
        s.sync(mirror_row)
        check('assembly row with mirrored members: accepted', s.status()[-1]['status'] == 'ok', s.status()[-1])
        mirror_state = snap(s)
        check('assembly row with mirrored members: copies retain exact reflected geometry', all(
            mirror_state['boards'][prefix + str(i)]['box'] == tuple(
                value + (800 * i if axis in (1, 4) else 0)
                for axis, value in enumerate(ctx.S0['boards'][source]['box']))
            and mirror_state['boards'][prefix + str(i)]['vol'] == ctx.S0['boards'][source]['vol']
            for source, prefix in [('left', 'ml'), ('right', 'mr')] for i in range(1, 4)))
        check('assembly row with mirrored members: counterparts share editable definitions', all(
            s.model.definition(s.model.body(b)) is s.model.definition(s.model.body('left'))
            for b in ['ml1', 'ml2', 'ml3', 'mr1', 'mr2', 'mr3']))
        master = s.doc.getObject(s.model.body('ml1').SSArray)
        spacing = mirror_row + [dict(id='mir-spacing', type='property_edit', body='ml1', object=master.Name,
                                    property='Step.y', value='900 mm', mode='value')]
        s.sync(spacing)
        mirror_spaced = snap(s)
        check('assembly row with mirrored members: spacing edits move both sides', all(
            mirror_spaced['boards'][b]['box'][1] == mirror_state['boards'][b]['box'][1] + 100 * i
            for i in range(1, 4) for b in ['ml' + str(i), 'mr' + str(i)]))
        detached = spacing + [dict(id='mir-detach', type='move', selection=True, detach=True,
                                  targets=['ml2', 'mr2'], vector=[10, 0, 0])]
        s.sync(detached)
        check('assembly row with mirrored members: detached assembly moves intact', s.status()[-1]['status'] == 'ok' and all(
            snap(s)['boards'][b]['box'][0] == mirror_spaced['boards'][b]['box'][0] + 10 for b in ['ml2', 'mr2']), s.status()[-1])
        s.sync(spacing)
        expected = snap(s)
        moved = spacing + [dict(id='mir-move-row', type='move', selection=True,
                               targets=['left', 'right', 'ml1', 'ml2', 'ml3', 'mr1', 'mr2', 'mr3'], vector=[10, 25, 0])]
        s.sync(moved)
        check('assembly row with mirrored members: moving the row moves each side once', s.status()[-1]['status'] == 'ok' and all(
            snap(s)['boards'][b]['box'][0] == expected['boards'][b]['box'][0] + 10
            and snap(s)['boards'][b]['box'][1] == expected['boards'][b]['box'][1] + 25
            for b in ['left', 'right', 'ml1', 'ml2', 'ml3', 'mr1', 'mr2', 'mr3']), s.status()[-1])
        plane = next(o for o in s.model.definition(s.model.body('left')).Group if o.TypeId == 'Part::Plane')
        reshaped = detached + [dict(id='mir-shape', type='property_edit', body='left', object=plane.Name,
                                   property='Length', value='30 mm', mode='value')]
        s.sync(reshaped)
        reshaped_state = snap(s)
        check('assembly row with mirrored members: edits update every linked shape after detachment',
              s.status()[-1]['status'] == 'ok'
              and reshaped_state['boards']['left']['vol'] != mirror_state['boards']['left']['vol']
              and all(reshaped_state['boards'][b]['vol'] == reshaped_state['boards']['left']['vol']
                      for b in ['right', 'ml1', 'ml2', 'ml3', 'mr1', 'mr2', 'mr3']), s.status()[-1])
        s.sync(spacing)
        fresh = Session(None); fresh.sync(spacing)
        check('assembly row with mirrored members: fresh build matches', snap(fresh) == expected)
        fresh.close(); fresh = None
        s.save(); path = s.path; s.close(); s = Session(path)
        check('assembly row with mirrored members: reopen matches', snap(s) == expected)
        s.sync(ctx.FIX)
        check('assembly row with mirrored members: undo removes the row', snap(s) == ctx.S0)
        s.sync(base)
        invalid = base + [dict(row, groups={'ar0': ['duplicate', 'duplicate', 'last']})]
        s.sync(invalid)
        check('assembly row: duplicate destination ids reject the whole operation',
              s.status()[-1]['status'] == 'failed' and snap(s) == baseline, s.status()[-1])
        s.sync(ctx.FIX)
    finally:
        s.close()
        if fresh is not None: fresh.close()
