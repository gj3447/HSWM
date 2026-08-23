import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import { S2SSha256Schema } from "../src/s2s-confirmatory.js"
import {
  S2S_NUMERIC_ADJUDICATION_MAX_BYTES,
  S2S_NUMERIC_ORACLE_SOURCE_SHA256,
  S2S_PYTHON_RSS_TELEMETRY_SCHEMA_VERSION,
  S2S_PYTHON_RUNTIME_SOURCE_IDENTITY_SCHEMA_VERSION,
  type S2SPythonNumericOutput,
  type S2SPythonRuntimeSourceIdentityReceipt
} from "../src/s2s-live-python.js"
import { bindS2SPythonExecutionEvidence } from "../src/s2s-python-evidence.js"

const hash = (label: string) =>
  S2SSha256Schema.make(
    rawS2SFileSha256(new TextEncoder().encode(label))
  )

const runtimeIdentity = (): S2SPythonRuntimeSourceIdentityReceipt => {
  const bytes = new TextEncoder().encode('{"runtime":"identity"}\n')
  return Object.freeze({
    schemaVersion: S2S_PYTHON_RUNTIME_SOURCE_IDENTITY_SCHEMA_VERSION,
    pythonExecutableSha256: hash("python-executable"),
    pythonVersion: "3.11.15",
    pythonImplementation: "CPython",
    pythonCacheTag: "cpython-311",
    byteorder: "little",
    numpyVersion: "2.4.6",
    numpyModulePath: "/pinned/numpy/__init__.py",
    modulePaths: Object.freeze({ oracle: "/repo/src/oracle.py" }),
    repositoryRoot: "/repo",
    pythonExecutableArgv0: "/pinned/python3.11",
    processEnvironmentContract: Object.freeze({ LANG: "C" }),
    processEnvironmentContractSha256: hash("environment"),
    sourceClosure: Object.freeze([
      Object.freeze({
        path: "src/hswm/experiments/swm0w_s2s_numeric_oracle.py",
        byteLength: 1,
        rawBytesSha256: S2SSha256Schema.make(
          S2S_NUMERIC_ORACLE_SOURCE_SHA256
        )
      })
    ]),
    sourceClosureSha256: hash("source-closure"),
    receiptSha256: hash("runtime-receipt"),
    readCanonicalBytes: () => new Uint8Array(bytes)
  })
}

const numericOutput = (
  runtime: S2SPythonRuntimeSourceIdentityReceipt,
  requestHash: ReturnType<typeof hash>
): S2SPythonNumericOutput => {
  const bytes = new TextEncoder().encode('{"numeric":"candidate"}\n')
  const rss = canonicalS2SControlJsonBytes({
    api: "getrusage",
    oom_observed: false,
    peak_rss_kib: 42_000,
    schema_version: S2S_PYTHON_RSS_TELEMETRY_SCHEMA_VERSION,
    subject: "RUSAGE_SELF",
    unit: "KiB"
  })
  if (Either.isLeft(rss)) throw rss.left
  return Object.freeze({
    operation: "CONFIRM",
    memberName: "numeric_candidate.json",
    inputRawBytesSha256: requestHash,
    rawBytesSha256: S2SSha256Schema.make(rawS2SFileSha256(bytes)),
    byteLength: bytes.byteLength,
    commandElapsedNanoseconds: 123_456,
    peakRssKiB: 42_000,
    rssTelemetryRawSha256: S2SSha256Schema.make(
      rawS2SFileSha256(rss.right)
    ),
    runtimeSourceIdentityReceiptSha256: runtime.receiptSha256,
    readCanonicalBytes: () => new Uint8Array(bytes),
    readRssTelemetryCanonicalBytes: () => new Uint8Array(rss.right)
  })
}

it("binds exact executor, runtime, request, and invocation identities", () => {
  const runtime = runtimeIdentity()
  const requestDocument = hash("confirm-request-document")
  const requestSelf = hash("confirm-request-self")
  const outcome = bindS2SPythonExecutionEvidence({
    output: numericOutput(runtime, requestDocument),
    runtimeSourceIdentity: runtime,
    requestDocumentSha256: requestDocument,
    requestSelfSha256: requestSelf
  })
  expect(Either.isRight(outcome)).toBe(true)
  if (Either.isRight(outcome)) {
    expect(outcome.right.evidence).toMatchObject({
      operation: "confirm",
      inputRawBytesSha256: requestDocument,
      requestDocumentSha256: requestDocument,
      requestSelfSha256: requestSelf,
      pythonRuntimeIdentitySha256: runtime.receiptSha256,
      numericOracleSourceSha256: S2S_NUMERIC_ORACLE_SOURCE_SHA256,
      exitCode: 0
    })
    const unsigned = { ...outcome.right.evidence } as Record<string, unknown>
    delete unsigned["receiptSha256"]
    const receipt = canonicalS2SControlSha256(unsigned)
    expect(Either.isRight(receipt)).toBe(true)
    if (Either.isRight(receipt)) {
      expect(receipt.right).toBe(outcome.right.evidence.receiptSha256)
    }
    const first = outcome.right.readInvocationIdentityCanonicalBytes()
    first.fill(0)
    expect(outcome.right.readInvocationIdentityCanonicalBytes()[0]).toBe(0x7b)
  }
})

