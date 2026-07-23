# HSWM paper ↔ code absorption ledger (2026-07-23)

> Status: **SOURCE-LOCKED / NOT ACTIVATED**
>
> HSWM comparison baseline: `gj3447/HSWM@6328de66e5bb`
>
> Source locks: [published provenance inventory](_research/competitor_absorption/source_locks/README.md)
>
> Raw third-party bundle: retained locally; not vendored in this repository
>
> Machine-readable gate: [`_research/competitor_absorption/manifest.v1.json`](_research/competitor_absorption/manifest.v1.json)

## Decision

HSWM must absorb each prior system as a **paper–code pair**, not as a name or a
headline result.

- The **paper** fixes the proposed mechanism, claimed result, benchmark boundary,
  and ablation that should have carried the claim.
- The **pinned code revision** fixes the mechanism that is actually executable,
  missing paths, defaults, paper/code drift, and license boundary.
- The **HSWM gate** decides whether to reimplement a narrow contract, run it only
  as a falsifier, keep it as an evaluation control, or reject it.

Therefore, no external result below is an HSWM result, and no candidate is active
merely because its source is present locally. The deployed HSWM defaults remain:

- `Admit flat. Expand gated (optional). Govern late.`
- `TRAVERSAL_OFF. Fuse weight may be 0.`

## Locked corpus

- 11 clean shallow code clones in the local research bundle, each pinned to a
  full Git commit.
- 11 primary paper PDFs, SHA-256 pinned; all parse, extract non-empty text, and
  had their first page rendered and visually checked.
- 12 explicit paper–code bindings: HippoRAG has two lineage papers, while the Zep
  paper maps separately to the Graphiti core and the Zep facade repository.
- No model, dataset, service, or dependency was installed. Third-party clones,
  PDFs, and extracted text are not committed here.

The exact Git commits are in
[`repos.lock.tsv`](_research/competitor_absorption/source_locks/repos.lock.tsv); paper identifiers,
URLs, hashes, pages, PDFs, and extracted text are in
[`papers.lock.tsv`](_research/competitor_absorption/source_locks/papers.lock.tsv).

## What each pair actually offers HSWM

