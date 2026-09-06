/**
 * One-request DNRD subprocess bridge.
 *
 * This is a local experimental structural adapter. It does not issue a
 * canonical Permit, establish admission, prove scorer independence, or claim
 * learning/scientific efficacy. Every invocation consumes one JSON object on
 * stdin, emits one JSON object on stdout, and exits.
 *
 * The whole request is one Effect program: the wire shapes are checked by
 * Either-returning decoders, every refusal is a typed failure, all file and
 * directory access goes through the `PosixFileSystem` service, each durable
 * mount is provided as a Layer, and the executable's only runtime boundary
 * is `runProcessMain`.
 */
import { createHash, randomUUID } from "node:crypto"
import { dirname, isAbsolute, join, relative, resolve } from "node:path"
import { pathToFileURL } from "node:url"

import { Cause, Context, Data, Effect, Either, Layer } from "effect"

import { canonicalJsonBytes, decodeCanonicalJsonBytes, type CanonicalJson } from "./canonical-atom-v2-json.js"
import {
  DNRD_FILE_LINEAGE,
  DnrdRoutingDiagnosticFile,
  makeDnrdRoutingDiagnosticFileLayer
} from "./canonical-atom-v2-routing-diagnostic-file.js"
import {
  DNRD_ROUTING_PAYLOAD_V1,
  DNRD_SCORE_MICROS_LIMIT,
  applyDnrdCreditUpdate,
  derangeDnrdRoutingBindings,
  dnrdRoutingPayloadSha256,
  makeDnrdOutcomeObservation,
  dnrdScoreNorms,
  selectDnrdRoute,
  validateDnrdEligibilityTrace,
  validateDnrdRoutingPayload,
  type DnrdEligibilityTrace,
  type DnrdOutcomeObservation,
  type DnrdRoutingPayload
} from "./canonical-atom-v2-routing-diagnostic.js"
import { PosixFileSystem, type PosixFileSystemShape, type PosixIoError } from "./effect-posix-filesystem.js"
import { ProcessRefusal, nodeProcessIo, readNodeStdin, refuse, runProcessMain, type ProcessIo } from "./effect-process-main.js"

const PROCESS_SCHEMA = "hswm-dnrd-routing-diagnostic-process/v1" as const
const MOUNT_SCHEMA = "hswm-dnrd-routing-diagnostic-process-mount/v1" as const
const ROOT_CONFIG_SCHEMA = "hswm-dnrd-routing-diagnostic-process-root-config/v1" as const
const STREAM_RESERVATION_SCHEMA = "hswm-dnrd-routing-diagnostic-stream-reservation/v1" as const
const CONTROL_RESERVATION_SCHEMA = "hswm-dnrd-routing-diagnostic-control-reservation/v1" as const
const MOUNT_PREFIX = "dnrd-mount-v1-"
const RAW_DELTA_RULE = "signed_reward_times_100000_div_1000000/v1" as const
const ROUTING_OWNER = "owner:dnrd:routing" as const
const PRODUCER_ADDRESS = "principal:dnrd-producer" as const
const SCORER_ADDRESS = "principal:dnrd-scorer" as const
const RAW_SCORER_ADDRESS = "_research/dnrd/scorer.py" as const
const SCORER_PROVENANCE_ADDRESS = `repo:${RAW_SCORER_ADDRESS}` as const
const PROCESS_INSTANCE_ID = randomUUID()
const MOUNT_ID = /^dnrd-mount-v1-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const SHA256 = /^[0-9a-f]{64}$/
const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/
const MAX_FILE_BYTES = 1_048_576
/** The implementation binding read was previously unbounded; this bound only excludes absurd files. */
const MAX_IMPLEMENTATION_BYTES = 67_108_864
const FS_OPERATION = "dnrd-routing-diagnostic-process"
const STDIN_REFUSAL = "stdin must contain one bounded JSON object without duplicate keys"

type JsonObject = Record<string, unknown>
type Operation = "INIT_STREAM" | "MATERIALIZE_CONTROL" | "SEAL_TRACE" | "APPLY_OUTCOME" | "RECOVER"
type MountRole = "W0_ROLLBACK" | "FULL_TRAINABLE" | "RAW_CONTROL" | "DERANGED_CONTROL"

interface ProcessConfig {
  readonly rootPath: string
  readonly frozenScorerSourceSha256: string
}

interface ProcessRoot {
  readonly root: string
  readonly mounts: string
  readonly registry: string
  readonly streams: string
  readonly controls: string
  readonly frozenScorerSourceSha256: string
}

interface ContextBinding {
  readonly contextKey: string
  readonly contextSha256: string
  readonly stratum: string
}

interface TrainingExposure {
  readonly episodeId: string
  readonly contextKey: string
  readonly selectedRouteId: string
}

interface EpisodeExposure {
  readonly episodeId: string
  readonly contextKey: string
  readonly phase: "training" | "heldout"
  readonly forcedRouteId: string | null
}

interface MountMetadata {
  readonly schemaVersion: typeof MOUNT_SCHEMA
  readonly mountId: string
  readonly mountRole: MountRole
  readonly sourceMountId: string | null
  readonly sourceStateSha256: string | null
  readonly frozenScorerSourceSha256: string
  readonly streamId: string
  readonly routeIds: ReadonlyArray<string>
  readonly contexts: ReadonlyArray<ContextBinding>
  readonly matchedDerangement: Readonly<Record<string, string>>
  readonly episodes: ReadonlyArray<EpisodeExposure>
  readonly training: ReadonlyArray<TrainingExposure>
}

type MountBaseMetadata = Omit<MountMetadata, "mountId" | "mountRole" | "sourceMountId" | "sourceStateSha256" | "frozenScorerSourceSha256">

interface RoutingStateWire {
  readonly state_sha256: string
  readonly revision_id: string
  readonly lineage_id: typeof DNRD_FILE_LINEAGE
  readonly owner_id: typeof ROUTING_OWNER
  readonly mount_id: string
  readonly mount_role: MountRole
  readonly immutable: true
  readonly scores: Readonly<Record<string, Readonly<Record<string, number>>>>
}

interface RecoveredMount {
  readonly metadata: MountMetadata
  readonly payload: DnrdRoutingPayload
  readonly state: RoutingStateWire
  readonly journalSha256: string
}

interface AdapterRecovery {
  readonly payload: DnrdRoutingPayload
  readonly payloadSha256: string
  readonly journalSha256: string
  readonly routingRevision: string
}

interface WireTrace {
  readonly trace_id: string
  readonly episode_id: string
  readonly context_key: string
  readonly context_sha256: string
  readonly stratum: string
  readonly selected_route_id: string
  readonly pre_outcome_score_micros: number
  readonly routing_payload_sha256: string
  readonly request_sha256: string
  readonly response_sha256: string
  readonly status: "SEALED_PRE_OUTCOME_LOCAL_EXPERIMENTAL_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING"
}

interface ParsedOutcome {
  readonly episodeId: string
  readonly routeId: string
  readonly reward: -1_000_000 | 0 | 1_000_000
  readonly digest: string
  readonly scorerAddress: string
  readonly scorerSourceIdentity: string
  readonly roleSeparation: "DECLARED_ROLE_SEPARATION_NOT_PROVEN"
}

interface TreeEntry {
  readonly path: string
  readonly mode: number
  readonly sha256: string
  readonly byteLength: number
  readonly device: number
  readonly inode: number
}

/**
 * A durable-mount adapter failure keeps its whole Cause so the process
 * boundary renders it exactly as the former Promise boundary rendered a
 * FiberFailure.
 */
export class DnrdRoutingDiagnosticAdapterFailure extends Data.TaggedError("DnrdRoutingDiagnosticAdapterFailure")<{
  readonly cause: Cause.Cause<unknown>
}> {}

export type DnrdRoutingDiagnosticProcessError = ProcessRefusal | PosixIoError | DnrdRoutingDiagnosticAdapterFailure

type RefusalOrIo = ProcessRefusal | PosixIoError

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

const sha256 = (value: Uint8Array | string): string =>
  createHash("sha256").update(value).digest("hex")

const contextSha256 = (contextKey: string): string => sha256(Buffer.from(contextKey, "utf8"))

const identicalBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength && left.every((byte, index) => byte === right[index])

const compareCodeUnits = (left: string, right: string): number => left < right ? -1 : left > right ? 1 : 0

const asObject = (value: unknown, label: string): Either.Either<JsonObject, ProcessRefusal> =>
  typeof value !== "object" || value === null || Array.isArray(value)
    ? Either.left(refuse(`${label} must be an object`))
    : Either.right(value as JsonObject)

const exactKeys = (value: JsonObject, keys: ReadonlyArray<string>, label: string): Either.Either<void, ProcessRefusal> => {
  const actual = Object.keys(value).sort()
  const expected = [...keys].sort()
  return actual.length !== expected.length || actual.some((key, index) => key !== expected[index])
    ? Either.left(refuse(`${label} has missing or excess fields`))
    : Either.void
}

const requiredString = (value: unknown, label: string): Either.Either<string, ProcessRefusal> =>
  typeof value !== "string" || value.length === 0
    ? Either.left(refuse(`${label} must be a nonempty string`))
    : Either.right(value)

const requiredSha256 = (value: unknown, label: string): Either.Either<string, ProcessRefusal> =>
  Either.flatMap(requiredString(value, label), (parsed) =>
    SHA256.test(parsed) ? Either.right(parsed) : Either.left(refuse(`${label} must be a lowercase SHA-256`)))

const requiredIdentifier = (value: unknown, label: string): Either.Either<string, ProcessRefusal> =>
  Either.flatMap(requiredString(value, label), (parsed) =>
    IDENTIFIER.test(parsed) ? Either.right(parsed) : Either.left(refuse(`${label} is not a DNRD identifier`)))

const requiredInteger = (value: unknown, label: string): Either.Either<number, ProcessRefusal> =>
  typeof value !== "number" || !Number.isSafeInteger(value)
    ? Either.left(refuse(`${label} must be a safe integer`))
    : Either.right(value)

const requiredArray = (value: unknown, label: string): Either.Either<ReadonlyArray<unknown>, ProcessRefusal> =>
  Array.isArray(value) ? Either.right(value as ReadonlyArray<unknown>) : Either.left(refuse(`${label} must be an array`))

const parseMountRole = (value: unknown, detail: string): Either.Either<MountRole, ProcessRefusal> =>
  value === "W0_ROLLBACK" || value === "FULL_TRAINABLE" || value === "RAW_CONTROL" || value === "DERANGED_CONTROL"
    ? Either.right(value)
    : Either.left(refuse(detail))

const canonicalBytes = (value: unknown): Either.Either<Uint8Array, ProcessRefusal> =>
  Either.mapBoth(canonicalJsonBytes(value), {
    onLeft: () => refuse("value cannot form canonical JSON"),
    onRight: (bytes) => Uint8Array.from(bytes)
  })

