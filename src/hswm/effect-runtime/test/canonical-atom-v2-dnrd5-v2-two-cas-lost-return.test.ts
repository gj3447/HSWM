import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"

import {
  CanonicalAtomV2DurableRuntime,
  recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal
} from "../src/canonical-atom-v2-durable-runtime.js"
import {
  resumeDnrd5V2AdmitTwoCas,
  submitDnrd5V2AdmitTwoCas
} from "../src/canonical-atom-v2-dnrd5-durable-permit.js"
import { canonicalAtomV2KeyId } from "../src/canonical-atom-v2-schema.js"
import type { Dnrd5V2TwoCasPreparedFixture } from "./fixtures/canonical-atom-v2-dnrd5-v2-two-cas.js"
import {
  makeDnrd5V2TwoCasFileLayer,
  makeDnrd5V2TwoCasIoFaultFileLayer,
  prepareDnrd5V2TwoCasFixture
} from "./fixtures/canonical-atom-v2-dnrd5-v2-two-cas.js"

const withTemporaryRoot = <A, E, R>(
  use: (root: string) => Effect.Effect<A, E, R>
): Effect.Effect<A, E, R> => {
  const root = mkdtempSync(join(tmpdir(), "hswm-dnrd5-v2-lost-return-"))
  return use(root).pipe(
    Effect.ensuring(Effect.sync(() => rmSync(root, { recursive: true, force: true })))
  )
}

const assertRaw = (
  fixture: Dnrd5V2TwoCasPreparedFixture,
  phase: "S0" | "R1" | "R2"
) => Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const witness = yield* recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal(
    runtime
  )
  const revision =
    phase === "S0"
      ? fixture.s0Revision
      : phase === "R1"
        ? fixture.s0Revision + 1
        : fixture.s0Revision + 2
  expect(witness.state.canonical.revision).toBe(revision)
  expect(witness.journal).toHaveLength(revision + 1)
  expect(witness.history).toHaveLength(revision)
  expect(witness.journal.at(-1)?.descriptor).toEqual(
    phase === "S0"
      ? witness.state.journalHead
      : phase === "R1"
        ? fixture.expectedR1
        : fixture.expectedR2
  )
  expect(witness.state.journalHead).toEqual(witness.journal.at(-1)?.descriptor)
  if (phase === "R1" || phase === "R2") {
    expect(witness.journal[fixture.s0Revision + 1]?.descriptor).toEqual(
      fixture.expectedR1
    )
  }
  if (phase === "R2") {
    expect(witness.journal[fixture.s0Revision + 2]?.descriptor).toEqual(
      fixture.expectedR2
    )
  }
  return witness
}).pipe(Effect.orDie)

const forgedReceiptInput = (fixture: Dnrd5V2TwoCasPreparedFixture) => {
  const receiptPayloadKeyId = fixture.input.receipt.writePayloads.find(
    ({ atomKeyId }) =>
      atomKeyId !== canonicalAtomV2KeyId(fixture.input.receipt.consumption.atom.key)
  )?.atomKeyId
  if (receiptPayloadKeyId === undefined) {
    throw new Error("fixture lacks receipt payload")
  }
  return {
    ...fixture.input,
    receipt: {
      ...fixture.input.receipt,
      writePayloads: fixture.input.receipt.writePayloads.map((payload) =>
        payload.atomKeyId === receiptPayloadKeyId
          ? { ...payload, bytes: Uint8Array.from([...payload.bytes, 10]) }
          : payload
      )
    }
  }
}

const prepareS0 = () => prepareDnrd5V2TwoCasFixture().pipe(Effect.orDie)

