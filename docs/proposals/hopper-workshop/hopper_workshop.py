#!/usr/bin/env python3
"""Responsive ASCII view of Napkin's Hopper. No queue writes or AI calls."""
from dataclasses import dataclass
import argparse
import os
import shutil
import sys
import time
import unicodedata

FRAME_SECONDS = 0.25

# Each sprite occupies a fixed 9 x 5 cell. The identity never changes.
# Only a recorded in-progress job uses the animated frames.
SPRITES = {
    'claude': (
        ('  \\ | /', '   \\|/', '  --o--', '   /|\\', '  / | \\'),
        ('   .|.', '  --|--', '  ( o )', '  --|--', '   `|\''),
        ('  / | \\', '   /|\\', '  --o--', '   \\|/', '  \\ | /'),
        ('   \\ /', '  .   .', '  --o--', '  `   \'', '   / \\'),
    ),
    'gemini': (
        ('   /\\', '  /  \\', ' <>  <>', '  \\  /', '   \\/'),
        ('    ^', '   /\\', '  <><>', '   \\/', '    v'),
        ('   /\\', '  /  \\', ' <>  <>', '  \\  /', '   \\/'),
        ('   /\\', ' /    \\', '<>    <>', ' \\    /', '   \\/'),
    ),
    'codex': (
        ('   __', ' /_  \\_', '/  /\\_ \\', '\\_/  / /', '  \\_/_/'),
        ('   __', ' /_  \\_', '/  /o_ \\', '\\_/  / /', '  \\_/_/'),
        ('   __', ' /o  \\_', '/  /\\_ \\', '\\_/  / /', '  \\_/_/'),
        ('   __', ' /_  \\_', '/  /\\_ \\', '\\_/  o /', '  \\_/_/'),
    ),
}
ICONS = {'claude': '*', 'gemini': '<>', 'codex': '@'}
UNKNOWN = ('', '  .---.', '  | ? |', '  `---\'', '')


