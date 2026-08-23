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
  symlinkSync,
  writeFileSync
} from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { Effect, Either } from "effect"

import { rawS2SFileSha256 } from "../src/s2s-canonical.js"
import {
  buildS2SEvidenceClaim,
  buildS2SEvidenceEnvelope,
  s2sEvidenceClaimFileName,
  type S2SEvidenceEnvelopeSnapshot
} from "../src/s2s-evidence-envelope.js"
import {
  S2SDurableEvidenceFileStore,
  S2SDurableEvidenceFileStoreError,
  makeS2SDurableEvidenceFileStoreLayer,
  type S2SEvidenceStageIdentity
} from "../src/s2s-evidence-file.js"
import {
  S2S_CONFIRMATORY_WORKFLOW_PATH,
  s2sConfirmatoryWorkflowContractSha256
} from "../src/s2s-workflow-contract.js"

const SOURCE_A = "a".repeat(40)
const REGISTRATION_B = "b".repeat(40)
const WORKFLOW_FILE_SHA256 = "c".repeat(64)
const WORKFLOW_RUN_ID = 101
const WORKFLOW_CREATED_AT = 1_700_000_000
const textEncoder = new TextEncoder()

const rightOrThrow = <A, E>(input: Either.Either<A, E>): A => {
  if (Either.isLeft(input)) throw input.left
  return input.right
}

const WORKFLOW_CONTRACT_SHA256 = rightOrThrow(
  s2sConfirmatoryWorkflowContractSha256()
)

const identityOf = (
  envelope: S2SEvidenceEnvelopeSnapshot
): S2SEvidenceStageIdentity => {
  const document = envelope.document
  return {
    sourceCommitA: document.source_commit_a,
    registrationCommitB: document.registration_commit_b,
    workflowRunId: document.workflow_run_id,
    stage: document.stage
  }
}

const makeEnvelope = (input: {
  readonly stage: "REGISTER" | "CONFIRM" | "ADJUDICATE"
  readonly currentJobDatabaseId: number
  readonly payload: string
  readonly predecessor: {
    readonly stage: "REGISTER" | "CONFIRM"
    readonly manifestRawSha256: string
    readonly claimRawSha256: string
  } | null
}): S2SEvidenceEnvelopeSnapshot =>
  rightOrThrow(
    buildS2SEvidenceEnvelope({
      sourceCommitA: SOURCE_A,
      registrationCommitB: REGISTRATION_B,
      workflowRunId: WORKFLOW_RUN_ID,
      workflowRunCreatedAtUnixSeconds: WORKFLOW_CREATED_AT,
      workflowApiPath: S2S_CONFIRMATORY_WORKFLOW_PATH,
      workflowFileSha256: WORKFLOW_FILE_SHA256,
      workflowContractSha256: WORKFLOW_CONTRACT_SHA256,
      stage: input.stage,
      currentJobDatabaseId: input.currentJobDatabaseId,
      predecessor: input.predecessor,
      attachments: [
        {
          logicalName: `observations/${input.stage.toLowerCase()}.json`,
          role: `${input.stage}_OBSERVATION`,
          schemaVersion: "hswm-swm0w-test-observation/v1",
          mediaType: "application/json",
          bytes: textEncoder.encode(`${input.payload}\n`)
        }
      ]
    })
  )

const healthyEnvelopeChain = (): {
  readonly registration: S2SEvidenceEnvelopeSnapshot
  readonly confirmation: S2SEvidenceEnvelopeSnapshot
  readonly adjudication: S2SEvidenceEnvelopeSnapshot
} => {
  const registration = makeEnvelope({
    stage: "REGISTER",
    currentJobDatabaseId: 201,
    payload: "registration",
    predecessor: null
  })
  const registrationClaim = rightOrThrow(
    buildS2SEvidenceClaim(registration)
  )
  const confirmation = makeEnvelope({
    stage: "CONFIRM",
    currentJobDatabaseId: 202,
    payload: "confirmation",
    predecessor: {
      stage: "REGISTER",
      manifestRawSha256: registration.manifestRawSha256,
      claimRawSha256: registrationClaim.claimRawSha256
    }
  })
  const confirmationClaim = rightOrThrow(
    buildS2SEvidenceClaim(confirmation)
  )
  const adjudication = makeEnvelope({
    stage: "ADJUDICATE",
    currentJobDatabaseId: 203,
    payload: "adjudication",
    predecessor: {
      stage: "CONFIRM",
      manifestRawSha256: confirmation.manifestRawSha256,
      claimRawSha256: confirmationClaim.claimRawSha256
    }
  })
  return { registration, confirmation, adjudication }
}

