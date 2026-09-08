import { existsSync, readFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { expect, it } from "vitest"
import { Effect, Fiber } from "effect"

import { BoundedSubprocess, NodeBoundedSubprocessLive } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"

const observe = (argv: ReadonlyArray<string>, timeoutMs = 2_000, maximumOutputBytes = 64_000) =>
  Effect.runPromise(Effect.gen(function* () {
    const subprocess = yield* BoundedSubprocess
    return yield* subprocess.observe({ argv, cwd: process.cwd(), environment: process.env as Record<string, string>, timeoutMs, maximumOutputBytes, killProcessGroup: true })
  }).pipe(Effect.provide(NodeBoundedSubprocessLive)))

it("bounds combined output and terminates the owned process group", async () => {
  const marker = join(tmpdir(), `hswm-grandchild-${process.pid}-${Date.now()}`)
  try {
    const source = `const fs=require('fs'),{spawn}=require('child_process'),p=process.argv[1]; const g=spawn(process.execPath,['-e',\"process.on('SIGTERM',()=>{});setInterval(()=>{},1000)\"],{stdio:'ignore'}); fs.writeFileSync(p,String(g.pid)); process.on('SIGTERM',()=>process.exit(0)); setInterval(()=>{},1000)`
    const result = await observe([process.execPath, "-e", source, marker], 80)
    expect(result.timedOut).toBe(true)
    const pid = Number(readFileSync(marker, "utf8"))
    let live = true
    try { process.kill(pid, 0) } catch { live = false }
    expect(live).toBe(false)
  } finally { if (existsSync(marker)) rmSync(marker) }
})

it("cuts output at the declared aggregate byte bound", async () => {
  const result = await observe([process.execPath, "-e", "process.stdout.write('x'.repeat(4096))"], 2_000, 127)
  expect(result.outputTruncated).toBe(true)
  expect(result.stdout.byteLength + result.stderr.byteLength).toBeLessThanOrEqual(127)
})

it("interruption escalates after a leader closes and reaps its descendants", async () => {
  const marker = join(tmpdir(), `hswm-interrupt-grandchild-${process.pid}-${Date.now()}`)
  try {
    const source = `const fs=require('fs'),{spawn}=require('child_process'),p=process.argv[1]; const g=spawn(process.execPath,['-e',\"process.on('SIGTERM',()=>{});setInterval(()=>{},1000)\"],{stdio:'ignore'}); fs.writeFileSync(p,String(g.pid)); process.on('SIGTERM',()=>process.exit(0)); setInterval(()=>{},1000)`
    await Effect.runPromise(Effect.gen(function* () {
      const subprocess = yield* BoundedSubprocess
      const fiber = yield* Effect.fork(subprocess.observe({ argv: [process.execPath, "-e", source, marker], cwd: process.cwd(), environment: process.env as Record<string, string>, timeoutMs: 10_000, maximumOutputBytes: 64_000, killProcessGroup: true }))
      yield* Effect.sleep("50 millis")
      yield* Fiber.interrupt(fiber)
    }).pipe(Effect.provide(NodeBoundedSubprocessLive)))
    const pid = Number(readFileSync(marker, "utf8"))
    let live = true
    try { process.kill(pid, 0) } catch { live = false }
    expect(live).toBe(false)
  } finally { if (existsSync(marker)) rmSync(marker) }
})
