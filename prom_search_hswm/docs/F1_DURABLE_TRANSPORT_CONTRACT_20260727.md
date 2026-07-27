# F1 durable model-call transport contract

Status: **LOCAL ENGINEERING PASS / TARGET DEPLOYMENT PENDING / SCIENCE UNJUDGED**

Date: 2026-07-27

Implementation commit: `95bf78b51aba5efde8674134a3eed4c2c7494c29`

## Outcome

The F1 runner no longer treats a malformed or interrupted model response as a
reason to sample the model again. Each accepted call, each completed item-arm,
and the final suite now has a durable, content-bound path. The client may repeat
delivery to the result spool, but the spool may dispatch one upstream inference
at most once for a `physical_call_id` and must replay the first committed bytes.

This closes the local engineering slice of closure gate G0. It does **not**
authorize a new F1 measurement. A successor preregistration must bind the new
structured-output schemas and code hashes, and the same disconnect test must
pass against the target DGX deployment before G1 can start.

## Decision: focused module, not a new engine

The implementation is an F1 transport module with two durable stores:

- `SQLiteResultSpool`: server-side one-dispatch, byte-replay authority;
- `SQLiteF1CallLedger`: client-side append-audited attempt, response, call, and
  item-arm ledger;
- `DurableSpoolJSONPort`: strict client adapter joining those two stores to the
  existing typed function network;
- `prom_f1_function_network`: bounded cohort scheduling and final suite
  materialization.

It does not own scientific judgment, model scheduling, generic workflows,
LakatoTree registration, or HSWM cellular execution. A second independent
consumer, multi-host writers, admission policy, or multiple durable backends
would be evidence for later engine promotion. None is present now.

OMD, leases, linked worktrees, and distributed writers are outside this design.
One F1 runner owns one client ledger, and one spool process owns one spool
database.

## Identity and exactly-three-call invariant

`physical_call_id` is the frozen inference identity already carried by
`ModelCallV1`. The durable intent additionally binds:

- exact canonical request bytes and request SHA-256;
- run, arm, item, call index, function, prompt, and registry identity;
- requested model and model revision;
- input and output typed-port identity;
- strict output JSON Schema and schema SHA-256;
- maximum output-token budget and result-spool route.

The same ID with different intent or request bytes is a hard conflict. Delivery
ordinal is not an inference identity. Repeating a `PUT` to the spool may recover
the same committed bytes; it may not add a fourth model sample to an item-arm.

The final suite is admissible only when its durable audit contains exactly:

- 3 accepted calls for every item-arm;
- 500 accepted item-arm receipts for the sealed 100-item, 5-arm cohort;
- 1 suite receipt whose embedded transport audit matches those rows.

## Durable state machines

Client call states are append-audited and hash-chained:

```text
PREPARED -> SENT -> RAW_COMPLETE -> ENVELOPE_VALID -> SCHEMA_VALID -> ACCEPTED
               \-> DELIVERY_AMBIGUOUS -> SENT
               \-> AMBIGUOUS_ABORT
RAW_COMPLETE / ENVELOPE_VALID / SCHEMA_VALID -> REJECTED_PROTOCOL
```

Server spool states are:

```text
ABSENT -> DISPATCHING -> COMPLETE
                     \-> UNKNOWN
```

`UNKNOWN`, identity conflict, attestation mismatch, reconciliation exhaustion,
or ledger corruption aborts the cohort. No terminal state is reopened to obtain
a more convenient model answer.

Both SQLite stores use `journal_mode=WAL`, `synchronous=FULL`, explicit
transactions, and parent-directory `fsync` on initial creation. The client
persists `PREPARED` before delivery, raw response bytes before validation, and
the existing `CallReceiptV1` before returning it to the item network. Completed
item-arm bytes are persisted immediately after their third accepted call.

## Strict acceptance pipeline

The acceptance order is fixed:

```text
bounded HTTP body
-> complete framing when Content-Length is present
-> spool ID/request/response/revision attestations
-> HTTP 200
-> strict outer RFC 8259 JSON
-> exactly one OpenAI-compatible choice
-> finish_reason == "stop"
-> served model identity and nonnegative usage
-> strict inner RFC 8259 JSON
-> frozen output JSON Schema
-> Python typed-port validation
-> durable CallReceiptV1
```

Both JSON layers reject duplicate object names and non-finite constants. A
partial body, `finish_reason=length`, wrong schema, wrong model, wrong spool
attestation, or typed-port mismatch stores forensic evidence but creates zero
accepted scientific call receipts.

