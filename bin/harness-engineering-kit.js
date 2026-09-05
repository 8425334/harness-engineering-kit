#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');
const { spawnSync } = require('node:child_process');

const packageRoot = path.resolve(__dirname, '..');
const metadata = JSON.parse(fs.readFileSync(path.join(packageRoot, 'package.json'), 'utf8'));

const AGENTS = [
  { id: 'claude', label: 'Claude Code', command: 'claude', kind: 'terminal' },
  { id: 'codex', label: 'Codex', command: 'codex', kind: 'terminal' },
  { id: 'cursor', label: 'Cursor', command: 'cursor', kind: 'desktop' },
  { id: 'gemini', label: 'Gemini CLI', command: 'gemini', kind: 'terminal' },
  { id: 'workbuddy', label: 'WorkBuddy', aliases: ['work-buddy'], command: null, kind: 'manual' },
  { id: 'trae-work', label: 'Trae Work', aliases: ['trae', 'trae work'], command: null, kind: 'manual' },
];

const DEFAULT_AGENT_PROMPT = '请在当前项目完成 Harness Engineering Kit 初始化：先读取项目中的 AGENTS.md 或 CLAUDE.md 与 docs/methodology/agent-policy.yaml，再根据需要继续工作。';

const TIER_CHOICES = [
  { value: '2', label: '完整接入（Tier 2，默认）', hint: '核心控制面 + Fitness 门禁 + 经验记忆' },
  { value: '1', label: '轻量接入（Tier 1）', hint: '仅核心控制面' },
];

const KEY_HINT = '（↑/↓ 移动，Enter 确认，Ctrl+C 取消）';
const VALUE_OPTIONS = new Set(['--agent', '--prompt', '--project-root', '--source-root', '--tier']);

function usage() {
  return `Harness Engineering Kit ${metadata.version}

Usage:
  harness-engineering-kit init [options]    Plan, confirm, install, and check
  harness-engineering-kit plan [options]    Print a read-only JSON plan
  harness-engineering-kit check [options]   Run deterministic checks
  harness-engineering-kit handoff [options] Generate a prompt for a desktop Agent without CLI
  harness-engineering-kit agents [options]  List supported AI agents

Options:
  --project-root <path>  Target project (default: current Git root/current directory)
  --source-root <path>   Kit source (default: installed package)
  --tier <1|2>           Install scope: 1 = lightweight, 2 = full (default: 2)
  --yes                  Apply init without an interactive confirmation
  --apply                Apply init without an interactive confirmation
  --plan                 Make init read-only
  --no-check             Skip the post-init check
  --agent <name>         Agent to open or hand off (claude, codex, cursor, gemini, workbuddy, trae-work)
  --open                 Open the selected agent in non-interactive mode
  --no-open              Do not open an agent after init
  --direct               Run the deterministic installer; --agent and HEK_AGENT are ignored
  --prompt <text>        Initial prompt sent to a terminal agent
  --list-agents          List supported agents and installation status
  --json                 Machine-readable output: never opens an agent and never prompts;
                         without --yes init prints the plan and exits 2; with --yes it
                         applies, checks, and prints one JSON receipt
  -h, --help             Show this help
  -v, --version          Show the version

The init command never deletes legacy files or overwrites existing project facts.
Interactive init asks for the install scope first (full or lightweight, chosen with
the arrow keys when --tier is not given), then opens the selected Agent; pick the
skip entry for the deterministic flow, and it falls back automatically when no agent
is installed. Set HARNESS_PYTHON to select a Python executable explicitly.
`;
}

function applyOption(result, name, value) {
  if (!value || value.startsWith('-')) throw new Error(`${name} requires a value`);
  if (name === '--tier' && !['1', '2'].includes(value)) throw new Error('--tier must be 1 or 2');
  const optionName = name.slice(2).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
  result.options[optionName] = value;
}

