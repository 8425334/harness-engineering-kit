const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { PassThrough } = require('node:stream');
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

test('lists agents without a subcommand', () => {
  const listed = run(['--list-agents']);
  assert.equal(listed.status, 0);
  assert.match(listed.stdout, /可用的 AI Agent/);
  assert.doesNotMatch(listed.stdout, /Usage:/);
});

test('supports --option=value arguments', () => {
  const parsed = cliModule.parseArgs(['init', '--agent=claude', '--tier=1', '--prompt=hello world']);
  assert.equal(parsed.options.agent, 'claude');
  assert.equal(parsed.options.tier, '1');
  assert.equal(parsed.options.prompt, 'hello world');
  assert.throws(() => cliModule.parseArgs(['init', '--json=true']));
  assert.throws(() => cliModule.parseArgs(['init', '--tier=3']));
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
  // M3: cmd.exe splits commands at newlines, so the prompt must stay single-line.
  assert.ok(!prompt.includes('\n'), 'agent prompt must be a single line');
  const custom = cliModule.buildAgentPrompt('/tmp/target-project', { sourceRoot: root, prompt: 'line1\nline2' });
  assert.equal(custom, 'line1\nline2');
});

test('json mode warns instead of failing when --agent/--open is supplied', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-cli-'));
  spawnSync('git', ['init', '-q'], { cwd: directory });
  const result = run(['init', '--project-root', directory, '--source-root', root, '--json', '--yes', '--no-check', '--agent', 'gemini', '--open'], { cwd: directory });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stderr, /--json 机器模式/);
  // The deterministic installer itself creates .claude/skills; an agent-driven
  // run would add nothing here, and launching gemini (not installed) would exit 2.
  const claudeEntries = fs.existsSync(path.join(directory, '.claude'))
    ? fs.readdirSync(path.join(directory, '.claude'))
    : [];
  assert.deepEqual(claudeEntries, ['skills'], 'json mode must not open agents');
  const receipt = JSON.parse(result.stdout);
  assert.equal(receipt.read_only, false);
});

test('check prints the gate outcome instead of a read-only plan', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-cli-'));
  spawnSync('git', ['init', '-q'], { cwd: directory });
  const applied = run(['init', '--project-root', directory, '--source-root', root, '--tier', '1', '--direct', '--yes', '--no-check'], { cwd: directory });
  assert.equal(applied.status, 0, applied.stderr);
  const checked = run(['check', '--project-root', directory, '--source-root', root], { cwd: directory });
  assert.equal(checked.status, 2);
  assert.match(checked.stdout, /ONBOARDING CHECK FAILED/);
  assert.doesNotMatch(checked.stdout, /Read-only plan/);
});

test('agent prompt uses the configured Python executable', () => {
  const previous = process.env.HARNESS_PYTHON;
  process.env.HARNESS_PYTHON = '/usr/bin/python3';
  try {
    const prompt = cliModule.buildAgentPrompt('/tmp/target-project', { sourceRoot: root });
    assert.match(prompt, /\/usr\/bin\/python3 /);
  } finally {
    if (previous === undefined) delete process.env.HARNESS_PYTHON;
    else process.env.HARNESS_PYTHON = previous;
  }
});

test('agent prompt names the install scope', () => {
  const light = cliModule.buildAgentPrompt('/tmp/target-project', { sourceRoot: root, tier: '1' });
  const full = cliModule.buildAgentPrompt('/tmp/target-project', { sourceRoot: root, tier: '2' });
  assert.match(light, /轻量接入/);
  assert.match(full, /完整接入/);
});

test('offers full and lightweight install scopes', () => {
  assert.deepEqual(cliModule.TIER_CHOICES.map((choice) => choice.value), ['2', '1']);
  assert.match(cliModule.TIER_CHOICES[0].label, /完整接入/);
  assert.match(cliModule.TIER_CHOICES[1].label, /轻量接入/);
  assert.match(cliModule.usage(), /lightweight/);
});

test('builds the agent menu from installed agents plus a skip entry', () => {
  const agents = [
    { id: 'claude', label: 'Claude Code', kind: 'terminal', installed: true },
    { id: 'codex', label: 'Codex', kind: 'terminal', installed: false },
    { id: 'cursor', label: 'Cursor', kind: 'desktop', installed: true },
  ];
  const items = cliModule.agentMenuItems(agents);
  assert.deepEqual(
    items.map((item) => item.label),
    ['Claude Code', 'Cursor', '跳过 Agent，使用确定性安装'],
  );
  assert.equal(items[0].value.id, 'claude');
  assert.equal(items[0].hint, 'CLI');
  assert.equal(items[1].hint, '桌面端');
  assert.equal(items[2].value, null);
});

test('arrow-key selector moves with the down key and confirms with Enter', async () => {
  const previous = process.env.NO_COLOR;
  process.env.NO_COLOR = '1';
  try {
    const input = new PassThrough();
    input.isTTY = true;
    input.setRawMode = () => {};
    const output = new PassThrough();
    output.isTTY = true;
    let rendered = '';
    output.on('data', (chunk) => { rendered += chunk.toString(); });
    const items = [
      { value: '2', label: '完整接入（Tier 2，默认）' },
      { value: '1', label: '轻量接入（Tier 1）' },
    ];
    const selection = cliModule.selectWithArrows('选择安装范围', items, 0, { input, output });
    await new Promise((resolve) => setImmediate(resolve));
    input.write('\x1b[B');
    input.write('\r');
    assert.equal(await selection, items[1]);
    assert.match(rendered, /选择安装范围/);
    assert.match(rendered, /❯ 完整接入/);
    assert.match(rendered, /❯ 轻量接入/);
  } finally {
    if (previous === undefined) delete process.env.NO_COLOR;
    else process.env.NO_COLOR = previous;
  }
});

test('arrow-key selector falls back to the default item without a TTY', async () => {
  const items = [{ value: 'a', label: 'A' }, { value: 'b', label: 'B' }];
  const input = new PassThrough();
  const output = new PassThrough();
  assert.equal(await cliModule.selectWithArrows('标题', items, 1, { input, output }), items[1]);
});

test('init --json without --yes prints the plan and exits 2', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-cli-'));
  const result = run(['init', '--project-root', directory, '--source-root', root, '--json'], { cwd: directory });
  assert.equal(result.status, 2);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.read_only, true);
  assert.match(result.stderr, /init --yes/);
  assert.equal(fs.existsSync(path.join(directory, 'docs/methodology')), false);
});

test('init --json --yes applies and prints one JSON receipt', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-cli-'));
  spawnSync('git', ['init', '-q'], { cwd: directory });
  const result = run(['init', '--project-root', directory, '--source-root', root, '--json', '--yes', '--no-check'], { cwd: directory });
  assert.equal(result.status, 0, result.stderr);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.read_only, false);
  assert.ok(Array.isArray(payload.results));
  assert.ok(payload.results.some((entry) => entry.target === 'docs/methodology/VERSION'));
  assert.ok(fs.existsSync(path.join(directory, 'docs/methodology/VERSION')));
});

test('init --json --yes runs the post-init check and fails closed on placeholders', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-cli-'));
  spawnSync('git', ['init', '-q'], { cwd: directory });
  const result = run(['init', '--project-root', directory, '--source-root', root, '--json', '--yes'], { cwd: directory });
  assert.equal(result.status, 2);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.check.status, 'failed');
  assert.match(result.stderr, /占位符/);
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
