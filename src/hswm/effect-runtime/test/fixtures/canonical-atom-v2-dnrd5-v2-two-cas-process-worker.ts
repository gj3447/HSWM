import { constants } from "node:fs"
import { access, writeFile } from "node:fs/promises"

import { Effect } from "effect"

import {
  resumeDnrd5V2AdmitTwoCas,
  submitDnrd5V2AdmitTwoCas
} from "../../src/canonical-atom-v2-dnrd5-durable-permit.js"
import {
  makeDnrd5V2TwoCasBeforeSlotLinkFileLayer,
  makeDnrd5V2TwoCasIoFaultFileLayer,
  makeDnrd5V2TwoCasLayer,
  prepareDnrd5V2TwoCasFixture
} from "./canonical-atom-v2-dnrd5-v2-two-cas.js"

// The fixture's exported file layer owns these grants.  Reconstructing input
// in a private memory runtime avoids serializing capability-bearing bytes.
const input = () => Effect.runPromise(
  prepareDnrd5V2TwoCasFixture().pipe(Effect.provide(makeDnrd5V2TwoCasLayer()))
)

const wait = async (ready: string, release: string): Promise<void> => {
  await writeFile(ready, `${process.pid}\n`, { flag: "wx", mode: 0o400 })
  const deadline = Date.now() + 10_000
  while (true) {
    try { await access(release, constants.F_OK); return } catch (cause) {
      if (typeof cause !== "object" || cause === null || !("code" in cause) || cause.code !== "ENOENT") throw cause
    }
    if (Date.now() >= deadline) throw new Error("two-CAS process barrier timed out")
    await new Promise<void>((resolveDelay) => setTimeout(resolveDelay, 5))
  }
}

const main = async (): Promise<void> => {
  const [role, root, ready, release] = process.argv.slice(2)
  if (root === undefined || (role !== "kill-cas1" && role !== "kill-cas2" && role !== "race")) throw new Error("invalid two-CAS process worker arguments")
  const fixture = await input()
  const run = role === "race"
    ? resumeDnrd5V2AdmitTwoCas(fixture.input).pipe(Effect.provide(
        makeDnrd5V2TwoCasBeforeSlotLinkFileLayer(root, () => wait(ready ?? "", release ?? ""))
      ))
    : (role === "kill-cas1" ? submitDnrd5V2AdmitTwoCas(fixture.input) : resumeDnrd5V2AdmitTwoCas(fixture.input)).pipe(Effect.provide(
        makeDnrd5V2TwoCasIoFaultFileLayer(root, [{ point: "slot-link", phase: "after", code: "EIO", onInjected: () => process.kill(process.pid, "SIGKILL") }])
      ))
  const confirmed = await Effect.runPromise(run)
  process.stdout.write(`${JSON.stringify({ pid: process.pid, milestone: confirmed.milestone })}\n`)
}

void main().catch((cause: unknown) => {
  process.stderr.write(`${cause instanceof Error ? cause.stack ?? cause.message : String(cause)}\n`)
  process.exitCode = 1
})
