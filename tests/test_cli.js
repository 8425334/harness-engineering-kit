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
  assert.match(help.stdout, /harness-engineering-kit uninstall/);
  assert.match(help.stdout, /harness-engineering-kit handoff/);

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
  assert.deepEqual(agents.map((agent) => agent.id), ['claude', 'codex', 'opencode', 'cursor', 'gemini', 'workbuddy', 'trae-work']);
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

test('resolves manual desktop agent aliases without a CLI', () => {
  assert.equal(cliModule.findAgent('workbuddy').kind, 'manual');
  assert.equal(cliModule.findAgent('trae work').id, 'trae-work');
  assert.equal(cliModule.findAgent('trae_work').id, 'trae-work');
  assert.equal(cliModule.findAgent('work-buddy').id, 'workbuddy');
  assert.equal(cliModule.commandAvailable(null), false);
});

test('uses the OpenCode run subcommand for agent prompts', () => {
  const agent = cliModule.findAgent('opencode');
  assert.equal(agent.kind, 'terminal');
  assert.deepEqual(cliModule.agentArguments(agent, '/tmp/project', 'onboard'), ['run', 'onboard']);
  assert.deepEqual(cliModule.agentArguments(cliModule.findAgent('claude'), '/tmp/project', 'onboard'), ['onboard']);
});

test('passes the selected Agent to the onboarding planner', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-plan-agent-'));
  const result = run(['plan', '--project-root', directory, '--source-root', root, '--agent', 'opencode'], { cwd: directory });
  assert.equal(result.status, 0, result.stderr);
  const plan = JSON.parse(result.stdout);
  assert.equal(plan.agent, 'opencode');
  assert.deepEqual(
    plan.actions.filter((action) => action.kind === 'sync-tree').map((action) => action.target),
    ['.opencode/skills/engineering'],
  );
  assert.ok(!plan.actions.some((action) => action.target === 'CLAUDE.md'));
});

test('builds a manual handoff payload without launching an agent', () => {
  const payload = cliModule.handoffPayload('/tmp/target-project', { sourceRoot: root, agent: 'trae-work', tier: '1' }, {
    status: 'fresh',
    installed_version: 'unknown',
    source_version: '0.3.0',
    version_relation: 'fresh',
  });
  assert.equal(payload.agent.id, 'trae-work');
  assert.equal(payload.agent.transport, 'manual-copy');
  assert.match(payload.prompt, /读取项目事实/);
  assert.ok(payload.instructions.some((instruction) => instruction.includes('复制 prompt')));
});

test('handoff command prints a copyable manual prompt', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-handoff-'));
  const result = run(['handoff', '--project-root', directory, '--source-root', root, '--agent', 'workbuddy'], { cwd: directory });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Agent handoff: WorkBuddy \(manual-copy\)/);
  assert.match(result.stdout, /可复制提示词/);
  assert.match(result.stdout, /读取项目事实/);
});

test('handoff JSON is machine-readable and does not write files', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-handoff-'));
  const result = run(['handoff', '--project-root', directory, '--source-root', root, '--agent', 'trae-work', '--json'], { cwd: directory });
  assert.equal(result.status, 0, result.stderr);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.agent.id, 'trae-work');
  assert.equal(payload.agent.transport, 'manual-copy');
  assert.equal(fs.existsSync(path.join(directory, 'docs')), false);
});

test('init can apply then hand off to a no-CLI Agent', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-init-handoff-'));
  spawnSync('git', ['init', '-q'], { cwd: directory });
  const result = run([
    'init', '--project-root', directory, '--source-root', root,
    '--agent', 'workbuddy', '--open', '--yes', '--no-check', '--tier', '1',
  ], { cwd: directory });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /WorkBuddy 不提供可调用 CLI/);
  assert.ok(fs.existsSync(path.join(directory, 'AGENTS.md')));
});

