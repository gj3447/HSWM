# HSWM — 작업 규칙

> `CLAUDE.md` 에서 분리 (2026-08-10 다이어트). 이 파일이 standalone HSWM 저장소의
> 활성 작업 규칙이다. 존재하지 않는 상위 파일이나 sibling 저장소 규칙을 암묵 상속하지 않는다.

## 실행·저장 3-tier 규약 (2026-07-30 사용자 승인)

- **Mac mini는 지휘 노드다.** HSWM Python/pytest/embedding을 Mac에서 직접 실행하거나
  내장 APFS를 데이터·체크포인트·모델 캐시 fallback으로 쓰지 않는다. 새 작업의 유일한
  진입점은 `~/bin/hswm-run` (`hswm-shell`은 이 진입점의 호환 wrapper)이다.
- **DGX NVMe는 실행 scratch다.** `hswm-run exec <run-id> -- <command>`는 DGX의
  `~/.cache/hswm-scratch/<run-id>`에 outputs/checkpoints/HF·Torch·pip·uv cache를 격리하고,
  기본 `MemoryMax=24G`, `MemoryHigh=20G`, swap 0, CPU 8개 scope에서 실행한다.
- **Proxmox data-01 4TB는 영구 정본이다.** DGX `/mnt/hswm` NFS가 없거나 여유·marker
  preflight가 실패하면 실행을 거부한다(fail-closed). 완료/실패 결과는 작은 파일을 NFS에서
  직접 실행하지 않고 `artifacts.tar` + `receipt.json` + 양쪽 SHA-256 + `.complete`를
  `/mnt/hswm/runs/<run-id>`에 원자적으로 발행한다.
- Mac `SYMPOSIUM/HSWM`은 DGX `~/symposium/HSWM`, 독립 `GIT/HSWM`은 DGX의 깨끗한
  `~/hswm-source` profile로 매핑한다. receipt의 `source_commit`이 실행 정본이며 Mac의
  미커밋 변경은 원격 실행에 섞지 않는다.
- `/Volumes/GM` ExFAT SSD는 과거 USB hang·소파일 지연 때문에 cold/read-only 전용이다.
  재포맷·burn-in 검증 전에는 HSWM 실행·cache·정본 tier로 사용하지 않는다.

## 결과 처리

- **완료한 변경은 항상 커밋·푸시한다.** 문서·코드·구조 정리를 포함해 사용자가 요청한
  작업은 검증 후 현재 정본 브랜치에 커밋하고 `origin`에 푸시한다. 사용자가 명시적으로
  커밋 또는 푸시를 금지한 경우만 예외다 (2026-08-16 사용자 지시).
- **브랜치는 `main` 하나만 유지한다.** 로컬·원격에 장기 feature/실험 브랜치를 남기지
  않는다. 고유 이력이 있는 임시 브랜치를 정리할 때는 먼저 현재 tree를 바꾸지 않는
  ancestry merge 등으로 `main`에서 도달 가능하게 보존한 뒤 ref를 삭제한다
  (2026-08-16 사용자 지시).
- HSWM 결과는 **항상 로그로 정리하고 커밋·푸시한다.** `HSWM/F1_R8_RESULTS_LOG.md`.
  dirty 로 남기지 않는다 (memory `feedback_hswm_results_always_logged_committed`).
- **연산 > 절약.** 더 비싸고 더 강한 옵션이 기본값이다. 목표는 절약이 아니라
  똑똑해지는 것이다 (memory `feedback_hswm_compute_over_frugality`).

## 최소 거버넌스 기본 경로 (2026-08-15 사용자 정전)

- 기본 경로는 **구현/실행 → 직접 측정 → 중요한 결과면 content-addressed 영수증 하나 →
  commit/push**다.
- 사용자가 2026-08-15에 지목한 세 개인 거버넌스 도구 계열은 **완전 삭제 상태**다.
  선택 감사층, 역사 read-only 도구, 원격 판정기 또는 조건부 재활성화 경로로 복원하지
  않는다. 그 도구들이 만든 판정은 HSWM 주장에 대한 권위를 갖지 않는다.
- MCP의 HSWM 기본 경로는 Google MCP Toolbox의 고정 `ontology_*` 조회면만 사용한다.
  교차 저장소의 `ontology_propose_ragnarok_fusion_split`은 고정된 `PENDING` 제안만 만드는
  유일한 예외이며 HSWM이나 정본을 변경하지 않는다. raw Cypher와 canonical write는
  금지하며, HSWM 인지·토큰 학습·매 단계 routing의 필수 경로로 만들지 않는다.
- 독립적으로 읽고 재현할 수 있는 원시 측정값은 보존할 수 있지만, 제거된 개인 도구의
  패키지·테스트·영수증 체인·판정 패킷·ordered-gate·연구 ledger는 복구하지 않는다.
  기본 실행 정책은 `research/HSWM_MINIMAL_GOVERNANCE.v1.json`을 따른다.

## 용어 주의

⚠️ `THEORY/재배맨/HSWM_STANDARD.md` 는 나생문 적대검증 후
**"DESIGN DRAFT (NOT a standard)"** 로 자기강등했다. **"표준" 표기 금지.**

## 정전 위치

HSWM 이 무엇인가(사도 #8 축, 합의 포함, 함수가 LLM 인 하이퍼그래프 신경망 등)는
규칙이 아니라 정전이다. 외부 ontology 조회면과 이 저장소의 `USER_PRIMARY_*` 문서를 본다.
주요 KG 노드:

- `user-canon-hswm-is-the-larger-ai-containing-consensus-2026-07-23`
- `verdict-omc-direct-commanders-and-lgm-reassignment-2026-07-21`
