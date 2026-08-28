/** Pure local consumption-candidate byte contract; it is not recovery, authority, Permit, CAS, occurrence, learning, or a scientific result. */
import { createHash } from "node:crypto";
import { Data, Either, Schema } from "effect";
import {
  validateCanonicalAtomV2State,
  type CanonicalAtomV2State,
} from "./canonical-atom-v2-domain.js";
import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes,
} from "./canonical-atom-v2-json.js";
import {
  CanonicalAtomV2Schema,
  CommitCanonicalAtomsV2CommandSchema,
  canonicalAtomV2KeyId,
  type CanonicalAtomV2,
} from "./canonical-atom-v2-schema.js";
import {
  canonicalAtomV2StateSha256,
  HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE,
} from "./canonical-atom-v2-state-journal.js";
import {
  DNRD5_V2_REFERENCE_TYPE,
  DNRD5_V2_SCHEMA_VERSION,
  makeDnrd5V2CanonicalSchema,
} from "./canonical-atom-v2-dnrd5-v2-schema.js";
import { validateDnrd5V2AtomicBatchChronology } from "./canonical-atom-v2-dnrd5-v2-batch-chronology.js";

export const DNRD5_V2_CONSUMPTION_PAYLOAD_V1 =
  "hswm-dnrd5-v2-consumption-payload/v1" as const;
export const DNRD5_V2_CONSUMPTION_COMMAND_INTENT_V1 =
  "hswm-dnrd5-v2-consumption-command-intent/v1" as const;
export const DNRD5_V2_CONSUMPTION_COMMAND_PROJECTION_V1 =
  "hswm-dnrd5-v2-consumption-command-projection/v1" as const;
export const DNRD5_V2_CONSUMPTION_COMMAND_INTENT_MEDIA_TYPE =
  "application/vnd.hswm.dnrd5.v2.consumption-command-intent-v1+json" as const;
export const DNRD5_V2_CAPABILITY_CONSUMPTION_MEDIA_TYPE =
  "application/vnd.hswm.dnrd5.v2.capability-consumption-v1+json" as const;
export const DNRD5_V2_EVIDENCE_SEAL_CONSUMPTION_MEDIA_TYPE =
  "application/vnd.hswm.dnrd5.v2.evidence-seal-consumption-v1+json" as const;
export const DNRD5_V2_CONSUMPTION_TERMINAL =
  "STRUCTURAL_CANDIDATE_NOT_DURABLE_RECOVERY_NOT_CONSUMED_NOT_PERMIT_NOT_CAS_NOT_OCCURRENCE_NOT_LEARNING_NOT_SCIENTIFIC_RESULT" as const;
export type Dnrd5V2ConsumptionPhase =
  "MAIN_ADMIT" | "MAIN_RESTORE" | "RECEIPT_ADMIT" | "RECEIPT_RESTORE";
