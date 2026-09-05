"""The G1 instrument admits through the real Atom v2 local Permit commit."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil

import pytest

from hswm.experiments import atom_v2_permit_bridge as bridge
from hswm.experiments import g1_micro
from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256

from tests.test_hswm_g1_micro import (
    _OpaquePilotBackend,
    _VaryingMicroBackend,
    _opaque_protocol,
    _opaque_tokenizer_receipt,
    _protocol,
)


ROOT = Path(__file__).resolve().parents[1]


def _process() -> bridge.LocalPermitCommitProcess:
    process = bridge.default_process(ROOT)
    if process is None:
        pytest.skip(
            "Atom v2 local Permit commit process is not built; run "
            "`cd src/hswm/effect-runtime && npm run build` (Node required)"
        )
    return process


def _claims(pre: bytes, post: bytes) -> dict:
    hexes = lambda digit: digit * 64  # noqa: E731
    return bridge.transition_claims(
        lineage_id="lineage:test", permit_id="permit:test", execution_id="execution:test",
        execution_intent_sha256=hexes("3"), permit_sha256=hexes("4"), proposal_sha256=hexes("5"),
        transition_invariant_sha256=hexes("6"), prior_record_sha256=hexes("2"),
        successor_record_sha256=hexes("8"), pre_state_bytes=pre, post_state_bytes=post,
        target_schema_version="schema:test", target_atom_uid="atom:test",
        authorization_ref="authorization:test", scope="scope:test",
    )


def test_bridge_commits_and_recovers_one_exact_transition(tmp_path: Path) -> None:
    process = _process()
    pre = canonical_json_bytes({"dispositions": [], "owner_uid": "o", "schema_version": "s"})
    post = canonical_json_bytes({"dispositions": [{"x": 1}], "owner_uid": "o", "schema_version": "s"})
    root = tmp_path / "commit"
    root.mkdir()
    issuer = {"keyId": "key:test", "authorizer": "principal:test", "policyVersion": "policy:test", "revocationEpoch": 0}
    summary = process.commit(
        root_path=root, trust_snapshot_path=root / "trust.json", issuer=issuer,
        claims=_claims(pre, post), pre_state_bytes=pre, post_state_bytes=post,
    )
    assert summary["pre_state_sha256"] == sha256(pre).hexdigest()
    assert summary["post_state_sha256"] == sha256(post).hexdigest()
    assert Path(summary["slot_path"]).is_file()
    bridge.verify_commit_summary(summary)
    recovered = process.recover(root_path=root, trust_snapshot_path=root / "trust.json")
    assert [item["recordSha256"] for item in recovered["commits"]] == [summary["commit_record_sha256"]]
    assert recovered["head"]["sequence"] == 1

    with pytest.raises(bridge.AtomV2PermitBridgeError, match="refused"):
        process.commit(
            root_path=root, trust_snapshot_path=root / "trust.json", issuer=issuer,
            claims=_claims(pre, post), pre_state_bytes=pre, post_state_bytes=post,
        )
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(bridge.AtomV2PermitBridgeError, match="refused"):
        process.commit(
            root_path=other, trust_snapshot_path=other / "trust.json", issuer=issuer,
            claims=_claims(pre, post), pre_state_bytes=pre, post_state_bytes=pre,
        )
    tampered = deepcopy(summary)
    tampered["post_state_sha256"] = "0" * 64
    with pytest.raises(bridge.AtomV2PermitBridgeError, match="digest mismatch"):
        bridge.verify_commit_summary(tampered)


def test_micro_slice_admits_through_the_atom_v2_permit_path(tmp_path: Path) -> None:
    process = _process()
    protocol, protocol_sha, registry = _protocol(tmp_path)
    output = tmp_path / "g1-micro"
    bundle = g1_micro._run_exploratory_slice_with_backend(
        backend=_VaryingMicroBackend(), protocol=protocol, protocol_sha256=protocol_sha,
        output_dir=output, execution_registry_path=registry, permit_commit=process,
    )
    bindings = bundle["atom_v2_permit_commit"]
    assert set(bindings) == {"ACTIVE", "OUTCOME_INDEPENDENT_SHAM"}
    for branch, binding in bindings.items():
        commit = binding["commit"]
        admission = bundle["local_admissions"][branch]
        assert commit["post_state_sha256"] == admission["admission"]["payload"]["resulting_state_sha256"]
        assert commit["pre_state_sha256"] == g1_micro.state_sha256(g1_micro.make_genesis_state())
        assert commit["execution_intent_sha256"] == admission["permit"]["record_sha256"]
        assert Path(commit["slot_path"]).is_file()
        assert "atom_v2_permit_commit" not in admission
    # The probe read exactly the Permit-committed successor state.
    assert bindings["ACTIVE"]["commit"]["post_state_sha256"] == bundle["probes"]["ACTIVE"]["payload"]["state_sha256"]
    assert bindings["ACTIVE"]["commit"]["post_state_sha256"] == bundle["probes"]["RESTORE"]["payload"]["state_sha256"]
    assert g1_micro.verify_bundle_file(output / "result.json")["verification"] == "VALID_LOCAL_STRUCTURAL_CONSISTENCY"

    def rewrite(mutate) -> dict:
        mutated = json.loads((output / "result.json").read_bytes())
        mutate(mutated)
        unsigned = dict(mutated)
        unsigned.pop("bundle_sha256")
        mutated["bundle_sha256"] = canonical_sha256(unsigned)
        return mutated

    swapped = rewrite(lambda b: b["atom_v2_permit_commit"].__setitem__("ACTIVE", deepcopy(b["atom_v2_permit_commit"]["OUTCOME_INDEPENDENT_SHAM"])))
    with pytest.raises(g1_micro.G1MicroError, match="another branch"):
        g1_micro.verify_exploratory_bundle(swapped, base_dir=output)

    def retarget(b: dict) -> None:
        commit = b["atom_v2_permit_commit"]["ACTIVE"]["commit"]
        commit["post_state_sha256"] = commit["pre_state_sha256"]
        unsigned = dict(commit)
        unsigned.pop("summary_sha256")
        commit["summary_sha256"] = canonical_sha256(unsigned)

    with pytest.raises(bridge.AtomV2PermitBridgeError, match="post-state digest"):
        g1_micro.verify_exploratory_bundle(rewrite(retarget), base_dir=output)

    shutil.rmtree(output / "atom-v2-permit-commit" / "active")
    # The slot bytes are gone; the summary still closes structurally but the
    # retained-slot check is only applied when the file exists.
    assert g1_micro.verify_bundle_file(output / "result.json")["verification"] == "VALID_LOCAL_STRUCTURAL_CONSISTENCY"


def test_opaque_pilot_admits_through_the_atom_v2_permit_path(tmp_path: Path) -> None:
    process = _process()
    protocol, protocol_sha, registry, reveal_path, reveal = _opaque_protocol(tmp_path)
    backend = _OpaquePilotBackend(
        {
            episode["cue"]: secret["correct_action_code"]
            for episode, secret in zip(protocol["episodes"], reveal["episodes"], strict=True)
        }
    )
    output = tmp_path / "opaque-output"
    bundle = g1_micro.run_opaque_identifiability_pilot_with_backend(
        backend=backend, protocol=protocol, protocol_sha256=protocol_sha, output_dir=output,
        execution_registry_path=registry, evaluator_reveal_path=reveal_path,
        tokenizer_receipt=_opaque_tokenizer_receipt(protocol), permit_commit=process,
    )
    committed = 0
    for episode in bundle["episodes"]:
        for branch in ("ACTIVE", "FORCED_OPPOSITE_FEEDBACK"):
            data = episode["dispositions"][branch]
            if data["admission"] is None:
                assert "atom_v2_permit_commit" not in data
                continue
            binding = data["atom_v2_permit_commit"]
            assert binding["branch"] == branch
            assert binding["commit"]["post_state_sha256"] == data["admission"]["admission"]["payload"]["resulting_state_sha256"]
            committed += 1
    assert committed == 16
    g1_micro.verify_opaque_identifiability_pilot_bundle(bundle, base_dir=output, protocol=protocol)
