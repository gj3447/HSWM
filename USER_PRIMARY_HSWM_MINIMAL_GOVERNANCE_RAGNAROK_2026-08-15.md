# HSWM 최소 거버넌스와 LX3 라그나로크 — USER_PRIMARY

## 권위와 원문

- 권위: `USER_PRIMARY`
- 원문 파일: `USER_PRIMARY_HSWM_MINIMAL_GOVERNANCE_RAGNAROK_2026-08-15.txt`
- 원문 SHA-256: `c82139e1a9f44f748a156ba32950cc1abd5ee01d5870de49858f72db6b6d0e89`

> 좀더 꼼곰하게 생각해주고 그 너무 복잡한 라카토트리나 ooptdd omd 좀 줄여주 ㅓ그게 라그나로크의 이유거든 ㅇㅇ 아직도 mcp 적용되있냐 ㅇㅇ?

이 문장의 정본 의미는 다음과 같다.

1. LakatoTree·OOPtDD·OMD 같은 정적 절차가 HSWM의 실행과 학습보다 커지면 그 복잡성
   자체가 `LX3 라그나로크`의 원인이 된다.
2. HSWM은 더 많은 규칙을 붙이는 방향이 아니라, AI 토큰·행동·외부 결과를 가소적인
   weight/routing/topology에 흡수하는 방향으로 가야 한다.
3. 과거 판정과 영수증을 지우라는 뜻은 아니다. 그것을 모든 작업의 선행 관문에서 내려
   필요한 위험이 실제로 있을 때만 선택적으로 사용하라는 뜻이다.

## SECONDARY_AI 운용 해석

기본 경로는 네 단계뿐이다.

`구현 또는 실행 → 직접 측정 → 중요한 결과면 영수증 하나 → commit/push`

선택 장치는 다음 조건에서만 켠다.

| 장치 | 기본값 | 켜는 조건 |
|---|---|---|
| LakatoTree | OFF | 사용자가 독립 판정을 요청하거나 공개·고위험 과학 승격을 주장할 때 |
| OOPtDD | 레거시 선택 감사 | 영수증 무결성/관측성이 실험 대상이거나 적대 감사가 명시됐을 때 |
| OMD | RETIRED · 역사 자료만 읽기 | 재활성 조건 없음 |
| MCP | 외부 bounded ontology 어댑터 | 고정 조회 또는 `PENDING` 제안이 실제로 필요할 때 |

평상시 작업에는 선택 거버넌스 층을 자동으로 중첩하지 않는다. 명시적 승격 사유가
없으면 최대 한 층만 사용한다. 원인과 효과를 입증할 때도 fixed-context replay,
matched-budget, removal ablation을 네 파일로 쪼개지 않고, 그 세 검사를 한 번에 증명하는
`causal_test_receipt_sha256` 하나만 HSWM 학습 영수증에 결속한다.

## MCP 실측 상태 — 2026-08-15

- 현재 dev-01 Claude와 Codex의 기본 MCP 서버는 외부 Google MCP Toolbox 1.9.0 기반
  `ontology` 하나다. Codex의 HSWM 기본면은 고정 조회 6개이며 Claude 서버의 일곱째 도구는
  라그나로크 split을 `PENDING`으로만 제안하는 고정 도구다.
- 개인 LakatoTree·raw Neo4j·symposium-memory MCP 등록과 잔류 프로세스는 2026-08-15
  제거됐고, raw Cypher·canonical write·ratification 도구는 기본면에 없다.
- Mac mini 설정에는 LakatoTree MCP가 없었다. 별개의 Codex MCP만 존재한다.
- Dell tower 설정에도 LakatoTree MCP가 없었다. `airo-neo4j`, `isaac-manager` 같은 장비별
  어댑터만 존재한다.
- OMD는 RETIRED이며 이 저장소에서 조건부로 다시 켤 수 없다.

따라서 “MCP가 아직 적용되어 있느냐”의 정확한 답은 **외부 Toolbox를 bounded ontology
I/O에만 적용하며 HSWM의 인지·학습 코어에는 적용하지 않는다**이다. MCP나 KG가 매 토큰의
사고를 지휘하는 정적 신경망 역할을 해서는 안 된다.

## 보존 경계

기존 `research/HSWM_RESEARCH_LEDGER.v1.json`, LakatoTree verdict, OOPtDD 영수증과
`hswm_next_research_harness.py`는 역사적·엄격 감사 자료로 보존한다. 다만 활성 기본 정책은
[`research/HSWM_MINIMAL_GOVERNANCE.v1.json`](research/HSWM_MINIMAL_GOVERNANCE.v1.json)이며,
그 자료들이 일반 구현·로컬 회귀·탐색 실험을 막는 전역 관문은 아니다.

이 문서는 사용자 방향을 운용 규칙으로 번역한 `SECONDARY_AI` 부분을 명시적으로 분리한다.
새로운 효능이나 HSWM이 이미 자율 학습한다는 과학적 주장을 추가하지 않는다.
