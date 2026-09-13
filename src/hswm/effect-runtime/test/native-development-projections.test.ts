import { execFileSync } from "node:child_process"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { Effect, Either, Layer } from "effect"
import { expect, it } from "vitest"
import { validateDevelopmentDayProjection } from "../src/native-development-day-projection.js"
import { validateDevelopmentWorkProjection } from "../src/native-development-work-projection.js"
import { applyReviewedDevelopmentWorkProjection } from "../src/native-development-work-projection.js"
import { applyReviewedDevelopmentDayProjection } from "../src/native-development-day-projection.js"
import { applyReviewedFrontierLearningProjection } from "../src/native-frontier-learning-projection.js"
import { validateFrontierLearningProjection } from "../src/native-frontier-learning-projection.js"
import { compileDevelopmentDayProjection } from "../src/native-development-day-projection.js"
import { compileDevelopmentWorkProjection } from "../src/native-development-work-projection.js"
import { compileFrontierLearningProjection } from "../src/native-frontier-learning-projection.js"
import { validateFrontierHistoricalSnapshot } from "../src/native-frontier-learning-projection.js"
import { validateFrontierPaperTopology } from "../src/native-frontier-learning-projection.js"
import { preloadDevelopmentProjectionSources } from "../src/native-development-projection-io.js"
import { NodePosixServicesLive } from "../src/effect-posix-services.js"
import { NodePosixFileSystemLive } from "../src/effect-posix-filesystem.js"
import { BoundedSubprocess } from "../src/effect-bounded-subprocess.js"
import { runNativeDevelopmentProjectionCli } from "../src/native-development-projection-cli.js"
import { parseNativeDevelopmentProjectionSourceConfig } from "../src/native-development-projection-publisher.js"
import { makeNativeDevelopmentProjectionPublisher } from "../src/native-development-projection-publisher.js"
import type { NativeDevelopmentProjectionDriver, NativeDevelopmentProjectionRecord } from "../src/native-development-projection-publisher.js"
import { mkdtempSync, symlinkSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join } from "node:path"
import { exportDevelopmentDayProjection } from "../src/native-development-day-projection.js"
import { exportDevelopmentWorkProjection } from "../src/native-development-work-projection.js"
import { exportFrontierLearningProjection } from "../src/native-frontier-learning-projection.js"
import type { HistoricalBlobSource } from "../src/native-development-projection-domain.js"
import type { KgBundle } from "../src/native-kg-bundle-domain.js"

const root = resolve(import.meta.dirname, "../../../..")
const bytes = (path: string): Uint8Array | undefined => { try { return readFileSync(resolve(root, path)) } catch { return undefined } }
const source: HistoricalBlobSource = {
  readPath: bytes,
  readBlob: (commit, path) => { try { return execFileSync("git", ["-C", root, "show", `${commit}:${path}`]) } catch { return undefined } }
}
const json = (path: string): unknown => JSON.parse(readFileSync(resolve(root, path), "utf8"))
const work = "ontology/identity/hswm_core/HSWM_ADAPTIVE_DEVELOPMENT_WORK_ONTOLOGY.v1.json"
const frontier = "ontology/identity/hswm_core/HSWM_FRONTIER_LEARNING_THEORY_ONTOLOGY.v1.json"
const day = "ontology/identity/hswm_core/HSWM_DEVELOPMENT_DAY_2026-09-08_ONTOLOGY.v1.json"
const raw = (path: string): Uint8Array => readFileSync(resolve(root, path))

type StoredNode = { readonly labels: readonly string[]; readonly properties: Readonly<Record<string, unknown>> }
type StoredRelation = { readonly properties: Readonly<Record<string, unknown>> }
type PublisherFault = "none" | "readback" | "count" | "hang" | "late"
const record = (values: Readonly<Record<string, unknown>>): NativeDevelopmentProjectionRecord => ({ get: key => values[key] })
const stringsOnly = (value: unknown): readonly string[] => Array.isArray(value) && value.every(item => typeof item === "string") ? value : []
const unknownRecord = (value: unknown): value is Readonly<Record<string, unknown>> => value !== null && typeof value === "object"
const relationKey = (from: string, type: string, to: string): string => `${from}\u0000${type}\u0000${to}`

