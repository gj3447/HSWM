import { expect, it } from "@effect/vitest"
import {
  chmodSync,
  existsSync,
  mkdtempSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  unlinkSync,
  writeFileSync
} from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import {
  link as linkFile,
  realpath as realpathFile
} from "node:fs/promises"

import { Effect, Either } from "effect"

import {
  S2STestOnlyGoldenArtifactStore,
  S2STestOnlyGoldenArtifactStoreError,
  makeS2STestOnlyGoldenArtifactStoreFileLayer,
  makeS2STestOnlyGoldenArtifactStoreFileLayerWithPosixForTest,
  type S2STestOnlyGoldenArtifactPublicationReceipt
} from "../src/s2s-test-only-golden-artifact-store.js"

const encoder = new TextEncoder()

const candidateMembers = (payload = "candidate\n") => [
  {
    name: "numeric_candidate.json" as const,
    bytes: encoder.encode(payload)
  }
]

const adjudicationMembers = (payload = "adjudication\n") => [
  {
    name: "numeric_adjudication.json" as const,
    bytes: encoder.encode(payload)
  }
]

const cleanup = (path: string): Effect.Effect<void> =>
  Effect.sync(() => rmSync(path, { force: true, recursive: true }))

const readBackWithLayer = (
  root: string,
  receipt: S2STestOnlyGoldenArtifactPublicationReceipt
) =>
  Effect.gen(function* () {
    const store = yield* S2STestOnlyGoldenArtifactStore
    return yield* store.readBackGoldenArtifact(receipt)
  }).pipe(
    Effect.provide(makeS2STestOnlyGoldenArtifactStoreFileLayer(root))
  )

const expectStoreReason = (
  outcome: Either.Either<unknown, S2STestOnlyGoldenArtifactStoreError>,
  reason: S2STestOnlyGoldenArtifactStoreError["reason"]
): void => {
  expect(Either.isLeft(outcome)).toBe(true)
  if (Either.isLeft(outcome)) {
    expect(outcome.left).toBeInstanceOf(
      S2STestOnlyGoldenArtifactStoreError
    )
    expect(outcome.left.reason).toBe(reason)
  }
}

it.effect("publishes fixed create-only files and independently reconstructs them through a fresh same-root Layer", () => {
  const temporaryRoot = mkdtempSync(
    join(tmpdir(), "hswm-s2s-test-only-golden-store-")
  )
  const originalMember = candidateMembers()

  const program = Effect.gen(function* () {
    const receipt = yield* Effect.gen(function* () {
      const store = yield* S2STestOnlyGoldenArtifactStore
      return yield* store.publishGoldenArtifact(
        "GOLDEN_CANDIDATE",
        originalMember
      )
    }).pipe(
      Effect.provide(
        makeS2STestOnlyGoldenArtifactStoreFileLayer(temporaryRoot)
      )
    )

    originalMember[0]?.bytes.fill(0)
    expect(receipt._tag).toBe(
      "S2STestOnlyGoldenArtifactPublicationReceipt"
    )
    expect(receipt.classification).toBe("TEST_ONLY_NON_AUTHORIZING")
    expect(receipt.origin).toBe("LOCAL_TEST_LAYER")
    expect(receipt.disposition).toBe("CREATED")
    expect(receipt.publicationKey).toBe(
      "s2s-test-only-golden-candidate.zip"
    )
    expect(receipt.postconditionPublicationKey).toBe(
      "s2s-test-only-golden-candidate-upload-postcondition.zip"
    )
    expect("root" in receipt).toBe(false)
    expect("path" in receipt).toBe(false)
    expect(readdirSync(temporaryRoot).sort()).toEqual([
      "s2s-test-only-golden-candidate-upload-postcondition.zip",
      "s2s-test-only-golden-candidate.zip"
    ])
    for (const entry of readdirSync(temporaryRoot)) {
      expect(statSync(join(temporaryRoot, entry)).mode & 0o777).toBe(0o400)
    }

    const exposedReceiptArchive = receipt.readArchiveBytes()
    exposedReceiptArchive.fill(0)
    expect(receipt.readArchiveBytes()[0]).not.toBe(0)

    const first = yield* readBackWithLayer(temporaryRoot, receipt)
    const second = yield* readBackWithLayer(temporaryRoot, receipt)
    expect(first).not.toBe(second)
    expect(first.archiveSha256).toBe(receipt.archiveSha256)
    expect(first.archiveByteLength).toBe(receipt.archiveByteLength)
    expect(first.postconditionSha256).toBe(receipt.postconditionSha256)
    expect(first.member.name).toBe("numeric_candidate.json")
    expect(new TextDecoder().decode(first.member.readBytes())).toBe(
      "candidate\n"
    )
    expect(first.readArchiveBytes()).toEqual(second.readArchiveBytes())
    expect(first.readPostconditionArchiveBytes()).toEqual(
      second.readPostconditionArchiveBytes()
    )

    first.member.readBytes().fill(0)
    first.readArchiveBytes().fill(0)
    first.readPostconditionArchiveBytes().fill(0)
    first.readPostconditionDocumentBytes().fill(0)
    expect(new TextDecoder().decode(second.member.readBytes())).toBe(
      "candidate\n"
    )
    const postcondition: unknown = JSON.parse(
      new TextDecoder().decode(second.readPostconditionDocumentBytes())
    )
    expect(postcondition).toMatchObject({
      classification: "TEST_ONLY_NON_AUTHORIZING",
      origin: "LOCAL_TEST_LAYER",
      role: "GOLDEN_CANDIDATE",
      publication_key: "s2s-test-only-golden-candidate.zip",
      publication_disposition: "CREATED",
      archive_readback_bytes_equal: true
    })
  })

  return program.pipe(Effect.ensuring(cleanup(temporaryRoot)))
})

