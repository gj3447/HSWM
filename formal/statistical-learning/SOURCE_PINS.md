# Statistical-learning proof dependency pins

- Lean: [`leanprover/lean4:v4.32.1`](https://github.com/leanprover/lean4/tree/v4.32.1)
  from `lean-toolchain`; its source is distributed under
  [Apache-2.0](https://github.com/leanprover/lean4/blob/v4.32.1/LICENSE).
- Mathlib: [`leanprover-community/mathlib4` at
  `520045ab14e26149ee970e2e617ca04b09bde5d6`](https://github.com/leanprover-community/mathlib4/tree/520045ab14e26149ee970e2e617ca04b09bde5d6),
  resolved from input tag `v4.32.1` by `lake-manifest.json`. License:
  [Apache-2.0](https://github.com/leanprover-community/mathlib4/blob/520045ab14e26149ee970e2e617ca04b09bde5d6/LICENSE).
- Imported result: `Mathlib/Probability/Moments/SubGaussian.lean`, namely
  `HasSubgaussianMGF.measure_sum_range_ge_le_of_iIndepFun` and
  `hasSubgaussianMGF_of_mem_Icc_of_integral_eq_zero`.

The manifest records every transitive revision. The runner checks each local
checkout HEAD against these manifest commits; these compiled imports remain a
transitive trust boundary rather than a re-audit of all dependency source.

| Package | Locked source | License |
| --- | --- | --- |
| plausible | [`e12c1910fe855cbfc38803cd4e55543906d5fa62`](https://github.com/leanprover-community/plausible/tree/e12c1910fe855cbfc38803cd4e55543906d5fa62) | [Apache-2.0](https://github.com/leanprover-community/plausible/blob/e12c1910fe855cbfc38803cd4e55543906d5fa62/LICENSE) |
| LeanSearchClient | [`c5d5b8fe6e5158def25cd28eb94e4141ad97c843`](https://github.com/leanprover-community/LeanSearchClient/tree/c5d5b8fe6e5158def25cd28eb94e4141ad97c843) | [Apache-2.0](https://github.com/leanprover-community/LeanSearchClient/blob/c5d5b8fe6e5158def25cd28eb94e4141ad97c843/LICENSE) |
| importGraph | [`7e9612bf0b9ee66db3cb5b9988a35afc706f5a12`](https://github.com/leanprover-community/import-graph/tree/7e9612bf0b9ee66db3cb5b9988a35afc706f5a12) | [Apache-2.0](https://github.com/leanprover-community/import-graph/blob/7e9612bf0b9ee66db3cb5b9988a35afc706f5a12/LICENSE) |
| proofwidgets | [`6e311e2a844da9b2cc3971187df2fe0066947b93`](https://github.com/leanprover-community/ProofWidgets4/tree/6e311e2a844da9b2cc3971187df2fe0066947b93) | [Apache-2.0](https://github.com/leanprover-community/ProofWidgets4/blob/6e311e2a844da9b2cc3971187df2fe0066947b93/LICENSE) |
| aesop | [`a7dbf0c63b694e47f425f3dcddbc0e178bb432d3`](https://github.com/leanprover-community/aesop/tree/a7dbf0c63b694e47f425f3dcddbc0e178bb432d3) | [Apache-2.0](https://github.com/leanprover-community/aesop/blob/a7dbf0c63b694e47f425f3dcddbc0e178bb432d3/LICENSE) |
| Qq | [`38d591e778f100aec9762bb582f9c7f55f50e9dc`](https://github.com/leanprover-community/quote4/tree/38d591e778f100aec9762bb582f9c7f55f50e9dc) | [Apache-2.0](https://github.com/leanprover-community/quote4/blob/38d591e778f100aec9762bb582f9c7f55f50e9dc/LICENSE) |
| batteries | [`023ce7d62a0531e22a5331e20b587817a80d49ff`](https://github.com/leanprover-community/batteries/tree/023ce7d62a0531e22a5331e20b587817a80d49ff) | [Apache-2.0](https://github.com/leanprover-community/batteries/blob/023ce7d62a0531e22a5331e20b587817a80d49ff/LICENSE) |
| Cli | [`88679d088c9720c27ebdf2ba4dafe17341747f94`](https://github.com/leanprover/lean4-cli/tree/88679d088c9720c27ebdf2ba4dafe17341747f94) | [MIT](https://github.com/leanprover/lean4-cli/blob/88679d088c9720c27ebdf2ba4dafe17341747f94/LICENSE) |

The adjacent `HSWMLegacy`
library is a read-only source-directory bridge to the parent `formal/`
Std-only files; it adds no package dependency and does not change their bytes.
