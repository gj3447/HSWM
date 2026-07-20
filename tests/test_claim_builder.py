"""B3 evidence-bound n-ary claim builder teeth (fully offline)."""
from dataclasses import fields, replace
import inspect
import json
import socket

import pytest

import claim_builder as cb
from world_ir import sha256_text


PROMPT_SHA = sha256_text("frozen claim prompt v1")
CONFIG_SHA = sha256_text("temperature=0;schema=strict-v1")


def _paragraphs() -> tuple[cb.ParagraphInputV1, ...]:
    return (
        cb.ParagraphInputV1(
            source_id="src:alice",
            title="Alice",
            text="Alice gave Bob a map in Paris. Willow Market stayed closed.",
        ),
        cb.ParagraphInputV1(
            source_id="src:bob",
            title="Bob",
            text="Bob later studied the map.",
        ),
        cb.ParagraphInputV1(
            source_id="src:paris",
            title="Paris",
            text="Paris is a city.",
        ),
        cb.ParagraphInputV1(
            source_id="src:willow",
            title="Willow Market",
            text="Willow Market sells fruit.",
        ),
    )


def _claim_payload(*, argument_exact: str = "Bob", include_label: bool = False) -> str:
    payload = {
        "schema_version": cb.EXTRACTION_SCHEMA_VERSION,
        "claims": [{
            "subject": {"start": 0, "end": 5, "exact": "Alice"},
            "predicate": {"start": 6, "end": 10, "exact": "gave"},
            "arguments": [
                {"role": "recipient", "start": 11, "end": 14,
                 "exact": argument_exact},
                {"role": "object", "start": 15, "end": 20, "exact": "a map"},
                {"role": "location", "start": 24, "end": 29, "exact": "Paris"},
            ],
        }],
    }
    if include_label:
        payload["claims"][0]["gold"] = True
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _extraction(payload: str | None = None) -> cb.FrozenExtractionV1:
    return cb.freeze_extraction(
        "src:alice",
        _claim_payload() if payload is None else payload,
        producer="offline-fixture",
        model_revision="fixture-model@sha256:0123",
        prompt_sha256=PROMPT_SHA,
        config_sha256=CONFIG_SHA,
    )


def test_input_boundary_and_compiler_signature_exclude_qa_labels():
    assert [field.name for field in fields(cb.ParagraphInputV1)] == [
        "source_id", "title", "text",
    ]
    assert list(inspect.signature(cb.compile_claim_graph).parameters) == [
        "paragraphs", "frozen_extractions",
    ]
    with pytest.raises(TypeError, match="raw QA rows are forbidden"):
        cb.compile_claim_graph([{
            "source_id": "src:x", "title": "X", "text": "X exists.",
            "question": "leak", "answer": "leak", "gold": True, "hop": 9,
        }], ())


def test_verified_nary_claim_is_not_collapsed_into_binary_facts():
    build = cb.compile_claim_graph(_paragraphs(), (_extraction(),))

    assert cb.verify_claim_graph(build) == ()
    assert len(build.claim_observations) == 1
    assert len(build.nary_claims) == 1
    claim = build.nary_claims[0]
    assert claim.subject.exact == "Alice"
    assert claim.predicate.exact == "gave"
    assert [(role.role, role.exact) for role in claim.arguments] == [
        ("recipient", "Bob"),
        ("object", "a map"),
        ("location", "Paris"),
    ]

    # One n-ary record yields role-carrying graph projections to the two
    # arguments that resolve to paragraph titles.  "a map" remains in the
    # claim even though it has no paragraph target.
    claim_arcs = [
        arc for arc in build.directed_arcs
        if arc.origin == "verified_nary_title"
    ]
    assert len(claim_arcs) == 2
    assert {
        (arc.object_source_id, arc.object_role, arc.claim_id,
         arc.predicate_role_id)
        for arc in claim_arcs
    } == {
        ("src:bob", "recipient", claim.claim_id, claim.predicate.role_id),
        ("src:paris", "location", claim.claim_id, claim.predicate.role_id),
    }
    assert all(arc.source_role_id and arc.target_role_id for arc in claim_arcs)
    assert all(
        arc.source_evidence_span.exact in {"Bob", "Paris"}
        and arc.target_evidence_span.text_scope == "title"
        for arc in claim_arcs
    )
    assert build.stats["role_arity"] == (5,)


