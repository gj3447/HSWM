"""Shared publication obligations through each existing public entrypoint."""
from functools import lru_cache
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hswm.infrastructure import kg_publication_integrity as integrity
from scripts import upsert_human_universal_body_fractal_projection as human
from scripts import upsert_hswm_fractal_scientific_connections as scientific
from scripts import upsert_hswm_causal_composition_research as causal
from scripts import upsert_hswm_ragnarok_pidna_research as ragnarok
from scripts import upsert_hswm_swm0r_evidence as swm0r
from scripts import upsert_hswm_swm0w_evidence as swm0w
from scripts import publish_hswm_frozen_evidence as frozen

ROOT = Path(__file__).resolve().parents[1]
PROFILES = [human, scientific, causal, ragnarok, swm0r, swm0w]


def publish_profile(module, data, config):
    if module in (swm0r, swm0w):
        return frozen.publish('swm0r' if module is swm0r else 'swm0w', data, config)
    return module.publish(data, config)


@lru_cache
def load_profile(module):
    if module in (swm0r, swm0w):
        suffix = 'R' if module is swm0r else 'W'
        return module.validate_bundle(
            ROOT / f'ontology/identity/human_universal_body/HSWM_SWM0{suffix}_EVIDENCE_BUNDLE.v1.json',
            ROOT, require_tracked_head=False, verify_replay=False)
    paths = {
        human: 'ontology/identity/human_universal_body/HSWM_HUMAN_UNIVERSAL_BODY_FRACTAL_PROJECTION.v1.json',
        scientific: 'ontology/identity/human_universal_body/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_ONTOLOGY.v1.json',
        causal: str(causal.ONTOLOGY_PATH.relative_to(ROOT)),
        ragnarok: 'ontology/identity/hswm_core/HSWM_RAGNAROK_PIDNA_RESEARCH_ONTOLOGY.v1.json',
    }
    return json.loads((ROOT / paths[module]).read_bytes())


@pytest.mark.parametrize('module', PROFILES, ids=lambda m: m.__name__.split('.')[-1])
def test_retained_projection_satisfies_existing_identity_contract(module):
    data = load_profile(module)
    identity = frozen.identity_bundle(data) if module in (swm0r, swm0w) else data
    assert integrity.validate_bundle_for_publication(identity)


@pytest.mark.parametrize('module', PROFILES, ids=lambda m: m.__name__.split('.')[-1])
@pytest.mark.parametrize('corruption', ['kind', 'uid_override', 'authority'])
def test_direct_publish_rejects_invalid_identity_before_connect(module, corruption):
    properties = {'uid': 'sym:Concept:test', 'authority_class': 'SECONDARY_AI'}
    labels = ['Concept']
    if corruption == 'kind':
        labels = ['Other']
    elif corruption == 'uid_override':
        properties['uid'] = 'sym:Concept:other'
    else:
        properties['ontology_authority_class_v1'] = 'USER_PRIMARY'
    data = {'nodes': [{'uid': 'sym:Concept:test', 'labels': labels, 'properties': properties}],
            'relations': []}
    if module in (swm0r, swm0w):
        data = SimpleNamespace(expected_nodes={'sym:Concept:test': (labels, properties)},
                               expected_relations=[])
    # Empty config would fail at connection setup if input validation were bypassed.
    with pytest.raises(integrity.KgPublicationIntegrityError):
        publish_profile(module, data, {})
