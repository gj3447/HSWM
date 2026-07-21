# 두 종류의 "깊이" — Solid Scaffold 정전 (USER_PRIMARY 2026-07-21)

> `verdict-user-hswm-two-kinds-of-depth-solid-scaffold-2026-07-21`
> LakatoTree: `LakatosTree_PromSearchHSWM_20260721` / node `ML18-solid-scaffold-depth`

## 1. 경위

PROM 2축 병렬 선행연구 조사(하이퍼그래프RAG novelty + deep-HGNN over-smoothing) 결과, 에이전트가
**"딥스택 = over-smoothing 함정 = 막다른 길"**로 판정했다. USER가 이를 정정:

> "사용하면서 학습 되기도 하고 딥스택으로도 쌓을 수 있는 거지. 나중에 어려운 문제는 딥스택이 될 거야.
> 그 왜 여러 층을 쓰냐면 **solid 해야 방향 수정이 쉽지.** 구조와 방향수정이 쉽도록 solid 하게 만드는 거야.
> 너무 하나만 딱 있으면 그 데이터 구조를 **붙이기도 어렵고 다른 데 이식하기도 어렵잖아.**"

## 2. 에이전트 오류 = "깊이" 두 종류 혼동

| 종류 | 정의 | over-smooth? | 출처 |
|---|---|---|---|
| **전파(propagation) 깊이** | 이웃 평균을 K번 반복 (신호가 K홉 확산) | **✅ 붕괴** | HGNN 8층 5% (arXiv:2203.17159), Oversmoothing Fallacy (arXiv:2506.04653) |
| **구조(structural) 깊이** | 층 = 발판(scaffold)·추상레벨·모듈 경계 | **❌ 무관** | 소프트웨어 계층화, ResNet/GCNII, RAPTOR 계층 |

문헌이 "깊으면 붕괴"라 한 건 **전파 깊이**(계속 평균 내니 다 뭉개짐). USER가 말한 층은 **구조 깊이**
— "solid 해서 방향수정·붙이기·이식이 쉽도록." over-smoothing은 후자에 **적용되지 않는다.**

## 3. 놀라운 수렴 — USER 직관 = 문헌의 over-smoothing 해법 그 자체

깊은 하이퍼그래프를 실제로 되게 만든 유일한 해법(**Deep-HGCN, GCNII** — arXiv:2203.17159 / 2007.02133)의
메커니즘 = **initial residual + identity mapping**. 이것을 말로 풀면:

> **원본을 solid 하게 유지(identity/teleport)** + **각 층은 작은 방향수정(Δ)만 얹는다.**

이것이 정확히 USER의 "solid 해야 방향 수정이 쉽다"이다. 발판(원본 항등)을 단단히 잡아두니
층을 쌓아도 안 무너지고(over-smooth 회피), 각 층은 steerable 한 보정만 한다.
**엔지니어링 직관 = over-smoothing을 푸는 메커니즘.** 우연이 아니라 같은 원리.

가중치 없는(weight-free) 검색 세팅에서 이 "solid" 메커니즘의 대응물 = **APPNP teleport(α로 초기 seed 복귀)**.
teleport = initial residual = "발판을 solid 하게 유지."

## 4. Novelty 재판정 갱신

| 조합 | 상태 | 근거 |
|---|---|---|
| 전파-깊이 딥스택 (검색) | **막다른 길** | over-smooth (문헌 + 우리 ML11) |
| learning-while-using (검색 메모리) | **이미 있음** | HippoRAG 2 non-parametric continual (arXiv:2502.14802) |
| n-ary 하이퍼그래프 RAG | **이미 있음(얕음)** | HyperGraphRAG NeurIPS 2025 (arXiv:2503.21322), 의도적으로 얕음 |
| **구조-깊이: solid·모듈·이식가능 다층 하이퍼그래프 메모리 (검색)** | **아무도 안 함** | RAG/하이퍼그래프 문헌 전부 flat 단층 인덱스 |

→ 에이전트가 "깊이는 빼라"고 한 건 **반만 맞음**. USER가 말한 종류의 깊이(구조/solid)는 오히려 **더 novel**.

## 5. HSWM 정전 매핑

- **하네스 = 場/scaffold(3계층)** = solid 다층 발판. 어려운 문제를 그 위에 조립.
- **롱기누스 = 층-간 바인딩 엣지** = "붙이기(attach)" + 층 연결.
- **오캄 = supersession** = "방향 수정"(낡은 것 쳐내며 steer).
- **판정루프 = learning-while-using** = soft 적응층.

**learning(soft) + deep-stack(solid scaffold) = 대립이 아니라 두 층.**
평시엔 학습으로 적응, 어려운 문제는 solid 발판 위에 딥스택으로 조립.

## 6. 실측 축 (recall@10 아님)

solid·모듈·이식의 이득은 **단일 벤치 recall@10로 안 잡힌다** — 유지보수·전이·steerability 축이다:

- **(S) 솔리디티**: 깊이 K를 늘려도 안 붕괴하나? (residual vs naive)
- **(P) 이식성**: 한 split에서 고른 config를 held-out split에 얼려 적용해도 이득 남나?
- **(A) 증분 attach**: base 구조에 새 코퍼스를 재빌드 없이 붙여도 full-rebuild 만큼 나오나?

실험 = `test_hswm_solid_scaffold.py` (ML18). 결과 = `EVIDENCE_hswm_solid_scaffold_ml18_*.json`.
