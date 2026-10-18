import { createHash } from "node:crypto"
import { spawnSync } from "node:child_process"
import { fileURLToPath } from "node:url"
import { Effect, Either } from "effect"
import { describe, expect, it } from "vitest"
import type { SemanticReadFrame } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.js"
import { reviewFiniteSemanticFrame, reviewFiniteSemanticRequest, type FiniteProgram } from "../../src/hswm/effect-runtime/src/semantic-context-finite-domain.js"
import { encodeSemanticFrameRepresentation } from "../../src/hswm/effect-runtime/src/semantic-frame-representation.js"
import { reviewPlannedFiniteSemantics } from "../../src/hswm/effect-runtime/src/semantic-context-finite-runtime.js"
import { prepareSemanticContext } from "../../src/hswm/effect-runtime/src/semantic-context-runtime.js"
import { semanticContextProcess } from "../../src/hswm/effect-runtime/src/semantic-context-process.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"
import { schema, spec, unwrap, withContextFixture } from "./semantic-context-fixture.js"

const hash = (s: string) => createHash("sha256").update(s).digest("hex")
const key = (atomUid: string) => ({ schemaVersion: "finite-test", lineageId: "fixture", atomUid, revisionId: 0 })
const frame = (program: unknown): SemanticReadFrame => {
  const bare = {
    event: "finite meaning review", stateRevision: 7,
    relation: { key: key("relation"), owner: "owner:test", semantic: {
      semanticText: typeof program === "string" ? program : JSON.stringify(program), disposition: "predict", uncertainty: "declared finite scope only",
      exceptionRefs: ["exception"], trace: null, outcome: null
    } },
    roles: ["subject", "context", "evidence", "exception"].map(role => ({ referenceType: "hswm:semantic:role", role, key: key(role), owner: "owner:test", contentSha256: hash(role), contentUtf8: role })), priorEvidence: null
  }
  return { ...bare, frameSha256: hash(JSON.stringify(bare)) }
}
const variables = ["guard", "required", "exception"].map((id, i) => ({ id, roleOrdinal: [0, 1, 3][i] ?? 0, values: ["0", "1"] }))
const unless: FiniteProgram = {
  contract: "hswm-finite-semantic-program/v1", variables,
  expressions: [{ op: "is", variable: "guard", value: "1" }, { op: "is", variable: "exception", value: "1" }, { op: "is", variable: "required", value: "1" }, { op: "unless", when: 0, exception: 1, require: 2 }],
  clauses: [{ id: "rule", expression: 3 }]
}
// Construct independent truth tables as DNF, then compare with integer bit-set oracles.
const truthTable = (mask: number, count = 2): FiniteProgram => {
  const vars = variables.slice(0, count)
  const expressions: Array<FiniteProgram["expressions"][number]> = []
  const add = (expr: FiniteProgram["expressions"][number]) => { expressions.push(expr); return expressions.length - 1 }
  let root: number | undefined
  for (let row = 0; row < 2 ** count; row++) {
    if (!(mask & (1 << row))) continue
    let term: number | undefined
    vars.forEach((v, i) => {
      const atom = add({ op: "is", variable: v.id, value: String((row >> (count - i - 1)) & 1) })
      term = term === undefined ? atom : add({ op: "and", left: term, right: atom })
    })
    if (term !== undefined) root = root === undefined ? term : add({ op: "or", left: root, right: term })
  }
  if (root === undefined) { const atom = add({ op: "is", variable: "guard", value: "1" }); root = add({ op: "and", left: atom, right: add({ op: "not", arg: atom }) }) }
  return { contract: unless.contract, variables: vars, expressions, clauses: [{ id: "truth", expression: root }] }
}
const errorCode = <A, E>(result: Either.Either<A, E>) => {
  expect(Either.isLeft(result)).toBe(true)
  return Either.isLeft(result) && typeof result.left === "object" && result.left !== null && "code" in result.left ? result.left.code : "unexpected-result"
}

