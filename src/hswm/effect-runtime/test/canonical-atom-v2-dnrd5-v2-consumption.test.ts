import { createHash } from "node:crypto";

import { Either } from "effect";
import { describe, expect, it } from "vitest";

import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js";
import { validateCanonicalAtomV2State } from "../src/canonical-atom-v2-domain.js";
import {
  DNRD5_V2_CAPABILITY_CONSUMPTION_MEDIA_TYPE,
  DNRD5_V2_CONSUMPTION_COMMAND_INTENT_MEDIA_TYPE,
  DNRD5_V2_CONSUMPTION_COMMAND_INTENT_V1,
  DNRD5_V2_CONSUMPTION_COMMAND_PROJECTION_V1,
  DNRD5_V2_CONSUMPTION_PAYLOAD_V1,
  DNRD5_V2_CONSUMPTION_TERMINAL,
  DNRD5_V2_EVIDENCE_SEAL_CONSUMPTION_MEDIA_TYPE,
  dnrd5V2ConsumptionAtomUid,
  validateDnrd5V2Consumption,
  type Dnrd5V2ConsumptionInput,
  type Dnrd5V2ConsumptionPhase,
} from "../src/canonical-atom-v2-dnrd5-v2-consumption.js";
import { DNRD5_V2_OWNER_ROLE_BY_KIND, DNRD5_V2_REFERENCE_TYPE, DNRD5_V2_SCHEMA_VERSION, makeDnrd5V2CanonicalSchema, type Dnrd5V2CanonicalAtomKind } from "../src/canonical-atom-v2-dnrd5-v2-schema.js";
import { canonicalAtomV2KeyId, type CanonicalAtomV2, type CanonicalAtomV2Key, type CommitCanonicalAtomsV2Command } from "../src/canonical-atom-v2-schema.js";
import { canonicalAtomV2StateSha256, HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE } from "../src/canonical-atom-v2-state-journal.js";

const LINEAGE = "lineage:dnrd5-v2-consumption";
const AT = "2026-08-28T12:00:00.000Z";
const hash = (value: Uint8Array | string): string => createHash("sha256").update(value).digest("hex");
const right = <A, E>(value: Either.Either<A, E>): A => { if (Either.isLeft(value)) throw new Error(JSON.stringify(value.left)); return value.right; };
const bytes = (value: object): Uint8Array => right(canonicalJsonBytes(value));
const descriptor = (mediaType: string, value: Uint8Array) => ({ mediaType, byteLength: value.byteLength, sha256: hash(value) });
const key = (atomUid: string): CanonicalAtomV2Key => ({ schemaVersion: DNRD5_V2_SCHEMA_VERSION, lineageId: LINEAGE, atomUid, revisionId: 0 });
const id = (value: CanonicalAtomV2): string => canonicalAtomV2KeyId(value.key);
type Ref = readonly [string, CanonicalAtomV2];

const atom = (uid: string, kind: Dnrd5V2CanonicalAtomKind, refs: ReadonlyArray<Ref> = []): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2", contractVersion: "hswm-canonical-atom/v2", key: key(uid),
  kind: `hswm:dnrd5:v2:${kind}`,
  responsibilityOwner: `owner:dnrd5:v2:${DNRD5_V2_OWNER_ROLE_BY_KIND[kind]}`,
  content: descriptor("application/json", bytes({})),
  provenance: refs.length === 0
    ? { mode: "BOOTSTRAP", evidenceSha256: "a".repeat(64), sourceRef: null }
    : { mode: "DERIVATION", evidenceSha256: "a".repeat(64), sourceRef: refs[0]![1].key },
  lifecycle: "ADMITTED",
  references: refs.map(([role, target]) => ({ referenceType: DNRD5_V2_REFERENCE_TYPE, role: `role:dnrd5:v2:${role}`, target: target.key })),
});

