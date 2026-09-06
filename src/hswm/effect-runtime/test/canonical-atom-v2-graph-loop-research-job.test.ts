import { mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Either, Layer } from "effect"

import {
  CanonicalAtomV2DurableGraphView
} from "../src/canonical-atom-v2-durable-runtime.js"
import {
  GraphLoopEngineeringController,
  makeGraphLoopEngineeringFileLayer
} from "../src/canonical-atom-v2-graph-loop-engineering.js"
import {
  GraphLoopResearchProcessRunner,
  makeGraphLoopResearchProcessRunnerLayer
} from "../src/canonical-atom-v2-graph-loop-research-job.js"
import {
  HSWM_GRAPH_LOOP_RESEARCH_JOB_PROCESS_V1_CONTRACT_VERSION,
  describeGraphLoopResearchJobProcessFailure,
  executeGraphLoopResearchJobProcess
} from "../src/canonical-atom-v2-graph-loop-job-process.js"
import { NodePosixServicesLive } from "../src/effect-posix-services.js"
import { runProcessMain, type ProcessIo } from "../src/effect-process-main.js"
import {
  decodeCanonicalAtomV2SchemaContent,
  type CanonicalAtomV2ContentAuthorizationGrant
} from "../src/canonical-atom-v2-content-bound.js"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"
import {
  HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  HSWM_SUPERSEDES_REFERENCE_ROLE,
  HSWM_SUPERSEDES_REFERENCE_TYPE,
  type HSWMCanonicalSchemaV2
} from "../src/canonical-atom-v2-schema.js"

const SCHEMA_VERSION = "hswm:test:graph-loop-job:v1"
const JOURNAL_LINEAGE = "journal:graph-loop-job:main"
const AUTHORIZATION = "authorization:graph-loop-job"
const SCOPE = "scope:graph-loop-job"

const schema = (): HSWMCanonicalSchemaV2 => ({
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion: SCHEMA_VERSION,
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement: "Fixture bootstrap is bounded and non-scientific.",
  owners: [{ address: "owner:graph-loop-job", obligation: "Own bounded local research-control atoms." }],
  kinds: [{
    kind: "kind:graph-loop-job",
    form: "ENTITY",
    revisionPolicy: "LINEAR",
    allowedOwners: ["owner:graph-loop-job"],
    minimumArity: 0,
    referenceContracts: [{
      referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
      roles: [{
        role: HSWM_SUPERSEDES_REFERENCE_ROLE,
        targetKinds: ["kind:graph-loop-job"],
        minimum: 0,
        maximum: 1
      }]
    }]
  }]
})

const rawSchema = (): Uint8Array =>
  new TextEncoder().encode(JSON.stringify(schema()))

const grants = (): ReadonlyArray<CanonicalAtomV2ContentAuthorizationGrant> => {
  const decoded = decodeCanonicalAtomV2SchemaContent(rawSchema())
  if (Either.isLeft(decoded)) throw new Error("fixture schema failed to decode")
  return [{
    authorizationRef: AUTHORIZATION,
    schemaVersion: SCHEMA_VERSION,
    schemaContentSha256: decoded.right.binding.content.sha256,
    scopes: [SCOPE]
  }]
}

const withRoot = <A, E>(
  use: (root: string) => Effect.Effect<A, E>
): Effect.Effect<A, E> => {
  const root = mkdtempSync(join(tmpdir(), "hswm-graph-loop-job-"))
  return use(root).pipe(
    Effect.ensuring(Effect.sync(() => rmSync(root, { recursive: true, force: true })))
  )
}

it.effect("actual action and separately identified verifier subprocesses are forced through LE-0 retries and terminal recording", () =>
  withRoot((root) => Effect.gen(function* () {
    const standard = makeGraphLoopEngineeringFileLayer(
      join(root, "state"),
      join(root, "loop"),
      JOURNAL_LINEAGE,
      rawSchema(),
      grants()
    )
    const runnerLayer = makeGraphLoopResearchProcessRunnerLayer.pipe(
      Layer.provide(standard)
    )
    const result = yield* Effect.gen(function* () {
      const runner = yield* GraphLoopResearchProcessRunner
      return yield* runner.run({
        contract: {
          runId: "run:actual-job",
          triggerId: "trigger:actual-job",
          actorId: "actor:actual-job",
          verifierId: "verifier:actual-job",
          maximumAttempts: 2,
          maximumActions: 2
        },
        action: {
          argv: [process.execPath, "-e", "process.stdout.write('action-observed')"],
          cwd: root,
          timeoutMs: 10_000
        },
        verifier: {
          command: {
            argv: [
              process.execPath,
              "-e",
              "process.exit(process.env.HSWM_LE0_ATTEMPT === '1' ? 75 : 0)"
            ],
            cwd: root,
            timeoutMs: 10_000
          },
          acceptExitCodes: [0],
          retryExitCodes: [75]
        }
      })
    }).pipe(Effect.provide(runnerLayer))

    expect(result.terminal).toBe("STOPPED_ACCEPTED_NO_GRAPH_DELTA")
    expect(result.attempts).toBe(2)
    const verifier = result.verifier
    if (verifier === null) throw new Error("accepted job omitted verifier artifact")

    const observed = yield* Effect.gen(function* () {
      const controller = yield* GraphLoopEngineeringController
      const view = yield* CanonicalAtomV2DurableGraphView
      const states = yield* controller.recover
      const verifierBytes = yield* view.readContent(verifier)
      return { states, verifierBytes }
    }).pipe(Effect.provide(standard))

    expect(observed.states.get("run:actual-job")?.phase).toBe("STOPPED")
    expect(new TextDecoder().decode(observed.verifierBytes)).toContain(
      '"role":"VERIFIER"'
    )
  }))
)

