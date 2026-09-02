#!/usr/bin/env node

import { createHash } from "node:crypto"
import { readFileSync, realpathSync } from "node:fs"
import path from "node:path"
import process from "node:process"
import { createRequire } from "node:module"
import { fileURLToPath, pathToFileURL } from "node:url"

const RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
const MF_ACTION = "http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#action"
const MF_NAME = "http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#name"
const RDFT_APPROVAL = "http://www.w3.org/ns/rdftest#approval"
const RDFT_APPROVED = "http://www.w3.org/ns/rdftest#Approved"
const NQUADS_POSITIVE = "http://www.w3.org/ns/rdftest#TestNQuadsPositiveSyntax"
const NQUADS_NEGATIVE = "http://www.w3.org/ns/rdftest#TestNQuadsNegativeSyntax"

function fail(message) {
  throw new Error(message)
}

function parseArguments(argv) {
  const allowed = new Set(["--module-root", "--profile", "--suite-root"])
  const values = new Map()
  for (let index = 0; index < argv.length; index += 2) {
    const name = argv[index]
    const value = argv[index + 1]
    if (!allowed.has(name) || value === undefined || values.has(name)) {
      fail("usage: qualify_graph_standards.mjs --module-root PATH --profile ID --suite-root PATH")
    }
    values.set(name, value)
  }
  if (values.size !== 3) {
    fail("usage: qualify_graph_standards.mjs --module-root PATH --profile ID --suite-root PATH")
  }
  return {
    moduleRoot: realpathSync(values.get("--module-root")),
    profile: values.get("--profile"),
    suiteRoot: realpathSync(values.get("--suite-root")),
  }
}

function safeSuiteFile(suiteRoot, relativePath) {
  if (typeof relativePath !== "string" || path.isAbsolute(relativePath)) {
    fail("suite path must be a relative string")
  }
  const candidate = realpathSync(path.join(suiteRoot, relativePath))
  const relative = path.relative(suiteRoot, candidate)
  if (relative === "" || relative.startsWith("..") || path.isAbsolute(relative)) {
    fail(`suite path escapes source root: ${relativePath}`)
  }
  return candidate
}

function sha256File(filePath) {
  return createHash("sha256").update(readFileSync(filePath)).digest("hex")
}

function packageVersion(packageName, moduleRoot) {
  const packageJson = path.join(moduleRoot, "node_modules", packageName, "package.json")
  const value = JSON.parse(readFileSync(packageJson, "utf8"))
  if (typeof value.version !== "string") {
    fail(`package version unavailable: ${packageName}`)
  }
  return value.version
}

function sortedObject(value) {
  if (Array.isArray(value)) {
    return value.map(sortedObject)
  }
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, sortedObject(item)]),
    )
  }
  return value
}

function nquadsManifestRecords({ manifestPath, requireApproval, requireFromModuleRoot }) {
  const { Parser } = requireFromModuleRoot("n3")
  const manifestQuads = new Parser({
    baseIRI: pathToFileURL(manifestPath).href,
    format: "text/turtle",
  }).parse(readFileSync(manifestPath, "utf8"))
  const values = (predicate) => new Map(
    manifestQuads
      .filter((quad) => quad.predicate.value === predicate)
      .map((quad) => [quad.subject.value, quad.object.value]),
  )
  const types = values(RDF_TYPE)
  const actions = values(MF_ACTION)
  const names = values(MF_NAME)
  const approvals = values(RDFT_APPROVAL)
  const records = []
  for (const [id, type] of types) {
    if (type !== NQUADS_POSITIVE && type !== NQUADS_NEGATIVE) {
      continue
    }
    if (requireApproval && approvals.get(id) !== RDFT_APPROVED) {
      continue
    }
    const action = actions.get(id)
    if (action === undefined || !action.startsWith("file:")) {
      fail(`test action is not a local file: ${id}`)
    }
    records.push({
      action: fileURLToPath(action),
      expectedToParse: type === NQUADS_POSITIVE,
      id,
      name: names.get(id) ?? id,
    })
  }
  return records.sort((left, right) => left.id.localeCompare(right.id))
}

function qualifyNQuads({
  manifestRelativePath,
  moduleRoot,
  profile,
  requireApproval,
  requireFromModuleRoot,
  suiteRoot,
}) {
  const { Parser } = requireFromModuleRoot("n3")
  const manifestPath = safeSuiteFile(suiteRoot, manifestRelativePath)
  const records = nquadsManifestRecords({ manifestPath, requireApproval, requireFromModuleRoot })
  const failures = []
  let positive = 0
  let negative = 0
  for (const record of records) {
    const inputPath = realpathSync(record.action)
    const relative = path.relative(suiteRoot, inputPath)
    if (relative.startsWith("..") || path.isAbsolute(relative)) {
      fail(`test action escapes suite root: ${record.name}`)
    }
    let parsed = true
    try {
      new Parser({ format: "N-Quads" }).parse(readFileSync(inputPath, "utf8"))
    } catch {
      parsed = false
    }
    if (record.expectedToParse) {
      positive += 1
    } else {
      negative += 1
    }
    if (parsed !== record.expectedToParse) {
      failures.push({
        expected: record.expectedToParse ? "ACCEPT" : "REJECT",
        id: record.id,
        name: record.name,
        observed: parsed ? "ACCEPT" : "REJECT",
      })
    }
  }
  return {
    adapter: { package: "n3", version: packageVersion("n3", moduleRoot) },
    counts: {
      failed: failures.length,
      negative,
      passed: records.length - failures.length,
      positive,
      total: records.length,
    },
    failures,
    manifest_sha256: sha256File(manifestPath),
    profile,
    status: failures.length === 0 ? "PASS" : "FAIL",
  }
}

