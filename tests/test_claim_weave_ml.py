"""ML weave teeth — 합성 재료만 (실 추출물 미사용, prereg 규율)."""
from __future__ import annotations

from hashlib import sha256
from types import SimpleNamespace

import pytest

from claim_builder import ArgumentRoleV1, NaryClaimV1
from claim_weave_ml import weave_ml
import typed_composition as tc


BODY_SHA = {"p1": sha256(b"p1:body").hexdigest(), "p2": sha256(b"p2:body").hexdigest(),
            "p3": sha256(b"p3:body").hexdigest()}


def _role(source_id, role, exact, start):
    return ArgumentRoleV1(
        role_id=f"role:{source_id}:{role}:{start}", source_id=source_id,
        role_kind="entity", role=role, start=start, end=start + len(exact),
        exact=exact, prefix="", suffix="",
        source_text_sha256=BODY_SHA[source_id])


def _claim(cid, source_id, subj, subj_start, pred, args):
    return NaryClaimV1(
        claim_id=cid, source_id=source_id,
        subject=_role(source_id, "subject", subj, subj_start),
        predicate=_role(source_id, "predicate", pred, 500),
        arguments=tuple(_role(source_id, r, x, s) for r, x, s in args),
        observation_ids=(f"obs:{cid}",))


CLAIMS = (
    # p1: film claim, director argument at [30, 45)
    _claim("c:film", "p1", "Polish-Russian War", 0, "directed by",
           [("director", "Xawery Zulawski", 30)]),
    # p2: director claim, subject at [0, 15)
    _claim("c:dir", "p2", "Xawery Zulawski", 0, "is son of",
           [("mother", "Malgorzata Braunek", 40)]),
    # p3: another subject with same QID (for fan test)
    _claim("c:dir2", "p3", "X. Zulawski", 0, "also directed", [("work", "Snow White", 40)]),
)
BUILD = SimpleNamespace(nary_claims=CLAIMS)
GRAPH = tc.make_typed_graph(("p1", "p2", "p3"), ())


def _link(source_id, spans):
    return {"source_id": source_id, "source_text_sha256": BODY_SHA[source_id],
            "spans": [{"start": s, "end": e, "qid": q} for s, e, q in spans]}


def _coref(source_id, clusters):
    return {"source_id": source_id, "source_text_sha256": BODY_SHA[source_id],
            "clusters": [[{"start": s, "end": e, "exact": "x"} for s, e in cl]
                         for cl in clusters]}


def test_m1_qid_direct_arc():
    link = {"p1": _link("p1", [(30, 45, "Q123")]),
            "p2": _link("p2", [(0, 15, "Q123")])}
    result, stats = weave_ml(BUILD, GRAPH, link, {})
    pairs = {(a.source_claim_id, a.target_claim_id) for a in result.arcs}
    assert ("c:film", "c:dir") in pairs
    arc = result.arcs[0]
    assert arc.join_entity_id == "canonical:qid:Q123"
    assert arc.origin == "woven_m1_qid"
    assert stats.roles_resolved_direct >= 2


def test_m2_coref_propagation():
    # p2에서 refined는 [0,15)만 QID — coref가 [40,58)(mother 역할과 겹침 아님,
    # 대신 p2의 두 번째 멘션)로 전파. 여기선 p1 쪽 전파를 시험:
    # p1 refined span 없음 + coref 클러스터가 [30,45)과 [0,19)를 묶고
    # [0,19)... QID 원천이 없으므로 전파 불가 → p1은 직접 span [0,19) 하나에 QID.
    link = {"p1": _link("p1", [(0, 19, "Q900")]),   # 주어 span만 QID
            "p2": _link("p2", [(0, 15, "Q123")])}
    coref = {"p1": _coref("p1", [[(0, 19), (30, 45)]])}  # 주어와 director가 동일체?
    # 전파: [30,45)가 Q900 상속 → c:film의 director 역할이 Q900으로 해소되지만
    # Q900 주어 claim은 c:film 자신(p1) → 같은 문단이라 arc 없음.
    result, stats = weave_ml(BUILD, GRAPH, link, coref)
    assert stats.roles_resolved_coref >= 1
    assert all(a.source_id != a.target_id for a in result.arcs)


def test_coref_qid_conflict_discards_cluster():
    link = {"p1": _link("p1", [(0, 19, "Q900"), (30, 45, "Q123")])}
    coref = {"p1": _coref("p1", [[(0, 19), (30, 45)]])}  # 두 QID 충돌 클러스터
    _, stats = weave_ml(BUILD, GRAPH, link, coref)
    assert stats.clusters_conflicted == 1


def test_sha_mismatch_skips_paragraph():
    bad = _link("p1", [(30, 45, "Q123")])
    bad["source_text_sha256"] = "0" * 64
    link = {"p1": bad, "p2": _link("p2", [(0, 15, "Q123")])}
    result, stats = weave_ml(BUILD, GRAPH, link, {})
    assert stats.paragraphs_sha_mismatch == 1
    assert all(a.source_claim_id != "c:film" for a in result.arcs)


def test_fan_cap():
    link = {"p1": _link("p1", [(30, 45, "Q123")]),
            "p2": _link("p2", [(0, 15, "Q123")]),
            "p3": _link("p3", [(0, 11, "Q123")])}
    result, stats = weave_ml(BUILD, GRAPH, link, {}, max_fan=1)
    assert stats.qids_fan_capped == 1
    assert not result.arcs


def test_role_qid_ambiguity_is_conservative():
    # director 역할 span을 두 QID span이 동시에 덮으면 해소 포기
    link = {"p1": _link("p1", [(30, 45, "Q123"), (28, 46, "Q999")]),
            "p2": _link("p2", [(0, 15, "Q123")])}
    result, _ = weave_ml(BUILD, GRAPH, link, {})
    assert all(a.source_claim_id != "c:film" for a in result.arcs)


def test_receipts_complete_and_reversible_origin():
    link = {"p1": _link("p1", [(30, 45, "Q123")]),
            "p2": _link("p2", [(0, 15, "Q123")])}
    result, _ = weave_ml(BUILD, GRAPH, link, {})
    assert len(result.arcs) == len(result.receipts)
    for arc in result.arcs:
        assert arc.origin.startswith("woven_")  # strip_weave 가역 보장 라벨
