#!/usr/bin/env node

// A deliberately standalone JSON-LD 1.1 qualification runner.  It executes
// only the W3C expand/compact evaluation vectors supplied as --suite-root;
// its document loader cannot leave that selected test tree or use the network.

import { createHash } from "node:crypto"
import { readFileSync, realpathSync } from "node:fs"
import { createRequire } from "node:module"
import path from "node:path"
import process from "node:process"
import { pathToFileURL } from "node:url"

const EXPAND_COMPACT_PROFILE = "jsonld11-jsonldjs-expand-compact"
const FROM_RDF_PROFILE = "jsonld11-jsonldjs-fromrdf"
const HSWM_FROM_RDF_PROFILE = "jsonld11-jsonldjs-hswm-fromrdf"
const MANIFESTS = ["expand-manifest.jsonld", "compact-manifest.jsonld"]
const FROM_RDF_MANIFEST = "fromRdf-manifest.jsonld"
const TEST_BASE_IRI = "https://w3c.github.io/json-ld-api/tests/"
const POSITIVE = "jld:PositiveEvaluationTest"
const NEGATIVE = "jld:NegativeEvaluationTest"
const EXPAND = "jld:ExpandTest"
const COMPACT = "jld:CompactTest"
const FROM_RDF = "jld:FromRDFTest"

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
      fail("usage: qualify_jsonld11.mjs --module-root PATH --profile ID --suite-root PATH")
    }
    values.set(name, value)
  }
  if (
    values.size !== 3 ||
    ![EXPAND_COMPACT_PROFILE, FROM_RDF_PROFILE, HSWM_FROM_RDF_PROFILE].includes(values.get("--profile"))
  ) {
    fail("usage: qualify_jsonld11.mjs --module-root PATH --profile {jsonld11-jsonldjs-expand-compact|jsonld11-jsonldjs-fromrdf|jsonld11-jsonldjs-hswm-fromrdf} --suite-root PATH")
  }
  return {
    moduleRoot: realpathSync(values.get("--module-root")),
    profile: values.get("--profile"),
    suiteRoot: realpathSync(values.get("--suite-root")),
  }
}

function sha256File(filePath) {
  return createHash("sha256").update(readFileSync(filePath)).digest("hex")
}

function sortedObject(value) {
  if (Array.isArray(value)) return value.map(sortedObject)
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, sortedObject(item)]),
    )
  }
  return value
}

