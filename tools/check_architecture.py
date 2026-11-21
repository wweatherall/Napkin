#!/usr/bin/env python3
"""Flag code changes whose architecture impact must be reviewed.

Commit hook: --staged --message-file PATH
CI: --range BASE..HEAD (checks the complete PR diff and its commit messages).
This is an omission detector, not proof that the architecture prose is accurate.
"""
import argparse
import re
import subprocess
from pathlib import Path


def git(*args):
    return subprocess.check_output(['git', *args], text=True)


def watched(path):
    p = Path(path)
    if p.name.startswith('test_') or p.name in ('tests.gd', 'test_load.py'):
        return False
    return (p.parts[0] in ('worker', 'viewport') and p.suffix in ('.py', '.gd', '.godot', '.tscn')) or path in ('tools/build_app.sh',)


def check(paths, messages, architecture_changed):
    affected = sorted(p for p in paths if watched(p))
    if not affected or architecture_changed:
        return True, 'Architecture check passed.'
    # A rationale is for changes which truly have no architectural impact, not an exemption.
    if re.search(r'^Architecture-Impact: none\s+[-—:]\s+\S.{14,}$', messages, re.MULTILINE | re.IGNORECASE):
        return True, 'Architecture check: no-impact rationale supplied; reviewer must verify it.'
    return False, ('Architecture review needed for:\n  ' + '\n  '.join(affected) +
                   '\nUpdate ARCHITECTURE.md with architectural changes in the same commit.\n'
                   'For a change with no architectural impact, include a specific commit-message line:\n'
                   'Architecture-Impact: none - <why modules, contracts, ownership and persistence are unchanged>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--staged', action='store_true')
    mode.add_argument('--range', dest='revision_range')
    parser.add_argument('--message-file')
    args = parser.parse_args()
    if args.staged:
        diff = ['diff', '--cached']
        messages = Path(args.message_file).read_text() if args.message_file else ''
    else:
        if args.revision_range.startswith('-') or '..' not in args.revision_range:
            parser.error('--range requires BASE..HEAD')
        diff = ['diff', args.revision_range]
        messages = git('log', '--format=%B', args.revision_range, '--')
    paths = git(*diff, '--name-only', '--no-renames', '-z', '--').split('\0')
    paths = [p for p in paths if p]
    arch_patch = git(*diff, '--ignore-all-space', '--', 'ARCHITECTURE.md')
    # Deleting the document or reducing it to whitespace cannot satisfy the guard.
    revision = ':' if args.staged else args.revision_range.split('..')[-1] + ':'
    architecture_changed = False
    if arch_patch and 'ARCHITECTURE.md' in paths:
        try:
            architecture_changed = bool(git('show', revision + 'ARCHITECTURE.md').strip())
        except subprocess.CalledProcessError:
            pass
    ok, message = check(paths, messages, architecture_changed)
    print(message)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