test('builds an agent-first onboarding prompt', () => {
  const prompt = cliModule.buildAgentPrompt('/tmp/target-project', { sourceRoot: root, tier: '1' });
  assert.match(prompt, /只加载当前任务需要的事实/);
  assert.match(prompt, /Tier 是本次目标范围/);
  assert.match(prompt, /升级须同步全部 Tier 1 核心资源/);
  assert.match(prompt, /--plan --json/);
  assert.match(prompt, /--apply/);
  assert.match(prompt, /授权=计划后待确认/);
  assert.match(prompt, /不做中英中转译/);
  assert.match(prompt, /不复述输入/);
  assert.ok(prompt.startsWith(cliModule.AGENT_PROMPT_PREFIX));
  assert.ok(prompt.length <= 650, `default prompt is too verbose: ${prompt.length} characters`);
  // M3: cmd.exe splits commands at newlines, so the prompt must stay single-line.
  assert.ok(!prompt.includes('\n'), 'agent prompt must be a single line');
  const custom = cliModule.buildAgentPrompt('/tmp/target-project', { sourceRoot: root, prompt: 'line1\nline2' });
  assert.equal(custom, 'line1\nline2');
});

test('keeps static prompt instructions before dynamic handoff data', () => {
  const first = cliModule.buildAgentPrompt('/tmp/project-a', { sourceRoot: root, tier: '1' });
  const second = cliModule.buildAgentPrompt('/tmp/project-b', { sourceRoot: root, tier: '2', agent: 'codex' });
  assert.ok(first.startsWith(`${cliModule.AGENT_PROMPT_PREFIX}；参数：`));
  assert.ok(second.startsWith(`${cliModule.AGENT_PROMPT_PREFIX}；参数：`));
  assert.ok(first.indexOf('/tmp/project-a') > first.indexOf('参数：'));
  assert.ok(second.indexOf('/tmp/project-b') > second.indexOf('参数：'));
});

test('json mode warns instead of failing when --agent/--open is supplied', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-cli-'));
  spawnSync('git', ['init', '-q'], { cwd: directory });
  const result = run(['init', '--project-root', directory, '--source-root', root, '--json', '--yes', '--no-check', '--agent', 'gemini', '--open'], { cwd: directory });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stderr, /仅忽略 --open/);
  assert.equal(fs.existsSync(path.join(directory, 'GEMINI.md')), true);
  assert.equal(fs.existsSync(path.join(directory, 'AGENTS.md')), false);
  assert.equal(fs.existsSync(path.join(directory, 'CLAUDE.md')), false);
  assert.equal(fs.existsSync(path.join(directory, '.claude')), false);
  const receipt = JSON.parse(result.stdout);
  assert.equal(receipt.read_only, false);
  assert.equal(receipt.agent, 'gemini');
});

