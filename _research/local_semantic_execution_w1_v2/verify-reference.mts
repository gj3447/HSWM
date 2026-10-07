/** Audit the finite reference without changing the frozen W1 experiment or contacting a model. */
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { join, resolve, isAbsolute } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createRequire } from 'node:module'
import { root, domain, sourcePins, sha, json, requestFor } from './runner.mts'

const dist = resolve(process.env.HSWM_RESEARCH_RUNTIME_DIST ?? join(root, 'src/hswm/effect-runtime/dist'))
const { Effect, Layer } = createRequire(join(dist, 'index.js'))('effect')
const proof = await import(pathToFileURL(join(dist, 'semantic-philosophy-proof-process.js')).href)
const fs = await import(pathToFileURL(join(dist, 'effect-posix-filesystem.js')).href)
const subprocess = await import(pathToFileURL(join(dist, 'effect-bounded-subprocess.js')).href)
const profile = Object.freeze({
  name: 'full-w1-reference', sourceOrder: ['HSWMFullW1Reference'], auditedSources: ['HSWMFullW1Reference'],
  schemaVersion: 'hswm-full-w1-reference-lean-verification/v1',
  claimCeiling: 'FINITE_AUTHORED_BOOLEAN_REFERENCE_NOT_NATURAL_LANGUAGE_TRUTH_JSON_PARSER_OR_MODEL_EFFICACY'
})
const extraSources = [
  'formal/HSWMFullW1Reference.lean', 'formal/HSWMFullW1ReferenceCli.lean',
  '_research/local_semantic_execution_w1_v2/verify-reference.mts',
  'tests/research/full-w1-reference.test.mts',
  'src/hswm/effect-runtime/src/semantic-philosophy-proof-process.ts',
  'src/hswm/effect-runtime/src/effect-posix-filesystem.ts',
  'src/hswm/effect-runtime/src/effect-bounded-subprocess.ts',
  'formal/lean-toolchain', '_research/llm_semantic_graph_v1/lean-verification.v1.json'
]
const readJson = async (path: string) => JSON.parse(await readFile(path, 'utf8'))
const save = (path: string, value: unknown) => writeFile(path, json(value), { flag: 'wx', mode: 0o600 })
async function command(argv: string[], cwd: string, environment: Record<string, string>, stdin?: string) {
  const result = await Effect.runPromise(subprocess.BoundedSubprocess.pipe(
    Effect.flatMap((service: any) => service.observe({ argv, cwd, environment,
      ...(stdin === undefined ? {} : { stdin: new TextEncoder().encode(stdin) }),
      timeoutMs: 120_000, maximumOutputBytes: 2 * 1024 * 1024, killProcessGroup: true })),
    Effect.provide(subprocess.NodeBoundedSubprocessLive)))
  if (result.exitCode !== 0 || result.timedOut || result.outputTruncated || result.launchError !== null) {
    throw new Error(`REFERENCE_COMMAND_FAILED:${new TextDecoder().decode(result.stderr).slice(0, 2000)}`)
  }
  return result
}
export function assertReferenceMatches(cases: readonly any[], result: any) {
  if (!Array.isArray(result.cases) || result.cases.length !== cases.length) throw new Error('REFERENCE_ROW_COUNT_MISMATCH')
  for (const [index, entry] of cases.entries()) {
    const row = result.cases[index]
    if (row.caseId !== entry.caseId || row.accepted !== true || JSON.stringify(row.output) !== JSON.stringify(entry.expected)) {
      // JSON object member order is immaterial; compare the declared output fields exactly.
      if (row.caseId !== entry.caseId || row.accepted !== true || !row.output ||
          Object.keys(row.output).sort().join(',') !== 'answer,base,context_flip,exception_flip' ||
          ['base', 'context_flip', 'exception_flip', 'answer'].some(key => row.output[key] !== entry.expected[key])) {
        throw new Error(`REFERENCE_OUTPUT_MISMATCH:${entry.caseId}`)
      }
    }
  }
}
const frame = (entry: any) => ({ caseId: entry.caseId, familyIndex: entry.familyIndex, transform: entry.transform, input: entry.input })
const expectedTransforms = ['original', 'paraphrase-a', 'paraphrase-b', 'rename', 'reorder', 'role-exchange']
const expectedModes = ['E0', 'E1', 'E2']
const expectedSentinels = [[0, 0], [0, 1], [1, 0], [1, 4], [2, 0], [2, 3], [3, 0], [3, 3]]
const key = (...parts: readonly (string | number)[]) => parts.join(':')
const fieldsFor = (entry: any) => {
  const renamed = entry.transform === 'rename'
  const fields = entry.input?.fields
  return renamed
    ? [fields?.r7?.v2, fields?.r7?.v5, fields?.r7?.v8, fields?.r3?.v4, fields?.r9?.v6]
    : [fields?.subject?.dax, fields?.subject?.wug, fields?.subject?.zif, fields?.context?.pel, fields?.exception?.nub]
}

