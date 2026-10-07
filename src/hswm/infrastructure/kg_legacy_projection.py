"""Checked transactions for the two historical, explicitly invoked KG loaders.

Preserves their declared properties and labels, including historical authority.
This is not an HSWM runtime/canon writer or a general graph administration API.
"""
from __future__ import annotations

from collections import Counter
import math
import re
from typing import Any

from . import kg_publication_integrity as integrity


def property_value(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        families = {"number" if type(v) in (int, float) else type(v).__name__ for v in value}
        return len(families) <= 1 and all(v is not None and not isinstance(v, list)
                                         and property_value(v) for v in value)
    return False


def validate_projection(data: dict[str, Any]) -> None:
    nodes = data['nodes']
    if not isinstance(nodes, list) or not nodes:
        raise ValueError('projection requires nodes')
    anchors = data.get('anchors', [])
    uids = [n['uid'] for n in nodes] + [n['uid'] for n in anchors]
    if any(not isinstance(u, str) or not u.strip() for u in uids) or len(set(uids)) != len(uids):
        raise ValueError('duplicate or empty projection UID')
    keys = []
    for row in nodes:
        integrity.uid_kind(row['uid'])
        if not isinstance(row['properties'], dict):
            raise ValueError('node properties must be a map')
        if row['properties'].get('uid', row['uid']) != row['uid']:
            raise ValueError('node properties cannot change UID')
        if not isinstance(row['labels'], list) or not row['labels']:
            raise ValueError('node requires declared labels')
        if any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', v)
               for v in row['labels']):
            raise ValueError('unsafe node label')
    for row in data['relations']:
        key = (row['from_uid'], row['type'], row['to_uid'])
        if key[0] not in uids or key[2] not in uids:
            raise ValueError('unknown relation endpoint')
        if not isinstance(key[1], str) or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key[1]):
            raise ValueError('unsafe relationship type')
        keys.append(key)
        if row['properties'].get('ontology_bundle_uid') != data['bundle_uid']:
            raise ValueError('relationship provenance must identify this bundle')
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate projected relationship identity')
    for row in nodes + data['relations']:
        for key, value in row['properties'].items():
            if not isinstance(key, str) or not property_value(value):
                raise ValueError(f'invalid Neo4j property: {key!r}')


def assert_projection_constraints(tx: Any, data: dict[str, Any]) -> None:
    # Historical sheaf ResearchSource UIDs deliberately use AbstractNode /
    # SourceDocument labels. Require uniqueness on an already-declared label;
    # do not invent a new label by interpreting the UID's kind as a migration.
    constraints = integrity._constraint_rows(tx)
    covered = {label for node in data['nodes'] for label in node['labels']
               if integrity._has_uid_unique_constraint(constraints, label)}
    if not integrity._has_uid_unique_constraint(constraints, 'SchemaRegistry'):
        raise RuntimeError('missing SchemaRegistry UID uniqueness constraint')
    missing = [node['uid'] for node in data['nodes'] if not covered.intersection(node['labels'])]
    if missing:
        raise RuntimeError(f'missing declared-label UID uniqueness constraint: {missing}')


