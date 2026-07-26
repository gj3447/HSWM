#!/usr/bin/env python3
"""Idempotently materialize the 2026-07-26 HSWM cellular packet on LakatoTree.

This uploader deliberately refuses to create or rewrite tree metadata.  The
canonical programme must already exist, all declared parents must be present,
and a write token must be explicitly supplied by the LakatoTree host.  It does
not call prediction, result, cycle, or verdict endpoints.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent
DEFAULT_PACKET = REPO / "receipts/HSWM_CELLULAR_LAKATOTREE_PACKET_20260726.json"
DEFAULT_RECEIPT = REPO / "receipts/HSWM_CELLULAR_LAKATOTREE_READBACK_20260726.json"
FORBIDDEN_ENDPOINT_TOKENS = ("prediction", "test_result", "cycle", "verdict")


class UploadError(RuntimeError):
    pass


class Client:
    def __init__(self, base: str, token: str) -> None:
        self.base = base.rstrip("/")
        self.token = token

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if method != "GET" and any(token in path for token in FORBIDDEN_ENDPOINT_TOKENS):
            raise UploadError(f"verdict-bearing endpoint forbidden by packet uploader: {path}")
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise UploadError(f"HTTP {exc.code} {method} {path}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise UploadError(f"LakatoTree unavailable at {self.base}: {exc}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise UploadError(f"non-JSON response for {method} {path}: {raw[:300]!r}") from exc


def quoted(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def canonical_sha(data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_packet(path: Path) -> dict[str, Any]:
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UploadError(f"invalid packet {path}: {exc}") from exc
    required = {
        "tree",
        "elements",
        "nodes",
        "element_uses",
        "foundations",
        "questions",
        "events",
        "world_actions",
        "readback",
    }
    missing = sorted(required - packet.keys())
    if missing:
        raise UploadError(f"packet missing keys: {missing}")
    if packet.get("scientific_status") != "UNJUDGED":
        raise UploadError("packet scientific_status must remain UNJUDGED")
    if packet.get("scientific_prediction_registered") is not False:
        raise UploadError("packet must not register a scientific prediction")
    if packet.get("scientific_result_submitted") is not False:
        raise UploadError("packet must not submit a scientific result")
    if packet.get("verdict_mutation_allowed") is not False:
        raise UploadError("packet must forbid verdict mutation")
    tags = [node.get("tag") for node in packet["nodes"]]
    if len(tags) != len(set(tags)) or any(not tag for tag in tags):
        raise UploadError("node tags must be nonempty and unique")
    qnames = [question.get("qname") for question in packet["questions"]]
    if len(qnames) != len(set(qnames)) or any(not name for name in qnames):
        raise UploadError("question names must be nonempty and unique")
    for node in packet["nodes"]:
        forbidden = {"metric_name", "metric_value", "script", "result_path", "verdict"} & node.keys()
        if forbidden:
            raise UploadError(f"node {node['tag']} contains verdict-bearing fields: {sorted(forbidden)}")
    return packet


def node_index(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(node.get("tag")): node for node in tree.get("nodes", []) if node.get("tag")}


def frontier_index(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(question.get("name") or question.get("qname")): question
        for question in tree.get("frontier", [])
        if question.get("name") or question.get("qname")
    }


def foundation_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(requirement.get("name")): requirement
        for requirement in data.get("requirements", [])
        if requirement.get("name")
    }


def validate_preflight(packet: dict[str, Any], tree: dict[str, Any]) -> None:
    if tree.get("name") not in (None, packet["tree"]):
        raise UploadError(f"tree identity mismatch: {tree.get('name')!r}")
    existing = node_index(tree)
    produced: set[str] = set()
    required_existing = set(packet.get("existing_parent_requirements", []))
    missing_existing = sorted(required_existing - existing.keys())
    if missing_existing:
        raise UploadError(f"required existing parents missing; no writes performed: {missing_existing}")
    for node in packet["nodes"]:
        for parent in node.get("parents", []):
            if parent not in existing and parent not in produced:
                raise UploadError(f"parent {parent!r} for {node['tag']!r} missing; no writes performed")
        produced.add(node["tag"])


def post_packet(client: Client, packet: dict[str, Any]) -> list[dict[str, Any]]:
    tree = quoted(packet["tree"])
    actions: list[dict[str, Any]] = []

    def post(kind: str, path: str, body: dict[str, Any]) -> None:
        response = client.call("POST", path, body)
        actions.append({"kind": kind, "path": path, "response": response})

    for element in packet["elements"]:
        post("element", f"/api/tree/{tree}/element", element)
    for node in packet["nodes"]:
        post("node", f"/api/tree/{tree}/node", node)
    for use in packet["element_uses"]:
        tag = quoted(use["tag"])
        element = quoted(use["element"])
        body = {key: use[key] for key in ("note", "evidence_ref") if key in use}
        post("element_use", f"/api/tree/{tree}/node/{tag}/element/{element}", body)
    for foundation in packet["foundations"]:
        post("foundation", f"/api/tree/{tree}/foundation", foundation)
    for question in packet["questions"]:
        post("question", f"/api/tree/{tree}/question", question)
    for event in packet["events"]:
        tag = quoted(event["tag"])
        body = {key: value for key, value in event.items() if key != "tag"}
        post("research_event", f"/api/tree/{tree}/node/{tag}/event", body)
    for action in packet["world_actions"]:
        tag = quoted(action["tag"])
        body = {key: value for key, value in action.items() if key != "tag"}
        post("world_action", f"/api/tree/{tree}/node/{tag}/world-action", body)
    return actions


def exact_readback(client: Client, packet: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    tree_name = packet["tree"]
    tree_q = quoted(tree_name)
    tree = client.call("GET", f"/api/tree/{tree_q}")
    metrics = client.call("GET", f"/api/tree/{tree_q}/metrics")
    foundation = client.call("GET", f"/api/tree/{tree_q}/foundation")
    fsck = client.call("GET", f"/api/ops/fsck?{urllib.parse.urlencode({'tree': tree_name})}")
    nodes = node_index(tree)
    frontier = frontier_index(tree)
    foundations = foundation_index(foundation)
    required_tags = packet["readback"]["required_node_tags"]
    required_questions = packet["readback"]["required_question_names"]
    required_foundations = [item["name"] for item in packet["foundations"]]
    missing_nodes = sorted(set(required_tags) - nodes.keys())
    missing_questions = sorted(set(required_questions) - frontier.keys())
    missing_foundations = sorted(set(required_foundations) - foundations.keys())
    if missing_nodes or missing_questions or missing_foundations:
        raise UploadError(
            "exact readback failed: "
            f"missing_nodes={missing_nodes}, missing_questions={missing_questions}, "
            f"missing_foundations={missing_foundations}"
        )
    events: dict[str, Any] = {}
    standing: dict[str, Any] = {}
    for tag in required_tags:
        tag_q = quoted(tag)
        events[tag] = client.call("GET", f"/api/tree/{tree_q}/node/{tag_q}/events")
        standing[tag] = client.call(
            "GET", f"/api/tree/{tree_q}/node/{tag_q}/claim-standing?require_replay=false"
        )
    return {
        "schema": "hswm-cellular-lakatotree-readback/v1",
        "status": "APPLIED_AND_EXACT_READBACK_PASS",
        "tree": tree_name,
        "packet_id": packet["packet_id"],
        "packet_sha256": canonical_sha(packet),
        "source_commit": packet["source_commit"],
        "scientific_status": "UNJUDGED",
        "verdict_mutation_performed": False,
        "registered_nodes": {tag: nodes[tag] for tag in required_tags},
        "registered_questions": {name: frontier[name] for name in required_questions},
        "registered_foundations": {name: foundations[name] for name in required_foundations},
        "research_events": events,
        "claim_standing": standing,
        "tree_metrics_after_upload": metrics,
        "fsck_after_upload": fsck,
        "mutation_responses": actions,
    }


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(rendered)
        tmp = Path(handle.name)
    os.replace(tmp, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--url", default=os.environ.get("LAKATOTREE_URL", "http://127.0.0.1:55170"))
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        packet = load_packet(args.packet.resolve())
        if args.validate_only:
            print(
                json.dumps(
                    {
                        "status": "PACKET_VALID",
                        "tree": packet["tree"],
                        "packet_sha256": canonical_sha(packet),
                        "nodes": len(packet["nodes"]),
                        "questions": len(packet["questions"]),
                        "foundations": len(packet["foundations"]),
                        "scientific_status": packet["scientific_status"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        token = os.environ.get("LAKATOS_API_TOKEN", "")
        if not token:
            raise UploadError(
                "LAKATOS_API_TOKEN is required; run on the canonical LakatoTree host after sourcing "
                "/opt/lakatotree/server.env. Mac MCP remains read-only."
            )
        client = Client(args.url, token)
        tree = client.call("GET", f"/api/tree/{quoted(packet['tree'])}")
        validate_preflight(packet, tree)
        actions = post_packet(client, packet)
        receipt = exact_readback(client, packet, actions)
        atomic_write(args.receipt.resolve(), receipt)
        print(json.dumps({"status": receipt["status"], "receipt": str(args.receipt.resolve())}, ensure_ascii=False))
        return 0
    except UploadError as exc:
        print(json.dumps({"status": "REFUSED", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
