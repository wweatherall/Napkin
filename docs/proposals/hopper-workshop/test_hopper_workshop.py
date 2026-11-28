import io
import unittest
from hopper_workshop import *


class WorkshopTests(unittest.TestCase):
    def test_sprite_animation_and_waiting(self):
        for agent in ('claude', 'gemini', 'codex'):
            self.assertEqual(len(sprite(agent)), 5)
            self.assertTrue(all(len(row) == 9 for row in sprite(agent)))
            self.assertGreater(len({sprite(agent, f, True) for f in range(8)}), 1)
            self.assertEqual(len({sprite(agent, f, False) for f in range(8)}), 1)
        self.assertEqual(len({sprite(a) for a in SPRITES}), 3)

    def test_widths(self):
        snap = demo_snapshot()
        for width in range(1, 241):
            with self.subTest(width=width):
                for compact in (False, True):
                    pic = render(snap, width=width, frame=3, compact=compact)
                    self.assertTrue(all(cells(line) <= width for line in pic.splitlines()))
        narrow = render(snap, width=78)
        wide = render(snap, width=120)
        self.assertFalse(any('WORKBENCH' in l and 'QUESTIONS' in l for l in narrow.splitlines()))
        self.assertTrue(any('WORKBENCH' in l and 'QUESTIONS' in l for l in wide.splitlines()))

    def test_queue_and_desk(self):
        st = {'jobs': {'H1': {'state': 'done', 'branch': 'base'},
                       'H2': {'state': 'done', 'base': 'base'},
                       'H3': {'state': 'returned'},
                       'H4': {'state': 'waiting', 'agent': 'codex'},
                       'H5': {'state': 'merged', 'merged': 42}},
              'launched': {'H6': {'agent': 'claude'}}}
        jobs = [{'id': f'H{i}', 'item': 'Title', 'kind': 'ready'} for i in range(1, 8)]
        snap = make_snapshot(st, jobs, ['H2', 'H1'])
        self.assertEqual([x[0] for x in snap.done], ['H1', 'H2'])
        self.assertEqual([x[0] for x in snap.queued], ['H3', 'H7'])
        self.assertEqual(snap.queued[0][2], 'returned')
        self.assertEqual(snap.launching[0][0], 'H6')
        self.assertEqual(snap.waiting[0][0], 'H4')
        self.assertEqual(snap.last_merged, 'H5')

    def test_long_unicode_and_escape(self):
        st = {'jobs': {'H1': {'state': 'waiting', 'agent': 'codex',
                              'question': '界' * 100 + '\x1b[2J' + 'long question'}}}
        s = make_snapshot(st, [], [])
        for width in (12, 20, 40, 78, 101):
            pic = render(s, width=width)
            self.assertNotIn('\x1b', pic)
            self.assertTrue(all(cells(l) <= width for l in pic.splitlines()))

    def test_cached_animation_and_timing(self):
        class Clock:
            t = 0
            def now(self): return self.t
            def sleep(self, seconds): self.t += seconds
        c = Clock()
        output = io.StringIO()
        display = WorkshopDisplay(output, width=lambda: 78, height=lambda: 80,
                                  monotonic=c.now, sleep=c.sleep)
        display.animate = True
        display.draw_for(demo_snapshot(), 20, now=10_000)
        self.assertEqual(c.t, 20)
        self.assertGreater(output.getvalue().count('\x1b[H'), 5)
        self.assertTrue(all(len(p.splitlines()) <= 80 for p in output.getvalue().split('\x1b[H')))

    def test_small_terminal(self):
        out = io.StringIO()
        d = WorkshopDisplay(out, width=lambda: 40, height=lambda: 12)
        d.draw_for(demo_snapshot(), 0)
        self.assertLessEqual(len(out.getvalue().splitlines()), 12)
        self.assertIn('more lines', out.getvalue())

    def test_empty_static(self):
        s = make_snapshot({}, [], [])
        self.assertEqual(render(s, now=1, frame=0), render(s, now=1, frame=25))


if __name__ == '__main__':
    unittest.main()
