# T5 first pass — traversal certification on real data (2026-07-19)

> Runner: `traversal_cert.py real` · worlds: `world_builder.py` (T4.5) · field: **0-LLM**
> (cosine-only, λ_j=0, b≡1; bge-m3 1024d via dgx ollama; judgment/supersession arms = T4 scope).
> n=200 rows per dataset, hop-stratified; val/test 50/50; certification = SELECT_Z_ADJ=2.5 paired.

## Verdict — both datasets: **TRAVERSAL_OFF (certified floor)**

| | musique | 2wiki |
|---|---|---|
| world (선행 보고) | 2094 edges / 3892 nodes / density 0.0013 / hubs=american·united states·france / hops 67·67·66 (2·3·4) | 1505 / 3045 / 0.0018 / hubs=american·french·british / hops 100·100 (2·4) |
| μ curve (val nDCG@10) | 0→**0.585**, 0.1→0.551, 0.2→0.502, 0.4→0.486, 0.8→0.487 | 0→**0.717**, 0.1→0.691, 0.2→0.641, 0.4→0.633, 0.8→0.633 |
| certification | μ=0 (traversal refused) | μ=0 (traversal refused) |
| probe(μ=0.4) Δ by hop | 2: −0.086 / 3: −0.099 / 4: −0.012 | 2: −0.061 / 4: −0.044 |
| trip rate (probe arm) | 88% abstain (entropy .31 / n_eff .38 / kept_mass .19) | 93% abstain (entropy .68 / n_eff .25) |
| deployed damage | **0** (μ=0 ⇒ bit-identical pointwise) | **0** |

**Reading**: on the sparse entity-cooccurrence worlds this pipeline was built to test
(the one regime where traversal had a literature edge), cosine-seeded damped-restart
traversal over a cosine-only field **monotonically hurts** as μ grows, on both
datasets, in every hop stratum. Combined with add1584 (dense para-para graph, 9
configs all worse), this is now **two independent substrate families agreeing**:
the multi-hop advantage of HSWM lives in the STATIC trained field, not in
query-time propagation. The certification machinery did exactly its job — the
deployed readout stays bit-identical to pointwise and ships zero damage.

Weak directional note (exploratory only): the 4-hop stratum is the least negative
on both datasets (−0.012 / −0.044) — consistent with the down-payment direction
(hop-monotone static-field gains) but nowhere near sign-flip.

## The artifact chain this run survived (선행보고·teeth가 잡은 것들)

1. bge-m3 NaN embeddings on plain inputs (ollama 500) → retry + perturbation +
   counted hash fallback (0 fallbacks in final runs).
2. Fake mega-hubs from sentence-initial capitals ('the' deg=1130, 'she',
   'september') → mention blocklist; hubs became real entities.
3. Head-truncation destroyed musique's hop mix (200 rows all 2-hop) →
   hop-stratified round-robin sampling.
4. n_eff trip-wire distorted by k=M full-score reconstruction (50% spurious
   abstain) → NEFF_TOPK=10 fixed per spec §3 semantics.
5. 2wiki hop labels pulled hex noise from ids (hop '87154') → '<N>hop' pattern +
   type-string mapping + #supporting fallback.

## Honest scope & what would change the verdict (T4+)

- **0-LLM field**: λ_j=0 (no judgment baked in) and b≡1 (supersession conductance
  never fires). The traversal spec's two distinguishing levers were NOT exercised.
  A judgment-baked field could re-rank the frontier the walk actually needs; the
  b^κ arm is the stale-poisoning falsifier's job (H-T3).
- Trip-wires dominate (88/93%) — prereg constants, reported not tuned. If the T4
  field changes seed concentration, the trip profile must be re-reported.
- Single seed split (42), n=100 test/dataset — certification is per-corpus as
  spec'd, but H-T1's full power gate (required_n) not yet applied to a positive
  claim (none was made: verdict is a refusal, which needs no power).
- Embedder = bge-m3 real (strawman guard satisfied); entity extraction remains a
  capitalization heuristic (NER/coref would change bridge coverage — logged via
  mention_misses).

## Files

`cert_musique_result.json` / `cert_2wiki_result.json` (full numbers incl. trip
rates, stats, fallback lists). Reproduce: `traversal_cert.py real --dataset {musique,2wiki}`
with `OLLAMA_URL` pointing at a bge-m3 server.
