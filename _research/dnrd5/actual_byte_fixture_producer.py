"""Deterministically construct the DNRD-5 one-block actual-byte corpus.

The artifact is deliberately a fixture: all responses are local fixed bytes and
the resulting terminal is expressly not a provider occurrence or a result.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import shutil
import tempfile
from typing import Any

from _research.dnrd5.actual_byte_corpus_contract import *
from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256, parse_canonical
from _research.dnrd5.lifecycle_contract import build_synthetic_lifecycle_vector


def _raw(obj: Any) -> bytes: return canonical_bytes(obj)
def _key(uid: str) -> dict[str, Any]: return {"schemaVersion": SCHEMA_VERSION, "lineageId": "dnrd5-fixture-block-0001", "atomUid": uid, "revisionId": 0}
def _ref(key: dict[str, str], role: str) -> dict[str, Any]: return {"referenceType": "hswm:dnrd5:v2:reference", "role": f"role:dnrd5:v2:{role}", "target": key}

# This table is intentionally a subset-free fixture atom plan: it covers each
# lifecycle row with an atom and explicitly names the v2 support kinds.
_ATOM_PLAN = (
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
).split()

def _schema_raw(repo: Path) -> bytes:
    # The TypeScript source is not used as an oracle.  The checked-in vector
    # contains the exact canonical schema bytes generated during fixture build.
    path = repo / "_research/dnrd5/vectors/dnrd5_v2_schema.json"
    if not path.exists():
        raise RuntimeError("schema.json is required; generate it with the documented local build helper")
    raw = path.read_bytes()
    if len(raw) != SCHEMA_BYTE_LENGTH or sha256(raw).hexdigest() != SCHEMA_SHA256:
        raise RuntimeError("pinned v2 schema bytes are absent or drifted")
    parse_canonical(raw)
    return raw

def _put(blobs: dict[str, tuple[bytes, str]], raw: bytes, media: str) -> dict[str, Any]:
    desc = descriptor(raw, media); prior = blobs.get(desc["sha256"])
    if prior is not None and prior != (raw, media): raise RuntimeError("digest collision/media ambiguity")
    blobs[desc["sha256"]] = (raw, media)
    return desc

def _blob_bytes(blobs: dict[str, tuple[bytes, str]], desc: dict[str, Any]) -> bytes:
    raw, media = blobs[desc["sha256"]]
    if media != desc["mediaType"] or len(raw) != desc["byteLength"]:
        raise RuntimeError("producer descriptor/blob mismatch")
    return raw

def _refresh_atom_envelope(blobs: dict[str, tuple[bytes, str]], atom: dict[str, Any], *, payload: dict[str, Any] | None = None, media_type: str | None = None) -> None:
    """Rebind one uncommitted atom's raw payload and exact envelope."""
    old_envelope=atom["envelope"]
    env=parse_canonical(_blob_bytes(blobs,old_envelope))
    if payload is not None:
        old_payload=atom["payload"]
        del blobs[old_payload["sha256"]]
        atom["payload"]=_put(blobs,_raw(payload),media_type or JSON_MEDIA_TYPE)
    env["key"]=atom["key"]
    env["content"]=atom["payload"]
    env["provenance"]["evidenceSha256"]=atom["payload"]["sha256"]
    del blobs[old_envelope["sha256"]]
    atom["envelope"]=_put(blobs,_raw(env),ATOM_MEDIA_TYPE)

def _replace_uncommitted_key(
    blobs: dict[str, tuple[bytes, str]], atoms: list[dict[str, Any]], old_key: dict[str, Any], new_key: dict[str, Any], committed: set[str],
) -> None:
    """Patch later envelope references after late-binding a receipt UID."""
    old_id=atom_key_id(old_key)
    for atom in atoms:
        if atom_key_id(atom["key"]) in committed: continue
        env=parse_canonical(_blob_bytes(blobs,atom["envelope"]))
        changed=False
        if atom_key_id(env["key"]) == old_id:
            atom["key"] = new_key; env["key"] = new_key; changed=True
        for ref in env["references"]:
            if atom_key_id(ref["target"]) == old_id: ref["target"] = new_key; changed=True
        source=env["provenance"]["sourceRef"]
        if source is not None and atom_key_id(source) == old_id:
            env["provenance"]["sourceRef"] = new_key; changed=True
        if changed:
            old_descriptor=atom["envelope"]; del blobs[old_descriptor["sha256"]]
            atom["envelope"]=_put(blobs,_raw(env),ATOM_MEDIA_TYPE)

def _descriptor_list(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(value) for value in values]

