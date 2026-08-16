# HSWM 개인 거버넌스 도구 제거 — USER_PRIMARY

## 권위

- 권위: `USER_PRIMARY`
- 원문 파일: `docs/canon/sources/USER_PRIMARY_HSWM_MINIMAL_GOVERNANCE_RAGNAROK_2026-08-15.txt`
- 원문 SHA-256: `6ab2e3221bff1cfe1b9a2a197bf24521453e4781ddffdfafffc3c6d9fc78ae6f`

## 현재 정전

사용자가 앞서 지목한 세 개인 거버넌스 도구 계열은 축소·선택 사용 대상이 아니라
**완전 제거 대상**이다. 구현, 패키지, 테스트, 영수증 체인, 외부 판정 패킷, 원격 실행기,
strict ordered-gate 연결과 재활성화 규칙을 저장소의 현재 트리에서 제거한다.

제거된 도구가 만들었던 판정은 HSWM 주장에 대한 권위를 갖지 않는다. 원시 측정값과 일반
실험 코드는 해당 도구 없이 독립적으로 읽고 재현할 수 있을 때만 보존한다. 보존된 원시
측정의 의미는 관측값에 한정되며 과거 외부 판정을 승계하지 않는다.

## 기본 실행 경로

```text
구현 또는 실행
→ 직접 측정
→ 중요한 결과면 content-addressed 영수증 하나
→ commit/push
```

권한, 타입, provenance, 예산, idempotency, rollback은 HSWM 실행 안전 경계로 남긴다.
연구 판정 장부나 다중 영수증 의식은 기본 경로에 다시 넣지 않는다.

## MCP 경계

외부 ontology 어댑터는 bounded I/O로만 취급한다. raw Cypher, canonical write,
ratification, HSWM 추론·토큰학습·매 단계 routing을 MCP에 위임하지 않는다. 이번 제거는
ontology 자료 자체를 삭제하라는 지시가 아니며, 개인 거버넌스 서버의 복구도 허용하지 않는다.

이 문서는 이전의 “선택적 보존” 해석을 폐기하고 최신 사용자 지시를 우선한다.
