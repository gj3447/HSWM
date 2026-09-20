import { describe, expect, it } from 'vitest';
import { task, label, protocol, score, responseFormat } from '../../_research/dgx_semantic_learning_v1/domain.mts';
import { copyTree } from '../../_research/dgx_semantic_learning_v1/io.mts';
import { mkdtemp, mkdir, writeFile, link, stat, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
describe('DGX semantic learning instrument', () => {
  it('seals disjoint balanced train and heldout cases for every declared trial', () => {
    expect(protocol.tasks).toHaveLength(16);
    for (const t of protocol.tasks) {
      expect(new Set([...t.train, ...t.heldout]).size).toBe(32);
      expect(t.train).toHaveLength(12); expect(t.heldout).toHaveLength(20);
      expect(t.train.reduce((n, i) => n + label(t.family, i), 0)).toBe(6);
      expect(t.heldout.reduce((n, i) => n + label(t.family, i), 0)).toBe(10);
      expect(task(t.family, t.seed)).toEqual(t);
    }
  });
  it('has counterfactual context and exception effects for every subject assignment', () => {
    for (let f = 0; f < 4; f++) for (let i = 0; i < 32; i++) {
      expect(label(f, i ^ 8)).toBe(1 - label(f, i));
      expect(label(f, i ^ 16)).toBe(1 - label(f, i));
    }
    expect(label(0, 1)).toBe(1); expect(label(0, 3)).toBe(0);
    expect(label(1, 4)).toBe(1); expect(label(1, 3)).toBe(0);
    expect(label(2, 3)).toBe(1); expect(label(2, 1)).toBe(0);
    expect(label(3, 4)).toBe(1); expect(label(3, 5)).toBe(0);
  });
  it('rejects malformed batches without partial-credit parsing or silent repair', () => {
    expect(score('1', 0, [1])).toEqual({ valid: true, correct: 1, total: 1 });
    for (const bad of [' 1', '1\n', '[1]', '10', 'true']) expect(score(bad, 0, [1])).toEqual({ valid: false, correct: 0, total: 1 });
  });
  it('preserves journal slot/object hard links within a clone without linking back to its source', async () => {
    const root = await mkdtemp(join(tmpdir(), 'hswm-journal-clone-'));
    try {
      const source = join(root, 'source'), clone = join(root, 'clone'); await mkdir(source);
      await writeFile(join(source, 'object'), 'sealed bytes'); await link(join(source, 'object'), join(source, 'slot'));
      await copyTree(source, clone);
      expect((await stat(join(clone, 'slot'))).ino).toBe((await stat(join(clone, 'object'))).ino);
      expect((await stat(join(clone, 'slot'))).ino).not.toBe((await stat(join(source, 'slot'))).ino);
      await writeFile(join(clone, 'object'), 'clone change');
      expect(await readFile(join(source, 'object'), 'utf8')).toBe('sealed bytes');
    } finally { await rm(root, { recursive: true, force: true }); }
  });
  it('constrains prediction shape independently of hidden truth and preserves exact exception references', () => {
    const frame = { event: JSON.stringify({ cases: [{ arbitrary: 9 }, { arbitrary: 12 }] }), relation: { semantic: { exceptionRefs: ['exception:flag'] } } };
    const prediction = responseFormat({ contract: 'hswm-llm-semantic-predict/v1', frame });
    expect(prediction.json_schema.schema.properties.prediction).toEqual({ type: 'string', pattern: '^[01]{2}$' });
    const revised = responseFormat({ contract: 'hswm-llm-semantic-learn/v1', frame });
    expect(revised.json_schema.schema.properties.exceptionRefs).toEqual({ type: 'array', const: ['exception:flag'] });
    expect(revised.json_schema.schema.additionalProperties).toBe(false);
  });
});
