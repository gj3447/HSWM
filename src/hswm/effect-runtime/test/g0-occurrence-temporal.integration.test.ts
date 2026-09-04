import { createHash } from "node:crypto"
import { execFileSync } from "node:child_process"
import { readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

import { TestWorkflowEnvironment } from "@temporalio/testing"
import { Worker } from "@temporalio/worker"
import { afterAll, beforeAll, describe, expect, it } from "vitest"
import { Effect } from "effect"

import {
  HSWM_G0_TEMPORAL_SIGNAL_ENVELOPE_V1,
  HSWM_G0_TEMPORAL_SIGNAL_NAME,
  type G0TemporalWorkflowResultV1
} from "../src/g0-occurrence-temporal-contract.js"
import {
  createG0TemporalWorker,
  signalG0TemporalOneShot,
  startG0TemporalOneShot
} from "../src/g0-occurrence-temporal-runtime.js"

const enabled = process.env["HSWM_RUN_G0_TEMPORAL_INTEGRATION"] === "1"
const digest = (value: number): string => value.toString(16).padStart(64, "0")
const workflowsPath = fileURLToPath(
  new URL("../src/g0-occurrence-temporal-workflow.ts", import.meta.url)
)

const toolchain = JSON.parse(readFileSync(
  new URL("../assets/g0-temporal-test-toolchain.json", import.meta.url),
  "utf8"
)) as {
  readonly status: string
  readonly temporal_cli: {
    readonly version: string
    readonly server_version: string
    readonly sha256: string
    readonly license_sha256: string
  }
}

const occurrence = (uid: string, timeout = 20) => ({
  occurrence_uid: uid,
  worm_claim_receipt: { name: "candidate_worm_claim_receipt", sha256: digest(1) },
  registration_evidence: { name: "registration_evidence", sha256: digest(2) },
  occurrence_timeout_seconds: timeout
})

const transition = (
  nextPhase: string,
  value: number,
  timing: "PRE_PULSE" | "POST_PULSE"
) => ({
  next_phase: nextPhase,
  evidence: { name: `evidence_${value}`, sha256: digest(value) },
  timing
})

describe.skipIf(!enabled).sequential("G0 TypeScript Temporal simulated operator rehearsal", () => {
  let environment: TestWorkflowEnvironment
  let configuration: Readonly<Record<string, unknown>>

  beforeAll(async () => {
    const cliPath = process.env["HSWM_G0_TEMPORAL_CLI_PATH"]
    if (cliPath === undefined || cliPath.length === 0) {
      throw new Error("HSWM_G0_TEMPORAL_CLI_PATH is required for the pinned integration lane")
    }
    const cliBytes = readFileSync(cliPath)
    expect(createHash("sha256").update(cliBytes).digest("hex")).toBe(toolchain.temporal_cli.sha256)
    expect(createHash("sha256").update(readFileSync(join(dirname(cliPath), "LICENSE"))).digest("hex"))
      .toBe(toolchain.temporal_cli.license_sha256)
    const version = execFileSync(cliPath, ["--version"], { encoding: "utf8" })
    expect(version).toContain(`temporal version ${toolchain.temporal_cli.version}`)
    expect(version).toContain(`Server ${toolchain.temporal_cli.server_version}`)
    expect(toolchain.status).toBe("LOCAL_ENGINEERING_INTEGRATION_PIN_NOT_EXTERNAL_QUALIFICATION")

    environment = await TestWorkflowEnvironment.createLocal({
      server: {
        executable: { type: "existing-path", path: cliPath },
        namespace: "default",
        ui: false,
        log: { format: "pretty", level: "error" }
      }
    })
    configuration = Object.freeze({
      address: environment.address,
      namespace: "default",
      task_queue: "hswm-g0-ts-integration",
      signal_authorization_binding_sha256: digest(4)
    })
  }, 60_000)

  afterAll(async () => {
    await environment.teardown()
  })

  const worker = async (): Promise<Worker> => Effect.runPromise(
    createG0TemporalWorker(configuration, workflowsPath, environment.nativeConnection)
  )

  it("runs a real durable happy path, rejects duplicate UID, and replays history", async () => {
    const temporalWorker = await worker()
    const execution = await temporalWorker.runUntil(async () => {
      const request = {
        occurrence: occurrence("future-outcome-ts-integration-happy"),
        executionClassification: "SIMULATED_OPERATOR_REHEARSAL" as const,
        operatorQualificationReceiptSha256: digest(3)
      }
      const handle = await Effect.runPromise(startG0TemporalOneShot(
        environment.client.workflow,
        configuration,
        request
      ))
      const steps = [
        transition("SCHEDULED", 5, "PRE_PULSE"),
        transition("PRE_PULSE_SEALED", 6, "PRE_PULSE"),
        transition("PULSE_VERIFIED", 7, "POST_PULSE"),
        transition("REVEALED", 8, "POST_PULSE"),
        transition("DUAL_EVALUATED", 9, "POST_PULSE"),
        transition("SEALED", 10, "POST_PULSE")
      ] as const
      for (const step of steps) {
        await Effect.runPromise(signalG0TemporalOneShot(handle, digest(4), step))
      }
      const result = await handle.result()
      const history = await handle.fetchHistory()
      const duplicate = await Effect.runPromiseExit(startG0TemporalOneShot(
        environment.client.workflow,
        configuration,
        request
      ))
      return { result, history, duplicate, runId: handle.firstExecutionRunId }
    })

    expect(execution.result).toMatchObject({
      occurrence_uid: "future-outcome-ts-integration-happy",
      phase: "SEALED",
      terminal: true,
      orchestration_authority: "TYPESCRIPT_TEMPORAL",
      temporal_execution_observed: true,
      execution_classification: "SIMULATED_OPERATOR_REHEARSAL",
      external_operator_qualification_claimed: false,
      scientific_evidence_claimed: false,
      publication_eligible: false,
      g0_passed: false
    } satisfies Partial<G0TemporalWorkflowResultV1>)
    expect(execution.result.evidence_sha256s).toHaveLength(8)
    expect(execution.runId).toMatch(/^[0-9a-f-]{36}$/u)
    expect(execution.history.events?.length ?? 0).toBeGreaterThan(2)
    expect(execution.duplicate._tag).toBe("Failure")
    await Worker.runReplayHistory({ workflowsPath }, execution.history)
  }, 60_000)

  it("turns a policy-binding mismatch into terminal VOID", async () => {
    const temporalWorker = await worker()
    const result = await temporalWorker.runUntil(async () => {
      const handle = await Effect.runPromise(startG0TemporalOneShot(
        environment.client.workflow,
        configuration,
        {
          occurrence: occurrence("future-outcome-ts-integration-auth"),
          executionClassification: "SIMULATED_OPERATOR_REHEARSAL",
          operatorQualificationReceiptSha256: digest(3)
        }
      ))
      await handle.signal(HSWM_G0_TEMPORAL_SIGNAL_NAME, {
        schema_version: HSWM_G0_TEMPORAL_SIGNAL_ENVELOPE_V1,
        signal_authorization_binding_sha256: digest(99),
        transition: transition("SCHEDULED", 5, "PRE_PULSE")
      })
      return handle.result()
    })
    expect(result.phase).toBe("VOID")
    expect(result.void_reason).toBe("INVALID_EVIDENCE_DESCRIPTOR")
    expect(result.g0_passed).toBe(false)
  }, 60_000)

  it("bounds pre-worker queued signals and makes post-seal backlog terminal re-entry", async () => {
    const temporalWorker = await worker()
    const handle = await Effect.runPromise(startG0TemporalOneShot(
      environment.client.workflow,
      configuration,
      {
        occurrence: occurrence("future-outcome-ts-integration-overflow"),
        executionClassification: "SIMULATED_OPERATOR_REHEARSAL",
        operatorQualificationReceiptSha256: digest(3)
      }
    ))
    const steps = [
      transition("SCHEDULED", 5, "PRE_PULSE"),
      transition("PRE_PULSE_SEALED", 6, "PRE_PULSE"),
      transition("PULSE_VERIFIED", 7, "POST_PULSE"),
      transition("REVEALED", 8, "POST_PULSE"),
      transition("DUAL_EVALUATED", 9, "POST_PULSE"),
      transition("SEALED", 10, "POST_PULSE"),
      transition("SEALED", 11, "POST_PULSE"),
      transition("SEALED", 12, "POST_PULSE"),
      transition("SEALED", 13, "POST_PULSE")
    ] as const
    for (const step of steps) {
      await Effect.runPromise(signalG0TemporalOneShot(handle, digest(4), step))
    }
    const result = await temporalWorker.runUntil(() => handle.result())
    expect(result.phase).toBe("VOID")
    expect(result.void_reason).toBe("TERMINAL_REENTRY")
    expect(result.rejected_evidence_sha256).toBe(digest(11))
    expect(result.evidence_sha256s).toHaveLength(8)
  }, 60_000)

  it("does not let queue overflow overwrite an earlier non-SEALED VOID reason", async () => {
    const temporalWorker = await worker()
    const handle = await Effect.runPromise(startG0TemporalOneShot(
      environment.client.workflow,
      configuration,
      {
        occurrence: occurrence("future-outcome-ts-integration-overflow-invalid"),
        executionClassification: "SIMULATED_OPERATOR_REHEARSAL",
        operatorQualificationReceiptSha256: digest(3)
      }
    ))
    for (let index = 0; index < 9; index += 1) {
      await handle.signal(HSWM_G0_TEMPORAL_SIGNAL_NAME, {
        schema_version: HSWM_G0_TEMPORAL_SIGNAL_ENVELOPE_V1,
        signal_authorization_binding_sha256: digest(99),
        transition: transition("SCHEDULED", 20 + index, "PRE_PULSE")
      })
    }
    const result = await temporalWorker.runUntil(() => handle.result())
    expect(result.phase).toBe("VOID")
    expect(result.void_reason).toBe("INVALID_EVIDENCE_DESCRIPTOR")
    expect(result.rejected_evidence_sha256).toBeNull()
  }, 60_000)

  it("refuses a raw SDK attempt to bypass the blocked LIVE admission", async () => {
    const temporalWorker = await worker()
    const outcome = await temporalWorker.runUntil(async () => {
      const handle = await environment.client.workflow.start(
        "hswm_g0_occurrence_one_shot_workflow",
        {
          args: [{
            schema_version: "hswm-g0-temporal-typescript-authority/v1",
            occurrence: occurrence("future-outcome-ts-integration-live-bypass"),
            execution_classification: "LIVE_EXTERNAL_OPERATOR",
            operator_qualification_receipt_sha256: digest(3),
            signal_authorization_binding_sha256: digest(4)
          }],
          taskQueue: "hswm-g0-ts-integration",
          workflowId: "g0-occurrence/future-outcome-ts-integration-live-bypass",
          retry: { maximumAttempts: 1 }
        }
      )
      try {
        await handle.result()
        return "unexpected-completion"
      } catch {
        return "live-admission-refused"
      }
    })
    expect(outcome).toBe("live-admission-refused")
  }, 60_000)

  it("uses the deterministic occurrence deadline and returns LATE VOID", async () => {
    const temporalWorker = await worker()
    const result = await temporalWorker.runUntil(async () => {
      const handle = await Effect.runPromise(startG0TemporalOneShot(
        environment.client.workflow,
        configuration,
        {
          occurrence: occurrence("future-outcome-ts-integration-timeout", 1),
          executionClassification: "SIMULATED_OPERATOR_REHEARSAL",
          operatorQualificationReceiptSha256: digest(3)
        }
      ))
      return handle.result()
    })
    expect(result.phase).toBe("VOID")
    expect(result.void_reason).toBe("LATE")
    expect(result.temporal_execution_observed).toBe(true)
    expect(result.publication_eligible).toBe(false)
  }, 60_000)
})

it("does not silently enable the integration lane", () => {
  expect(enabled).toBe(process.env["HSWM_RUN_G0_TEMPORAL_INTEGRATION"] === "1")
  expect(toolchain.status).toBe("LOCAL_ENGINEERING_INTEGRATION_PIN_NOT_EXTERNAL_QUALIFICATION")
})
