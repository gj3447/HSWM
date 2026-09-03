#!/usr/bin/env python3
"""Validate and explicitly publish the bounded causal-composition projection."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from scripts import build_hswm_causal_composition_research_ontology as builder


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = ROOT / builder.ONTOLOGY_PATH
SCHEMA_VERSION = builder.SCHEMA_VERSION
BUNDLE_UID = builder.BUNDLE_UID
PROGRAM_UID = builder.PROGRAM_UID
REGISTRY_UID = "sym:KG_INFRA:schema-registry-v1-2026-08-03"
NONCLAIM = builder.NONCLAIM
EXPECTED_COUNTS = {
    "nodes": 99,
    "anchors": 12,
    "relations": 394,
    "gates": 8,
    "control_families": 14,
    "alternative_explanations": 14,
    "confound_axes": 6,
    "claim_ceilings": 27,
    "metacognitive_rules": 5,
    "source_records": 2,
    "run_artifact_kinds": 11,
    "run_artifact_extension_schemas": 5,
    "control_arm_classes": 4,
}
EXPECTED_PROJECTION_SHA256 = (
    "290a7bbddd9d530b7566cbeb6a577a697ac5a9fee0647e425227cc75e674f5cf"
)
EXPECTED_NODES_SHA256 = (
    "f4ced8acb8b8cc366be97c4987d05ef01195ef1162a5f3cb1c1df74ea1ada4ef"
)
EXPECTED_ANCHORS_SHA256 = (
    "24287a62d07c33f6500141a237be6b52f70d7a7e50f7824b8a7c98f51f93da1c"
)
EXPECTED_RELATIONS_SHA256 = (
    "d8b6d75799b9b5911abb540f217cb266207f4498de83c1f87e278b29219749c8"
)
EXPECTED_FILE_SHA256 = (
    "499aaa7535181d711fb340dce4085877e9389e9960c59950e1f0e99b8144f171"
)
SAFE_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SAFE_RELATION = re.compile(r"[A-Z][A-Z0-9_]*")
TOP_LEVEL_KEYS = {
    "schema_version",
    "bundle_uid",
    "status",
    "nonclaim",
    "authority_boundary",
    "artifact_bindings",
    "expected_counts",
    "anchors",
    "nodes",
    "relations",
}


def _canonical_sha(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _neo4j_property(value: Any) -> bool:
    return isinstance(value, (str, bool, int, float)) or (
        isinstance(value, list)
        and all(isinstance(item, (str, bool, int, float)) for item in value)
    )


def read_flat_yaml(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if ":" in raw and not raw.lstrip().startswith("#"):
            key, value = raw.split(":", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    if {"uri", "user", "password", "database"} - values.keys():
        raise ValueError("source config is incomplete")
    return values


def _binding_map(data: Mapping[str, Any], repo_root: Path) -> dict[str, str]:
    rows = data.get("artifact_bindings")
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) or set(row) != {"path", "sha256"}
        for row in rows
    ):
        raise ValueError("artifact bindings have an invalid shape")
    expected_paths = {path.as_posix() for path in builder.SOURCE_BINDING_PATHS}
    observed_paths = [row["path"] for row in rows]
    if len(observed_paths) != len(set(observed_paths)) or set(observed_paths) != expected_paths:
        raise ValueError("artifact binding paths drifted")
    result: dict[str, str] = {}
    root = repo_root.resolve()
    for row in rows:
        logical = Path(row["path"])
        if (
            logical.is_absolute()
            or ".." in logical.parts
            or logical.as_posix() != row["path"]
        ):
            raise ValueError("artifact binding path is not normalized")
        path = repo_root / logical
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"artifact binding is not a regular file: {logical}")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError(f"artifact binding escapes repository: {logical}")
        observed_sha = _file_sha(path)
        if row["sha256"] != observed_sha:
            raise ValueError(f"artifact binding drifted: {logical}")
        result[row["path"]] = observed_sha
    return result


def validate_data(data: dict[str, Any], repo_root: Path = ROOT) -> None:
    """Fail closed on identity, authority, graph, control, or source drift."""

    if set(data) != TOP_LEVEL_KEYS:
        raise ValueError("causal-composition ontology top-level shape drifted")
    if data.get("schema_version") != SCHEMA_VERSION or data.get("bundle_uid") != BUNDLE_UID:
        raise ValueError("unexpected causal-composition ontology identity")
    if data.get("status") != (
        "DESIGN_SEEDED_SCIENTIFICALLY_CONNECTED_INTEGRATED_CLAIM_UNJUDGED"
    ):
        raise ValueError("causal-composition scientific status drifted")
    if data.get("nonclaim") != NONCLAIM:
        raise ValueError("causal-composition nonclaim drifted")
    if data.get("expected_counts") != EXPECTED_COUNTS:
        raise ValueError("causal-composition declared counts drifted")
    _binding_map(data, repo_root)
    if (
        _canonical_sha(data),
        _canonical_sha(data.get("nodes")),
        _canonical_sha(data.get("anchors")),
        _canonical_sha(data.get("relations")),
    ) != (
        EXPECTED_PROJECTION_SHA256,
        EXPECTED_NODES_SHA256,
        EXPECTED_ANCHORS_SHA256,
        EXPECTED_RELATIONS_SHA256,
    ):
        raise ValueError("causal-composition projection content drifted")
    if data != builder.build_data():
        raise ValueError("causal-composition projection is not the deterministic build")

    nodes = data["nodes"]
    anchors = data["anchors"]
    relations = data["relations"]
    if not all(isinstance(rows, list) for rows in (nodes, anchors, relations)):
        raise ValueError("nodes, anchors, and relations must be arrays")
    if (len(nodes), len(anchors), len(relations)) != (
        EXPECTED_COUNTS["nodes"],
        EXPECTED_COUNTS["anchors"],
        EXPECTED_COUNTS["relations"],
    ):
        raise ValueError("causal-composition graph count mismatch")
    if any(not isinstance(row, dict) for row in nodes + anchors + relations):
        raise ValueError("causal-composition graph records must be objects")

    anchor_uids = [row.get("uid") for row in anchors]
    if any(
        set(row) != {"uid", "name", "required_labels"}
        or not isinstance(row["uid"], str)
        or not row["uid"]
        or not isinstance(row["name"], str)
        or not row["name"]
        or not isinstance(row["required_labels"], list)
        or not row["required_labels"]
        or any(
            not isinstance(label, str) or not SAFE_LABEL.fullmatch(label)
            for label in row["required_labels"]
        )
        for row in anchors
    ):
        raise ValueError("anchor descriptors are unsafe")
    node_uids = [row.get("uid") for row in nodes]
    duplicates = {
        uid: count
        for uid, count in Counter(node_uids + anchor_uids).items()
        if not isinstance(uid, str) or not uid or count > 1
    }
    if duplicates or set(node_uids) & set(anchor_uids):
        raise ValueError(f"duplicate or overlapping ontology UID: {duplicates}")
    if BUNDLE_UID not in node_uids or PROGRAM_UID not in node_uids:
        raise ValueError("bundle or research program node is absent")

    required_properties = {
        "name",
        "description",
        "authority_class",
        "canonical_scope",
        "ontology_kind",
        "ontology_plane",
        "epistemic_state",
        "responsibility_owner",
        "claim_boundary",
        "projection_nonclaim",
        "ontology_domain",
        "record_lifecycle",
        "review_required",
        "semantic_roles",
    }
    for row in nodes:
        if set(row) != {"uid", "labels", "properties"}:
            raise ValueError("node record shape drifted")
        labels = row["labels"]
        properties = row["properties"]
        if (
            not isinstance(labels, list)
            or not labels
            or len(labels) != len(set(labels))
            or any(
                not isinstance(label, str) or not SAFE_LABEL.fullmatch(label)
                for label in labels
            )
        ):
            raise ValueError("node labels are unsafe")
        if not required_properties <= set(properties):
            raise ValueError("node lacks authority, owner, evidence, or claim boundary")
        if (
            properties["authority_class"] != "SECONDARY_AI"
            or properties["canonical_scope"] != "RESEARCH_PROJECTION_NOT_HSWM_CANON"
            or properties["projection_nonclaim"] != NONCLAIM
            or properties["review_required"] is not True
        ):
            raise ValueError("node authority or nonclaim boundary drifted")
        if any(
            not isinstance(key, str) or not _neo4j_property(value)
            for key, value in properties.items()
        ):
            raise ValueError(f"node has unsafe Neo4j properties: {row['uid']}")

    gate_nodes = {
        row["properties"]["gate_id"]: row
        for row in nodes
        if "gate_id" in row["properties"]
    }
    control_nodes = {
        row["properties"]["control_id"]: row
        for row in nodes
        if "control_id" in row["properties"]
        and "CONTROL_FAMILY" in row["properties"]["semantic_roles"]
    }
    alternative_nodes = [
        row for row in nodes
        if "ALTERNATIVE_EXPLANATION" in row["properties"]["semantic_roles"]
    ]
    axis_nodes = [
        row for row in nodes if "CONFOUND_AXIS" in row["properties"]["semantic_roles"]
    ]
    ceiling_nodes = [
        row for row in nodes if "CLAIM_CEILING" in row["properties"]["semantic_roles"]
    ]
    rule_nodes = [
        row for row in nodes if "METACOGNITIVE_RULE" in row["properties"]["semantic_roles"]
    ]
    source_nodes = [row for row in nodes if "SourceDocument" in row["labels"]]
    run_artifact_nodes = [
        row
        for row in nodes
        if "RUN_ARTIFACT_KIND" in row["properties"]["semantic_roles"]
    ]
    extension_nodes = [
        row
        for row in nodes
        if "RUN_ARTIFACT_EXTENSION_SCHEMA"
        in row["properties"]["semantic_roles"]
    ]
    arm_class_nodes = [
        row
        for row in nodes
        if "CONTROL_ARM_CLASS" in row["properties"]["semantic_roles"]
    ]
    if (
        len(gate_nodes),
        len(control_nodes),
        len(alternative_nodes),
        len(axis_nodes),
        len(ceiling_nodes),
        len(rule_nodes),
        len(source_nodes),
        len(run_artifact_nodes),
        len(extension_nodes),
        len(arm_class_nodes),
    ) != (
        EXPECTED_COUNTS["gates"],
        EXPECTED_COUNTS["control_families"],
        EXPECTED_COUNTS["alternative_explanations"],
        EXPECTED_COUNTS["confound_axes"],
        EXPECTED_COUNTS["claim_ceilings"],
        EXPECTED_COUNTS["metacognitive_rules"],
        EXPECTED_COUNTS["source_records"],
        EXPECTED_COUNTS["run_artifact_kinds"],
        EXPECTED_COUNTS["run_artifact_extension_schemas"],
        EXPECTED_COUNTS["control_arm_classes"],
    ):
        raise ValueError("causal-composition atom-family counts drifted")
    if {
        row["properties"].get("artifact_kind_id") for row in run_artifact_nodes
    } != set(builder.RUN_ARTIFACT_UIDS) or any(
        not row["properties"].get("required_fields")
        or row["properties"]["epistemic_state"] != "SCHEMA_DEFINITION"
        for row in run_artifact_nodes
    ):
        raise ValueError("run-artifact schema definition drifted")
    if {
        row["properties"].get("extension_schema_id") for row in extension_nodes
    } != set(builder.EXTENSION_UIDS) or any(
        not row["properties"].get("required_fields")
        or not row["properties"].get("applies_to_id")
        or row["properties"]["epistemic_state"] != "SCHEMA_DEFINITION"
        for row in extension_nodes
    ):
        raise ValueError("run-artifact extension schema definition drifted")
    if {
        row["properties"].get("arm_class_id") for row in arm_class_nodes
    } != set(builder.CONTROL_ARM_CLASS_UIDS) or any(
        not isinstance(row["properties"].get("eligible_for_causal_ranking"), bool)
        or not row["properties"].get("information_contract")
        for row in arm_class_nodes
    ):
        raise ValueError("control-arm class definition drifted")
    if set(gate_nodes) != set(builder.GATE_UIDS) or set(control_nodes) != set(builder.CONTROL_UIDS):
        raise ValueError("gate or control identifiers drifted")
    if any(
        row["properties"]["epistemic_state"] != "PROPOSED_TEST"
        or not row["properties"].get("exact_intervention")
        or not row["properties"].get("pass_rule")
        or not row["properties"].get("failure_observation")
        or not row["properties"].get("stop_rule")
        for row in gate_nodes.values()
    ):
        raise ValueError("gate falsification or stop contract is incomplete")
    if any(
        row["properties"]["epistemic_state"] != "PROPOSED_TEST"
        or not row["properties"].get("alternative_explanation")
        or not row["properties"].get("intervention")
        or not row["properties"].get("primary_observables")
        or not row["properties"].get("failure_inference")
        or not row["properties"].get("claim_ceiling_if_failed")
        for row in control_nodes.values()
    ):
        raise ValueError("control-family metacognitive contract is incomplete")

    endpoints = set(node_uids + anchor_uids)
    relation_keys: list[tuple[str, str, str]] = []
    for row in relations:
        if (
            set(row)
            != {"from_uid", "type", "to_uid", "authority_class", "scope", "status"}
            or not isinstance(row.get("type"), str)
            or not SAFE_RELATION.fullmatch(row["type"])
            or row.get("from_uid") not in endpoints
            or row.get("to_uid") not in endpoints
            or any(
                not isinstance(row.get(key), str) or not row[key]
                for key in ("authority_class", "scope", "status")
            )
        ):
            raise ValueError("relation shape, token, or endpoint closure drifted")
        if row["from_uid"] in anchor_uids and row["to_uid"] in anchor_uids:
            raise ValueError("projection may not create anchor-to-anchor relations")
        if row["type"] == "EVIDENCE_FOR":
            raise ValueError("research design may not claim HSWM efficacy evidence")
        relation_keys.append((row["from_uid"], row["type"], row["to_uid"]))
    if len(relation_keys) != len(set(relation_keys)):
        raise ValueError("duplicate causal-composition relation identity")
    used = {
        endpoint
        for relation in relations
        for endpoint in (relation["from_uid"], relation["to_uid"])
    }
    if endpoints - used:
        raise ValueError(f"unused ontology endpoints: {sorted(endpoints - used)}")

    project = json.loads((repo_root / builder.PROJECT_PATH).read_text(encoding="utf-8"))
    validator_path = project["run_contract"]["instance_validator"]["path"]
    if validator_path != "scripts/validate_hswm_causal_composition_run.py":
        raise ValueError("run-bundle validator path drifted")
    validator_file = repo_root / validator_path
    if validator_file.is_symlink() or not validator_file.is_file():
        raise ValueError("run-bundle validator is missing or not a regular file")
    if project.get("claim_ceiling_uids") != builder.CEILING_UIDS:
        raise ValueError("claim-ceiling UID contract drifted")
    relation_set = set(relation_keys)
    for gate in project["gates"]:
        gate_uid = builder.GATE_UIDS[gate["id"]]
        observed_prerequisites = {
            to_uid
            for from_uid, relation_type, to_uid in relation_set
            if from_uid == gate_uid
            and relation_type == "REQUIRES"
            and to_uid in set(builder.GATE_UIDS.values())
        }
        if observed_prerequisites != {
            builder.GATE_UIDS[gate_id] for gate_id in gate["prerequisites"]
        }:
            raise ValueError(f"gate prerequisite drifted: {gate['id']}")
        observed_controls = {
            to_uid
            for from_uid, relation_type, to_uid in relation_set
            if from_uid == gate_uid
            and relation_type == "REQUIRES"
            and to_uid in set(builder.CONTROL_UIDS.values())
        }
        if observed_controls != {
            builder.CONTROL_UIDS[control_id]
            for control_id in gate["required_control_ids"]
        }:
            raise ValueError(f"gate control requirement drifted: {gate['id']}")
        observed_fcls = {
            to_uid
            for from_uid, relation_type, to_uid in relation_set
            if from_uid == gate_uid and relation_type == "SPECULATIVE_LINK"
        }
        if observed_fcls != {
            builder.FCL_UIDS[fcl_id] for fcl_id in gate["mapped_fcl_ids"]
        }:
            raise ValueError(f"gate FCL mapping drifted: {gate['id']}")
        ceiling_edges = {
            to_uid
            for from_uid, relation_type, to_uid in relation_set
            if from_uid == gate_uid
            and relation_type == "HAS_CONCEPT"
            and to_uid in set(builder.CEILING_UIDS.values())
        }
        expected_ceiling_ids = {gate["claim_ceiling"]}
        if "precursor_claim_ceiling" in gate:
            expected_ceiling_ids.add(gate["precursor_claim_ceiling"])
        if "fallback_claim_ceiling" in gate:
            expected_ceiling_ids.add(gate["fallback_claim_ceiling"])
        if ceiling_edges != {
            builder.CEILING_UIDS[ceiling_id]
            for ceiling_id in expected_ceiling_ids
        }:
            raise ValueError(f"gate claim ceiling drifted: {gate['id']}")
    mapped_fcls = {
        to_uid
        for from_uid, relation_type, to_uid in relation_set
        if from_uid in set(builder.GATE_UIDS.values())
        and relation_type == "SPECULATIVE_LINK"
        and to_uid in set(builder.FCL_UIDS.values())
    }
    if mapped_fcls != set(builder.FCL_UIDS.values()):
        raise ValueError("research gates must cover all eight FCL laws")
    for control in project["control_families"]:
        control_uid = builder.CONTROL_UIDS[control["id"]]
        targeted_alternatives = {
            to_uid
            for from_uid, relation_type, to_uid in relation_set
            if from_uid == control_uid
            and relation_type == "TARGETS"
            and to_uid in set(builder.ALT_UIDS.values())
        }
        if targeted_alternatives != {builder.ALT_UIDS[control["id"]]}:
            raise ValueError(f"control alternative explanation drifted: {control['id']}")
        matched_axes = {
            to_uid
            for from_uid, relation_type, to_uid in relation_set
            if from_uid == control_uid
            and relation_type == "PRESERVES"
            and to_uid in set(builder.AXIS_UIDS.values())
        }
        if matched_axes != {
            builder.AXIS_UIDS[axis_id] for axis_id in control["matched_axes"]
        }:
            raise ValueError(f"control matched-axis graph drifted: {control['id']}")
        failure_ceiling_edges = {
            to_uid
            for from_uid, relation_type, to_uid in relation_set
            if from_uid == control_uid
            and relation_type == "HAS_CONCEPT"
            and to_uid in set(builder.CEILING_UIDS.values())
        }
        if failure_ceiling_edges != {
            builder.CEILING_UIDS[control["claim_ceiling_if_failed"]]
        }:
            raise ValueError(f"control failure ceiling drifted: {control['id']}")
    for artifact_uid in builder.RUN_ARTIFACT_UIDS.values():
        if (
            builder.PROGRAM_UID,
            "HAS_CONCEPT",
            artifact_uid,
        ) not in relation_set or (
            builder.BENCHMARK_UID,
            "REQUIRES",
            artifact_uid,
        ) not in relation_set:
            raise ValueError("run-artifact program or benchmark binding drifted")
    expected_artifact_dependencies = {
        (
            builder.RUN_ARTIFACT_UIDS[source_kind],
            "REQUIRES",
            builder.RUN_ARTIFACT_UIDS[target_kind],
        )
        for source_kind, target_kind in (
            ("ControlInstance", "MatchedBudget"),
            ("ControlInstance", "PreOutcomeSeal"),
            ("ObservedResult", "OutcomeSource"),
            ("ObservedResult", "InstrumentCalibration"),
            ("ObservedResult", "PreOutcomeSeal"),
            ("ControlAssessment", "ObservedResult"),
            ("ClaimDecision", "ControlAssessment"),
            ("GateAssessment", "ClaimDecision"),
            ("GateDecision", "GateAssessment"),
        )
    }
    observed_artifact_dependencies = {
        key
        for key in relation_set
        if key[0] in set(builder.RUN_ARTIFACT_UIDS.values())
        and key[2] in set(builder.RUN_ARTIFACT_UIDS.values())
    }
    if observed_artifact_dependencies != expected_artifact_dependencies:
        raise ValueError("run-artifact dependency graph drifted")
    extension_base_dependencies = {
        "CF08LifecycleCostEvidence": {"MatchedBudget", "ObservedResult"},
        "CF13SelectionEvidence": {
            "ControlInstance",
            "PreOutcomeSeal",
            "ObservedResult",
            "ClaimDecision",
        },
        "CF14AuthorityEvidence": {
            "ControlInstance",
            "ObservedResult",
            "ClaimDecision",
        },
        "G4PrecursorDecisionEvidence": {
            "GateAssessment",
            "GateDecision",
        },
        "G5MacroIdentificationEvidence": {
            "GateAssessment",
            "GateDecision",
            "BoundaryEvidence",
        },
    }
    extension_rows = {
        row["id"]: row for row in project["run_contract"]["extension_schemas"]
    }
    for extension_id, extension in extension_rows.items():
        extension_uid = builder.EXTENSION_UIDS[extension_id]
        applies_to_id = extension["applies_to_id"]
        owner_uid = (
            builder.CONTROL_UIDS[applies_to_id]
            if applies_to_id in builder.CONTROL_UIDS
            else builder.GATE_UIDS[applies_to_id]
        )
        if (
            builder.PROGRAM_UID,
            "HAS_CONCEPT",
            extension_uid,
        ) not in relation_set or (
            builder.BENCHMARK_UID,
            "HAS_CONCEPT",
            extension_uid,
        ) not in relation_set or (
            owner_uid,
            "REQUIRES",
            extension_uid,
        ) not in relation_set:
            raise ValueError("run-artifact extension binding drifted")
        observed_dependencies = {
            to_uid
            for from_uid, relation_type, to_uid in relation_set
            if from_uid == extension_uid
            and relation_type == "REQUIRES"
            and to_uid in set(builder.RUN_ARTIFACT_UIDS.values())
        }
        if observed_dependencies != {
            builder.RUN_ARTIFACT_UIDS[artifact_id]
            for artifact_id in extension_base_dependencies[extension_id]
        }:
            raise ValueError("run-artifact extension dependency drifted")
    for arm in project["control_arm_classes"]:
        arm_uid = builder.CONTROL_ARM_CLASS_UIDS[arm["id"]]
        if (
            builder.PROGRAM_UID,
            "HAS_CONCEPT",
            arm_uid,
        ) not in relation_set or (
            builder.BENCHMARK_UID,
            "HAS_CONCEPT",
            arm_uid,
        ) not in relation_set or (
            builder.CONTROL_UIDS[arm["control_id"]],
            "HAS_CONCEPT",
            arm_uid,
        ) not in relation_set:
            raise ValueError("control-arm class binding drifted")


def _project_sha(data: Mapping[str, Any]) -> str:
    bindings = {row["path"]: row["sha256"] for row in data["artifact_bindings"]}
    return bindings[builder.PROJECT_PATH.as_posix()]


def _expected_node_properties(
    data: Mapping[str, Any], row: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "uid": row["uid"],
        **row["properties"],
        "ontology_bundle_uid": data["bundle_uid"],
        "ontology_projection_sha256": EXPECTED_FILE_SHA256,
        "ontology_project_sha256": _project_sha(data),
    }


def _expected_relation_properties(
    data: Mapping[str, Any], row: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "ontology_bundle_uid": data["bundle_uid"],
        "ontology_projection_sha256": EXPECTED_FILE_SHA256,
        "authority_class": row["authority_class"],
        "scope": row["scope"],
        "status": row["status"],
    }


def _find_unique_nodes(tx: Any, uids: list[str]) -> dict[str, dict[str, Any]]:
    rows = tx.run(
        "MATCH (n) WHERE n.uid IN $uids "
        "RETURN n.uid AS uid, labels(n) AS labels, properties(n) AS properties",
        uids=uids,
    ).data()
    counts = Counter(row["uid"] for row in rows)
    duplicates = {uid: count for uid, count in counts.items() if count > 1}
    if duplicates:
        raise RuntimeError(f"duplicate remote KG UIDs: {duplicates}")
    return {row["uid"]: row for row in rows}


def _assert_exact_node(
    uid: str,
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> None:
    if set(observed["labels"]) != set(expected["labels"]):
        raise RuntimeError(f"node label collision or drift: {uid}")
    if observed["properties"] != expected["properties"]:
        raise RuntimeError(f"node property collision or drift: {uid}")


def _relation_rows(tx: Any, row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return tx.run(
        "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) "
        f"MATCH (a)-[r:{row['type']}]->(b) RETURN properties(r) AS properties",
        from_uid=row["from_uid"],
        to_uid=row["to_uid"],
    ).data()


def _assert_exact_relation(
    data: Mapping[str, Any],
    row: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> None:
    if observed["properties"] != _expected_relation_properties(data, row):
        key = (row["from_uid"], row["type"], row["to_uid"])
        raise RuntimeError(f"relationship property collision or drift: {key}")


def _registry_readback(tx: Any, data: Mapping[str, Any]) -> None:
    registry = tx.run(
        "MATCH (r:SchemaRegistry {uid:$uid}) "
        "RETURN r.allowed_labels AS labels, r.allowed_reltypes AS relations",
        uid=REGISTRY_UID,
    ).single()
    if not registry:
        raise RuntimeError(f"KG schema registry not found: {REGISTRY_UID}")
    labels = {label for row in data["nodes"] for label in row["labels"]}
    reltypes = {row["type"] for row in data["relations"]}
    missing_labels = labels - set(registry["labels"] or [])
    missing_reltypes = reltypes - set(registry["relations"] or [])
    if missing_labels or missing_reltypes:
        raise RuntimeError(
            f"unregistered schema tokens: labels={sorted(missing_labels)}, "
            f"relations={sorted(missing_reltypes)}"
        )


def _exact_readback(tx: Any, data: Mapping[str, Any]) -> dict[str, int]:
    expected_nodes = {
        row["uid"]: {
            "labels": row["labels"],
            "properties": _expected_node_properties(data, row),
        }
        for row in data["nodes"]
    }
    observed_nodes = _find_unique_nodes(tx, list(expected_nodes))
    if set(observed_nodes) != set(expected_nodes):
        raise RuntimeError("exact causal-composition node readback UID mismatch")
    for uid, expected in expected_nodes.items():
        _assert_exact_node(uid, expected, observed_nodes[uid])
    for relation in data["relations"]:
        observed = _relation_rows(tx, relation)
        if len(observed) != 1:
            raise RuntimeError(
                "exact causal-composition relation readback mismatch: "
                f"{(relation['from_uid'], relation['type'], relation['to_uid'])}"
            )
        _assert_exact_relation(data, relation, observed[0])
    owned_nodes = tx.run(
        "MATCH (n {ontology_bundle_uid:$uid}) RETURN count(n) AS count",
        uid=data["bundle_uid"],
    ).single()["count"]
    owned_relations = tx.run(
        "MATCH ()-[r {ontology_bundle_uid:$uid}]->() RETURN count(r) AS count",
        uid=data["bundle_uid"],
    ).single()["count"]
    if owned_nodes != len(expected_nodes) or owned_relations != len(data["relations"]):
        raise RuntimeError("causal-composition projection ownership readback drifted")
    return {"readback_nodes": owned_nodes, "readback_relations": owned_relations}


def publish(data: dict[str, Any], config: dict[str, str]) -> dict[str, int]:
    """Create this projection transactionally; every external anchor is MATCH-only."""

    try:
        from neo4j import GraphDatabase
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("--apply requires the optional kg dependency") from error
    driver = GraphDatabase.driver(
        config["uri"], auth=(config["user"], config["password"])
    )
    try:
        with driver.session(database=config["database"]) as session:

            def transaction(tx: Any) -> dict[str, int]:
                _registry_readback(tx, data)
                anchor_uids = [row["uid"] for row in data["anchors"]]
                present_anchors = _find_unique_nodes(tx, anchor_uids)
                if set(present_anchors) != set(anchor_uids):
                    raise RuntimeError("required causal-composition anchors are missing")
                for row in data["anchors"]:
                    observed = present_anchors[row["uid"]]
                    if observed["properties"].get("name") != row["name"]:
                        raise RuntimeError(f"anchor name drifted: {row['uid']}")
                    if not set(row["required_labels"]) <= set(observed["labels"]):
                        raise RuntimeError(f"anchor label drifted: {row['uid']}")

                new_uids = [row["uid"] for row in data["nodes"]]
                existing = _find_unique_nodes(tx, new_uids)
                if existing and len(existing) != len(new_uids):
                    raise RuntimeError(
                        "refusing a partial pre-existing causal-composition projection"
                    )
                if existing:
                    expected_by_uid = {row["uid"]: row for row in data["nodes"]}
                    for uid, observed in existing.items():
                        row = expected_by_uid[uid]
                        _assert_exact_node(
                            uid,
                            {
                                "labels": row["labels"],
                                "properties": _expected_node_properties(data, row),
                            },
                            observed,
                        )
                else:
                    for row in data["nodes"]:
                        labels = ":".join(row["labels"])
                        tx.run(
                            f"CREATE (n:{labels}) SET n=$properties",
                            properties=_expected_node_properties(data, row),
                        ).consume()

                relation_rows: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
                for row in data["relations"]:
                    key = (row["from_uid"], row["type"], row["to_uid"])
                    found = _relation_rows(tx, row)
                    if len(found) > 1:
                        raise RuntimeError(f"duplicate existing relationship: {key}")
                    if found:
                        _assert_exact_relation(data, row, found[0])
                    relation_rows[key] = found
                if any(relation_rows.values()) and not all(relation_rows.values()):
                    raise RuntimeError(
                        "refusing a partial pre-existing causal-composition relation set"
                    )
                created_relations = 0
                if not any(relation_rows.values()):
                    for row in data["relations"]:
                        tx.run(
                            "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) "
                            f"CREATE (a)-[r:{row['type']}]->(b) SET r=$properties",
                            from_uid=row["from_uid"],
                            to_uid=row["to_uid"],
                            properties=_expected_relation_properties(data, row),
                        ).consume()
                        created_relations += 1
                return {
                    "created_nodes": 0 if existing else len(new_uids),
                    "created_relations": created_relations,
                    "existing_nodes": len(existing),
                    "existing_relations": len(data["relations"])
                    - created_relations,
                    **_exact_readback(tx, data),
                }

            return session.execute_write(transaction)
    finally:
        driver.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ontology", type=Path, default=ONTOLOGY_PATH)
    parser.add_argument("--source-config", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.ontology.read_text(encoding="utf-8"))
    validate_data(data, ROOT)
    if _file_sha(args.ontology) != EXPECTED_FILE_SHA256:
        raise SystemExit("causal-composition ontology file bytes drifted")
    if not args.apply:
        print(
            json.dumps(
                {
                    "new_nodes": len(data["nodes"]),
                    "relations": len(data["relations"]),
                    "projection_sha256": EXPECTED_FILE_SHA256,
                    "status": "VALIDATED_ONLY_NOT_PUBLISHED",
                },
                sort_keys=True,
            )
        )
        return
    if args.source_config is None:
        raise SystemExit("--apply requires --source-config")
    result = publish(data, read_flat_yaml(args.source_config))
    print(
        json.dumps(
            {**result, "projection_sha256": EXPECTED_FILE_SHA256, "status": "APPLIED_OR_VERIFIED_EXACT_PROJECTION"},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
