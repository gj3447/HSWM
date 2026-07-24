# OOPTDD Critique — Structural Weaknesses and v2 Mitigations (2026-07-23)

> External review feedback on the `ooptdd` measurement methodology as documented
> in `README.md` §Methodology and instantiated in `receipts/receipt_cosine_floor.py`.
> This document is itself a *claim ledger entry*: each problem below is stated
> falsifiably, with a concrete v2 mitigation. None of this disputes the value of
> the 5-gate receipt (pre-run locked trace, real execution, positive readback,
> source binding, negative oracle); the critique is about what the gates
> **cannot** see.

## P1 — Self-certification: no independent auditor gate

The receipt author is the same agent making the claim. The author writes the
LOCK prose, chooses the negative oracle, and sets the thresholds. A weak LOCK
or a trivially-breakable oracle yields a VALID receipt with zero information —
the same "form passes, substance absent" failure mode OMD had on the merge side.

**Falsifiable test:** hand a receipt to a reviewer who has not seen the claim;
if the reviewer cannot determine, from the receipt alone, what would make the
claim *false*, the receipt is ceremony.

**v2 mitigation:** add an **adversarial-review gate**. A receipt becomes
`audited` only after a second, context-independent agent (or human) attempts to
break the LOCK and records either a counterexample or a signed "no break found
within budget N" attestation. Status enum: `draft → self-valid → audited`.

## P2 — Negative oracle proves sensitivity, not correctness

The negative oracle shows the test *can* fail (non-vacuous). It does not show
the test checks the *right* invariant. A test can be mutation-sensitive and
still measure the wrong quantity. "The oracle choice is correct" is itself an
unreceipted claim — infinite regress.

**v2 mitigation:** (a) auto-generate mutants (mutmut/cosmic-ray-style) instead
of one hand-picked oracle; report **mutation score** (killed/total) in the
receipt header. (b) For each receipt, require one **domain counterexample** from
the problem space, not only a code mutant — e.g. for the cosine floor, an
adversarial embedding configuration, not just "ReLU removed".

## P3 — LOCK is unverified prose

`LOCK = {"F1_pointwise": "W = cosine + lam*ReLU(r) >= cosine ..."}` is a string.
Nothing machine-checks that the executable assertions semantically match the
lock text. Strong wording + weak code passes silently.

**v2 mitigation:** make locks **executable predicates**. The lock *is* the
assertion (property-based style, e.g. Hypothesis strategies), and the prose is
generated from the predicate, not the reverse. Where prose must lead, require a
machine-checkable anchor (symbol, equation id, schema ref) per lock entry.

## P4 — No receipt integrity chain

Source binding pins the *examined* files by sha, but the receipt itself is a
plain editable `.py`. Nothing prevents post-hoc receipt edits that keep CI
green; there is no timestamping, no hash chain, no content-addressed receipt
store. (LakatoTree already has VerdictReceipt chains — ooptdd receipts have no
equivalent.)

**v2 mitigation:** content-address receipts: on each VALID run, emit
`receipt_result.json` containing `{receipt_sha, source_shas, lock_sha,
verdict, timestamp}` and append to an append-only, hash-chained receipt log.
`verify_efficacy_claims.py` should refuse receipts whose chain link is missing
or whose result json is absent/stale.

## P5 — Claim atomization vs system-level truth

Receipts cover narrow claims one at a time. 100 VALID receipts do not imply the
integrated system works; composition behavior is unreceipted. Today `receipts/`
holds exactly one receipt while README carries several larger efficacy claims
(e.g. the 300-row ladder win) that are *not* in receipt form. Covering
system-level claims combinatorially explodes receipt count → maintenance cost
approaches the OMD overhead ooptdd was meant to replace.

**v2 mitigation:** (a) tier the ledger: every README ✅ claim must link at least
one receipt id, else it is downgraded to ⚠️ automatically by
`verify_efficacy_claims.py`. (b) Add **composition receipts** that run the
integrated path end-to-end on a small fixed fixture, rather than one receipt
per micro-claim.

## P6 — The strongest claims live outside the gate

Only deterministic NumPy-only claims are receiptable. Tier-3 claims (LLM
judgments, GPU runs, real benchmarks) — precisely the *strongest* claims — are
covered by "attested workflow", which is a gesture, not a mechanism. Falsifi-
ability applies only where falsification is cheap.

**v2 mitigation:** define a **Tier-3 attestation receipt**: environment capture
(pip lock, GPU id, endpoint fingerprint), prompt/judgment hashes, and a
replay-window ("re-run within N days or the claim auto-decays to ⚠️"). Claims
without a live attestation decay on a schedule, enforced by the verifier.

## P7 — Manual re-invention of existing automation

The positive/negative-oracle pair is hand-written property-based testing plus
hand-written mutation testing. Hypothesis + mutmut automate both. OOPTDD's real
novelty is the *honesty culture* (non-claims in the LOCK, rejected results in
the ledger) — which is social and cannot be tool-enforced; the mechanical parts
should be delegated to existing tooling.

**v2 mitigation:** keep the LOCK/ledger culture, but generate the mechanical
gates: property-based strategies for invariants, mutation runs for oracles.
Receipts then record *coverage and mutation scores*, shrinking hand-written
oracle code to domain counterexamples only.

---

## Summary

| # | weakness | root cause | v2 gate |
|---|---|---|---|
| P1 | self-certification | author == auditor | adversarial-review status (`audited`) |
| P2 | oracle ≠ correctness | hand-picked single mutant | mutation score + domain counterexample |
| P3 | LOCK is prose | no machine binding | executable predicates / anchored locks |
| P4 | receipt mutable | no chain | content-addressed hash-chained receipt log |
| P5 | atomization | per-claim scope | claim→receipt link enforcement + composition receipts |
| P6 | strong claims outside | determinism requirement | Tier-3 attestation + auto-decay |
| P7 | manual mechanics | no automation | Hypothesis/mutmut integration |

The open question under all of these: **who audits the auditor** — v2 should
treat audit depth as an explicit budget parameter, not a binary.

---

## Appendix A — LakatoTree feedback payload (pending server)

LakatoTree server was unreachable at authoring time (`list_trees` → connection
refused, 2026-07-23 17:51 KST). When the server is back, register this critique
with the following calls (tree name: the active HSWM tree; tag: the node
carrying the ooptdd methodology claim — substitute actual values):

```
critique(name=<hswm-tree>, tag=<ooptdd-methodology-node>, arg_id="ooptdd-critique-2026-07-23-P1",
         attacks="<ooptdd-methodology-node>", kind="rebuttal", by="external-review",
         body="P1 self-certification: no independent auditor gate; see OOPTDD_CRITIQUE_2026-07-23.md")
# ... repeat for P2..P7, one arg per problem ...

open_question(name=<hswm-tree>, qname="ooptdd-v2-auditor-budget",
              body="Who audits ooptdd receipts, and at what budget? v2 proposal: adversarial-review
                    gate + mutation score + hash-chained receipt log + Tier-3 attestation decay.")
```