const cleanup = (path: string): Effect.Effect<void> =>
  Effect.sync(() => rmSync(path, { force: true, recursive: true }))

const provisionedStoreLayer = (path: string) => {
  mkdirSync(path, { recursive: true, mode: 0o700 })
  return makeS2SDurableEvidenceFileStoreLayer(path)
}

it.effect("commits attachment objects, manifest objects, then durable claim anchors and recovers after restart", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-evidence-"))
  const storeRoot = join(temporaryRoot, "store")
  const { registration, confirmation, adjudication } = healthyEnvelopeChain()

  const program = Effect.gen(function* () {
    const publications = yield* Effect.gen(function* () {
      const store = yield* S2SDurableEvidenceFileStore
      const first = yield* store.commit(registration)
      const duplicate = yield* store.commit(registration)
      const second = yield* store.commit(confirmation)
      const third = yield* store.commit(adjudication)
      return { first, duplicate, second, third }
    }).pipe(Effect.provide(provisionedStoreLayer(storeRoot)))

    expect(publications.first._tag).toBe("Committed")
    expect(publications.duplicate._tag).toBe("AlreadyCommitted")
    expect(publications.second._tag).toBe("Committed")
    expect(publications.third._tag).toBe("Committed")
    expect(publications.third.recovery.chain.map(({ envelope }) =>
      envelope.document.stage
    )).toEqual(["REGISTER", "CONFIRM", "ADJUDICATE"])

    expect(statSync(storeRoot).mode & 0o777).toBe(0o700)
    expect(statSync(join(storeRoot, "objects")).mode & 0o777).toBe(0o700)
    expect(statSync(join(storeRoot, "claims")).mode & 0o777).toBe(0o700)
    for (const directory of ["objects", "claims"]) {
      for (const entry of readdirSync(join(storeRoot, directory))) {
        expect(statSync(join(storeRoot, directory, entry)).mode & 0o777).toBe(
          0o400
        )
      }
    }

    const orphanHash = "f".repeat(64)
    writeFileSync(join(storeRoot, "objects", orphanHash), "orphan\n", {
      mode: 0o400
    })
    const recovered = yield* Effect.gen(function* () {
      const store = yield* S2SDurableEvidenceFileStore
      return yield* store.recover(identityOf(adjudication))
    }).pipe(Effect.provide(provisionedStoreLayer(storeRoot)))

    expect(recovered.chain).toHaveLength(3)
    expect(recovered.latest.envelope.manifestRawSha256).toBe(
      adjudication.manifestRawSha256
    )
    const exposedManifest = recovered.latest.envelope.canonicalBytes
    exposedManifest.fill(0)
    expect(rawS2SFileSha256(recovered.latest.envelope.canonicalBytes)).toBe(
      adjudication.manifestRawSha256
    )
    const exposedAttachment = recovered.latest.envelope.attachments[0]
    expect(exposedAttachment).toBeDefined()
    const beforeMutation = exposedAttachment?.descriptor.raw_sha256
    exposedAttachment?.readBytes().fill(0)
    expect(
      recovered.latest.envelope.attachments[0]?.descriptor.raw_sha256
    ).toBe(beforeMutation)
  })

  return program.pipe(Effect.ensuring(cleanup(temporaryRoot)))
})

