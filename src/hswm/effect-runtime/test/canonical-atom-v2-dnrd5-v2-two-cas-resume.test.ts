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
  makeDnrd5V2TwoCasLayer,
  prepareDnrd5V2TwoCasFixture
} from "./fixtures/canonical-atom-v2-dnrd5-v2-two-cas.js"

const assertExactRawPrefix = (
  fixture: Dnrd5V2TwoCasPreparedFixture,
  expected: "S0" | "R1" | "R2"
) => Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const witness = yield* recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal(
    runtime
  )
  const expectedRevision =
    expected === "S0"
      ? fixture.s0Revision
      : expected === "R1"
        ? fixture.s0Revision + 1
        : fixture.s0Revision + 2
  const expectedHead =
    expected === "S0"
      ? witness.journal[fixture.s0Revision]!.descriptor
      : expected === "R1"
        ? fixture.expectedR1
        : fixture.expectedR2
  expect(witness.state.canonical.revision).toBe(expectedRevision)
  // Raw journal contains genesis at slot zero, hence revision + one entries.
  expect(witness.journal).toHaveLength(expectedRevision + 1)
  expect(witness.history).toHaveLength(expectedRevision)
  expect(witness.state.journalHead).toEqual(expectedHead)
  expect(witness.journal.at(-1)?.descriptor).toEqual(expectedHead)
  if (expected === "R1" || expected === "R2") {
    expect(witness.journal[fixture.s0Revision + 1]?.descriptor).toEqual(
      fixture.expectedR1
    )
  }
  if (expected === "R2") {
    expect(witness.journal[fixture.s0Revision + 2]?.descriptor).toEqual(
      fixture.expectedR2
    )
  }
  return witness
}).pipe(Effect.orDie)

const makeExactR1 = () =>
  Effect.gen(function* () {
    // Preserve the valid original candidate for resume. Only the first call
    // receives a forged receipt payload, so it durably publishes R1 then
    // stops before CAS2.
    const fixture = yield* prepareDnrd5V2TwoCasFixture()
    const receiptPayloadAtomKeyId = fixture.input.receipt.writePayloads.find(
      ({ atomKeyId }) =>
        atomKeyId !== canonicalAtomV2KeyId(fixture.input.receipt.consumption.atom.key)
    )?.atomKeyId
    if (receiptPayloadAtomKeyId === undefined) {
      throw new Error("two-CAS fixture lacks its receipt payload write")
    }
    const forgedInput = {
      ...fixture.input,
      receipt: {
        ...fixture.input.receipt,
        writePayloads: fixture.input.receipt.writePayloads.map((payload) =>
          payload.atomKeyId === receiptPayloadAtomKeyId
            ? { ...payload, bytes: Uint8Array.from([...payload.bytes, 10]) }
            : payload
        )
      }
    }
    const attempt = yield* submitDnrd5V2AdmitTwoCas(forgedInput).pipe(
      Effect.either
    )
    expect(Either.isLeft(attempt)).toBe(true)
    if (Either.isLeft(attempt)) {
      expect(attempt.left).toMatchObject({
        _tag: "Dnrd5V2TwoCasRecoveryError",
        milestone: "CAS1_EXACT_R1_RECEIPT_PENDING"
      })
    }
    yield* assertExactRawPrefix(fixture, "R1")
    return fixture
  }).pipe(Effect.orDie)

it.effect("resumes an exact raw R1 forged-receipt stop with CAS2 only", () =>
  Effect.gen(function* () {
    const fixture = yield* makeExactR1()
    const confirmed = yield* resumeDnrd5V2AdmitTwoCas(fixture.input)
    expect(confirmed).toMatchObject({
      milestone: "CAS2_EXACT_R2_CONFIRMED",
      mainRecord: fixture.expectedR1,
      receiptRecord: fixture.expectedR2
    })
    const raw = yield* assertExactRawPrefix(fixture, "R2")
    // There is one and only one raw R1: resume may never append another CAS1.
    expect(
      raw.journal.filter(
        (entry) => entry.descriptor.sha256 === fixture.expectedR1.sha256
      )
    ).toHaveLength(1)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer()))
)

it.effect("treats exact R2 resume as no-write idempotent confirmation", () =>
  Effect.gen(function* () {
    const fixture = yield* makeExactR1()
    yield* resumeDnrd5V2AdmitTwoCas(fixture.input)
    const before = yield* assertExactRawPrefix(fixture, "R2")
    const confirmed = yield* resumeDnrd5V2AdmitTwoCas(fixture.input)
    expect(confirmed).toMatchObject({
      milestone: "CAS2_EXACT_R2_CONFIRMED",
      mainRecord: fixture.expectedR1,
      receiptRecord: fixture.expectedR2
    })
    const after = yield* assertExactRawPrefix(fixture, "R2")
    expect(after.journal).toEqual(before.journal)
    expect(after.history).toEqual(before.history)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer()))
)

it.effect("rejects S0-only resume without publishing CAS1", () =>
  Effect.gen(function* () {
    const fixture = yield* prepareDnrd5V2TwoCasFixture()
    const before = yield* assertExactRawPrefix(fixture, "S0")
    const resumed = yield* resumeDnrd5V2AdmitTwoCas(fixture.input).pipe(
      Effect.either
    )
    expect(Either.isLeft(resumed)).toBe(true)
    const after = yield* assertExactRawPrefix(fixture, "S0")
    expect(after.journal).toEqual(before.journal)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer()))
)

