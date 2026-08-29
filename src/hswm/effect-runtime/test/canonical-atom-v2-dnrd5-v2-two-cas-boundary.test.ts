import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"

import {
  CanonicalAtomV2DurableRuntime,
  makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest
} from "../src/canonical-atom-v2-durable-runtime.js"
import {
  DNRD5_V2_TWO_CAS_ADMIT_V1,
  submitDnrd5V2AdmitTwoCas
} from "../src/canonical-atom-v2-dnrd5-durable-permit.js"
import { canonicalAtomV2SchemaContentBytes } from "../src/canonical-atom-v2-content-bound.js"
import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes
} from "../src/canonical-atom-v2-json.js"
import { makeDnrd5V2CanonicalSchema } from "../src/canonical-atom-v2-dnrd5-v2-schema.js"
import { canonicalAtomV2KeyId } from "../src/canonical-atom-v2-schema.js"
import {
  makeDnrd5V2TwoCasLayer,
  prepareDnrd5V2TwoCasFixture
} from "./fixtures/canonical-atom-v2-dnrd5-v2-two-cas.js"

const schemaBytes = (() => {
  const encoded = canonicalAtomV2SchemaContentBytes(makeDnrd5V2CanonicalSchema())
  if (Either.isLeft(encoded)) throw new Error("cannot construct v2 runtime schema bytes")
  return encoded.right
})()

const layer = () =>
  makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest(
    "journal:dnrd5:v2:two-cas-boundary",
    schemaBytes
  )

it.effect("rejects malformed two-CAS candidates before any durable journal mutation", () =>
  Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const before = yield* runtime.snapshot
    const submitted = yield* submitDnrd5V2AdmitTwoCas({
      _tag: "Dnrd5V2TwoCasAdmitInput",
      contractVersion: DNRD5_V2_TWO_CAS_ADMIT_V1,
      main: {},
      receipt: {}
    }).pipe(Effect.either)
    expect(Either.isLeft(submitted)).toBe(true)
    if (Either.isLeft(submitted)) {
      expect(submitted.left).toMatchObject({
        _tag: "Dnrd5V2TwoCasRecoveryError",
        milestone: "RECOVERY_INDETERMINATE"
      })
    }
    const after = yield* runtime.snapshot
    expect(after.canonical.revision).toBe(before.canonical.revision)
    expect(after.journalHead).toEqual(before.journalHead)
  }).pipe(Effect.provide(layer()))
)

it.effect("recovers exact R1 and R2 before confirming a bounded two-CAS admission", () =>
  Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const fixture = yield* prepareDnrd5V2TwoCasFixture()
    const before = yield* runtime.snapshot
    expect(before.canonical.revision).toBe(fixture.s0Revision)

    const confirmed = yield* submitDnrd5V2AdmitTwoCas(fixture.input)
    expect(confirmed).toMatchObject({
      milestone: "CAS2_EXACT_R2_CONFIRMED",
      mainRecord: fixture.expectedR1,
      receiptRecord: fixture.expectedR2,
      terminal: "NOT_PROVIDER_CALL_NOT_OCCURRENCE_NOT_LEARNING_NOT_EFFICACY"
    })
    expect(Object.isFrozen(confirmed)).toBe(true)
    expect(Object.isFrozen(confirmed.mainRecord)).toBe(true)
    expect(Object.isFrozen(confirmed.receiptRecord)).toBe(true)

    const after = yield* runtime.snapshot
    expect(after.canonical.revision).toBe(fixture.s0Revision + 2)
    expect(after.journalHead).toEqual(fixture.expectedR2)

    const repeated = yield* submitDnrd5V2AdmitTwoCas(fixture.input).pipe(
      Effect.either
    )
    expect(Either.isLeft(repeated)).toBe(true)
    const afterRepeated = yield* runtime.snapshot
    expect(afterRepeated.canonical.revision).toBe(after.canonical.revision)
    expect(afterRepeated.journalHead).toEqual(after.journalHead)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer()))
)

it.effect("leaves exact R1 receipt-pending when a forged receipt is rejected before CAS2", () =>
  Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const fixture = yield* prepareDnrd5V2TwoCasFixture()
    const receiptAtomKeyId = fixture.input.receipt.writePayloads.find(
      ({ atomKeyId }) => atomKeyId !== canonicalAtomV2KeyId(
        fixture.input.receipt.consumption.atom.key
      )
    )
    const forgedPayloads = fixture.input.receipt.writePayloads.map((payload) =>
      payload.atomKeyId === receiptAtomKeyId?.atomKeyId
        ? { ...payload, bytes: Uint8Array.from([...payload.bytes, 10]) }
        : payload
    )
    const submitted = yield* submitDnrd5V2AdmitTwoCas({
      ...fixture.input,
      receipt: { ...fixture.input.receipt, writePayloads: forgedPayloads }
    }).pipe(Effect.either)
    expect(Either.isLeft(submitted)).toBe(true)
    if (Either.isLeft(submitted)) {
      expect(submitted.left).toMatchObject({
        _tag: "Dnrd5V2TwoCasRecoveryError",
        milestone: "CAS1_EXACT_R1_RECEIPT_PENDING"
      })
    }
    const after = yield* runtime.snapshot
    expect(after.canonical.revision).toBe(fixture.s0Revision + 1)
    expect(after.journalHead).toEqual(fixture.expectedR1)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer()))
)