describe("finite semantic research transfer", () => {
  it("retains unless as exemption, with the sole violating assignment as witness", () => {
    const result = unwrap(reviewFiniteSemanticFrame(frame(unless)))
    expect(result.completeAssignments).toBe(8)
    expect(result.allowedBefore).toBe(7)
    expect(result.clauseDiagnostics[0]?.removalWitness).toEqual({ guard: "1", required: "0", exception: "0" })
    expect(result.source.bindings[2]?.participant?.role).toBe("exception")
    expect(result.source.stateRevision).toBe(7)
    expect(result.canonicalWrite).toBe(false)
    expect(result.utility).toBeNull()
  })
  it("classifies all pairs of two-variable truth functions against a bit-set oracle", () => {
    for (let before = 0; before < 16; before++) for (let after = 0; after < 16; after++) {
      const added = after & ~before, removed = before & ~after
      const result = unwrap(reviewFiniteSemanticFrame(frame(truthTable(before)), { proposedSemanticText: JSON.stringify(truthTable(after)) }))
      expect(result.revision?.classification).toBe(added ? removed ? "INCOMPARABLE" : "WEAKENED" : removed ? "STRENGTHENED" : "EQUIVALENT")
      expect(result.revision?.addedCount).toBe(added.toString(2).replaceAll("0", "").length)
      expect(result.revision?.removedCount).toBe(removed.toString(2).replaceAll("0", "").length)
    }
  })
  it("detects a removed exception reference as well as meaning change", () => {
    const proposed: FiniteProgram = { ...unless, expressions: [{ op: "is", variable: "guard", value: "1" }, { op: "not", arg: 0 }, { op: "is", variable: "required", value: "1" }, { op: "or", left: 1, right: 2 }] }
    const result = unwrap(reviewFiniteSemanticFrame(frame(unless), { proposedSemanticText: JSON.stringify(proposed) }))
    expect(result.revision?.classification).toBe("STRENGTHENED")
    expect(result.revision?.removedWitness).toEqual({ guard: "1", required: "0", exception: "1" })
    expect(result.revision?.lostExceptionReferences).toEqual(["exception"])
  })
  it("finds clause redundancy without granting deletion, and preserves inconsistent-base status", () => {
    const duplicate = { ...unless, clauses: [...unless.clauses, { id: "duplicate", expression: 3 }] }
    const result = unwrap(reviewFiniteSemanticFrame(frame(duplicate)))
    expect(result.clauseDiagnostics.map(c => c.status)).toEqual(["REDUNDANT_WITHIN_DECLARED_DOMAIN", "REDUNDANT_WITHIN_DECLARED_DOMAIN"])
    const inconsistent = unwrap(reviewFiniteSemanticFrame(frame(truthTable(0)), { factorBags: [["guard"], ["required"]] }))
    expect(inconsistent.allowedBefore).toBe(0)
    expect(inconsistent.clauseDiagnostics[0]?.status).toBe("INCONSISTENT_BASE_REVIEW_REQUIRED")
    expect(inconsistent.factorization?.status).toBe("INCONSISTENT_BASE_REVIEW_REQUIRED")
  })
  it("exposes three-way parity lost by pairwise factorization, with a concrete spurious witness", () => {
    const parity = truthTable(0b10010110, 3)
    const result = unwrap(reviewFiniteSemanticFrame(frame(parity), { factorBags: [["guard", "required"], ["required", "exception"], ["guard", "exception"]] }))
    expect(result.allowedBefore).toBe(4)
    expect(result.factorization).toMatchObject({ status: "LOSSY_ADDS_INTERPRETATIONS", joinedRows: 8, spuriousCount: 4, spuriousWitness: { guard: "0", required: "0", exception: "0" }, changesApplied: false })
  })
  it("recognizes independent lossless factors and refuses incomplete/duplicate/unknown scopes", () => {
    const source = frame(truthTable(0b1100))
    expect(unwrap(reviewFiniteSemanticFrame(source, { factorBags: [["guard"], ["required"]] })).factorization?.status).toBe("LOSSLESS_WITHIN_DECLARED_DOMAIN")
    for (const factorBags of [[["guard"]], [["guard", "required"], ["required", "guard"]], [["guard", "required", "absent"]]]) expect(errorCode(reviewFiniteSemanticFrame(source, { factorBags }))).toBe("FACTOR_SCOPE")
  })
  it("refuses role/domain realignment even if the new rule looks equivalent", () => {
    for (const changed of [variables.map(v => ({ ...v, values: [...v.values].reverse() })), variables.map(v => ({ ...v, roleOrdinal: v.roleOrdinal + 1 }))]) {
      expect(errorCode(reviewFiniteSemanticFrame(frame(unless), { proposedSemanticText: JSON.stringify({ ...unless, variables: changed }) }))).toBe("ALIGNMENT_CHANGED")
    }
    expect(errorCode(reviewFiniteSemanticFrame(frame({ ...unless, variables: variables.map(v => ({ ...v, roleOrdinal: 12 + v.roleOrdinal })) })))).toBe("ROLE_MISSING")
  })
  it("refuses free prose, unknown/null observations, cycles, hidden dead nodes and ambiguous JSON", () => {
    for (const p of ["allow if safe", { ...unless, unexpected: true }, { ...unless, variables: variables.map(v => ({ ...v, values: [null] })) }, { ...unless, expressions: [{ op: "not", arg: 0 }] }, { ...unless, expressions: [...unless.expressions, { op: "is", variable: "guard", value: "0" }] }, JSON.stringify(unless).replace('"contract":', '"contract":"duplicate","contract":'), JSON.stringify(unless) + " tail"]) expect(Either.isLeft(reviewFiniteSemanticFrame(frame(p)))).toBe(true)
    const unknown = { ...unless, expressions: [{ op: "is", variable: "guard", value: "unknown" }], clauses: [{ id: "rule", expression: 0 }] }
    expect(errorCode(reviewFiniteSemanticFrame(frame(unknown)))).toBe("DOMAIN_MISMATCH")
  })
  it("refuses products beyond 4096 rather than sampling the meaning space", () => {
    const large = { ...unless, variables: Array.from({ length: 13 }, (_, i) => ({ id: i === 0 ? "guard" : `v${i}`, roleOrdinal: i, values: ["0", "1"] })) }
    expect(errorCode(reviewFiniteSemanticFrame(frame(large)))).toBe("ASSIGNMENT_LIMIT")
  })
  it("accepts all exact native representations and rejects a modified commitment", () => {
    for (const kind of ["incidence", "role_table", "direct_json"] as const) {
      const encoded = unwrap(encodeSemanticFrameRepresentation(frame(unless), kind))
      const request = { contract: "hswm-finite-semantic-review/v1", representation: { kind, payload: encoded.payload } }
      expect(unwrap(reviewFiniteSemanticRequest(request)).allowedBefore).toBe(7)
      const source = JSON.stringify(request).replace("finite meaning review", "different review")
      expect(errorCode(reviewFiniteSemanticRequest(JSON.parse(source)))).toBe("COMMITMENT_MISMATCH")
    }
  })
  it("executes the actual standalone CLI and keeps refusal distinct from a completed negative diagnostic", () => {
    const encoded = unwrap(encodeSemanticFrameRepresentation(frame(unless), "incidence"))
    const launcher = fileURLToPath(new URL("../../src/hswm/effect-runtime/bin/hswm-semantic-finite", import.meta.url))
    const good = spawnSync(launcher, { input: JSON.stringify({ contract: "hswm-finite-semantic-review/v1", representation: { kind: encoded.kind, payload: encoded.payload }, factorBags: [["guard"], ["required"], ["exception"]] }), encoding: "utf8", timeout: 15000 })
    expect(good.status, good.stderr).toBe(0)
    expect(JSON.parse(good.stdout)).toMatchObject({ allowedBefore: 7, factorization: { status: "LOSSY_ADDS_INTERPRETATIONS" }, canonicalWrite: false })
    const bad = spawnSync(launcher, { input: "{}", encoding: "utf8", timeout: 15000 })
    expect(bad.status).toBe(2)
    expect(bad.stdout).toBe("")
  })
  it("reads an admitted file-backed relation via hswm-context, without changing the store", async () => {
    await Effect.runPromise(withContextFixture((runtime, root) => Effect.gen(function* () {
      const before = yield* runtime.snapshot
      const plan = yield* prepareSemanticContext(runtime, spec)
      const direct = yield* reviewPlannedFiniteSemantics(runtime, plan, "relation:door")
      expect(direct.allowedBefore).toBe(7)
      expect(direct.source.relationKey.atomUid).toBe("relation:door")
      const cli = yield* semanticContextProcess({ contract: "hswm-semantic-context-cli/v1", action: "finite-review", durableRoot: root, journalLineageId: "context-journal", schema, spec, expectedPlanSha256: plan.planSha256, finiteReview: { relationUid: "relation:door", factorBags: [["guard", "required", "exception"]] } })
      expect(cli).toMatchObject({ planSha256: plan.planSha256, sourceAuthority: "ADMITTED_STORE_READ_AT_PINNED_PLAN", factorization: { status: "LOSSLESS_WITHIN_DECLARED_DOMAIN" } })
      const outside = yield* Effect.either(reviewPlannedFiniteSemantics(runtime, plan, "relation:unbound"))
      expect(errorCode(outside)).toBe("REVIEW_OUTSIDE_PLAN")
      const stale = yield* Effect.either(reviewPlannedFiniteSemantics(runtime, { ...plan, planSha256: "0".repeat(64) }, "relation:door"))
      expect(errorCode(stale)).toBe("PLAN_STALE")
      const short = yield* prepareSemanticContext(runtime, { ...spec, maximumContextBytes: 1 })
      expect(errorCode(yield* Effect.either(reviewPlannedFiniteSemantics(runtime, short, "relation:door")))).toBe("CONTEXT_BUDGET_EXCEEDED")
      expect(yield* runtime.snapshot).toEqual(before)
    }), { door: JSON.stringify(unless) }).pipe(Effect.provide(NodePosixServicesLive)))
  })
})