def build_fixture(repository_root: Path) -> tuple[dict[str, Any], dict[str, tuple[bytes, str]]]:
    blobs: dict[str, tuple[bytes, str]] = {}
    schema_raw = _schema_raw(repository_root)
    schema_desc = _put(blobs, schema_raw, "application/vnd.hswm.canonical-schema-v2+json")
    lifecycle_raw = _raw(build_synthetic_lifecycle_vector())
    if sha256(lifecycle_raw).hexdigest() != LIFECYCLE_SHA256: raise RuntimeError("pinned lifecycle drift")
    lifecycle_desc = _put(blobs, lifecycle_raw, JSON_MEDIA_TYPE)
    alignment_raw = (repository_root / "_research/dnrd5/vectors/lifecycle_atom_alignment_v1.json").read_bytes()
    if sha256(alignment_raw).hexdigest() != ALIGNMENT_SHA256: raise RuntimeError("pinned lifecycle alignment drift")
    alignment_desc = _put(blobs, alignment_raw, JSON_MEDIA_TYPE)
    # Every atom has a raw payload and a canonical envelope.  Payloads carry no
    # invented occurrence fact; provenance names the bounded fixture source.
    schema = parse_canonical(schema_raw)
    contracts = {entry["kind"].removeprefix("hswm:dnrd5:v2:"): entry for entry in schema["kinds"]}
    atoms=[]; by_kind: dict[str, list[dict[str, Any]]] = {}
    for ordinal, kind in enumerate(_ATOM_PLAN, 1):
        uid=f"{kind}-{ordinal:03d}"; key=_key(uid)
        arm_kinds={"fork_incidence","feedback_assignment","revision_proposal","candidate_validation","credit_decision","behavior_projection","probe_trajectory","probe_outcome"}
        arm = ARMS[len(by_kind.get(kind,[]))] if kind in arm_kinds else None
        payload_slot=len(by_kind.get(kind,[])) if arm is not None else None
        if kind in {"revision_admission_decision","macro_disposition","revision_transition_receipt"}:
            decision_index=len(by_kind.get(kind,[])); arm = ("ACTIVE","OUTCOME_INDEPENDENT_SHAM","EXACT_W0_ROLLBACK")[decision_index]
            payload_slot=(0,1,3)[decision_index]
        payload={"_tag":"Dnrd5FixtureAtomPayload","fixtureClass":FIXTURE_CLASS,"kind":kind,"ordinal":ordinal,"arm":arm,"slot":payload_slot}
        payload_desc=_put(blobs,_raw(payload),JSON_MEDIA_TYPE)
        contract = contracts[kind]
        references=[]
        for ref_contract in contract["referenceContracts"]:
            for role_contract in ref_contract["roles"]:
                target_kind = role_contract["targetKinds"][0].removeprefix("hswm:dnrd5:v2:")
                candidates = by_kind.get(target_kind, [])
                # The fixture plan is topologically ordered.  If that changes,
                # failing here is preferable to inventing a forward reference.
                if len(candidates) < role_contract["minimum"]:
                    raise RuntimeError(f"atom plan lacks prior {target_kind} for {kind}")
                for target in candidates[-role_contract["minimum"]:]:
                    references.append(_ref(target["key"], role_contract["role"].removeprefix("role:dnrd5:v2:")))
        # Provenance follows a declared typed source whenever one exists.  It
        # must not accidentally depend on the previous *textual* plan item,
        # because special same-CAS pairs are intentionally interleaved in that
        # plan but have their own transaction topology.
        source = references[0]["target"] if references else (atoms[-1]["key"] if atoms else None)
        atom={"_tag":"CanonicalAtomV2","contractVersion":"hswm-canonical-atom/v2","key":key,"kind":contract["kind"],"responsibilityOwner":contract["allowedOwners"][0],"content":payload_desc,"provenance":{"mode":"DERIVATION" if source else "BOOTSTRAP","evidenceSha256":payload_desc["sha256"],"sourceRef":source},"lifecycle":"ADMITTED","references":references}
        env_desc=_put(blobs,_raw(atom),ATOM_MEDIA_TYPE)
        atoms.append({"key":key,"kind":kind,"payload":payload_desc,"envelope":env_desc})
        by_kind.setdefault(kind, []).append(atoms[-1])
    # Replace the schema-valid but deliberately conservative construction above
    # with the one block's arm-indexed semantic wiring.  Each four-arm object
    # uses the same fork/index; hidden outcome owns release zero and fresh probes
    # use releases one through four.  This avoids the otherwise tempting
    # "last compatible atom" collapse.
    arm_index={atom_key_id(atom["key"]): index for kind, rows in by_kind.items() for index, atom in enumerate(rows)}
    def selected(kind: str, index: int) -> dict[str, Any]:
        rows=by_kind[kind]; return rows[min(index,len(rows)-1)]
    def refs_for(atom: dict[str, Any]) -> list[dict[str, Any]]:
        kind=atom["kind"]; index=arm_index[atom_key_id(atom["key"])]; contract=contracts[kind]; out=[]
        for family in contract["referenceContracts"]:
            for spec in family["roles"]:
                role=spec["role"].removeprefix("role:dnrd5:v2:"); target_kind=spec["targetKinds"][0].removeprefix("hswm:dnrd5:v2:")
                choices=[]
                if kind=="audit_release" and role in {"probe-trajectory","probe-outcome","evaluator-release"}: choices=[selected(target_kind,i+1 if role=="evaluator-release" else i) for i in range(4)]
                elif kind=="evaluator_release" and role=="trajectory": choices=[selected("trajectory_seal",0)] if index == 0 else [selected("probe_trajectory",index-1)]
                elif kind=="hidden_outcome" and role=="release": choices=[selected("evaluator_release",0)]
                elif kind=="probe_outcome" and role=="release": choices=[selected("evaluator_release",index+1)]
                elif kind=="probe_outcome" and role=="probe": choices=[selected("probe_commitment",index+1)]
                elif kind=="probe_trajectory" and role=="probe": choices=[selected("probe_commitment",index+1)]
                elif kind=="feedback_assignment" and role=="source": choices=[selected(("hidden_outcome","placebo_receipt","outcome_credit_escrow","hidden_outcome")[index],0)]
                elif kind=="credit_decision" and role=="credit-source": choices=[selected(("hidden_outcome","placebo_receipt","outcome_credit_escrow","hidden_outcome")[index],0)]
                elif kind=="rollback_decision" and role=="fork": choices=[selected("fork_incidence",3)]
                elif kind=="rollback_decision" and role in {"staging-successor","staging-receipt"}: choices=[selected("macro_disposition" if role=="staging-successor" else "revision_transition_receipt",3)]
                elif kind=="restore_transaction" and role in {"decision","consumption","staging-successor"}: choices=[selected({"decision":"rollback_decision","consumption":"capability_consumption","staging-successor":"macro_disposition"}[role],3)]
                elif kind=="rollback_transition_receipt" and role in {"decision","effect-consumption","restore","evidence-consumption"}: choices=[selected({"decision":"rollback_decision","effect-consumption":"capability_consumption","restore":"restore_transaction","evidence-consumption":"evidence_seal_consumption"}[role],3)]
                elif kind=="revision_admission_decision" and role in {"fork","proposal","validation","credit"}:
                    source_slot=(0,1,3)[index]
                    choices=[selected({"fork":"fork_incidence","proposal":"revision_proposal","validation":"candidate_validation","credit":"credit_decision"}[role],source_slot)]
                elif kind=="revision_transition_receipt" and role in {"decision","effect-consumption","successor","evidence-consumption"}:
                    slot=(0,1,3)[index]
                    choices=[selected({"decision":"revision_admission_decision","effect-consumption":"capability_consumption","successor":"macro_disposition","evidence-consumption":"evidence_seal_consumption"}[role], index if role != "decision" else index)]
                elif kind=="macro_disposition" and role in {"proposal","revision-admission-decision","effect-consumption"}:
                    slot=(0,1,3)[index]
                    choices=[selected({"proposal":"revision_proposal","revision-admission-decision":"revision_admission_decision","effect-consumption":"capability_consumption"}[role], slot if role=="proposal" else index)]
                elif kind=="capability_consumption" and role=="decision": choices=[selected("revision_admission_decision",index) if index < 3 else selected("rollback_decision",0)]
                elif kind=="evidence_seal_consumption" and role=="purpose": choices=[selected("revision_admission_decision",index) if index < 3 else selected("rollback_decision",0) if index == 3 else selected("audit_release_capability",0)]
                elif kind=="audit_release" and role=="evidence-consumption": choices=[selected("evidence_seal_consumption",4)]
                elif kind=="behavior_projection" and role=="source": choices=[selected("macro_disposition",index) if index<2 else selected("w0_snapshot",0) if index==2 else selected("restore_transaction",0)]
                else: choices=[selected(target_kind,index+i) for i in range(spec["minimum"])]
                for chosen in choices: out.append(_ref(chosen["key"],role))
        return out
    for ordinal, atom in enumerate(atoms):
        old=atom["envelope"]; env=parse_canonical(_blob_bytes(blobs,old)); refs=refs_for(atom)
        source=refs[0]["target"] if refs else (atoms[ordinal-1]["key"] if ordinal else None)
        env["references"]=refs; env["provenance"]={"mode":"DERIVATION" if source else "BOOTSTRAP","evidenceSha256":atom["payload"]["sha256"],"sourceRef":source}
        del blobs[old["sha256"]]
        atom["envelope"]=_put(blobs,_raw(env),ATOM_MEDIA_TYPE)
    # Canonical ledger material: distinct projection/transmitted request bytes
    # are crucial to this fixture and are independently indexed as raw roles.
    calls=[]
    for ordinal, call_class in enumerate(CALL_CLASSES, 1):
        call_id=f"fixture-call-{ordinal:02d}"; role_desc={}
        for role in ROLES:
            content={"_tag":"Dnrd5FixtureCallContent","fixtureClass":FIXTURE_CLASS,"callId":call_id,"callClass":call_class,"role":role,"ordinal":ordinal}
            if role == "request-projection": content["privateBinding"] = f"private-{ordinal:02d}"
            if role == "transmitted-request": content["wireOnly"] = f"wire-{ordinal:02d}"
            role_desc[role]=_put(blobs,_raw(content),JSON_MEDIA_TYPE)
        receipt={"_tag":"Dnrd5FixtureTransportReceipt","contractVersion":FIXTURE_TRANSPORT_VERSION,"fixtureClass":FIXTURE_CLASS,"callId":call_id,"callClass":call_class,"sessionId":f"session-{ordinal:02d}","workerId":f"worker-{ordinal:02d}","requestNonce":f"nonce-{ordinal:02d}","rngDescriptor":role_desc["rng"],"contents":role_desc,"terminal":"SUCCEEDED"}
        receipt_desc=_put(blobs,_raw(receipt),JSON_MEDIA_TYPE)
        calls.append({"callId":call_id,"callClass":call_class,"receipt":receipt_desc,"contents":role_desc})
    ledger=[]; predecessor=None
    for seq, call in enumerate(calls,1):
        for phase in ("START","SUCCEEDED"):
            item={"_tag":"Dnrd5FixtureLedgerRecord","contractVersion":FIXTURE_TRANSPORT_VERSION,"fixtureClass":FIXTURE_CLASS,"sequence":len(ledger)+1,"phase":phase,"callId":call["callId"],"callClass":call["callClass"],"receipt":call["receipt"],"predecessor":predecessor}
            desc=_put(blobs,_raw(item),JSON_MEDIA_TYPE); ledger.append({"record":desc,"phase":phase,"callId":call["callId"]}); predecessor=desc
    evidence_roles=("evaluator-input","evaluator-output","genuine-commitment","genuine-opening","placebo-commitment","placebo-opening","assignment-receipt","randomness-receipt","permit-input","permit-resolution","authorization","revocation","trusted-time-placeholder","source-tree","selected-build","allowed-import-graph","runtime","custody-isolation-statement")
    placeholder_roles={"trusted-time-placeholder","source-tree","selected-build","allowed-import-graph"}
    material_sources={
        "evaluator-input":[calls[0]["contents"]["model-input"]], "evaluator-output":[calls[0]["contents"]["observed-response"]],
        "genuine-commitment":[by_kind["evaluator_commitment"][0]["payload"]], "genuine-opening":[by_kind["evaluator_release"][0]["payload"]],
        "placebo-commitment":[by_kind["placebo_commitment"][0]["payload"]], "placebo-opening":[by_kind["placebo_receipt"][0]["payload"]],
        "assignment-receipt":[by_kind["block_assignment"][0]["payload"]], "randomness-receipt":[by_kind["study_randomness"][0]["payload"]],
        "permit-input":[by_kind["permit_policy"][0]["payload"]], "permit-resolution":[by_kind["capability_issuance"][0]["payload"]],
        "authorization":[by_kind["authorization_decision"][0]["payload"]], "revocation":[by_kind["revocation_status"][0]["payload"]],
        "runtime":[calls[0]["contents"]["runtime-identity"]], "custody-isolation-statement":[calls[0]["contents"]["isolation-statement"]],
    }
    evidence_bindings={}
    for role in evidence_roles:
        evidence_class="DECLARED_PLACEHOLDER_NOT_AUTHENTICATED_EVIDENCE" if role in placeholder_roles else "DETERMINISTIC_FIXTURE_MATERIAL_NOT_AUTHENTICATED_EVIDENCE"
        binding={"_tag":"Dnrd5FixtureEvidenceBinding","contractVersion":EVIDENCE_BINDING_VERSION,"fixtureClass":FIXTURE_CLASS,"role":role,"evidenceClass":evidence_class,"claimBoundary":EVIDENCE_CLAIM_BOUNDARY,"sourceDescriptors":material_sources.get(role,[])}
        evidence_bindings[role]=_put(blobs,_raw(binding),JSON_MEDIA_TYPE)
    # Construct the state journal from exact v2 wire objects.  Special batches
    # are intentionally two writes: main effect+consumption, immediate
    # evidence-consumption+receipt, audit evidence-consumption+audit, and the
    # terminal manifest+seal.  All other support atoms are independent commits.
    by_kind = {}
    for atom in atoms: by_kind.setdefault(atom["kind"], []).append(atom)
    special_groups: list[list[dict[str, Any]]] = []
    special_ids: set[str] = set()
    def group(items: list[dict[str, Any]]) -> None:
        special_groups.append(items); special_ids.update(atom_key_id(x["key"]) for x in items)
    for index in range(3):
        group([by_kind["capability_consumption"][index], by_kind["macro_disposition"][index]])
        group([by_kind["evidence_seal_consumption"][index], by_kind["revision_transition_receipt"][index]])
    group([by_kind["capability_consumption"][3], by_kind["restore_transaction"][0]])
    group([by_kind["evidence_seal_consumption"][3], by_kind["rollback_transition_receipt"][0]])
    group([by_kind["evidence_seal_consumption"][4], by_kind["audit_release"][0]])
    group([by_kind["block_evidence_manifest"][0], by_kind["block_seal"][0]])
    units: list[list[dict[str, Any]]] = [[atom] for atom in atoms if atom_key_id(atom["key"]) not in special_ids] + special_groups
    unit_by_key={atom_key_id(atom["key"]): index for index, unit in enumerate(units) for atom in unit}
    env_by_key={atom_key_id(atom["key"]): parse_canonical(_blob_bytes(blobs,atom["envelope"])) for atom in atoms}
    dependencies: dict[int,set[int]]={index:set() for index in range(len(units))}
    for index, unit in enumerate(units):
        for atom in unit:
            env=env_by_key[atom_key_id(atom["key"])]
            targets=[ref["target"] for ref in env["references"]]
            if env["provenance"]["sourceRef"] is not None: targets.append(env["provenance"]["sourceRef"])
            for target in targets:
                owner=unit_by_key[atom_key_id(target)]
                if owner != index: dependencies[index].add(owner)
    # Kahn ordering preserves source order among currently ready units.  This
    # makes every external reference and provenance source available before the
    # commit that consumes it, while retaining the deliberate special batches.
    grouped=[]; remaining=set(range(len(units))); special_unit_order=[len(units)-len(special_groups)+i for i in range(len(special_groups))]; next_special=0
    while remaining:
        ready=[index for index in sorted(remaining) if dependencies[index].isdisjoint(remaining)]
        if not ready: raise RuntimeError("fixture atom/unit dependencies are cyclic")
        wanted=special_unit_order[next_special] if next_special < len(special_unit_order) else None
        # A special transaction gets priority as soon as its prerequisites are
        # committed.  Thus its receipt is literally the next journal commit,
        # rather than merely the next special commit after unrelated support.
        index=wanted if wanted in ready else next((candidate for candidate in ready if candidate not in special_unit_order), ready[0])
        grouped.append(units[index]); remaining.remove(index)
        if index == wanted: next_special += 1
    journal=[]; state={"schemaVersion":SCHEMA_VERSION,"revision":0,"bootstrapClosed":False,"atoms":[],"acceptedTransitionIds":[]}; committed: set[str]=set(); preceding_main: dict[str, Any] | None=None
    genesis={"_tag":"CanonicalAtomV2StateJournalGenesis","contractVersion":"hswm-canonical-atom-v2-state-journal/v1","encoding":CANONICAL_JSON_VERSION,"journalLineageId":"dnrd5-fixture-journal-0001","schema":{"schemaVersion":SCHEMA_VERSION,"content":schema_desc},"stateRevision":0,"bootstrapClosed":False,"predecessor":None,"resultingStateSha256":canonical_sha256(state)}
    previous=_put(blobs,_raw(genesis),JOURNAL_MEDIA_TYPE); journal.append({"record":previous,"tag":"GENESIS"})
    for revision, batch in enumerate(grouped,1):
        terminal_manifest=next((atom for atom in batch if atom["kind"]=="block_evidence_manifest"),None)
        if terminal_manifest is not None:
            terminal_seal=next(atom for atom in batch if atom["kind"]=="block_seal")
            preterminal=[atom for atom in atoms if atom is not terminal_manifest and atom is not terminal_seal]
            call_roles=[{"callId":call["callId"],"role":role,"descriptor":call["contents"][role]} for call in calls for role in ROLES]
            manifest_payload={"_tag":"Dnrd5FixtureBlockEvidenceManifestPayload","contractVersion":BLOCK_MANIFEST_VERSION,"fixtureClass":FIXTURE_CLASS,"closureClass":"PRETERMINAL_EXACT_SET_NOT_PROVIDER_OCCURRENCE_OR_SCIENTIFIC_RESULT","atomListings":[{"key":atom["key"],"kind":atom["kind"],"payload":atom["payload"],"envelope":atom["envelope"]} for atom in preterminal],"atomPayloadDescriptors":[atom["payload"] for atom in preterminal],"atomEnvelopeDescriptors":[atom["envelope"] for atom in preterminal],"journalRecordDescriptors":[entry["record"] for entry in journal],"providerReceipts":[call["receipt"] for call in calls],"callRoleBindings":call_roles,"ledgerDescriptors":[item["record"] for item in ledger],"schemaDescriptor":schema_desc,"lifecycleDescriptor":lifecycle_desc,"alignmentDescriptor":alignment_desc,"evidenceBindings":evidence_bindings}
            _refresh_atom_envelope(blobs,terminal_manifest,payload=manifest_payload,media_type=JSON_MEDIA_TYPE)
            seal_payload={"_tag":"Dnrd5FixtureBlockSealPayload","contractVersion":BLOCK_SEAL_VERSION,"fixtureClass":FIXTURE_CLASS,"terminal":TERMINAL,"claimBoundary":EVIDENCE_CLAIM_BOUNDARY,"preterminalJournalHead":previous,"blockEvidenceManifestPayload":terminal_manifest["payload"],"blockEvidenceManifestEnvelope":terminal_manifest["envelope"]}
            _refresh_atom_envelope(blobs,terminal_seal,payload=seal_payload,media_type=JSON_MEDIA_TYPE)
        receipt_atom=next((atom for atom in batch if atom["kind"] in {"revision_transition_receipt","rollback_transition_receipt"}),None)
        if receipt_atom is not None:
            if preceding_main is None: raise RuntimeError("receipt seal has no immediately preceding main effect")
            receipt_env=parse_canonical(_blob_bytes(blobs,receipt_atom["envelope"]))
            role_targets={ref["role"].removeprefix("role:dnrd5:v2:"): ref["target"] for ref in receipt_env["references"]}
            effect_role="successor" if receipt_atom["kind"]=="revision_transition_receipt" else "restore"
            decision=role_targets["decision"]; consumption=role_targets["effect-consumption"]; effect=role_targets[effect_role]
            identity=canonical_sha256({"contractVersion":POSTCOMMIT_RECEIPT_IDENTITY_VERSION,"effectRecordDescriptorSha256":preceding_main["record"]["sha256"],"journalLineageId":"dnrd5-fixture-journal-0001","transitionId":preceding_main["transitionId"],"decisionAtomKeyId":atom_key_id(decision),"effectConsumptionAtomKeyId":atom_key_id(consumption),"effectAtomKeyId":atom_key_id(effect)})
            old_key=dict(receipt_atom["key"]); new_key={**old_key,"atomUid":f"receipt:{identity}"}
            _replace_uncommitted_key(blobs,atoms,old_key,new_key,committed)
            receipt_payload={"contractVersion":RECEIPT_SEAL_VERSION,"receiptKind":"REVISION" if receipt_atom["kind"]=="revision_transition_receipt" else "ROLLBACK","precedingEffectRecordDescriptorSha256":preceding_main["record"]["sha256"],"postcommitReceiptIdentity":identity,"decisionAtomKeyId":atom_key_id(decision),"effectConsumptionAtomKeyId":atom_key_id(consumption),"effectAtomKeyId":atom_key_id(effect)}
            _refresh_atom_envelope(blobs,receipt_atom,payload=receipt_payload,media_type=RECEIPT_MEDIA_TYPE)
        envs=[parse_canonical(_blob_bytes(blobs, atom["envelope"])) for atom in batch]
        writes=sorted([{"key":atom["key"],"payload":atom["payload"],"envelope":atom["envelope"]} for atom in batch],key=lambda x: atom_key_id(x["key"]))
        next_atoms=sorted(state["atoms"]+envs,key=lambda x: atom_key_id(x["key"]))
        transition=f"fixture-transition-{revision:03d}"
        batch_ids={atom_key_id(atom["key"]) for atom in batch}; read_by_id={}
        for env in envs:
            for ref in env["references"]: read_by_id[atom_key_id(ref["target"])]=ref["target"]
            source=env["provenance"]["sourceRef"]
            if source is not None: read_by_id[atom_key_id(source)]=source
        read_set=[read_by_id[key] for key in sorted(read_by_id) if key not in batch_ids]
        if any(atom_key_id(key) not in {atom_key_id(x["key"]) for x in state["atoms"]} for key in read_set):
            raise RuntimeError("journal read set contains a non-prior external source")
        receipt={"_tag":"CanonicalAtomV2EffectReceipt","contractVersion":"hswm-canonical-effect-receipt/v2","transitionId":transition,"schemaVersion":SCHEMA_VERSION,"previousStateRevision":revision-1,"nextStateRevision":revision,"readSet":read_set,"writeSet":[x["key"] for x in writes],"traceRef":None,"guard":{"schema":"PASSED","ownerTotality":"PASSED","references":"PASSED","revision":"PASSED","permission":"REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT"},"actorClaim":"fixture-actor","authorizationRef":"fixture-authorization","scope":"fixture-byte-closure","decidedAt":"2026-08-28T00:00:00.000Z","decision":"ACCEPTED","provenanceSha256":canonical_sha256({"transitionId":transition,"fixtureClass":FIXTURE_CLASS})}
        next_state={"schemaVersion":SCHEMA_VERSION,"revision":revision,"bootstrapClosed":True,"atoms":next_atoms,"acceptedTransitionIds":state["acceptedTransitionIds"]+[transition]}
        commit={"_tag":"CanonicalAtomV2StateJournalCommit","contractVersion":"hswm-canonical-atom-v2-state-journal/v1","encoding":CANONICAL_JSON_VERSION,"journalLineageId":"dnrd5-fixture-journal-0001","schema":{"schemaVersion":SCHEMA_VERSION,"content":schema_desc},"stateRevision":revision,"predecessor":previous,"receipt":receipt,"writeBindings":writes,"previousStateSha256":canonical_sha256(state),"resultingStateSha256":canonical_sha256(next_state),"durability":"LOCAL_PREDECESSOR_BOUND_JOURNAL_V1_NOT_CANONICAL_PERMIT_NOT_LEARNING"}
        previous=_put(blobs,_raw(commit),JOURNAL_MEDIA_TYPE); journal.append({"record":previous,"state":commit["resultingStateSha256"]}); state=next_state
        committed.update(atom_key_id(atom["key"]) for atom in batch)
        main_atom=next((atom for atom in batch if atom["kind"] in {"macro_disposition","restore_transaction"}),None)
        if main_atom is not None:
            main_env=parse_canonical(_blob_bytes(blobs,main_atom["envelope"]))
            role="revision-admission-decision" if main_atom["kind"]=="macro_disposition" else "decision"
            consume_role="effect-consumption" if main_atom["kind"]=="macro_disposition" else "consumption"
            targets={ref["role"].removeprefix("role:dnrd5:v2:"): ref["target"] for ref in main_env["references"]}
            preceding_main={"record":previous,"transitionId":transition,"decision":targets[role],"consumption":targets[consume_role],"effect":main_atom["key"]}
        elif receipt_atom is not None:
            preceding_main=None
    adapter=[]; adapter_cursor: dict[str, int] = {}
    lifecycle_kind = {
        "STUDY_RANDOMNESS":"study_randomness", "BLOCK_SPEC":"block_spec", "EVALUATOR_COMMITMENT":"evaluator_commitment",
        "PROBE_COMMITMENT":"probe_commitment", "PLACEBO_COMMITMENT":"placebo_commitment", "W0_SNAPSHOT":"w0_snapshot",
        "FORK_INCIDENCE":"fork_incidence", "ARM_ASSIGNMENT":"block_assignment", "EPISODE_ACTIVATION":"episode_activation",
        "TRAJECTORY_CONTRACT":"trajectory_contract", "TRAJECTORY_SEAL":"trajectory_seal", "EVALUATOR_RELEASE":"evaluator_release",
        "HIDDEN_OUTCOME":"hidden_outcome", "OUTCOME_CREDIT_ESCROW":"outcome_credit_escrow", "PLACEBO_RECEIPT":"placebo_receipt",
        "FEEDBACK_ASSIGNMENT":"feedback_assignment", "REVISION_PROPOSAL":"revision_proposal", "CANDIDATE_VALIDATION":"candidate_validation",
        "CREDIT_DECISION":"credit_decision", "ARM_TRANSITION":"revision_admission_decision", "TRANSITION_RECEIPT":"revision_transition_receipt",
        "RESTORE_TRANSACTION":"restore_transaction", "BEHAVIOR_PROJECTION":"behavior_projection", "PROBE_RESPONSE_SEAL":"probe_trajectory",
        "PROBE_OUTCOME":"probe_outcome", "DELAYED_AUDIT_RELEASE":"audit_release", "BLOCK_SEAL":"block_seal",
    }
    for event in build_synthetic_lifecycle_vector()["lifecycle"]["events"]:
        for artifact in event["artifacts"]:
            artifact_kind=artifact["kind"]; arm=artifact["arm"]; arm_slot=ARMS.index(arm) if arm is not None else None
            base={"event":event["event"],"artifactId":artifact["artifactId"]}
            if artifact_kind=="ARM_ASSIGNMENT":
                adapter.append({**base,"bindingClass":"ASSIGNMENT_DERIVED","bindings":{"assignment":by_kind["block_assignment"][0]["key"],"fork":by_kind["fork_incidence"][arm_slot]["key"]}})
            elif artifact_kind=="ARM_TRANSITION":
                if arm_slot == 2:
                    bindings={"validation":by_kind["candidate_validation"][2]["key"],"credit":by_kind["credit_decision"][2]["key"],"stagingMainConsumption":None,"macroDisposition":None,"revisionReceipt":None,"restoreTransaction":None,"restoreMainConsumption":None,"rollbackReceipt":None}
                else:
                    main_slot=arm_slot if arm_slot < 2 else 2
                    bindings={"validation":by_kind["candidate_validation"][arm_slot]["key"],"credit":by_kind["credit_decision"][arm_slot]["key"],"stagingMainConsumption":by_kind["capability_consumption"][main_slot]["key"],"macroDisposition":by_kind["macro_disposition"][main_slot]["key"],"revisionReceipt":by_kind["revision_transition_receipt"][main_slot]["key"],"restoreTransaction":by_kind["restore_transaction"][0]["key"] if arm_slot==3 else None,"restoreMainConsumption":by_kind["capability_consumption"][3]["key"] if arm_slot==3 else None,"rollbackReceipt":by_kind["rollback_transition_receipt"][0]["key"] if arm_slot==3 else None}
                adapter.append({**base,"bindingClass":"ARM_TRANSITION_DERIVED","bindings":bindings})
            elif artifact_kind=="PROBE_RESPONSE_SEAL":
                adapter.append({**base,"bindingClass":"PROBE_DERIVED","bindings":{"behaviorProjection":by_kind["behavior_projection"][arm_slot]["key"],"probeTrajectory":by_kind["probe_trajectory"][arm_slot]["key"]}})
            elif artifact_kind=="DELAYED_AUDIT_RELEASE":
                adapter.append({**base,"bindingClass":"AUDIT_DERIVED","bindings":{"auditRelease":by_kind["audit_release"][0]["key"],"hiddenOutcome":by_kind["hidden_outcome"][0]["key"],"escrow":by_kind["outcome_credit_escrow"][0]["key"],"probeTrajectories":[x["key"] for x in by_kind["probe_trajectory"]],"probeOutcomes":[x["key"] for x in by_kind["probe_outcome"]]}})
            else:
                target_kind=lifecycle_kind[artifact_kind]; offset=adapter_cursor.get(target_kind,0); chosen=by_kind[target_kind][offset % len(by_kind[target_kind])]; adapter_cursor[target_kind]=offset+1
                adapter.append({**base,"bindingClass":"DIRECT","bindings":{"atom":chosen["key"]}})
    if len(adapter)!=59: raise RuntimeError("lifecycle adapter must have exactly 59 rows")
    journal_writes=[parse_canonical(_blob_bytes(blobs,entry["record"]))["writeBindings"] for entry in journal[1:]]
    # Atom UIDs may be receipt:<digest>; count from listed kinds instead of UID
    # text so the summary is a derived observation, never a stale assertion.
    atom_kind_by_key={atom_key_id(atom["key"]):atom["kind"] for atom in atoms}
    kind_sets=[{atom_kind_by_key[atom_key_id(binding["key"])] for binding in writes} for writes in journal_writes]
    exact_counts={"admitMainEffects":sum({"capability_consumption","macro_disposition"}==kinds for kinds in kind_sets),"restoreMainEffects":sum({"capability_consumption","restore_transaction"}==kinds for kinds in kind_sets),"revisionReceiptSeals":sum({"evidence_seal_consumption","revision_transition_receipt"}==kinds for kinds in kind_sets),"rollbackReceiptSeals":sum({"evidence_seal_consumption","rollback_transition_receipt"}==kinds for kinds in kind_sets),"auditReleases":sum({"evidence_seal_consumption","audit_release"}==kinds for kinds in kind_sets),"terminalSeals":sum({"block_evidence_manifest","block_seal"}==kinds for kinds in kind_sets),"ledgerStarts":sum(item["phase"]=="START" for item in ledger),"ledgerSucceeded":sum(item["phase"]=="SUCCEEDED" for item in ledger),"callReceipts":len(calls),"receiptContentRoles":sum(len(call["contents"]) for call in calls)}
    core={"schema":schema_desc,"lifecycle":lifecycle_desc,"alignment":alignment_desc,"lifecycleSha256":LIFECYCLE_SHA256,"alignmentSha256":ALIGNMENT_SHA256,"atoms":atoms,"lifecycleAdapter":adapter,"journal":journal,"fixtureLedger":ledger,"calls":calls,"evidenceBindings":evidence_bindings,"exactCounts":exact_counts}
    manifest=fixture_root_manifest(core,[descriptor(raw,media) for raw,media in blobs.values()])
    return manifest, blobs

