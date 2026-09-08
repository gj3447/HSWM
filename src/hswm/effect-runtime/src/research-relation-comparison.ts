/**
 * Authored local calibration helpers for a future, matched LLM comparison.
 *
 * This module neither calls a model nor derives an outcome.  It serializes
 * caller-supplied graphs, builds prompt inputs, and independently interprets a
 * deliberately tiny JSON program grammar.  It is not an HSWM revision,
 * baseline replication, G0/G1 evidence, or a canonical-write path.
 */
import { Data, Either } from "effect"

import type { RelationGraph } from "./relation-program-research.js"

export const CALIBRATION_MAX_GRAPH_RELATIONS = 256 as const
export const CALIBRATION_MAX_PARTICIPANTS = 16 as const
export const CALIBRATION_MAX_DEPTH = 3 as const
export const CALIBRATION_MAX_NODES = 7 as const
export const CALIBRATION_MAX_STEPS = 4096 as const
export const CALIBRATION_MAX_LESSON_UTF8_BYTES = 8192 as const

export interface CalibrationPrimitive {
  readonly meaning: string
  readonly fromRole: string
  readonly toRole: string
}

/** The fixed, public relation schema for this authored catalog calibration. */
export const CALIBRATION_PUBLIC_PRIMITIVES: ReadonlyArray<CalibrationPrimitive> = Object.freeze([
  Object.freeze({ meaning: "Declared KG relation: INVALIDATES", fromRole: "change", toRole: "artifact" }),
  Object.freeze({ meaning: "Declared KG relation: REQUIRES", fromRole: "artifact", toRole: "requirement" }),
  Object.freeze({ meaning: "Declared KG relation: CHECKS", fromRole: "requirement", toRole: "check" })
])

export type CalibrationProgram =
  | { readonly tag: "Here" }
  | { readonly tag: "Traverse"; readonly input: CalibrationProgram; readonly meaning: string; readonly fromRole: string; readonly toRole: string }
  | { readonly tag: "Union" | "Intersect" | "Difference"; readonly left: CalibrationProgram; readonly right: CalibrationProgram }

export interface CalibrationTrainingExample {
  readonly id: string
  readonly focus: string
  readonly graph: RelationGraph
  /** Training-only owner labels. They are never accepted on a target input. */
  readonly expectedUids: ReadonlyArray<string>
}

export interface CalibrationTarget {
  readonly id: string
  readonly focus: string
  readonly graph: RelationGraph
}

export interface CalibrationPrompt {
  readonly scope: "AUTHORED_LOCAL_CALIBRATION_ONLY"
  readonly arm: "OPEN_BOOK_HISTORY" | "TEXT_LESSON_CONSOLIDATION" | "TEXT_LESSON_INFERENCE" | "EXECUTABLE_PROGRAM_CONSOLIDATION" | "EXECUTABLE_PROGRAM_INFERENCE"
  readonly text: string
  readonly containsTargetLabels: false
}

export interface IndependentProgramResult {
  readonly uids: ReadonlyArray<string>
  readonly nodeSteps: number
  readonly interpreter: "INDEPENDENT_CALIBRATION_INTERPRETER_V1"
}

/** The two permitted, explicitly discriminated inference outputs. */
export type CalibrationInferenceResponse =
  | { readonly uids: ReadonlyArray<string> }
  | { readonly program: CalibrationProgram }

export class RelationComparisonError extends Data.TaggedError("RelationComparisonError")<{
  readonly code: "GRAPH_INVALID" | "PROGRAM_INVALID" | "EXECUTION_BUDGET" | "RESPONSE_INVALID" | "PROMPT_INPUT_INVALID"
  readonly detail: string
}> {}

const fail = <A = never>(
  code: RelationComparisonError["code"],
  detail: string
): Either.Either<A, RelationComparisonError> => Either.left(new RelationComparisonError({ code, detail }))

const releft = <A>(error: RelationComparisonError): Either.Either<A, RelationComparisonError> => Either.left(error)

const isText = (value: unknown): value is string => typeof value === "string" && value.length > 0 && value.length <= 256

