# W1의 유한 기준식: Lean 증명과 실제 입력 대조

W1의 명시적 불리언 규칙에 대한 정리·보조정리 22개를 Lean 4.32.1로 검사했다.
TypeScript가 생성하는 여섯 변형의 입력 768개를 Lean 어댑터로 읽어 답과 중간값을
대조했다. 이것은 **작성된 유한 기준식의 증명과 구현 대조**다. 실제 모델 호출은 0회이며,
기존 진행표의 T5 모델 측정과 T6–T9 실측 과제는 완료로 바뀌지 않는다.

## 증명한 계약

[Lean 소스](../../formal/HSWMFullW1Reference.lean)는 subject의 세 비트, context와
exception의 각 한 비트로 입력을 정의한다. 네 family의 base는 각각 XOR, zif,
AND, dax에 따른 wug/zif 선택이다. answer는 base에 context와 exception 비트를
차례로 XOR한 값이다. 이 명시적 해석이 전제이며 자연어에서 자동으로 도출한 의미가 아니다.

| 대상 | 검사한 내용 | 범위 |
|---|---|---|
| context·exception | 해당 비트를 뒤집으면 answer가 반전됨 | 모든 typed 입력, 네 family |
| 이름 변경 | 역할과 필드의 명시적 전단사, 복호화 후 기준식 보존 | r7/r3/r9와 v2/v5/v8/v4/v6 매핑 |
| 순서 변경 | 역할·ordinal을 유지한 세 binding의 역순 조회와 재구성 | W1이 사용하는 reverse 변형; 임의 순열 일반 정리가 아님 |
| 역할 간 값 교환 | dax와 pel 교환의 involution, 고정점 조건 | dax와 pel이 같을 때만 원 입력과 같음 |
| 교환 민감도 | 입력 64개, 최종 답 32개, 중간값 묶음 64개 변경 | 네 family의 원본 128개 전체 |
| 유한 입력 공간 | 32개 typed 입력의 중복 없음·완전성, 원본 128개 | 자연어 또는 외부 세계 전체의 완전성이 아님 |
| 실험 크기 | 실제 Lean list의 768행, census 2,304건, sentinel 480건 | 총 2,784건; 셔플 순서·HTTP 실행에 대한 Lean 증명이 아님 |

이름 변경과 순서 변경은 구체적인 표현을 복원한 뒤 비교한다. 역할 간 값 교환은
정답 불변 변형으로 취급하지 않고 교환된 입력에서 다시 계산한다.

## 구현과 연결한 부분

[검증기](../../_research/local_semantic_execution_w1_v2/verify-reference.mts)는
기존 Effect 파일·bounded subprocess 서비스와 증명 검사기를 사용한다. 새 출력
디렉터리에서 `--trust=0`으로 모듈을 컴파일하고 모든 named theorem의 공리를 검사한다.
이번 모듈에서 나온 공리는 `propext`, `Quot.sound`이며, `sorry`, `admit`,
`native_decide`, 사용자 추가 공리로 증명을 대체하지 않았다. 이는 같은 Lean 커널의
검사이며 Lean 컴파일러·표준 라이브러리 자체를 독립 검증했다는 의미는 아니다.

[JSON 어댑터](../../formal/HSWMFullW1ReferenceCli.lean)는 실제 TS 입력 객체를
역할·ordinal·rename 매핑에 따라 읽는다. evaluator의 expected 값은 Lean 요청에
보내지 않는다. 반환된 base/context_flip/exception_flip/answer를 TS 정답표와 비교한다.
비트 범위 오류, ordinal 오류, 중복·누락 역할, 불완전 rename, 미지 transform/family,
정답 주입, 예상하지 않은 prior evidence의 아홉 사례는 거절된다.

별도의 유한 검사는 각 변형이 네 family와 32개 비트 조합을 정확히 한 번 포함하는지,
실제 schedule이 census의 case×arm 및 sentinel×반복×arm 조합을 빠짐없이 포함하는지
확인한다. `inputJson`과 입력 객체의 직렬화 일치, 실제 `requestFor`의 프롬프트 구성도
검사하고 입력 문장·mode instruction·요청 bytes를 hash로 결속한다. 이것은 실행된
검사 결과이며 해당 TS 검사기와 JSON parser의 보편적 Lean 증명은 아니다.

paraphrase 문장과 family의 대응은 **작성자 선언 해석**으로 남긴다. 문장 hash를
결속하면 검사 대상 문장이 무엇이었는지는 추적할 수 있지만, 그 문장이 같은 뜻이라는
사실을 증명하거나 임의 문장의 진실성을 판단할 수는 없다.

## 재현과 표준 그래프

저장소 루트에서 기존 런타임 빌드를 사용하고, 존재하지 않는 private 출력 경로를 지정한다.
네트워크나 모델 서버는 필요하지 않다. 기존 출력 디렉터리는 덮어쓰지 않는다.

```sh
node --test tests/research/full-w1-reference.test.mts
node _research/local_semantic_execution_w1_v2/verify-reference.mts /absolute/new/private/output
src/hswm/effect-runtime/bin/hswm-workspace validate w1-reference
src/hswm/effect-runtime/bin/hswm-workspace query w1-reference proofs
src/hswm/effect-runtime/bin/hswm-workspace query w1-reference comparison
```

[검증 기록](artifacts/hswm_w1_reference_2026-10-07/verification.v1.json)은 toolchain,
소스·실행 모듈 hashes, 정리별 공리, 유한 대조와 범위를 보존한다. 원본 실행 입력·출력과
호스트 경로는 private 출력에 남는다. 동일한 검증 JSON을 SHA-256 파일명으로
`evidence/hswm_w1_reference_2026-10-07/`에도 보존한다.

[그래프](../../ontology/development/HSWM_W1_REFERENCE_LEAN_2026-10-07.v1.json)는
기존 RDF/SHACL/SPARQL/PROV 도구 위에서 증명·대조·출처·경계를 연결하는 추가 view다.
[질의 모음](../../ontology/queries/hswm_w1_reference_2026-10-07/README.md)과
workspace의 `w1-reference`에서 조회한다. 기존 `progress` 선택과 원본 W1 프로토콜은
보존한다. 그래프의 구조 검증 통과 역시 모델 성능이나 canonical 학습을 뜻하지 않는다.

다음 실측 단계에는 현재 서빙 attestation과 기존 승인 범위의 프로젝트 USL 실행 경로가
필요하다. 해당 경로가 확인되면 이미 동결된 W1 계획으로 원본 pilot부터 측정한다.
이번 결과로 모델 readiness, 일반화, 학습 효능, CR/FCL, 전체 HSWM 또는 metahumotonic
완성을 주장하지 않는다.