test('init only installs the selected native context and skill', () => {
  for (const [agent, nativeFile, absentFile, skillPath] of [
    ['claude', 'CLAUDE.md', 'AGENTS.md', '.claude/skills/engineering'],
    ['codex', 'AGENTS.md', 'CLAUDE.md', '.agents/skills/engineering'],
    ['opencode', 'AGENTS.md', 'CLAUDE.md', '.opencode/skills/engineering'],
    ['cursor', 'AGENTS.md', 'CLAUDE.md', '.cursor/skills/engineering'],
    ['gemini', 'GEMINI.md', 'AGENTS.md', '.gemini/skills/engineering'],
    ['trae-work', 'AGENTS.md', 'CLAUDE.md', '.trae/skills/engineering'],
  ]) {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-agent-target-'));
    spawnSync('git', ['init', '-q'], { cwd: directory });
    const result = run([
      'init', '--project-root', directory, '--source-root', root,
      '--agent', agent, '--tier', '1', '--json', '--yes', '--no-check',
    ], { cwd: directory });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(fs.existsSync(path.join(directory, nativeFile)), true);
    assert.equal(fs.existsSync(path.join(directory, absentFile)), false);
    assert.equal(fs.existsSync(path.join(directory, skillPath)), true);
  }
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

test('includes manual agents in the interactive menu without claiming a CLI install', () => {
  const items = cliModule.agentMenuItems([
    { id: 'workbuddy', label: 'WorkBuddy', kind: 'manual', installed: false },
  ]);
  assert.equal(items[0].value.id, 'workbuddy');
  assert.equal(items[0].hint, '手动交接');
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

test('parses the uninstall options', () => {
  const parsed = cliModule.parseArgs(['uninstall', '--keep-project-facts', '--yes']);
  assert.equal(parsed.command, 'uninstall');
  assert.equal(parsed.options.keepProjectFacts, true);
  assert.equal(parsed.options.yes, true);
  assert.equal(typeof cliModule.runUninstall, 'function');
  assert.match(cliModule.usage(), /--keep-project-facts/);
});

test('uninstall --json without --yes prints the plan and keeps files', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-uninstall-'));
  spawnSync('git', ['init', '-q'], { cwd: directory });
  const installed = run([
    'init', '--project-root', directory, '--source-root', root,
    '--tier', '1', '--agent', 'codex', '--json', '--yes', '--no-check',
  ], { cwd: directory });
  assert.equal(installed.status, 0, installed.stderr);

  const planned = run(['uninstall', '--project-root', directory, '--source-root', root, '--json'], { cwd: directory });
  assert.equal(planned.status, 2);
  const plan = JSON.parse(planned.stdout);
  assert.equal(plan.mode, 'uninstall');
  assert.equal(plan.read_only, true);
  assert.equal(plan.receipt_source, 'docs/methodology/onboarding.json');
  assert.match(planned.stderr, /uninstall --yes/);
  assert.equal(fs.existsSync(path.join(directory, 'AGENTS.md')), true);
  assert.equal(fs.existsSync(path.join(directory, '.agents/skills/engineering')), true);
});

test('uninstall --json --yes removes installed assets and prints a receipt', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-uninstall-'));
  spawnSync('git', ['init', '-q'], { cwd: directory });
  const installed = run([
    'init', '--project-root', directory, '--source-root', root,
    '--tier', '1', '--agent', 'codex', '--json', '--yes', '--no-check',
  ], { cwd: directory });
  assert.equal(installed.status, 0, installed.stderr);

  const applied = run(['uninstall', '--project-root', directory, '--source-root', root, '--json', '--yes'], { cwd: directory });
  assert.equal(applied.status, 0, applied.stderr);
  const receipt = JSON.parse(applied.stdout);
  assert.equal(receipt.read_only, false);
  assert.ok(receipt.results.some((entry) => entry.result === 'removed'));
  assert.equal(fs.existsSync(path.join(directory, 'AGENTS.md')), false);
  assert.equal(fs.existsSync(path.join(directory, '.agents/skills/engineering')), false);
  assert.equal(fs.existsSync(path.join(directory, 'docs/methodology/onboarding.json')), false);
  assert.equal(fs.existsSync(path.join(directory, 'docs/methodology/uninstall.json')), true);
});

test('uninstall --keep-project-facts preserves project configuration', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-uninstall-'));
  spawnSync('git', ['init', '-q'], { cwd: directory });
  const installed = run([
    'init', '--project-root', directory, '--source-root', root,
    '--tier', '1', '--agent', 'codex', '--json', '--yes', '--no-check',
  ], { cwd: directory });
  assert.equal(installed.status, 0, installed.stderr);

  const applied = run([
    'uninstall', '--project-root', directory, '--source-root', root,
    '--json', '--yes', '--keep-project-facts',
  ], { cwd: directory });
  assert.equal(applied.status, 0, applied.stderr);
  const receipt = JSON.parse(applied.stdout);
  assert.equal(receipt.keep_project_facts, true);
  assert.equal(fs.existsSync(path.join(directory, 'AGENTS.md')), true);
  assert.equal(fs.existsSync(path.join(directory, 'ai.json')), true);
  assert.equal(fs.existsSync(path.join(directory, 'docs/methodology/agent-policy.yaml')), true);
  assert.equal(fs.existsSync(path.join(directory, 'docs/methodology/core')), false);
});

test('uninstall explains how to confirm in a non-interactive shell', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-uninstall-'));
  const result = run(['uninstall', '--project-root', directory, '--source-root', root], { cwd: directory });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /uninstall --yes/);
});

test('uninstall without a receipt never deletes files it cannot verify', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-uninstall-'));
  spawnSync('git', ['init', '-q'], { cwd: directory });
  fs.writeFileSync(path.join(directory, 'AGENTS.md'), '# Project rules\n');
  fs.writeFileSync(path.join(directory, 'ai.json'), '{"name":"mine"}\n');

  const applied = run([
    'uninstall', '--project-root', directory, '--source-root', root, '--json', '--yes',
  ], { cwd: directory });

  assert.equal(applied.status, 0, applied.stderr);
  const receipt = JSON.parse(applied.stdout);
  assert.equal(receipt.receipt_source, 'source-analysis');
  assert.deepEqual(receipt.results.filter((entry) => entry.result === 'removed'), []);
  assert.equal(fs.existsSync(path.join(directory, 'AGENTS.md')), true);
  assert.equal(fs.existsSync(path.join(directory, 'ai.json')), true);
});

