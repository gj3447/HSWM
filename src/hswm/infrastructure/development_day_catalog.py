"""Build the fixed development-day ontology from committed records and reports."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

from hswm.infrastructure import development_day_projection as projection

ROOT = Path(__file__).resolve().parents[3]
RECORDS = 'ontology/catalogs/HSWM_DEVELOPMENT_DAY_2026-09-08.records.json'
SELF_REPORT = 'ontology/catalogs/HSWM_SELF_DEVELOPMENT_RUN_2026-09-08.json'
SELF_DOC = 'docs/operations/HSWM_SELF_DEVELOPMENT_2026-09-08.md'
SELF_PROFILE = '_research/causal_composition/examples/adaptive_hswm_development.v1.json'
PREFIX = 'sym:AbstractNode:hswm-development-day-2026-09-08-'
NONCLAIM = ('DATED_ENGINEERING_REFERENCE_NOT_CURRENT_RUNTIME_STATE_NOT_CANONICAL_ADMISSION_'
            'NOT_INDEPENDENT_CAUSAL_CREDIT_NOT_HSWM_EFFICACY_NOT_GATE_PASS')
ANCHOR_PATHS = (
    'ontology/identity/hswm_core/HSWM_ADAPTIVE_DEVELOPMENT_WORK_ONTOLOGY.v1.json',
    'ontology/identity/hswm_core/HSWM_CONDITIONAL_CAPABILITY_CONTRACT_ONTOLOGY.v1.json',
    'ontology/identity/hswm_core/HSWM_HYPERGRAPH_LEARNING_PLAN_ONTOLOGY.v1.json',
    'ontology/identity/hswm_core/HSWM_FRONTIER_LEARNING_THEORY_ONTOLOGY.v1.json',
)
GROUPS = {
    'changes': '오늘 변경 계보', 'implementation': '실제 구현', 'reviews': '적대적 검토와 수정 계보',
    'integration': '개발 표본과 도구 연결', 'verification': '범위가 명시된 실행 보고',
    'boundaries': '사용자 지침과 판정 경계', 'gaps': '남은 작업', 'sources': 'Git 바이트 출처',
}


def build_bundle(repo_root: Path = ROOT) -> dict:
    commit = projection.SOURCE_COMMIT
    if re.fullmatch(r'[0-9a-f]{40}', commit) is None:
        raise ValueError('commit the source snapshot before building')
    blobs: dict[str, bytes] = {}
    def blob(path: str) -> bytes:
        if path not in blobs:
            blobs[path] = subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=repo_root)
        return blobs[path]
    records = json.loads(blob(RECORDS))
    if records['schema_version'] != 'hswm-development-day-records/v1' or records['date'] != '2026-09-08':
        raise ValueError('dated record catalog identity drift')
    report = json.loads(blob(SELF_REPORT))
    if report['profile_sha256'] != sha256(blob(SELF_PROFILE)).hexdigest():
        raise ValueError('self-development report/profile source mismatch')
    nodes, relations, source_ids, bindings, seen_edges = [], [], {}, {}, set()
    def uid(key: str) -> str:
        return projection.BUNDLE_UID if key == 'bundle' else PREFIX + key
    def edge(a: str, kind: str, b: str, *, external: bool = False) -> None:
        if kind not in projection.ALLOWED_RELATION_TYPES:
            raise ValueError('record link outside relation allowlist')
        identity = (uid(a), kind, b if external else uid(b))
        if identity not in seen_edges:
            seen_edges.add(identity)
            relations.append(dict(from_uid=identity[0], type=kind, to_uid=identity[2],
                                  authority_class='SECONDARY_AI', scope='DEVELOPMENT_DAY_2026_09_08',
                                  status='REFERENCE_LINK_NOT_EFFICACY_OR_PERMISSION'))
    def node(key: str, name: str, role: str, description: str, status: str,
             *, primary: bool = False, **extra) -> None:
        authority = 'USER_PRIMARY' if primary else 'SECONDARY_AI'
        declared = extra.pop('authority_class', authority)
        if declared != authority:
            raise ValueError('record authority promotion')
        role = re.sub(r'[^A-Z0-9_]+', '_', role.upper())
        props = dict(name=name, description=description, role=role, standard_graph_role=role,
                     authority_class=authority, ontology_authority=authority,
                     source_commit=commit, snapshot_date='2026-09-08', status=status,
                     responsibility_owner='user:hswm-development-direction' if primary else projection.OWNER,
                     claim_boundary=NONCLAIM, projection_nonclaim=NONCLAIM,
                     ontology_sensitivity_v1='NORMAL', ontology_authority_class_v1=authority,
                     ontology_epistemic_state_v1='PENDING', ontology_record_lifecycle_v1='ACTIVE',
                     ontology_review_required_v1=not primary,
                     ontology_canonical_scope_v1='USER_REQUEST_ONLY' if primary else 'AI_ANALYSIS_NOT_USER_RATIFIED',
                     ontology_domain_v1='AI', ontology_kind_v1='CONCEPT',
                     ontology_plane_v1='RESEARCH_PROJECTION', ontology_semantic_roles_v1=[role])
        if set(extra) & set(props):
            raise ValueError('record properties may not override projection fields')
        props.update(extra)
        nodes.append(dict(uid=uid(key), labels=['AbstractNode', 'Concept'], properties=props))
    def source(path: str) -> str:
        if path not in source_ids:
            key = 'source-' + sha256(path.encode()).hexdigest()[:16]
            digest = sha256(blob(path)).hexdigest()
            source_ids[path], bindings[path] = key, digest
            node(key, '오늘 작업 출처 · ' + path, 'SOURCE_ARTIFACT',
                 '고정 Git commit의 파일 바이트. 현재 체크아웃이나 원격 제품 상태의 인증이 아니다.',
                 'GIT_BLOB_SOURCE_PINNED', source_path=path, source_paths=[path], source_sha256=digest,
                 source_url=f'https://github.com/gj3447/HSWM/blob/{commit}/{path}')
            edge('sources', 'HAS_SOURCE', key)
        return source_ids[path]
    def record(key, name, role, group, description, status, paths, **props):
        if group not in GROUPS or not paths:
            raise ValueError('record needs an allowed group and source')
        node(key, name, role, description, status, source_paths=list(paths), **props)
        edge(group, 'HAS_CONCEPT', key)
        for path in paths:
            edge(key, 'HAS_SOURCE', source(path))

    node('bundle', 'HSWM 오늘 작업·USL·Reluvator·자체 개발 KG 2026-09-08', 'DEVELOPMENT_DAY_BUNDLE',
         '오늘 커밋, 구현, 적대적 검증과 수정 계보, 17개 Reluvator 구성원, HSWM 자체 개발 실행과 '
         '에이전트 피드백을 출처로 연결한다. 사용자 원문과 AI 해석을 분리하며 과거 KG는 보존한다.',
         'ENGINEERING_REFERENCE_SNAPSHOT_NOT_EFFICACY',
         aliases=['HSWM 오늘 작업', 'HSWM 자체 개발', 'HSWM 자기 개발', 'USL Reluvator 오늘 KG'],
         evidence_cutoff_commit=commit, publication_scope='COMMITTED_RECORDS_AND_DATED_REPORTS')
    for key, name in GROUPS.items():
        node(key, 'HSWM 오늘 · ' + name, 'REFERENCE_SECTION', name + '의 탐색 경로.',
             'ENGINEERING_REFERENCE_SNAPSHOT_NOT_EFFICACY')
        edge('bundle', 'HAS_CONCEPT', key)
    edge('bundle', 'HAS_SOURCE', source(RECORDS))
    for row in records['records']:
        record(row['key'], row['name'], row['role'], row['group'], row['description'], row['status'],
               row['source_paths'], **row.get('properties', {}))
        for link in row.get('links', []):
            edge(row['key'], link['type'], link['target'])

    primary = projection.PRIMARY_SOURCE_PATH
    node('user-request', '사용자 지침 · HSWM 자체 개발과 오늘 작업 KG 기록', 'USER_DIRECT_REQUEST',
         '2026-09-08 직접 사용자 지침. 이후 구현법, 내부 점수와 효능 주장은 사용자 승인으로 소급하지 않는다.',
         'USER_REQUEST_RECORDED_NOT_EFFICACY', primary=True, source_path=primary, source_paths=[primary],
         source_sha256=sha256(blob(primary)).hexdigest(), verbatim_text=blob(primary).decode().rstrip('\n'),
         user_utterance=blob(primary).decode().rstrip('\n'), aliases=['HSWM도 HSWM으로 개발', '자체 개발 사용자 지침'])
    edge('boundaries', 'HAS_CONCEPT', 'user-request')
    edge('user-request', 'HAS_SOURCE', source(primary))
    record('commit-self-development', 'HSWM 자체 개발 지침·프로필·관측 소스 commit',
           'IMPLEMENTATION_COMMIT', 'changes',
           '이 스냅샷의 소스 commit. 사용자 원문, 자체 개발 profile, 실행 요약과 오늘 작업 목록을 고정한다.',
           'COMMITTED_SOURCE_LINEAGE_NOT_EFFICACY', [SELF_DOC, SELF_PROFILE, SELF_REPORT, 'AGENTS.md'],
           change_commit=commit, change_url='https://github.com/gj3447/HSWM/commit/'+commit)
    record('self-profile', 'HSWM 자체 개발 profile · hswm-dev hswm', 'DEVELOPMENT_PROFILE', 'integration',
           'runtime/usl/ontology/docs의 집중·확장 검사를 기존 적응 런타임으로 실행한다. '
           'workspace 표식을 확인하며 테스트 exit code를 자동 유용성 보상으로 바꾸지 않는다.',
           'IMPLEMENTED_LOCAL_SELF_DEVELOPMENT_NOT_AUTONOMOUS_SELF_IMPROVEMENT',
           [SELF_DOC, SELF_PROFILE, 'src/hswm/infrastructure/development_cli.py', 'AGENTS.md'],
           aliases=['HSWM 자체 개발 profile', 'hswm-dev hswm'], focuses=['runtime','usl','ontology','docs'])
    edge('self-profile', 'REQUIRES', 'user-request')
    edge('self-profile', 'REFINES', 'adaptive-runtime-lifecycle')
    record('self-feedback-report', 'HSWM 자체 개발 · 에이전트 feedback 뒤 관계 갱신', 'DATED_ENGINEERING_REPORT',
           'verification', '4건은 명시 피드백 전 success=null이었다. ontology 검사에 대한 에이전트의 '
           '유용성 피드백 1건 이후 관계 관측 수 0→1, revision 1→2와 다음 프로세스의 점수 변화가 '
           '관측됐다. 선택 관계는 같았고 실제 효과나 인과적 credit을 증명하지 않는다.',
           'DATED_AGENT_FEEDBACK_NOT_USER_FEEDBACK_OR_EFFICACY', [SELF_REPORT, SELF_DOC],
           observed_at=report['observed_at'], feedback_source=report['feedback']['source'],
           reported_pending_feedback=report['pending_feedback_count'], reported_events=report['event_count'],
           before_revision=report['before_feedback_plan']['revision'], after_revision=report['after_feedback_plan']['revision'],
           before_score=report['before_feedback_plan']['score'], after_score=report['after_feedback_plan']['score'])
    edge('self-feedback-report', 'TESTS', 'self-profile')
    for run in report['runs']:
        key = 'self-run-' + run['focus']
        record(key, 'HSWM 자체 개발 실행 · ' + run['focus'], 'DATED_ENGINEERING_REPORT', 'verification',
               '실제 CLI 실행의 날짜 고정 요약. 다른 테스트 범위와 합산하지 않으며 현재 DB를 대신하지 않는다.',
               'PASSED_DATED_ENGINEERING_SCOPE_NOT_EFFICACY', [SELF_REPORT, SELF_DOC, SELF_PROFILE],
               reported_episode=run['episode'], reported_test_pass_count=run['passed_tests'],
               output_sha256=run['output_sha256'], reported_exit_code=run['command_exit_code'])
        edge(key, 'TESTS', 'self-profile')
    record('self-development-gaps', 'HSWM 자체 개발의 미완료 범위', 'OPEN_ENGINEERING_GAP', 'gaps',
           '전체 편집·코딩을 자동 조정하는 에이전트 통합, 독립 개발시간/품질 비교, 인과적 credit과 '
           '인지 합성은 미완료다. 에이전트의 자기 평가가 사용자 피드백이나 독립 효능 검증을 대체하지 않는다.',
           'OPEN_NOT_CLOSED_BY_SELF_CHECKS', [SELF_DOC, 'docs/canon/HSWM_CONSTITUTION_2026-08-20.md'])
    edge('self-profile', 'REQUIRES', 'self-development-gaps')
    record('claim-boundary', '기존 목표·과학 판정과 개발 관측의 구분', 'EVIDENCE_BOUNDARY', 'boundaries',
           'HSWM의 하나의 token-native macro network 목표와 FCL-1..8을 보존한다. '
           'G0 미통과/G1 미평가/D-4 미완료/P1 RED는 이번 개발·KG 게시로 바뀌지 않는다. '
           '원격 RED 0, 내부 score 변화, 테스트 통과와 외부 효능을 구분한다.',
           'TARGET_PRESERVED_SCIENTIFIC_STATUS_UNCHANGED',
           ['docs/canon/HSWM_CONSTITUTION_2026-08-20.md',
            'docs/operations/HSWM_ADAPTIVE_DEVELOPMENT_WORK_KG_2026-09-08.md', SELF_DOC])
    for key in ('self-profile','self-feedback-report','reluvator-dated-run-report','usl-adapter-v2'):
        edge(key, 'PRESERVES', 'claim-boundary')
    anchors = []
    for path in ANCHOR_PATHS:
        old = json.loads(blob(path)); root = next(n for n in old['nodes'] if n['uid']==old['bundle_uid'])
        anchors.append(dict(uid=root['uid'], name=root['properties']['name'], required_labels=root['labels']))
        source(path)
        edge('bundle', 'REFINES' if path == ANCHOR_PATHS[0] else 'HAS_CONCEPT', root['uid'], external=True)
    return dict(schema_version=projection.SCHEMA_VERSION, bundle_uid=projection.BUNDLE_UID,
                status='ENGINEERING_REFERENCE_SNAPSHOT_NOT_EFFICACY', nonclaim=NONCLAIM,
                authority_boundary='ONE_VERBATIM_USER_PRIMARY_REQUEST_AND_SECONDARY_AI_ENGINEERING_PROJECTION',
                source_accessed_on='2026-09-08', artifact_bindings=[dict(path=p,sha256=bindings[p]) for p in sorted(bindings)],
                expected_counts=dict(nodes=len(nodes),anchors=len(anchors),relations=len(relations)),
                anchors=anchors,nodes=nodes,relations=relations)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    args=parser.parse_args();data=build_bundle();projection.validate_data(data)
    raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode()
    path=ROOT/projection.ONTOLOGY_PATH
    if args.check:
        if path.read_bytes()!=raw:raise SystemExit('dated ontology differs from committed-source catalog')
    else:path.write_bytes(raw)
    print(json.dumps(dict(status='CHECKED' if args.check else 'BUILT',sha256=sha256(raw).hexdigest(),**data['expected_counts'])))


if __name__ == '__main__':
    main()
