/**
 * One-request DNRD subprocess bridge.
 *
 * This is a local experimental structural adapter. It does not issue a
 * canonical Permit, establish admission, prove scorer independence, or claim
 * learning/scientific efficacy. Every invocation consumes one JSON object on
 * stdin, emits one JSON object on stdout, and exits.
 */
import { createHash, randomUUID } from "node:crypto"
import { constants } from "node:fs"
import { chmod, link, lstat, mkdir, open, readdir, readFile } from "node:fs/promises"
import { dirname, isAbsolute, join, relative, resolve } from "node:path"
import { pathToFileURL } from "node:url"

import { Effect, Either, Layer } from "effect"

import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
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

class ProcessRefusal extends Error {
  constructor(readonly detail: string) {
    super(detail)
    this.name = "DnrdRoutingDiagnosticProcessRefusal"
  }
}

const sha256 = (value: Uint8Array | string): string =>
  createHash("sha256").update(value).digest("hex")

const contextSha256 = (contextKey: string): string => sha256(Buffer.from(contextKey, "utf8"))

const asObject = (value: unknown, label: string): JsonObject => {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ProcessRefusal(`${label} must be an object`)
  }
  return value as JsonObject
}

const exactKeys = (value: JsonObject, keys: ReadonlyArray<string>, label: string): void => {
  const actual = Object.keys(value).sort()
  const expected = [...keys].sort()
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    throw new ProcessRefusal(`${label} has missing or excess fields`)
  }
}

const requiredString = (value: unknown, label: string): string => {
  if (typeof value !== "string" || value.length === 0) throw new ProcessRefusal(`${label} must be a nonempty string`)
  return value
}

const requiredSha256 = (value: unknown, label: string): string => {
  const parsed = requiredString(value, label)
  if (!SHA256.test(parsed)) throw new ProcessRefusal(`${label} must be a lowercase SHA-256`)
  return parsed
}

const requiredIdentifier = (value: unknown, label: string): string => {
  const parsed = requiredString(value, label)
  if (!IDENTIFIER.test(parsed)) throw new ProcessRefusal(`${label} is not a DNRD identifier`)
  return parsed
}

const requiredInteger = (value: unknown, label: string): number => {
  if (typeof value !== "number" || !Number.isSafeInteger(value)) throw new ProcessRefusal(`${label} must be a safe integer`)
  return value
}

const requiredArray = (value: unknown, label: string): ReadonlyArray<unknown> => {
  if (!Array.isArray(value)) throw new ProcessRefusal(`${label} must be an array`)
  return value
}

const canonicalBytes = (value: unknown): Uint8Array => {
  const bytes = canonicalJsonBytes(value)
  if (Either.isLeft(bytes)) throw new ProcessRefusal("value cannot form canonical JSON")
  return Uint8Array.from(bytes.right)
}

/** Python task_family.commitment-compatible JSON for the ASCII request config. */
const pythonJson = (value: unknown): string => {
  if (value === null) return "null"
  if (value === true) return "true"
  if (value === false) return "false"
  if (typeof value === "string") {
    const encoded = JSON.stringify(value)
    if (encoded === undefined) throw new ProcessRefusal("configuration string is not JSON encodable")
    return encoded.replace(/[\u0080-\uFFFF]/g, (character) => `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`)
  }
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value) || Object.is(value, -0)) throw new ProcessRefusal("configuration number is not a canonical integer")
    return String(value)
  }
  if (Array.isArray(value)) return `[${value.map(pythonJson).join(",")}]`
  const object = asObject(value, "configuration value")
  return `{${Object.keys(object).sort().map((key) => `${pythonJson(key)}:${pythonJson(object[key])}`).join(",")}}`
}

const canonicalHash = (value: unknown): string => sha256(canonicalBytes(value))

const sameCanonical = (left: unknown, right: unknown): boolean => {
  const leftBytes = canonicalBytes(left)
  const rightBytes = canonicalBytes(right)
  return leftBytes.byteLength === rightBytes.byteLength && leftBytes.every((byte, index) => byte === rightBytes[index])
}

const exactCoreDerangementForBindings = (
  contexts: ReadonlyArray<ContextBinding>
): Readonly<Record<string, string>> => {
  const byStratum = new Map<string, ContextBinding[]>()
  for (const context of contexts) {
    const group = byStratum.get(context.stratum) ?? []
    group.push(context)
    byStratum.set(context.stratum, group)
  }
  const unsorted: Record<string, string> = Object.create(null)
  for (const stratum of [...byStratum.keys()].sort()) {
    const ordered = [...byStratum.get(stratum)!].sort((left, right) => left.contextSha256.localeCompare(right.contextSha256))
    if (ordered.length < 2) throw new ProcessRefusal("exact TS-core derangement is impossible for a one-context stratum")
    for (const [index, receiver] of ordered.entries()) {
      unsorted[receiver.contextKey] = ordered[(index + 1) % ordered.length]!.contextKey
    }
  }
  const canonical: Record<string, string> = Object.create(null)
  for (const receiver of Object.keys(unsorted).sort()) canonical[receiver] = unsorted[receiver]!
  return Object.freeze(canonical)
}

const parseRequestJson = (source: string): unknown => {
  const decoded = decodeCanonicalJsonBytes(new TextEncoder().encode(source))
  if (Either.isLeft(decoded)) throw new ProcessRefusal("stdin must contain one bounded JSON object without duplicate keys")
  return decoded.right
}

const parseConfig = (value: unknown): ProcessConfig => {
  const input = asObject(value, "config")
  exactKeys(input, ["root_path", "frozen_scorer_source_sha256"], "config")
  const rootPath = requiredString(input["root_path"], "config.root_path")
  if (!isAbsolute(rootPath)) throw new ProcessRefusal("config.root_path must be absolute")
  return Object.freeze({ rootPath: resolve(rootPath), frozenScorerSourceSha256: requiredSha256(input["frozen_scorer_source_sha256"], "config.frozen_scorer_source_sha256") })
}

const parseOperation = (value: unknown): Operation => {
  if (value === "INIT_STREAM" || value === "MATERIALIZE_CONTROL" || value === "SEAL_TRACE" || value === "APPLY_OUTCOME" || value === "RECOVER") return value
  throw new ProcessRefusal("operation is not a supported DNRD bridge operation")
}

const assertPlainPrivateDirectory = async (path: string, label: string): Promise<void> => {
  const stat = await lstat(path)
  if (stat.isSymbolicLink() || !stat.isDirectory() || (stat.mode & 0o777) !== 0o700) {
    throw new ProcessRefusal(`${label} must be a plain private 0700 directory`)
  }
}

const existsCode = (value: unknown): value is { readonly code: string } =>
  typeof value === "object" && value !== null && "code" in value && typeof value.code === "string"

const makePrivateChildDirectory = async (path: string, label: string): Promise<void> => {
  try {
    await mkdir(path, { mode: 0o700 })
  } catch (error) {
    if (!existsCode(error) || error.code !== "EEXIST") throw error
  }
  await assertPlainPrivateDirectory(path, label)
}

const prepareDedicatedRoot = async (config: ProcessConfig): Promise<ProcessRoot> => {
  await assertPlainPrivateDirectory(config.rootPath, "configured DNRD root")
  const mounts = join(config.rootPath, "mounts")
  const registry = join(config.rootPath, "registry")
  const streams = join(config.rootPath, "streams")
  const controls = join(config.rootPath, "controls")
  await makePrivateChildDirectory(mounts, "DNRD mounts root")
  await makePrivateChildDirectory(registry, "DNRD registry root")
  await makePrivateChildDirectory(streams, "DNRD stream-reservation root")
  await makePrivateChildDirectory(controls, "DNRD control-reservation root")
  const rootConfigPath = join(config.rootPath, "root-config.json")
  const rootConfigBytes = canonicalBytes({ schema_version: ROOT_CONFIG_SCHEMA, frozen_scorer_source_sha256: config.frozenScorerSourceSha256 })
  try {
    await writeImmutableNewFile(rootConfigPath, rootConfigBytes, "DNRD immutable root configuration")
  } catch (error) {
    if (!existsCode(error) || error.code !== "EEXIST") throw error
    const existing = await readImmutableFile(rootConfigPath, "DNRD immutable root configuration")
    if (existing.byteLength !== rootConfigBytes.byteLength || !existing.every((byte, index) => byte === rootConfigBytes[index])) {
      throw new ProcessRefusal("configured DNRD root is already frozen to a different scorer/configuration")
    }
  }
  return Object.freeze({ root: config.rootPath, mounts, registry, streams, controls, frozenScorerSourceSha256: config.frozenScorerSourceSha256 })
}

