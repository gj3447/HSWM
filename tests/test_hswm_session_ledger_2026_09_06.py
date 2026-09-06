"""The 2026-09-06 session ledger is deterministic, source-bound, complete over the burden window, and claim-free."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess

from scripts import build_hswm_session_ledger_2026_09_06 as builder
from scripts import upsert_hswm_session_ledger_2026_09_06 as publisher


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = ROOT / builder.ONTOLOGY_PATH


def _data() -> dict:
    return json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))


def test_projection_is_deterministic_source_bound_and_valid() -> None:
    data = builder.build_data()
    assert ONTOLOGY_PATH.read_bytes() == builder.encoded_data(data)
    publisher.validate_data(data)
    assert sha256(ONTOLOGY_PATH.read_bytes()).hexdigest() == publisher.EXPECTED_FILE_SHA256
    assert builder.canonical_sha(data) == publisher.EXPECTED_PROJECTION_SHA256
    assert data["status"] == builder.STATUS


def test_every_window_commit_is_ledgered_once_with_the_right_core_flag() -> None:
    log = subprocess.run(
        ["git", "log", f"{builder.WINDOW_START_COMMIT}..{builder.COMMITS[-1]['sha']}", "--format=%x1e%H", "--name-only", "--reverse"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    observed = {}
    for chunk in log.split("\x1e")[1:]:
        lines = [line for line in chunk.strip("\n").split("\n") if line]
        observed[lines[0]] = any(path.startswith(builder.CORE_PATH_PREFIXES) for path in lines[1:])
    ledgered = {row["sha"]: row["core"] for row in builder.COMMITS}
    assert ledgered == observed
    positions = [row["position"] for row in builder.COMMITS]
    assert positions == list(range(1, len(builder.COMMITS) + 1))
    assert sum(1 for row in builder.COMMITS if row["core"]) == 27


def test_streams_cover_all_commits_and_join_the_closure_graph() -> None:
    data = _data()
    nodes = {row["uid"]: row for row in data["nodes"]}
    commits = [row for row in data["nodes"] if "commit_sha" in row["properties"]]
    assert len(commits) == len(builder.COMMITS) == data["expected_counts"]["commits"]
    streams = [row for row in data["nodes"] if row["properties"].get("stream_id") and "commit_count" in row["properties"] and "commit_sha" not in row["properties"]]
    assert sum(row["properties"]["commit_count"] for row in streams) == len(commits)
    assert {row["properties"]["stream_id"] for row in streams} == set(builder.STREAMS)
    anchor_uids = {row["uid"] for row in data["anchors"]}
    step_targets = {row["to_uid"] for row in data["relations"] if row["type"] == "ADDRESSES"}
    assert step_targets <= anchor_uids and len(step_targets) >= 5
    receipts = {row["to_uid"] for row in data["relations"] if row["scope"] == "RESULT_FILE_FOR_RECEIPT"}
    assert len(receipts) == 3 and receipts <= anchor_uids
    chain = [row for row in data["relations"] if row["type"] == "PRECEDES"]
    assert len(chain) == len(commits) - 1
    for row in data["relations"]:
        assert row["from_uid"] in nodes or row["from_uid"] in anchor_uids
        assert row["to_uid"] in nodes or row["to_uid"] in anchor_uids


def test_open_items_name_owners_and_block_only_anchored_targets() -> None:
    data = _data()
    anchor_uids = {row["uid"] for row in data["anchors"]}
    items = [row for row in data["nodes"] if "open_item_id" in row["properties"]]
    assert len(items) == len(builder.OPEN_ITEMS) == 8
    user_owned = {row["properties"]["open_item_id"] for row in items if row["properties"]["open_item_owner"] == "USER_PRIMARY"}
    assert user_owned == {"OI-1", "OI-2", "OI-8"}
    for row in data["relations"]:
        if row["type"] in {"BLOCKS", "CONSTRAINS"}:
            assert row["to_uid"] in anchor_uids, row
    blocked = {row["to_uid"] for row in data["relations"] if row["type"] == "BLOCKS"}
    assert builder.step_uid("S-5") in blocked and builder.step_uid("S-6") in blocked and builder.step_uid("S-1") in blocked
    assert f"sym:Concept:hswm-closure-v1-done-state-{builder.CLOSURE_TAG}" in blocked


def test_ledger_is_claim_free_and_anchor_names_match_the_bound_closure_bundle() -> None:
    data = _data()
    text = json.dumps(data, ensure_ascii=False)
    for forbidden in ("G0_PASSED", "G1_PASSED", "DONE_STATE_REACHED", "EFFICACY_SHOWN"):
        assert forbidden not in text
    assert "G0_NOT_PASSED_G1_LOCKED" in data["status"]
    closure = json.loads((ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v5.json").read_text(encoding="utf-8"))
    names = {row["uid"]: row["properties"]["name"] for row in closure["nodes"]}
    for anchor in data["anchors"]:
        if anchor["uid"] in names:
            assert anchor["name"] == names[anchor["uid"]], anchor["uid"]
    bound = {row["path"] for row in data["artifact_bindings"]}
    assert "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v5.json" in bound
    assert "F1_R8_RESULTS_LOG.md" not in bound


def test_v1_ledger_snapshot_is_retained_unchanged_and_superseded() -> None:
    v1 = ROOT / "ontology/identity/hswm_core/HSWM_SESSION_LEDGER_2026-09-06.v1.json"
    assert sha256(v1.read_bytes()).hexdigest() == "2c663f9e82122badeea72dbec7e1aef74e541aece9c551491aa6812cfcbf6bd7"
    old = json.loads(v1.read_text(encoding="utf-8"))
    assert old["bundle_uid"] == builder.PREDECESSOR_BUNDLE_UID
    assert old["expected_counts"]["commits"] == 48
    data = _data()
    follow = [row for row in data["relations"] if row["type"] == "SUPERSEDES_AS_FOLLOWUP"]
    assert [(row["from_uid"], row["to_uid"]) for row in follow] == [(builder.BUNDLE_UID, builder.PREDECESSOR_BUNDLE_UID)]
    parallel = [row for row in data["nodes"] if row["properties"].get("stream_id") == "parallel_session_s5_recovery" and "commit_sha" in row["properties"]]
    assert len(parallel) == 5 and sum(1 for row in parallel if row["properties"]["core_path_commit"]) == 4