/** Structural and byte-level W1 bindings only; family-text interpretation remains author declared. */
export function validateW1Structure(input: {
  readonly cases: readonly any[]
  readonly schedule: readonly any[]
  readonly sentinels: readonly any[]
  readonly transforms?: readonly string[]
  readonly modes?: readonly string[]
  readonly requestFor?: (item: any) => any
}) {
  const { cases, schedule, sentinels } = input
  const transforms = input.transforms ?? expectedTransforms, modes = input.modes ?? expectedModes
  if (JSON.stringify(transforms) !== JSON.stringify(expectedTransforms) || JSON.stringify(modes) !== JSON.stringify(expectedModes)) throw new Error('STRUCTURE_DECLARATION_MISMATCH')
  if (cases.length !== 768 || new Set(cases.map(entry => entry.caseId)).size !== 768) throw new Error('CASE_ID_COVERAGE_MISMATCH')
  const byCase = new Map(cases.map(entry => [entry.caseId, entry]))
  const textBindings: any[] = []
  for (const transform of transforms) for (let family = 0; family < 4; family += 1) {
    const block = cases.filter(entry => entry.transform === transform && entry.familyIndex === family)
    if (block.length !== 32) throw new Error(`FAMILY_BLOCK_COUNT_MISMATCH:${transform}:${family}`)
    const tuples = block.map(fieldsFor)
    if (tuples.some(tuple => tuple.length !== 5 || tuple.some(bit => bit !== 0 && bit !== 1)) || new Set(tuples.map(tuple => tuple.join(''))).size !== 32) throw new Error(`BINARY_TUPLE_COVERAGE_MISMATCH:${transform}:${family}`)
    const texts = new Set(block.map(entry => entry.input?.relation?.semanticText))
    if (texts.size !== 1 || typeof block[0]?.input?.relation?.semanticText !== 'string' || block[0].input.relation.semanticText.length === 0) throw new Error(`RELATION_TEXT_BINDING_MISMATCH:${transform}:${family}`)
    textBindings.push(Object.freeze({ transform, familyIndex: family, semantic_text_sha256: sha(block[0].input.relation.semanticText), interpretation: 'AUTHOR_DECLARED_NOT_NLP_SEMANTICS_PROOF' }))
  }
  for (const entry of cases) if (entry.inputJson !== JSON.stringify(entry.input)) throw new Error(`INPUT_JSON_MISMATCH:${entry.caseId}`)
  if (sentinels.length !== 8 || new Set(sentinels.map(entry => entry.sentinelId)).size !== 8) throw new Error('SENTINEL_DECLARATION_MISMATCH')
  for (const [index, [family, ordinal]] of expectedSentinels.entries()) {
    const sentinel = sentinels[index], baseCaseId = `local-semantic-f${family}-i${String(ordinal).padStart(2, '0')}`
    if (!sentinel || sentinel.sentinelId !== `sentinel-f${family}-i${String(ordinal).padStart(2, '0')}` || sentinel.baseCaseId !== baseCaseId || sentinel.caseId !== `original:${baseCaseId}` || sentinel.familyIndex !== family || !byCase.has(sentinel.caseId)) throw new Error(`SENTINEL_MAPPING_MISMATCH:${index}`)
  }
  if (schedule.length !== 2784 || schedule.some((entry, ordinal) => entry.ordinal !== ordinal)) throw new Error('SCHEDULE_ORDINAL_MISMATCH')
  const census = schedule.filter(entry => entry.kind === 'census'), sentinelRows = schedule.filter(entry => entry.kind === 'sentinel')
  if (census.length !== 2304 || sentinelRows.length !== 480 || census.some(entry => entry.ordinal >= 2304 || entry.repetition !== null || entry.sentinelId !== null) || sentinelRows.some(entry => entry.ordinal < 2304)) throw new Error('SCHEDULE_PARTITION_MISMATCH')
  const censusCounts = new Map<string, number>()
  for (const row of census) {
    if (!byCase.has(row.caseId) || !modes.includes(row.mode)) throw new Error('CENSUS_REFERENCE_MISMATCH')
    const countKey = key(row.caseId, row.mode); censusCounts.set(countKey, (censusCounts.get(countKey) ?? 0) + 1)
  }
  for (const entry of cases) for (const mode of modes) if (censusCounts.get(key(entry.caseId, mode)) !== 1) throw new Error(`CENSUS_ARM_COVERAGE_MISMATCH:${entry.caseId}:${mode}`)
  const sentinelCounts = new Map<string, number>()
  for (const row of sentinelRows) {
    if (!Number.isInteger(row.repetition) || row.repetition < 0 || row.repetition >= 20 || !modes.includes(row.mode)) throw new Error('SENTINEL_REPETITION_MISMATCH')
    const sentinel = sentinels.find(entry => entry.sentinelId === row.sentinelId)
    if (!sentinel || row.caseId !== sentinel.caseId) throw new Error('SENTINEL_SCHEDULE_MAPPING_MISMATCH')
    const countKey = key(row.sentinelId, row.repetition, row.mode); sentinelCounts.set(countKey, (sentinelCounts.get(countKey) ?? 0) + 1)
  }
  for (const sentinel of sentinels) for (let repetition = 0; repetition < 20; repetition += 1) for (const mode of modes) if (sentinelCounts.get(key(sentinel.sentinelId, repetition, mode)) !== 1) throw new Error(`SENTINEL_ARM_COVERAGE_MISMATCH:${sentinel.sentinelId}:${repetition}:${mode}`)
  const requestBindings = input.requestFor === undefined ? [] : schedule.map(item => {
    const request = input.requestFor!(item), entry = byCase.get(item.caseId)
    const content = request?.messages?.[1]?.content
    const expectedContent = entry === undefined ? null : `${entry.inputJson}\n${domain.fullW1ModeInstructions(entry, item.mode)}`
    if (typeof content !== 'string' || content !== expectedContent) throw new Error(`MODEL_VISIBLE_REQUEST_MISMATCH:${item.ordinal}`)
    return Object.freeze({ ordinal: item.ordinal, caseId: item.caseId, mode: item.mode, request_sha256: sha(JSON.stringify(request)) })
  })
  return Object.freeze({
    relation_text_bindings: textBindings,
    structure: Object.freeze({ case_ids: cases.length, transforms: transforms.map(transform => ({ transform, cases: cases.filter(entry => entry.transform === transform).length })), census_rows: census.length, sentinel_rows: sentinelRows.length, schedule_rows: schedule.length, order_claim: 'ORDINAL_AND_PARTITION_CHECKED_NOT_LEAN_ORDER_EQUIVALENCE_PROOF' }),
    request_bindings: requestBindings,
    request_bindings_sha256: sha(JSON.stringify(requestBindings))
  })
}
function refusalCases() {
  const original = frame(domain.fullW1Cases[0]), renamed = frame(domain.fullW1Cases.find((entry: any) => entry.transform === 'rename'))
  const mutations: [string, any, (value: any) => void][] = [
    ['invalid-bit', original, x => { x.input.fields.subject.dax = 2 }],
    ['wrong-ordinal', original, x => { x.input.roles[0].ordinal = 1 }],
    ['duplicate-role', original, x => { x.input.roles[1] = structuredClone(x.input.roles[0]) }],
    ['partial-rename', renamed, x => { x.input.fields.r7.dax = x.input.fields.r7.v2; delete x.input.fields.r7.v2 }],
    ['unknown-transform', original, x => { x.transform = 'unpublished' }],
    ['gold-in-request', original, x => { x.expected = { answer: 0 } }],
    ['unexpected-prior', original, x => { x.input.priorEvidence = [0] }],
    ['unknown-family', original, x => { x.familyIndex = 4 }],
    ['missing-role', original, x => { x.input.roles.pop() }]
  ]
  return mutations.map(([name, source, mutate]) => { const value = structuredClone(source); value.caseId = name; mutate(value); return value })
}