/** Explicit transaction fake: committed state changes only after commit resolves. */
const makeProjectionDriver = (bundle: KgBundle, fault: PublisherFault = "none") => {
  const nodes = new Map<string, StoredNode>(bundle.anchors.map(anchor => [anchor.uid, { labels: anchor.required_labels, properties: { name: anchor.name } }]))
  const relations = new Map<string, StoredRelation>()
  const statements: Array<readonly [string, Readonly<Record<string, unknown>>]> = []
  let sessionClosed = false, driverClosed = false, writes = 0, commits = 0, rollbacks = 0
  let resolveLate: (() => void) | undefined
  const transactionTimeouts: number[] = []
  const cloneNodes = (source: ReadonlyMap<string, StoredNode>) => new Map([...source].map(([uid, node]) => [uid, { labels: [...node.labels], properties: { ...node.properties } }]))
  const cloneRelations = (source: ReadonlyMap<string, StoredRelation>) => new Map([...source].map(([key, edge]) => [key, { properties: { ...edge.properties } }]))
  const driver: NativeDevelopmentProjectionDriver = {
    session: () => ({
      beginTransaction: config => {
        writes++
        transactionTimeouts.push(config.timeout)
        const transactionalNodes = cloneNodes(nodes), transactionalRelations = cloneRelations(relations)
        let nodeLookupCount = 0
        return {
          run: async (statement, parameters) => {
          statements.push([statement, parameters])
          if (statement.startsWith("MATCH (r:SchemaRegistry")) {
            if (fault === "hang") return new Promise<never>(() => undefined)
            if (fault === "late") return new Promise<{ records: readonly NativeDevelopmentProjectionRecord[] }>(resolve => { resolveLate = () => resolve({ records: [record({ labels: [...new Set([...bundle.nodes.flatMap(node => node.labels), ...bundle.anchors.flatMap(anchor => anchor.required_labels)])], relations: [...new Set(bundle.relations.map(edge => edge.type))] })] }) })
            return { records: [record({ labels: [...new Set([...bundle.nodes.flatMap(node => node.labels), ...bundle.anchors.flatMap(anchor => anchor.required_labels)])], relations: [...new Set(bundle.relations.map(edge => edge.type))] })] }
          }
          if (statement.startsWith("MATCH (n) WHERE n.uid IN $uids")) {
            nodeLookupCount++
            const requested = stringsOnly(parameters["uids"])
            const found = requested.flatMap(uid => {
              const node = transactionalNodes.get(uid)
              return node === undefined ? [] : [record({ uid, labels: node.labels, properties: node.properties })]
            })
            return { records: fault === "readback" && nodeLookupCount === 3 ? found.slice(1) : found }
          }
          if (statement.startsWith("CREATE (n:")) {
            const labels = statement.match(/^CREATE \(n:([A-Za-z_:]+)\) SET n=\$properties$/)?.[1]?.split(":")
            const properties = parameters["properties"]
            if (labels === undefined || !unknownRecord(properties) || typeof properties["uid"] !== "string") throw new Error("unexpected node create")
            transactionalNodes.set(properties["uid"], { labels, properties: { ...properties } })
            return { records: [] }
          }
          if (statement.startsWith("MATCH (n {ontology_bundle_uid:$uid})")) {
            const count = [...transactionalNodes.values()].filter(node => node.properties["ontology_bundle_uid"] === bundle.bundle_uid).length
            return { records: [record({ count: fault === "count" ? count + 1 : count })] }
          }
          if (statement.startsWith("MATCH ()-[r {ontology_bundle_uid:$uid}]->()")) {
            const count = [...transactionalRelations.values()].filter(edge => edge.properties["ontology_bundle_uid"] === bundle.bundle_uid).length
            return { records: [record({ count })] }
          }
          if (statement.startsWith("MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) CREATE (a)-[r:")) {
            const from = parameters["from_uid"], to = parameters["to_uid"], type = statement.match(/\[r:([A-Z_]+)\]/)?.[1]
            if (typeof from !== "string" || typeof to !== "string" || type === undefined) throw new Error("unexpected relation query")
            const key = relationKey(from, type, to)
            const properties = parameters["properties"]
            if (!unknownRecord(properties)) throw new Error("unexpected relation create")
            transactionalRelations.set(key, { properties: { ...properties } })
            return { records: [] }
          }
          if (statement.startsWith("MATCH (a {uid:$from_uid})-[r:")) {
            const from = parameters["from_uid"], to = parameters["to_uid"], type = statement.match(/\[r:([A-Z_]+)\]/)?.[1]
            if (typeof from !== "string" || typeof to !== "string" || type === undefined) throw new Error("unexpected relation query")
            const key = relationKey(from, type, to)
            const edge = transactionalRelations.get(key)
            return { records: edge === undefined ? [] : [record({ properties: edge.properties })] }
          }
            throw new Error(`unexpected Cypher: ${statement}`)
          },
          commit: async () => {
            commits++
            nodes.clear(); for (const [uid, node] of transactionalNodes) nodes.set(uid, node)
            relations.clear(); for (const [key, edge] of transactionalRelations) relations.set(key, edge)
          },
          rollback: async () => { rollbacks++ }
        }
      },
      close: async () => { sessionClosed = true }
    }),
    close: async () => { driverClosed = true }
  }
  return {
    driver,
    statements,
    get closed () { return sessionClosed && driverClosed },
    get writes () { return writes },
    get commits () { return commits },
    get rollbacks () { return rollbacks },
    get transactionTimeouts () { return transactionTimeouts },
    resolveLate: () => resolveLate?.(),
    get ownedNodeCount () { return [...nodes.values()].filter(node => node.properties["ontology_bundle_uid"] === bundle.bundle_uid).length },
    get ownedRelationCount () { return [...relations.values()].filter(edge => edge.properties["ontology_bundle_uid"] === bundle.bundle_uid).length },
    corruptFirstOwnedNode: () => {
      const node = bundle.nodes[0]
      if (node === undefined) throw new Error("test bundle has no nodes")
      const stored = nodes.get(node.uid)
      if (stored === undefined) throw new Error("test projection was not committed")
      nodes.set(node.uid, { labels: stored.labels, properties: { ...stored.properties, name: "collision" } })
    }
  }
}

