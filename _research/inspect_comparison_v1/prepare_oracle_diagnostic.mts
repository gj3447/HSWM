/// <reference path="./effect-runtime.d.ts" />
/** Prepare a deterministic, development-exposed oracle-vs-frozen E1 fixture. */
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { Effect } from '../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js';
import { example, label, task } from '../dgx_semantic_learning_v1/domain.mts';
import { localSemanticCases } from '../../src/hswm/effect-runtime/src/local-semantic-execution-domain.ts';

const sha256 = (text: string) => createHash('sha256').update(text).digest('hex');
const sourcePaths = ['_research/dgx_semantic_learning_v1/domain.mts', 'src/hswm/effect-runtime/src/local-semantic-execution-domain.ts', '_research/inspect_comparison_v1/prepare_oracle_diagnostic.mts'] as const;
const execution = { base_url: 'http://127.0.0.1:8001', model: 'qwen3-4b-real', max_tokens: 32, timeout_seconds: 30, seed: 0 };
const screening = { oracleCorrectAtLeast: 30, frozenRuleConsistencyAtLeast: 30, eachFamilyOracleCorrectAtLeast: 7, allOutputsValid: true, mandatoryExceptionCasesRecorded: true, decisionPass: 'DEVELOPMENT_SCREEN_PASSED', decisionFail: 'REVISE_LOCAL_EXECUTION', noEfficacyOrPopulationClaim: true } as const;

export type DiagnosticRow = { id: string; split: 'train'; input: unknown; target: string };
export type Selection = { originalId: number; expected: 0 | 1; pel: 0 | 1; nub: 0 | 1; frozenRuleExpected: 0 | 1 };
type FamilyBuild = { study: ReturnType<typeof task>; selected: Selection[]; rows: DiagnosticRow[] };
type FileMap = Record<string, string>;
const bit = (value: number, name: string): 0 | 1 => { if (value !== 0 && value !== 1) throw new Error(`${name} must be a bit`); return value; };
const familyNumber = (family: number) => { if (!Number.isInteger(family) || family < 0 || family > 3) throw new Error('family must be 0..3'); return family; };

/** Pure deterministic selection: one label of each kind in every (pel,nub) stratum. */
export function selectDiagnosticCases(inputFamily: number): Selection[] {
  const family = familyNumber(inputFamily);
  const rows = Array.from({ length: 32 }, (_, originalId) => {
    const fields = example(originalId), expected = bit(label(family, originalId), 'label');
    const pel = bit(fields.context.pel, 'pel'), nub = bit(fields.exception.nub, 'nub');
    return { originalId, expected, pel, nub, frozenRuleExpected: bit(expected ^ pel, 'frozen rule expected') };
  });
  const selected: Selection[] = [];
  for (const pel of [0, 1] as const) for (const nub of [0, 1] as const) for (const expected of [0, 1] as const) {
    const item = rows.find(row => row.pel === pel && row.nub === nub && row.expected === expected);
    if (!item) throw new Error(`family ${family} lacks stratum ${pel}/${nub}/${expected}`);
    selected.push(item);
  }
  return selected;
}

/** Validates the independently authored local fixture before any selection. */
export function validateDomainAgreement(): void {
  for (const family of [0, 1, 2, 3]) for (let originalId = 0; originalId < 32; originalId++) {
    const source = localSemanticCases[family * 32 + originalId];
    if (!source) throw new Error(`missing local semantic case ${family}/${originalId}`);
    const fields = example(originalId), expected = bit(label(family, originalId), 'label');
    if (source.expected.answer !== expected || source.input.fields.context.pel !== fields.context.pel || source.input.fields.exception.nub !== fields.exception.nub)
      throw new Error(`domain disagreement ${family}/${originalId}`);
  }
}

export function buildFamily(inputFamily: number): FamilyBuild {
  const family = familyNumber(inputFamily), study = task(family, 0), selected = selectDiagnosticCases(family);
  const rows = selected.map(selection => {
    const source = localSemanticCases[family * 32 + selection.originalId];
    if (!source) throw new Error(`missing local semantic case ${family}/${selection.originalId}`);
    const input = { ...source.input, relation: { ...source.input.relation, semanticText: study.initial } };
    return { id: source.caseId, split: 'train' as const, input, target: String(selection.expected) };
  });
  return { study, selected, rows };
}

