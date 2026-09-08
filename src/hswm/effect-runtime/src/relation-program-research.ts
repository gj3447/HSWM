/**
 * A deliberately small, pure instrument for qualifying relational-program
 * synthesis. It does not admit relations, assign causal credit, or establish
 * G0/G1 efficacy. Native graph identifiers remain data throughout.
 */
import { Data, Either } from "effect"

export interface RelationParticipant {
  readonly role: string
  readonly uid: string
}

export interface NativeRelation {
  readonly uid: string
  readonly meaning: string
  readonly participants: ReadonlyArray<RelationParticipant>
}

export interface RelationGraph {
  readonly relations: ReadonlyArray<NativeRelation>
}

/** Public resource bounds for this qualification instrument. */
export const MAX_GRAPH_RELATIONS = 256 as const
export const MAX_PARTICIPANTS_PER_RELATION = 16 as const
export const MAX_EXECUTION_BUDGET = 4096 as const

export interface HopPrimitive {
  readonly meaning: string
  readonly fromRole: string
  readonly toRole: string
}

export type ProgramAST =
  | { readonly tag: "Here" }
  | {
      readonly tag: "Traverse"
      readonly input: ProgramAST
      readonly meaning: string
      readonly fromRole: string
      readonly toRole: string
    }
  | {
      readonly tag: "Union" | "Intersect" | "Difference"
      readonly left: ProgramAST
      readonly right: ProgramAST
    }

export interface ProgramLimits {
  readonly maxDepth?: number
  readonly maxNodes?: number
  readonly maxCandidates?: number
}

export interface ProgramCounters {
  readonly programExecutions: number
  readonly nodeSteps: number
}

export interface ProgramEvaluation {
  readonly uids: ReadonlyArray<string>
  readonly counters: ProgramCounters
}

export interface TrainingExample {
  readonly graph: RelationGraph
  readonly focus: string
  /** Supplied external labels; the instrument never derives them. */
  readonly expected: ReadonlyArray<string>
}

export interface CandidateEnumeration {
  readonly status: "DECLARED_BOUNDED_SUBSET"
  readonly candidates: ReadonlyArray<ProgramAST>
  readonly limits: Required<ProgramLimits>
  readonly grammar: "HERE_AND_DECLARED_HOPS_WITH_BINARY_SET_OPS"
}

export interface ProgramFit {
  readonly status: "UNIQUE_BEST" | "AMBIGUOUS_BEST"
  readonly best: ReadonlyArray<ProgramAST>
  readonly minimumErrors: number
  readonly complexity: number
  readonly candidatesEvaluated: number
  readonly counters: ProgramCounters
  readonly claim: "INSTRUMENT_QUALIFICATION_ONLY"
}

export class RelationProgramError extends Data.TaggedError("RelationProgramError")<{
  readonly code:
    | "GRAPH_INVALID"
    | "PROGRAM_INVALID"
    | "PRIMITIVE_INVALID"
    | "LIMIT_INVALID"
    | "CANDIDATE_LIMIT"
    | "EXECUTION_BUDGET"
    | "EXAMPLE_INVALID"
  readonly detail: string
}> {}

const fail = <A = never>(
  code: RelationProgramError["code"],
  detail: string
): Either.Either<A, RelationProgramError> =>
  Either.left(new RelationProgramError({ code, detail }))

const releft = <A>(error: RelationProgramError): Either.Either<A, RelationProgramError> =>
  Either.left(error)

const text = (value: unknown): value is string =>
  typeof value === "string" && value.length > 0 && value.length <= 256

const defaults = (limits: ProgramLimits = {}): Either.Either<Required<ProgramLimits>, RelationProgramError> => {
  const resolved = {
    maxDepth: limits.maxDepth ?? 3,
    maxNodes: limits.maxNodes ?? 7,
    maxCandidates: limits.maxCandidates ?? 2048
  }
  return Number.isSafeInteger(resolved.maxDepth) && resolved.maxDepth >= 0 && resolved.maxDepth <= 3 &&
    Number.isSafeInteger(resolved.maxNodes) && resolved.maxNodes >= 1 && resolved.maxNodes <= 7 &&
    Number.isSafeInteger(resolved.maxCandidates) && resolved.maxCandidates >= 1 && resolved.maxCandidates <= 2048
    ? Either.right(Object.freeze(resolved))
    : fail("LIMIT_INVALID", "depth <= 3, nodes <= 7, candidates <= 2048")
}