/** Python task_family.commitment-compatible JSON for the ASCII request config. */
const pythonJson = (value: unknown): Either.Either<string, ProcessRefusal> => {
  if (value === null) return Either.right("null")
  if (value === true) return Either.right("true")
  if (value === false) return Either.right("false")
  if (typeof value === "string") {
    const encoded = JSON.stringify(value)
    return encoded === undefined
      ? Either.left(refuse("configuration string is not JSON encodable"))
      : Either.right(encoded.replace(/[\u0080-\uFFFF]/g, (character) => `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`))
  }
  if (typeof value === "number") {
    return !Number.isSafeInteger(value) || Object.is(value, -0)
      ? Either.left(refuse("configuration number is not a canonical integer"))
      : Either.right(String(value))
  }
  if (Array.isArray(value)) return Either.map(Either.all(value.map(pythonJson)), (items) => `[${items.join(",")}]`)
  return Either.gen(function* () {
    const object = yield* asObject(value, "configuration value")
    const members = yield* Either.all(Object.keys(object).sort().map((key) => Either.gen(function* () {
      const encodedKey = yield* pythonJson(key)
      const encodedValue = yield* pythonJson(object[key])
      return `${encodedKey}:${encodedValue}`
    })))
    return `{${members.join(",")}}`
  })
}

const canonicalHash = (value: unknown): Either.Either<string, ProcessRefusal> => Either.map(canonicalBytes(value), sha256)

const sameCanonical = (left: unknown, right: unknown): Either.Either<boolean, ProcessRefusal> => Either.gen(function* () {
  const leftBytes = yield* canonicalBytes(left)
  const rightBytes = yield* canonicalBytes(right)
  return identicalBytes(leftBytes, rightBytes)
})

const exactCoreDerangementForBindings = (
  contexts: ReadonlyArray<ContextBinding>
): Either.Either<Readonly<Record<string, string>>, ProcessRefusal> => Either.gen(function* () {
  const byStratum = new Map<string, ContextBinding[]>()
  for (const context of contexts) {
    const group = byStratum.get(context.stratum) ?? []
    group.push(context)
    byStratum.set(context.stratum, group)
  }
  const unsorted: Record<string, string> = Object.create(null)
  for (const stratum of [...byStratum.keys()].sort()) {
    const ordered = [...byStratum.get(stratum)!].sort((left, right) => left.contextSha256.localeCompare(right.contextSha256))
    if (ordered.length < 2) return yield* Either.left(refuse("exact TS-core derangement is impossible for a one-context stratum"))
    for (const [index, receiver] of ordered.entries()) {
      unsorted[receiver.contextKey] = ordered[(index + 1) % ordered.length]!.contextKey
    }
  }
  const canonical: Record<string, string> = Object.create(null)
  for (const receiver of Object.keys(unsorted).sort()) canonical[receiver] = unsorted[receiver]!
  return Object.freeze(canonical)
})

const parseConfig = (value: unknown): Either.Either<ProcessConfig, ProcessRefusal> => Either.gen(function* () {
  const input = yield* asObject(value, "config")
  yield* exactKeys(input, ["root_path", "frozen_scorer_source_sha256"], "config")
  const rootPath = yield* requiredString(input["root_path"], "config.root_path")
  if (!isAbsolute(rootPath)) return yield* Either.left(refuse("config.root_path must be absolute"))
  const frozenScorerSourceSha256 = yield* requiredSha256(input["frozen_scorer_source_sha256"], "config.frozen_scorer_source_sha256")
  return Object.freeze({ rootPath: resolve(rootPath), frozenScorerSourceSha256 })
})

const parseOperation = (value: unknown): Either.Either<Operation, ProcessRefusal> =>
  value === "INIT_STREAM" || value === "MATERIALIZE_CONTROL" || value === "SEAL_TRACE" || value === "APPLY_OUTCOME" || value === "RECOVER"
    ? Either.right(value)
    : Either.left(refuse("operation is not a supported DNRD bridge operation"))

const mountPath = (root: { readonly mounts: string }, mountId: string): Either.Either<string, ProcessRefusal> => {
  if (!MOUNT_ID.test(mountId)) return Either.left(refuse("mount_id is not a process-owned opaque mount id"))
  const path = resolve(root.mounts, mountId)
  if (dirname(path) !== resolve(root.mounts)) return Either.left(refuse("mount_id escapes the dedicated mounts root"))
  return Either.right(path)
}

const registryPath = (root: { readonly registry: string }, mountId: string): Either.Either<string, ProcessRefusal> => {
  if (!MOUNT_ID.test(mountId)) return Either.left(refuse("mount_id is not a process-owned opaque mount id"))
  const path = resolve(root.registry, `${mountId}.json`)
  if (dirname(path) !== resolve(root.registry)) return Either.left(refuse("mount_id escapes the dedicated registry root"))
  return Either.right(path)
}

const parseMetadata = (value: unknown): Either.Either<MountMetadata, ProcessRefusal> => Either.gen(function* () {
  const input = yield* asObject(value, "mount registry")
  yield* exactKeys(input, ["schema_version", "mount_id", "mount_role", "source_mount_id", "source_state_sha256", "frozen_scorer_source_sha256", "stream_id", "route_ids", "contexts", "matched_derangement", "episodes", "training"], "mount registry")
  if (input["schema_version"] !== MOUNT_SCHEMA) return yield* Either.left(refuse("mount registry schema is invalid"))
  const mountId = yield* requiredString(input["mount_id"], "mount registry.mount_id")
  if (!MOUNT_ID.test(mountId)) return yield* Either.left(refuse("mount registry mount id is invalid"))
  const mountRole = yield* parseMountRole(input["mount_role"], "mount registry role is invalid")
  const rawSourceMountId = input["source_mount_id"]
  const rawSourceStateSha256 = input["source_state_sha256"]
  const sourceMountId = rawSourceMountId === null ? null : (yield* requiredString(rawSourceMountId, "mount registry.source_mount_id"))
  const sourceStateSha256 = rawSourceStateSha256 === null ? null : (yield* requiredSha256(rawSourceStateSha256, "mount registry.source_state_sha256"))
  if ((sourceMountId !== null && !MOUNT_ID.test(sourceMountId)) || (mountRole === "W0_ROLLBACK") !== (sourceMountId === null && sourceStateSha256 === null)) {
    return yield* Either.left(refuse("mount registry source lineage does not match its immutable role"))
  }
  if (mountRole !== "W0_ROLLBACK" && (sourceMountId === null || sourceStateSha256 === null)) return yield* Either.left(refuse("non-W0 mount lacks exact source lineage"))
  const frozenScorerSourceSha256 = yield* requiredSha256(input["frozen_scorer_source_sha256"], "mount registry.frozen_scorer_source_sha256")
  const streamId = yield* requiredIdentifier(input["stream_id"], "mount registry.stream_id")
  const rawRouteIds = yield* requiredArray(input["route_ids"], "mount registry.route_ids")
  const routeIds = yield* Either.all(rawRouteIds.map((route, index) => requiredIdentifier(route, `mount registry.route_ids[${index}]`)))
  if (routeIds.length < 1 || routeIds.length > 256 || new Set(routeIds).size !== routeIds.length || [...routeIds].sort().some((route, index) => route !== routeIds[index])) {
    return yield* Either.left(refuse("mount registry routes must be sorted and unique"))
  }
  const rawContexts = yield* requiredArray(input["contexts"], "mount registry.contexts")
  const contexts = yield* Either.all(rawContexts.map((entry, index) => Either.gen(function* () {
    const object = yield* asObject(entry, `mount registry.contexts[${index}]`)
    yield* exactKeys(object, ["context_key", "context_sha256", "stratum"], `mount registry.contexts[${index}]`)
    const contextKey = yield* requiredString(object["context_key"], `mount registry.contexts[${index}].context_key`)
    const contextDigest = yield* requiredSha256(object["context_sha256"], `mount registry.contexts[${index}].context_sha256`)
    const stratum = yield* requiredIdentifier(object["stratum"], `mount registry.contexts[${index}].stratum`)
    if (contextDigest !== contextSha256(contextKey)) return yield* Either.left(refuse("mount registry context hash differs from raw context key"))
    return Object.freeze({ contextKey, contextSha256: contextDigest, stratum })
  })))
  if (contexts.length < 1 || contexts.length > 256 || new Set(contexts.map((context) => context.contextKey)).size !== contexts.length || new Set(contexts.map((context) => context.contextSha256)).size !== contexts.length) {
    return yield* Either.left(refuse("mount registry contexts are not unique"))
  }
  const sortedContexts = [...contexts].sort((left, right) => `${left.stratum}\u0000${left.contextSha256}`.localeCompare(`${right.stratum}\u0000${right.contextSha256}`))
  if (sortedContexts.some((context, index) => context !== contexts[index])) return yield* Either.left(refuse("mount registry contexts are not canonically sorted"))
  const matchedInput = yield* asObject(input["matched_derangement"], "mount registry.matched_derangement")
  const contextKeys = new Set(contexts.map((context) => context.contextKey))
  if (Object.keys(matchedInput).length !== contextKeys.size || Object.keys(matchedInput).some((receiver) => !contextKeys.has(receiver) || typeof matchedInput[receiver] !== "string" || !contextKeys.has(matchedInput[receiver] as string) || receiver === matchedInput[receiver]) || new Set(Object.values(matchedInput) as string[]).size !== contextKeys.size) {
    return yield* Either.left(refuse("mount registry derangement is not an exact fixed-point-free context bijection"))
  }
  const matchedDerangement: Record<string, string> = Object.create(null)
  for (const receiver of Object.keys(matchedInput).sort()) matchedDerangement[receiver] = matchedInput[receiver] as string
  const coreDerangement = yield* exactCoreDerangementForBindings(contexts)
  if (!(yield* sameCanonical(matchedDerangement, coreDerangement))) {
    return yield* Either.left(refuse("mount registry derangement differs structurally from the exact TS-core SHA-ordered binding"))
  }
  const rawEpisodes = yield* requiredArray(input["episodes"], "mount registry.episodes")
  const episodes = yield* Either.all(rawEpisodes.map((entry, index) => Either.gen(function* () {
    const object = yield* asObject(entry, `mount registry.episodes[${index}]`)
    yield* exactKeys(object, ["episode_id", "context_key", "phase", "forced_route_id"], `mount registry.episodes[${index}]`)
    const phase = object["phase"]
    if (phase !== "training" && phase !== "heldout") return yield* Either.left(refuse("mount registry episode phase is invalid"))
    const forcedRouteId = object["forced_route_id"]
    if (phase === "training" && typeof forcedRouteId !== "string") return yield* Either.left(refuse("training episode is missing forced route"))
    if (phase === "heldout" && forcedRouteId !== null) return yield* Either.left(refuse("heldout episode must not have a forced route"))
    const episodeId = yield* requiredIdentifier(object["episode_id"], `mount registry.episodes[${index}].episode_id`)
    const contextKey = yield* requiredString(object["context_key"], `mount registry.episodes[${index}].context_key`)
    const forced = forcedRouteId === null ? null : (yield* requiredIdentifier(forcedRouteId, `mount registry.episodes[${index}].forced_route_id`))
    return Object.freeze({ episodeId, contextKey, phase, forcedRouteId: forced })
  })))
  if (episodes.length !== 16 || new Set(episodes.map((entry) => entry.episodeId)).size !== episodes.length || episodes.some((entry) => !contexts.some((context) => context.contextKey === entry.contextKey) || (entry.forcedRouteId !== null && !routeIds.includes(entry.forcedRouteId)))) {
    return yield* Either.left(refuse("mount registry episode support is invalid"))
  }
  const rawTraining = yield* requiredArray(input["training"], "mount registry.training")
  const training = yield* Either.all(rawTraining.map((entry, index) => Either.gen(function* () {
    const object = yield* asObject(entry, `mount registry.training[${index}]`)
    yield* exactKeys(object, ["episode_id", "context_key", "selected_route_id"], `mount registry.training[${index}]`)
    const episodeId = yield* requiredIdentifier(object["episode_id"], `mount registry.training[${index}].episode_id`)
    const contextKey = yield* requiredString(object["context_key"], `mount registry.training[${index}].context_key`)
    const selectedRouteId = yield* requiredIdentifier(object["selected_route_id"], `mount registry.training[${index}].selected_route_id`)
    return Object.freeze({ episodeId, contextKey, selectedRouteId })
  })))
  if (new Set(training.map((entry) => entry.episodeId)).size !== training.length || training.length !== 8 || training.some((entry) => !contexts.some((context) => context.contextKey === entry.contextKey) || !routeIds.includes(entry.selectedRouteId) || !episodes.some((episode) => episode.phase === "training" && episode.episodeId === entry.episodeId && episode.contextKey === entry.contextKey && episode.forcedRouteId === entry.selectedRouteId))) {
    return yield* Either.left(refuse("mount registry training exposure support is invalid"))
  }
  return Object.freeze({ schemaVersion: MOUNT_SCHEMA, mountId, mountRole, sourceMountId, sourceStateSha256, frozenScorerSourceSha256, streamId, routeIds: Object.freeze(routeIds), contexts: Object.freeze(contexts), matchedDerangement: Object.freeze(matchedDerangement), episodes: Object.freeze(episodes), training: Object.freeze(training) })
})