it.effect("recovers exact R1 after CAS1 lost return, then fresh-valid resume writes only R2", () => {
  let injected = 0
  return withTemporaryRoot((root) =>
    prepareS0().pipe(
      Effect.provide(makeDnrd5V2TwoCasFileLayer(root)),
      Effect.flatMap((fixture) =>
        submitDnrd5V2AdmitTwoCas(forgedReceiptInput(fixture)).pipe(
          Effect.either,
          Effect.provide(makeDnrd5V2TwoCasIoFaultFileLayer(root, [{
            point: "journal-readback",
            phase: "after",
            code: "EIO",
            onInjected: () => { injected += 1 }
          }])),
          Effect.map((lostReturn) => ({ fixture, lostReturn }))
        )
      ),
      Effect.flatMap(({ fixture, lostReturn }) =>
        Effect.gen(function* () {
          // The caller may observe publication-unknown or R1-pending; raw
          // recovery, not that return, is the durability oracle.
          expect(Either.isLeft(lostReturn)).toBe(true)
          expect(injected).toBe(1)
          const r1 = yield* assertRaw(fixture, "R1")
          const confirmed = yield* resumeDnrd5V2AdmitTwoCas(fixture.input)
          expect(confirmed).toMatchObject({
            milestone: "CAS2_EXACT_R2_CONFIRMED",
            mainRecord: fixture.expectedR1,
            receiptRecord: fixture.expectedR2
          })
          const r2 = yield* assertRaw(fixture, "R2")
          expect(r2.journal[fixture.s0Revision + 1]?.descriptor).toEqual(
            r1.journal[fixture.s0Revision + 1]?.descriptor
          )
          expect(
            r2.journal.filter(
              (entry) => entry.descriptor.sha256 === fixture.expectedR1.sha256
            )
          ).toHaveLength(1)
        }).pipe(Effect.provide(makeDnrd5V2TwoCasFileLayer(root)))
      )
    )
  )
}, 15_000)

it.effect("fresh recovery confirms exact R2 after CAS2 lost return", () => {
  let injected = 0
  return withTemporaryRoot((root) =>
    prepareS0().pipe(
      Effect.provide(makeDnrd5V2TwoCasFileLayer(root)),
      Effect.flatMap((fixture) =>
        submitDnrd5V2AdmitTwoCas(forgedReceiptInput(fixture)).pipe(
          Effect.either,
          Effect.provide(makeDnrd5V2TwoCasFileLayer(root)),
          Effect.map(() => fixture)
        )
      ),
      Effect.flatMap((fixture) =>
        resumeDnrd5V2AdmitTwoCas(fixture.input).pipe(
          Effect.either,
          Effect.provide(makeDnrd5V2TwoCasIoFaultFileLayer(root, [{
            point: "journal-readback",
            phase: "after",
            code: "EIO",
            onInjected: () => { injected += 1 }
          }])),
          Effect.map((lostReturn) => ({ fixture, lostReturn }))
        )
      ),
      Effect.flatMap(({ fixture, lostReturn }) =>
        Effect.gen(function* () {
          expect(injected).toBe(1)
          expect(Either.isRight(lostReturn)).toBe(true)
          if (Either.isRight(lostReturn)) {
            expect(lostReturn.right).toMatchObject({
              milestone: "CAS2_EXACT_R2_CONFIRMED",
              receiptRecord: fixture.expectedR2
            })
          }
          const raw = yield* assertRaw(fixture, "R2")
          expect(
            raw.journal.filter(
              (entry) => entry.descriptor.sha256 === fixture.expectedR2.sha256
            )
          ).toHaveLength(1)
          const confirmed = yield* resumeDnrd5V2AdmitTwoCas(fixture.input)
          expect(confirmed).toMatchObject({
            milestone: "CAS2_EXACT_R2_CONFIRMED",
            receiptRecord: fixture.expectedR2
          })
          const after = yield* assertRaw(fixture, "R2")
          expect(after.journal).toEqual(raw.journal)
        }).pipe(Effect.provide(makeDnrd5V2TwoCasFileLayer(root)))
      )
    )
  )
}, 15_000)

it.effect("interrupted resume at already exact R2 consumes no publish fault and writes nothing", () => {
  let injected = 0
  return withTemporaryRoot((root) =>
    prepareS0().pipe(
      Effect.provide(makeDnrd5V2TwoCasFileLayer(root)),
      Effect.flatMap((fixture) =>
        submitDnrd5V2AdmitTwoCas(fixture.input).pipe(
          Effect.map(() => fixture),
          Effect.provide(makeDnrd5V2TwoCasFileLayer(root))
        )
      ),
      Effect.flatMap((fixture) =>
        Effect.gen(function* () {
          const before = yield* assertRaw(fixture, "R2")
          const confirmed = yield* resumeDnrd5V2AdmitTwoCas(fixture.input)
          expect(confirmed).toMatchObject({
            milestone: "CAS2_EXACT_R2_CONFIRMED",
            receiptRecord: fixture.expectedR2
          })
          const after = yield* assertRaw(fixture, "R2")
          expect(after.journal).toEqual(before.journal)
          expect(after.history).toEqual(before.history)
          expect(injected).toBe(0)
        }).pipe(
          Effect.provide(makeDnrd5V2TwoCasIoFaultFileLayer(root, [{
            point: "journal-readback",
            phase: "after",
            code: "EIO",
            onInjected: () => { injected += 1 }
          }]))
        )
      )
    )
  )
}, 15_000)
