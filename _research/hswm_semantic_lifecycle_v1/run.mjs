#!/usr/bin/env node
/** One finite lifecycle diagnostic, with fresh OS processes and no implicit live-model use. */
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { copyTree } from '../dgx_semantic_learning_v1/io.mts';

const here = dirname(fileURLToPath(import.meta.url));
const repository = resolve(here, '../..');
const sha = raw => createHash('sha256').update(raw).digest('hex');
const save = (path, value) => writeFile(path, JSON.stringify(value, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
const readJson = async path => JSON.parse(await readFile(path, 'utf8'));
const arms = Object.freeze(['frozen', 'evidence_only', 'sham', 'learned']);
export const usage = `Usage: node _research/hswm_semantic_lifecycle_v1/run.mjs --output NEW_PRIVATE_DIRECTORY --transport scripted|http [--cell CELL_JSON]
Build src/hswm/effect-runtime first. Scripted mode performs no network/model calls.
HTTP mode requires an explicit cell {base_url, model, max_tokens, api_key_env?}.
On maintainer DGX, use the documented hswm-run preflight and execution wrapper.
All outputs are a finite authored diagnostic, not HSWM efficacy evidence.\n`;

export const parseArgs = argv => {
  if (argv.length === 1 && argv[0] === '--help') return null;
  const values = new Map();
  for (let i = 0; i < argv.length; i += 2) {
    const option = argv[i], value = argv[i + 1];
    if (!['--output', '--transport', '--cell'].includes(option) || values.has(option) || !value || value.startsWith('--')) throw new Error('Invalid or duplicate option');
    values.set(option, value);
  }
  const mode = values.get('--transport');
  if (!values.has('--output') || !['scripted', 'http'].includes(mode)) throw new Error('Explicit new output and transport are required');
  if ((mode === 'http') !== values.has('--cell')) throw new Error('Only HTTP mode requires --cell');
  return { output: resolve(values.get('--output')), transport: mode, cellPath: values.has('--cell') ? resolve(values.get('--cell')) : null };
};

const readCell = async options => {
  if (options.transport === 'scripted') return { base_url: 'https://fixture.invalid/v1', model: 'SCRIPTED_NOT_A_MODEL', max_tokens: 512 };
  const cell = await readJson(options.cellPath);
  if (!cell || typeof cell !== 'object' || Array.isArray(cell) ||
      Object.keys(cell).some(k => !['base_url', 'model', 'max_tokens', 'api_key_env'].includes(k)) ||
      typeof cell.model !== 'string' || !cell.model.trim() ||
      !Number.isSafeInteger(cell.max_tokens) || cell.max_tokens < 1 || cell.max_tokens > 4096) throw new Error('Invalid bounded cell');
  const endpoint = new URL(cell.base_url);
  if (!['http:', 'https:'].includes(endpoint.protocol) || endpoint.username || endpoint.password || endpoint.search || endpoint.hash) throw new Error('Invalid endpoint; credentials belong in the environment');
  if (cell.api_key_env !== undefined && (typeof cell.api_key_env !== 'string' || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(cell.api_key_env) || !process.env[cell.api_key_env])) throw new Error('Missing named credential environment');
  return cell;
};

/** Bind imported local source/compiled closure; no packages are downloaded. */
export async function sourcePins() {
  const entries = new Map();
  const collect = async relative => {
    if (entries.has(relative)) return;
    const raw = await readFile(join(repository, relative));
    entries.set(relative, { path: relative, sha256: sha(raw), byteLength: raw.byteLength });
    if (relative.includes('/dist/')) {
      const source = relative.replace('/dist/', '/src/').replace(/\.js$/, '.ts');
      try { await collect(source); } catch (e) { if (e.code !== 'ENOENT') throw e; }
    }
    if (!/\.(?:mjs|js)$/.test(relative) || relative.includes('/node_modules/')) return;
    for (const match of raw.toString('utf8').matchAll(/(?:from\s*|import\s*)['"]([^'"]+)['"]/g)) {
      const specifier = match[1];
      if (!specifier.startsWith('.') || specifier.includes('node_modules')) continue;
      await collect(resolve(repository, dirname(relative), specifier).slice(repository.length + 1));
    }
  };
  // Resolve relatives against the checkout, including when invoked from another cwd.
  const visit = async relative => {
    const raw = await readFile(join(repository, relative));
    entries.set(relative, { path: relative, sha256: sha(raw), byteLength: raw.byteLength });
    for (const match of raw.toString('utf8').matchAll(/from\s*['"]([^'"]+)['"]/g)) {
      const specifier = match[1];
      if (specifier.startsWith('.') && !specifier.includes('node_modules')) {
        const child = resolve(repository, dirname(relative), specifier).slice(repository.length + 1);
        await collect(child);
      }
    }
  };
  for (const file of ['run.mjs', 'worker.mjs', 'runtime.mjs', 'transport.mjs']) await visit(`_research/hswm_semantic_lifecycle_v1/${file}`);
  for (const path of ['src/hswm/effect-runtime/package-lock.json', 'src/hswm/effect-runtime/node_modules/effect/package.json']) await collect(path);
  return [...entries.values()].sort((a, b) => a.path.localeCompare(b.path));
}

async function verifyPins(pins) {
  for (const pin of pins) if (sha(await readFile(join(repository, pin.path))) !== pin.sha256) throw new Error(`Source changed during run: ${pin.path}`);
}

const child = (stage, configPath, arm) => new Promise((ok, fail) => {
  const processHandle = spawn(process.execPath, [join(here, 'worker.mjs'), stage, configPath, arm], { stdio: ['ignore', 'pipe', 'pipe'] });
  let output = '', finished = false, killed = false;
  const capture = chunk => { output = (output + chunk.toString()).slice(-4096); };
  processHandle.stdout.on('data', capture); processHandle.stderr.on('data', capture);
  const timer = setTimeout(() => { killed = true; processHandle.kill('SIGKILL'); }, 75_000);
  const finish = error => {
    if (finished) return;
    finished = true; clearTimeout(timer);
    error ? fail(error) : ok({ stage, arm, childPid: processHandle.pid, exitedBeforeNextStage: true });
  };
  processHandle.on('error', () => finish(new Error('Worker launch failed')));
  processHandle.on('close', code => finish(code === 0 && !killed ? null : new Error(`Worker ${stage}/${arm} failed (${killed ? 'timeout' : code}): ${output}`)));
});

export async function runLifecycle(options) {
  const cell = await readCell(options);
  const pins = await sourcePins();
  const environmentSha256 = pins.find(p => p.path === 'src/hswm/effect-runtime/src/semantic-rule-environment.ts')?.sha256;
  if (!environmentSha256) throw new Error('Build the new environment before running');
  await mkdir(dirname(options.output), { recursive: true });
  await mkdir(options.output, { mode: 0o700 }); // refuse overwrite, including partial earlier attempts
  const config = { contract: 'hswm-semantic-lifecycle/v1', root: options.output, transport: options.transport, cell, arms, environmentSha256,
    candidateCount: 1, developmentUsedForSelection: false, heldoutUsedForRevision: false,
    budget: { maximumModelRequests: 10, maximumWorkerMs: 75_000, automaticRetries: 0 },
    modelExecutionStatus: options.transport === 'scripted' ? 'NO_MODEL' : 'CALLER_DECLARED_HTTP_ENDPOINT_NOT_INDEPENDENTLY_VERIFIED',
    claimCeiling: options.transport === 'scripted' ? 'SCRIPTED_WIRING_ONLY_NOT_MODEL_EFFICACY' : 'FINITE_AUTHORED_DIAGNOSTIC_NOT_CONFIRMATORY_EFFICACY' };
  const configPath = join(options.output, 'config.json');
  await save(configPath, config); await save(join(options.output, 'source-pins.json'), { node: process.version, pins });
  await mkdir(join(options.output, 'states'), { mode: 0o700 });
  const launches = [];
  const launch = async (stage, arm) => { await verifyPins(pins); launches.push(await child(stage, configPath, arm)); };
  try {
    await launch('train', 'base');
    // Archive copy preserves the native journal's internal slot/object hard links.
    for (const arm of arms) await copyTree(join(options.output, 'states/base'), join(options.output, 'states', arm));
    for (const arm of arms.filter(a => a !== 'frozen')) await launch('revise', arm);
    for (const split of ['development', 'heldout']) for (const arm of arms) await launch(split, arm);
    const training = await readJson(join(options.output, 'train-base.json'));
    const revisions = await Promise.all(arms.filter(a => a !== 'frozen').map(a => readJson(join(options.output, `revise-${a}.json`))));
    const evaluations = await Promise.all(['development', 'heldout'].flatMap(split => arms.map(a => readJson(join(options.output, `${split}-${a}.json`)))));
    const allCalls = [training, ...revisions, ...evaluations].flatMap(r => r.calls);
    const committedEvidenceBindingsValid = revisions.filter(r => r.committed).every(r =>
      r.after.semantic.trace?.sha256 === training.trace.traceContent.sha256 &&
      r.after.semantic.outcome?.sha256 === training.outcome.outcomeContent.sha256);
    const revisionFailures = revisions.filter(r => !r.committed).map(r => ({ arm: r.arm, disposition: r.disposition, errorCode: r.errorCode }));
    const sharedEvidence = revisions.length === 3 && revisionFailures.length === 0 && committedEvidenceBindingsValid;
    const reopened = evaluations.every(e => {
      const revision = revisions.find(r => r.arm === e.arm);
      const priorState = revision?.after ?? training.state;
      return e.before.canonicalSha256 === priorState.canonicalSha256 && e.canonicalUnchanged &&
        (!e.trace || (e.trace.relationKey.revisionId === priorState.relationKey.revisionId &&
          e.calls.some(c => c.frameSha256 === e.trace.frameSha256))) &&
        JSON.stringify(e.before.roleRefs) === JSON.stringify(training.state.roleRefs) &&
        e.processId !== training.processId && e.processId !== revision?.processId;
    });
    if (!committedEvidenceBindingsValid || !reopened) throw new Error('Lifecycle binding checks failed');
    await verifyPins(pins);
    const report = { ...config, status: revisionFailures.length ? 'COMPLETED_WITH_REVISION_FAILURES' : 'COMPLETED_DIAGNOSTIC',
      launches, sharedEvidence, committedEvidenceBindingsValid, revisionFailures, reopened,
      training, revisions, evaluations, calls: allCalls,
      httpModelRequests: allCalls.filter(c => c.httpModelRequest).length,
      usageStatus: allCalls.filter(c => c.httpModelRequest).every(c => c.usage !== null) ? 'RAW_USAGE_PRESENT_OR_NO_HTTP_REQUESTS' : 'PARTIALLY_UNAVAILABLE_NOT_ZERO',
      scientificStatus: 'NOT_ADJUDICATED', outcomeAuthority: training.outcome.status };
    await save(join(options.output, 'summary.json'), report);
    return report;
  } catch (error) {
    await save(join(options.output, 'failure.json'), { status: 'FAILED_DIAGNOSTIC', launches, plannedHeldoutCasesPerArm: 4,
      message: error.message, scientificStatus: 'NOT_ADJUDICATED' });
    throw error;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const options = parseArgs(process.argv.slice(2));
    if (options === null) process.stdout.write(usage);
    else {
      const result = await runLifecycle(options);
      process.stdout.write(JSON.stringify({ output: options.output, status: result.status, claimCeiling: result.claimCeiling,
        reopened: result.reopened, sharedEvidence: result.sharedEvidence, httpModelRequests: result.httpModelRequests,
        heldout: result.evaluations.filter(e => e.stage === 'heldout').map(e => ({ arm: e.arm, correct: e.assessment.correct, total: e.assessment.denominator })) }) + '\n');
    }
  } catch (error) { process.stderr.write(`SEMANTIC_LIFECYCLE_REFUSED: ${error.message}\n`); process.exitCode = 1; }
}