it.effect("rejects extra or duplicate receipt payload candidates at R1, then accepts the exact original", () =>
  Effect.gen(function* () {
    const fixture = yield* makeExactR1()
    const duplicate = fixture.input.receipt.writePayloads[0]!
    const malformed = {
      ...fixture.input,
      receipt: {
        ...fixture.input.receipt,
        writePayloads: [
          ...fixture.input.receipt.writePayloads,
          { atomKeyId: duplicate.atomKeyId, bytes: Uint8Array.from(duplicate.bytes) }
        ]
      }
    }
    const rejected = yield* resumeDnrd5V2AdmitTwoCas(malformed).pipe(
      Effect.either
    )
    expect(Either.isLeft(rejected)).toBe(true)
    const afterRejected = yield* assertExactRawPrefix(fixture, "R1")
    expect(afterRejected.journal).toHaveLength(fixture.s0Revision + 2)

    const confirmed = yield* resumeDnrd5V2AdmitTwoCas(fixture.input)
    expect(confirmed).toMatchObject({
      milestone: "CAS2_EXACT_R2_CONFIRMED",
      mainRecord: fixture.expectedR1,
      receiptRecord: fixture.expectedR2
    })
    yield* assertExactRawPrefix(fixture, "R2")
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer()))
)

it.effect("rejects a schema-valid ignored main transition mutation at exact R2 without writing", () =>
  Effect.gen(function* () {
    const fixture = yield* makeExactR1()
    yield* resumeDnrd5V2AdmitTwoCas(fixture.input)
    const before = yield* assertExactRawPrefix(fixture, "R2")
    const mutated = {
      ...fixture.input,
      main: {
        ...fixture.input.main,
        transition: {
          ...fixture.input.main.transition,
          command: {
            ...fixture.input.main.transition.command,
            provenanceSha256: "0".repeat(64)
          }
        }
      }
    }
    const rejected = yield* resumeDnrd5V2AdmitTwoCas(mutated).pipe(
      Effect.either
    )
    expect(Either.isLeft(rejected)).toBe(true)
    const after = yield* assertExactRawPrefix(fixture, "R2")
    expect(after.journal).toEqual(before.journal)
    expect(after.history).toEqual(before.history)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer()))
)

it.effect("rejects changed main write-payload bytes at exact R2 without writing", () =>
  Effect.gen(function* () {
    const fixture = yield* makeExactR1()
    yield* resumeDnrd5V2AdmitTwoCas(fixture.input)
    const before = yield* assertExactRawPrefix(fixture, "R2")
    const changed = fixture.input.main.writePayloads[0]!
    const mutated = {
      ...fixture.input,
      main: {
        ...fixture.input.main,
        writePayloads: fixture.input.main.writePayloads.map((payload) =>
          payload.atomKeyId === changed.atomKeyId
            ? { ...payload, bytes: Uint8Array.from([...payload.bytes, 0]) }
            : payload
        )
      }
    }
    const rejected = yield* resumeDnrd5V2AdmitTwoCas(mutated).pipe(
      Effect.either
    )
    expect(Either.isLeft(rejected)).toBe(true)
    const after = yield* assertExactRawPrefix(fixture, "R2")
    expect(after.journal).toEqual(before.journal)
    expect(after.history).toEqual(before.history)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer()))
)

it.effect("concurrent same-runtime resumes converge on exact R2 without R3", () =>
  Effect.gen(function* () {
    const fixture = yield* makeExactR1()
    const attempts = yield* Effect.all(
      [
        resumeDnrd5V2AdmitTwoCas(fixture.input).pipe(Effect.either),
        resumeDnrd5V2AdmitTwoCas(fixture.input).pipe(Effect.either)
      ],
      { concurrency: "unbounded" }
    )
    expect(attempts.every(Either.isRight)).toBe(true)
    for (const attempt of attempts) {
      if (Either.isRight(attempt)) {
        expect(attempt.right).toMatchObject({
          milestone: "CAS2_EXACT_R2_CONFIRMED",
          mainRecord: fixture.expectedR1,
          receiptRecord: fixture.expectedR2
        })
      }
    }
    const raw = yield* assertExactRawPrefix(fixture, "R2")
    expect(raw.journal).toHaveLength(fixture.s0Revision + 3)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer()))
)

it.effect("fresh file-runtime reopen resumes exact R1 without duplicating it", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-dnrd5-v2-resume-"))
  return Effect.gen(function* () {
    const fixture = yield* makeExactR1()
    const rawR1 = yield* assertExactRawPrefix(fixture, "R1")
    return { fixture, rawR1 }
  }).pipe(
    Effect.provide(makeDnrd5V2TwoCasFileLayer(root)),
    Effect.flatMap(({ fixture, rawR1 }) =>
      Effect.gen(function* () {
        const confirmed = yield* resumeDnrd5V2AdmitTwoCas(fixture.input)
        expect(confirmed).toMatchObject({
          milestone: "CAS2_EXACT_R2_CONFIRMED",
          mainRecord: fixture.expectedR1,
          receiptRecord: fixture.expectedR2
        })
        const rawR2 = yield* assertExactRawPrefix(fixture, "R2")
        expect(rawR2.journal[fixture.s0Revision + 1]?.descriptor).toEqual(
          rawR1.journal[fixture.s0Revision + 1]?.descriptor
        )
        expect(
          rawR2.journal.filter(
            (entry) => entry.descriptor.sha256 === fixture.expectedR1.sha256
          )
        ).toHaveLength(1)
      }).pipe(Effect.provide(makeDnrd5V2TwoCasFileLayer(root)))
    ),
    Effect.ensuring(Effect.sync(() => rmSync(root, { recursive: true, force: true })))
  )
})