const metadataWire = (metadata: MountMetadata): JsonObject => ({
  schema_version: metadata.schemaVersion,
  mount_id: metadata.mountId,
  mount_role: metadata.mountRole,
  source_mount_id: metadata.sourceMountId,
  source_state_sha256: metadata.sourceStateSha256,
  frozen_scorer_source_sha256: metadata.frozenScorerSourceSha256,
  stream_id: metadata.streamId,
  route_ids: metadata.routeIds,
  contexts: metadata.contexts.map((context) => ({ context_key: context.contextKey, context_sha256: context.contextSha256, stratum: context.stratum })),
  matched_derangement: metadata.matchedDerangement,
  episodes: metadata.episodes.map((episode) => ({ episode_id: episode.episodeId, context_key: episode.contextKey, phase: episode.phase, forced_route_id: episode.forcedRouteId })),
  training: metadata.training.map((training) => ({ episode_id: training.episodeId, context_key: training.contextKey, selected_route_id: training.selectedRouteId }))
})

const payloadFromScores = (
  metadata: Pick<MountMetadata, "contexts" | "routeIds">,
  scores: Readonly<Record<string, Readonly<Record<string, number>>>>
): Either.Either<DnrdRoutingPayload, ProcessRefusal> => Either.gen(function* () {
  const expectedContextKeys = new Set(metadata.contexts.map((context) => context.contextKey))
  const actualContextKeys = Object.keys(scores)
  if (actualContextKeys.length !== expectedContextKeys.size || actualContextKeys.some((context) => !expectedContextKeys.has(context))) {
    return yield* Either.left(refuse("state scores do not have exact raw context support"))
  }
  const contexts = yield* Either.all(metadata.contexts.map((context) => Either.gen(function* () {
    const routes = scores[context.contextKey]
    if (routes === undefined) return yield* Either.left(refuse("state score context is absent"))
    const actualRoutes = Object.keys(routes)
    if (actualRoutes.length !== metadata.routeIds.length || actualRoutes.some((route) => !metadata.routeIds.includes(route))) {
      return yield* Either.left(refuse("state scores do not have exact route support"))
    }
    const routeScores = yield* Either.all(metadata.routeIds.map((routeId) => Either.gen(function* () {
      const scoreMicros = yield* requiredInteger(routes[routeId], `state score ${context.contextKey}/${routeId}`)
      if (scoreMicros < -DNRD_SCORE_MICROS_LIMIT || scoreMicros > DNRD_SCORE_MICROS_LIMIT) return yield* Either.left(refuse("state score is outside frozen signed-micros bounds"))
      return Object.freeze({ routeId, scoreMicros })
    })))
    return Object.freeze({ contextSha256: context.contextSha256, stratum: context.stratum, routes: routeScores })
  })))
  const payload = { schemaVersion: DNRD_ROUTING_PAYLOAD_V1, contexts: Object.freeze(contexts), structuralStatus: "LOCAL_EXPERIMENTAL_ROUTING_PAYLOAD_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING" as const }
  const checked = validateDnrdRoutingPayload(payload)
  if (Either.isLeft(checked)) return yield* Either.left(refuse(`routing payload is invalid: ${checked.left.detail}`))
  return checked.right
})

const scoresFromPayload = (
  metadata: MountMetadata,
  payload: DnrdRoutingPayload
): Either.Either<Readonly<Record<string, Readonly<Record<string, number>>>>, ProcessRefusal> => Either.gen(function* () {
  const scores: Record<string, Readonly<Record<string, number>>> = Object.create(null)
  for (const binding of metadata.contexts) {
    const context = payload.contexts.find((candidate) => candidate.contextSha256 === binding.contextSha256 && candidate.stratum === binding.stratum)
    if (context === undefined) return yield* Either.left(refuse("durable payload lacks a registered raw context"))
    if (context.routes.length !== metadata.routeIds.length || context.routes.some((route) => !metadata.routeIds.includes(route.routeId))) {
      return yield* Either.left(refuse("durable payload route support differs from mount registry"))
    }
    const routeScores: Record<string, number> = Object.create(null)
    for (const routeId of metadata.routeIds) {
      const route = context.routes.find((candidate) => candidate.routeId === routeId)
      if (route === undefined) return yield* Either.left(refuse("durable payload route is absent"))
      routeScores[routeId] = route.scoreMicros
    }
    scores[binding.contextKey] = Object.freeze(routeScores)
  }
  if (payload.contexts.length !== metadata.contexts.length) return yield* Either.left(refuse("durable payload has an unregistered context"))
  return Object.freeze(scores)
})

const makeState = (
  metadata: MountMetadata,
  recovered: { readonly payload: DnrdRoutingPayload; readonly payloadSha256: string; readonly routingRevision: string }
): Either.Either<RoutingStateWire, ProcessRefusal> =>
  Either.map(scoresFromPayload(metadata, recovered.payload), (scores) => Object.freeze({
    state_sha256: recovered.payloadSha256,
    revision_id: recovered.routingRevision,
    lineage_id: DNRD_FILE_LINEAGE,
    owner_id: ROUTING_OWNER,
    mount_id: metadata.mountId,
    mount_role: metadata.mountRole,
    immutable: true as const,
    scores
  }))

const parseStateWire = (value: unknown): Either.Either<RoutingStateWire, ProcessRefusal> => Either.gen(function* () {
  const input = yield* asObject(value, "state")
  yield* exactKeys(input, ["state_sha256", "revision_id", "lineage_id", "owner_id", "mount_id", "mount_role", "immutable", "scores"], "state")
  const stateSha256 = yield* requiredSha256(input["state_sha256"], "state.state_sha256")
  const revisionId = yield* requiredString(input["revision_id"], "state.revision_id")
  if (!/^(0|[1-9][0-9]*)$/.test(revisionId)) return yield* Either.left(refuse("state.revision_id must be a nonnegative decimal routing revision"))
  if (input["lineage_id"] !== DNRD_FILE_LINEAGE || input["owner_id"] !== ROUTING_OWNER || input["immutable"] !== true) {
    return yield* Either.left(refuse("state has a non-DNRD lineage, owner, or mutability claim"))
  }
  const mountId = yield* requiredString(input["mount_id"], "state.mount_id")
  if (!MOUNT_ID.test(mountId)) return yield* Either.left(refuse("state.mount_id is invalid"))
  const mountRole = yield* parseMountRole(input["mount_role"], "state.mount_role is invalid")
  const scoresInput = yield* asObject(input["scores"], "state.scores")
  const scores: Record<string, Readonly<Record<string, number>>> = Object.create(null)
  for (const contextKey of Object.keys(scoresInput)) {
    const routesInput = yield* asObject(scoresInput[contextKey], `state.scores.${contextKey}`)
    const routes: Record<string, number> = Object.create(null)
    for (const routeId of Object.keys(routesInput)) routes[routeId] = yield* requiredInteger(routesInput[routeId], `state.scores.${contextKey}.${routeId}`)
    scores[contextKey] = Object.freeze(routes)
  }
  return Object.freeze({ state_sha256: stateSha256, revision_id: revisionId, lineage_id: DNRD_FILE_LINEAGE, owner_id: ROUTING_OWNER, mount_id: mountId, mount_role: mountRole, immutable: true as const, scores: Object.freeze(scores) })
})

const randomMountId = (): string => `${MOUNT_PREFIX}${randomUUID()}`

const controlMetadata = (source: RecoveredMount, mountRole: "RAW_CONTROL" | "DERANGED_CONTROL"): Omit<MountMetadata, "mountId"> => Object.freeze({
  schemaVersion: source.metadata.schemaVersion,
  mountRole,
  sourceMountId: source.metadata.mountId,
  sourceStateSha256: source.state.state_sha256,
  frozenScorerSourceSha256: source.metadata.frozenScorerSourceSha256,
  streamId: source.metadata.streamId,
  routeIds: source.metadata.routeIds,
  contexts: source.metadata.contexts,
  matchedDerangement: source.metadata.matchedDerangement,
  episodes: source.metadata.episodes,
  training: source.metadata.training
})

const treeManifest = (entries: ReadonlyArray<TreeEntry>): ReadonlyArray<Readonly<{ path: string; mode: number; sha256: string; byteLength: number }>> =>
  Object.freeze(entries.map((entry) => Object.freeze({ path: entry.path, mode: entry.mode, sha256: entry.sha256, byteLength: entry.byteLength })))

