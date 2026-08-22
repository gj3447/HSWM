import { execFileSync } from "node:child_process"
import {
  mkdirSync,
  mkdtempSync,
  rmSync,
  writeFileSync
} from "node:fs"
import { dirname, join, resolve } from "node:path"
import { tmpdir } from "node:os"

import { Effect } from "effect"

import {
  S2S_PREREG_PILOT_SOURCE_COMMIT,
  S2S_PREREG_RESOURCE_POLICY_SHA256,
  S2S_PREREGISTRATION_PATH,
  buildS2SPreregistration,
  makeS2SPreregGitRepositoryProcessLayer,
  parseAndValidateS2SPreregistration,
  validateS2SRegistrationCommitB,
  type S2SRegistrationCommitAuthority
} from "../../src/s2s-preregistration.js"
import { S2S_CONFIRMATORY_WORKFLOW_PATH } from "../../src/s2s-workflow-contract.js"

const WORKSPACE_ROOT = resolve(process.cwd(), "../../..")
const GIT_MAX_BUFFER = 32 * 1_048_576

export const S2S_AUTHORITY_WORKFLOW_FIXTURE_BYTES = new TextEncoder().encode(
  "name: SWM-0W-S2S confirmatory\n"
)

export interface S2SRegistrationAuthorityFixture {
  readonly root: string
  readonly sourceCommitA: string
  readonly registrationCommitB: string
  readonly registrationAuthority: S2SRegistrationCommitAuthority
  readonly cleanup: () => void
}
const runGit = (root: string, arguments_: ReadonlyArray<string>): string =>
  execFileSync("git", ["-C", root, ...arguments_], {
    encoding: "utf8",
    maxBuffer: GIT_MAX_BUFFER
  }).trim()

export const makeS2SRegistrationAuthorityFixture = async (): Promise<
  S2SRegistrationAuthorityFixture
> => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-authority-"))
  const root = join(temporaryRoot, "repository")
  const cleanup = (): void =>
    rmSync(temporaryRoot, { force: true, recursive: true })
  try {
    execFileSync(
      "git",
      ["clone", "--shared", "--no-checkout", "--quiet", WORKSPACE_ROOT, root],
      { maxBuffer: GIT_MAX_BUFFER }
    )
    runGit(root, ["config", "user.email", "s2s-authority@example.invalid"])
    runGit(root, ["config", "user.name", "S2S authority fixture"])
    runGit(root, [
      "checkout",
      "--quiet",
      "-b",
      "source-a",
      S2S_PREREG_PILOT_SOURCE_COMMIT
    ])
    writeFileSync(join(root, "s2s-authority-fixture.txt"), "source A\n", "utf8")
    const workflowPath = join(root, S2S_CONFIRMATORY_WORKFLOW_PATH)
    mkdirSync(dirname(workflowPath), { recursive: true })
    writeFileSync(workflowPath, S2S_AUTHORITY_WORKFLOW_FIXTURE_BYTES)
    runGit(root, [
      "add",
      "--",
      "s2s-authority-fixture.txt",
      S2S_CONFIRMATORY_WORKFLOW_PATH
    ])
    runGit(root, ["commit", "--quiet", "-m", "create source A fixture"])
    const sourceCommitA = runGit(root, ["rev-parse", "HEAD"])
    const layer = makeS2SPreregGitRepositoryProcessLayer(root)
    const built = await Effect.runPromise(
      buildS2SPreregistration({
        experimentId: "SWM0W-S2S-GATE-V1",
        resourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256,
        sourceCommitA,
        registeredAtUnix: 1_692_806_000,
        futureRound: 1_000
      }).pipe(Effect.provide(layer))
    )
    const validated = await Effect.runPromise(
      parseAndValidateS2SPreregistration(built.canonicalBytes, {
        expectedResourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256
      }).pipe(Effect.provide(layer))
    )
    runGit(root, ["checkout", "--quiet", "-b", "registration-b"])
    const preregistrationPath = join(root, S2S_PREREGISTRATION_PATH)
    mkdirSync(dirname(preregistrationPath), { recursive: true })
    writeFileSync(preregistrationPath, built.canonicalBytes)
    runGit(root, ["add", "--", S2S_PREREGISTRATION_PATH])
    runGit(root, ["commit", "--quiet", "-m", "create registration B"])
    const registrationCommitB = runGit(root, ["rev-parse", "HEAD"])
    const registrationAuthority = await Effect.runPromise(
      validateS2SRegistrationCommitB(validated, registrationCommitB).pipe(
        Effect.provide(layer)
      )
    )
    return Object.freeze({
      root,
      sourceCommitA,
      registrationCommitB,
      registrationAuthority,
      cleanup
    })
  } catch (error: unknown) {
    cleanup()
    throw error
  }
}
