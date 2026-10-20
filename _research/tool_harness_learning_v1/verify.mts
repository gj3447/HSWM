/** Verify the published content-addressed receipt against retained archives, without extraction. */
import { readFileSync } from "node:fs"
import { resolve, join, basename, relative } from "node:path"
import { fileURLToPath } from "node:url"
import { createHash } from "node:crypto"
import { execFileSync } from "node:child_process"
import assert from "node:assert/strict"

const sha = (data: Uint8Array) => createHash("sha256").update(data).digest("hex")
const obj = (value: unknown): Record<string, unknown> => {
  assert.ok(value !== null && typeof value === "object" && !Array.isArray(value))
  return value as Record<string, unknown>
}
const [directory, receiptPath] = process.argv.slice(2)
assert.ok(directory && receiptPath, "verify.mts ARTIFACT_DIRECTORY RECEIPT.json")
const receiptBytes = readFileSync(receiptPath), receipt = obj(JSON.parse(receiptBytes.toString()))
assert.equal(basename(receiptPath), sha(receiptBytes) + ".json")
assert.equal(receipt["schema_version"], "hswm-research-receipt/v1")
const repository = resolve(fileURLToPath(new URL("../../", import.meta.url)))
const revision = execFileSync("git", ["log", "-1", "--format=%H", "--", relative(repository, resolve(receiptPath))],
  { cwd: repository, encoding: "utf8" }).trim()
assert.ok(Array.isArray(receipt["sources"]))
for (const raw of receipt["sources"]) {
  const source = obj(raw), path = String(source["path"])
  assert.ok(!path.startsWith("/") && !path.split("/").includes(".."))
  const actual: Buffer = revision ? execFileSync("git", ["show", `${revision}:${path}`], { cwd: repository, maxBuffer: 4_194_304 }) : readFileSync(join(repository, path))
  assert.equal(sha(actual), source["sha256"], path)
}
assert.ok(Array.isArray(receipt["archives"]))
for (const raw of receipt["archives"]) {
  const item = obj(raw), name = String(item["name"])
  assert.match(name, /^[a-z0-9.-]+\.tar\.gz$/)
  const archive: Buffer = readFileSync(join(resolve(directory), name))
  assert.equal(sha(archive), item["sha256"], name)
  assert.equal(archive.length, item["bytes"], name)
}
assert.ok(Array.isArray(receipt["members"]))
for (const raw of receipt["members"]) {
  const item = obj(raw), archive = String(item["archive"]), path = String(item["path"])
  assert.match(archive, /^[a-z0-9.-]+\.tar\.gz$/)
  assert.ok(path.startsWith("cohort/") && !path.split("/").includes(".."))
  const actual: Buffer = execFileSync("tar", ["-xOf", join(resolve(directory), archive), path], { maxBuffer: 16_777_216 })
  assert.equal(sha(actual), item["sha256"], path)
  assert.equal(actual.length, item["bytes"], path)
}
// The retained independent reconstruction is separately bound, not a replacement for rerunning it.
const checked = obj(JSON.parse(execFileSync("tar", ["-xOf", join(resolve(directory), "cohort-02.tar.gz"), "cohort/check.json"], { encoding: "utf8" })))
assert.equal(checked["status"], receipt["status"])
assert.deepEqual(checked["scores"], obj(receipt["observations"])["scores"])
assert.equal(checked["calls"], obj(receipt["observations"])["actualProviderCalls"])
console.log(JSON.stringify({ status: "RECEIPT_AND_RETAINED_BYTES_VERIFIED", archives: receipt["archives"].length,
  members: receipt["members"].length, evidence: checked["status"],
  next: "Extract the verified cohort into caller-selected scratch and rerun check.mts; hashes alone do not authenticate measurement truth." }))
