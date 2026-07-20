"""Teeth for the frozen H3-B3 shared-join identity adjudicator."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import bge_m3_embed as bge
import h3_arc_adjudicator as arc
import model_deployment_receipt as mdr
import recorded_llm_extractor as rex
from world_ir import canonical_json, sha256_text


DEPLOYMENT_ATTESTATION_SHA256 = sha256_text("fixture deployment attestation")


def _context(source_id: str, title: str, text: str, mention: str) -> dict:
    start = text.index(mention)
    end = start + len(mention)
    return {
        "source_id": source_id,
        "title": title,
        "context_start": 0,
        "context_end": len(text),
        "context_exact": text,
        "selector_start": start,
        "selector_end": end,
        "selector_exact": mention,
        "selector_start_in_context": start,
        "selector_end_in_context": end,
        "source_text_sha256": sha256_text(text),
    }


def _item(index: int) -> dict:
    mention = "Ada Lovelace" if index == 0 else "Grace Hopper"
    left_text = f"{mention} wrote notes on the machine."
    right_text = f"The award named for {mention} honors computing work."
    payload = {
        "dataset": "musique",
        "join_entity_id": f"hswm:claim_join_entity:v1:join-{index}",
        "normalized_surface": mention.casefold(),
        "source_claim_id": f"hswm:nary_claim:v1:left-{index}",
        "target_claim_id": f"hswm:nary_claim:v1:right-{index}",
        "source_predicate_exact": "wrote notes on",
        "target_predicate_exact": "named for",
        "source_role": "person",
        "target_role": "subject",
        "left_context": _context(
            f"source:left:{index}", f"Left {index}", left_text, mention,
        ),
        "right_context": _context(
            f"source:right:{index}", f"Right {index}", right_text, mention,
        ),
    }
    return {
        "audit_item_id": sha256_text(canonical_json(payload)),
        **payload,
    }


def _packet(n: int = 2) -> dict:
    body = {
        "schema_version": arc.PACKET_SCHEMA_VERSION,
        "seed": arc.FROZEN_PACKET_SEED,
        "dataset": "musique",
        "sampling_unit": "unique emitted shared-join source pair",
        "max_audit_units": 100,
        "n_available_audit_units": n,
        "n_sampled": n,
        "evaluation_labels_included": False,
        "items": [_item(index) for index in range(n)],
    }
    return {
        **body,
        "packet_sha256": sha256_text(canonical_json(body)),
    }


def _config(**changes) -> arc.ArcAdjudicatorConfigV1:
    values = {
        "endpoint": "http://fixture.invalid/v1",
        "deployment_attestation_sha256": DEPLOYMENT_ATTESTATION_SHA256,
        "max_concurrency": 1,
    }
    values.update(changes)
    return arc.ArcAdjudicatorConfigV1(**values)


def _write_deployment_attestation(tmp_path: Path) -> Path:
    repository = tmp_path / "models--Qwen--Qwen3.6-27B"
    snapshot_path = repository / "snapshots" / arc.FROZEN_MODEL_REVISION
    snapshot_path.mkdir(parents=True)
    (snapshot_path / "config.json").write_text(json.dumps({
        "_name_or_path": arc.FROZEN_MODEL_ID,
        "model_type": "qwen3",
        "architectures": ["Qwen3ForCausalLM"],
        "torch_dtype": "bfloat16",
    }), encoding="utf-8")
    (snapshot_path / "tokenizer_config.json").write_text(json.dumps({
        "name_or_path": arc.FROZEN_MODEL_ID,
        "tokenizer_class": "QwenTokenizerFast",
        "model_max_length": 262144,
    }), encoding="utf-8")
    (snapshot_path / "tokenizer.json").write_text(
        '{"version":"1"}', encoding="utf-8",
    )
    (snapshot_path / "model.safetensors").write_bytes(b"fixture-qwen-weights")
    snapshot = bge.attest_model_snapshot(
        snapshot_path, expected_model=arc.FROZEN_MODEL_ID,
        expected_revision=arc.FROZEN_MODEL_REVISION,
    )
    catalog = {"data": [{"id": arc.FROZEN_MODEL}]}
    body = {
        "schema_version": mdr.SCHEMA_VERSION,
        "created_unix_ns": 1,
        "host": "fixture-host",
        "endpoint": "http://fixture.invalid/v1",
        "served_model": arc.FROZEN_MODEL,
        "advertised_models": [arc.FROZEN_MODEL],
        "models_response": catalog,
        "models_response_sha256": sha256_text(canonical_json(catalog)),
        "snapshot": snapshot,
        "server_process": {
            "schema_version": mdr.PROCESS_SCHEMA_VERSION,
            "pid": 1, "process_start_ticks": "1",
            "executable": "/fixture/vllm",
            "executable_sha256": sha256_text("fixture executable"),
            "argv_sha256": sha256_text("fixture argv"), "argc": 1,
            "model_reference": snapshot["resolved_snapshot_path"],
            "model_reference_kind": "snapshot_path",
            "revision_binding": arc.FROZEN_MODEL_REVISION,
            "served_alias": arc.FROZEN_MODEL,
            "served_alias_explicit": True,
        },
        "runtime_versions": {"vllm": None, "transformers": None, "torch": None},
    }
    integrity = sha256_text(canonical_json(body))
    receipt = {
        **body,
        "receipt_sha256": integrity,
        "deployment_id": f"hswm:model_deployment:v2:{integrity}",
    }
    assert mdr.validate_deployment_receipt(receipt) == receipt
    path = tmp_path / "deployment-attestation.json"
    path.write_text(canonical_json(receipt) + "\n", encoding="utf-8")
    return path


def _packet_seal(tmp_path: Path, n: int = 2):
    packet = _packet(n)
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(canonical_json(packet) + "\n", encoding="utf-8")
    attestation_path = _write_deployment_attestation(tmp_path)
    config = _config(
        deployment_attestation_sha256=arc.file_sha256(attestation_path),
    )
    paths = {
        "seal_path": tmp_path / "packet-seal.json",
        "ledger_path": tmp_path / "arc-ledger.jsonl",
        "output_path": tmp_path / "arc-output.json",
        "close_path": tmp_path / "arc-close.json",
    }
    seal = arc.create_packet_seal(
        seal_path=paths["seal_path"], stage_run_id="fresh-fixture-run",
        run_manifest_sha256="a" * 64,
        certificate_transition_sha256="b" * 64,
        fresh_artifact_seal_sha256="c" * 64,
        packet_path=packet_path, config=config,
        deployment_attestation_path=attestation_path,
        ledger_path=paths["ledger_path"], output_path=paths["output_path"],
        close_path=paths["close_path"],
    )
    return packet, config, attestation_path, paths, seal


def _response(
    decision_payload: str,
    *,
    model: str = arc.FROZEN_MODEL,
    finish_reason: str | None = "stop",
):
    choice = {"message": {"content": decision_payload}}
    if finish_reason is not None:
        choice["finish_reason"] = finish_reason
    return rex.TransportResponseV1(canonical_json({
        "model": model,
        "choices": [choice],
        "usage": {"completion_tokens": 4, "prompt_tokens": 80},
    }))


def test_packet_validation_recomputes_item_and_packet_preimages():
    packet = _packet(1)
    assert arc.validate_audit_packet(packet) == packet

    tampered = json.loads(canonical_json(packet))
    tampered["items"][0]["left_context"]["context_exact"] += " altered"
    with pytest.raises(arc.PacketIntegrityError, match="offsets|self-hash"):
        arc.validate_audit_packet(tampered)

    leaked = json.loads(canonical_json(packet))
    leaked["items"][0]["question"] = "hidden evaluation prompt"
    leaked_body = {key: leaked[key] for key in leaked if key != "packet_sha256"}
    leaked["packet_sha256"] = sha256_text(canonical_json(leaked_body))
    with pytest.raises(arc.PacketIntegrityError, match="keys"):
        arc.validate_audit_packet(leaked)


def test_packet_unit_allows_one_join_across_pairs_but_collapses_reverse_pair():
    packet = _packet(2)

    def rehash(value):
        for item in value["items"]:
            payload = {
                key: child for key, child in item.items()
                if key != "audit_item_id"
            }
            item["audit_item_id"] = sha256_text(canonical_json(payload))
        body = {
            key: child for key, child in value.items()
            if key != "packet_sha256"
        }
        value["packet_sha256"] = sha256_text(canonical_json(body))

    # The same normalized join can appear in more than two documents.  Each
    # emitted source pair is an audit unit, so a second pair must remain.
    packet["items"][1]["join_entity_id"] = packet["items"][0]["join_entity_id"]
    rehash(packet)
    assert arc.validate_audit_packet(packet) == packet

    # Reversing an already represented source pair is not a new audit unit.
    packet["items"][1]["left_context"] = packet["items"][0]["right_context"]
    packet["items"][1]["right_context"] = packet["items"][0]["left_context"]
    rehash(packet)
    with pytest.raises(arc.PacketIntegrityError, match="source pair"):
        arc.validate_audit_packet(packet)


def test_request_is_one_item_query_blind_local_context_only():
    packet = _packet(1)
    item = packet["items"][0]
    request = arc.make_openai_request(
        item, packet_sha256=packet["packet_sha256"], config=_config(),
    )

    assert request.body["temperature"] == 0
    assert request.body["seed"] == 0
    assert request.body["chat_template_kwargs"] == {"enable_thinking": False}
    assert request.body["response_format"] == {"type": "json_object"}
    user = request.body["messages"][1]["content"]
    pair = json.loads(user.removeprefix("PAIR_JSON="))
    assert set(pair) == {"left", "right"}
    assert set(pair["left"]) == {
        "title", "excerpt", "mention_start", "mention_end", "mention_exact",
    }
    assert pair["left"]["excerpt"] == item["left_context"]["context_exact"]
    serialized = canonical_json(pair).casefold()
    for forbidden in (
        '"question"', '"answer"', '"gold"', '"hop"', '"source_claim_id"',
        '"target_claim_id"', '"source_predicate_exact"', '"join_entity_id"',
    ):
        assert forbidden not in serialized
    assert "outside knowledge" in arc.SYSTEM_PROMPT
    assert "same spelling alone is not evidence" in arc.SYSTEM_PROMPT


def test_run_is_deterministic_append_safe_and_resumable(tmp_path: Path):
    packet = _packet(2)
    cache_path = tmp_path / "arc.jsonl"
    calls: list[str] = []

    def transport(request):
        calls.append(request.request_id)
        return _response('{"decision":"SAME"}')

    first = arc.run_arc_adjudication(
        packet, _config(), cache_path=cache_path, transport=transport,
    )
    assert first.endpoint_calls == 2
    assert first.cache_hits == 0
    assert len(calls) == 2
    assert all(item["correct"] for item in first.adjudication["judgments"])
    assert first.adjudication["deployment_attestation_sha256"] == (
        DEPLOYMENT_ATTESTATION_SHA256
    )
    assert {
        item["receipt"]["deployment_attestation_sha256"]
        for item in first.adjudication["judgments"]
    } == {DEPLOYMENT_ATTESTATION_SHA256}
    assert {
        item["receipt"]["finish_reason"]
        for item in first.adjudication["judgments"]
    } == {"stop"}
    assert arc.validate_adjudication(first.adjudication, packet) == first.adjudication

    # Only an interrupted final line may be repaired.  Both complete receipts
    # remain first-write-wins and therefore cannot be selectively retried.
    with cache_path.open("ab") as handle:
        handle.write(b'{"interrupted":')

    def forbidden_transport(_request):  # pragma: no cover - failure path
        raise AssertionError("resume must not call the model")

    second = arc.run_arc_adjudication(
        packet, _config(), cache_path=cache_path, transport=forbidden_transport,
    )
    assert second.endpoint_calls == 0
    assert second.cache_hits == 2
    assert second.adjudication == first.adjudication
    assert cache_path.read_bytes().endswith(b"\n")

    # Operational/config changes cannot create a second outcome for the same
    # frozen packet item in the same audit ledger.
    with pytest.raises(arc.CacheCorruptionError, match="does not bind"):
        arc.run_arc_adjudication(
            packet, _config(max_tokens=97), cache_path=cache_path,
            transport=forbidden_transport,
        )


@pytest.mark.parametrize(
    ("transport", "expects_error"),
    [
        (lambda _request: _response('{"verdict":"SAME"}'), True),
        (lambda _request: _response('{"decision":"MAYBE"}'), True),
        (lambda _request: _response('{"decision":"UNCLEAR"}'), False),
        (lambda _request: (_ for _ in ()).throw(ConnectionError("offline")), True),
    ],
)
def test_invalid_missing_transport_and_explicit_unclear_all_fail_closed(
    tmp_path: Path, transport, expects_error: bool,
):
    packet = _packet(1)
    result = arc.run_arc_adjudication(
        packet, _config(),
        cache_path=tmp_path / f"cache-{expects_error}-{id(transport)}.jsonl",
        transport=transport,
    )
    judgment = result.adjudication["judgments"][0]
    receipt = judgment["receipt"]
    assert judgment["decision"] == "UNCLEAR"
    assert judgment["correct"] is False
    assert (json.loads(receipt["error_json"]) != {}) is expects_error


def test_response_model_mismatch_and_duplicate_decision_key_fail_closed(tmp_path: Path):
    packet = _packet(1)
    mismatch = arc.run_arc_adjudication(
        packet, _config(), cache_path=tmp_path / "mismatch.jsonl",
        transport=lambda _request: _response(
            '{"decision":"SAME"}', model="different-model",
        ),
    )
    assert mismatch.adjudication["judgments"][0]["decision"] == "UNCLEAR"
    duplicate = arc.run_arc_adjudication(
        packet, _config(), cache_path=tmp_path / "duplicate.jsonl",
        transport=lambda _request: _response(
            '{"decision":"SAME","decision":"DIFFERENT"}',
        ),
    )
    assert duplicate.adjudication["judgments"][0]["decision"] == "UNCLEAR"


@pytest.mark.parametrize("finish_reason", ["length", "content_filter", None])
def test_nonstop_or_missing_finish_reason_is_durable_unclear(
    tmp_path: Path, finish_reason: str | None,
):
    packet = _packet(1)
    result = arc.run_arc_adjudication(
        packet, _config(),
        cache_path=tmp_path / f"finish-{finish_reason}.jsonl",
        transport=lambda _request: _response(
            '{"decision":"SAME"}', finish_reason=finish_reason,
        ),
    )
    judgment = result.adjudication["judgments"][0]
    receipt = judgment["receipt"]
    assert judgment["decision"] == "UNCLEAR"
    assert judgment["correct"] is False
    assert receipt["finish_reason"] == (finish_reason or "")
    assert json.loads(receipt["error_json"])["type"] == (
        "InvalidOpenAIResponse"
    )
    assert arc.validate_adjudication(result.adjudication, packet) == (
        result.adjudication
    )


def test_cache_and_embedded_receipt_tampering_is_detected(tmp_path: Path):
    packet = _packet(1)
    cache_path = tmp_path / "arc.jsonl"
    result = arc.run_arc_adjudication(
        packet, _config(), cache_path=cache_path,
        transport=lambda _request: _response('{"decision":"SAME"}'),
    )

    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    cached["raw_response"] += " "
    cache_path.write_text(canonical_json(cached) + "\n", encoding="utf-8")
    with pytest.raises(arc.CacheCorruptionError, match="raw response hash"):
        arc.JSONLArcAdjudicationCache(cache_path).records()

    tampered = json.loads(canonical_json(result.adjudication))
    tampered["judgments"][0]["receipt"]["raw_response"] += " "
    body = {
        key: tampered[key]
        for key in tampered
        if key != "adjudication_sha256"
    }
    tampered["adjudication_sha256"] = sha256_text(canonical_json(body))
    with pytest.raises(arc.AdjudicationIntegrityError, match="embedded receipt"):
        arc.validate_adjudication(tampered, packet)

    attestation_tampered = json.loads(canonical_json(result.adjudication))
    attestation_tampered["deployment_attestation_sha256"] = "b" * 64
    body = {
        key: attestation_tampered[key]
        for key in attestation_tampered
        if key != "adjudication_sha256"
    }
    attestation_tampered["adjudication_sha256"] = sha256_text(
        canonical_json(body)
    )
    with pytest.raises(arc.AdjudicationIntegrityError, match="disagree"):
        arc.validate_adjudication(attestation_tampered, packet)


def test_frozen_model_revision_and_decoding_policy_cannot_drift():
    with pytest.raises(ValueError, match="deployment_attestation_sha256"):
        _config(deployment_attestation_sha256="not-a-sha")
    with pytest.raises(ValueError, match="model is frozen"):
        _config(model="another-model")
    with pytest.raises(ValueError, match="preregistered revision"):
        _config(model_revision="0" * 40)
    with pytest.raises(ValueError, match="temperature"):
        _config(temperature=1)
    with pytest.raises(ValueError, match="one audit item"):
        _config(items_per_request=2)


def test_packet_seal_commits_empty_inode_and_closed_evidence_chain(tmp_path: Path):
    packet, config, attestation, paths, seal = _packet_seal(tmp_path)
    ledger_info = paths["ledger_path"].stat()
    assert paths["ledger_path"].read_bytes() == b""
    assert seal["schema_version"] == arc.PACKET_SEAL_SCHEMA_VERSION
    assert seal["ledger_initial_sha256"] == arc.EMPTY_FILE_SHA256
    assert (seal["ledger_device"], seal["ledger_inode"]) == (
        ledger_info.st_dev, ledger_info.st_ino,
    )
    assert seal["durable_outcome_claim"] == (
        "one durable outcome per audit item"
    )
    assert not paths["output_path"].exists()
    assert not paths["close_path"].exists()

    calls: list[str] = []

    def transport(request):
        calls.append(request.request_id)
        return _response('{"decision":"SAME"}')

    first = arc.run_sealed_arc_adjudication(
        paths["seal_path"], config,
        deployment_attestation_path=attestation, transport=transport,
    )
    assert first.endpoint_calls == len(packet["items"])
    assert first.cache_hits == 0
    assert len(calls) == len(packet["items"])
    close = arc.validate_adjudication_close(paths["seal_path"])
    assert close["schema_version"] == arc.ADJUDICATION_CLOSE_SCHEMA_VERSION
    assert close["endpoint_calls"] == len(packet["items"])
    assert close["cache_hits"] == 0
    assert close["n_items"] == close["n_outcomes"] == len(packet["items"])
    assert len(close["completed_request_ids"]) == len(
        set(close["completed_request_ids"])
    )
    assert close["same_ledger_inode"] is True

    def forbidden(_request):  # pragma: no cover - failure path
        raise AssertionError("a valid close must never call the endpoint")

    resumed = arc.run_sealed_arc_adjudication(
        paths["seal_path"], config,
        deployment_attestation_path=attestation, transport=forbidden,
    )
    assert resumed.endpoint_calls == 0
    assert resumed.cache_hits == len(packet["items"])
    assert resumed.adjudication == first.adjudication


def test_packet_seal_rejects_a_hash_bound_but_semantically_invalid_attestation(
    tmp_path: Path,
):
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(canonical_json(_packet(1)) + "\n", encoding="utf-8")
    attestation = tmp_path / "fake-attestation.json"
    attestation.write_text('{"served_model":"qwen3.6-27b"}\n', encoding="utf-8")
    config = _config(
        deployment_attestation_sha256=arc.file_sha256(attestation),
    )
    with pytest.raises(arc.PacketSealIntegrityError, match="valid self-bound"):
        arc.create_packet_seal(
            seal_path=tmp_path / "seal.json", stage_run_id="invalid-attestation",
            run_manifest_sha256="a" * 64,
            certificate_transition_sha256="b" * 64,
            fresh_artifact_seal_sha256="c" * 64,
            packet_path=packet_path, config=config,
            deployment_attestation_path=attestation,
            ledger_path=tmp_path / "ledger.jsonl",
            output_path=tmp_path / "output.json",
            close_path=tmp_path / "close.json",
        )
    assert not (tmp_path / "ledger.jsonl").exists()


def test_sealed_resume_calls_only_missing_item_but_close_is_cumulative(tmp_path: Path):
    packet, config, attestation, paths, _seal = _packet_seal(tmp_path)
    first_item = packet["items"][0]
    receipt = arc.adjudicate_item(
        first_item, packet_sha256=packet["packet_sha256"], config=config,
        transport=lambda _request: _response('{"decision":"SAME"}'),
    )
    assert arc.JSONLArcAdjudicationCache(paths["ledger_path"]).append(receipt)
    calls: list[str] = []

    def transport(request):
        calls.append(request.request_id)
        return _response('{"decision":"DIFFERENT"}')

    resumed = arc.run_sealed_arc_adjudication(
        paths["seal_path"], config,
        deployment_attestation_path=attestation, transport=transport,
    )
    assert resumed.cache_hits == 1
    assert resumed.endpoint_calls == 1
    assert len(calls) == 1
    close = arc.validate_adjudication_close(paths["seal_path"])
    assert close["endpoint_calls"] == 2
    assert close["cache_hits"] == 0


def test_seal_drift_fails_before_any_endpoint_call(tmp_path: Path):
    _packet_value, config, attestation, paths, seal = _packet_seal(tmp_path)
    calls = 0

    def transport(_request):  # pragma: no cover - failure path
        nonlocal calls
        calls += 1
        return _response('{"decision":"SAME"}')

    with pytest.raises(arc.PacketSealIntegrityError, match="config/deployment"):
        arc.run_sealed_arc_adjudication(
            paths["seal_path"], _config(max_tokens=97),
            deployment_attestation_path=attestation, transport=transport,
        )
    assert calls == 0

    tampered = json.loads(paths["seal_path"].read_text(encoding="utf-8"))
    tampered["output_path"] = str(tmp_path / "cherry-picked-output.json")
    paths["seal_path"].write_text(
        canonical_json(tampered) + "\n", encoding="utf-8",
    )
    with pytest.raises(arc.PacketSealIntegrityError, match="self-hash"):
        arc.run_sealed_arc_adjudication(
            paths["seal_path"], config,
            deployment_attestation_path=attestation, transport=transport,
        )
    assert calls == 0
    assert seal["packet_seal_sha256"] != tampered["packet_seal_sha256"] or (
        tampered["output_path"] != seal["output_path"]
    )


def test_close_tamper_or_absence_forbids_metric_gate(tmp_path: Path):
    _packet_value, config, attestation, paths, _seal = _packet_seal(tmp_path, 1)
    arc.run_sealed_arc_adjudication(
        paths["seal_path"], config,
        deployment_attestation_path=attestation,
        transport=lambda _request: _response('{"decision":"SAME"}'),
    )
    close = json.loads(paths["close_path"].read_text(encoding="utf-8"))
    close["cache_hits"] = 1
    body = {
        key: close[key] for key in close
        if key != "adjudication_close_sha256"
    }
    close["adjudication_close_sha256"] = sha256_text(canonical_json(body))
    paths["close_path"].write_text(canonical_json(close) + "\n", encoding="utf-8")
    with pytest.raises(arc.AdjudicationCloseIntegrityError, match="cache_hits"):
        arc.validate_adjudication_close(paths["seal_path"])

    paths["close_path"].unlink()
    with pytest.raises(arc.AdjudicationCloseIntegrityError, match="cannot read"):
        arc.validate_adjudication_close(paths["seal_path"])
