"""Opt-in tests that COMMIT, corrupt fixtures, and abruptly exit test clients.

Use only an empty disposable Neo4j. No production configuration fallback.
HSWM_LEGACY_DISPOSABLE_TEST=1 HSWM_LEGACY_DISPOSABLE_CONFIG=/private/test.json
Config keys: uri, user, password, database. The old implementation comparison
requires Git object 8043a83841bf3e89dc4e089adbab012475839fc8 in this checkout.
"""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import types

import pytest

from hswm.infrastructure import kg_legacy_projection as gateway
from hswm.infrastructure.kg_publication_integrity import REGISTRY_UID
from scripts import upsert_human_universal_body_ontology as human
from scripts import upsert_sheaf_ontology as sheaf

ROOT = Path(__file__).resolve().parents[1]
BASE = '8043a83841bf3e89dc4e089adbab012475839fc8'
pytestmark = pytest.mark.skipif(os.environ.get('HSWM_LEGACY_DISPOSABLE_TEST') != '1',
                                reason='explicit disposable database opt-in required')


@pytest.fixture
def db():
    from neo4j import GraphDatabase
    config = json.loads(Path(os.environ['HSWM_LEGACY_DISPOSABLE_CONFIG']).read_text())
    driver = GraphDatabase.driver(config['uri'], auth=(config['user'], config['password']),
                                 notifications_min_severity='OFF')
    owned = []
    def run(query, **params):
        with driver.session(database=config['database']) as session:
            return session.run(query, **params).data()
    try:
        assert run('MATCH (n) RETURN count(n) AS n')[0]['n'] == 0, 'Refuse nonempty database'
        def prepare(data):
            owned.extend([REGISTRY_UID] + [n['uid'] for n in data['nodes'] + data.get('anchors', [])])
            labels = {label for node in data['nodes'] for label in node['labels']}
            for label in labels | {'SchemaRegistry'}:
                run(f'CREATE CONSTRAINT legacy_test_{label} IF NOT EXISTS '
                    f'FOR (n:{label}) REQUIRE n.uid IS UNIQUE')
            run('CREATE (:SchemaRegistry {uid:$uid, allowed_labels:$labels, allowed_reltypes:$rels})',
                uid=REGISTRY_UID, labels=sorted(labels), rels=sorted({r['type'] for r in data['relations']}))
            for anchor in data.get('anchors', []):
                run('CREATE (n {uid:$uid, name:$name})', uid=anchor['uid'], name=anchor.get('name'))
        def publish(data):
            with driver.session(database=config['database']) as session:
                return session.execute_write(gateway.publish_projection, data)
        yield driver, config, run, prepare, publish
    finally:
        if owned:
            run('MATCH (n) WHERE n.uid IN $uids DETACH DELETE n', uids=owned)
            assert run('MATCH (n) RETURN count(n) AS n')[0]['n'] == 0
        driver.close()


def fixture():
    uid = 'sym:Concept:legacy-integration-bundle'
    return {'bundle_uid': uid, 'nodes': [
        {'uid': uid, 'labels': ['Concept'], 'properties': {'name': 'bundle', 'description': 'original'}},
        {'uid': 'sym:Concept:legacy-integration-child', 'labels': ['Concept'], 'properties': {'name': 'child'}},
    ], 'relations': [{'from_uid': uid, 'to_uid': 'sym:Concept:legacy-integration-child',
                      'type': 'HAS_CONCEPT', 'properties': {'ontology_bundle_uid': uid, 'status': 'PROPOSED'}}]}


def snapshot(run, *, timestamps=True):
    nodes = run('MATCH (n) RETURN n.uid AS uid, labels(n) AS labels, properties(n) AS properties ORDER BY uid')
    edges = run('MATCH (a)-[r]->(b) RETURN a.uid AS source, type(r) AS kind, b.uid AS target, '
                'properties(r) AS properties ORDER BY source, kind, target')
    for node in nodes:
        node['labels'].sort()
    if not timestamps:
        for row in nodes + edges:
            for key in ('createdAt', 'updatedAt'):
                row['properties'].pop(key, None)
    return nodes, edges


@pytest.mark.parametrize('profile', ['human', 'sheaf'])
def test_historical_projection_matches_exact_content_and_retry_preserves_timestamps(db, profile):
    driver, config, run, prepare, publish = db
    module, path = ((human, 'ontology/identity/human_universal_body/HSWM_HUMAN_UNIVERSAL_BODY_ONTOLOGY.v1.json')
                    if profile == 'human' else (sheaf, 'ontology/field/sheaf/HSWM_SHEAF_ONTOLOGY.v1.json'))
    data = json.loads((ROOT / path).read_bytes())
    projected = module._projection(data)
    prepare(projected)
    legacy = types.ModuleType('historical_publisher')
    script = Path(module.__file__).relative_to(ROOT).as_posix()
    exec(compile(subprocess.check_output(['git', 'show', f'{BASE}:{script}'], cwd=ROOT), script, 'exec'), legacy.__dict__)
    with driver.session(database=config['database']) as session:
        if profile == 'human':
            session.execute_write(legacy._publish_transaction, data)
        else:
            session.execute_write(legacy._upsert_transaction, data, data['kg_schema_binding'], {})
    historical = snapshot(run, timestamps=False)
    retry_before = snapshot(run)
    assert publish(projected)['updated_nodes'] == 0
    assert snapshot(run) == retry_before
    run('MATCH (n) WHERE n.uid IN $uids DETACH DELETE n', uids=[n['uid'] for n in projected['nodes']])
    assert publish(projected)['created_nodes'] == len(projected['nodes'])
    assert snapshot(run, timestamps=False) == historical


