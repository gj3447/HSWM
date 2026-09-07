"""Small durable store for versioned, role-typed adaptive hypergraph atoms.

It is a local prototype persistence boundary.  It records immutable revisions
and compare-and-swap rewrites; it neither decides learning efficacy nor writes
to the reference KG.
"""

from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any


SCHEMA_VERSION = "hswm-adaptive-hypergraph/v1"


class AdaptiveStoreError(RuntimeError):
    pass


def _bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                          separators=(",", ":")).encode()
    except (TypeError, ValueError) as error:
        raise AdaptiveStoreError("value is not canonical JSON") from error


def _digest(value: Any) -> str:
    return sha256(_bytes(value)).hexdigest()


def _load(raw: bytes, label: str) -> Any:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise AdaptiveStoreError(f"stored {label} is malformed") from error
    if _bytes(value) != raw:
        raise AdaptiveStoreError(f"stored {label} is not canonical")
    return value


def _atom(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"uid", "kind", "owner", "refs", "payload"}:
        raise AdaptiveStoreError("atom shape is invalid")
    if any(not isinstance(value[key], str) or not value[key] for key in ("uid", "kind", "owner")):
        raise AdaptiveStoreError("atom identity is invalid")
    if not isinstance(value["refs"], list):
        raise AdaptiveStoreError("atom refs are invalid")
    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for ref in value["refs"]:
        if (not isinstance(ref, dict) or set(ref) != {"role", "uid"} or
                not isinstance(ref["role"], str) or not ref["role"] or
                not isinstance(ref["uid"], str) or not ref["uid"]):
            raise AdaptiveStoreError("atom reference is invalid")
        key = (ref["role"], ref["uid"])
        if key in seen:
            raise AdaptiveStoreError("duplicate role reference")
        seen.add(key)
        refs.append({"role": ref["role"], "uid": ref["uid"]})
    _bytes(value["payload"])
    return {"uid": value["uid"], "kind": value["kind"], "owner": value["owner"],
            "refs": refs, "payload": value["payload"]}


