# Student-specific structural assessment

The documented submission is `students/YOUR-NAME/challenge-N.md`, copied from the
shared template and filled out in the student's own directory. The existing
challenge-content workflow validates shared course files, not individual student
work. This separate workflow closes that gap without changing course content or
replacing human review.

## What students submit

Use a unique student handle of 1–64 ASCII letters, digits, hyphens or underscores,
starting with a letter or digit. For each challenge submit:

- `students/YOUR-NAME/challenge-1.md`
- `students/YOUR-NAME/challenge-2.md` plus `students/YOUR-NAME/MORNING-TAPE.md`
- `students/YOUR-NAME/challenge-3.md`
- `students/YOUR-NAME/challenge-4.md`

Do not overwrite the shared templates. The Challenge 2 tape belongs in the same
student directory: another student's file or the shared example is not a
substitute. Sanitize submitted examples; do not include credentials, private
messages, personal contact information, or sensitive live operating details.
Nothing here grants permission to retain information, contact someone, restart a
session or run another agent. Perform any course exercise only within the human
operator's explicit authority and normal stop/reset controls.

## Automated checks

`Check Student Submission Structure` runs on `pull_request` changes to `students/**`.
It inspects only changed challenge files, plus the same student's Challenge 2 when
their MORNING-TAPE changes. Multiple students are assessed independently.

The validator checks these H2 sections for some non-template text:

| Challenge | Required topics / accepted headings |
| --- | --- |
| 1 | What I Tried To Do; What I Actually Did; What Was Lost / What I Lost; Reflection |
| 2 | Testing Evidence; Reflection; separate same-student MORNING-TAPE |
| 3 | Notes on/from [the] Hitchhiker…; The Task…; What Worked + What Failed, or Honest Assessment; Changes to Make / Changes to My Memory System |
| 4 | Who You/I Mentored; Your/My Mentoring Approach; The Surprises / What Surprised…; What You Learned / How Teaching Changed… |

The MORNING-TAPE requires non-template text under Who Am I?, What Was I Doing?,
Current Priorities, Active Conversations, System Status, Quick Reference, and
Session Notes. Customized additional sections are welcome. The small explicit
heading vocabulary includes the existing student examples; unrecognized customized
headings need renaming or a reviewed validator improvement, not a fabricated answer.
An honest statement that something failed or is not applicable is acceptable
structural content. Do not turn an incomplete experiment into a success claim to
satisfy a check.

Code-fenced examples do not supply required headings or answers. Blank fields,
empty bullets and exact template prompts do not count as answers. This is a
lightweight Markdown heuristic, not a complete Markdown parser or a measure of
answer quality: a plausible sentence can satisfy it while saying nothing true.

Statuses:
- `structure_ready_for_review`: selected structure was present; human review needed.
- `structure_needs_changes`: required section/content missing.
- `missing_or_removed`: submission or required same-student attachment absent.
- `unreadable_or_unsafe`: malformed, oversized, symlink, device, or unsafe file.
- `invalid_path`: unsafe changed student path.

Other files under a student's directory are listed as unassessed. A documentation-
only change produces no submission assessment, not a false graduation. Deletions
and renames are deliberately visible: Git rename detection is disabled, so moving
a submission yields the old missing path and the new path separately. Intentional
removals may require reviewer judgment despite a failing structural check; never
restore unwanted personal material merely to make CI green.

## Human review remains essential

Every result leaves learning assessment to a human and graduation unassessed.
Review the actual experience, evidence limitations, simulation versus real reset,
what failed, permission, reflection, mentoring and the student's next adjustment.
For example, a well-structured simulated mentoring account is not proof that
someone was actually mentored. Neither the workflow nor a matching heading updates
REVIEWERS.md, approves a PR, merges, graduates a student or executes recovery steps.
The report does not establish that the PR author owns the student handle.

## Running locally

Python 3.9+ and a POSIX system with `O_NOFOLLOW` / directory-relative file access
are required. No package install, network, credentials or student execution.

```sh
git diff --no-ext-diff --no-textconv --no-renames --name-only -z BASE...HEAD -- students/ > /tmp/student-paths.z
python3 -I tools/validate-students.py --root . --course-root /path/to/trusted-course --changed-files /tmp/student-paths.z
python3 -m unittest discover -s tests -p 'test_validate_students.py' -v
```

`--root` is the submitted checkout. `--course-root` must be a separate trusted base
revision when checking untrusted contributions: the validator removes prompts from
those trusted templates, not templates edited by the submitter. Changed paths are
NUL-delimited rather than shell-split. Exit 0 means all selected structures were
ready for review, or no recognized submissions changed; 1 means structural issues;
2 means invalid inputs. Full JSON is printed, with no student answer excerpts.

## CI trust boundary and integration

This is a new, separate workflow; the previous shared-course validation/reporting
workflow is unchanged. It coexists with the earlier fork-safe comment fix and does
not require stacking on that patch. Once this contribution is merged, subsequent
student PRs run the base revision's validator and templates from `course/`, against
submission data in `submission/`. The initial feature PR adds no student files, so
this new workflow does not run on itself: its tests must be reviewed/run locally.
A feature PR that also adds students would lack the validator in its base and fail;
keep first installation separate. Hosted Actions execution has not been verified
by the local test suite.

The job has only `contents: read`, persists no checkout credentials, uses no secrets,
and makes no PR comments. It uses `pull_request`, never `pull_request_target`.
No student scripts, imports, links or instructions are executed by the validator;
Python isolated mode also prevents current-directory imports. It refuses symlink
components and non-regular files and limits each Markdown file to 256 KiB.
The caller-selected roots and trusted base revision remain trust assumptions;
hard links or a malicious filesystem are outside this local path guarantee.
As with ordinary GitHub Actions, a contributor can propose workflow changes: human
review must inspect those, and repository-level Actions/security settings still
apply. This workflow is not a security sandbox for arbitrary contributed workflows.
