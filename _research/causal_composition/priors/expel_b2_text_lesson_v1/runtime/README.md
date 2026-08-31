# ExpeL B2 direct-capture runtime

This directory closes one bounded executable slice of the pinned ExpeL source:
the two model-visible ALFWorld evaluation channels consisting of numbered
global rules and FAISS-retrieved successful-trajectory few-shots. It does not
close the full ExpeL training, insight-extraction, LLM, ALFWorld simulator, or
efficacy boundary.

## Pinned closure

[`runtime_pin.v1.json`](runtime_pin.v1.json) binds CPython 3.9.17, a
hash-locked 61-distribution dependency set, the immutable
`sentence-transformers/all-mpnet-base-v2` revision
`e8c3b32edf5434bc2275fc9bab85f82640a19130`, its ten required local files,
and the `tiktoken==0.4.0` `cl100k_base` cache bytes. The model files and cache
remain external runtime inputs and are not checked into this repository.

[`direct_capture_fixture.v1.json`](direct_capture_fixture.v1.json) is synthetic
engineering data. It resolves the paper/config rule-cap discrepancy to the
paper's ALFWorld command value of 10, supplies four successful trajectories,
and fixes the current task and retrieval configuration. It is not benchmark
outcome data.

The dependency environment can be reconstructed with the pinned Python and
lock file:

```bash
uv python install 3.9.17
uv venv --python 3.9.17 /path/to/expel-b2-venv
uv pip sync --python /path/to/expel-b2-venv/bin/python \
  --require-hashes \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  _research/causal_composition/priors/expel_b2_text_lesson_v1/runtime/requirements.lock
```

Download only the model files named in `runtime_pin.v1.json` from the pinned
Hugging Face revision, and provide a `tiktoken` cache whose key and digest match
that record. Given an extracted official ExpeL commit whose files pass the
source pin, run:

```bash
uv run python scripts/check_hswm_expel_b2_direct_parity.py \
  --pinned-python /path/to/expel-b2-venv/bin/python \
  --source-root /path/to/ExpeL-e41ec9a \
  --model-root /path/to/all-mpnet-base-v2-e8c3b32 \
  --tiktoken-cache /path/to/tiktoken-cache
```

The checker launches two fresh offline processes. The direct side imports and
executes the pinned upstream `ExpelAgent` methods. The wrapper-vector side does
not import the upstream agent and independently executes the pinned embedding,
FAISS ranking, and token counting inputs before the repository adapter builds
its projection. Both sides fail closed on source, runtime, model, cache, or
capture drift.

## Qualification ceiling

The checked-in qualification records exact parity for all eight engineering
dimensions on the synthetic fixture. It also records the upstream behavior of
building two physical FAISS indexes and embedding the same document batch
twice. No network connection, LLM call, simulator step, outcome, or learning
occurs. Therefore this is not ExpeL efficacy evidence, G0 or G1 evidence, an
HSWM revision admission, a `Permit`, or support for any FCL law.