function parseArgs(argv) {
  const result = { command: null, options: {} };
  const args = [...argv];
  while (args.length) {
    const token = args.shift();
    if (!result.command && !token.startsWith('-')) {
      result.command = token;
      continue;
    }
    if (token.startsWith('--') && token.includes('=')) {
      const separator = token.indexOf('=');
      const name = token.slice(0, separator);
      if (!VALUE_OPTIONS.has(name)) throw new Error(`unknown option: ${token}`);
      applyOption(result, name, token.slice(separator + 1));
      continue;
    }
    if (token === '-h' || token === '--help') result.options.help = true;
    else if (token === '-v' || token === '--version') result.options.version = true;
    else if (token === '--json') result.options.json = true;
    else if (token === '--yes') result.options.yes = true;
    else if (token === '--apply') result.options.apply = true;
    else if (token === '--plan') result.options.plan = true;
    else if (token === '--no-check') result.options.noCheck = true;
    else if (token === '--open') result.options.open = true;
    else if (token === '--no-open') result.options.noOpen = true;
    else if (token === '--direct') result.options.direct = true;
    else if (token === '--list-agents') result.options.listAgents = true;
    else if (VALUE_OPTIONS.has(token)) {
      applyOption(result, token, args.shift());
    } else {
      throw new Error(`unknown option: ${token}`);
    }
  }
  return result;
}

function commandAvailable(command) {
  if (!command) return false;
  const probe = process.platform === 'win32'
    ? spawnSync('where', [command], { stdio: 'ignore', shell: true })
    : spawnSync('/bin/sh', ['-c', 'command -v "$1" >/dev/null 2>&1', 'hek', command], { stdio: 'ignore' });
  return probe.status === 0;
}

function availableAgents() {
  return AGENTS.map((agent) => ({
    ...agent,
    installed: agent.kind === 'manual' ? false : commandAvailable(agent.command),
    available: agent.kind === 'manual' || commandAvailable(agent.command),
  }));
}

function printAgents(asJson = false) {
  const agents = availableAgents();
  if (asJson) {
    console.log(JSON.stringify(agents, null, 2));
    return agents;
  }
  console.log('可用的 AI Agent：');
  agents.forEach((agent, index) => {
    const status = agent.kind === 'manual'
      ? '✓ 手动交接'
      : (agent.installed ? '✓ 已安装' : '— 未找到命令');
    console.log(`  ${index + 1}. ${agent.label} (${agent.id}) ${status}`);
  });
  return agents;
}

function findAgent(value) {
  if (!value) return null;
  const normalized = String(value).toLowerCase().trim().replace(/[\s_]+/g, '-');
  return AGENTS.find((agent) => {
    const names = [agent.id, agent.command, ...(agent.aliases || [])]
      .filter(Boolean)
      .map((name) => String(name).toLowerCase().trim().replace(/[\s_]+/g, '-'));
    return names.includes(normalized);
  }) || null;
}

function agentWillOpen(options) {
  if (options.noOpen) return false;
  return Boolean(options.open) || (process.stdin.isTTY && process.stdout.isTTY);
}

function selectWithArrows(title, items, defaultIndex = 0, io = {}) {
  const input = io.input || process.stdin;
  const output = io.output || process.stdout;
  if (!input.isTTY || !output.isTTY || typeof input.setRawMode !== 'function') {
    return Promise.resolve(items[defaultIndex]);
  }
  const colored = !process.env.NO_COLOR;
  const accent = (text) => (colored ? `\x1b[36m${text}\x1b[0m` : text);
  const dim = (text) => (colored ? `\x1b[2m${text}\x1b[0m` : text);
  const wasRaw = Boolean(input.isRaw);
  return new Promise((resolve) => {
    let index = Math.min(Math.max(defaultIndex, 0), items.length - 1);
    const paint = () => {
      items.forEach((item, i) => {
        const selected = i === index;
        const pointer = selected ? `${accent('❯')} ` : '  ';
        const label = selected ? accent(item.label) : item.label;
        const hint = item.hint ? `  ${dim(item.hint)}` : '';
        output.write(`${pointer}${label}${hint}\n`);
      });
    };
    const repaint = () => {
      output.write(`\x1b[${items.length}A\x1b[J`);
      paint();
    };
    const release = () => {
      input.setRawMode(wasRaw);
      input.removeListener('keypress', onKeypress);
      output.write(`\x1b[${items.length}A\x1b[J\x1b[?25h`);
    };
    const onKeypress = (_, key) => {
      if (!key) return;
      if (key.ctrl && key.name === 'c') {
        release();
        output.write('\n');
        process.exit(130);
      }
      if (key.name === 'up' && index > 0) index -= 1;
      else if (key.name === 'down' && index < items.length - 1) index += 1;
      else if (key.name === 'enter' || key.name === 'return') {
        release();
        return resolve(items[index]);
      } else return;
      repaint();
    };
    readline.emitKeypressEvents(input);
    input.setRawMode(true);
    input.on('keypress', onKeypress);
    output.write(`\x1b[?25l${title}${dim(KEY_HINT)}\n`);
    paint();
  });
}

