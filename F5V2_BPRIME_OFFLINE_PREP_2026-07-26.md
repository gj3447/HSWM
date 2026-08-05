# F5v2 B-prime offline preparation receipt

> Status: **OFFLINE SUBSTRATE GREEN / PREREG DRAFT / NO MEASUREMENT AUTHORIZED**
>
> This is an engineering receipt, not a scientific result or a user-ratified
> machine lock.

## What landed

- `f5v2_operators.py`: exact five-field CPL1 numeric packet parser, immutable
  append receipt, order-independent canonical source-cut identity, and
  explicitly ephemeral R/QFR reassembly controls.
- `f5v2_topic_cache.py`: separate query-free content-addressed arms: durable B0
  stores only atomic packets, while B-prime produces deterministic slow-W and
  slow-H **candidates** with packet/provenance hashes and an exception ledger.
- `f5v2_judge.py`: deterministic provenance citation, adversarial canary, and
  DRM related-but-unstated lure gates.
- `f5v2_sealed_prep.py`: self-hashed write-once manifest/prep/smoke chain that
  revalidates the official ORDERED receipt, current harness/plan/code hashes,
  exact CPL1 packet, and every bound input before an **offline integrity seal**.
  Self-hash is explicitly not treated as user, harness, or measurement authority.
- Machine-readable design draft:
  `prom_search_hswm/evidence/PREREG_F5V2_BPRIME_DURABLE_CACHE_20260726.draft.json`.

## Verification

```text
tests/test_f5v2_*.py: 31 passed
tests/test_packaging_contract.py: 4 passed
git diff --check: PASS
```

Injected negatives cover unknown packet fields, query leakage, non-finite
numeric values, fabricated citation, content tamper, source-cut mismatch,
write-once replacement, missing ordered gates, missing CPL1 causal gates,
forged ORDERED/CPL1/manifest/prep/smoke receipts, judge canary failure, DRM
lure acceptance, durable-B0 derived-field injection, and reversed packet
iteration.

Two independent guards are active: the prereg is still a draft, and the ordered
receipt exposes F1 rather than P4. The recorded
`receipts/HSWM_F5V2_PREP_REFUSAL_20260726.json` stops at the first guard. The
ordered-status injected negative verifies the second. No development or sealed
manifest was created.

## Explicitly not implemented or claimed

- no SQLite compare-and-swap epoch activation or rollback receipt log;
- no real slow-H activation;
- no episode/outcome/topic-freeze envelope, contrastive novelty gate, or
  pre-query topic-partition receipt; the current weighted aggregate is only a
  candidate operator;
- no `f5v2_run.py`, live model call, measurement, or replay judge;
- no code path emits measurement authorization; even a structurally valid
  synthetic chain can produce only `OFFLINE_SEALED_NOT_AUTHORIZED` with
  `measurement_authorized=false`;
- no claim that a file-cache candidate is already durable HSWM learning;
- no user ratification, LakatoTree verdict, or KG canon write.

Those surfaces remain gated by the ordered chain
`F1 -> B22 Gate0 -> P1v5 -> P2 -> P3 -> P4`, a real CPL1 numeric packet and
provenance/removal receipt, and a fresh user-ratified machine lock.

## Legacy evidence integrity

The old F5 evidence was not edited:

```text
e7f3269952ec489331efdaccd7792d0bed089492e159d0260f16d8f986ad1e08  f5_consolidation.py
cb767d4cd72472331713a2b121157b96fe7f2a648bd84bbfe6ed2fcaa2ac2793  f5_replay_judge.py
3acec13a80e0701a371e5e6d58fed974f78e42223a1427e034c4ddb5c1619745  receipts/f5_consolidation_sealed_1784998952.json
```
