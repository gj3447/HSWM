"""B1 identity-material unlock — H3-C0 successor builder factorial, T0 only.

Development-only.  Loads the frozen V5 development artifacts (journal replay,
no LLM/network/embedding), layers the deterministic weave arms of
``claim_weave.py`` over the frozen typed graph, and publishes the immutable
T0 chain ledgers of ``chain_viability.py`` per (dataset x arm).

Arms: C0 frozen / C1 +title-subject / C2 +canonical-entity / C3 C1+C2+handoff.

Per H3-C0: this gate spends zero embedding or certificate budget.  If C3 has
no admissible chain on a dataset the verdict there is PRECOMPUTE_NOOP_DEPTH2
and downstream (T1-T3, efficacy) must not run for that dataset.

Do not run before PREREG_B1_IDENTITY_UNLOCK_2026-07-22.json records a live
LakatoTree prediction and freezes the module hashes this guard checks.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import claim_builder as cb
import h3_b3_falsifier as fz
import typed_composition as typed
from chain_viability import enumerate_admissible_chains, ledger_as_json
from claim_weave import apply_weave, strip_weave, weave_c1, weave_c2, weave_c3

HERE = Path(__file__).parent
CACHE = HERE / ".ab_p5_cache" / "h3_b3"
JOURNAL = CACHE / "runs" / "qwen35-r3-schema-v4-20260720" / "development" / "extractions.jsonl"
SEGMENTS = {
    "musique": CACHE / "musique_development_v4_segment.json",
    "2wiki": CACHE / "2wiki_development_v4_segment.json",
}
PREREG = HERE / "PREREG_B1_IDENTITY_UNLOCK_2026-07-22.json"
EVIDENCE = HERE / "EVIDENCE_B1_IDENTITY_UNLOCK_2026-07-22.json"
RECEIPTS = HERE / "RECEIPTS_B1_IDENTITY_UNLOCK_2026-07-22.json"

FROZEN_MODULES = ("chain_viability.py", "claim_weave.py", "b1_identity_unlock.py")


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def preregistration_guard() -> dict:
    if not PREREG.exists():
        raise RuntimeError(f"missing preregistration: {PREREG}")
    locked = json.loads(PREREG.read_text(encoding="utf-8"))
    if locked.get("registered_before_measurement") is not True:
        raise RuntimeError("preregistration is not confirmed before measurement")
    if not locked.get("prediction_receipt_sha256"):
        raise RuntimeError("preregistration lacks a prediction receipt")
    for module in FROZEN_MODULES:
        expected = locked["module_sha256"].get(module)
        actual = _sha256_file(HERE / module)
        if expected != actual:
            raise RuntimeError(
                f"frozen module drift: {module} locked={expected!r} actual={actual!r}")
    for name, path in SEGMENTS.items():
        expected = locked["segment_sha256"].get(name)
        actual = _sha256_file(path)
        if expected != actual:
            raise RuntimeError(
                f"frozen segment drift: {name} locked={expected!r} actual={actual!r}")
    if locked["journal_sha256"] != _sha256_file(JOURNAL):
        raise RuntimeError("frozen journal drift")
    return locked


def load_frozen_graphs() -> dict[str, dict]:
    segments = {name: fz.load_prepared_segment(path)
                for name, path in SEGMENTS.items()}
    artifact = fz.load_extraction_artifact(JOURNAL, tuple(segments.values()))
    frozen_by_source = artifact.frozen_by_source
    out: dict[str, dict] = {}
    for name, segment in segments.items():
        paragraphs = fz._paragraph_inputs(segment)
        frozen = tuple(frozen_by_source[p.source_id] for p in paragraphs)
        build = cb.compile_claim_graph(paragraphs, frozen)
        problems = cb.verify_claim_graph(build)
        if problems:
            raise RuntimeError(f"{name}: claim graph verification failed: {problems[:3]}")
        graph = typed.graph_from_claim_build(build)
        out[name] = {
            "build": build,
            "graph": graph,
            "titles": {p.source_id: p.title for p in paragraphs},
        }
    return out


def main() -> int:
    locked = preregistration_guard()
    datasets = load_frozen_graphs()

    measurement: dict[str, dict] = {}
    receipts_out: dict[str, dict] = {}
    for name in sorted(datasets):
        entry = datasets[name]
        build, base, titles = entry["build"], entry["graph"], entry["titles"]

        w1 = weave_c1(build, titles, base)
        w2 = weave_c2(build, titles, base)
        w3 = weave_c3(build, titles, base)
        arms = {
            "C0": apply_weave(base, []),
            "C1": apply_weave(base, [w1]),
            "C2": apply_weave(base, [w2]),
            "C3": apply_weave(base, [w1, w2, w3]),
        }

        # Reversibility audit: stripping every woven arc restores the frozen
        # topology bit-exactly (canonical arc order on both sides).
        canonical_base = typed.make_typed_graph(
            base.target_ids, tuple(sorted(base.arcs, key=lambda a: a.arc_id)))
        stripped = strip_weave(arms["C3"])
        if stripped.topology_sha256 != canonical_base.topology_sha256:
            raise RuntimeError(f"{name}: weave is not reversible — abort")

        arm_rows: dict[str, dict] = {}
        for arm_name in ("C0", "C1", "C2", "C3"):
            ledger = enumerate_admissible_chains(arms[arm_name])
            row = ledger_as_json(ledger)
            row["woven_arc_count"] = sum(
                1 for a in arms[arm_name].arcs if a.origin.startswith("woven_"))
            # The full chain list can be large; evidence keeps counts + a
            # deterministic head sample, receipts file keeps everything.
            row["chains_sample"] = row["chains"][:50]
            full_chains = row.pop("chains")
            arm_rows[arm_name] = row
            receipts_out.setdefault(name, {})[arm_name] = {
                "ledger_sha256": row["ledger_sha256"],
                "chains": full_chains,
            }

        receipts_out[name]["weave_receipts"] = {
            "c1": [r.payload() for r in w1.receipts],
            "c2": [r.payload() for r in w2.receipts],
            "c3": [r.payload() for r in w3.receipts],
        }
        measurement[name] = {
            "frozen_arc_count": len(base.arcs),
            "claims": len(build.nary_claims),
            "arms": arm_rows,
        }

    c3_counts = {name: measurement[name]["arms"]["C3"]["admissible_chain_count"]
                 for name in measurement}
    c1_counts = {name: measurement[name]["arms"]["C1"]["admissible_chain_count"]
                 for name in measurement}
    primary = min(c3_counts.values())
    novel = sum(c3_counts.values()) - sum(c1_counts.values())

    receipts_blob = json.dumps(receipts_out, ensure_ascii=False, sort_keys=True,
                               indent=1)
    RECEIPTS.write_text(receipts_blob, encoding="utf-8")

    evidence = {
        "schema": "hswm-b1-identity-unlock-evidence/v1",
        "programme": "LakatosTree_PromSearchHSWM_20260721",
        "branch": "B1-identity-material-unlock-t0",
        "preregistration": {
            "path": PREREG.name,
            "sha256": _sha256_file(PREREG),
            "prediction_receipt_sha256": locked["prediction_receipt_sha256"],
        },
        "measurement": {
            "metric": "min_over_datasets_c3_admissible_depth2_chains",
            "value": primary,
            "novel_metric": "sum_c3_minus_c1_admissible_depth2_chains",
            "novel_value": novel,
            "per_dataset": measurement,
        },
        "budget": {
            "llm_calls": 0, "network_calls": 0, "embedding_calls": 0,
            "note": "T0 material gate only, per H3-C0 waterfall discipline",
        },
        "receipts_file": {"path": RECEIPTS.name,
                          "sha256": sha256(receipts_blob.encode()).hexdigest()},
        "limitations": [
            "Deterministic weave sub-lane only: exact/normalized surface and title-anchor identity; the ReFinED-QID and fastcoref ML lanes are not implemented.",
            "T0 is structural viability, not retrieval efficacy; T1-T3 and any recall claim require a separate preregistration.",
            "Development split only; fresh/certificate splits untouched.",
        ],
    }
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(json.dumps({
        "evidence": str(EVIDENCE),
        "evidence_sha256": _sha256_file(EVIDENCE),
        "primary_min_c3_chains": primary,
        "novel_c3_minus_c1": novel,
        "c3_per_dataset": c3_counts,
        "c1_per_dataset": c1_counts,
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