function agentMenuItems(agents) {
  return [
    ...agents.filter((agent) => agent.installed || agent.kind === 'manual').map((agent) => ({
      value: agent,
      label: agent.label,
      hint: agent.kind === 'manual' ? '手动交接' : (agent.kind === 'desktop' ? '桌面端' : 'CLI'),
    })),
    { value: null, label: '跳过 Agent，使用确定性安装', hint: '直接由 hek 执行计划与检查' },
  ];
}

async function selectTier() {
  const choice = await selectWithArrows('选择安装范围', TIER_CHOICES);
  console.log(`✓ 安装范围: ${choice.label}`);
  return choice.value;
}

async function selectAgent(options) {
  const requested = options.agent || process.env.HEK_AGENT;
  if (requested) {
    const agent = findAgent(requested);
    if (!agent) throw new Error(`不支持的 AI Agent: ${requested}。使用 --list-agents 查看选项。`);
    if (agent.kind !== 'manual' && agentWillOpen(options) && !commandAvailable(agent.command)) {
      throw new Error(`${agent.label} 命令未找到。请先安装它，或使用 --no-open 完成初始化。`);
    }
    return agent;
  }
  if (!process.stdin.isTTY || !process.stdout.isTTY) return null;
  const agents = availableAgents();
  if (!agents.some((agent) => agent.installed || agent.kind === 'manual')) {
    console.log('未检测到已安装的 AI Agent，进入确定性安装流程（安装后可重新运行 hek init）。');
    return null;
  }
  const choice = await selectWithArrows('选择要打开的 AI Agent', agentMenuItems(agents));
  if (!choice.value) {
    console.log('✓ 已跳过 Agent，使用确定性安装。');
    return null;
  }
  console.log(`✓ 已选择 Agent: ${choice.value.label}`);
  return choice.value;
}

function windowsArgument(value) {
  let escaped = '';
  for (const char of String(value)) {
    if (char === '"') escaped += '\\"';
    else if (char === '\\') escaped += '\\\\';
    else escaped += char;
  }
  return `"${escaped}"`;
}

function openAgent(agent, projectRoot, prompt) {
  if (!agent) return 0;
  let text = prompt || DEFAULT_AGENT_PROMPT;
  if (agent.kind === 'manual') {
    console.log(`\n${agent.label} 不提供可调用 CLI，已生成手动交接内容。`);
    console.log(`请在 ${agent.label} 中打开项目：${projectRoot}`);
    console.log('复制下面的提示词发送给 Agent：');
    console.log(text);
    console.log('Agent 必须先执行只读 plan，得到确认后再 apply 和 check。\n');
    return 0;
  }
  if (process.platform === 'win32') {
    // cmd.exe treats newlines as command separators; keep the argument single-line.
    text = String(text).replace(/\r?\n/g, ' ');
  }
  const args = agent.kind === 'desktop' ? [projectRoot] : [text];
  console.log(`正在打开 ${agent.label}…`);
  let child;
  if (process.platform === 'win32') {
    const command = [agent.command, ...args].map(windowsArgument).join(' ');
    child = spawnSync(command, { cwd: projectRoot, stdio: 'inherit', shell: true });
  } else {
    child = spawnSync(agent.command, args, { cwd: projectRoot, stdio: 'inherit' });
  }
  if (child.error) {
    console.error(`无法打开 ${agent.label}: ${child.error.message}`);
    return 2;
  }
  return typeof child.status === 'number' ? child.status : 2;
}

function findPython() {
  const configured = process.env.HARNESS_PYTHON;
  const candidates = configured
    ? [[configured, []]]
    : [
        ['python3', []],
        ['python', []],
        ...(process.platform === 'win32' ? [['py', ['-3']]] : []),
      ];
  for (const [command, prefix] of candidates) {
    const probe = spawnSync(command, [...prefix, '--version'], { stdio: 'ignore' });
    if (!probe.error && probe.status === 0) return { command, args: prefix };
  }
  throw new Error('Python 3 is required. Install Python 3 or set HARNESS_PYTHON to its executable path.');
}

function pythonCommand() {
  try {
    const interpreter = findPython();
    return [interpreter.command, ...interpreter.args].join(' ');
  } catch (_) {
    return 'python3';
  }
}