const isLesson = (value: unknown): value is string =>
  typeof value === "string" && Buffer.byteLength(value, "utf8") > 0 && Buffer.byteLength(value, "utf8") <= CALIBRATION_MAX_LESSON_UTF8_BYTES

const stable = (value: unknown): string => JSON.stringify(value)

const graphIsValid = (graph: unknown): graph is RelationGraph => {
  if (typeof graph !== "object" || graph === null || Array.isArray(graph)) return false
  const relations = (graph as Record<string, unknown>)["relations"]
  if (!Array.isArray(relations) || relations.length > CALIBRATION_MAX_GRAPH_RELATIONS) return false
  const relationUids = new Set<string>()
  for (const relation of relations) {
    if (typeof relation !== "object" || relation === null || Array.isArray(relation)) return false
    const row = relation as Record<string, unknown>
    if (!isText(row["uid"]) || !isText(row["meaning"]) || !Array.isArray(row["participants"]) ||
      row["participants"].length > CALIBRATION_MAX_PARTICIPANTS || relationUids.has(row["uid"])) return false
    relationUids.add(row["uid"])
    const roles = new Set<string>()
    for (const participant of row["participants"]) {
      if (typeof participant !== "object" || participant === null || Array.isArray(participant)) return false
      const item = participant as Record<string, unknown>
      if (!isText(item["role"]) || !isText(item["uid"]) || roles.has(item["role"])) return false
      roles.add(item["role"])
    }
  }
  return true
}

/** Lossless for the public graph shape: relation UID, meaning and ordered roles remain explicit. */
export const serializeCalibrationGraph = (graph: RelationGraph): Either.Either<string, RelationComparisonError> => {
  if (!graphIsValid(graph)) return fail("GRAPH_INVALID", "relation graph is invalid or exceeds calibration bounds")
  return Either.right(stable({
    relations: graph.relations.map((relation) => ({
      uid: relation.uid,
      meaning: relation.meaning,
      participants: relation.participants.map((participant) => ({ role: participant.role, uid: participant.uid }))
    }))
  }))
}

const targetBlock = (target: CalibrationTarget): Either.Either<string, RelationComparisonError> => {
  if (!isText(target.id) || !isText(target.focus)) return fail("PROMPT_INPUT_INVALID", "target id or focus is invalid")
  const graph = serializeCalibrationGraph(target.graph)
  return Either.isLeft(graph) ? releft(graph.left) : Either.right(stable({ id: target.id, focus: target.focus, graph: JSON.parse(graph.right) }))
}

const trainingBlock = (training: ReadonlyArray<CalibrationTrainingExample>): Either.Either<string, RelationComparisonError> => {
  if (training.length === 0 || training.length > 64) return fail("PROMPT_INPUT_INVALID", "training must contain 1 through 64 examples")
  const rows: Array<Record<string, unknown>> = []
  for (const example of training) {
    if (!isText(example.id) || !isText(example.focus) || !Array.isArray(example.expectedUids) ||
      example.expectedUids.some((uid) => !isText(uid)) || new Set(example.expectedUids).size !== example.expectedUids.length) {
      return fail("PROMPT_INPUT_INVALID", "training example contains invalid fields or duplicate label UIDs")
    }
    const graph = serializeCalibrationGraph(example.graph)
    if (Either.isLeft(graph)) return releft(graph.left)
    rows.push({ id: example.id, focus: example.focus, graph: JSON.parse(graph.right), expectedUids: [...example.expectedUids].sort() })
  }
  return Either.right(stable(rows))
}

const primitivesBlock = (primitives: ReadonlyArray<CalibrationPrimitive>): Either.Either<string, RelationComparisonError> => {
  if (primitives.length === 0 || primitives.length > 32 || primitives.some((item) => !isText(item.meaning) || !isText(item.fromRole) || !isText(item.toRole))) {
    return fail("PROMPT_INPUT_INVALID", "primitive schema is invalid")
  }
  return Either.right(stable(primitives.map((item) => ({ meaning: item.meaning, fromRole: item.fromRole, toRole: item.toRole }))))
}

