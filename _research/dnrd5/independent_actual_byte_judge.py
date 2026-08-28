"""Independent, fail-closed judge for the DNRD-5 actual-byte fixture.

This module deliberately does not import the fixture producer, its contract,
the provider gateway, or any TypeScript validator.  It repeats only the frozen
wire vocabulary and parses every byte itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, NoReturn


CORPUS_VERSION = "hswm-dnrd5-one-block-actual-byte-corpus/v1"
JUDGE_VERSION = "hswm-dnrd5-independent-actual-byte-judge/v2"
CANONICAL_JSON_VERSION = "hswm-canonical-json/v1"
FIXTURE_CLASS = "DETERMINISTIC_FIXTURE_NOT_TRANSPORT_OR_PROVIDER_OBSERVATION"
TERMINAL = "FIXTURE_BYTE_CLOSURE_VALIDATED_NOT_PROVIDER_OCCURRENCE_OR_SCIENTIFIC_RESULT"
SCHEMA_VERSION = "hswm:dnrd5:causal-macroplasticity:v2"
SCHEMA_SHA256 = "a921264c5d1b5d9186d291e6a17ddc0282ce4eaa8832b1a599b7237c23d4b357"
SCHEMA_BYTES = 31_298
LIFECYCLE_SHA256 = "179225541585267214a6cc5b358551c39597c66e546adf46bebad121550763cc"
ALIGNMENT_SHA256 = "0e3ba180d8a3be3c2ed83ffe932965f8500862e02bdb07d953bf67a483f5c807"
ROLES = ("request-projection", "transmitted-request", "observed-response", "rng", "model-identity", "runtime-identity", "isolation-statement", "instruction", "model-input", "response-schema")
CALL_CLASSES = ("PRE_OUTCOME_TRAJECTORY",) + ("REVISION_PROPOSAL",) * 4 + ("FRESH_PROBE",) * 4
ARMS = ("ACTIVE", "OUTCOME_INDEPENDENT_SHAM", "DELAYED_NO_CREDIT", "EXACT_W0_ROLLBACK")
JOURNAL_MEDIA = "application/vnd.hswm.canonical-atom-v2-state-journal+json"
ATOM_MEDIA = "application/vnd.hswm.canonical-atom-v2+json"
SCHEMA_MEDIA = "application/vnd.hswm.canonical-schema-v2+json"
FIXTURE_JSON_MEDIA = "application/vnd.hswm.dnrd5.fixture+json"
RECEIPT_MEDIA = "application/vnd.hswm.dnrd5-v2.transition-receipt+json"
SHA = set("0123456789abcdef")
IDENTIFIER_HEAD = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
IDENTIFIER_TAIL = IDENTIFIER_HEAD | frozenset("._:/-")
MAX_JSON_BYTES = 1 << 20
MAX_JSON_DEPTH = 128
MAX_JSON_NODES = 100_000
EVIDENCE_ROLES = frozenset((
    "evaluator-input", "evaluator-output", "genuine-commitment", "genuine-opening",
    "placebo-commitment", "placebo-opening", "assignment-receipt", "randomness-receipt",
    "permit-input", "permit-resolution", "authorization", "revocation",
    "trusted-time-placeholder", "source-tree", "selected-build", "allowed-import-graph",
    "runtime", "custody-isolation-statement",
))
ATOM_KINDS = tuple((
    "study_randomness evaluator_commitment block_spec probe_commitment probe_commitment probe_commitment probe_commitment probe_commitment placebo_commitment w0_snapshot "
    "fork_incidence fork_incidence fork_incidence fork_incidence block_assignment episode_activation trajectory_contract trajectory_seal "
    "permit_policy authorization_decision capability_issuance revocation_status evaluator_capability audit_release_capability evaluator_release evaluator_release evaluator_release evaluator_release evaluator_release "
    "hidden_outcome placebo_receipt outcome_credit_escrow feedback_assignment feedback_assignment feedback_assignment feedback_assignment grant_snapshot restore_policy projection_policy "
    "revision_proposal revision_proposal revision_proposal revision_proposal candidate_validation candidate_validation candidate_validation candidate_validation credit_decision credit_decision credit_decision credit_decision "
    "revision_admission_decision revision_admission_decision revision_admission_decision "
    "capability_consumption capability_consumption capability_consumption evidence_seal_consumption evidence_seal_consumption evidence_seal_consumption "
    "macro_disposition macro_disposition macro_disposition revision_transition_receipt revision_transition_receipt revision_transition_receipt "
    "rollback_decision capability_consumption evidence_seal_consumption restore_transaction rollback_transition_receipt "
    "behavior_projection behavior_projection behavior_projection behavior_projection probe_trajectory probe_trajectory probe_trajectory probe_trajectory probe_outcome probe_outcome probe_outcome probe_outcome "
    "evidence_seal_consumption audit_release block_evidence_manifest block_seal"
).split())
FOUR_ARM_PAYLOAD_KINDS = frozenset({
    "fork_incidence", "feedback_assignment", "revision_proposal",
    "candidate_validation", "credit_decision", "behavior_projection",
    "probe_trajectory", "probe_outcome",
})
SPECIAL_PAYLOAD_KINDS = frozenset({
    "revision_transition_receipt", "rollback_transition_receipt",
    "block_evidence_manifest", "block_seal",
})


class ActualByteJudgeRefusal(ValueError):
    """A corpus is not independently admissible as a byte-closure candidate."""
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class ActualByteJudgeResult:
    terminal: str
    root_sha256: str
    unique_blob_count: int
    logical_provider_binding_count: int


def _refuse(code: str, detail: str) -> NoReturn:
    raise ActualByteJudgeRefusal(code, detail)


def _utf16_key(value: str) -> bytes:
    try:
        return value.encode("utf-16-be", errors="strict")
    except UnicodeEncodeError as error:
        _refuse("CANONICAL_JSON_INVALID", f"lone surrogate: {error}")


def _encode(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int and not isinstance(value, bool):
        if not -(2**53 - 1) <= value <= 2**53 - 1:
            _refuse("CANONICAL_JSON_INVALID", "integer outside safe range")
        return str(value)
    if type(value) is str:
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            _refuse("CANONICAL_JSON_INVALID", f"non-scalar string value: {error}")
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if type(value) is list:
        return "[" + ",".join(_encode(v) for v in value) + "]"
    if type(value) is dict and all(type(k) is str for k in value):
        return "{" + ",".join(f"{_encode(k)}:{_encode(value[k])}" for k in sorted(value, key=_utf16_key)) + "}"
    _refuse("CANONICAL_JSON_INVALID", "value has an unsupported JSON type")


def _parse(raw: bytes, label: str) -> Any:
    if len(raw) > MAX_JSON_BYTES:
        _refuse("CANONICAL_JSON_LIMIT_EXCEEDED", f"{label} exceeds 1 MiB")
    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in rows:
            if key in value:
                _refuse("CANONICAL_JSON_INVALID", f"{label} has duplicate key {key!r}")
            value[key] = item
        return value
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs,
                           parse_constant=lambda x: _refuse("CANONICAL_JSON_INVALID", f"{label} constant {x}"),
                           parse_float=lambda x: _refuse("CANONICAL_JSON_INVALID", f"{label} float {x}"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        _refuse("CANONICAL_JSON_INVALID", f"{label}: {error}")
    nodes = 0
    def bounded(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            _refuse("CANONICAL_JSON_LIMIT_EXCEEDED", f"{label} exceeds node/depth bound")
        if type(item) is dict:
            for child in item.values(): bounded(child, depth + 1)
        elif type(item) is list:
            for child in item: bounded(child, depth + 1)
    bounded(value, 0)
    if _encode(value).encode("utf-8") != raw:
        _refuse("CANONICAL_JSON_INVALID", f"{label} is not exact canonical-json/v1")
    return value


def _record(value: Any, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        _refuse("SHAPE_INVALID", f"{label} must be an object")
    return value


def _descriptor(value: Any, label: str) -> dict[str, Any]:
    row = _record(value, label)
    if set(row) != {"mediaType", "byteLength", "sha256"} or type(row["mediaType"]) is not str or not row["mediaType"] or type(row["byteLength"]) is not int or row["byteLength"] < 0 or type(row["sha256"]) is not str or len(row["sha256"]) != 64 or set(row["sha256"]) - SHA:
        _refuse("DESCRIPTOR_INVALID", label)
    return row


def _desc_id(row: Mapping[str, Any]) -> tuple[str, int, str]:
    return (row["mediaType"], row["byteLength"], row["sha256"])


def _key_id(value: Any) -> str:
    key = _record(value, "atom key")
    def identifier(item: Any) -> bool:
        return type(item) is str and 1 <= len(item) <= 256 and item[0] in IDENTIFIER_HEAD and not (set(item) - IDENTIFIER_TAIL)
    if set(key) != {"schemaVersion", "lineageId", "atomUid", "revisionId"} or key["schemaVersion"] != SCHEMA_VERSION or not all(identifier(key[n]) for n in ("schemaVersion", "lineageId", "atomUid")) or type(key["revisionId"]) is not int or not 0 <= key["revisionId"] <= 2**53 - 1:
        _refuse("ATOM_KEY_INVALID", "invalid v2 atom key")
    return "|".join((key["schemaVersion"], key["lineageId"], key["atomUid"], str(key["revisionId"])))


def _load(root: Path, desc: Any, label: str) -> tuple[dict[str, Any], bytes]:
    row = _descriptor(desc, label)
    path = root / "blobs" / row["sha256"]
    if path.is_symlink():
        _refuse("ROOT_CLOSURE_INVALID", f"blob must not be a symlink: {row['sha256']}")
    if not path.is_file():
        _refuse("BLOB_MISSING", f"{label}: {row['sha256']}")
    raw = path.read_bytes()
    if len(raw) != row["byteLength"] or sha256(raw).hexdigest() != row["sha256"]:
        _refuse("BLOB_DESCRIPTOR_MISMATCH", label)
    return row, raw


def _validate_root(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[tuple[str, int, str], bytes]]:
    if root.is_symlink() or not root.is_dir():
        _refuse("ROOT_CLOSURE_INVALID", "corpus root must be a regular directory")
    entries = {path.name for path in root.iterdir()}
    if entries != {"manifest.json", "blobs"}:
        _refuse("ROOT_CLOSURE_INVALID", "root entries must be exactly manifest.json and blobs")
    manifest_path = root / "manifest.json"
    blob_directory = root / "blobs"
    if manifest_path.is_symlink(): _refuse("ROOT_CLOSURE_INVALID", "manifest.json must not be a symlink")
    if not manifest_path.is_file(): _refuse("MANIFEST_MISSING", "manifest.json regular file")
    if blob_directory.is_symlink() or not blob_directory.is_dir(): _refuse("ROOT_CLOSURE_INVALID", "blobs must be a regular directory")
    manifest_raw = manifest_path.read_bytes(); manifest = _record(_parse(manifest_raw, "manifest"), "manifest")
    if set(manifest) != {"_tag", "contractVersion", "canonicalJsonVersion", "fixtureClass", "expectedTerminal", "core", "descriptorIndex", "rootDerivation"}:
        _refuse("MANIFEST_IDENTITY_INVALID", "manifest exact field set")
    if manifest.get("_tag") != "Dnrd5OneBlockActualByteCorpus" or manifest.get("contractVersion") != CORPUS_VERSION or manifest.get("canonicalJsonVersion") != CANONICAL_JSON_VERSION or manifest.get("fixtureClass") != FIXTURE_CLASS or manifest.get("expectedTerminal") != TERMINAL or manifest.get("rootDerivation") != "CANONICAL_MANIFEST_BYTES_SHA256_V1":
        _refuse("MANIFEST_IDENTITY_INVALID", "frozen manifest identity drifted")
    core = _record(manifest.get("core"), "manifest core")
    if set(core) != {"schema", "lifecycle", "alignment", "lifecycleSha256", "alignmentSha256", "atoms", "lifecycleAdapter", "journal", "fixtureLedger", "calls", "evidenceBindings", "exactCounts"}:
        _refuse("MANIFEST_IDENTITY_INVALID", "core exact field set")
    index = manifest.get("descriptorIndex")
    if type(index) is not list: _refuse("DESCRIPTOR_INDEX_INVALID", "index missing")
    descriptors = [_descriptor(v, "descriptor index") for v in index]
    # The producer's frozen descriptor order is lexical over its string ID,
    # including the decimal byte length (not numeric tuple ordering).
    order = lambda row: f"{row['mediaType']}|{row['byteLength']}|{row['sha256']}"
    if descriptors != sorted(descriptors, key=order) or len({_desc_id(v) for v in descriptors}) != len(descriptors):
        _refuse("DESCRIPTOR_INDEX_INVALID", "index is not sorted and unique")
    blobs: dict[tuple[str, int, str], bytes] = {}
    hashes: set[str] = set()
    for row in descriptors:
        _, raw = _load(root, row, "descriptor index")
        blobs[_desc_id(row)] = raw; hashes.add(row["sha256"])
    on_disk = {p.name for p in blob_directory.iterdir()}
    if on_disk != hashes:
        _refuse("BLOB_CLOSURE_INVALID", "blob directory has missing or unindexed entries")
    return manifest, core, blobs


def _validate_reachable_descriptor_closure(manifest: Mapping[str, Any], core: Mapping[str, Any], blobs: Mapping[tuple[str, int, str], bytes]) -> None:
    """Index is exactly the descriptor graph reachable from core, never a bag."""
    indexed = {_desc_id(_descriptor(row, "descriptor index")) for row in manifest["descriptorIndex"]}
    sha_media: dict[str, str] = {}
    for media, _, digest in indexed:
        prior = sha_media.setdefault(digest, media)
        if prior != media: _refuse("DESCRIPTOR_INDEX_INVALID", "one SHA has alternate media types")
    reached: set[tuple[str, int, str]] = set(); queue: list[dict[str, Any]] = []
    def scan(value: Any) -> None:
        if type(value) is dict:
            if set(value) == {"mediaType", "byteLength", "sha256"}:
                queue.append(_descriptor(value, "reachable descriptor")); return
            for child in value.values(): scan(child)
        elif type(value) is list:
            for child in value: scan(child)
    scan(core)
    while queue:
        desc = queue.pop(); ident = _desc_id(desc)
        if ident in reached: continue
        reached.add(ident)
        raw = _blob(blobs, desc, f"reachable descriptor {desc['sha256']}")
        # The frozen lifecycle vector contains foreign synthetic-artifact
        # descriptors by definition; it is a pinned reference document, not a
        # corpus-owned descriptor graph.
        if desc["sha256"] == LIFECYCLE_SHA256:
            continue
        try:
            value = _parse(raw, "reachable JSON blob")
        except ActualByteJudgeRefusal as error:
            # Non-JSON leaves are permitted; malformed JSON with JSON-like
            # media is never silently treated as an opaque leaf.
            if desc["mediaType"].endswith("+json") or desc["mediaType"] == "application/json": raise error
            continue
        scan(value)
    if reached != indexed:
        _refuse("DESCRIPTOR_INDEX_INVALID", "index differs from reachable descriptor closure")


def _blob(blobs: Mapping[tuple[str, int, str], bytes], desc: Any, label: str) -> bytes:
    row = _descriptor(desc, label); raw = blobs.get(_desc_id(row))
    if raw is None: _refuse("LOGICAL_BINDING_UNINDEXED", label)
    return raw


def _validate_schema(core: Mapping[str, Any], blobs: Mapping[tuple[str, int, str], bytes]) -> dict[str, Any]:
    schema_descriptor = _descriptor(core.get("schema"), "schema")
    if schema_descriptor["mediaType"] != SCHEMA_MEDIA:
        _refuse("SCHEMA_PIN_INVALID", "schema media type")
    raw = _blob(blobs, schema_descriptor, "schema")
    if len(raw) != SCHEMA_BYTES or sha256(raw).hexdigest() != SCHEMA_SHA256:
        _refuse("SCHEMA_PIN_INVALID", "v2 schema pin drifted")
    schema = _record(_parse(raw, "schema"), "schema")
    if schema.get("schemaVersion") != SCHEMA_VERSION or type(schema.get("kinds")) is not list or len(schema["kinds"]) != 44:
        _refuse("SCHEMA_INVALID", "v2 schema structure")
    kinds = schema["kinds"]
    names = [row.get("kind") for row in kinds if type(row) is dict]
    owners = [tuple(row.get("allowedOwners", [])) for row in kinds if type(row) is dict]
    if len(names) != 44 or len(set(names)) != 44 or any(len(owner) != 1 for owner in owners):
        _refuse("SCHEMA_INVALID", "requires 44 kinds and exactly one owner per kind")
    return schema


def _validate_atoms(core: Mapping[str, Any], blobs: Mapping[tuple[str, int, str], bytes], schema: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    for entry in schema["kinds"]:
        row = _record(entry, "schema kind"); kind = row.get("kind")
        if type(kind) is not str or not kind.startswith("hswm:dnrd5:v2:") or kind in contracts: _refuse("SCHEMA_INVALID", "kind closure")
        contracts[kind] = row
    atoms = core.get("atoms")
    if type(atoms) is not list or not atoms: _refuse("ATOM_CLOSURE_INVALID", "atom list")
    if len(atoms) != len(ATOM_KINDS) or tuple(row.get("kind") for row in atoms if type(row) is dict) != ATOM_KINDS:
        _refuse("ATOM_CLOSURE_INVALID", "fixture requires the exact 87-atom kind sequence")
    by_key: dict[str, dict[str, Any]] = {}
    kind_offsets: dict[str, int] = {}
    for ordinal, row in enumerate(atoms, 1):
        listed = _record(row, "atom listing")
        if set(listed) != {"key", "kind", "payload", "envelope"}: _refuse("ATOM_CLOSURE_INVALID", "atom listing exact fields")
        keyid = _key_id(listed.get("key")); kind = listed.get("kind")
        if listed["key"].get("revisionId") != 0 or listed["key"].get("lineageId") != "dnrd5-fixture-block-0001":
            _refuse("ATOM_CLOSURE_INVALID", "fixture lineage/revisions")
        if keyid in by_key or type(kind) is not str or f"hswm:dnrd5:v2:{kind}" not in contracts: _refuse("ATOM_CLOSURE_INVALID", "duplicate/unknown listed atom")
        payload = _descriptor(listed.get("payload"), "atom payload")
        expected_payload_media = RECEIPT_MEDIA if kind in {"revision_transition_receipt", "rollback_transition_receipt"} else FIXTURE_JSON_MEDIA
        if payload["mediaType"] != expected_payload_media: _refuse("ATOM_ENVELOPE_INVALID", "payload media")
        _blob(blobs, payload, "atom payload")
        envelope_raw = _blob(blobs, listed.get("envelope"), "atom envelope")
        if _descriptor(listed["envelope"], "atom envelope")["mediaType"] != ATOM_MEDIA: _refuse("ATOM_ENVELOPE_INVALID", "envelope media")
        env = _record(_parse(envelope_raw, "atom envelope"), "atom envelope")
        envelope_fields = {"_tag", "contractVersion", "key", "kind", "responsibilityOwner", "content", "provenance", "lifecycle", "references"}
        if set(env) != envelope_fields or env.get("_tag") != "CanonicalAtomV2" or env.get("contractVersion") != "hswm-canonical-atom/v2" or env.get("_key") is not None or _key_id(env.get("key")) != keyid or env.get("kind") != f"hswm:dnrd5:v2:{kind}" or env.get("content") != payload or env.get("lifecycle") != "ADMITTED":
            _refuse("ATOM_ENVELOPE_INVALID", keyid)
        contract = contracts[env["kind"]]
        if env.get("responsibilityOwner") not in contract.get("allowedOwners", []): _refuse("ATOM_OWNER_INVALID", keyid)
        by_key[keyid] = env
        offset = kind_offsets.get(kind, 0); kind_offsets[kind] = offset + 1
        if kind not in SPECIAL_PAYLOAD_KINDS:
            payload_value = _record(_parse(_blob(blobs, payload, "atom payload"), "atom payload"), "atom payload")
            if set(payload_value) != {"_tag", "fixtureClass", "kind", "ordinal", "arm", "slot"} or payload_value.get("_tag") != "Dnrd5FixtureAtomPayload" or payload_value.get("fixtureClass") != FIXTURE_CLASS or payload_value.get("kind") != kind or payload_value.get("ordinal") != ordinal:
                _refuse("SEMANTIC_JOIN_INVALID", "non-special atom payload grammar")
            expected_arm: str | None = None; expected_slot: int | None = None
            if kind in FOUR_ARM_PAYLOAD_KINDS:
                expected_arm, expected_slot = ARMS[offset], offset
            elif kind in {"revision_admission_decision", "macro_disposition"}:
                expected_arm = (ARMS[0], ARMS[1], ARMS[3])[offset]
                expected_slot = (0, 1, 3)[offset]
            if payload_value.get("arm") != expected_arm or payload_value.get("slot") != expected_slot:
                _refuse("SEMANTIC_JOIN_INVALID", f"{kind} arm/slot payload")
    for keyid, atom in by_key.items():
        refs = atom.get("references")
        if type(refs) is not list: _refuse("ATOM_REFERENCE_INVALID", keyid)
        for ref in refs:
            row = _record(ref, "atom reference")
            if row.get("referenceType") != "hswm:dnrd5:v2:reference" or _key_id(row.get("target")) not in by_key:
                _refuse("ATOM_REFERENCE_INVALID", keyid)
        provenance = _record(atom.get("provenance"), "atom provenance")
        if set(provenance) != {"mode", "evidenceSha256", "sourceRef"}:
            _refuse("JOURNAL_PROVENANCE_INVALID", keyid)
    return by_key


def _validate_evidence_bindings(core: Mapping[str, Any], blobs: Mapping[tuple[str, int, str], bytes]) -> None:
    """Require explicit bounded-fixture evidence, never an occurrence assertion."""
    rows = core.get("evidenceBindings")
    if type(rows) is not dict or set(rows) != EVIDENCE_ROLES:
        _refuse("EVIDENCE_BINDING_INVALID", "requires the frozen 18-role evidence binding set")
    placeholder = {"trusted-time-placeholder", "source-tree", "selected-build", "allowed-import-graph"}
    payloads: dict[str, list[dict[str, Any]]] = {}
    for listing in core["atoms"]:
        payloads.setdefault(listing["kind"], []).append(listing["payload"])
    call0 = _record(core["calls"][0], "first fixture call")
    call0_contents = _record(call0.get("contents"), "first fixture call contents")
    expected_sources = {
        "evaluator-input": [call0_contents.get("model-input")],
        "evaluator-output": [call0_contents.get("observed-response")],
        "genuine-commitment": [payloads["evaluator_commitment"][0]],
        "genuine-opening": [payloads["evaluator_release"][0]],
        "placebo-commitment": [payloads["placebo_commitment"][0]],
        "placebo-opening": [payloads["placebo_receipt"][0]],
        "assignment-receipt": [payloads["block_assignment"][0]],
        "randomness-receipt": [payloads["study_randomness"][0]],
        "permit-input": [payloads["permit_policy"][0]],
        "permit-resolution": [payloads["capability_issuance"][0]],
        "authorization": [payloads["authorization_decision"][0]],
        "revocation": [payloads["revocation_status"][0]],
        "trusted-time-placeholder": [],
        "source-tree": [],
        "selected-build": [],
        "allowed-import-graph": [],
        "runtime": [call0_contents.get("runtime-identity")],
        "custody-isolation-statement": [call0_contents.get("isolation-statement")],
    }
    fields = {"_tag", "contractVersion", "fixtureClass", "role", "evidenceClass", "claimBoundary", "sourceDescriptors"}
    for role, desc in rows.items():
        if _descriptor(desc, f"evidence {role}")["mediaType"] != FIXTURE_JSON_MEDIA:
            _refuse("EVIDENCE_BINDING_INVALID", f"{role} media type")
        item = _record(_parse(_blob(blobs, desc, f"evidence {role}"), f"evidence {role}"), "evidence binding")
        if set(item) != fields or item.get("_tag") != "Dnrd5FixtureEvidenceBinding" or item.get("contractVersion") != "hswm-dnrd5-fixture-evidence-binding/v1" or item.get("fixtureClass") != FIXTURE_CLASS or item.get("role") != role or item.get("claimBoundary") != "NOT_SOURCE_BUILD_IMPORT_PERMIT_PROVIDER_OCCURRENCE_OR_SCIENTIFIC_RESULT" or type(item.get("sourceDescriptors")) is not list:
            _refuse("EVIDENCE_BINDING_INVALID", "exact evidence binding grammar")
        if role in placeholder:
            if item["evidenceClass"] != "DECLARED_PLACEHOLDER_NOT_AUTHENTICATED_EVIDENCE" or item["sourceDescriptors"] != []: _refuse("EVIDENCE_BINDING_INVALID", role)
        elif item["evidenceClass"] != "DETERMINISTIC_FIXTURE_MATERIAL_NOT_AUTHENTICATED_EVIDENCE":
            _refuse("EVIDENCE_BINDING_INVALID", role)
        if item["sourceDescriptors"] != expected_sources[role]:
            _refuse("EVIDENCE_BINDING_INVALID", f"{role} source binding")
        for source in item["sourceDescriptors"]: _blob(blobs, source, f"evidence source {role}")


def _validate_lifecycle(core: Mapping[str, Any], blobs: Mapping[tuple[str, int, str], bytes], atoms: Mapping[str, Any]) -> None:
    lifecycle_desc = _descriptor(core.get("lifecycle"), "lifecycle descriptor")
    alignment_desc = _descriptor(core.get("alignment"), "lifecycle alignment descriptor")
    if lifecycle_desc["mediaType"] != FIXTURE_JSON_MEDIA or alignment_desc["mediaType"] != FIXTURE_JSON_MEDIA:
        _refuse("LIFECYCLE_PIN_INVALID", "lifecycle/alignment media type")
    lifecycle = _blob(blobs, lifecycle_desc, "lifecycle")
    alignment = _blob(blobs, alignment_desc, "lifecycle alignment")
    if sha256(lifecycle).hexdigest() != LIFECYCLE_SHA256 or sha256(alignment).hexdigest() != ALIGNMENT_SHA256 or core.get("lifecycleSha256") != LIFECYCLE_SHA256 or core.get("alignmentSha256") != ALIGNMENT_SHA256: _refuse("LIFECYCLE_PIN_INVALID", "source pin")
    source = _record(_parse(lifecycle, "lifecycle"), "lifecycle")
    alignment_value = _record(_parse(alignment, "lifecycle alignment"), "lifecycle alignment")
    if alignment_value.get("_tag") != "Dnrd5LifecycleAtomAlignment" or alignment_value.get("contractVersion") != "hswm-dnrd5-lifecycle-atom-alignment/v1" or alignment_value.get("canonicalJsonVersion") != CANONICAL_JSON_VERSION: _refuse("LIFECYCLE_PIN_INVALID", "alignment bytes do not carry frozen contract")
    events = _record(source.get("lifecycle"), "lifecycle root").get("events")
    adapter = core.get("lifecycleAdapter")
    if type(events) is not list or len(events) != 15 or type(adapter) is not list or len(adapter) != 59: _refuse("LIFECYCLE_ADAPTER_INVALID", "requires 15 events and 59 bindings")
    artifacts = [(event.get("event"), a.get("artifactId"), a.get("kind"), a.get("arm")) for event in events if type(event) is dict for a in event.get("artifacts", []) if type(a) is dict]
    mapped = [(row.get("event"), row.get("artifactId")) for row in adapter if type(row) is dict]
    if len(artifacts) != 59 or mapped != [(event, artifact) for event, artifact, _, _ in artifacts]: _refuse("LIFECYCLE_ADAPTER_INVALID", "adapter does not exactly enumerate lifecycle artifacts")
    direct = {"STUDY_RANDOMNESS":"study_randomness", "BLOCK_SPEC":"block_spec", "EVALUATOR_COMMITMENT":"evaluator_commitment", "PROBE_COMMITMENT":"probe_commitment", "PLACEBO_COMMITMENT":"placebo_commitment", "W0_SNAPSHOT":"w0_snapshot", "FORK_INCIDENCE":"fork_incidence", "EPISODE_ACTIVATION":"episode_activation", "TRAJECTORY_CONTRACT":"trajectory_contract", "TRAJECTORY_SEAL":"trajectory_seal", "EVALUATOR_RELEASE":"evaluator_release", "HIDDEN_OUTCOME":"hidden_outcome", "OUTCOME_CREDIT_ESCROW":"outcome_credit_escrow", "PLACEBO_RECEIPT":"placebo_receipt", "FEEDBACK_ASSIGNMENT":"feedback_assignment", "REVISION_PROPOSAL":"revision_proposal", "CANDIDATE_VALIDATION":"candidate_validation", "CREDIT_DECISION":"credit_decision", "TRANSITION_RECEIPT":"revision_transition_receipt", "RESTORE_TRANSACTION":"restore_transaction", "BEHAVIOR_PROJECTION":"behavior_projection", "PROBE_OUTCOME":"probe_outcome", "BLOCK_SEAL":"block_seal"}
    ordered_by_kind: dict[str, list[str]] = {}
    for listing in core["atoms"]:
        ordered_by_kind.setdefault(listing["kind"], []).append(_key_id(listing["key"]))
    direct_cursor: dict[str, int] = {}
    def bound(value: Any, expected: str) -> str:
        keyid = _key_id(value); atom = atoms.get(keyid)
        if atom is None or atom.get("kind") != f"hswm:dnrd5:v2:{expected}": _refuse("LIFECYCLE_ADAPTER_INVALID", f"binding is not {expected}")
        return keyid
    def ordered_key(kind: str, offset: int) -> str:
        values = ordered_by_kind.get(kind, [])
        if offset >= len(values): _refuse("LIFECYCLE_ADAPTER_INVALID", f"missing ordered {kind} atom")
        return values[offset]
    def listed_key(kind: str, offset: int = 0) -> Mapping[str, Any]:
        return atoms[ordered_key(kind, offset)]["key"]
    def arm_slot(keyid: str, arm: str, slot: int) -> None:
        atom = atoms[keyid]
        payload = _record(_parse(_blob(blobs, atom.get("content"), "arm payload"), "arm payload"), "arm payload")
        if payload.get("arm") != arm or payload.get("slot") != slot:
            _refuse("SEMANTIC_JOIN_INVALID", f"{atom.get('kind')} is not bound to lifecycle arm/slot")
    assignment: list[str] = []; forks: list[str] = []; probes: dict[str, str] = {}
    for source_row, target in zip(artifacts, adapter):
        _, _, artifact_kind, arm = source_row; row = _record(target, "lifecycle adapter row")
        if artifact_kind in direct:
            if set(row) != {"event", "artifactId", "bindingClass", "bindings"} or row.get("bindingClass") != "DIRECT": _refuse("LIFECYCLE_ADAPTER_INVALID", f"{artifact_kind} must be DIRECT")
            bindings = _record(row.get("bindings"), "direct bindings")
            if set(bindings) != {"atom"}: _refuse("LIFECYCLE_ADAPTER_INVALID", "direct binding exact fields")
            kind = direct[artifact_kind]; offset = direct_cursor.get(kind, 0); direct_cursor[kind] = offset + 1
            keyid = bound(bindings.get("atom"), kind)
            if keyid != ordered_key(kind, offset):
                _refuse("LIFECYCLE_ADAPTER_INVALID", f"{artifact_kind} does not bind its exact ordered atom")
            if arm is not None and kind in FOUR_ARM_PAYLOAD_KINDS:
                if arm not in ARMS: _refuse("LIFECYCLE_ADAPTER_INVALID", "unknown direct arm")
                arm_slot(keyid, arm, ARMS.index(arm))
        elif artifact_kind == "ARM_ASSIGNMENT":
            if set(row) != {"event", "artifactId", "bindingClass", "bindings"} or row.get("bindingClass") != "ASSIGNMENT_DERIVED": _refuse("LIFECYCLE_ADAPTER_INVALID", "assignment row shape")
            bindings = _record(row.get("bindings"), "assignment bindings");
            if set(bindings) != {"assignment", "fork"}: _refuse("LIFECYCLE_ADAPTER_INVALID", "assignment binding keys")
            if arm not in ARMS: _refuse("LIFECYCLE_ADAPTER_INVALID", "unknown assignment arm")
            slot = ARMS.index(arm)
            assignment_key = bound(bindings["assignment"], "block_assignment"); fork_key = bound(bindings["fork"], "fork_incidence")
            if assignment_key != ordered_key("block_assignment", 0) or fork_key != ordered_key("fork_incidence", slot):
                _refuse("LIFECYCLE_ADAPTER_INVALID", "assignment/fork does not match lifecycle arm")
            assignment.append(assignment_key); forks.append(fork_key); arm_slot(fork_key, arm, slot)
        elif artifact_kind == "ARM_TRANSITION":
            if set(row) != {"event", "artifactId", "bindingClass", "bindings"} or row.get("bindingClass") != "ARM_TRANSITION_DERIVED": _refuse("LIFECYCLE_ADAPTER_INVALID", "arm transition row shape")
            b = _record(row.get("bindings"), "arm transition bindings);")
            required = {"validation", "credit", "stagingMainConsumption", "macroDisposition", "revisionReceipt", "restoreTransaction", "restoreMainConsumption", "rollbackReceipt"}
            if set(b) != required: _refuse("LIFECYCLE_ADAPTER_INVALID", "arm transition binding keys")
            if arm not in ARMS: _refuse("LIFECYCLE_ADAPTER_INVALID", "unknown transition arm")
            slot = ARMS.index(arm)
            expected_bindings: dict[str, Any] = {
                "validation": listed_key("candidate_validation", slot),
                "credit": listed_key("credit_decision", slot),
                "stagingMainConsumption": None,
                "macroDisposition": None,
                "revisionReceipt": None,
                "restoreTransaction": None,
                "restoreMainConsumption": None,
                "rollbackReceipt": None,
            }
            if arm != "DELAYED_NO_CREDIT":
                main_slot = slot if slot < 2 else 2
                expected_bindings.update({
                    "stagingMainConsumption": listed_key("capability_consumption", main_slot),
                    "macroDisposition": listed_key("macro_disposition", main_slot),
                    "revisionReceipt": listed_key("revision_transition_receipt", main_slot),
                })
            if arm == "EXACT_W0_ROLLBACK":
                expected_bindings.update({
                    "restoreTransaction": listed_key("restore_transaction"),
                    "restoreMainConsumption": listed_key("capability_consumption", 3),
                    "rollbackReceipt": listed_key("rollback_transition_receipt"),
                })
            if b != expected_bindings:
                _refuse("LIFECYCLE_ADAPTER_INVALID", "transition bindings do not equal exact arm tuple")
            validation_key = bound(b["validation"], "candidate_validation"); credit_key = bound(b["credit"], "credit_decision")
            arm_slot(validation_key, arm, slot); arm_slot(credit_key, arm, slot)
            for name, kind in (("stagingMainConsumption", "capability_consumption"), ("macroDisposition", "macro_disposition"), ("revisionReceipt", "revision_transition_receipt"), ("restoreTransaction", "restore_transaction"), ("restoreMainConsumption", "capability_consumption"), ("rollbackReceipt", "rollback_transition_receipt")):
                if b[name] is not None:
                    effect_key = bound(b[name], kind)
                    if kind == "macro_disposition": arm_slot(effect_key, arm, slot)
        elif artifact_kind == "PROBE_RESPONSE_SEAL":
            if set(row) != {"event", "artifactId", "bindingClass", "bindings"} or row.get("bindingClass") != "PROBE_DERIVED": _refuse("LIFECYCLE_ADAPTER_INVALID", "probe row shape")
            b = _record(row.get("bindings"), "probe bindings")
            if set(b) != {"behaviorProjection", "probeTrajectory"}: _refuse("LIFECYCLE_ADAPTER_INVALID", "probe binding keys")
            if arm not in ARMS: _refuse("LIFECYCLE_ADAPTER_INVALID", "unknown probe arm")
            slot = ARMS.index(arm)
            expected_probe = {"behaviorProjection": listed_key("behavior_projection", slot), "probeTrajectory": listed_key("probe_trajectory", slot)}
            if b != expected_probe: _refuse("LIFECYCLE_ADAPTER_INVALID", "probe binding does not equal exact arm tuple")
            projection = bound(b["behaviorProjection"], "behavior_projection"); probes[arm] = bound(b["probeTrajectory"], "probe_trajectory"); arm_slot(projection, arm, slot); arm_slot(probes[arm], arm, slot)
        elif artifact_kind == "DELAYED_AUDIT_RELEASE":
            if set(row) != {"event", "artifactId", "bindingClass", "bindings"} or row.get("bindingClass") != "AUDIT_DERIVED": _refuse("LIFECYCLE_ADAPTER_INVALID", "audit row shape")
            b = _record(row.get("bindings"), "audit bindings")
            if set(b) != {"auditRelease", "hiddenOutcome", "escrow", "probeTrajectories", "probeOutcomes"}: _refuse("LIFECYCLE_ADAPTER_INVALID", "audit binding keys")
            expected_audit = {"auditRelease": listed_key("audit_release"), "hiddenOutcome": listed_key("hidden_outcome"), "escrow": listed_key("outcome_credit_escrow"), "probeTrajectories": [listed_key("probe_trajectory", slot) for slot in range(4)], "probeOutcomes": [listed_key("probe_outcome", slot) for slot in range(4)]}
            if b != expected_audit: _refuse("LIFECYCLE_ADAPTER_INVALID", "audit binding does not equal exact ordered closure")
            bound(b["auditRelease"], "audit_release"); bound(b["hiddenOutcome"], "hidden_outcome"); bound(b["escrow"], "outcome_credit_escrow")
            if type(b["probeTrajectories"]) is not list or type(b["probeOutcomes"]) is not list or len(b["probeTrajectories"]) != 4 or len(b["probeOutcomes"]) != 4: _refuse("LIFECYCLE_ADAPTER_INVALID", "audit four-way bindings")
            if [_key_id(value) for value in b["probeTrajectories"]] != [probes[arm_name] for arm_name in ARMS]: _refuse("LIFECYCLE_ADAPTER_INVALID", "audit/probe trajectory ordered cross-link")
            for slot, value in enumerate(b["probeOutcomes"]): arm_slot(bound(value, "probe_outcome"), ARMS[slot], slot)
        else: _refuse("LIFECYCLE_ADAPTER_INVALID", f"unhandled artifact {artifact_kind}")
    if len(set(assignment)) != 1 or len(set(forks)) != 4: _refuse("LIFECYCLE_ADAPTER_INVALID", "four slots require one assignment and four distinct forks")


def _validate_semantic_joins(atoms: Mapping[str, Mapping[str, Any]], blobs: Mapping[tuple[str, int, str], bytes]) -> None:
    """Reconstruct the complete four-arm causal joins from atom references."""
    by_kind: dict[str, list[tuple[str, Mapping[str, Any], Mapping[str, Any]]]] = {}
    refs: dict[str, dict[str, list[str]]] = {}
    for key, atom in atoms.items():
        payload = _record(_parse(_blob(blobs, atom.get("content"), "semantic payload"), "semantic payload"), "semantic payload")
        kind = atom["kind"].removeprefix("hswm:dnrd5:v2:")
        by_kind.setdefault(kind, []).append((key, atom, payload))
        role_map: dict[str, list[str]] = {}
        for ref in atom.get("references", []):
            row = _record(ref, "semantic reference")
            role = str(row.get("role", "")).removeprefix("role:dnrd5:v2:")
            role_map.setdefault(role, []).append(_key_id(row.get("target")))
        refs[key] = role_map

    def keys(kind: str) -> list[str]:
        return [row[0] for row in by_kind.get(kind, [])]
    def only(kind: str) -> str:
        found = keys(kind)
        if len(found) != 1: _refuse("SEMANTIC_JOIN_INVALID", f"requires one {kind}")
        return found[0]
    def one(key: str, role: str) -> str:
        values = refs[key].get(role, [])
        if len(values) != 1: _refuse("SEMANTIC_JOIN_INVALID", f"{key} requires one {role}")
        return values[0]
    def many(key: str, role: str) -> list[str]:
        return refs[key].get(role, [])
    def expect(key: str, role: str, expected: str) -> None:
        if one(key, role) != expected: _refuse("SEMANTIC_JOIN_INVALID", f"{key} {role} crosswired")
    def expect_many(key: str, role: str, expected: list[str]) -> None:
        if many(key, role) != expected or len(set(expected)) != len(expected):
            _refuse("SEMANTIC_JOIN_INVALID", f"{key} {role} set/order crosswired")
    def arm_rows(kind: str) -> dict[str, str]:
        rows = by_kind.get(kind, [])
        result = {str(payload.get("arm")): key for key, _, payload in rows}
        if len(rows) != 4 or tuple(result) != ARMS: _refuse("SEMANTIC_JOIN_INVALID", f"{kind} must be four-arm")
        return result
    def authority(key: str, *, include_policy: bool = False) -> tuple[str, ...]:
        names = (("policy",) if include_policy else ()) + ("grant", "authorization", "capability", "revocation")
        return tuple(one(key, name) for name in names if name in refs[key])

    randomness = only("study_randomness"); evaluator = only("evaluator_commitment"); block = only("block_spec")
    probes = keys("probe_commitment"); placebo_commitment = only("placebo_commitment"); w0 = only("w0_snapshot")
    forks = arm_rows("fork_incidence"); assignment = only("block_assignment"); activation = only("episode_activation")
    trajectory_contract = only("trajectory_contract"); trajectory = only("trajectory_seal")
    policy = only("permit_policy"); authorization = only("authorization_decision"); capability = only("capability_issuance"); revocation = only("revocation_status")
    evaluator_capability = only("evaluator_capability"); audit_capability = only("audit_release_capability")
    hidden = only("hidden_outcome"); placebo = only("placebo_receipt"); escrow = only("outcome_credit_escrow")
    grant = only("grant_snapshot"); restore_policy = only("restore_policy"); projection_policy = only("projection_policy")

    expect(block, "randomness", randomness); expect(block, "evaluator", evaluator)
    if len(probes) != 5: _refuse("SEMANTIC_JOIN_INVALID", "one activation plus four fresh probe commitments required")
    for probe in probes: expect(probe, "block-spec", block); expect(probe, "randomness", randomness)
    expect(placebo_commitment, "block-spec", block); expect(placebo_commitment, "randomness", randomness)
    expect(w0, "block-spec", block)
    for arm in ARMS: expect(forks[arm], "w0", w0)
    expect(assignment, "randomness", randomness); expect(assignment, "block-spec", block); expect_many(assignment, "fork", [forks[a] for a in ARMS])
    for role, expected in (("block-spec", block), ("probe", probes[0]), ("w0", w0), ("assignment", assignment), ("evaluator", evaluator)):
        expect(activation, role, expected)
    expect_many(activation, "fork", [forks[a] for a in ARMS])
    expect(trajectory_contract, "activation", activation)
    expect(trajectory, "activation", activation); expect(trajectory, "contract", trajectory_contract); expect(trajectory, "w0", w0)

    expect(authorization, "policy", policy); expect(capability, "authorization", authorization); expect(capability, "policy", policy)
    expect(revocation, "authorization", authorization); expect(revocation, "capability", capability)
    for role, expected in (("commitment", evaluator), ("capability", capability), ("authorization", authorization), ("revocation", revocation)):
        expect(evaluator_capability, role, expected)
    for role, expected in (("block", block), ("commitment", evaluator), ("policy", policy), ("authorization", authorization), ("capability", capability), ("revocation", revocation)):
        expect(audit_capability, role, expected)
    for role, expected in (("policy", policy), ("authorization", authorization), ("capability", capability), ("revocation", revocation)):
        expect(grant, role, expected)
    expect(restore_policy, "policy", policy); expect(restore_policy, "capability", capability)
    expect(hidden, "trajectory", trajectory); expect(hidden, "commitment", evaluator)
    expect(placebo, "commitment", placebo_commitment); expect(placebo, "randomness", randomness)
    expect(escrow, "outcome", hidden); expect(escrow, "capability", capability); expect(escrow, "policy", policy)

    feedbacks = arm_rows("feedback_assignment"); proposals = arm_rows("revision_proposal")
    validations = arm_rows("candidate_validation"); credits = arm_rows("credit_decision")
    source_by_arm = {ARMS[0]: hidden, ARMS[1]: placebo, ARMS[2]: escrow, ARMS[3]: hidden}
    for arm in ARMS:
        expect(feedbacks[arm], "fork", forks[arm]); expect(feedbacks[arm], "assignment", assignment); expect(feedbacks[arm], "source", source_by_arm[arm])
        expect(proposals[arm], "trajectory", trajectory); expect(proposals[arm], "feedback", feedbacks[arm])
        expect(validations[arm], "proposal", proposals[arm])
        for role, expected in (("trajectory", trajectory), ("credit-source", source_by_arm[arm]), ("feedback", feedbacks[arm]), ("proposal", proposals[arm]), ("grant", grant)):
            expect(credits[arm], role, expected)

    decision_rows = by_kind.get("revision_admission_decision", []); admitted_arms = (ARMS[0], ARMS[1], ARMS[3])
    if tuple(row[2].get("arm") for row in decision_rows) != admitted_arms or tuple(row[2].get("slot") for row in decision_rows) != (0, 1, 3):
        _refuse("SEMANTIC_JOIN_INVALID", "admission decisions must be slots 0,1,3")
    decisions = {arm: decision_rows[index][0] for index, arm in enumerate(admitted_arms)}
    consumptions = keys("capability_consumption"); evidence = keys("evidence_seal_consumption")
    macros = {row[2]["arm"]: row[0] for row in by_kind.get("macro_disposition", [])}
    revision_receipts = keys("revision_transition_receipt")
    if len(consumptions) != 4 or len(evidence) != 5 or len(macros) != 3 or len(revision_receipts) != 3:
        _refuse("SEMANTIC_JOIN_INVALID", "effect/receipt cardinality")
    common_decision = (("block", block), ("assignment", assignment), ("grant", grant), ("authorization", authorization), ("capability", capability), ("revocation", revocation))
    for index, arm in enumerate(admitted_arms):
        decision = decisions[arm]; consumption = consumptions[index]; macro = macros[arm]; receipt = revision_receipts[index]
        for role, expected in common_decision + (("fork", forks[arm]), ("proposal", proposals[arm]), ("validation", validations[arm]), ("credit", credits[arm])):
            expect(decision, role, expected)
        for role, expected in (("grant", grant), ("capability", capability), ("revocation", revocation), ("decision", decision)):
            expect(consumption, role, expected)
        for role, expected in (("proposal", proposals[arm]), ("revision-admission-decision", decision), ("restore-policy", restore_policy), ("effect-consumption", consumption)):
            expect(macro, role, expected)
        for role, expected in (("grant", grant), ("capability", capability), ("revocation", revocation), ("purpose", decision)):
            expect(evidence[index], role, expected)
        for role, expected in (("decision", decision), ("effect-consumption", consumption), ("successor", macro), ("evidence-consumption", evidence[index])):
            expect(receipt, role, expected)

    rollback = only("rollback_decision"); restore_consumption = consumptions[3]; rollback_evidence = evidence[3]
    restore = only("restore_transaction"); rollback_receipt = only("rollback_transition_receipt")
    for role, expected in common_decision + (("fork", forks[ARMS[3]]), ("w0", w0), ("policy", restore_policy), ("staging-successor", macros[ARMS[3]]), ("staging-receipt", revision_receipts[2])):
        expect(rollback, role, expected)
    for role, expected in (("grant", grant), ("capability", capability), ("revocation", revocation), ("decision", rollback)):
        expect(restore_consumption, role, expected)
    for role, expected in (("w0", w0), ("grant", grant), ("policy", restore_policy), ("decision", rollback), ("consumption", restore_consumption), ("staging-successor", macros[ARMS[3]])):
        expect(restore, role, expected)
    for role, expected in (("grant", grant), ("capability", capability), ("revocation", revocation), ("purpose", rollback)):
        expect(rollback_evidence, role, expected)
    for role, expected in (("decision", rollback), ("effect-consumption", restore_consumption), ("restore", restore), ("evidence-consumption", rollback_evidence)):
        expect(rollback_receipt, role, expected)

    behaviors = arm_rows("behavior_projection"); probe_trajectories = arm_rows("probe_trajectory"); outcomes = arm_rows("probe_outcome")
    behavior_sources = {ARMS[0]: macros[ARMS[0]], ARMS[1]: macros[ARMS[1]], ARMS[2]: w0, ARMS[3]: restore}
    fresh_probes = probes[1:]; releases = keys("evaluator_release")
    if len(releases) != 5: _refuse("SEMANTIC_JOIN_INVALID", "one evaluator release plus four fresh-probe releases required")
    expect(hidden, "release", releases[0])
    for index, arm in enumerate(ARMS):
        expect(behaviors[arm], "source", behavior_sources[arm]); expect(behaviors[arm], "policy", projection_policy)
        expect(probe_trajectories[arm], "probe", fresh_probes[index]); expect(probe_trajectories[arm], "projection", behaviors[arm])
        release = releases[index + 1]
        for role, expected in (("trajectory", probe_trajectories[arm]), ("capability", evaluator_capability), ("authorization", authorization), ("revocation", revocation)):
            expect(release, role, expected)
        for role, expected in (("trajectory", probe_trajectories[arm]), ("release", release), ("probe", fresh_probes[index])):
            expect(outcomes[arm], role, expected)
    for role, expected in (("trajectory", trajectory), ("capability", evaluator_capability), ("authorization", authorization), ("revocation", revocation)):
        expect(releases[0], role, expected)

    audit_evidence = evidence[4]; audit = only("audit_release")
    for role, expected in (("grant", grant), ("capability", capability), ("revocation", revocation), ("purpose", audit_capability)):
        expect(audit_evidence, role, expected)
    for role, expected in (("block", block), ("assignment", assignment), ("outcome", hidden), ("escrow", escrow), ("evaluator-capability", evaluator_capability), ("release-capability", audit_capability), ("evidence-consumption", audit_evidence)):
        expect(audit, role, expected)
    expect_many(audit, "probe-trajectory", [probe_trajectories[a] for a in ARMS]); expect_many(audit, "probe-outcome", [outcomes[a] for a in ARMS]); expect_many(audit, "evaluator-release", releases[1:])

    manifest_atom = only("block_evidence_manifest"); block_seal = only("block_seal")
    for role, expected in (("block", block), ("assignment", assignment), ("trajectory", trajectory), ("audit-release", audit), ("rollback-receipt", rollback_receipt), ("restore", restore)):
        expect(manifest_atom, role, expected)
    expect_many(manifest_atom, "probe-trajectory", [probe_trajectories[a] for a in ARMS]); expect_many(manifest_atom, "probe-outcome", [outcomes[a] for a in ARMS]); expect_many(manifest_atom, "revision-receipt", revision_receipts)
    for role, expected in (("block", block), ("assignment", assignment), ("manifest", manifest_atom), ("audit-release", audit)):
        expect(block_seal, role, expected)
    expect_many(block_seal, "probe-outcome", [outcomes[a] for a in ARMS])


def _validate_provider(core: Mapping[str, Any], blobs: Mapping[tuple[str, int, str], bytes]) -> tuple[int, dict[str, int]]:
    calls = core.get("calls"); ledger = core.get("fixtureLedger")
    if type(calls) is not list or len(calls) != 9 or type(ledger) is not list or len(ledger) != 18: _refuse("PROVIDER_CARDINALITY_INVALID", "nine calls / eighteen records required")
    ids: list[str] = []
    identity_values: dict[str, set[str]] = {name: set() for name in ("callId", "sessionId", "workerId", "requestNonce")}
    rng_descriptors: set[tuple[str, int, str]] = set(); private_bindings: set[str] = set()
    receipt_by_call: dict[str, dict[str, Any]] = {}
    for zero_index, call in enumerate(calls):
        ordinal = zero_index + 1; row = _record(call, "call")
        if set(row) != {"callId", "callClass", "receipt", "contents"}: _refuse("PROVIDER_GRAMMAR_INVALID", "call exact fields")
        call_id = row.get("callId")
        if call_id != f"fixture-call-{ordinal:02d}" or row.get("callClass") != CALL_CLASSES[zero_index]: _refuse("PROVIDER_GRAMMAR_INVALID", "call identity/class/order")
        ids.append(call_id); contents = _record(row.get("contents"), "call contents")
        if set(contents) != set(ROLES): _refuse("PROVIDER_CONTENT_INVALID", "ten exact content roles")
        raw_by_role: dict[str, bytes] = {}
        for role in ROLES:
            desc = _descriptor(contents[role], f"call {call_id} {role}")
            if desc["mediaType"] != FIXTURE_JSON_MEDIA: _refuse("PROVIDER_CONTENT_INVALID", f"{role} media type")
            raw_by_role[role] = _blob(blobs, desc, f"call {call_id} {role}")
        if raw_by_role["request-projection"] == raw_by_role["transmitted-request"]: _refuse("PROVIDER_PROJECTION_INVALID", "projection must differ from request")
        if b"privateBinding" in raw_by_role["transmitted-request"] or b"private-" in raw_by_role["transmitted-request"]: _refuse("PROVIDER_HIDDEN_LEAK", call_id)
        for role in ROLES:
            raw = raw_by_role[role]
            value = _record(_parse(raw, f"call {call_id} {role}"), "call content")
            base = {"_tag", "fixtureClass", "callId", "callClass", "role", "ordinal"}
            extra = {"privateBinding"} if role == "request-projection" else {"wireOnly"} if role == "transmitted-request" else set()
            if set(value) != base | extra or value.get("_tag") != "Dnrd5FixtureCallContent" or value.get("fixtureClass") != FIXTURE_CLASS or value.get("callId") != call_id or value.get("callClass") != row["callClass"] or value.get("role") != role or value.get("ordinal") != ordinal:
                _refuse("PROVIDER_CONTENT_INVALID", f"{call_id} {role} raw grammar")
            if role == "request-projection":
                private = value.get("privateBinding")
                if private != f"private-{ordinal:02d}" or private in private_bindings: _refuse("PROVIDER_IDENTITY_INVALID", "private binding")
                private_bindings.add(private)
            elif role == "transmitted-request" and value.get("wireOnly") != f"wire-{ordinal:02d}":
                _refuse("PROVIDER_CONTENT_INVALID", "transmitted request wire identity")
        receipt_descriptor = _descriptor(row.get("receipt"), "call receipt")
        if receipt_descriptor["mediaType"] != FIXTURE_JSON_MEDIA: _refuse("PROVIDER_IDENTITY_INVALID", "receipt media")
        receipt = _record(_parse(_blob(blobs, receipt_descriptor, "call receipt"), "call receipt"), "call receipt")
        required = {"_tag", "contractVersion", "fixtureClass", "callId", "callClass", "sessionId", "workerId", "requestNonce", "rngDescriptor", "contents", "terminal"}
        if set(receipt) != required or receipt.get("_tag") != "Dnrd5FixtureTransportReceipt" or receipt.get("contractVersion") != "hswm-dnrd5-fixture-transport-receipt/v1" or receipt.get("fixtureClass") != FIXTURE_CLASS or receipt.get("callId") != call_id or receipt.get("callClass") != row["callClass"] or receipt.get("terminal") != "SUCCEEDED" or receipt.get("contents") != contents:
            _refuse("PROVIDER_IDENTITY_INVALID", call_id)
        if receipt.get("rngDescriptor") != contents["rng"]:
            _refuse("PROVIDER_IDENTITY_INVALID", "receipt rng descriptor")
        expected_identity = {
            "callId": call_id,
            "sessionId": f"session-{ordinal:02d}",
            "workerId": f"worker-{ordinal:02d}",
            "requestNonce": f"nonce-{ordinal:02d}",
        }
        for name in identity_values:
            value = receipt.get(name)
            if value != expected_identity[name] or value in identity_values[name]: _refuse("PROVIDER_IDENTITY_INVALID", f"noncanonical or duplicate {name}")
            identity_values[name].add(value)
        rng_descriptors.add(_desc_id(_descriptor(contents["rng"], "rng")))
        receipt_by_call[call_id] = {"descriptor": receipt_descriptor, "class": row["callClass"]}
    if len(set(ids)) != 9: _refuse("PROVIDER_IDENTITY_DUPLICATE", "call ID")
    predecessor = None
    for sequence, item in enumerate(ledger, 1):
        row = _record(item, "ledger listing")
        if set(row) != {"record", "phase", "callId"}: _refuse("PROVIDER_LEDGER_INVALID", "ledger listing exact fields")
        descriptor = _descriptor(row.get("record"), "ledger record")
        if descriptor["mediaType"] != FIXTURE_JSON_MEDIA: _refuse("PROVIDER_LEDGER_INVALID", "ledger media")
        raw = _blob(blobs, descriptor, "ledger record"); record = _record(_parse(raw, "ledger record"), "ledger record")
        expected_phase = "START" if sequence % 2 else "SUCCEEDED"; expected_call = ids[(sequence - 1) // 2]
        required = {"_tag", "contractVersion", "fixtureClass", "sequence", "phase", "callId", "callClass", "receipt", "predecessor"}
        if set(record) != required or record.get("_tag") != "Dnrd5FixtureLedgerRecord" or record.get("contractVersion") != "hswm-dnrd5-fixture-transport-receipt/v1" or record.get("fixtureClass") != FIXTURE_CLASS or row.get("phase") != expected_phase or row.get("callId") != expected_call or record.get("sequence") != sequence or record.get("phase") != expected_phase or record.get("callId") != expected_call or record.get("callClass") != receipt_by_call[expected_call]["class"] or record.get("receipt") != receipt_by_call[expected_call]["descriptor"] or record.get("predecessor") != predecessor:
            _refuse("PROVIDER_LEDGER_INVALID", "ordered exact predecessor/receipt chain")
        predecessor = row["record"]
    if len(rng_descriptors) != 9 or len(private_bindings) != 9:
        _refuse("PROVIDER_IDENTITY_INVALID", "rng/private identities are not unique")
    logical = len(calls) + sum(len(call["contents"]) for call in calls)
    return logical, {
        "ledgerStarts": sum(item["phase"] == "START" for item in ledger),
        "ledgerSucceeded": sum(item["phase"] == "SUCCEEDED" for item in ledger),
        "callReceipts": len(calls),
        "receiptContentRoles": sum(len(call["contents"]) for call in calls),
    }


def _validate_journal_wire_first(
    core: Mapping[str, Any],
    blobs: Mapping[tuple[str, int, str], bytes],
    schema: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], list[tuple[str, ...]], list[dict[str, Any]]]:
    """Reject reduced producer records before any possible success projection.

    A repair must emit the exact TS journal commit fields, notably ``receipt``
    (the accepted receipt object), canonical descriptor writeBindings rather
    than producer atom listings, and no ``fixtureTag``.
    """
    journal = core.get("journal")
    if type(journal) is not list or len(journal) < 2:
        _refuse("JOURNAL_MISSING", "fixture requires genesis plus a complete commit lineage")
    genesis_listing = _record(journal[0], "genesis listing")
    if set(genesis_listing) != {"record", "tag"} or genesis_listing.get("tag") != "GENESIS":
        _refuse("JOURNAL_WIRE_GRAMMAR_REQUIRED", "genesis listing exact fields/tag")
    genesis_desc = _descriptor(genesis_listing.get("record"), "genesis descriptor")
    if genesis_desc["mediaType"] != JOURNAL_MEDIA:
        _refuse("JOURNAL_WIRE_GRAMMAR_REQUIRED", "genesis journal media type")
    genesis_raw = _blob(blobs, genesis_desc, "genesis")
    if genesis_desc != {"mediaType": JOURNAL_MEDIA, "byteLength": len(genesis_raw), "sha256": sha256(genesis_raw).hexdigest()}:
        _refuse("JOURNAL_WIRE_GRAMMAR_REQUIRED", "genesis descriptor does not bind exact bytes")
    genesis = _record(_parse(genesis_raw, "genesis"), "genesis")
    if genesis.get("_tag") != "CanonicalAtomV2StateJournalGenesis": _refuse("JOURNAL_WIRE_GRAMMAR_REQUIRED", "missing exact genesis")
    required = {"_tag", "contractVersion", "encoding", "journalLineageId", "schema", "stateRevision", "predecessor", "receipt", "writeBindings", "previousStateSha256", "resultingStateSha256", "durability"}
    commits: list[dict[str, Any]] = []
    for ordinal, item in enumerate(journal[1:], 1):
        listing = _record(item, "journal listing")
        if set(listing) != {"record", "state"}:
            _refuse("JOURNAL_WIRE_GRAMMAR_REQUIRED", f"commit listing {ordinal} exact fields")
        record_desc = _descriptor(listing.get("record"), "journal commit descriptor")
        if record_desc["mediaType"] != JOURNAL_MEDIA:
            _refuse("JOURNAL_WIRE_GRAMMAR_REQUIRED", f"commit {ordinal} journal media type")
        record_raw = _blob(blobs, record_desc, "journal commit")
        if record_desc != {"mediaType": JOURNAL_MEDIA, "byteLength": len(record_raw), "sha256": sha256(record_raw).hexdigest()}:
            _refuse("JOURNAL_WIRE_GRAMMAR_REQUIRED", f"commit {ordinal} descriptor does not bind exact bytes")
        record = _record(_parse(record_raw, "journal commit"), "journal commit")
        if record.get("_tag") != "CanonicalAtomV2StateJournalCommit" or set(record) != required:
            _refuse("JOURNAL_WIRE_GRAMMAR_REQUIRED", f"commit {ordinal} is not exact CanonicalAtomV2StateJournalCommit; emit accepted receipt, descriptor writeBindings, durability, and remove fixtureTag")
        if listing.get("state") != record.get("resultingStateSha256"):
            _refuse("JOURNAL_WIRE_GRAMMAR_REQUIRED", f"commit {ordinal} listing state is not record state")
        commits.append(record)
    replayed, groups = _replay_exact_journal(genesis, commits, schema, blobs, core.get("schema"))
    return replayed, groups, commits


def _digest(value: Any) -> str:
    return sha256(_encode(value).encode("utf-8")).hexdigest()


def _equal(left: Any, right: Any) -> bool:
    return left == right


def _schema_contracts(schema: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    return {row["kind"]: row for row in schema["kinds"]}


def _validate_receipt(receipt: Any, *, revision: int, transition_ids: set[str], writes: list[dict[str, Any]], external_reads: set[str], available: Mapping[str, Mapping[str, Any]]) -> str:
    row = _record(receipt, "accepted receipt")
    expected = {"_tag", "contractVersion", "transitionId", "schemaVersion", "previousStateRevision", "nextStateRevision", "readSet", "writeSet", "traceRef", "guard", "actorClaim", "authorizationRef", "scope", "decidedAt", "decision", "provenanceSha256"}
    if set(row) != expected or row.get("_tag") != "CanonicalAtomV2EffectReceipt" or row.get("contractVersion") != "hswm-canonical-effect-receipt/v2" or row.get("schemaVersion") != SCHEMA_VERSION or row.get("previousStateRevision") != revision - 1 or row.get("nextStateRevision") != revision or row.get("decision") != "ACCEPTED" or row.get("traceRef") is not None:
        _refuse("JOURNAL_RECEIPT_INVALID", "accepted receipt fixed fields")
    transition = row.get("transitionId")
    if transition != f"fixture-transition-{revision:03d}" or transition in transition_ids:
        _refuse("JOURNAL_RECEIPT_INVALID", "transition must be exact and unique")
    reads = row.get("readSet")
    if type(reads) is not list or not all(type(value) is dict for value in reads):
        _refuse("JOURNAL_RECEIPT_INVALID", "fixture receipt read/authority fields")
    if row.get("actorClaim") != "fixture-actor" or row.get("authorizationRef") != "fixture-authorization" or row.get("scope") != "fixture-byte-closure" or row.get("decidedAt") != "2026-08-28T00:00:00.000Z" or row.get("provenanceSha256") != _digest({"transitionId": transition, "fixtureClass": FIXTURE_CLASS}):
        _refuse("JOURNAL_RECEIPT_INVALID", "fixture receipt authority/provenance identity")
    guard = row.get("guard")
    if guard != {"schema": "PASSED", "ownerTotality": "PASSED", "references": "PASSED", "revision": "PASSED", "permission": "REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT"}:
        _refuse("JOURNAL_RECEIPT_INVALID", "guard is not exact")
    write_ids = [_key_id(item["key"]) for item in writes]
    receipt_write_ids = [_key_id(value) for value in row.get("writeSet", [])] if type(row.get("writeSet")) is list and all(type(value) is dict for value in row["writeSet"]) else []
    read_ids = [_key_id(value) for value in reads]
    if receipt_write_ids != write_ids:
        _refuse("JOURNAL_RECEIPT_INVALID", "writeSet differs from sorted write bindings")
    if read_ids != sorted(read_ids) or len(set(read_ids)) != len(read_ids) or set(read_ids) != external_reads or any(key not in available for key in read_ids):
        _refuse("JOURNAL_RECEIPT_INVALID", "readSet must be the exact sorted external dependency closure")
    return transition


def _validate_atom_against_schema(
    atom: Mapping[str, Any],
    *,
    contracts: Mapping[str, Mapping[str, Any]],
    available: Mapping[str, Mapping[str, Any]],
    batch: Mapping[str, Mapping[str, Any]],
    bootstrap_allowed: bool,
) -> tuple[set[str], set[str]]:
    keyid = _key_id(atom.get("key")); kind = atom.get("kind")
    contract = contracts.get(kind) if type(kind) is str else None
    if contract is None or atom.get("responsibilityOwner") not in contract.get("allowedOwners", []):
        _refuse("JOURNAL_ATOM_SCHEMA_INVALID", keyid)
    refs = atom.get("references")
    if type(refs) is not list: _refuse("JOURNAL_ATOM_REFERENCE_INVALID", keyid)
    role_contracts = {role["role"]: role for group in contract.get("referenceContracts", []) for role in group.get("roles", [])}
    counts: dict[str, int] = {role: 0 for role in role_contracts}
    external: set[str] = set(); same_batch: set[str] = set()
    seen_role_targets: set[tuple[str, str]] = set()
    for value in refs:
        ref = _record(value, "journal atom reference"); role = ref.get("role")
        if set(ref) != {"referenceType", "role", "target"}:
            _refuse("JOURNAL_ATOM_REFERENCE_INVALID", f"{keyid} reference exact fields")
        target_id = _key_id(ref.get("target")); target = available.get(target_id) or batch.get(target_id)
        spec = role_contracts.get(role) if type(role) is str else None
        if ref.get("referenceType") != "hswm:dnrd5:v2:reference" or spec is None or target is None or target.get("kind") not in spec.get("targetKinds", []):
            _refuse("JOURNAL_ATOM_REFERENCE_INVALID", keyid)
        pair = (role, target_id)
        if pair in seen_role_targets:
            _refuse("JOURNAL_ATOM_REFERENCE_INVALID", f"{keyid} repeats one target under one role")
        seen_role_targets.add(pair)
        counts[role] += 1
        (same_batch if target_id in batch else external).add(target_id)
    if any(counts[role] < spec["minimum"] or counts[role] > spec["maximum"] for role, spec in role_contracts.items()):
        _refuse("JOURNAL_ATOM_REFERENCE_INVALID", keyid)
    provenance = _record(atom.get("provenance"), "atom provenance")
    if set(provenance) != {"mode", "evidenceSha256", "sourceRef"}:
        _refuse("JOURNAL_PROVENANCE_INVALID", keyid)
    if provenance.get("evidenceSha256") != _descriptor(atom.get("content"), "atom content")["sha256"]:
        _refuse("JOURNAL_PROVENANCE_INVALID", keyid)
    source = provenance.get("sourceRef")
    if provenance.get("mode") == "BOOTSTRAP":
        if not bootstrap_allowed or source is not None:
            _refuse("JOURNAL_PROVENANCE_INVALID", keyid)
    elif provenance.get("mode") == "DERIVATION":
        if bootstrap_allowed:
            _refuse("JOURNAL_PROVENANCE_INVALID", "first fixture atom must be the sole bootstrap")
        source_id = _key_id(source)
        if source_id not in available and source_id not in batch:
            _refuse("JOURNAL_PROVENANCE_INVALID", keyid)
        (same_batch if source_id in batch else external).add(source_id)
    else:
        _refuse("JOURNAL_PROVENANCE_INVALID", keyid)
    return external, same_batch


def _replay_exact_journal(
    genesis: Mapping[str, Any],
    commits: list[Mapping[str, Any]],
    schema: Mapping[str, Any],
    blobs: Mapping[tuple[str, int, str], bytes],
    core_schema_descriptor: Any,
) -> tuple[dict[str, Mapping[str, Any]], list[tuple[str, ...]]]:
    genesis_fields = {"_tag", "contractVersion", "encoding", "journalLineageId", "schema", "stateRevision", "bootstrapClosed", "predecessor", "resultingStateSha256"}
    pinned_schema = _descriptor(core_schema_descriptor, "core schema descriptor")
    schema_binding = {"schemaVersion": SCHEMA_VERSION, "content": pinned_schema}
    if set(genesis) != genesis_fields or genesis.get("_tag") != "CanonicalAtomV2StateJournalGenesis" or genesis.get("contractVersion") != "hswm-canonical-atom-v2-state-journal/v1" or genesis.get("encoding") != CANONICAL_JSON_VERSION or genesis.get("journalLineageId") != "dnrd5-fixture-journal-0001" or genesis.get("stateRevision") != 0 or genesis.get("bootstrapClosed") is not False or genesis.get("predecessor") is not None or genesis.get("schema") != schema_binding:
        _refuse("JOURNAL_GENESIS_INVALID", "exact genesis binding/fields")
    state: dict[str, Any] = {"schemaVersion": SCHEMA_VERSION, "revision": 0, "bootstrapClosed": False, "atoms": [], "acceptedTransitionIds": []}
    if genesis.get("resultingStateSha256") != _digest(state): _refuse("JOURNAL_GENESIS_INVALID", "genesis state digest")
    contracts = _schema_contracts(schema); available: dict[str, Mapping[str, Any]] = {}; transition_ids: set[str] = set(); previous_raw = _encode(genesis).encode("utf-8")
    previous_desc = {"mediaType": JOURNAL_MEDIA, "byteLength": len(previous_raw), "sha256": sha256(previous_raw).hexdigest()}
    groups: list[tuple[str, ...]] = []
    for revision, record in enumerate(commits, 1):
        if record.get("_tag") != "CanonicalAtomV2StateJournalCommit" or record.get("contractVersion") != "hswm-canonical-atom-v2-state-journal/v1" or record.get("encoding") != CANONICAL_JSON_VERSION or record.get("journalLineageId") != genesis["journalLineageId"] or record.get("stateRevision") != revision or record.get("schema") != schema_binding or record.get("predecessor") != previous_desc or record.get("previousStateSha256") != _digest(state) or record.get("durability") != "LOCAL_PREDECESSOR_BOUND_JOURNAL_V1_NOT_CANONICAL_PERMIT_NOT_LEARNING":
            _refuse("JOURNAL_PREDECESSOR_INVALID", f"commit {revision}")
        bindings = record.get("writeBindings")
        if type(bindings) is not list or not 1 <= len(bindings) <= 64: _refuse("JOURNAL_WRITE_BINDING_INVALID", f"commit {revision}")
        ids = [_key_id(_record(row, "write binding").get("key")) for row in bindings]
        if ids != sorted(ids) or len(set(ids)) != len(ids) or any(key in available for key in ids): _refuse("JOURNAL_WRITE_BINDING_INVALID", f"commit {revision}")
        batch: dict[str, Mapping[str, Any]] = {}
        for binding, keyid in zip(bindings, ids):
            bind = _record(binding, "write binding")
            if set(bind) != {"key", "payload", "envelope"}:
                _refuse("JOURNAL_WRITE_BINDING_INVALID", f"commit {revision} binding exact fields")
            payload_desc = _descriptor(bind.get("payload"), "journal payload descriptor")
            envelope_desc = _descriptor(bind.get("envelope"), "journal envelope descriptor")
            if envelope_desc["mediaType"] != ATOM_MEDIA or payload_desc["mediaType"] not in {FIXTURE_JSON_MEDIA, RECEIPT_MEDIA}:
                _refuse("JOURNAL_WRITE_BINDING_INVALID", f"commit {revision} binding media type")
            envelope_raw = _blob(blobs, bind.get("envelope"), "journal envelope")
            atom = _record(_parse(envelope_raw, "journal envelope"), "journal envelope")
            if _key_id(atom.get("key")) != keyid or atom.get("content") != bind.get("payload"):
                _refuse("JOURNAL_WRITE_BINDING_INVALID", f"commit {revision}")
            _blob(blobs, bind.get("payload"), "journal payload")
            batch[keyid] = atom
        if revision == 1:
            if len(batch) != 1 or next(iter(batch.values())).get("kind") != "hswm:dnrd5:v2:study_randomness":
                _refuse("JOURNAL_PROVENANCE_INVALID", "first commit must contain only study_randomness")
        external_reads: set[str] = set(); edges: dict[str, set[str]] = {key: set() for key in batch}
        for keyid, atom in batch.items():
            external, same_batch = _validate_atom_against_schema(
                atom,
                contracts=contracts,
                available=available,
                batch=batch,
                bootstrap_allowed=revision == 1,
            )
            external_reads.update(external); edges[keyid].update(same_batch)
        # A batch can bind same-batch references, but cannot use them to hide a
        # cyclic provenance/reference dependency from the receipt read set.
        visiting: set[str] = set(); visited: set[str] = set()
        def visit(key: str) -> None:
            if key in visiting: _refuse("JOURNAL_SAME_BATCH_CYCLE", key)
            if key not in visited:
                visiting.add(key)
                for dependency in edges[key]: visit(dependency)
                visiting.remove(key); visited.add(key)
        for key in edges: visit(key)
        transition = _validate_receipt(record.get("receipt"), revision=revision, transition_ids=transition_ids, writes=bindings, external_reads=external_reads, available=available)
        transition_ids.add(transition)
        state = {"schemaVersion": SCHEMA_VERSION, "revision": revision, "bootstrapClosed": True, "atoms": sorted([*state["atoms"], *batch.values()], key=lambda x: _key_id(x["key"])), "acceptedTransitionIds": [*state["acceptedTransitionIds"], transition]}
        if record.get("resultingStateSha256") != _digest(state): _refuse("JOURNAL_STATE_REPLAY_INVALID", f"commit {revision}")
        available.update(batch); groups.append(tuple(sorted(atom["kind"].removeprefix("hswm:dnrd5:v2:") for atom in batch.values())))
        raw = _encode(record).encode("utf-8"); previous_desc = {"mediaType": JOURNAL_MEDIA, "byteLength": len(raw), "sha256": sha256(raw).hexdigest()}
    _validate_grouped_effect_closure(groups)
    return available, groups


def _validate_atom_journal_closure(core_atoms: Mapping[str, Mapping[str, Any]], replayed: Mapping[str, Mapping[str, Any]]) -> None:
    if set(core_atoms) != set(replayed):
        _refuse("ATOM_JOURNAL_CLOSURE_INVALID", "core atom keys differ from replayed journal keys")
    for key in core_atoms:
        if core_atoms[key] != replayed[key]:
            _refuse("ATOM_JOURNAL_CLOSURE_INVALID", f"core envelope differs from journal: {key}")


def _validate_grouped_effect_closure(groups: list[tuple[str, ...]]) -> None:
    admit = ("capability_consumption", "macro_disposition")
    revision_receipt = ("evidence_seal_consumption", "revision_transition_receipt")
    restore = ("capability_consumption", "restore_transaction")
    rollback_receipt = ("evidence_seal_consumption", "rollback_transition_receipt")
    audit = ("audit_release", "evidence_seal_consumption")
    terminal = ("block_evidence_manifest", "block_seal")
    expected = [admit, revision_receipt, admit, revision_receipt, admit, revision_receipt, restore, rollback_receipt, audit, terminal]
    special = {admit, revision_receipt, restore, rollback_receipt, audit, terminal}
    positions = [(index, group) for index, group in enumerate(groups) if group in special]
    if [group for _, group in positions] != expected:
        _refuse("JOURNAL_EFFECT_CLOSURE_INVALID", "special effect/receipt sequence is not exact")
    for left, right in ((0, 1), (2, 3), (4, 5), (6, 7)):
        if positions[right][0] != positions[left][0] + 1:
            _refuse("JOURNAL_EFFECT_CLOSURE_INVALID", "effect receipt is not the immediate next commit")
    if positions[-2][0] != len(groups) - 2 or positions[-1][0] != len(groups) - 1:
        _refuse("JOURNAL_EFFECT_CLOSURE_INVALID", "audit and terminal must be the final two commits")


def _validate_exact_counts(
    core: Mapping[str, Any],
    groups: list[tuple[str, ...]],
    provider_counts: Mapping[str, int],
) -> None:
    expected = {
        "admitMainEffects": groups.count(("capability_consumption", "macro_disposition")),
        "restoreMainEffects": groups.count(("capability_consumption", "restore_transaction")),
        "revisionReceiptSeals": groups.count(("evidence_seal_consumption", "revision_transition_receipt")),
        "rollbackReceiptSeals": groups.count(("evidence_seal_consumption", "rollback_transition_receipt")),
        "auditReleases": groups.count(("audit_release", "evidence_seal_consumption")),
        "terminalSeals": groups.count(("block_evidence_manifest", "block_seal")),
        **provider_counts,
    }
    if core.get("exactCounts") != expected:
        _refuse("EXACT_COUNTS_INVALID", "declared counters differ from observed journal/provider bytes")


def _validate_canonical_journal_schedule(
    core: Mapping[str, Any],
    atoms: Mapping[str, Mapping[str, Any]],
    commits: list[dict[str, Any]],
) -> None:
    """Bind actual admission time to the frozen lifecycle/arm chronology.

    Dependency-valid alternative schedules are not interchangeable evidence:
    commitments precede W0/forks, and ACTIVE, SHAM, EXACT, rollback, audit, and
    terminal groups have one canonical temporal order.  This rederives the
    schedule from atom bytes and core source order without importing producer
    code or accepting a caller-supplied ordering projection.
    """
    by_kind: dict[str, list[str]] = {}
    core_order: list[str] = []
    for listing in core["atoms"]:
        keyid = _key_id(listing["key"]); core_order.append(keyid)
        by_kind.setdefault(listing["kind"], []).append(keyid)
    special_groups: list[tuple[str, ...]] = []
    for index in range(3):
        special_groups.append((by_kind["capability_consumption"][index], by_kind["macro_disposition"][index]))
        special_groups.append((by_kind["evidence_seal_consumption"][index], by_kind["revision_transition_receipt"][index]))
    special_groups.extend((
        (by_kind["capability_consumption"][3], by_kind["restore_transaction"][0]),
        (by_kind["evidence_seal_consumption"][3], by_kind["rollback_transition_receipt"][0]),
        (by_kind["evidence_seal_consumption"][4], by_kind["audit_release"][0]),
        (by_kind["block_evidence_manifest"][0], by_kind["block_seal"][0]),
    ))
    special_ids = {key for group in special_groups for key in group}
    units: list[tuple[str, ...]] = [(key,) for key in core_order if key not in special_ids] + special_groups
    unit_by_key = {key: index for index, unit in enumerate(units) for key in unit}
    dependencies: dict[int, set[int]] = {index: set() for index in range(len(units))}
    for index, unit in enumerate(units):
        for key in unit:
            atom = atoms[key]
            targets = [_key_id(ref["target"]) for ref in atom["references"]]
            source = atom["provenance"]["sourceRef"]
            if source is not None: targets.append(_key_id(source))
            for target in targets:
                owner = unit_by_key.get(target)
                if owner is None: _refuse("JOURNAL_CHRONOLOGY_INVALID", "dependency is outside atom closure")
                if owner != index: dependencies[index].add(owner)
    special_unit_order = list(range(len(units) - len(special_groups), len(units)))
    next_special = 0; remaining = set(range(len(units))); expected: list[tuple[str, ...]] = []
    while remaining:
        ready = [index for index in sorted(remaining) if dependencies[index].isdisjoint(remaining)]
        if not ready: _refuse("JOURNAL_CHRONOLOGY_INVALID", "canonical unit graph is cyclic")
        wanted = special_unit_order[next_special] if next_special < len(special_unit_order) else None
        chosen = wanted if wanted in ready else next((index for index in ready if index not in special_unit_order), ready[0])
        expected.append(tuple(sorted(units[chosen]))); remaining.remove(chosen)
        if chosen == wanted: next_special += 1
    observed = [tuple(_key_id(binding["key"]) for binding in commit["writeBindings"]) for commit in commits]
    if observed != expected:
        _refuse("JOURNAL_CHRONOLOGY_INVALID", "journal differs from canonical lifecycle/arm schedule")


def _validate_receipt_and_terminal_contract(
    core: Mapping[str, Any],
    atoms: Mapping[str, Mapping[str, Any]],
    blobs: Mapping[tuple[str, int, str], bytes],
    commits: list[dict[str, Any]],
) -> None:
    """A generic fixture payload can never stand in for a v2 transition seal."""
    receipt_kinds = {"hswm:dnrd5:v2:revision_transition_receipt": "REVISION", "hswm:dnrd5:v2:rollback_transition_receipt": "ROLLBACK"}
    required = {"contractVersion", "receiptKind", "precedingEffectRecordDescriptorSha256", "postcommitReceiptIdentity", "decisionAtomKeyId", "effectConsumptionAtomKeyId", "effectAtomKeyId"}
    commit_for_key: dict[str, tuple[int, Mapping[str, Any]]] = {}
    journal = core.get("journal")
    if type(journal) is not list: _refuse("RECEIPT_SEAL_INVALID", "journal missing")
    for index, listing in enumerate(journal[1:], 1):
        record = _record(_parse(_blob(blobs, _record(listing, "journal listing").get("record"), "journal commit"), "journal commit"), "journal commit")
        for binding in record.get("writeBindings", []):
            keyid = _key_id(_record(binding, "write binding").get("key"))
            if keyid in commit_for_key: _refuse("RECEIPT_SEAL_INVALID", "atom appears in multiple commits")
            commit_for_key[keyid] = (index, listing)
    receipt_atoms = [atom for atom in atoms.values() if atom.get("kind") in receipt_kinds]
    if len(receipt_atoms) != 4:
        _refuse("RECEIPT_SEAL_INVALID", "requires exactly three revision and one rollback receipt")
    identities: set[str] = set(); receipt_positions: list[int] = []
    def batch_by_kind(record: Mapping[str, Any]) -> dict[str, str]:
        result: dict[str, str] = {}
        for binding in record.get("writeBindings", []):
            keyid = _key_id(_record(binding, "write binding").get("key"))
            atom = atoms.get(keyid)
            if atom is None: _refuse("RECEIPT_SEAL_INVALID", "commit writes an unknown atom")
            kind = str(atom.get("kind", "")).removeprefix("hswm:dnrd5:v2:")
            if kind in result: _refuse("RECEIPT_SEAL_INVALID", "effect batch repeats one kind")
            result[kind] = keyid
        return result
    def one_ref(atom: Mapping[str, Any], role: str) -> str:
        values = [_key_id(ref.get("target")) for ref in atom.get("references", []) if type(ref) is dict and ref.get("role") == f"role:dnrd5:v2:{role}"]
        if len(values) != 1: _refuse("RECEIPT_SEAL_INVALID", f"requires one {role}")
        return values[0]
    for atom in receipt_atoms:
        wanted = receipt_kinds.get(atom.get("kind"))
        if _descriptor(atom.get("content"), "transition receipt payload").get("mediaType") != RECEIPT_MEDIA:
            _refuse("RECEIPT_SEAL_INVALID", "transition receipt media type")
        content = _record(_parse(_blob(blobs, atom.get("content"), "transition receipt payload"), "transition receipt payload"), "transition receipt payload")
        if set(content) != required or content.get("contractVersion") != "hswm-dnrd5-v2-receipt-seal/v1" or content.get("receiptKind") != wanted or not all(type(content.get(name)) is str and content[name] for name in required - {"contractVersion", "receiptKind"}):
            _refuse("RECEIPT_SEAL_INVALID", "transition receipt lacks exact postcommit identity payload")
        key = _key_id(atom["key"]); position, _ = commit_for_key.get(key, (0, {}))
        if position < 2: _refuse("RECEIPT_SEAL_INVALID", "receipt has no preceding effect record")
        receipt_positions.append(position)
        previous_record = commits[position - 2]; current_record = commits[position - 1]
        previous_desc = _record(journal[position - 1], "previous journal listing").get("record")
        previous_sha = _descriptor(previous_desc, "preceding effect record") ["sha256"]
        decision = one_ref(atom, "decision"); consumption = one_ref(atom, "effect-consumption")
        effect = one_ref(atom, "successor" if wanted == "REVISION" else "restore")
        evidence = one_ref(atom, "evidence-consumption")
        if not all((decision, consumption, effect)) or content["precedingEffectRecordDescriptorSha256"] != previous_sha or content["decisionAtomKeyId"] != decision or content["effectConsumptionAtomKeyId"] != consumption or content["effectAtomKeyId"] != effect:
            _refuse("RECEIPT_SEAL_INVALID", "receipt tuple does not bind its immediate effect")
        previous_batch = batch_by_kind(previous_record); current_batch = batch_by_kind(current_record)
        expected_effect_kind = "macro_disposition" if wanted == "REVISION" else "restore_transaction"
        expected_receipt_kind = "revision_transition_receipt" if wanted == "REVISION" else "rollback_transition_receipt"
        if set(previous_batch) != {"capability_consumption", expected_effect_kind} or previous_batch["capability_consumption"] != consumption or previous_batch[expected_effect_kind] != effect:
            _refuse("RECEIPT_SEAL_INVALID", "preceding commit is not the exact bound main effect pair")
        if set(current_batch) != {"evidence_seal_consumption", expected_receipt_kind} or current_batch[expected_receipt_kind] != key or current_batch["evidence_seal_consumption"] != evidence:
            _refuse("RECEIPT_SEAL_INVALID", "receipt commit is not the exact bound evidence/receipt pair")
        evidence_atom = atoms[evidence]; decision_atom = atoms[decision]
        if one_ref(evidence_atom, "purpose") != decision:
            _refuse("RECEIPT_SEAL_INVALID", "receipt evidence purpose differs from decision")
        for authority_role in ("grant", "capability", "revocation"):
            if one_ref(evidence_atom, authority_role) != one_ref(decision_atom, authority_role):
                _refuse("RECEIPT_SEAL_INVALID", f"receipt evidence {authority_role} differs from decision")
        identity = _digest({"contractVersion":"hswm-dnrd5-v2-postcommit-receipt-identity/v1", "effectRecordDescriptorSha256":previous_sha, "journalLineageId":previous_record.get("journalLineageId"), "transitionId":_record(previous_record.get("receipt"), "effect receipt").get("transitionId"), "decisionAtomKeyId":decision, "effectConsumptionAtomKeyId":consumption, "effectAtomKeyId":effect})
        if content["postcommitReceiptIdentity"] != identity:
            _refuse("RECEIPT_SEAL_INVALID", "postcommit receipt identity mismatch")
        if atom["key"].get("atomUid") != f"receipt:{identity}":
            _refuse("RECEIPT_SEAL_INVALID", "receipt UID is not identity-bound")
        if identity in identities: _refuse("RECEIPT_SEAL_INVALID", "postcommit identity is not unique")
        identities.add(identity)
    if receipt_positions != sorted(receipt_positions) or len(set(receipt_positions)) != 4:
        _refuse("RECEIPT_SEAL_INVALID", "receipt chronology must be ACTIVE, SHAM, EXACT, then rollback")
    audit_atoms = [atom for atom in atoms.values() if atom.get("kind") == "hswm:dnrd5:v2:audit_release"]
    if len(audit_atoms) != 1 or len(commits) < 2:
        _refuse("AUDIT_SEAL_INVALID", "requires one penultimate audit release")
    audit_atom = audit_atoms[0]; audit_key = _key_id(audit_atom["key"])
    audit_evidence = one_ref(audit_atom, "evidence-consumption")
    audit_batch = batch_by_kind(commits[-2])
    if set(audit_batch) != {"audit_release", "evidence_seal_consumption"} or audit_batch["audit_release"] != audit_key or audit_batch["evidence_seal_consumption"] != audit_evidence:
        _refuse("AUDIT_SEAL_INVALID", "penultimate batch is not the audit-bound evidence/release pair")
    audit_capability = one_ref(audit_atom, "release-capability")
    audit_evidence_atom = atoms[audit_evidence]
    if one_ref(audit_evidence_atom, "purpose") != audit_capability:
        _refuse("AUDIT_SEAL_INVALID", "audit evidence purpose differs from release capability")
    manifests = [atom for atom in atoms.values() if atom.get("kind") == "hswm:dnrd5:v2:block_evidence_manifest"]
    seals = [atom for atom in atoms.values() if atom.get("kind") == "hswm:dnrd5:v2:block_seal"]
    if len(manifests) != 1 or len(seals) != 1:
        _refuse("TERMINAL_CLOSURE_INVALID", "requires one terminal manifest and seal")
    manifest_atom = manifests[0]
    if _descriptor(manifest_atom.get("content"), "block manifest payload")["mediaType"] != FIXTURE_JSON_MEDIA or _descriptor(seals[0].get("content"), "block seal payload")["mediaType"] != FIXTURE_JSON_MEDIA:
        _refuse("TERMINAL_CLOSURE_INVALID", "terminal payload media type")
    manifest_payload = _record(_parse(_blob(blobs, manifest_atom.get("content"), "block manifest"), "block manifest"), "block manifest")
    preterminal = [row for row in core.get("atoms", []) if row.get("kind") not in {"block_evidence_manifest", "block_seal"}]
    roles = [{"callId": call["callId"], "role": role, "descriptor": call["contents"][role]} for call in core["calls"] for role in ROLES]
    expected_manifest = {"_tag":"Dnrd5FixtureBlockEvidenceManifestPayload", "contractVersion":"hswm-dnrd5-fixture-block-evidence-manifest/v1", "fixtureClass":FIXTURE_CLASS, "closureClass":"PRETERMINAL_EXACT_SET_NOT_PROVIDER_OCCURRENCE_OR_SCIENTIFIC_RESULT", "atomListings":[{"key":row["key"],"kind":row["kind"],"payload":row["payload"],"envelope":row["envelope"]} for row in preterminal], "atomPayloadDescriptors":[row["payload"] for row in preterminal], "atomEnvelopeDescriptors":[row["envelope"] for row in preterminal], "journalRecordDescriptors":[row["record"] for row in core["journal"][:-1]], "providerReceipts":[call["receipt"] for call in core["calls"]], "callRoleBindings":roles, "ledgerDescriptors":[row["record"] for row in core["fixtureLedger"]], "schemaDescriptor":core["schema"], "lifecycleDescriptor":core["lifecycle"], "alignmentDescriptor":core["alignment"], "evidenceBindings":core["evidenceBindings"]}
    if manifest_payload != expected_manifest:
        _refuse("TERMINAL_CLOSURE_INVALID", "block manifest is not the exact preterminal closure")
    terminal_batch = batch_by_kind(commits[-1])
    manifest_key = _key_id(manifest_atom["key"]); seal_key = _key_id(seals[0]["key"])
    if set(terminal_batch) != {"block_evidence_manifest", "block_seal"} or terminal_batch["block_evidence_manifest"] != manifest_key or terminal_batch["block_seal"] != seal_key:
        _refuse("TERMINAL_CLOSURE_INVALID", "manifest/seal must be the exact final commit")
    seal = _record(_parse(_blob(blobs, seals[0].get("content"), "block seal"), "block seal"), "block seal")
    if set(seal) != {"_tag", "contractVersion", "fixtureClass", "terminal", "claimBoundary", "preterminalJournalHead", "blockEvidenceManifestPayload", "blockEvidenceManifestEnvelope"} or seal.get("_tag") != "Dnrd5FixtureBlockSealPayload" or seal.get("contractVersion") != "hswm-dnrd5-fixture-block-seal/v1" or seal.get("fixtureClass") != FIXTURE_CLASS or seal.get("claimBoundary") != "NOT_SOURCE_BUILD_IMPORT_PERMIT_PROVIDER_OCCURRENCE_OR_SCIENTIFIC_RESULT" or seal.get("terminal") != TERMINAL or seal.get("preterminalJournalHead") != core["journal"][-2]["record"] or seal.get("blockEvidenceManifestPayload") != manifest_atom["content"] or seal.get("blockEvidenceManifestEnvelope") != next(row["envelope"] for row in core["atoms"] if _key_id(row["key"]) == _key_id(manifest_atom["key"])):
        _refuse("TERMINAL_CLOSURE_INVALID", "block seal grammar")


def judge_actual_byte_corpus(root: Path) -> ActualByteJudgeResult:
    """Independently validate a bounded deterministic byte-closure fixture."""
    if not isinstance(root, Path): _refuse("ROOT_INVALID", "root must be Path")
    manifest, core, blobs = _validate_root(root)
    _validate_reachable_descriptor_closure(manifest, core, blobs)
    schema = _validate_schema(core, blobs)
    atoms = _validate_atoms(core, blobs, schema)
    logical_bindings, provider_counts = _validate_provider(core, blobs)
    _validate_evidence_bindings(core, blobs)
    _validate_lifecycle(core, blobs, atoms)
    _validate_semantic_joins(atoms, blobs)
    replayed, groups, commits = _validate_journal_wire_first(core, blobs, schema)
    _validate_atom_journal_closure(atoms, replayed)
    _validate_canonical_journal_schedule(core, atoms, commits)
    _validate_exact_counts(core, groups, provider_counts)
    _validate_receipt_and_terminal_contract(core, atoms, blobs, commits)
    return ActualByteJudgeResult(TERMINAL, sha256((root / "manifest.json").read_bytes()).hexdigest(), len(blobs), logical_bindings)
