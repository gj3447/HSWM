# Jev 원리 적용 그래프 조회

Bundle: `sym:AbstractNode:hswm-jev-principles-2026-09-21`.

`applications.rq`는 원리·적용 구조·구현 상태 6행, `obligations.rq`는 CR-0..7/FCL-1..8의 source-bound 의무 16행, `observations.rq`는 실제 조건별 관측 12행을 반환한다. `unsupported.rq`의 기대값은 출처 연결 없는 주장 0행이다. 출처 연결은 참이나 연구 완료를 뜻하지 않는다.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle project --source jev=ontology/development/HSWM_JEV_PRINCIPLES_2026-09-21.v1.json --profile v2 --output-dir NEW_DIRECTORY
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source jev=ontology/development/HSWM_JEV_PRINCIPLES_2026-09-21.v1.json --profile v2 --query ontology/queries/hswm_jev_principles_2026-09-21/obligations.rq
```

기존 base v2, research integration, DGX source SHACL을 재사용한다. 모든 proposal과 관측은 세 ordered role participation을 가진다. local artifact는 SHA-256, 외부 공식 문서는 URL·조회 날짜로 결속하며 URL digest를 문서 내용 hash로 표현하지 않는다. 원래 의무 UID의 live 존재를 가정하지 않고 이전 고정 source와 pointer를 보존한 reference를 쓴다. 새 snapshot은 기존 DGX 연구 root와 연결하며 원래 기록을 고치지 않는다.
