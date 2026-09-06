#!/usr/bin/env python3
"""Generate the opaque v3 (G0-local) protocol draft and its secret evaluator reveal.

The public protocol is written into the repository preregistration directory
as DRAFT_NOT_FROZEN.  The reveal, which contains the correct action codes,
salts, and canaries, is written only to the private path you name and must
be moved to the evaluator OS user before the occurrence.  The seed itself is
read from a file and never written anywhere else.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from hswm.experiments import g1_opaque_v3
from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256


TOKENIZER_MODEL_FIELDS = (
    "container_image", "container_image_id", "model_repository", "model_revision", "snapshot_manifest_sha256",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-file", type=Path, required=True, help="private file holding >= 32 random bytes")
    parser.add_argument("--study-date", required=True)
    parser.add_argument("--live-binding-from", type=Path, required=True, help="an earlier protocol whose live_binding and tokenizer model pins are reused")
    parser.add_argument("--registry-path", required=True, help="durable one-shot consumption registry path on the run host")
    parser.add_argument("--protocol-out", type=Path, required=True)
    parser.add_argument("--reveal-out", type=Path, required=True, help="private reveal path; must not be inside the repository")
    parser.add_argument("--emit-code-pool", type=Path, help="write the public seed-derived candidate code pool here and stop (no protocol, no reveal)")
    parser.add_argument("--token-counts", type=Path, help="public offline token counts of the candidate pool (scripts/freeze_hswm_g1_opaque_v3.py measure-pool)")
    parser.add_argument("--run-suffix", help="repaired rerun under SR-3 within the same protocol family, e.g. r2")
    parser.add_argument("--design", default="v3", choices=list(g1_opaque_v3.DESIGN_REVISIONS), help="v4: independent, stratum-balanced no-state orders")
    args = parser.parse_args(argv)

    seed = args.seed_file.read_bytes()
    if args.emit_code_pool is not None:
        pool = g1_opaque_v3.v3_code_pool(seed)
        if args.emit_code_pool.exists():
            raise SystemExit("refusing to overwrite an existing code pool")
        args.emit_code_pool.write_bytes(canonical_json_bytes({"schema_version": "hswm-g1-opaque-v3-code-pool/v1", "candidates_per_episode": g1_opaque_v3.CANDIDATE_PAIRS_PER_EPISODE, "pool": pool}))
        print(json.dumps({"code_pool_path": str(args.emit_code_pool), "pool_sha256": canonical_sha256(pool), "codes": sum(2 * len(pairs) for pairs in pool.values())}, sort_keys=True))
        return 0
    token_counts = None
    if args.token_counts is not None:
        counts = json.loads(args.token_counts.read_text(encoding="utf-8"))
        token_counts = counts["token_counts"] if isinstance(counts, dict) and "token_counts" in counts else counts
    source = json.loads(args.live_binding_from.read_text(encoding="utf-8"))
    tokenizer_model = {key: source["tokenizer_binding"][key] for key in TOKENIZER_MODEL_FIELDS}
    protocol, reveal = g1_opaque_v3.generate_v3(
        seed=seed, study_date=args.study_date, live_binding=source["live_binding"],
        tokenizer_model=tokenizer_model, consumption_registry_path=args.registry_path,
        token_counts=token_counts, run_suffix=args.run_suffix, design=args.design,
    )
    if args.protocol_out.exists() or args.reveal_out.exists():
        raise SystemExit("refusing to overwrite an existing protocol or reveal")
    args.protocol_out.parent.mkdir(parents=True, exist_ok=True)
    args.protocol_out.write_bytes(json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    args.reveal_out.parent.mkdir(parents=True, exist_ok=True)
    fd = __import__("os").open(args.reveal_out, __import__("os").O_WRONLY | __import__("os").O_CREAT | __import__("os").O_EXCL, 0o600)
    with __import__("os").fdopen(fd, "wb") as handle:
        handle.write(canonical_json_bytes(reveal))
    print(json.dumps({
        "protocol_path": str(args.protocol_out),
        "protocol_canonical_sha256": canonical_sha256(protocol),
        "protocol_file_sha256": sha256(args.protocol_out.read_bytes()).hexdigest(),
        "reveal_path": str(args.reveal_out),
        "reveal_commitment_root": protocol["evaluator_reveal_contract"]["reveal_commitment_root"],
        "seed_commitment_sha256": protocol["generation"]["seed_commitment_sha256"],
        "freeze_status": protocol["freeze"]["status"],
        "tokenizer_binding_status": protocol["tokenizer_binding"]["status"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