it("rejects request, runtime, and output drift", () => {
  const runtime = runtimeIdentity()
  const request = hash("request")
  const output = numericOutput(runtime, request)
  const requestDrift = bindS2SPythonExecutionEvidence({
    output,
    runtimeSourceIdentity: runtime,
    requestDocumentSha256: hash("different-request"),
    requestSelfSha256: hash("self")
  })
  const runtimeDrift = bindS2SPythonExecutionEvidence({
    output: { ...output, runtimeSourceIdentityReceiptSha256: hash("other-runtime") },
    runtimeSourceIdentity: runtime,
    requestDocumentSha256: request,
    requestSelfSha256: hash("self")
  })
  const outputDrift = bindS2SPythonExecutionEvidence({
    output: { ...output, rawBytesSha256: hash("other-output") },
    runtimeSourceIdentity: runtime,
    requestDocumentSha256: request,
    requestSelfSha256: hash("self")
  })
  const rssDrift = bindS2SPythonExecutionEvidence({
    output: { ...output, peakRssKiB: output.peakRssKiB + 1 },
    runtimeSourceIdentity: runtime,
    requestDocumentSha256: request,
    requestSelfSha256: hash("self")
  })
  expect(Either.isLeft(requestDrift)).toBe(true)
  expect(Either.isLeft(runtimeDrift)).toBe(true)
  expect(Either.isLeft(outputDrift)).toBe(true)
  expect(Either.isLeft(rssDrift)).toBe(true)
  if (Either.isLeft(requestDrift)) {
    expect(requestDrift.left.reason).toBe("REQUEST_BINDING_MISMATCH")
  }
  if (Either.isLeft(runtimeDrift)) {
    expect(runtimeDrift.left.reason).toBe("RUNTIME_IDENTITY_MISMATCH")
  }
  if (Either.isLeft(outputDrift)) {
    expect(outputDrift.left.reason).toBe("EXECUTOR_OUTPUT_DRIFT")
  }
})

it("rejects forged empty and over-cap executor outputs before evidence binding", () => {
  const runtime = runtimeIdentity()
  const request = hash("bounded-output-request")
  const output = numericOutput(runtime, request)
  const emptyBytes = new Uint8Array()
  const oversizedBytes = new Uint8Array(
    S2S_NUMERIC_ADJUDICATION_MAX_BYTES + 1
  )
  const empty = bindS2SPythonExecutionEvidence({
    output: {
      ...output,
      byteLength: emptyBytes.byteLength,
      rawBytesSha256: S2SSha256Schema.make(rawS2SFileSha256(emptyBytes)),
      readCanonicalBytes: () => new Uint8Array(emptyBytes)
    },
    runtimeSourceIdentity: runtime,
    requestDocumentSha256: request,
    requestSelfSha256: hash("self")
  })
  const oversized = bindS2SPythonExecutionEvidence({
    output: {
      ...output,
      operation: "ADJUDICATE",
      memberName: "numeric_adjudication.json",
      byteLength: oversizedBytes.byteLength,
      rawBytesSha256: S2SSha256Schema.make(rawS2SFileSha256(oversizedBytes)),
      readCanonicalBytes: () => new Uint8Array(oversizedBytes)
    },
    runtimeSourceIdentity: runtime,
    requestDocumentSha256: request,
    requestSelfSha256: hash("self")
  })

  expect(Either.isLeft(empty)).toBe(true)
  expect(Either.isLeft(oversized)).toBe(true)
  if (Either.isLeft(empty)) {
    expect(empty.left.reason).toBe("EXECUTOR_OUTPUT_DRIFT")
  }
  if (Either.isLeft(oversized)) {
    expect(oversized.left.reason).toBe("EXECUTOR_OUTPUT_DRIFT")
  }
})
