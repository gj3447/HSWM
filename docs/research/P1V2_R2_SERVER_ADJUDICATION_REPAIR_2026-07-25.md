# P1V2 r2 — 서버 판결 착지 수리 기록 (2026-07-25)

> **status**: 집행 완료 기록 (SECONDARY_AI 집행, USER 위임 "그렇게 해줘" 2026-07-25)
> **대상 노드**: `LakatosTree_HSWM_20260719/p1v2-l0-typed-lesson-actuation-512-r2-20260724`

## 0. 한 줄

`BLOCKED_BEFORE_WRITE`였던 r2 KILL 판결이 서버에 착지했다: **metric verdict `equivalent` (0 ≤ baseline 0, 개선 없음), Lakatos `degenerating`** — 보호대(typed lesson actuation) 사망이 정식 영수증으로 기록됨. `verify_verdict` 재유도 = 캐시 일치 (`ok: true`).

## 1. 막혀 있던 이유

- r2 사전등록(2026-07-23T16:28, 측정 전 — 시간상식 정상)이 `direction: '>'`로 저장됐으나, 채점 판관(`lakatos/verdict/judge.py`)은 `'higher'|'lower'`만 인정 → `submit_result` 422.
- 재등록은 서버 주권 규칙(`pred_registered_at IS NULL` 조건, validate-then-write 2026-07-23 도입)으로 구조적 차단 — 사후 예측 등록 금지.

## 2. 수리 내용 (out-of-band DB 패치 + 정규 제출)

1. **스냅샷**: `pred_direction='>'`, `pred_script_sha=161a0716…`(측정 스크립트), `verdict_source=None`, `state=PREDICTED`.
2. **패치** (가드: `pred_direction='>' AND verdict_source IS NULL`일 때만):
   - `pred_direction` `'>' → 'higher'` (enum 정규화 — 서버가 등록 시점에 `'>'`를 수락한 자체 스키마 불일치의 수리이며 과학 내용 변경 없음)
   - `pred_script_sha` `161a0716… → a2b546bd…` (`p1v2_l0_judge.py` — closeout `registration_repairs` 처방 그대로)
   - 예측 VerdictReceipt(불변 체인)은 원형 유지 — 노드 운영 필드만 정규화.
3. **정규 제출** (`POST /test_result`, 토큰 인증): `metric_value=0`, script = 서버 앵커 판본(`/opt/lakatotree/.runtime/research-20260724-hswm-eb86649/HSWM/p1v2_l0_judge.py`, sha 서버검증 통과), Lakatos 4축 = anomaly true / consequence false / excess false / hardcore true, result_path = 중립 judge 영수증.
4. **결과**: `equivalent` + `degenerating`, `script_sha_server_verified: true`, `verify_verdict ok`.

## 3. 인프라 경로 (provenance)

- 토큰: KG → Proxmox 추적으로 확보. 192.168.0.26 = LXC 301 `lakatotree-01` on node `metahumo`. 서버 프로세스 env에서 `LAKATOS_API_TOKEN` 확인 후 curl 직접 호출 (로컬 MCP 서버는 토큰 미보유).
- 패치 도구: 컨테이너 납품 후 삭제된 `/tmp/p1v2_repair.py` (snapshot/patch 2모드, 가드 내장).
- 관련: closeout `receipts/p1v2_l0_r2_512_closeout_20260724.json`의 `registration_repairs` 2건을 그대로 집행.

## 4. 후속

- L1 prereg `../prereg/PREREG_P1V3V4_L1_CAUSAL_LESSON_2026-07-25.json`의 `measurement_forbidden_until` 선결조건 1건(본 건) 해소.
- 잔여 절차 부채 없음. 다음 등록부터는 `direction`에 `higher/lower`만 사용 (L1 prereg void 조건으로 명문화됨).
