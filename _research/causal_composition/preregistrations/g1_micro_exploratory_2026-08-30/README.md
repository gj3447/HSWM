# HSWM G1 micro exploratory freeze

This source freeze starts the smallest executable G1-shaped vertical slice. It
is an integration-readiness study, not a G0 pass, G1 occurrence, gate promotion,
or efficacy claim.

The canonical JSON SHA-256 of `protocol.v1.json` is
`1506653fdc1eb8026c2e1041a295e1b57a05026f523c175f4ec22ebab3ebea5f`.

The slice permits one experiment-local, cue-bound operator disposition. A model
trajectory is sealed before feedback; the true outcome is computed by a local,
same-process evaluator; a precommitted outcome-independent sham supplies an alternative;
and one fresh model call reads only the disposition compiled from each branch's
durable state. The ACTIVE state is then removed to exact genesis and restored to
the exact prior state hash.

Provider response bytes are retained as observations. Semantic schema validity,
call caps, no retry, a local one-shot in-process guard, durable CAS, and exact state
identity remain strict; response-byte equality is not a precondition.

The local evaluator has a separate schema owner label but is not independently
owned or externally authenticated. The run therefore cannot satisfy G0/CF-07.
Eight completion POSTs each have one tokenizer-preflight POST, for a total cap
of sixteen loopback HTTP POSTs. Any five-branch pattern is descriptive only;
the completed-run terminal always forbids efficacy inference.

If the precommitted sham bit happens to equal the observed ACTIVE feedback,
that occurrence is recorded as an uninformative equality, not as evidence from
a sham control contrast.

Run the no-network preflight first:

```sh
uv run --locked python -m hswm.experiments.g1_micro \
  --protocol _research/causal_composition/preregistrations/g1_micro_exploratory_2026-08-30/protocol.v1.json \
  --endpoint http://127.0.0.1:18080 \
  --model qwen3.6-35b-a3b \
  --output-dir OUTPUT \
  --execution-registry /mnt/hswm/evidence/hswm-g1-micro-exploratory-2026-08-30-consumption-v1 \
  --preflight-only
```

On the maintainer DGX path, run the checked-in fresh-service wrapper through
`~/bin/hswm-run`. Its `--preflight-only` mode performs no service mutation or
model HTTP call. Removing that flag stops only the three allowlisted shared
containers, launches one fresh pinned vLLM at host endpoint
`127.0.0.1:18080`, and authorizes at most eight completions plus eight
tokenizer preflights. The host ingress is loopback-bound, but the container
uses Docker bridge networking; outbound egress is not independently blocked.
No cloud credential belongs in arguments or artifacts.

```sh
uv run --locked python -m hswm.experiments.g1_micro_dgx \
  --protocol _research/causal_composition/preregistrations/g1_micro_exploratory_2026-08-30/protocol.v1.json \
  --model-snapshot MODEL_SNAPSHOT \
  --lock-path /mnt/hswm/evidence/hswm-g1-micro-dgx.lock \
  --execution-registry /mnt/hswm/evidence/hswm-g1-micro-exploratory-2026-08-30-consumption-v1 \
  --preflight-only
```

After the single execution, replay the local frozen-protocol, raw runtime,
eight-request final-attestation, teardown, and service-restoration joins:

```sh
uv run --locked python scripts/verify_hswm_g1_micro_bundle.py RESULT_JSON \
  --protocol _research/causal_composition/preregistrations/g1_micro_exploratory_2026-08-30/protocol.v1.json \
  --execution-registry /mnt/hswm/evidence/hswm-g1-micro-exploratory-2026-08-30-consumption-v1 \
  --dgx-runtime-receipt DGX_RUNTIME_RECEIPT
```

The local in-process guard explicitly is not an Atom v2 Permit and does not write
repository-canonical HSWM state. Complete G1 still requires a passed G0 and the
full frozen `CF-01`, `CF-02`, `CF-05`, `CF-06`, `CF-07`, `CF-08`, `CF-09`,
`CF-13`, and `CF-14` confirmatory control set.
