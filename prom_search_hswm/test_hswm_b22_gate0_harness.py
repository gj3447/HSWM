#!/usr/bin/env python3
"""Synthetic conformance and injected-negative tests for B2.2 Gate 0."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import hswm_b22_gate0_harness as gate0

from hswm_b22_gate0_harness import (
    ACCEPTANCE_ROLES,
    ARRAY_FILES,
    MANIFEST_FILE,
    PackIntegrityError,
    ReplayMismatch,
    _canonical_bytes,
    _compiled_semantic_sha256,
    _json_sha256,
    _producer_hashes,
    _write_frozen_reference,
    _unsealed_manifest,
    accept_gate0_bundle,
    compile_full_candidate_pack,
    compare_b21_scorepack,
    compare_frozen_b2,
    create_acceptance_lock,
    load_feature_view,
    sha256_file,
    verify_pack,
    write_pack,
)
from prom_b2_crossfield_merge import finding_text, title_parity
from prom_b21_learned_router import (
    compile_scorepack,
    directory_manifest,
    frozen_b2_reference,
    normalize_rows,
    write_scorepack,
)


def hash_embed(texts: list[str]) -> np.ndarray:
    out = []
    for text in texts:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector = np.asarray([byte - 127.5 for byte in digest], dtype=np.float64)
        vector /= math.sqrt(float(vector @ vector))
        out.append(vector)
    return np.vstack(out)


def titles_by_parity(n: int = 80) -> tuple[list[str], list[str]]:
    left, right = [], []
    for index in range(n):
        title = f"Title{index}"
        (left if title_parity(title) == "A" else right).append(title)
    return left, right


TA, TB = titles_by_parity()


def mk_row(row_id: str, question: str, pairs: list[tuple[str, str]],
           supporting: list[str]) -> dict:
    return {
        "id": row_id,
        "question": question,
        "answer": "answer",
        "type": "compositional",
        "supporting_facts": {"title": supporting,
                             "sent_id": [0] * len(supporting)},
        "context": {"title": [title for title, _ in pairs],
                    "sentences": [[body] for _, body in pairs]},
    }


@pytest.fixture
def raw_rows() -> list[dict]:
    shared = "Zorblax"
    return [
        mk_row(
            "q-cross-1",
            finding_text(TA[0], f"{shared} visited Mereworth."),
            [(TA[0], f"{shared} visited Mereworth."),
             (TB[0], f"{shared} founded Blergstad."),
             (TA[1], "Alpha Person wrote a book."),
             (TB[1], "Beta Person sailed away.")],
            [TA[0], TB[0]],
        ),
        mk_row(
            "q-cross-2",
            "Where did Zorblax travel next?",
            [(TA[2], f"{shared} met Gamma Person."),
             (TB[2], f"Gamma Person entered Delta City."),
             (TA[3], "Noise Person stayed home."),
             (TB[3], "Other Person slept.")],
            [TA[2], TB[2]],
        ),
        mk_row(
            "q-in-1",
            finding_text(TA[4], "Frobnak painted Vexampolis."),
            [(TA[4], "Frobnak painted Vexampolis."),
             (TA[5], "Frobnak died in Vexampolis."),
             (TB[4], "Quux Person hummed a tune.")],
            [TA[4], TA[5]],
        ),
    ]


def provenance() -> dict:
    return {
        "dataset_sha256": "a" * 64,
        "model_snapshot_sha256": "b" * 64,
        "producer_sha256": {"synthetic-test": "c" * 64},
    }


def compiled(raw_rows: list[dict]):
    queries, pool = normalize_rows(raw_rows, "2wiki")
    pack = compile_full_candidate_pack(
        queries, pool, hash_embed, dataset="2wiki", salt="legacy",
        cohort="synthetic", provenance=provenance(),
    )
    return queries, pool, pack


def synthetic_b21(queries, pool, *, dataset: str, cohort: str,
                  dataset_sha256: str, model_snapshot_sha256: str) -> dict:
    scorepack = compile_scorepack(queries, pool, hash_embed, dataset=dataset,
                                  salt="legacy", top_k=20)
    scorepack["cohort"] = cohort
    scorepack["provenance"] = {
        "dataset_sha256": dataset_sha256,
        "model_snapshot_sha256": model_snapshot_sha256,
    }
    return scorepack


def write_role_artifact(root: Path, role: str, raw_rows: list[dict],
                        *, model_payload: bytes = b"synthetic frozen model\n") -> tuple[Path, Path]:
    contract = ACCEPTANCE_ROLES[role]
    dataset, cohort = contract["dataset"], contract["cohort"]
    role_root = root / role
    role_root.mkdir(parents=True)
    data_path = role_root / "input.json"
    data_path.write_bytes(_canonical_bytes(raw_rows))
    model_path = role_root / "model"
    model_path.mkdir()
    (model_path / "weights.bin").write_bytes(model_payload)
    data_sha = sha256_file(data_path)
    model_sha = directory_manifest(model_path)["sha256"]
    provenance1 = {
        "dataset_sha256": data_sha,
        "model_snapshot_sha256": model_sha,
        "producer_sha256": _producer_hashes(),
    }
    queries, pool = normalize_rows(raw_rows, "2wiki")
    compiled_pack = compile_full_candidate_pack(
        queries, pool, hash_embed, dataset=dataset, salt="legacy",
        cohort=cohort, provenance=provenance1,
    )
    b21 = synthetic_b21(
        queries, pool, dataset=dataset, cohort=cohort,
        dataset_sha256=data_sha, model_snapshot_sha256=model_sha,
    )
    b21_path = role_root / "b21.json.gz"
    b21_info = write_scorepack(b21_path, b21)
    reference = (frozen_b2_reference(raw_rows, hash_embed, top_k=len(pool))
                 if contract["requires_frozen_b2"] else None)
    reference_path = role_root / "frozen-b2.json.gz"
    reference_info = (_write_frozen_reference(reference_path, reference)
                      if reference is not None else None)
    pack_path = role_root / "pack"
    receipt = write_pack(pack_path, compiled_pack, frozen_b2=reference,
                         b21_scorepack=b21)
    receipt.update({
        "determinism_replay": {
            "pass": True,
            "same_embedding_table": True,
            "primary_semantic_sha256": _compiled_semantic_sha256(compiled_pack),
            "repeated_semantic_sha256": _compiled_semantic_sha256(compiled_pack),
        },
        "inputs": {
            "data": str(data_path), "data_sha256": data_sha,
            "model": str(model_path), "model_snapshot_sha256": model_sha,
            "producer_sha256": provenance1["producer_sha256"],
            "b21_scorepack": str(b21_path),
            "b21_scorepack_sha256": b21_info["sha256"],
            "b21_payload_sha256": b21_info["payload_sha256"],
            "frozen_b2_reference": reference_info["path"] if reference_info else None,
            "frozen_b2_reference_sha256": reference_info["sha256"] if reference_info else None,
            "frozen_b2_payload_sha256": reference_info["payload_sha256"] if reference_info else None,
        },
    })
    receipt_path = role_root / "compile-receipt.json"
    receipt_path.write_bytes(_canonical_bytes(receipt))
    return pack_path, receipt_path


def load_manifest(pack_dir: Path) -> dict:
    return json.loads((pack_dir / MANIFEST_FILE).read_text(encoding="utf-8"))


def reseal(pack_dir: Path) -> str:
    manifest = load_manifest(pack_dir)
    for filename, entry in manifest["files"].items():
        path = pack_dir / filename
        entry["sha256"] = sha256_file(path)
        entry["bytes"] = path.stat().st_size
        if filename.endswith(".npy"):
            array = np.load(path, allow_pickle=False)
            entry["dtype"] = array.dtype.str
            entry["shape"] = list(array.shape)
            entry["c_contiguous"] = bool(array.flags.c_contiguous)
    core = _unsealed_manifest(manifest)
    manifest["pack_root_sha256"] = _json_sha256(core)
    (pack_dir / MANIFEST_FILE).write_bytes(_canonical_bytes(manifest))
    return manifest["pack_root_sha256"]


def test_full_pack_roundtrip_neutral_and_frozen_replay(tmp_path: Path, raw_rows):
    queries, pool, pack = compiled(raw_rows)
    reference = frozen_b2_reference(raw_rows, hash_embed, top_k=len(pool))
    b21 = compile_scorepack(queries, pool, hash_embed, dataset="2wiki",
                            salt="legacy", top_k=20)
    b21["cohort"] = "synthetic"
    b21["provenance"] = {
        "dataset_sha256": provenance()["dataset_sha256"],
        "model_snapshot_sha256": provenance()["model_snapshot_sha256"],
    }
    output = tmp_path / "pack"
    receipt = write_pack(output, pack, frozen_b2=reference, b21_scorepack=b21)

    assert receipt["pass"]
    assert receipt["status"] == "PACK_SELF_CHECK_PASS"
    assert receipt["learner_allowed"] is False
    assert receipt["frozen_b2_replay"]["ranked_id_mismatches"] == 0
    assert receipt["b21_topk_continuity"]["ranked_id_mismatches"] == 0
    verified = verify_pack(output, expected_root=receipt["pack_root_sha256"])
    assert verified["component_replay"]["max_abs_merged_error"] <= 1e-12
    assert verified["neutral_replay"]["ranking_mismatches"] == 0
    assert verified["neutral_replay"]["variants"] == [
        "zero_slow_omitted_query", "constant_query_logits",
        "zero_scales_arbitrary_nonpositive",
    ]
    assert compare_frozen_b2(output, reference)["pass"]
    assert compare_b21_scorepack(output, b21)["pass"]


def test_repeat_compilation_has_identical_pack_root(tmp_path: Path, raw_rows):
    _, _, first = compiled(raw_rows)
    _, _, second = compiled(list(raw_rows))
    r1 = write_pack(tmp_path / "one", first)
    r2 = write_pack(tmp_path / "two", second)
    assert r1["learner_allowed"] is False and r2["learner_allowed"] is False
    assert r1["pack_root_sha256"] == r2["pack_root_sha256"]
    for filename in ARRAY_FILES.values():
        assert sha256_file(tmp_path / "one" / filename) == sha256_file(tmp_path / "two" / filename)


def set_synthetic_acceptance_counts(monkeypatch, raw_rows) -> None:
    queries, pool = normalize_rows(raw_rows, "2wiki")
    for contract in ACCEPTANCE_ROLES.values():
        monkeypatch.setitem(contract, "queries", len(queries))
        monkeypatch.setitem(contract, "edges", len(pool))


def test_accepted_feature_view_cannot_expose_supervision(
        tmp_path: Path, raw_rows, monkeypatch):
    set_synthetic_acceptance_counts(monkeypatch, raw_rows)
    role_paths = {role: write_role_artifact(tmp_path, role, raw_rows)
                  for role in ACCEPTANCE_ROLES}
    lock_path = tmp_path / "gate0.lock.json"
    create_acceptance_lock(role_paths, lock_path)
    acceptance_path = tmp_path / "gate0.acceptance.json"
    acceptance = accept_gate0_bundle(lock_path, acceptance_path)
    assert acceptance["learner_allowed"] is True
    pack_path, _ = role_paths["b2_reproduction400"]
    view = load_feature_view(
        pack_path, acceptance_receipt=acceptance_path,
        role="b2_reproduction400",
    )
    assert "supervision" not in view
    assert set(view["manifest"]) == {
        "schema", "identity", "counts", "array_contract", "formula",
        "candidate_set_sha256", "query_set_sha256",
        "embedding_table_sha256", "pack_root_sha256",
    }
    assert "files" not in view["manifest"]
    payload = json.dumps({
        "manifest": view["manifest"], "edges": view["edges"],
        "queries": view["queries"], "acceptance": view["acceptance"],
    })
    assert "supervision.json" not in payload

    def all_keys(value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key
                yield from all_keys(item)
        elif isinstance(value, list):
            for item in value:
                yield from all_keys(item)

    public_keys = set(all_keys({
        "manifest": view["manifest"], "edges": view["edges"],
        "queries": view["queries"], "acceptance": view["acceptance"],
    }))
    assert not {"path", "filename", "gold_edge_ids", "class"} & public_keys
    for array in view["arrays"].values():
        assert isinstance(array, np.ndarray)
        assert array.flags.owndata and not array.flags.writeable
        assert array.base is None and not hasattr(array, "filename")
        with pytest.raises(ValueError):
            array.flat[0] = 0.0

    pack_link = tmp_path / "accepted-pack-link"
    pack_link.symlink_to(pack_path, target_is_directory=True)
    with pytest.raises(PackIntegrityError, match="must not be a symlink"):
        load_feature_view(
            pack_link, acceptance_receipt=acceptance_path,
            role="b2_reproduction400",
        )

    # A syntactically valid but relabelled acceptance receipt cannot unlock.
    forged = copy.deepcopy(acceptance)
    forged["entries"]["b2_reproduction400"] = copy.deepcopy(
        forged["entries"]["2wiki_full_closed_corpus"])
    forged_path = tmp_path / "forged-acceptance.json"
    forged_path.write_bytes(_canonical_bytes(forged))
    with pytest.raises(PackIntegrityError, match="reconstructed lock"):
        load_feature_view(pack_path, acceptance_receipt=forged_path,
                          role="b2_reproduction400")

    # The locked compile receipt cannot be changed and re-accepted.
    _, compile_receipt = role_paths["2wiki_full_closed_corpus"]
    compile_receipt.write_bytes(compile_receipt.read_bytes() + b" ")
    with pytest.raises(PackIntegrityError, match="changed after lock"):
        accept_gate0_bundle(lock_path, tmp_path / "second-acceptance.json")


def test_acceptance_rejects_cross_role_model_drift(
        tmp_path: Path, raw_rows, monkeypatch):
    set_synthetic_acceptance_counts(monkeypatch, raw_rows)
    role_paths = {}
    for role in ACCEPTANCE_ROLES:
        payload = (b"different model\n" if role == "musique_full_closed_corpus"
                   else b"synthetic frozen model\n")
        role_paths[role] = write_role_artifact(
            tmp_path, role, raw_rows, model_payload=payload)
    reproduction_receipt = role_paths["b2_reproduction400"][1]
    original = reproduction_receipt.read_bytes()
    forged = json.loads(original)
    forged["b21_topk_continuity"]["score_comparisons"] += 1
    reproduction_receipt.write_bytes(_canonical_bytes(forged))
    with pytest.raises(ReplayMismatch, match="direct replay"):
        create_acceptance_lock(role_paths, tmp_path / "forged.lock.json")
    reproduction_receipt.write_bytes(original)
    with pytest.raises(PackIntegrityError, match="one frozen model"):
        create_acceptance_lock(role_paths, tmp_path / "drift.lock.json")


def test_lock_rejects_nested_model_symlink_ignored_by_legacy_manifest(
        tmp_path: Path, raw_rows, monkeypatch):
    set_synthetic_acceptance_counts(monkeypatch, raw_rows)
    role_paths = {role: write_role_artifact(tmp_path, role, raw_rows)
                  for role in ACCEPTANCE_ROLES}
    _, receipt_path = role_paths["2wiki_full_closed_corpus"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    model_path = Path(receipt["inputs"]["model"])
    legacy_before = directory_manifest(model_path)["sha256"]

    external = tmp_path / "external-model-fragment"
    external.mkdir()
    target = external / "weights.bin"
    target.write_bytes(b"first target bytes\n")
    (model_path / "nested-link").symlink_to(external, target_is_directory=True)
    assert directory_manifest(model_path)["sha256"] == legacy_before
    target.write_bytes(b"changed target bytes\n")
    assert directory_manifest(model_path)["sha256"] == legacy_before

    with pytest.raises(PackIntegrityError, match="model snapshot contains symlink"):
        create_acceptance_lock(role_paths, tmp_path / "symlinked-model.lock.json")

    top_level_link = tmp_path / "model-link"
    top_level_link.symlink_to(model_path, target_is_directory=True)
    with pytest.raises(PackIntegrityError, match="real directory"):
        gate0._strict_model_manifest(top_level_link)


def test_compile_rechecks_model_snapshot_after_lightweight_compilation(
        tmp_path: Path, raw_rows, monkeypatch):
    data_path = tmp_path / "input.json"
    data_path.write_bytes(_canonical_bytes(raw_rows))
    model_path = tmp_path / "model"
    model_path.mkdir()
    weights = model_path / "weights.bin"
    weights.write_bytes(b"initial model bytes\n")

    class MutatingEmbedder:
        def __init__(self, _model_path: str, *, device: str,
                     batch_size: int) -> None:
            assert device == "cpu" and batch_size == 4
            self.mutated = False

        def __call__(self, texts: list[str]) -> np.ndarray:
            if not self.mutated:
                weights.write_bytes(b"changed model bytes\n")
                self.mutated = True
            return hash_embed(texts)

    monkeypatch.setattr(gate0, "SentenceEmbedder", MutatingEmbedder)
    args = SimpleNamespace(
        data=str(data_path), dataset="2wiki", cohort="full_closed_corpus",
        salt="legacy", model_path=str(model_path), model_id="synthetic-model",
        device="cpu", batch_size=4, b21_scorepack=None,
        frozen_b2_reference=None, output=str(tmp_path / "pack"),
        receipt=str(tmp_path / "compile-receipt.json"),
    )
    with pytest.raises(PackIntegrityError, match="changed during compilation"):
        gate0._compile_cli(args)
    assert not Path(args.output).exists() and not Path(args.receipt).exists()


@pytest.mark.parametrize(
    "placement",
    ["receipt_in_pack", "receipt_in_model", "frozen_in_pack", "frozen_in_model"],
)
def test_compile_rejects_overlapping_artifacts_before_embedding(
        tmp_path: Path, raw_rows, monkeypatch, placement: str):
    data_path = tmp_path / "input.json"
    data_path.write_bytes(_canonical_bytes(raw_rows))
    model_path = tmp_path / "model"
    model_path.mkdir()
    (model_path / "weights.bin").write_bytes(b"model\n")
    pack_path = tmp_path / "pack"
    receipt_path = tmp_path / "compile-receipt.json"
    frozen_path = None
    if placement == "receipt_in_pack":
        receipt_path = pack_path / "compile-receipt.json"
    elif placement == "receipt_in_model":
        receipt_path = model_path / "compile-receipt.json"
    elif placement == "frozen_in_pack":
        frozen_path = pack_path / "frozen-b2.json.gz"
    else:
        frozen_path = model_path / "frozen-b2.json.gz"

    class UnexpectedEmbedder:
        def __init__(self, *_args, **_kwargs) -> None:
            raise AssertionError("embedding must not start before overlap rejection")

    monkeypatch.setattr(gate0, "SentenceEmbedder", UnexpectedEmbedder)
    args = SimpleNamespace(
        data=str(data_path), dataset="2wiki", cohort="b2_reproduction400",
        salt="legacy", model_path=str(model_path), model_id="synthetic-model",
        device="cpu", batch_size=4, b21_scorepack=None,
        frozen_b2_reference=str(frozen_path) if frozen_path else None,
        output=str(pack_path), receipt=str(receipt_path),
    )
    with pytest.raises(PackIntegrityError, match="artifact paths overlap"):
        gate0._compile_cli(args)


def test_acceptance_outputs_cannot_be_written_inside_any_pack(
        tmp_path: Path, raw_rows, monkeypatch):
    set_synthetic_acceptance_counts(monkeypatch, raw_rows)
    role_paths = {role: write_role_artifact(tmp_path, role, raw_rows)
                  for role in ACCEPTANCE_ROLES}
    pack_path, _ = role_paths["b2_reproduction400"]
    for forbidden in (pack_path, pack_path / "gate0.lock.json"):
        with pytest.raises(PackIntegrityError, match="receipt output is inside pack"):
            create_acceptance_lock(role_paths, forbidden)
    pack_alias = tmp_path / "pack-alias"
    pack_alias.symlink_to(pack_path, target_is_directory=True)
    with pytest.raises(PackIntegrityError, match="receipt output is inside pack"):
        create_acceptance_lock(role_paths, pack_alias / "gate0.lock.json")

    lock_path = tmp_path / "gate0.lock.json"
    create_acceptance_lock(role_paths, lock_path)
    for forbidden in (pack_path, pack_path / "gate0.acceptance.json"):
        with pytest.raises(PackIntegrityError, match="receipt output is inside pack"):
            accept_gate0_bundle(lock_path, forbidden)

    sibling = tmp_path / "gate0.acceptance.json"
    assert accept_gate0_bundle(lock_path, sibling)["pass"] is True


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("claim_boundary", "retrieval gain accepted", "claim boundary drift"),
        ("accepted_at", 123, "must be a UTC ISO-8601 string"),
    ],
)
def test_acceptance_receipt_claim_and_timestamp_are_exact(
        tmp_path: Path, raw_rows, monkeypatch,
        field: str, replacement: object, message: str):
    set_synthetic_acceptance_counts(monkeypatch, raw_rows)
    role_paths = {role: write_role_artifact(tmp_path, role, raw_rows)
                  for role in ACCEPTANCE_ROLES}
    lock_path = tmp_path / "gate0.lock.json"
    create_acceptance_lock(role_paths, lock_path)
    acceptance_path = tmp_path / "gate0.acceptance.json"
    acceptance = accept_gate0_bundle(lock_path, acceptance_path)
    assert acceptance["claim_boundary"] == gate0.ACCEPTANCE_CLAIM_BOUNDARY
    gate0._require_utc_timestamp(acceptance["accepted_at"], "accepted_at")

    forged = copy.deepcopy(acceptance)
    forged[field] = replacement
    forged_path = tmp_path / f"forged-{field}.json"
    forged_path.write_bytes(_canonical_bytes(forged))
    pack_path, _ = role_paths["b2_reproduction400"]
    with pytest.raises(PackIntegrityError, match=message):
        load_feature_view(
            pack_path, acceptance_receipt=forged_path,
            role="b2_reproduction400",
        )


def test_production_acceptance_counts_reject_tiny_fixture(tmp_path: Path, raw_rows):
    role_paths = {role: write_role_artifact(tmp_path, role, raw_rows)
                  for role in ACCEPTANCE_ROLES}
    with pytest.raises(PackIntegrityError, match="role count mismatch"):
        create_acceptance_lock(role_paths, tmp_path / "tiny.lock.json")


def test_self_checked_pack_cannot_authorize_feature_loader(tmp_path: Path, raw_rows):
    _, _, pack = compiled(raw_rows)
    output = tmp_path / "pack"
    receipt = write_pack(output, pack)
    receipt_path = tmp_path / "self-check.json"
    receipt_path.write_bytes(_canonical_bytes(receipt))
    with pytest.raises(PackIntegrityError, match="acceptance receipt"):
        load_feature_view(output, acceptance_receipt=receipt_path,
                          role="b2_reproduction400")


def test_refuses_pack_replacement(tmp_path: Path, raw_rows):
    _, _, pack = compiled(raw_rows)
    output = tmp_path / "pack"
    write_pack(output, pack)
    with pytest.raises(PackIntegrityError, match="refusing to replace"):
        write_pack(output, pack)

    symlink_output = tmp_path / "symlink-pack"
    symlink_output.symlink_to(tmp_path / "symlink-target", target_is_directory=True)
    with pytest.raises(PackIntegrityError, match="symlinked pack output"):
        write_pack(symlink_output, pack)


def test_byte_tamper_and_missing_file_fail_closed(tmp_path: Path, raw_rows):
    _, _, pack = compiled(raw_rows)
    output = tmp_path / "pack"
    write_pack(output, pack)
    target = output / ARRAY_FILES["edge_cosine"]
    with target.open("r+b") as handle:
        handle.seek(-1, 2)
        old = handle.read(1)
        handle.seek(-1, 2)
        handle.write(bytes([old[0] ^ 1]))
    with pytest.raises(PackIntegrityError, match="payload hash mismatch"):
        verify_pack(output)

    _, _, pack2 = compiled(raw_rows)
    output2 = tmp_path / "missing"
    write_pack(output2, pack2)
    (output2 / ARRAY_FILES["vertex_channel"]).unlink()
    with pytest.raises(PackIntegrityError, match="file set mismatch"):
        verify_pack(output2)


@pytest.mark.parametrize("filename", ["edges.json", ARRAY_FILES["edge_cosine"]])
def test_injected_mutation_between_file_set_check_and_pinned_load_fails(
        tmp_path: Path, raw_rows, monkeypatch, filename: str):
    _, _, pack = compiled(raw_rows)
    output = tmp_path / "pack"
    write_pack(output, pack)
    original = gate0._validate_file_set
    injected = False

    def mutate_after_file_set(pack_dir: Path, manifest) -> None:
        nonlocal injected
        original(pack_dir, manifest)
        if not injected:
            target = Path(pack_dir) / filename
            payload = bytearray(target.read_bytes())
            payload[-1] ^= 1
            target.write_bytes(payload)
            injected = True

    monkeypatch.setattr(gate0, "_validate_file_set", mutate_after_file_set)
    with pytest.raises(PackIntegrityError, match="payload hash mismatch"):
        verify_pack(output)
    assert injected


def test_feature_view_rejects_mutation_after_acceptance_reverification(
        tmp_path: Path, raw_rows, monkeypatch):
    set_synthetic_acceptance_counts(monkeypatch, raw_rows)
    role_paths = {role: write_role_artifact(tmp_path, role, raw_rows)
                  for role in ACCEPTANCE_ROLES}
    lock_path = tmp_path / "gate0.lock.json"
    create_acceptance_lock(role_paths, lock_path)
    acceptance_path = tmp_path / "gate0.acceptance.json"
    accept_gate0_bundle(lock_path, acceptance_path)
    target_pack, _ = role_paths["b2_reproduction400"]
    target_pack = target_pack.absolute()
    original = gate0._validate_file_set
    target_checks = 0

    def mutate_on_feature_snapshot(pack_dir: Path, manifest) -> None:
        nonlocal target_checks
        original(pack_dir, manifest)
        if Path(pack_dir).absolute() == target_pack:
            target_checks += 1
            # 1: receipt reconstruction, 2: feature-view verify,
            # 3: detached feature snapshot immediately before pinned reads.
            if target_checks == 3:
                target = target_pack / ARRAY_FILES["edge_cosine"]
                payload = bytearray(target.read_bytes())
                payload[-1] ^= 1
                target.write_bytes(payload)

    monkeypatch.setattr(gate0, "_validate_file_set", mutate_on_feature_snapshot)
    with pytest.raises(PackIntegrityError, match="payload hash mismatch"):
        load_feature_view(
            target_pack, acceptance_receipt=acceptance_path,
            role="b2_reproduction400",
        )
    assert target_checks == 3


@pytest.mark.parametrize("mutation", ["float32", "transpose", "nonfinite", "component"])
def test_resealed_semantic_corruption_still_fails(tmp_path: Path, raw_rows, mutation: str):
    _, _, pack = compiled(raw_rows)
    output = tmp_path / mutation
    write_pack(output, pack)
    filename = (ARRAY_FILES["edge_cosine"] if mutation != "component"
                else ARRAY_FILES["base_merged"])
    path = output / filename
    array = np.load(path, allow_pickle=False)
    if mutation == "float32":
        changed = array.astype("<f4")
    elif mutation == "transpose":
        changed = np.ascontiguousarray(array.T, dtype="<f8")
    elif mutation == "nonfinite":
        changed = np.array(array, copy=True)
        changed[0, 0] = np.nan
    else:
        changed = np.array(array, copy=True)
        changed[0, 0] += 1e-4
    with path.open("wb") as handle:
        np.save(handle, changed, allow_pickle=False)
    reseal(output)
    expected = ReplayMismatch if mutation == "component" else PackIntegrityError
    with pytest.raises(expected):
        verify_pack(output)


@pytest.mark.parametrize("sidecar", ["edges.json", "queries.json"])
def test_duplicate_identity_is_rejected_even_after_reseal(tmp_path: Path, raw_rows,
                                                           sidecar: str):
    _, _, pack = compiled(raw_rows)
    output = tmp_path / sidecar.split(".")[0]
    write_pack(output, pack)
    path = output / sidecar
    doc = json.loads(path.read_text(encoding="utf-8"))
    if sidecar == "edges.json":
        doc["records"][1]["edge_id"] = doc["records"][0]["edge_id"]
    else:
        doc["records"][1]["qid_sha256"] = doc["records"][0]["qid_sha256"]
    path.write_bytes(_canonical_bytes(doc))
    reseal(output)
    with pytest.raises(PackIntegrityError):
        verify_pack(output)


def test_extra_and_symlink_payload_are_rejected(tmp_path: Path, raw_rows):
    _, _, pack = compiled(raw_rows)
    output = tmp_path / "pack"
    write_pack(output, pack)
    (output / "extra").symlink_to(output / "edges.json")
    with pytest.raises(PackIntegrityError, match="file set mismatch"):
        verify_pack(output)


def test_pack_directory_symlink_is_rejected(tmp_path: Path, raw_rows):
    _, _, pack = compiled(raw_rows)
    output = tmp_path / "real-pack"
    write_pack(output, pack)
    link = tmp_path / "pack-link"
    link.symlink_to(output, target_is_directory=True)
    with pytest.raises(PackIntegrityError, match="must not be a symlink"):
        verify_pack(link)


def test_nonfinite_and_underwidth_references_fail_closed(tmp_path: Path, raw_rows):
    queries, pool, pack = compiled(raw_rows)
    output = tmp_path / "pack"
    write_pack(output, pack)
    reference = frozen_b2_reference(raw_rows, hash_embed, top_k=len(pool))
    broken_reference = copy.deepcopy(reference)
    broken_reference["records"][0]["arms"]["merged"]["scores"][0] = float("nan")
    with pytest.raises(ReplayMismatch, match="non-finite"):
        compare_frozen_b2(output, broken_reference)

    b21 = synthetic_b21(
        queries, pool, dataset="2wiki", cohort="synthetic",
        dataset_sha256=provenance()["dataset_sha256"],
        model_snapshot_sha256=provenance()["model_snapshot_sha256"],
    )
    broken_b21 = copy.deepcopy(b21)
    broken_b21["records"][0]["arms"]["merged"]["scores"][0] = float("nan")
    with pytest.raises(ReplayMismatch, match="non-finite"):
        compare_b21_scorepack(output, broken_b21)
    broken_b21 = copy.deepcopy(b21)
    broken_b21["top_k"] = 1
    with pytest.raises(ReplayMismatch, match="top_k=20"):
        compare_b21_scorepack(output, broken_b21)


def test_duplicate_query_is_rejected_before_embedding(raw_rows):
    queries, pool = normalize_rows(raw_rows, "2wiki")
    with pytest.raises(PackIntegrityError, match="duplicate query identity"):
        compile_full_candidate_pack(
            [queries[0], queries[0]], pool, hash_embed, dataset="2wiki",
            cohort="synthetic", provenance=provenance(),
        )