function buildAgentPrompt(projectRoot, options) {
  const sourceRoot = path.resolve(options.sourceRoot || packageRoot);
  const tier = options.tier || '2';
  const approval = options.yes || options.apply
    ? '用户已通过命令参数预先确认；完成只读检查后直接应用。'
    : '先展示只读计划并等待用户明确确认，确认前不得写入文件。';
  const parts = [
    '请作为 Harness Engineering Kit 的项目接入 Agent，完成当前项目初始化或增量升级。',
    `目标项目：${projectRoot}`,
    `Kit 源码：${sourceRoot}`,
    `安装范围：Tier ${tier}（${tier === '1' ? '轻量接入' : '完整接入'}）`,
    approval,
    '先读取项目事实（包括现有的 AGENTS.md、CLAUDE.md、ai.json、AI.md 和项目配置），识别真实技术栈、命令、目录边界与已有接入状态；Tier 只表示本次期望的安装范围，不表示 Tier 1 已经安装，任何低版本到高版本升级都必须核对并同步所有 Tier 1 核心资源。',
    `使用 canonical onboarding 脚本生成计划：${pythonCommand()} "${path.join(sourceRoot, 'scripts', 'onboard.py')}" --project-root "${projectRoot}" --source-root "${sourceRoot}" --tier ${tier} --plan --json`,
    '根据项目事实补齐或调整配置占位符；保留已有配置和旧入口，不要盲目覆盖或删除。得到确认后，使用同一脚本执行 --apply，再执行 --check。',
    '最后汇报创建、更新、保留的文件、检查结果和仍需人工决策的事项。',
  ];
  // Keep the prompt single-line: Windows passes it through cmd.exe, where a
  // newline would split the command and truncate the onboarding contract.
  return options.prompt || parts.map((part) => part.replace(/[。]$/, '')).join('；') + '。';
}

function handoffPayload(projectRoot, options, plan) {
  const agent = findAgent(options.agent || 'workbuddy');
  if (!agent) throw new Error(`不支持的 AI Agent: ${options.agent}`);
  return {
    schema_version: 1,
    agent: { id: agent.id, label: agent.label, kind: agent.kind, transport: agent.kind === 'manual' ? 'manual-copy' : agent.kind },
    project_root: projectRoot,
    source_root: path.resolve(options.sourceRoot || packageRoot),
    prompt: buildAgentPrompt(projectRoot, options),
    plan,
    instructions: agent.kind === 'manual'
      ? ['在桌面 Agent 中打开 project_root', '复制 prompt 发送给 Agent', '确认只读 plan 后才允许 apply']
      : ['使用 init --agent <id> --open 交给 CLI Agent 执行'],
  };
}

function runHandoff(options) {
  const planned = invoke('plan', { ...options, json: true }, true);
  if (planned.status !== 0) {
    process.stdout.write(planned.stdout || '');
    process.stderr.write(planned.stderr || '');
    return planned.status || 2;
  }
  const plan = parsePlan(planned.stdout);
  if (!plan) {
    console.error('无法解析 onboarding plan，无法生成 Agent handoff。');
    return 2;
  }
  const projectRoot = plan && plan.project_root
    ? plan.project_root
    : (options.projectRoot ? path.resolve(options.projectRoot) : process.cwd());
  const payload = handoffPayload(projectRoot, options, plan);
  if (options.json) {
    process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
  } else {
    console.log(`Agent handoff: ${payload.agent.label} (${payload.agent.transport})`);
    console.log(`项目: ${payload.project_root}`);
    console.log(`计划状态: ${payload.plan.status} | 版本: ${payload.plan.installed_version} → ${payload.plan.source_version}（${payload.plan.version_relation}）`);
    console.log('\n--- 可复制提示词 ---\n');
    console.log(payload.prompt);
    console.log('\n--- 操作 ---');
    payload.instructions.forEach((instruction, index) => console.log(`${index + 1}. ${instruction}`));
  }
  return 0;
}

function baseArgs(options) {
  const args = [];
  if (options.projectRoot) args.push('--project-root', path.resolve(options.projectRoot));
  args.push('--source-root', path.resolve(options.sourceRoot || packageRoot));
  if (options.tier) args.push('--tier', options.tier);
  if (options.json) args.push('--json');
  return args;
}