| Pair | Paper contract | Executable-code reality and drift | HSWM disposition |
|---|---|---|---|
| [HyperGraphRAG](https://proceedings.neurips.cc/paper_files/paper/2025/file/df55ee6e59f8ac4a625219e11fe9ddba-Paper-Conference.pdf) ↔ [`d587cdf`](https://github.com/LHRLAB/HyperGraphRAG/tree/d587cdf8c3fe2be7719557f845324cb3a321f5e2) | Preserve one n-ary fact as a hyperedge; retrieve entity and relation lanes, then expand incidence. | Hyperedges are reified nodes joined by binary incidence edges. The dense chunk store is populated but not used by public query; alternate query modes and delete schema have broken paths. | **Experiment only:** typed `V` and `E` lanes plus certified one-hop incidence expansion. Keep flat arm and shuffled-incidence control. |
| [HGRAG](https://ojs.aaai.org/index.php/AAAI/article/download/40623/44584) ↔ [`dfff451`](https://github.com/MF-AIR/HGRAG/tree/dfff451d6cbf72babae28b530179d21de72b8eb9) | Entity-node / passage-hyperedge normalized diffusion with a dense residual and structural enhancement. | Default public script uses multihot seeds and parameters far from the paper table; no paper-run manifest or license file. | **Clean-room falsifier only:** normalized `V→E→V` branch behind `mu=0`. It may challenge, not silently overturn, `TRAVERSAL_OFF`. |
| [SiReRAG](https://openreview.net/forum?id=yp95goUAT1) ↔ [`70c9434`](https://github.com/SalesforceAIResearch/SiReRAG/tree/70c9434776ca0eaac17590285285c26313817365) | Similarity tree plus shared-entity relatedness tree. | It is two recursive summary trees flattened into one cosine pool, not a persistent horizontal-edge graph. Training pipeline is absent; persist/traversal paths drift; code is CC BY-NC 4.0. | **Clean-room experiment:** two provenance-preserving mounts with a typed union; never copy the code into HSWM. |
| [HippoRAG 1](https://arxiv.org/abs/2405.14831) + [HippoRAG 2](https://proceedings.mlr.press/v267/gutierrez25a.html) ↔ [`1e8f609`](https://github.com/OSU-NLP-Group/HippoRAG/tree/1e8f60981bf760b64003aa5bf5668126d0c106b3) | OpenIE memory, recognition filtering, phrase/passage seeding, and associative PPR retrieval. | Current `main` primarily implements v2 plus later platform work. The graph is pairwise; predicates are embedded but do not survive into topology or PPR seeds. | **Experiment only:** typed fact-member and evidence-unit seed compiler; preserve HSWM n-ary predicates and keep PPR gated/off by default. |
| [Zep temporal KG paper](https://arxiv.org/abs/2501.13956) ↔ Graphiti [`4674e1e`](https://github.com/getzep/graphiti/tree/4674e1ed834810f5d90e1abd627cff493b25f0ae) | Episode, semantic fact, and community tiers with event-valid and ingestion time; history-preserving invalidation. | `EntityEdge` retains episode IDs and temporal fields; current OSS is broader than the evaluated hosted service. Contradiction and timestamps remain partly LLM-derived. | **Absorb contract P0:** `valid_at`, `invalid_at`, `observed_at`, and source episode IDs on A3 events. Reimplement against HSWM evidence hashes. |
| Same Zep paper ↔ Zep [`0375d7b`](https://github.com/getzep/zep/tree/0375d7be4a72cda6a43ecdc6fd9055846eb0fd0e) | Product-level agent memory and benchmark claims. | This repository explicitly contains integrations, examples, and benchmark clients, not the product engine evaluated in the paper. | **Facade/control only:** SDK port shape and benchmark receipt schema. Do not attribute hosted-service results to this clone. |
| [T-GRAG](https://arxiv.org/abs/2508.01680) ↔ [`8c6d4ea`](https://github.com/Arvin0313/T-GRAG/tree/8c6d4ea19e4e4fafb4504f691cb7f3873c0ac595) | Temporal query decomposition and node → temporal subgraph → evidence retrieval. | Public dispatch references undefined multi-time functions, routes several modes through the single-time path, and contains a node/edge state mix-up. It slices snapshots rather than keeping a bi-temporal ledger. No license file. | **Concept only:** deterministic revision/time-sliced candidate view, clean-room. Do not reuse code or treat its multi-time path as reproduced. |
| [GFM-RAG](https://proceedings.neurips.cc/paper_files/paper/2025/file/33ca0b1102b54c191a9a45a05adafaf4-Paper-Conference.pdf) ↔ [`57e3e28`](https://github.com/RManLuo/gfm-rag/tree/57e3e28045fffff5411e2454a4323fbe4dff9b91) | Query-conditioned learned graph scorer pretrained across many KGs. | Repository now mixes the paper model with later G-reasoner work. Paper-scale training is an 8×A100-80GB class workload and is not online memory learning. | **Dell-only residual experiment:** compare a small scorer with flat cosine and current B2 scorer. Never make deep GNN the default. |
| [AriGraph](https://arxiv.org/abs/2407.04363) ↔ [`e884b76`](https://github.com/AIRI-Institute/AriGraph/tree/e884b76d7fa5185a3a8a55e5a67393b5a43f5ef2) | Semantic plus episodic memory used inside environment planning. | Main pipeline runs a triplet `ContrieverGraph`; the n-ary `Hypergraph` class is orphaned. Outdated facts are destructively deleted. | **Absorb evaluator P1:** closed-loop `(observation, facts, invalidations, memory, plan, action, reward)` receipt. Reject destructive history deletion. |
| [TierMem](https://arxiv.org/abs/2602.17913) ↔ [`5ceda34`](https://github.com/FreedomIntelligence/Tiermem/tree/5ceda3465c08e234c00549ac43abf7eb539323f9) | Summary-first memory with raw-evidence escalation and provenance-linked write-back. | Summary hits carry raw-log IDs, but the store is not cryptographically immutable; router variants differ and verified write-back is off by default. | **Absorb contract P0:** source-linked summary/raw sufficiency router with fail-closed broken-pointer behavior. Audit vendored notices before any code reuse. |
| [ProveRAG](https://doi.org/10.1109/ACCESS.2025.3638251) ↔ [`18fe54b`](https://github.com/RezzFayyazi/ProveRAG/tree/18fe54ba20ff9564c2f2a47a2af86ec61eb8f14b) | Claim evaluation as TP/FP/FN with rationale and evidence spans. | Provenance is reconstructed post hoc from mutable web pages and usually judged by the same model; generation-time source identity is lost. | **Absorb schema P1:** independent evaluation receipt with frozen-source byte spans. Reject similarity or same-model critique as proof. |

## Non-equivalences that must remain explicit

1. **HyperGraphRAG ≠ HGRAG.** The former stores n-ary facts; the latter treats a
   passage as a hyperedge and diffuses across its entity incidence.
2. **Graphiti ≠ T-GRAG.** Graphiti keeps bi-temporal fact history; T-GRAG
   builds a time-filtered query view.
3. **TierMem ≠ ProveRAG.** TierMem allocates summary versus raw evidence;
   ProveRAG emits a post-generation evaluation packet.
4. **SiReRAG relatedness ≠ a horizontal semantic graph.** It is a second
   recursive tree that is flattened into a shared retrieval pool.
5. **HippoRAG continual learning ≠ learned weights.** It is non-parametric
   insertion; GFM-RAG is the learned graph scorer.

## Admission order

### Gate 0 — preserve the active HSWM programme

Complete the already mandated B2.2 neutral exact replay and full-candidate
score-component pack before fitting a new learner or interpreting competitor
mechanisms as progress. This ledger does not supersede that gate.

### P0 — contracts that do not change ranking by default

1. Graphiti-derived temporal fact fields on the A3 supersession event.
2. TierMem-derived source-linked summary/raw escalation interface.
3. Both ship initially as pure schemas and fail-closed unit tests, with no
   retrieval-uplift claim.

### P1 — independent evidence and environment receipts

1. ProveRAG-derived TP/FP/FN packet, repaired with a frozen source hash, byte
   span, and independent evaluator identity.
2. AriGraph-derived closed-loop world-memory receipt, retaining invalidated
   history rather than deleting it.

### P2 — equal-compute structural experiments

1. HGRAG normalized incidence diffusion.
2. HyperGraphRAG dual entity/relation retrieval.
3. SiReRAG dual evidence-preserving mounts.
4. HippoRAG typed seed compiler and optional PPR.

Every P2 arm must retain flat-only, structure-shuffled, and simple-factual
no-harm controls. Failure leaves `TRAVERSAL_OFF` and fuse weight `0` unchanged.

### P3 — expensive or reference-only work

- GFM-RAG: small residual scorer first; paper-scale training only by explicit
  remote-compute experiment.
- T-GRAG: idea-level clean-room time-slice control only.
- Zep: facade and benchmark client only.

## Falsifiers that decide absorption

| Candidate | Required falsifier |
|---|---|
| Graphiti temporal record | Temporal-QA CI lower bound must be positive versus current late filter, with non-temporal retention loss ≤1 percentage point. |
| TierMem router | Versus raw-only, accuracy loss ≤2.2 points while reducing tokens/latency; a broken `raw_log_id` must refuse; learned router must beat a random router at the same escalation rate. |
| HGRAG diffusion | Real incidence must beat degree-preserving shuffled incidence and must not harm the simple-factual set. |
| HyperGraphRAG dual lane | On arity≥3 items, `V∪E` must beat both `E`-only and shuffled incidence under matched candidates/tokens. |
| SiReRAG dual mount | Union must beat the best single tree, while shuffled entity membership must lose, under equal summary calls/nodes/tokens. |
| Hippo typed PPR | Associative gain must survive predicate-preserving n-ary topology and disappear under shuffled membership; simple factual recall must not fall. |
| GFM residual | Gain must survive unseen held-out graphs and disappear under edge permutation; otherwise it is not structural learning. |
| AriGraph receipt | Under fixed decision model/tokens, action reward must improve over full-history/flat controls and collapse when action–outcome links are shuffled. |
| ProveRAG receipt | Injected unsupported and omitted claims must both be caught; cited spans must byte-match the frozen source; shuffled response/context must collapse the score. |

## First safe absorption wedge delivered here

The first implemented wedge is the **source-binding admission gate**, not a
competitor algorithm:

- [`manifest.v1.json`](_research/competitor_absorption/manifest.v1.json) binds
  every candidate to paper keys, code clones, exact executable reference sites,
  license handling, HSWM surface, default-off disposition, and falsifier.
- [`verify_sources.py`](_research/competitor_absorption/verify_sources.py)
  checks the paper hashes/text, Git HEADs/cleanliness, code anchors, complete
  paper/repository coverage, restricted-license clean-room policy, and that no
  candidate is marked active.

This converts the source dump into a reproducible intake boundary while leaving
HSWM scientific and deployment claims unchanged. No KG record was written.