const writeExclusive = (path: string, contents: string) => Effect.tryPromise({ try: () => writeFile(path, contents, { flag: 'wx', mode: 0o600 }), catch: cause => new Error(`write failed: ${path}`, { cause }) });
const readText = (path: string) => Effect.tryPromise({ try: () => readFile(path, 'utf8'), catch: cause => new Error(`read failed: ${path}`, { cause }) });
const makeDirectory = (path: string, recursive: boolean) => Effect.tryPromise({ try: () => mkdir(path, { recursive, mode: 0o700 }), catch: cause => new Error(`mkdir failed: ${path}`, { cause }) });
const hashes = (files: FileMap) => Object.fromEntries(Object.entries(files).map(([name, contents]) => [name, sha256(contents)]));

const prepareEffect = (destination: string, checkoutRoot: string) => Effect.gen(function*() {
  validateDomainAgreement();
  const root = resolve(destination);
  const sourceHashes = yield* Effect.forEach(sourcePaths, source => readText(join(checkoutRoot, source)).pipe(Effect.map(contents => [source, sha256(contents)] as const)));
  const sourceSha256 = Object.fromEntries(sourceHashes);
  yield* makeDirectory(dirname(root), true); yield* makeDirectory(root, false);
  const familyManifests: { family: number; fixtureSha256: string; selectedIds: number[] }[] = [];
  for (const family of [0, 1, 2, 3]) {
    const dir = join(root, `family-${family}`), { study, selected, rows } = buildFamily(family);
    yield* makeDirectory(dir, false);
    const files: FileMap = { 'train.jsonl': rows.map(row => JSON.stringify(row)).join('\n') + '\n', 'baseline.txt': study.initial + '\n', 'oracle.txt': study.oracle + '\n', 'execution.json': JSON.stringify(execution, null, 2) + '\n' };
    const fileHashes = hashes(files), fixtureSha256 = sha256(Object.entries(files).map(([name, contents]) => `${name}\0${contents}`).join(''));
    yield* Effect.forEach(Object.entries(files), ([name, contents]) => writeExclusive(join(dir, name), contents));
    const manifest = { schema: 'hswm-inspect-oracle-single-diagnostic/v1', family, seed: 0, task: study.id, developmentExposure: 'DEVELOPMENT_EXPOSED_HISTORICAL_FAMILY_NOT_FINAL_HOLDOUT', originalHistoricalMembership: 'NOT_CLAIMED_AS_HELDOUT', fixedArms: ['FROZEN_SINGLE_E1', 'ORACLE_SINGLE_E1'], maxModelCallsForThisFamily: 16, sourceSha256, fixtureSha256, files: fileHashes, selected: selected.map(row => ({ ...row, evaluatorOnly: { groundTruth: row.expected, frozenRuleExpected: row.frozenRuleExpected } })), screening };
    yield* writeExclusive(join(dir, 'fixture.json'), JSON.stringify(manifest, null, 2) + '\n');
    familyManifests.push({ family, fixtureSha256, selectedIds: selected.map(row => row.originalId) });
  }
  const rootManifest = { schema: 'hswm-inspect-oracle-diagnostic-root/v1', sourceSha256, families: familyManifests, totalLogicalCases: 32, totalModelCallMaximum: 64, arms: ['FROZEN_SINGLE_E1', 'ORACLE_SINGLE_E1'], modelCallsPerformed: false, screening };
  yield* writeExclusive(join(root, 'fixture.json'), JSON.stringify(rootManifest, null, 2) + '\n');
  return root;
});

/** The sole production composition root for all fixture filesystem I/O. */
export const prepareOracleDiagnostic = (destination: string, checkoutRoot = resolve(import.meta.dirname, '../..')) => Effect.runPromise(prepareEffect(destination, checkoutRoot));

if (process.argv[1] && resolve(process.argv[1]) === resolve(import.meta.filename)) {
  if (process.argv[2] === '--help') process.stdout.write('Usage: node prepare_oracle_diagnostic.mts NEW_OUTPUT_DIRECTORY\n');
  else { const destination = process.argv[2]; if (!destination || process.argv.length !== 3) throw new Error('Usage: node prepare_oracle_diagnostic.mts NEW_OUTPUT_DIRECTORY'); process.stdout.write(await prepareOracleDiagnostic(destination) + '\n'); }
}