def test_exact_spans_and_all_extractor_provenance_are_preserved():
    extraction = _extraction()
    build = cb.compile_claim_graph(_paragraphs(), (extraction,))
    observation = build.claim_observations[0]
    paragraph = next(item for item in build.paragraphs if item.source_id == "src:alice")
    assert observation.producer == extraction.producer
    assert observation.model_revision == extraction.model_revision
    assert observation.prompt_sha256 == PROMPT_SHA
    assert observation.config_sha256 == CONFIG_SHA
    assert observation.output_sha256 == sha256_text(extraction.payload_json)
    for role in (observation.subject, observation.predicate, *observation.arguments):
        assert paragraph.text[role.start:role.end] == role.exact
        assert role.source_text_sha256 == sha256_text(paragraph.text)
        assert role.offset_unit == cb.OFFSET_UNIT


def test_hallucinated_argument_and_tampered_output_hash_are_quarantined():
    hallucinated = _extraction(_claim_payload(argument_exact="Eve"))
    parsed = cb.parse_extraction_payload(_paragraphs()[0], hallucinated)
    assert parsed.observations == ()
    assert [item.reason for item in parsed.quarantines] == ["exact_span_mismatch"]

    valid = _extraction()
    hash_tampered = replace(valid, output_sha256="0" * 64)
    parsed = cb.parse_extraction_payload(_paragraphs()[0], hash_tampered)
    assert parsed.observations == ()
    assert [item.reason for item in parsed.quarantines] == ["output_hash_mismatch"]


def test_post_compile_span_tamper_is_detected_by_integrity_verifier():
    build = cb.compile_claim_graph(_paragraphs(), (_extraction(),))
    observation = build.claim_observations[0]
    bad_subject = replace(observation.subject, exact="Mallory")
    bad_observation = replace(observation, subject=bad_subject)
    tampered = replace(
        build,
        claim_observations=(bad_observation,),
    )
    issues = cb.verify_claim_graph(tampered)
    assert any(issue.startswith("role_quote_mismatch:") for issue in issues)
    assert any(issue.startswith("observation_id_mismatch:") for issue in issues)


def test_evaluation_label_leakage_fails_closed_before_schema_acceptance():
    extraction = _extraction(_claim_payload(include_label=True))
    parsed = cb.parse_extraction_payload(_paragraphs()[0], extraction)
    assert parsed.observations == ()
    assert len(parsed.quarantines) == 1
    assert parsed.quarantines[0].reason == "evaluation_label_leakage"
    assert "gold" in parsed.quarantines[0].detail


def test_duplicate_json_keys_are_not_silently_overwritten():
    payload = (
        '{"schema_version":"hswm-claim-extraction/v1",'
        '"schema_version":"hswm-claim-extraction/v1","claims":[]}'
    )
    parsed = cb.parse_extraction_payload(_paragraphs()[0], _extraction(payload))
    assert parsed.observations == ()
    assert parsed.quarantines[0].reason == "duplicate_json_key"


def test_title_anchor_is_auditable_fallback_not_a_fake_claim():
    build = cb.compile_claim_graph(_paragraphs(), ())
    assert build.nary_claims == ()
    assert build.claim_observations == ()
    assert build.directed_arcs
    assert all(arc.origin == "title_anchor_fallback" for arc in build.directed_arcs)
    assert {
        (arc.subject_source_id, arc.object_source_id)
        for arc in build.directed_arcs
    } >= {
        ("src:alice", "src:bob"),
        ("src:alice", "src:paris"),
        ("src:alice", "src:willow"),
    }
    assert cb.verify_claim_graph(build) == ()


def test_input_order_does_not_change_canonical_build_or_projection():
    paragraphs = _paragraphs()
    extraction = _extraction()
    first = cb.compile_claim_graph(paragraphs, (extraction,))
    second = cb.compile_claim_graph(tuple(reversed(paragraphs)), (extraction,))
    assert first == second
    assert first.build_id == second.build_id
    assert first.paragraph_graph.edge_pairs() == second.paragraph_graph.edge_pairs()


