# HSWM AI 연구 도구

2026-09-27 적용. 필요한 작업에서 선택해서 쓰며, 일반 개발의 필수 단계는 아니다.
문서 검색은 QMD, 코드 탐색은 Serena, 응답 비교는 Inspect AI를 사용한다.
GEPA는 관계 설명 수정 방법을 비교하는 독립 실험 도구다.
기존 [연구 작업환경](HSWM_RESEARCH_WORKFLOW.md)에서 필요한 도구만 선택한다.

## QMD: 저장소 문서 검색

[QMD](https://github.com/tobi/qmd)의 공식 npm 패키지 `@tobilu/qmd@2.8.3`
(MIT)를 [별도 package-lock.json](../../src/hswm/development/qmd/package-lock.json)에
전이 의존성과 integrity까지 고정했다. HSWM 런타임 의존성이나 다른 프로젝트의 전역
QMD 설치를 바꾸지 않는다. 저장소 루트에서 한 번 설치하고 색인한다.
이 Linux 체크아웃에서는 네이티브 실행 의존성을 포함해 약 0.9 GB를 사용한다.
이는 아래에서 구분하는 모델 가중치 다운로드와 별도다.

```sh
npm --prefix src/hswm/development/qmd ci --ignore-scripts --no-audit --no-fund
src/hswm/development/qmd/node_modules/.bin/qmd update
src/hswm/development/qmd/node_modules/.bin/qmd search 'Hyperon' -c hswm-canon
src/hswm/development/qmd/node_modules/.bin/qmd search '연구 작업환경' -c hswm-operations
src/hswm/development/qmd/node_modules/.bin/qmd get qmd://hswm-canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md
```

[.qmd/index.yml](../../.qmd/index.yml)은 `docs/canon`, `docs/research`,
`docs/operations`의 Markdown만 색인한다. DB는 `.qmd/index.sqlite`에 로컬로 보관하고
Git에서 제외한다. 편집 후 필요할 때 `qmd update`를 실행한다. 검색 순위는 관련도이며,
최종 판단에는 원문 경로·날짜·출처를 확인한다. 원본 JSON ontology 조회는 기존
`hswm-workspace`를 사용한다.

[Codex 설정](../../.codex/config.toml)의 `hswm_docs`는 이 체크아웃의 고정된 QMD를
실행하는 선택적 MCP다. 새 Codex 세션에서 로드하며 `query`, `get`, `multi_get`,
`status` 네 가지 읽기 도구만 허용한다. 서버가 없어도 개발 세션을 막지 않는다.
프로젝트 MCP 설정의 의미는 [공식 Codex 설정 문서](https://learn.chatgpt.com/docs/config-file/config-reference)를 따른다.

이번에 적용하고 검증한 것은 **모델이 필요 없는 키워드 검색**이다. MCP에서도 다음처럼
`lex` 검색과 `rerank: false`를 사용한다.

```json
{"searches":[{"type":"lex","query":"Hyperon"}],"collections":["hswm-canon"],"rerank":false,"limit":3}
```

벡터 색인·쿼리 확장·재정렬용 모델은 내려받지 않았다. `embed` 또는 모델 기반 `query`를
사용하려면 별도로 모델 revision·digest·라이선스와 실행 자원을 확인한다. 자동 갱신 hook이나
원격 MCP 서버도 추가하지 않았다.

## Serena: 코드의 정의와 참조 탐색

[Serena](https://github.com/oraios/serena/releases/tag/v1.7.0) `v1.7.0`을 별도
[uv 프로젝트](../../src/hswm/development/serena/pyproject.toml)에 고정했다.
이 태그의 라이선스는 MIT다. 언어 서버도 별도 npm lockfile로 고정한다.

```sh
uv sync --locked --project src/hswm/development/serena
npm --prefix src/hswm/development/serena ci --ignore-scripts --no-audit --no-fund
```

새 Codex 세션의 `hswm_code` MCP에서 심볼 개요, 정의, 참조, 파일 진단을 조회한다.
실제 TypeScript 파일에서 네 도구를 호출해 교차 파일 참조까지 확인했다.
편집·shell·memory 도구는 노출하지 않는다. 기존 TypeScript/Effect 검사와 함께 쓰는
개발 편의 도구이며, 설정·언어 서버 상세는 [Serena 안내](../../src/hswm/development/serena/README.md)에 있다.

## Inspect AI: 저장된 응답 두 군 비교

[Inspect AI](https://inspect.aisi.org.uk/) 공식 패키지 `inspect-ai==0.3.260` (MIT)를
독립 [uv 프로젝트](../../_research/inspect_comparison_v1/pyproject.toml)에 고정했다.
Inspect의 Task·Dataset·Solver·Scorer와 기본 `.eval` 로그 형식을 사용한다.
다음 명령은 저장소 루트에서 기존 관측 16쌍을 변환하고 평가한다.

```sh
uv run --locked --project _research/inspect_comparison_v1 python \
  _research/inspect_comparison_v1/semantic_locality_adapter.py \
  _research/semantic_locality_dgx_v1/observations.jsonl \
  .hswm-local/inspect-comparison/semantic-locality-full-vs-role-swap.jsonl
uv run --locked --project _research/inspect_comparison_v1 python \
  _research/inspect_comparison_v1/paired_eval.py \
  .hswm-local/inspect-comparison/semantic-locality-full-vs-role-swap.jsonl \
  --log-dir .hswm-local/inspect-comparison/eval-logs
uv run --locked --project _research/inspect_comparison_v1 inspect view \
  --log-dir .hswm-local/inspect-comparison/eval-logs
```

새 모델 호출 없이 이미 저장된 결정을 exact match로 채점한다. 기본 예제의 `role_swap`은
입력 역할을 바꾼 진단군이므로 같은 입력에서 후보 모델이 개선됐다는 비교가 아니다.
원래 [분석과 한계](../../_research/semantic_locality_dgx_v1/analysis.v1.json)를 함께 읽는다.
잘못되거나 빈 관측은 실패로 남기고, 누락된 쌍·중복 ID·중복 JSON 키·불일치 target은 거부한다.
평가 로그는 Git에서 제외된 `.hswm-local/`에 둔다.

다른 저장 응답에도 `id`, `input`, `target`, `baseline`, `candidate`를 갖춘 JSONL로
사용할 수 있다. 입력 계약·출처 pin·실행 상세는
[Inspect 안내](../../_research/inspect_comparison_v1/README.md)에 있다.

```sh
uv run --locked --project _research/inspect_comparison_v1 --group dev \
  pytest -q tests/test_inspect_comparison.py
```

검증 범위는 한국어·영어 키워드 검색, 실제 MCP 조회·원문 읽기, 저장 응답 평가와 `.eval`
로그 생성이다. 이는 도구 연결 확인이며 새로운 HSWM 성능 결과나 CR/FCL 판정이 아니다.

## Inspect 실모델 연결과 GEPA 비교

`live_eval.py`는 기존 HSWM W1 국소 의미 입력·E1 출력 schema·엄격한 parser를
재사용하는 [TypeScript bridge](../../_research/inspect_comparison_v1/hswm_bridge.mts)를 호출한다.
두 군은 같은 문제·모델·출력 한도를 쓰고 `relation.semanticText`만 다르게 실행한다.
정답·case ID·split은 모델 요청에서 제외하며, 잘못된 응답과 HTTP 실패도 채점 분모에 남긴다.
각 호출의 요청·응답, hash, 서버가 보고한 토큰 사용량은 로컬 평가 로그에 기록한다.
같은 호출 한도는 같은 실제 토큰 비용을 뜻하지 않으므로 사용량을 함께 확인한다.

기존 합성 사례의 학습 12개·평가 20개 분할을 별도 파일로 준비한다. 아래 출력 디렉터리는
새 경로여야 한다. 학습 입력의 관계 설명도 초기 가설로 교체해 정답 관계가 유출되지 않게 한다.

```sh
node _research/inspect_comparison_v1/prepare_fixture.mts \
  .hswm-local/relation-comparison-01
```

[GEPA](https://pypi.org/project/gepa/0.1.4/) `0.1.4` (MIT)는 독립
[비교 프로젝트](../../_research/gepa_relation_comparison_v1/README.md)에 설치한다.
GEPA에는 학습 사례와 그 실행 피드백만 제공하고, 선택된 관계 설명을 고정한 뒤 Inspect로
초기 설명과 같은 평가 사례에 대조한다. 학습 호출·수정 제안 호출·최종 평가 호출의 예산을
각각 제한한다. canonical graph에 자동 반영하지 않는 관계 텍스트 최적화 비교다.

```sh
uv sync --locked --project _research/gepa_relation_comparison_v1 --group dev
```

실행 명령은 [Inspect 실모델 안내](../../_research/inspect_comparison_v1/README.md)와
[GEPA 안내](../../_research/gepa_relation_comparison_v1/README.md)를 따른다.
기존 W1 전체 실험이나 CR/FCL 판정을 대체하지 않으며, 새 모델 관측을 연구 결과로
공개할 때는 해당 실험의 출처·비용·대조군을 별도로 기록한다.

2026-09-27 환경 확인: DGX의 `qwen3-4b-real` 모델 목록과 vLLM `0.25.1` 버전은 응답했다.
그러나 `~/bin/hswm-run preflight`는 `/mnt/hswm`의 data-01 저장소가 연결되지 않아 실패했다.
따라서 이번 도구 연결은 로컬 HTTP fixture와 실제 Inspect/GEPA 라이브러리로 검증하고,
DGX 생성 요청은 실행하지 않았다. 저장소 연결과 wrapper preflight가 정상인 환경에서
실모델 실행을 진행한다. Docling은 논문 PDF 변환 수요가 생길 때 별도로 도입한다.