const samePrimitiveSchema = (left: ReadonlyArray<CalibrationPrimitive>, right: ReadonlyArray<CalibrationPrimitive>): boolean =>
  stable(left) === stable(right)

/** Derives only the fixed public three-hop schema from labelled training graphs. */
export const deriveCalibrationPrimitives = (
  training: ReadonlyArray<CalibrationTrainingExample>
): Either.Either<ReadonlyArray<CalibrationPrimitive>, RelationComparisonError> => {
  const checked = trainingBlock(training)
  if (Either.isLeft(checked)) return releft(checked.left)
  for (const example of training) {
    for (const primitive of CALIBRATION_PUBLIC_PRIMITIVES) {
      const present = example.graph.relations.some((relation) => relation.meaning === primitive.meaning &&
        relation.participants.some((participant) => participant.role === primitive.fromRole) &&
        relation.participants.some((participant) => participant.role === primitive.toRole))
      if (!present) return fail("PROMPT_INPUT_INVALID", "training graph does not expose the fixed public primitive schema")
    }
  }
  return Either.right(CALIBRATION_PUBLIC_PRIMITIVES)
}

const grammar = (primitives: ReadonlyArray<CalibrationPrimitive>): Either.Either<string, RelationComparisonError> => {
  const rendered = primitivesBlock(primitives)
  if (Either.isLeft(rendered)) return releft(rendered.left)
  return Either.right(`GRAMMAR: Here returns the target focus UID. Traverse first evaluates input, then follows relations with exact meaning and exact named fromRole/toRole. Union, Intersect, Difference operate on UID sets. AST maximum depth=${CALIBRATION_MAX_DEPTH}, nodes=${CALIBRATION_MAX_NODES}, execution steps=${CALIBRATION_MAX_STEPS}. No UID literals are permitted in an AST. PUBLIC_PRIMITIVES=${rendered.right}`)
}

const prompt = (arm: CalibrationPrompt["arm"], body: string): CalibrationPrompt => Object.freeze({
  scope: "AUTHORED_LOCAL_CALIBRATION_ONLY",
  arm,
  text: body,
  containsTargetLabels: false
})

export const buildOpenBookPrompt = (
  training: ReadonlyArray<CalibrationTrainingExample>,
  target: CalibrationTarget
): Either.Either<CalibrationPrompt, RelationComparisonError> => {
  const train = trainingBlock(training)
  if (Either.isLeft(train)) return releft(train.left)
  const primitives = deriveCalibrationPrimitives(training)
  if (Either.isLeft(primitives)) return releft(primitives.left)
  const sharedGrammar = grammar(primitives.right)
  if (Either.isLeft(sharedGrammar)) return releft(sharedGrammar.left)
  const test = targetBlock(target)
  if (Either.isLeft(test)) return releft(test.left)
  return Either.right(prompt("OPEN_BOOK_HISTORY", `AUTHORED LOCAL CALIBRATION ONLY. Infer target UIDs from the labelled training records. Return exactly one JSON object: {"uids":["..."]} OR {"program":AST}. Do not explain.\n${sharedGrammar.right}\nTRAINING=${train.right}\nTARGET_WITHOUT_LABELS=${test.right}`))
}

export const buildTextLessonConsolidationPrompt = (
  training: ReadonlyArray<CalibrationTrainingExample>
): Either.Either<CalibrationPrompt, RelationComparisonError> => {
  const train = trainingBlock(training)
  if (Either.isLeft(train)) return releft(train.left)
  const primitives = deriveCalibrationPrimitives(training)
  if (Either.isLeft(primitives)) return releft(primitives.left)
  const sharedGrammar = grammar(primitives.right)
  return Either.isLeft(sharedGrammar) ? releft(sharedGrammar.left) : Either.right(prompt("TEXT_LESSON_CONSOLIDATION", `AUTHORED LOCAL CALIBRATION ONLY. Consolidate the labelled training records into one reusable textual lesson of at most ${CALIBRATION_MAX_LESSON_UTF8_BYTES} UTF-8 bytes. Return exactly JSON {"lesson":"..."}.\n${sharedGrammar.right}\nTRAINING=${train.right}`))
}