test('parses the repair and doctor commands', () => {
  const parsed = cliModule.parseArgs(['repair', '--agent', 'codex', '--yes', '--json']);
  assert.equal(parsed.command, 'repair');
  assert.equal(parsed.options.agent, 'codex');
  assert.equal(parsed.options.yes, true);
  assert.equal(typeof cliModule.runRepair, 'function');
  assert.equal(typeof cliModule.invokeRepair, 'function');
  assert.match(cliModule.usage(), /harness-engineering-kit doctor/);
  assert.match(cliModule.usage(), /harness-engineering-kit repair/);
});

function installHarnessProject(prefix) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  spawnSync('git', ['init', '-q'], { cwd: directory });
  const installed = run([
    'init', '--project-root', directory, '--source-root', root,
    '--tier', '1', '--agent', 'codex', '--json', '--yes', '--no-check',
  ], { cwd: directory });
  assert.equal(installed.status, 0, installed.stderr);
  return directory;
}

test('doctor prints a read-only diagnosis and never writes', () => {
  const directory = installHarnessProject('harness-doctor-');
  const skill = path.join(directory, '.agents/skills/engineering');
  fs.rmSync(skill, { recursive: true, force: true });

  const result = run(['doctor', '--project-root', directory, '--source-root', root, '--json'], { cwd: directory });
  assert.equal(result.status, 2);
  const diagnosis = JSON.parse(result.stdout);
  assert.equal(diagnosis.mode, 'diagnose');
  assert.equal(diagnosis.read_only, true);
  assert.equal(diagnosis.agent, 'codex');
  assert.equal(typeof diagnosis.environment.python.ok, 'boolean');
  assert.ok(diagnosis.findings.some((finding) => finding.id === 'skill-missing'));
  assert.equal(fs.existsSync(skill), false);
  assert.equal(fs.existsSync(path.join(directory, 'docs/methodology/repair.json')), false);
});

test('doctor reports a healthy install without findings', () => {
  const directory = installHarnessProject('harness-doctor-healthy-');
  const result = run(['doctor', '--project-root', directory, '--source-root', root, '--json'], { cwd: directory });
  assert.equal(result.status, 0, result.stdout);
  const diagnosis = JSON.parse(result.stdout);
  assert.ok(diagnosis.status.startsWith('healthy'), diagnosis.status);
  assert.equal(fs.existsSync(path.join(directory, 'docs/methodology/repair.json')), false);
});

test('repair --json without --yes prints the diagnosis and keeps files', () => {
  const directory = installHarnessProject('harness-repair-plan-');
  fs.rmSync(path.join(directory, '.agents/skills/engineering'), { recursive: true, force: true });

  const result = run(['repair', '--project-root', directory, '--source-root', root, '--json'], { cwd: directory });
  assert.equal(result.status, 2);
  const diagnosis = JSON.parse(result.stdout);
  assert.equal(diagnosis.read_only, true);
  assert.match(result.stderr, /repair --yes/);
  assert.equal(fs.existsSync(path.join(directory, '.agents/skills/engineering')), false);
});

test('repair --json --yes restores canonical assets and writes a receipt', () => {
  const directory = installHarnessProject('harness-repair-apply-');
  fs.rmSync(path.join(directory, '.agents/skills/engineering'), { recursive: true, force: true });
  fs.rmSync(path.join(directory, 'docs/methodology/core/change-lifecycle.md'), { force: true });

  const result = run([
    'repair', '--project-root', directory, '--source-root', root, '--json', '--yes',
  ], { cwd: directory });
  assert.equal(result.status, 0, result.stdout || result.stderr);
  const receipt = JSON.parse(result.stdout);
  assert.equal(receipt.mode, 'apply');
  assert.equal(receipt.read_only, false);
  assert.equal(receipt.status, 'repaired');
  assert.equal(receipt.verification.status, 'passed');
  assert.equal(fs.existsSync(path.join(directory, '.agents/skills/engineering/SKILL.md')), true);
  assert.equal(fs.existsSync(path.join(directory, 'docs/methodology/core/change-lifecycle.md')), true);
  assert.equal(fs.existsSync(path.join(directory, 'docs/methodology/repair.json')), true);
});
