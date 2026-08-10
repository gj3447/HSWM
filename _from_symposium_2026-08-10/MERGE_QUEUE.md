# SYMPOSIUM/HSWM 병합 대기열 — 2026-08-10

`SYMPOSIUM/HSWM` 전량을 이 저장소로 이관했다 (사용자 결정 2026-08-10: 저장소 메모리 효율,
SYMPOSIUM 한 곳에 다 때려박지 않는다).

아래는 **양쪽에 고유한 줄이 있어** 기계적으로 한쪽을 고를 수 없던 파일이다. 버리지 않고 여기 둔다.
이 저장소의 같은 이름 파일이 정본이고, 아래는 SYMPOSIUM 판본이다.

| 정본 (이 저장소) | SYMPOSIUM 판본 | SYM 고유줄 | HSWM 고유줄 |
|---|---|---|---|
| `AMENDMENT_OPEN_HSWM_KERNEL_V2_2026-07-22.md` | `_from_symposium_2026-08-10/AMENDMENT_OPEN_HSWM_KERNEL_V2_2026-07-22.md` | 3 | 3 |
| `INDEX.md` | `_from_symposium_2026-08-10/INDEX.md` | 111 | 206 |
| `PAPER_CODE_ABSORPTION_LEDGER_2026-07-23.md` | `_from_symposium_2026-08-10/PAPER_CODE_ABSORPTION_LEDGER_2026-07-23.md` | 20 | 27 |
| `PROM_P5_MULTIVIEW_HARDHOP_2026-07-22.md` | `_from_symposium_2026-08-10/PROM_P5_MULTIVIEW_HARDHOP_2026-07-22.md` | 1 | 1 |
| `R1_T1_RETRY_RESULTS_2026-07-22.md` | `_from_symposium_2026-08-10/R1_T1_RETRY_RESULTS_2026-07-22.md` | 19 | 19 |
| `SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md` | `_from_symposium_2026-08-10/SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md` | 9 | 8 |
| `SPEC_SHARED_HYPERGRAPH_NN_SEMANTIC_WEIGHT_2026-07-22.md` | `_from_symposium_2026-08-10/SPEC_SHARED_HYPERGRAPH_NN_SEMANTIC_WEIGHT_2026-07-22.md` | 19 | 19 |
| `_research/competitor_absorption/manifest.v1.json` | `_from_symposium_2026-08-10/_research/competitor_absorption/manifest.v1.json` | 4 | 4 |
| `_research/competitor_absorption/test_verify_sources.py` | `_from_symposium_2026-08-10/_research/competitor_absorption/test_verify_sources.py` | 9 | 49 |
| `_research/competitor_absorption/verify_sources.py` | `_from_symposium_2026-08-10/_research/competitor_absorption/verify_sources.py` | 106 | 444 |
| `prom_search_hswm/INDEX.md` | `_from_symposium_2026-08-10/prom_search_hswm/INDEX.md` | 1 | 2 |

병합이 끝나면 표에서 지우고 대기열 파일을 삭제한다. 표가 비면 이 디렉터리째 지운다.

## `.gitignore` 정책 때문에 자연 경로에 못 놓은 파일

`prom_search_hswm/data/` 는 이 저장소에서 **의도적 allowlist** 다
(`prom_search_hswm/data/*` 를 무시하고 `README.md` 와 `gold_badiou24.json` 만 예외).
SYMPOSIUM 은 아래 3개를 추적하고 있었다. 정책을 몰래 우회하지 않기 위해 자연 경로가 아니라
여기에 둔다. **allowlist 를 넓힐지 계속 제외할지는 소유자 판단이다.**

| 파일 | 크기 |
|---|---|
| `_from_symposium_2026-08-10/prom_search_hswm/data_files_gitignored/binding_gold_p1.json` | 425 KB |
| `_from_symposium_2026-08-10/prom_search_hswm/data_files_gitignored/real_gold_gfs.json` | 4.4 KB |
| `_from_symposium_2026-08-10/prom_search_hswm/data_files_gitignored/sources_realfields.json` | 6.3 KB |

원래 경로는 `prom_search_hswm/data/` 였다. `.gitignore` 의 `data/` 규칙이 **모든 depth 의**
`data` 디렉터리를 잡아서 대기열 안에서도 무시되므로 디렉터리명을 바꿔 보관한다.
