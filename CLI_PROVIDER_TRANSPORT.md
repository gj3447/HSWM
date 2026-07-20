# HSWM exploratory CLI provider transport

## Outcome

`cli_provider_transport.py` lets HSWM invoke installed Claude, Grok, or Codex
CLIs through the same Python callable shape as an API transport. It is a local,
one-call/one-process adapter, not an HTTP server and not an official provider
API.

The split is intentional:

| path | role | evidence strength |
|---|---|---|
| pinned Qwen vLLM endpoint | H3-B3 confirmatory extraction | content-attested model snapshot and deployment receipt |
| Claude/Grok/Codex CLI transport | exploratory comparison, review, or development probe | provider-managed, unattested model identity |
| deterministic world compiler | compile already-frozen observations | no live model, network, queue, or retry |

CLI subscription access can therefore reduce exploratory API usage, but it is
not a stable substitute for a supported API: provider quotas, login state,
model aliases, CLI output, and automation terms may change. Keep bulk and
confirmatory work on an attested API/vLLM path.

## Contract

```python
from cli_provider_transport import (
    CLIProvider,
    CLIProviderConfigV1,
    OutputContract,
    make_cli_transport,
)

transport = make_cli_transport(
    CLIProviderConfigV1(
        provider=CLIProvider.CLAUDE,
        executable="claude",
        requested_model="sonnet",
        timeout_seconds=300,
        max_in_flight=1,
    ),
    OutputContract.CLAIMS_V1,
)

response = transport(openai_request_v1)
receipt = transport.receipt(openai_request_v1.request_id)
transport.close()
```

The callable accepts `recorded_llm_extractor.OpenAIRequestV1` and returns
`TransportResponseV1`. A success response contains one ordinary
OpenAI-compatible choice plus top-level `hswm_cli_receipt`. The receipt is also
available from `transport.receipt(request_id)`.

`CLAIMS_V1` accepts exactly:

```json
{"claims":[{"subject":"...","predicate":"...","arguments":[{"role":"...","exact":"..."}]}]}
```

`BATCH_CLAIMS_V1` accepts exactly one `results` array with unique `source_id`
values and the same claim contract. Provider-native JSON schema constraints are
followed by local duplicate-key and exact structural validation. Exact quote
binding and source-span verification remain the extractor's job.

## Provider isolation

- Claude: `--safe-mode`, no tools, no session persistence, no Chrome, no MCPs.
- Grok: an empty temporary `GROK_HOME`, no configured MCPs/skills/hooks,
  `--deny "*"`, no built-in tools, subagents, memory, web search, or plan. Grok
  retains an inert MCP meta-tool surface even with no configured servers, so
  the honest receipt label is `isolated-no-external-tools`, not
  `hard-no-tools`.
- Codex: the current CLI has no hard `--tools ""` equivalent. Construction is
  refused by default. Exploratory callers must explicitly set
  `allow_soft_tool_isolation=True`; the receipt then says `soft-read-only`.

Every invocation uses an argv array with `shell=False`. Prompt text travels by
stdin or a mode-0600 temporary file, never in argv. The transport creates a new
temporary `HOME` and copies only that provider's credential file when an API
key is unavailable; Anthropic, xAI, and OpenAI credential variables are never
cross-inherited. Receipts retain inherited environment variable names only,
never values. Stdout and stderr are drained concurrently with hard byte caps;
stderr content is never persisted because arbitrary provider diagnostics can
contain credentials. Only the stderr byte count and SHA-256 digest are retained.
Cancellation, deadline, or overflow kills the entire process group with a
bounded TERM-to-KILL sequence.

The OpenAI messages and decoding fields are projected into one isolated CLI
prompt. None of the three CLIs currently exposes temperature, seed, top-p, or
max-token parity through this command path, so every receipt says
`generation_control_strength=requested-not-cli-enforced`. The native/local JSON
schema is enforced; API-equivalent decoding is not claimed.

Terminal states are:

```text
succeeded | failed | timed_out | cancelled | output_limit | schema_rejected
```

Only `succeeded` returns a response. Every other state raises
`CLITransportError`, whose `.receipt` is complete and tamper-evident.
Receipts are embedded in every response; the in-process convenience cache is
bounded (16 by default) and keeps separate invocation IDs for retries. Callers
that need durable history must persist the embedded receipts themselves.

## H3 boundary

Do not inject this transport into the current H3-B3 confirmatory run. The
confirmatory preregistration pins Qwen and requires a content-attested live
deployment. In addition, `recorded_llm_extractor.PRODUCER` is currently fixed
to `hswm-recorded-openai-compatible/v1`; changing that frozen module would
invalidate the current preflight receipt.

For exploratory use, persist the embedded CLI receipt beside a separately
labelled cache/manifest and use a model revision such as
`provider-managed-unattested:<provider>:<requested-model>`. Do not merge that
cache into a Qwen manifest. Producer parameterization is a later, separately
gated change after the current confirmatory run.

## Why there is no local HTTP broker yet

There is one current consumer and no measured need for durable scheduling,
restart recovery, multi-client admission, authentication, or schema migration.
Adding an HTTP daemon and job database now would manufacture a mutable runtime
owner. The promotion gates are recorded in
`CLI_PROVIDER_MODULE_DECISION_2026-07-20.json`; build a broker only when those
obligations are real.

## Verification

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q \
  -p no:cacheprovider tests/test_cli_provider_transport.py
```

The tests use fake executables and spend no provider quota. A live smoke test
should use one empty-claims request per provider, inspect the receipt, and stay
outside all confirmatory H3 artifacts.

### Live smoke — 2026-07-20

After isolation hardening, the installed CLIs were each invoked once with the
exact module command path and an empty-claims contract. No smoke output was
written into an H3 cache.

| provider | installed version | requested model | isolation | result | receipt SHA-256 |
|---|---|---|---|---|---|
| Claude | `2.1.215` | `sonnet` | `hard-no-tools` | `{"claims":[]}` | `c393867ab10c7781f32ebcfbbecd151c4a311c69aa482ccbb00fe5dfdd8c7016` |
| Grok | `0.2.101` | `grok-4.5` | `isolated-no-external-tools` | `{"claims":[]}` | `a9b2057e79360fb22a6aff4a55a5ee3a8f037009fb354dd12ba5037d1cac197a` |
| Codex | `0.144.6` | `gpt-5.6-sol` | `soft-read-only` | `{"claims":[]}` | `39eba8bea38a5c48d083dbf75d5be3db7887cd1843c52fbda4e4d36a3014055d` |

Grok reported runtime model `grok-4.5-build`; Claude and Codex did not expose a
runtime model in their result event. None exposed an independently observed
immutable revision, so all receipts correctly retain
`model_identity_strength=provider-managed-unattested` regardless of the
requested alias.

An earlier Grok smoke using the first draft was rejected as validation evidence
after review showed that global skills and MCP servers had been injected. The
corrected smoke above used a temporary `GROK_HOME`, added a deny-all tool rule,
and produced no new file under the global `~/.grok/sessions` tree.