const astKey = (program: ProgramAST): string => {
  switch (program.tag) {
    case "Here": return "H"
    case "Traverse": return `T(${astKey(program.input)}|${JSON.stringify(program.meaning)}|${JSON.stringify(program.fromRole)}|${JSON.stringify(program.toRole)})`
    case "Union": return `U(${astKey(program.left)},${astKey(program.right)})`
    case "Intersect": return `I(${astKey(program.left)},${astKey(program.right)})`
    case "Difference": return `D(${astKey(program.left)},${astKey(program.right)})`
  }
}

export const programComplexity = (program: ProgramAST): number =>
  program.tag === "Here" ? 1 : program.tag === "Traverse"
    ? 1 + programComplexity(program.input)
    : 1 + programComplexity(program.left) + programComplexity(program.right)

export const programDepth = (program: ProgramAST): number =>
  program.tag === "Here" ? 0 : program.tag === "Traverse"
    ? 1 + programDepth(program.input)
    : 1 + Math.max(programDepth(program.left), programDepth(program.right))

const validPrimitive = (primitive: HopPrimitive): boolean =>
  text(primitive.meaning) && text(primitive.fromRole) && text(primitive.toRole)

const validGraph = (graph: unknown): graph is RelationGraph => {
  if (typeof graph !== "object" || graph === null || Array.isArray(graph)) return false
  const relations = (graph as Record<string, unknown>)["relations"]
  if (!Array.isArray(relations) || relations.length > MAX_GRAPH_RELATIONS) return false
  const relationUids = new Set<string>()
  for (const relation of relations) {
    if (typeof relation !== "object" || relation === null || Array.isArray(relation)) return false
    const item = relation as Record<string, unknown>
    if (!text(item["uid"]) || !text(item["meaning"]) || !Array.isArray(item["participants"]) ||
      item["participants"].length > MAX_PARTICIPANTS_PER_RELATION || relationUids.has(item["uid"])) return false
    relationUids.add(item["uid"])
    const roles = new Set<string>()
    for (const participant of item["participants"]) {
      if (typeof participant !== "object" || participant === null || Array.isArray(participant)) return false
      const value = participant as Record<string, unknown>
      if (!text(value["role"]) || !text(value["uid"]) || roles.has(value["role"])) return false
      roles.add(value["role"])
    }
  }
  return true
}

/** Validates the public DSL; UID literals are intentionally absent from it. */
export const validateProgram = (
  program: ProgramAST,
  limits: ProgramLimits = {}
): Either.Either<ProgramAST, RelationProgramError> => {
  const resolved = defaults(limits)
  if (Either.isLeft(resolved)) return releft(resolved.left)
  type Visit = { readonly phase: "enter" | "exit"; readonly node: unknown; readonly depth: number }
  const active = new WeakSet<object>()
  const work: Visit[] = [{ phase: "enter", node: program, depth: 0 }]
  let nodes = 0
  while (work.length > 0) {
    const visit = work.pop()!
    if (visit.phase === "exit") {
      active.delete(visit.node as object)
      continue
    }
    if (typeof visit.node !== "object" || visit.node === null || Array.isArray(visit.node) || visit.depth > resolved.right.maxDepth) {
      return fail("PROGRAM_INVALID", "program is outside the declared AST grammar or bounds")
    }
    if (active.has(visit.node)) return fail("PROGRAM_INVALID", "cyclic AST is not a program")
    nodes += 1
    if (nodes > resolved.right.maxNodes) return fail("PROGRAM_INVALID", "program exceeds node bound")
    const item = visit.node as Record<string, unknown>
    active.add(visit.node)
    work.push({ phase: "exit", node: visit.node, depth: visit.depth })
    if (item["tag"] === "Here" && Object.keys(item).length === 1) continue
    if (item["tag"] === "Traverse" && Object.keys(item).length === 5 && text(item["meaning"]) && text(item["fromRole"]) && text(item["toRole"])) {
      work.push({ phase: "enter", node: item["input"], depth: visit.depth + 1 })
      continue
    }
    if ((item["tag"] === "Union" || item["tag"] === "Intersect" || item["tag"] === "Difference") && Object.keys(item).length === 3) {
      work.push({ phase: "enter", node: item["right"], depth: visit.depth + 1 })
      work.push({ phase: "enter", node: item["left"], depth: visit.depth + 1 })
      continue
    }
    return fail("PROGRAM_INVALID", "program is outside the declared AST grammar or bounds")
  }
  return Either.right(program)
}

const mergeCounters = (left: ProgramCounters, right: ProgramCounters): ProgramCounters => Object.freeze({
  programExecutions: left.programExecutions + right.programExecutions,
  nodeSteps: left.nodeSteps + right.nodeSteps
})

