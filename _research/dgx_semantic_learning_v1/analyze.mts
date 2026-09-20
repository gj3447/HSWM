/** Public, synthetic-only result projection; raw stores remain in the durable run archive. */
import { readFile, writeFile, readdir, mkdir } from 'node:fs/promises';
import { join, basename } from 'node:path';
import { createHash } from 'node:crypto';
import { task, label } from './domain.mts';
const sha = (v: string | Uint8Array) => createHash('sha256').update(v).digest('hex');
const json = async (p: string) => JSON.parse(await readFile(p, 'utf8'));
async function files(root: string): Promise<string[]> {
  const entries = await readdir(root, { withFileTypes: true });
  return (await Promise.all(entries.map(e => e.isDirectory() ? files(join(root, e.name)) : Promise.resolve([join(root, e.name)])))).flat();
}
const input = process.argv[2], output = process.argv[3];
if (!input || !output) throw new Error('Usage: analyze.mts PRIVATE_RUN_OUTPUT_DIR PUBLIC_OUTPUT_JSON');
const paths = await files(input), raw = await readFile(join(input, 'summary.json'));
const summary = JSON.parse(raw.toString()), protocol = await json(join(input, 'protocol.json'));
let auditedRequests = 0, auditedLearningRequests = 0;
for (const p of paths.filter(p => p.endsWith('.request.json'))) {
  const request = await json(p), inner = JSON.parse(request.messages.find((m: any) => m.role === 'user').content);
  const parts = p.split('/'), trialId = parts[parts.indexOf('trials') + 1];
  const trial = summary.results.find((r: any) => r.id === trialId), t = task(trial.family, trial.seed);
  const cases = JSON.parse(inner.frame.event).cases;
  const training = p.includes('/http/train-'), expected = training ? t.train : t.heldout;
  if (JSON.stringify(cases.map((c: any) => c.id)) !== JSON.stringify(expected) || cases.some((c: any) => 'observed' in c || 'label' in c || 'expected' in c)) throw new Error('Prediction input split/label violation');
  if (inner.contract === 'hswm-llm-semantic-learn/v1') {
    const observed = JSON.parse(inner.outcome.observed);
    if (inner.frame.relation.semantic.semanticText !== t.initial || JSON.stringify(observed.cases.map((c: any) => c.id)) !== JSON.stringify(t.train) ||
      observed.cases.some((c: any) => c.observed !== label(t.family, c.id))) throw new Error('Learning evidence leakage or target mismatch');
    auditedLearningRequests++;
  }
  auditedRequests++;
}
const calls = (await Promise.all(paths.filter(p => basename(p) === 'calls.jsonl').map(p => readFile(p, 'utf8')))).flatMap(s => s.trim().split('\n').filter(Boolean).map(s => JSON.parse(s)));
const trains = await Promise.all(paths.filter(p => basename(p) === 'train-learned.json').map(json));
const observations = summary.results.map((r: any) => ({ id: r.id, model: r.model.id, family: r.family, seed: r.seed, status: r.status,
  restorationExact: r.restorationExact ?? null, removalExact: r.removalExact ?? null, feedbackEqual: r.feedbackEqual ?? null,
  error: r.error ?? null, arms: r.arms.map((a: any) => ({ arm: a.arm, valid: a.valid, correct: a.correct, total: a.total,
    prediction: a.prediction ?? null, canonicalSha256: a.state?.canonicalSha256 ?? null, relationRevision: a.state?.relationRevision ?? null,
    semanticSha256: a.state?.semanticSha256 ?? null, canonicalUnchanged: a.canonicalUnchanged ?? false, error: a.error ?? null })) }));