async function qualifyRdfc({ moduleRoot, profile, requireFromModuleRoot, suiteRoot }) {
  const canonize = requireFromModuleRoot("rdf-canonize")
  const manifestPath = safeSuiteFile(suiteRoot, "manifest.jsonld")
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"))
  if (!Array.isArray(manifest.entries)) {
    fail("RDFC manifest entries are unavailable")
  }
  const counts = { evaluation: 0, failed: 0, identifier_map: 0, negative: 0, passed: 0, total: 0 }
  const failures = []
  for (const test of manifest.entries) {
    if (test.approval !== "rdft:Approved") {
      continue
    }
    counts.total += 1
    const inputPath = safeSuiteFile(suiteRoot, test.action)
    const input = readFileSync(inputPath, "utf8")
    const options = {
      algorithm: "RDFC-1.0",
      inputFormat: "application/n-quads",
      messageDigestAlgorithm: test.hashAlgorithm ?? "sha256",
      rejectURDNA2015: true,
    }
    try {
      if (test.type === "rdfc:RDFC10NegativeEvalTest") {
        counts.negative += 1
        let rejectedForComplexity = false
        try {
          await canonize.canonize(input, { ...options, maxWorkFactor: 1 })
        } catch (error) {
          rejectedForComplexity = String(error?.message).startsWith(
            "Maximum deep iterations exceeded",
          )
        }
        if (!rejectedForComplexity) {
          fail("negative vector was not rejected for excessive deep iterations")
        }
      } else if (test.type === "rdfc:RDFC10MapTest") {
        counts.identifier_map += 1
        const canonicalIdMap = new Map()
        await canonize.canonize(input, {
          ...options,
          canonicalIdMap,
          maxWorkFactor: Infinity,
          signal: AbortSignal.timeout(30_000),
        })
        const actual = sortedObject(Object.fromEntries(canonicalIdMap))
        const expectedPath = safeSuiteFile(suiteRoot, test.result)
        const expected = sortedObject(JSON.parse(readFileSync(expectedPath, "utf8")))
        if (JSON.stringify(actual) !== JSON.stringify(expected)) {
          fail("issued identifier map differs from the official vector")
        }
      } else if (test.type === "rdfc:RDFC10EvalTest") {
        counts.evaluation += 1
        const actual = await canonize.canonize(input, {
          ...options,
          maxWorkFactor: Infinity,
          signal: AbortSignal.timeout(30_000),
        })
        const expectedPath = safeSuiteFile(suiteRoot, test.result)
        if (actual !== readFileSync(expectedPath, "utf8")) {
          fail("canonical N-Quads differs from the official vector")
        }
      } else {
        fail(`unsupported approved RDFC test type: ${test.type}`)
      }
      counts.passed += 1
    } catch (error) {
      failures.push({ id: test.id, name: test.name, reason: String(error?.message) })
    }
  }
  counts.failed = failures.length
  return {
    adapter: { package: "rdf-canonize", version: packageVersion("rdf-canonize", moduleRoot) },
    counts,
    failures,
    manifest_sha256: sha256File(manifestPath),
    profile,
    status: failures.length === 0 ? "PASS" : "FAIL",
  }
}

async function main() {
  const { moduleRoot, profile, suiteRoot } = parseArguments(process.argv.slice(2))
  const requireFromModuleRoot = createRequire(
    pathToFileURL(path.join(moduleRoot, "package.json")),
  )
  let result
  if (profile === "rdf11-nquads-n3") {
    result = qualifyNQuads({
      manifestRelativePath: "manifest.ttl",
      moduleRoot,
      profile,
      requireApproval: true,
      requireFromModuleRoot,
      suiteRoot,
    })
  } else if (profile === "rdf12-nquads-n3-experimental") {
    result = qualifyNQuads({
      manifestRelativePath: "syntax/manifest.ttl",
      moduleRoot,
      profile,
      requireApproval: false,
      requireFromModuleRoot,
      suiteRoot,
    })
  } else if (profile === "rdfc10-rdf-canonize") {
    result = await qualifyRdfc({ moduleRoot, profile, requireFromModuleRoot, suiteRoot })
  } else {
    fail(`profile is not executable: ${profile}`)
  }
  process.stdout.write(`${JSON.stringify(sortedObject(result))}\n`)
  if (result.status !== "PASS") {
    process.exitCode = 1
  }
}

main().catch((error) => {
  process.stderr.write(`${String(error?.message ?? error)}\n`)
  process.exitCode = 2
})