function suiteFile(suiteRoot, relativePath) {
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

function readJson(suiteRoot, relativePath) {
  return JSON.parse(readFileSync(suiteFile(suiteRoot, relativePath), "utf8"))
}

function remoteTestUrl(relativePath) {
  return new URL(relativePath, TEST_BASE_IRI).href
}

function localDocumentLoader(suiteRoot) {
  return async (url) => {
    let parsed
    try {
      parsed = new URL(url)
    } catch {
      fail(`document loader rejected a non-URL: ${String(url)}`)
    }
    if (!parsed.href.startsWith(TEST_BASE_IRI)) {
      fail(`document loader blocked non-suite URL: ${parsed.href}`)
    }
    const relativePath = decodeURIComponent(parsed.href.slice(TEST_BASE_IRI.length).split(/[?#]/, 1)[0])
    const documentPath = suiteFile(suiteRoot, relativePath)
    return {
      contextUrl: null,
      document: JSON.parse(readFileSync(documentPath, "utf8")),
      documentUrl: parsed.href,
    }
  }
}

function typesOf(test) {
  if (!Array.isArray(test["@type"]) || !test["@type"].every((type) => typeof type === "string")) {
    fail(`test types unavailable: ${String(test["@id"])}`)
  }
  return test["@type"]
}

function testKind(test, manifestName) {
  const types = typesOf(test)
  const positive = types.includes(POSITIVE)
  const negative = types.includes(NEGATIVE)
  const operation = manifestName === "expand-manifest.jsonld" ? EXPAND : COMPACT
  if ((positive === negative) || !types.includes(operation)) {
    fail(`unsupported JSON-LD evaluation test: ${String(test["@id"])}`)
  }
  return { negative, operation }
}

function operationOptions(test, inputUrl, loader) {
  const option = test.option ?? {}
  if (option === null || Array.isArray(option) || typeof option !== "object") {
    fail(`test option must be an object: ${String(test["@id"])}`)
  }
  const allowed = new Set([
    "base",
    "compactArrays",
    "compactToRelative",
    "expandContext",
    "normative",
    "processingMode",
    "specVersion",
  ])
  for (const key of Object.keys(option)) {
    if (!allowed.has(key)) fail(`unsupported JSON-LD test option ${key}: ${String(test["@id"])}`)
  }
  const specVersion = option.specVersion
  const explicitMode = option.processingMode
  if (specVersion !== undefined && specVersion !== "json-ld-1.0" && specVersion !== "json-ld-1.1") {
    fail(`unsupported specVersion: ${String(specVersion)}`)
  }
  if (explicitMode !== undefined && explicitMode !== "json-ld-1.0" && explicitMode !== "json-ld-1.1") {
    fail(`unsupported processingMode: ${String(explicitMode)}`)
  }
  if (option.base !== undefined && typeof option.base !== "string") {
    fail(`unsupported base option: ${String(test["@id"])}`)
  }
  if (option.expandContext !== undefined && typeof option.expandContext !== "string") {
    fail(`unsupported expandContext option: ${String(test["@id"])}`)
  }
  if (option.compactArrays !== undefined && typeof option.compactArrays !== "boolean") {
    fail(`unsupported compactArrays option: ${String(test["@id"])}`)
  }
  if (option.compactToRelative !== undefined && typeof option.compactToRelative !== "boolean") {
    fail(`unsupported compactToRelative option: ${String(test["@id"])}`)
  }
  if (option.normative !== undefined && typeof option.normative !== "boolean") {
    fail(`unsupported normative marker: ${String(test["@id"])}`)
  }
  const options = {
    base: option.base ?? inputUrl,
    documentLoader: loader,
    // ``processingMode`` is the operation setting; ``specVersion`` selects a
    // manifest lane.  The W3C vectors intentionally include combinations
    // where an explicit 1.0 processing mode is tested against 1.1 syntax.
    processingMode: explicitMode ?? specVersion ?? "json-ld-1.1",
  }
  if (option.compactArrays !== undefined) options.compactArrays = option.compactArrays
  if (option.compactToRelative !== undefined) options.compactToRelative = option.compactToRelative
  if (option.expandContext !== undefined) {
    options.expandContext = new URL(option.expandContext, TEST_BASE_IRI).href
  }
  return options
}

function errorCode(error) {
  const code = error?.details?.code ?? error?.code
  return typeof code === "string" ? code : undefined
}

async function runTest({ jsonld, loader, manifestName, suiteRoot, test }) {
  const { negative, operation } = testKind(test, manifestName)
  if (typeof test.input !== "string") fail(`test input unavailable: ${String(test["@id"])}`)
  const inputUrl = remoteTestUrl(test.input)
  const options = operationOptions(test, inputUrl, loader)
  const input = readJson(suiteRoot, test.input)
  try {
    let actual
    if (operation === EXPAND) {
      actual = await jsonld.expand(input, options)
    } else {
      if (typeof test.context !== "string") fail(`compact context unavailable: ${String(test["@id"])}`)
      actual = await jsonld.compact(input, readJson(suiteRoot, test.context), options)
    }
    if (negative) {
      fail(`negative test accepted: ${String(test["@id"])}`)
    }
    if (typeof test.expect !== "string") fail(`expected output unavailable: ${String(test["@id"])}`)
    const expected = readJson(suiteRoot, test.expect)
    if (JSON.stringify(sortedObject(actual)) !== JSON.stringify(sortedObject(expected))) {
      fail("result JSON differs from official expected JSON")
    }
  } catch (error) {
    if (!negative) throw error
    if (typeof test.expectErrorCode !== "string") {
      fail(`negative expected error unavailable: ${String(test["@id"])}`)
    }
    const observed = errorCode(error)
    if (observed !== test.expectErrorCode) {
      fail(`expected error ${test.expectErrorCode}, observed ${observed ?? String(error?.message ?? error)}`)
    }
  }
  return { negative, operation }
}

function fromRdfOptions(test) {
  const option = test.option ?? {}
  if (option === null || Array.isArray(option) || typeof option !== "object") {
    fail(`test option must be an object: ${String(test["@id"])}`)
  }
  const allowed = new Set(["normative", "rdfDirection", "specVersion", "useNativeTypes", "useRdfType"])
  for (const key of Object.keys(option)) {
    if (!allowed.has(key)) fail(`unsupported JSON-LD FromRDF option ${key}: ${String(test["@id"])}`)
  }
  if (option.specVersion !== undefined && option.specVersion !== "json-ld-1.0" && option.specVersion !== "json-ld-1.1") {
    fail(`unsupported specVersion: ${String(option.specVersion)}`)
  }
  if (option.useNativeTypes !== undefined && typeof option.useNativeTypes !== "boolean") {
    fail(`unsupported useNativeTypes option: ${String(test["@id"])}`)
  }
  if (option.useRdfType !== undefined && typeof option.useRdfType !== "boolean") {
    fail(`unsupported useRdfType option: ${String(test["@id"])}`)
  }
  if (option.normative !== undefined && typeof option.normative !== "boolean") {
    fail(`unsupported normative marker: ${String(test["@id"])}`)
  }
  if (option.rdfDirection !== undefined && !["compound-literal", "i18n-datatype"].includes(option.rdfDirection)) {
    fail(`unsupported rdfDirection option: ${String(option.rdfDirection)}`)
  }
  const options = {
    format: "application/n-quads",
    processingMode: option.specVersion ?? "json-ld-1.1",
  }
  for (const key of ["rdfDirection", "useNativeTypes", "useRdfType"]) {
    if (option[key] !== undefined) options[key] = option[key]
  }
  return options
}

function fromRdfKind(test) {
  const types = typesOf(test)
  const positive = types.includes(POSITIVE)
  const negative = types.includes(NEGATIVE)
  if ((positive === negative) || !types.includes(FROM_RDF)) {
    fail(`unsupported JSON-LD FromRDF evaluation test: ${String(test["@id"])}`)
  }
  return { negative }
}

async function runFromRdfTest({ jsonld, suiteRoot, test }) {
  const { negative } = fromRdfKind(test)
  if (typeof test.input !== "string" || !test.input.endsWith(".nq")) {
    fail(`FromRDF input must be a local N-Quads file: ${String(test["@id"])}`)
  }
  const input = readFileSync(suiteFile(suiteRoot, test.input), "utf8")
  try {
    const actual = await jsonld.fromRDF(input, fromRdfOptions(test))
    if (negative) fail(`negative test accepted: ${String(test["@id"])}`)
    if (typeof test.expect !== "string") fail(`expected output unavailable: ${String(test["@id"])}`)
    const expected = readJson(suiteRoot, test.expect)
    if (JSON.stringify(sortedObject(actual)) !== JSON.stringify(sortedObject(expected))) {
      fail("result JSON differs from official expected JSON")
    }
  } catch (error) {
    if (!negative) throw error
    if (typeof test.expectErrorCode !== "string") {
      fail(`negative expected error unavailable: ${String(test["@id"])}`)
    }
    const observed = errorCode(error)
    if (observed !== test.expectErrorCode) {
      fail(`expected error ${test.expectErrorCode}, observed ${observed ?? String(error?.message ?? error)}`)
    }
  }
  return { negative }
}

async function qualifyFromRdf({ jsonld, profile, suiteRoot }) {
  const manifestPath = suiteFile(suiteRoot, FROM_RDF_MANIFEST)
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"))
  if (!Array.isArray(manifest.sequence)) fail("FromRDF manifest sequence unavailable")
  const counts = { failed: 0, from_rdf: 0, negative: 0, passed: 0, total: 0 }
  const failures = []
  for (const test of manifest.sequence) {
    counts.total += 1
    counts.from_rdf += 1
    const types = Array.isArray(test["@type"]) ? test["@type"] : []
    if (types.includes(NEGATIVE)) counts.negative += 1
    try {
      await runFromRdfTest({ jsonld, suiteRoot, test })
      counts.passed += 1
    } catch (error) {
      failures.push({
        id: typeof test["@id"] === "string" ? test["@id"] : "unknown",
        name: typeof test.name === "string" ? test.name : "unknown",
        reason: String(error?.message ?? error),
      })
    }
  }
  counts.failed = failures.length
  return {
    counts,
    failures,
    manifest_sha256: sha256File(manifestPath),
    profile,
    status: failures.length === 0 ? "PASS" : "FAIL",
  }
}

function hswmFromRdfExclusionReasons(test, input) {
  const option = test.option ?? {}
  if (option === null || Array.isArray(option) || typeof option !== "object") {
    fail(`test option must be an object: ${String(test["@id"])}`)
  }
  const reasons = []
  for (const key of ["specVersion", "processingMode"]) {
    if (option[key] !== undefined && option[key] !== "json-ld-1.1") {
      reasons.push("processing_mode_not_json_ld_1_1")
      break
    }
  }
  if (option.useNativeTypes !== undefined && option.useNativeTypes !== false) {
    reasons.push("use_native_types_not_false")
  }
  if (option.useRdfType !== undefined && option.useRdfType !== false) {
    reasons.push("use_rdf_type_not_false")
  }
  if (option.rdfDirection !== undefined) reasons.push("rdf_direction_present")
  // The production TypeScript adapter accepts only blank-node-free sources.
  // This intentionally follows the contract's literal `_:` source criterion,
  // rather than trying to reinterpret RDF terms in the qualification runner.
  if (input.includes("_:")) reasons.push("blank_node_outside_hswm_source_profile")
  return reasons
}

async function qualifyHswmFromRdf({ jsonld, profile, suiteRoot }) {
  const manifestPath = suiteFile(suiteRoot, FROM_RDF_MANIFEST)
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"))
  if (!Array.isArray(manifest.sequence)) fail("HSWM FromRDF manifest sequence unavailable")
  const counts = { approved: 0, attempted: 0, discovered: 0, excluded: 0, failed: 0, passed: 0 }
  const exclusions = { counts: {}, entries: [] }
  const failures = []
  for (const test of manifest.sequence) {
    counts.discovered += 1
    fromRdfKind(test)
    counts.approved += 1
    if (typeof test.input !== "string" || !test.input.endsWith(".nq")) {
      fail(`FromRDF input must be a local N-Quads file: ${String(test["@id"])}`)
    }
    const input = readFileSync(suiteFile(suiteRoot, test.input), "utf8")
    const reasons = hswmFromRdfExclusionReasons(test, input)
    if (reasons.length > 0) {
      counts.excluded += 1
      exclusions.entries.push({ id: test["@id"], reasons })
      for (const reason of reasons) exclusions.counts[reason] = (exclusions.counts[reason] ?? 0) + 1
      continue
    }
    counts.attempted += 1
    try {
      await runFromRdfTest({ jsonld, suiteRoot, test })
      counts.passed += 1
    } catch (error) {
      failures.push({
        id: typeof test["@id"] === "string" ? test["@id"] : "unknown",
        name: typeof test.name === "string" ? test.name : "unknown",
        reason: String(error?.message ?? error),
      })
    }
  }
  counts.failed = failures.length
  return {
    counts,
    exclusions,
    failures,
    manifest_sha256: sha256File(manifestPath),
    profile,
    profile_contract: {
      blank_node_policy: "EXCLUDE_INPUTS_CONTAINING_LITERAL_BLANK_NODE_TOKEN__COLON",
      processing_mode: "json-ld-1.1",
      use_native_types: false,
      use_rdf_type: false,
      rdf_direction: "ABSENT",
    },
    status: failures.length === 0 ? "PASS" : "FAIL",
  }
}

async function main() {
  const { moduleRoot, profile, suiteRoot } = parseArguments(process.argv.slice(2))
  const requireFromModuleRoot = createRequire(pathToFileURL(path.join(moduleRoot, "package.json")))
  const jsonld = requireFromModuleRoot("jsonld")
  const packageJson = JSON.parse(readFileSync(path.join(moduleRoot, "node_modules/jsonld/package.json"), "utf8"))
  const adapter = { package: "jsonld", version: packageJson.version }
  if (profile === FROM_RDF_PROFILE || profile === HSWM_FROM_RDF_PROFILE) {
    const qualification = profile === FROM_RDF_PROFILE
      ? await qualifyFromRdf({ jsonld, profile, suiteRoot })
      : await qualifyHswmFromRdf({ jsonld, profile, suiteRoot })
    const result = { adapter, ...qualification }
    process.stdout.write(`${JSON.stringify(sortedObject(result))}\n`)
    if (result.status !== "PASS") process.exitCode = 1
    return
  }
  const loader = localDocumentLoader(suiteRoot)
  const counts = { compact: 0, expand: 0, failed: 0, negative: 0, passed: 0, total: 0 }
  const failures = []
  const manifestSha256 = {}
  for (const manifestName of MANIFESTS) {
    const manifestPath = suiteFile(suiteRoot, manifestName)
    manifestSha256[manifestName] = sha256File(manifestPath)
    const manifest = JSON.parse(readFileSync(manifestPath, "utf8"))
    if (!Array.isArray(manifest.sequence)) fail(`manifest sequence unavailable: ${manifestName}`)
    for (const test of manifest.sequence) {
      counts.total += 1
      let kind
      try {
        kind = await runTest({ jsonld, loader, manifestName, suiteRoot, test })
        counts[kind.operation === EXPAND ? "expand" : "compact"] += 1
        if (kind.negative) counts.negative += 1
        counts.passed += 1
      } catch (error) {
        const types = Array.isArray(test["@type"]) ? test["@type"] : []
        if (types.includes(EXPAND)) counts.expand += 1
        if (types.includes(COMPACT)) counts.compact += 1
        if (types.includes(NEGATIVE)) counts.negative += 1
        failures.push({
          id: typeof test["@id"] === "string" ? test["@id"] : "unknown",
          name: typeof test.name === "string" ? test.name : "unknown",
          reason: String(error?.message ?? error),
        })
      }
    }
  }
  counts.failed = failures.length
  const result = {
    adapter,
    counts,
    failures,
    manifest_sha256: manifestSha256,
    profile,
    status: failures.length === 0 ? "PASS" : "FAIL",
  }
  process.stdout.write(`${JSON.stringify(sortedObject(result))}\n`)
  if (result.status !== "PASS") process.exitCode = 1
}

main().catch((error) => {
  process.stderr.write(`${String(error?.message ?? error)}\n`)
  process.exitCode = 2
})
