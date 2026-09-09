/**
 * Private, local SQLite snapshot support for HSWM development state.
 *
 * This is an engineering recovery surface only.  It does not admit canonical
 * state, award causal credit, or alter a running development lease.  SQLite's
 * online backup API is used rather than copying the database/WAL files: that
 * API produces one consistent database snapshot while another connection may
 * continue writing.
 */
import { createHash, randomUUID } from "node:crypto"
import { dirname, isAbsolute, join, resolve } from "node:path"
import { backup, DatabaseSync } from "node:sqlite"

import { Data, Effect } from "effect"

import { canonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { PosixFileSystem, type PosixFileSystemShape } from "./effect-posix-filesystem.js"
import { refuse, type ProcessReply } from "./effect-process-main.js"

export const HSWM_DEVELOPMENT_BACKUP_V1 = "hswm-development-backup/v1" as const
const PRIVATE_DIRECTORY_MODE = 0o700
const PRIVATE_FILE_MODE = 0o400
const TEMPORARY_FILE_MODE = 0o600
const FS_OPERATION = "hswm-development-backup"
const MANIFEST_SUFFIX = ".hswm-backup.json"

export class DevelopmentBackupError extends Data.TaggedError("DevelopmentBackupError")<{
  readonly operation: "BACKUP" | "VERIFY" | "RESTORE"
  readonly detail: string
}> {}

export interface DevelopmentBackupManifest {
  readonly contract: typeof HSWM_DEVELOPMENT_BACKUP_V1
  readonly backup_sha256: string
  readonly byte_length: number
  readonly integrity_check: "ok"
  readonly logical_state_sha256: string
  readonly page_count: number
  readonly schema_sha256: string
}

const failure = (operation: DevelopmentBackupError["operation"], detail: string) =>
  new DevelopmentBackupError({ operation, detail })

const sha256 = (bytes: Uint8Array | string): string => createHash("sha256").update(bytes).digest("hex")
const manifestPath = (backupPath: string): string => `${backupPath}${MANIFEST_SUFFIX}`
const asError = (operation: DevelopmentBackupError["operation"], detail: string) => (cause: unknown): DevelopmentBackupError =>
  failure(operation, cause instanceof Error ? `${detail}: ${cause.message}` : detail)

/** Pure argv decoding; commands deliberately accept only one database at a time. */
export const decodeDevelopmentBackupCommand = (
  argv: ReadonlyArray<string>
): Effect.Effect<{ readonly command: "backup" | "verify" | "restore"; readonly source?: string; readonly backup: string; readonly destination?: string }, DevelopmentBackupError> => {
  const command = argv[0]
  if (command !== "backup" && command !== "verify" && command !== "restore") {
    return Effect.fail(failure("VERIFY", "usage: backup --source FILE --destination NEW_FILE | verify --backup FILE | restore --backup FILE --destination NEW_FILE"))
  }
  const values: Record<string, string> = {}
  for (let index = 1; index < argv.length; index += 2) {
    const flag = argv[index]
    const value = argv[index + 1]
    if ((flag !== "--source" && flag !== "--backup" && flag !== "--destination") || value === undefined || values[flag] !== undefined) {
      return Effect.fail(failure(command === "restore" ? "RESTORE" : command === "backup" ? "BACKUP" : "VERIFY", "arguments must be unique --name FILE pairs"))
    }
    values[flag] = value
  }
  if (command === "backup" && values["--source"] !== undefined && values["--destination"] !== undefined && Object.keys(values).length === 2) {
    return Effect.succeed(Object.freeze({ command, source: values["--source"], backup: values["--destination"] }))
  }
  if (command === "verify" && values["--backup"] !== undefined && Object.keys(values).length === 1) {
    return Effect.succeed(Object.freeze({ command, backup: values["--backup"] }))
  }
  if (command === "restore" && values["--backup"] !== undefined && values["--destination"] !== undefined && Object.keys(values).length === 2) {
    return Effect.succeed(Object.freeze({ command, backup: values["--backup"], destination: values["--destination"] }))
  }
  return Effect.fail(failure(command === "restore" ? "RESTORE" : command === "backup" ? "BACKUP" : "VERIFY", "usage requires exactly the flags for this command"))
}

const inspectPrivateDirectory = (
  fs: PosixFileSystemShape,
  directory: string,
  operation: DevelopmentBackupError["operation"]
) => Effect.gen(function* () {
  const identity = yield* fs.identity(directory, FS_OPERATION).pipe(Effect.mapError(asError(operation, "cannot inspect parent directory")))
  if (identity.kind !== "DIRECTORY" || identity.mode !== PRIVATE_DIRECTORY_MODE) {
    return yield* Effect.fail(failure(operation, "parent directory must be a non-symlink private 0700 directory"))
  }
  return identity
})

const inspectSource = (
  fs: PosixFileSystemShape,
  path: string,
  operation: DevelopmentBackupError["operation"]
) => Effect.gen(function* () {
  if (!isAbsolute(path)) return yield* Effect.fail(failure(operation, "database paths must be absolute"))
  const normalized = resolve(path)
  const identity = yield* fs.identity(normalized, FS_OPERATION).pipe(Effect.mapError(asError(operation, "cannot inspect database")))
  if (identity.kind !== "FILE") return yield* Effect.fail(failure(operation, "database must be an existing non-symlink regular file"))
  yield* inspectPrivateDirectory(fs, dirname(normalized), operation)
  return normalized
})

const inspectNewDestination = (
  fs: PosixFileSystemShape,
  path: string,
  operation: DevelopmentBackupError["operation"]
) => Effect.gen(function* () {
  if (!isAbsolute(path)) return yield* Effect.fail(failure(operation, "database paths must be absolute"))
  const normalized = resolve(path)
  yield* inspectPrivateDirectory(fs, dirname(normalized), operation)
  const exists = yield* fs.identity(normalized, FS_OPERATION).pipe(
    Effect.as(true),
    Effect.catchIf((error) => error.code === "ENOENT", () => Effect.succeed(false)),
    Effect.mapError(asError(operation, "cannot inspect destination"))
  )
  if (exists) return yield* Effect.fail(failure(operation, "destination must not already exist"))
  const metadataExists = yield* fs.identity(manifestPath(normalized), FS_OPERATION).pipe(
    Effect.as(true),
    Effect.catchIf((error) => error.code === "ENOENT", () => Effect.succeed(false)),
    Effect.mapError(asError(operation, "cannot inspect destination metadata"))
  )
  if (metadataExists) return yield* Effect.fail(failure(operation, "destination metadata must not already exist"))
  return normalized
})

const sqliteSnapshot = (path: string, operation: DevelopmentBackupError["operation"]): Effect.Effect<{ readonly integrityCheck: "ok"; readonly logicalStateSha256: string; readonly pageCount: number; readonly schemaSha256: string }, DevelopmentBackupError> =>
  Effect.try({
    try: () => {
      const database = new DatabaseSync(path, { readOnly: true, allowExtension: false, timeout: 5_000 })
      try {
        const integrity = database.prepare("PRAGMA integrity_check").all() as ReadonlyArray<Record<string, unknown>>
        const schema = database.prepare("SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name, tbl_name").all() as ReadonlyArray<Record<string, unknown>>
        const state = createHash("sha256")
        state.update("hswm-development-backup-logical-state/v1\n")
        for (const entry of schema) {
          state.update(JSON.stringify(entry))
          state.update("\n")
          if (entry["type"] !== "table" || typeof entry["name"] !== "string" || entry["name"].startsWith("sqlite_")) continue
          const quoted = `"${entry["name"].replaceAll("\"", "\"\"")}"`
          const columns = database.prepare(`PRAGMA table_info(${quoted})`).all() as ReadonlyArray<Record<string, unknown>>
          const expressions = columns.map((column, index) => `quote("${String(column["name"]).replaceAll("\"", "\"\"")}") AS c${index}`).join(", ")
          if (expressions.length === 0) continue
          const rows = database.prepare(`SELECT ${expressions} FROM ${quoted}`).all() as ReadonlyArray<Record<string, unknown>>
          for (const row of rows) { state.update(JSON.stringify(row)); state.update("\n") }
        }
        const pageCount = database.prepare("PRAGMA page_count").get() as Record<string, unknown> | undefined
        const pages = pageCount?.["page_count"]
        return Object.freeze({ integrityValue: integrity.length === 1 ? integrity[0]?.["integrity_check"] : undefined, logicalStateSha256: state.digest("hex"), pageCount: pages, schemaSha256: sha256(JSON.stringify(schema)) })
      } finally { database.close() }
    },
    catch: asError(operation, "SQLite snapshot inspection failed")
  }).pipe(Effect.flatMap((snapshot) =>
    snapshot.integrityValue === "ok" && typeof snapshot.pageCount === "number" && Number.isSafeInteger(snapshot.pageCount)
      ? Effect.succeed(Object.freeze({ integrityCheck: "ok" as const, logicalStateSha256: snapshot.logicalStateSha256, pageCount: snapshot.pageCount, schemaSha256: snapshot.schemaSha256 }))
      : Effect.fail(failure(operation, "SQLite integrity_check or page_count is invalid"))
  ))

const readPrivateBytes = (fs: PosixFileSystemShape, path: string, operation: DevelopmentBackupError["operation"]) =>
  fs.readRegularBounded(path, { maximumBytes: 512 * 1024 * 1024, requiredMode: PRIVATE_FILE_MODE, operation: FS_OPERATION }).pipe(
    Effect.mapError(asError(operation, "backup must be a private immutable regular file"))
  )

const decodeManifest = (bytes: Uint8Array, operation: DevelopmentBackupError["operation"]): Effect.Effect<DevelopmentBackupManifest, DevelopmentBackupError> =>
  Effect.try({ try: () => JSON.parse(new TextDecoder().decode(bytes)) as unknown, catch: asError(operation, "manifest is not JSON") }).pipe(
    Effect.flatMap((value) => {
      if (typeof value !== "object" || value === null || Array.isArray(value)) return Effect.fail(failure(operation, "manifest has invalid shape"))
      const manifest = value as Partial<DevelopmentBackupManifest>
      const expectedKeys = ["backup_sha256", "byte_length", "contract", "integrity_check", "logical_state_sha256", "page_count", "schema_sha256"]
      const keys = Object.keys(value).sort()
      const digest = /^[0-9a-f]{64}$/
      if (keys.length !== expectedKeys.length || keys.some((key, index) => key !== expectedKeys[index]) || manifest.contract !== HSWM_DEVELOPMENT_BACKUP_V1 || typeof manifest.backup_sha256 !== "string" || !digest.test(manifest.backup_sha256) || typeof manifest.byte_length !== "number" || !Number.isSafeInteger(manifest.byte_length) || manifest.byte_length <= 0 || manifest.integrity_check !== "ok" || typeof manifest.logical_state_sha256 !== "string" || !digest.test(manifest.logical_state_sha256) || typeof manifest.page_count !== "number" || !Number.isSafeInteger(manifest.page_count) || manifest.page_count <= 0 || typeof manifest.schema_sha256 !== "string" || !digest.test(manifest.schema_sha256)) {
        return Effect.fail(failure(operation, "manifest has invalid fields"))
      }
      return Effect.succeed(Object.freeze(manifest as DevelopmentBackupManifest))
    })
  )

const verify = (fs: PosixFileSystemShape, requested: string, operation: DevelopmentBackupError["operation"]): Effect.Effect<DevelopmentBackupManifest, DevelopmentBackupError> =>
  Effect.gen(function* () {
    const backupPath = yield* inspectSource(fs, requested, operation)
    const data = yield* readPrivateBytes(fs, backupPath, operation)
    const manifestBytes = yield* readPrivateBytes(fs, manifestPath(backupPath), operation)
    const manifest = yield* decodeManifest(manifestBytes.bytes, operation)
    if (manifest.backup_sha256 !== sha256(data.bytes) || manifest.byte_length !== data.bytes.byteLength) return yield* Effect.fail(failure(operation, "backup digest or byte length differs from manifest"))
    const snapshot = yield* sqliteSnapshot(backupPath, operation)
    if (snapshot.integrityCheck !== manifest.integrity_check || snapshot.logicalStateSha256 !== manifest.logical_state_sha256 || snapshot.schemaSha256 !== manifest.schema_sha256 || snapshot.pageCount !== manifest.page_count) {
      return yield* Effect.fail(failure(operation, "backup logical state differs from manifest"))
    }
    return manifest
  })

const sqliteBackup = (source: string, destination: string, operation: DevelopmentBackupError["operation"]): Effect.Effect<void, DevelopmentBackupError> =>
  Effect.acquireUseRelease(
    Effect.try({ try: () => new DatabaseSync(source, { readOnly: true, allowExtension: false, timeout: 5_000 }), catch: asError(operation, "cannot open source read-only") }),
    (sourceDb) => Effect.tryPromise({ try: () => backup(sourceDb, destination, { rate: 100 }), catch: asError(operation, "SQLite online backup failed") }).pipe(Effect.asVoid),
    (sourceDb) => Effect.sync(() => sourceDb.close()).pipe(Effect.ignore)
  )

/** A backup inherits a source's persistent WAL mode.  Collapse it to one main-file snapshot before publication. */
const normalizeBackupJournal = (path: string, operation: DevelopmentBackupError["operation"]): Effect.Effect<void, DevelopmentBackupError> =>
  Effect.try({
    try: () => {
      const database = new DatabaseSync(path, { allowExtension: false, timeout: 5_000 })
      try {
        const row = database.prepare("PRAGMA journal_mode=DELETE").get() as Record<string, unknown> | undefined
        return row?.["journal_mode"]
      } finally { database.close() }
    },
    catch: asError(operation, "cannot normalize backup journal mode")
  }).pipe(Effect.flatMap((mode) =>
    mode === "delete"
      ? Effect.void
      : Effect.fail(failure(operation, "backup journal mode did not normalize to delete"))
  ))

const publishNewFile = (fs: PosixFileSystemShape, temporary: string, finalPath: string, operation: DevelopmentBackupError["operation"]) =>
  fs.linkNoReplace(temporary, finalPath, FS_OPERATION).pipe(Effect.mapError(asError(operation, "cannot publish without replacing an existing path")))

const backupCommand = (fs: PosixFileSystemShape, sourceArgument: string, destinationArgument: string): Effect.Effect<ProcessReply, DevelopmentBackupError> =>
  Effect.gen(function* () {
    const source = yield* inspectSource(fs, sourceArgument, "BACKUP")
    const destination = yield* inspectNewDestination(fs, destinationArgument, "BACKUP")
    if (source === destination) return yield* Effect.fail(failure("BACKUP", "source and destination must differ"))
    const temporary = join(dirname(destination), `.hswm-backup-${randomUUID()}.tmp`)
    const temporaryManifest = `${temporary}${MANIFEST_SUFFIX}`
    const phase = Effect.gen(function* () {
      yield* fs.writeExclusive(temporary, new Uint8Array(), { mode: TEMPORARY_FILE_MODE, sync: true, operation: FS_OPERATION }).pipe(Effect.mapError(asError("BACKUP", "cannot reserve temporary destination")))
      yield* sqliteBackup(source, temporary, "BACKUP")
      yield* normalizeBackupJournal(temporary, "BACKUP")
      yield* fs.chmod(temporary, PRIVATE_FILE_MODE, FS_OPERATION).pipe(Effect.mapError(asError("BACKUP", "cannot make backup private")))
      yield* fs.syncRegular(temporary, FS_OPERATION).pipe(Effect.mapError(asError("BACKUP", "cannot sync completed backup")))
      const backupBytes = yield* readPrivateBytes(fs, temporary, "BACKUP")
      const snapshot = yield* sqliteSnapshot(temporary, "BACKUP")
      const manifest: DevelopmentBackupManifest = Object.freeze({ contract: HSWM_DEVELOPMENT_BACKUP_V1, backup_sha256: sha256(backupBytes.bytes), byte_length: backupBytes.bytes.byteLength, integrity_check: snapshot.integrityCheck, logical_state_sha256: snapshot.logicalStateSha256, page_count: snapshot.pageCount, schema_sha256: snapshot.schemaSha256 })
      const encoded = canonicalJsonBytes(manifest)
      if (encoded._tag === "Left") return yield* Effect.fail(failure("BACKUP", "cannot encode backup manifest"))
      yield* fs.writeExclusive(temporaryManifest, encoded.right, { mode: TEMPORARY_FILE_MODE, finalMode: PRIVATE_FILE_MODE, sync: true, operation: FS_OPERATION }).pipe(Effect.mapError(asError("BACKUP", "cannot stage manifest")))
      yield* publishNewFile(fs, temporary, destination, "BACKUP")
      yield* publishNewFile(fs, temporaryManifest, manifestPath(destination), "BACKUP")
      yield* fs.syncDirectory(dirname(destination), FS_OPERATION).pipe(Effect.mapError(asError("BACKUP", "cannot sync backup directory")))
      return Object.freeze({ stdout: `${JSON.stringify(manifest)}\n`, exitCode: 0 })
    })
    return yield* phase.pipe(
      Effect.ensuring(fs.unlinkIfPresent(temporary, FS_OPERATION).pipe(Effect.ignore)),
      Effect.ensuring(fs.unlinkIfPresent(temporaryManifest, FS_OPERATION).pipe(Effect.ignore))
    )
  })

const restoreCommand = (fs: PosixFileSystemShape, backupArgument: string, destinationArgument: string): Effect.Effect<ProcessReply, DevelopmentBackupError> =>
  Effect.gen(function* () {
    const backupPath = yield* inspectSource(fs, backupArgument, "RESTORE")
    const destination = yield* inspectNewDestination(fs, destinationArgument, "RESTORE")
    if (backupPath === destination) return yield* Effect.fail(failure("RESTORE", "backup and destination must differ"))
    const manifest = yield* verify(fs, backupPath, "RESTORE")
    const temporary = join(dirname(destination), `.hswm-restore-${randomUUID()}.tmp`)
    const phase = Effect.gen(function* () {
      yield* fs.writeExclusive(temporary, new Uint8Array(), { mode: TEMPORARY_FILE_MODE, sync: true, operation: FS_OPERATION }).pipe(Effect.mapError(asError("RESTORE", "cannot reserve temporary destination")))
      yield* sqliteBackup(backupPath, temporary, "RESTORE")
      yield* normalizeBackupJournal(temporary, "RESTORE")
      yield* fs.chmod(temporary, TEMPORARY_FILE_MODE, FS_OPERATION).pipe(Effect.mapError(asError("RESTORE", "cannot make restored database private and writable")))
      yield* fs.syncRegular(temporary, FS_OPERATION).pipe(Effect.mapError(asError("RESTORE", "cannot sync completed restored database")))
      const restored = yield* sqliteSnapshot(temporary, "RESTORE")
      if (restored.logicalStateSha256 !== manifest.logical_state_sha256 || restored.schemaSha256 !== manifest.schema_sha256) return yield* Effect.fail(failure("RESTORE", "restored logical state differs from verified backup"))
      yield* publishNewFile(fs, temporary, destination, "RESTORE")
      yield* fs.syncDirectory(dirname(destination), FS_OPERATION).pipe(Effect.mapError(asError("RESTORE", "cannot sync restore directory")))
      return Object.freeze({ stdout: `${JSON.stringify({ destination, logical_state_sha256: manifest.logical_state_sha256 })}\n`, exitCode: 0 })
    })
    return yield* phase.pipe(Effect.ensuring(fs.unlinkIfPresent(temporary, FS_OPERATION).pipe(Effect.ignore)))
  })

export const runDevelopmentBackupCli = (argv: ReadonlyArray<string>) =>
  Effect.gen(function* () {
    const command = yield* decodeDevelopmentBackupCommand(argv)
    const fs = yield* PosixFileSystem
    if (command.command === "backup") return yield* backupCommand(fs, command.source as string, command.backup)
    if (command.command === "verify") {
      const manifest = yield* verify(fs, command.backup, "VERIFY")
      return Object.freeze({ stdout: `${JSON.stringify(manifest)}\n`, exitCode: 0 })
    }
    return yield* restoreCommand(fs, command.backup, command.destination as string)
  }).pipe(Effect.catchTag("DevelopmentBackupError", (error) => Effect.fail(refuse(`${error.operation}: ${error.detail}`))))