const parseStream = (value: unknown): Either.Either<{ readonly metadata: MountBaseMetadata; readonly zeroPayload: DnrdRoutingPayload }, ProcessRefusal> => Either.gen(function* () {
  const stream = yield* asObject(value, "stream")
  yield* exactKeys(stream, ["stream_id", "route_ids", "context_keys", "matched_derangement", "training", "heldout"], "stream")
  const streamId = yield* requiredIdentifier(stream["stream_id"], "stream.stream_id")
  const rawRouteIds = yield* requiredArray(stream["route_ids"], "stream.route_ids")
  const routeIds = yield* Either.all(rawRouteIds.map((route, index) => requiredIdentifier(route, `stream.route_ids[${index}]`)))
  if (routeIds.length !== 2 || new Set(routeIds).size !== routeIds.length) return yield* Either.left(refuse("stream must contain exactly two unique routes"))
  const sortedRoutes = [...routeIds].sort()
  const rawContextKeys = yield* requiredArray(stream["context_keys"], "stream.context_keys")
  const contextKeys = yield* Either.all(rawContextKeys.map((context, index) => requiredString(context, `stream.context_keys[${index}]`)))
  if (contextKeys.length !== 4 || new Set(contextKeys).size !== contextKeys.length) return yield* Either.left(refuse("stream must contain exactly four unique contexts"))
  const stratum = `stratum:${sha256(streamId)}`
  const contexts = contextKeys.map((contextKey) => Object.freeze({ contextKey, contextSha256: contextSha256(contextKey), stratum })).sort((left, right) => `${left.stratum}\u0000${left.contextSha256}`.localeCompare(`${right.stratum}\u0000${right.contextSha256}`))
  const contextSet = new Set(contextKeys)
  const mapping = yield* asObject(stream["matched_derangement"], "stream.matched_derangement")
  if (Object.keys(mapping).length !== contextKeys.length || Object.keys(mapping).some((source) => !contextSet.has(source) || typeof mapping[source] !== "string" || !contextSet.has(mapping[source] as string) || source === mapping[source])) {
    return yield* Either.left(refuse("stream matched_derangement is not a fixed-point-free context binding"))
  }
  if (new Set(Object.values(mapping) as string[]).size !== contextKeys.length) return yield* Either.left(refuse("stream matched_derangement is not a bijection"))
  const matchedDerangement: Record<string, string> = Object.create(null)
  for (const receiver of Object.keys(mapping).sort()) matchedDerangement[receiver] = mapping[receiver] as string
  const coreDerangement = yield* exactCoreDerangementForBindings(contexts)
  if (!(yield* sameCanonical(matchedDerangement, coreDerangement))) {
    return yield* Either.left(refuse("stream matched_derangement differs structurally from the exact TS-core SHA-ordered binding"))
  }
  const parseEpisode = (entry: unknown, phase: "training" | "heldout", index: number): Either.Either<EpisodeExposure, ProcessRefusal> => Either.gen(function* () {
    const episode = yield* asObject(entry, `stream.${phase}[${index}]`)
    const keys = phase === "training"
      ? ["episode_id", "stream_id", "phase", "context_key", "candidate_route_ids", "entity", "aliases", "surface_template", "prompt", "route_evidence", "forced_route_id", "provenance_canary"]
      : ["episode_id", "stream_id", "phase", "context_key", "candidate_route_ids", "entity", "aliases", "surface_template", "prompt", "route_evidence", "arm_order"]
    yield* exactKeys(episode, keys, `stream.${phase}[${index}]`)
    const episodeId = yield* requiredIdentifier(episode["episode_id"], `stream.${phase}[${index}].episode_id`)
    if (episode["stream_id"] !== streamId || episode["phase"] !== phase) return yield* Either.left(refuse(`stream.${phase}[${index}] has a mismatched stream or phase`))
    const contextKey = yield* requiredString(episode["context_key"], `stream.${phase}[${index}].context_key`)
    if (!contextSet.has(contextKey)) return yield* Either.left(refuse(`stream.${phase}[${index}] has unknown context support`))
    const candidates = yield* requiredArray(episode["candidate_route_ids"], `stream.${phase}[${index}].candidate_route_ids`)
    if (candidates.length !== routeIds.length || new Set(candidates).size !== routeIds.length || candidates.some((route) => typeof route !== "string" || !routeIds.includes(route))) {
      return yield* Either.left(refuse(`stream.${phase}[${index}] candidate route support differs`))
    }
    yield* requiredString(episode["entity"], `stream.${phase}[${index}].entity`)
    yield* requiredString(episode["surface_template"], `stream.${phase}[${index}].surface_template`)
    const prompt = yield* requiredString(episode["prompt"], `stream.${phase}[${index}].prompt`)
    const aliases = yield* requiredArray(episode["aliases"], `stream.${phase}[${index}].aliases`)
    if (aliases.length !== 2 || new Set(aliases).size !== 2) return yield* Either.left(refuse(`stream.${phase}[${index}] aliases differ from frozen two-alias shape`))
    yield* Either.all(aliases.map((alias, aliasIndex) => requiredString(alias, `stream.${phase}[${index}].aliases[${aliasIndex}]`)))
    const evidence = yield* requiredArray(episode["route_evidence"], `stream.${phase}[${index}].route_evidence`)
    if (evidence.length !== routeIds.length) return yield* Either.left(refuse(`stream.${phase}[${index}] evidence count differs from route support`))
    const evidenceRoutes = new Set<string>()
    for (const [evidenceIndex, entryEvidence] of evidence.entries()) {
      const evidenceObject = yield* asObject(entryEvidence, `stream.${phase}[${index}].route_evidence[${evidenceIndex}]`)
      yield* exactKeys(evidenceObject, ["route_id", "evidence_text", "response_token"], `stream.${phase}[${index}].route_evidence[${evidenceIndex}]`)
      const evidenceRoute = yield* requiredIdentifier(evidenceObject["route_id"], `stream.${phase}[${index}].route_evidence[${evidenceIndex}].route_id`)
      if (!routeIds.includes(evidenceRoute) || evidenceRoutes.has(evidenceRoute)) return yield* Either.left(refuse(`stream.${phase}[${index}] evidence route support differs`))
      evidenceRoutes.add(evidenceRoute)
      yield* requiredString(evidenceObject["evidence_text"], `stream.${phase}[${index}].route_evidence[${evidenceIndex}].evidence_text`)
      yield* requiredString(evidenceObject["response_token"], `stream.${phase}[${index}].route_evidence[${evidenceIndex}].response_token`)
    }
    if (phase === "training") {
      const route = yield* requiredIdentifier(episode["forced_route_id"], `stream.training[${index}].forced_route_id`)
      const canary = yield* requiredString(episode["provenance_canary"], `stream.training[${index}].provenance_canary`)
      if (!/^dnrd-training-provenance:[0-9a-f]{32}$/.test(canary) || !prompt.includes(canary)) {
        return yield* Either.left(refuse("training provenance canary is malformed or absent from its prompt"))
      }
      if (!routeIds.includes(route)) return yield* Either.left(refuse("training forced route is outside stream route support"))
      return Object.freeze({ episodeId, contextKey, phase, forcedRouteId: route })
    }
    const armOrder = yield* requiredArray(episode["arm_order"], `stream.heldout[${index}].arm_order`)
    const arms = ["FULL", "NO_MEMORY_ROLLBACK", "BINDING_DERANGED_NUMERIC_PLACEBO"]
    if (armOrder.length !== arms.length || new Set(armOrder).size !== arms.length || armOrder.some((arm) => typeof arm !== "string" || !arms.includes(arm))) {
      return yield* Either.left(refuse("heldout arm order differs from frozen arm set"))
    }
    return Object.freeze({ episodeId, contextKey, phase, forcedRouteId: null })
  })
  const trainingValues = yield* requiredArray(stream["training"], "stream.training")
  const heldoutValues = yield* requiredArray(stream["heldout"], "stream.heldout")
  if (trainingValues.length !== 8 || heldoutValues.length !== 8) return yield* Either.left(refuse("stream must contain exactly eight training and eight heldout episodes"))
  const trainingEpisodes = yield* Either.all(trainingValues.map((entry, index) => parseEpisode(entry, "training", index)))
  const heldoutEpisodes = yield* Either.all(heldoutValues.map((entry, index) => parseEpisode(entry, "heldout", index)))
  const episodes = [...trainingEpisodes, ...heldoutEpisodes]
  if (new Set(episodes.map((entry) => entry.episodeId)).size !== 16) return yield* Either.left(refuse("stream episode ids are not unique"))
  const training = episodes.filter((entry): entry is EpisodeExposure & { readonly forcedRouteId: string } => entry.phase === "training").map((entry) => Object.freeze({ episodeId: entry.episodeId, contextKey: entry.contextKey, selectedRouteId: entry.forcedRouteId }))
  const metadata = Object.freeze({ schemaVersion: MOUNT_SCHEMA, streamId, routeIds: Object.freeze(sortedRoutes), contexts: Object.freeze(contexts), matchedDerangement: Object.freeze(matchedDerangement), episodes: Object.freeze(episodes), training: Object.freeze(training) })
  const zeroScores: Record<string, Readonly<Record<string, number>>> = Object.create(null)
  for (const context of contexts) {
    const routes: Record<string, number> = Object.create(null)
    for (const routeId of sortedRoutes) routes[routeId] = 0
    zeroScores[context.contextKey] = Object.freeze(routes)
  }
  const zeroPayload = yield* payloadFromScores(metadata, zeroScores)
  return Object.freeze({ metadata, zeroPayload })
})

const parseWireTrace = (value: unknown): Either.Either<WireTrace, ProcessRefusal> => Either.gen(function* () {
  const trace = yield* asObject(value, "trace")
  yield* exactKeys(trace, ["trace_id", "episode_id", "context_key", "context_sha256", "stratum", "selected_route_id", "pre_outcome_score_micros", "routing_payload_sha256", "request_sha256", "response_sha256", "status"], "trace")
  if (trace["status"] !== "SEALED_PRE_OUTCOME_LOCAL_EXPERIMENTAL_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING") return yield* Either.left(refuse("trace status is invalid"))
  const preOutcomeScoreMicros = yield* requiredInteger(trace["pre_outcome_score_micros"], "trace.pre_outcome_score_micros")
  if (preOutcomeScoreMicros < -DNRD_SCORE_MICROS_LIMIT || preOutcomeScoreMicros > DNRD_SCORE_MICROS_LIMIT) return yield* Either.left(refuse("trace pre-outcome score is out of range"))
  const traceId = yield* requiredSha256(trace["trace_id"], "trace.trace_id")
  const episodeId = yield* requiredIdentifier(trace["episode_id"], "trace.episode_id")
  const contextKey = yield* requiredString(trace["context_key"], "trace.context_key")
  const contextDigest = yield* requiredSha256(trace["context_sha256"], "trace.context_sha256")
  const stratum = yield* requiredIdentifier(trace["stratum"], "trace.stratum")
  const selectedRouteId = yield* requiredIdentifier(trace["selected_route_id"], "trace.selected_route_id")
  const routingPayloadSha256 = yield* requiredSha256(trace["routing_payload_sha256"], "trace.routing_payload_sha256")
  const requestSha256 = yield* requiredSha256(trace["request_sha256"], "trace.request_sha256")
  const responseSha256 = yield* requiredSha256(trace["response_sha256"], "trace.response_sha256")
  return Object.freeze({
    trace_id: traceId,
    episode_id: episodeId,
    context_key: contextKey,
    context_sha256: contextDigest,
    stratum,
    selected_route_id: selectedRouteId,
    pre_outcome_score_micros: preOutcomeScoreMicros,
    routing_payload_sha256: routingPayloadSha256,
    request_sha256: requestSha256,
    response_sha256: responseSha256,
    status: "SEALED_PRE_OUTCOME_LOCAL_EXPERIMENTAL_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING" as const
  })
})

const traceFromWire = (trace: WireTrace): DnrdEligibilityTrace => Object.freeze({
  schemaVersion: "hswm-dnrd-eligibility-trace/v1",
  traceId: trace.trace_id,
  episodeId: trace.episode_id,
  routingPayloadSha256: trace.routing_payload_sha256,
  contextSha256: trace.context_sha256,
  stratum: trace.stratum,
  routeId: trace.selected_route_id,
  preOutcomeScoreMicros: trace.pre_outcome_score_micros,
  requestSha256: trace.request_sha256,
  responseSha256: trace.response_sha256,
  status: trace.status
})

