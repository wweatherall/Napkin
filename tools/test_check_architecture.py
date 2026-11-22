# runner: none (unittest, run by .github/workflows/architecture.yml)
"""Regression tests for the architecture omission guard, including actual Git staging."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from check_architecture import check

SCRIPT = Path(__file__).with_name('check_architecture.py').resolve()

class GuardTests(unittest.TestCase):
    def test_new_module_requires_map(self):
        self.assertFalse(check(['worker/new_feature.py'], '', False)[0])

    def test_map_update_satisfies_check(self):
        self.assertTrue(check(['worker/serve.py', 'ARCHITECTURE.md'], '', True)[0])

    def test_documentation_and_tests_do_not_trigger(self):
        self.assertTrue(check(['CLAUDE.md', 'worker/test_native.py', 'viewport/tests.gd'], '', False)[0])

    def test_explicit_rationale(self):
        self.assertTrue(check(['viewport/main.gd'], 'Architecture-Impact: none - Corrects a label typo; contracts and state ownership are unchanged.', False)[0])
        self.assertFalse(check(['viewport/main.gd'], 'Architecture-Impact: none', False)[0])

    def test_real_git_staging_and_deletion(self):
        with tempfile.TemporaryDirectory() as folder:
            def git(*args):
                subprocess.run(['git', *args], cwd=folder, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            def run(*args):
                return subprocess.run(['python3', str(SCRIPT), *args], cwd=folder, capture_output=True, text=True).returncode
            root = Path(folder)
            git('init'); git('config','user.email','test@example.invalid'); git('config','user.name','Guard test')
            (root/'ARCHITECTURE.md').write_text('Baseline architecture\n')
            git('add','.'); git('commit','-m','Baseline')
            (root/'worker').mkdir(); (root/'worker/new module.py').write_text('value = 1\n')
            git('add','worker')
            self.assertEqual(run('--staged'), 1)
            (root/'ARCHITECTURE.md').write_text('Baseline architecture\nNew module responsibility\n')
            self.assertEqual(run('--staged'), 1, 'Unstaged docs must not satisfy commit check')
            git('add','ARCHITECTURE.md')
            self.assertEqual(run('--staged'), 0)
            git('commit','-m','Feature and architecture')
            self.assertEqual(run('--range','HEAD~1..HEAD'), 0)
            git('mv','worker/new module.py','worker/renamed.py')
            self.assertEqual(run('--staged'), 1)
            (root/'ARCHITECTURE.md').unlink(); git('add','ARCHITECTURE.md')
            self.assertEqual(run('--staged'), 1)

class HandoffTests(unittest.TestCase):
    """P28: on a branch, the map changes may be given as Architecture: lines in the job's handoff entry."""
    LINES = {'H062': 'Response.\n\nArchitecture: session.py saves generations (A32)\n',
             'H063': 'Response.\n\n- Architecture: the open reply gains recovered\n',
             'H070': 'Response, no map lines. A mention mid-line: `Architecture: <what>` is not one.\n'}
    MSG = 'Work\n\nArchitecture-Impact: in the handoff - {}\n'

    def run_check(self, hid, on_main=False):
        return check(['worker/session.py'], self.MSG.format(hid), False, on_main, self.LINES.get)

    def test_branch_commit_with_lines_passes(self):
        self.assertTrue(self.run_check('H062')[0])
        self.assertTrue(self.run_check('H063')[0], 'a leading "- " is allowed')

    def test_branch_commit_without_lines_fails_and_says_to_add_them(self):
        ok, message = self.run_check('H070')
        self.assertFalse(ok)
        self.assertIn('no "Architecture: <what>" line', message)
        self.assertFalse(self.run_check('H099')[0], 'an entry the branch does not have')

    def test_on_main_the_map_is_still_wanted(self):
        ok, message = self.run_check('H062', on_main=True)
        self.assertFalse(ok)
        self.assertIn('on main the map changes in the same commit', message)
        self.assertTrue(check(['worker/session.py', 'ARCHITECTURE.md'], '', True, True)[0])

    def test_none_with_a_reason_still_passes_on_a_branch(self):
        self.assertTrue(check(['viewport/main.gd'], 'Architecture-Impact: none - Corrects a label typo; nothing else.',
                              False, False)[0])

    def test_branch_message_without_either_names_the_handoff_form(self):
        ok, message = check(['worker/session.py'], '', False, False)
        self.assertFalse(ok)
        self.assertIn('Architecture-Impact: in the handoff - H0NN', message)

    def test_real_git_branch_and_range(self):
        with tempfile.TemporaryDirectory() as folder:
            def git(*args):
                subprocess.run(['git', *args], cwd=folder, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            def run(*args):
                return subprocess.run(['python3', str(SCRIPT), *args], cwd=folder, capture_output=True, text=True)
            root = Path(folder)
            git('init', '-b', 'main'); git('config', 'user.email', 'test@example.invalid'); git('config', 'user.name', 'Guard test')
            (root/'ARCHITECTURE.md').write_text('Baseline architecture\n')
            (root/'docs/handoff').mkdir(parents=True)
            (root/'docs/handoff/H062-gen.md').write_text('### H062 - a job\n\nRequest: do it.\n')
            git('add', '.'); git('commit', '-m', 'Baseline')
            msg = root/'msg.txt'
            msg.write_text('Work\n\nArchitecture-Impact: in the handoff - H062\n')
            git('checkout', '-b', 'claude/h062-gen')
            (root/'worker').mkdir(); (root/'worker/session.py').write_text('x = 1\n'); git('add', 'worker')
            r = run('--staged', '--message-file', str(msg))
            self.assertEqual(r.returncode, 1, 'the entry has no Architecture: line yet')
            self.assertIn('H062 has no "Architecture: <what>" line', r.stdout)
            (root/'docs/handoff/H062-gen.md').write_text('### H062 - a job\n\nArchitecture: session.py saves generations\n')
            r = run('--staged', '--message-file', str(msg))
            self.assertEqual(r.returncode, 1, 'unstaged handoff lines must not satisfy the commit check')
            git('add', 'docs')
            self.assertEqual(run('--staged', '--message-file', str(msg)).returncode, 0)
            git('commit', '-F', str(msg))
            self.assertEqual(run('--range', 'main..claude/h062-gen').returncode, 0, 'the PR check reads the head')
            git('checkout', 'main')
            (root/'worker').mkdir(exist_ok=True); (root/'worker/serve.py').write_text('y = 1\n'); git('add', 'worker')
            self.assertEqual(run('--staged', '--message-file', str(msg)).returncode, 1, 'on main the map is wanted')


if __name__ == '__main__':
    unittest.main()
