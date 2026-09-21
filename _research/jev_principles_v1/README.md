# Jev principles applied to HSWM

This bounded study implements two public ideas: typed decision probabilities and outcome-fitted probability calibration. It uses an existing Qwen3-4B LM head through vLLM logprobs, not Jev's service, a newly trained neural head, or a reconstruction of its unpublished RLCD algorithm.

The HSWM target remains one large AI, hypergraph neural organization, LLM-function computation, and hypergraph Semantic Weight. A graph relation's role/context-conditioned disposition is not a confidence scalar. Canonical graph learning and checkpoint training are separate measured interventions.

`domain.mts` freezes four prior Boolean task families, 12 training cases per family, 8 calibration cases and 12 final test cases. Each graph condition is compared with single-case JSON generation and a one-token candidate-logprob readout. The decision module is pure TypeScript/Effect Either in `src/hswm/effect-runtime/src/semantic-decision-domain.ts`. Temperature is fitted only on the calibration split and cannot change binary argmax predictions. A uniform-probability baseline and secondary decision-only JSON accuracy expose improvements caused merely by output consistency checks.

`support/` preserves copies of the existing semantic learning runner and its pure domain/I/O. The old runner's data, protocol and reference-grant authority are unchanged. The new study protocol describes the new readout experiment, not a retroactive replacement of the prior protocol. `store.mts` reopens the native canonical store in fresh processes. It reuses the prior store initialization/read implementation and exposes its actual typed roles. The native LLM proposal, observed training feedback, graph-loop admission, journal and remove/restore copies are used, with no canonical Permit or identified causal-credit claim.

The source manifest seals 315 runner/compiled artifacts before the DGX run. The remote installed Effect version is 3.22.1; complete dependency-tree identity is not claimed. Source pins list the observed model cache revision; cache identity alone does not authenticate every loaded tensor byte. No new package or model weight was downloaded.

Run only after building, qualifying the two candidate token IDs, verifying staged hashes and the `hswm-run` preflight:

```sh
npm --prefix src/hswm/effect-runtime run build
npm --prefix src/hswm/effect-runtime run test -- ../../../tests/effect-runtime/semantic-decision-domain.test.ts --maxWorkers=1
HSWM_RESEARCH_RUNTIME_DIST=/absolute/pinned/runtime-dist \
  ~/bin/hswm-run exec NEW_RUN_ID --profile hswm -- bash _research/jev_principles_v1/launch.sh
node _research/jev_principles_v1/analyze.mts PRIVATE_OUTPUT_ROOT NEW_OBSERVATIONS_JSON
```

The capability probe is separate from the evaluation cohort. It demonstrated logprob access and also preserved an overconfident wrong conjunction answer. Study calls are serial; there is no measured shared-backbone or parallel-head speedup. Retain failures and all raw requests in the durable run archive. Do not edit a runner used by an active run.

Source interpretation: [TypeSafe principles](https://docs.typesafe.ai/introduction/machine-learning-primer), [confidence](https://docs.typesafe.ai/confidence), [limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13), [vLLM 0.25.1 protocol](https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/entrypoints/openai/chat_completion/protocol.py), [temperature scaling](https://proceedings.mlr.press/v70/guo17a.html). TypeSafe's architecture, training data, loss and RL optimizer remain unpublished in the reviewed material; logprob conditioning and temperature scaling must not be relabeled RLCD.

Completed result: [DGX observations and adoption decision](../../results/HSWM_JEV_PRINCIPLES_2026-09-21.md). All four admitted revisions left the visible semantic fields unchanged. Direct readout was faster and structurally reliable; neither meaning learning nor useful direct-probability quality was established. `audit.mts` preserves this no-op finding and repeated-request variation.

The separate `prepare-artifacts.mts` and `graph.mts` create public summaries and the source-bound KG snapshot; they are post-run artifact builders, not part of the frozen execution manifest. `publish.mts` accepts only the reviewed exact bundle digest through the existing registry/anchor/collision-checking publisher. `readback.mts` verifies every published property and relationship in a fresh read session. [Competency queries](../../ontology/queries/hswm_jev_principles_2026-09-21/README.md) connect six principles to all 16 CR/FCL obligations without claiming to discharge them.