def _shared_entity_fixture():
    paragraphs = (
        cb.ParagraphInputV1(
            "src:green", "Green History",
            "Green was formed by Steve Hillage in 1975."
        ),
        cb.ParagraphInputV1(
            "src:miquette", "Collaboration Record",
            "Steve Hillage collaborated with Miquette Giraudy on records."
        ),
    )
    green_payload = json.dumps({
        "schema_version": cb.EXTRACTION_SCHEMA_VERSION,
        "claims": [{
            "subject": {"start": 0, "end": 5, "exact": "Green"},
            "predicate": {"start": 6, "end": 19, "exact": "was formed by"},
            "arguments": [{
                "role": "founder", "start": 20, "end": 33,
                "exact": "Steve Hillage",
            }],
        }],
    }, separators=(",", ":"))
    miquette_payload = json.dumps({
        "schema_version": cb.EXTRACTION_SCHEMA_VERSION,
        "claims": [{
            "subject": {"start": 0, "end": 13, "exact": "Steve Hillage"},
            "predicate": {"start": 14, "end": 31, "exact": "collaborated with"},
            "arguments": [{
                "role": "collaborator", "start": 32, "end": 48,
                "exact": "Miquette Giraudy",
            }],
        }],
    }, separators=(",", ":"))
    extractions = tuple(
        cb.freeze_extraction(
            source_id, payload, producer="offline-fixture",
            model_revision="fixture-model@sha256:0123",
            prompt_sha256=PROMPT_SHA, config_sha256=CONFIG_SHA,
        )
        for source_id, payload in (
            ("src:green", green_payload), ("src:miquette", miquette_payload)
        )
    )
    return paragraphs, extractions


def test_shared_exact_claim_roles_create_topology_beyond_title_anchors():
    paragraphs, extractions = _shared_entity_fixture()
    build = cb.compile_claim_graph(paragraphs, extractions)
    assert cb.verify_claim_graph(build) == ()
    assert {
        (link.subject_source_id, link.object_source_id)
        for link in build.title_anchor_fallback.directed_links
    } == set()  # there is deliberately no Steve Hillage title paragraph

    shared = [
        arc for arc in build.directed_arcs
        if arc.origin == "verified_shared_entity"
    ]
    assert [(arc.subject_source_id, arc.object_source_id) for arc in shared] == [
        ("src:green", "src:miquette")
    ]
    assert len({arc.join_entity_id for arc in shared}) == 1
    assert all(
        arc.source_evidence_span.exact == "Steve Hillage"
        and arc.target_evidence_span.exact == "Steve Hillage"
        and arc.source_role_id != arc.target_role_id
        and not arc.evidence_receipt_ids
        for arc in shared
    )
    claim_by_id = {claim.claim_id: claim for claim in build.nary_claims}
    assert claim_by_id[shared[0].claim_id].arguments[0].role_kind == "argument"
    assert claim_by_id[shared[0].target_claim_id].subject.role_kind == "subject"
    # The invalid subject->argument reverse is retained as a typed refusal,
    # not silently emitted as a symmetric edge.
    direction_rejections = [
        item for item in build.quarantined_shared_entities
        if item.reason == "role_direction_mismatch"
    ]
    assert len(direction_rejections) == 1
    assert direction_rejections[0].candidate_pair_count == 2
    assert direction_rejections[0].rejected_pair_count == 1
    graph_pairs = {
        (
            build.paragraph_graph.target_source_ids[source],
            build.paragraph_graph.target_source_ids[target],
        )
        for source, target in build.paragraph_graph.edge_pairs()
    }
    assert graph_pairs == {("src:green", "src:miquette")}
    assert ("src:miquette", "src:green") not in graph_pairs
    assert build == cb.compile_claim_graph(
        tuple(reversed(paragraphs)), tuple(reversed(extractions))
    )


