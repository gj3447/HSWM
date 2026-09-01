import { createHash } from "node:crypto"
import {
  lstatSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  unlinkSync
} from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"
import { Parser } from "n3"

import {
  decodeCanonicalAtomV2SchemaContent,
  describeCanonicalAtomV2Envelope,
  makeCanonicalAtomV2ContentBoundInput,
  type CanonicalAtomV2ContentAuthorizationGrant,
  type CanonicalAtomV2WriteContentBinding
} from "../src/canonical-atom-v2-content-bound.js"
import type { CanonicalAtomV2ContentDescriptor } from "../src/canonical-atom-v2-content.js"
import {
  HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_PREFIX_COMMITMENT_V1,
  canonicalAtomV2DurableRdfProjectionBytes,
  compileCanonicalAtomV2DurableRdfProjection,
  decodeCanonicalAtomV2DurableRdfProjectionBytes,
  verifyCanonicalAtomV2DurableRdfProjection,
  type CanonicalAtomV2DurableRdfProjection
} from "../src/canonical-atom-v2-durable-rdf-projection.js"
import { canonicalAtomV2RdfProjectionBytes } from "../src/canonical-atom-v2-rdf-projection.js"
import {
  CanonicalAtomV2DurableRuntime,
  makeCanonicalAtomV2DurableRuntimeFileLayer,
  makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest
} from "../src/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2StateJournalSlotName } from "../src/canonical-atom-v2-state-journal-file.js"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  HSWM_SUPERSEDES_REFERENCE_ROLE,
  HSWM_SUPERSEDES_REFERENCE_TYPE,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type CommitCanonicalAtomsV2Command,
  type HSWMCanonicalSchemaV2
} from "../src/canonical-atom-v2-schema.js"

const SCHEMA_VERSION = "hswm:test:durable-rdf:v2"
const JOURNAL_LINEAGE = "journal:durable-rdf:main"
const AUTHORIZATION = "authorization:durable-rdf-writer"
const WRITE_SCOPE = "scope:canonical-write"

const utf8 = (value: string): Uint8Array => new TextEncoder().encode(value)
const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error("fixture construction failed")
  return value.right
}

const schema: HSWMCanonicalSchemaV2 = {
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion: SCHEMA_VERSION,
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement: "A bounded durable RDF recovery fixture.",
  owners: [{
    address: "owner:durable-rdf",
    obligation: "Own exact atom lineage and durable RDF projection accountability."
  }],
  kinds: [{
    kind: "kind:durable-rdf-atom",
    form: "ENTITY",
    revisionPolicy: "LINEAR",
    allowedOwners: ["owner:durable-rdf"],
    minimumArity: 0,
    referenceContracts: [{
      referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
      roles: [{
        role: HSWM_SUPERSEDES_REFERENCE_ROLE,
        targetKinds: ["kind:durable-rdf-atom"],
        minimum: 0,
        maximum: 1
      }]
    }]
  }]
}

const rawSchemaBytes = (): Uint8Array => utf8(JSON.stringify(schema))
const schemaContent = () => right(decodeCanonicalAtomV2SchemaContent(rawSchemaBytes()))
const grants = (): ReadonlyArray<CanonicalAtomV2ContentAuthorizationGrant> => [{
  authorizationRef: AUTHORIZATION,
  schemaVersion: SCHEMA_VERSION,
  schemaContentSha256: schemaContent().binding.content.sha256,
  scopes: [WRITE_SCOPE]
}]
const key = (atomUid: string, revisionId: number): CanonicalAtomV2Key => ({
  schemaVersion: SCHEMA_VERSION,
  lineageId: "lineage:durable-rdf:atoms",
  atomUid,
  revisionId
})

const atom = (
  atomUid: string,
  revisionId: number,
  content: CanonicalAtomV2ContentDescriptor
): CanonicalAtomV2 => {
  const predecessor = revisionId === 0 ? null : key(atomUid, revisionId - 1)
  return {
    _tag: "CanonicalAtomV2",
    contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
    key: key(atomUid, revisionId),
    kind: "kind:durable-rdf-atom",
    responsibilityOwner: "owner:durable-rdf",
    content,
    provenance: predecessor === null
      ? { mode: "BOOTSTRAP", evidenceSha256: "b".repeat(64), sourceRef: null }
      : { mode: "DERIVATION", evidenceSha256: "d".repeat(64), sourceRef: predecessor },
    lifecycle: "ADMITTED",
    references: predecessor === null
      ? []
      : [{
          referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
          role: HSWM_SUPERSEDES_REFERENCE_ROLE,
          target: predecessor
        }]
  }
}

