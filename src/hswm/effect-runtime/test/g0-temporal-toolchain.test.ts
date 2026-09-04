import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"

import { expect, it } from "vitest"

const manifest = JSON.parse(readFileSync(
  new URL("../assets/g0-temporal-test-toolchain.json", import.meta.url),
  "utf8"
)) as {
  readonly schema_version: string
  readonly temporal_cli: {
    readonly version: string
    readonly source_commit: string
    readonly release_archive_sha256: string
    readonly sha256: string
    readonly license_sha256: string
    readonly checksums_source: string
  }
  readonly temporal_typescript_sdk: {
    readonly version: string
    readonly license: string
    readonly license_sha256: string
    readonly packages: Readonly<Record<string, string>>
  }
}
const packageJson = JSON.parse(readFileSync(
  new URL("../package.json", import.meta.url),
  "utf8"
)) as {
  readonly dependencies: Readonly<Record<string, string>>
  readonly devDependencies: Readonly<Record<string, string>>
  readonly exports: Readonly<Record<string, unknown>>
  readonly bin: Readonly<Record<string, string>>
}
const lock = JSON.parse(readFileSync(
  new URL("../package-lock.json", import.meta.url),
  "utf8"
)) as {
  readonly packages: Readonly<Record<string, {
    readonly version?: string
    readonly integrity?: string
    readonly license?: string
  }>>
}

it("pins every official Temporal package to one version, integrity, and MIT license", () => {
  expect(manifest.schema_version).toBe("hswm-g0-temporal-test-toolchain/v1")
  expect(manifest.temporal_cli).toMatchObject({
    version: "1.8.3",
    source_commit: "1ff10b1012b44ba8bc953fcaa8ce5d296bf169d0",
    release_archive_sha256: "6f0afac1e9ddea71f480c43a49f5db5167a244c21db923707f069a79bcabdfea",
    sha256: "76aea8d71fafe2d39c1104bef3ce86c1600d9adbff79953d102f60e535ae1413",
    license_sha256: "692992f9a78f825b332d03f9b98aeb6cd5823ae884572af02e79f17327aa0612",
    checksums_source: "https://github.com/temporalio/cli/releases/download/v1.8.3/checksums.txt"
  })
  const expected = Object.keys(manifest.temporal_typescript_sdk.packages)
  expect(manifest.temporal_typescript_sdk.license_sha256).toBe(
    "434e542427eae40756e435acb1ad7273164953277a090b54ed3336e7339bcde9"
  )
  expect(expected).toEqual([
    "@temporalio/activity",
    "@temporalio/client",
    "@temporalio/common",
    "@temporalio/testing",
    "@temporalio/worker",
    "@temporalio/workflow"
  ])
  for (const name of expected) {
    const declared = packageJson.dependencies[name] ?? packageJson.devDependencies[name]
    const installed = lock.packages[`node_modules/${name}`]
    expect(declared, name).toBe(manifest.temporal_typescript_sdk.version)
    expect(installed?.version, name).toBe(manifest.temporal_typescript_sdk.version)
    expect(installed?.integrity, name).toBe(manifest.temporal_typescript_sdk.packages[name])
    expect(installed?.license, name).toBe(manifest.temporal_typescript_sdk.license)
    expect(createHash("sha256").update(readFileSync(
      new URL(`../node_modules/${name}/LICENSE`, import.meta.url)
    )).digest("hex"), name).toBe(manifest.temporal_typescript_sdk.license_sha256)
  }
  expect(Object.keys(packageJson.exports)).toEqual([".", "./g0-temporal"])
  expect(Object.keys(packageJson.exports).some((key) => key.includes("test"))).toBe(false)
  expect(packageJson.bin["hswm-g0-temporal-rehearsal-worker"]).toBe(
    "./dist/g0-occurrence-temporal-worker-process.js"
  )
})
