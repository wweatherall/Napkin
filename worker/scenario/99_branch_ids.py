"""T67: old file/journal IDs remain verbatim; abandoned IDs persist after save/reopen."""
import json
import os
import uuid
from session import Session, read_journal, write_meta_journal
from scenario.context import snap

requires = ()

def run(ctx):
    path = os.path.join(ctx.TESTDIR, 'branch-ids.FCStd')
    old = Session(path, fresh=True)
    try:
        old.sync(ctx.FIX)
        old.save()
        native = {o.Name: {k: getattr(o, k) for k in ('BodyId','RectId','SSOp','AssemblyId','SSLineId') if hasattr(o, k)} for o in old.doc.Objects}
        before = snap(old)
    finally:
        old.close()
    # Model the actual old schema, with no registry extension.
    journal = read_journal(path)
    journal.pop('reserved_ids', None)
    journal.pop('id_owners', None)
    write_meta_journal(path, journal)
    opened = Session(path)
    try:
        ctx.check('T67 old journal retains every op ID verbatim', [e['op'] for e in opened.applied] == ctx.FIX)
        ctx.check('T67 old native identity properties remain verbatim', all(
            opened.doc.getObject(name) is not None and all(getattr(opened.doc.getObject(name), k) == v for k,v in props.items())
            for name,props in native.items()))
        ctx.check('T67 migration reserves native and op IDs without geometry changes',
                  snap(opened) == before and all(v in opened.ids.reserved for props in native.values() for v in props.values() if v))
        rid, oid, bid = ('r100_' + uuid.uuid4().hex, 'pp100_' + uuid.uuid4().hex, 'b100_' + uuid.uuid4().hex)
        modern = ctx.FIX + [dict(id=rid, type='rect', plane=dict(origin=[10000,0,0], normal=[0,0,1]), size=[50,40]),
                            dict(id=oid, type='push_pull', target=dict(rect=rid), distance=10, body=bid)]
        opened.sync(modern)
        ctx.check('T67 random identities build a native board with a readable name',
                  opened.model.body(bid).Label == 'Board 100' and opened.model.rect_obj(rid).RectId == rid
                  and all(e['status'] == 'ok' for e in opened.status()))
        opened.save()
        opened.close()
        opened = Session(path)
        ctx.check('T67 random profile, board and op IDs reopen verbatim',
                  [e['op'] for e in opened.applied] == modern and opened.model.body(bid).Label == 'Board 100')
        opened.sync(ctx.FIX)
        abandoned = 'hd1_' + uuid.uuid4().hex
        opened.sync(ctx.FIX + [dict(id=abandoned, type='hide', targets=['bottom'], hidden=True)])
        opened.sync(ctx.FIX)
        opened.save()
    finally:
        opened.close()
    reopened = Session(path)
    try:
        ctx.check('T67 save/reopen reserves abandoned futures without keeping their geometry',
                  abandoned in reopened.ids.reserved and snap(reopened) == before)
        ctx.check('T67 saving an old journal never rewrites its op IDs', [e['op'] for e in reopened.applied] == ctx.FIX)
    finally:
        reopened.close()
