import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { test } from 'node:test';
import { prepareOracleDiagnostic, selectDiagnosticCases } from '../../_research/inspect_comparison_v1/prepare_oracle_diagnostic.mts';

test('oracle diagnostic selection covers each pel/nub/label stratum exactly once', () => {
  for (const family of [0, 1, 2, 3]) {
    const selected = selectDiagnosticCases(family);
    assert.equal(selected.length, 8);
    assert.equal(new Set(selected.map(row => `${row.pel}/${row.nub}/${row.expected}`)).size, 8);
    assert(selected.every(row => row.frozenRuleExpected === (row.expected ^ row.pel)));
  }
});

test('oracle diagnostic fixture is private, development-exposed, and no-overwrite', async () => {
  const parent = await mkdtemp(join(tmpdir(), 'hswm-oracle-diagnostic-')), root = join(parent, 'fixture');
  try {
    await prepareOracleDiagnostic(root, process.cwd());
    const rootManifest = JSON.parse(await readFile(join(root, 'fixture.json'), 'utf8'));
    assert.equal(rootManifest.totalLogicalCases, 32); assert.equal(rootManifest.totalModelCallMaximum, 64); assert.equal(rootManifest.modelCallsPerformed, false);
    for (const family of [0, 1, 2, 3]) {
      const dir = join(root, `family-${family}`), manifest = JSON.parse(await readFile(join(dir, 'fixture.json'), 'utf8'));
      const rows = (await readFile(join(dir, 'train.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
      assert.equal(rows.length, 8); assert(rows.every(row => row.split === 'train'));
      assert.equal(manifest.developmentExposure, 'DEVELOPMENT_EXPOSED_HISTORICAL_FAMILY_NOT_FINAL_HOLDOUT');
      assert.equal(manifest.originalHistoricalMembership, 'NOT_CLAIMED_AS_HELDOUT');
      assert.equal(manifest.selected.filter((row: { nub: number }) => row.nub === 1).length, 4);
      assert.notEqual(await readFile(join(dir, 'baseline.txt'), 'utf8'), await readFile(join(dir, 'oracle.txt'), 'utf8'));
    }
    await assert.rejects(() => prepareOracleDiagnostic(root, process.cwd()));
  } finally { await rm(parent, { recursive: true, force: true }); }
});