This ordering follows HTTP incomplete-message rules in
[RFC 9112](https://www.rfc-editor.org/rfc/rfc9112.html#section-6.3) and strict
JSON interoperability concerns in [RFC 8259](https://www.rfc-editor.org/info/rfc8259/).

## Retry and recovery rule

The legacy direct OpenAI-compatible port now permits zero automatic POST
retries. [RFC 9110 section 9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)
does not authorize automatic retry of a non-idempotent request after an
ambiguous send. OpenAI and vLLM request IDs are retained as tracing concepts,
not assumed to be durable replay guarantees.

The durable client therefore retries only the idempotent spool `PUT` carrying
the same ID and exact request bytes. The spool commits the first upstream HTTP
status, safe header subset, raw body, and body SHA-256 before responding. An
exact retry returns those bytes with `X-HSWM-Spool-Replayed`; a changed request
returns an identity conflict. This mirrors the key/request/result binding
principle documented by [Stripe's idempotency contract](https://docs.stripe.com/api/idempotent_requests),
but the HSWM spool implements and tests its own contract rather than assuming
vLLM provides it.

After a server restart, an unfinished `DISPATCHING` row becomes `UNKNOWN` and is
never redispatched automatically. After a client restart:

- `ACCEPTED` returns the stored typed response without network traffic;
- `RAW_COMPLETE`, `ENVELOPE_VALID`, or `SCHEMA_VALID` resumes offline validation;
- `SENT` or `DELIVERY_AMBIGUOUS` reconciles the same spool identity;
- `AMBIGUOUS_ABORT` remains terminal.

## Local fault evidence

The focused test battery proves the following against real HTTP and SQLite
process boundaries with a deterministic upstream fixture:

- disconnect after spool commit, followed by byte-identical replay with one
  upstream dispatch;
- process death after `DISPATCHING`, followed by `UNKNOWN` and no redispatch;
- outer and inner JSON truncation;
- duplicate inner key and non-admissible schema;
- `finish_reason=length`;
- crash after raw commit and offline resume;
- pending spool result followed by exact reconciliation;
- event-chain and item-run byte tamper detection;
- same ID with different intent refusal;
- bearer secret absence from both SQLite files;
- non-loopback plain-HTTP bind refusal;
- deterministic `1 item x 5 arms x 3 calls = 15/5/1` reconstruction and
  network-free second materialization.

Validation command:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  prom_search_hswm/test_f1_durable_transport.py \
  prom_search_hswm/test_prom9_experiment_harness.py
```

## Target deployment gate

Before any successor sealed F1 observation:

1. Put the spool SQLite file on local durable Linux storage, never NFS or an
   ExFAT/cold-data volume.
2. Run exactly one spool process on loopback and separate its client bearer
   token from the upstream model API key.
3. Reach it through local placement or an authenticated tunnel. The bundled
   server refuses a non-loopback plain-HTTP bind.
4. Pin the actual upstream model revision, server revision, spool code commit,
   typed output schemas, tokenizer, and runner commit in a successor
   preregistration. Structured-output generation changes the sampling contract,
   so the old sealed preregistration cannot be silently reused.
5. Repeat the post-inference/pre-client-commit disconnect falsifier against the
   deployed spool and actual upstream. Confirm one upstream dispatch and an
   identical replay body SHA-256.
6. Capture target-filesystem crash/power-loss evidence. SQLite documents why
   WAL with `synchronous=FULL` is the selected policy, but deployment durability
   still depends on filesystem and storage behavior:
   [WAL](https://www.sqlite.org/wal.html),
   [`synchronous`](https://www.sqlite.org/pragma.html#pragma_synchronous), and
   [atomic commit](https://www.sqlite.org/atomiccommit.html).
7. Only after the successor registration is exactly read back may the runner
   pursue `1500/1500`, `500/500`, and `1/1`, followed by an independent judge
   and LakatoTree exact readback.

## Claim boundary

Current disposition:

- local G0 implementation and deterministic fault battery: **PASS**;
- target DGX spool deployment, actual-upstream disconnect falsifier, and
  target-filesystem durability: **PENDING**;
- successor preregistration and exact readback: **PENDING**;
- G1 measurement and independent judgment: **BLOCKED**;
- programme scientific status: **UNJUDGED**.

No model was called and no scientific observation was created by this repair.
