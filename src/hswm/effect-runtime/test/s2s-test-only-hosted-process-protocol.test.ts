import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import * as publicApi from "../src/index.js"
import {
  canonicalS2SControlJsonBytes,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import {
  S2S_TEST_ONLY_HOSTED_PROCESS_PROTOCOL_VERSION,
  canonicalS2STestOnlyHostedProcessFrame,
  decodeS2STestOnlyHostedProcessReadyFrame,
  decodeS2STestOnlyHostedProcessReconcileFrame,
  decodeS2STestOnlyHostedProcessTerminalFrame,
  makeS2STestOnlyHostedProcessBinding,
  makeS2STestOnlyHostedProcessReady,
  makeS2STestOnlyHostedProcessReconcileFrame,
  makeS2STestOnlyHostedProcessTerminal,
  type S2STestOnlyHostedProcessBinding,
  type S2STestOnlyHostedProcessReady,
  type S2STestOnlyHostedProcessTerminal
} from "../src/s2s-test-only-hosted-process-protocol.js"

const token = (byte = 7): Uint8Array => new Uint8Array(32).fill(byte)

const bindingInput = (
  stage: "REGISTER" | "CONFIRM" | "ADJUDICATE" = "REGISTER",
  jobId: "register" | "confirm" | "adjudicate" = "register",
  feasibilityAttempt: 1 | 2 | 3 = 1
) => ({
  protocolVersion: S2S_TEST_ONLY_HOSTED_PROCESS_PROTOCOL_VERSION,
  nonce: "11".repeat(32),
  workflowRunId: 73,
  workflowRunAttempt: 1 as const,
  feasibilityAttempt,
  stage,
  jobId,
  runtimeIdentity: {
    rootPid: 701,
    procStartTicks: "12345",
    bootIdSha256: "22".repeat(32),
    nodeVersion: "v24.13.0",
    nodeExecutableSha256: "33".repeat(32),
    nodeExecutableDevice: 8,
    nodeExecutableInode: 99,
    instanceId: "44".repeat(32)
  }
})

const right = <A, E>(value: Either.Either<A, E>): A => {
  expect(Either.isRight(value)).toBe(true)
  if (Either.isLeft(value)) throw new Error("expected Right")
  return value.right
}

const binding = (
  stage: "REGISTER" | "CONFIRM" | "ADJUDICATE" = "REGISTER",
  jobId: "register" | "confirm" | "adjudicate" = "register",
  feasibilityAttempt: 1 | 2 | 3 = 1
): S2STestOnlyHostedProcessBinding =>
  right(
    makeS2STestOnlyHostedProcessBinding(
      bindingInput(stage, jobId, feasibilityAttempt)
    )
  )

const ready = (
  selectedBinding: S2STestOnlyHostedProcessBinding = binding(),
  selectedToken: Uint8Array = token()
): S2STestOnlyHostedProcessReady =>
  right(
    makeS2STestOnlyHostedProcessReady(
      selectedBinding,
      selectedToken,
      rawS2SFileSha256(selectedToken)
    )
  )

const canonical = (document: unknown): Uint8Array =>
  right(canonicalS2SControlJsonBytes(document))

const reason = <A>(
  value: Either.Either<A, { readonly reason: string }>
): string => {
  expect(Either.isLeft(value)).toBe(true)
  if (Either.isRight(value)) throw new Error("expected Left")
  return value.left.reason
}

it("authenticates canonical READY, RECONCILE, and TERMINAL frames", () => {
  const selectedToken = token()
  const selectedBinding = binding()
  const selectedReady = ready(selectedBinding, selectedToken)
  const readyFrame = right(
    canonicalS2STestOnlyHostedProcessFrame(selectedReady, "READY")
  )
  expect(
    right(
      decodeS2STestOnlyHostedProcessReadyFrame(readyFrame, selectedToken)
    )
  ).toEqual(selectedReady)

  const reconcileFrame = right(
    makeS2STestOnlyHostedProcessReconcileFrame(
      selectedReady,
      "success",
      selectedToken
    )
  )
  expect(
    right(
      decodeS2STestOnlyHostedProcessReconcileFrame(
        reconcileFrame,
        selectedBinding,
        selectedToken
      )
    ).uploadStepOutcome
  ).toBe("success")

  const terminal = right(
    makeS2STestOnlyHostedProcessTerminal(
      selectedBinding,
      "success",
      "RECONCILED_ACTION_SUCCESS",
      1,
      selectedToken
    )
  )
  const terminalFrame = canonical(terminal)
  expect(
    right(
      decodeS2STestOnlyHostedProcessTerminalFrame(
        terminalFrame,
        selectedBinding,
        selectedToken
      )
    )
  ).toEqual(terminal)
})

it("admits exactly the three fixed stage/job pairs and attempts", () => {
  const cases = [
    ["REGISTER", "register", 1],
    ["CONFIRM", "confirm", 2],
    ["ADJUDICATE", "adjudicate", 3]
  ] as const
  for (const [stage, jobId, attempt] of cases) {
    const value = binding(stage, jobId, attempt)
    expect(value.stage).toBe(stage)
    expect(value.jobId).toBe(jobId)
    expect(value.feasibilityAttempt).toBe(attempt)
    expect(Object.isFrozen(value)).toBe(true)
    expect(Object.isFrozen(value.runtimeIdentity)).toBe(true)
  }
  expect(
    reason(
      makeS2STestOnlyHostedProcessBinding(
        bindingInput("REGISTER", "confirm", 1)
      )
    )
  ).toBe("STAGE_JOB_MISMATCH")
  for (const [stage, jobId, attempt] of [
    ["REGISTER", "register", 2],
    ["REGISTER", "register", 3],
    ["CONFIRM", "confirm", 1],
    ["CONFIRM", "confirm", 3],
    ["ADJUDICATE", "adjudicate", 1],
    ["ADJUDICATE", "adjudicate", 2]
  ] as const) {
    expect(
      reason(
        makeS2STestOnlyHostedProcessBinding(
          bindingInput(stage, jobId, attempt)
        )
      )
    ).toBe("ATTEMPT_STAGE_MISMATCH")
  }
})

it("rejects wrong secrets and coherent-looking token commitment drift", () => {
  const selectedToken = token()
  const selectedReady = ready(binding(), selectedToken)
  const readyFrame = canonical(selectedReady)
  expect(
    reason(
      decodeS2STestOnlyHostedProcessReadyFrame(readyFrame, token(8))
    )
  ).toBe("AUTHENTICATION_FAILED")
  expect(
    reason(
      makeS2STestOnlyHostedProcessReady(
        binding(),
        selectedToken,
        "aa".repeat(32)
      )
    )
  ).toBe("SCHEMA_INVALID")
})

it("rejects stale nonce, PID/runtime drift, and outcome mutation", () => {
  const selectedToken = token()
  const selectedBinding = binding()
  const selectedReady = ready(selectedBinding, selectedToken)
  const reconcileFrame = right(
    makeS2STestOnlyHostedProcessReconcileFrame(
      selectedReady,
      "unknown",
      selectedToken
    )
  )
  const stale = right(
    makeS2STestOnlyHostedProcessBinding({
      ...bindingInput(),
      nonce: "55".repeat(32)
    })
  )
  expect(
    reason(
      decodeS2STestOnlyHostedProcessReconcileFrame(
        reconcileFrame,
        stale,
        selectedToken
      )
    )
  ).toBe("BINDING_MISMATCH")

  const mutated = new TextDecoder().decode(reconcileFrame).replace(
    '"uploadStepOutcome":"unknown"',
    '"uploadStepOutcome":"success"'
  )
  expect(
    reason(
      decodeS2STestOnlyHostedProcessReconcileFrame(
        new TextEncoder().encode(mutated),
        selectedBinding,
        selectedToken
      )
    )
  ).toBe("AUTHENTICATION_FAILED")
})

it("rejects noncanonical, duplicate, excess, and oversized frames", () => {
  const selectedToken = token()
  const selectedReady = ready(binding(), selectedToken)
  const readyText = new TextDecoder().decode(canonical(selectedReady))
  expect(
    reason(
      decodeS2STestOnlyHostedProcessReadyFrame(
        new TextEncoder().encode(` ${readyText}`),
        selectedToken
      )
    )
  ).toBe("FRAME_NON_CANONICAL")
  expect(
    reason(
      decodeS2STestOnlyHostedProcessReadyFrame(
        new TextEncoder().encode(
          readyText.replace(
            '"sequence":0',
            '"sequence":0,"sequence":0'
          )
        ),
        selectedToken
      )
    )
  ).toBe("FRAME_INVALID")
  expect(
    reason(
      decodeS2STestOnlyHostedProcessReadyFrame(
        canonical({ ...selectedReady, bearer: "forbidden" }),
        selectedToken
      )
    )
  ).toBe("SCHEMA_INVALID")
  expect(
    reason(
      decodeS2STestOnlyHostedProcessReadyFrame(
        new Uint8Array(2_049),
        selectedToken
      )
    )
  ).toBe("FRAME_INVALID")
})

it("freezes nonauthorizing success, failure, unknown, and void terminals", () => {
  const selectedBinding = binding()
  const selectedToken = token()
  const cases = [
    ["success", "RECONCILED_ACTION_SUCCESS", 1],
    ["failure", "RECONCILED_ACTION_FAILURE", 1],
    ["unknown", "RECONCILED_ACTION_UNKNOWN_NO_RETRY", 1],
    ["unknown", "VOID_NO_COMPLETION", 0]
  ] as const
  for (const [outcome, status, probeCount] of cases) {
    const terminal: S2STestOnlyHostedProcessTerminal = right(
      makeS2STestOnlyHostedProcessTerminal(
        selectedBinding,
        outcome,
        status,
        probeCount,
        selectedToken
      )
    )
    expect(Object.isFrozen(terminal)).toBe(true)
    expect(Object.isFrozen(terminal.binding)).toBe(true)
    expect(Object.isFrozen(terminal.rootPidObservations)).toBe(true)
    expect(terminal.productionCompletionClaimed).toBe(false)
    expect(terminal.externalExactlyOnceClaimed).toBe(false)
    expect(terminal.scientificEvidenceClaimed).toBe(false)
    expect(terminal.publicationRetryCount).toBe(0)
  }
})

it("rejects every inconsistent outcome, terminal status, and probe count", () => {
  const selectedBinding = binding()
  const selectedToken = token()
  for (const [outcome, status, probeCount] of [
    ["success", "RECONCILED_ACTION_FAILURE", 1],
    ["failure", "RECONCILED_ACTION_SUCCESS", 1],
    ["unknown", "RECONCILED_ACTION_FAILURE", 1],
    ["success", "RECONCILED_ACTION_SUCCESS", 0],
    ["unknown", "VOID_NO_COMPLETION", 1]
  ] as const) {
    expect(
      reason(
        makeS2STestOnlyHostedProcessTerminal(
          selectedBinding,
          outcome,
          status,
          probeCount,
          selectedToken
        )
      )
    ).toBe("TERMINAL_INVARIANT_INVALID")
  }

  const valid = right(
    makeS2STestOnlyHostedProcessTerminal(
      selectedBinding,
      "success",
      "RECONCILED_ACTION_SUCCESS",
      1,
      selectedToken
    )
  )
  const invalidCore = Object.freeze({
    ...valid,
    terminalStatus: "RECONCILED_ACTION_FAILURE" as const,
    reconciliationProbeCount: 0 as const,
    authTag: undefined
  })
  const { authTag: _discarded, ...core } = invalidCore
  const coreBytes = canonical(core)
  const forgedAuthTag = createHmac("sha256", selectedToken)
    .update(S2S_TEST_ONLY_HOSTED_PROCESS_PROTOCOL_VERSION, "ascii")
    .update("\0TERMINAL\0", "ascii")
    .update(coreBytes)
    .digest("hex")
  const frame = canonical(Object.freeze({ ...core, authTag: forgedAuthTag }))
  expect(
    reason(
      decodeS2STestOnlyHostedProcessTerminalFrame(
        frame,
        selectedBinding,
        selectedToken
      )
    )
  ).toBe("TERMINAL_INVARIANT_INVALID")
})

it("fails hostile proxy and accessor surfaces closed without invoking traps", () => {
  let traps = 0
  const hostile = new Proxy(bindingInput(), {
    ownKeys: () => {
      traps += 1
      throw new Error("ownKeys trap must not run")
    },
    getPrototypeOf: () => {
      traps += 1
      throw new Error("prototype trap must not run")
    }
  })
  expect(reason(makeS2STestOnlyHostedProcessBinding(hostile))).toBe(
    "SCHEMA_INVALID"
  )
  expect(
    reason(canonicalS2STestOnlyHostedProcessFrame(hostile, "READY"))
  ).toBe("FRAME_INVALID")
  expect(traps).toBe(0)

  let reads = 0
  const accessor = { ...bindingInput() }
  Object.defineProperty(accessor, "nonce", {
    enumerable: true,
    get: () => {
      reads += 1
      throw new Error("accessor must not run")
    }
  })
  expect(reason(makeS2STestOnlyHostedProcessBinding(accessor))).toBe(
    "SCHEMA_INVALID"
  )
  expect(reads).toBe(0)

  expect(
    reason(
      canonicalS2STestOnlyHostedProcessFrame(
        { payload: "x".repeat(2_049) },
        "READY"
      )
    )
  ).toBe("FRAME_INVALID")
  expect(
    reason(
      canonicalS2STestOnlyHostedProcessFrame(
        { ["k".repeat(257)]: true },
        "READY"
      )
    )
  ).toBe("FRAME_INVALID")
})

it("keeps every hosted-process protocol capability out of the package root", () => {
  for (const key of [
    "makeS2STestOnlyHostedProcessBinding",
    "makeS2STestOnlyHostedProcessReady",
    "makeS2STestOnlyHostedProcessReconcileFrame",
    "decodeS2STestOnlyHostedProcessReconcileFrame",
    "makeS2STestOnlyHostedProcessTerminal"
  ]) {
    expect(key in publicApi).toBe(false)
  }
})
import { createHmac } from "node:crypto"