/** Schema-valid predecessor containing both purpose branches. */
const predecessor = () => {
  const policy = atom("policy", "permit_policy"), randomness = atom("randomness", "study_randomness"), evaluator = atom("evaluator", "evaluator_commitment");
  const block = atom("block", "block_spec", [["randomness", randomness], ["evaluator", evaluator]]);
  const probe = atom("probe", "probe_commitment", [["block-spec", block], ["randomness", randomness]]);
  const placebo = atom("placebo", "placebo_commitment", [["block-spec", block], ["randomness", randomness]]);
  const w0 = atom("w0", "w0_snapshot", [["block-spec", block]]);
  const forks = [1, 2, 3, 4].map((n) => atom(`fork-${n}`, "fork_incidence", [["w0", w0]]));
  const assignment = atom("assignment", "block_assignment", [["randomness", randomness], ["block-spec", block], ...forks.map((fork) => ["fork", fork] as const)]);
  const activation = atom("activation", "episode_activation", [["block-spec", block], ["probe", probe], ["w0", w0], ...forks.map((fork) => ["fork", fork] as const), ["assignment", assignment], ["evaluator", evaluator]]);
  const contract = atom("contract", "trajectory_contract", [["activation", activation]]);
  const trajectory = atom("trajectory", "trajectory_seal", [["activation", activation], ["contract", contract], ["w0", w0]]);
  const placeboReceipt = atom("placebo-receipt", "placebo_receipt", [["commitment", placebo], ["randomness", randomness]]);
  const feedback = atom("feedback", "feedback_assignment", [["fork", forks[0]!], ["assignment", assignment], ["source", placeboReceipt]]);
  const proposal = atom("proposal", "revision_proposal", [["trajectory", trajectory], ["feedback", feedback]]);
  const validation = atom("validation", "candidate_validation", [["proposal", proposal]]);
  const authorization = atom("authorization", "authorization_decision", [["policy", policy]]);
  const capability = atom("capability", "capability_issuance", [["authorization", authorization], ["policy", policy]]);
  const revocation = atom("revocation", "revocation_status", [["authorization", authorization], ["capability", capability]]);
  const grant = atom("grant", "grant_snapshot", [["policy", policy], ["authorization", authorization], ["capability", capability], ["revocation", revocation]]);
  const credit = atom("credit", "credit_decision", [["trajectory", trajectory], ["credit-source", placeboReceipt], ["feedback", feedback], ["proposal", proposal], ["grant", grant]]);
  const decision = atom("decision", "revision_admission_decision", [["block", block], ["assignment", assignment], ["fork", forks[0]!], ["proposal", proposal], ["validation", validation], ["credit", credit], ["grant", grant], ["authorization", authorization], ["capability", capability], ["revocation", revocation]]);
  const restorePolicy = atom("restore-policy", "restore_policy", [["policy", policy], ["capability", capability]]);
  const stagedConsumption = atom("staged-consumption", "capability_consumption", [["grant", grant], ["capability", capability], ["revocation", revocation], ["decision", decision]]);
  const stagedMacro = atom("staged-macro", "macro_disposition", [["proposal", proposal], ["revision-admission-decision", decision], ["restore-policy", restorePolicy], ["effect-consumption", stagedConsumption]]);
  const stagedEvidence = atom("staged-evidence", "evidence_seal_consumption", [["grant", grant], ["capability", capability], ["revocation", revocation], ["purpose", decision]]);
  const stagedReceipt = atom("staged-receipt", "revision_transition_receipt", [["decision", decision], ["effect-consumption", stagedConsumption], ["successor", stagedMacro], ["evidence-consumption", stagedEvidence]]);
  const rollback = atom("rollback", "rollback_decision", [["block", block], ["assignment", assignment], ["fork", forks[0]!], ["w0", w0], ["grant", grant], ["policy", restorePolicy], ["authorization", authorization], ["capability", capability], ["revocation", revocation], ["staging-successor", stagedMacro], ["staging-receipt", stagedReceipt]]);
  const stagedRestore = atom("staged-restore", "restore_transaction", [["w0", w0], ["grant", grant], ["policy", restorePolicy], ["decision", rollback], ["consumption", stagedConsumption], ["staging-successor", stagedMacro]]);
  const atoms = [policy, randomness, evaluator, block, probe, placebo, w0, ...forks, assignment, activation, contract, trajectory, placeboReceipt, feedback, proposal, validation, authorization, capability, revocation, grant, credit, decision, restorePolicy, stagedConsumption, stagedMacro, stagedEvidence, stagedReceipt, rollback, stagedRestore].sort((a, b) => id(a).localeCompare(id(b)));
  return { state: { schemaVersion: DNRD5_V2_SCHEMA_VERSION, revision: 1, bootstrapClosed: true, atoms, acceptedTransitionIds: ["transition:consumption-bootstrap"] }, grant, capability, revocation, decision, rollback, restorePolicy, w0, proposal, stagedConsumption, stagedMacro, stagedRestore };
};

