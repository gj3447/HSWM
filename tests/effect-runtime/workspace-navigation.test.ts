import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { Effect, Either } from "effect"
import { describe, expect, it } from "vitest"
import { runWorkspaceCli } from "../../src/hswm/effect-runtime/src/workspace-cli.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"
import { decodeWorkspaceManifest, type WorkspaceManifest } from "../../src/hswm/effect-runtime/src/workspace-manifest-domain.js"
import { runWorkspaceNavigation } from "../../src/hswm/effect-runtime/src/workspace-navigation-runtime.js"
import { compileKgBundle, decodeKgBundleSource, kgSha256, type KgBundle } from "../../src/hswm/effect-runtime/src/native-kg-bundle-domain.js"
import { queryKgBundle, validateKgShacl } from "../../src/hswm/effect-runtime/src/native-kg-standards.js"

const bytes = (value: unknown) => new TextEncoder().encode(JSON.stringify(value))
const text = (value: string) => new TextEncoder().encode(value)
const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error(String(value.left))
  return value.right
}
const uid = (id: string) => `sym:AbstractNode:${id}`
const bundle = (id: string, anchors: readonly string[] = [], source = `source for ${id}\n`): KgBundle => ({
  schema_version: "workspace-navigation-test/v1", bundle_uid: uid(id), status: "TEST", nonclaim: "TEST_ONLY",
  artifact_bindings: [{ path: `docs/${id}.md`, sha256: kgSha256(source) }],
  expected_counts: { nodes: 1, anchors: anchors.length, relations: anchors.length },
  nodes: [{ uid: uid(id), labels: ["AbstractNode"], properties: {
    name: id, authority_class: "SECONDARY_AI", status: "ACTIVE", source_path: `docs/${id}.md`, source_sha256: kgSha256(source),
  } }],
  anchors: anchors.map(id => ({ uid: uid(id), name: id, required_labels: ["AbstractNode"] })),
  relations: anchors.map(id => ({ from_uid: uid("root"), to_uid: uid(id), type: "RELATED_TO", authority_class: "SECONDARY_AI", scope: "TEST", status: "RETIRED" })),
})
const fixture = () => {
  const root = bundle("root", ["middle", "unread"])
  const middleBase = bundle("middle", ["leaf"])
  const middle = { ...middleBase, relations: middleBase.relations.map(r => ({ ...r, from_uid: uid("middle"), status: "PROPOSED" })) }
  const leaf = bundle("leaf")
  const files = new Map<string, Uint8Array>([
    ["ontology/root.json", bytes(root)], ["ontology/middle.json", bytes(middle)], ["ontology/leaf.json", bytes(leaf)],
    ["docs/leaf.md", text("source for leaf\n")],
  ])
  const raw = {
    schema_version: "hswm-workspace-manifest/v1", authority: "SECONDARY_AI_NAVIGATION_ONLY", workflows: [],
    entries: [root, middle, leaf, bundle("unread")].map(b => {
      const id = String(b.nodes[0]?.properties["name"])
      return { id, title: id, lane: "ENGINEERING", reading: "fixture", bundle: `ontology/${id}.json`, document: `docs/${id}.md`, queries: [], shapes: [],
        anchor_routes: b.anchors.filter(a => a.name !== "unread").map(a => ({ uid: a.uid, entry: a.name, sha256: kgSha256(files.get(`ontology/${a.name}.json`) ?? new Uint8Array()) })) }
    }),
  }
  const manifest = right(decodeWorkspaceManifest(raw))
  const reads: string[] = []
  const run = (command: "navigate" | "follow" | "read", entryId: string, selectedUid?: string, overrides: {
    expectedSha256?: string; offset?: number; limit?: number; maximumBytes?: number
  } = {}) => Effect.runPromise(runWorkspaceNavigation({ command, entryId, uid: selectedUid, expectedSha256: overrides.expectedSha256,
    offset: overrides.offset ?? 0, limit: overrides.limit ?? 16, maximumBytes: overrides.maximumBytes ?? 65536, manifest,
    read: path => Effect.sync(() => { reads.push(path); return files.get(path) }).pipe(Effect.flatMap(value =>
      value === undefined ? Effect.fail(new Error(`unexpected read: ${path}`)) : Effect.succeed(value))),
  }).pipe(Effect.mapError(error => new Error("detail" in error ? error.detail : error.message))))
  return { files, reads, run, raw }
}

