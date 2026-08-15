# HSWM — 작업 규칙

> `CLAUDE.md` 에서 분리 (2026-08-10 다이어트). HSWM 작업 규칙은 HSWM 안에 둔다.
> 상위 규칙(단일 writer 토큰, 세션 핸드오프, KG 정본)은 저장소 루트 `AGENTS.md` 를 따른다.

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

- HSWM 결과는 **항상 로그로 정리하고 커밋·푸시한다.** `HSWM/F1_R8_RESULTS_LOG.md`.
  dirty 로 남기지 않는다 (memory `feedback_hswm_results_always_logged_committed`).
- **연산 > 절약.** 더 비싸고 더 강한 옵션이 기본값이다. 목표는 절약이 아니라
  똑똑해지는 것이다 (memory `feedback_hswm_compute_over_frugality`).

## 최소 거버넌스 기본 경로 (2026-08-15 사용자 정전)

- 기본 경로는 **구현/실행 → 직접 측정 → 중요한 결과면 content-addressed 영수증 하나 →
  commit/push**다.
- LakatoTree는 명시적 독립 판정 또는 공개·고위험 과학 승격, OOPtDD는 영수증 무결성 자체의
  감사, OMD는 실제 복수 writer 충돌에만 선택적으로 사용한다. 일반 구현·로컬 회귀·탐색
  실험의 선행 관문으로 요구하지 않는다.
- MCP는 외부 시스템이 실제로 필요할 때만 쓰는 I/O 어댑터다. HSWM 인지·토큰 학습·매 단계
  routing의 필수 경로로 만들지 않는다.
- 명시적 사유가 없으면 한 작업에 선택 거버넌스 층을 둘 이상 중첩하지 않는다. 과거 장부와
  영수증은 보존하지만 기본 실행 정책은
  `research/HSWM_MINIMAL_GOVERNANCE.v1.json`을 따른다.

## 용어 주의

⚠️ `THEORY/재배맨/HSWM_STANDARD.md` 는 나생문 적대검증 후
**"DESIGN DRAFT (NOT a standard)"** 로 자기강등했다. **"표준" 표기 금지.**

## 정전 위치

HSWM 이 무엇인가(사도 #8 축, 합의 포함, 함수가 LLM 인 하이퍼그래프 신경망 등)는
규칙이 아니라 정전이다. KG 와
[`THEORY/00_공통/CLAUDE_archive_canon_summary_2026-08-10.md`](../THEORY/00_공통/CLAUDE_archive_canon_summary_2026-08-10.md)
를 본다. 주요 KG 노드:

- `user-canon-hswm-is-the-larger-ai-containing-consensus-2026-07-23`
- `verdict-omc-direct-commanders-and-lgm-reassignment-2026-07-21`
