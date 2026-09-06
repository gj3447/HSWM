from hashlib import sha256
import json

import pytest

from hswm.experiments import d4_heldout_task as d4


SEED = bytes(range(32))  # Qualification fixture only; not a scientific draw.
GENERATOR = sha256(b"generator").hexdigest()
COMPILER = sha256(b"compiler").hexdigest()


def _contract() -> d4.TaskContract:
    return d4.TaskContract(GENERATOR, COMPILER)


def test_fresh_opaque_instances_have_disjoint_ids_and_strict_actions() -> None:
    contract = _contract()
    train = d4.make_instance(seed=SEED, occurrence_uid="d4-test", split="TRAIN", selector_bit=0, candidate_order=0)
    final = d4.make_instance(seed=SEED, occurrence_uid="d4-test", split="FINAL_HELDOUT", selector_bit=0, candidate_order=0)
    assert set(train.action_codes).isdisjoint(final.action_codes)
    valid = json.dumps({"action_id": final.action_codes[0]}, separators=(",", ":")).encode()
    assert d4.parse_action(valid, final) == final.action_codes[0]
    with pytest.raises(d4.D4HeldoutTaskError):
        d4.parse_action(b'{"action_id":"wrong","extra":0}', final)
    with pytest.raises(d4.D4HeldoutTaskError, match="duplicate"):
        d4.parse_action((b'{"action_id":"%b","action_id":"%b"}' % (final.action_codes[0].encode(), final.action_codes[1].encode())), final)
    assert b"latent_bit" not in final.render(contract)


@pytest.mark.parametrize("theta,action_index", [(0, 0), (0, 1), (1, 0), (1, 1)])
def test_sealed_train_independent_outcome_derives_true_candidate(theta: int, action_index: int) -> None:
    contract = _contract()
    instance = d4.make_instance(seed=SEED, occurrence_uid=f"d4-credit-{theta}-{action_index}", split="TRAIN", selector_bit=1, candidate_order=0)
    action = json.dumps({"action_id": instance.action_codes[action_index]}, separators=(",", ":")).encode()
    seal = d4.sealed_train(instance, contract, action)
    outcome = d4.independently_evaluate(instance=instance, contract=contract, seal=seal, theta=theta)
    credit = d4.derive_credit(contract=contract, instance=instance, seal=seal, outcome=outcome)
    assert credit["candidate_theta"] == theta
    disposition = d4.make_disposition(contract=contract, credit=credit)
    compiled = d4.compile_recovered(contract=contract, disposition=disposition)
    assert compiled == {"compiler_source_sha256": COMPILER, "latent_bit": theta, "task_contract_sha256": contract.sha256}
    assert "occurrence" not in json.dumps(compiled)


def test_credit_rejects_unsealed_or_tampered_outcome() -> None:
    contract = _contract()
    instance = d4.make_instance(seed=SEED, occurrence_uid="d4-tamper", split="TRAIN", selector_bit=0, candidate_order=1)
    seal = d4.sealed_train(instance, contract, json.dumps({"action_id": instance.action_codes[0]}).encode())
    outcome = d4.independently_evaluate(instance=instance, contract=contract, seal=seal, theta=0)
    outcome["outcome"] = "SUCCESS" if outcome["outcome"] == "FAILURE" else "FAILURE"
    with pytest.raises(d4.D4HeldoutTaskError, match="outcome"):
        d4.derive_credit(contract=contract, instance=instance, seal=seal, outcome=outcome)
    outcome = d4.independently_evaluate(instance=instance, contract=contract, seal=seal, theta=0)
    seal["action_id"] = instance.action_codes[1]
    with pytest.raises(d4.D4HeldoutTaskError, match="seal"):
        d4.derive_credit(contract=contract, instance=instance, seal=seal, outcome=outcome)


def test_schedule_is_jointly_balanced_and_shuffle_preserves_origin_credit() -> None:
    schedule = d4.make_schedule(SEED)
    assert len(schedule) == 32
    assert {(r["theta"], r["selector_bit"], r["candidate_order"], r["sham_theta"]) for r in schedule} == {
        (theta, selector, order, sham) for theta in (0, 1) for selector in (0, 1) for order in (0, 1) for sham in (0, 1)
    }
    assert sum(r["theta"] == 0 for r in schedule) == 16
    assert sum(r["sham_theta"] == 0 for r in schedule) == 16
    pairing = d4.opposite_theta_derangement(schedule)
    by_uid = {r["occurrence_uid"]: r for r in schedule}
    assert all(by_uid[source]["theta"] != by_uid[target]["theta"] for source, target in pairing.items())
    contract = _contract(); row = schedule[0]
    instance = d4.make_instance(seed=SEED, occurrence_uid=str(row["occurrence_uid"]), split="TRAIN", selector_bit=int(row["selector_bit"]), candidate_order=int(row["candidate_order"]))
    seal = d4.sealed_train(instance, contract, json.dumps({"action_id": instance.action_codes[0]}).encode())
    credit = d4.derive_credit(contract=contract, instance=instance, seal=seal, outcome=d4.independently_evaluate(instance=instance, contract=contract, seal=seal, theta=int(row["theta"])))
    control = d4.shuffled_credit_control(contract=contract, credit=credit, receiving_occurrence_uid=pairing[str(row["occurrence_uid"])])
    assert control["credit_sha256"] == credit["credit_sha256"]
    assert control["origin_occurrence_uid"] == credit["origin_occurrence_uid"]
    forged = dict(credit); forged["credit_sha256"] = "0" * 64
    with pytest.raises(d4.D4HeldoutTaskError, match="credit"):
        d4.shuffled_credit_control(contract=contract, credit=forged, receiving_occurrence_uid=pairing[str(row["occurrence_uid"])])


def test_compiler_rejects_instance_or_raw_outcome_in_disposition() -> None:
    contract = _contract()
    invalid = {"schema_version": d4.DISPOSITION_SCHEMA, "task_family": d4.TASK_FAMILY, "task_contract_sha256": contract.sha256, "generator_source_sha256": GENERATOR, "compiler_source_sha256": COMPILER, "transform": "XOR", "latent_bit": 1, "credit_sha256": "0" * 64, "final_instance": "leak"}
    with pytest.raises(d4.D4HeldoutTaskError):
        d4.compile_recovered(contract=contract, disposition=invalid)