const mountPath = (root: { readonly mounts: string }, mountId: string): string => {
  if (!MOUNT_ID.test(mountId)) throw new ProcessRefusal("mount_id is not a process-owned opaque mount id")
  const path = resolve(root.mounts, mountId)
  if (dirname(path) !== resolve(root.mounts)) throw new ProcessRefusal("mount_id escapes the dedicated mounts root")
  return path
}

const registryPath = (root: { readonly registry: string }, mountId: string): string => {
  if (!MOUNT_ID.test(mountId)) throw new ProcessRefusal("mount_id is not a process-owned opaque mount id")
  const path = resolve(root.registry, `${mountId}.json`)
  if (dirname(path) !== resolve(root.registry)) throw new ProcessRefusal("mount_id escapes the dedicated registry root")
  return path
}

const readImmutableFile = async (path: string, label: string): Promise<Uint8Array> => {
  const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK)
  try {
    const before = await handle.stat()
    if (!before.isFile() || (before.mode & 0o777) !== 0o400 || before.size < 1 || before.size > MAX_FILE_BYTES) {
      throw new ProcessRefusal(`${label} must be a bounded immutable regular file`)
    }
    const bytes = new Uint8Array(await handle.readFile())
    const after = await handle.stat()
    if (bytes.byteLength !== before.size || after.dev !== before.dev || after.ino !== before.ino || after.size !== before.size) {
      throw new ProcessRefusal(`${label} changed during read`)
    }
    return bytes
  } finally {
    await handle.close()
  }
}

const writeImmutableNewFile = async (path: string, bytes: Uint8Array, label: string): Promise<void> => {
  const handle = await open(path, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600)
  try {
    await handle.writeFile(bytes)
    await handle.chmod(0o400)
    await handle.sync()
  } catch (error) {
    throw error instanceof ProcessRefusal ? error : new ProcessRefusal(`${label} could not be immutably published`)
  } finally {
    await handle.close()
  }
  await chmod(path, 0o400)
  const checked = await readImmutableFile(path, label)
  if (checked.byteLength !== bytes.byteLength || !checked.every((byte, index) => byte === bytes[index])) {
    throw new ProcessRefusal(`${label} immutable readback differs`)
  }
}

const reserveOnce = async (path: string, value: unknown, label: string): Promise<void> => {
  try {
    await writeImmutableNewFile(path, canonicalBytes(value), label)
  } catch (error) {
    if (existsCode(error) && error.code === "EEXIST") throw new ProcessRefusal(`${label} already exists; this occurrence cannot choose an alternate mount`)
    throw error
  }
}

const parseMetadata = (value: unknown): MountMetadata => {
  const input = asObject(value, "mount registry")
  exactKeys(input, ["schema_version", "mount_id", "mount_role", "source_mount_id", "source_state_sha256", "frozen_scorer_source_sha256", "stream_id", "route_ids", "contexts", "matched_derangement", "episodes", "training"], "mount registry")
  if (input["schema_version"] !== MOUNT_SCHEMA) throw new ProcessRefusal("mount registry schema is invalid")
  const mountId = requiredString(input["mount_id"], "mount registry.mount_id")
  if (!MOUNT_ID.test(mountId)) throw new ProcessRefusal("mount registry mount id is invalid")
  const mountRole = input["mount_role"]
  if (mountRole !== "W0_ROLLBACK" && mountRole !== "FULL_TRAINABLE" && mountRole !== "RAW_CONTROL" && mountRole !== "DERANGED_CONTROL") throw new ProcessRefusal("mount registry role is invalid")
  const rawSourceMountId = input["source_mount_id"]
  const rawSourceStateSha256 = input["source_state_sha256"]
  const sourceMountId = rawSourceMountId === null ? null : requiredString(rawSourceMountId, "mount registry.source_mount_id")
  const sourceStateSha256 = rawSourceStateSha256 === null ? null : requiredSha256(rawSourceStateSha256, "mount registry.source_state_sha256")
  if ((sourceMountId !== null && !MOUNT_ID.test(sourceMountId)) || (mountRole === "W0_ROLLBACK") !== (sourceMountId === null && sourceStateSha256 === null)) {
    throw new ProcessRefusal("mount registry source lineage does not match its immutable role")
  }
  if (mountRole !== "W0_ROLLBACK" && (sourceMountId === null || sourceStateSha256 === null)) throw new ProcessRefusal("non-W0 mount lacks exact source lineage")
  const frozenScorerSourceSha256 = requiredSha256(input["frozen_scorer_source_sha256"], "mount registry.frozen_scorer_source_sha256")
  const streamId = requiredIdentifier(input["stream_id"], "mount registry.stream_id")
  const routeIds = requiredArray(input["route_ids"], "mount registry.route_ids").map((route, index) => requiredIdentifier(route, `mount registry.route_ids[${index}]`))
  if (routeIds.length < 1 || routeIds.length > 256 || new Set(routeIds).size !== routeIds.length || [...routeIds].sort().some((route, index) => route !== routeIds[index])) {
    throw new ProcessRefusal("mount registry routes must be sorted and unique")
  }
  const contexts = requiredArray(input["contexts"], "mount registry.contexts").map((entry, index) => {
    const object = asObject(entry, `mount registry.contexts[${index}]`)
    exactKeys(object, ["context_key", "context_sha256", "stratum"], `mount registry.contexts[${index}]`)
    const contextKey = requiredString(object["context_key"], `mount registry.contexts[${index}].context_key`)
    const contextDigest = requiredSha256(object["context_sha256"], `mount registry.contexts[${index}].context_sha256`)
    const stratum = requiredIdentifier(object["stratum"], `mount registry.contexts[${index}].stratum`)
    if (contextDigest !== contextSha256(contextKey)) throw new ProcessRefusal("mount registry context hash differs from raw context key")
    return Object.freeze({ contextKey, contextSha256: contextDigest, stratum })
  })
  if (contexts.length < 1 || contexts.length > 256 || new Set(contexts.map((context) => context.contextKey)).size !== contexts.length || new Set(contexts.map((context) => context.contextSha256)).size !== contexts.length) {
    throw new ProcessRefusal("mount registry contexts are not unique")
  }
  const sortedContexts = [...contexts].sort((left, right) => `${left.stratum}\u0000${left.contextSha256}`.localeCompare(`${right.stratum}\u0000${right.contextSha256}`))
  if (sortedContexts.some((context, index) => context !== contexts[index])) throw new ProcessRefusal("mount registry contexts are not canonically sorted")
  const matchedInput = asObject(input["matched_derangement"], "mount registry.matched_derangement")
  const contextKeys = new Set(contexts.map((context) => context.contextKey))
  if (Object.keys(matchedInput).length !== contextKeys.size || Object.keys(matchedInput).some((receiver) => !contextKeys.has(receiver) || typeof matchedInput[receiver] !== "string" || !contextKeys.has(matchedInput[receiver] as string) || receiver === matchedInput[receiver]) || new Set(Object.values(matchedInput) as string[]).size !== contextKeys.size) {
    throw new ProcessRefusal("mount registry derangement is not an exact fixed-point-free context bijection")
  }
  const matchedDerangement: Record<string, string> = Object.create(null)
  for (const receiver of Object.keys(matchedInput).sort()) matchedDerangement[receiver] = matchedInput[receiver] as string
  if (!sameCanonical(matchedDerangement, exactCoreDerangementForBindings(contexts))) {
    throw new ProcessRefusal("mount registry derangement differs structurally from the exact TS-core SHA-ordered binding")
  }
  const episodes = requiredArray(input["episodes"], "mount registry.episodes").map((entry, index) => {
    const object = asObject(entry, `mount registry.episodes[${index}]`)
    exactKeys(object, ["episode_id", "context_key", "phase", "forced_route_id"], `mount registry.episodes[${index}]`)
    const phase = object["phase"]
    if (phase !== "training" && phase !== "heldout") throw new ProcessRefusal("mount registry episode phase is invalid")
    const forcedRouteId = object["forced_route_id"]
    if (phase === "training" && typeof forcedRouteId !== "string") throw new ProcessRefusal("training episode is missing forced route")
    if (phase === "heldout" && forcedRouteId !== null) throw new ProcessRefusal("heldout episode must not have a forced route")
    return Object.freeze({ episodeId: requiredIdentifier(object["episode_id"], `mount registry.episodes[${index}].episode_id`), contextKey: requiredString(object["context_key"], `mount registry.episodes[${index}].context_key`), phase, forcedRouteId: forcedRouteId === null ? null : requiredIdentifier(forcedRouteId, `mount registry.episodes[${index}].forced_route_id`) })
  })
  if (episodes.length !== 16 || new Set(episodes.map((entry) => entry.episodeId)).size !== episodes.length || episodes.some((entry) => !contexts.some((context) => context.contextKey === entry.contextKey) || (entry.forcedRouteId !== null && !routeIds.includes(entry.forcedRouteId)))) {
    throw new ProcessRefusal("mount registry episode support is invalid")
  }
  const training = requiredArray(input["training"], "mount registry.training").map((entry, index) => {
    const object = asObject(entry, `mount registry.training[${index}]`)
    exactKeys(object, ["episode_id", "context_key", "selected_route_id"], `mount registry.training[${index}]`)
    return Object.freeze({ episodeId: requiredIdentifier(object["episode_id"], `mount registry.training[${index}].episode_id`), contextKey: requiredString(object["context_key"], `mount registry.training[${index}].context_key`), selectedRouteId: requiredIdentifier(object["selected_route_id"], `mount registry.training[${index}].selected_route_id`) })
  })
  if (new Set(training.map((entry) => entry.episodeId)).size !== training.length || training.length !== 8 || training.some((entry) => !contexts.some((context) => context.contextKey === entry.contextKey) || !routeIds.includes(entry.selectedRouteId) || !episodes.some((episode) => episode.phase === "training" && episode.episodeId === entry.episodeId && episode.contextKey === entry.contextKey && episode.forcedRouteId === entry.selectedRouteId))) {
    throw new ProcessRefusal("mount registry training exposure support is invalid")
  }
  return Object.freeze({ schemaVersion: MOUNT_SCHEMA, mountId, mountRole, sourceMountId, sourceStateSha256, frozenScorerSourceSha256, streamId, routeIds: Object.freeze(routeIds), contexts: Object.freeze(contexts), matchedDerangement: Object.freeze(matchedDerangement), episodes: Object.freeze(episodes), training: Object.freeze(training) })
}

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

