# 학습 결과 → 저장된 정책 판본 → 다음 문맥 선택

2026-10-11. 기존 Jev 문맥 선택과 별도로, HSWM_LIKENESS의 유한 context×coalition 학습 결과를
HSWM의 owner가 적용한 `semantic_context_policy` 원자로 읽는 연결을 추가했다.
관계 의미 원문은 유지하고 후보 묶음의 선택만 바꾼다. 이 정책은 HSWM Semantic Weight 전체의
정의가 아니며, 새 문맥 일반화·온라인 탐험·실제 모델 성능 향상을 뜻하지 않는다.

```text
native plan의 정확한 원문·역할·예외·후보 binding
 → 기존 W 학습기의 train-only 후보 + 별도 holdout 판정 재계산
 → byte-bound 외부 평가 export
 → native 정책 successor 제안
 → 기존 owner admission
 → 정확한 정책 key/content 재읽기
 → 다음 문맥 조립·실행 trace
```

`prepare...` 함수와 CLI는 제안만 만든다. 실제 canonical 쓰기는 기존 admission owner가
content-bound candidate를 검사하고 처리한다. 로컬 파일 store 내부의 `runtime.submit`을
새 public 우회 경로로 노출하지 않는다. schema·owner·authorization·scope·read set·예상 state revision은
기존 writer가 검사한다. 이 연결이 새로운 권한이나 전역 스키마 변경을 자동 생성하지 않는다.

## 원문과 조합의 결속

`bindContextLearning`은 plan의 전체 spec과 정확한 root/participant key·owner·content descriptor를
scope hash로 묶는다. event 문자열, 필수 관계, 후보, 역할 순서, 원문 판본, 예산이 달라지면 다른
scope다. snapshot 전체 revision은 scope hash에서 제외하므로 정책 원자 자체의 추가가 학습 원문을
바꾸지는 않는다. 실행 plan은 계속 전체 snapshot revision에 묶여 경합 시 거부된다.

각 원문은 `rule:<key-hash>`로 식별하고 원래 content SHA-256을 revision으로 사용한다.
관계 JSON의 재직렬화 결과를 원문으로 취급하지 않는다. 관계 자체와 참여자의 원문을 모두 포함하며,
member role에는 frame ID를 결속한다. 별도 incidence manifest가 원래 reference type·role·순서·
정확한 key·owner를 보존한다. 같은 원문이 다른 관계/역할에 참여해도 발생 위치를 합치지 않는다.
필수 관계의 모든 원문·역할은 모든 action에 남는다. W v1의 source 128개·action member 64개
한도를 넘으면 binding을 거부한다.

W의 `maxBytes`는 중복 제거 원문 bytes이고 native `maximumContextBytes`는 전체 JSON payload
bytes다. 같은 예산 수치를 사용해도 측정 대상은 다르며, 실행 시 native assembler가 전체 frame의
payload 예산을 다시 검사한다. 초과분을 자르지 않는다.

## 외부 평가와 적용 권한

HSWM_LIKENESS의 새 명령은 원문 파일을 확인한 뒤 기존 `runW`를 다시 계산한다.

```sh
./hswm-likeness w context-policy INPUT.json NATIVE_BINDING.json --out NEW_POLICY.json
```

입력 graph가 native binding과 정확히 같아야 하고, 원문 hash·길이·revision 및 action↔candidate
대응이 일치해야 한다. train에서 선택한 후보가 별도 holdout에서 `READY_FOR_OWNER_REVIEW`일
때만 export한다. unknown support·부족한 평가·NO_CHANGE는 기존 선택을 유지하도록 거부한다.
임의로 제공한 report나 Jev confidence로 후보를 골라 내보내지 않는다.

HSWM은 export의 전체 report bytes를 별도 content artifact에 저장하고 정책 payload에 descriptor를
둔다. native 소비자는 source binding·report digest·context·policy/evaluation/proposal 연결과
선택을 대조한다. **native가 외부 추정기를 재실행하거나 관측의 진실·독립성을 인증하는 것은 아니다.**
통계 재계산은 likeness exporter, 실제 적용 결정은 owner의 책임이다. 손으로 위조한 report의
hash를 다시 계산해 진실한 측정으로 만들 수 없다. `SECONDARY_AI_EXTERNAL_EVALUATION_NOT_ADMISSION`,
`OWNER_ADMITTED_EXTERNAL_ASSESSMENT_NOT_AUTHENTICATED`, 미측정 효능 `null`을 유지한다.

## native API와 CLI

기존 `hswm-context` launcher를 build한 뒤 `--help`로 전체 계약을 확인한다.
요청은 기존 `hswm-semantic-context-cli/v1`이며 공통 store/schema/spec/expectedPlanSha256을 사용한다.

| action | 추가 입력 | 결과·효과 |
| --- | --- | --- |
| `learning-binding` | `baselineCandidateId` | W graph·원문 descriptor·incidence manifest; 원문 파일 export는 별도 |
| `policy-initialize` | baseline·`policyTarget` | 최초 baseline 원자 제안; 쓰기 없음 |
| `policy-propose` | baseline·target·`policyEvidence` | 학습된 successor 제안; 쓰기 없음 |
| `policy-restore` | `restoreKey`·target | 과거 선택 내용의 새 successor 제안; journal 되감기 없음 |
| `policy-select` | `decision` | 현재의 정확한 admitted 정책 key 읽기 |
| `policy-assemble` | decision | 선택한 관계와 필수 관계의 완전한 frame 조립 |
| `policy-execute` | decision·기존 LLM `cell` | 기존 실행기를 통한 한 번의 모델 호출·trace |