const fixture = (phase: Dnrd5V2ConsumptionPhase): Dnrd5V2ConsumptionInput => {
  const base = predecessor();
  const state = right(validateCanonicalAtomV2State(makeDnrd5V2CanonicalSchema(), base.state));
  const purpose = phase === "MAIN_ADMIT" || phase === "RECEIPT_ADMIT" ? base.decision : base.rollback;
  const main = phase === "MAIN_ADMIT" || phase === "MAIN_RESTORE";
  const purposeRole = main ? "decision" : "purpose";
  const nonce = hash(`nonce:${phase}`), uid = right(dnrd5V2ConsumptionAtomUid(phase, nonce, id(purpose)));
  const consumptionStub = { key: key(uid) } as CanonicalAtomV2;
  const companion = phase === "MAIN_ADMIT"
    ? atom("candidate-macro", "macro_disposition", [["proposal", base.proposal], ["revision-admission-decision", base.decision], ["restore-policy", base.restorePolicy], ["effect-consumption", consumptionStub]])
    : phase === "MAIN_RESTORE"
      ? atom("candidate-restore", "restore_transaction", [["w0", base.w0], ["grant", base.grant], ["policy", base.restorePolicy], ["decision", base.rollback], ["consumption", consumptionStub], ["staging-successor", base.stagedMacro]])
      : phase === "RECEIPT_ADMIT"
        ? atom("candidate-receipt", "revision_transition_receipt", [["decision", base.decision], ["effect-consumption", base.stagedConsumption], ["successor", base.stagedMacro], ["evidence-consumption", consumptionStub]])
        : atom("candidate-rollback-receipt", "rollback_transition_receipt", [["decision", base.rollback], ["effect-consumption", base.stagedConsumption], ["restore", base.stagedRestore], ["evidence-consumption", consumptionStub]]);
  const needed = [base.grant, base.capability, base.revocation, purpose,
    ...(phase === "MAIN_ADMIT" ? [base.proposal, base.restorePolicy] : []),
    ...(phase === "MAIN_RESTORE" ? [base.w0, base.restorePolicy, base.stagedMacro] : []),
    ...(phase === "RECEIPT_ADMIT" ? [base.stagedConsumption, base.stagedMacro] : []),
    ...(phase === "RECEIPT_RESTORE" ? [base.stagedConsumption, base.stagedRestore] : [])];
  const readSet = [...new Map(needed.map((value) => [id(value), value.key])).values()].sort((a, b) => canonicalAtomV2KeyId(a).localeCompare(canonicalAtomV2KeyId(b)));
  const command: CommitCanonicalAtomsV2Command = { _tag: "CommitCanonicalAtomsV2", contractVersion: "hswm-canonical-transition/v2", transitionId: `transition:consumption:${phase}`, expectedStateRevision: 1, schemaVersion: DNRD5_V2_SCHEMA_VERSION, actorClaim: "principal:consumption-test", authorizationRef: "authorization:consumption-test", scope: "scope:consumption-test", decidedAt: AT, traceRef: null, readSet, writes: [companion], provenanceSha256: hash(`provenance:${phase}`) };
  const projectionBytes = bytes({ contractVersion: DNRD5_V2_CONSUMPTION_COMMAND_PROJECTION_V1, phase, consumptionAtomKeyId: canonicalAtomV2KeyId(consumptionStub.key), command });
  const snapshot = { stateRevision: 1, stateSha256: right(canonicalAtomV2StateSha256(state)), journalLineageId: "journal:dnrd5-v2-consumption", journalHead: { ...descriptor(HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE, new TextEncoder().encode("head")), mediaType: HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE } };
  const authority = { grantAtomKeyId: id(base.grant), capabilityAtomKeyId: id(base.capability), revocationAtomKeyId: id(base.revocation) };
  const intentBytes = bytes({ contractVersion: DNRD5_V2_CONSUMPTION_COMMAND_INTENT_V1, phase, capabilityNonceSha256: nonce, purposeAtomKeyId: id(purpose), authority, authorizationSnapshot: snapshot, evaluatedAt: AT, commandProjectionSha256: hash(projectionBytes) });
  const payloadBytes = bytes({ _tag: "Dnrd5V2ConsumptionPayload", contractVersion: DNRD5_V2_CONSUMPTION_PAYLOAD_V1, phase, capabilityNonceSha256: nonce, purposeAtomKeyId: id(purpose), authority, authorizationSnapshot: snapshot, commandIntent: descriptor(DNRD5_V2_CONSUMPTION_COMMAND_INTENT_MEDIA_TYPE, intentBytes), evaluatedAt: AT, terminal: DNRD5_V2_CONSUMPTION_TERMINAL });
  const candidate = atom(uid, main ? "capability_consumption" : "evidence_seal_consumption", [["grant", base.grant], ["capability", base.capability], ["revocation", base.revocation], [purposeRole, purpose]]);
  return { _tag: "Dnrd5V2ConsumptionInput", payloadBytes, commandIntentBytes: intentBytes, commandProjectionBytes: projectionBytes, atom: { ...candidate, content: descriptor(main ? DNRD5_V2_CAPABILITY_CONSUMPTION_MEDIA_TYPE : DNRD5_V2_EVIDENCE_SEAL_CONSUMPTION_MEDIA_TYPE, payloadBytes), provenance: { mode: "DERIVATION", evidenceSha256: hash(projectionBytes), sourceRef: purpose.key } }, authorizationSnapshot: snapshot, state };
};

