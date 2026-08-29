/**
 * Target/evidence/delta: this is a structural W0-byte-projection instrument,
 * not evidence of an occurrence or learning.  The raw-record positive path is
 * exercised by the RESTORE integration fixture; these focused boundary tests
 * keep this new public-in-package ingress fail-closed for hostile values.
 */
import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"

import {
  DNRD5_V2_BEHAVIORAL_ROOT_V1,
  DNRD5_V2_COMPILED_BEHAVIOR_READSET_V1,
  DNRD5_V2_EXACT_W0_RESTORE_PROJECTION_V1,
  validateDnrd5V2ExactW0RestoreProjection
} from "../src/canonical-atom-v2-dnrd5-v2-exact-w0-restore-projection.js"
import { CanonicalAtomV2DurableRuntime, commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal } from "../src/canonical-atom-v2-durable-runtime.js"
import { submitDnrd5V2RestoreTwoCas } from "../src/canonical-atom-v2-dnrd5-durable-permit.js"
import { canonicalAtomV2StateSha256 } from "../src/canonical-atom-v2-state-journal.js"
import { makeDnrd5V2TwoCasLayer, prepareDnrd5V2RestoreFixture } from "./fixtures/canonical-atom-v2-dnrd5-v2-two-cas.js"

/** Materialize the real raw R1/R2/R3 chain; mutations below never rebuild it. */
const materializedProjection = () => Effect.gen(function* () {
  const fixture = yield* prepareDnrd5V2RestoreFixture()
  yield* submitDnrd5V2RestoreTwoCas(fixture.input)
  const runtime = yield* CanonicalAtomV2DurableRuntime
  yield* commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal(
    runtime,
    fixture.projectionTransition
  )
  const recovered = yield* runtime.snapshot
  const stateSha = canonicalAtomV2StateSha256(recovered.canonical)
  if (Either.isLeft(stateSha)) throw new Error("fixture R3 state hash failed")
  return {
    ...fixture.projectionInput,
    postProjectionState: recovered.canonical,
    postProjectionStateRevision: recovered.canonical.revision,
    postProjectionStateSha256: stateSha.right
  }
})

it("target W0 byte identity; current evidence is structural; delta is NOT_OCCURRENCE/NOT_LEARNING", () => {
  expect(DNRD5_V2_EXACT_W0_RESTORE_PROJECTION_V1).toBe("hswm-dnrd5-v2-exact-w0-restore-projection/v1")
  expect(DNRD5_V2_BEHAVIORAL_ROOT_V1).toBe("hswm-dnrd5-v2-behavioral-root/v1")
  expect(DNRD5_V2_COMPILED_BEHAVIOR_READSET_V1).toBe("hswm-dnrd5-v2-compiled-behavior-readset/v1")
})

it("adversarial ingress: malformed structural witness fails closed before any occurrence or learning claim", () => {
  const result = validateDnrd5V2ExactW0RestoreProjection(null as never)
  expect(Either.isLeft(result)).toBe(true)
  if (Either.isLeft(result)) expect(result.left.code).toBe("INPUT_INVALID")
})

it.effect("fixture-only raw R1/R2 RESTORE then deterministic generic R3 proves an exact W0 structural projection, not execution", () =>
  Effect.gen(function* () {
    const fixture = yield* prepareDnrd5V2RestoreFixture()
    yield* submitDnrd5V2RestoreTwoCas(fixture.input)
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const r3 = yield* commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime, fixture.projectionTransition)
    expect(r3.receipt.record).toEqual(fixture.expectedR3)
    const recovered = yield* runtime.snapshot
    const stateSha = canonicalAtomV2StateSha256(recovered.canonical)
    if (Either.isLeft(stateSha)) throw new Error("fixture R3 state hash failed")
    const result = validateDnrd5V2ExactW0RestoreProjection({
      ...fixture.projectionInput,
      postProjectionState: recovered.canonical,
      postProjectionStateRevision: recovered.canonical.revision,
      postProjectionStateSha256: stateSha.right
    })
    if (Either.isLeft(result)) throw new Error(JSON.stringify(result.left))
    expect(Either.isRight(result)).toBe(true)
    if (Either.isRight(result)) expect(result.right.status).toContain("NOT_OCCURRENCE_NOT_LEARNING")
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer())), 15_000
)

