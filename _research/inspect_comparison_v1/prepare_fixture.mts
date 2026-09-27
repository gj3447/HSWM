/** Export one existing authored family with the old frozen train/heldout split. */
import { mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve, join, dirname } from 'node:path';
import { task } from '../dgx_semantic_learning_v1/domain.mts';
import { localSemanticCases } from '../../src/hswm/effect-runtime/src/local-semantic-execution-domain.ts';

const [destination, familyArg = '0', seedArg = '0'] = process.argv.slice(2);
const family = Number(familyArg), seed = Number(seedArg);
if (!destination || !Number.isInteger(family) || family < 0 || family > 3 || !Number.isInteger(seed) || seed < 0 || seed > 3)
  throw new Error('Usage: node prepare_fixture.mts NEW_OUTPUT_DIRECTORY [family 0..3] [seed 0..3]');
const root = resolve(destination), study = task(family, seed);
await mkdir(dirname(root), { recursive: true, mode: 0o700 });
await mkdir(root, { recursive: false, mode: 0o700 });
const hashes: Record<string, string> = {};
async function save(name: string, text: string) {
  await writeFile(join(root, name), text, { flag: 'wx', mode: 0o600 });
  hashes[name] = createHash('sha256').update(text).digest('hex');
}
for (const split of ['train', 'heldout'] as const) {
  const records = study[split].map(index => {
    const example = localSemanticCases[family * 32 + index]!;
    // The W1 fixture contains oracle meaning. Keep it out of optimizer inputs.
    const input = { ...example.input, relation: { ...example.input.relation, semanticText: study.initial } };
    return { id: example.caseId, split, input, target: String(example.expected.answer) };
  });
  await save(`${split}.jsonl`, records.map(row => JSON.stringify(row)).join('\n') + '\n');
}
await save('baseline.txt', study.initial + '\n');
await save('execution.json', JSON.stringify({ base_url: 'http://127.0.0.1:8001', model: 'qwen3-4b-real', max_tokens: 32, timeout_seconds: 30, seed: 0 }, null, 2) + '\n');
await save('fixture.json', JSON.stringify({ family, seed, task: study.id, train: study.train.length, heldout: study.heldout.length,
  hashes, source: '_research/dgx_semantic_learning_v1/domain.mts + local-semantic-execution-domain.ts',
  evidence_kind: 'AUTHORED_SYNTHETIC_TOOLING_FIXTURE_NOT_MODEL_RESULT',
  model_identity: 'HISTORICAL_SERVED_NAME_REQUIRES_LIVE_PREFLIGHT_NOT_WEIGHT_ATTESTATION' }, null, 2) + '\n');
process.stdout.write(root + '\n');
