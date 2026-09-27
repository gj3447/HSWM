# GEPA relation-text comparison

This isolated experiment uses [GEPA](https://gepa-ai.github.io/gepa/) to propose
bounded revisions of a relation text from **training-only** evaluator feedback.
Candidate execution uses the shared HSWM live evaluator. A separate HTTP
reflection call proposes revised text; it does not alter the canonical graph
or write a candidate into HSWM state.

The optimizer receives only training examples. The standalone runner passes the
seed and chosen candidate to the same Inspect `live_eval.run_live` held-out
comparison after optimization, with the same model, execution budget, and
resource-accounting contract. GEPA candidate selection or a held-out score is
an optimizer comparison and does not establish full HSWM efficacy or authorize
a canonical revision.

## Contract

`live_eval.evaluate_relation(candidate_text, example, execution)` is the shared
callable. Its input example has `id`, `split`, `input`, and target; candidate text
replaces only `input.relation.semanticText`. `execution` fixes base URL, model,
max tokens, timeout, and seed. The bridge returns the typed local execution
result, including answer, request/response hashes, model, usage, latency, and
one model-call count. This adapter derives training score/feedback from the
target, and sends only the training evaluator’s side information to GEPA.
That side information includes the training input with its evaluated candidate
text, expected answer, observed answer, and score; held-out problems and labels
are excluded from reflection.

`max_metric_calls` caps calls to the shared evaluator from GEPA. The caller also
supplies a reflection proposer; this adapter fail-closes after
`max_reflection_calls`, and GEPA receives the same cap as candidate proposals.
The default intended envelope is at most 32 training evaluator calls, 2
reflection calls, and 40 held-out calls total across the two arms (74 total
request attempts). Tests use deterministic proposers and a loopback HTTP fixture;
they make no real-model call. Do not use `hswm_bridge.mts --fixture`: that surface contains oracle
semantic text. Generate provisional-text data with `prepare_fixture.mts`, which
preserves the split and replaces every input relation text before GEPA can see it.

## Run

```sh
cd _research/gepa_relation_comparison_v1
uv sync --locked --group dev
uv run --locked pytest ../../tests/test_gepa_relation_comparison.py ../../tests/test_gepa_relation_cli.py -q
```

After live-model preflight is available, run only from a generated fixture:

```sh
node ../inspect_comparison_v1/prepare_fixture.mts ../../.hswm-local/gepa-fixture
uv run --locked python runner.py ../../.hswm-local/gepa-fixture \
  --output-dir ../../.hswm-local/gepa-relation-comparison
```

The runner writes candidate text and a compact record privately, then writes
ordinary Inspect held-out logs. Missing usage is reported as unknown rather than
converted to zero tokens.
Resource fields named `physical_model_calls` count HTTP request attempts from
the bridge, not confirmed server-side model executions; bridge timeouts carry
an unknown count and a separate upper bound. Reflection requests do not retry
or follow redirects.

## Pin and provenance

This project pins `gepa==0.1.4`, the official PyPI release of 2026-07-15:
wheel SHA-256 `12b971039599625c156d2231f6d72a29c31a22e9c237689459b5f1a3c353f532`.
GEPA is MIT licensed at the release tag
[`v0.1.4`](https://github.com/gepa-ai/gepa/blob/v0.1.4/LICENSE). The lockfile
records all resolved artifacts; it is the installation authority, rather than a
moving `main` branch. GEPA's evaluator protocol and its Actionable Side
Information are documented at
<https://gepa-ai.github.io/gepa/api/optimize_anything/Evaluator/>.
It also pins `inspect-ai==0.3.260` because the runner invokes the existing
shared Inspect evaluator; its exact transitive artifacts are in `uv.lock`.
