import { task, example, label, digest } from './support/domain.mts';
export { task, example, label, digest };
export const arms = ['frozen', 'learned', 'evidence_only', 'removed', 'restored', 'oracle'] as const;
export const modes = ['direct', 'generated'] as const;
export const split = (family: number) => {
  const t = task(family, 0);
  const calibration = [0,1].flatMap(y => t.heldout.filter(id => label(family,id) === y).slice(0,4));
  const test = t.heldout.filter(id => !calibration.includes(id));
  return { family, task: t, calibration, test };
};
export const protocol = {
  schema_version: 'hswm-jev-principles/v1', date: '2026-09-21',
  conceptual_delta: 'Apply typed decision readout and outcome-fitted temperature to the existing local LLM semantic graph; use frozen LM candidate logprobs rather than generate probability text.',
  identity: 'One AI organized as a Semantic Weight hypergraph, with LLM functions as basic computation; graph state persists and local operators read it.',
  model: 'qwen3-4b-real', port: 8001, checkpoint_cache: '1cfa9a7208912126459214e8b04321603b3df60c',
  tasks: [0,1,2,3].map(split), arms, modes,
  trials: 4, evaluation_cases_per_trial: 20, calibration_cases_per_trial: 8, test_cases_per_trial: 12,
  calibration: 'Fit one positive temperature per arm and output mode, pooling 32 calibration cases; 48 separate test cases; grid 0.25..4 plus 1; no bias or label-based argmax changes.',
  learning: 'Reuse source-pinned native train worker with 12 training examples; mechanical graph-loop admission and durable journal; reference authorization only, not canonical Permit or causal credit.',
  projection: 'Read semantic content, typed role descriptions and prior observed training evidence from a reopened native graph. No test labels enter inference; cases have no answer-derived IDs.',
  direct: 'One-token existing LM readout; allowed token IDs 15/16 independently verified; raw logprobs conditioned on 0/1. Missing candidate => refused, not imputed. Not a new trained head, parallel sampler, or RLCD reproduction.',
  generated: 'One case per JSON generation: prediction 0/1 and p1. Shape constraints contain no answer. Disagreement between chosen bit and p1 => refused; no repair.',
  scheduling: 'Serial model calls; mode order alternates by case and arm. No shared-trunk or parallel-speedup claim.',
  execution_cap: { model_calls: 980, wall_seconds: 2400, retries: 0, request_seconds: 60 },
  metrics: ['test exact accuracy with refusals counted wrong', 'coverage/refusal rate', 'Brier and NLL on valid predictions', 'paired-valid Brier/NLL', 'prompt/output tokens', 'latency including warm/cold mixed effects'],
  comparisons: ['direct vs generated on same graph/cases', 'learned vs frozen and evidence-only within mode', 'raw vs calibration-only temperature on test', 'removed/frozen and restored/learned state and output consistency', 'oracle semantic execution'],
  frozen_success_interpretation: 'Report descriptive deltas with family breakdown. Do not claim general superiority from synthetic 4-family data. A speed gain with accuracy loss is a tradeoff, not overall improvement. Temperature cannot improve binary argmax accuracy.',
  dependency_boundary: 'Parallel head training, learned candidate discovery, n-ary joint readout and two-scale composition remain unimplemented; no evidence from this experiment transfers to them.',
  claim_ceiling: 'BOUNDED_SYNTHETIC_READOUT_AND_CALIBRATION_NOT_HSWM_EFFICACY_CR_FCL_CLOSURE'
};
export const system = 'You are a local semantic operator. Apply the supplied relation to the single case. Respect role bindings, context and exceptions. Prior observations are evidence, not the answer for this case. Compute the output bit prescribed by the relation. No tools.';
export function projectedInput(state: any, id: number) {
  const { id: unused, ...localCase } = example(id);
  return { relation: { semanticText: state.semantic.semanticText, disposition: state.semantic.disposition,
    exceptionRefs: state.semantic.exceptionRefs, uncertainty: state.semantic.uncertainty },
    roleContract: state.roles,
    priorTrainingEvidence: state.priorEvidence, case: localCase };
}
