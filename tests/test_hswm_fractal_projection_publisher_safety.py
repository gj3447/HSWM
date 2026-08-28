"""Fail-closed publisher-boundary tests for the isolated fractal projection."""

from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path

import pytest

from scripts import upsert_human_universal_body_fractal_projection as publisher


ROOT = Path(__file__).resolve().parents[1]
PROJECTION = ROOT / "ontology/identity/human_universal_body/HSWM_HUMAN_UNIVERSAL_BODY_FRACTAL_PROJECTION.v1.json"


class _Result:
    def __init__(self, rows: list[dict[str, object]] = (), single: dict[str, object] | None = None) -> None:
        self._rows, self._single = rows, single

    def data(self) -> list[dict[str, object]]:
        return self._rows

    def single(self) -> dict[str, object] | None:
        return self._single


class _Tx:
    def __init__(self, responder) -> None:
        self.responder = responder
        self.queries: list[tuple[str, dict[str, object]]] = []

    def run(self, query: str, **kwargs: object) -> _Result:
        self.queries.append((query, kwargs))
        return self.responder(query, kwargs)


def _data() -> dict[str, object]:
    return json.loads(PROJECTION.read_text(encoding="utf-8"))


def test_duplicate_remote_uid_is_refused_before_any_write() -> None:
    tx = _Tx(lambda _query, _kwargs: _Result([
        {"uid": "duplicate", "labels": [], "properties": {}},
        {"uid": "duplicate", "labels": [], "properties": {}},
    ]))
    with pytest.raises(RuntimeError, match="duplicate remote KG UIDs"):
        publisher._find_unique_nodes(tx, ["duplicate"])


def test_exact_node_and_relation_property_collisions_are_refused() -> None:
    data = _data()
    node = data["nodes"][0]
    expected = {"labels": node["labels"], "properties": publisher._expected_node_properties(data, node)}
    observed = deepcopy(expected)
    observed["properties"]["responsibility_owner"] = "wrong_owner"
    with pytest.raises(RuntimeError, match="node property collision"):
        publisher._assert_exact_node(node["uid"], expected, observed)

    relation = data["relations"][0]
    with pytest.raises(RuntimeError, match="relationship property collision"):
        publisher._assert_exact_relation(data, relation, {"properties": {"ontology_bundle_uid": data["bundle_uid"]}})


def test_registry_readback_requires_every_declared_label_and_relation_token() -> None:
    data = _data()
    tx = _Tx(lambda _query, _kwargs: _Result(single={"labels": ["Concept"], "relations": ["HAS_SOURCE"]}))
    with pytest.raises(RuntimeError, match="unregistered schema tokens"):
        publisher._registry_readback(tx, data)


def test_exact_readback_refuses_projection_ownership_count_drift() -> None:
    data = _data()
    expected_nodes = {
        row["uid"]: {"uid": row["uid"], "labels": row["labels"], "properties": publisher._expected_node_properties(data, row)}
        for row in data["nodes"]
    }

    def respond(query: str, kwargs: dict[str, object]) -> _Result:
        if "RETURN n.uid AS uid" in query:
            return _Result(list(expected_nodes.values()))
        if "RETURN properties(r) AS properties" in query:
            row = next(item for item in data["relations"] if item["from_uid"] == kwargs["from_uid"] and item["type"] in query and item["to_uid"] == kwargs["to_uid"])
            return _Result([{"properties": publisher._expected_relation_properties(data, row)}])
        if "MATCH (n {ontology_bundle_uid" in query:
            return _Result(single={"count": len(expected_nodes) - 1})
        if "MATCH ()-[r {ontology_bundle_uid" in query:
            return _Result(single={"count": len(data["relations"])})
        raise AssertionError(query)

    with pytest.raises(RuntimeError, match="projection ownership readback count drifted"):
        publisher._exact_readback(_Tx(respond), data)


def test_anchor_handling_is_match_only_not_create_merge_or_set() -> None:
    source = inspect.getsource(publisher.publish)
    anchor_block = source[source.index("anchors ="):source.index("existing =")]
    executable = "\n".join(line for line in anchor_block.splitlines() if not line.lstrip().startswith("#"))
    assert "_find_unique_nodes(tx, anchors)" in anchor_block
    assert "CREATE" not in executable and "MERGE" not in executable and " SET " not in executable
    assert "for row in data[\"nodes\"]" in source
    assert "for row in data[\"anchors\"]" not in source[source.index("else:"):]
