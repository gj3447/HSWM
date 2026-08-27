import { constants } from "node:fs"
import { access, writeFile } from "node:fs/promises"

import { Effect, Either } from "effect"

import {
  makeCanonicalAtomV2StateJournalFileStoreLayer,
  makeCanonicalAtomV2StateJournalFileStoreLayerWithBeforeSlotLinkForTest
} from "../../src/canonical-atom-v2-state-journal-file.js"
import { CanonicalAtomV2StateJournalStore } from "../../src/canonical-atom-v2-state-journal-store.js"

const writeFrame = (frame: unknown): void => {
  process.stdout.write(`${JSON.stringify(frame)}\n`)
}

const waitForRelease = async (
  readyPath: string,
  releasePath: string
): Promise<void> => {
  await writeFile(readyPath, `${process.pid}\n`, {
    flag: "wx",
    mode: 0o400
  })
  const deadline = Date.now() + 10_000
  while (true) {
    try {
      await access(releasePath, constants.F_OK)
      return
    } catch (cause) {
      if (
        typeof cause !== "object" ||
        cause === null ||
        !("code" in cause) ||
        cause.code !== "ENOENT"
      ) {
        throw cause
      }
    }
    if (Date.now() >= deadline) {
      throw new Error("slot-link barrier release did not appear")
    }
    await new Promise<void>((resolveDelay) => setTimeout(resolveDelay, 5))
  }
}

const publish = async (arguments_: ReadonlyArray<string>): Promise<void> => {
  const [root, lineage, schema, workerId, encoded, readyPath, releasePath] =
    arguments_
  if (
    root === undefined ||
    lineage === undefined ||
    schema === undefined ||
    workerId === undefined ||
    encoded === undefined ||
    readyPath === undefined ||
    releasePath === undefined
  ) {
    throw new Error("publish worker arguments are incomplete")
  }
  const record = Uint8Array.from(Buffer.from(encoded, "base64"))
  const journalLayer =
    makeCanonicalAtomV2StateJournalFileStoreLayerWithBeforeSlotLinkForTest(
      root,
      lineage,
      schema,
      () => waitForRelease(readyPath, releasePath)
    )
  const outcome = await Effect.runPromise(
    Effect.gen(function* () {
      const store = yield* CanonicalAtomV2StateJournalStore
      return yield* store.publish({
        stateRevision: 0,
        expectedPredecessor: null,
        bytes: record
      })
    }).pipe(Effect.provide(journalLayer), Effect.either)
  )
  if (Either.isLeft(outcome)) {
    writeFrame({
      mode: "publish",
      pid: process.pid,
      workerId,
      ok: false,
      operation: outcome.left.operation,
      reason: outcome.left.reason
    })
    return
  }
  writeFrame({
    mode: "publish",
    pid: process.pid,
    workerId,
    ok: true,
    tag: outcome.right._tag,
    sha256: outcome.right.recovery[0]?.descriptor.sha256 ?? null
  })
}

const recover = async (arguments_: ReadonlyArray<string>): Promise<void> => {
  const [root, lineage, schema] = arguments_
  if (root === undefined || lineage === undefined || schema === undefined) {
    throw new Error("recover worker arguments are incomplete")
  }
  const outcome = await Effect.runPromise(
    Effect.gen(function* () {
      const store = yield* CanonicalAtomV2StateJournalStore
      return yield* store.recover
    }).pipe(
      Effect.provide(
        makeCanonicalAtomV2StateJournalFileStoreLayer(root, lineage, schema)
      ),
      Effect.either
    )
  )
  if (Either.isLeft(outcome)) {
    writeFrame({
      mode: "recover",
      pid: process.pid,
      ok: false,
      operation: outcome.left.operation,
      reason: outcome.left.reason
    })
    return
  }
  writeFrame({
    mode: "recover",
    pid: process.pid,
    ok: true,
    entries: outcome.right.map((entry) => ({
      descriptor: entry.descriptor,
      bytesBase64: Buffer.from(entry.bytes).toString("base64")
    }))
  })
}

const main = async (): Promise<void> => {
  const [mode, ...arguments_] = process.argv.slice(2)
  if (mode === "publish") return publish(arguments_)
  if (mode === "recover") return recover(arguments_)
  throw new Error("worker mode is invalid")
}

void main().catch((cause: unknown) => {
  process.stderr.write(
    `${cause instanceof Error ? cause.stack ?? cause.message : String(cause)}\n`
  )
  process.exitCode = 1
})