function invoke(modes, options, capture = false) {
  const modeList = Array.isArray(modes) ? modes : [modes];
  const interpreter = findPython();
  const script = path.join(path.resolve(options.sourceRoot || packageRoot), 'scripts', 'onboard.py');
  if (!fs.existsSync(script) || !fs.statSync(script).isFile()) throw new Error(`Harness source is missing scripts/onboard.py: ${path.dirname(script)}`);
  const args = [...interpreter.args, script, ...baseArgs(options), ...modeList.map((mode) => `--${mode}`)];
  const completed = spawnSync(interpreter.command, args, {
    cwd: process.cwd(),
    encoding: 'utf8',
    stdio: capture ? ['ignore', 'pipe', 'pipe'] : 'inherit',
  });
  if (completed.error) throw completed.error;
  return completed;
}

function parsePlan(output) {
  try {
    return JSON.parse(output);
  } catch (_) {
    return null;
  }
}

function summarizePlan(output) {
  const plan = parsePlan(output);
  if (!plan) {
    process.stdout.write(output);
    return null;
  }
  const counts = plan.actions.reduce((all, action) => {
    all[action.kind] = (all[action.kind] || 0) + 1;
    return all;
  }, {});
  const actions = Object.entries(counts).map(([kind, count]) => `${kind}=${count}`).join(', ');
  console.log(`状态: ${plan.status} | Tier ${plan.tier} | 项目: ${plan.project_root}`);
  console.log(`版本: ${plan.installed_version} → ${plan.source_version}（${plan.version_relation}）`);
  if (plan.migration_manifest_errors && plan.migration_manifest_errors.length) {
    console.log(`迁移清单错误: ${plan.migration_manifest_errors.join('；')}`);
  }
  console.log(`计划: ${actions || '无动作'}`);
  if (plan.release_migrations && plan.release_migrations.length) {
    console.log(`发布迁移: ${plan.release_migrations.length} 项，需按清单人工确认`);
  }
  if (plan.legacy_markers && plan.legacy_markers.length) {
    console.log(`保留旧入口: ${plan.legacy_markers.join(', ')}`);
  }
  return plan;
}

function askForConfirmation() {
  if (!process.stdin.isTTY || !process.stdout.isTTY) return Promise.resolve(false);
  const interfaceHandle = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    interfaceHandle.question('按 y 应用以上计划，其他键取消: ', (answer) => {
      interfaceHandle.close();
      resolve(/^y(es)?$/i.test(answer.trim()));
    });
  });
}

function printPlaceholderHint(output) {
  if (/placeholder|占位/.test(output || '')) {
    console.error('全新安装的占位符需由 Agent 或人工按项目事实填写后再通过检查；填写后重新运行 hek check。');
  }
}

