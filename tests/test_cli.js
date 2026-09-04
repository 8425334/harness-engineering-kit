const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const test = require('node:test');

const root = path.resolve(__dirname, '..');
const cli = path.join(root, 'bin', 'harness-engineering-kit.js');
const cliModule = require(cli);

function run(args, options = {}) {
  return spawnSync(process.execPath, [cli, ...args], {
    cwd: options.cwd || root,
    encoding: 'utf8',
    env: { ...process.env, ...(options.env || {}) },
  });
}

test('prints help and version', () => {
  const help = run(['--help']);
  assert.equal(help.status, 0);
  assert.match(help.stdout, /harness-engineering-kit init/);

  const version = run(['--version']);
  assert.equal(version.status, 0);
  assert.equal(version.stdout.trim(), fs.readFileSync(path.join(root, 'VERSION'), 'utf8').trim());
});

test('exposes the hek npm alias and agent listing', () => {
  const packageMetadata = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
  assert.equal(packageMetadata.bin.hek, 'bin/harness-engineering-kit.js');

  const listed = run(['agents', '--json']);
  assert.equal(listed.status, 0);
  const agents = JSON.parse(listed.stdout);
  assert.deepEqual(agents.map((agent) => agent.id), ['claude', 'codex', 'cursor', 'gemini']);
  assert.ok(agents.every((agent) => typeof agent.installed === 'boolean'));
});

test('parses agent and opening controls', () => {
  const parsed = cliModule.parseArgs(['init', '--agent', 'codex', '--no-open', '--prompt', 'hello']);
  assert.equal(parsed.command, 'init');
  assert.equal(parsed.options.agent, 'codex');
  assert.equal(parsed.options.noOpen, true);
  assert.equal(parsed.options.prompt, 'hello');
});

test('builds an agent-first onboarding prompt', () => {
  const prompt = cliModule.buildAgentPrompt('/tmp/target-project', { sourceRoot: root, tier: '1' });
  assert.match(prompt, /读取项目事实/);
  assert.match(prompt, /--plan --json/);
  assert.match(prompt, /--apply/);
  assert.match(prompt, /等待用户明确确认/);
});

test('plan delegates to the packaged Python core', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-cli-'));
  const planned = run(['plan', '--project-root', directory, '--source-root', root, '--tier', '1'], { cwd: directory });
  assert.equal(planned.status, 0, planned.stderr);
  const payload = JSON.parse(planned.stdout);
  assert.equal(payload.status, 'fresh');
  assert.equal(payload.tier, 1);
  assert.equal(payload.source_root, root);
});

test('non-interactive init explains how to confirm', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-cli-'));
  const initialized = run(['init', '--project-root', directory, '--source-root', root], { cwd: directory });
  assert.equal(initialized.status, 2);
  assert.match(initialized.stderr, /init --yes/);
});

test('reports an unavailable configured Python executable', () => {
  const result = run(['plan'], { env: { HARNESS_PYTHON: 'definitely-not-a-python' } });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /Python 3 is required/);
});