it.effect("adversarial canonical surplus projection field fails closed", () =>
  Effect.gen(function* () {
    const fixture = yield* prepareDnrd5V2RestoreFixture()
    const result = validateDnrd5V2ExactW0RestoreProjection({
      ...fixture.projectionInput,
      projection: { ...fixture.projectionInput.projection, surplus: "canonical-but-forbidden" } as never
    })
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) expect(result.left.code).toBe("PROJECTION_INVALID")
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer())), 15_000
)

it.effect("raw R3 record bytes, descriptor, and envelope mutations each fail the chronology gate", () =>
  materializedProjection().pipe(
    Effect.map((input) => {
      const mutations = [
        { ...input, projectionCommit: { ...input.projectionCommit, recordBytes: Uint8Array.from([...input.projectionCommit.recordBytes, 0]) } },
        { ...input, projectionCommit: { ...input.projectionCommit, recordDescriptor: { ...input.projectionCommit.recordDescriptor, sha256: "0".repeat(64) } } },
        { ...input, projectionCommit: { ...input.projectionCommit, envelope: Uint8Array.from([...input.projectionCommit.envelope, 0]) } }
      ]
      for (const mutated of mutations) {
        const result = validateDnrd5V2ExactW0RestoreProjection(mutated)
        expect(Either.isLeft(result)).toBe(true)
        if (Either.isLeft(result)) expect(result.left.code).toBe("STATE_INVALID")
      }
    }),
    Effect.provide(makeDnrd5V2TwoCasLayer())
  ), 15_000
)

it.effect("raw R3 predecessor and surplus readSet cannot be smuggled past exact chronology", () =>
  materializedProjection().pipe(
    Effect.map((input) => {
      const wrongPredecessor = validateDnrd5V2ExactW0RestoreProjection({
        ...input,
        projectionCommit: {
          ...input.projectionCommit,
          record: { ...input.projectionCommit.record, predecessor: input.projectionCommit.recordDescriptor }
        }
      })
      expect(Either.isLeft(wrongPredecessor)).toBe(true)
      if (Either.isLeft(wrongPredecessor)) expect(wrongPredecessor.left.code).toBe("STATE_INVALID")

      const extra = input.projectionCommit.command.writes[0]!.key
      const surplusReadSet = validateDnrd5V2ExactW0RestoreProjection({
        ...input,
        projectionCommit: {
          ...input.projectionCommit,
          command: { ...input.projectionCommit.command, readSet: [...input.projectionCommit.command.readSet, extra] }
        }
      })
      expect(Either.isLeft(surplusReadSet)).toBe(true)
      if (Either.isLeft(surplusReadSet)) expect(surplusReadSet.left.code).toBe("STATE_INVALID")
    }),
    Effect.provide(makeDnrd5V2TwoCasLayer())
  ), 15_000
)

it.effect("rollback-seal to restore-effect descriptor crosswire is rejected as receipt evidence", () =>
  materializedProjection().pipe(
    Effect.map((input) => {
      const result = validateDnrd5V2ExactW0RestoreProjection({
        ...input,
        rollbackSeal: {
          ...input.rollbackSeal,
          precedingEffect: {
            ...input.rollbackSeal.precedingEffect,
            recordDescriptor: input.projectionCommit.recordDescriptor
          }
        }
      })
      expect(Either.isLeft(result)).toBe(true)
      if (Either.isLeft(result)) expect(result.left.code).toBe("RECEIPT_INVALID")
    }),
    Effect.provide(makeDnrd5V2TwoCasLayer())
  ), 15_000
)

it.effect("immutable behavioural-root bytes that no longer bind their descriptor fail content validation", () =>
  materializedProjection().pipe(
    Effect.map((input) => {
      const corrupted = new Map(input.contentBySha256)
      corrupted.set(input.projection.behavioralRoot.sha256, Uint8Array.of(0))
      const result = validateDnrd5V2ExactW0RestoreProjection({
        ...input,
        contentBySha256: corrupted
      })
      expect(Either.isLeft(result)).toBe(true)
      if (Either.isLeft(result)) expect(result.left.code).toBe("CONTENT_INVALID")
    }),
    Effect.provide(makeDnrd5V2TwoCasLayer())
  ), 15_000
)