it.effect("rejects receipt clones and proxies while distinguishing a genuine receipt used at another root", () => {
  const temporaryRoot = mkdtempSync(
    join(tmpdir(), "hswm-s2s-test-only-golden-receipt-")
  )
  const firstRoot = join(temporaryRoot, "first")
  const otherRoot = join(temporaryRoot, "other")
  mkdirSync(firstRoot, { mode: 0o700 })
  mkdirSync(otherRoot, { mode: 0o700 })

  const program = Effect.gen(function* () {
    const receipt = yield* Effect.gen(function* () {
      const store = yield* S2STestOnlyGoldenArtifactStore
      return yield* store.publishGoldenArtifact(
        "GOLDEN_ADJUDICATION",
        adjudicationMembers()
      )
    }).pipe(
      Effect.provide(makeS2STestOnlyGoldenArtifactStoreFileLayer(firstRoot))
    )

    const clone = Object.freeze({ ...receipt })
    const proxy = new Proxy(receipt, {})
    const cloned = yield* readBackWithLayer(firstRoot, clone).pipe(Effect.either)
    const proxied = yield* readBackWithLayer(firstRoot, proxy).pipe(Effect.either)
    const wrongRoot = yield* readBackWithLayer(otherRoot, receipt).pipe(
      Effect.either
    )

    expectStoreReason(cloned, "READBACK_FAILED")
    expectStoreReason(proxied, "READBACK_FAILED")
    expectStoreReason(wrongRoot, "RECOVERY_MISMATCH")
    const recovered = yield* readBackWithLayer(firstRoot, receipt)
    expect(new TextDecoder().decode(recovered.member.readBytes())).toBe(
      "adjudication\n"
    )
  })

  return program.pipe(Effect.ensuring(cleanup(temporaryRoot)))
})