const uniqueSorted = (uids: Iterable<string>): ReadonlyArray<string> => Object.freeze([...new Set(uids)].sort())

/** Executes only declared meanings and roles over caller-supplied native IDs. */
export const evaluateProgram = (
  graph: RelationGraph,
  focus: string,
  program: ProgramAST,
  executionBudget: number = MAX_EXECUTION_BUDGET
): Either.Either<ProgramEvaluation, RelationProgramError> => {
  if (!validGraph(graph) || !text(focus)) return fail("GRAPH_INVALID", "graph or focus is invalid")
  if (!Number.isSafeInteger(executionBudget) || executionBudget < 1 || executionBudget > MAX_EXECUTION_BUDGET) return fail("EXECUTION_BUDGET", "budget is outside the public execution bound")
  const checked = validateProgram(program)
  if (Either.isLeft(checked)) return releft(checked.left)
  let steps = 0
  const spend = (amount = 1): Either.Either<void, RelationProgramError> => {
    steps += amount
    return steps <= executionBudget ? Either.right(undefined) : fail("EXECUTION_BUDGET", "program exceeded node-step budget")
  }
  const visit = (node: ProgramAST): Either.Either<ReadonlyArray<string>, RelationProgramError> => {
    const step = spend()
    if (Either.isLeft(step)) return releft(step.left)
    if (node.tag === "Here") return Either.right([focus])
    if (node.tag === "Traverse") {
      const input = visit(node.input)
      if (Either.isLeft(input)) return releft(input.left)
      const from = new Set(input.right)
      const output: string[] = []
      for (const relation of graph.relations) {
        const scanned = spend()
        if (Either.isLeft(scanned)) return releft(scanned.left)
        if (relation.meaning !== node.meaning) continue
        if (!relation.participants.some((participant) => participant.role === node.fromRole && from.has(participant.uid))) continue
        for (const participant of relation.participants) if (participant.role === node.toRole) output.push(participant.uid)
      }
      return Either.right(uniqueSorted(output))
    }
    const left = visit(node.left)
    if (Either.isLeft(left)) return releft(left.left)
    const right = visit(node.right)
    if (Either.isLeft(right)) return releft(right.left)
    const l = new Set(left.right)
    const r = new Set(right.right)
    const values = node.tag === "Union" ? [...l, ...r] : node.tag === "Intersect"
      ? [...l].filter((uid) => r.has(uid))
      : [...l].filter((uid) => !r.has(uid))
    return Either.right(uniqueSorted(values))
  }
  const result = visit(checked.right)
  return Either.isLeft(result) ? releft(result.left) : Either.right(Object.freeze({
    uids: result.right,
    counters: Object.freeze({ programExecutions: 1, nodeSteps: steps })
  }))
}

const addCandidate = (
  target: Map<string, ProgramAST>,
  candidate: ProgramAST,
  limits: Required<ProgramLimits>
): Either.Either<void, RelationProgramError> => {
  if (programDepth(candidate) > limits.maxDepth || programComplexity(candidate) > limits.maxNodes) return Either.right(undefined)
  const key = astKey(candidate)
  if (target.has(key)) return Either.right(undefined)
  if (target.size >= limits.maxCandidates) return fail("CANDIDATE_LIMIT", "declared candidate limit reached; enumeration is incomplete")
  target.set(key, Object.freeze(candidate))
  return Either.right(undefined)
}

/**
 * Enumerates only the declared finite subset: Here, hop chains, then binary
 * set operations over already declared terms. A limit failure is explicit;
 * callers must not interpret a partial search as grammar completeness.
 */
