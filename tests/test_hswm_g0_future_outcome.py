from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from hashlib import sha256

import pytest

from hswm.experiments import g0_future_outcome as future
from hswm.experiments import swm0w_beacon as beacon


ROUND = 1000
ROUND_TIME = beacon.quicknet_round_time(ROUND)
DIGESTS = {
    "analysis": "a" * 64,
    "holdout": "b" * 64,
    "arms": "c" * 64,
}


def episodes() -> tuple[future.OpaqueEpisodeV1, ...]:
    return tuple(
        future.OpaqueEpisodeV1(
            episode_uid=f"episode:opaque-{index:02d}",
            action_codes=(f"act-{index:02d}-left", f"act-{index:02d}-right"),
        )
        for index in range(future.EPISODE_COUNT)
    )


def plan() -> future.FutureOutcomePlanV1:
    planned = episodes()
    payload = future.registration_payload(
        experiment_id="g0-future-outcome-known-answer",
        chain_hash=beacon.QUICKNET_CHAIN_HASH,
        round_number=ROUND,
        round_time_unix=ROUND_TIME,
        episodes=planned,
        analysis_sha256=DIGESTS["analysis"],
        holdout_sha256=DIGESTS["holdout"],
        arm_schedule_sha256=DIGESTS["arms"],
    )
    commitment = beacon.make_future_round_commitment(
        experiment_id="g0-future-outcome-known-answer",
        registration_evidence_sha256=beacon.canonical_sha256(payload),
        registered_at_unix=ROUND_TIME - 1,
        round_number=ROUND,
    )
    return future.make_plan(
        commitment=commitment,
        episodes=planned,
        analysis_sha256=DIGESTS["analysis"],
        holdout_sha256=DIGESTS["holdout"],
        arm_schedule_sha256=DIGESTS["arms"],
    )


def seal(value: future.FutureOutcomePlanV1) -> future.PrePulseActionSealV1:
    return future.make_action_seal(
        plan=value,
        completed_at_unix=ROUND_TIME - 1,
        actions=tuple(
            future.SealedActionV1(episode.episode_uid, episode.action_codes[0])
            for episode in value.episodes
        ),
    )


def test_exact_plan_is_bound_to_beacon_registration_evidence() -> None:
    value = plan()
    assert value.registration_payload_sha256 == value.commitment.registration_evidence_sha256
    assert value.registration_payload()["episodes"] == [
        item.canonical() for item in value.episodes
    ]
    assert value.registration_payload()["analysis_sha256"] == DIGESTS["analysis"]


def test_mutating_any_prebound_component_breaks_registration_link() -> None:
    value = plan()
    with pytest.raises(future.G0FutureOutcomeError, match="registration evidence"):
        future.make_plan(
            commitment=value.commitment,
            episodes=value.episodes,
            analysis_sha256="d" * 64,
            holdout_sha256=DIGESTS["holdout"],
            arm_schedule_sha256=DIGESTS["arms"],
        )


def test_plan_rejects_mutable_episode_container_before_it_can_stale_its_binding() -> None:
    value = plan()
    assert type(value.episodes) is tuple
    with pytest.raises(future.G0FutureOutcomeError, match="immutable ordered tuple"):
        replace(value, episodes=list(value.episodes))


def test_plan_factory_normalizes_a_single_pass_episode_iterable_once() -> None:
    value = plan()
    rebuilt = future.make_plan(
        commitment=value.commitment,
        episodes=(episode for episode in value.episodes),
        analysis_sha256=DIGESTS["analysis"],
        holdout_sha256=DIGESTS["holdout"],
        arm_schedule_sha256=DIGESTS["arms"],
    )
    assert rebuilt == value


def test_action_seal_requires_exactly_twenty_unique_pre_pulse_actions() -> None:
    value = plan()
    with pytest.raises(future.G0FutureOutcomeError, match="exactly 20"):
        future.make_action_seal(
            plan=value,
            completed_at_unix=ROUND_TIME - 1,
            actions=tuple(
                future.SealedActionV1(item.episode_uid, item.action_codes[0])
                for item in value.episodes[:-1]
            ),
        )

    with pytest.raises(future.G0FutureOutcomeError, match="SealedActionV1"):
        future.make_action_seal(
            plan=value,
            completed_at_unix=ROUND_TIME - 1,
            actions=("not-an-action",),  # type: ignore[arg-type]
        )
    with pytest.raises(future.G0FutureOutcomeError, match="strictly before pulse"):
        future.make_action_seal(
            plan=value,
            completed_at_unix=ROUND_TIME,
            actions=tuple(
                future.SealedActionV1(item.episode_uid, item.action_codes[0])
                for item in value.episodes
            ),
        )