const writeMetadata = async (root: { readonly registry: string }, metadata: MountMetadata): Promise<void> => {
  await writeImmutableNewFile(registryPath(root, metadata.mountId), canonicalBytes(metadataWire(metadata)), "mount registry")
}

const loadMetadata = async (root: { readonly registry: string }, mountId: string): Promise<MountMetadata> => {
  const bytes = await readImmutableFile(registryPath(root, mountId), "mount registry")
  const decoded = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(decoded)) throw new ProcessRefusal("mount registry is not canonical JSON")
  const metadata = parseMetadata(decoded.right)
  if (metadata.mountId !== mountId) throw new ProcessRefusal("mount registry identity does not match requested mount")
  return metadata
}

const payloadFromScores = (metadata: Pick<MountMetadata, "contexts" | "routeIds">, scores: Readonly<Record<string, Readonly<Record<string, number>>>>): DnrdRoutingPayload => {
  const expectedContextKeys = new Set(metadata.contexts.map((context) => context.contextKey))
  const actualContextKeys = Object.keys(scores)
  if (actualContextKeys.length !== expectedContextKeys.size || actualContextKeys.some((context) => !expectedContextKeys.has(context))) {
    throw new ProcessRefusal("state scores do not have exact raw context support")
  }
  const contexts = metadata.contexts.map((context) => {
    const routes = scores[context.contextKey]
    if (routes === undefined) throw new ProcessRefusal("state score context is absent")
    const actualRoutes = Object.keys(routes)
    if (actualRoutes.length !== metadata.routeIds.length || actualRoutes.some((route) => !metadata.routeIds.includes(route))) {
      throw new ProcessRefusal("state scores do not have exact route support")
    }
    return Object.freeze({
      contextSha256: context.contextSha256,
      stratum: context.stratum,
      routes: metadata.routeIds.map((routeId) => {
        const scoreMicros = requiredInteger(routes[routeId], `state score ${context.contextKey}/${routeId}`)
        if (scoreMicros < -DNRD_SCORE_MICROS_LIMIT || scoreMicros > DNRD_SCORE_MICROS_LIMIT) throw new ProcessRefusal("state score is outside frozen signed-micros bounds")
        return Object.freeze({ routeId, scoreMicros })
      })
    })
  })
  const payload = { schemaVersion: DNRD_ROUTING_PAYLOAD_V1, contexts: Object.freeze(contexts), structuralStatus: "LOCAL_EXPERIMENTAL_ROUTING_PAYLOAD_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING" as const }
  const checked = validateDnrdRoutingPayload(payload)
  if (Either.isLeft(checked)) throw new ProcessRefusal(`routing payload is invalid: ${checked.left.detail}`)
  return checked.right
}

const scoresFromPayload = (metadata: MountMetadata, payload: DnrdRoutingPayload): Readonly<Record<string, Readonly<Record<string, number>>>> => {
  const scores: Record<string, Readonly<Record<string, number>>> = Object.create(null)
  for (const binding of metadata.contexts) {
    const context = payload.contexts.find((candidate) => candidate.contextSha256 === binding.contextSha256 && candidate.stratum === binding.stratum)
    if (context === undefined) throw new ProcessRefusal("durable payload lacks a registered raw context")
    if (context.routes.length !== metadata.routeIds.length || context.routes.some((route) => !metadata.routeIds.includes(route.routeId))) {
      throw new ProcessRefusal("durable payload route support differs from mount registry")
    }
    const routeScores: Record<string, number> = Object.create(null)
    for (const routeId of metadata.routeIds) {
      const route = context.routes.find((candidate) => candidate.routeId === routeId)
      if (route === undefined) throw new ProcessRefusal("durable payload route is absent")
      routeScores[routeId] = route.scoreMicros
    }
    scores[binding.contextKey] = Object.freeze(routeScores)
  }
  if (payload.contexts.length !== metadata.contexts.length) throw new ProcessRefusal("durable payload has an unregistered context")
  return Object.freeze(scores)
}

const recoverAdapter = async (path: string): Promise<{ readonly payload: DnrdRoutingPayload; readonly payloadSha256: string; readonly journalSha256: string; readonly routingRevision: string }> => {
  const layer = makeDnrdRoutingDiagnosticFileLayer(path) as Layer.Layer<DnrdRoutingDiagnosticFile, never, never>
  const program = Effect.gen(function* () {
    const adapter = yield* DnrdRoutingDiagnosticFile
    const recovered = (yield* adapter.recover) as { readonly payload: DnrdRoutingPayload; readonly payloadSha256: string; readonly journalHead: { readonly sha256: string } }
    const snapshot = (yield* adapter.snapshot) as { readonly canonical: { readonly atoms: ReadonlyArray<{ readonly kind: string; readonly key: { readonly revisionId: number } }> } }
    const routing = snapshot.canonical.atoms.filter((atom) => atom.kind === "dnrd:routing-disposition").sort((left, right) => right.key.revisionId - left.key.revisionId)[0]
    if (routing === undefined) throw new ProcessRefusal("durable mount has no routing disposition")
    return Object.freeze({ payload: recovered.payload, payloadSha256: recovered.payloadSha256, journalSha256: recovered.journalHead.sha256, routingRevision: String(routing.key.revisionId) })
  }).pipe(Effect.provide(layer))
  return Effect.runPromise(program as Effect.Effect<{ readonly payload: DnrdRoutingPayload; readonly payloadSha256: string; readonly journalSha256: string; readonly routingRevision: string }, unknown, never>)
}

const initializeAdapter = async (path: string, payload: DnrdRoutingPayload): Promise<void> => {
  const layer = makeDnrdRoutingDiagnosticFileLayer(path) as Layer.Layer<DnrdRoutingDiagnosticFile, never, never>
  const program = Effect.gen(function* () {
    const adapter = yield* DnrdRoutingDiagnosticFile
    yield* adapter.initialize(payload)
  }).pipe(Effect.provide(layer))
  await Effect.runPromise(program as Effect.Effect<void, unknown, never>)
}

const sealAdapterTrace = async (path: string, input: { readonly episodeId: string; readonly contextSha256: string; readonly routeId: string; readonly requestSha256: string; readonly responseSha256: string }): Promise<DnrdEligibilityTrace> => {
  const layer = makeDnrdRoutingDiagnosticFileLayer(path) as Layer.Layer<DnrdRoutingDiagnosticFile, never, never>
  const program = Effect.gen(function* () {
    const adapter = yield* DnrdRoutingDiagnosticFile
    return yield* adapter.sealTrainingTrajectory(input)
  }).pipe(Effect.provide(layer))
  return Effect.runPromise(program as Effect.Effect<DnrdEligibilityTrace, unknown, never>)
}

const applyAdapterOutcome = async (path: string, outcome: DnrdOutcomeObservation): Promise<unknown> => {
  const layer = makeDnrdRoutingDiagnosticFileLayer(path) as Layer.Layer<DnrdRoutingDiagnosticFile, never, never>
  const program = Effect.gen(function* () {
    const adapter = yield* DnrdRoutingDiagnosticFile
    return yield* adapter.applyOutcome(outcome, 100_000, 100_000)
  }).pipe(Effect.provide(layer))
  return Effect.runPromise(program as Effect.Effect<unknown, unknown, never>)
}

