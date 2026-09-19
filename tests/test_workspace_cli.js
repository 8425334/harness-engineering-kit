const assert = require('node:assert/strict');
const fs = require('node:fs');
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

function python(args, options = {}) {
  const interpreter = process.env.HARNESS_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  return spawnSync(interpreter, args, {
    cwd: options.cwd || root,
    encoding: 'utf8',
    env: { ...process.env, ...(options.env || {}) },
  });
}

function buildFixture(name) {
  const probe = python([
    '-c',
    `import sys; sys.path.insert(0, 'tests'); from fixtures.workspace import build; print(build('${name}'))`,
  ]);
  assert.equal(probe.status, 0, probe.stderr);
  return probe.stdout.trim();
}

test('parses workspace subcommands, repeated --root, and the exec separator', () => {
  const discover = cliModule.parseArgs(['workspace', 'discover', '--root', 'a', '--root', 'b', '--json']);
  assert.equal(discover.command, 'workspace');
  assert.equal(discover.options.subcommand, 'discover');
  assert.deepEqual(discover.options.root, ['a', 'b']);
  assert.equal(discover.options.json, true);

  const exec = cliModule.parseArgs(['workspace', 'exec', 'backend-api', '--', 'python', '-c', 'print(1)']);
  assert.equal(exec.options.subcommand, 'exec');
  assert.deepEqual(exec.options.positionals, ['backend-api']);
  assert.deepEqual(exec.options.rest, ['python', '-c', 'print(1)']);

  const guard = cliModule.parseArgs(['workspace', 'guard', '--path', 'src/x.ts', '--session-root', '.', '--json']);
  assert.equal(guard.options.path, 'src/x.ts');
  assert.equal(guard.options.sessionRoot, '.');

  const run = cliModule.parseArgs(['workspace', 'run', 'all', 'test']);
  assert.deepEqual(run.options.positionals, ['all', 'test']);

  const status = cliModule.parseArgs(['workspace', 'status', '--root', 'a', '--json']);
  assert.equal(status.options.subcommand, 'status');
  assert.deepEqual(cliModule.workspaceArgs(status.options).slice(0, 4), ['status', '--root', path.resolve('a'), '--json']);
});

test('forwards workspace arguments to the Python entry point', () => {
  const args = cliModule.workspaceArgs({
    subcommand: 'exec',
    root: ['one', 'two'],
    depth: '2',
    positionals: ['backend-api'],
    rest: ['python', '-c', 'print(1)'],
    json: true,
  });
  assert.equal(args[0], 'exec');
  assert.deepEqual(args.slice(1, 5), ['--root', path.resolve('one'), '--root', path.resolve('two')]);
  assert.ok(args.includes('--depth'));
  assert.ok(args.includes('--json'));
  assert.ok(args.includes('--'));
  assert.equal(args[args.length - 1], 'print(1)');

  assert.throws(() => cliModule.workspaceArgs({ subcommand: 'exec', positionals: ['x'] }), /-- <cmd/);
  assert.throws(() => cliModule.workspaceArgs({ subcommand: 'nope' }), /requires one of/);
});

test('workspace discover output matches the Python entry point', () => {
  const fixture = buildFixture('pair-ok');
  try {
    const viaNode = run(['workspace', 'discover', '--root', fixture, '--json']);
    assert.equal(viaNode.status, 0, viaNode.stderr);
    const viaPython = python([path.join('scripts', 'workspace_ctl.py'), 'discover', '--root', fixture, '--json']);
    assert.equal(viaPython.status, 0, viaPython.stderr);
    assert.deepEqual(JSON.parse(viaNode.stdout), JSON.parse(viaPython.stdout));
    assert.equal(JSON.parse(viaNode.stdout).units.length, 2);
  } finally {
    fs.rmSync(fixture, { recursive: true, force: true });
  }
});

test('workspace guard and verify surface blocked exit codes', () => {
  const fixture = buildFixture('nested');
  try {
    const target = path.join(fixture, 'backend-api', 'backend-ui', 'src', 'x.ts');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, 'export {}\n');
    const guarded = run([
      'workspace', 'guard', '--path', target, '--session-root', path.join(fixture, 'backend-api'), '--json',
    ]);
    assert.equal(guarded.status, 2);
    assert.equal(JSON.parse(guarded.stdout).diagnostics[0].code, 'nested.detected');

    const verified = run(['workspace', 'verify', '--root', fixture, '--json']);
    assert.equal(verified.status, 2);
    assert.equal(JSON.parse(verified.stdout).status, 'blocked');
  } finally {
    fs.rmSync(fixture, { recursive: true, force: true });
  }
});

test('workspace exec runs inside the unit root with HEK_* injected', () => {
  const fixture = buildFixture('pair-ok');
  try {
    const completed = run([
      'workspace', 'exec', '--root', fixture, 'backend-api', '--',
      process.execPath, '-e', 'console.log(process.cwd());console.log(process.env.HEK_UNIT)',
    ], { cwd: fixture });
    assert.equal(completed.status, 0, completed.stderr);
    const [cwd, unit] = completed.stdout.trim().split(/\r?\n/);
    assert.equal(path.resolve(cwd), path.resolve(path.join(fixture, 'backend-api')));
    assert.equal(unit, 'backend-api');
  } finally {
    fs.rmSync(fixture, { recursive: true, force: true });
  }
});

test('init --unit-id forwards the flag to the Python entry point', () => {
  const planned = run(['init', '--plan', '--json', '--unit-id', 'backend-api', '--project-root', root]);
  assert.equal(planned.status, 0, planned.stderr);
  const plan = JSON.parse(planned.stdout);
  assert.ok(plan.actions.some((action) => action.target === '.hek/project/identity.yaml'));
});