export async function verifyReference(output: string) {
  if (!isAbsolute(output)) throw new Error('USE_ABSOLUTE_NEW_PRIVATE_DIRECTORY')
  const pinned = await sourcePins()
  const bindings = validateW1Structure({ cases: domain.fullW1Cases, schedule: domain.fullW1Schedule, sentinels: domain.fullW1Sentinels, requestFor })
  const sourceBindings = [...pinned.sources, ...await Promise.all(extraSources.map(async path => ({ path, sha256: sha(await readFile(join(root, path))) })))]
  const compiledBindings = [...pinned.compiled, ...await Promise.all(['semantic-philosophy-proof-process.js', 'effect-posix-filesystem.js', 'effect-bounded-subprocess.js'].map(async name => ({ name, sha256: sha(await readFile(join(dist, name))) })))]
  await mkdir(output, { mode: 0o700 })
  const formal = join(root, 'formal'), kernel = join(output, 'kernel')
  const environment = { PATH: process.env.PATH ?? '/usr/bin:/bin' }
  await Effect.runPromise(proof.runSemanticPhilosophyProof({ output: kernel, lean: null, profile }).pipe(
    Effect.provide(Layer.succeed(proof.SemanticPhilosophyProofHost, { repository: root, environment })),
    Effect.provide(fs.NodePosixFileSystemLive), Effect.provide(subprocess.NodeBoundedSubprocessLive)))
  const kernelReport = await readJson(join(kernel, 'lean-verification.v1.json'))
  const lean = kernelReport.toolchain.execution_binary
  const freshEnvironment = { ...environment, LEAN_PATH: kernelReport.toolchain.lean_path_entries.join(':') }
  const cliPath = join(formal, 'HSWMFullW1ReferenceCli.lean')
  const cliCompilation = await command([lean, '--trust=0', '-o', join(kernel, 'olean', 'HSWMFullW1ReferenceCli.olean'), cliPath], formal, freshEnvironment)
  const request = { contract: 'hswm-full-w1-reference/v1', cases: domain.fullW1Cases.map(frame) }
  const execution = await command([lean, '--trust=0', '--run', cliPath], formal, freshEnvironment, JSON.stringify(request))
  const result = JSON.parse(new TextDecoder().decode(execution.stdout))
  assertReferenceMatches(domain.fullW1Cases, result)
  const invalid = { contract: 'hswm-full-w1-reference/v1', cases: refusalCases() }
  const refusalExecution = await command([lean, '--trust=0', '--run', cliPath], formal, freshEnvironment, JSON.stringify(invalid))
  const refused = JSON.parse(new TextDecoder().decode(refusalExecution.stdout))
  if (refused.cases?.length !== invalid.cases.length || refused.cases.some((row: any, index: number) => row.accepted !== false || row.caseId !== invalid.cases[index].caseId)) throw new Error('REFERENCE_REFUSAL_MISMATCH')
  await save(join(output, 'request.json'), request)
  await save(join(output, 'response.json'), result)
  await save(join(output, 'refusals.json'), { request: invalid, response: refused })
  for (const source of sourceBindings) if (sha(await readFile(join(root, source.path))) !== source.sha256) throw new Error(`SOURCE_CHANGED:${source.path}`)
  for (const compiled of compiledBindings) if (sha(await readFile(join(dist, compiled.name))) !== compiled.sha256) throw new Error(`COMPILED_SOURCE_CHANGED:${compiled.name}`)
  const { lean_path: _path, execution_binary: _binary, lean_path_entries: _entries, ...toolchain } = kernelReport.toolchain
  const report = {
    schema_version: 'hswm-full-w1-reference-conformance/v1', recorded_at: new Date().toISOString(),
    authority: 'SECONDARY_AI_ENGINEERING_VALIDATION', status: 'FINITE_REFERENCE_KERNEL_CHECKED_AND_NATIVE_TABLE_MATCHED',
    source_bindings: sourceBindings, compiled_bindings: compiledBindings, toolchain,
    kernel: { sources: kernelReport.source_records, allowed_axioms: kernelReport.allowed_axioms,
      trust: 0, fresh_output: true, auditor_source: kernelReport.runner_source },
    comparison: { rows: result.cases.length, transforms: domain.fullW1Transforms.map((transform: string) => ({ transform, matched: domain.fullW1Cases.filter((entry: any) => entry.transform === transform).length })),
      request_sha256: sha(JSON.stringify(request)), response_sha256: sha(execution.stdout),
      source_frame_mapping: 'ACTUAL_TS_INPUT_OBJECTS_DECODED_IN_LEAN_BY_ROLE_ORDINAL_AND_DECLARED_RENAME_MAP',
      family_semantics: 'AUTHOR_DECLARED_FAMILY_INDEX_NOT_DERIVED_FROM_NATURAL_LANGUAGE',
      relation_text_bindings: bindings.relation_text_bindings,
      structure: bindings.structure,
      model_visible_request_bindings: bindings.request_bindings,
      model_visible_request_bindings_sha256: bindings.request_bindings_sha256 },
    refused_cases: refused.cases.map((row: any) => ({ caseId: row.caseId, reason: row.reason })),
    cli_compile_stdout_sha256: sha(cliCompilation.stdout), cli_compile_stderr_sha256: sha(cliCompilation.stderr),
    actual_model_requests: 0, experiment_protocol_changed: false,
    claim_ceiling: profile.claimCeiling,
    limitations: ['The CLI JSON decoder and TypeScript implementation are compared finitely, not universally proved.',
      'Relation-text hashes bind authored bytes only; paraphrase meaning and the mapping from authored text to the four family labels remain explicit assumptions.',
      'Schedule ordinal and partition coverage are checked structurally; this report does not claim Lean proof of scheduler order equivalence.',
      'This audit does not establish model readiness, learning, causal efficacy, CR/FCL, or complete HSWM.']
  }
  await save(join(output, 'verification.v1.json'), report)
  return report
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [output] = process.argv.slice(2)
  if (!output || process.argv.length !== 3) throw new Error('Usage: node verify-reference.mts ABS_NEW_PRIVATE_DIRECTORY')
  const result = await verifyReference(output)
  console.log(JSON.stringify({ status: result.status, rows: result.comparison.rows, theorems: result.kernel.sources[0].named_theorem_count, actual_model_requests: 0 }))
}
