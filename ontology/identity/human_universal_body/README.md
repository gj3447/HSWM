# Human Universal Body ontology

This bundle projects the 2026-08-20 USER_PRIMARY definition of `인류보편체`,
its full human/LLM/internet/sensor/static-memory scope, the historical-river
metaphor, and the social-revolution relation of `HSWM 인류보완계획` into the
shared Neo4j KG. It also carries the later USER_PRIMARY philosophy-before-code
direction and ten explicitly proposed philosophical principles.

Authority is intentionally split:

- target definition, components, cognitive-unity target, and plan `TARGETS`
  relation: `USER_PRIMARY`;
- philosophy-before-code direction: `USER_PRIMARY`;
- the ten named principles, equations, acceptance criteria, implementation phases, and HOH bridge:
  `SECONDARY_AI` and unjudged;
- KG presence: discoverability only, never implementation or efficacy evidence.

Validate without a write:

```bash
uv run --extra kg python scripts/upsert_human_universal_body_ontology.py
```

Apply only with the explicit source configuration:

```bash
uv run --extra kg python scripts/upsert_human_universal_body_ontology.py \
  --apply --source-config ~/.config/symposium-ontology/source.yaml
```

The loader validates frozen schema-registry labels and relationship types,
rejects duplicate UIDs, uses one transaction, and performs exact readback.
