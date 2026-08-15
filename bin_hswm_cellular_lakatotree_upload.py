#!/usr/bin/env python3
"""Validate the historical HSWM cellular LakatoTree packet without uploading.

The personal LakatoTree writer was retired on 2026-08-15. The packet and past
readback receipt remain historical evidence, but this module performs no
network requests and accepts no mutation mode. Use ``--validate-only``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent
DEFAULT_PACKET = REPO / "receipts/HSWM_CELLULAR_LAKATOTREE_PACKET_20260726.json"
DEFAULT_RECEIPT = REPO / "receipts/HSWM_CELLULAR_LAKATOTREE_READBACK_20260726.json"


class UploadError(RuntimeError):
    pass


def canonical_sha(data: Any) -> str:
    payload = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
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
        forbidden = {
            "metric_name",
            "metric_value",
            "script",
            "result_path",
            "verdict",
        } & node.keys()
        if forbidden:
            raise UploadError(
                f"node {node['tag']} contains verdict-bearing fields: {sorted(forbidden)}"
            )
    return packet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--url")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        packet = load_packet(args.packet.resolve())
        if not args.validate_only:
            raise UploadError(
                "RETIRED: personal LakatoTree mutation was removed; "
                "only --validate-only is supported"
            )
        print(
            json.dumps(
                {
                    "status": "PACKET_VALID_HISTORICAL_READ_ONLY",
                    "tree": packet["tree"],
                    "packet_sha256": canonical_sha(packet),
                    "nodes": len(packet["nodes"]),
                    "questions": len(packet["questions"]),
                    "foundations": len(packet["foundations"]),
                    "scientific_status": packet["scientific_status"],
                    "mutation_allowed": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except UploadError as exc:
        print(
            json.dumps({"status": "REFUSED", "reason": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