it.effect("rejects a main command authority-header mismatch before CAS1", () =>
  Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const fixture = yield* prepareDnrd5V2TwoCasFixture()
    const before = yield* runtime.snapshot
    const submitted = yield* submitDnrd5V2AdmitTwoCas({
      ...fixture.input,
      main: {
        ...fixture.input.main,
        transition: {
          ...fixture.input.main.transition,
          command: {
            ...fixture.input.main.transition.command,
            actorClaim: "principal:dnrd5:v2:wrong-actor"
          }
        }
      }
    }).pipe(Effect.either)
    expect(Either.isLeft(submitted)).toBe(true)
    if (Either.isLeft(submitted)) {
      expect(submitted.left).toMatchObject({
        _tag: "Dnrd5V2TwoCasRecoveryError",
        milestone: "RECOVERY_INDETERMINATE"
      })
    }
    const after = yield* runtime.snapshot
    expect(after.canonical.revision).toBe(before.canonical.revision)
    expect(after.journalHead).toEqual(before.journalHead)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer()))
)

it.effect("rejects a main/evidence authority crosswire after R1 and before CAS2", () =>
  Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const fixture = yield* prepareDnrd5V2TwoCasFixture()
    const submitted = yield* submitDnrd5V2AdmitTwoCas({
      ...fixture.input,
      receipt: {
        ...fixture.input.receipt,
        authority: {
          ...fixture.input.main.authority,
          // Keep R1 state shape valid; only the authority chain is crosswired.
          state: fixture.input.receipt.authority.state
        }
      }
    }).pipe(Effect.either)
    expect(Either.isLeft(submitted)).toBe(true)
    if (Either.isLeft(submitted)) {
      expect(submitted.left).toMatchObject({
        _tag: "Dnrd5V2TwoCasRecoveryError",
        milestone: "CAS1_EXACT_R1_RECEIPT_PENDING"
      })
    }
    const after = yield* runtime.snapshot
    expect(after.canonical.revision).toBe(fixture.s0Revision + 1)
    expect(after.journalHead).toEqual(fixture.expectedR1)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer()))
)

it.effect("rejects reuse of the main capability nonce by a receipt candidate before CAS1", () =>
  Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const fixture = yield* prepareDnrd5V2TwoCasFixture()
    const decodedReceipt = decodeCanonicalJsonBytes(
      fixture.input.receipt.consumption.payloadBytes
    )
    expect(Either.isRight(decodedReceipt)).toBe(true)
    if (Either.isLeft(decodedReceipt)) return
    const decodedMain = decodeCanonicalJsonBytes(
      fixture.input.main.consumption.payloadBytes
    )
    expect(Either.isRight(decodedMain)).toBe(true)
    if (Either.isLeft(decodedMain)) return
    const reusedNoncePayload = canonicalJsonBytes({
      ...(decodedReceipt.right as Record<string, unknown>),
      capabilityNonceSha256: (decodedMain.right as Record<string, unknown>)["capabilityNonceSha256"]
    })
    expect(Either.isRight(reusedNoncePayload)).toBe(true)
    if (Either.isLeft(reusedNoncePayload)) return

    const before = yield* runtime.snapshot
    const submitted = yield* submitDnrd5V2AdmitTwoCas({
      ...fixture.input,
      receipt: {
        ...fixture.input.receipt,
        consumption: {
          ...fixture.input.receipt.consumption,
          // The phase remains RECEIPT_ADMIT: this is specifically a nonce collision.
          payloadBytes: reusedNoncePayload.right
        }
      }
    }).pipe(Effect.either)
    expect(Either.isLeft(submitted)).toBe(true)
    if (Either.isLeft(submitted)) {
      expect(submitted.left).toMatchObject({
        _tag: "Dnrd5V2TwoCasRecoveryError",
        milestone: "RECOVERY_INDETERMINATE"
      })
    }
    const after = yield* runtime.snapshot
    expect(after.canonical.revision).toBe(before.canonical.revision)
    expect(after.journalHead).toEqual(before.journalHead)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer()))
)

it.effect("rejects generic-schema-valid main cross-wiring before CAS1", () =>
  Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const fixture = yield* prepareDnrd5V2TwoCasFixture({
      mainEffectGrammarCrosswire: true
    })
    const before = yield* runtime.snapshot
    const submitted = yield* submitDnrd5V2AdmitTwoCas(fixture.input).pipe(
      Effect.either
    )
    expect(Either.isLeft(submitted)).toBe(true)
    if (Either.isLeft(submitted)) {
      expect(submitted.left).toMatchObject({
        _tag: "Dnrd5V2TwoCasRecoveryError",
        milestone: "RECOVERY_INDETERMINATE"
      })
      expect(submitted.left.detail).toContain(
        "main effect failed pre-CAS DNRD grammar: GRAMMAR_INVALID"
      )
    }
    const after = yield* runtime.snapshot
    expect(after.canonical.revision).toBe(before.canonical.revision)
    expect(after.journalHead).toEqual(before.journalHead)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer()))
)

it.effect("rejects generic-schema-valid receipt cross-wiring before CAS2", () =>
  Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const fixture = yield* prepareDnrd5V2TwoCasFixture({
      receiptGrammarCrosswire: true
    })
    const submitted = yield* submitDnrd5V2AdmitTwoCas(fixture.input).pipe(
      Effect.either
    )
    expect(Either.isLeft(submitted)).toBe(true)
    if (Either.isLeft(submitted)) {
      expect(submitted.left).toMatchObject({
        _tag: "Dnrd5V2TwoCasRecoveryError",
        milestone: "CAS1_EXACT_R1_RECEIPT_PENDING"
      })
      expect(submitted.left.detail).toContain(
        "receipt failed pre-CAS DNRD grammar: GRAMMAR_INVALID"
      )
    }
    const after = yield* runtime.snapshot
    expect(after.canonical.revision).toBe(fixture.s0Revision + 1)
    expect(after.journalHead).toEqual(fixture.expectedR1)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer()))
)
