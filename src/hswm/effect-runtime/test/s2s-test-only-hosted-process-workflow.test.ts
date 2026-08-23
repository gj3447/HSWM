import { readFileSync } from "node:fs"
import { resolve } from "node:path"

import { expect, it } from "@effect/vitest"

import {
  S2S_HOSTED_PROCESS_CONTINUITY_PINNED_UPLOAD_ACTION,
  S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT
} from "../src/s2s-hosted-process-continuity-contract.js"

const repositoryRoot = resolve(import.meta.dirname, "../../../..")
const workflowPath = resolve(
  repositoryRoot,
  ".github/workflows/s2s-test-only-hosted-process-continuity.yml"
)
const rootSourcePath = resolve(
  import.meta.dirname,
  "../src/s2s-test-only-hosted-process-root.ts"
)
const workflow = readFileSync(workflowPath, "utf8")
const rootSource = readFileSync(rootSourcePath, "utf8")

const occurrences = (source: string, literal: string): number =>
  source.split(literal).length - 1

it("is dispatch-only, repository-bound, attempt-one, and non-authorizing", () => {
  expect(workflow).toContain(
    "name: TEST_ONLY NON_AUTHORIZING hosted Effect-root continuity"
  )
  expect(workflow).toContain("  workflow_dispatch:")
  expect(workflow).not.toContain("  push:")
  expect(workflow).not.toContain("  pull_request:")
  expect(occurrences(workflow, "github.repository == 'gj3447/HSWM'")).toBe(2)
  expect(occurrences(workflow, "github.ref == 'refs/heads/main'")).toBe(2)
  expect(occurrences(workflow, "github.run_attempt == 1")).toBe(2)
  expect(workflow).toContain("  actions: read")
  expect(workflow).toContain("  contents: read")
  expect(workflow).not.toContain("id-token:")
  expect(workflow).not.toContain("secrets.")
  expect(workflow).not.toContain("GITHUB_TOKEN")
  expect(workflow).not.toContain("prereg/")
  expect(workflow).not.toContain("future seed")
  expect(occurrences(workflow, "persist-credentials: false")).toBe(2)
  expect(occurrences(workflow, "package-manager-cache: false")).toBe(2)
  expect(workflow).not.toContain("cache: npm")
  expect(workflow).not.toContain("needs: continuity")
})

it("pins all actions and never consumes upload outputs as authority", () => {
  expect(occurrences(workflow, "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1")).toBe(2)
  expect(occurrences(workflow, "actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e")).toBe(2)
  expect(
    occurrences(workflow, `uses: ${S2S_HOSTED_PROCESS_CONTINUITY_PINNED_UPLOAD_ACTION}`)
  ).toBe(5)
  expect(workflow).not.toContain("outputs.artifact-id")
  expect(workflow).not.toContain("outputs.artifact-url")
  expect(workflow).not.toContain("outputs.artifact-digest")
  expect(workflow).not.toContain("overwrite: true")
  expect(occurrences(workflow, "overwrite: false")).toBe(5)
  expect(occurrences(workflow, "retention-days: 1")).toBe(5)
})

it("uses one hosted root across each foreground action and an explicit cancel", () => {
  expect(occurrences(workflow, "background: true")).toBe(4)
  expect(occurrences(workflow, "wait: register_root")).toBe(1)
  expect(occurrences(workflow, "wait: confirm_root")).toBe(1)
  expect(occurrences(workflow, "wait: adjudicate_root")).toBe(1)
  expect(occurrences(workflow, "cancel: cancelled_root")).toBe(1)
  expect(occurrences(workflow, 'exec node "$HOSTED_PROCESS_CLI" root')).toBe(4)
  expect(occurrences(workflow, 'node "$HOSTED_PROCESS_CLI" await-ready')).toBe(4)
  expect(occurrences(workflow, 'ready_output="$(')).toBe(4)
  expect(
    occurrences(workflow, `printf '%s\\n' "$ready_output" | tee`)
  ).toBe(4)
  expect(occurrences(workflow, 'node "$HOSTED_PROCESS_CLI" reconcile')).toBe(3)
  expect(workflow).toContain(
    "test/s2s-test-only-hosted-process-workflow.test.ts"
  )
  expect(occurrences(workflow, "mktemp -d /var/tmp/hswm-pc.XXXXXXXX")).toBe(2)
})

it("covers three structural archive shapes and success/failure/injected-unknown diagnostics", () => {
  for (const literal of [
    "--feasibility-attempt 1",
    "--feasibility-attempt 2",
    "--feasibility-attempt 3",
    "--stage REGISTER",
    "--stage CONFIRM",
    "--stage ADJUDICATE",
    "--outcome success",
    "--outcome failure",
    "--outcome unknown",
    "intentionally-missing"
  ]) {
    expect(workflow).toContain(literal)
  }
  expect(workflow).toContain(
    "Inject unknown diagnostic and reconcile without blind retry"
  )
  expect(workflow).not.toMatch(/^\s*retry:/mu)
  expect(workflow).toContain(
    "upload/registration_archive.zip"
  )
  expect(workflow).toContain(
    "upload/adjudication_archive.zip"
  )
  expect(workflow).not.toMatch(/hswm-s2s-pc-register\/upload\/$/mu)
  expect(workflow).not.toMatch(/hswm-s2s-pc-adjudicate\/upload\/$/mu)
})

it("keeps production capability, observer, preregistration, and verdict modules outside the root", () => {
  for (const forbiddenImport of [
    "s2s-run-authority",
    "s2s-prepared-stage-carrier",
    "s2s-stage-upload-assertion",
    "s2s-live-github",
    "s2s-preregistration",
    "s2s-job-sequence"
  ]) {
    expect(rootSource).not.toContain(`from "./${forbiddenImport}.js"`)
  }
  expect(rootSource).toContain("Effect.acquireUseRelease")
  expect(rootSource).toContain("Effect.scoped")
  expect(rootSource).not.toContain("forkDaemon")
})

it("leaves production policy unchanged while freezing feasible additive timings", () => {
  expect(S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.stages).toMatchObject({
    REGISTER: { jobTimeoutMillis: 4_500_000, jobTimeoutMinutes: 75 },
    CONFIRM: { jobTimeoutMillis: 14_700_000, jobTimeoutMinutes: 245 },
    ADJUDICATE: { jobTimeoutMillis: 4_500_000, jobTimeoutMinutes: 75 }
  })
  expect(
    S2S_HOSTED_PROCESS_CONTINUITY_TIMING_CONTRACT.claimBoundary
  ).toMatchObject({
    hChanged: false,
    wChanged: false,
    aChanged: false,
    fChanged: false,
    piProductionPolicyChanged: false,
    testOnlyFeasibilityWorkflowDefined: true,
    productionWorkflowMutated: false,
    productionAuthorizationClaimed: false,
    scientificVerdictClaimed: false,
    causalLearningClaimed: false
  })
  expect(occurrences(workflow, "timeout-minutes: 20")).toBe(1)
  expect(occurrences(workflow, "timeout-minutes: 10")).toBe(1)
  expect(workflow).not.toContain("timeout-minutes: 75")
  expect(workflow).not.toContain("timeout-minutes: 245")
})