const objectFrom = (value: Uint8Array): any =>
  JSON.parse(new TextDecoder().decode(value));

const withPayload = (
  input: Dnrd5V2ConsumptionInput,
  mutate: (payload: any) => void,
): Dnrd5V2ConsumptionInput => {
  const payload = objectFrom(input.payloadBytes);
  mutate(payload);
  const payloadBytes = bytes(payload);
  return {
    ...input,
    payloadBytes,
    atom: {
      ...input.atom,
      content: descriptor(input.atom.content.mediaType, payloadBytes),
    },
  };
};

const withIntent = (
  input: Dnrd5V2ConsumptionInput,
  mutate: (intent: any) => void,
): Dnrd5V2ConsumptionInput => {
  const intent = objectFrom(input.commandIntentBytes);
  mutate(intent);
  const commandIntentBytes = bytes(intent);
  const rebound = withPayload(input, (payload) => {
    payload.commandIntent = descriptor(
      DNRD5_V2_CONSUMPTION_COMMAND_INTENT_MEDIA_TYPE,
      commandIntentBytes,
    );
  });
  return { ...rebound, commandIntentBytes };
};

const withProjectionBytes = (
  input: Dnrd5V2ConsumptionInput,
  commandProjectionBytes: Uint8Array,
): Dnrd5V2ConsumptionInput => {
  const rebound = withIntent(input, (intent) => {
    intent.commandProjectionSha256 = hash(commandProjectionBytes);
  });
  return {
    ...rebound,
    commandProjectionBytes,
    atom: {
      ...rebound.atom,
      provenance: {
        ...rebound.atom.provenance,
        evidenceSha256: hash(commandProjectionBytes),
      },
    },
  };
};

const withProjection = (
  input: Dnrd5V2ConsumptionInput,
  mutate: (projection: any) => void,
): Dnrd5V2ConsumptionInput => {
  const projection = objectFrom(input.commandProjectionBytes);
  mutate(projection);
  return withProjectionBytes(input, bytes(projection));
};

const withState = (
  input: Dnrd5V2ConsumptionInput,
  mutate: (state: any) => void,
): Dnrd5V2ConsumptionInput => {
  const state = structuredClone(input.state);
  mutate(state);
  const normalized = right(
    validateCanonicalAtomV2State(makeDnrd5V2CanonicalSchema(), state),
  );
  const authorizationSnapshot = {
    ...input.authorizationSnapshot,
    stateRevision: normalized.revision,
    stateSha256: right(canonicalAtomV2StateSha256(normalized)),
  };
  const reboundIntent = withIntent(input, (intent) => {
    intent.authorizationSnapshot = authorizationSnapshot;
  });
  const reboundPayload = withPayload(reboundIntent, (payload) => {
    payload.authorizationSnapshot = authorizationSnapshot;
  });
  return {
    ...reboundPayload,
    authorizationSnapshot,
    state: normalized,
  };
};

