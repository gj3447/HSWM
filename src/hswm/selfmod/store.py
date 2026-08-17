"""Durable content-addressed state and monotonic activation CAS for HSWM."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any, Mapping, Sequence

from .contracts import (
    ActiveSnapshot,
    ActivationReceipt,
    CognitiveToken,
    MutationProposal,
    SelfModelPolicy,
    SelfModelSnapshot,
    activation_from_mapping,
    apply_mutation,
    canonical_json_bytes,
    canonical_sha256,
    make_activation_receipt,
    make_snapshot,
    mutation_from_mapping,
    snapshot_from_mapping,
    token_from_mapping,
)


STORE_SCHEMA_VERSION = 2


class SelfModelStoreError(RuntimeError):
    pass


class StoreIntegrityError(SelfModelStoreError):
    pass


class StaleGenerationError(SelfModelStoreError):
    pass


class IdentityConflictError(SelfModelStoreError):
    pass


class MissingSourceTokenError(SelfModelStoreError):
    pass


def _json(raw: bytes, label: str) -> Mapping[str, Any]:
    try:
        value = __import__("json").loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise StoreIntegrityError(f"invalid stored {label} JSON: {error}") from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise StoreIntegrityError(f"stored {label} JSON is not canonical")
    return value


class SQLiteSelfModelStore:
    """Empty-genesis store for agent-authored snapshots and exact restoration."""

    def __init__(self, path: str | Path, *, policy: SelfModelPolicy) -> None:
        self.path = Path(path)
        self.policy = policy
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=10.0,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        policy_raw = canonical_json_bytes(self.policy.canonical())
        genesis = make_snapshot()
        if len(canonical_json_bytes(genesis.canonical())) > self.policy.max_snapshot_bytes:
            raise SelfModelStoreError("policy cannot admit the empty genesis snapshot")
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, STORE_SCHEMA_VERSION):
                raise StoreIntegrityError(f"unsupported store schema {version}")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS store_authority (
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                    policy_json BLOB NOT NULL,
                    policy_sha256 TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cognitive_tokens (
                    token_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    position INTEGER NOT NULL CHECK(position >= 0),
                    token_json BLOB NOT NULL,
                    token_sha256 TEXT NOT NULL,
                    UNIQUE(episode_id, position)
                );
                CREATE TABLE IF NOT EXISTS self_model_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    snapshot_json BLOB NOT NULL,
                    snapshot_sha256 TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS active_self_model (
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                    snapshot_id TEXT NOT NULL,
                    generation INTEGER NOT NULL CHECK(generation >= 0),
                    FOREIGN KEY(snapshot_id)
                        REFERENCES self_model_snapshots(snapshot_id)
                );
                CREATE TABLE IF NOT EXISTS self_mutations (
                    mutation_id TEXT PRIMARY KEY,
                    mutation_json BLOB NOT NULL,
                    mutation_sha256 TEXT NOT NULL,
                    target_snapshot_id TEXT NOT NULL,
                    activation_id TEXT NOT NULL UNIQUE,
                    FOREIGN KEY(target_snapshot_id)
                        REFERENCES self_model_snapshots(snapshot_id)
                );
                CREATE TABLE IF NOT EXISTS self_activations (
                    active_generation INTEGER PRIMARY KEY,
                    activation_id TEXT NOT NULL UNIQUE,
                    activation_json BLOB NOT NULL,
                    activation_sha256 TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS activation_requests (
                    request_id TEXT PRIMARY KEY,
                    request_json BLOB NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    activation_id TEXT NOT NULL UNIQUE
                );
                """
            )
            connection.execute(f"PRAGMA user_version={STORE_SCHEMA_VERSION}")
            connection.execute("BEGIN IMMEDIATE")
            authority = connection.execute(
                "SELECT policy_json,policy_sha256 FROM store_authority WHERE singleton=1"
            ).fetchone()
            if authority is None:
                connection.execute(
                    "INSERT INTO store_authority VALUES(1,?,?)",
                    (policy_raw, self.policy.policy_sha256),
                )
            elif (
                bytes(authority["policy_json"]) != policy_raw
                or authority["policy_sha256"] != self.policy.policy_sha256
            ):
                connection.rollback()
                raise StoreIntegrityError("configured authority differs from stored policy")

            self._insert_snapshot_in_tx(connection, genesis)
            active = connection.execute(
                "SELECT snapshot_id,generation FROM active_self_model WHERE singleton=1"
            ).fetchone()
            if active is None:
                connection.execute(
                    "INSERT INTO active_self_model VALUES(1,?,0)",
                    (genesis.snapshot_id,),
                )
                active = connection.execute(
                    "SELECT snapshot_id,generation FROM active_self_model WHERE singleton=1"
                ).fetchone()
            if active is None:
                connection.rollback()
                raise StoreIntegrityError("active snapshot initialization failed")
            self._load_snapshot_in_tx(connection, active["snapshot_id"])
            self._validate_history_in_tx(
                connection,
                active_snapshot_id=active["snapshot_id"],
                active_generation=active["generation"],
            )
            connection.commit()

    def _insert_snapshot_in_tx(
        self, connection: sqlite3.Connection, snapshot: SelfModelSnapshot
    ) -> None:
        # Frozen dataclasses may still contain caller-owned mutable JSON values.
        # Reparse at the durable boundary so an object mutated after construction
        # cannot poison the content-addressed store.
        snapshot = snapshot_from_mapping(snapshot.canonical())
        raw = canonical_json_bytes(snapshot.canonical())
        digest = canonical_sha256(snapshot.canonical())
        prior = connection.execute(
            "SELECT snapshot_json,snapshot_sha256 FROM self_model_snapshots WHERE snapshot_id=?",
            (snapshot.snapshot_id,),
        ).fetchone()
        if prior is not None:
            if bytes(prior["snapshot_json"]) != raw or prior["snapshot_sha256"] != digest:
                raise IdentityConflictError("snapshot id carries different bytes")
            return
        connection.execute(
            "INSERT INTO self_model_snapshots VALUES(?,?,?)",
            (snapshot.snapshot_id, raw, digest),
        )

    def _load_snapshot_in_tx(
        self, connection: sqlite3.Connection, snapshot_id: str
    ) -> SelfModelSnapshot:
        row = connection.execute(
            "SELECT * FROM self_model_snapshots WHERE snapshot_id=?", (snapshot_id,)
        ).fetchone()
        if row is None:
            raise SelfModelStoreError(f"unknown snapshot {snapshot_id!r}")
        raw = bytes(row["snapshot_json"])
        value = _json(raw, "snapshot")
        if canonical_sha256(value) != row["snapshot_sha256"]:
            raise StoreIntegrityError("stored snapshot digest mismatch")
        try:
            snapshot = snapshot_from_mapping(value)
        except ValueError as error:
            raise StoreIntegrityError(str(error)) from error
        if snapshot.snapshot_id != row["snapshot_id"]:
            raise StoreIntegrityError("snapshot row identity mismatch")
        return snapshot

    def load_snapshot(self, snapshot_id: str) -> SelfModelSnapshot:
        with self._connect() as connection:
            return self._load_snapshot_in_tx(connection, snapshot_id)

    def _active_row(self, connection: sqlite3.Connection) -> sqlite3.Row:
        row = connection.execute(
            "SELECT snapshot_id,generation FROM active_self_model WHERE singleton=1"
        ).fetchone()
        if row is None:
            raise StoreIntegrityError("active snapshot pointer is missing")
        return row

    def active_snapshot(self) -> ActiveSnapshot:
        with self._connect() as connection:
            row = self._active_row(connection)
            snapshot = self._load_snapshot_in_tx(connection, row["snapshot_id"])
        return ActiveSnapshot(
            snapshot=snapshot, generation=row["generation"], policy=self.policy
        )

    def append_tokens(self, tokens: Sequence[CognitiveToken]) -> None:
        if not tokens:
            return
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for token in tokens:
                    token = token_from_mapping(token.canonical())
                    raw = canonical_json_bytes(token.canonical())
                    if len(raw) > self.policy.max_token_bytes:
                        raise SelfModelStoreError("token exceeds byte budget")
                    digest = canonical_sha256(token.canonical())
                    prior = connection.execute(
                        "SELECT token_json,token_sha256 FROM cognitive_tokens WHERE token_id=?",
                        (token.token_id,),
                    ).fetchone()
                    if prior is not None:
                        if (
                            bytes(prior["token_json"]) != raw
                            or prior["token_sha256"] != digest
                        ):
                            raise IdentityConflictError(
                                "token id carries different canonical bytes"
                            )
                        continue
                    occupied = connection.execute(
                        "SELECT token_id FROM cognitive_tokens WHERE episode_id=? AND position=?",
                        (token.episode_id, token.position),
                    ).fetchone()
                    if occupied is not None:
                        raise IdentityConflictError(
                            "episode position already carries another token"
                        )
                    connection.execute(
                        "INSERT INTO cognitive_tokens VALUES(?,?,?,?,?)",
                        (
                            token.token_id,
                            token.episode_id,
                            token.position,
                            raw,
                            digest,
                        ),
                    )
                connection.commit()
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise

    def _load_token_in_tx(
        self, connection: sqlite3.Connection, token_id: str
    ) -> CognitiveToken:
        row = connection.execute(
            "SELECT * FROM cognitive_tokens WHERE token_id=?", (token_id,)
        ).fetchone()
        if row is None:
            raise MissingSourceTokenError(token_id)
        raw = bytes(row["token_json"])
        value = _json(raw, "token")
        if canonical_sha256(value) != row["token_sha256"]:
            raise StoreIntegrityError("stored token digest mismatch")
        try:
            token = token_from_mapping(value)
        except ValueError as error:
            raise StoreIntegrityError(str(error)) from error
        if (
            token.token_id != row["token_id"]
            or token.episode_id != row["episode_id"]
            or token.position != row["position"]
        ):
            raise StoreIntegrityError("token columns differ from canonical bytes")
        return token

    def load_token(self, token_id: str) -> CognitiveToken:
        with self._connect() as connection:
            return self._load_token_in_tx(connection, token_id)

    def _require_sources(
        self, connection: sqlite3.Connection, token_ids: Sequence[str]
    ) -> None:
        for token_id in sorted(set(token_ids)):
            try:
                self._load_token_in_tx(connection, token_id)
            except MissingSourceTokenError as error:
                raise MissingSourceTokenError(
                    f"source token {token_id!r} is not stored"
                ) from error

    def _load_activation_in_tx(
        self, connection: sqlite3.Connection, activation_id: str
    ) -> ActivationReceipt:
        row = connection.execute(
            "SELECT * FROM self_activations WHERE activation_id=?", (activation_id,)
        ).fetchone()
        if row is None:
            raise StoreIntegrityError("activation receipt is missing")
        raw = bytes(row["activation_json"])
        value = _json(raw, "activation")
        if canonical_sha256(value) != row["activation_sha256"]:
            raise StoreIntegrityError("activation digest mismatch")
        try:
            receipt = activation_from_mapping(value)
        except ValueError as error:
            raise StoreIntegrityError(str(error)) from error
        if (
            receipt.activation_id != row["activation_id"]
            or receipt.active_generation != row["active_generation"]
        ):
            raise StoreIntegrityError("activation columns differ from receipt")
        return receipt

    def _validate_history_in_tx(
        self,
        connection: sqlite3.Connection,
        *,
        active_snapshot_id: str,
        active_generation: int,
    ) -> None:
        rows = connection.execute(
            "SELECT activation_id FROM self_activations ORDER BY active_generation"
        ).fetchall()
        if len(rows) != active_generation:
            raise StoreIntegrityError("activation history length differs from generation")

        expected_base = make_snapshot().snapshot_id
        for expected_generation, row in enumerate(rows, start=1):
            receipt = self._load_activation_in_tx(connection, row["activation_id"])
            if (
                receipt.base_snapshot_id != expected_base
                or receipt.active_generation != expected_generation
                or receipt.base_generation != expected_generation - 1
            ):
                raise StoreIntegrityError("activation history is not one continuous chain")
            self._load_snapshot_in_tx(connection, receipt.base_snapshot_id)
            self._load_snapshot_in_tx(connection, receipt.active_snapshot_id)

            if receipt.mutation_id is not None:
                mutation_row = connection.execute(
                    "SELECT * FROM self_mutations WHERE mutation_id=?",
                    (receipt.mutation_id,),
                ).fetchone()
                if mutation_row is None:
                    raise StoreIntegrityError("mutation activation lacks its proposal")
                mutation_raw = bytes(mutation_row["mutation_json"])
                mutation_value = _json(mutation_raw, "mutation")
                if canonical_sha256(mutation_value) != mutation_row["mutation_sha256"]:
                    raise StoreIntegrityError("stored mutation digest mismatch")
                try:
                    mutation = mutation_from_mapping(mutation_value)
                except ValueError as error:
                    raise StoreIntegrityError(str(error)) from error
                if (
                    mutation.mutation_id != mutation_row["mutation_id"]
                    or mutation_row["activation_id"] != receipt.activation_id
                    or mutation_row["target_snapshot_id"]
                    != receipt.active_snapshot_id
                    or mutation.base_snapshot_id != receipt.base_snapshot_id
                    or mutation.expected_generation != receipt.base_generation
                    or mutation.author_id != receipt.author_id
                    or mutation.source_token_ids != receipt.source_token_ids
                ):
                    raise StoreIntegrityError(
                        "mutation row and activation receipt disagree"
                    )
            else:
                request_row = connection.execute(
                    "SELECT * FROM activation_requests WHERE activation_id=?",
                    (receipt.activation_id,),
                ).fetchone()
                if request_row is None:
                    raise StoreIntegrityError("direct activation lacks its request")
                request_raw = bytes(request_row["request_json"])
                request_value = _json(request_raw, "activation request")
                if (
                    canonical_sha256(request_value) != request_row["request_sha256"]
                    or canonical_sha256(request_value) != request_row["request_id"]
                    or request_value.get("snapshot_id")
                    != receipt.active_snapshot_id
                    or request_value.get("expected_generation")
                    != receipt.base_generation
                    or request_value.get("reason") != receipt.reason
                    or request_value.get("author_id") != receipt.author_id
                    or tuple(request_value.get("source_token_ids", ()))
                    != receipt.source_token_ids
                ):
                    raise StoreIntegrityError(
                        "activation request and receipt disagree"
                    )
            self._require_sources(connection, receipt.source_token_ids)
            expected_base = receipt.active_snapshot_id

        if expected_base != active_snapshot_id:
            raise StoreIntegrityError("active pointer differs from activation history")

    def _activate_in_tx(
        self,
        connection: sqlite3.Connection,
        *,
        base_snapshot_id: str,
        base_generation: int,
        target_snapshot_id: str,
        reason: str,
        mutation_id: str | None,
        author_id: str,
        source_token_ids: Sequence[str],
    ) -> ActivationReceipt:
        if target_snapshot_id == base_snapshot_id:
            raise SelfModelStoreError("activation target is already active")
        self._load_snapshot_in_tx(connection, target_snapshot_id)
        receipt = make_activation_receipt(
            reason=reason,
            base_snapshot_id=base_snapshot_id,
            base_generation=base_generation,
            active_snapshot_id=target_snapshot_id,
            mutation_id=mutation_id,
            author_id=author_id,
            source_token_ids=source_token_ids,
        )
        changed = connection.execute(
            """
            UPDATE active_self_model
            SET snapshot_id=?,generation=?
            WHERE singleton=1 AND snapshot_id=? AND generation=?
            """,
            (
                target_snapshot_id,
                receipt.active_generation,
                base_snapshot_id,
                base_generation,
            ),
        ).rowcount
        if changed != 1:
            raise StaleGenerationError("active snapshot generation changed")
        raw = canonical_json_bytes(receipt.canonical())
        connection.execute(
            "INSERT INTO self_activations VALUES(?,?,?,?)",
            (
                receipt.active_generation,
                receipt.activation_id,
                raw,
                canonical_sha256(receipt.canonical()),
            ),
        )
        return receipt

    def commit(self, proposal: MutationProposal) -> ActivationReceipt:
        proposal = mutation_from_mapping(proposal.canonical())
        mutation_raw = canonical_json_bytes(proposal.canonical())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                prior = connection.execute(
                    "SELECT * FROM self_mutations WHERE mutation_id=?",
                    (proposal.mutation_id,),
                ).fetchone()
                if prior is not None:
                    if (
                        bytes(prior["mutation_json"]) != mutation_raw
                        or prior["mutation_sha256"]
                        != canonical_sha256(proposal.canonical())
                    ):
                        raise IdentityConflictError(
                            "mutation id carries different canonical bytes"
                        )
                    receipt = self._load_activation_in_tx(
                        connection, prior["activation_id"]
                    )
                    if (
                        receipt.mutation_id != proposal.mutation_id
                        or receipt.active_snapshot_id != prior["target_snapshot_id"]
                        or receipt.base_snapshot_id != proposal.base_snapshot_id
                        or receipt.base_generation != proposal.expected_generation
                        or receipt.author_id != proposal.author_id
                        or receipt.source_token_ids != proposal.source_token_ids
                    ):
                        raise StoreIntegrityError(
                            "stored mutation and activation receipt disagree"
                        )
                    self._load_snapshot_in_tx(
                        connection, prior["target_snapshot_id"]
                    )
                    connection.commit()
                    return receipt

                source_ids = set(proposal.source_token_ids)
                for memory in proposal.upsert_memories:
                    if not set(memory.source_token_ids) <= source_ids:
                        raise SelfModelStoreError(
                            "memory provenance exceeds the mutation source scope"
                        )
                    source_ids.update(memory.source_token_ids)
                self._require_sources(connection, tuple(source_ids))
                active = self._active_row(connection)
                if (
                    active["snapshot_id"] != proposal.base_snapshot_id
                    or active["generation"] != proposal.expected_generation
                ):
                    raise StaleGenerationError("mutation lost the active-state CAS")
                base = self._load_snapshot_in_tx(
                    connection, proposal.base_snapshot_id
                )
                target = apply_mutation(base, proposal, self.policy)
                self._insert_snapshot_in_tx(connection, target)
                receipt = self._activate_in_tx(
                    connection,
                    base_snapshot_id=base.snapshot_id,
                    base_generation=proposal.expected_generation,
                    target_snapshot_id=target.snapshot_id,
                    reason="SELF_AUTHORED_MUTATION",
                    mutation_id=proposal.mutation_id,
                    author_id=proposal.author_id,
                    source_token_ids=proposal.source_token_ids,
                )
                connection.execute(
                    "INSERT INTO self_mutations VALUES(?,?,?,?,?)",
                    (
                        proposal.mutation_id,
                        mutation_raw,
                        canonical_sha256(proposal.canonical()),
                        target.snapshot_id,
                        receipt.activation_id,
                    ),
                )
                connection.commit()
                return receipt
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise

    def activate_snapshot(
        self,
        snapshot_id: str,
        *,
        expected_generation: int,
        reason: str,
        author_id: str,
        source_token_ids: Sequence[str],
    ) -> ActivationReceipt:
        request = {
            "snapshot_id": snapshot_id,
            "expected_generation": expected_generation,
            "reason": reason,
            "author_id": author_id,
            "source_token_ids": sorted(source_token_ids),
        }
        request_raw = canonical_json_bytes(request)
        request_id = canonical_sha256(request)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                prior = connection.execute(
                    "SELECT * FROM activation_requests WHERE request_id=?",
                    (request_id,),
                ).fetchone()
                if prior is not None:
                    if (
                        bytes(prior["request_json"]) != request_raw
                        or prior["request_sha256"] != request_id
                    ):
                        raise IdentityConflictError(
                            "activation request id carries different bytes"
                        )
                    receipt = self._load_activation_in_tx(
                        connection, prior["activation_id"]
                    )
                    if (
                        receipt.base_generation != expected_generation
                        or receipt.active_snapshot_id != snapshot_id
                        or receipt.reason != reason
                        or receipt.author_id != author_id
                        or receipt.source_token_ids
                        != tuple(sorted(source_token_ids))
                        or receipt.mutation_id is not None
                    ):
                        raise StoreIntegrityError(
                            "activation request and receipt disagree"
                        )
                    connection.commit()
                    return receipt
                self._require_sources(connection, source_token_ids)
                active = self._active_row(connection)
                if active["generation"] != expected_generation:
                    raise StaleGenerationError("activation lost the generation CAS")
                receipt = self._activate_in_tx(
                    connection,
                    base_snapshot_id=active["snapshot_id"],
                    base_generation=expected_generation,
                    target_snapshot_id=snapshot_id,
                    reason=reason,
                    mutation_id=None,
                    author_id=author_id,
                    source_token_ids=source_token_ids,
                )
                connection.execute(
                    "INSERT INTO activation_requests VALUES(?,?,?,?)",
                    (
                        request_id,
                        request_raw,
                        canonical_sha256(request),
                        receipt.activation_id,
                    ),
                )
                connection.commit()
                return receipt
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise

    def activation_history(self) -> tuple[ActivationReceipt, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT activation_id FROM self_activations ORDER BY active_generation"
            ).fetchall()
            return tuple(
                self._load_activation_in_tx(connection, row["activation_id"])
                for row in rows
            )

    def activation_count(self) -> int:
        with self._connect() as connection:
            return int(
                connection.execute("SELECT COUNT(*) FROM self_activations").fetchone()[
                    0
                ]
            )

    def token_count(self) -> int:
        with self._connect() as connection:
            return int(
                connection.execute("SELECT COUNT(*) FROM cognitive_tokens").fetchone()[
                    0
                ]
            )

    def snapshot_count(self) -> int:
        with self._connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM self_model_snapshots"
                ).fetchone()[0]
            )

    def close(self) -> None:
        """Connections are per-operation; present for a uniform store API."""

    def __enter__(self) -> "SQLiteSelfModelStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


__all__ = [
    "IdentityConflictError",
    "MissingSourceTokenError",
    "SQLiteSelfModelStore",
    "STORE_SCHEMA_VERSION",
    "SelfModelStoreError",
    "StaleGenerationError",
    "StoreIntegrityError",
]
