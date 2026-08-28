from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import shutil

import pytest

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dnrd5.independent_actual_byte_judge import (
    ActualByteJudgeRefusal,
    _parse,
    _validate_atoms,
    _validate_canonical_journal_schedule,
    _validate_journal_wire_first,
    _validate_root,
    _validate_schema,
    judge_actual_byte_corpus,
)

FIXTURE = Path(__file__).parents[1] / "_research/dnrd5/vectors/actual_byte_corpus_v1"


def _copy(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / f"corpus-{sum(1 for _ in tmp_path.iterdir())}"
    shutil.copytree(FIXTURE, root)
    return root, parse_canonical((root / "manifest.json").read_bytes())


def _descriptor(raw: bytes, media: str) -> dict:
    return {"mediaType": media, "byteLength": len(raw), "sha256": sha256(raw).hexdigest()}


def _raw(root: Path, descriptor: dict) -> bytes:
    return (root / "blobs" / descriptor["sha256"]).read_bytes()


def _put(root: Path, manifest: dict, raw: bytes, media: str) -> dict:
    descriptor = _descriptor(raw, media)
    (root / "blobs" / descriptor["sha256"]).write_bytes(raw)
    if descriptor not in manifest["descriptorIndex"]:
        manifest["descriptorIndex"].append(descriptor)
        manifest["descriptorIndex"].sort(key=lambda row: f"{row['mediaType']}|{row['byteLength']}|{row['sha256']}")
    return descriptor


def _seal(root: Path, manifest: dict) -> None:
    """Re-encode the root after every logical mutation."""
    (root / "manifest.json").write_bytes(canonical_bytes(manifest))


def _refuses(root: Path, code: str) -> None:
    with pytest.raises(ActualByteJudgeRefusal) as caught:
        judge_actual_byte_corpus(root)
    assert caught.value.code == code


def _records(root: Path, listings: list[dict]) -> list[dict]:
    return [parse_canonical(_raw(root, row["record"])) for row in listings]


def _replace_records(root: Path, manifest: dict, listings: list[dict], records: list[dict]) -> None:
    for index, record in enumerate(records):
        media = listings[index]["record"]["mediaType"]
        listings[index]["record"] = _put(root, manifest, canonical_bytes(record), media)


def _replace_unreferenced_record(root: Path, manifest: dict, listing: dict, record: dict) -> None:
    old = listing["record"]
    listing["record"] = _put(root, manifest, canonical_bytes(record), old["mediaType"])
    manifest["descriptorIndex"].remove(old)
    (root / "blobs" / old["sha256"]).unlink()


def test_clean_fixture_requires_every_gate_to_pass() -> None:
    result = judge_actual_byte_corpus(FIXTURE)
    assert result.terminal == "FIXTURE_BYTE_CLOSURE_VALIDATED_NOT_PROVIDER_OCCURRENCE_OR_SCIENTIFIC_RESULT"
    assert result.root_sha256 == "ccf11bb67b406e226da7efc4b76c9512e7d581a54af109a650a914dbf8775271"
    assert result.logical_provider_binding_count == 99


def test_omission_and_addition_are_exact_blob_closure_refusals(tmp_path: Path) -> None:
    root, _ = _copy(tmp_path)
    next((root / "blobs").iterdir()).unlink()
    _refuses(root, "BLOB_MISSING")
    root, _ = _copy(tmp_path)
    (root / "blobs" / ("0" * 64)).write_bytes(b"extra")
    _refuses(root, "BLOB_CLOSURE_INVALID")


def test_root_and_blob_symlink_surfaces_are_closed(tmp_path: Path) -> None:
    root, _ = _copy(tmp_path)
    (root / "unbound.txt").write_text("extra", encoding="utf-8")
    _refuses(root, "ROOT_CLOSURE_INVALID")

    root, _ = _copy(tmp_path)
    manifest_target = tmp_path / "manifest-target.json"
    (root / "manifest.json").replace(manifest_target)
    (root / "manifest.json").symlink_to(manifest_target)
    _refuses(root, "ROOT_CLOSURE_INVALID")

    root, _ = _copy(tmp_path)
    blob = next((root / "blobs").iterdir())
    blob_target = tmp_path / f"{blob.name}.blob"
    blob.replace(blob_target)
    blob.symlink_to(blob_target)
    _refuses(root, "ROOT_CLOSURE_INVALID")


def test_unreachable_descriptor_and_blob_byte_drift_are_refused(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    _put(root, manifest, canonical_bytes({"unreachable": True}), "application/vnd.hswm.dnrd5.fixture+json")
    _seal(root, manifest)
    _refuses(root, "DESCRIPTOR_INDEX_INVALID")

    root, manifest = _copy(tmp_path)
    descriptor = manifest["descriptorIndex"][0]
    (root / "blobs" / descriptor["sha256"]).write_bytes(b"tampered")
    _refuses(root, "BLOB_DESCRIPTOR_MISMATCH")


def test_descriptor_and_arm_fork_swaps_reach_semantic_gates(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    atoms = manifest["core"]["atoms"]
    atoms[0]["envelope"] = atoms[1]["envelope"]
    _seal(root, manifest)
    _refuses(root, "ATOM_ENVELOPE_INVALID")
    root, manifest = _copy(tmp_path)
    rows = [row for row in manifest["core"]["lifecycleAdapter"] if row["bindingClass"] == "ASSIGNMENT_DERIVED"]
    rows[0]["bindings"]["fork"], rows[0]["bindings"]["assignment"] = rows[0]["bindings"]["assignment"], rows[0]["bindings"]["fork"]
    _seal(root, manifest)
    _refuses(root, "LIFECYCLE_ADAPTER_INVALID")


def test_resealed_journal_predecessor_and_decision_effect_mutations(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    listings = manifest["core"]["journal"]
    records = _records(root, listings)
    records[2]["predecessor"] = listings[0]["record"]
    _replace_records(root, manifest, listings, records)
    _seal(root, manifest)
    _refuses(root, "JOURNAL_PREDECESSOR_INVALID")
    root, manifest = _copy(tmp_path)
    listings = manifest["core"]["journal"]
    records = _records(root, listings)
    effect = next(record for record in records if len(record.get("writeBindings", [])) == 2)
    effect["receipt"]["writeSet"] = list(reversed(effect["receipt"]["writeSet"]))
    _replace_records(root, manifest, listings, records)
    _seal(root, manifest)
    _refuses(root, "JOURNAL_RECEIPT_INVALID")


def test_provider_count_order_projection_and_hidden_leak_mutations(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    manifest["core"]["calls"].pop()
    _seal(root, manifest)
    _refuses(root, "PROVIDER_CARDINALITY_INVALID")
    root, manifest = _copy(tmp_path)
    calls = manifest["core"]["calls"]
    calls[0], calls[1] = calls[1], calls[0]
    _seal(root, manifest)
    _refuses(root, "PROVIDER_GRAMMAR_INVALID")
    root, manifest = _copy(tmp_path)
    call = manifest["core"]["calls"][0]
    call["contents"]["request-projection"] = call["contents"]["transmitted-request"]
    _seal(root, manifest)
    _refuses(root, "PROVIDER_PROJECTION_INVALID")
    root, manifest = _copy(tmp_path)
    call = manifest["core"]["calls"][0]
    transmitted = parse_canonical(_raw(root, call["contents"]["transmitted-request"]))
    transmitted["privateBinding"] = "private-leak"
    descriptor = _put(root, manifest, canonical_bytes(transmitted), call["contents"]["transmitted-request"]["mediaType"])
    call["contents"]["transmitted-request"] = descriptor
    receipt = parse_canonical(_raw(root, call["receipt"]))
    receipt["contents"]["transmitted-request"] = descriptor
    call["receipt"] = _put(root, manifest, canonical_bytes(receipt), call["receipt"]["mediaType"])
    ledger_listings = manifest["core"]["fixtureLedger"]
    ledger = _records(root, ledger_listings)
    for record in ledger:
        if record["callId"] == call["callId"]:
            record["receipt"] = call["receipt"]
    _replace_records(root, manifest, ledger_listings, ledger)
    _seal(root, manifest)
    _refuses(root, "PROVIDER_HIDDEN_LEAK")


def test_provider_fixture_identity_is_ordinal_bound(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    call = manifest["core"]["calls"][0]
    receipt = parse_canonical(_raw(root, call["receipt"]))
    receipt["sessionId"] = "arbitrary-but-unique"
    call["receipt"] = _put(root, manifest, canonical_bytes(receipt), call["receipt"]["mediaType"])
    _seal(root, manifest)
    _refuses(root, "PROVIDER_IDENTITY_INVALID")


def test_root_identity_change_is_not_masked_by_rehash(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    manifest["expectedTerminal"] = "OVERRIDDEN"
    _seal(root, manifest)
    _refuses(root, "MANIFEST_IDENTITY_INVALID")


def test_lifecycle_descriptor_cannot_gain_an_alternate_media_identity(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    lifecycle = manifest["core"]["lifecycle"]
    manifest["core"]["lifecycle"] = _put(root, manifest, _raw(root, lifecycle), "application/octet-stream")
    _seal(root, manifest)
    _refuses(root, "DESCRIPTOR_INDEX_INVALID")


def test_evidence_claim_boundary_and_ledger_predecessor_are_bound(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    evidence = manifest["core"]["evidenceBindings"]["evaluator-input"]
    value = parse_canonical(_raw(root, evidence))
    value["claimBoundary"] = "PROMOTED"
    manifest["core"]["evidenceBindings"]["evaluator-input"] = _put(root, manifest, canonical_bytes(value), evidence["mediaType"])
    _seal(root, manifest)
    _refuses(root, "EVIDENCE_BINDING_INVALID")

    root, manifest = _copy(tmp_path)
    listing = manifest["core"]["fixtureLedger"][-1]
    record = parse_canonical(_raw(root, listing["record"]))
    record["predecessor"] = None
    listing["record"] = _put(root, manifest, canonical_bytes(record), listing["record"]["mediaType"])
    _seal(root, manifest)
    _refuses(root, "PROVIDER_LEDGER_INVALID")


def test_fresh_probe_semantic_reference_cannot_use_activation_commitment(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    atoms = manifest["core"]["atoms"]
    trajectory = next(row for row in atoms if row["kind"] == "probe_trajectory")
    activation_probe = next(row for row in atoms if row["kind"] == "probe_commitment")["key"]
    envelope = parse_canonical(_raw(root, trajectory["envelope"]))
    probe_reference = next(ref for ref in envelope["references"] if ref["role"] == "role:dnrd5:v2:probe")
    probe_reference["target"] = activation_probe
    trajectory["envelope"] = _put(root, manifest, canonical_bytes(envelope), trajectory["envelope"]["mediaType"])
    _seal(root, manifest)
    _refuses(root, "SEMANTIC_JOIN_INVALID")


def test_independent_parser_enforces_frozen_byte_depth_and_node_bounds() -> None:
    with pytest.raises(ActualByteJudgeRefusal, match="CANONICAL_JSON_LIMIT_EXCEEDED"):
        _parse(b'"' + b"a" * (1 << 20) + b'"', "oversized")
    with pytest.raises(ActualByteJudgeRefusal, match="CANONICAL_JSON_LIMIT_EXCEEDED"):
        _parse(b"[" * 129 + b"0" + b"]" * 129, "deep")
    with pytest.raises(ActualByteJudgeRefusal, match="CANONICAL_JSON_LIMIT_EXCEEDED"):
        _parse(b"[" + b",".join([b"0"] * 100_001) + b"]", "many-nodes")
    with pytest.raises(ActualByteJudgeRefusal, match="CANONICAL_JSON_INVALID"):
        _parse(b'"\\ud800"', "lone-surrogate-value")


def test_resealed_active_sham_validation_swap_reaches_lifecycle_gate(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    rows = [row for row in manifest["core"]["lifecycleAdapter"] if row["bindingClass"] == "ARM_TRANSITION_DERIVED"]
    rows[0]["bindings"]["validation"], rows[1]["bindings"]["validation"] = rows[1]["bindings"]["validation"], rows[0]["bindings"]["validation"]
    _seal(root, manifest)
    _refuses(root, "LIFECYCLE_ADAPTER_INVALID")


def test_resealed_direct_feedback_swap_reaches_lifecycle_gate(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    rows = [row for row in manifest["core"]["lifecycleAdapter"] if row["event"] == "ESCROW_PLACEBO_AND_FEEDBACK_ASSIGNMENTS" and row["artifactId"].endswith(("03:feedback_assignment", "04:feedback_assignment"))]
    assert len(rows) == 2
    rows[0]["bindings"]["atom"], rows[1]["bindings"]["atom"] = rows[1]["bindings"]["atom"], rows[0]["bindings"]["atom"]
    _seal(root, manifest)
    _refuses(root, "LIFECYCLE_ADAPTER_INVALID")


def test_atom_listing_deletion_reaches_exact_atom_closure_gate(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    manifest["core"]["atoms"].pop()
    _seal(root, manifest)
    _refuses(root, "ATOM_CLOSURE_INVALID")


def test_atom_key_uses_the_cross_language_identifier_domain(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    manifest["core"]["atoms"][0]["key"]["atomUid"] = "invalid\nuid"
    _seal(root, manifest)
    _refuses(root, "ATOM_KEY_INVALID")


def test_exact_count_mutation_reaches_exact_counts_gate(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    manifest["core"]["exactCounts"]["callReceipts"] = 0
    _seal(root, manifest)
    _refuses(root, "EXACT_COUNTS_INVALID")


def test_evidence_role_set_is_exact(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    manifest["core"]["evidenceBindings"].pop("evaluator-input")
    _seal(root, manifest)
    _refuses(root, "EVIDENCE_BINDING_INVALID")


def test_journal_listing_shape_is_exact(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    manifest["core"]["journal"][1]["fixtureTag"] = "bypass"
    _seal(root, manifest)
    _refuses(root, "JOURNAL_WIRE_GRAMMAR_REQUIRED")


def test_terminal_commit_contract_and_encoding_are_replayed(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    listing = manifest["core"]["journal"][-1]
    old = listing["record"]
    record = parse_canonical(_raw(root, old))
    record["contractVersion"] = "attacker-contract"
    _replace_unreferenced_record(root, manifest, listing, record)
    _seal(root, manifest)
    _refuses(root, "JOURNAL_PREDECESSOR_INVALID")


def test_terminal_read_set_state_and_write_order_are_replayed(tmp_path: Path) -> None:
    root, manifest = _copy(tmp_path)
    listing = manifest["core"]["journal"][-1]
    record = parse_canonical(_raw(root, listing["record"]))
    assert record["receipt"]["readSet"]
    record["receipt"]["readSet"].pop()
    _replace_unreferenced_record(root, manifest, listing, record)
    _seal(root, manifest)
    _refuses(root, "JOURNAL_RECEIPT_INVALID")

    root, manifest = _copy(tmp_path)
    listing = manifest["core"]["journal"][-1]
    record = parse_canonical(_raw(root, listing["record"]))
    record["resultingStateSha256"] = "0" * 64
    listing["state"] = record["resultingStateSha256"]
    _replace_unreferenced_record(root, manifest, listing, record)
    _seal(root, manifest)
    _refuses(root, "JOURNAL_STATE_REPLAY_INVALID")

    root, manifest = _copy(tmp_path)
    listing = manifest["core"]["journal"][-1]
    record = parse_canonical(_raw(root, listing["record"]))
    record["writeBindings"].reverse()
    _replace_unreferenced_record(root, manifest, listing, record)
    _seal(root, manifest)
    _refuses(root, "JOURNAL_WRITE_BINDING_INVALID")


def test_arm_and_ready_queue_schedule_permutations_are_refused() -> None:
    _, core, blobs = _validate_root(FIXTURE)
    schema = _validate_schema(core, blobs)
    atoms = _validate_atoms(core, blobs, schema)
    _, _, clean_commits = _validate_journal_wire_first(core, blobs, schema)

    arm_permuted = list(clean_commits)
    arm_permuted[48:50], arm_permuted[51:53] = clean_commits[51:53], clean_commits[48:50]
    with pytest.raises(ActualByteJudgeRefusal, match="JOURNAL_CHRONOLOGY_INVALID"):
        _validate_canonical_journal_schedule(core, atoms, arm_permuted)

    support_permuted = list(clean_commits)
    support_permuted[3], support_permuted[9] = support_permuted[9], support_permuted[3]
    with pytest.raises(ActualByteJudgeRefusal, match="JOURNAL_CHRONOLOGY_INVALID"):
        _validate_canonical_journal_schedule(core, atoms, support_permuted)
