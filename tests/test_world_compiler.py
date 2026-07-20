"""S1 teeth for the pure evidence-preserving World Compiler."""
from __future__ import annotations

from dataclasses import fields, replace

from world_compiler import compile_world, verify_world_artifact
from world_ir import (
    CompilePolicyV1,
    CompileRejectionV1,
    EvaluationQueryV1,
    ObservationBundleV1,
    RejectCode,
    SourceBundleV1,
    TextSelectorV1,
    WorldArtifactV1,
    canonical_json,
    make_mention_observation,
    make_source_snapshot,
    sha256_text,
)


POLICY = CompilePolicyV1()


def _selector(source, exact: str, occurrence: int = 0) -> TextSelectorV1:
    start = -1
    cursor = 0
    for _ in range(occurrence + 1):
        start = source.content.index(exact, cursor)
        cursor = start + 1
    end = start + len(exact)
    return TextSelectorV1(
        start=start,
        end=end,
        exact=exact,
        prefix=source.content[max(0, start - 8):start],
        suffix=source.content[end:end + 8],
        normalization_policy_hash=POLICY.normalization_policy_hash,
    )


def _fixture():
    a = make_source_snapshot("fixture://alpha", "Alpha Keep :: Alpha Keep met Beta Vale.")
    b = make_source_snapshot("fixture://beta", "Beta Vale :: Beta Vale guarded Cinder Peak.")
    observations = (
        make_mention_observation(a, _selector(a, "Alpha Keep"), "alpha keep", "title", "fixture", "v1"),
        make_mention_observation(a, _selector(a, "Beta Vale"), "beta vale", "body", "fixture", "v1"),
        make_mention_observation(b, _selector(b, "Beta Vale"), "beta vale", "title", "fixture", "v1"),
        make_mention_observation(b, _selector(b, "Cinder Peak"), "cinder peak", "body", "fixture", "v1"),
    )
    return SourceBundleV1((a, b)), ObservationBundleV1(mentions=observations)


def _codes(result) -> set[RejectCode]:
    assert isinstance(result, CompileRejectionV1)
    return {issue.code for issue in result.issues}


def test_compile_world_preserves_exact_evidence_and_stable_bindings():
    sources, observations = _fixture()
    result = compile_world(sources, observations, POLICY)
    assert isinstance(result, WorldArtifactV1)
    assert result.build_id == result.manifest.build_id
    assert len(result.sources) == 2
    assert len(result.evidence_units) == 2
    assert {entity.label for entity in result.entities} == {"alpha keep", "beta vale"}
    # Cinder Peak appears in one body document and is honestly unbound by DF=2.
    cinder = next(m for m in result.mentions if m.normalized_surface == "cinder peak")
    assert cinder.bound_entity_id is None
    for mention in result.mentions:
        source = next(s for s in result.sources if s.source_id == mention.source_id)
        assert source.content[mention.selector.start:mention.selector.end] == mention.surface
    assert all(target.member_entity_ids for target in result.field_targets)
    assert result.policy == POLICY
    assert result.mention_observations
    assert verify_world_artifact(result) == ()


def test_source_tamper_is_typed_rejection():
    sources, observations = _fixture()
    bad = replace(sources.sources[0], content=sources.sources[0].content + " tampered")
    result = compile_world(SourceBundleV1((bad, sources.sources[1])), observations, POLICY)
    assert _codes(result) == {RejectCode.SOURCE_HASH_MISMATCH}


def test_selector_quote_tamper_is_typed_rejection():
    sources, observations = _fixture()
    original = observations.mentions[0]
    selector = replace(original.selector, exact="Alphx Keep")
    tampered = replace(original, selector=selector, output_sha256=sha256_text(selector.exact))
    result = compile_world(sources, replace(observations, mentions=(tampered,) + observations.mentions[1:]), POLICY)
    assert RejectCode.SELECTOR_QUOTE_MISMATCH in _codes(result)