const invalid = (
  value: unknown,
  code?: string,
  detail?: string,
): void => {
  const result = validateDnrd5V2Consumption(value);
  expect(Either.isLeft(result)).toBe(true);
  if (Either.isLeft(result)) {
    if (code !== undefined) expect(result.left.code).toBe(code);
    if (detail !== undefined) expect(result.left.detail).toContain(detail);
  }
};

describe("DNRD-5 v2 consumption candidate", () => {
  it("accepts one exact two-write, cycle-free command for every phase", () => {
    for (const phase of ["MAIN_ADMIT", "MAIN_RESTORE", "RECEIPT_ADMIT", "RECEIPT_RESTORE"] as const) {
      const result = validateDnrd5V2Consumption(fixture(phase));
      expect(Either.isRight(result), Either.isLeft(result) ? JSON.stringify(result.left) : "").toBe(true);
      if (Either.isRight(result)) {
        expect(result.right.phase).toBe(phase);
        expect(result.right.topologySha256).toMatch(/^[0-9a-f]{64}$/);
        expect(Object.isFrozen(result.right)).toBe(true);
        expect(Object.isFrozen(result.right.authority)).toBe(true);
        expect(Object.isFrozen(result.right.authorizationSnapshot)).toBe(true);
        expect(() => { (result.right.authority as { grantAtomKeyId: string }).grantAtomKeyId = "forged"; }).toThrow();
      }
    }
  });

  it("rejects phase/input/snapshot/state/history and head boundary drift", () => {
    const input = fixture("MAIN_ADMIT");
    expect(Either.isLeft(dnrd5V2ConsumptionAtomUid("INVALID", "a".repeat(64), id(input.state.atoms[0]!)))).toBe(true);
    invalid({ ...input, extra: true }, "INPUT_INVALID");
    invalid({ ...input, authorizationSnapshot: { ...input.authorizationSnapshot, extra: true } }, "SNAPSHOT_MISMATCH");
    invalid({ ...input, authorizationSnapshot: { ...input.authorizationSnapshot, journalLineageId: "bad|lineage" } }, "SNAPSHOT_MISMATCH");
    invalid({ ...input, authorizationSnapshot: { ...input.authorizationSnapshot, journalHead: { ...input.authorizationSnapshot.journalHead, mediaType: "application/json" } } }, "SNAPSHOT_MISMATCH");
    invalid({ ...input, authorizationSnapshot: { ...input.authorizationSnapshot, journalHead: { ...input.authorizationSnapshot.journalHead, extra: true } } }, "SNAPSHOT_MISMATCH");
    invalid({ ...input, state: { ...input.state, acceptedTransitionIds: [] } }, "STATE_INVALID");
    invalid({ ...input, state: { ...input.state, revision: 2 } }, "STATE_INVALID");
    invalid({ ...input, state: { ...input.state, atoms: [...input.state.atoms, input.state.atoms[0]!] } }, "STATE_INVALID");
    invalid({ ...input, state: { ...input.state, extra: true } }, "STATE_INVALID");
  });

  it("rejects noncanonical projections, duplicate/missing reads, and a wrong companion reference", () => {
    const input = fixture("MAIN_ADMIT");
    const projection = objectFrom(input.commandProjectionBytes);
    const noncanonical = new TextEncoder().encode(JSON.stringify({
      phase: projection.phase,
      contractVersion: projection.contractVersion,
      consumptionAtomKeyId: projection.consumptionAtomKeyId,
      command: projection.command,
    }));
    invalid(withProjectionBytes(input, noncanonical), "INTENT_INVALID", "projection digest/bytes drift");
    invalid(withProjection(input, (value) => {
      value.command.readSet.push(value.command.readSet[0]);
    }), "INTENT_INVALID", "cycle-free command commitment");
    invalid(withProjection(input, (value) => {
      value.command.readSet = value.command.readSet.slice(1);
    }), "INTENT_INVALID", "external dependency set");
    const surplus = input.state.atoms.find((value) => value.kind === "hswm:dnrd5:v2:study_randomness")!;
    invalid(withProjection(input, (value) => {
      value.command.readSet.push(surplus.key);
    }), "INTENT_INVALID", "external dependency set");
    invalid(withProjection(input, (value) => {
      value.command.writes[0].references = value.command.writes[0].references.map((ref: any) =>
        ref.role === "role:dnrd5:v2:effect-consumption"
          ? { ...ref, role: "role:dnrd5:v2:consumption" }
          : ref,
      );
    }), "INTENT_INVALID", "cycle-free command commitment");
    invalid(withProjection(input, (value) => {
      value.command.writes[0].kind = "hswm:dnrd5:v2:restore_transaction";
    }), "INTENT_INVALID", "cycle-free command commitment");
  });

  it("rejects byte, intent, descriptor, UID, owner, media, provenance, and source-reference drift", () => {
    const input = fixture("RECEIPT_ADMIT");
    invalid({ ...input, payloadBytes: Uint8Array.from([...input.payloadBytes, 0]) }, "CANONICAL_ENCODING_INVALID");
    invalid({ ...input, commandIntentBytes: Uint8Array.from([...input.commandIntentBytes, 0]) }, "CANONICAL_ENCODING_INVALID");
    invalid({ ...input, atom: { ...input.atom, content: { ...input.atom.content, sha256: "f".repeat(64) } } }, "ATOM_INVALID");

    const forgedUid = "forged-consumption-uid";
    const forgedKey = { ...input.atom.key, atomUid: forgedUid };
    const uidRebound = withProjection(input, (value) => {
      value.consumptionAtomKeyId = canonicalAtomV2KeyId(forgedKey);
      value.command.writes[0].references = value.command.writes[0].references.map((ref: any) =>
        ref.role === "role:dnrd5:v2:evidence-consumption"
          ? { ...ref, target: forgedKey }
          : ref,
      );
    });
    invalid({ ...uidRebound, atom: { ...uidRebound.atom, key: forgedKey } }, "UID_INVALID");

    invalid({ ...input, atom: { ...input.atom, responsibilityOwner: "owner:dnrd5:v2:forged" } }, "ATOM_INVALID");
    invalid({ ...input, atom: { ...input.atom, content: { ...input.atom.content, mediaType: "application/json" } } }, "ATOM_INVALID");
    invalid({ ...input, atom: { ...input.atom, provenance: { ...input.atom.provenance, evidenceSha256: "e".repeat(64) } } }, "ATOM_INVALID");
    invalid({ ...input, atom: { ...input.atom, provenance: { ...input.atom.provenance, sourceRef: input.state.atoms[0]!.key } } }, "ATOM_INVALID");

    invalid(withIntent(input, (intent) => {
      intent.capabilityNonceSha256 = "0".repeat(64);
    }), "INTENT_INVALID", "intent does not bind payload");
    invalid(withIntent(input, (intent) => {
      intent.evaluatedAt = "2026-08-28T12:00:01.000Z";
    }), "INTENT_INVALID", "intent does not bind payload");
    invalid(withIntent(input, (intent) => {
      intent.extra = true;
    }), "INTENT_INVALID");

    let nonceRebound = withIntent(input, (intent) => {
      intent.capabilityNonceSha256 = "0".repeat(64);
    });
    nonceRebound = withPayload(nonceRebound, (payload) => {
      payload.capabilityNonceSha256 = "0".repeat(64);
    });
    invalid(nonceRebound, "UID_INVALID");
    invalid(withPayload(input, (payload) => {
      payload.evaluatedAt = "2026-08-28T12:00:00Z";
    }), "PAYLOAD_INVALID");
    invalid(withPayload(input, (payload) => {
      payload.commandIntent.byteLength += 1;
    }), "DESCRIPTOR_MISMATCH");
    invalid(withPayload(input, (payload) => {
      payload.extra = true;
    }), "PAYLOAD_INVALID");
  });

  it("rejects duplicate, crosswired, missing, or wrong-kind references", () => {
    const input = fixture("MAIN_RESTORE");
    invalid({ ...input, atom: { ...input.atom, references: [...input.atom.references, input.atom.references[0]!] } }, "REFERENCE_INVALID");
    invalid({ ...input, atom: { ...input.atom, references: input.atom.references.slice(1) } }, "REFERENCE_INVALID");
    invalid({ ...input, atom: { ...input.atom, references: input.atom.references.map((ref) => ref.role === "role:dnrd5:v2:grant" ? { ...ref, target: input.atom.references[1]!.target } : ref) } }, "REFERENCE_INVALID");
    invalid({ ...input, atom: { ...input.atom, references: input.atom.references.map((ref) => ref.role === "role:dnrd5:v2:decision" ? { ...ref, role: "role:dnrd5:v2:purpose" } : ref) } }, "REFERENCE_INVALID");

    const payload = objectFrom(input.payloadBytes);
    const capabilityKeyId = payload.authority.capabilityAtomKeyId as string;
    let duplicateAuthority = withIntent(input, (intent) => {
      intent.authority.grantAtomKeyId = capabilityKeyId;
    });
    duplicateAuthority = withPayload(duplicateAuthority, (candidate) => {
      candidate.authority.grantAtomKeyId = capabilityKeyId;
    });
    duplicateAuthority = {
      ...duplicateAuthority,
      atom: {
        ...duplicateAuthority.atom,
        references: duplicateAuthority.atom.references.map((ref) =>
          ref.role === "role:dnrd5:v2:grant"
            ? { ...ref, target: input.atom.references.find((value) => value.role === "role:dnrd5:v2:capability")!.target }
            : ref,
        ),
      },
    };
    invalid(duplicateAuthority, "REFERENCE_INVALID", "pairwise distinct");

    const wrongTarget = input.state.atoms.find((value) => value.kind === "hswm:dnrd5:v2:study_randomness")!;
    const grantKeyId = payload.authority.grantAtomKeyId as string;
    let wrongKind = withProjection(input, (projection) => {
      projection.command.readSet = projection.command.readSet
        .map((candidate: CanonicalAtomV2Key) => canonicalAtomV2KeyId(candidate) === grantKeyId ? wrongTarget.key : candidate)
        .sort((left: CanonicalAtomV2Key, right: CanonicalAtomV2Key) => canonicalAtomV2KeyId(left).localeCompare(canonicalAtomV2KeyId(right)));
    });
    wrongKind = withIntent(wrongKind, (intent) => {
      intent.authority.grantAtomKeyId = id(wrongTarget);
    });
    wrongKind = withPayload(wrongKind, (candidate) => {
      candidate.authority.grantAtomKeyId = id(wrongTarget);
    });
    wrongKind = {
      ...wrongKind,
      atom: {
        ...wrongKind.atom,
        references: wrongKind.atom.references.map((ref) =>
          ref.role === "role:dnrd5:v2:grant"
            ? { ...ref, target: wrongTarget.key }
            : ref,
        ),
      },
    };
    invalid(wrongKind, "REFERENCE_INVALID", "exact state members");
  });

  it("rejects local candidate/transition replay while preserving the global nonce nonclaim", () => {
    const input = fixture("MAIN_ADMIT");
    invalid(withState(input, (state) => {
      state.atoms.push(input.atom);
    }), "INTENT_INVALID", "reuses an admitted write/transition identity");
    const transitionId = objectFrom(input.commandProjectionBytes).command.transitionId as string;
    invalid(withState(input, (state) => {
      state.acceptedTransitionIds = [transitionId];
    }), "INTENT_INVALID", "reuses an admitted write/transition identity");

    const purposeA = objectFrom(input.payloadBytes).purposeAtomKeyId as string;
    const purposeB = id(input.state.atoms.find((value) => value.kind === "hswm:dnrd5:v2:rollback_decision")!);
    const nonce = "d".repeat(64);
    const uidA = right(dnrd5V2ConsumptionAtomUid("MAIN_ADMIT", nonce, purposeA));
    const uidB = right(dnrd5V2ConsumptionAtomUid("MAIN_ADMIT", nonce, purposeB));
    expect(uidA).not.toBe(uidB);
    expect(DNRD5_V2_CONSUMPTION_TERMINAL).toContain("NOT_CONSUMED");
  });

  it("makes only the explicit structural nonclaim", () => {
    const result = validateDnrd5V2Consumption(fixture("RECEIPT_RESTORE"));
    expect(Either.isRight(result)).toBe(true);
    if (Either.isRight(result)) for (const token of ["NOT_DURABLE_RECOVERY", "NOT_CONSUMED", "NOT_PERMIT", "NOT_CAS", "NOT_OCCURRENCE", "NOT_LEARNING", "NOT_SCIENTIFIC_RESULT"]) expect(result.right.status).toContain(token);
  });
});