it.effect("rejects a divergent exact B/stage claim and reconciles identical concurrent commits", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-claim-cas-"))
  const identicalRoot = join(temporaryRoot, "identical")
  const divergentRoot = join(temporaryRoot, "divergent")
  const { registration } = healthyEnvelopeChain()
  const fork = makeEnvelope({
    stage: "REGISTER",
    currentJobDatabaseId: 999,
    payload: "forked-registration",
    predecessor: null
  })
  const commitThroughNewLayer = (
    root: string,
    envelope: S2SEvidenceEnvelopeSnapshot
  ) =>
    Effect.gen(function* () {
      const store = yield* S2SDurableEvidenceFileStore
      return yield* store.commit(envelope)
    }).pipe(Effect.provide(provisionedStoreLayer(root)))

  const program = Effect.gen(function* () {
    const identical = yield* Effect.all(
      [
        commitThroughNewLayer(identicalRoot, registration),
        commitThroughNewLayer(identicalRoot, registration)
      ],
      { concurrency: 2 }
    )
    expect(identical.map(({ _tag }) => _tag).sort()).toEqual([
      "AlreadyCommitted",
      "Committed"
    ])

    const divergentOutcomes = yield* Effect.all(
        [
          commitThroughNewLayer(divergentRoot, registration).pipe(
            Effect.either
          ),
          commitThroughNewLayer(divergentRoot, fork).pipe(Effect.either)
        ],
        { concurrency: 2 }
      )
    const winner = divergentOutcomes.find(Either.isRight)
    if (winner === undefined) throw new Error("one claim must win")
    const divergentRecovery = yield* Effect.gen(function* () {
      const store = yield* S2SDurableEvidenceFileStore
      const recovery = yield* store.recover(
        identityOf(winner.right.recovery.latest.envelope)
      )
      return recovery
    }).pipe(
      Effect.provide(provisionedStoreLayer(divergentRoot))
    )
    expect(divergentOutcomes.filter(Either.isRight)).toHaveLength(1)
    const rejected = divergentOutcomes.find(Either.isLeft)
    expect(rejected?.left).toBeInstanceOf(S2SDurableEvidenceFileStoreError)
    if (rejected?.left instanceof S2SDurableEvidenceFileStoreError) {
      expect(rejected.left.reason).toBe("CLAIM_CONFLICT")
    }
    expect(divergentRecovery.chain).toHaveLength(1)
    expect(readdirSync(join(divergentRoot, "claims"))).toHaveLength(1)
    // Independent adapters may both publish harmless content-addressed
    // orphans before the single create-only claim chooses a winner.
    const divergentObjectCount = readdirSync(
      join(divergentRoot, "objects")
    ).length
    expect(divergentObjectCount).toBeGreaterThanOrEqual(2)
    expect(divergentObjectCount).toBeLessThanOrEqual(4)
  })

  return program.pipe(Effect.ensuring(cleanup(temporaryRoot)))
})

it.effect("requires the exact committed predecessor before publishing any successor object", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-predecessor-"))
  const missingRoot = join(temporaryRoot, "missing")
  const mismatchRoot = join(temporaryRoot, "mismatch")
  const { registration, confirmation } = healthyEnvelopeChain()
  const mismatchedConfirmation = makeEnvelope({
    stage: "CONFIRM",
    currentJobDatabaseId: 202,
    payload: "mismatched-confirmation",
    predecessor: {
      stage: "REGISTER",
      manifestRawSha256: "e".repeat(64),
      claimRawSha256: "f".repeat(64)
    }
  })

  const program = Effect.gen(function* () {
    const missing = yield* Effect.gen(function* () {
      const store = yield* S2SDurableEvidenceFileStore
      return yield* store.commit(confirmation).pipe(Effect.either)
    }).pipe(Effect.provide(provisionedStoreLayer(missingRoot)))
    expect(Either.isLeft(missing)).toBe(true)
    if (
      Either.isLeft(missing) &&
      missing.left instanceof S2SDurableEvidenceFileStoreError
    ) {
      expect(missing.left.reason).toBe("PREDECESSOR_MISSING")
    }
    expect(readdirSync(join(missingRoot, "objects"))).toEqual([])
    expect(readdirSync(join(missingRoot, "claims"))).toEqual([])

    const mismatch = yield* Effect.gen(function* () {
      const store = yield* S2SDurableEvidenceFileStore
      yield* store.commit(registration)
      return yield* store.commit(mismatchedConfirmation).pipe(Effect.either)
    }).pipe(
      Effect.provide(provisionedStoreLayer(mismatchRoot))
    )
    expect(Either.isLeft(mismatch)).toBe(true)
    if (
      Either.isLeft(mismatch) &&
      mismatch.left instanceof S2SDurableEvidenceFileStoreError
    ) {
      expect(mismatch.left.reason).toBe("PREDECESSOR_MISMATCH")
    }
    expect(
      existsSync(
        join(
          mismatchRoot,
          "claims",
          s2sEvidenceClaimFileName(
            mismatchedConfirmation.document.registration_commit_b,
            "CONFIRM"
          )
        )
      )
    ).toBe(false)
  })

  return program.pipe(Effect.ensuring(cleanup(temporaryRoot)))
})