it.effect("lazily initializes a genuinely fresh same-root Layer for each explicit recovery", () => {
  const temporaryRoot = mkdtempSync(
    join(tmpdir(), "hswm-s2s-test-only-golden-fresh-method-")
  )
  let realpathCalls = 0
  const layer =
    makeS2STestOnlyGoldenArtifactStoreFileLayerWithPosixForTest(
      temporaryRoot,
      {
        realpath: async (path) => {
          realpathCalls += 1
          return await realpathFile(path)
        }
      }
    )

  const program = Effect.gen(function* () {
    const store = yield* S2STestOnlyGoldenArtifactStore
    const receipt = yield* store.publishGoldenArtifact(
      "GOLDEN_CANDIDATE",
      candidateMembers()
    )
    expect(realpathCalls).toBe(1)

    const direct = yield* store.readBackGoldenArtifact(receipt)
    expect(realpathCalls).toBe(1)

    const pendingRecovery =
      store.recoverGoldenArtifactWithFreshLayer(receipt)
    expect(realpathCalls).toBe(1)
    const recovered = yield* pendingRecovery
    expect(realpathCalls).toBe(2)

    const recoveredAgain = yield* store.recoverGoldenArtifactWithFreshLayer(
      receipt
    )
    expect(realpathCalls).toBe(3)
    expect(recovered).not.toBe(direct)
    expect(recoveredAgain).not.toBe(recovered)
    expect(recovered.readArchiveBytes()).toEqual(direct.readArchiveBytes())
    expect(recoveredAgain.readPostconditionArchiveBytes()).toEqual(
      direct.readPostconditionArchiveBytes()
    )
    expect(new TextDecoder().decode(recovered.member.readBytes())).toBe(
      "candidate\n"
    )
  }).pipe(Effect.provide(layer))

  return program.pipe(Effect.ensuring(cleanup(temporaryRoot)))
})

it.effect("treats every second role publication as a create-only conflict, including identical bytes", () => {
  const temporaryRoot = mkdtempSync(
    join(tmpdir(), "hswm-s2s-test-only-golden-conflict-")
  )

  const program = Effect.gen(function* () {
    const outcomes = yield* Effect.gen(function* () {
      const store = yield* S2STestOnlyGoldenArtifactStore
      const first = yield* store.publishGoldenArtifact(
        "GOLDEN_CANDIDATE",
        candidateMembers()
      )
      const identical = yield* store
        .publishGoldenArtifact("GOLDEN_CANDIDATE", candidateMembers())
        .pipe(Effect.either)
      const divergent = yield* store
        .publishGoldenArtifact(
          "GOLDEN_CANDIDATE",
          candidateMembers("different\n")
        )
        .pipe(Effect.either)
      return { first, identical, divergent }
    }).pipe(
      Effect.provide(
        makeS2STestOnlyGoldenArtifactStoreFileLayer(temporaryRoot)
      )
    )

    expect(outcomes.first.disposition).toBe("CREATED")
    expectStoreReason(outcomes.identical, "CREATE_ONLY_CONFLICT")
    expectStoreReason(outcomes.divergent, "CREATE_ONLY_CONFLICT")
    expect(readdirSync(temporaryRoot).sort()).toEqual([
      "s2s-test-only-golden-candidate-upload-postcondition.zip",
      "s2s-test-only-golden-candidate.zip"
    ])
  })

  return program.pipe(Effect.ensuring(cleanup(temporaryRoot)))
})

it.effect("fails typed independent readback when either fixed file is missing or changed", () => {
  const temporaryRoot = mkdtempSync(
    join(tmpdir(), "hswm-s2s-test-only-golden-readback-")
  )
  const mismatchRoot = join(temporaryRoot, "mismatch")
  const missingRoot = join(temporaryRoot, "missing")
  mkdirSync(mismatchRoot, { mode: 0o700 })
  mkdirSync(missingRoot, { mode: 0o700 })

  const publishAt = (root: string) =>
    Effect.gen(function* () {
      const store = yield* S2STestOnlyGoldenArtifactStore
      return yield* store.publishGoldenArtifact(
        "GOLDEN_CANDIDATE",
        candidateMembers()
      )
    }).pipe(
      Effect.provide(makeS2STestOnlyGoldenArtifactStoreFileLayer(root))
    )

  const program = Effect.gen(function* () {
    const mismatchReceipt = yield* publishAt(mismatchRoot)
    const mismatchPath = join(
      mismatchRoot,
      "s2s-test-only-golden-candidate.zip"
    )
    const mutated = readFileSync(mismatchPath)
    mutated[0] = (mutated[0] ?? 0) ^ 0xff
    chmodSync(mismatchPath, 0o600)
    writeFileSync(mismatchPath, mutated)
    chmodSync(mismatchPath, 0o400)
    const mismatch = yield* readBackWithLayer(
      mismatchRoot,
      mismatchReceipt
    ).pipe(Effect.either)
    expectStoreReason(mismatch, "READBACK_MISMATCH")

    const missingReceipt = yield* publishAt(missingRoot)
    unlinkSync(
      join(
        missingRoot,
        "s2s-test-only-golden-candidate-upload-postcondition.zip"
      )
    )
    const missing = yield* readBackWithLayer(missingRoot, missingReceipt).pipe(
      Effect.either
    )
    expectStoreReason(missing, "READBACK_FAILED")
  })

  return program.pipe(Effect.ensuring(cleanup(temporaryRoot)))
})