const Phase = Schema.Literal(
  "MAIN_ADMIT",
  "MAIN_RESTORE",
  "RECEIPT_ADMIT",
  "RECEIPT_RESTORE",
);
const Sha = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/));
const Key = Schema.String.pipe(Schema.minLength(7), Schema.maxLength(1027));
const Id = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/),
);
const Int = Schema.Number.pipe(
  Schema.int(),
  Schema.nonNegative(),
  Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER),
);
const Time = Schema.String.pipe(
  Schema.pattern(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/),
);
const Media = Schema.String.pipe(
  Schema.pattern(
    /^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*\/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$/,
  ),
);
const Descriptor = Schema.Struct({
  mediaType: Media,
  byteLength: Int,
  sha256: Sha,
});
const Authority = Schema.Struct({
  grantAtomKeyId: Key,
  capabilityAtomKeyId: Key,
  revocationAtomKeyId: Key,
});
const Head = Schema.Struct({
  mediaType: Schema.Literal(HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE),
  byteLength: Int,
  sha256: Sha,
});
const Snapshot = Schema.Struct({
  stateRevision: Int,
  stateSha256: Sha,
  journalLineageId: Id,
  journalHead: Head,
});
/** Exact cycle-free projection: it commits command header/readset/non-consumption writes, intentionally excluding consumption content. */
export const Dnrd5V2ConsumptionCommandProjectionSchema = Schema.Struct({
  contractVersion: Schema.Literal(DNRD5_V2_CONSUMPTION_COMMAND_PROJECTION_V1),
  phase: Phase,
  consumptionAtomKeyId: Key,
  command: CommitCanonicalAtomsV2CommandSchema,
});
export const Dnrd5V2ConsumptionCommandIntentSchema = Schema.Struct({
  contractVersion: Schema.Literal(DNRD5_V2_CONSUMPTION_COMMAND_INTENT_V1),
  phase: Phase,
  capabilityNonceSha256: Sha,
  purposeAtomKeyId: Key,
  authority: Authority,
  authorizationSnapshot: Snapshot,
  evaluatedAt: Time,
  commandProjectionSha256: Sha,
});
export const Dnrd5V2ConsumptionPayloadSchema = Schema.Struct({
  _tag: Schema.Literal("Dnrd5V2ConsumptionPayload"),
  contractVersion: Schema.Literal(DNRD5_V2_CONSUMPTION_PAYLOAD_V1),
  phase: Phase,
  capabilityNonceSha256: Sha,
  purposeAtomKeyId: Key,
  authority: Authority,
  authorizationSnapshot: Snapshot,
  commandIntent: Descriptor,
  evaluatedAt: Time,
  terminal: Schema.Literal(DNRD5_V2_CONSUMPTION_TERMINAL),
});
export type Dnrd5V2ConsumptionPayload = Schema.Schema.Type<
  typeof Dnrd5V2ConsumptionPayloadSchema
>;
export interface Dnrd5V2ConsumptionInput {
  readonly _tag: "Dnrd5V2ConsumptionInput";
  readonly payloadBytes: Uint8Array;
  readonly commandIntentBytes: Uint8Array;
  readonly commandProjectionBytes: Uint8Array;
  readonly atom: CanonicalAtomV2;
  /** Caller-supplied; recovery is established elsewhere. */ readonly authorizationSnapshot: Schema.Schema.Type<
    typeof Snapshot
  >;
  readonly state: CanonicalAtomV2State;
}
export interface Dnrd5V2ConsumptionValidated {
  readonly status: typeof DNRD5_V2_CONSUMPTION_TERMINAL;
  readonly phase: Dnrd5V2ConsumptionPhase;
  readonly atomUid: string;
  readonly atomKeyId: string;
  readonly purposeAtomKeyId: string;
  readonly authority: {
    readonly grantAtomKeyId: string;
    readonly capabilityAtomKeyId: string;
    readonly revocationAtomKeyId: string;
  };
  readonly capabilityNonceSha256: string;
  readonly evaluatedAt: string;
  readonly authorizationSnapshot: {
    readonly stateRevision: number;
    readonly stateSha256: string;
    readonly journalLineageId: string;
    readonly journalHeadSha256: string;
  };
  readonly transitionId: string;
  readonly companionAtomKeyId: string;
  readonly commandProjectionSha256: string;
  readonly topologySha256: string;
}
export type Dnrd5V2ConsumptionErrorCode =
  | "INPUT_INVALID"
  | "PAYLOAD_INVALID"
  | "CANONICAL_ENCODING_INVALID"
  | "DESCRIPTOR_MISMATCH"
  | "INTENT_INVALID"
  | "SNAPSHOT_MISMATCH"
  | "STATE_INVALID"
  | "ATOM_INVALID"
  | "REFERENCE_INVALID"
  | "UID_INVALID"
  | "TIME_INVALID";