async function runInit(options) {
  const interactive = process.stdin.isTTY && process.stdout.isTTY;
  let deferredAgent = null;
  if (options.direct && (options.agent || process.env.HEK_AGENT)) {
    console.error('已指定 --direct：忽略 --agent/HEK_AGENT，执行确定性安装。');
  }
  if (options.direct && options.open && !options.noOpen) {
    console.error('已指定 --direct：忽略 --open。');
  }
  if (options.json && !options.direct && (options.agent || process.env.HEK_AGENT || options.open)) {
    console.error('--json 机器模式不启动 Agent：已忽略 --agent/--open/HEK_AGENT。');
  }
  if (options.open && !options.direct && !options.noOpen && !options.agent && !process.env.HEK_AGENT && !interactive && !options.json) {
    console.error('错误: 非交互环境使用 --open 时必须通过 --agent 或 HEK_AGENT 指定要打开的 Agent。');
    return 2;
  }

  if (interactive && !options.json && !options.tier) {
    options.tier = await selectTier();
  }

  const planned = invoke('plan', { ...options, json: true }, true);
  if (planned.status !== 0) {
    process.stdout.write(planned.stdout || '');
    process.stderr.write(planned.stderr || '');
    return planned.status || 2;
  }
  const plan = parsePlan(planned.stdout);
  const projectRoot = plan && plan.project_root
    ? plan.project_root
    : (options.projectRoot ? path.resolve(options.projectRoot) : process.cwd());
  if (!options.json) summarizePlan(planned.stdout);

  if (options.plan) {
    if (options.json) process.stdout.write(planned.stdout);
    return 0;
  }

  if (!options.direct && !options.json && interactive) {
    let agent;
    try {
      agent = await selectAgent(options);
    } catch (error) {
      console.error(`Agent 选择失败: ${error.message}`);
      return 2;
    }
    if (agent && !options.noOpen) {
      if (agent.kind === 'manual') deferredAgent = agent;
      else return openAgent(agent, projectRoot, buildAgentPrompt(projectRoot, options));
    }
  }

  if (!deferredAgent && !options.direct && !options.json && !interactive && (options.agent || process.env.HEK_AGENT)) {
    try {
      deferredAgent = await selectAgent(options);
    } catch (error) {
      console.error(`Agent 选择失败: ${error.message}`);
      return 2;
    }
    if (!options.open) deferredAgent = null;
  }

  const confirmed = options.yes || options.apply || (!options.json && await askForConfirmation());
  if (!confirmed) {
    if (options.json) {
      process.stdout.write(planned.stdout);
      console.error('未执行写入：--json 模式需要 --yes 才会应用（harness-engineering-kit init --yes）。');
      return 2;
    }
    if (!interactive) {
      console.error('未执行写入：非交互环境请使用 harness-engineering-kit init --yes。');
      return 2;
    }
    console.log('已取消，未修改项目。');
    return 0;
  }

  if (options.json) {
    const modes = options.noCheck ? ['apply'] : ['apply', 'check'];
    const receipt = invoke(modes, { ...options, json: true }, true);
    process.stdout.write(receipt.stdout || '');
    process.stderr.write(receipt.stderr || '');
    if (receipt.status !== 0) printPlaceholderHint(receipt.stdout);
    return typeof receipt.status === 'number' ? receipt.status : 2;
  }

  const applied = invoke('apply', options);
  if (applied.status !== 0) return applied.status || 2;
  let checkStatus = 0;
  if (!options.noCheck) {
    const checked = invoke('check', options, true);
    process.stdout.write(checked.stdout || '');
    process.stderr.write(checked.stderr || '');
    checkStatus = checked.status || 0;
    if (checkStatus !== 0) printPlaceholderHint(checked.stdout);
  }
  if (deferredAgent && !options.noOpen) {
    const agentStatus = openAgent(deferredAgent, projectRoot, buildAgentPrompt(projectRoot, options));
    if (options.noCheck) return agentStatus;
    // Re-check after the agent closes so the exit code reflects the post-fill
    // state instead of the pre-agent placeholder failure.
    const rechecked = invoke('check', { ...options, json: true }, true);
    process.stdout.write(rechecked.stdout || '');
    process.stderr.write(rechecked.stderr || '');
    const finalStatus = typeof rechecked.status === 'number' ? rechecked.status : 2;
    if (finalStatus !== 0) printPlaceholderHint(rechecked.stdout);
    return finalStatus !== 0 ? finalStatus : agentStatus;
  }
  return checkStatus;
}

async function main(argv = process.argv.slice(2)) {
  let parsed;
  try {
    parsed = parseArgs(argv);
  } catch (error) {
    console.error(`错误: ${error.message}`);
    console.error(usage());
    return 2;
  }
  if (parsed.options.version || parsed.command === 'version') {
    console.log(metadata.version);
    return 0;
  }
  if (parsed.options.help || parsed.command === 'help') {
    console.log(usage());
    return 0;
  }
  try {
    if (parsed.options.listAgents || parsed.command === 'agents') {
      printAgents(parsed.options.json);
      return 0;
    }
    if (!parsed.command) {
      console.log(usage());
      return 0;
    }
    if (parsed.command === 'init') return await runInit(parsed.options);
    if (parsed.command === 'handoff') return runHandoff(parsed.options);
    if (parsed.command === 'plan') return invoke('plan', { ...parsed.options, json: true }).status || 0;
    if (parsed.command === 'check') return invoke('check', parsed.options).status || 0;
    throw new Error(`unknown command: ${parsed.command}`);
  } catch (error) {
    console.error(`Harness CLI failed: ${error.message}`);
    return 2;
  }
}

if (require.main === module) {
  main().then((code) => { process.exitCode = code; });
}

module.exports = {
  AGENTS,
  DEFAULT_AGENT_PROMPT,
  TIER_CHOICES,
  agentMenuItems,
  availableAgents,
  buildAgentPrompt,
  commandAvailable,
  findAgent,
  findPython,
  handoffPayload,
  main,
  parseArgs,
  selectAgent,
  selectTier,
  selectWithArrows,
  usage,
};