const consumedOutcomeIds = async (path: string): Promise<ReadonlyArray<string>> => {
  const layer = makeDnrdRoutingDiagnosticFileLayer(path) as Layer.Layer<DnrdRoutingDiagnosticFile, never, never>
  const program = Effect.gen(function* () {
    const adapter = yield* DnrdRoutingDiagnosticFile
    const snapshot = (yield* adapter.snapshot) as { readonly canonical: { readonly atoms: ReadonlyArray<{ readonly kind: string; readonly key: { readonly atomUid: string } }> } }
    const ids = snapshot.canonical.atoms.filter((atom) => atom.kind === "dnrd:outcome").map((atom) => {
      const prefix = "dnrd:outcome:"
      if (!atom.key.atomUid.startsWith(prefix)) throw new ProcessRefusal("durable outcome atom uid does not have DNRD outcome identity")
      return atom.key.atomUid.slice(prefix.length)
    }).sort()
    if (ids.some((id, index) => !SHA256.test(id) || (index > 0 && ids[index - 1] === id))) throw new ProcessRefusal("durable outcome atom identities are not sorted unique SHA-256 values")
    return Object.freeze(ids)
  }).pipe(Effect.provide(layer))
  return Effect.runPromise(program as Effect.Effect<ReadonlyArray<string>, unknown, never>)
}

const creditedEpisodeIds = async (path: string): Promise<ReadonlyArray<string>> => {
  const layer = makeDnrdRoutingDiagnosticFileLayer(path) as Layer.Layer<DnrdRoutingDiagnosticFile, never, never>
  const program = Effect.gen(function* () {
    const adapter = yield* DnrdRoutingDiagnosticFile
    return yield* adapter.creditedEpisodeIds
  }).pipe(Effect.provide(layer))
  return Effect.runPromise(program as Effect.Effect<ReadonlyArray<string>, unknown, never>)
}

const makeState = (metadata: MountMetadata, recovered: { readonly payload: DnrdRoutingPayload; readonly payloadSha256: string; readonly routingRevision: string }): RoutingStateWire => Object.freeze({
  state_sha256: recovered.payloadSha256,
  revision_id: recovered.routingRevision,
  lineage_id: DNRD_FILE_LINEAGE,
  owner_id: ROUTING_OWNER,
  mount_id: metadata.mountId,
  mount_role: metadata.mountRole,
  immutable: true,
  scores: scoresFromPayload(metadata, recovered.payload)
})

const parseStateWire = (value: unknown): RoutingStateWire => {
  const input = asObject(value, "state")
  exactKeys(input, ["state_sha256", "revision_id", "lineage_id", "owner_id", "mount_id", "mount_role", "immutable", "scores"], "state")
  const stateSha256 = requiredSha256(input["state_sha256"], "state.state_sha256")
  const revisionId = requiredString(input["revision_id"], "state.revision_id")
  if (!/^(0|[1-9][0-9]*)$/.test(revisionId)) throw new ProcessRefusal("state.revision_id must be a nonnegative decimal routing revision")
  if (input["lineage_id"] !== DNRD_FILE_LINEAGE || input["owner_id"] !== ROUTING_OWNER || input["immutable"] !== true) {
    throw new ProcessRefusal("state has a non-DNRD lineage, owner, or mutability claim")
  }
  const mountId = requiredString(input["mount_id"], "state.mount_id")
  if (!MOUNT_ID.test(mountId)) throw new ProcessRefusal("state.mount_id is invalid")
  const mountRole = input["mount_role"]
  if (mountRole !== "W0_ROLLBACK" && mountRole !== "FULL_TRAINABLE" && mountRole !== "RAW_CONTROL" && mountRole !== "DERANGED_CONTROL") {
    throw new ProcessRefusal("state.mount_role is invalid")
  }
  const scoresInput = asObject(input["scores"], "state.scores")
  const scores: Record<string, Readonly<Record<string, number>>> = Object.create(null)
  for (const contextKey of Object.keys(scoresInput)) {
    const routesInput = asObject(scoresInput[contextKey], `state.scores.${contextKey}`)
    const routes: Record<string, number> = Object.create(null)
    for (const routeId of Object.keys(routesInput)) routes[routeId] = requiredInteger(routesInput[routeId], `state.scores.${contextKey}.${routeId}`)
    scores[contextKey] = Object.freeze(routes)
  }
  return Object.freeze({ state_sha256: stateSha256, revision_id: revisionId, lineage_id: DNRD_FILE_LINEAGE, owner_id: ROUTING_OWNER, mount_id: mountId, mount_role: mountRole, immutable: true, scores: Object.freeze(scores) })
}

const recoverMount = async (root: ProcessRoot, supplied: unknown): Promise<RecoveredMount> => {
  const requested = parseStateWire(supplied)
  const metadata = await loadMetadata(root, requested.mount_id)
  if (metadata.frozenScorerSourceSha256 !== root.frozenScorerSourceSha256) throw new ProcessRefusal("mount scorer identity differs from the immutable root configuration")
  const path = mountPath(root, requested.mount_id)
  await assertPlainPrivateDirectory(path, "DNRD mount")
  const recovered = await recoverAdapter(path)
  const payloadDigest = dnrdRoutingPayloadSha256(recovered.payload)
  if (Either.isLeft(payloadDigest) || payloadDigest.right !== recovered.payloadSha256) throw new ProcessRefusal("fresh recovery payload digest is invalid")
  const expected = makeState(metadata, recovered)
  if (!sameCanonical(requested, expected)) throw new ProcessRefusal("supplied state does not exactly match fresh local experimental recovery")
  return Object.freeze({ metadata, payload: recovered.payload, state: expected, journalSha256: recovered.journalSha256 })
}

const randomMountId = (): string => `${MOUNT_PREFIX}${randomUUID()}`

const createBootstrapMount = async (root: { readonly mounts: string; readonly registry: string }, metadataWithoutId: Omit<MountMetadata, "mountId">, payload: DnrdRoutingPayload): Promise<RecoveredMount> => {
  const mountId = randomMountId()
  const path = mountPath(root, mountId)
  try {
    await mkdir(path, { mode: 0o700 })
  } catch (error) {
    if (existsCode(error) && error.code === "EEXIST") throw new ProcessRefusal("random mount id unexpectedly already exists")
    throw error
  }
  await assertPlainPrivateDirectory(path, "new DNRD mount")
  await initializeAdapter(path, payload)
  const metadata: MountMetadata = Object.freeze({ ...metadataWithoutId, mountId })
  await writeMetadata(root, metadata)
  const recovered = await recoverAdapter(path)
  const state = makeState(metadata, recovered)
  return Object.freeze({ metadata, payload: recovered.payload, state, journalSha256: recovered.journalSha256 })
}

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

interface TreeEntry { readonly path: string; readonly mode: number; readonly sha256: string; readonly byteLength: number; readonly device: number; readonly inode: number }

const treeManifest = (entries: ReadonlyArray<TreeEntry>): ReadonlyArray<Readonly<{ path: string; mode: number; sha256: string; byteLength: number }>> =>
  Object.freeze(entries.map((entry) => Object.freeze({ path: entry.path, mode: entry.mode, sha256: entry.sha256, byteLength: entry.byteLength })))

const collectImmutableTree = async (root: string, current = root): Promise<ReadonlyArray<TreeEntry>> => {
  const stat = await lstat(current)
  if (stat.isSymbolicLink() || !stat.isDirectory() || (stat.mode & 0o777) !== 0o700) throw new ProcessRefusal("mount tree contains an unsafe directory")
  const entries: TreeEntry[] = []
  for (const name of (await readdir(current)).sort()) {
    if (!/^[A-Za-z0-9._-]{1,256}$/.test(name)) throw new ProcessRefusal("mount tree entry has an unsafe name")
    const path = join(current, name)
    const child = await lstat(path)
    if (child.isSymbolicLink()) throw new ProcessRefusal("mount tree contains a symlink")
    if (child.isDirectory()) {
      entries.push(...await collectImmutableTree(root, path))
    } else if (child.isFile()) {
      const bytes = await readImmutableFile(path, "mount tree entry")
      entries.push(Object.freeze({ path: relative(root, path), mode: child.mode & 0o777, sha256: sha256(bytes), byteLength: bytes.byteLength, device: child.dev, inode: child.ino }))
    } else {
      throw new ProcessRefusal("mount tree contains a nonregular file")
    }
  }
  return Object.freeze(entries.sort((left, right) => left.path.localeCompare(right.path)))
}

