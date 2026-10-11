"""Opt-in, real committed transactions for the six remaining publisher paths.

Uses the same empty disposable database contract as the legacy integration suite.
Full source projections are retained; no production credentials are discovered.
"""
from concurrent.futures import ThreadPoolExecutor
import os

import pytest

from test_kg_legacy_projection_integration import db, snapshot
from test_kg_remaining_publishers import PROFILES, load_profile, publish_profile, swm0r, swm0w, frozen

pytestmark = pytest.mark.skipif(os.environ.get('HSWM_LEGACY_DISPOSABLE_TEST') != '1',
                                reason='explicit disposable database opt-in required')


def prepare_profile(module, prepare, run):
    data = load_profile(module)
    if module in (swm0r, swm0w):
        projection = frozen.identity_bundle(data)
        projection['anchors'] = [{'uid': module.ANCHOR_UID,
                                  'name': 'SWM-0 — n-ary non-collapse witness'}]
    else:
        projection = data
    prepare(projection)
    for anchor in projection['anchors']:
        labels = anchor.get('required_labels', ['Plan', 'ImplementationPlan'])
        run('MATCH (n {uid:$uid}) SET n:' + ':'.join(labels), uid=anchor['uid'])
        if module in (swm0r, swm0w):
            run('MATCH (n {uid:$uid}) SET n.ontology_authority_class_v1="SECONDARY_AI", '
                'n.implementation_stage="SWM-0"', uid=anchor['uid'])
    return data, projection


@pytest.mark.parametrize('module', PROFILES, ids=lambda m: m.__name__.split('.')[-1])
def test_complete_projection_concurrent_publish_and_exact_retry(db, module):
    _, config, run, prepare, _ = db
    data, projection = prepare_profile(module, prepare, run)
    anchors_before = run('MATCH (n) RETURN n.uid AS uid, labels(n) AS labels, '
                         'properties(n) AS properties ORDER BY uid')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish_profile(module, data, config), range(2)))
    assert sorted(r['created_nodes'] for r in results) == [0, len(projection['nodes'])]
    before = snapshot(run)
    assert publish_profile(module, data, config)['created_nodes'] == 0
    assert snapshot(run) == before
    assert run('MATCH (n) WHERE n.uid IN $uids RETURN n.uid AS uid, labels(n) AS labels, '
               'properties(n) AS properties ORDER BY uid',
               uids=[r['uid'] for r in anchors_before]) == anchors_before


@pytest.mark.parametrize('module', PROFILES, ids=lambda m: m.__name__.split('.')[-1])
def test_missing_constraint_refuses_without_content_writes(db, module):
    _, config, run, prepare, _ = db
    data, projection = prepare_profile(module, prepare, run)
    kind = projection['nodes'][0]['uid'].split(':')[1]
    run('DROP CONSTRAINT legacy_test_' + kind)
    before = snapshot(run)
    with pytest.raises(RuntimeError, match='uniqueness constraints'):
        publish_profile(module, data, config)
    assert snapshot(run) == before
