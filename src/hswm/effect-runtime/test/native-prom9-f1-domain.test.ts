import { readFile } from "node:fs/promises"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"
import { decodeNativeTaskJson } from "../src/native-task-json-domain.js"
import { judgeNativeProm9F1Suite, verifyNativeProm9F1Suite } from "../src/native-prom9-f1-domain.js"

const load = async (name: string) => {
  const parsed = decodeNativeTaskJson(await readFile(resolve(import.meta.dirname, "../../../../_research/prom9_runs/f1-2wiki-dev-r5-live", name)))
  if (parsed._tag === "Left") throw new Error(parsed.left.detail)
  return parsed.right
}

describe("native PROM-9 F1 suite judge", () => {
  it("replays the original development F1 judgment byte-for-byte", async () => {
    const suite = await load("suite.json"), gold = await load("gold.json")
    expect(verifyNativeProm9F1Suite(suite)).toMatchObject({ _tag: "Right", right: "c06533f10c9d90e9a1a437f024243598c56b71ba5fdc0003eb4c1876563210a9" })
    expect(judgeNativeProm9F1Suite(suite, gold, 100, 20260724)).toMatchObject({ _tag: "Right", right: { judgment_sha256: "87c804a5295fee95501a61c5f258acf2e85bb4909f34e59e035ef01152199bf9", verdict: "DEVELOPMENT_ONLY" } })
  })

  it("refuses a resealed token-parity mutation", async () => {
    const suite = await load("suite.json") as Record<string, unknown>
    const parity = suite["token_parity"] as Record<string, unknown>
    const altered = { ...suite, token_parity: { ...parity, spread_max: 99 } }
    const { canonicalNativeProm9Sha256 } = await import("../src/native-prom9-ports-domain.js")
    const digest = canonicalNativeProm9Sha256(Object.fromEntries(Object.entries(altered).filter(([key]) => key !== "suite_receipt_sha256")))
    if (digest._tag === "Left") throw new Error(digest.left.detail)
    expect(verifyNativeProm9F1Suite({ ...altered, suite_receipt_sha256: digest.right })).toMatchObject({ _tag: "Left" })
  })

  it("matches original Python judgments across bootstrap seeds and repetition counts", async () => {
    const suite = await load("suite.json"), gold = await load("gold.json")
    for (const [reps, seed, digest] of [[1, 1, "dd4416eaaac78b14cd70a3157fa3a323254c198972ca2e838aec42404d57f3cb"], [17, 42, "8ed789751b69ecdebc0f9fc90fe12eff05971a8bbcca7fdda5b439603bdb66e2"], [101, 99, "4179620eb17a6bff07358fd72bbead4b95be3247fb6783d0dfaf21630ceef48f"]] as const) {
      expect(judgeNativeProm9F1Suite(suite, gold, reps, seed)).toMatchObject({ _tag: "Right", right: { judgment_sha256: digest } })
    }
  })
})
