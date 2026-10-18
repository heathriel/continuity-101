const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const workflow = fs.readFileSync(path.join(__dirname, '../.github/workflows/validate.yml'), 'utf8');
// Execute the reporting step's actual script, without running actions or making API calls.
const marker = '        script: |\n';
const scripts = workflow.split(marker);
assert.equal(scripts.length, 2, 'Expected exactly one github-script block');
const source = scripts[1].split('\n').map(line => {
  assert.ok(line === '' || line.startsWith('          '), 'Unexpected script indentation');
  return line.slice(10);
}).join('\n');
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

async function report({ fork = false, actor = 'student', status = 'success', error } = {}) {
  const result = { comments: [], summaries: [], warnings: [], writes: 0 };
  const core = {
    summary: {
      addRaw(value) { result.summaries.push(value); return this; },
      async write() { result.writes++; },
    },
    info() {},
    warning(value) { result.warnings.push(value); },
  };
  const context = {
    actor,
    repo: { owner: 'course', repo: 'course' },
    issue: { number: 7 },
    payload: { pull_request: { head: { repo: { full_name: fork ? 'student/course' : 'course/course' } } } },
  };
  const github = { rest: { issues: { async createComment(comment) {
    result.comments.push(comment);
    if (fork) throw new Error('Resource not accessible by integration');
    if (error) throw error;
  } } } };
  const script = source.replaceAll('${{ job.status }}', status);
  await new AsyncFunction('github', 'context', 'core', script)(github, context, core);
  return result;
}

test('fork success writes summary without attempting a comment', async () => {
  const result = await report({ fork: true });
  assert.equal(result.comments.length, 0);
  assert.equal(result.writes, 1);
  assert.match(result.summaries.join(''), /Validation Passed/);
  assert.match(result.summaries.join(''), /human review/);
});

test('fork failure remains visible in summary', async () => {
  const result = await report({ fork: true, status: 'failure' });
  assert.equal(result.comments.length, 0);
  assert.match(result.summaries.join(''), /Validation Failed/);
});

test('same-repository PR retains comment and summary', async () => {
  const result = await report();
  assert.equal(result.comments.length, 1);
  assert.equal(result.comments[0].issue_number, 7);
  assert.equal(result.comments[0].body, result.summaries[0]);
  assert.equal(result.writes, 1);
});

test('Dependabot read-only token does not attempt commenting', async () => {
  const result = await report({ actor: 'dependabot[bot]' });
  assert.equal(result.comments.length, 0);
  assert.equal(result.writes, 1);
});

test('optional comment failure warns without failing validation reporting', async () => {
  const result = await report({ error: new Error('API unavailable') });
  assert.equal(result.writes, 1);
  assert.equal(result.warnings.length, 1);
  assert.match(result.warnings[0], /API unavailable/);
});

test('reporting stays unconditional without privileged PR execution', () => {
  assert.match(workflow, /- name: Report validation result\n      if: always\(\)/);
  assert.doesNotMatch(workflow, /pull_request_target:/);
  assert.match(workflow, /  pull_request:/);
});
