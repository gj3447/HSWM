import { createHash } from "node:crypto"
import { existsSync, mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "vitest"
import { Effect, Either } from "effect"

import {
  describeCanonicalAtomV2Envelope,
  makeCanonicalAtomV2ContentBoundInput
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { CanonicalAtomV2DurableRuntime } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import {
  makeEphemeralLocalPermitIssuer,
  makeLocalPermitVerifierContext,
  type LocalPermitIssuer
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-local-permit-commit.js"
import {
  describeCanonicalAtomV2StateJournalRecord,
  makeCanonicalAtomV2StateJournalCommit
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-state-journal.js"
import { canonicalJsonBytes } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-json.js"
import {
  evolveCanonicalAtomsV2,
  makeCanonicalAtomV2AcceptedReceipt,
  snapshotCanonicalAtomV2State
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-domain.js"
import { HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import { makeVerifiedAdmissionGatewayV2 } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-verified-admission-gateway.js"
import {
  authorizationRef,
  makeSemanticLifecycleFileLayer,
  scope,
  seedSemanticLifecycle
} from "../../src/hswm/effect-runtime/src/semantic-lifecycle-runtime.js"

const fixedClock = (): Date => new Date("2026-10-07T00:00:00.000Z")
const hex = (digit: string): string => digit.repeat(64)
const digest = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex")

const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw value.left
  return value.right
}
const canonicalStateBytes = (state: Parameters<typeof snapshotCanonicalAtomV2State>[0]): Uint8Array =>
  right(canonicalJsonBytes(snapshotCanonicalAtomV2State(state)))

const nonce = (issuer: LocalPermitIssuer): string => {
  const minted = issuer.mintNonce()
  if (Either.isLeft(minted)) throw minted.left
  return minted.right.nonceDigest
}

/**
 * This is an observation predicate for the integration witness, not another
 * admission mechanism.  The generic durable journal remains reference-grant
 * authorized; the protected Permit journal validates its own signed state
 * bytes in a separate namespace.
 */
const matchesDomainTransition = (
  expected: {
    readonly beforeBytes: Uint8Array
    readonly afterBytes: Uint8Array
    readonly beforeRecordSha256: string
    readonly afterRecordSha256: string
  },
  observed: {
    readonly preStateBytes: Uint8Array
    readonly postStateBytes: Uint8Array
    readonly priorRecordDigest: string
    readonly nextRecordDigest: string
  }
): boolean =>
  Buffer.from(expected.beforeBytes).equals(Buffer.from(observed.preStateBytes)) &&
  Buffer.from(expected.afterBytes).equals(Buffer.from(observed.postStateBytes)) &&
  expected.beforeRecordSha256 === observed.priorRecordDigest &&
  expected.afterRecordSha256 === observed.nextRecordDigest

it("binds one native Permit approval to the same durable transition bytes and fresh read frame", async () => {
  const leanCli = join(process.cwd(), "../../../formal/.lake/build/bin/HSWMAdmissionKernelCli")
  expect(existsSync(leanCli)).toBe(true)

  const root = mkdtempSync(join(tmpdir(), "hswm-journal-v2-durability-trace-"))
  try {
    const transition = await Effect.runPromise(
      Effect.gen(function* () {
        const runtime = yield* CanonicalAtomV2DurableRuntime
        yield* seedSemanticLifecycle
        const before = yield* runtime.snapshot
        const template = before.canonical.atoms.find((atom) => atom.kind === "semantic_participant")
        if (template === undefined) throw new Error("semantic fixture omitted a participant")
        const evidence = yield* runtime.stageContent("text/plain", Uint8Array.from(Buffer.from("journal-v2 trace evidence")))
        const atom = {
          ...template,
          key: { ...template.key, atomUid: "atom:journal-v2-durability-trace" },
          provenance: {
            mode: "DERIVATION" as const,
            evidenceSha256: evidence.sha256,
            sourceRef: template.key
          }
        }
        const envelope = right(describeCanonicalAtomV2Envelope(atom))
        const candidate = makeCanonicalAtomV2ContentBoundInput(
          runtime.schemaContent.content.sha256,
          {
            _tag: "CommitCanonicalAtomsV2",
            contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
            transitionId: "transition:journal-v2-durability-trace",
            expectedStateRevision: before.canonical.revision,
            schemaVersion: runtime.schema.schemaVersion,
            actorClaim: "fixture:journal-v2-durability-trace",
            authorizationRef,
            scope,
            decidedAt: "2026-10-07T00:00:00.000Z",
            traceRef: null,
            readSet: [template.key],
            writes: [atom],
            provenanceSha256: evidence.sha256
          },
          [{ key: atom.key, payload: atom.content, envelope }]
        )
        const predicted = right(makeCanonicalAtomV2StateJournalCommit(
          runtime.schema,
          {
            state: before.canonical,
            descriptor: before.journalHead,
            journalLineageId: before.journalLineageId,
            schema: runtime.schemaContent
          },
          makeCanonicalAtomV2AcceptedReceipt(
            candidate.command,
            before.canonical.revision,
            before.canonical.revision + 1
          ),
          candidate.writeBindings,
          [atom]
        ))
        const predictedState = canonicalStateBytes(
          right(evolveCanonicalAtomsV2(runtime.schema, before.canonical, candidate.command))
        )
        const beforeBytes = canonicalStateBytes(before.canonical)
        return Object.freeze({
          before,
          candidate,
          beforeBytes,
          afterBytes: predictedState,
          content: evidence,
          journal: right(describeCanonicalAtomV2StateJournalRecord(predicted))
        })
      }).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)))
    )

    const issuer = makeEphemeralLocalPermitIssuer({
      keyId: "key:journal-v2-durability-trace",
      authorizer: "principal:journal-v2-durability-trace",
      policyVersion: "policy:journal-v2-durability-trace",
      revocationEpoch: 0,
      clock: fixedClock
    })
    if (Either.isLeft(issuer)) throw issuer.left
    const verifier = makeLocalPermitVerifierContext(issuer.right.trustSnapshotBytes)
    if (Either.isLeft(verifier)) throw verifier.left
    const issued = issuer.right.issue({
      permitId: "permit:journal-v2-durability-trace",
      executionId: "execution:journal-v2-durability-trace",
      executionIntentDigest: hex("1"),
      permitDigest: hex("2"),
      proposalDigest: hex("3"),
      transitionInvariantDigest: hex("4"),
      // The Permit journal is separately sequenced, while these record
      // digests bind it to the exact generic durable transition below.
      priorHead: {
        lineageId: "lineage:permit:journal-v2-durability-trace",
        sequence: 0,
        stateDigest: digest(transition.beforeBytes),
        recordDigest: transition.before.journalHead.sha256
      },
      expectedNextHead: {
        lineageId: "lineage:permit:journal-v2-durability-trace",
        sequence: 1,
        stateDigest: digest(transition.afterBytes),
        recordDigest: transition.journal.sha256
      },
      target: {
        schemaVersion: "schema:journal-v2-durability-trace",
        lineageId: transition.before.journalLineageId,
        atomUid: "atom:journal-v2-durability-trace"
      },
      expectedRevision: "permit-revision:0",
      candidateRevision: "permit-revision:1",
      authorizationRef: "authorization:journal-v2-durability-trace",
      scope: "scope:journal-v2-durability-trace",
      nonceDigest: nonce(issuer.right),
      linearizationIndex: 1
    }, 60_000)
    if (Either.isLeft(issued)) throw issued.left

    const gateway = makeVerifiedAdmissionGatewayV2(
      root,
      verifier.right,
      { leanExecutable: leanCli },
      fixedClock
    )
    if (Either.isLeft(gateway)) throw gateway.left
    const published = await Effect.runPromise(gateway.right.submit({
      ...issued.right,
      preStateBytes: transition.beforeBytes,
      postStateBytes: transition.afterBytes
    }))

    const committed = await Effect.runPromise(
      Effect.gen(function* () {
        const runtime = yield* CanonicalAtomV2DurableRuntime
        const receipt = yield* runtime.submit(transition.candidate)
        const snapshot = yield* runtime.snapshot
        return Object.freeze({ receipt, snapshot })
      }).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)))
    )
    expect(committed.snapshot.journalHead).toEqual(transition.journal)

    const restartedGateway = makeVerifiedAdmissionGatewayV2(
      root,
      verifier.right,
      { leanExecutable: leanCli },
      fixedClock
    )
    if (Either.isLeft(restartedGateway)) throw restartedGateway.left
    const recoveredPermit = await Effect.runPromise(restartedGateway.right.recover())
    const restartedFrame = await Effect.runPromise(
      Effect.gen(function* () {
        const runtime = yield* CanonicalAtomV2DurableRuntime
        const snapshot = yield* runtime.snapshot
        const history = yield* runtime.history
        const content = yield* runtime.readContent(transition.content)
        return Object.freeze({ snapshot, history, content })
      }).pipe(Effect.provide(makeSemanticLifecycleFileLayer(root)))
    )

    expect(recoveredPermit.commits).toHaveLength(1)
    const readPermit = recoveredPermit.commits[0]!
    expect(readPermit.commit.recordSha256).toBe(published.commit.recordSha256)
    expect(readPermit.decision.requestSha256).toBe(published.decision.requestSha256)
    expect(readPermit.decision.decisionSha256).toBe(published.decision.decisionSha256)
    expect(readPermit.commit.postStateBytes).toEqual(transition.afterBytes)
    expect(restartedFrame.snapshot.canonical).toEqual(committed.snapshot.canonical)
    expect(restartedFrame.snapshot.journalHead).toEqual(transition.journal)
    expect(restartedFrame.history.at(-1)?.record).toEqual(transition.journal)
    expect(restartedFrame.content).toEqual(Uint8Array.from(Buffer.from("journal-v2 trace evidence")))

    const expected = {
      beforeBytes: transition.beforeBytes,
      afterBytes: transition.afterBytes,
      beforeRecordSha256: transition.before.journalHead.sha256,
      afterRecordSha256: transition.journal.sha256
    }
    const observed = {
      preStateBytes: readPermit.commit.priorHead.stateDigest === digest(transition.beforeBytes)
        ? transition.beforeBytes
        : new Uint8Array(),
      postStateBytes: readPermit.commit.postStateBytes,
      priorRecordDigest: readPermit.commit.priorHead.recordDigest,
      nextRecordDigest: readPermit.commit.expectedNextHead.recordDigest
    }
    expect(matchesDomainTransition(expected, observed)).toBe(true)
    expect(matchesDomainTransition(expected, {
      ...observed,
      postStateBytes: Uint8Array.from([...observed.postStateBytes, 0])
    })).toBe(false)
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
}, 30_000)
