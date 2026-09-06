#!/usr/bin/env python3
"""Freeze the opaque v3 (G0-local) protocol on the run host, in two custody roles.

``measure`` runs as the actor user: it measures the thirty-two public action
code pairs offline inside the pinned vLLM image (Docker network ``none``),
writes the measurement into ``tokenizer_binding`` as ``MEASURED``, sets
``freeze.status`` to ``FROZEN``, and prints the canonical and file digests.
It refuses a protocol that is already frozen and refuses unequal token counts.

``rebind-reveal`` runs as the evaluator user: after the freeze changed the
protocol's canonical digest, it rewrites only the reveal's outer
``protocol_canonical_sha256`` so the evaluator process accepts requests bound
to the frozen protocol.  The commitment root excludes that outer field, so the
episode commitments in the public protocol are unchanged.

Neither command performs a model or tokenizer HTTP request, claims the
one-shot registry, or reads the other role's private files.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

# The DGX launcher imports repository-local packages (_research.*); running
# this script by path must see the checkout root exactly like `python -m`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hswm.experiments import g1_micro_dgx, g1_opaque_v3  # noqa: E402
from hswm.experiments import g1_opaque_evaluator_process as evaluator_process  # noqa: E402
from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256  # noqa: E402


def _docker(argv: tuple[str, ...]) -> bytes:
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise SystemExit(f"offline tokenizer measurement failed: {result.stderr.decode('utf-8', 'replace')[-400:]}")
    return result.stdout


def measure_pool(args: argparse.Namespace) -> int:
    """Actor: standalone offline token counts of the public candidate pool (no protocol yet)."""

    pool_document = json.loads(args.pool.read_text(encoding="utf-8"))
    pool = pool_document["pool"]
    codes = [code for pairs in pool.values() for pair in pairs for code in pair]
    source = json.loads(args.live_binding_from.read_text(encoding="utf-8"))
    image = source["tokenizer_binding"]["container_image"]
    counts = g1_micro_dgx.offline_code_token_counts(
        command=args.command, snapshot=args.model_snapshot.resolve(), image=image, codes=codes,
    )
    if args.out.exists():
        raise SystemExit("refusing to overwrite existing token counts")
    args.out.write_bytes(canonical_json_bytes({
        "schema_version": "hswm-g1-opaque-v3-code-token-counts/v1",
        "container_image": image, "model_revision": args.model_snapshot.resolve().name,
        "pool_sha256": canonical_sha256(pool), "token_counts": counts,
    }))
    equal = sum(1 for pairs in pool.values() for a, b in pairs if counts[a] == counts[b])
    print(json.dumps({"codes": len(counts), "pairs": sum(len(p) for p in pool.values()), "pairs_with_equal_counts": equal, "token_counts_path": str(args.out)}, sort_keys=True))
    return 0


def measure(args: argparse.Namespace) -> int:
    protocol, draft_sha = g1_opaque_v3.load_v3_protocol(args.protocol)
    if protocol["freeze"]["status"] != "DRAFT_NOT_FROZEN":
        raise SystemExit("refusing to re-freeze: protocol is not a draft")
    binding = protocol["tokenizer_binding"]
    if binding["status"] != "PENDING_DGX_OFFLINE_MEASUREMENT":
        raise SystemExit("refusing: tokenizer binding is not pending measurement")
    receipt = g1_micro_dgx.offline_action_code_tokenizer_receipt(
        command=args.command,
        snapshot=args.model_snapshot.resolve(),
        image=binding["container_image"],
        image_id=binding["container_image_id"],
        snapshot_manifest_sha256=binding["snapshot_manifest_sha256"],
        episodes=protocol["episodes"],
    )
    if receipt["model_repository"] != binding["model_repository"] or receipt["model_revision"] != binding["model_revision"]:
        raise SystemExit("measured tokenizer model differs from the protocol's pinned model")
    frozen = json.loads(json.dumps(protocol))
    frozen["tokenizer_binding"] = {
        **binding,
        "status": "MEASURED",
        "encoding": receipt["encoding"],
        "transformers_version": receipt["transformers_version"],
        "tokenizers_version": receipt["tokenizers_version"],
        "episodes": receipt["episodes"],
        "measurement_receipt_sha256": receipt["receipt_sha256"],
    }
    frozen["freeze"] = {
        "status": "FROZEN",
        "frozen_on": args.frozen_on,
        "draft_canonical_sha256": draft_sha,
        "rule": "The frozen protocol bytes are committed before the one-shot registry claim; any later edit is a new protocol family, never an amendment.",
    }
    g1_micro_dgx._validate_opaque_tokenizer_receipt(receipt, frozen["tokenizer_binding"])
    g1_opaque_v3.validate_v3_protocol(frozen)
    payload = json.dumps(frozen, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    temporary = args.protocol.with_name(args.protocol.name + ".freeze.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, args.protocol)
    print(json.dumps({
        "draft_canonical_sha256": draft_sha,
        "frozen_canonical_sha256": canonical_sha256(frozen),
        "frozen_file_sha256": sha256(payload).hexdigest(),
        "measurement_receipt_sha256": receipt["receipt_sha256"],
        "protocol_path": str(args.protocol),
        "status": "FROZEN_TOKENIZER_MEASURED_NO_POST_NO_REGISTRY_CLAIM",
    }, sort_keys=True))
    return 0


def rebind_reveal(args: argparse.Namespace) -> int:
    reveal = evaluator_process.load_reveal(args.reveal)
    _, frozen_sha = g1_opaque_v3.load_v3_protocol(args.protocol)
    if reveal["protocol_canonical_sha256"] == frozen_sha:
        print(json.dumps({"status": "ALREADY_BOUND", "protocol_canonical_sha256": frozen_sha}, sort_keys=True))
        return 0
    rebound = {**reveal, "protocol_canonical_sha256": frozen_sha}
    temporary = args.reveal.with_name(args.reveal.name + ".rebind.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical_json_bytes(rebound))
    os.replace(temporary, args.reveal)
    evaluator_process.load_reveal(args.reveal)
    print(json.dumps({
        "previous_protocol_canonical_sha256": reveal["protocol_canonical_sha256"],
        "protocol_canonical_sha256": frozen_sha,
        "reveal_path": str(args.reveal),
        "status": "REVEAL_OUTER_BINDING_REBOUND_TO_FROZEN_PROTOCOL",
    }, sort_keys=True))
    return 0


def publish_after_seal(args: argparse.Namespace) -> int:
    """Evaluator user: wait for the actor's seal marker, then publish the reveal for the actor."""

    import time

    _, frozen_sha = g1_opaque_v3.load_v3_protocol(args.protocol)
    reveal = evaluator_process.load_reveal(args.reveal)
    if reveal["protocol_canonical_sha256"] != frozen_sha:
        raise SystemExit("reveal is not bound to the frozen protocol; run rebind-reveal first")
    if args.to.exists():
        raise SystemExit("refusing: the after-seal path already exists")
    deadline = time.monotonic() + float(args.timeout_seconds)
    while True:
        if args.marker.is_file():
            try:
                marker = json.loads(args.marker.read_bytes())
            except (OSError, ValueError):
                marker = None
            if (
                isinstance(marker, dict)
                and marker.get("schema_version") == "hswm-g1-opaque-v3-seal-marker/v1"
                and marker.get("protocol_canonical_sha256") == frozen_sha
                and marker.get("study_uid") == reveal["study_uid"]
                and marker.get("behavior_calls_sealed") == g1_opaque_v3.PROVIDER_CALL_CAP
                and isinstance(marker.get("sealed_journals"), dict)
                and len(marker["sealed_journals"]) == g1_opaque_v3.EPISODE_COUNT
                and marker.get("sealed_journals_sha256") == canonical_sha256({"sealed_journals": marker["sealed_journals"]})
            ):
                break
        if time.monotonic() >= deadline:
            raise SystemExit("seal marker did not appear within the wait bound; reveal not published")
        time.sleep(float(args.poll_seconds))
    temporary = args.to.with_name(args.to.name + ".publish.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(args.reveal.read_bytes())
    os.replace(temporary, args.to)
    print(json.dumps({
        "protocol_canonical_sha256": frozen_sha,
        "published_to": str(args.to),
        "sealed_journals_sha256": marker["sealed_journals_sha256"],
        "status": "REVEAL_PUBLISHED_AFTER_SEAL_MARKER",
    }, sort_keys=True))
    return 0


def main(argv: list[str] | None = None, *, command=_docker) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pool = commands.add_parser("measure-pool", help="actor: offline token counts of the public candidate code pool")
    pool.add_argument("--pool", type=Path, required=True)
    pool.add_argument("--model-snapshot", type=Path, required=True)
    pool.add_argument("--live-binding-from", type=Path, required=True, help="protocol whose tokenizer_binding names the pinned image")
    pool.add_argument("--out", type=Path, required=True)
    pool.set_defaults(handler=measure_pool)
    freeze = commands.add_parser("measure", help="actor: measure the tokenizer binding offline and freeze the protocol")
    freeze.add_argument("--protocol", type=Path, required=True)
    freeze.add_argument("--model-snapshot", type=Path, required=True, help="…/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots/<revision>")
    freeze.add_argument("--frozen-on", required=True, help="YYYY-MM-DD")
    freeze.set_defaults(handler=measure)
    rebind = commands.add_parser("rebind-reveal", help="evaluator user: bind the reveal's outer object to the frozen protocol digest")
    rebind.add_argument("--reveal", type=Path, required=True)
    rebind.add_argument("--protocol", type=Path, required=True)
    rebind.set_defaults(handler=rebind_reveal)
    publish = commands.add_parser("publish-after-seal", help="evaluator user: publish the reveal to the actor-readable path once the seal marker exists")
    publish.add_argument("--marker", type=Path, required=True, help="seal marker path written by the actor instrument (--seal-marker-out)")
    publish.add_argument("--reveal", type=Path, required=True)
    publish.add_argument("--protocol", type=Path, required=True)
    publish.add_argument("--to", type=Path, required=True, help="the actor's --reveal-after-seal path")
    publish.add_argument("--timeout-seconds", type=float, default=6 * 3600)
    publish.add_argument("--poll-seconds", type=float, default=2.0)
    publish.set_defaults(handler=publish_after_seal)
    args = parser.parse_args(argv)
    args.command = command
    return int(args.handler(args))


if __name__ == "__main__":
    sys.exit(main())
