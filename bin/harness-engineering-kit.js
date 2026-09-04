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
  --direct               Run the deterministic installer without opening an agent
  --prompt <text>        Initial prompt sent to a terminal agent
  --list-agents          List supported agents and installation status
  --json                 Emit machine-readable output
  -h, --help             Show this help
  -v, --version          Show the version

The init command never deletes legacy files or overwrites existing project facts.
Set HARNESS_PYTHON to select a Python executable explicitly.
`;
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
    else if (token === '--agent' || token === '--prompt' || token === '--project-root' || token === '--source-root' || token === '--tier') {
      const value = args.shift();
      if (!value || value.startsWith('-')) throw new Error(`${token} requires a value`);
      if (token === '--tier' && !['1', '2'].includes(value)) throw new Error('--tier must be 1 or 2');
      const optionName = token.slice(2).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
      result.options[optionName] = value;
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

async function selectAgent(options) {
  const requested = options.agent || process.env.HEK_AGENT;
  if (requested) {
    const agent = findAgent(requested);
    if (!agent) throw new Error(`不支持的 AI Agent: ${requested}。使用 --list-agents 查看选项。`);
    if (!commandAvailable(agent.command) && !options.noOpen) {
      throw new Error(`${agent.label} 命令未找到。请先安装它，或使用 --no-open 完成初始化。`);
    }
    return agent;
  }
  if (!process.stdin.isTTY || !process.stdout.isTTY) return null;
  const agents = availableAgents();
  printAgents(false);
  const installed = agents.find((agent) => agent.installed);
  const interfaceHandle = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve, reject) => {
    interfaceHandle.question(`选择 Agent${installed ? `（默认 ${installed.label}）` : ''}: `, (answer) => {
      interfaceHandle.close();
      const value = answer.trim();
      if (!value && installed) return resolve(installed);
      const index = Number.parseInt(value, 10);
      const selected = Number.isInteger(index) && index >= 1 ? agents[index - 1] : findAgent(value);
      if (!selected) return reject(new Error('无效的 Agent 选择。'));
      if (!selected.installed) return reject(new Error(`${selected.label} 命令未找到，请先安装或重新选择。`));
      return resolve(selected);
    });
  });
}

function openAgent(agent, projectRoot, prompt) {
  if (!agent) return 0;
  const args = agent.kind === 'desktop' ? [projectRoot] : [prompt || DEFAULT_AGENT_PROMPT];
  console.log(`正在打开 ${agent.label}…`);
  const child = spawnSync(agent.command, args, {
    cwd: projectRoot,
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });
  if (child.error) {
    console.error(`无法打开 ${agent.label}: ${child.error.message}`);
    return 2;
  }
  return typeof child.status === 'number' ? child.status : 2;
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
    `使用 canonical onboarding 脚本生成计划：python3 "${path.join(sourceRoot, 'scripts', 'onboard.py')}" --project-root "${projectRoot}" --source-root "${sourceRoot}" --tier ${tier} --plan --json`,
    '根据项目事实补齐或调整配置占位符；保留已有配置和旧入口，不要盲目覆盖或删除。得到确认后，使用同一脚本执行 --apply，再执行 --check。',
    '最后汇报创建、更新、保留的文件、检查结果和仍需人工决策的事项。',
  ].join('\n');
}

function findPython() {
  const configured = process.env.HARNESS_PYTHON;
  const candidates = configured ? [configured] : ['python3', 'python'];
  for (const candidate of candidates) {
    const probe = spawnSync(candidate, ['--version'], { stdio: 'ignore' });
    if (!probe.error && probe.status === 0) return candidate;
  }
  throw new Error('Python 3 is required. Install Python 3 or set HARNESS_PYTHON to its executable path.');
}

function baseArgs(options) {
  const args = [];
  if (options.projectRoot) args.push('--project-root', path.resolve(options.projectRoot));
  args.push('--source-root', path.resolve(options.sourceRoot || packageRoot));
  if (options.tier) args.push('--tier', options.tier);
  if (options.json) args.push('--json');
  return args;
}

function invoke(mode, options, capture = false) {
  const python = findPython();
  const script = path.join(path.resolve(options.sourceRoot || packageRoot), 'scripts', 'onboard.py');
  if (!fs.existsSync(script) || !fs.statSync(script).isFile()) throw new Error(`Harness source is missing scripts/onboard.py: ${path.dirname(script)}`);
  const args = [script, ...baseArgs(options), `--${mode}`];
  const completed = spawnSync(python, args, {
    cwd: process.cwd(),
    encoding: 'utf8',
    stdio: capture ? ['ignore', 'pipe', 'pipe'] : 'inherit',
  });
  if (completed.error) throw completed.error;
  return completed;
}

function summarizePlan(output) {
  try {
    const plan = JSON.parse(output);
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
  } catch (_) {
    process.stdout.write(output);
    return null;
  }
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

async function runInit(options) {
  const interactive = process.stdin.isTTY && process.stdout.isTTY;
  let agent;
  if (!options.direct && !options.plan && !options.json && interactive) {
    try {
      agent = await selectAgent(options);
    } catch (error) {
      console.error(`Agent 选择失败: ${error.message}`);
      return 2;
    }
    if (agent && !options.noOpen) {
      const projectRoot = options.projectRoot ? path.resolve(options.projectRoot) : process.cwd();
      return openAgent(agent, projectRoot, buildAgentPrompt(projectRoot, options));
    }
  }
  const planOptions = { ...options, json: true };
  const planned = invoke('plan', planOptions, true);
  if (planned.status !== 0) {
    process.stdout.write(planned.stdout || '');
    process.stderr.write(planned.stderr || '');
    return planned.status || 2;
  }
  const plan = summarizePlan(planned.stdout);
  if (options.plan || options.json) {
    if (options.json) process.stdout.write(planned.stdout);
    return 0;
  }
  if (!agent && options.agent) {
    try {
      agent = await selectAgent(options);
    } catch (error) {
      console.error(`Agent 选择失败: ${error.message}`);
      return 2;
    }
  }
  const confirmed = options.yes || options.apply || await askForConfirmation();
  if (!confirmed) {
    if (!process.stdin.isTTY) {
      console.error('未执行写入：非交互环境请使用 harness-engineering-kit init --yes。');
      return 2;
    }
    console.log('已取消，未修改项目。');
    return 0;
  }
  const applied = invoke('apply', options);
  if (applied.status !== 0) return applied.status || 2;
  if (!options.noCheck) {
    const checked = invoke('check', options);
    if (checked.status !== 0) return checked.status || 2;
  }
  if (!options.noOpen && agent && (options.open || process.stdin.isTTY)) {
    const projectRoot = plan && plan.project_root ? plan.project_root : process.cwd();
    return openAgent(agent, projectRoot, buildAgentPrompt(projectRoot, options));
  }
  return 0;
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
  if (parsed.options.help || parsed.command === 'help' || !parsed.command) {
    console.log(usage());
    return 0;
  }
  try {
    if (parsed.options.listAgents || parsed.command === 'agents') {
      printAgents(parsed.options.json);
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