def test_mapping_is_pure_domain_separated_and_action_order_sensitive() -> None:
    value = plan()
    seed = bytes(range(32))
    first = future.derive_correct_action(
        seed=seed,
        plan_sha256=value.plan_sha256,
        episode=value.episodes[0],
    )
    assert first in value.episodes[0].action_codes
    reversed_episode = future.OpaqueEpisodeV1(
        value.episodes[0].episode_uid,
        tuple(reversed(value.episodes[0].action_codes)),
    )
    second = future.derive_correct_action(
        seed=seed,
        plan_sha256=value.plan_sha256,
        episode=reversed_episode,
    )
    material = b"\x00".join(
        (
            future.MAPPING_DOMAIN,
            seed,
            bytes.fromhex(value.plan_sha256),
            reversed_episode.episode_uid.encode("ascii"),
            *[code.encode("ascii") for code in reversed_episode.action_codes],
        )
    )
    assert second == reversed_episode.action_codes[sha256(material).digest()[0] & 1]
    assert first != "not-an-action"


def test_projection_requires_internal_verified_execution_capability() -> None:
    value = plan()
    with pytest.raises(future.G0FutureOutcomeError, match="verified-execution capability"):
        future._project_after_verified_execution(  # type: ignore[attr-defined]
            plan=value,
            seal=seal(value),
            execution=None,  # type: ignore[arg-type]
        )


@pytest.mark.skipif(
    not beacon.verifier_dependency_available(),
    reason="offline historical BLS known-answer needs installed pinned drand-client",
)
def test_historical_offline_fixture_is_known_answer_only_and_never_promotes_g0() -> None:
    value = plan()
    receipt = future.verify_and_project_offline_known_answer(plan=value, seal=seal(value))
    assert receipt.verification_mode == "offline"
    assert len(receipt.outcomes) == future.EPISODE_COUNT
    assert receipt.outcome_owner_independence_established is False
    assert receipt.cf07_satisfied is False
    assert receipt.g0_pass_allowed is False
    assert receipt.claim_ceiling == future.CLAIM_CEILING
    assert receipt.independent_replay_required is True
    assert receipt.action_chronology_independently_established is False
    assert receipt.registration_timestamp_independently_established is False
    assert receipt.external_singleton_no_retry_registry_implemented is False
    assert receipt.verifier_execution_evidence_embedded is False
    assert receipt.receipt_alone_proves_verifier_execution is False
    assert receipt.receipt_sha256 == beacon.canonical_sha256(receipt.unsigned())
    future.validate_future_outcome_receipt_links(
        plan=value,
        seal=seal(value),
        receipt=receipt,
    )
    assert isinstance(receipt.outcomes[0], future.SyntheticOutcomeV1)
    with pytest.raises(FrozenInstanceError):
        receipt.outcomes[0].is_correct = False  # type: ignore[misc]


@pytest.mark.skipif(
    not beacon.verifier_dependency_available(),
    reason="offline historical BLS known-answer needs installed pinned drand-client",
)
def test_manual_receipt_promotion_or_mutation_is_rejected() -> None:
    value = plan()
    receipt = future.verify_and_project_offline_known_answer(plan=value, seal=seal(value))
    with pytest.raises(future.G0FutureOutcomeError, match="CF-07"):
        replace(receipt, cf07_satisfied=True)
    with pytest.raises(future.G0FutureOutcomeError, match="chronology"):
        replace(receipt, action_chronology_independently_established=True)
    with pytest.raises(future.G0FutureOutcomeError, match="receipt alone"):
        replace(receipt, receipt_alone_proves_verifier_execution=True)
    with pytest.raises(future.G0FutureOutcomeError, match="singleton/no-retry"):
        replace(receipt, external_singleton_no_retry_registry_implemented=True)
    with pytest.raises(future.G0FutureOutcomeError, match="is_correct"):
        replace(receipt.outcomes[0], is_correct=not receipt.outcomes[0].is_correct)


@pytest.mark.skipif(
    not beacon.verifier_dependency_available(),
    reason="offline historical BLS known-answer needs installed pinned drand-client",
)
def test_self_hashed_foreign_outcome_roster_cannot_construct_a_receipt() -> None:
    value = plan()
    original = future.verify_and_project_offline_known_answer(
        plan=value,
        seal=seal(value),
    )
    foreign = tuple(
        future.SyntheticOutcomeV1(
            episode_uid=f"foreign-{index}",
            selected_action_code="opaque-a",
            correct_action_code="opaque-a",
            is_correct=True,
        )
        for index in range(future.EPISODE_COUNT)
    )
    unsigned = {
        **original.unsigned(),
        "outcomes": [item.canonical() for item in foreign],
    }
    with pytest.raises(future.G0FutureOutcomeError, match="verified projection path"):
        replace(
            original,
            outcomes=foreign,
            receipt_sha256=beacon.canonical_sha256(unsigned),
        )
