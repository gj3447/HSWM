#!/usr/bin/env python3
"""Protected publication adapter for hash-bound SWM-0R/W evidence.

The historical validators and publishers are themselves source artifacts. Keep
their bytes/digests unchanged; add transaction protection around their existing
publication callback. Default invocation validates only, without credentials.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from typing import Any

from hswm.infrastructure import kg_publication_integrity as integrity
PROFILES = {name: f'scripts.upsert_hswm_{name}_evidence' for name in ('swm0r', 'swm0w')}


def identity_bundle(bundle: Any) -> dict[str, Any]:
    return {
        'nodes': [{'uid': uid, 'labels': list(labels), 'properties': dict(properties)}
                  for uid, (labels, properties) in bundle.expected_nodes.items()],
        'relations': list(bundle.expected_relations),
    }


def publish(profile: str, bundle: Any, config: dict[str, str]) -> dict[str, int]:
    identity = identity_bundle(bundle)
    integrity.validate_bundle_for_publication(identity)
    module = importlib.import_module(PROFILES[profile])
    driver = module._connect(config)
    try:
        def transaction(tx: Any) -> dict[str, int]:
            integrity.assert_uid_kind_constraints(tx, identity)
            integrity.serialize_on_schema_registry(tx)
            return module._publish_transaction(tx, bundle)
        with driver.session(database=config['database']) as session:
            result = session.execute_write(transaction)
        with driver.session(database=config['database']) as session:
            return {**result, **session.execute_read(module._exact_remote_readback, bundle)}
    finally:
        driver.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', choices=sorted(PROFILES))
    parser.add_argument('--ontology', type=Path, required=True)
    parser.add_argument('--source-config', type=Path,
                        help='Private JSON with uri, user, password, database; read only with --apply')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    module = importlib.import_module(PROFILES[args.profile])
    bundle = module.validate_bundle(args.ontology, Path(__file__).resolve().parents[1],
                                    require_tracked_head=True, verify_replay=True)
    integrity.validate_bundle_for_publication(identity_bundle(bundle))
    if not args.apply:
        print(json.dumps({'status': 'VALIDATED_ONLY_NOT_PUBLISHED', 'profile': args.profile}))
        return
    if args.source_config is None:
        parser.error('--apply requires --source-config')
    result = publish(args.profile, bundle, json.loads(args.source_config.read_text()))
    print(json.dumps({'status': 'APPLIED_OR_VERIFIED_EXACT_PROJECTION', **result}))


if __name__ == '__main__':
    main()