def _matches(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    # None in SET maps removes a property. Extra, unrelated properties survive.
    def same(a: Any, b: Any) -> bool:
        if isinstance(a, list) and isinstance(b, list):
            return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
        return a == b and isinstance(a, bool) == isinstance(b, bool)
    return all(same(actual.get(key), value) for key, value in expected.items())


def _nodes(tx: Any, uids: list[str]) -> dict[str, Any]:
    rows = tx.run('MATCH (n) WHERE n.uid IN $uids RETURN n.uid AS uid, '
                  'elementId(n) AS eid, labels(n) AS labels, properties(n) AS properties',
                  uids=uids).data()
    if any(n > 1 for n in Counter(r['uid'] for r in rows).values()):
        raise RuntimeError('duplicate remote node identity')
    return {r['uid']: r for r in rows}


def _edges(tx: Any, row: dict[str, Any]) -> list[dict[str, Any]]:
    return tx.run('MATCH (a {uid:$source})-[r]->(b {uid:$target}) '
                  'WHERE type(r)=$kind RETURN elementId(r) AS eid, properties(r) AS properties',
                  source=row['from_uid'], target=row['to_uid'], kind=row['type']).data()


def verify_projection(tx: Any, data: dict[str, Any]) -> dict[str, int]:
    observed = _nodes(tx, [n['uid'] for n in data['nodes']])
    if set(observed) != {n['uid'] for n in data['nodes']}:
        raise RuntimeError('node readback identity mismatch')
    for row in data['nodes']:
        found = observed[row['uid']]
        if not set(row['labels']) <= set(found['labels']) or not _matches(found['properties'], row['properties']):
            raise RuntimeError(f'node readback content mismatch: {row["uid"]}')
    for row in data['relations']:
        found = _edges(tx, row)
        if len(found) != 1 or not _matches(found[0]['properties'], row['properties']):
            raise RuntimeError(f'relationship readback content mismatch: {row["type"]}')
    count = tx.run('MATCH ()-[r {ontology_bundle_uid:$uid}]->() RETURN count(r) AS n',
                   uid=data['bundle_uid']).single()['n']
    if count != len(data['relations']):
        raise RuntimeError('unexpected bundle-owned relationship set')
    return {'readback_nodes': len(observed), 'readback_relations': count}


def publish_projection(tx: Any, data: dict[str, Any]) -> dict[str, int]:
    """Resolve identities only after taking the existing registry transaction lock."""
    validate_projection(data)
    assert_projection_constraints(tx, data)
    integrity.serialize_on_schema_registry(tx)
    registry = tx.run('MATCH (r:SchemaRegistry {uid:$uid}) RETURN r.allowed_labels AS labels, '
                      'r.allowed_reltypes AS relations', uid=integrity.REGISTRY_UID).single()
    labels = {v for n in data['nodes'] for v in n['labels']}
    kinds = {r['type'] for r in data['relations']}
    if not registry or labels - set(registry['labels'] or []) or kinds - set(registry['relations'] or []):
        raise RuntimeError('unregistered projection schema tokens')
    anchors = data.get('anchors', [])
    observed = _nodes(tx, [n['uid'] for n in data['nodes'] + anchors])
    for anchor in anchors:
        if anchor['uid'] not in observed:
            raise RuntimeError(f'missing anchor: {anchor["uid"]}')
    edges = []
    for row in data['relations']:
        found = _edges(tx, row)
        if len(found) > 1:
            raise RuntimeError('duplicate remote relationship identity')
        if found and found[0]['properties'].get('ontology_bundle_uid') not in (None, data['bundle_uid']):
            raise RuntimeError('relationship belongs to another bundle')
        edges.append(found)
    # Preserve the two legacy profiles' existing provenance property names.
    for row in data['nodes']:
        found = observed.get(row['uid'])
        if found:
            for key in ('ontology_bundle_uid', 'sheaf_research_bundle_uid_v1'):
                if found['properties'].get(key) not in (None, data['bundle_uid']):
                    raise RuntimeError('node belongs to another bundle')
    created = updated = 0
    for row in data['nodes']:
        found = observed.get(row['uid'])
        labels = ':'.join(row['labels'])
        if found and set(row['labels']) <= set(found['labels']) and _matches(found['properties'], row['properties']):
            continue
        if found:
            tx.run(f'MATCH (n) WHERE elementId(n)=$eid SET n:{labels}, '
                   'n += $properties, n.updatedAt=datetime()',
                   eid=found['eid'], properties=row['properties']).consume()
            updated += 1
        else:
            tx.run(f'CREATE (n:{labels}) SET n.uid=$uid, n += $properties, '
                   'n.createdAt=datetime(), n.updatedAt=datetime()',
                   uid=row['uid'], properties=row['properties']).consume()
            created += 1
    for row, found in zip(data['relations'], edges):
        if found and _matches(found[0]['properties'], row['properties']):
            continue
        tx.run('MATCH (a {uid:$source}), (b {uid:$target}) '
               f'MERGE (a)-[r:{row["type"]}]->(b) SET r += $properties, r.updatedAt=datetime()',
               source=row['from_uid'], target=row['to_uid'], properties=row['properties']).consume()
    return {'created_nodes': created, 'updated_nodes': updated, **verify_projection(tx, data)}