it.effect("detects content-address corruption on commit and recovery", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-corrupt-"))
  const conflictRoot = join(temporaryRoot, "conflict")
  const recoveryRoot = join(temporaryRoot, "recovery")
  const { registration } = healthyEnvelopeChain()
  const attachment = registration.attachments[0]
  if (attachment === undefined) throw new Error("fixture attachment is missing")
  const attachmentHash = attachment.descriptor.raw_sha256
  const corruptBytes = attachment.readBytes()
  corruptBytes[0] = (corruptBytes[0] ?? 0) ^ 0xff

  const program = Effect.gen(function* () {
    const conflict = yield* Effect.gen(function* () {
      const store = yield* S2SDurableEvidenceFileStore
      yield* Effect.sync(() =>
        writeFileSync(join(conflictRoot, "objects", attachmentHash), corruptBytes, {
          mode: 0o400
        })
      )
      return yield* store.commit(registration).pipe(Effect.either)
    }).pipe(
      Effect.provide(provisionedStoreLayer(conflictRoot))
    )
    expect(Either.isLeft(conflict)).toBe(true)
    if (
      Either.isLeft(conflict) &&
      conflict.left instanceof S2SDurableEvidenceFileStoreError
    ) {
      expect(conflict.left.reason).toBe("CONTENT_ADDRESS_CORRUPTION")
    }
    expect(readdirSync(join(conflictRoot, "claims"))).toEqual([])

    const committedReadback = yield* Effect.gen(function* () {
      const store = yield* S2SDurableEvidenceFileStore
      yield* store.commit(registration)
      yield* Effect.sync(() => {
        const objectPath = join(recoveryRoot, "objects", attachmentHash)
        chmodSync(objectPath, 0o600)
        writeFileSync(objectPath, corruptBytes)
        chmodSync(objectPath, 0o400)
      })
      const duplicate = yield* store.commit(registration).pipe(Effect.either)
      const recovered = yield* store
        .recover(identityOf(registration))
        .pipe(Effect.either)
      return { duplicate, recovered }
    }).pipe(
      Effect.provide(provisionedStoreLayer(recoveryRoot))
    )
    expect(Either.isLeft(committedReadback.duplicate)).toBe(true)
    if (
      Either.isLeft(committedReadback.duplicate) &&
      committedReadback.duplicate.left instanceof
        S2SDurableEvidenceFileStoreError
    ) {
      expect(committedReadback.duplicate.left.reason).toBe(
        "COMMITTED_READBACK_FAILED"
      )
    }
    expect(Either.isLeft(committedReadback.recovered)).toBe(true)
    if (
      Either.isLeft(committedReadback.recovered) &&
      committedReadback.recovered.left instanceof
        S2SDurableEvidenceFileStoreError
    ) {
      expect(committedReadback.recovered.left.reason).toBe(
        "CONTENT_ADDRESS_CORRUPTION"
      )
    }
  })

  return program.pipe(Effect.ensuring(cleanup(temporaryRoot)))
})