export const enumerateCandidates = (
  primitives: ReadonlyArray<HopPrimitive>,
  limits: ProgramLimits = {}
): Either.Either<CandidateEnumeration, RelationProgramError> => {
  const resolved = defaults(limits)
  if (Either.isLeft(resolved)) return releft(resolved.left)
  if (!Array.isArray(primitives) || primitives.some((primitive) => !validPrimitive(primitive))) return fail("PRIMITIVE_INVALID", "hop primitives need meaning and exact roles")
  const primitiveSet = [...new Map(primitives.map((primitive) => [`${primitive.meaning}\u0000${primitive.fromRole}\u0000${primitive.toRole}`, primitive] as const)).values()]
    .sort((left, right) => `${left.meaning}\u0000${left.fromRole}\u0000${left.toRole}`.localeCompare(`${right.meaning}\u0000${right.fromRole}\u0000${right.toRole}`))
  const candidates = new Map<string, ProgramAST>()
  const here: ProgramAST = Object.freeze({ tag: "Here" })
  const initial = addCandidate(candidates, here, resolved.right)
  if (Either.isLeft(initial)) return releft(initial.left)
  let frontier: ReadonlyArray<ProgramAST> = [here]
  for (let depth = 1; depth <= resolved.right.maxDepth; depth += 1) {
    const next: ProgramAST[] = []
    for (const input of frontier) for (const primitive of primitiveSet) {
      const candidate: ProgramAST = Object.freeze({ tag: "Traverse", input, ...primitive })
      const added = addCandidate(candidates, candidate, resolved.right)
      if (Either.isLeft(added)) return releft(added.left)
      if (candidates.get(astKey(candidate)) === candidate) next.push(candidate)
    }
    frontier = next
  }
  // Closure is deliberately limited to combinations of the finite unary pool.
  const unary = [...candidates.values()]
  for (const left of unary) for (const right of unary) {
    const ordered = astKey(left).localeCompare(astKey(right)) <= 0 ? [left, right] as const : [right, left] as const
    for (const tag of ["Union", "Intersect", "Difference"] as const) {
      const [first, second] = tag === "Difference" ? [left, right] as const : ordered
      const candidate: ProgramAST = Object.freeze({ tag, left: first, right: second })
      const added = addCandidate(candidates, candidate, resolved.right)
      if (Either.isLeft(added)) return releft(added.left)
    }
  }
  return Either.right(Object.freeze({
    status: "DECLARED_BOUNDED_SUBSET",
    candidates: Object.freeze([...candidates.values()].sort((left, right) => astKey(left).localeCompare(astKey(right)))),
    limits: resolved.right,
    grammar: "HERE_AND_DECLARED_HOPS_WITH_BINARY_SET_OPS"
  }))
}

const expectedSet = (expected: ReadonlyArray<string>): Either.Either<ReadonlyArray<string>, RelationProgramError> =>
  Array.isArray(expected) && expected.every(text) ? Either.right(uniqueSorted(expected)) : fail("EXAMPLE_INVALID", "expected labels must be native IDs")

/** Fits supplied labels only; it never inspects an unprovided holdout. */
export const fitProgram = (
  candidates: ReadonlyArray<ProgramAST>,
  examples: ReadonlyArray<TrainingExample>,
  executionBudget: number = MAX_EXECUTION_BUDGET
): Either.Either<ProgramFit, RelationProgramError> => {
  if (!Array.isArray(candidates) || candidates.length === 0 || candidates.length > 2048 || !Array.isArray(examples) || examples.length === 0) return fail("EXAMPLE_INVALID", "bounded candidates and at least one training example are required")
  let total = Object.freeze({ programExecutions: 0, nodeSteps: 0 }) as ProgramCounters
  const scored: Array<{ readonly program: ProgramAST; readonly errors: number; readonly complexity: number }> = []
  for (const program of candidates) {
    const valid = validateProgram(program)
    if (Either.isLeft(valid)) return releft(valid.left)
    let errors = 0
    for (const example of examples) {
      const expected = expectedSet(example.expected)
      if (Either.isLeft(expected)) return releft(expected.left)
      const evaluated = evaluateProgram(example.graph, example.focus, program, executionBudget)
      if (Either.isLeft(evaluated)) return releft(evaluated.left)
      total = mergeCounters(total, evaluated.right.counters)
      const actual = new Set(evaluated.right.uids)
      const target = new Set(expected.right)
      errors += [...actual].filter((uid) => !target.has(uid)).length + [...target].filter((uid) => !actual.has(uid)).length
    }
    scored.push({ program, errors, complexity: programComplexity(program) })
  }
  const minimumErrors = Math.min(...scored.map((item) => item.errors))
  const minimumComplexity = Math.min(...scored.filter((item) => item.errors === minimumErrors).map((item) => item.complexity))
  const best = scored.filter((item) => item.errors === minimumErrors && item.complexity === minimumComplexity)
    .map((item) => item.program).sort((left, right) => astKey(left).localeCompare(astKey(right)))
  return Either.right(Object.freeze({
    status: best.length === 1 ? "UNIQUE_BEST" : "AMBIGUOUS_BEST",
    best: Object.freeze(best),
    minimumErrors,
    complexity: minimumComplexity,
    candidatesEvaluated: candidates.length,
    counters: total,
    claim: "INSTRUMENT_QUALIFICATION_ONLY"
  }))
}