const traceWire = (trace: DnrdEligibilityTrace, rawContextKey: string): WireTrace => Object.freeze({
  trace_id: trace.traceId,
  episode_id: trace.episodeId,
  context_key: rawContextKey,
  context_sha256: trace.contextSha256,
  stratum: trace.stratum,
  selected_route_id: trace.routeId,
  pre_outcome_score_micros: trace.preOutcomeScoreMicros,
  routing_payload_sha256: trace.routingPayloadSha256,
  request_sha256: trace.requestSha256,
  response_sha256: trace.responseSha256,
  status: trace.status
})

const parseOutcome = (value: unknown, config: ProcessConfig): Either.Either<ParsedOutcome, ProcessRefusal> => Either.gen(function* () {
  const outcome = yield* asObject(value, "outcome")
  yield* exactKeys(outcome, ["episode_id", "selected_route_id", "reward", "outcome_digest", "scorer_source_identity", "scorer_address", "role_separation"], "outcome")
  const reward = yield* requiredInteger(outcome["reward"], "outcome.reward")
  if (reward !== -1_000_000 && reward !== 0 && reward !== 1_000_000) return yield* Either.left(refuse("outcome.reward violates frozen signed outcome contract"))
  const scorerSourceIdentity = yield* requiredSha256(outcome["scorer_source_identity"], "outcome.scorer_source_identity")
  if (scorerSourceIdentity !== config.frozenScorerSourceSha256) return yield* Either.left(refuse("outcome scorer source differs from frozen configuration"))
  const roleSeparation = yield* requiredString(outcome["role_separation"], "outcome.role_separation")
  if (roleSeparation !== "DECLARED_ROLE_SEPARATION_NOT_PROVEN") return yield* Either.left(refuse("outcome role separation declaration is invalid"))
  const scorerAddress = yield* requiredString(outcome["scorer_address"], "outcome.scorer_address")
  if (scorerAddress !== RAW_SCORER_ADDRESS) return yield* Either.left(refuse("outcome scorer address differs from the frozen raw scorer provenance"))
  const episodeId = yield* requiredIdentifier(outcome["episode_id"], "outcome.episode_id")
  const routeId = yield* requiredIdentifier(outcome["selected_route_id"], "outcome.selected_route_id")
  const digest = yield* requiredSha256(outcome["outcome_digest"], "outcome.outcome_digest")
  return Object.freeze({ episodeId, routeId, reward, digest, scorerAddress, scorerSourceIdentity, roleSeparation: "DECLARED_ROLE_SEPARATION_NOT_PROVEN" as const })
})

const createControlReceipt = (arm: string, source: RoutingStateWire, target: RoutingStateWire, payload: DnrdRoutingPayload): Either.Either<string, ProcessRefusal> =>
  canonicalHash({ schema_version: PROCESS_SCHEMA, status: "LOCAL_EXPERIMENTAL_STRUCTURAL_ONLY_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING", arm, source_state_sha256: source.state_sha256, target_state_sha256: target.state_sha256, target_routing_payload: payload })

// ---------------------------------------------------------------------------
// Filesystem effects over the PosixFileSystem service
// ---------------------------------------------------------------------------

const assertPlainPrivateDirectory = (fs: PosixFileSystemShape, path: string, label: string): Effect.Effect<void, RefusalOrIo> =>
  Effect.flatMap(fs.identity(path, FS_OPERATION), (identity) =>
    identity.kind !== "DIRECTORY" || identity.mode !== 0o700
      ? Effect.fail(refuse(`${label} must be a plain private 0700 directory`))
      : Effect.void)

const makePrivateChildDirectory = (fs: PosixFileSystemShape, path: string, label: string): Effect.Effect<void, RefusalOrIo> =>
  Effect.gen(function* () {
    yield* fs.makeDirectory(path, { mode: 0o700, operation: FS_OPERATION }).pipe(
      Effect.catchIf((error) => error.code === "EEXIST", () => Effect.void)
    )
    yield* assertPlainPrivateDirectory(fs, path, label)
  })

/** Bounded 0400 read whose file identity is re-checked after the read. */
const readImmutableFile = (fs: PosixFileSystemShape, path: string, label: string): Effect.Effect<Uint8Array, RefusalOrIo> =>
  fs.readRegularBounded(path, { maximumBytes: MAX_FILE_BYTES, minimumBytes: 1, requiredMode: 0o400, operation: FS_OPERATION }).pipe(
    Effect.map((result) => result.bytes),
    Effect.mapError((cause) =>
      cause.code === "NOT_REGULAR_FILE" || cause.code === "MODE_INVALID" || cause.code === "BYTE_BOUND_EXCEEDED"
        ? refuse(`${label} must be a bounded immutable regular file`)
        : cause.code === "IDENTITY_CHANGED"
          ? refuse(`${label} changed during read`)
          : cause)
  )

/** Exclusive 0600 creation, chmod 0400, fsync, then exact immutable readback. */
const writeImmutableNewFile = (fs: PosixFileSystemShape, path: string, bytes: Uint8Array, label: string): Effect.Effect<void, RefusalOrIo> =>
  Effect.gen(function* () {
    yield* fs.writeExclusive(path, bytes, { mode: 0o600, finalMode: 0o400, sync: true, operation: FS_OPERATION }).pipe(
      Effect.mapError((cause) => cause.code === "IO_FAILED" ? refuse(`${label} could not be immutably published`) : cause)
    )
    yield* fs.chmod(path, 0o400, FS_OPERATION)
    const checked = yield* readImmutableFile(fs, path, label)
    if (!identicalBytes(checked, bytes)) return yield* Effect.fail(refuse(`${label} immutable readback differs`))
  })

const isExisting = (error: RefusalOrIo): boolean => error._tag === "PosixIoError" && error.code === "EEXIST"

const reserveOnce = (fs: PosixFileSystemShape, path: string, value: unknown, label: string): Effect.Effect<void, RefusalOrIo> =>
  Effect.gen(function* () {
    const bytes = yield* canonicalBytes(value)
    yield* writeImmutableNewFile(fs, path, bytes, label).pipe(
      Effect.mapError((error) => isExisting(error) ? refuse(`${label} already exists; this occurrence cannot choose an alternate mount`) : error)
    )
  })

const prepareDedicatedRoot = (fs: PosixFileSystemShape, config: ProcessConfig): Effect.Effect<ProcessRoot, RefusalOrIo> =>
  Effect.gen(function* () {
    yield* assertPlainPrivateDirectory(fs, config.rootPath, "configured DNRD root")
    const mounts = join(config.rootPath, "mounts")
    const registry = join(config.rootPath, "registry")
    const streams = join(config.rootPath, "streams")
    const controls = join(config.rootPath, "controls")
    yield* makePrivateChildDirectory(fs, mounts, "DNRD mounts root")
    yield* makePrivateChildDirectory(fs, registry, "DNRD registry root")
    yield* makePrivateChildDirectory(fs, streams, "DNRD stream-reservation root")
    yield* makePrivateChildDirectory(fs, controls, "DNRD control-reservation root")
    const rootConfigPath = join(config.rootPath, "root-config.json")
    const rootConfigBytes = yield* canonicalBytes({ schema_version: ROOT_CONFIG_SCHEMA, frozen_scorer_source_sha256: config.frozenScorerSourceSha256 })
    yield* writeImmutableNewFile(fs, rootConfigPath, rootConfigBytes, "DNRD immutable root configuration").pipe(
      Effect.catchIf(isExisting, () => Effect.gen(function* () {
        const existing = yield* readImmutableFile(fs, rootConfigPath, "DNRD immutable root configuration")
        if (!identicalBytes(existing, rootConfigBytes)) {
          return yield* Effect.fail(refuse("configured DNRD root is already frozen to a different scorer/configuration"))
        }
      }))
    )
    return Object.freeze({ root: config.rootPath, mounts, registry, streams, controls, frozenScorerSourceSha256: config.frozenScorerSourceSha256 })
  })

const writeMetadata = (fs: PosixFileSystemShape, root: { readonly registry: string }, metadata: MountMetadata): Effect.Effect<void, RefusalOrIo> =>
  Effect.gen(function* () {
    const path = yield* registryPath(root, metadata.mountId)
    const bytes = yield* canonicalBytes(metadataWire(metadata))
    yield* writeImmutableNewFile(fs, path, bytes, "mount registry")
  })

const loadMetadata = (fs: PosixFileSystemShape, root: { readonly registry: string }, mountId: string): Effect.Effect<MountMetadata, RefusalOrIo> =>
  Effect.gen(function* () {
    const path = yield* registryPath(root, mountId)
    const bytes = yield* readImmutableFile(fs, path, "mount registry")
    const decoded = decodeCanonicalJsonBytes(bytes)
    if (Either.isLeft(decoded)) return yield* Effect.fail(refuse("mount registry is not canonical JSON"))
    const metadata = yield* parseMetadata(decoded.right)
    if (metadata.mountId !== mountId) return yield* Effect.fail(refuse("mount registry identity does not match requested mount"))
    return metadata
  })

const collectImmutableTree = (fs: PosixFileSystemShape, root: string, current: string = root): Effect.Effect<ReadonlyArray<TreeEntry>, RefusalOrIo> =>
  Effect.gen(function* () {
    const directory = yield* fs.identity(current, FS_OPERATION)
    if (directory.kind !== "DIRECTORY" || directory.mode !== 0o700) return yield* Effect.fail(refuse("mount tree contains an unsafe directory"))
    const names = (yield* fs.listDirectory(current, FS_OPERATION)).map((entry) => entry.name).sort(compareCodeUnits)
    const entries: TreeEntry[] = []
    for (const name of names) {
      if (!/^[A-Za-z0-9._-]{1,256}$/.test(name)) return yield* Effect.fail(refuse("mount tree entry has an unsafe name"))
      const path = join(current, name)
      const child = yield* fs.identity(path, FS_OPERATION)
      if (child.kind === "SYMLINK") return yield* Effect.fail(refuse("mount tree contains a symlink"))
      if (child.kind === "DIRECTORY") {
        entries.push(...(yield* collectImmutableTree(fs, root, path)))
      } else if (child.kind === "FILE") {
        const bytes = yield* readImmutableFile(fs, path, "mount tree entry")
        entries.push(Object.freeze({ path: relative(root, path), mode: child.mode, sha256: sha256(bytes), byteLength: bytes.byteLength, device: child.device, inode: child.inode }))
      } else {
        return yield* Effect.fail(refuse("mount tree contains a nonregular file"))
      }
    }
    return Object.freeze(entries.sort((left, right) => left.path.localeCompare(right.path)))
  })