const command = (
  value: CanonicalAtomV2,
  expectedStateRevision: number
): CommitCanonicalAtomsV2Command => ({
  _tag: "CommitCanonicalAtomsV2",
  contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  transitionId: `transition:durable-rdf:${value.key.revisionId}`,
  expectedStateRevision,
  schemaVersion: SCHEMA_VERSION,
  actorClaim: "actor:durable-rdf-writer",
  authorizationRef: AUTHORIZATION,
  scope: WRITE_SCOPE,
  decidedAt: `2026-09-01T00:0${expectedStateRevision}:00.000Z`,
  traceRef: null,
  readSet: value.key.revisionId === 0
    ? []
    : [key(value.key.atomUid, value.key.revisionId - 1)],
  writes: [value],
  provenanceSha256: "c".repeat(64)
})

const binding = (value: CanonicalAtomV2): CanonicalAtomV2WriteContentBinding => ({
  key: value.key,
  payload: value.content,
  envelope: right(describeCanonicalAtomV2Envelope(value))
})

const input = (value: CanonicalAtomV2, expectedStateRevision: number) =>
  makeCanonicalAtomV2ContentBoundInput(
    schemaContent().binding.content.sha256,
    command(value, expectedStateRevision),
    [binding(value)]
  )

const fileLayer = (root: string) =>
  makeCanonicalAtomV2DurableRuntimeFileLayer(
    root,
    JOURNAL_LINEAGE,
    rawSchemaBytes(),
    grants()
  )

const withRoot = <A, E>(
  use: (root: string) => Effect.Effect<A, E>
): Effect.Effect<A, E> => {
  const root = mkdtempSync(join(tmpdir(), "hswm-v2-durable-rdf-"))
  return use(root).pipe(
    Effect.ensuring(Effect.sync(() => rmSync(root, { recursive: true, force: true })))
  )
}

const storageFingerprint = (root: string): ReadonlyArray<Readonly<Record<string, string | number>>> => {
  const rows: Array<Readonly<Record<string, string | number>>> = []
  const visit = (relative: string): void => {
    const path = relative.length === 0 ? root : join(root, relative)
    const stat = lstatSync(path)
    rows.push(Object.freeze({
      path: relative.length === 0 ? "." : relative,
      type: stat.isDirectory() ? "directory" : stat.isFile() ? "file" : "other",
      mode: stat.mode & 0o777,
      inode: stat.ino,
      links: stat.nlink,
      size: stat.size,
      sha256: stat.isFile()
        ? createHash("sha256").update(readFileSync(path)).digest("hex")
        : "-"
    }))
    if (stat.isDirectory()) {
      for (const name of readdirSync(path).sort()) {
        visit(relative.length === 0 ? name : join(relative, name))
      }
    }
  }
  visit("")
  return Object.freeze(rows)
}

const commitRevision = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  revisionId: number,
  expectedStateRevision: number
) => Effect.gen(function* () {
  const payload = yield* runtime.stageContent(
    "text/plain",
    utf8(`durable-rdf-payload:${revisionId}`)
  )
  return yield* runtime.submit(
    input(atom("atom:durable-rdf", revisionId, payload), expectedStateRevision)
  )
})