def write_fixture(repository_root: Path, output: Path) -> str:
    manifest, blobs=build_fixture(repository_root)
    # Build a complete sibling then replace the exact requested fixture target;
    # this makes stale blob reuse impossible while never touching another path.
    stage=Path(tempfile.mkdtemp(prefix=f".{output.name}.stage-", dir=output.parent))
    for digest,(raw,_media) in blobs.items():
        target=blob_path(stage,digest); target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(raw)
    root_raw=_raw(manifest); (stage/"manifest.json").write_bytes(root_raw)
    if output.exists(): shutil.rmtree(output)
    stage.replace(output)
    return sha256(root_raw).hexdigest()

def self_check_fixture(output: Path) -> str:
    """Producer-side transport/descriptor determinism check, not a judge."""
    manifest_raw=(output/"manifest.json").read_bytes(); manifest=parse_canonical(manifest_raw)
    index=manifest["descriptorIndex"]; identities=[descriptor_id(d) for d in index]
    if identities != sorted(identities) or len(identities) != len(set(identities)):
        raise RuntimeError("manifest descriptor index is not sorted and unique")
    expected={d["sha256"] for d in index}; actual={p.name for p in (output/"blobs").iterdir()}
    if actual != expected: raise RuntimeError("fixture blob closure is not exact")
    for desc in index:
        raw=(output/"blobs"/desc["sha256"]).read_bytes()
        if descriptor(raw,desc["mediaType"]) != desc: raise RuntimeError("fixture descriptor drift")
    core=manifest["core"]
    if len(core["lifecycleAdapter"]) != 59 or len(core["calls"]) != 9 or len(core["fixtureLedger"]) != 18:
        raise RuntimeError("fixture cardinality drift")
    evidence=core.get("evidenceBindings")
    required_evidence={"evaluator-input","evaluator-output","genuine-commitment","genuine-opening","placebo-commitment","placebo-opening","assignment-receipt","randomness-receipt","permit-input","permit-resolution","authorization","revocation","trusted-time-placeholder","source-tree","selected-build","allowed-import-graph","runtime","custody-isolation-statement"}
    if type(evidence) is not dict or set(evidence) != required_evidence:
        raise RuntimeError("fixture evidence role closure drift")
    check_by_kind: dict[str,list[dict[str,Any]]] = {}
    for atom in core["atoms"]: check_by_kind.setdefault(atom["kind"],[]).append(atom)
    check_calls=core["calls"]
    expected_sources={
        "evaluator-input":[check_calls[0]["contents"]["model-input"]], "evaluator-output":[check_calls[0]["contents"]["observed-response"]],
        "genuine-commitment":[check_by_kind["evaluator_commitment"][0]["payload"]], "genuine-opening":[check_by_kind["evaluator_release"][0]["payload"]],
        "placebo-commitment":[check_by_kind["placebo_commitment"][0]["payload"]], "placebo-opening":[check_by_kind["placebo_receipt"][0]["payload"]],
        "assignment-receipt":[check_by_kind["block_assignment"][0]["payload"]], "randomness-receipt":[check_by_kind["study_randomness"][0]["payload"]],
        "permit-input":[check_by_kind["permit_policy"][0]["payload"]], "permit-resolution":[check_by_kind["capability_issuance"][0]["payload"]],
        "authorization":[check_by_kind["authorization_decision"][0]["payload"]], "revocation":[check_by_kind["revocation_status"][0]["payload"]],
        "runtime":[check_calls[0]["contents"]["runtime-identity"]], "custody-isolation-statement":[check_calls[0]["contents"]["isolation-statement"]],
    }
    check_placeholders={"trusted-time-placeholder","source-tree","selected-build","allowed-import-graph"}
    for role, desc in evidence.items():
        raw=(output/"blobs"/desc["sha256"]).read_bytes(); value=parse_canonical(raw)
        expected_class="DECLARED_PLACEHOLDER_NOT_AUTHENTICATED_EVIDENCE" if role in check_placeholders else "DETERMINISTIC_FIXTURE_MATERIAL_NOT_AUTHENTICATED_EVIDENCE"
        expected_value={"_tag":"Dnrd5FixtureEvidenceBinding","contractVersion":EVIDENCE_BINDING_VERSION,"fixtureClass":FIXTURE_CLASS,"role":role,"evidenceClass":expected_class,"claimBoundary":EVIDENCE_CLAIM_BOUNDARY,"sourceDescriptors":expected_sources.get(role,[])}
        if value != expected_value:
            raise RuntimeError("fixture evidence payload grammar drift")
    receipt_atoms=[atom for atom in core["atoms"] if atom["kind"] in {"revision_transition_receipt","rollback_transition_receipt"}]
    if len(receipt_atoms) != 4:
        raise RuntimeError("fixture postcommit receipt cardinality drift")
    for atom in receipt_atoms:
        value=parse_canonical((output/"blobs"/atom["payload"]["sha256"]).read_bytes())
        required={"contractVersion", "receiptKind", "precedingEffectRecordDescriptorSha256", "postcommitReceiptIdentity", "decisionAtomKeyId", "effectConsumptionAtomKeyId", "effectAtomKeyId"}
        if set(value) != required or value["contractVersion"] != RECEIPT_SEAL_VERSION or atom["key"]["atomUid"] != f"receipt:{value['postcommitReceiptIdentity']}":
            raise RuntimeError("fixture postcommit receipt identity drift")
    semantic_by_key={atom_key_id(atom["key"]):atom for atom in core["atoms"]}
    def env(atom: dict[str,Any]) -> dict[str,Any]: return parse_canonical((output/"blobs"/atom["envelope"]["sha256"]).read_bytes())
    def one_target(atom: dict[str,Any], role: str) -> dict[str,Any]:
        found=[ref["target"] for ref in env(atom)["references"] if ref["role"]==f"role:dnrd5:v2:{role}"]
        if len(found)!=1: raise RuntimeError(f"fixture semantic role drift: {role}")
        return found[0]
    def payload_for_key(key: dict[str,Any]) -> dict[str,Any]:
        atom=semantic_by_key[atom_key_id(key)]; return parse_canonical((output/"blobs"/atom["payload"]["sha256"]).read_bytes())
    expected_slots=(0,1,3); expected_arms=("ACTIVE","OUTCOME_INDEPENDENT_SHAM","EXACT_W0_ROLLBACK")
    for index, decision in enumerate(check_by_kind["revision_admission_decision"]):
        if payload_for_key(decision["key"])["arm"] != expected_arms[index] or payload_for_key(decision["key"])["slot"] != expected_slots[index]: raise RuntimeError("decision arm/slot drift")
        for role in ("fork","proposal","validation","credit"):
            reference_payload=payload_for_key(one_target(decision,role))
            if reference_payload.get("arm") != expected_arms[index] or reference_payload.get("slot") != expected_slots[index]: raise RuntimeError("decision tuple source drift")
    for index, macro in enumerate(check_by_kind["macro_disposition"]):
        value=payload_for_key(macro["key"])
        if value["arm"] != expected_arms[index] or value["slot"] != expected_slots[index]: raise RuntimeError("macro arm/slot drift")
    for index, trajectory in enumerate(check_by_kind["probe_trajectory"]):
        if atom_key_id(one_target(trajectory,"probe")) != atom_key_id(check_by_kind["probe_commitment"][index+1]["key"]): raise RuntimeError("fresh probe trajectory binding drift")
        outcome=check_by_kind["probe_outcome"][index]
        if atom_key_id(one_target(outcome,"probe")) != atom_key_id(check_by_kind["probe_commitment"][index+1]["key"]): raise RuntimeError("fresh probe outcome binding drift")
    audit=check_by_kind["audit_release"][0]
    if atom_key_id(one_target(audit,"evidence-consumption")) != atom_key_id(check_by_kind["evidence_seal_consumption"][4]["key"]): raise RuntimeError("audit evidence consumption drift")
    return sha256(manifest_raw).hexdigest()

if __name__ == "__main__":
    root=Path(__file__).parents[2]; output=root/"_research/dnrd5/vectors/actual_byte_corpus_v1"
    written=write_fixture(root,output)
    if written != self_check_fixture(output): raise RuntimeError("post-write fixture root drift")
    print(written)
