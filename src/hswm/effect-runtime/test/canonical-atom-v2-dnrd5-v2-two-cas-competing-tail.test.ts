import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"

import {
  CanonicalAtomV2DurableRuntime,
  commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal,
  recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal
} from "../src/canonical-atom-v2-durable-runtime.js"
import { resumeDnrd5V2AdmitTwoCas, submitDnrd5V2AdmitTwoCas } from "../src/canonical-atom-v2-dnrd5-durable-permit.js"
import type { CanonicalAtomV2ContentDescriptor } from "../src/canonical-atom-v2-content.js"
import {
  makeDnrd5V2TwoCasFileLayer,
  makeDnrd5V2TwoCasLayer,
  prepareDnrd5V2TwoCasFixture
} from "./fixtures/canonical-atom-v2-dnrd5-v2-two-cas.js"

const withTemporaryRoot = <A, E, R>(
  use: (root: string) => Effect.Effect<A, E, R>
): Effect.Effect<A, E, R> => {
  const root = mkdtempSync(join(tmpdir(), "hswm-dnrd5-v2-competing-tail-"))
  return use(root).pipe(
    Effect.ensuring(Effect.sync(() => rmSync(root, { recursive: true, force: true })))
  )
}

const normalFixture = () =>
  prepareDnrd5V2TwoCasFixture().pipe(
    Effect.provide(makeDnrd5V2TwoCasLayer()),
    Effect.orDie
  )

const assertRawTail = (
  revision: number,
  descriptor: CanonicalAtomV2ContentDescriptor
) => Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const witness = yield* recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal(
    runtime
  )
  expect(witness.state.canonical.revision).toBe(revision)
  expect(witness.journal).toHaveLength(revision + 1)
  expect(witness.history).toHaveLength(revision)
  expect(witness.state.journalHead).toEqual(descriptor)
  expect(witness.journal.at(-1)?.descriptor).toEqual(descriptor)
  return witness
}).pipe(Effect.orDie)

it.effect("rejects a generic-schema-valid but DNRD-invalid competing R1 without CAS2", () =>
  withTemporaryRoot((root) =>
    Effect.gen(function* () {
      const target = yield* prepareDnrd5V2TwoCasFixture({
        mainEffectGrammarCrosswire: true
      })
      const runtime = yield* CanonicalAtomV2DurableRuntime
      const competing = yield* commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal(
        runtime,
        target.input.main.transition
      )
      const competingR1 = competing.receipt.record
      const normal = yield* normalFixture()
      expect(normal.s0Revision).toBe(target.s0Revision)
      expect(competingR1).not.toEqual(normal.expectedR1)
      expect(competingR1.sha256).not.toBe(normal.expectedR1.sha256)
      const before = yield* assertRawTail(
        target.s0Revision + 1,
        competingR1
      )
      expect(
        before.journal.filter(
          (entry) => entry.descriptor.sha256 === competingR1.sha256
        )
      ).toHaveLength(1)
      expect(
        before.journal.some(
          (entry) => entry.descriptor.sha256 === normal.expectedR1.sha256
        )
      ).toBe(false)
      const resumed = yield* resumeDnrd5V2AdmitTwoCas(normal.input).pipe(
        Effect.either
      )
      expect(Either.isLeft(resumed)).toBe(true)
      const after = yield* assertRawTail(
        target.s0Revision + 1,
        competingR1
      )
      expect(after.journal).toEqual(before.journal)
      expect(after.history).toEqual(before.history)
      expect(after.journal).toHaveLength(target.s0Revision + 2)
    }).pipe(Effect.provide(makeDnrd5V2TwoCasFileLayer(root)), Effect.orDie)
  ), 15_000
)

it.effect("rejects a generic-schema-valid but DNRD-invalid competing R2 without mutation", () =>
  withTemporaryRoot((root) =>
    Effect.gen(function* () {
      const target = yield* prepareDnrd5V2TwoCasFixture({
        receiptGrammarCrosswire: true
      })
      const stopped = yield* submitDnrd5V2AdmitTwoCas(target.input).pipe(
        Effect.either
      )
      expect(Either.isLeft(stopped)).toBe(true)
      const runtime = yield* CanonicalAtomV2DurableRuntime
      const competing = yield* commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal(
        runtime,
        target.input.receipt.transition
      )
      const competingR2 = competing.receipt.record
      const normal = yield* normalFixture()
      expect(normal.s0Revision).toBe(target.s0Revision)
      expect(competingR2).not.toEqual(normal.expectedR2)
      expect(competingR2.sha256).not.toBe(normal.expectedR2.sha256)
      const before = yield* assertRawTail(
        target.s0Revision + 2,
        competingR2
      )
      expect(before.journal[target.s0Revision + 1]?.descriptor).toEqual(
        target.expectedR1
      )
      expect(
        before.journal.filter(
          (entry) => entry.descriptor.sha256 === competingR2.sha256
        )
      ).toHaveLength(1)
      expect(
        before.journal.some(
          (entry) => entry.descriptor.sha256 === normal.expectedR2.sha256
        )
      ).toBe(false)
      const resumed = yield* resumeDnrd5V2AdmitTwoCas(normal.input).pipe(
        Effect.either
      )
      expect(Either.isLeft(resumed)).toBe(true)
      const after = yield* assertRawTail(
        target.s0Revision + 2,
        competingR2
      )
      expect(after.journal).toEqual(before.journal)
      expect(after.history).toEqual(before.history)
      expect(after.journal).toHaveLength(target.s0Revision + 3)
    }).pipe(Effect.provide(makeDnrd5V2TwoCasFileLayer(root)), Effect.orDie)
  ), 15_000
)