def sprite(agent, frame=0, active=False):
    frames = SPRITES.get(str(agent).lower(), (UNKNOWN,))
    return tuple(s.ljust(9) for s in frames[(frame // 2 if active else 0) % len(frames)])


def _clean(value):
    # Prevent job titles/questions from injecting terminal escape sequences.
    return ' '.join(''.join(c if not unicodedata.category(c).startswith('C') else ' '
                            for c in str(value or '')).split())


def cells(s):
    return sum(0 if unicodedata.combining(c) else
               2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)


def fit(value, width, *, ellipsis=True):
    """Clip and pad to terminal columns (not Python character count)."""
    width = max(0, width)
    s = str(value)
    if cells(s) > width:
        marker = '...' if ellipsis and width >= 4 else ''
        limit = width - len(marker)
        out = ''
        used = 0
        for c in s:
            n = cells(c)
            if used + n > limit:
                break
            out += c
            used += n
        s = out + marker
    return s + ' ' * (width - cells(s))


def center(s, width):
    s = fit(s, min(width, cells(s))).rstrip()
    left = max(0, (width - cells(s)) // 2)
    return ' ' * left + fit(s, width - left)


def wrap(value, width):
    """Word wrap, with hard breaks for exceptionally long tokens."""
    value = _clean(value)
    if width <= 0:
        return ['']
    lines = []
    while cells(value) > width:
        piece = fit(value, width, ellipsis=False).rstrip()
        if not piece:  # A wide glyph cannot fit a one-column display.
            piece = value[0]
        cut = len(piece)
        if cut < len(value) and value[cut] != ' ' and ' ' in piece:
            cut = piece.rfind(' ')
        lines.append(fit(value[:cut].rstrip(), width).rstrip())
        value = value[cut:].lstrip()
    return lines + [value]


def duration(seconds):
    mins = max(0, int(seconds)) // 60
    return f'{mins // 60}h{mins % 60:02}m' if mins >= 60 else f'{mins}m'


def panel(title, body, width):
    inside = width - 4
    label = ' ' + title + ' '
    label = fit(label, min(width - 2, cells(label))).strip()
    label = f' {label} ' if cells(label) + 2 <= width - 2 else label
    gap = width - 2 - cells(label)
    return ['+' + '-' * (gap // 2) + label + '-' * (gap - gap // 2) + '+',
            *['| ' + fit(row, inside) + ' |' for row in body or ['(empty)']],
            '+' + '-' * (width - 2) + '+']


def side_by_side(left, right, lw, rw, gap=2):
    height = max(len(left), len(right))
    def pad(rows, width):
        return rows[:-1] + ['| ' + ' ' * (width - 4) + ' |'] * (height - len(rows)) + rows[-1:]
    return [a + ' ' * gap + b for a, b in zip(pad(left, lw), pad(right, rw))]


@dataclass(frozen=True)
class Snapshot:
    queued: tuple
    launching: tuple
    working: tuple
    waiting: tuple
    done: tuple
    last_merged: str


def make_snapshot(st, resolved_jobs, order):
    """Build a display-only view from already dependency-resolved queue data."""
    states = st.get('jobs', {})
    ranks = {jid: i for i, jid in enumerate(order)}
    titles = {j['id']: j.get('item', '') for j in resolved_jobs}
    def sort_key(jid):
        return ranks.get(jid, len(ranks)), jid
    def item(jid, entry):
        return (jid, {**entry, 'title': titles.get(jid) or entry.get('branch', '')})
    held = ('in progress', 'waiting', 'done', 'merged')
    launches = [(jid, dict(j)) for jid, j in st.get('launched', {}).items()
                if states.get(jid, {}).get('state') not in held]
    launch_ids = {jid for jid, _ in launches}
    queued = []
    for j in sorted(resolved_jobs, key=lambda j: sort_key(j['id'])):
        jid = j['id']
        state = states.get(jid, {}).get('state')
        if state in held or jid in launch_ids:
            continue
        tag = 'returned' if state == 'returned' else (
            'wait ' + str(j['waits']) if j.get('kind') == 'queued' and j.get('waits') else '')
        queued.append((jid, j.get('item', ''), tag))
    def group(state):
        return tuple(sorted((item(jid, j) for jid, j in states.items() if j.get('state') == state),
                            key=lambda pair: (pair[1].get('since' if state == 'waiting' else 'taken')
                                              or pair[1].get('taken') or 0, pair[0])))
    # Same base-before-stacked ordering as hopper_picture._batch_order_done.
    done = {jid: j for jid, j in states.items() if j.get('state') == 'done'}
    by_branch = {j['branch']: jid for jid, j in done.items() if j.get('branch')}
    pending = set(done)
    ordered_done = []
    while pending:
        ready = [jid for jid in pending if by_branch.get(done[jid].get('base')) not in pending]
        jid = min(ready or pending, key=sort_key)
        ordered_done.append(item(jid, done[jid]))
        pending.remove(jid)
    merged = [(j.get('merged') or 0, jid) for jid, j in states.items() if j.get('state') == 'merged']
    last = max(merged)[1] if merged else next((e['job'] for e in reversed(st.get('events', []))
                                               if e.get('kind') == 'merged' and e.get('job')), '')
    return Snapshot(tuple(queued), tuple(launches), group('in progress'), group('waiting'),
                    tuple(ordered_done), last)


def load_snapshot(root):
    import job  # lazy: the dispatcher itself imports this renderer
    jobs, order = job.main_view(root)
    st = job.read_state(job.state_path(root))
    resolved = job.resolve_dependencies(jobs, st)
    # Match the original queue's fallback ordering for jobs not on BOARD.md.
    sorted_jobs = job.ordered(resolved, order)
    complete_order = list(dict.fromkeys([*order, *(j['id'] for j in sorted_jobs)]))
    return make_snapshot(st, sorted_jobs, complete_order)


def _worker_rows(jid, entry, width, frame, now, waiting, compact=False):
    agent = _clean(entry.get('agent') or '?').lower()
    who = agent.upper()
    since = (entry.get('since') if waiting else entry.get('taken')) or entry.get('taken') or entry.get('beat') or now
    elapsed = duration(now - since)
    status = ('Waiting ' if waiting else 'In progress ') + elapsed
    session = _clean(entry.get('session'))
    # UUIDs are transport identifiers, not useful labels.
    if len(session) == 36 and session.count('-') == 4:
        session = ''
    name = f'{jid}  {who}' + (f' / {session}' if session and session != agent else '')
    detail = entry.get('question') or '(no question)' if waiting else entry.get('title') or '(untitled)'
    target = 'To integrator' if entry.get('question_kind') == 'scope' else 'To William'
    if compact:
        icon = ICONS.get(agent, '?')
        motion = '?' if waiting else ('.', ':', '*', ':')[(frame // 2) % 4]
        return wrap(f'{icon}{motion} {jid} {who} {elapsed} | {detail}' +
                    (f' [{target}]' if waiting else ''), width)
    if width < 31:
        return [*wrap(f'{ICONS.get(agent, "?")} {name}', width), *wrap(detail, width),
                *wrap(status, width), *([*wrap(target, width)] if waiting else [])]
    art = sprite(agent, frame, active=not waiting)
    tw = width - 11
    info = [*wrap(name, tw), *wrap(detail, tw), *wrap(status, tw)]
    if waiting:
        info += wrap('? ' + target, tw)
    n = max(len(art), len(info))
    return [(art[i] if i < len(art) else ' ' * 9) + '  ' +
            (info[i] if i < len(info) else '') for i in range(n)]


def _station(items, width, frame, now, waiting=False, compact=False):
    result = []
    for jid, j in items:
        if result and not compact:
            result.append(' ' + '-' * max(0, width - 2))
        result += _worker_rows(jid, j, width, frame, now, waiting, compact)
    return result


def render(snapshot, *, width=78, now=None, frame=0, logs=(), compact=False):
    """Render a fixed snapshot; deterministic when width, now and frame are supplied."""
    width = max(1, int(width))
    now = time.time() if now is None else now
    s = snapshot
    if width < 12:
        return '\n'.join(fit(x, width).rstrip() for x in ('HOPPER', f'Q:{len(s.queued)} W:{len(s.working)}',
                                                         f'?:{len(s.waiting)} D:{len(s.done)}'))
    inner = width - 4
    lines = [fit('NAPKIN / HOPPER', width),
             fit(f'{len(s.queued)} queued | {len(s.launching)} launching | {len(s.working)} working | {len(s.waiting)} waiting | {len(s.done)} done', width), '']
    q = []
    for jid, title, tag in s.queued:
        suffix = f' [{_clean(tag)}]' if tag else ''
        # Wrap rather than hiding dependency information at narrow widths.
        q.extend(wrap(f'{jid}  {_clean(title)}{suffix}', inner))
    funnel = panel(f'HOPPER [{len(s.queued)}]', q, width)
    funnel[-1] = '\\' + '_' * (width - 2) + '/'
    lines += funnel
    lines.append(center('\\    /', width))
    if s.launching:
        for jid, entry in s.launching:
            marker = ('v', '.', 'v', '|')[frame % 4]
            lines.append(center('|' + _clean(jid) + '|', width))
            lines.append(center(marker + ' ' + _clean(entry.get('agent') or ''), width))
    else:
        lines.append(center('|    |', width))
    # At 100 columns, both stations have room for an avatar and useful text.
    if width >= 100:
        lw = (width - 2) // 2
        rw = width - 2 - lw
        left = panel(f'WORKBENCH [{len(s.working)}]', _station(s.working, lw - 4, frame, now, compact=compact), lw)
        right = panel(f'QUESTIONS [{len(s.waiting)}]', _station(s.waiting, rw - 4, frame, now, True, compact), rw)
        lines += side_by_side(left, right, lw, rw)
    else:
        lines += panel(f'WORKBENCH [{len(s.working)}]', _station(s.working, inner, frame, now, compact=compact), width)
        lines += panel(f'QUESTIONS [{len(s.waiting)}]', _station(s.waiting, inner, frame, now, True, compact), width)
    lines.append(center('v', width))
    desk = []
    for jid, j in s.done:
        agent = _clean(j.get('agent') or '?')
        desk.extend(wrap(f'[=] {jid} {j.get("title", "")} ({agent})', inner))
    desk.append('[OK] ' + s.last_merged + ' merged' if s.last_merged else 'Last merged: (none)')
    lines += panel(f'INTEGRATOR\'S DESK [{len(s.done)}]', desk, width)
    if logs:
        lines += [''] + [fit(_clean(line), width) for line in logs[-6:]]
    return '\n'.join(lines)


def terminal_height():
    return max(1, shutil.get_terminal_size(fallback=(79, 24)).lines - 1)


def terminal_width():
    # Reserve the last column so terminals with auto-wrap don't jump a line.
    return max(1, shutil.get_terminal_size(fallback=(79, 24)).columns - 1)


class WorkshopDisplay:
    """Animation is independent of the dispatcher's operational polling cycle."""
    def __init__(self, stream=None, *, width=terminal_width, height=terminal_height, monotonic=time.monotonic, sleep=time.sleep):
        self.stream = sys.stdout if stream is None else stream
        self.width, self.height, self.monotonic, self.sleep = width, height, monotonic, sleep
        self.start = monotonic()
        self.last = None
        self.animate = not os.environ.get('HOPPER_NO_ANIMATION')

    def draw_for(self, snapshot, seconds, *, now=None, logs=()):
        """Draw cached data until the existing poll interval expires; never reload it."""
        start = self.monotonic()
        deadline = start + max(0, seconds)
        wall = time.time() if now is None else now
        while True:
            t = self.monotonic()
            frame = int((t - self.start) / FRAME_SECONDS) if self.animate else 0
            width, height = self.width(), self.height()
            kwargs = dict(width=width, now=wall + t - start, frame=frame, logs=logs)
            picture = render(snapshot, **kwargs)
            if len(picture.splitlines()) > height:
                picture = render(snapshot, compact=True, **kwargs)
            rows = picture.splitlines()
            if len(rows) > height:
                # Preserve queue counts at the top and never scroll the live viewport.
                hidden = len(rows) - max(0, height - 1)
                rows = rows[:max(0, height - 1)] + [fit(f'[{hidden} more lines; enlarge window]', width)]
                picture = '\n'.join(rows)
            if picture != self.last:
                self.stream.write('\033[H' + picture + '\033[J')
                self.stream.flush()
                self.last = picture
            remaining = deadline - self.monotonic()
            if remaining <= 0:
                return
            self.sleep(min(FRAME_SECONDS, remaining))


def watch(root):
    import job
    display = WorkshopDisplay()
    while True:
        display.draw_for(load_snapshot(root), job.WATCH_POLL)


def demo_snapshot():
    now = time.time()
    names = [('H210', 'Choose coordinate system'), ('H211', 'Repair face selection'),
             ('H212', 'Optimize geometry'), ('H213', 'Improve snapping'),
             ('H214', 'Repair extrusion'), ('H215', 'Add constraints'),
             ('H208', 'Update tests'), ('H209', 'Fix edge detection'), ('H216', 'Improve sketch snapping')]
    jobs = [{'id': jid, 'item': title, 'kind': 'queued' if jid == 'H215' else 'ready',
             'waits': 'H214' if jid == 'H215' else ''} for jid, title in names]
    state = {'jobs': {
        'H210': {'state': 'waiting', 'agent': 'codex', 'since': now - 180,
                 'question_kind': 'scope', 'question': 'Which coordinate system?'},
        'H211': {'state': 'in progress', 'agent': 'claude', 'taken': now - 240},
        'H212': {'state': 'in progress', 'agent': 'gemini', 'taken': now - 120},
        'H216': {'state': 'in progress', 'agent': 'codex', 'taken': now - 60},
        'H208': {'state': 'done', 'agent': 'gemini'}, 'H209': {'state': 'done', 'agent': 'codex'},
        'H207': {'state': 'merged', 'merged': now - 500}},
        'launched': {'H213': {'agent': 'claude'}}}
    return make_snapshot(state, jobs, [jid for jid, _ in names])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true', help='use illustrative jobs, not the real queue')
    parser.add_argument('--watch', action='store_true', help='refresh and animate on a terminal')
    parser.add_argument('--width', type=int, help='override the terminal width')
    args = parser.parse_args()
    if args.width is not None and args.width < 1:
        parser.error('--width must be positive')
    if args.demo:
        snapshot = demo_snapshot()
        read = lambda: snapshot
    else:
        import job
        root = job.main_root(os.getcwd())
        read = lambda: load_snapshot(root)
    width = (lambda: args.width) if args.width is not None else terminal_width
    if args.watch and sys.stdout.isatty() and os.environ.get('TERM') != 'dumb':
        display = WorkshopDisplay(width=width)
        try:
            while True:
                display.draw_for(read(), 20 if args.demo else job.WATCH_POLL)
        except KeyboardInterrupt:
            return
    else:
        print(render(read(), width=width()))


if __name__ == '__main__':
    main()
