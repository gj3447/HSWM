import copy
import hashlib
import json
from pathlib import Path

import pytest

from hswm.infrastructure import kg_legacy_projection as gateway
from scripts import upsert_human_universal_body_ontology as human
from scripts import upsert_sheaf_ontology as sheaf

ROOT = Path(__file__).resolve().parents[1]
HUMAN_PATH = ROOT / 'ontology/identity/human_universal_body/HSWM_HUMAN_UNIVERSAL_BODY_ONTOLOGY.v1.json'
SHEAF_PATH = ROOT / 'ontology/field/sheaf/HSWM_SHEAF_ONTOLOGY.v1.json'


def test_human_projection_preserves_every_declared_property_and_qualified_edge():
    data = json.loads(HUMAN_PATH.read_bytes())
    projected = human._projection(data)
    assert projected['anchors'] == data['anchors']
    for actual, original in zip(projected['nodes'], data['nodes']):
        assert actual['uid'] == original['uid']
        assert actual['labels'] == original['labels']
        for key, value in original['properties'].items():
            assert actual['properties'][key] == value
    for actual, original in zip(projected['relations'], data['relations']):
        assert all(actual[k] == original[k] for k in ('from_uid', 'to_uid', 'type'))
        assert actual['properties']['authority_class'] == original['authority_class']
        assert actual['properties']['status'] == original['status']


def test_sheaf_projection_keeps_source_fields_module_label_and_aliases():
    data = json.loads(SHEAF_PATH.read_bytes())
    projected = sheaf._projection(data)
    nodes = {n['uid']: n for n in projected['nodes']}
    assert len(nodes) == 49
    assert 'OntologyModule' in nodes[data['module_uid']]['labels']
    for source in data['sources']:
        assert nodes[source['uid']]['properties']['title'] == source['title']
        assert nodes[source['uid']]['properties']['supports_topics'] == source['supports']
    for mapping in data['hswm_mappings']:
        assert nodes[mapping['uid']]['properties']['authority'] == 'NONCANONICAL_RESEARCH_MAPPING'
    edges = {(r['from_uid'], r['type'], r['to_uid']) for r in projected['relations']}
    assert len(edges) == len(projected['relations'])
    for edge in data['concept_relations']:
        kind = data['kg_schema_binding']['relationship_type_aliases'].get(edge['type'], edge['type'])
        assert (edge['from_uid'], kind, edge['to_uid']) in edges


@pytest.mark.parametrize('value', [[True, 1], ['1', 1], [None], [[1]], float('nan'), float('inf')])
def test_invalid_property_values_rejected(value):
    data = sheaf._projection(json.loads(SHEAF_PATH.read_bytes()))
    data['nodes'][0]['properties']['invalid'] = value
    with pytest.raises(ValueError, match='invalid Neo4j property'):
        gateway.validate_projection(data)


@pytest.mark.parametrize('mutation', ['uid', 'label', 'labels_string', 'edge', 'provenance'])
def test_projection_rejects_identity_or_schema_corruption(mutation):
    data = sheaf._projection(json.loads(SHEAF_PATH.read_bytes()))
    if mutation == 'uid':
        data['nodes'][0]['properties']['uid'] = 'sym:AbstractNode:other'
    elif mutation == 'label':
        data['nodes'][0]['labels'].append('Bad`Label')
    elif mutation == 'labels_string':
        data['nodes'][0]['labels'] = 'AbstractNode'
    elif mutation == 'edge':
        data['relations'].append(copy.deepcopy(data['relations'][0]))
    else:
        data['relations'][0]['properties']['ontology_bundle_uid'] = 'other'
    with pytest.raises((ValueError, RuntimeError)):
        gateway.validate_projection(data)


def test_unknown_sheaf_module_rejected_before_connecting():
    data = json.loads(SHEAF_PATH.read_bytes())
    data['module_uid'] = 'sym:Concept:absent'
    with pytest.raises(ValueError, match='module_uid'):
        sheaf.load_ontology(data, {})


def test_exact_comparison_preserves_null_deletion_and_boolean_types():
    assert gateway._matches({'foreign': 'preserve'}, {'removed': None})
    assert not gateway._matches({'flag': 1}, {'flag': True})
    assert not gateway._matches({'flags': [1]}, {'flags': [True]})


def test_human_original_hash_drift_remains_a_validation_failure(tmp_path):
    data = json.loads(HUMAN_PATH.read_bytes())
    for prefix in ('source', 'philosophy_source', 'token_hypergraph_source',
                   'deep_set_hypergraph_source', 'occam_direction_source', 'occam_research'):
        path = tmp_path / (prefix + '.txt'); path.write_text(prefix)
        data[prefix + '_path'] = path.name
        data[prefix + '_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    human.validate_data(data, tmp_path)
    (tmp_path / 'occam_research.txt').write_text('later source revision')
    with pytest.raises(ValueError, match='occam_research_sha256 mismatch'):
        human.validate_data(data, tmp_path)