it.effect("fails closed on a symlink claim, a missing claim, and unsafe roots", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-root-"))
  const symlinkRoot = join(temporaryRoot, "symlink")
  const missingRoot = join(temporaryRoot, "missing")
  const unprovisionedRoot = join(temporaryRoot, "unprovisioned")
  const unsafeRoot = join(temporaryRoot, "unsafe")
  const externalPath = join(temporaryRoot, "external.json")
  const { registration } = healthyEnvelopeChain()
  writeFileSync(externalPath, registration.canonicalBytes, { mode: 0o600 })
  writeFileSync(unsafeRoot, "not-a-directory\n", { mode: 0o600 })
  mkdirSync(missingRoot, { mode: 0o700 })

  const recover = (root: string) =>
    Effect.gen(function* () {
      const store = yield* S2SDurableEvidenceFileStore
      return yield* store.recover(identityOf(registration))
    }).pipe(
      Effect.provide(makeS2SDurableEvidenceFileStoreLayer(root)),
      Effect.either
    )

  const program = Effect.gen(function* () {
    const symlinked = yield* Effect.gen(function* () {
      const store = yield* S2SDurableEvidenceFileStore
      yield* Effect.sync(() =>
        symlinkSync(
          externalPath,
          join(
            symlinkRoot,
            "claims",
            s2sEvidenceClaimFileName(
              registration.document.registration_commit_b,
              "REGISTER"
            )
          )
        )
      )
      return yield* store.recover(identityOf(registration)).pipe(Effect.either)
    }).pipe(
      Effect.provide(provisionedStoreLayer(symlinkRoot))
    )
    const missing = yield* recover(missingRoot)
    const relative = yield* recover("relative-evidence-root")
    const unsafe = yield* recover(unsafeRoot)
    const unprovisioned = yield* recover(unprovisionedRoot)

    expect(Either.isLeft(symlinked)).toBe(true)
    if (
      Either.isLeft(symlinked) &&
      symlinked.left instanceof S2SDurableEvidenceFileStoreError
    ) {
      expect(symlinked.left.reason).toBe("FILE_TYPE_INVALID")
    }
    expect(Either.isLeft(missing)).toBe(true)
    if (
      Either.isLeft(missing) &&
      missing.left instanceof S2SDurableEvidenceFileStoreError
    ) {
      expect(missing.left.reason).toBe("CLAIM_NOT_FOUND")
    }
    for (const failure of [relative, unsafe, unprovisioned]) {
      expect(Either.isLeft(failure)).toBe(true)
      if (
        Either.isLeft(failure) &&
        failure.left instanceof S2SDurableEvidenceFileStoreError
      ) {
        expect(failure.left.reason).toBe("ROOT_UNSAFE")
      }
    }
    expect(readFileSync(externalPath)).toEqual(
      Buffer.from(registration.canonicalBytes)
    )
  })

  return program.pipe(Effect.ensuring(cleanup(temporaryRoot)))
})

it.effect("keeps hostile commit inspection lazy until the returned Effect runs", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-lazy-"))
  const storeRoot = join(temporaryRoot, "store")
  let manifestReads = 0
  const counterfeit = Object.create(null) as Record<string, unknown>
  Object.defineProperties(counterfeit, {
    canonicalBytes: {
      enumerable: true,
      get: () => {
        manifestReads += 1
        return Uint8Array.from([0x7b])
      }
    },
    attachments: { enumerable: true, value: [] },
    manifestRawSha256: { enumerable: true, value: "0".repeat(64) }
  })

  const program = Effect.gen(function* () {
    const store = yield* S2SDurableEvidenceFileStore
    const pending = store.commit(
      counterfeit as unknown as S2SEvidenceEnvelopeSnapshot
    )
    expect(manifestReads).toBe(0)
    const outcome = yield* pending.pipe(Effect.either)
    expect(manifestReads).toBe(1)
    expect(Either.isLeft(outcome)).toBe(true)
    expect(readdirSync(join(storeRoot, "objects"))).toEqual([])
    expect(readdirSync(join(storeRoot, "claims"))).toEqual([])
  }).pipe(Effect.provide(provisionedStoreLayer(storeRoot)))

  return program.pipe(Effect.ensuring(cleanup(temporaryRoot)))
})