def _single_argument_extraction(
    paragraph: cb.ParagraphInputV1,
    *,
    predicate: str,
    argument: str,
    role: str = "related_entity",
    subject: str | None = None,
) -> cb.FrozenExtractionV1:
    subject_exact = paragraph.title if subject is None else subject
    subject_start = paragraph.text.index(subject_exact)
    predicate_start = paragraph.text.index(predicate)
    argument_start = paragraph.text.index(argument)
    payload = json.dumps({
        "schema_version": cb.EXTRACTION_SCHEMA_VERSION,
        "claims": [{
            "subject": {
                "start": subject_start,
                "end": subject_start + len(subject_exact),
                "exact": subject_exact,
            },
            "predicate": {
                "start": predicate_start,
                "end": predicate_start + len(predicate),
                "exact": predicate,
            },
            "arguments": [{
                "role": role,
                "start": argument_start,
                "end": argument_start + len(argument),
                "exact": argument,
            }],
        }],
    }, separators=(",", ":"))
    return cb.freeze_extraction(
        paragraph.source_id, payload, producer="offline-fixture",
        model_revision="fixture-model@sha256:0123",
        prompt_sha256=PROMPT_SHA, config_sha256=CONFIG_SHA,
    )


def test_generic_and_hub_shared_surfaces_are_quarantined_not_percolated():
    generic_paragraphs = (
        cb.ParagraphInputV1("src:alpha", "Alpha", "Alpha followed the band yesterday."),
        cb.ParagraphInputV1("src:beta", "Beta", "Beta criticized the band publicly."),
    )
    generic_extractions = (
        _single_argument_extraction(
            generic_paragraphs[0], predicate="followed", argument="the band"
        ),
        _single_argument_extraction(
            generic_paragraphs[1], predicate="criticized", argument="the band"
        ),
    )
    generic = cb.compile_claim_graph(generic_paragraphs, generic_extractions)
    assert [item.reason for item in generic.quarantined_shared_entities] == [
        "generic_surface"
    ]
    assert not any(
        arc.origin == "verified_shared_entity" for arc in generic.directed_arcs
    )

    assert cb.SHARED_ENTITY_POLICY.max_document_frequency == 8
    hub_paragraphs = tuple(
        cb.ParagraphInputV1(
            f"src:node-{index}", f"Node {index}",
            f"Node {index} references Common Shared Entity."
        )
        for index in range(9)
    )
    hub_extractions = tuple(
        _single_argument_extraction(
            paragraph, predicate="references", argument="Common Shared Entity"
        )
        for paragraph in hub_paragraphs
    )
    hub = cb.compile_claim_graph(hub_paragraphs, hub_extractions)
    assert [item.reason for item in hub.quarantined_shared_entities] == [
        "hub_document_frequency"
    ]
    assert hub.quarantined_shared_entities[0].document_frequency == 9
    assert not any(arc.origin == "verified_shared_entity" for arc in hub.directed_arcs)
    assert cb.verify_claim_graph(generic) == ()
    assert cb.verify_claim_graph(hub) == ()


def test_multiple_same_surface_roles_in_one_document_are_ambiguous():
    alpha = cb.ParagraphInputV1(
        "src:alpha", "Alpha",
        "Alpha met Steve Hillage and praised Steve Hillage.",
    )
    beta = cb.ParagraphInputV1(
        "src:beta", "Beta", "Beta cited Steve Hillage.",
    )
    first = alpha.text.index("Steve Hillage")
    second = alpha.text.index("Steve Hillage", first + 1)
    alpha_payload = json.dumps({
        "schema_version": cb.EXTRACTION_SCHEMA_VERSION,
        "claims": [
            {
                "subject": {"start": 0, "end": 5, "exact": "Alpha"},
                "predicate": {"start": 6, "end": 9, "exact": "met"},
                "arguments": [{
                    "role": "related_entity", "start": first,
                    "end": first + len("Steve Hillage"), "exact": "Steve Hillage",
                }],
            },
            {
                "subject": {"start": 0, "end": 5, "exact": "Alpha"},
                "predicate": {"start": 28, "end": 35, "exact": "praised"},
                "arguments": [{
                    "role": "related_entity", "start": second,
                    "end": second + len("Steve Hillage"), "exact": "Steve Hillage",
                }],
            },
        ],
    }, separators=(",", ":"))
    alpha_extraction = cb.freeze_extraction(
        alpha.source_id, alpha_payload, producer="offline-fixture",
        model_revision="fixture-model@sha256:0123",
        prompt_sha256=PROMPT_SHA, config_sha256=CONFIG_SHA,
    )
    beta_extraction = _single_argument_extraction(
        beta, predicate="cited", argument="Steve Hillage"
    )
    build = cb.compile_claim_graph(
        (alpha, beta), (alpha_extraction, beta_extraction)
    )
    assert [item.reason for item in build.quarantined_shared_entities] == [
        "within_document_ambiguity"
    ]
    assert not any(
        arc.origin == "verified_shared_entity" for arc in build.directed_arcs
    )
    assert cb.verify_claim_graph(build) == ()