export class Dnrd5V2ConsumptionError extends Data.TaggedError(
  "Dnrd5V2ConsumptionError",
)<{ readonly code: Dnrd5V2ConsumptionErrorCode; readonly detail: string }> {}
const fail = (
  code: Dnrd5V2ConsumptionErrorCode,
  detail: string,
): Either.Either<never, Dnrd5V2ConsumptionError> =>
  Either.left(new Dnrd5V2ConsumptionError({ code, detail }));
const hash = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");
const equal = (a: object, b: object) => JSON.stringify(a) === JSON.stringify(b);
const plain = (value: unknown): value is object =>
  typeof value === "object" &&
  value !== null &&
  !Array.isArray(value) &&
  Object.getPrototypeOf(value) === Object.prototype;
const keys = (value: object, fields: ReadonlyArray<string>) =>
  Object.keys(value).length === fields.length &&
  fields.every((field) => Object.prototype.hasOwnProperty.call(value, field));
const instant = (value: string) =>
  Number.isFinite(Date.parse(value)) &&
  new Date(Date.parse(value)).toISOString() === value;
const keyId = (value: string) => {
  const p = value.split("|");
  return (
    p.length === 4 &&
    p
      .slice(0, 3)
      .every((part) => /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/.test(part)) &&
    /^(?:0|[1-9]\d*)$/.test(p[3]!) &&
    Number.isSafeInteger(Number(p[3]))
  );
};
const sameBytes = (a: Uint8Array, b: Uint8Array) =>
  a.byteLength === b.byteLength && a.every((v, i) => v === b[i]);
const decode = <A>(
  schema: Schema.Schema<A>,
  value: unknown,
  code: Dnrd5V2ConsumptionErrorCode,
) => {
  const out = Schema.decodeUnknownEither(schema, { onExcessProperty: "error" })(
    value,
  );
  return Either.isLeft(out)
    ? fail(code, "shape is not exact")
    : Either.right(out.right);
};
const freeze = <A>(value: A): A => {
  if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    for (const x of Object.values(value)) freeze(x);
  }
  return value;
};
export const dnrd5V2ConsumptionAtomUid = (
  phase: unknown,
  nonce: string,
  purpose: string,
): Either.Either<string, Dnrd5V2ConsumptionError> => {
  if (
    !(
      phase === "MAIN_ADMIT" ||
      phase === "MAIN_RESTORE" ||
      phase === "RECEIPT_ADMIT" ||
      phase === "RECEIPT_RESTORE"
    ) ||
    !/^[0-9a-f]{64}$/.test(nonce) ||
    !keyId(purpose)
  )
    return fail("UID_INVALID", "phase, nonce, or purpose is invalid");
  const encoded = canonicalJsonBytes({
    contractVersion: DNRD5_V2_CONSUMPTION_PAYLOAD_V1,
    domain: "hswm:dnrd5:v2:consumption-atom-uid/v1",
    phase,
    capabilityNonceSha256: nonce,
    purposeAtomKeyId: purpose,
  });
  return Either.isLeft(encoded)
    ? fail("CANONICAL_ENCODING_INVALID", encoded.left.detail)
    : Either.right(`dnrd5-v2-consume:${hash(encoded.right)}`);
};
const need = (phase: Dnrd5V2ConsumptionPhase) =>
  phase === "MAIN_ADMIT"
    ? ([
        "hswm:dnrd5:v2:capability_consumption",
        "owner:dnrd5:v2:capability_consumption_custodian",
        "role:dnrd5:v2:decision",
        "hswm:dnrd5:v2:revision_admission_decision",
        DNRD5_V2_CAPABILITY_CONSUMPTION_MEDIA_TYPE,
      ] as const)
    : phase === "MAIN_RESTORE"
      ? ([
          "hswm:dnrd5:v2:capability_consumption",
          "owner:dnrd5:v2:capability_consumption_custodian",
          "role:dnrd5:v2:decision",
          "hswm:dnrd5:v2:rollback_decision",
          DNRD5_V2_CAPABILITY_CONSUMPTION_MEDIA_TYPE,
        ] as const)
      : phase === "RECEIPT_ADMIT"
        ? ([
            "hswm:dnrd5:v2:evidence_seal_consumption",
            "owner:dnrd5:v2:evidence_seal_consumption_custodian",
            "role:dnrd5:v2:purpose",
            "hswm:dnrd5:v2:revision_admission_decision",
            DNRD5_V2_EVIDENCE_SEAL_CONSUMPTION_MEDIA_TYPE,
          ] as const)
        : ([
            "hswm:dnrd5:v2:evidence_seal_consumption",
            "owner:dnrd5:v2:evidence_seal_consumption_custodian",
            "role:dnrd5:v2:purpose",
            "hswm:dnrd5:v2:rollback_decision",
            DNRD5_V2_EVIDENCE_SEAL_CONSUMPTION_MEDIA_TYPE,
          ] as const);