it.effect("performs one create-only link and no retry when publication definitely fails", () => {
  const temporaryRoot = mkdtempSync(
    join(tmpdir(), "hswm-s2s-test-only-golden-publish-failed-")
  )
  let linkCalls = 0
  let syncCalls = 0
  const rejected = Object.assign(new Error("synthetic link failure"), {
    code: "EIO"
  })

  const program = Effect.gen(function* () {
    const outcome = yield* Effect.gen(function* () {
      const store = yield* S2STestOnlyGoldenArtifactStore
      return yield* store
        .publishGoldenArtifact("GOLDEN_CANDIDATE", candidateMembers())
        .pipe(Effect.either)
    }).pipe(
      Effect.provide(
        makeS2STestOnlyGoldenArtifactStoreFileLayerWithPosixForTest(
          temporaryRoot,
          {
            link: async () => {
              linkCalls += 1
              throw rejected
            },
            syncDirectory: async () => {
              syncCalls += 1
            }
          }
        )
      )
    )

    expectStoreReason(outcome, "PUBLISH_FAILED")
    expect(linkCalls).toBe(1)
    expect(syncCalls).toBe(0)
    expect(
      existsSync(
        join(temporaryRoot, "s2s-test-only-golden-candidate.zip")
      )
    ).toBe(false)
    expect(readdirSync(temporaryRoot)).toEqual([])
  })

  return program.pipe(Effect.ensuring(cleanup(temporaryRoot)))
})

it.effect("reports unknown outcome after one successful link and one failed directory sync without retry", () => {
  const temporaryRoot = mkdtempSync(
    join(tmpdir(), "hswm-s2s-test-only-golden-unknown-")
  )
  let linkCalls = 0
  let syncCalls = 0
  const rejected = Object.assign(new Error("synthetic directory sync failure"), {
    code: "EIO"
  })

  const program = Effect.gen(function* () {
    const outcome = yield* Effect.gen(function* () {
      const store = yield* S2STestOnlyGoldenArtifactStore
      return yield* store
        .publishGoldenArtifact("GOLDEN_CANDIDATE", candidateMembers())
        .pipe(Effect.either)
    }).pipe(
      Effect.provide(
        makeS2STestOnlyGoldenArtifactStoreFileLayerWithPosixForTest(
          temporaryRoot,
          {
            link: async (existingPath, newPath) => {
              linkCalls += 1
              await linkFile(existingPath, newPath)
            },
            syncDirectory: async () => {
              syncCalls += 1
              throw rejected
            }
          }
        )
      )
    )

    expectStoreReason(outcome, "PUBLICATION_OUTCOME_UNKNOWN")
    expect(linkCalls).toBe(1)
    expect(syncCalls).toBe(1)
    expect(
      existsSync(
        join(temporaryRoot, "s2s-test-only-golden-candidate.zip")
      )
    ).toBe(true)
    expect(
      existsSync(
        join(
          temporaryRoot,
          "s2s-test-only-golden-candidate-upload-postcondition.zip"
        )
      )
    ).toBe(false)
  })

  return program.pipe(Effect.ensuring(cleanup(temporaryRoot)))
})
