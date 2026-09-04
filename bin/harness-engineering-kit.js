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
];

const DEFAULT_AGENT_PROMPT = '请在当前项目完成 Harness Engineering Kit 初始化：先读取项目中的 AGENTS.md 或 CLAUDE.md 与 docs/methodology/agent-policy.yaml，再根据需要继续工作。';

const SKIP_ANSWERS = new Set(['0', 'n', 'no', 'skip', 'none']);
const VALUE_OPTIONS = new Set(['--agent', '--prompt', '--project-root', '--source-root', '--tier']);

function usage() {
  return `Harness Engineering Kit ${metadata.version}

Usage:
  harness-engineering-kit init [options]    Plan, confirm, install, and check
  harness-engineering-kit plan [options]    Print a read-only JSON plan
  harness-engineering-kit check [options]   Run deterministic checks
  harness-engineering-kit agents [options]  List supported AI agents

Options:
  --project-root <path>  Target project (default: current Git root/current directory)
  --source-root <path>   Kit source (default: installed package)
  --tier <1|2>           Installation scope (default: 2)
  --yes                  Apply init without an interactive confirmation
  --apply                Apply init without an interactive confirmation
  --plan                 Make init read-only
  --no-check             Skip the post-init check
  --agent <name>         AI agent to open after init (claude, codex, cursor, gemini)
  --open                 Open the selected agent in non-interactive mode
  --no-open              Do not open an agent after init
  --direct               Run the deterministic installer; --agent and HEK_AGENT are ignored
  --prompt <text>        Initial prompt sent to a terminal agent
  --list-agents          List supported agents and installation status
  --json                 Machine-readable output: without --yes init prints the plan and
                         exits 2; with --yes it applies, checks, and prints one JSON receipt
  -h, --help             Show this help
  -v, --version          Show the version

The init command never deletes legacy files or overwrites existing project facts.
Interactive init opens the selected Agent first (enter 0 or skip for the deterministic
flow; it falls back automatically when no agent is installed). Set HARNESS_PYTHON to
select a Python executable explicitly.
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
  const probe = process.platform === 'win32'
    ? spawnSync('where', [command], { stdio: 'ignore', shell: true })
    : spawnSync('/bin/sh', ['-c', 'command -v "$1" >/dev/null 2>&1', 'hek', command], { stdio: 'ignore' });
  return probe.status === 0;
}

function availableAgents() {
  return AGENTS.map((agent) => ({ ...agent, installed: commandAvailable(agent.command) }));
}

function printAgents(asJson = false) {
  const agents = availableAgents();
  if (asJson) {
    console.log(JSON.stringify(agents, null, 2));
    return agents;
  }
  console.log('可用的 AI Agent：');
  agents.forEach((agent, index) => {
    console.log(`  ${index + 1}. ${agent.label} (${agent.id}) ${agent.installed ? '✓ 已安装' : '— 未找到命令'}`);
  });
  return agents;
}

function findAgent(value) {
  if (!value) return null;
  return AGENTS.find((agent) => agent.id === value.toLowerCase() || agent.command === value.toLowerCase()) || null;
}

function agentWillOpen(options) {
  if (options.noOpen) return false;
  return Boolean(options.open) || (process.stdin.isTTY && process.stdout.isTTY);
}

async function selectAgent(options) {
  const requested = options.agent || process.env.HEK_AGENT;
  if (requested) {
    const agent = findAgent(requested);
    if (!agent) throw new Error(`不支持的 AI Agent: ${requested}。使用 --list-agents 查看选项。`);
    if (agentWillOpen(options) && !commandAvailable(agent.command)) {
      throw new Error(`${agent.label} 命令未找到。请先安装它，或使用 --no-open 完成初始化。`);
    }
    return agent;
  }
  if (!process.stdin.isTTY || !process.stdout.isTTY) return null;
  const agents = availableAgents();
  printAgents(false);
  const installed = agents.find((agent) => agent.installed);
  if (!installed) {
    console.log('未检测到已安装的 AI Agent，进入确定性安装流程（安装后可重新运行 hek init）。');
    return null;
  }
  const interfaceHandle = readline.createInterface({ input: process.stdin, output: process.stdout });
  const question = `选择 Agent（默认 ${installed.label}，输入 0 或 skip 跳过）: `;
  const ask = (resolve, reject, attempts) => {
    interfaceHandle.question(question, (answer) => {
      const value = answer.trim().toLowerCase();
      if (!value) {
        interfaceHandle.close();
        return resolve(installed);
      }
      if (SKIP_ANSWERS.has(value)) {
        interfaceHandle.close();
        return resolve(null);
      }
      const index = Number.parseInt(value, 10);
      const selected = Number.isInteger(index) && index >= 1 ? agents[index - 1] : findAgent(value);
      if (!selected) {
        console.error('无效的 Agent 选择。');
        if (attempts > 1) return ask(resolve, reject, attempts - 1);
        interfaceHandle.close();
        return reject(new Error('无效的 Agent 选择。'));
      }
      if (!selected.installed) {
        console.error(`${selected.label} 命令未找到，请重新选择或输入 0 跳过。`);
        if (attempts > 1) return ask(resolve, reject, attempts - 1);
        interfaceHandle.close();
        return reject(new Error(`${selected.label} 命令未找到，请先安装或输入 0 跳过。`));
      }
      interfaceHandle.close();
      return resolve(selected);
    });
  };
  return new Promise((resolve, reject) => ask(resolve, reject, 3));
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
  const args = agent.kind === 'desktop' ? [projectRoot] : [prompt || DEFAULT_AGENT_PROMPT];
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
  return options.prompt || [
    '请作为 Harness Engineering Kit 的项目接入 Agent，完成当前项目初始化。',
    `目标项目：${projectRoot}`,
    `Kit 源码：${sourceRoot}`,
    `安装范围：Tier ${tier}`,
    approval,
    '先读取项目事实（包括现有的 AGENTS.md、CLAUDE.md、ai.json、AI.md 和项目配置），识别真实技术栈、命令、目录边界与已有接入状态。',
    `使用 canonical onboarding 脚本生成计划：${pythonCommand()} "${path.join(sourceRoot, 'scripts', 'onboard.py')}" --project-root "${projectRoot}" --source-root "${sourceRoot}" --tier ${tier} --plan --json`,
    '根据项目事实补齐或调整配置占位符；保留已有配置和旧入口，不要盲目覆盖或删除。得到确认后，使用同一脚本执行 --apply，再执行 --check。',
    '最后汇报创建、更新、保留的文件、检查结果和仍需人工决策的事项。',
  ].join('\n');
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
  console.log(`计划: ${actions || '无动作'}`);
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
  if (options.direct && (options.agent || process.env.HEK_AGENT)) {
    console.error('已指定 --direct：忽略 --agent/HEK_AGENT，执行确定性安装。');
  }
  if (options.open && !options.direct && !options.noOpen && !options.agent && !process.env.HEK_AGENT && !interactive) {
    console.error('错误: 非交互环境使用 --open 时必须通过 --agent 或 HEK_AGENT 指定要打开的 Agent。');
    return 2;
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
      return openAgent(agent, projectRoot, buildAgentPrompt(projectRoot, options));
    }
  }

  let deferredAgent = null;
  if (!options.direct && !options.json && !interactive && (options.agent || process.env.HEK_AGENT)) {
    try {
      deferredAgent = await selectAgent(options);
    } catch (error) {
      console.error(`Agent 选择失败: ${error.message}`);
      return 2;
    }
    if (!options.open) deferredAgent = null;
  }

  const confirmed = options.yes || options.apply || await askForConfirmation();
  if (!confirmed) {
    if (!interactive) {
      if (options.json) process.stdout.write(planned.stdout);
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
    return openAgent(deferredAgent, projectRoot, buildAgentPrompt(projectRoot, options));
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
  availableAgents,
  buildAgentPrompt,
  commandAvailable,
  findAgent,
  findPython,
  main,
  parseArgs,
  selectAgent,
  usage,
};
