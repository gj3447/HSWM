#!/usr/bin/env node
import { execFile } from "node:child_process"
import { randomUUID } from "node:crypto"
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { dirname, join, resolve } from "node:path"
import { promisify } from "node:util"
import { fileURLToPath } from "node:url"

import { Effect, Either } from "effect"
import neo4j from "neo4j-driver"

import { compileHypergraphProjection, decodeHypergraphProjectionBytes } from "./canonical-atom-v2-hypergraph-projection.js"
import { canonicalAtomV2RdfProjectionBytes } from "./canonical-atom-v2-rdf-projection.js"
import { publishNeo4jHypergraphProjection, rebuildNeo4jHypergraphProjection } from "./canonical-atom-v2-neo4j-projection.js"
import { makeHypergraphProjectionRehearsal } from "./hypergraph-projection-rehearsal.js"
import { buildHypergraphProjectionPackage } from "./hypergraph-projection-receipt.js"
import { makeOpenConnectivityRehearsal } from "./open-connectivity-rehearsal.js"

const right = <A, E>(result: Either.Either<A, E>): A => {
  if (Either.isLeft(result)) throw new Error("projection contract verification failed")
  return result.right
}
const execute = promisify(execFile)

const main = async (): Promise<void> => {
  const args = process.argv.slice(2)
  const values = new Map<string, string>()
  const flags = new Set<string>()
  for (let index = 0; index < args.length; index++) {
    const arg = args[index]!
    if (["--rehearsal", "--connectivity-rehearsal", "--apply", "--rebuild", "--help"].includes(arg)) {
      if (flags.has(arg)) throw new Error("duplicate CLI flag")
      flags.add(arg)
    } else if (["--input", "--out", "--repository-root", "--source-config"].includes(arg)) {
      const value = args[++index]
      if (values.has(arg) || value === undefined || value.startsWith("--")) throw new Error("missing or duplicate CLI argument")
      values.set(arg, value)
    } else throw new Error("unknown CLI argument")
  }
  if (flags.has("--help")) {
    process.stdout.write("Usage: hswm-hypergraph-projection (--rehearsal | --connectivity-rehearsal | --input canonical-projection.json) --out NEW_DIRECTORY [--repository-root CHECKOUT] [--apply --source-config FILE [--rebuild]]\nDefault: local compilation, real SHACL validation and receipt; no database connection. --connectivity-rehearsal is a synthetic recursive/peer/external metadata example, not a live connection or learning result. Both rehearsals publish only synthetic metadata with --apply, not live connectivity. --rebuild replaces only the exact verified projection namespace.\n")
    return
  }
  const sourceCount = Number(flags.has("--rehearsal")) + Number(flags.has("--connectivity-rehearsal")) + Number(values.has("--input"))
  if (sourceCount !== 1 || !values.has("--out")) throw new Error("supply exactly one source and a new output directory")
  if (flags.has("--rebuild") && !flags.has("--apply")) throw new Error("--rebuild requires --apply")
  if (flags.has("--apply") && !values.has("--source-config")) throw new Error("--apply requires --source-config")
  const root = resolve(values.get("--repository-root") ?? join(dirname(fileURLToPath(import.meta.url)), "../../../.."))
  const output = resolve(values.get("--out")!)
  const startedAt = new Date().toISOString()
  const fixture = flags.has("--rehearsal") ? makeHypergraphProjectionRehearsal()
    : flags.has("--connectivity-rehearsal") ? makeOpenConnectivityRehearsal() : undefined
  const projection = fixture === undefined
    ? right(decodeHypergraphProjectionBytes(await readFile(resolve(values.get("--input")!))))
    : right(compileHypergraphProjection(fixture.schema, fixture.source))
  // Reserve a new directory before any DB action; never overwrite user output.
  await mkdir(output, { recursive: false })
  const temporary = await mkdtemp(join(tmpdir(), "hswm-projection-validation-"))
  try {
    await writeFile(join(temporary, "rdf.json"), right(canonicalAtomV2RdfProjectionBytes(projection.rdf)), { flag: "wx" })
    await writeFile(join(temporary, "rdf.nq"), projection.rdf.nquads, { flag: "wx" })
    const validation = await execute("uv", [
      "run", "--project", join(root, "_research/graph_standards/runtime"), "--locked", "--extra", "graph",
      "python", "-m", "hswm.infrastructure.hypergraph_projection_validation",
      "--projection-json", join(temporary, "rdf.json"), "--nquads", join(temporary, "rdf.nq"),
      "--shapes", join(root, "schemas/HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_SHACL_1_0.ttl")
    ], { cwd: root, maxBuffer: 1_048_576, timeout: 120_000 })
    const shaclEvidence = JSON.parse(validation.stdout) as Record<string, unknown>
    if (shaclEvidence["conforms"] !== true || shaclEvidence["datasetSha256"] !== projection.manifest.rdfSha256) throw new Error("SHACL did not verify this exact RDF dataset")
    let readbackGraph: { readonly nodes: typeof projection.nodes; readonly relationships: typeof projection.relationships } | undefined
    if (flags.has("--apply")) {
      const raw = await readFile(resolve(values.get("--source-config")!), "utf8")
      // Match the repository publisher's flat YAML credential-file convention.
      const config = Object.fromEntries(raw.split(/\r?\n/).flatMap((line) => {
        const trimmed = line.trim()
        if (!trimmed || trimmed.startsWith("#")) return []
        const split = trimmed.indexOf(":")
        if (split < 0) throw new Error("source-config must be flat YAML")
        return [[trimmed.slice(0, split).trim(), trimmed.slice(split + 1).trim().replace(/^(["'])(.*)\1$/, "$2")]]
      }))
      for (const key of ["uri", "user", "password", "database"]) if (!config[key]) throw new Error("source-config requires uri, user, password and database")
      const driver = neo4j.driver(config["uri"]!, neo4j.auth.basic(config["user"]!, config["password"]!), { connectionTimeout: 10_000, maxTransactionRetryTime: 10_000 })
      try {
        const options = { database: config["database"]!, apply: true }
        const final = flags.has("--rebuild")
          ? await Effect.runPromise(rebuildNeo4jHypergraphProjection(driver, projection, options))
          : await Effect.runPromise(publishNeo4jHypergraphProjection(driver, projection, options))
        readbackGraph = { nodes: final.readback.nodes, relationships: final.readback.relationships }
      } finally { await driver.close() }
    }
    const packaged = right(buildHypergraphProjectionPackage(projection, {
      runId: randomUUID(), startedAt, completedAt: new Date().toISOString(),
      producer: "https://github.com/gj3447/HSWM",
      parity: readbackGraph === undefined
        ? { mode: "LOCAL_COMPILER_ONLY", shaclEvidence: { bytes: Buffer.from(validation.stdout), mediaType: "application/json" } }
        : { mode: "CALLER_REPORTED_LIVE_NEO4J_PARITY", readbackGraph, shaclEvidence: { bytes: Buffer.from(validation.stdout), mediaType: "application/json" }, reportedBy: "hswm-hypergraph-projection CLI managed transaction readback" }
    }))
    for (const [name, content] of packaged.files) await writeFile(join(output, name), content, { flag: "wx" })
    process.stdout.write(JSON.stringify({ status: readbackGraph === undefined ? "LOCAL_COMPILED_SHACL_VALIDATED" : "NEO4J_PUBLISHED_READBACK_VERIFIED", rebuilt: flags.has("--rebuild"), projectionId: projection.manifest.projectionId, graphSha256: projection.manifest.graphSha256, output, claimCeiling: projection.manifest.claimCeiling }) + "\n")
  } finally {
    await rm(temporary, { recursive: true, force: true })
  }
}

main().catch(() => {
  // Driver/config/parser details can contain credentials; public output is bounded.
  process.stderr.write("Hypergraph projection failed; no success receipt was emitted. Check source, SHACL runtime, output path and DB configuration.\n")
  process.exitCode = 1
})