const copyImmutableTree = (fs: PosixFileSystemShape, source: string, destination: string): Effect.Effect<void, RefusalOrIo> =>
  Effect.gen(function* () {
    const sourceEntries = yield* collectImmutableTree(fs, source)
    yield* fs.makeDirectory(destination, { mode: 0o700, operation: FS_OPERATION }).pipe(
      Effect.mapError((cause) => cause.code === "EEXIST" ? refuse("destination mount already exists; process never overwrites it") : cause)
    )
    yield* assertPlainPrivateDirectory(fs, destination, "copied DNRD mount")
    const directories = new Set<string>([""])
    for (const entry of sourceEntries) {
      let parent = dirname(entry.path)
      while (parent !== "." && parent !== "") {
        directories.add(parent)
        parent = dirname(parent)
      }
    }
    for (const directory of [...directories].filter((directory) => directory !== "").sort((left, right) => left.split("/").length - right.split("/").length || left.localeCompare(right))) {
      const target = join(destination, directory)
      yield* fs.makeDirectory(target, { mode: 0o700, operation: FS_OPERATION })
      yield* assertPlainPrivateDirectory(fs, target, "copied DNRD mount directory")
    }
    const copiedBySourceIdentity = new Map<string, string>()
    for (const entry of sourceEntries) {
      const bytes = yield* readImmutableFile(fs, join(source, entry.path), "source mount file")
      if (sha256(bytes) !== entry.sha256 || bytes.byteLength !== entry.byteLength || entry.mode !== 0o400) return yield* Effect.fail(refuse("source mount tree changed during copy"))
      const target = join(destination, entry.path)
      const sourceIdentity = `${entry.device}:${entry.inode}`
      const firstTarget = copiedBySourceIdentity.get(sourceIdentity)
      if (firstTarget === undefined) {
        yield* writeImmutableNewFile(fs, target, bytes, "copied mount file")
        copiedBySourceIdentity.set(sourceIdentity, target)
      } else {
        yield* fs.linkNoReplace(firstTarget, target, FS_OPERATION)
        const linked = yield* readImmutableFile(fs, target, "copied hard-linked mount file")
        if (!identicalBytes(linked, bytes)) return yield* Effect.fail(refuse("copied mount hard link differs from source bytes"))
      }
    }
    const copied = yield* collectImmutableTree(fs, destination)
    if (!(yield* sameCanonical(treeManifest(sourceEntries), treeManifest(copied)))) {
      return yield* Effect.fail(refuse("copied mount tree does not exactly equal source prefix"))
    }
  })

const assertImplementationBinding = (fs: PosixFileSystemShape, pathValue: unknown, digestValue: unknown): Effect.Effect<void, RefusalOrIo> =>
  Effect.gen(function* () {
    const path = yield* requiredString(pathValue, "implementation_path")
    if (!isAbsolute(path)) return yield* Effect.fail(refuse("implementation_path must be absolute"))
    const identity = yield* fs.identity(path, FS_OPERATION)
    if (identity.kind !== "FILE") return yield* Effect.fail(refuse("implementation_path must name a plain file"))
    const expected = yield* requiredSha256(digestValue, "implementation_sha256")
    const implementation = yield* fs.readRegularBounded(path, { maximumBytes: MAX_IMPLEMENTATION_BYTES, operation: FS_OPERATION })
    if (sha256(implementation.bytes) !== expected) return yield* Effect.fail(refuse("implementation path/hash binding mismatch"))
  })

// ---------------------------------------------------------------------------
// Durable mount adapter, provided as a fresh Layer per use
// ---------------------------------------------------------------------------

type DnrdAdapter = Context.Tag.Service<typeof DnrdRoutingDiagnosticFile>

interface AdapterRecoveryWire {
  readonly payload: DnrdRoutingPayload
  readonly payloadSha256: string
  readonly journalHead: { readonly sha256: string }
}

interface AdapterSnapshotWire {
  readonly canonical: {
    readonly atoms: ReadonlyArray<{ readonly kind: string; readonly key: { readonly atomUid: string; readonly revisionId: number } }>
  }
}

/**
 * Every adapter use recovers the mount from its files through a fresh Layer;
 * nothing is cached across calls, so each observation is a fresh recovery.
 */
const withAdapter = <A>(path: string, use: (adapter: DnrdAdapter) => Effect.Effect<A, unknown>): Effect.Effect<A, DnrdRoutingDiagnosticAdapterFailure> =>
  Effect.flatMap(DnrdRoutingDiagnosticFile, use).pipe(
    Effect.provide(makeDnrdRoutingDiagnosticFileLayer(path) as Layer.Layer<DnrdRoutingDiagnosticFile, unknown>),
    Effect.catchAllCause((cause) => Effect.fail(new DnrdRoutingDiagnosticAdapterFailure({ cause })))
  )

const recoverAdapter = (path: string): Effect.Effect<AdapterRecovery, ProcessRefusal | DnrdRoutingDiagnosticAdapterFailure> =>
  Effect.gen(function* () {
    const observed = yield* withAdapter(path, (adapter) => Effect.gen(function* () {
      const recovered = (yield* adapter.recover) as AdapterRecoveryWire
      const snapshot = (yield* adapter.snapshot) as AdapterSnapshotWire
      return { recovered, snapshot }
    }))
    const routing = observed.snapshot.canonical.atoms.filter((atom) => atom.kind === "dnrd:routing-disposition").sort((left, right) => right.key.revisionId - left.key.revisionId)[0]
    if (routing === undefined) return yield* Effect.fail(refuse("durable mount has no routing disposition"))
    return Object.freeze({
      payload: observed.recovered.payload,
      payloadSha256: observed.recovered.payloadSha256,
      journalSha256: observed.recovered.journalHead.sha256,
      routingRevision: String(routing.key.revisionId)
    })
  })

const initializeAdapter = (path: string, payload: DnrdRoutingPayload): Effect.Effect<void, DnrdRoutingDiagnosticAdapterFailure> =>
  withAdapter(path, (adapter) => Effect.asVoid(adapter.initialize(payload)))

const sealAdapterTrace = (
  path: string,
  input: { readonly episodeId: string; readonly contextSha256: string; readonly routeId: string; readonly requestSha256: string; readonly responseSha256: string }
): Effect.Effect<DnrdEligibilityTrace, DnrdRoutingDiagnosticAdapterFailure> =>
  withAdapter(path, (adapter) => adapter.sealTrainingTrajectory(input))

const applyAdapterOutcome = (path: string, outcome: DnrdOutcomeObservation): Effect.Effect<unknown, DnrdRoutingDiagnosticAdapterFailure> =>
  withAdapter(path, (adapter) => adapter.applyOutcome(outcome, 100_000, 100_000))

const consumedOutcomeIds = (path: string): Effect.Effect<ReadonlyArray<string>, ProcessRefusal | DnrdRoutingDiagnosticAdapterFailure> =>
  Effect.gen(function* () {
    const snapshot = yield* withAdapter(path, (adapter) => Effect.map(adapter.snapshot, (value) => value as AdapterSnapshotWire))
    const prefix = "dnrd:outcome:"
    const outcomeAtoms = snapshot.canonical.atoms.filter((atom) => atom.kind === "dnrd:outcome")
    if (outcomeAtoms.some((atom) => !atom.key.atomUid.startsWith(prefix))) {
      return yield* Effect.fail(refuse("durable outcome atom uid does not have DNRD outcome identity"))
    }
    const ids = outcomeAtoms.map((atom) => atom.key.atomUid.slice(prefix.length)).sort()
    if (ids.some((id, index) => !SHA256.test(id) || (index > 0 && ids[index - 1] === id))) {
      return yield* Effect.fail(refuse("durable outcome atom identities are not sorted unique SHA-256 values"))
    }
    return Object.freeze(ids)
  })

const creditedEpisodeIds = (path: string): Effect.Effect<ReadonlyArray<string>, DnrdRoutingDiagnosticAdapterFailure> =>
  withAdapter(path, (adapter) => adapter.creditedEpisodeIds)

// ---------------------------------------------------------------------------
// Mount programs
// ---------------------------------------------------------------------------

const recoverMount = (fs: PosixFileSystemShape, root: ProcessRoot, supplied: unknown): Effect.Effect<RecoveredMount, DnrdRoutingDiagnosticProcessError> =>
  Effect.gen(function* () {
    const requested = yield* parseStateWire(supplied)
    const metadata = yield* loadMetadata(fs, root, requested.mount_id)
    if (metadata.frozenScorerSourceSha256 !== root.frozenScorerSourceSha256) return yield* Effect.fail(refuse("mount scorer identity differs from the immutable root configuration"))
    const path = yield* mountPath(root, requested.mount_id)
    yield* assertPlainPrivateDirectory(fs, path, "DNRD mount")
    const recovered = yield* recoverAdapter(path)
    const payloadDigest = dnrdRoutingPayloadSha256(recovered.payload)
    if (Either.isLeft(payloadDigest) || payloadDigest.right !== recovered.payloadSha256) return yield* Effect.fail(refuse("fresh recovery payload digest is invalid"))
    const expected = yield* makeState(metadata, recovered)
    if (!(yield* sameCanonical(requested, expected))) return yield* Effect.fail(refuse("supplied state does not exactly match fresh local experimental recovery"))
    return Object.freeze({ metadata, payload: recovered.payload, state: expected, journalSha256: recovered.journalSha256 })
  })

const createBootstrapMount = (
  fs: PosixFileSystemShape,
  root: { readonly mounts: string; readonly registry: string },
  metadataWithoutId: Omit<MountMetadata, "mountId">,
  payload: DnrdRoutingPayload
): Effect.Effect<RecoveredMount, DnrdRoutingDiagnosticProcessError> =>
  Effect.gen(function* () {
    const mountId = randomMountId()
    const path = yield* mountPath(root, mountId)
    yield* fs.makeDirectory(path, { mode: 0o700, operation: FS_OPERATION }).pipe(
      Effect.mapError((cause) => cause.code === "EEXIST" ? refuse("random mount id unexpectedly already exists") : cause)
    )
    yield* assertPlainPrivateDirectory(fs, path, "new DNRD mount")
    yield* initializeAdapter(path, payload)
    const metadata: MountMetadata = Object.freeze({ ...metadataWithoutId, mountId })
    yield* writeMetadata(fs, root, metadata)
    const recovered = yield* recoverAdapter(path)
    const state = yield* makeState(metadata, recovered)
    return Object.freeze({ metadata, payload: recovered.payload, state, journalSha256: recovered.journalSha256 })
  })

// ---------------------------------------------------------------------------
// Operations
// ---------------------------------------------------------------------------

