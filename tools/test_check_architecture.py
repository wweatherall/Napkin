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

if __name__ == '__main__':
    unittest.main()