describe("explicit multi-hop source navigation", () => {
  it("reads only the selected neighborhood and preserves withdrawn edge status independently", async () => {
    const f = fixture()
    const result = JSON.parse((await f.run("navigate", "root", undefined, { limit: 1 })).stdout)
    expect(f.reads).toEqual(["ontology/root.json"])
    expect(result.neighborhood.complete).toBe(false)
    expect(result.neighborhood.nextOffset).toBe(1)
    expect(result.neighborhood.neighbors[0].edge.status).toBe("RETIRED")
    expect(result.neighborhood.node.properties.status).toBe("ACTIVE")
    const second = JSON.parse((await f.run("navigate", "root", undefined, { offset: 1, expectedSha256: result.bundleSha256 })).stdout)
    expect(second.neighborhood.neighbors.map((n: { target: { uid: string } }) => n.target.uid)).toEqual([uid("unread")])
    expect(second.neighborhood.complete).toBe(true)
  })

  it("crosses two separate maps before reading the selected source, without fetching an unrelated sibling", async () => {
    const f = fixture()
    const first = JSON.parse((await f.run("follow", "root", uid("middle"))).stdout)
    expect(first.next.entry).toBe("middle")
    const second = JSON.parse((await f.run("follow", first.next.entry, uid("leaf"), { expectedSha256: first.next.sha256 })).stdout)
    const result = JSON.parse((await f.run("read", second.next.entry, second.next.uid, { expectedSha256: second.next.sha256 })).stdout)
    expect(result.text).toBe("source for leaf\n")
    expect(result.complete).toBe(true)
    expect(f.reads).toEqual(["ontology/root.json", "ontology/middle.json", "ontology/middle.json", "ontology/leaf.json", "ontology/leaf.json", "docs/leaf.md"])
    expect(f.reads).not.toContain("ontology/unread.json")
  })

  it("rejects unbound anchors without global search", async () => {
    const f = fixture()
    await expect(f.run("follow", "root", uid("unread"))).rejects.toThrow("explicit route")
    expect(f.reads).toEqual(["ontology/root.json"])
  })

  it("rejects changed destination bytes and stale current-bundle pins", async () => {
    const f = fixture()
    f.files.set("ontology/middle.json", bytes(bundle("middle")))
    await expect(f.run("follow", "root", uid("middle"))).rejects.toThrow("digest")
    await expect(f.run("navigate", "root", undefined, { expectedSha256: "0".repeat(64) })).rejects.toThrow("digest")
  })

  it("rejects source drift, absent UIDs and incomplete output budgets", async () => {
    const f = fixture()
    f.files.set("docs/leaf.md", text("changed\n"))
    await expect(f.run("read", "leaf", uid("leaf"))).rejects.toThrow("source digest mismatch")
    await expect(f.run("navigate", "root", uid("unknown"))).rejects.toThrow("UID absent")
    await expect(f.run("read", "root", uid("middle"))).rejects.toThrow("follow an external anchor")
    await expect(f.run("navigate", "root", undefined, { maximumBytes: 10 })).rejects.toThrow("no partial source")
    await expect(f.run("navigate", "root", undefined, { offset: 20 })).rejects.toThrow("offset exceeds")
  })

  it("rejects duplicate identities and source paths outside the content domains", async () => {
    const f = fixture()
    const original = bundle("leaf")
    f.files.set("ontology/leaf.json", bytes({ ...original, nodes: [...original.nodes, ...original.nodes] }))
    await expect(f.run("read", "leaf", uid("leaf"))).rejects.toThrow("duplicate node")
    f.files.set("ontology/leaf.json", bytes({ ...original,
      nodes: original.nodes.map(node => ({ ...node, properties: { ...node.properties, source_path: ".env" } })),
      artifact_bindings: [{ path: ".env", sha256: kgSha256("source for leaf\n") }],
    }))
    await expect(f.run("read", "leaf", uid("leaf"))).rejects.toThrow()
    expect(f.reads).not.toContain(".env")
  })

  it("refuses ambiguous and dangling route declarations", () => {
    const { raw } = fixture()
    const entry = raw.entries[0]
    if (!entry) throw new Error("missing fixture")
    const route = entry.anchor_routes[0]
    if (!route) throw new Error("missing route")
    expect(Either.isLeft(decodeWorkspaceManifest({ ...raw, entries: [{ ...entry, anchor_routes: [route, route] }, ...raw.entries.slice(1)] }))).toBe(true)
    expect(Either.isLeft(decodeWorkspaceManifest({ ...raw, entries: [{ ...entry, anchor_routes: [{ ...route, entry: "missing" }] }, ...raw.entries.slice(1)] }))).toBe(true)
  })
})