const handleInitialize = (fs: PosixFileSystemShape, root: ProcessRoot, payload: unknown): Effect.Effect<JsonObject, DnrdRoutingDiagnosticProcessError> =>
  Effect.gen(function* () {
    const input = yield* asObject(payload, "INIT_STREAM payload")
    yield* exactKeys(input, ["stream"], "INIT_STREAM payload")
    const parsed = yield* parseStream(input["stream"])
    if (!/^stream-[0-3]$/.test(parsed.metadata.streamId)) return yield* Effect.fail(refuse("INIT_STREAM accepts only the four frozen DNRD stream identities"))
    const publicStreamSha256 = yield* canonicalHash(input["stream"])
    yield* reserveOnce(fs, join(root.streams, `${parsed.metadata.streamId}.json`), {
      schema_version: STREAM_RESERVATION_SCHEMA,
      stream_id: parsed.metadata.streamId,
      public_stream_sha256: publicStreamSha256
    }, "DNRD stream reservation")
    const w0Metadata: Omit<MountMetadata, "mountId"> = Object.freeze({
      ...parsed.metadata,
      mountRole: "W0_ROLLBACK",
      sourceMountId: null,
      sourceStateSha256: null,
      frozenScorerSourceSha256: root.frozenScorerSourceSha256
    })
    const w0 = yield* createBootstrapMount(fs, root, w0Metadata, parsed.zeroPayload)
    if (Object.values(w0.state.scores).some((routes) => Object.values(routes).some((score) => score !== 0))) return yield* Effect.fail(refuse("W0 bootstrap did not expose exact zero payload"))
    const w1Id = randomMountId()
    const w1Path = yield* mountPath(root, w1Id)
    const w0Path = yield* mountPath(root, w0.metadata.mountId)
    const prefix = yield* collectImmutableTree(fs, w0Path)
    yield* copyImmutableTree(fs, w0Path, w1Path)
    const copiedPrefix = yield* collectImmutableTree(fs, w1Path)
    if (!(yield* sameCanonical(treeManifest(prefix), treeManifest(copiedPrefix)))) return yield* Effect.fail(refuse("W0/W1 content-tree common prefix differs after byte copy"))
    const w1Metadata: MountMetadata = Object.freeze({
      ...parsed.metadata,
      mountId: w1Id,
      mountRole: "FULL_TRAINABLE",
      sourceMountId: w0.metadata.mountId,
      sourceStateSha256: w0.state.state_sha256,
      frozenScorerSourceSha256: root.frozenScorerSourceSha256
    })
    yield* writeMetadata(fs, root, w1Metadata)
    const w1Recovery = yield* recoverAdapter(w1Path)
    const w1State = yield* makeState(w1Metadata, w1Recovery)
    const w1 = Object.freeze({ metadata: w1Metadata, payload: w1Recovery.payload, state: w1State, journalSha256: w1Recovery.journalSha256 })
    if (!(yield* sameCanonical(w0.payload, w1.payload)) || w0.state.state_sha256 !== w1.state.state_sha256 || !(yield* sameCanonical(w0.state.scores, w1.state.scores))) {
      return yield* Effect.fail(refuse("W0/W1 copied genesis payload differs"))
    }
    const commonPrefixSha256 = yield* canonicalHash(treeManifest(prefix))
    const initializationReceiptSha256 = yield* canonicalHash({ schema_version: PROCESS_SCHEMA, status: "LOCAL_EXPERIMENTAL_STRUCTURAL_ONLY_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING", operation: "INIT_STREAM", w0_state_sha256: w0.state.state_sha256, w1_state_sha256: w1.state.state_sha256, common_prefix_sha256: commonPrefixSha256 })
    return Object.freeze({ w0: w0.state, w1: w1.state, initialization_receipt_sha256: initializationReceiptSha256, common_prefix_sha256: commonPrefixSha256, equal_genesis_content: true })
  })

const handleMaterializeControl = (fs: PosixFileSystemShape, root: ProcessRoot, payload: unknown): Effect.Effect<JsonObject, DnrdRoutingDiagnosticProcessError> =>
  Effect.gen(function* () {
    const input = yield* asObject(payload, "MATERIALIZE_CONTROL payload")
    const arm = input["arm"]
    if (arm !== "RAW_EQUAL_BUDGET" && arm !== "BINDING_DERANGED_NUMERIC_PLACEBO") return yield* Effect.fail(refuse("control arm is invalid"))
    const expectedKeys = arm === "RAW_EQUAL_BUDGET"
      ? ["state", "stream_id", "arm", "raw_delta_rule", "training_update_records", "required_training_outcome_count"]
      : ["state", "stream_id", "arm", "matched_derangement"]
    yield* exactKeys(input, expectedKeys, "MATERIALIZE_CONTROL payload")
    const source = yield* recoverMount(fs, root, input["state"])
    const streamId = yield* requiredIdentifier(input["stream_id"], "MATERIALIZE_CONTROL.stream_id")
    if (streamId !== source.metadata.streamId) return yield* Effect.fail(refuse("control stream id differs from source mount"))
    let targetPayload: DnrdRoutingPayload
    if (arm === "RAW_EQUAL_BUDGET") {
      if (source.metadata.mountRole !== "W0_ROLLBACK") return yield* Effect.fail(refuse("RAW must materialize only from the immutable recovered W0 rollback mount"))
      if (input["raw_delta_rule"] !== RAW_DELTA_RULE || input["required_training_outcome_count"] !== 8) return yield* Effect.fail(refuse("RAW frozen replay rule or count differs"))
      if (source.metadata.training.length !== 8 || Object.values(source.state.scores).some((routes) => Object.values(routes).some((score) => score !== 0))) return yield* Effect.fail(refuse("RAW must start from an exact zero W0 routing payload"))
      const records = yield* requiredArray(input["training_update_records"], "RAW training_update_records")
      if (records.length !== 8) return yield* Effect.fail(refuse("RAW requires exactly eight signed training update records"))
      const expectedByEpisode = new Map(source.metadata.training.map((entry) => [entry.episodeId, entry] as const))
      const scores: Record<string, Readonly<Record<string, number>>> = Object.create(null)
      for (const [contextKey, routes] of Object.entries(source.state.scores)) scores[contextKey] = Object.freeze({ ...routes })
      const seen = new Set<string>()
      for (const [index, rawRecord] of records.entries()) {
        const record = yield* asObject(rawRecord, `RAW training_update_records[${index}]`)
        yield* exactKeys(record, ["episode_id", "context_key", "selected_route_id", "reward", "trace_id", "outcome_digest"], `RAW training_update_records[${index}]`)
        const episodeId = yield* requiredIdentifier(record["episode_id"], `RAW record ${index}.episode_id`)
        const expected = expectedByEpisode.get(episodeId)
        const expectedAtIndex = source.metadata.training[index]
        const contextKey = yield* requiredString(record["context_key"], `RAW record ${index}.context_key`)
        const routeId = yield* requiredIdentifier(record["selected_route_id"], `RAW record ${index}.selected_route_id`)
        const reward = yield* requiredInteger(record["reward"], `RAW record ${index}.reward`)
        yield* requiredSha256(record["trace_id"], `RAW record ${index}.trace_id`)
        yield* requiredSha256(record["outcome_digest"], `RAW record ${index}.outcome_digest`)
        if (expected === undefined || expectedAtIndex === undefined || expectedAtIndex.episodeId !== episodeId || seen.has(episodeId) || expected.contextKey !== contextKey || expected.selectedRouteId !== routeId || (reward !== -1_000_000 && reward !== 0 && reward !== 1_000_000)) {
          return yield* Effect.fail(refuse("RAW record differs from one exact ordered public forced training exposure"))
        }
        seen.add(episodeId)
        const routes = scores[contextKey]
        if (routes === undefined || routes[routeId] === undefined) return yield* Effect.fail(refuse("RAW record has unsupported context/route"))
        const updated = Math.max(-DNRD_SCORE_MICROS_LIMIT, Math.min(DNRD_SCORE_MICROS_LIMIT, routes[routeId] + Math.trunc((reward * 100_000) / 1_000_000)))
        scores[contextKey] = Object.freeze({ ...routes, [routeId]: updated })
      }
      if (seen.size !== expectedByEpisode.size) return yield* Effect.fail(refuse("RAW records do not cover exactly the eight training exposures"))
      targetPayload = yield* payloadFromScores(source.metadata, scores)
    } else {
      if (source.metadata.mountRole !== "FULL_TRAINABLE") return yield* Effect.fail(refuse("DERANGED must materialize only from the recovered trained FULL mount"))
      const sourcePath = yield* mountPath(root, source.metadata.mountId)
      const credited = yield* creditedEpisodeIds(sourcePath)
      const expectedTraining = source.metadata.training.map((entry) => entry.episodeId).sort()
      if (!(yield* sameCanonical(credited, expectedTraining))) return yield* Effect.fail(refuse("DERANGED requires exactly all eight once-credited FULL training exposures"))
      const mapping = yield* asObject(input["matched_derangement"], "DERANGED matched_derangement")
      const contexts = source.metadata.contexts.map((context) => context.contextKey)
      const contextSet = new Set(contexts)
      if (Object.keys(mapping).length !== contexts.length || Object.keys(mapping).some((receiver) => !contextSet.has(receiver) || typeof mapping[receiver] !== "string" || !contextSet.has(mapping[receiver] as string) || receiver === mapping[receiver]) || new Set(Object.values(mapping) as string[]).size !== contexts.length) {
        return yield* Effect.fail(refuse("DERANGED must use an exact supplied fixed-point-free context bijection"))
      }
      if (!(yield* sameCanonical(mapping, source.metadata.matchedDerangement))) return yield* Effect.fail(refuse("DERANGED map differs from the exact public mounted binding"))
      const scores: Record<string, Readonly<Record<string, number>>> = Object.create(null)
      for (const receiver of contexts) {
        const donor = mapping[receiver] as string
        const donorScores = source.state.scores[donor]
        if (donorScores === undefined) return yield* Effect.fail(refuse("DERANGED donor score support is absent"))
        scores[receiver] = Object.freeze({ ...donorScores })
      }
      targetPayload = yield* payloadFromScores(source.metadata, scores)
      const coreDeranged = derangeDnrdRoutingBindings(source.payload)
      if (Either.isLeft(coreDeranged) || !(yield* sameCanonical(coreDeranged.right, targetPayload))) return yield* Effect.fail(refuse("public DERANGED map differs from the exact TS-core binding derangement"))
      const sourceNorms = dnrdScoreNorms(source.payload)
      const targetNorms = dnrdScoreNorms(targetPayload)
      if (Either.isLeft(sourceNorms) || Either.isLeft(targetNorms) || sourceNorms.right.l1Micros !== targetNorms.right.l1Micros || sourceNorms.right.l2SquaredMicros !== targetNorms.right.l2SquaredMicros) {
        return yield* Effect.fail(refuse("DERANGED payload does not preserve exact L1/L2-squared score norms"))
      }
    }
    const targetRole = arm === "RAW_EQUAL_BUDGET" ? "RAW_CONTROL" : "DERANGED_CONTROL"
    const targetPayloadSha256 = yield* canonicalHash(targetPayload)
    yield* reserveOnce(fs, join(root.controls, `${source.metadata.streamId}-${arm}.json`), {
      schema_version: CONTROL_RESERVATION_SCHEMA,
      stream_id: source.metadata.streamId,
      arm,
      source_mount_id: source.metadata.mountId,
      source_state_sha256: source.state.state_sha256,
      target_payload_sha256: targetPayloadSha256
    }, "DNRD control reservation")
    const materialized = yield* createBootstrapMount(fs, root, controlMetadata(source, targetRole), targetPayload)
    const receiptSha256 = yield* createControlReceipt(arm, source.state, materialized.state, targetPayload)
    return Object.freeze({ state: materialized.state, receipt_sha256: receiptSha256 })
  })