class AdaptiveStore:
    """SQLite CAS store for one or more locally named adaptive graphs."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
            CREATE TABLE IF NOT EXISTS adaptive_graphs (
              graph_id TEXT PRIMARY KEY, manifest_digest TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS adaptive_atoms (
              graph_id TEXT NOT NULL, uid TEXT NOT NULL, revision INTEGER NOT NULL,
              kind TEXT NOT NULL, owner TEXT NOT NULL, refs_json BLOB NOT NULL,
              payload_json BLOB NOT NULL, atom_digest TEXT NOT NULL, event_id TEXT,
              PRIMARY KEY (graph_id, uid, revision),
              FOREIGN KEY (graph_id) REFERENCES adaptive_graphs(graph_id)
            );
            CREATE TABLE IF NOT EXISTS adaptive_heads (
              graph_id TEXT NOT NULL, uid TEXT NOT NULL, revision INTEGER NOT NULL,
              kind TEXT NOT NULL, owner TEXT NOT NULL, atom_digest TEXT NOT NULL,
              PRIMARY KEY (graph_id, uid),
              FOREIGN KEY (graph_id, uid, revision) REFERENCES adaptive_atoms(graph_id, uid, revision)
            );
            CREATE TABLE IF NOT EXISTS adaptive_events (
              graph_id TEXT NOT NULL, event_id TEXT NOT NULL, intent_digest TEXT NOT NULL,
              source_json BLOB NOT NULL, consumed_json BLOB NOT NULL, produced_json BLOB NOT NULL,
              PRIMARY KEY (graph_id, event_id),
              FOREIGN KEY (graph_id) REFERENCES adaptive_graphs(graph_id)
            );
            """)

    def initialize(self, graph_id: str, manifest_digest: str, atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(graph_id, str) or not graph_id or not isinstance(manifest_digest, str) or not manifest_digest:
            raise AdaptiveStoreError("graph identity is invalid")
        rows = [_atom(item) for item in atoms]
        if not rows or len({row["uid"] for row in rows}) != len(rows):
            raise AdaptiveStoreError("initial atoms must be unique and non-empty")
        uids = {row["uid"] for row in rows}
        if any(ref["uid"] not in uids for row in rows for ref in row["refs"]):
            raise AdaptiveStoreError("initial reference is unresolved")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT manifest_digest FROM adaptive_graphs WHERE graph_id=?", (graph_id,)).fetchone()
            if existing is not None:
                if existing["manifest_digest"] != manifest_digest:
                    connection.rollback()
                    raise AdaptiveStoreError("graph manifest digest conflict")
                connection.commit()
                return self.heads(graph_id)
            connection.execute("INSERT INTO adaptive_graphs VALUES(?,?)", (graph_id, manifest_digest))
            for row in rows:
                atom_digest = _digest(row)
                connection.execute("INSERT INTO adaptive_atoms VALUES(?,?,?,?,?,?,?,?,?)", (
                    graph_id, row["uid"], 1, row["kind"], row["owner"], _bytes(row["refs"]),
                    _bytes(row["payload"]), atom_digest, None))
                connection.execute("INSERT INTO adaptive_heads VALUES(?,?,?,?,?,?)", (
                    graph_id, row["uid"], 1, row["kind"], row["owner"], atom_digest))
            connection.commit()
        return self.heads(graph_id)

    def _graph(self, connection: sqlite3.Connection, graph_id: str) -> None:
        if connection.execute("SELECT 1 FROM adaptive_graphs WHERE graph_id=?", (graph_id,)).fetchone() is None:
            raise AdaptiveStoreError("graph does not exist")

    @staticmethod
    def _head(row: sqlite3.Row) -> dict[str, Any]:
        return {key: row[key] for key in ("uid", "revision", "kind", "owner", "digest")}

    def head(self, graph_id: str, uid: str) -> dict[str, Any]:
        with self._connection() as connection:
            self._graph(connection, graph_id)
            row = connection.execute("SELECT uid,revision,kind,owner,atom_digest AS digest FROM adaptive_heads WHERE graph_id=? AND uid=?", (graph_id, uid)).fetchone()
            if row is None:
                raise AdaptiveStoreError("atom head does not exist")
            return self._head(row)

    def heads(self, graph_id: str, kind: str | None = None) -> list[dict[str, Any]]:
        with self._connection() as connection:
            self._graph(connection, graph_id)
            query = "SELECT uid,revision,kind,owner,atom_digest AS digest FROM adaptive_heads WHERE graph_id=?"
            values: tuple[Any, ...] = (graph_id,)
            if kind is not None:
                query += " AND kind=?"
                values += (kind,)
            return [self._head(row) for row in connection.execute(query + " ORDER BY uid", values)]

    def get_revision(self, graph_id: str, uid: str, revision: int) -> dict[str, Any]:
        if type(revision) is not int or revision < 1:
            raise AdaptiveStoreError("atom revision is invalid")
        with self._connection() as connection:
            self._graph(connection, graph_id)
            row = connection.execute("SELECT * FROM adaptive_atoms WHERE graph_id=? AND uid=? AND revision=?", (graph_id, uid, revision)).fetchone()
            if row is None:
                raise AdaptiveStoreError("atom revision does not exist")
            atom = _atom({"uid": row["uid"], "kind": row["kind"], "owner": row["owner"],
                          "refs": _load(bytes(row["refs_json"]), "refs"),
                          "payload": _load(bytes(row["payload_json"]), "payload")})
            if _digest(atom) != row["atom_digest"]:
                raise AdaptiveStoreError("stored atom digest mismatch")
            return {**atom, "revision": row["revision"], "digest": row["atom_digest"], "event_id": row["event_id"]}

    def rewrite(self, graph_id: str, *, event_id: str, expected: dict[str, int], atoms: list[dict[str, Any]], source: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(event_id, str) or not event_id or not isinstance(expected, dict) or not isinstance(source, dict):
            raise AdaptiveStoreError("rewrite identity is invalid")
        if any(not isinstance(uid, str) or not uid or type(revision) is not int or revision < 0 for uid, revision in expected.items()):
            raise AdaptiveStoreError("rewrite expectations are invalid")
        rows = [_atom(item) for item in atoms]
        if not rows or len({row["uid"] for row in rows}) != len(rows) or set(expected) != {row["uid"] for row in rows}:
            raise AdaptiveStoreError("rewrite atoms must exactly match expectations")
        intent = {"expected": expected, "atoms": rows, "source": source}
        intent_digest = _digest(intent)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._graph(connection, graph_id)
            prior = connection.execute("SELECT * FROM adaptive_events WHERE graph_id=? AND event_id=?", (graph_id, event_id)).fetchone()
            if prior is not None:
                if prior["intent_digest"] != intent_digest:
                    connection.rollback()
                    raise AdaptiveStoreError("event id was reused with a different intent")
                connection.commit()
                return self.get_event(graph_id, event_id)
            current = {row["uid"]: row for row in connection.execute("SELECT * FROM adaptive_heads WHERE graph_id=?", (graph_id,))}
            transaction_uids = {row["uid"] for row in rows}
            for row in rows:
                prior_head = current.get(row["uid"])
                wanted = expected[row["uid"]]
                if prior_head is None:
                    if wanted != 0:
                        connection.rollback()
                        raise AdaptiveStoreError("new atom must expect revision zero")
                elif prior_head["revision"] != wanted:
                    connection.rollback()
                    raise AdaptiveStoreError("head compare-and-swap conflict")
                elif prior_head["owner"] != row["owner"]:
                    connection.rollback()
                    raise AdaptiveStoreError("atom owner is immutable")
                elif prior_head["kind"] != row["kind"]:
                    connection.rollback()
                    raise AdaptiveStoreError("atom kind is immutable")
                for ref in row["refs"]:
                    if ref["uid"] not in current and ref["uid"] not in transaction_uids:
                        connection.rollback()
                        raise AdaptiveStoreError("rewrite reference is unresolved")
            consumed = [
                {"uid": row["uid"], "revision": row["revision"], "kind": row["kind"],
                 "owner": row["owner"], "digest": row["atom_digest"]}
                for row in current.values() if row["uid"] in expected
            ]
            produced: list[dict[str, Any]] = []
            for row in rows:
                prior_head = current.get(row["uid"])
                revision = 1 if prior_head is None else prior_head["revision"] + 1
                atom_digest = _digest(row)
                connection.execute("INSERT INTO adaptive_atoms VALUES(?,?,?,?,?,?,?,?,?)", (graph_id, row["uid"], revision, row["kind"], row["owner"], _bytes(row["refs"]), _bytes(row["payload"]), atom_digest, event_id))
                if prior_head is None:
                    connection.execute("INSERT INTO adaptive_heads VALUES(?,?,?,?,?,?)", (graph_id, row["uid"], revision, row["kind"], row["owner"], atom_digest))
                else:
                    connection.execute("UPDATE adaptive_heads SET revision=?,kind=?,owner=?,atom_digest=? WHERE graph_id=? AND uid=?", (revision, row["kind"], row["owner"], atom_digest, graph_id, row["uid"]))
                produced.append({"uid": row["uid"], "revision": revision, "kind": row["kind"], "owner": row["owner"], "digest": atom_digest})
            connection.execute("INSERT INTO adaptive_events VALUES(?,?,?,?,?,?)", (graph_id, event_id, intent_digest, _bytes(source), _bytes(consumed), _bytes(produced)))
            connection.commit()
        return {"event_id": event_id, "intent_digest": intent_digest, "consumed": consumed,
                "produced": produced, "output_heads": produced}

    def get_event(self, graph_id: str, event_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            self._graph(connection, graph_id)
            row = connection.execute("SELECT * FROM adaptive_events WHERE graph_id=? AND event_id=?", (graph_id, event_id)).fetchone()
            if row is None:
                raise AdaptiveStoreError("event does not exist")
            produced = _load(bytes(row["produced_json"]), "produced")
            return {"event_id": event_id, "intent_digest": row["intent_digest"],
                    "source": _load(bytes(row["source_json"]), "source"),
                    "consumed": _load(bytes(row["consumed_json"]), "consumed"),
                    "produced": produced, "output_heads": produced}

    def events(self, graph_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            self._graph(connection, graph_id)
            ids = [row["event_id"] for row in connection.execute("SELECT event_id FROM adaptive_events WHERE graph_id=? ORDER BY rowid", (graph_id,))]
        return [self.get_event(graph_id, event_id) for event_id in ids]