it.effect("binds one observed recovered durable prefix and exact-verifies it after restart", () =>
  withRoot((root) => Effect.gen(function* () {
    const created = yield* Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2DurableRuntime
      yield* commitRevision(runtime, 0, 0)
      const staleAfterNextCommit = yield* compileCanonicalAtomV2DurableRdfProjection(runtime)
      yield* commitRevision(runtime, 1, 1)
      const before = yield* runtime.snapshot
      const storageBefore = storageFingerprint(root)
      const artifact = yield* compileCanonicalAtomV2DurableRdfProjection(runtime)
      const duplicate = yield* compileCanonicalAtomV2DurableRdfProjection(runtime)
      const verified = yield* verifyCanonicalAtomV2DurableRdfProjection(runtime, artifact)
      const encoded = right(canonicalAtomV2DurableRdfProjectionBytes(artifact))
      const decoded = yield* decodeCanonicalAtomV2DurableRdfProjectionBytes(runtime, encoded)
      const storageAfter = storageFingerprint(root)
      const after = yield* runtime.snapshot
      const staleResult = yield* verifyCanonicalAtomV2DurableRdfProjection(
        runtime,
        staleAfterNextCommit
      ).pipe(Effect.either)
      return {
        after,
        artifact,
        before,
        decoded,
        duplicate,
        encoded,
        staleResult,
        storageAfter,
        storageBefore,
        verified
      }
    }).pipe(Effect.provide(fileLayer(root)))

    expect(created.artifact).toEqual(created.duplicate)
    expect(created.decoded).toEqual(created.artifact)
    expect(created.verified).toEqual(created.artifact)
    expect(created.before).toEqual(created.after)
    expect(created.storageAfter).toEqual(created.storageBefore)
    expect(Either.isLeft(created.staleResult)).toBe(true)
    expect(created.artifact.manifest.source).toMatchObject({
      journalLineageId: JOURNAL_LINEAGE,
      stateRevision: 2,
      recoveredRecordCount: 3,
      journalPrefixCommitment: {
        algorithm: HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_PREFIX_COMMITMENT_V1
      }
    })
    expect(created.artifact.manifest.source.journalPrefixCommitment.sha256).toMatch(/^[0-9a-f]{64}$/)
    expect(created.artifact.manifest.sourceAttestation).toBe(
      "LOCAL_POSIX_FILE_RUNTIME_ONE_RECOVERY_OBSERVATION_PREFIX_ATTESTED_GLOBAL_TAIL_AND_ANTIROLLBACK_NOT_ATTESTED"
    )
    expect(created.artifact.manifest.tailCompleteness).toBe(
      "ONE_RECOVERY_OBSERVATION_CONTIGUOUS_PREFIX_ONLY"
    )
    expect(created.artifact.manifest.antiRollback).toBe("NOT_ATTESTED")
    expect(created.artifact.manifest.writeBack).toBe("FORBIDDEN")
    expect(created.artifact.manifest.journalPrefixRecoveryLimits).toEqual({
      maximumRecords: 4_096,
      maximumRecoveredJournalBytes: 67_108_864
    })
    expect(created.artifact.manifest.nonclaims).toContain(
      "NOT_TOTAL_CONTENT_REPLAY_IO_OR_CPU_BUDGET"
    )

    const parsed = new Parser({ format: "N-Quads" }).parse(
      new TextDecoder().decode(created.artifact.projection.nquads)
    )
    expect(parsed.length).toBe(created.artifact.projection.manifest.counts.emittedQuads)

    const restarted = yield* Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2DurableRuntime
      const compiled = yield* compileCanonicalAtomV2DurableRdfProjection(runtime)
      const verified = yield* verifyCanonicalAtomV2DurableRdfProjection(runtime, created.artifact)
      const decoded = yield* decodeCanonicalAtomV2DurableRdfProjectionBytes(runtime, created.encoded)
      return { compiled, decoded, verified }
    }).pipe(Effect.provide(fileLayer(root)))
    expect(restarted.compiled).toEqual(created.artifact)
    expect(restarted.verified).toEqual(created.artifact)
    expect(restarted.decoded).toEqual(created.artifact)

    expect(created.duplicate).not.toBe(created.artifact)
    const firstByte = created.duplicate.projection.nquads[0]
    if (firstByte === undefined) throw new Error("compiled N-Quads unexpectedly empty")
    created.duplicate.projection.nquads[0] = firstByte ^ 0x01
    expect(Either.isLeft(
      canonicalAtomV2DurableRdfProjectionBytes(created.duplicate)
    )).toBe(true)
  }))
)

it.effect("exposes rollback as a shorter valid visible prefix but refuses the newer artifact", () =>
  withRoot((root) => Effect.gen(function* () {
    const newer = yield* Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2DurableRuntime
      yield* commitRevision(runtime, 0, 0)
      yield* commitRevision(runtime, 1, 1)
      return yield* compileCanonicalAtomV2DurableRdfProjection(runtime)
    }).pipe(Effect.provide(fileLayer(root)))

    const finalSlot = canonicalAtomV2StateJournalSlotName(
      JOURNAL_LINEAGE,
      schemaContent().binding.content.sha256,
      2
    )
    unlinkSync(join(root, "journal-slots", finalSlot))

    const rolledBack = yield* Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2DurableRuntime
      const current = yield* compileCanonicalAtomV2DurableRdfProjection(runtime)
      const olderVerification = yield* verifyCanonicalAtomV2DurableRdfProjection(
        runtime,
        newer
      ).pipe(Effect.either)
      return { current, olderVerification }
    }).pipe(Effect.provide(fileLayer(root)))

    expect(rolledBack.current.manifest.source.stateRevision).toBe(1)
    expect(rolledBack.current.manifest.source.recoveredRecordCount).toBe(2)
    expect(rolledBack.current.manifest.source.journalPrefixCommitment.sha256).not.toBe(
      newer.manifest.source.journalPrefixCommitment.sha256
    )
    expect(Either.isLeft(rolledBack.olderVerification)).toBe(true)
    expect(rolledBack.current.manifest.antiRollback).toBe("NOT_ATTESTED")
  }))
)