export const buildTextLessonInferencePrompt = (
  lesson: string,
  target: CalibrationTarget,
  primitives: ReadonlyArray<CalibrationPrimitive> = CALIBRATION_PUBLIC_PRIMITIVES
): Either.Either<CalibrationPrompt, RelationComparisonError> => {
  if (!isLesson(lesson)) return fail("PROMPT_INPUT_INVALID", "lesson is invalid or exceeds the UTF-8 byte cap")
  const sharedGrammar = grammar(primitives)
  if (Either.isLeft(sharedGrammar)) return releft(sharedGrammar.left)
  const test = targetBlock(target)
  return Either.isLeft(test) ? releft(test.left) : Either.right(prompt("TEXT_LESSON_INFERENCE", `AUTHORED LOCAL CALIBRATION ONLY. Apply the supplied lesson to the target. Return exactly one JSON object: {"uids":["..."]} OR {"program":AST}. Do not explain.\n${sharedGrammar.right}\nLESSON=${stable(lesson)}\nTARGET_WITHOUT_LABELS=${test.right}`))
}

export const buildExecutableProgramConsolidationPrompt = (
  training: ReadonlyArray<CalibrationTrainingExample>,
  primitives: ReadonlyArray<CalibrationPrimitive> = CALIBRATION_PUBLIC_PRIMITIVES
): Either.Either<CalibrationPrompt, RelationComparisonError> => {
  const train = trainingBlock(training)
  if (Either.isLeft(train)) return releft(train.left)
  const derived = deriveCalibrationPrimitives(training)
  if (Either.isLeft(derived)) return releft(derived.left)
  if (!samePrimitiveSchema(primitives, derived.right)) return fail("PROMPT_INPUT_INVALID", "program arm primitive schema differs from training-derived public schema")
  const sharedGrammar = grammar(derived.right)
  if (Either.isLeft(sharedGrammar)) return releft(sharedGrammar.left)
  return Either.right(prompt("EXECUTABLE_PROGRAM_CONSOLIDATION", `AUTHORED LOCAL CALIBRATION ONLY. Infer a reusable JSON AST from labelled training records. Return exactly JSON {"program":AST}.\n${sharedGrammar.right}\nTRAINING=${train.right}`))
}

/** Gives a consolidated JSON AST the same later inference surface as text/history arms. */
export const buildProgramInferencePrompt = (
  program: CalibrationProgram,
  target: CalibrationTarget,
  primitives: ReadonlyArray<CalibrationPrimitive> = CALIBRATION_PUBLIC_PRIMITIVES
): Either.Either<CalibrationPrompt, RelationComparisonError> => {
  const checked = validateProgram(program)
  if (Either.isLeft(checked)) return releft(checked.left)
  const sharedGrammar = grammar(primitives)
  if (Either.isLeft(sharedGrammar)) return releft(sharedGrammar.left)
  const test = targetBlock(target)
  return Either.isLeft(test) ? releft(test.left) : Either.right(prompt("EXECUTABLE_PROGRAM_INFERENCE", `AUTHORED LOCAL CALIBRATION ONLY. Apply the supplied bounded JSON AST to the target relation graph. Return exactly one JSON object: {"uids":["..."]} OR {"program":AST}. Do not explain.\n${sharedGrammar.right}\nPROGRAM=${stable(checked.right)}\nTARGET_WITHOUT_LABELS=${test.right}`))
}

const parseJsonEnvelope = (response: string): Either.Either<unknown, RelationComparisonError> => {
  const trimmed = response.trim()
  const fenced = /^```json\s*\n([\s\S]*?)\n```$/.exec(trimmed)
  const candidate = fenced === null ? trimmed : fenced[1]!
  if (candidate.length === 0 || (fenced === null && trimmed.includes("```"))) return fail("RESPONSE_INVALID", "response must be JSON or one json fence")
  try {
    return Either.right(JSON.parse(candidate))
  } catch {
    return fail("RESPONSE_INVALID", "response is not valid JSON")
  }
}