const copyImmutableTree = async (source: string, destination: string): Promise<void> => {
  const sourceEntries = await collectImmutableTree(source)
  try {
    await mkdir(destination, { mode: 0o700 })
  } catch (error) {
    if (existsCode(error) && error.code === "EEXIST") throw new ProcessRefusal("destination mount already exists; process never overwrites it")
    throw error
  }
  await assertPlainPrivateDirectory(destination, "copied DNRD mount")
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
    await mkdir(target, { mode: 0o700 })
    await assertPlainPrivateDirectory(target, "copied DNRD mount directory")
  }
  const copiedBySourceIdentity = new Map<string, string>()
  for (const entry of sourceEntries) {
    const bytes = await readImmutableFile(join(source, entry.path), "source mount file")
    if (sha256(bytes) !== entry.sha256 || bytes.byteLength !== entry.byteLength || entry.mode !== 0o400) throw new ProcessRefusal("source mount tree changed during copy")
    const target = join(destination, entry.path)
    const sourceIdentity = `${entry.device}:${entry.inode}`
    const firstTarget = copiedBySourceIdentity.get(sourceIdentity)
    if (firstTarget === undefined) {
      await writeImmutableNewFile(target, bytes, "copied mount file")
      copiedBySourceIdentity.set(sourceIdentity, target)
    } else {
      await link(firstTarget, target)
      const linked = await readImmutableFile(target, "copied hard-linked mount file")
      if (linked.byteLength !== bytes.byteLength || !linked.every((byte, index) => byte === bytes[index])) throw new ProcessRefusal("copied mount hard link differs from source bytes")
    }
  }
  const copied = await collectImmutableTree(destination)
  if (!sameCanonical(treeManifest(sourceEntries), treeManifest(copied))) throw new ProcessRefusal("copied mount tree does not exactly equal source prefix")
}

const parseStream = (value: unknown): { readonly metadata: MountBaseMetadata; readonly zeroPayload: DnrdRoutingPayload } => {
  const stream = asObject(value, "stream")
  exactKeys(stream, ["stream_id", "route_ids", "context_keys", "matched_derangement", "training", "heldout"], "stream")
  const streamId = requiredIdentifier(stream["stream_id"], "stream.stream_id")
  const routeIds = requiredArray(stream["route_ids"], "stream.route_ids").map((route, index) => requiredIdentifier(route, `stream.route_ids[${index}]`))
  if (routeIds.length !== 2 || new Set(routeIds).size !== routeIds.length) throw new ProcessRefusal("stream must contain exactly two unique routes")
  const sortedRoutes = [...routeIds].sort()
  const contextKeys = requiredArray(stream["context_keys"], "stream.context_keys").map((context, index) => requiredString(context, `stream.context_keys[${index}]`))
  if (contextKeys.length !== 4 || new Set(contextKeys).size !== contextKeys.length) throw new ProcessRefusal("stream must contain exactly four unique contexts")
  const stratum = `stratum:${sha256(streamId)}`
  const contexts = contextKeys.map((contextKey) => Object.freeze({ contextKey, contextSha256: contextSha256(contextKey), stratum })).sort((left, right) => `${left.stratum}\u0000${left.contextSha256}`.localeCompare(`${right.stratum}\u0000${right.contextSha256}`))
  const contextSet = new Set(contextKeys)
  const mapping = asObject(stream["matched_derangement"], "stream.matched_derangement")
  if (Object.keys(mapping).length !== contextKeys.length || Object.keys(mapping).some((source) => !contextSet.has(source) || typeof mapping[source] !== "string" || !contextSet.has(mapping[source] as string) || source === mapping[source])) {
    throw new ProcessRefusal("stream matched_derangement is not a fixed-point-free context binding")
  }
  if (new Set(Object.values(mapping) as string[]).size !== contextKeys.length) throw new ProcessRefusal("stream matched_derangement is not a bijection")
  const matchedDerangement: Record<string, string> = Object.create(null)
  for (const receiver of Object.keys(mapping).sort()) matchedDerangement[receiver] = mapping[receiver] as string
  if (!sameCanonical(matchedDerangement, exactCoreDerangementForBindings(contexts))) {
    throw new ProcessRefusal("stream matched_derangement differs structurally from the exact TS-core SHA-ordered binding")
  }
  const parseEpisode = (entry: unknown, phase: "training" | "heldout", index: number): EpisodeExposure => {
    const episode = asObject(entry, `stream.${phase}[${index}]`)
    const keys = phase === "training"
      ? ["episode_id", "stream_id", "phase", "context_key", "candidate_route_ids", "entity", "aliases", "surface_template", "prompt", "route_evidence", "forced_route_id", "provenance_canary"]
      : ["episode_id", "stream_id", "phase", "context_key", "candidate_route_ids", "entity", "aliases", "surface_template", "prompt", "route_evidence", "arm_order"]
    exactKeys(episode, keys, `stream.${phase}[${index}]`)
    const episodeId = requiredIdentifier(episode["episode_id"], `stream.${phase}[${index}].episode_id`)
    if (episode["stream_id"] !== streamId || episode["phase"] !== phase) throw new ProcessRefusal(`stream.${phase}[${index}] has a mismatched stream or phase`)
    const contextKey = requiredString(episode["context_key"], `stream.${phase}[${index}].context_key`)
    if (!contextSet.has(contextKey)) throw new ProcessRefusal(`stream.${phase}[${index}] has unknown context support`)
    const candidates = requiredArray(episode["candidate_route_ids"], `stream.${phase}[${index}].candidate_route_ids`)
    if (candidates.length !== routeIds.length || new Set(candidates).size !== routeIds.length || candidates.some((route) => typeof route !== "string" || !routeIds.includes(route))) throw new ProcessRefusal(`stream.${phase}[${index}] candidate route support differs`)
    requiredString(episode["entity"], `stream.${phase}[${index}].entity`)
    requiredString(episode["surface_template"], `stream.${phase}[${index}].surface_template`)
    const prompt = requiredString(episode["prompt"], `stream.${phase}[${index}].prompt`)
    const aliases = requiredArray(episode["aliases"], `stream.${phase}[${index}].aliases`)
    if (aliases.length !== 2 || new Set(aliases).size !== 2) throw new ProcessRefusal(`stream.${phase}[${index}] aliases differ from frozen two-alias shape`)
    aliases.forEach((alias, aliasIndex) => { requiredString(alias, `stream.${phase}[${index}].aliases[${aliasIndex}]`) })
    const evidence = requiredArray(episode["route_evidence"], `stream.${phase}[${index}].route_evidence`)
    if (evidence.length !== routeIds.length) throw new ProcessRefusal(`stream.${phase}[${index}] evidence count differs from route support`)
    const evidenceRoutes = new Set<string>()
    evidence.forEach((entryEvidence, evidenceIndex) => {
      const evidenceObject = asObject(entryEvidence, `stream.${phase}[${index}].route_evidence[${evidenceIndex}]`)
      exactKeys(evidenceObject, ["route_id", "evidence_text", "response_token"], `stream.${phase}[${index}].route_evidence[${evidenceIndex}]`)
      const evidenceRoute = requiredIdentifier(evidenceObject["route_id"], `stream.${phase}[${index}].route_evidence[${evidenceIndex}].route_id`)
      if (!routeIds.includes(evidenceRoute) || evidenceRoutes.has(evidenceRoute)) throw new ProcessRefusal(`stream.${phase}[${index}] evidence route support differs`)
      evidenceRoutes.add(evidenceRoute)
      requiredString(evidenceObject["evidence_text"], `stream.${phase}[${index}].route_evidence[${evidenceIndex}].evidence_text`)
      requiredString(evidenceObject["response_token"], `stream.${phase}[${index}].route_evidence[${evidenceIndex}].response_token`)
    })
    if (phase === "training") {
      const route = requiredIdentifier(episode["forced_route_id"], `stream.training[${index}].forced_route_id`)
      const canary = requiredString(episode["provenance_canary"], `stream.training[${index}].provenance_canary`)
      if (!/^dnrd-training-provenance:[0-9a-f]{32}$/.test(canary) || !prompt.includes(canary)) {
        throw new ProcessRefusal("training provenance canary is malformed or absent from its prompt")
      }
      if (!routeIds.includes(route)) throw new ProcessRefusal("training forced route is outside stream route support")
      return Object.freeze({ episodeId, contextKey, phase, forcedRouteId: route })
    }
    const armOrder = requiredArray(episode["arm_order"], `stream.heldout[${index}].arm_order`)
    const arms = ["FULL", "NO_MEMORY_ROLLBACK", "BINDING_DERANGED_NUMERIC_PLACEBO"]
    if (armOrder.length !== arms.length || new Set(armOrder).size !== arms.length || armOrder.some((arm) => typeof arm !== "string" || !arms.includes(arm))) throw new ProcessRefusal("heldout arm order differs from frozen arm set")
    return Object.freeze({ episodeId, contextKey, phase, forcedRouteId: null })
  }
  const trainingValues = requiredArray(stream["training"], "stream.training")
  const heldoutValues = requiredArray(stream["heldout"], "stream.heldout")
  if (trainingValues.length !== 8 || heldoutValues.length !== 8) throw new ProcessRefusal("stream must contain exactly eight training and eight heldout episodes")
  const episodes = [...trainingValues.map((entry, index) => parseEpisode(entry, "training", index)), ...heldoutValues.map((entry, index) => parseEpisode(entry, "heldout", index))]
  if (new Set(episodes.map((entry) => entry.episodeId)).size !== 16) throw new ProcessRefusal("stream episode ids are not unique")
  const training = episodes.filter((entry): entry is EpisodeExposure & { readonly forcedRouteId: string } => entry.phase === "training").map((entry) => Object.freeze({ episodeId: entry.episodeId, contextKey: entry.contextKey, selectedRouteId: entry.forcedRouteId }))
  const metadata = Object.freeze({ schemaVersion: MOUNT_SCHEMA, streamId, routeIds: Object.freeze(sortedRoutes), contexts: Object.freeze(contexts), matchedDerangement: Object.freeze(matchedDerangement), episodes: Object.freeze(episodes), training: Object.freeze(training) })
  const zeroScores: Record<string, Readonly<Record<string, number>>> = Object.create(null)
  for (const context of contexts) {
    const routes: Record<string, number> = Object.create(null)
    for (const routeId of sortedRoutes) routes[routeId] = 0
    zeroScores[context.contextKey] = Object.freeze(routes)
  }
  return Object.freeze({ metadata, zeroPayload: payloadFromScores(metadata, zeroScores) })
}

