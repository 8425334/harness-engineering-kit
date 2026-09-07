const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const test = require('node:test');

const root = path.resolve(__dirname, '..');

function run(command, args, options = {}) {
  return spawnSync(command, args, {
    cwd: options.cwd || root,
    encoding: 'utf8',
    env: { ...process.env, ...(options.env || {}) },
  });
}

test('published package installs and runs without repository-only files', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-package-'));
  try {
    const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
    const npmEnv = { npm_config_cache: path.join(directory, 'npm-cache') };
    const packed = run(npm, ['pack', '--json', '--pack-destination', directory], { env: npmEnv });
    assert.equal(packed.status, 0, packed.stderr);
    const packResults = JSON.parse(packed.stdout);
    assert.equal(packResults.length, 1);

    const includedFiles = new Set(packResults[0].files.map((entry) => entry.path));
    for (const required of [
      'bin/harness-engineering-kit.js',
      'scripts/onboard.py',
      'scripts/verify_skill.py',
      'templates/engineering/SKILL.md',
      'templates/engineering/manifest.yaml',
      'templates/workflow/change.json.template',
      'VERSION',
    ]) {
      assert.ok(includedFiles.has(required), `package is missing ${required}`);
    }
    assert.ok(![...includedFiles].some((file) => file.startsWith('tests/')), 'package must not ship its test suite');

    const archive = path.join(directory, packResults[0].filename);
    const consumer = path.join(directory, 'consumer');
    fs.mkdirSync(consumer);
    const installed = run(npm, ['install', '--ignore-scripts', '--no-audit', '--no-fund', archive], {
      cwd: consumer,
      env: npmEnv,
    });
    assert.equal(installed.status, 0, installed.stderr);

    const packageRoot = fs.realpathSync(path.join(consumer, 'node_modules', 'harness-engineering-kit'));
    const cli = path.join(packageRoot, 'bin', 'harness-engineering-kit.js');
    const version = run(process.execPath, [cli, '--version'], { cwd: consumer });
    assert.equal(version.status, 0, version.stderr);
    assert.equal(version.stdout.trim(), fs.readFileSync(path.join(root, 'VERSION'), 'utf8').trim());

    const target = path.join(directory, 'target-project');
    fs.mkdirSync(target);
    const planned = run(process.execPath, [
      cli, 'plan', '--project-root', target, '--source-root', packageRoot, '--tier', '1', '--json',
    ], { cwd: target });
    assert.equal(planned.status, 0, planned.stderr);
    const plan = JSON.parse(planned.stdout);
    assert.equal(plan.status, 'fresh');
    assert.equal(plan.source_root, packageRoot);
    assert.ok(plan.actions.some((action) => action.target === 'docs/methodology/agent-policy.yaml'));
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
