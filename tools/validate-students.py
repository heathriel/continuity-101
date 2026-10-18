#!/usr/bin/env python3
"""Check changed student Markdown structure; never execute it or assess learning."""
import argparse
import json
import os
import re
import stat
import sys

LIMIT = 256 * 1024
STUDENT = r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}'
SUBMISSION = re.compile(rf'^students/({STUDENT})/(challenge-([1-4])\.md|MORNING-TAPE\.md)$')
REQUIREMENTS = {
    1: [('attempted work', r'what i tried to do'), ('actual work', r'what i actually did'),
        ('lost context', r'what (?:was|i) lost'), ('reflection', r'reflection')],
    2: [('testing description', r'testing evidence'), ('reflection', r'reflection')],
    3: [('reading notes', r'notes (?:on|from) (?:the )?hitchhiker'),
        ('attempted task', r'the task'), ('worked/failed assessment', r'what worked|honest assessment'),
        ('changes', r'changes (?:to make|to my memory system)')],
    4: [('mentee', r'who (?:you|i) mentored'), ('approach', r'(?:your|my) mentoring approach'),
        ('surprises', r'(?:the surprises|what surprised)'),
        ('learning', r'(?:what you learned|how teaching changed)')],
}


def read_local(root, relative):
    parts = relative.split('/')
    if any(p in ('', '.', '..') or p.startswith('.') for p in parts) or '\\' in relative:
        raise ValueError('unsafe path')
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = next_fd
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, 'rb') as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                raise ValueError('not a regular file')
            raw = f.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise ValueError('file too large')
            return raw.decode('utf-8')
    finally:
        os.close(directory)


def sections(text):
    """H2 sections; code fences never supply required headings."""
    result = []
    current = None
    fence = None
    for line in text.splitlines():
        mark = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if mark:
            token = mark[1]
            if fence is None:
                fence = token
            elif (token[0] == fence[0] and len(token) >= len(fence)
                  and not line[mark.end():].strip()):
                fence = None
            continue
        if fence:
            continue
        heading = re.match(r'^##\s+(.+?)\s*#*$', line)
        if heading:
            current = [heading[1].casefold(), []]
            result.append(current)
        elif re.match(r'^#\s+', line):
            current = None
        elif current is not None:
            current[1].append(line)
    return result


def has_answer(lines, template_lines):
    for line in lines:
        text = line.strip()
        if not text or text in template_lines or re.match(r'^#{1,6}\s', text):
            continue
        if re.fullmatch(r'[-*_\s]+|(?:[-*]|\d+\.)\s*(?:\[[ xX]\])?\s*', text):
            continue
        if re.fullmatch(r'\[.*\]', text) or re.fullmatch(r'[*_]*\[.*\][*_]*', text):
            continue
        if re.search(r'_{3,}|\[(?:Your|YYYY|Number|Task|Priority|What|Who|Name|Date)\b', text):
            continue
        # A substantive-looking line is only structure, never evidence of truth.
        if re.search(r'\w', text):
            return True
    return False


def validate_file(root, course_root, path, number):
    text = read_local(root, path)
    template = read_local(course_root, f'challenge-{number}/template.md')
    boilerplate = {line.strip() for line in template.splitlines() if line.strip()}
    found = sections(text)
    issues = []
    for label, pattern in REQUIREMENTS[number]:
        candidates = [body for title, body in found if re.search(pattern, title)]
        if not candidates:
            issues.append(f'missing section: {label}')
        elif not any(has_answer(body, boilerplate) for body in candidates):
            issues.append(f'no non-template text in section: {label}')
    if number == 3 and not any('honest assessment' in title and has_answer(body, boilerplate)
                               for title, body in found):
        candidates = [body for title, body in found if title == 'what failed']
        if not candidates or not any(has_answer(body, boilerplate) for body in candidates):
            issues.append('missing non-template What Failed assessment')
    return issues


def assess(root, course_root, changed):
    if not isinstance(changed, list) or len(changed) > 10000 or any(not isinstance(p,str) for p in changed):
        raise ValueError('changed paths must be a bounded string list')
    selected = {}
    ignored = []
    invalid = []
    for path in sorted(set(changed)):
        match = SUBMISSION.fullmatch(path)
        if match:
            student, filename, number = match.groups()
            target = f'students/{student}/challenge-{number or "2"}.md'
            selected[target] = int(number or 2)
        elif path.startswith('students/'):
            # Other artifacts are not executions or completion submissions.
            if any(p in ('', '.', '..') for p in path.split('/')) or '\\' in path or '\x00' in path:
                invalid.append({'path':path,'status':'invalid_path','issues':['unsafe student path']})
            else:
                ignored.append(path)
    rows = invalid
    for path, number in sorted(selected.items()):
        row = {'path': path, 'challenge': number, 'learning_assessment': 'human_review_required'}
        try:
            issues = validate_file(root, course_root, path, number)
            if number == 2:
                tape_path = path.rsplit('/', 1)[0] + '/MORNING-TAPE.md'
                tape = read_local(root, tape_path)
                tape_sections = sections(tape)
                template = read_local(course_root, 'challenge-2/template.md')
                boilerplate = {line.strip() for line in template.splitlines() if line.strip()}
                for title in ('who am i?', 'what was i doing?', 'current priorities',
                              'active conversations', 'system status', 'quick reference', 'session notes'):
                    bodies = [body for heading, body in tape_sections if heading == title]
                    if not bodies or not any(has_answer(body, boilerplate) for body in bodies):
                        issues.append(f'MORNING-TAPE.md missing non-template section: {title}')
                # The same student's artifact is required; shared examples cannot substitute.
                row['attachment'] = tape_path
            row.update(status='structure_needs_changes' if issues else 'structure_ready_for_review', issues=issues)
        except FileNotFoundError:
            row.update(status='missing_or_removed', issues=['submission or required same-student attachment is missing; reviewer must inspect deletion/rename intent'])
        except (OSError, ValueError, UnicodeError):
            row.update(status='unreadable_or_unsafe', issues=['file is unsafe, malformed, or exceeds 256 KiB'])
        rows.append(row)
    return {'scope':'changed student submission structure only', 'graduation':'not_assessed',
            'results': rows, 'unassessed_student_paths': ignored,
            'note':'No submitted code, links, recovery steps, or instructions were executed. Review honesty, simulation limits, permission, and learning manually.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True)
    parser.add_argument('--course-root',required=True,help='trusted course templates, not PR-edited templates')
    parser.add_argument('--changed-files',required=True,help='NUL-delimited git diff --name-only output')
    args = parser.parse_args(argv)
    try:
        with open(args.changed_files,'rb') as f:
            raw = f.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024 or (raw and not raw.endswith(b'\0')):
            raise ValueError('invalid changed-path list')
        changed = [p.decode('utf-8') for p in raw.split(b'\0')[:-1]] if raw else []
        report = assess(args.root,args.course_root,changed)
        print(json.dumps(report,indent=2))
        return int(any(r['status'] != 'structure_ready_for_review' for r in report['results']))
    except (OSError, ValueError, UnicodeError):
        print(json.dumps({'error':'invalid inputs; no assessment performed','graduation':'not_assessed'}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