export const validateDnrd5V2Consumption = (
  input: unknown,
): Either.Either<Dnrd5V2ConsumptionValidated, Dnrd5V2ConsumptionError> => {
  try {
    if (
      !plain(input) ||
      !keys(input, [
        "_tag",
        "payloadBytes",
        "commandIntentBytes",
        "commandProjectionBytes",
        "atom",
        "authorizationSnapshot",
        "state",
      ])
    )
      return fail("INPUT_INVALID", "input shape is not exact");
    const i = input as Partial<Dnrd5V2ConsumptionInput>;
    if (
      i._tag !== "Dnrd5V2ConsumptionInput" ||
      !(i.payloadBytes instanceof Uint8Array) ||
      !(i.commandIntentBytes instanceof Uint8Array) ||
      !(i.commandProjectionBytes instanceof Uint8Array)
    )
      return fail("INPUT_INVALID", "bytes missing");
    const raw = decodeCanonicalJsonBytes(i.payloadBytes);
    if (Either.isLeft(raw))
      return fail(
        "CANONICAL_ENCODING_INVALID",
        "payload is not canonical JSON",
      );
    const payload = decode(
      Dnrd5V2ConsumptionPayloadSchema,
      raw.right,
      "PAYLOAD_INVALID",
    );
    if (Either.isLeft(payload))
      return fail(payload.left.code, payload.left.detail);
    const encoded = canonicalJsonBytes(payload.right);
    if (Either.isLeft(encoded) || !sameBytes(encoded.right, i.payloadBytes))
      return fail("CANONICAL_ENCODING_INVALID", "payload bytes drift");
    const authorityKeys = [
      payload.right.purposeAtomKeyId,
      payload.right.authority.grantAtomKeyId,
      payload.right.authority.capabilityAtomKeyId,
      payload.right.authority.revocationAtomKeyId,
    ];
    if (!instant(payload.right.evaluatedAt))
      return fail("TIME_INVALID", "evaluation time is not a canonical instant");
    if (
      !authorityKeys.every(keyId) ||
      new Set(authorityKeys).size !== authorityKeys.length
    )
      return fail(
        "REFERENCE_INVALID",
        "authority and purpose keys must be canonical and pairwise distinct",
      );
    const snapshot = decode(
      Snapshot,
      i.authorizationSnapshot,
      "SNAPSHOT_MISMATCH",
    );
    if (
      Either.isLeft(snapshot) ||
      !keys(i.authorizationSnapshot as object, [
        "stateRevision",
        "stateSha256",
        "journalLineageId",
        "journalHead",
      ]) ||
      !equal(snapshot.right, payload.right.authorizationSnapshot)
    )
      return fail("SNAPSHOT_MISMATCH", "caller-supplied snapshot differs");
    const state = validateCanonicalAtomV2State(
      makeDnrd5V2CanonicalSchema(),
      i.state,
    );
    if (
      Either.isLeft(state) ||
      !keys(i.state as object, [
        "schemaVersion",
        "revision",
        "bootstrapClosed",
        "atoms",
        "acceptedTransitionIds",
      ])
    )
      return fail("STATE_INVALID", "caller-supplied state invalid");
    const stateHash = canonicalAtomV2StateSha256(state.right);
    if (
      Either.isLeft(stateHash) ||
      state.right.revision !== snapshot.right.stateRevision ||
      stateHash.right !== snapshot.right.stateSha256
    )
      return fail("SNAPSHOT_MISMATCH", "state does not bind snapshot");
    const intentRaw = decodeCanonicalJsonBytes(i.commandIntentBytes);
    if (Either.isLeft(intentRaw))
      return fail("CANONICAL_ENCODING_INVALID", "intent is not canonical JSON");
    const intent = decode(
      Dnrd5V2ConsumptionCommandIntentSchema,
      intentRaw.right,
      "INTENT_INVALID",
    );
    if (Either.isLeft(intent))
      return fail(intent.left.code, intent.left.detail);
    const intentBytes = canonicalJsonBytes(intent.right);
    if (
      Either.isLeft(intentBytes) ||
      !sameBytes(intentBytes.right, i.commandIntentBytes) ||
      !equal(payload.right.commandIntent, {
        mediaType: DNRD5_V2_CONSUMPTION_COMMAND_INTENT_MEDIA_TYPE,
        byteLength: i.commandIntentBytes.byteLength,
        sha256: hash(i.commandIntentBytes),
      })
    )
      return fail("DESCRIPTOR_MISMATCH", "intent descriptor drift");
    if (
      intent.right.phase !== payload.right.phase ||
      intent.right.capabilityNonceSha256 !==
        payload.right.capabilityNonceSha256 ||
      intent.right.purposeAtomKeyId !== payload.right.purposeAtomKeyId ||
      !equal(intent.right.authority, payload.right.authority) ||
      !equal(
        intent.right.authorizationSnapshot,
        payload.right.authorizationSnapshot,
      ) ||
      intent.right.evaluatedAt !== payload.right.evaluatedAt
    )
      return fail("INTENT_INVALID", "intent does not bind payload");
    const atom = decode(CanonicalAtomV2Schema, i.atom, "ATOM_INVALID");
    if (
      Either.isLeft(atom) ||
      atom.right.key.schemaVersion !== DNRD5_V2_SCHEMA_VERSION ||
      atom.right.key.revisionId !== 0
    )
      return fail("ATOM_INVALID", "atom not v2 singleton");
    const projectionRaw = decodeCanonicalJsonBytes(i.commandProjectionBytes);
    if (Either.isLeft(projectionRaw))
      return fail(
        "CANONICAL_ENCODING_INVALID",
        "projection is not canonical JSON",
      );
    const projection = decode(
      Dnrd5V2ConsumptionCommandProjectionSchema,
      projectionRaw.right,
      "INTENT_INVALID",
    );
    if (Either.isLeft(projection))
      return fail(projection.left.code, projection.left.detail);
    const projectionBytes = canonicalJsonBytes(projection.right);
    if (
      Either.isLeft(projectionBytes) ||
      !sameBytes(projectionBytes.right, i.commandProjectionBytes) ||
      intent.right.commandProjectionSha256 !== hash(i.commandProjectionBytes)
    )
      return fail("INTENT_INVALID", "projection digest/bytes drift");
    const projectionCommand = projection.right.command;
    const projectionReadSet =
      projectionCommand.readSet.map(canonicalAtomV2KeyId);
    const projectionWrite = projectionCommand.writes[0];
    const companionRole =
      payload.right.phase === "MAIN_ADMIT"
        ? "role:dnrd5:v2:effect-consumption"
        : payload.right.phase === "MAIN_RESTORE"
          ? "role:dnrd5:v2:consumption"
          : "role:dnrd5:v2:evidence-consumption";
    if (
      projection.right.phase !== payload.right.phase ||
      projection.right.consumptionAtomKeyId !==
        canonicalAtomV2KeyId(atom.right.key) ||
      projectionCommand.schemaVersion !== DNRD5_V2_SCHEMA_VERSION ||
      projectionCommand.expectedStateRevision !==
        payload.right.authorizationSnapshot.stateRevision ||
      projectionCommand.decidedAt !== payload.right.evaluatedAt ||
      projectionCommand.traceRef !== null ||
      projectionCommand.writes.length !== 1 ||
      projectionWrite === undefined ||
      projectionWrite.kind !==
        (payload.right.phase === "MAIN_ADMIT"
          ? "hswm:dnrd5:v2:macro_disposition"
          : payload.right.phase === "MAIN_RESTORE"
            ? "hswm:dnrd5:v2:restore_transaction"
            : payload.right.phase === "RECEIPT_ADMIT"
              ? "hswm:dnrd5:v2:revision_transition_receipt"
              : "hswm:dnrd5:v2:rollback_transition_receipt") ||
      projectionWrite.references.filter(
        (ref) =>
          ref.referenceType === DNRD5_V2_REFERENCE_TYPE &&
          ref.role === companionRole &&
          canonicalAtomV2KeyId(ref.target) ===
            canonicalAtomV2KeyId(atom.right.key),
      ).length !== 1 ||
      new Set(projectionReadSet).size !== projectionReadSet.length ||
      projectionCommand.writes.some(
        (write) =>
          canonicalAtomV2KeyId(write.key) ===
          projection.right.consumptionAtomKeyId,
      )
    )
      return fail(
        "INTENT_INVALID",
        "projection is not exact cycle-free command commitment",
      );
    const [kind, owner, purposeRole, purposeKind, media] = need(
      payload.right.phase,
    );
    // This is only exact-candidate replay detection inside the supplied state.
    // Global or cross-purpose nonce consumption requires the later durable
    // authority/CAS dispatcher and is deliberately not claimed here.
    if (
      atom.right.kind !== kind ||
      atom.right.responsibilityOwner !== owner ||
      atom.right.content.mediaType !== media ||
      atom.right.content.byteLength !== i.payloadBytes.byteLength ||
      atom.right.content.sha256 !== hash(i.payloadBytes) ||
      atom.right.provenance.mode !== "DERIVATION" ||
      atom.right.provenance.sourceRef === null ||
      canonicalAtomV2KeyId(atom.right.provenance.sourceRef) !==
        payload.right.purposeAtomKeyId ||
      atom.right.provenance.evidenceSha256 !== hash(i.commandProjectionBytes)
    )
      return fail("ATOM_INVALID", "atom descriptor/provenance invalid");
    const uid = dnrd5V2ConsumptionAtomUid(
      payload.right.phase,
      payload.right.capabilityNonceSha256,
      payload.right.purposeAtomKeyId,
    );
    if (Either.isLeft(uid) || atom.right.key.atomUid !== uid.right)
      return fail("UID_INVALID", "UID drift");
    const members = new Map(
      state.right.atoms.map((a) => [canonicalAtomV2KeyId(a.key), a] as const),
    );
    if (
      members.get(payload.right.authority.grantAtomKeyId)?.kind !==
        "hswm:dnrd5:v2:grant_snapshot" ||
      members.get(payload.right.authority.capabilityAtomKeyId)?.kind !==
        "hswm:dnrd5:v2:capability_issuance" ||
      members.get(payload.right.authority.revocationAtomKeyId)?.kind !==
        "hswm:dnrd5:v2:revocation_status" ||
      members.get(payload.right.purposeAtomKeyId)?.kind !== purposeKind
    )
      return fail(
        "REFERENCE_INVALID",
        "authority/purpose not exact state members",
      );
    const refs = new Map(atom.right.references.map((r) => [r.role, r]));
    const ref = (role: string, target: string) => {
      const x = refs.get(role);
      return (
        x !== undefined &&
        x.referenceType === DNRD5_V2_REFERENCE_TYPE &&
        canonicalAtomV2KeyId(x.target) === target
      );
    };
    if (
      refs.size !== 4 ||
      atom.right.references.length !== 4 ||
      !ref("role:dnrd5:v2:grant", payload.right.authority.grantAtomKeyId) ||
      !ref(
        "role:dnrd5:v2:capability",
        payload.right.authority.capabilityAtomKeyId,
      ) ||
      !ref(
        "role:dnrd5:v2:revocation",
        payload.right.authority.revocationAtomKeyId,
      ) ||
      !ref(purposeRole, payload.right.purposeAtomKeyId)
    )
      return fail("REFERENCE_INVALID", "typed refs invalid");
    const writeIds = new Set([
      canonicalAtomV2KeyId(atom.right.key),
      canonicalAtomV2KeyId(projectionWrite.key),
    ]);
    const exactExternalReads = [atom.right, projectionWrite]
      .flatMap((write) => [
        ...write.references.map((reference) =>
          canonicalAtomV2KeyId(reference.target),
        ),
        ...(write.provenance.sourceRef === null
          ? []
          : [canonicalAtomV2KeyId(write.provenance.sourceRef)]),
      ])
      .filter((id) => !writeIds.has(id));
    const expectedReadSet = [...new Set(exactExternalReads)].sort();
    const actualReadSet = [...projectionReadSet].sort();
    if (
      expectedReadSet.length !== actualReadSet.length ||
      expectedReadSet.some((id, index) => id !== actualReadSet[index])
    )
      return fail(
        "INTENT_INVALID",
        "projection read set is not the exact external dependency set",
      );
    if (
      projectionReadSet.some((id) => !members.has(id)) ||
      members.has(canonicalAtomV2KeyId(atom.right.key)) ||
      members.has(canonicalAtomV2KeyId(projectionWrite.key)) ||
      state.right.acceptedTransitionIds.includes(projectionCommand.transitionId)
    )
      return fail(
        "INTENT_INVALID",
        "projection reads a missing atom or reuses an admitted write/transition identity",
      );
    const topology = validateDnrd5V2AtomicBatchChronology(
      makeDnrd5V2CanonicalSchema(),
      state.right,
      {
        ...projectionCommand,
        writes: [atom.right, projectionWrite],
      },
    );
    if (Either.isLeft(topology))
      return fail(
        "INTENT_INVALID",
        `reconstructed two-write command is invalid: ${topology.left.code}: ${topology.left.detail}`,
      );
    return Either.right(
      freeze({
        status: DNRD5_V2_CONSUMPTION_TERMINAL,
        phase: payload.right.phase,
        atomUid: uid.right,
        atomKeyId: canonicalAtomV2KeyId(atom.right.key),
        purposeAtomKeyId: payload.right.purposeAtomKeyId,
        authority: {
          grantAtomKeyId: payload.right.authority.grantAtomKeyId,
          capabilityAtomKeyId: payload.right.authority.capabilityAtomKeyId,
          revocationAtomKeyId: payload.right.authority.revocationAtomKeyId,
        },
        capabilityNonceSha256: payload.right.capabilityNonceSha256,
        evaluatedAt: payload.right.evaluatedAt,
        authorizationSnapshot: {
          stateRevision: snapshot.right.stateRevision,
          stateSha256: snapshot.right.stateSha256,
          journalLineageId: snapshot.right.journalLineageId,
          journalHeadSha256: snapshot.right.journalHead.sha256,
        },
        transitionId: projectionCommand.transitionId,
        companionAtomKeyId: canonicalAtomV2KeyId(projectionWrite.key),
        commandProjectionSha256: hash(i.commandProjectionBytes),
        topologySha256: topology.right.topologySha256,
      }),
    );
  } catch {
    return fail("INPUT_INVALID", "unexpected malformed input");
  }
};