const aggregates = protocol.models.flatMap((model: any) => protocol.arms.map((arm: string) => {
  const rows = observations.filter((r: any) => r.model === model.id).flatMap((r: any) => r.arms.filter((a: any) => a.arm === arm));
  const correct = rows.reduce((n: number, r: any) => n + r.correct, 0), total = rows.reduce((n: number, r: any) => n + r.total, 0);
  return { model: model.id, arm, batches: rows.length, validBatches: rows.filter((r: any) => r.valid).length, correct, total,
    accuracy: total ? correct / total : null, unavailableTrials: protocol.tasks.length - rows.length };
}));
const paired = protocol.models.map((model: any) => {
  const rows = observations.filter((r: any) => r.model === model.id && r.status === 'COMPLETE');
  const value = (r: any, arm: string) => r.arms.find((a: any) => a.arm === arm);
  return { model: model.id, completeTrials: rows.length,
    learnedMinusFrozenCorrect: rows.reduce((n: number, r: any) => n + value(r, 'learned').correct - value(r, 'frozen').correct, 0),
    learnedMinusEvidenceOnlyCorrect: rows.reduce((n: number, r: any) => n + value(r, 'learned').correct - value(r, 'evidence_only').correct, 0),
    regressionsVsFrozen: rows.filter((r: any) => value(r, 'learned').correct < value(r, 'frozen').correct).length,
    improvementsVsFrozen: rows.filter((r: any) => value(r, 'learned').correct > value(r, 'frozen').correct).length,
    restoredPredictionDisagreements: rows.filter((r: any) => value(r, 'learned').prediction !== value(r, 'restored').prediction).length,
    removedPredictionDisagreements: rows.filter((r: any) => value(r, 'frozen').prediction !== value(r, 'removed').prediction).length,
    exactRestorations: rows.filter((r: any) => r.restorationExact).length, exactRemovals: rows.filter((r: any) => r.removalExact).length,
    feedbackEqual: rows.filter((r: any) => r.feedbackEqual).length };
});
const samples = (await readFile(join(input, 'gpu.csv'), 'utf8')).trim().split('\n').slice(1).map(line => line.split(',').map(x => x.trim()));
const gpu = samples.map(s => ({ utilization: parseFloat(s[1]), power: parseFloat(s[2]) })).filter(s => Number.isFinite(s.utilization) && Number.isFinite(s.power));
const result = { schema_version: 'hswm-dgx-learning-observation/v1', protocol_version: protocol.schema_version,
  raw_summary_sha256: sha(raw), protocol_sha256: sha(await readFile(join(input, 'protocol.json'))),
  durable_receipt: await json(join(input, 'receipt.json')), started: summary.started, finished: summary.finished,
  wall_seconds: (Date.parse(summary.finished) - Date.parse(summary.started)) / 1000,
  planned_trials: summary.plannedTrials, attempted_trials: summary.attemptedTrials, complete_trials: summary.completeTrials,
  runtime_committed_learns: trains.filter((t: any) => t.committedDisposition === 'COMMITTED').length,
  input_audit: { auditedRequests, auditedLearningRequests, predictionCasesLabelFree: true, learnerOnlySawDeclaredTrainingOutcomes: true,
    scope: 'Exact captured HTTP requests; oracle rule intentionally provided only in the separately declared oracle arm.' },
  http: { requestArtifacts: paths.filter(p => p.endsWith('.request.json')).length, recordedResponses: calls.length,
    successfulResponses: calls.filter(c => c.status === 200).length, errorResponses: calls.filter(c => c.status !== 200).length,
    prompt_tokens: calls.reduce((n, c) => n + (c.usage?.prompt_tokens ?? 0), 0), completion_tokens: calls.reduce((n, c) => n + (c.usage?.completion_tokens ?? 0), 0),
    usageMissingResponses: calls.filter(c => c.usage == null).length, reportedFingerprints: [...new Set(calls.map(c => c.fingerprint).filter(Boolean))] },
  gpu: { samples: gpu.length, meanUtilization: gpu.length ? gpu.reduce((n, s) => n + s.utilization, 0) / gpu.length : null,
    peakUtilization: gpu.length ? Math.max(...gpu.map(s => s.utilization)) : null,
    meanPowerWatts: gpu.length ? gpu.reduce((n, s) => n + s.power, 0) / gpu.length : null,
    caveat: 'Device-wide sampling includes serving reload and any co-resident activity; not isolated job attribution or energy measurement.' },
  aggregates, paired, observations,
  learned_relations: trains.map((t: any) => ({ relation: t.state?.semantic?.semanticText, disposition: t.state?.semantic?.disposition,
    uncertainty: t.state?.semantic?.uncertainty, semanticSha256: t.state?.semanticSha256, traceSha256: t.trace?.traceSha256,
    trainingScore: t.trainingScore, observedStatus: t.outcome?.status })),
  limitations: ['Authored synthetic rules and caller-owned observations', 'No checkpoint-weight training, novel topology discovery or external real-world task',
    'Train/heldout cases are disjoint within each trial but overlap across seeds; seeds are not independent task populations',
    'Evidence-only control changes canonical revision metadata and preserves feedback; token costs are not matched',
    'Exact canonical clones still generate fresh execution IDs and requests; temperature zero does not establish output determinism',
    'No Hyperon empirical comparison, independent causal credit, CR/FCL closure or general HSWM efficacy'],
  claim_ceiling: protocol.claim_ceiling };
await mkdir(join(output, '..'), { recursive: true }); await writeFile(output, JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify({ file: output, complete: result.complete_trials, committed: result.runtime_committed_learns, http: result.http, aggregates: result.aggregates, paired: result.paired, gpu: result.gpu }));