def test_two_committing_writers_serialize_and_retry_is_noop(db):
    _, _, run, prepare, publish = db
    data = fixture(); prepare(data)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish(data), range(2)))
    assert sorted(r['created_nodes'] for r in results) == [0, 2]
    before = snapshot(run)
    assert publish(data)['updated_nodes'] == 0
    assert snapshot(run) == before


@pytest.mark.parametrize('kind', ['node', 'edge'])
def test_equal_count_content_corruption_rolls_back(db, monkeypatch, kind):
    _, _, run, prepare, publish = db
    data = fixture(); prepare(data); before = snapshot(run)
    verify = gateway.verify_projection
    def corrupt(tx, projection):
        query = ('MATCH (n {uid:$uid}) SET n.description="wrong"' if kind == 'node'
                 else 'MATCH ()-[r {ontology_bundle_uid:$uid}]->() SET r.status="ACTIVE"')
        tx.run(query, uid=data['bundle_uid']).consume()
        return verify(tx, projection)
    monkeypatch.setattr(gateway, 'verify_projection', corrupt)
    with pytest.raises(RuntimeError, match='readback content mismatch'):
        publish(data)
    assert snapshot(run) == before


def test_duplicate_edge_and_foreign_owner_refuse_without_repair(db):
    _, _, run, prepare, publish = db
    data = fixture(); prepare(data); publish(data)
    run('MATCH (a {uid:$uid})-[r]->(b) CREATE (a)-[:HAS_CONCEPT]->(b)', uid=data['bundle_uid'])
    before = snapshot(run)
    with pytest.raises(RuntimeError, match='duplicate remote relationship'):
        publish(data)
    assert snapshot(run) == before
    run('MATCH ()-[r:HAS_CONCEPT]->() WHERE r.ontology_bundle_uid IS NULL DELETE r')
    run('MATCH ()-[r]->() SET r.ontology_bundle_uid="other-owner"')
    before = snapshot(run)
    with pytest.raises(RuntimeError, match='another bundle'):
        publish(data)
    assert snapshot(run) == before


def test_missing_constraint_refuses_before_writes(db):
    _, _, run, prepare, publish = db
    data = fixture(); prepare(data)
    run('DROP CONSTRAINT legacy_test_Concept')
    before = snapshot(run)
    with pytest.raises(RuntimeError, match='uniqueness constraint'):
        publish(data)
    assert snapshot(run) == before


@pytest.mark.parametrize('commit', [False, True])
def test_abrupt_client_death_before_or_after_commit_recovers(db, tmp_path, commit):
    _, _, run, prepare, publish = db
    data = fixture(); prepare(data)
    path = tmp_path / 'fixture.json'; path.write_text(json.dumps(data))
    program = '''import json, os, sys
from pathlib import Path
from neo4j import GraphDatabase
from hswm.infrastructure.kg_legacy_projection import publish_projection
c=json.loads(Path(os.environ['HSWM_LEGACY_DISPOSABLE_CONFIG']).read_text())
d=GraphDatabase.driver(c['uri'],auth=(c['user'],c['password']))
s=d.session(database=c['database']); tx=s.begin_transaction()
publish_projection(tx,json.loads(Path(sys.argv[1]).read_text()))
if sys.argv[2]=='commit': tx.commit()
os._exit(73)
'''
    result = subprocess.run([sys.executable, '-B', '-c', program, str(path), 'commit' if commit else 'abort'],
                            cwd=ROOT, timeout=30, capture_output=True)
    assert result.returncode == 73, result.stderr.decode()
    retried = publish(data)
    assert retried['created_nodes'] == (0 if commit else 2)
    assert retried['readback_nodes'] == 2 and retried['readback_relations'] == 1


def test_intended_update_preserves_foreign_property_and_anchor(db):
    _, _, run, prepare, publish = db
    data = fixture(); data['anchors'] = [{'uid': 'sym:Concept:anchor', 'name': 'existing'}]
    prepare(data); publish(data)
    run('MATCH (n {uid:$uid}) SET n.foreign="preserve"', uid=data['bundle_uid'])
    changed = copy.deepcopy(data); changed['nodes'][0]['properties']['description'] = 'new'
    assert publish(changed)['updated_nodes'] == 1
    assert run('MATCH (n {uid:$uid}) RETURN n.foreign AS v', uid=data['bundle_uid'])[0]['v'] == 'preserve'
    assert run('MATCH (n {uid:"sym:Concept:anchor"}) RETURN properties(n) AS p')[0]['p'] == data['anchors'][0]
