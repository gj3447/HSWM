from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import numpy as np
import pytest

from hswm.experiments.continual import (
    ArmAnswer,
    ArmUpdate,
    LearningBatch,
    bootstrap_lcb,
    canonical_sha256,
    deterministic_test_seed,
    evaluate_confirmatory,
    exact_sign_flip_pvalue,
    generate_stream,
    holm_adjust,
    make_confirmatory_score_bundle,
    paired_stream_deltas,
    parse_choice,
    run_prequential,
    validate_stream,
    validate_stream_set,
)


class _GraphArm:
    def __init__(self, name: str, events: list[str], *, persist: bool) -> None:
        self.name = name
        self.events = events
        self.persist = persist
        self.edges: dict[tuple[str, str], str] = {}

    def state_canonical_bytes(self) -> bytes:
        value = [(*key, target) for key, target in sorted(self.edges.items())]
        return str(value).encode("ascii")

    def answer(self, probe):
        assert not hasattr(probe, "answer")
        assert not hasattr(probe, "support_edge_ids")
        self.events.append(f"answer:{probe.step}:{self.name}")
        node = probe.source
        for relation in probe.relations:
            target = self.edges.get((node, relation))
            if target is None:
                node = probe.choices[0]
                break
            node = target
        response = '{"choice":"' + node + '"}'
        return ArmAnswer(
            response_text=response,
            receipt_sha256=canonical_sha256([self.name, probe.step, response]),
            calls=1,
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
        )

    def update(self, batch: LearningBatch):
        assert not hasattr(batch, "stream")
        assert batch.episode_id.startswith("episode_")
        self.events.append(f"update:{batch.after_step}:{self.name}")
        if self.persist:
            for token in batch.learning_tokens:
                assert not hasattr(token, "edge_id")
                assert not hasattr(token, "reveal_step")
                self.edges[(token.source, token.relation)] = token.target
        return ArmUpdate(
            receipt_sha256=canonical_sha256([self.name, batch.canonical()]),
            calls=1,
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
        )


class _FixedOutcomeArm(_GraphArm):
    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        answers: dict[tuple[str, tuple[str, ...]], str],
        success: tuple[bool, ...],
    ) -> None:
        super().__init__(name, events, persist=False)
        self.answers = answers
        self.success = success

    def answer(self, probe):
        self.events.append(f"answer:{probe.step}:{self.name}")
        answer = self.answers[(probe.source, probe.relations)]
        if self.success[probe.step - 1]:
            choice = answer
        else:
            choice = next(value for value in probe.choices if value != answer)
        response = '{"choice":"' + choice + '"}'
        return ArmAnswer(
            response_text=response,
            receipt_sha256=canonical_sha256([self.name, probe.step, response]),
            calls=1,
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
        )


def test_nonce_graph_stream_is_deterministic_disjoint_and_prequential() -> None:
    first = generate_stream(0, seed_preimage=deterministic_test_seed(0))
    repeated = generate_stream(0, seed_preimage=deterministic_test_seed(0))
    second = generate_stream(1, seed_preimage=deterministic_test_seed(1))

    assert first.canonical() == repeated.canonical()
    assert first.manifest_sha256 == repeated.manifest_sha256
    assert first.manifest_sha256 != second.manifest_sha256

    first_entities = {
        value
        for edge in first.edges
        for value in (edge.source, edge.target)
    }
    second_entities = {
        value
        for edge in second.edges
        for value in (edge.source, edge.target)
    }
    assert first_entities.isdisjoint(second_entities)

    for query in first.queries:
        cutoff = max(0, query.step - first.delay)
        assert max(query.support_reveal_steps) <= cutoff
        if query.step > first.delay:
            assert max(query.support_reveal_steps) == cutoff
        test_token = query.test_token()
        assert "answer" not in test_token
        assert "support_edge_ids" not in test_token
        probe = query.public_probe()
        assert not hasattr(probe, "answer")
        assert not hasattr(probe, "support_edge_ids")


