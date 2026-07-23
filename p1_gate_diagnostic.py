"""Post-hoc diagnostic for frozen P1 candidate fresh-gate decisions.

This does not alter, rerun, or judge the preregistered arm experiment.  It
replays only the deterministic fresh-question retrieval comparison from the
frozen split and staged snapshot bytes so the gate's numeric cause is visible.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Sequence

from hswm_weight_snapshot import canonical_sha256, parse_snapshot
from p1_phantom_environment import PhantomP1Environment


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _snapshot(connection: sqlite3.Connection, snapshot_id: str):
    row = connection.execute(
        "SELECT canonical_snapshot FROM weight_snapshots WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"missing snapshot {snapshot_id}")
    return parse_snapshot(bytes(row[0]))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--experiment-directory", type=Path, required=True)
    parser.add_argument("--embedding-cache-folder", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    environment = PhantomP1Environment(
        dataset_root=args.dataset_root,
        work_directory=args.experiment_directory,
        answerer=object(),  # retrieval-only replay; the answer port is never called
        embedding_cache_folder=args.embedding_cache_folder,
    )
    rows = []
    for arm in evidence["experiment_receipt"]["arms"]:
        database = args.experiment_directory / "arms" / f"{arm['arm_id']}.weights.sqlite3"
        with sqlite3.connect(database) as connection:
            for episode in arm["episodes"]:
                candidate_id = episode["candidate_id"]
                if candidate_id is None:
                    continue
                staged = connection.execute(
                    "SELECT snapshot_id FROM staged_weight_candidates WHERE candidate_id = ?",
                    (candidate_id,),
                ).fetchone()
                if staged is None:
                    raise RuntimeError(f"missing staged candidate {candidate_id}")
                base = _snapshot(connection, episode["base_snapshot_id"])
                candidate = _snapshot(connection, str(staged[0]))
                gate = environment.evaluate_candidate(
                    arm["arm_id"], episode["episode_index"], base, candidate, ()
                )
                rows.append(
                    {
                        "arm_id": arm["arm_id"],
                        "episode_index": episode["episode_index"],
                        "candidate_id": candidate_id,
                        "unseen_delta": gate.unseen_delta,
                        "unseen_ci_low": gate.unseen_ci_low,
                        "fresh_gate_pass": (
                            gate.unseen_delta >= 0.01 and gate.unseen_ci_low > 0.0
                        ),
                        "recorded_fsm_final_state": episode["fsm_final_state"],
                    }
                )
    output = {
        "schema_version": "hswm-p1-posthoc-gate-diagnostic/v1",
        "scientific_status": "POSTHOC_DIAGNOSTIC_NOT_A_NEW_ARM_OUTCOME",
        "source_evidence_sha256": _sha(args.evidence),
        "frozen_split_manifest_sha256": environment.split_manifest_sha256,
        "candidate_gates": rows,
        "summary": {
            "candidates": len(rows),
            "fresh_gate_passes": sum(row["fresh_gate_pass"] for row in rows),
            "nonzero_unseen_delta": sum(row["unseen_delta"] != 0.0 for row in rows),
        },
    }
    output["diagnostic_sha256"] = canonical_sha256(output)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(output["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
