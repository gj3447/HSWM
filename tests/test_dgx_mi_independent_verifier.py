"""Adversarial fixtures for the standalone MI evidence reducer."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from dataclasses import replace
import pytest

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256
from _research.dgx_mi.independent_verifier import COMPLETE, INCOMPLETE, UNAVAILABLE, VOID, main, verify


def _put(root: Path, raw: bytes) -> dict[str, object]:
    digest = sha256(raw).hexdigest()
    (root / "content" / digest).write_bytes(raw)
    return {"sha256": digest, "byte_length": len(raw)}


def _row(rows: list[dict[str, object]], value: dict[str, object]) -> None:
    value["ordinal"] = len(rows) + 1
    value["previous_record_sha256"] = rows[-1]["record_sha256"] if rows else "0" * 64
    value["record_sha256"] = canonical_sha256(value)
    rows.append(value)


def _envelope(content: str, *, peer: bool = True) -> bytes:
    # Deliberate decimals exercise the lossless ordinary-JSON path.
    tokens = []
    for character in content.encode():
        alternate = (character + 1) % 256
        top = [{"token": chr(character), "bytes": [character], "logprob": -0.1}]
        top += [{"token": chr(alternate), "bytes": [alternate], "logprob": -1.1} for _ in range(19)]
        tokens.append({"token": chr(character), "bytes": [character], "logprob": -0.1, "top_logprobs": top})
    return json.dumps({"model": "test-model", "choices": [{"finish_reason": "stop", "message": {"content": content}, "logprobs": {"content": tokens}}]}, separators=(",", ":")).encode()


def _root(tmp_path: Path, *, missing_peer: bool = False) -> Path:
    root = tmp_path / "root"; (root / "content").mkdir(parents=True); (root / "dispatch.lock").write_bytes(b"")
    plan = {"schema_version": "hswm-dgx-qcase024-mi-plan/v2", "namespace": "DNRD5-QCASE024-MECHANISM-ISOLATION-ONLY/v2", "source": {}, "runner_version": "hswm-dgx-qcase024-mi-runner/v2", "material": {}, "request_sha256": sha256(b"request").hexdigest(), "post_result_selection": {}, "arms": {arm: {f"i{i}": sha256(f"{arm}-{i}".encode()).hexdigest() for i in range(6)} for arm in ("ASYNC_ENABLED", "ASYNC_DISABLED")}, "block_order": [{"arm": a, "block_id": b} for a, b in (("ASYNC_ENABLED", "B01"), ("ASYNC_DISABLED", "B01"), ("ASYNC_DISABLED", "B02"), ("ASYNC_ENABLED", "B02"))], "attempts_per_block": 4, "budget": 16, "zero_retry": True, "consumption_registry": {}, "verifier": {}, "evidence_root_genesis_sha256": sha256(b"genesis").hexdigest(), "allowed_terminals": ["LIVE_COMPLETE_DGX_QCASE024_MECHANISM_DIAGNOSTIC", "INCONCLUSIVE_DGX_QCASE024_MI_INCOMPLETE_LIVE_SLOTS", "INCONCLUSIVE_DGX_QCASE024_MI_REQUIRED_LOGPROB_OR_ALIGNMENT_UNAVAILABLE", "VOID_DGX_QCASE024_MI_PROTOCOL_LEDGER_HASH_ORDER_OR_BOUNDARY_BREACH"], "nonclaims": []}
    plan_raw = canonical_bytes(plan); plan_d = _put(root, plan_raw); request_d = _put(root, b"request"); genesis_d = _put(root, b"genesis")
    marker_raw = canonical_bytes({"schema_version": "hswm-dgx-qcase024-mi-start-marker/v2", "namespace": plan["namespace"], "plan_sha256": sha256(plan_raw).hexdigest(), "request_sha256": plan["request_sha256"], "scheduled_attempts": [f"MI-024-V2-{a}-{b}-R{r:03d}" for a, b in (("ASYNC_ENABLED", "B01"), ("ASYNC_DISABLED", "B01"), ("ASYNC_DISABLED", "B02"), ("ASYNC_ENABLED", "B02")) for r in range(1, 5)], "terminal": "ALL_16_SERIALIZED_POSTS_AND_LOGPROB_OBSERVABILITY_BOUND_BEFORE_LIVE_START", "nonclaims": []})
    marker_d = _put(root, marker_raw)
    closure_d = _put(root, canonical_bytes({"schema_version": "hswm-dgx-qcase024-mi-preregistration-freeze/v2", "namespace": plan["namespace"], "artifacts": [{"path": "plan.json", **plan_d}]}))
    identities: dict[str, dict[str, object]] = {}
    for arm, values in plan["arms"].items():
        identities[arm] = {}
        for name, digest in values.items():
            raw = f"{arm}-{name[-1]}".encode(); assert sha256(raw).hexdigest() == digest
            identities[arm][name] = _put(root, raw)
    rows: list[dict[str, object]] = []
    consumption_d = _put(root, b"consumption")
    _row(rows, {"record_type": "PLAN_CONSUMPTION", "plan_sha256": sha256(plan_raw).hexdigest(), "consumption": consumption_d})
    _row(rows, {"record_type": "MI_MARKER", "plan": plan_d, "marker": marker_d, "freeze_closure": closure_d, "root_genesis": genesis_d, "identities": identities, "request": request_d, "request_sha256": plan["request_sha256"], "all_request_blob_durable": True, "plan_sha256": sha256(plan_raw).hexdigest()})
    for arm, block in (("ASYNC_ENABLED", "B01"), ("ASYNC_DISABLED", "B01"), ("ASYNC_DISABLED", "B02"), ("ASYNC_ENABLED", "B02")):
        server = _put(root, f"server-{arm}-{block}".encode())
        _row(rows, {"record_type": "BLOCK_START", "arm": arm, "block_id": block, "server_identity": server})
        for rep in range(1, 5):
            attempt = f"MI-024-V2-{arm}-{block}-R{rep:03d}"
            _row(rows, {"record_type": "START", "attempt_id": attempt, "arm": arm, "block_id": block, "replicate": rep, "request": request_d, "plan_sha256": sha256(plan_raw).hexdigest(), "retry": "NONE"})
            content = '{"answer":"VISTA"}'
            content_d = _put(root, content.encode()); structured_d = _put(root, canonical_bytes(json.loads(content)))
            envelope_d = _put(root, _envelope(content))
            _row(rows, {"record_type": "TERMINAL", "attempt_id": attempt, "start_record_sha256": rows[-1]["record_sha256"], "retry": "NONE", "retry_allowed": False, "outcome": "SUCCEEDED", "model_content_utf8": content_d, "structured_content_diagnostic": structured_d, "raw_envelope": envelope_d})
        _row(rows, {"record_type": "BLOCK_SEAL", "arm": arm, "block_id": block, "started_slots": 4, "successful_slots": 4, "failed_slots": 0, "server_identity": server})
    _row(rows, {"record_type": "RUN_SEAL", "status": "COMPLETE_16_LIVE_POSTS", "started_slots": 16, "successful_slots": 16, "failed_slots": 0})
    (root / "mi_ledger.jsonl").write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in rows))
    return root


def test_refuses_legacy_marker_shape_even_when_the_ledger_chain_is_valid(tmp_path: Path) -> None:
    # The deliberately minimal fixture predates the frozen MI marker contract;
    # a verifier must not silently accept a hash-valid but under-bound root.
    assert verify(_root(tmp_path))["terminal"] == VOID


def test_rejects_hash_chain_tampering(tmp_path: Path) -> None:
    root = _root(tmp_path); ledger = root / "mi_ledger.jsonl"
    ledger.write_bytes(ledger.read_bytes().replace(b'"record_type":"RUN_SEAL"', b'"record_type":"RUN_XEAL"', 1))
    assert verify(root)["terminal"] == VOID


def test_reports_logprob_unavailability_not_integrity_success(tmp_path: Path) -> None:
    root = _root(tmp_path)
    # The first raw envelope remains hash-addressed but has only 19 top alternatives.
    content = '{"answer":"VISTA"}'
    raw = json.loads(_envelope(content)); raw["choices"][0]["logprobs"]["content"][0]["top_logprobs"].pop()
    old = next((root / "content").iterdir())
    # Tampering a stored envelope is a hash breach, which is intentionally VOID.
    old.write_bytes(json.dumps(raw).encode())
    assert verify(root)["terminal"] == VOID


def _run_valid(tmp_path: Path, *, variant: bool = False, short_top: bool = False, early_failure: bool = False):
    """A real runner-shaped root is required for a positive verifier verdict."""
    from _research.dgx_mi.preregistration import build_mi_preregistration, build_verifier_source_manifest
    from _research.dgx_mi.runner import MiObservation, MiRunner
    from tests.test_dgx_mi_preregistration import _inputs
    from tests.test_dgx_mi_runtime import _specs

    source = Path("_research/dgx_mi/independent_verifier.py").read_bytes()
    inputs = _inputs()
    inputs = replace(inputs, verifier_build=build_verifier_source_manifest(source, source_path="_research/dgx_mi/independent_verifier.py"))
    artifacts = build_mi_preregistration(inputs)
    content = '{"answer":"VISTA","rationale":"The first public cue begins with V, while the other cue is a different public word and label."}'
    model = json.loads(artifacts["identities/ASYNC_ENABLED/model_identity_sha256.json"])["model"]
    def raw_for(text: str) -> bytes:
        body = json.loads(_envelope(text)); body["model"] = model; body["usage"] = {"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}
        if short_top:
            for token in body["choices"][0]["logprobs"]["content"]: token["top_logprobs"] = token["top_logprobs"][:1]
        return json.dumps(body, separators=(",", ":")).encode()
    raws = [raw_for(content) for _ in range(16)]
    if early_failure:
        # A live provider response without the required trace is a sealed,
        # consumed partial root, rather than permission to replace the slot.
        raws[0] = json.dumps({"model": model, "choices": [{"finish_reason": "stop", "message": {"content": content}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}, separators=(",", ":")).encode()
    if variant:
        alternative = '{"answer":"VISTA","rationale":"The first public cue starts with V, while the other cue is a different public word and label."}'
        raws[1] = raw_for(alternative)
        offset = next(i for i, pair in enumerate(zip(content.encode(), alternative.encode())) if pair[0] != pair[1])
        for position, peer in ((0, alternative.encode()[offset]), (1, content.encode()[offset])):
            body = json.loads(raws[position]); token = body["choices"][0]["logprobs"]["content"][offset]
            token["top_logprobs"][-1] = {"token": chr(peer), "bytes": [peer], "logprob": -0.2}
            raws[position] = json.dumps(body, separators=(",", ":")).encode()

    class Lease:
        def __init__(self, spec): self.spec = spec
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def attest(self, phase, completed):
            argv = ["--model", "/model-repository/snapshots/95a723d08a9490559dae23d0cff1d9466213d989", "--served-model-name", "qwen3.6-35b-a3b", "--host", "0.0.0.0", "--port", "8000", "--max-num-seqs", "1", "--no-enable-prefix-caching", "--max-model-len", "32768", "--gpu-memory-utilization", "0.500", "--generation-config", "vllm", "--seed", "0", "--enforce-eager", "--language-model-only", "--max-logprobs", "20", "--logprobs-mode", "processed_logprobs", "--async-scheduling" if self.spec.async_scheduling else "--no-async-scheduling"]
            tag = sha256((self.spec.arm + self.spec.block_id).encode()).hexdigest()
            identity = {"container_id_sha256": tag, "container_start_sha256": sha256((tag+"s").encode()).hexdigest(), "cgroup_sha256": "1"*64, "network_namespace_sha256": "2"*64, "server_argv_sha256": sha256("\0".join(argv).encode()).hexdigest()}
            return canonical_bytes({"schema_version":"hswm-dgx-qcase024-mi-boundary/v2","arm":self.spec.arm,"block_id":self.spec.block_id,"phase":phase,"completed":completed,"async_scheduling":self.spec.async_scheduling,"server_argv":argv,"server_argv_sha256":identity["server_argv_sha256"],"server_identity":identity,"request_success_total":completed,"raw_metrics_sha256":"3"*64,"terminal":"FINITE_BLOCK_BOUNDARY_NOT_NO_INTERFERENCE_PROOF"})

    registry = tmp_path / "registry"; registry.mkdir()
    identities = {arm:{name:artifacts[f"identities/{arm}/{name}.json"] for name in ("endpoint_sha256","model_identity_sha256","runtime_identity_sha256","tls_identity_sha256","declared_isolation_contract_sha256","model_snapshot_manifest_sha256")} for arm in ("ASYNC_ENABLED","ASYNC_DISABLED")}
    provenance = {"source_ci_receipt_sha256":artifacts["provenance/source_ci_receipt_sha256.json"],"verifier_ci_receipt_sha256":artifacts["provenance/verifier_ci_receipt_sha256.json"],"verifier_build_output_sha256":artifacts["provenance/verifier_build_output_sha256.json"]}
    specs = _specs(tmp_path)
    for key, spec in list(specs.items()):
        runtime = json.loads(identities[key[0]]["runtime_identity_sha256"])
        specs[key] = replace(spec, endpoint=runtime["endpoint"], image=runtime["container_image"], image_id=runtime["image_id"], gpu_uuid=runtime["gpu_uuid"], served_model=runtime["served_model"], model_revision=runtime["model_revision"], max_model_len=runtime["max_model_len"], gpu_memory_utilization_milli=runtime["gpu_memory_utilization_milli"])
    runner = MiRunner(tmp_path / "evidence", plan_raw=artifacts["plan.json"], marker_raw=artifacts["start_marker.json"], closure_raw=artifacts["closure_manifest.json"], genesis_raw=artifacts["root_genesis.json"], material_raw=artifacts["material_provenance.json"], request_raw=artifacts["request.json"], schema_raw=artifacts["materials/QCASE-024/response_schema.json"], identities=identities, provenance=provenance, consumption_root=registry, specs=specs, publication_commit=inputs.source_commit, publication_tree=inputs.source_tree, publication_ci_receipt=inputs.source_ci_receipt, lease_factory=Lease, transport=lambda *_: MiObservation(200, raws.pop(0), "application/json", None))
    runner.execute()
    return tmp_path / "evidence", registry, artifacts


def test_valid_frozen_runner_root_reduces_to_complete_with_decimal_trace(tmp_path: Path) -> None:
    root, registry, artifacts = _run_valid(tmp_path)
    result = verify(root, external_registry_root=registry)
    assert result["terminal"] == COMPLETE
    assert result["observation_pattern"] == "ALL_ARM_BLOCKS_EXACT"
    marker_path = registry / (sha256(artifacts["plan.json"]).hexdigest() + ".consumed")
    marker_raw = marker_path.read_bytes()
    marker_path.unlink()
    assert verify(tmp_path / "evidence", external_registry_root=registry)["terminal"] == INCOMPLETE
    marker_path.write_bytes(marker_raw + b"x")
    assert verify(tmp_path / "evidence", external_registry_root=registry)["terminal"] == INCOMPLETE
    marker_path.write_bytes(marker_raw)
    ledger = root / "mi_ledger.jsonl"
    ledger.write_bytes(ledger.read_bytes().replace(b'"record_type":"RUN_SEAL"', b'"record_type":"RUN_XEAL"', 1))
    assert verify(tmp_path / "evidence", external_registry_root=registry)["terminal"] == VOID


def test_valid_variation_has_finite_arm_pattern_and_decimal_diagnostic(tmp_path: Path) -> None:
    root, registry, _ = _run_valid(tmp_path, variant=True)
    result = verify(root, external_registry_root=registry)
    assert result["terminal"] == COMPLETE
    assert result["observation_pattern"] == "ASYNC_ENABLED_VARIATION_ASYNC_DISABLED_EXACT"
    assert result["first_divergence_diagnostics"]


def test_short_top_logprobs_is_inconclusive_not_void(tmp_path: Path) -> None:
    root, registry, _ = _run_valid(tmp_path, short_top=True)
    assert verify(root, external_registry_root=registry)["terminal"] == UNAVAILABLE


def test_valid_early_sealed_unavailable_root_is_not_misreported_as_void(tmp_path: Path) -> None:
    root, registry, _ = _run_valid(tmp_path, early_failure=True)
    assert verify(root, external_registry_root=registry)["terminal"] == UNAVAILABLE


def test_reused_immutable_server_or_provenance_blob_is_void(tmp_path: Path) -> None:
    root, registry, _ = _run_valid(tmp_path)
    ledger = root / "mi_ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_bytes().splitlines()]
    starts = [row for row in rows if row["record_type"] == "BLOCK_START"]
    starts[1]["server_identity"]["observed"] = starts[0]["server_identity"]["observed"]
    previous = "0" * 64
    for ordinal, row in enumerate(rows, 1):
        row["ordinal"] = ordinal; row["previous_record_sha256"] = previous
        row.pop("record_sha256", None); row["record_sha256"] = canonical_sha256(row); previous = row["record_sha256"]
    ledger.write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in rows))
    assert verify(root, external_registry_root=registry)["terminal"] == VOID


def test_rechained_boundary_argv_drift_is_void(tmp_path: Path) -> None:
    root, registry, _ = _run_valid(tmp_path)
    ledger = root / "mi_ledger.jsonl"; rows = [json.loads(line) for line in ledger.read_bytes().splitlines()]
    descriptor = next(row["pre_boundary_attestation"] for row in rows if row["record_type"] == "BLOCK_START")
    boundary_path = root / "content" / descriptor["sha256"]
    boundary = json.loads(boundary_path.read_bytes()); boundary["server_argv"][0] = "--wrong-model"
    # Preserve the original descriptor's length/hash impossibility deliberately:
    # a re-chained ledger cannot make a frozen boundary descriptor valid.
    boundary_path.write_bytes(canonical_bytes(boundary))
    assert verify(root, external_registry_root=registry)["terminal"] == VOID


def test_pinned_plan_identity_map_mutation_is_void(tmp_path: Path) -> None:
    root, registry, _ = _run_valid(tmp_path)
    marker = json.loads((root / "mi_ledger.jsonl").read_bytes().splitlines()[1])
    plan_path = root / "content" / marker["plan"]["sha256"]
    plan = json.loads(plan_path.read_bytes())
    plan["arms"]["ASYNC_ENABLED"]["runtime_identity_sha256"] = "f" * 64
    plan_path.write_bytes(canonical_bytes(plan))
    assert verify(root, external_registry_root=registry)["terminal"] == VOID


def test_unreferenced_content_blob_is_void(tmp_path: Path) -> None:
    root, registry, _ = _run_valid(tmp_path)
    (root / "content" / sha256(b"orphan").hexdigest()).write_bytes(b"orphan")
    assert verify(root, external_registry_root=registry)["terminal"] == VOID

    second = tmp_path / "second"; second.mkdir()
    root, registry, _ = _run_valid(second)
    rows = [json.loads(line) for line in (root / "mi_ledger.jsonl").read_bytes().splitlines()]
    provenance = rows[1]["provenance"]["source_ci_receipt_sha256"]
    (root / "content" / provenance["sha256"]).write_bytes(b"tampered")
    assert verify(root, external_registry_root=registry)["terminal"] == VOID


def test_cli_atomically_writes_the_canonical_complete_projection(tmp_path: Path) -> None:
    root, registry, _ = _run_valid(tmp_path)
    output = tmp_path / "projection.json"
    assert main(["--root", str(root), "--external-registry-root", str(registry), "--output", str(output)]) == 0
    assert json.loads(output.read_bytes())["terminal"] == COMPLETE