it.effect("a verifier rejection is durably stopped rather than retried or admitted", () =>
  withRoot((root) => Effect.gen(function* () {
    const standard = makeGraphLoopEngineeringFileLayer(
      join(root, "state"),
      join(root, "loop"),
      JOURNAL_LINEAGE,
      rawSchema(),
      grants()
    )
    const runnerLayer = makeGraphLoopResearchProcessRunnerLayer.pipe(
      Layer.provide(standard)
    )
    const result = yield* Effect.gen(function* () {
      const runner = yield* GraphLoopResearchProcessRunner
      return yield* runner.run({
        contract: {
          runId: "run:verifier-reject",
          triggerId: "trigger:verifier-reject",
          actorId: "actor:verifier-reject",
          verifierId: "verifier:verifier-reject",
          maximumAttempts: 2,
          maximumActions: 2
        },
        action: {
          argv: [process.execPath, "-e", "process.stdout.write('action-observed')"],
          cwd: root,
          timeoutMs: 10_000
        },
        verifier: {
          command: {
            argv: [process.execPath, "-e", "process.exit(9)"],
            cwd: root,
            timeoutMs: 10_000
          },
          acceptExitCodes: [0],
          retryExitCodes: []
        }
      })
    }).pipe(Effect.provide(runnerLayer))

    expect(result.terminal).toBe("STOPPED_REJECTED")
    expect(result.attempts).toBe(1)
    const state = yield* Effect.gen(function* () {
      const controller = yield* GraphLoopEngineeringController
      return (yield* controller.recover).get("run:verifier-reject")
    }).pipe(Effect.provide(standard))
    expect(state?.phase).toBe("STOPPED")
  }))
)

it.effect("a verifier timeout is content-addressed and escalated without a hidden retry", () =>
  withRoot((root) => Effect.gen(function* () {
    const standard = makeGraphLoopEngineeringFileLayer(
      join(root, "state"),
      join(root, "loop"),
      JOURNAL_LINEAGE,
      rawSchema(),
      grants()
    )
    const runnerLayer = makeGraphLoopResearchProcessRunnerLayer.pipe(
      Layer.provide(standard)
    )
    const result = yield* Effect.gen(function* () {
      const runner = yield* GraphLoopResearchProcessRunner
      return yield* runner.run({
        contract: {
          runId: "run:verifier-timeout",
          triggerId: "trigger:verifier-timeout",
          actorId: "actor:verifier-timeout",
          verifierId: "verifier:verifier-timeout",
          maximumAttempts: 2,
          maximumActions: 2
        },
        action: {
          argv: [process.execPath, "-e", "process.stdout.write('action-observed')"],
          cwd: root,
          timeoutMs: 10_000
        },
        verifier: {
          command: {
            argv: [process.execPath, "-e", "setTimeout(() => {}, 60000)"],
            cwd: root,
            timeoutMs: 50
          },
          acceptExitCodes: [0],
          retryExitCodes: []
        }
      })
    }).pipe(Effect.provide(runnerLayer))

    expect(result.terminal).toBe("ESCALATED")
    expect(result.attempts).toBe(1)
    expect(result.verifier).not.toBeNull()
    const state = yield* Effect.gen(function* () {
      const controller = yield* GraphLoopEngineeringController
      return (yield* controller.recover).get("run:verifier-timeout")
    }).pipe(Effect.provide(standard))
    expect(state?.phase).toBe("ESCALATED")
    expect(state?.attempt).toBe(1)
  }))
)

type Reply = Record<string, unknown>

