# F2-F5 sealed universe cohort

This directory declares a **21-universe** Tier-3 cohort. Sixteen `uni_s*`
universes are bundled in Git. Five larger R3 replay universes are intentionally
excluded because the ignored replay bundle is about 105 MB.

The complete membership and content hashes are locked in [`COHORT.v1.json`](COHORT.v1.json).
`f2_delta_w_credit.load_question_pool()` validates that contract before any
model or network call. A public clone therefore refuses the sealed run instead
of silently shrinking from 21 universes to 16.

## Hydration

Restore or reproduce `_research/r3_replay/` with
[`r3_dump_replay_artifacts.py`](../../r3_dump_replay_artifacts.py), then verify:

```bash
sha256sum _research/r3_replay/manifest.json
# expected: c814d85beacf5751bd4811e82648e37e4384705669687ddd8ef91f31518dd54e
```

After the replay bundle is present, create the local links:

```bash
for name in dense_t200_fk9 large_t200_fk3 mid_t20_fk3 small_t2_fk3 sparse_t200_fk1; do
  ln -s "../r3_replay/universes/$name" "_research/f2_sealed_universes/$name"
done
```

Those five links are explicitly ignored and must remain local. Historical
receipts retain their original paths; the tracked repository contains no
dangling placeholder links.