export const parseUidInferenceResponse = (response: string): Either.Either<ReadonlyArray<string>, RelationComparisonError> => {
  const value = parseJsonEnvelope(response)
  if (Either.isLeft(value)) return releft(value.left)
  if (typeof value.right !== "object" || value.right === null || Array.isArray(value.right)) return fail("RESPONSE_INVALID", "response must be an object")
  const object = value.right as Record<string, unknown>
  if (Object.keys(object).length !== 1 || !Array.isArray(object["uids"]) || object["uids"].some((uid) => !isText(uid))) return fail("RESPONSE_INVALID", "response must have only a string uids array")
  const uids = object["uids"] as string[]
  if (new Set(uids).size !== uids.length) return fail("RESPONSE_INVALID", "response contains duplicate UIDs")
  return Either.right(Object.freeze([...uids].sort()))
}

export const parseLessonResponse = (response: string): Either.Either<string, RelationComparisonError> => {
  const value = parseJsonEnvelope(response)
  if (Either.isLeft(value)) return releft(value.left)
  if (typeof value.right !== "object" || value.right === null || Array.isArray(value.right)) return fail("RESPONSE_INVALID", "lesson response must be an object")
  const object = value.right as Record<string, unknown>
  if (Object.keys(object).length !== 1 || !isLesson(object["lesson"])) return fail("RESPONSE_INVALID", "lesson response must have only a bounded UTF-8 lesson field")
  return Either.right(object["lesson"])
}

const isProgram = (value: unknown): value is CalibrationProgram => typeof value === "object" && value !== null && !Array.isArray(value)

const validateProgram = (program: unknown): Either.Either<CalibrationProgram, RelationComparisonError> => {
  type Visit = { readonly phase: "enter" | "exit"; readonly node: unknown; readonly depth: number }
  const work: Visit[] = [{ phase: "enter", node: program, depth: 0 }]
  const active = new WeakSet<object>()
  let nodes = 0
  while (work.length > 0) {
    const visit = work.pop()!
    if (visit.phase === "exit") { active.delete(visit.node as object); continue }
    if (!isProgram(visit.node) || visit.depth > CALIBRATION_MAX_DEPTH) return fail("PROGRAM_INVALID", "program is outside the calibration grammar or depth bound")
    if (active.has(visit.node)) return fail("PROGRAM_INVALID", "program AST is cyclic")
    nodes += 1
    if (nodes > CALIBRATION_MAX_NODES) return fail("PROGRAM_INVALID", "program exceeds node bound")
    const node = visit.node as Record<string, unknown>
    active.add(visit.node)
    work.push({ phase: "exit", node: visit.node, depth: visit.depth })
    if (node["tag"] === "Here" && Object.keys(node).length === 1) continue
    if (node["tag"] === "Traverse" && Object.keys(node).length === 5 && isText(node["meaning"]) && isText(node["fromRole"]) && isText(node["toRole"])) {
      work.push({ phase: "enter", node: node["input"], depth: visit.depth + 1 }); continue
    }
    if ((node["tag"] === "Union" || node["tag"] === "Intersect" || node["tag"] === "Difference") && Object.keys(node).length === 3) {
      work.push({ phase: "enter", node: node["right"], depth: visit.depth + 1 })
      work.push({ phase: "enter", node: node["left"], depth: visit.depth + 1 }); continue
    }
    return fail("PROGRAM_INVALID", "program is outside the calibration grammar")
  }
  return Either.right(program as CalibrationProgram)
}

export const parseProgramResponse = (response: string): Either.Either<CalibrationProgram, RelationComparisonError> => {
  const value = parseJsonEnvelope(response)
  if (Either.isLeft(value)) return releft(value.left)
  if (typeof value.right !== "object" || value.right === null || Array.isArray(value.right)) return fail("RESPONSE_INVALID", "response must be an object")
  const object = value.right as Record<string, unknown>
  if (Object.keys(object).length !== 1 || !("program" in object)) return fail("RESPONSE_INVALID", "response must have only program")
  return validateProgram(object["program"])
}

