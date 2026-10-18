import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/validate-students.py'
spec = importlib.util.spec_from_file_location('students', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

HEADINGS = {
  1:['What I Tried To Do','What I Actually Did','What Was Lost','Reflection'],
  2:['Testing Evidence','Reflection'],
  3:["Notes on the Hitchhiker's Guide",'The Task','What Worked','What Failed','Changes to Make'],
  4:['Who You Mentored','Your Mentoring Approach','The Surprises','What You Learned'],
}
TAPE = ['Who Am I?','What Was I Doing?','Current Priorities','Active Conversations',
        'System Status','Quick Reference','Session Notes']


class StudentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'submission'
        self.course = Path(self.temp.name) / 'trusted'
        self.root.mkdir(); self.course.mkdir()
        for n in range(1,5):
            path=self.course/f'challenge-{n}/template.md';path.parent.mkdir()
            path.write_text(self.document(HEADINGS[n], '[Your answer]'))

    def document(self, headings, answer='A specific synthetic answer for structural testing.'):
        return '\n\n'.join('## '+h+'\n\n'+answer for h in headings)+'\n'

    def write(self, path, text):
        target=self.root/path; target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)

    def submission(self, student='alice', n=1):
        path=f'students/{student}/challenge-{n}.md'
        self.write(path,self.document(HEADINGS[n]))
        if n==2:self.write(f'students/{student}/MORNING-TAPE.md',self.document(TAPE))
        return path

    def run_paths(self, paths):
        return m.assess(self.root,self.course,paths)

    def test_each_valid_challenge_is_ready_only_for_review(self):
        paths=[self.submission(n=n) for n in range(1,5)]
        report=self.run_paths(paths)
        self.assertEqual(report['graduation'],'not_assessed')
        self.assertEqual(len(report['results']),4)
        for row in report['results']:
            self.assertEqual(row['status'],'structure_ready_for_review')
            self.assertEqual(row['learning_assessment'],'human_review_required')

    def test_only_changed_student_checked(self):
        self.submission('alice'); path=self.submission('bob')
        self.assertEqual([r['path'] for r in self.run_paths([path])['results']],[path])

    def test_shared_example_never_satisfies_student(self):
        self.write('challenge-1/template.md',self.document(HEADINGS[1]))
        self.write('challenge-1/examples/full.md',self.document(HEADINGS[1]))
        row=self.run_paths(['students/alice/challenge-1.md'])['results'][0]
        self.assertEqual(row['status'],'missing_or_removed')

    def test_other_student_tape_never_substitutes(self):
        self.submission('alice',2)
        path='students/bob/challenge-2.md';self.write(path,self.document(HEADINGS[2]))
        self.assertEqual(self.run_paths([path])['results'][0]['status'],'missing_or_removed')

    def test_unfilled_template_rejected(self):
        path='students/alice/challenge-1.md'
        self.write(path,(self.course/'challenge-1/template.md').read_text())
        self.assertEqual(self.run_paths([path])['results'][0]['status'],'structure_needs_changes')

    def test_missing_section_rejected(self):
        path=self.submission();self.write(path,self.document(HEADINGS[1][:-1]))
        self.assertEqual(self.run_paths([path])['results'][0]['status'],'structure_needs_changes')

    def test_headings_inside_code_fences_not_credit(self):
        path=self.submission();self.write(path,'```markdown\n'+self.document(HEADINGS[1])+'```\n')
        self.assertEqual(self.run_paths([path])['results'][0]['status'],'structure_needs_changes')

    def test_fence_with_trailing_text_does_not_close(self):
        for marker in ('```', '~~~'):
            path=self.submission()
            self.write(path,marker+'markdown\n'+marker+'not-a-closing-fence\n'+
                       self.document(HEADINGS[1])+marker+'\n')
            self.assertEqual(self.run_paths([path])['results'][0]['status'],'structure_needs_changes')

    def test_only_headings_or_empty_bullets_not_credit(self):
        for answer in ('','-\n1.\n- [ ]','[Your answer]'):
            path=self.submission();self.write(path,self.document(HEADINGS[1],answer))
            self.assertEqual(self.run_paths([path])['results'][0]['status'],'structure_needs_changes')

    def test_tape_change_checks_own_challenge_two(self):
        path=self.submission(n=2)
        report=self.run_paths(['students/alice/MORNING-TAPE.md',path])
        self.assertEqual(len(report['results']),1)
        self.assertEqual(report['results'][0]['path'],path)

    def test_tape_requires_sections(self):
        path=self.submission(n=2);self.write('students/alice/MORNING-TAPE.md','Just a title')
        self.assertEqual(self.run_paths([path])['results'][0]['status'],'structure_needs_changes')

    def test_deleted_submission_needs_review(self):
        self.assertEqual(self.run_paths(['students/alice/challenge-1.md'])['results'][0]['status'],'missing_or_removed')

    def test_mixed_students_independent(self):
        good=self.submission('alice');bad='students/bob/challenge-1.md'
        self.write(bad,'## Reflection\nA reflection')
        rows=self.run_paths([good,bad])['results']
        self.assertEqual([r['status'] for r in rows],['structure_ready_for_review','structure_needs_changes'])

    def test_symlink_file_and_directory_rejected(self):
        path=self.submission('alice'); real=self.root/path
        real.rename(real.with_name('real.md'));real.symlink_to('real.md')
        self.assertEqual(self.run_paths([path])['results'][0]['status'],'unreadable_or_unsafe')
        (self.root/'students/bob').symlink_to(self.root/'students/alice',target_is_directory=True)
        self.assertEqual(self.run_paths(['students/bob/challenge-1.md'])['results'][0]['status'],'unreadable_or_unsafe')

    def test_paths_not_shell_split_or_executed(self):
        report=self.run_paths(['students/../../outside','students/a/challenge-1.md\n$(touch injected)',
                               'students/a/notes with spaces.md','README.md'])
        self.assertEqual(report['results'][0]['status'],'invalid_path')
        self.assertEqual(len(report['unassessed_student_paths']),2)
        self.assertFalse((self.root/'injected').exists())

    def test_unrelated_docs_no_assessment(self):
        self.assertEqual(self.run_paths(['README.md','challenge-1/README.md'])['results'],[])

    def test_student_code_is_only_unassessed_path(self):
        self.write('students/alice/exploit.py','raise RuntimeError("do not run")')
        report=self.run_paths(['students/alice/exploit.py'])
        self.assertEqual(report['results'],[])
        self.assertEqual(report['unassessed_student_paths'],['students/alice/exploit.py'])

    def test_oversize_or_invalid_utf8_rejected(self):
        path=self.submission()
        for data in (b'x'*(m.LIMIT+1),b'\xff'):
            (self.root/path).write_bytes(data)
            self.assertEqual(self.run_paths([path])['results'][0]['status'],'unreadable_or_unsafe')

    def test_challenge_three_requires_failures(self):
        path=self.submission(n=3);self.write(path,self.document([h for h in HEADINGS[3] if h!='What Failed']))
        self.assertEqual(self.run_paths([path])['results'][0]['status'],'structure_needs_changes')

    def test_empty_combined_assessment_cannot_hide_missing_failures(self):
        path=self.submission(n=3)
        self.write(path,self.document([h for h in HEADINGS[3] if h!='What Failed'])+'\n## Honest Assessment\n')
        self.assertEqual(self.run_paths([path])['results'][0]['status'],'structure_needs_changes')

    def test_accepted_historical_aliases(self):
        path=self.submission(n=3)
        self.write(path,self.document(['Notes from Hitchhiker’s Guide','The Task I Attempted','Honest Assessment','Changes to My Memory System']))
        self.assertEqual(self.run_paths([path])['results'][0]['status'],'structure_ready_for_review')

    def test_cli_nul_paths_and_exit_status(self):
        path=self.submission(); changed=Path(self.temp.name)/'paths.z';changed.write_bytes(path.encode()+b'\0')
        run=subprocess.run([sys.executable,str(SCRIPT),'--root',str(self.root),'--course-root',str(self.course),
                            '--changed-files',str(changed)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(json.loads(run.stdout)['graduation'],'not_assessed')
        changed.write_bytes(path.encode())
        run=subprocess.run([sys.executable,str(SCRIPT),'--root',str(self.root),'--course-root',str(self.course),
                            '--changed-files',str(changed)],capture_output=True,text=True)
        self.assertEqual(run.returncode,2)

    def test_workflow_is_unprivileged_and_uses_base_code(self):
        workflow=(SCRIPT.parents[1]/'.github/workflows/validate-students.yml').read_text()
        self.assertIn('contents: read',workflow)
        self.assertNotIn('pull_request_target',workflow)
        self.assertNotIn('issues: write',workflow)
        self.assertIn('python3 -I course/tools/validate-students.py',workflow)
        self.assertIn('--course-root course',workflow)
        self.assertIn('git -C submission diff --no-ext-diff --no-textconv --no-renames --name-only -z',workflow)
        self.assertEqual(workflow.count('persist-credentials: false'),2)
        self.assertNotIn('run: submission/',workflow)

if __name__=='__main__':unittest.main()