const checkout = resolve(import.meta.dirname, "../..")
const read = (path: string) => readFileSync(resolve(checkout, path))
const manifest: WorkspaceManifest = right(decodeWorkspaceManifest(JSON.parse(read("ontology/workspace/HSWM_WORKSPACE.v1.json").toString())))
const modules = manifest.entries.filter(entry => entry.id === "constitution" || entry.id.startsWith("constitution-"))
const source = (id: string) => {
  const entry = manifest.entries.find(entry => entry.id === id)
  if (!entry) throw new Error(`missing ${id}`)
  return right(decodeKgBundleSource({ sourceId: entry.id, rawBytes: read(entry.bundle) })).bundle
}
const cli = (argv: readonly string[]) => Effect.runPromise(runWorkspaceCli([...argv, "--checkout", checkout]).pipe(Effect.provide(NodePosixServicesLive)))

describe("current HSWM constitution graph", () => {
  it("keeps every registered topic reachable, with historical source-only content explicit", () => {
    const routed = new Set(modules.flatMap(entry => entry.anchor_routes?.map(route => route.entry) ?? []))
    const historical = new Set(modules.flatMap(entry => source(entry.id).nodes.flatMap(node =>
      typeof node.properties["legacy_entry_id"] === "string" ? [node.properties["legacy_entry_id"]] : [])))
    for (const entry of manifest.entries.filter(entry => !entry.id.startsWith("constitution")))
      expect(routed.has(entry.id) || historical.has(entry.id), entry.id).toBe(true)
    expect(historical).toEqual(new Set(["fractal"]))
  })

  it("binds each current module/source and every explicit destination to actual bytes and exact typed identities", () => {
    for (const entry of modules) {
      const b = source(entry.id)
      for (const binding of b.artifact_bindings) expect(kgSha256(read(binding.path)), binding.path).toBe(binding.sha256)
      for (const route of entry.anchor_routes ?? []) {
        const target = manifest.entries.find(entry => entry.id === route.entry)
        if (!target) throw new Error("missing target")
        expect(kgSha256(read(target.bundle)), target.id).toBe(route.sha256)
        const anchor = b.anchors.find(anchor => anchor.uid === route.uid)
        const node = source(target.id).nodes.find(node => node.uid === route.uid)
        expect(node, route.uid).toBeDefined()
        expect(anchor?.required_labels.every(label => node?.labels.includes(label))).toBe(true)
      }
    }
  })

  it("validates real SHACL and exact SPARQL targets for each module; authority promotion is rejected", async () => {
    const shapes = read("schemas/HSWM_CONSTITUTION_NAVIGATION_SHACL_1_0.ttl")
    for (const entry of modules) {
      const b = source(entry.id)
      const projection = right(compileKgBundle([{ sourceId: entry.id, rawBytes: read(entry.bundle) }], "v2"))
      expect((await Effect.runPromise(validateKgShacl(projection, shapes))).conforms, entry.id).toBe(true)
      const rows = await Effect.runPromise(queryKgBundle(projection, read("ontology/queries/hswm_constitution/contents.rq").toString()))
      if (typeof rows === "boolean") throw new Error("SELECT expected")
      const moduleUids = new Set(b.nodes.filter(node => node.properties["standard_graph_role"] === "CONSTITUTION_MODULE").map(node => node.uid))
      expect(rows.map(row => row["target"]?.["value"]).sort()).toEqual(b.relations
        .filter(edge => edge.type === "HAS_CONCEPT" && moduleUids.has(edge.from_uid)).map(edge => edge.to_uid).sort())
    }
    const b = source("constitution")
    const forged = { ...b, nodes: b.nodes.map(node => ({ ...node, properties: { ...node.properties, authority_class: "USER_PRIMARY" } })) }
    const projected = right(compileKgBundle([{ sourceId: "forged", rawBytes: bytes(forged) }], "v2"))
    expect((await Effect.runPromise(validateKgShacl(projected, shapes))).conforms).toBe(false)
  }, 30_000)

  it.each([
    ["What is the AI state?", "constitution-state", "state-operator"],
    ["How do tool, condition and rule connect?", "constitution-activation", "tool-harness"],
    ["What changes after an outcome?", "constitution-learning", "semantic-topology"],
    ["How do CHU and HSWM differ?", "constitution-composition", "chu-being"],
    ["What supports the W claims?", "constitution-assurance", "w1-reference"],
  ])("answers %s through explicit source-scoped hops", async (_question, moduleId, targetId) => {
    const rootRoute = manifest.entries.find(entry => entry.id === "constitution")?.anchor_routes?.find(route => route.entry === moduleId)
    const targetRoute = manifest.entries.find(entry => entry.id === moduleId)?.anchor_routes?.find(route => route.entry === targetId)
    if (!rootRoute || !targetRoute) throw new Error("missing question path")
    const first = JSON.parse((await cli(["follow", "constitution", "--uid", rootRoute.uid])).stdout)
    const second = JSON.parse((await cli(["follow", first.next.entry, "--uid", targetRoute.uid, "--sha256", first.next.sha256])).stdout)
    expect(second.next.entry).toBe(targetId)
    expect(second.neighborhood.node.uid).toBe(targetRoute.uid)
  })

  it("reads the actual two user messages without treating assistant interpretation as user words", async () => {
    const result = JSON.parse((await cli(["read", "constitution-activation", "--uid", uid("hswm-multihop-user-source-2026-10-24")])).stdout)
    expect(result.source.authority).toBe("USER_PRIMARY")
    expect(result.text).toContain("타고타고타고")
    expect(result.text).toContain("HSWM 헌법도 부족하고")
    expect(result.text).not.toContain("국소성은 한두 홉")
    expect(result.complete).toBe(true)
  })

  it.each(["constitution", "constitution-learning", "constitution-composition", "constitution-assurance"])(
    "reaches the Internet evidence contract from %s with an exact source pin", async entry => {
      const designUid = uid("hswm-internet-evidence-acquisition-2026-10-24")
      const hop = JSON.parse((await cli(["follow", entry, "--uid", designUid])).stdout)
      expect(hop.next.entry).toBe("constitution-activation")
      const result = JSON.parse((await cli(["read", hop.next.entry, "--uid", hop.next.uid, "--sha256", hop.next.sha256])).stdout)
      expect(result.source.authority).toBe("SECONDARY_AI")
      expect(result.text).toBe(read("docs/research/HSWM_INTERNET_NATIVE_EVIDENCE_ACQUISITION_2026-10-24.md").toString())
      expect(result.complete).toBe(true)
    },
  )

  it("keeps the Internet-native request separate from the proposed retrieval and participation design", async () => {
    const sourceUid = uid("hswm-internet-native-user-source-2026-10-24")
    const design = JSON.parse((await cli(["navigate", "constitution-activation", "--uid", uid("hswm-internet-evidence-acquisition-2026-10-24")])).stdout)
    expect(design.neighborhood.neighbors.map((neighbor: { target: { uid: string } }) => neighbor.target.uid)).toContain(sourceUid)
    const hop = JSON.parse((await cli(["follow", "constitution-composition", "--uid", sourceUid])).stdout)
    const result = JSON.parse((await cli(["read", hop.next.entry, "--uid", sourceUid, "--sha256", hop.next.sha256])).stdout)
    expect(result.source.authority).toBe("USER_PRIMARY")
    expect(result.text).toContain("그 검색이 부족한지도 만들어줘야하는데 ㅇㅇ 언제 검색해서 가져올지 이런것도 그리고 HSWM 이 인터넷 native 하게 인류랑 같이 움직여줘야함 ㅇㅇ")
    expect(result.text).toBe(read("docs/canon/sources/USER_PRIMARY_HSWM_INTERNET_NATIVE_2026-10-24.md").toString())
    expect(result.complete).toBe(true)
  })
})