const parseWireTrace = (value: unknown): WireTrace => {
  const trace = asObject(value, "trace")
  exactKeys(trace, ["trace_id", "episode_id", "context_key", "context_sha256", "stratum", "selected_route_id", "pre_outcome_score_micros", "routing_payload_sha256", "request_sha256", "response_sha256", "status"], "trace")
  if (trace["status"] !== "SEALED_PRE_OUTCOME_LOCAL_EXPERIMENTAL_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING") throw new ProcessRefusal("trace status is invalid")
  const preOutcomeScoreMicros = requiredInteger(trace["pre_outcome_score_micros"], "trace.pre_outcome_score_micros")
  if (preOutcomeScoreMicros < -DNRD_SCORE_MICROS_LIMIT || preOutcomeScoreMicros > DNRD_SCORE_MICROS_LIMIT) throw new ProcessRefusal("trace pre-outcome score is out of range")
  return Object.freeze({
    trace_id: requiredSha256(trace["trace_id"], "trace.trace_id"),
    episode_id: requiredIdentifier(trace["episode_id"], "trace.episode_id"),
    context_key: requiredString(trace["context_key"], "trace.context_key"),
    context_sha256: requiredSha256(trace["context_sha256"], "trace.context_sha256"),
    stratum: requiredIdentifier(trace["stratum"], "trace.stratum"),
    selected_route_id: requiredIdentifier(trace["selected_route_id"], "trace.selected_route_id"),
    pre_outcome_score_micros: preOutcomeScoreMicros,
    routing_payload_sha256: requiredSha256(trace["routing_payload_sha256"], "trace.routing_payload_sha256"),
    request_sha256: requiredSha256(trace["request_sha256"], "trace.request_sha256"),
    response_sha256: requiredSha256(trace["response_sha256"], "trace.response_sha256"),
    status: "SEALED_PRE_OUTCOME_LOCAL_EXPERIMENTAL_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING"
  })
}

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

const parseOutcome = (value: unknown, config: ProcessConfig): { readonly episodeId: string; readonly routeId: string; readonly reward: -1_000_000 | 0 | 1_000_000; readonly digest: string; readonly scorerAddress: string; readonly scorerSourceIdentity: string; readonly roleSeparation: "DECLARED_ROLE_SEPARATION_NOT_PROVEN" } => {
  const outcome = asObject(value, "outcome")
  exactKeys(outcome, ["episode_id", "selected_route_id", "reward", "outcome_digest", "scorer_source_identity", "scorer_address", "role_separation"], "outcome")
  const reward = requiredInteger(outcome["reward"], "outcome.reward")
  if (reward !== -1_000_000 && reward !== 0 && reward !== 1_000_000) throw new ProcessRefusal("outcome.reward violates frozen signed outcome contract")
  const scorerSourceIdentity = requiredSha256(outcome["scorer_source_identity"], "outcome.scorer_source_identity")
  if (scorerSourceIdentity !== config.frozenScorerSourceSha256) throw new ProcessRefusal("outcome scorer source differs from frozen configuration")
  if (requiredString(outcome["role_separation"], "outcome.role_separation") !== "DECLARED_ROLE_SEPARATION_NOT_PROVEN") throw new ProcessRefusal("outcome role separation declaration is invalid")
  const scorerAddress = requiredString(outcome["scorer_address"], "outcome.scorer_address")
  if (scorerAddress !== RAW_SCORER_ADDRESS) throw new ProcessRefusal("outcome scorer address differs from the frozen raw scorer provenance")
  return Object.freeze({ episodeId: requiredIdentifier(outcome["episode_id"], "outcome.episode_id"), routeId: requiredIdentifier(outcome["selected_route_id"], "outcome.selected_route_id"), reward, digest: requiredSha256(outcome["outcome_digest"], "outcome.outcome_digest"), scorerAddress, scorerSourceIdentity, roleSeparation: "DECLARED_ROLE_SEPARATION_NOT_PROVEN" })
}

const createControlReceipt = (arm: string, source: RoutingStateWire, target: RoutingStateWire, payload: DnrdRoutingPayload): string => canonicalHash({ schema_version: PROCESS_SCHEMA, status: "LOCAL_EXPERIMENTAL_STRUCTURAL_ONLY_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING", arm, source_state_sha256: source.state_sha256, target_state_sha256: target.state_sha256, target_routing_payload: payload })

const handleInitialize = async (root: ProcessRoot, payload: unknown): Promise<JsonObject> => {
  const input = asObject(payload, "INIT_STREAM payload")
  exactKeys(input, ["stream"], "INIT_STREAM payload")
  const parsed = parseStream(input["stream"])
  if (!/^stream-[0-3]$/.test(parsed.metadata.streamId)) throw new ProcessRefusal("INIT_STREAM accepts only the four frozen DNRD stream identities")
  await reserveOnce(join(root.streams, `${parsed.metadata.streamId}.json`), {
    schema_version: STREAM_RESERVATION_SCHEMA,
    stream_id: parsed.metadata.streamId,
    public_stream_sha256: canonicalHash(input["stream"])
  }, "DNRD stream reservation")
  const w0Metadata: Omit<MountMetadata, "mountId"> = Object.freeze({
    ...parsed.metadata,
    mountRole: "W0_ROLLBACK",
    sourceMountId: null,
    sourceStateSha256: null,
    frozenScorerSourceSha256: root.frozenScorerSourceSha256
  })
  const w0 = await createBootstrapMount(root, w0Metadata, parsed.zeroPayload)
  if (Object.values(w0.state.scores).some((routes) => Object.values(routes).some((score) => score !== 0))) throw new ProcessRefusal("W0 bootstrap did not expose exact zero payload")
  const w1Id = randomMountId()
  const w1Path = mountPath(root, w1Id)
  const w0Path = mountPath(root, w0.metadata.mountId)
  const prefix = await collectImmutableTree(w0Path)
  await copyImmutableTree(w0Path, w1Path)
  const copiedPrefix = await collectImmutableTree(w1Path)
  if (!sameCanonical(treeManifest(prefix), treeManifest(copiedPrefix))) throw new ProcessRefusal("W0/W1 content-tree common prefix differs after byte copy")
  const w1Metadata: MountMetadata = Object.freeze({
    ...parsed.metadata,
    mountId: w1Id,
    mountRole: "FULL_TRAINABLE",
    sourceMountId: w0.metadata.mountId,
    sourceStateSha256: w0.state.state_sha256,
    frozenScorerSourceSha256: root.frozenScorerSourceSha256
  })
  await writeMetadata(root, w1Metadata)
  const w1Recovery = await recoverAdapter(w1Path)
  const w1 = Object.freeze({ metadata: w1Metadata, payload: w1Recovery.payload, state: makeState(w1Metadata, w1Recovery), journalSha256: w1Recovery.journalSha256 })
  if (!sameCanonical(w0.payload, w1.payload) || w0.state.state_sha256 !== w1.state.state_sha256 || !sameCanonical(w0.state.scores, w1.state.scores)) throw new ProcessRefusal("W0/W1 copied genesis payload differs")
  const commonPrefixSha256 = canonicalHash(treeManifest(prefix))
  const initializationReceiptSha256 = canonicalHash({ schema_version: PROCESS_SCHEMA, status: "LOCAL_EXPERIMENTAL_STRUCTURAL_ONLY_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING", operation: "INIT_STREAM", w0_state_sha256: w0.state.state_sha256, w1_state_sha256: w1.state.state_sha256, common_prefix_sha256: commonPrefixSha256 })
  return Object.freeze({ w0: w0.state, w1: w1.state, initialization_receipt_sha256: initializationReceiptSha256, common_prefix_sha256: commonPrefixSha256, equal_genesis_content: true })
}