def test_stream_validation_rejects_hash_and_chronology_tampering() -> None:
    stream = generate_stream(3, seed_preimage=deterministic_test_seed(3))
    with pytest.raises(ValueError, match="content hash"):
        validate_stream(replace(stream, manifest_sha256="0" * 64))

    query = stream.queries[-1]
    bad_query = replace(
        query,
        support_reveal_steps=tuple(step + stream.horizon for step in query.support_reveal_steps),
    )
    bad_queries = (*stream.queries[:-1], bad_query)
    tampered = replace(stream, queries=bad_queries)
    tampered = replace(tampered, manifest_sha256=tampered.manifest_sha256)
    with pytest.raises(ValueError):
        validate_stream(tampered)


def test_stream_set_binds_independent_worlds_before_statistics() -> None:
    manifests = tuple(
        generate_stream(index, seed_preimage=deterministic_test_seed(index), horizon=6)
        for index in range(4)
    )
    receipt = validate_stream_set(
        manifests,
        expected_count=4,
        expected_horizon=6,
    )
    assert receipt.validation_sha256 == canonical_sha256(receipt.unsigned())

    duplicated_world = generate_stream(
        1,
        seed_preimage=deterministic_test_seed(0),
        horizon=6,
    )
    with pytest.raises(ValueError, match="seed_sha256.*unique"):
        validate_stream_set(
            (manifests[0], duplicated_world, *manifests[2:]),
            expected_count=4,
            expected_horizon=6,
        )


def test_choice_parser_is_strict_and_programmatic() -> None:
    choices = ("n_a", "n_b")
    assert parse_choice('{"choice":"n_b"}', choices=choices) == "n_b"
    assert parse_choice('{"choice":"n_b","reason":"x"}', choices=choices) is None
    assert parse_choice("```json\n{\"choice\":\"n_b\"}\n```", choices=choices) is None
    assert parse_choice('{"choice":"n_c"}', choices=choices) is None
    assert parse_choice(
        '{"choice":"n_a","choice":"n_b"}', choices=choices
    ) is None


def test_stream_level_statistics_do_not_treat_steps_as_independent() -> None:
    hswm = [[1, 1, 1, 1], [1, 1, 0, 1], [1, 1, 1, 0], [1, 1, 1, 1]]
    control = [[0, 0, 1, 0], [0, 1, 0, 0], [1, 0, 0, 0], [0, 1, 0, 1]]
    deltas = paired_stream_deltas(hswm, control)
    np.testing.assert_allclose(deltas, (0.75, 0.5, 0.5, 0.5))
    assert exact_sign_flip_pvalue(deltas) == pytest.approx(1 / 16)
    assert bootstrap_lcb(deltas, resamples=2_000) > 0