def test_two_argument_mentions_do_not_license_a_composition_edge():
    paragraphs = (
        cb.ParagraphInputV1(
            "src:a", "Alpha Person", "Alpha Person met Steve Hillage."
        ),
        cb.ParagraphInputV1(
            "src:b", "Beta Person", "Beta Person cited Steve Hillage."
        ),
    )
    extractions = (
        _single_argument_extraction(
            paragraphs[0], predicate="met", argument="Steve Hillage"
        ),
        _single_argument_extraction(
            paragraphs[1], predicate="cited", argument="Steve Hillage"
        ),
    )
    build = cb.compile_claim_graph(paragraphs, extractions)
    assert not any(
        arc.origin == "verified_shared_entity" for arc in build.directed_arcs
    )
    refusal = next(
        item for item in build.quarantined_shared_entities
        if item.reason == "role_direction_mismatch"
    )
    assert refusal.candidate_pair_count == refusal.rejected_pair_count == 2
    assert cb.verify_claim_graph(build) == ()


def test_single_token_homonym_is_quarantined_even_with_argument_to_subject_shape():
    paragraphs = (
        cb.ParagraphInputV1("src:a", "Alpha Record", "Alpha met Jordan."),
        cb.ParagraphInputV1("src:b", "Beta Record", "Jordan joined Beta."),
    )
    extractions = (
        _single_argument_extraction(
            paragraphs[0], subject="Alpha", predicate="met", argument="Jordan"
        ),
        _single_argument_extraction(
            paragraphs[1], subject="Jordan", predicate="joined", argument="Beta"
        ),
    )
    build = cb.compile_claim_graph(paragraphs, extractions)
    refusal = next(
        item for item in build.quarantined_shared_entities
        if item.normalized_surface == "jordan"
    )
    assert refusal.reason == "homonym_prone_surface"
    assert refusal.candidate_pair_count == refusal.rejected_pair_count == 2
    assert not any(
        arc.origin == "verified_shared_entity" for arc in build.directed_arcs
    )
    assert cb.verify_claim_graph(build) == ()


def test_uncased_non_ascii_name_shape_remains_eligible():
    paragraphs = (
        cb.ParagraphInputV1("src:ko-a", "첫 기록", "밴드는 김 영준을 만났다."),
        cb.ParagraphInputV1("src:ko-b", "둘째 기록", "김 영준은 새 앨범을 만들었다."),
    )
    extractions = (
        _single_argument_extraction(
            paragraphs[0], subject="밴드는", predicate="만났다", argument="김 영준"
        ),
        _single_argument_extraction(
            paragraphs[1], subject="김 영준", predicate="만들었다", argument="새 앨범"
        ),
    )
    build = cb.compile_claim_graph(paragraphs, extractions)
    shared = [
        arc for arc in build.directed_arcs
        if arc.origin == "verified_shared_entity"
    ]
    assert [(arc.subject_source_id, arc.object_source_id) for arc in shared] == [
        ("src:ko-a", "src:ko-b")
    ]
    assert shared[0].source_evidence_span.normalized_surface == "김 영준"
    assert cb.verify_claim_graph(build) == ()