const handleMaterializeControl = async (root: ProcessRoot, payload: unknown): Promise<JsonObject> => {
  const input = asObject(payload, "MATERIALIZE_CONTROL payload")
  const arm = input["arm"]
  if (arm !== "RAW_EQUAL_BUDGET" && arm !== "BINDING_DERANGED_NUMERIC_PLACEBO") throw new ProcessRefusal("control arm is invalid")
  const expectedKeys = arm === "RAW_EQUAL_BUDGET"
    ? ["state", "stream_id", "arm", "raw_delta_rule", "training_update_records", "required_training_outcome_count"]
    : ["state", "stream_id", "arm", "matched_derangement"]
  exactKeys(input, expectedKeys, "MATERIALIZE_CONTROL payload")
  const source = await recoverMount(root, input["state"])
  if (requiredIdentifier(input["stream_id"], "MATERIALIZE_CONTROL.stream_id") !== source.metadata.streamId) throw new ProcessRefusal("control stream id differs from source mount")
  let targetPayload: DnrdRoutingPayload
  if (arm === "RAW_EQUAL_BUDGET") {
    if (source.metadata.mountRole !== "W0_ROLLBACK") throw new ProcessRefusal("RAW must materialize only from the immutable recovered W0 rollback mount")
    if (input["raw_delta_rule"] !== RAW_DELTA_RULE || input["required_training_outcome_count"] !== 8) throw new ProcessRefusal("RAW frozen replay rule or count differs")
    if (source.metadata.training.length !== 8 || Object.values(source.state.scores).some((routes) => Object.values(routes).some((score) => score !== 0))) throw new ProcessRefusal("RAW must start from an exact zero W0 routing payload")
    const records = requiredArray(input["training_update_records"], "RAW training_update_records")
    if (records.length !== 8) throw new ProcessRefusal("RAW requires exactly eight signed training update records")
    const expectedByEpisode = new Map(source.metadata.training.map((entry) => [entry.episodeId, entry] as const))
    const scores: Record<string, Readonly<Record<string, number>>> = Object.create(null)
    for (const [contextKey, routes] of Object.entries(source.state.scores)) scores[contextKey] = Object.freeze({ ...routes })
    const seen = new Set<string>()
    for (const [index, rawRecord] of records.entries()) {
      const record = asObject(rawRecord, `RAW training_update_records[${index}]`)
      exactKeys(record, ["episode_id", "context_key", "selected_route_id", "reward", "trace_id", "outcome_digest"], `RAW training_update_records[${index}]`)
      const episodeId = requiredIdentifier(record["episode_id"], `RAW record ${index}.episode_id`)
      const expected = expectedByEpisode.get(episodeId)
      const expectedAtIndex = source.metadata.training[index]
      const contextKey = requiredString(record["context_key"], `RAW record ${index}.context_key`)
      const routeId = requiredIdentifier(record["selected_route_id"], `RAW record ${index}.selected_route_id`)
      const reward = requiredInteger(record["reward"], `RAW record ${index}.reward`)
      requiredSha256(record["trace_id"], `RAW record ${index}.trace_id`)
      requiredSha256(record["outcome_digest"], `RAW record ${index}.outcome_digest`)
      if (expected === undefined || expectedAtIndex === undefined || expectedAtIndex.episodeId !== episodeId || seen.has(episodeId) || expected.contextKey !== contextKey || expected.selectedRouteId !== routeId || (reward !== -1_000_000 && reward !== 0 && reward !== 1_000_000)) throw new ProcessRefusal("RAW record differs from one exact ordered public forced training exposure")
      seen.add(episodeId)
      const routes = scores[contextKey]
      if (routes === undefined || routes[routeId] === undefined) throw new ProcessRefusal("RAW record has unsupported context/route")
      const updated = Math.max(-DNRD_SCORE_MICROS_LIMIT, Math.min(DNRD_SCORE_MICROS_LIMIT, routes[routeId] + Math.trunc((reward * 100_000) / 1_000_000)))
      scores[contextKey] = Object.freeze({ ...routes, [routeId]: updated })
    }
    if (seen.size !== expectedByEpisode.size) throw new ProcessRefusal("RAW records do not cover exactly the eight training exposures")
    targetPayload = payloadFromScores(source.metadata, scores)
  } else {
    if (source.metadata.mountRole !== "FULL_TRAINABLE") throw new ProcessRefusal("DERANGED must materialize only from the recovered trained FULL mount")
    const credited = await creditedEpisodeIds(mountPath(root, source.metadata.mountId))
    const expectedTraining = source.metadata.training.map((entry) => entry.episodeId).sort()
    if (!sameCanonical(credited, expectedTraining)) throw new ProcessRefusal("DERANGED requires exactly all eight once-credited FULL training exposures")
    const mapping = asObject(input["matched_derangement"], "DERANGED matched_derangement")
    const contexts = source.metadata.contexts.map((context) => context.contextKey)
    const contextSet = new Set(contexts)
    if (Object.keys(mapping).length !== contexts.length || Object.keys(mapping).some((receiver) => !contextSet.has(receiver) || typeof mapping[receiver] !== "string" || !contextSet.has(mapping[receiver] as string) || receiver === mapping[receiver]) || new Set(Object.values(mapping) as string[]).size !== contexts.length) {
      throw new ProcessRefusal("DERANGED must use an exact supplied fixed-point-free context bijection")
    }
    if (!sameCanonical(mapping, source.metadata.matchedDerangement)) throw new ProcessRefusal("DERANGED map differs from the exact public mounted binding")
    const scores: Record<string, Readonly<Record<string, number>>> = Object.create(null)
    for (const receiver of contexts) {
      const donor = mapping[receiver] as string
      const donorScores = source.state.scores[donor]
      if (donorScores === undefined) throw new ProcessRefusal("DERANGED donor score support is absent")
      scores[receiver] = Object.freeze({ ...donorScores })
    }
    targetPayload = payloadFromScores(source.metadata, scores)
    const coreDeranged = derangeDnrdRoutingBindings(source.payload)
    if (Either.isLeft(coreDeranged) || !sameCanonical(coreDeranged.right, targetPayload)) throw new ProcessRefusal("public DERANGED map differs from the exact TS-core binding derangement")
    const sourceNorms = dnrdScoreNorms(source.payload)
    const targetNorms = dnrdScoreNorms(targetPayload)
    if (Either.isLeft(sourceNorms) || Either.isLeft(targetNorms) || sourceNorms.right.l1Micros !== targetNorms.right.l1Micros || sourceNorms.right.l2SquaredMicros !== targetNorms.right.l2SquaredMicros) {
      throw new ProcessRefusal("DERANGED payload does not preserve exact L1/L2-squared score norms")
    }
  }
  const targetRole = arm === "RAW_EQUAL_BUDGET" ? "RAW_CONTROL" : "DERANGED_CONTROL"
  await reserveOnce(join(root.controls, `${source.metadata.streamId}-${arm}.json`), {
    schema_version: CONTROL_RESERVATION_SCHEMA,
    stream_id: source.metadata.streamId,
    arm,
    source_mount_id: source.metadata.mountId,
    source_state_sha256: source.state.state_sha256,
    target_payload_sha256: canonicalHash(targetPayload)
  }, "DNRD control reservation")
  const materialized = await createBootstrapMount(root, controlMetadata(source, targetRole), targetPayload)
  const receiptSha256 = createControlReceipt(arm, source.state, materialized.state, targetPayload)
  return Object.freeze({ state: materialized.state, receipt_sha256: receiptSha256 })
}