it("validates all three installed source-bound projection snapshots", () => {
  for (const [name, validate, path] of [["work", validateDevelopmentWorkProjection, work], ["frontier", validateFrontierLearningProjection, frontier], ["day", validateDevelopmentDayProjection, day]] as const) {
    const result = validate(json(path), source)
    if (Either.isLeft(result)) throw new Error(`${name}: ${result.left.detail}`)
    expect(Either.isRight(result), name).toBe(true)
  }
})
it("refuses binding, endpoint, authority, and direct-request quote drift", () => {
  const workValue = json(work) as Record<string, unknown>
  const badBinding = structuredClone(workValue) as { artifact_bindings: Array<{ sha256: string }> }
  badBinding.artifact_bindings[0]!.sha256 = "0".repeat(64)
  expect(Either.isLeft(validateDevelopmentWorkProjection(badBinding, source))).toBe(true)
  const dayValue = json(day) as Record<string, unknown>
  const badEndpoint = structuredClone(dayValue) as { relations: Array<{ to_uid: string }> }
  badEndpoint.relations[0]!.to_uid = "sym:AbstractNode:missing"
  expect(Either.isLeft(validateDevelopmentDayProjection(badEndpoint, source))).toBe(true)
  const badQuote = structuredClone(dayValue) as { nodes: Array<{ uid: string; properties: Record<string, unknown> }> }
  const user = badQuote.nodes.find(node => node.uid === "sym:AbstractNode:hswm-development-day-2026-09-08-user-request")
  if (user === undefined) throw new Error("missing fixture user node")
  user.properties["verbatim_text"] = "tampered"
  expect(Either.isLeft(validateDevelopmentDayProjection(badQuote, source))).toBe(true)
  const badAuthority = structuredClone(workValue) as { nodes: Array<{ properties: Record<string, unknown> }> }
  badAuthority.nodes[0]!.properties["authority_class"] = "USER_PRIMARY"
  expect(Either.isLeft(validateDevelopmentWorkProjection(badAuthority, source))).toBe(true)
  const badStatus = structuredClone(workValue) as { status: string }
  badStatus.status = "EFFICACY_PROVEN"
  expect(Either.isLeft(validateDevelopmentWorkProjection(badStatus, source))).toBe(true)
  const badLabels = structuredClone(dayValue) as { nodes: Array<{ labels: string[] }> }
  badLabels.nodes[0]!.labels = ["AbstractNode"]
  expect(Either.isLeft(validateDevelopmentDayProjection(badLabels, source))).toBe(true)
  const badUserAuthority = structuredClone(dayValue) as { nodes: Array<{ uid: string; properties: Record<string, unknown> }> }
  const directRequest = badUserAuthority.nodes.find(node => node.uid === "sym:AbstractNode:hswm-development-day-2026-09-08-user-request")
  if (directRequest === undefined) throw new Error("missing fixture user node")
  directRequest.properties["ontology_authority"] = "SECONDARY_AI"
  expect(Either.isLeft(validateDevelopmentDayProjection(badUserAuthority, source))).toBe(true)
  const badSource = structuredClone(dayValue) as { nodes: Array<{ uid: string; properties: Record<string, unknown> }> }
  const sourceNode = badSource.nodes.find(node => node.properties["source_path"] === "docs/canon/sources/USER_PRIMARY_HSWM_SELF_DEVELOPMENT_AND_DAILY_KG_2026-09-08.txt")
  if (sourceNode === undefined) throw new Error("missing source node")
  sourceNode.properties["source_sha256"] = "0".repeat(64)
  expect(Either.isLeft(validateDevelopmentDayProjection(badSource, source))).toBe(true)
})
it("keeps the original work, frontier, and day projection refusal contracts on source bindings, relation rows, and user-source links", () => {
  const workValue = json(work)
  const bindingDrift: HistoricalBlobSource = { readPath: source.readPath, readBlob: () => new TextEncoder().encode("drift") }
  expect(Either.isLeft(validateDevelopmentWorkProjection(workValue, bindingDrift))).toBe(true)
  const malformedFrontier = structuredClone(json(frontier)) as { relations: unknown; expected_counts: Record<string, number> }
  malformedFrontier.relations = ["not-a-relation"]
  malformedFrontier.expected_counts["relations"] = 1
  expect(Either.isLeft(validateFrontierLearningProjection(malformedFrontier, source))).toBe(true)
  const duplicateFrontier = structuredClone(json(frontier)) as { relations: Array<Record<string, unknown>>; expected_counts: Record<string, number> }
  duplicateFrontier.relations.push({ ...duplicateFrontier.relations[0]! })
  duplicateFrontier.expected_counts["relations"] = duplicateFrontier.relations.length
  expect(Either.isLeft(validateFrontierLearningProjection(duplicateFrontier, source))).toBe(true)
  const missingUserSource = structuredClone(json(day)) as { relations: Array<{ from_uid: string; to_uid: string; type: string }> }
  const userSource = missingUserSource.relations.find(relation => relation.from_uid === "sym:AbstractNode:hswm-development-day-2026-09-08-user-request" && relation.type === "HAS_SOURCE")
  if (userSource === undefined) throw new Error("missing day user-source relation")
  userSource.to_uid = "sym:AbstractNode:missing"
  expect(Either.isLeft(validateDevelopmentDayProjection(missingUserSource, source))).toBe(true)
})
it("writes only derived export artifacts through each injected bounded writer", () => {
  for (const [path, exportProjection] of [[work, exportDevelopmentWorkProjection], [frontier, exportFrontierLearningProjection], [day, exportDevelopmentDayProjection]] as const) {
    const writes: Array<readonly [string, Uint8Array]> = []
    const writer = { write: (name: string, contents: Uint8Array) => { writes.push([name, contents]); return Effect.void } }
    const result = Effect.runSync(Effect.either(exportProjection(json(path), raw(path), source, writer)))
    expect(Either.isRight(result)).toBe(true)
    expect(writes.map(([name]) => name)).toEqual(["view.nq", "manifest.json", "prov.jsonld"])
    expect(new TextDecoder().decode(writes[0]![1])).toContain("urn:hswm:kg-bundle-projection:")
  }
})
it("preloads bounded current and historical source bytes before pure validation", async () => {
  const path = "docs/canon/sources/USER_PRIMARY_HSWM_SELF_DEVELOPMENT_AND_DAILY_KG_2026-09-08.txt"
  const loaded = await Effect.runPromise(preloadDevelopmentProjectionSources(root, { currentPaths: [path], historical: [{ commit: "d4fed000369f1b6545c505dd9505e7c9b3c41cf7", path }] }).pipe(Effect.provide(NodePosixServicesLive)))
  expect(loaded.readPath(path)?.byteLength).toBeGreaterThan(0)
  expect(loaded.readBlob("d4fed000369f1b6545c505dd9505e7c9b3c41cf7", path)?.byteLength).toBeGreaterThan(0)
  expect(loaded.readBlob("other", path)).toBeUndefined()
})
it("fails closed when a preloaded source or historical Git blob is unavailable", async () => {
  const missingCurrent = await Effect.runPromise(preloadDevelopmentProjectionSources(root, { currentPaths: ["missing-development-projection-source"], historical: [] }).pipe(Effect.either, Effect.provide(NodePosixServicesLive)))
  expect(Either.isLeft(missingCurrent)).toBe(true)
  const missingHistorical = await Effect.runPromise(preloadDevelopmentProjectionSources(root, { currentPaths: [], historical: [{ commit: "0000000000000000000000000000000000000000", path: work }] }).pipe(Effect.either, Effect.provide(NodePosixServicesLive)))
  expect(Either.isLeft(missingHistorical)).toBe(true)
})
it("fails closed when bounded Git observation times out or truncates output", async () => {
  for (const observation of [
    { exitCode: null, signal: "SIGTERM", timedOut: true, outputTruncated: false, launchError: null, stdout: new Uint8Array(), stderr: new Uint8Array() },
    { exitCode: 0, signal: null, timedOut: false, outputTruncated: true, launchError: null, stdout: new Uint8Array(), stderr: new Uint8Array() }
  ] as const) {
    const services = Layer.merge(NodePosixFileSystemLive, Layer.succeed(BoundedSubprocess, { observe: () => Effect.succeed(observation) }))
    const result = await Effect.runPromise(preloadDevelopmentProjectionSources(root, { currentPaths: [], historical: [{ commit: "d4fed000369f1b6545c505dd9505e7c9b3c41cf7", path: work }] }).pipe(Effect.either, Effect.provide(services)))
    expect(Either.isLeft(result)).toBe(true)
  }
})
it("runs public validation, exclusive SHACL export, and reviewed mock apply without cwd or live publication", async () => {
  const exportRoot = mkdtempSync(join(tmpdir(), "hswm-native-development-projection-"), { encoding: "utf8" })
  const exportDir = join(exportRoot, "projection")
  const validate = await Effect.runPromise(runNativeDevelopmentProjectionCli(["work", "--repo-root", root]).pipe(Effect.provide(NodePosixServicesLive)))
  expect(validate.exitCode).toBe(0)
  expect(JSON.parse(validate.stdout).status).toBe("VALIDATED_ONLY_NOT_PUBLISHED")
  const exported = await Effect.runPromise(runNativeDevelopmentProjectionCli(["day", "--repo-root", root, "--export-dir", exportDir]).pipe(Effect.provide(NodePosixServicesLive)))
  expect(exported.exitCode).toBe(0)
  expect(readFileSync(join(exportDir, "validation.json"), "utf8")).toContain("conforms")
  const config = join(exportRoot, "source-config.yaml")
  writeFileSync(config, "uri: bolt://example.invalid\nuser: test\npassword: test-password\ndatabase: neo4j\n")
  let published = 0
  const publisher = { publish: () => { published++; return Effect.succeed({ created_nodes: 1 }) } }
  const applied = await Effect.runPromise(runNativeDevelopmentProjectionCli(["work", "--repo-root", root, "--source-config", config, "--apply"], publisher).pipe(Effect.provide(NodePosixServicesLive)))
  expect(applied.exitCode).toBe(0)
  expect(published).toBe(1)
})
it("parses only the required flat Neo4j source-config fields and rejects unsafe credentials configuration", () => {
  const accepted = Effect.runSync(Effect.either(parseNativeDevelopmentProjectionSourceConfig("uri: bolt://example.invalid\nuser: projection\npassword: never-log-this\ndatabase: neo4j\n")))
  expect(Either.isRight(accepted)).toBe(true)
  const refused = Effect.runSync(Effect.either(parseNativeDevelopmentProjectionSourceConfig("uri: https://not-neo4j.invalid\nuser: x\npassword: y\ndatabase: invalid/database\n")))
  expect(Either.isLeft(refused)).toBe(true)
  expect(JSON.stringify(refused)).not.toContain("never-log-this")
})
it("executes the injected managed transaction to create, read back, and idempotently return the full original counts", async () => {
  const valid = validateDevelopmentWorkProjection(json(work), source)
  if (Either.isLeft(valid)) throw new Error(valid.left.detail)
  const sha = "737324f0a9b64d061d7155c207a62877a122c1818b2a56460b54fe6e7050ca64"
  const fake = makeProjectionDriver(valid.right)
  const publisher = makeNativeDevelopmentProjectionPublisher({ uri: "bolt://example.invalid", user: "projection", password: "credential-must-not-leak", database: "neo4j" }, () => fake.driver)
  const created = await Effect.runPromise(publisher.publish(valid.right, sha))
  expect(created).toEqual({ created_nodes: valid.right.nodes.length, created_relations: valid.right.relations.length, existing_nodes: 0, existing_relations: 0, readback_nodes: valid.right.nodes.length, readback_relations: valid.right.relations.length })
  expect(fake.closed).toBe(true)
  expect(fake.statements[0]).toEqual(["MATCH (r:SchemaRegistry {uid:$uid}) RETURN r.allowed_labels AS labels, r.allowed_reltypes AS relations", { uid: "sym:KG_INFRA:schema-registry-v1-2026-08-03" }])
  expect(fake.statements.filter(([statement]) => statement.startsWith("CREATE (n:"))).toHaveLength(valid.right.nodes.length)
  expect(fake.statements.filter(([statement]) => statement.includes(" CREATE (a)-[r:"))).toHaveLength(valid.right.relations.length)
  expect(fake.statements.filter(([statement]) => statement.startsWith("MATCH (n) WHERE n.uid IN $uids"))).toHaveLength(3)
  const existing = await Effect.runPromise(publisher.publish(valid.right, sha))
  expect(existing).toEqual({ created_nodes: 0, created_relations: 0, existing_nodes: valid.right.nodes.length, existing_relations: valid.right.relations.length, readback_nodes: valid.right.nodes.length, readback_relations: valid.right.relations.length })
  expect(fake.writes).toBe(2)
})
it("refuses collision, readback, and ownership-count failures without committing a mocked transaction and always closes it", async () => {
  const valid = validateDevelopmentWorkProjection(json(work), source)
  if (Either.isLeft(valid)) throw new Error(valid.left.detail)
  const sha = "737324f0a9b64d061d7155c207a62877a122c1818b2a56460b54fe6e7050ca64"
  const config = { uri: "bolt://example.invalid", user: "projection", password: "credential-must-not-leak", database: "neo4j" }
  const collision = makeProjectionDriver(valid.right)
  const collisionPublisher = makeNativeDevelopmentProjectionPublisher(config, () => collision.driver)
  await Effect.runPromise(collisionPublisher.publish(valid.right, sha))
  collision.corruptFirstOwnedNode()
  const collisionResult = await Effect.runPromise(Effect.either(collisionPublisher.publish(valid.right, sha)))
  expect(Either.isLeft(collisionResult)).toBe(true)
  expect(JSON.stringify(collisionResult)).toContain("node collision")
  expect(collision.closed).toBe(true)
  for (const fault of ["readback", "count"] as const) {
    const fake = makeProjectionDriver(valid.right, fault)
    const publisher = makeNativeDevelopmentProjectionPublisher(config, () => fake.driver)
    const result = await Effect.runPromise(Effect.either(publisher.publish(valid.right, sha)))
    expect(Either.isLeft(result), fault).toBe(true)
    expect(fake.ownedNodeCount, fault).toBe(0)
    expect(fake.ownedRelationCount, fault).toBe(0)
    expect(fake.closed, fault).toBe(true)
    expect(JSON.stringify(result), fault).not.toContain("credential-must-not-leak")
  }
  const hanging = makeProjectionDriver(valid.right, "hang")
  const hangingPublisher = makeNativeDevelopmentProjectionPublisher(config, () => hanging.driver, "5 millis")
  const timedOut = await Effect.runPromise(Effect.either(hangingPublisher.publish(valid.right, sha)))
  expect(Either.isLeft(timedOut)).toBe(true)
  expect(hanging.closed).toBe(true)
  expect(hanging.ownedNodeCount).toBe(0)
  expect(hanging.transactionTimeouts).toEqual([5])
})
it("sends the server transaction deadline and cannot commit when an interrupted query resolves late", async () => {
  const valid = validateDevelopmentWorkProjection(json(work), source)
  if (Either.isLeft(valid)) throw new Error(valid.left.detail)
  const sha = "737324f0a9b64d061d7155c207a62877a122c1818b2a56460b54fe6e7050ca64"
  const late = makeProjectionDriver(valid.right, "late")
  const publisher = makeNativeDevelopmentProjectionPublisher({ uri: "bolt://example.invalid", user: "projection", password: "credential-must-not-leak", database: "neo4j" }, () => late.driver, "5 millis")
  const outcome = await Effect.runPromise(Effect.either(publisher.publish(valid.right, sha)))
  expect(Either.isLeft(outcome)).toBe(true)
  expect(late.transactionTimeouts).toEqual([5])
  expect(late.closed).toBe(true)
  expect(late.rollbacks).toBe(1)
  late.resolveLate()
  await new Promise(resolve => setTimeout(resolve, 20))
  expect(late.commits).toBe(0)
  expect(late.ownedNodeCount).toBe(0)
  expect(late.ownedRelationCount).toBe(0)
})
it("runs the freshly emitted public process from a foreign cwd with only Node on PATH", () => {
  const emitted = mkdtempSync(join(tmpdir(), "hswm-native-development-process-"), { encoding: "utf8" })
  const foreign = mkdtempSync(join(tmpdir(), "hswm-native-development-foreign-cwd-"), { encoding: "utf8" })
  symlinkSync(resolve(root, "src/hswm/effect-runtime/node_modules"), join(emitted, "node_modules"))
  execFileSync(process.execPath, [resolve(root, "src/hswm/effect-runtime/node_modules/typescript/bin/tsc"), "--module", "NodeNext", "--moduleResolution", "NodeNext", "--target", "ES2023", "--skipLibCheck", "--outDir", emitted, "--rootDir", resolve(root, "src/hswm/effect-runtime/src"), resolve(root, "src/hswm/effect-runtime/src/native-development-projection-process.ts")], { cwd: foreign, env: { PATH: dirname(process.execPath) } })
  const stdout = execFileSync(process.execPath, [join(emitted, "native-development-projection-process.js"), "work", "--repo-root", root], { cwd: foreign, env: { PATH: dirname(process.execPath) }, encoding: "utf8" })
  expect(JSON.parse(stdout).status).toBe("VALIDATED_ONLY_NOT_PUBLISHED")
})
it("reproduces the checked-in read-only N-Quads views from exact source bytes", () => {
  const projections = [
    [work, "ontology/projections/hswm_adaptive_development_work_2026-09-08", compileDevelopmentWorkProjection],
    [frontier, "ontology/projections/hswm_frontier_learning_theory_2026-09-07", compileFrontierLearningProjection],
    [day, "ontology/projections/hswm_development_day_2026-09-08", compileDevelopmentDayProjection]
  ] as const
  for (const [input, output, compile] of projections) {
    const result = compile(json(input), raw(input), source)
    if (Either.isLeft(result)) throw new Error(result.left.detail)
    expect(new TextDecoder().decode(result.right.nquads), input).toBe(readFileSync(resolve(root, output, "view.nq"), "utf8"))
  }
})
it("replays the frontier source-index snapshot from exact historical Git blobs", () => {
  const snapshot = json("ontology/history/HSWM_FRONTIER_LEARNING_THEORY_SOURCE_SNAPSHOT.v1.json")
  const result = validateFrontierHistoricalSnapshot(snapshot, raw(frontier), source)
  expect(Either.isRight(result)).toBe(true)
  if (Either.isRight(result)) expect(result.right).toEqual({ historical_source_commit: "6e2e49f881ac96cd24cc3064d87273075be339a6", artifact_bindings: 14 })
  const corrupted = structuredClone(snapshot) as { artifact_bindings: Array<{ sha256: string }> }
  corrupted.artifact_bindings[0]!.sha256 = "0".repeat(64)
  expect(Either.isLeft(validateFrontierHistoricalSnapshot(corrupted, raw(frontier), source))).toBe(true)
  const rawHashDrift = structuredClone(snapshot) as { bundle_sha256: string }
  rawHashDrift.bundle_sha256 = "0".repeat(64)
  expect(Either.isLeft(validateFrontierHistoricalSnapshot(rawHashDrift, raw(frontier), source))).toBe(true)
  const missingBundleBlob: HistoricalBlobSource = { readPath: source.readPath, readBlob: (commit, path) => path === frontier ? undefined : source.readBlob(commit, path) }
  expect(Either.isLeft(validateFrontierHistoricalSnapshot(snapshot, raw(frontier), missingBundleBlob))).toBe(true)
})
it("keeps every frontier literature source connected to its falsifiable bridge", () => {
  expect(Either.isRight(validateFrontierPaperTopology(json(frontier)))).toBe(true)
  const changed = structuredClone(json(frontier)) as { nodes: Array<{ properties: Record<string, unknown> }> }
  const paper = changed.nodes.find(node => node.properties["standard_graph_role"] === "LITERATURE_SOURCE")
  if (paper === undefined) throw new Error("missing literature source")
  paper.properties["authors"] = ""
  expect(Either.isLeft(validateFrontierPaperTopology(changed))).toBe(true)
  const remove = (type: string) => {
    const data = structuredClone(json(frontier)) as { relations: Array<{ type: string }> }
    data.relations = data.relations.filter(edge => edge.type !== type)
    return data
  }
  for (const type of ["HAS_CONCEPT", "SPECULATIVE_LINK", "REQUIRES", "TESTS"]) expect(Either.isLeft(validateFrontierPaperTopology(remove(type)))).toBe(true)
  const wrongAuthority = structuredClone(json(frontier)) as { relations: Array<{ authority_class: string }> }
  wrongAuthority.relations[0]!.authority_class = "USER_PRIMARY"
  expect(Either.isLeft(validateFrontierPaperTopology(wrongAuthority))).toBe(true)
})
it("refuses unreviewed bytes before the injected bounded gateway and dispatches exact reviewed bytes", () => {
  let calls = 0
  const publisher = { publish: () => { calls++; return Effect.succeed({ created_nodes: 2 }) } }
  const data = json(work), bytes = raw(work)
  const rejected = Effect.either(applyReviewedDevelopmentWorkProjection(data, bytes, "0".repeat(64), source, publisher))
  expect(Effect.runSync(rejected)).toMatchObject({ _tag: "Left" })
  expect(calls).toBe(0)
  const forged = structuredClone(data) as { nodes: Array<{ properties: Record<string, unknown> }> }
  forged.nodes[0]!.properties["name"] = "forged reviewed payload"
  expect(Effect.runSync(Effect.either(applyReviewedDevelopmentWorkProjection(forged, bytes, "737324f0a9b64d061d7155c207a62877a122c1818b2a56460b54fe6e7050ca64", source, publisher)))).toMatchObject({ _tag: "Left" })
  expect(calls).toBe(0)
  const applied = Effect.runSync(applyReviewedDevelopmentWorkProjection(data, bytes, "737324f0a9b64d061d7155c207a62877a122c1818b2a56460b54fe6e7050ca64", source, publisher))
  expect(applied).toEqual({ created_nodes: 2 })
  expect(calls).toBe(1)
})
it("refuses unreviewed frontier and day bytes before their bounded publisher gateways", () => {
  let calls = 0
  const publisher = { publish: () => { calls++; return Effect.succeed({ created_nodes: 1 }) } }
  expect(Effect.runSync(Effect.either(applyReviewedFrontierLearningProjection(json(frontier), raw(frontier), "0".repeat(64), source, publisher)))).toMatchObject({ _tag: "Left" })
  expect(Effect.runSync(Effect.either(applyReviewedDevelopmentDayProjection(json(day), raw(day), "0".repeat(64), source, publisher)))).toMatchObject({ _tag: "Left" })
  expect(calls).toBe(0)
})