const handleSealTrace = (fs: PosixFileSystemShape, root: ProcessRoot, payload: unknown): Effect.Effect<WireTrace, DnrdRoutingDiagnosticProcessError> =>
  Effect.gen(function* () {
    const input = yield* asObject(payload, "SEAL_TRACE payload")
    yield* exactKeys(input, ["state", "episode_id", "context_key", "selected_route_id", "request_sha256", "response_sha256"], "SEAL_TRACE payload")
    const recovered = yield* recoverMount(fs, root, input["state"])
    const episodeId = yield* requiredIdentifier(input["episode_id"], "SEAL_TRACE.episode_id")
    const rawContext = yield* requiredString(input["context_key"], "SEAL_TRACE.context_key")
    const binding = recovered.metadata.contexts.find((context) => context.contextKey === rawContext)
    if (binding === undefined) return yield* Effect.fail(refuse("SEAL_TRACE context is absent from recovered mount"))
    const routeId = yield* requiredIdentifier(input["selected_route_id"], "SEAL_TRACE.selected_route_id")
    if (!recovered.metadata.routeIds.includes(routeId)) return yield* Effect.fail(refuse("SEAL_TRACE selected route is absent from recovered mount"))
    const publicEpisode = recovered.metadata.episodes.find((episode) => episode.episodeId === episodeId)
    if (publicEpisode === undefined || publicEpisode.contextKey !== rawContext || (publicEpisode.forcedRouteId !== null && publicEpisode.forcedRouteId !== routeId)) {
      return yield* Effect.fail(refuse("SEAL_TRACE must name one exact registered public episode/context/route exposure"))
    }
    if (publicEpisode.phase === "training" && recovered.metadata.mountRole !== "FULL_TRAINABLE") return yield* Effect.fail(refuse("only the FULL trainable mount may seal a forced-training trajectory"))
    if (publicEpisode.phase === "heldout") {
      const selected = selectDnrdRoute(recovered.payload, binding.contextSha256)
      if (Either.isLeft(selected) || selected.right.routeId !== routeId) return yield* Effect.fail(refuse("heldout trace route differs from the TS-core deterministic routing readout"))
    }
    const path = yield* mountPath(root, recovered.metadata.mountId)
    const requestSha256 = yield* requiredSha256(input["request_sha256"], "SEAL_TRACE.request_sha256")
    const responseSha256 = yield* requiredSha256(input["response_sha256"], "SEAL_TRACE.response_sha256")
    const trace = yield* sealAdapterTrace(path, { episodeId, contextSha256: binding.contextSha256, routeId, requestSha256, responseSha256 })
    if (trace.routingPayloadSha256 !== recovered.state.state_sha256 || trace.contextSha256 !== contextSha256(rawContext)) return yield* Effect.fail(refuse("sealed trace did not bind recovered routing state and raw context hash"))
    return traceWire(trace, rawContext)
  })

const handleApplyOutcome = (fs: PosixFileSystemShape, config: ProcessConfig, root: ProcessRoot, payload: unknown): Effect.Effect<JsonObject, DnrdRoutingDiagnosticProcessError> =>
  Effect.gen(function* () {
    const input = yield* asObject(payload, "APPLY_OUTCOME payload")
    yield* exactKeys(input, ["state", "trace", "outcome"], "APPLY_OUTCOME payload")
    const recovered = yield* recoverMount(fs, root, input["state"])
    if (recovered.metadata.mountRole !== "FULL_TRAINABLE") return yield* Effect.fail(refuse("only the immutable FULL trainable mount role may consume an outcome"))
    const trace = yield* parseWireTrace(input["trace"])
    const binding = recovered.metadata.contexts.find((context) => context.contextKey === trace.context_key)
    if (binding === undefined || trace.context_sha256 !== binding.contextSha256 || trace.context_sha256 !== contextSha256(trace.context_key) || trace.stratum !== binding.stratum || !recovered.metadata.routeIds.includes(trace.selected_route_id) || trace.routing_payload_sha256 !== recovered.state.state_sha256) {
      return yield* Effect.fail(refuse("trace does not exactly bind the supplied fresh routing state"))
    }
    const training = recovered.metadata.training.find((episode) => episode.episodeId === trace.episode_id)
    if (training === undefined || training.contextKey !== trace.context_key || training.selectedRouteId !== trace.selected_route_id) {
      return yield* Effect.fail(refuse("only one exact registered forced-training trace may create a local experimental credit successor; heldout traces remain read-only"))
    }
    const path = yield* mountPath(root, recovered.metadata.mountId)
    const alreadyCreditedEpisodes = yield* creditedEpisodeIds(path)
    if (alreadyCreditedEpisodes.includes(trace.episode_id)) {
      return yield* Effect.fail(refuse("one registered training episode may produce at most one local experimental credit successor"))
    }
    const outcome = yield* parseOutcome(input["outcome"], config)
    if (outcome.episodeId !== trace.episode_id || outcome.routeId !== trace.selected_route_id) return yield* Effect.fail(refuse("outcome episode/route does not match sealed trace"))
    const reconstructedTrace = validateDnrdEligibilityTrace(traceFromWire(trace))
    if (Either.isLeft(reconstructedTrace)) return yield* Effect.fail(refuse(`trace wire does not reproduce a valid sealed trace: ${reconstructedTrace.left.detail}`))
    const observation = makeDnrdOutcomeObservation({ traceId: trace.trace_id, producerAddress: PRODUCER_ADDRESS, scorerAddress: SCORER_ADDRESS, scorerProvenanceAddress: SCORER_PROVENANCE_ADDRESS, scorerSourceSha256: outcome.scorerSourceIdentity, outcomeScoreMicros: outcome.reward, scorerObservationSha256: outcome.digest })
    if (Either.isLeft(observation)) return yield* Effect.fail(refuse(`outcome observation cannot be sealed: ${observation.left.detail}`))
    const consumed = yield* consumedOutcomeIds(path)
    const credit = applyDnrdCreditUpdate({ payload: recovered.payload, trace: reconstructedTrace.right, outcome: observation.right, consumedOutcomeIds: consumed, learningRateMicros: 100_000, scoreLimitMicros: 100_000 })
    if (Either.isLeft(credit)) return yield* Effect.fail(refuse(`outcome cannot produce a frozen local experimental credit update: ${credit.left.detail}`))
    // The durable adapter resolves and revalidates the matching sealed trace by
    // traceId; reconstructedTrace above additionally binds all wire fields.
    yield* applyAdapterOutcome(path, observation.right)
    const after = yield* recoverAdapter(path)
    if (after.payloadSha256 !== credit.right.receipt.afterPayloadSha256) return yield* Effect.fail(refuse("durable successor payload does not equal the exact frozen credit receipt"))
    const state = yield* makeState(recovered.metadata, after)
    return Object.freeze({ state, receipt: {
      credit_receipt: credit.right.receipt,
      observation: observation.right,
      scorer_provenance: {
        scorer_address: outcome.scorerAddress,
        scorer_source_identity: outcome.scorerSourceIdentity,
        role_separation: outcome.roleSeparation
      },
      status: "LOCAL_EXPERIMENTAL_STRUCTURAL_OUTCOME_RECEIPT_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING"
    } })
  })

const handleRecover = (fs: PosixFileSystemShape, root: ProcessRoot, payload: unknown): Effect.Effect<JsonObject, DnrdRoutingDiagnosticProcessError> =>
  Effect.gen(function* () {
    const input = yield* asObject(payload, "RECOVER payload")
    yield* exactKeys(input, ["state"], "RECOVER payload")
    const recovered = yield* recoverMount(fs, root, input["state"])
    const routingPayloadBytes = yield* canonicalBytes(recovered.payload)
    return Object.freeze({
      state: recovered.state,
      journal_sha256: recovered.journalSha256,
      recovered: true,
      fresh_process: true,
      process_instance_id: PROCESS_INSTANCE_ID,
      mount_role: recovered.metadata.mountRole,
      routing_payload_utf8: new TextDecoder().decode(routingPayloadBytes),
      routing_payload_sha256: sha256(routingPayloadBytes),
      routing_payload_bytes: routingPayloadBytes.byteLength
    })
  })

// ---------------------------------------------------------------------------
// The process program and its single boundary
// ---------------------------------------------------------------------------

/** Executes one strict request. Its return is intentionally local structural data only. */
export const executeDnrdRoutingDiagnosticProcess = (
  request: unknown
): Effect.Effect<JsonObject, DnrdRoutingDiagnosticProcessError, PosixFileSystem> =>
  Effect.gen(function* () {
    const fs = yield* PosixFileSystem
    const input = yield* asObject(request, "DNRD subprocess request")
    yield* exactKeys(input, ["operation", "implementation_path", "implementation_sha256", "config", "config_sha256", "payload"], "DNRD subprocess request")
    const operation = yield* parseOperation(input["operation"])
    yield* assertImplementationBinding(fs, input["implementation_path"], input["implementation_sha256"])
    const config = yield* parseConfig(input["config"])
    const configSha256 = yield* requiredSha256(input["config_sha256"], "config_sha256")
    const pythonConfig = yield* pythonJson(input["config"])
    if (configSha256 !== sha256(pythonConfig)) return yield* Effect.fail(refuse("config_sha256 does not bind the exact Python bridge configuration"))
    const root = yield* prepareDedicatedRoot(fs, config)
    switch (operation) {
      case "INIT_STREAM": return yield* handleInitialize(fs, root, input["payload"])
      case "MATERIALIZE_CONTROL": return yield* handleMaterializeControl(fs, root, input["payload"])
      case "SEAL_TRACE": return Object.freeze({ ...(yield* handleSealTrace(fs, root, input["payload"])) })
      case "APPLY_OUTCOME": return yield* handleApplyOutcome(fs, config, root, input["payload"])
      case "RECOVER": return yield* handleRecover(fs, root, input["payload"])
    }
  })

/** One stderr line per failure, rendered exactly as the former Promise boundary rendered it. */
export const describeDnrdRoutingDiagnosticProcessFailure = (error: DnrdRoutingDiagnosticProcessError): string =>
  error._tag === "ProcessRefusal" || error._tag === "PosixIoError"
    ? error.detail
    : Cause.prettyErrors(error.cause)[0]?.message ?? "unknown DNRD process refusal"

/**
 * The DNRD stdin refusal string predates the shared process main, so stdin is
 * checked here before the shared decoder sees it; the shared decoder then
 * cannot refuse a source this check accepted.
 */
const dnrdProcessIo = (stdin: string | undefined): ProcessIo => Object.freeze({
  ...nodeProcessIo,
  readStdin: (maximumBytes: number) => (stdin === undefined ? readNodeStdin(maximumBytes) : Effect.succeed(stdin)).pipe(
    Effect.filterOrFail(
      (source) => Either.isRight(decodeCanonicalJsonBytes(new TextEncoder().encode(source))),
      () => refuse(STDIN_REFUSAL)
    )
  )
})

/** Runs one request end to end; a supplied `stdin` string replaces the Node stdin reader. */
export const runDnrdRoutingDiagnosticProcess = (stdin?: string): Promise<number> =>
  runProcessMain({
    refusalPrefix: "DNRD_ROUTING_DIAGNOSTIC_PROCESS_REFUSED",
    maximumStdinBytes: MAX_FILE_BYTES,
    program: (request) => Effect.map(executeDnrdRoutingDiagnosticProcess(request), (reply) => reply as CanonicalJson),
    describeFailure: describeDnrdRoutingDiagnosticProcessFailure
  }, dnrdProcessIo(stdin))

const invokedPath = process.argv[1]
if (invokedPath !== undefined && import.meta.url === pathToFileURL(invokedPath).href) {
  void runDnrdRoutingDiagnosticProcess().then((exitCode) => { process.exitCode = exitCode })
}