it.effect("fails closed instead of projecting a non-tail journal gap", () =>
  withRoot((root) => Effect.gen(function* () {
    const result = yield* Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2DurableRuntime
      yield* commitRevision(runtime, 0, 0)
      yield* commitRevision(runtime, 1, 1)
      const middleSlot = canonicalAtomV2StateJournalSlotName(
        JOURNAL_LINEAGE,
        schemaContent().binding.content.sha256,
        1
      )
      unlinkSync(join(root, "journal-slots", middleSlot))
      return yield* compileCanonicalAtomV2DurableRdfProjection(runtime).pipe(Effect.either)
    }).pipe(Effect.provide(fileLayer(root)))
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) expect(result.left.code).toBe("RECOVERY_FAILED")
  }))
)

it.effect("refuses the registered process-local memory test runtime as durable provenance", () =>
  Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const result = yield* compileCanonicalAtomV2DurableRdfProjection(runtime).pipe(
      Effect.either
    )
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) expect(result.left.code).toBe("RECOVERY_FAILED")
  }).pipe(
    Effect.provide(makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest(
      JOURNAL_LINEAGE,
      rawSchemaBytes(),
      grants()
    ))
  )
)

it.effect("refuses manifest, inner projection, canonical-byte, and runtime-boundary tampering", () =>
  withRoot((root) => Effect.gen(function* () {
    const artifact = yield* Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2DurableRuntime
      yield* commitRevision(runtime, 0, 0)
      return yield* compileCanonicalAtomV2DurableRdfProjection(runtime)
    }).pipe(Effect.provide(fileLayer(root)))
    const encoded = right(canonicalAtomV2DurableRdfProjectionBytes(artifact))
    const withSource = (
      source: CanonicalAtomV2DurableRdfProjection["manifest"]["source"]
    ) => ({
      ...artifact,
      manifest: { ...artifact.manifest, source }
    } as CanonicalAtomV2DurableRdfProjection)
    const manifestVariants: ReadonlyArray<CanonicalAtomV2DurableRdfProjection> = [
      withSource({
        ...artifact.manifest.source,
        journalPrefixCommitment: {
          ...artifact.manifest.source.journalPrefixCommitment,
          sha256: "0".repeat(64)
        }
      }),
      withSource({ ...artifact.manifest.source, stateRevision: 99 }),
      withSource({ ...artifact.manifest.source, stateSha256: "1".repeat(64) }),
      withSource({ ...artifact.manifest.source, recoveredRecordCount: 99 }),
      withSource({ ...artifact.manifest.source, recoveredJournalByteLength: 99 }),
      withSource({
        ...artifact.manifest.source,
        journalHead: { ...artifact.manifest.source.journalHead, sha256: "2".repeat(64) }
      }),
      withSource({
        ...artifact.manifest.source,
        schemaBinding: {
          ...artifact.manifest.source.schemaBinding,
          content: {
            ...artifact.manifest.source.schemaBinding.content,
            sha256: "3".repeat(64)
          }
        }
      })
    ]
    const tamperedProjection = {
      ...artifact,
      projection: {
        ...artifact.projection,
        nquads: Uint8Array.from([...artifact.projection.nquads, 0x0a])
      }
    } as CanonicalAtomV2DurableRdfProjection
    const tamperedInnerManifest = {
      ...artifact,
      projection: {
        ...artifact.projection,
        manifest: {
          ...artifact.projection.manifest,
          dataset: {
            ...artifact.projection.manifest.dataset,
            sha256: "4".repeat(64)
          }
        }
      }
    } as CanonicalAtomV2DurableRdfProjection
    const tamperedInnerBytes = right(canonicalAtomV2RdfProjectionBytes(
      tamperedInnerManifest.projection
    ))
    const recomputedInnerDescriptorForgery = {
      ...tamperedInnerManifest,
      manifest: {
        ...tamperedInnerManifest.manifest,
        innerProjection: {
          mediaType: tamperedInnerManifest.manifest.innerProjection.mediaType,
          byteLength: tamperedInnerBytes.byteLength,
          sha256: createHash("sha256").update(tamperedInnerBytes).digest("hex")
        }
      }
    } as CanonicalAtomV2DurableRdfProjection
    const encodedText = new TextDecoder().decode(encoded)
    const parsed = JSON.parse(encodedText) as {
      readonly manifest: unknown
      readonly projectionBase64Url: string
    }
    const modifiedBase64 = right(canonicalJsonBytes({
      ...parsed,
      projectionBase64Url: `${parsed.projectionBase64Url[0] === "A" ? "B" : "A"}${parsed.projectionBase64Url.slice(1)}`
    }))
    const duplicateKey = utf8(encodedText.replace(
      "{\"manifest\":",
      "{\"manifest\":null,\"manifest\":"
    ))
    const reordered = utf8(
      `{\"projectionBase64Url\":${JSON.stringify(parsed.projectionBase64Url)},\"manifest\":${JSON.stringify(parsed.manifest)}}`
    )
    const byteVariants = [
      Uint8Array.from([0x20, ...encoded]),
      Uint8Array.from([...encoded, 0x00]),
      Uint8Array.from([...encoded, 0xff]),
      duplicateKey,
      reordered,
      modifiedBase64
    ]

    const results = yield* Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2DurableRuntime
      return {
        manifests: yield* Effect.forEach(
          manifestVariants,
          (candidate) => verifyCanonicalAtomV2DurableRdfProjection(runtime, candidate).pipe(Effect.either),
          { concurrency: 1 }
        ),
        projection: yield* verifyCanonicalAtomV2DurableRdfProjection(runtime, tamperedProjection).pipe(Effect.either),
        innerManifest: yield* verifyCanonicalAtomV2DurableRdfProjection(runtime, tamperedInnerManifest).pipe(Effect.either),
        bytes: yield* Effect.forEach(
          byteVariants,
          (candidate) => decodeCanonicalAtomV2DurableRdfProjectionBytes(runtime, candidate).pipe(Effect.either),
          { concurrency: 1 }
        )
      }
    }).pipe(Effect.provide(fileLayer(root)))
    expect(results.manifests.every(Either.isLeft)).toBe(true)
    expect(Either.isLeft(results.projection)).toBe(true)
    expect(Either.isLeft(results.innerManifest)).toBe(true)
    expect(results.bytes.every(Either.isLeft)).toBe(true)
    expect(Either.isLeft(canonicalAtomV2DurableRdfProjectionBytes(
      recomputedInnerDescriptorForgery
    ))).toBe(true)
    expect(Either.isLeft(canonicalAtomV2DurableRdfProjectionBytes({
      manifest: null,
      projection: null
    } as unknown as CanonicalAtomV2DurableRdfProjection))).toBe(true)
    const invalidEnvelopeVariants: ReadonlyArray<CanonicalAtomV2DurableRdfProjection> = [
      { ...artifact, unexpected: true },
      { ...artifact, manifest: { ...artifact.manifest, unexpected: true } },
      { ...artifact, manifest: { ...artifact.manifest, writeBack: "ALLOWED" } },
      {
        ...artifact,
        manifest: {
          ...artifact.manifest,
          journalPrefixRecoveryLimits: {
            ...artifact.manifest.journalPrefixRecoveryLimits,
            maximumRecords: 4_095
          }
        }
      },
      {
        ...artifact,
        manifest: {
          ...artifact.manifest,
          invalidatedBy: [...artifact.manifest.invalidatedBy].reverse()
        }
      },
      {
        ...artifact,
        manifest: {
          ...artifact.manifest,
          nonclaims: [...artifact.manifest.nonclaims].reverse()
        }
      }
    ] as unknown as ReadonlyArray<CanonicalAtomV2DurableRdfProjection>
    expect(invalidEnvelopeVariants.every((candidate) =>
      Either.isLeft(canonicalAtomV2DurableRdfProjectionBytes(candidate))
    )).toBe(true)

    const unregistered = yield* compileCanonicalAtomV2DurableRdfProjection(
      {} as CanonicalAtomV2DurableRuntime["Type"]
    ).pipe(Effect.either)
    expect(Either.isLeft(unregistered)).toBe(true)
    if (Either.isLeft(unregistered)) expect(unregistered.left.code).toBe("RECOVERY_FAILED")
  }))
)
