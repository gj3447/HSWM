# HSWM QKV structure experiment plan — 2026-07-20

Status: development-only protocol freeze. This is not a fresh confirmatory
preregistration. A small evaluator-only feasibility probe had already exposed
the eligible chain counts and exact symbolic completion before this document
was written. No B1-QKV development outcome had been computed at freeze time.

## Question

The narrow hypothesis does not depend on the HSWM target identity as an LLM-executed function network. It is that an
evidence-preserving memory can expose a Q/K/V-like operator:

```text
Q_t = current bound frontier plus the relation still being sought
K_e = an evidence-bound source frontier and relation address
V_e = an evidence-bound target frontier
Q_(t+1).frontier = V_e.target
```

The causal novelty over `typed_composition.py` is the last line. The current
typed comparator keeps one bag of query terms fixed across every hop. This
experiment asks whether a selected Value can create the next Query state and
whether that state change matters.

Passing this experiment cannot establish neural computation, raw-language
reasoning, answer generation, or general intelligence.

## Experiment A — QKV-R1 ordered routing teeth

The deterministic fixture is an order collision:

```text
A --alpha--> B --beta--> D
A --beta----> C --alpha-> E
```

The programs `(alpha, beta)` and `(beta, alpha)` have the same relation bag but
must terminate at different Values. Thirty-two content-addressed isomorphic
worlds yield 64 fully enumerated programs.

Required controls and gates:

- ordered K=2 reaches the exact terminal in 64/64 cases;
- matched K=1 reaches no K=2 terminal;
- a second-step key derangement and a second-step value derangement each kill
  all 64 completions while preserving every matched-K1 receipt root;
- an unseen relation and an ambiguous key refuse query-atomically;
- every refusal returns the supplied static payload byte-identically;
- every hop receipt proves `selected V target == next Q frontier`;
- reversing memory input order and repeating the run preserve the receipt root;
- an unordered bag control cannot distinguish both orders.

This arm may earn only the phrase **synthetic evidence-bound ordered key-value
routing mechanism**.

## Experiment B — B1-QKV development probe

This arm uses only the two existing development-v4 segments, never a fresh
segment or fresh evaluator result:

- MuSiQue development: 200 queries;
- 2WikiMultihopQA development: 200 queries;
- BGE-M3 vectors from the existing frozen local artifact;
- deterministic B1 exact-title links built from `(source_id, title, text)`.

Questions and gold IDs are joined only after the title graph and QKV scores are
built. MuSiQue decomposition and 2Wiki evidence triples never enter the scorer.

For unit-normalized paragraph vectors `K_i`, query state `q_t`, and outgoing
title-linked target vectors `V_i`:

```text
attention_t = softmax(top_seed_k(q_t dot K) / temperature)
read_t      = weighted mean of evidence-linked V vectors
q_(t+1)     = normalize(q_t + gamma * read_t)
score_t     = q_t dot K
```

Sources without an admitted B1 edge contribute no Value. The scorer is
query-atomic: a safety failure or no readable Value returns the original cosine
row. `gamma=0` must also be byte-identical to cosine.

Frozen policy grid (selected on the relation/evidence-disjoint development
validation half by mean nDCG@10, then ASR@10, then lower complexity):

```text
seed_k      in {3, 10}
temperature in {0.05, 0.10, 0.20}
gamma       in {0.10, 0.25, 0.50, 1.00}
hops        = 2
```

The held development test half reports matched QKV K1, QKV K2, cosine, and five
degree-preserving Value/topology shuffles with seeds `0..4`. Primary metrics are
nDCG@10 and all-support recall@10; support recall@10 is secondary. Inference is
clustered by the existing union of relation-template and exact-evidence
components.

The exploratory effect clears the mechanism gate only if, on both datasets:

- K2 minus matched K1 is at least `+0.02` nDCG@10 and `+0.03` ASR@10;
- K2 minus cosine clears the same margins;
- cluster bootstrap lower bounds are positive for both primary metrics;
- K2 beats every frozen shuffle on both primary metrics;
- apply coverage is at least 0.50.

Failure is informative: it means this immediately available title-value QKV
operator does not turn HSWM structure into measured real-data retrieval uplift.

## Explicit non-result boundaries

The available B3 extraction cache is too incomplete for a claim-level QKV
evaluation: no development query has all candidate paragraphs extracted.
Therefore no B3-QKV score is permitted in this run. The evaluator-only symbolic
chain ceiling may be reported separately, but it is label-leaky by construction
and is never HSWM efficacy evidence.

Fresh H3-B3 segments, manifests, labels, and efficacy gates remain untouched.
A positive development probe would justify a new sealed B3-QKV extraction/key
artifact and a separate prospective fresh experiment; it would not authorize
reusing the current H3-B3 fresh protocol.