/** Parses either permitted inference output without executing model text as code. */
export const parseInferenceResponse = (response: string): Either.Either<CalibrationInferenceResponse, RelationComparisonError> => {
  const value = parseJsonEnvelope(response)
  if (Either.isLeft(value)) return releft(value.left)
  if (typeof value.right !== "object" || value.right === null || Array.isArray(value.right)) return fail("RESPONSE_INVALID", "response must be an object")
  const object = value.right as Record<string, unknown>
  if (Object.keys(object).length !== 1) return fail("RESPONSE_INVALID", "response must have exactly one discriminator")
  if ("uids" in object) {
    const parsed = parseUidInferenceResponse(response)
    return Either.isLeft(parsed) ? releft(parsed.left) : Either.right(Object.freeze({ uids: parsed.right }))
  }
  if ("program" in object) {
    const parsed = parseProgramResponse(response)
    return Either.isLeft(parsed) ? releft(parsed.left) : Either.right(Object.freeze({ program: parsed.right }))
  }
  return fail("RESPONSE_INVALID", "response discriminator must be uids or program")
}

/** A separately written interpreter; it intentionally does not call the synthesis instrument evaluator. */
export const evaluateIndependentProgram = (
  graph: RelationGraph,
  focus: string,
  program: CalibrationProgram,
  executionBudget: number = CALIBRATION_MAX_STEPS
): Either.Either<IndependentProgramResult, RelationComparisonError> => {
  if (!graphIsValid(graph) || !isText(focus)) return fail("GRAPH_INVALID", "graph or focus is invalid")
  if (!Number.isSafeInteger(executionBudget) || executionBudget < 1 || executionBudget > CALIBRATION_MAX_STEPS) return fail("EXECUTION_BUDGET", "execution budget is invalid")
  const checked = validateProgram(program)
  if (Either.isLeft(checked)) return releft(checked.left)
  let steps = 0
  const spend = (): Either.Either<void, RelationComparisonError> => {
    steps += 1
    return steps <= executionBudget ? Either.right(undefined) : fail("EXECUTION_BUDGET", "program exceeded node-step budget")
  }
  const ordered = (values: Iterable<string>): ReadonlyArray<string> => Object.freeze([...new Set(values)].sort())
  const visit = (node: CalibrationProgram): Either.Either<ReadonlyArray<string>, RelationComparisonError> => {
    const entry = spend()
    if (Either.isLeft(entry)) return releft(entry.left)
    if (node.tag === "Here") return Either.right(Object.freeze([focus]))
    if (node.tag === "Traverse") {
      const input = visit(node.input)
      if (Either.isLeft(input)) return releft(input.left)
      const source = new Set(input.right)
      const found: string[] = []
      for (const relation of graph.relations) {
        const scan = spend()
        if (Either.isLeft(scan)) return releft(scan.left)
        if (relation.meaning !== node.meaning) continue
        const from = relation.participants.find((participant) => participant.role === node.fromRole)
        const to = relation.participants.find((participant) => participant.role === node.toRole)
        if (from !== undefined && to !== undefined && source.has(from.uid)) found.push(to.uid)
      }
      return Either.right(ordered(found))
    }
    const left = visit(node.left)
    if (Either.isLeft(left)) return releft(left.left)
    const right = visit(node.right)
    if (Either.isLeft(right)) return releft(right.left)
    const lhs = new Set(left.right), rhs = new Set(right.right)
    const values = node.tag === "Union" ? [...lhs, ...rhs] : node.tag === "Intersect"
      ? [...lhs].filter((uid) => rhs.has(uid)) : [...lhs].filter((uid) => !rhs.has(uid))
    return Either.right(ordered(values))
  }
  const result = visit(checked.right)
  return Either.isLeft(result) ? releft(result.left) : Either.right(Object.freeze({
    uids: result.right,
    nodeSteps: steps,
    interpreter: "INDEPENDENT_CALIBRATION_INTERPRETER_V1"
  }))
}
