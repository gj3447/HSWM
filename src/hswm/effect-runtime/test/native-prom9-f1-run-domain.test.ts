import { readFileSync } from "node:fs"
import { createHash } from "node:crypto"
import { describe, expect, it } from "vitest"
import { Either } from "effect"
import { assembleNativeProm9F1SuiteReceipt, assembleNativeProm9F1TokenParity } from "../src/native-prom9-f1-run-domain.js"
import { decodeNativeTaskJson, renderNativeTaskJson, taskJsonRecord, type TaskJson } from "../src/native-task-json-domain.js"

const positiveBytes = readFileSync(new URL("../../../../tests/fixtures/prom9_f1_v1/positive.suite.json", import.meta.url))
const oracle = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_f1_run_v1/original.v1.json", import.meta.url), "utf8")) as { source_pins: Record<string, string>; case: { suite_path: string; expected_suite_receipt_sha256: string } }
const decode = (value: Uint8Array): TaskJson => Either.getOrThrow(decodeNativeTaskJson(value))

describe("native PROM-9 F1 run receipt projection", () => {
  it("rebuilds the sealed Python token-parity record including arbitrary-size integer totals", () => {
    const suite = decode(positiveBytes), rows = (suite as Record<string, TaskJson>)["item_runs"] as TaskJson[], envelope = (suite as Record<string, TaskJson>)["token_envelope"]
    const actual = Either.getOrThrow(assembleNativeProm9F1TokenParity(rows, envelope, 512n))
    expect(renderNativeTaskJson(actual)).toBe(renderNativeTaskJson((suite as Record<string, TaskJson>)["token_parity"]!))
    const huge = decode(readFileSync(new URL("../../../../tests/fixtures/prom9_f1_v1/bigint_tokens.suite.json", import.meta.url))) as Record<string, TaskJson>
    const parity = Either.getOrThrow(assembleNativeProm9F1TokenParity(huge["item_runs"] as TaskJson[], huge["token_envelope"], 512n)) as Record<string, TaskJson>
    expect(renderNativeTaskJson(parity)).toContain("27021597764222979")
  })

  it("fails closed on a duplicate item-arm receipt rather than overwriting it in a map", () => {
    const suite = decode(positiveBytes) as Record<string, TaskJson>, rows = suite["item_runs"] as TaskJson[]
    expect(assembleNativeProm9F1TokenParity([...rows, rows[0]!], suite["token_envelope"], 512n)).toMatchObject({ _tag: "Left", left: { detail: "duplicate item-arm receipt: synthetic-positive-item-01/typed_hswm_three_function_network" } })
  })

  it("assembles the original development suite receipt from externally supplied sealed runs", () => {
    expect(createHash("sha256").update(readFileSync(new URL("../../../../prom_search_hswm/prom_f1_function_network.py", import.meta.url))).digest("hex")).toBe(oracle.source_pins["prom_f1_function_network.py"])
    const suite = decode(readFileSync(new URL(`../../../../${oracle.case.suite_path}`, import.meta.url))) as Record<string, TaskJson>
    const assembled = assembleNativeProm9F1SuiteReceipt({
      run_id: suite["run_id"] as string, mode: suite["mode"] as "development", manifest_sha256: suite["manifest_sha256"] as string, model: suite["model"] as string, model_revision: suite["model_revision"] as string,
      token_tolerance: BigInt(suite["token_tolerance"] as number), state_capacity_bytes: BigInt(suite["state_capacity_bytes"] as number), preregistration_receipt_sha256: suite["preregistration_receipt_sha256"]!, token_envelope: suite["token_envelope"]!, envelope_projection: suite["envelope_projection"]!, max_workers: BigInt(suite["max_workers"] as number), registries: suite["registries"]!, item_runs: suite["item_runs"] as TaskJson[]
    })
    if (Either.isLeft(assembled)) throw new Error(assembled.left.detail)
    const result = assembled.right
    if (!taskJsonRecord(result)) throw new Error("assembled suite is not an object")
    expect(result["suite_receipt_sha256"]).toBe(oracle.case.expected_suite_receipt_sha256)
    expect(renderNativeTaskJson(result)).toBe(renderNativeTaskJson(suite))
  })

  it("refuses unknown runtime inputs before property access", () => {
    for (const raw of [null, [], { mode: "other" }, { run_id: null }]) expect(assembleNativeProm9F1SuiteReceipt(raw)).toMatchObject({ _tag: "Left" })
    const suite = decode(positiveBytes) as Record<string, TaskJson>
    for (const rows of [null, {}, Object.freeze(Array(2))]) expect(assembleNativeProm9F1TokenParity(rows, suite["token_envelope"], 512n)).toMatchObject({ _tag: "Left" })
    for (const tolerance of [null, 512, "512", -1n]) expect(assembleNativeProm9F1TokenParity(suite["item_runs"], suite["token_envelope"], tolerance)).toMatchObject({ _tag: "Left" })
    let reads = 0
    const accessor = Object.freeze(Object.defineProperty({}, "run_id", { enumerable: true, get: () => { reads += 1; return "forged" } }))
    expect(assembleNativeProm9F1SuiteReceipt(accessor)).toMatchObject({ _tag: "Left" })
    expect(assembleNativeProm9F1TokenParity([accessor], suite["token_envelope"], 512n)).toMatchObject({ _tag: "Left" })
    expect(reads).toBe(0)
  })

  it("snapshots nested suite inputs before returning a sealed receipt", () => {
    const suite = decode(readFileSync(new URL(`../../../../${oracle.case.suite_path}`, import.meta.url))) as Record<string, TaskJson>
    const input = Object.fromEntries(Object.entries(suite).filter(([key]) => !["schema_version", "suite_receipt_sha256", "token_parity", "gold_opened", "scientific_verdict_emitted"].includes(key)))
    const result = Either.getOrThrow(assembleNativeProm9F1SuiteReceipt(input))
    const before = renderNativeTaskJson(result)
    const registries = input["registries"] as Record<string, TaskJson>
    registries[Object.keys(registries)[0]!] = null
    expect(renderNativeTaskJson(result)).toBe(before)
    const immutable = (value: TaskJson): boolean => value === null || typeof value !== "object" || Object.isFrozen(value) && Object.values(value).every(immutable)
    expect(immutable(result)).toBe(true)
  })
})
