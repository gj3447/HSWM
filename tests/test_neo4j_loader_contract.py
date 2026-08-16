from __future__ import annotations

import json
import sys
import types

from hswm.prototypes import neo4j_loader


ENV_NAMES = ("NEO4J_URI", "NEO4J_USER", "NEO4J_PW", "NEO4J_DATABASE")


def test_credentials_fail_closed_and_ignore_personal_mcp_config(monkeypatch, tmp_path):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    personal = tmp_path / "CD" / ".mcp.json"
    personal.parent.mkdir()
    personal.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "neo4j": {
                        "env": {
                            "NEO4J_URI": "bolt://must-not-be-read",
                            "NEO4J_PASSWORD": "must-not-be-read",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    try:
        neo4j_loader._creds()
    except RuntimeError as exc:
        assert "explicit read-only Neo4j configuration required" in str(exc)
        assert all(name in str(exc) for name in ENV_NAMES)
    else:  # pragma: no cover - defensive fail-closed assertion
        raise AssertionError("personal MCP credential fallback was accepted")


def test_loader_opens_an_explicit_read_access_session(monkeypatch, tmp_path):
    for name, value in {
        "NEO4J_URI": "bolt://reader.example.invalid:7687",
        "NEO4J_USER": "hswm_reader",
        "NEO4J_PW": "test-only-password",
        "NEO4J_DATABASE": "neo4j",
    }.items():
        monkeypatch.setenv(name, value)

    read_access = object()
    observed = {}

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def data(self):
            return self.rows

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def run(self, query, **params):
            if "RETURN elementId(h) AS hid" in query:
                return Result([{"hid": "h1", "members": ["m1", "m2", "m3"]}])
            assert params == {"ids": ["m1", "m2", "m3"]}
            return Result(
                [
                    {"mid": mid, "emb": [float(index)] * neo4j_loader.DIM}
                    for index, mid in enumerate(("m1", "m2", "m3"), start=1)
                ]
            )

    class Driver:
        def session(self, **kwargs):
            observed["session"] = kwargs
            return Session()

        def close(self):
            observed["closed"] = True

    class GraphDatabase:
        @staticmethod
        def driver(uri, auth):
            observed["driver"] = {"uri": uri, "auth": auth}
            return Driver()

    monkeypatch.setitem(
        sys.modules,
        "neo4j",
        types.SimpleNamespace(GraphDatabase=GraphDatabase, READ_ACCESS=read_access),
    )

    result = neo4j_loader.load_and_cache(
        max_hyperedges=1,
        min_arity=3,
        path=tmp_path / "real_kg_hypergraph.npz",
    )

    assert result == {"n_nodes": 3, "n_edges": 1}
    assert observed["driver"] == {
        "uri": "bolt://reader.example.invalid:7687",
        "auth": ("hswm_reader", "test-only-password"),
    }
    assert observed["session"] == {
        "database": "neo4j",
        "default_access_mode": read_access,
    }
    assert observed["closed"] is True