```json
{
  "contract": "hswm-context-policy-decision/v1",
  "policyKey": {
    "schemaVersion": "YOUR_SCHEMA",
    "lineageId": "YOUR_LINEAGE",
    "atomUid": "YOUR_POLICY_UID",
    "revisionId": 1
  }
}
```

`policyTarget`은 `{key,owner,authorizationRef,scope,decidedAt}`다. key는 **다음에 쓸** 판본이다.
initialize는 0번 한 번만, 이후 변경은 현재 key+1과 같은 책임 owner를 요구한다.
학습의 baseline은 현재 정책이 선택하는 후보와 같아야 한다. source scope가 달라졌으면 재바인딩과
새 평가가 필요하며, 같은 policy UID를 임의의 다른 문맥에 재사용하지 않는다.

owner schema에는 `semantic_context_policy`를 LINEAR relation으로 명시적으로 허용해야 한다.
`hswm:context-policy:scope / candidate-root`는 policy→semantic_relation의 정확한 source root
참조이며 1..72개다. mandatory/candidate 구분과 세부 incidence는 byte-bound binding으로 돌아간다.
`hswm:reference:supersedes / hswm:role:predecessor`는 기존 동일 policy의 이전 판본 0..1개다.
이는 새 일반 RDF predicate나 공유 KG canon 등록이 아니라 해당 owner schema의 로컬 atom 계약이다.

정책 선택은 결정론적이므로 실제 분포는 선택 후보 1, 나머지 0이고 confidence는 null이다.
이 실행만으로 미선택 arm의 학습 support가 생기지 않는다. 다음 randomized cohort를 자동 수집하는
producer hook은 이번 변경에 포함되지 않는다. 실패·기권을 성공/실패 label로 만들지 않으며,
기존 `observe`도 계속 귀속된 관찰만 기록한다.

정책 key를 생략해 최신 판본을 몰래 고르지 않는다. 오래된 key, 바뀐 source/role/예산, owner 불일치,
오래된 read set과 admission revision을 거부한다. 복원은 이전 원자를 삭제하지 않는 새 판본이다.
기존 Jev assemble/project 계약과 과거 RDF evidence는 유지한다. 정책 경로의 RDF projection은
기존 Jev receipt로 위장하지 않으며 이번 CLI는 policy용 `project` action을 추가하지 않는다.

## 재현과 검증 범위

두 저장소의 build 후 아래 도구로 교차 실행을 확인한다. 원문·정답·비용은 authored synthetic fixture,
모델 응답은 mock이다. 새 store에만 fixture owner 권한을 설정하며 운영 store를 변경하지 않는다.

```sh
# HSWM_LIKENESS에서. 대상 HSWM checkout을 명시한다.
proxmox-scratch run context-policy-witness --max-bytes 268435456 --timeout 600 -- \
  node tools/context-policy/verify.mjs ../HSWM
```

이 도구는 source 20개·64 train·320 holdout의 합성 입력을 만들고 **실제 likeness CLI**로
source 검증·학습·holdout 계산을 수행한다. native baseline→학습 successor→다음 문맥 실행을
확인하고, 별도 OS 프로세스로 store를 재개방해 정책을 읽으며, 새 successor로 baseline을 복원한다.
출력은 관리된 artifact 디렉터리의 `validation.json`, binding/input/report, before/after/restored와
원문 파일이다. 도구의 기대 동작 설명 자체는 PASS 관측이 아니며 실제 실행 결과를 따로 확인한다.

관련 구현: `semantic-context-policy-domain.ts`, `semantic-context-policy-runtime.ts`, 기존 context
runtime/process, HSWM_LIKENESS `src/w-context-policy.ts`. 기존 2026-10-10 설계와 오픈소스
묶음의 hash-bound bytes는 수정하지 않는다. 현재 구현 상태를 이 문서에서 별도로 설명한다.
실제 native producer 집단의 결과 평가·모델 비용·학습 효능·Hyperon 우위는 여전히 별도 실험 대상이다.

### 현재 확인된 검증 상태

2026-10-11의 TypeScript 검사, Effect 경계 검사와 build는 통과했다. 사용자 허용 후 로컬
POSIX 임시 공간에서 context·policy·semantic·adaptive 회귀 36개가 모두 통과했다.
HSWM_LIKENESS 전체 `npm run verify`도 262개 테스트·타입 검사·build가 통과했다.

교차 실행 witness도 PASS다. 실제 W CLI가 원문 20개를 확인하고 64 train·320 holdout을 계산해
`calendar → door` 정책을 제안했다. owner 적용 후 다음 문맥 실행에 반영됐고, 별도 프로세스
재개방에서도 유지됐다. 복원은 원래 원자를 보존한 판본 2로 `calendar`를 다시 선택했다.
실제 provider 호출 0회, 모의 모델 호출 2회이며 운영 효능은 null이다.
결과와 원문·입력·전체 report·구현 hash는 sibling HSWM_LIKENESS의
`docs/artifacts/context_policy_2026-10-11/{validation,verification}.json`에 보존했다.

앞선 bulk(NFS) 검사의 native content 쓰기 실패, likeness 기존 6개 테스트 timeout,
시간 한도를 늘린 실행의 storage-guard `du` 관측 오류는 이전 실패로 기록했다.
첫 로컬 witness에서 fixture가 store를 0755로 만든 문제를 0700으로 수정했다.
store의 기존 안전 조건은 바꾸지 않았다. 재검증은 64 MiB·10분 한도 안에서 두 실행 합계
64.13초, 최대 임시 할당 약 6.4 MiB였고 임시 디렉터리를 정리했다.