def test_dangling_observation_source_is_rejected():
    sources, observations = _fixture()
    bad = replace(observations.mentions[0], source_id="hswm:src:v1:missing")
    result = compile_world(sources, replace(observations, mentions=(bad,) + observations.mentions[1:]), POLICY)
    assert RejectCode.DANGLING_REFERENCE in _codes(result)


def test_input_order_is_bit_invariant():
    sources, observations = _fixture()
    a = compile_world(sources, observations, POLICY)
    b = compile_world(
        SourceBundleV1(tuple(reversed(sources.sources))),
        ObservationBundleV1(mentions=tuple(reversed(observations.mentions))),
        POLICY,
    )
    assert isinstance(a, WorldArtifactV1) and isinstance(b, WorldArtifactV1)
    assert a.build_id == b.build_id
    assert canonical_json(a) == canonical_json(b)


def test_conflict_rejection_is_input_order_invariant():
    sources, observations = _fixture()
    conflict = replace(sources.sources[0], locator="fixture://conflict")
    a = compile_world(
        SourceBundleV1((sources.sources[0], conflict, sources.sources[1])), observations, POLICY,
    )
    b = compile_world(
        SourceBundleV1((conflict, sources.sources[0], sources.sources[1])), observations, POLICY,
    )
    assert isinstance(a, CompileRejectionV1) and isinstance(b, CompileRejectionV1)
    assert canonical_json(a) == canonical_json(b)


def test_duplicate_id_with_different_payload_rejected():
    sources, observations = _fixture()
    conflict = replace(sources.sources[0], locator="fixture://conflict")
    result = compile_world(
        SourceBundleV1((sources.sources[0], conflict, sources.sources[1])),
        observations,
        POLICY,
    )
    assert RejectCode.DUPLICATE_ID_CONFLICT in _codes(result)


def test_observation_id_tamper_is_rejected():
    sources, observations = _fixture()
    tampered = replace(observations.mentions[0], observation_id="hswm:obs_mention:v1:forged")
    result = compile_world(
        sources,
        replace(observations, mentions=(tampered,) + observations.mentions[1:]),
        POLICY,
    )
    assert _codes(result) == {RejectCode.OBSERVATION_HASH_MISMATCH}


def test_zero_width_title_cannot_manufacture_entity():
    sources, observations = _fixture()
    source = sources.sources[0]
    selector = TextSelectorV1(
        start=0, end=0, exact="",
        normalization_policy_hash=POLICY.normalization_policy_hash,
    )
    ghost = make_mention_observation(source, selector, "ghost", "title", "fixture", "v1")
    result = compile_world(sources, replace(observations, mentions=(ghost,) + observations.mentions), POLICY)
    assert RejectCode.INVALID_SELECTOR_RANGE in _codes(result)


def test_unsupported_projection_fails_closed():
    sources, observations = _fixture()
    result = compile_world(sources, observations, replace(POLICY, projection="nary-v1"))
    assert RejectCode.SCHEMA_INCOMPATIBLE in _codes(result)


def test_self_verifier_catches_artifact_tamper():
    sources, observations = _fixture()
    result = compile_world(sources, observations, POLICY)
    assert isinstance(result, WorldArtifactV1)
    issues = verify_world_artifact(replace(result, build_id="hswm:world:v1:forged"))
    assert {issue.code for issue in issues} == {RejectCode.CANONICALIZATION_ERROR}


def test_evaluation_labels_have_no_core_ir_field():
    forbidden = {"question", "answer", "answer_aliases", "hop", "gold", "is_supporting"}
    for record_type in (type(_fixture()[0].sources[0]), WorldArtifactV1):
        assert forbidden.isdisjoint({field.name for field in fields(record_type)})
    # Evaluation stays representable, but it is not an input to compile_world.
    query = EvaluationQueryV1("q:0", "q0", "changed?", "changed", 9, ())
    assert query.question == "changed?"


def test_canonical_build_id_golden():
    sources, observations = _fixture()
    result = compile_world(sources, observations, POLICY)
    assert isinstance(result, WorldArtifactV1)
    assert result.build_id == (
        "hswm:world:v1:8b24cb7a547fbc2bcd8dc06cc822d601"
        "2b9f8426fba1975ece5632e58e099897"
    )