/** Writes the schema, grants, and one declared frozen input under `root` and returns the process request. */
const processRequest = (root: string): Reply => {
  const schemaPath = join(root, "schema.json")
  const grantsPath = join(root, "grants.json")
  const frozenInputPath = join(root, "frozen-input.json")
  writeFileSync(schemaPath, rawSchema())
  const grantBytes = canonicalJsonBytes(grants() as never)
  if (Either.isLeft(grantBytes)) throw new Error("fixture grants cannot form canonical JSON")
  writeFileSync(grantsPath, grantBytes.right)
  writeFileSync(frozenInputPath, "{\"fixture\":true}\n")
  return {
    _tag: "GraphLoopResearchJobProcessRequest",
    contractVersion: HSWM_GRAPH_LOOP_RESEARCH_JOB_PROCESS_V1_CONTRACT_VERSION,
    durableRoot: join(root, "state"),
    controlJournalRoot: join(root, "loop"),
    journalLineageId: "journal:job-process:main",
    schemaPath,
    grantsPath,
    frozenInputs: [{
      path: frozenInputPath,
      mediaType: "application/json"
    }],
    job: {
      contract: {
        runId: "run:job-process",
        triggerId: "trigger:job-process",
        actorId: "actor:job-process",
        verifierId: "verifier:job-process",
        maximumAttempts: 1,
        maximumActions: 1
      },
      action: {
        argv: [process.execPath, "-e", "process.stdout.write('process-action')"],
        cwd: root,
        timeoutMs: 10_000
      },
      verifier: {
        command: {
          argv: [process.execPath, "-e", "process.exit(0)"],
          cwd: root,
          timeoutMs: 10_000
        },
        acceptExitCodes: [0],
        retryExitCodes: []
      }
    }
  }
}

it.effect("the real job-process entrypoint constructs the protected runtime and runs action plus verifier commands", () =>
  withRoot((root) => Effect.gen(function* () {
    const result = (yield* executeGraphLoopResearchJobProcess(processRequest(root) as never)) as Reply
    expect(result["terminal"]).toBe("STOPPED_ACCEPTED_NO_GRAPH_DELTA")
    expect(result["attempts"]).toBe(1)
    expect(result["frozenInputs"]).toBeDefined()
  }).pipe(Effect.provide(NodePosixServicesLive)))
)

it.effect("the job process refuses shape drift and missing inputs as typed failures", () =>
  withRoot((root) => Effect.gen(function* () {
    const refusal = (request: Reply) =>
      executeGraphLoopResearchJobProcess(request as never).pipe(Effect.flip, Effect.map(describeGraphLoopResearchJobProcessFailure))
    const valid = processRequest(root)
    expect(yield* refusal({ ...valid, extra: 1 })).toMatch(/not a valid research job request/)
    expect(yield* refusal({ ...valid, _tag: "Other" })).toMatch(/request tag or contract version is invalid/)
    expect(yield* refusal({ ...valid, schemaPath: "relative/schema.json" })).toMatch(/not a valid research job request/)
    expect(yield* refusal({ ...valid, frozenInputs: [{ path: join(root, "absent.json"), mediaType: "application/json" }] })).toMatch(
      /frozen input is not a regular non-symlink file/
    )
  }).pipe(Effect.provide(NodePosixServicesLive)))
)

it.effect("the whole request runs through the single process boundary with in-memory io", () =>
  withRoot((root) => Effect.promise(async () => {
    const stdout: Array<string> = []
    const stderr: Array<string> = []
    const io = (input: string): ProcessIo => ({
      readStdin: () => Effect.succeed(input),
      writeStdout: (text) => Effect.sync(() => { stdout.push(text) }),
      writeStderr: (text) => Effect.sync(() => { stderr.push(text) })
    })
    const spec = {
      refusalPrefix: "HSWM_GRAPH_LOOP_RESEARCH_JOB_REFUSED",
      program: executeGraphLoopResearchJobProcess,
      describeFailure: describeGraphLoopResearchJobProcessFailure
    }
    const canonical = new TextDecoder().decode(Either.getOrThrow(canonicalJsonBytes(processRequest(root) as never)))
    expect(await runProcessMain(spec, io(canonical))).toBe(0)
    expect(stdout).toHaveLength(1)
    const reply = JSON.parse(stdout[0]!) as Reply
    expect(reply["_tag"]).toBe("GraphLoopResearchJobProcessResult")
    expect(reply["terminal"]).toBe("STOPPED_ACCEPTED_NO_GRAPH_DELTA")
    expect(await runProcessMain(spec, io("not json"))).toBe(2)
    expect(stderr[0]).toMatch(/^HSWM_GRAPH_LOOP_RESEARCH_JOB_REFUSED: stdin must be canonical JSON/)
  }))
)