def test_confirmatory_verdict_binds_24_stream_decision_rule() -> None:
    manifests = tuple(
        generate_stream(index, seed_preimage=deterministic_test_seed(index))
        for index in range(24)
    )
    stream_set = validate_stream_set(manifests, expected_count=24)
    runs = {}
    for manifest in manifests:
        answers = {
            (query.source, query.relations): query.answer
            for query in manifest.queries
        }
        events: list[str] = []
        runs[manifest.stream] = run_prequential(
            manifest,
            (
                _FixedOutcomeArm(
                    "hswm", events, answers=answers, success=(True,) * 20
                ),
                _FixedOutcomeArm(
                    "reset",
                    events,
                    answers=answers,
                    success=tuple(bool(step % 2) for step in range(20)),
                ),
                _FixedOutcomeArm(
                    "no_write",
                    events,
                    answers=answers,
                    success=tuple(not bool(step % 2) for step in range(20)),
                ),
                _FixedOutcomeArm(
                    "plain",
                    events,
                    answers=answers,
                    success=tuple(step % 4 != 0 for step in range(20)),
                ),
            ),
        )
    manifest_map = {manifest.stream: manifest for manifest in manifests}
    bundle = make_confirmatory_score_bundle(stream_set, manifest_map, runs)
    verdict = evaluate_confirmatory(stream_set, bundle, manifest_map, runs)
    assert verdict.passed
    assert verdict.verdict_sha256 == canonical_sha256(verdict.unsigned())
    assert all(comparison.passed for comparison in verdict.comparisons)

    row = bundle.rows[0]
    arm_scores = dict(row.arm_scores)
    arm_scores["plain"] = (not arm_scores["plain"][0], *arm_scores["plain"][1:])
    tampered_row = replace(
        row,
        arm_scores=tuple((arm, arm_scores[arm]) for arm, _ in row.arm_scores),
    )
    tampered_unsigned = {
        **bundle.unsigned(),
        "rows": [tampered_row.canonical(), *[item.canonical() for item in bundle.rows[1:]]],
    }
    tampered_bundle = replace(
        bundle,
        rows=(tampered_row, *bundle.rows[1:]),
        score_bundle_sha256=canonical_sha256(tampered_unsigned),
    )
    with pytest.raises(ValueError, match="canonical stream runs"):
        evaluate_confirmatory(stream_set, tampered_bundle, manifest_map, runs)

    wrong_runs = {**runs, 0: runs[1]}
    with pytest.raises(ValueError, match="manifest differs"):
        make_confirmatory_score_bundle(stream_set, manifest_map, wrong_runs)

    original_run = runs[0]
    changed_result = replace(
        original_run.results[0],
        correct=not original_run.results[0].correct,
    )
    changed_results = (changed_result, *original_run.results[1:])
    unhashed_run = replace(
        original_run,
        results=changed_results,
        run_sha256="0" * 64,
    )
    changed_run = replace(
        unhashed_run,
        run_sha256=canonical_sha256(unhashed_run.unsigned()),
    )
    with pytest.raises(ValueError, match="programmatic regrading"):
        make_confirmatory_score_bundle(
            stream_set,
            manifest_map,
            {**runs, 0: changed_run},
        )


def test_prequential_runner_tests_every_arm_before_any_update() -> None:
    secret = b"held-out-confirmatory-seed-preimage-09"
    manifest = generate_stream(9, seed_preimage=secret, horizon=6)
    events: list[str] = []
    run = run_prequential(
        manifest,
        (
            _GraphArm("hswm", events, persist=True),
            _GraphArm("no_write", events, persist=False),
        ),
    )

    assert run.run_sha256 == canonical_sha256(run.unsigned())
    assert all(
        result.genesis_state_sha256
        and result.post_warmup_state_sha256
        for result in run.warmup_results
    )
    for step in range(1, 7):
        answer_positions = [
            events.index(f"answer:{step}:{name}") for name in ("hswm", "no_write")
        ]
        update_positions = [
            events.index(f"update:{step}:{name}") for name in ("hswm", "no_write")
        ]
        assert max(answer_positions) < min(update_positions)
    hswm_results = [result for result in run.results if result.arm == "hswm"]
    assert any(result.correct for result in hswm_results)
    assert all(
        result.pre_state_sha256 == result.post_test_state_sha256
        for result in run.results
    )


def test_arm_surface_does_not_expose_seed_or_reconstructible_stream_index() -> None:
    secret = b"unrevealed-confirmatory-seed-preimage-17"
    manifest = generate_stream(17, seed_preimage=secret, horizon=6)
    events: list[str] = []
    run = run_prequential(manifest, (_GraphArm("inspect", events, persist=True),))

    assert manifest.seed_sha256 == sha256(secret).hexdigest()
    assert secret.hex() not in str(run.canonical())
    public_sources = {
        generate_stream(
            candidate,
            seed_preimage=deterministic_test_seed(candidate),
            horizon=6,
        ).queries[0].source
        for candidate in range(24)
    }
    assert manifest.queries[0].source not in public_sources
    with pytest.raises(TypeError):
        generate_stream(17)  # type: ignore[call-arg]


def test_holm_adjustment_is_monotone_in_sorted_order() -> None:
    adjusted = holm_adjust({"reset": 0.01, "no_write": 0.02, "plain": 0.03})
    assert adjusted == pytest.approx(
        {"reset": 0.03, "no_write": 0.04, "plain": 0.04}
    )