def test_unique_title_anchor_binds_to_target_subject_claim_for_continuation():
    paragraphs = (
        cb.ParagraphInputV1(
            "src:engine", "Engine History", "The engine inspired Ada Lovelace."
        ),
        cb.ParagraphInputV1(
            "src:ada", "Ada Lovelace",
            "Ada Lovelace wrote the first algorithm."
        ),
    )
    source_extraction = _single_argument_extraction(
        paragraphs[0], subject="The engine", predicate="inspired",
        argument="Ada Lovelace",
    )
    target_extraction = _single_argument_extraction(
        paragraphs[1], subject="Ada Lovelace", predicate="wrote",
        argument="the first algorithm",
    )
    build = cb.compile_claim_graph(
        paragraphs, (source_extraction, target_extraction)
    )
    title_arc = next(
        arc for arc in build.directed_arcs
        if arc.origin == "verified_nary_title"
        and arc.subject_source_id == "src:engine"
        and arc.object_source_id == "src:ada"
    )
    assert title_arc.target_claim_id is None  # retrieval anchor remains honest
    continuation = next(
        arc for arc in build.directed_arcs
        if arc.origin == "verified_shared_entity"
    )
    assert (continuation.subject_source_id, continuation.object_source_id) == (
        "src:engine", "src:ada"
    )
    assert continuation.target_claim_id is not None
    assert continuation.target_evidence_span.text_scope == "body"
    assert continuation.target_evidence_span.exact == "Ada Lovelace"
    target_claim = next(
        claim for claim in build.nary_claims
        if claim.claim_id == continuation.target_claim_id
    )
    assert target_claim.subject.role_kind == "subject"
    assert target_claim.predicate.exact == "wrote"
    assert cb.verify_claim_graph(build) == ()

    # With no verified subject claim in the title paragraph, the retrieval arc
    # remains but typed continuation fails closed with a counted quarantine.
    missing = cb.compile_claim_graph(paragraphs, (source_extraction,))
    assert any(
        arc.origin == "verified_nary_title" for arc in missing.directed_arcs
    )
    assert not any(
        arc.origin == "verified_shared_entity" for arc in missing.directed_arcs
    )
    refusal = next(
        item for item in missing.quarantined_shared_entities
        if item.reason == "title_continuation_missing_subject"
    )
    assert refusal.candidate_pair_count == refusal.rejected_pair_count == 1
    assert cb.verify_claim_graph(missing) == ()


def test_multiple_matching_title_subject_claims_refuse_typed_continuation():
    paragraphs = (
        cb.ParagraphInputV1(
            "src:engine", "Engine History", "The engine inspired Ada Lovelace."
        ),
        cb.ParagraphInputV1(
            "src:ada", "Ada Lovelace",
            "Ada Lovelace wrote and published Notes."
        ),
    )
    source_extraction = _single_argument_extraction(
        paragraphs[0], subject="The engine", predicate="inspired",
        argument="Ada Lovelace",
    )
    target_payload = json.dumps({
        "schema_version": cb.EXTRACTION_SCHEMA_VERSION,
        "claims": [
            {
                "subject": {"start": 0, "end": 12, "exact": "Ada Lovelace"},
                "predicate": {"start": 13, "end": 18, "exact": "wrote"},
                "arguments": [{
                    "role": "object", "start": 33, "end": 38, "exact": "Notes",
                }],
            },
            {
                "subject": {"start": 0, "end": 12, "exact": "Ada Lovelace"},
                "predicate": {"start": 23, "end": 32, "exact": "published"},
                "arguments": [{
                    "role": "object", "start": 33, "end": 38, "exact": "Notes",
                }],
            },
        ],
    }, separators=(",", ":"))
    target_extraction = cb.freeze_extraction(
        "src:ada", target_payload, producer="offline-fixture",
        model_revision="fixture-model@sha256:0123",
        prompt_sha256=PROMPT_SHA, config_sha256=CONFIG_SHA,
    )
    build = cb.compile_claim_graph(
        paragraphs, (source_extraction, target_extraction)
    )
    assert any(
        arc.origin == "verified_nary_title" for arc in build.directed_arcs
    )
    assert not any(
        arc.origin == "verified_shared_entity" for arc in build.directed_arcs
    )
    assert any(
        item.reason == "title_continuation_ambiguous_subject"
        for item in build.quarantined_shared_entities
    )
    assert cb.verify_claim_graph(build) == ()


def test_compiler_does_not_need_network(monkeypatch: pytest.MonkeyPatch):
    def forbidden_network(*args, **kwargs):
        raise AssertionError("network access is forbidden inside B3 compiler")

    monkeypatch.setattr(socket, "socket", forbidden_network)
    build = cb.compile_claim_graph(_paragraphs(), (_extraction(),))
    assert len(build.nary_claims) == 1
    assert cb.verify_claim_graph(build) == ()
