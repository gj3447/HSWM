import { createHash } from 'node:crypto';
export const digest = (v: string | Uint8Array) => createHash('sha256').update(v).digest('hex');
export const arms = ['frozen', 'learned', 'evidence_only', 'removed', 'restored', 'oracle'] as const;
export const models = [{ id: 'qwen3.6-35b-a3b', port: 8000 }, { id: 'qwen3-4b-real', port: 8001 }] as const;
export const families = [
  { name: 'xor', base: 'The initial bit is 1 exactly when subject fields dax and wug differ.' },
  { name: 'role_selection', base: 'The initial bit is the value of subject field zif; dax and wug do not determine it.' },
  { name: 'conjunction', base: 'The initial bit is 1 exactly when both subject fields dax and wug are 1.' },
  { name: 'conditional', base: 'If subject field dax is 1, the initial bit is wug; otherwise it is zif.' }
] as const;
export const example = (id: number) => ({ id, subject: { dax: id & 1, wug: (id >> 1) & 1, zif: (id >> 2) & 1 }, context: { pel: (id >> 3) & 1 }, exception: { nub: (id >> 4) & 1 } });
export function label(family: number, id: number): number {
  const { subject: { dax: a, wug: b, zif: c }, context: { pel: d }, exception: { nub: e } } = example(id);
  const base = [a ^ b, c, a & b, a ? b : c][family];
  return base ^ d ^ e;
}
export function task(family: number, seed: number) {
  const ids = Array.from({ length: 32 }, (_, i) => i);
  const rank = (a: number, b: number) => digest(`${family}:${seed}:${a}`).localeCompare(digest(`${family}:${seed}:${b}`));
  const train = [0, 1].flatMap(bit => ids.filter(id => label(family, id) === bit).sort(rank).slice(0, 6)).sort(rank);
  const heldout = ids.filter(id => !train.includes(id)).sort(rank);
  const suffix = 'Finally, exception flag nub equal to 1 flips the bit; nub equal to 0 leaves it unchanged.';
  return { id: `${families[family].name}-seed${seed}`, family, seed, train, heldout,
    initial: `${families[family].base} Provisional hypothesis: context flag pel never affects the initial bit. ${suffix}`,
    oracle: `${families[family].base} Context flag pel equal to 1 flips that bit, while pel equal to 0 leaves it unchanged. ${suffix}` };
}
export const protocol = {
  schema_version: 'hswm-dgx-semantic-learning/v1', date: '2026-09-20',
  purpose: 'Real LLM outcome-conditioned durable semantic revision; compare revised meaning with feedback-only control.',
  models, families, arms, seeds: [0, 1, 2, 3], tasks: families.flatMap((_, f) => [0, 1, 2, 3].map(s => task(f, s))),
  trials: 32, maximum_model_calls: 256, maximum_wall_seconds: 2400, trial_concurrency: 2,
  temperature: 0, max_output_tokens: 1536, thinking: false, retries: 0,
  train_cases_per_trial: 12, heldout_cases_per_trial: 20,
  primary_metric: 'Exact held-out bit accuracy; malformed batch predictions count as zero correct with validity reported separately.',
  comparisons: ['learned versus frozen', 'learned versus evidence_only', 'removed versus frozen', 'restored versus learned', 'oracle execution ceiling'],
  controls: 'All arms share frozen held-out examples and model/output caps. Evidence-only retains training outcome while restoring initial semantic text. Token costs are measured, not assumed equal.',
  frozen_labels: 'Authored deterministic environment; labels are not independent real-world observations or third-party custody.',
  criteria: 'Report every trial, gain, regression, malformed response, mutation error, restoration hash and cost. No post-hoc pass threshold or population significance claim.',
  claim_ceiling: 'BOUNDED_SYNTHETIC_RUNTIME_OBSERVATION_NOT_GENERAL_HSWM_EFFICACY_CAUSAL_CREDIT_OR_CR_FCL_CLOSURE'
};
export function score(prediction: string, family: number, ids: readonly number[]) {
  const valid = prediction.length === ids.length && /^[01]+$/.test(prediction);
  return { valid, correct: valid ? ids.filter((id, i) => Number(prediction[i]) === label(family, id)).length : 0, total: ids.length };
}