const handleSealTrace = async (root: ProcessRoot, payload: unknown): Promise<WireTrace> => {
  const input = asObject(payload, "SEAL_TRACE payload")
  exactKeys(input, ["state", "episode_id", "context_key", "selected_route_id", "request_sha256", "response_sha256"], "SEAL_TRACE payload")
  const recovered = await recoverMount(root, input["state"])
  const episodeId = requiredIdentifier(input["episode_id"], "SEAL_TRACE.episode_id")
  const rawContext = requiredString(input["context_key"], "SEAL_TRACE.context_key")
  const binding = recovered.metadata.contexts.find((context) => context.contextKey === rawContext)
  if (binding === undefined) throw new ProcessRefusal("SEAL_TRACE context is absent from recovered mount")
  const routeId = requiredIdentifier(input["selected_route_id"], "SEAL_TRACE.selected_route_id")
  if (!recovered.metadata.routeIds.includes(routeId)) throw new ProcessRefusal("SEAL_TRACE selected route is absent from recovered mount")
  const publicEpisode = recovered.metadata.episodes.find((episode) => episode.episodeId === episodeId)
  if (publicEpisode === undefined || publicEpisode.contextKey !== rawContext || (publicEpisode.forcedRouteId !== null && publicEpisode.forcedRouteId !== routeId)) {
    throw new ProcessRefusal("SEAL_TRACE must name one exact registered public episode/context/route exposure")
  }
  if (publicEpisode.phase === "training" && recovered.metadata.mountRole !== "FULL_TRAINABLE") throw new ProcessRefusal("only the FULL trainable mount may seal a forced-training trajectory")
  if (publicEpisode.phase === "heldout") {
    const selected = selectDnrdRoute(recovered.payload, binding.contextSha256)
    if (Either.isLeft(selected) || selected.right.routeId !== routeId) throw new ProcessRefusal("heldout trace route differs from the TS-core deterministic routing readout")
  }
  const trace = await sealAdapterTrace(mountPath(root, recovered.metadata.mountId), { episodeId, contextSha256: binding.contextSha256, routeId, requestSha256: requiredSha256(input["request_sha256"], "SEAL_TRACE.request_sha256"), responseSha256: requiredSha256(input["response_sha256"], "SEAL_TRACE.response_sha256") })
  if (trace.routingPayloadSha256 !== recovered.state.state_sha256 || trace.contextSha256 !== contextSha256(rawContext)) throw new ProcessRefusal("sealed trace did not bind recovered routing state and raw context hash")
  return traceWire(trace, rawContext)
}

const handleApplyOutcome = async (config: ProcessConfig, root: ProcessRoot, payload: unknown): Promise<JsonObject> => {
  const input = asObject(payload, "APPLY_OUTCOME payload")
  exactKeys(input, ["state", "trace", "outcome"], "APPLY_OUTCOME payload")
  const recovered = await recoverMount(root, input["state"])
  if (recovered.metadata.mountRole !== "FULL_TRAINABLE") throw new ProcessRefusal("only the immutable FULL trainable mount role may consume an outcome")
  const trace = parseWireTrace(input["trace"])
  const binding = recovered.metadata.contexts.find((context) => context.contextKey === trace.context_key)
  if (binding === undefined || trace.context_sha256 !== binding.contextSha256 || trace.context_sha256 !== contextSha256(trace.context_key) || trace.stratum !== binding.stratum || !recovered.metadata.routeIds.includes(trace.selected_route_id) || trace.routing_payload_sha256 !== recovered.state.state_sha256) {
    throw new ProcessRefusal("trace does not exactly bind the supplied fresh routing state")
  }
  const training = recovered.metadata.training.find((episode) => episode.episodeId === trace.episode_id)
  if (training === undefined || training.contextKey !== trace.context_key || training.selectedRouteId !== trace.selected_route_id) {
    throw new ProcessRefusal("only one exact registered forced-training trace may create a local experimental credit successor; heldout traces remain read-only")
  }
  const alreadyCreditedEpisodes = await creditedEpisodeIds(mountPath(root, recovered.metadata.mountId))
  if (alreadyCreditedEpisodes.includes(trace.episode_id)) {
    throw new ProcessRefusal("one registered training episode may produce at most one local experimental credit successor")
  }
  const outcome = parseOutcome(input["outcome"], config)
  if (outcome.episodeId !== trace.episode_id || outcome.routeId !== trace.selected_route_id) throw new ProcessRefusal("outcome episode/route does not match sealed trace")
  const reconstructedTrace = validateDnrdEligibilityTrace(traceFromWire(trace))
  if (Either.isLeft(reconstructedTrace)) throw new ProcessRefusal(`trace wire does not reproduce a valid sealed trace: ${reconstructedTrace.left.detail}`)
  const observation = makeDnrdOutcomeObservation({ traceId: trace.trace_id, producerAddress: PRODUCER_ADDRESS, scorerAddress: SCORER_ADDRESS, scorerProvenanceAddress: SCORER_PROVENANCE_ADDRESS, scorerSourceSha256: outcome.scorerSourceIdentity, outcomeScoreMicros: outcome.reward, scorerObservationSha256: outcome.digest })
  if (Either.isLeft(observation)) throw new ProcessRefusal(`outcome observation cannot be sealed: ${observation.left.detail}`)
  const credit = applyDnrdCreditUpdate({ payload: recovered.payload, trace: reconstructedTrace.right, outcome: observation.right, consumedOutcomeIds: await consumedOutcomeIds(mountPath(root, recovered.metadata.mountId)), learningRateMicros: 100_000, scoreLimitMicros: 100_000 })
  if (Either.isLeft(credit)) throw new ProcessRefusal(`outcome cannot produce a frozen local experimental credit update: ${credit.left.detail}`)
  // The durable adapter resolves and revalidates the matching sealed trace by
  // traceId; reconstructedTrace above additionally binds all wire fields.
  await applyAdapterOutcome(mountPath(root, recovered.metadata.mountId), observation.right)
  const after = await recoverAdapter(mountPath(root, recovered.metadata.mountId))
  if (after.payloadSha256 !== credit.right.receipt.afterPayloadSha256) throw new ProcessRefusal("durable successor payload does not equal the exact frozen credit receipt")
  const state = makeState(recovered.metadata, after)
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
}

const handleRecover = async (root: ProcessRoot, payload: unknown): Promise<JsonObject> => {
  const input = asObject(payload, "RECOVER payload")
  exactKeys(input, ["state"], "RECOVER payload")
  const recovered = await recoverMount(root, input["state"])
  const routingPayloadBytes = canonicalBytes(recovered.payload)
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
}

const assertImplementationBinding = async (pathValue: unknown, digestValue: unknown): Promise<void> => {
  const path = requiredString(pathValue, "implementation_path")
  if (!isAbsolute(path)) throw new ProcessRefusal("implementation_path must be absolute")
  const stat = await lstat(path)
  if (stat.isSymbolicLink() || !stat.isFile()) throw new ProcessRefusal("implementation_path must name a plain file")
  const expected = requiredSha256(digestValue, "implementation_sha256")
  const actual = sha256(await readFile(path))
  if (actual !== expected) throw new ProcessRefusal("implementation path/hash binding mismatch")
}

/** Executes one strict request. Its return is intentionally local structural data only. */
export const executeDnrdRoutingDiagnosticProcess = async (request: unknown): Promise<JsonObject> => {
  const input = asObject(request, "DNRD subprocess request")
  exactKeys(input, ["operation", "implementation_path", "implementation_sha256", "config", "config_sha256", "payload"], "DNRD subprocess request")
  const operation = parseOperation(input["operation"])
  await assertImplementationBinding(input["implementation_path"], input["implementation_sha256"])
  const config = parseConfig(input["config"])
  if (requiredSha256(input["config_sha256"], "config_sha256") !== sha256(pythonJson(input["config"]))) throw new ProcessRefusal("config_sha256 does not bind the exact Python bridge configuration")
  const root = await prepareDedicatedRoot(config)
  switch (operation) {
    case "INIT_STREAM": return handleInitialize(root, input["payload"])
    case "MATERIALIZE_CONTROL": return handleMaterializeControl(root, input["payload"])
    case "SEAL_TRACE": return Object.freeze({ ...await handleSealTrace(root, input["payload"]) })
    case "APPLY_OUTCOME": return handleApplyOutcome(config, root, input["payload"])
    case "RECOVER": return handleRecover(root, input["payload"])
  }
}

export const runDnrdRoutingDiagnosticProcess = async (stdin: string): Promise<number> => {
  try {
    const result = await executeDnrdRoutingDiagnosticProcess(parseRequestJson(stdin))
    process.stdout.write(`${new TextDecoder().decode(canonicalBytes(result))}\n`)
    return 0
  } catch (error) {
    const detail = error instanceof Error ? error.message : "unknown DNRD process refusal"
    process.stderr.write(`DNRD_ROUTING_DIAGNOSTIC_PROCESS_REFUSED: ${detail}\n`)
    return 2
  }
}

const invokedPath = process.argv[1]
if (invokedPath !== undefined && import.meta.url === pathToFileURL(invokedPath).href) {
  const stdin = new Promise<string>((resolveStdin, rejectStdin) => {
    let source = ""
    process.stdin.setEncoding("utf8")
    process.stdin.on("data", (chunk: string) => {
      source += chunk
      if (Buffer.byteLength(source, "utf8") > MAX_FILE_BYTES) {
        process.stdin.pause()
        rejectStdin(new ProcessRefusal("stdin exceeds the bounded canonical JSON limit"))
      }
    })
    process.stdin.once("end", () => resolveStdin(source))
    process.stdin.once("error", rejectStdin)
  })
  void stdin.then(runDnrdRoutingDiagnosticProcess).then((exitCode) => { process.exitCode = exitCode }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : "stdin read failure"
    process.stderr.write(`DNRD_ROUTING_DIAGNOSTIC_PROCESS_REFUSED: ${detail}\n`)
    process.exitCode = 2
  })
}
