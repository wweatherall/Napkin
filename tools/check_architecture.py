#!/usr/bin/env python3
"""Flag code changes whose architecture impact must be reviewed.

Commit hook: --staged --message-file PATH
CI: --range BASE..HEAD (checks the complete PR diff and its commit messages, as a branch: a PR is never main).
This is an omission detector, not proof that the architecture prose is accurate.

A commit touching watched code passes with one of:
- ARCHITECTURE.md changed in the same commit (on main: the integrator writes the map, P28);
- "Architecture-Impact: none - <why>" (a specific reason; the reviewer verifies it);
- on a branch only (P28): "Architecture-Impact: in the handoff - H0NN" (or H-new-N), when that entry
  (docs/handoff/H0NN-*.md in the commit, or at the range's head) has at least one "Architecture: <what>" line.
  Workers don't edit ARCHITECTURE.md or docs/protocol.md; the integrator writes those lines in at merge.
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


ARCHITECTURE_LINE = re.compile(r'^[-*]?\s*Architecture:\s*\S', re.MULTILINE)
IN_HANDOFF = re.compile(r'^Architecture-Impact: in the handoff\s+[-—:]\s+(H\d+|H-new-\d+)\b', re.MULTILINE | re.IGNORECASE)


def check(paths, messages, architecture_changed, on_main=True, handoff_text=lambda hid: None):
    """handoff_text(id): that handoff entry's text in the commit (or the range's head), None if it has none."""
    affected = sorted(p for p in paths if watched(p))
    if not affected or architecture_changed:
        return True, 'Architecture check passed.'
    # A rationale is for changes which truly have no architectural impact, not an exemption.
    if re.search(r'^Architecture-Impact: none\s+[-—:]\s+\S.{14,}$', messages, re.MULTILINE | re.IGNORECASE):
        return True, 'Architecture check: no-impact rationale supplied; reviewer must verify it.'
    named = IN_HANDOFF.findall(messages)
    if named and on_main:
        return False, ('Architecture-Impact: in the handoff is for a branch: on main the map changes in the same '
                       'commit (the integrator writes the Architecture: lines in, P28), or none with a reason.')
    if named:
        missing = [h for h in dict.fromkeys(named) if not ARCHITECTURE_LINE.search(handoff_text(h) or '')]
        if not missing:
            return True, ('Architecture check: the map changes are in ' + ', '.join(dict.fromkeys(named)) +
                          "'s Architecture: lines; the integrator writes them at merge (P28).")
        return False, ('Architecture review needed for:\n  ' + '\n  '.join(affected) + '\n' +
                       ', '.join(missing) + ' has no "Architecture: <what>" line in docs/handoff/ (in this commit): '
                       'add one per change to the map or the protocol (a module, a message, state ownership, '
                       'saving), then commit again (P28).')
    return False, ('Architecture review needed for:\n  ' + '\n  '.join(affected) +
                   ('\nUpdate ARCHITECTURE.md with architectural changes in the same commit.\n' if on_main else
                    '\nOn a branch, don\'t edit ARCHITECTURE.md or docs/protocol.md (P28): write what the change does '
                    'to them as "Architecture: <what>" lines in your handoff entry and add the commit-message line\n'
                    'Architecture-Impact: in the handoff - H0NN\n') +
                   'For a change with no architectural impact, include a specific commit-message line:\n'
                   'Architecture-Impact: none - <why modules, contracts, ownership and persistence are unchanged>')


def handoff_reader(revision):
    """handoff_text for a tree: ':' (the index) or '<commit>:'."""
    def read(hid):
        tree = revision[:-1] or None
        names = git('ls-files', '--', 'docs/handoff/') if tree is None else \
            git('ls-tree', '-r', '--name-only', tree, '--', 'docs/handoff/')
        for n in names.split('\n'):
            if Path(n).name.startswith(hid + '-') and n.endswith('.md'):
                try:
                    return git('show', revision + n)
                except subprocess.CalledProcessError:
                    return None
        return None
    return read


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
    on_main = args.staged and git('branch', '--show-current').strip() == 'main'
    ok, message = check(paths, messages, architecture_changed, on_main, handoff_reader(revision))
    print(message)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
