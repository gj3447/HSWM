#!/usr/bin/env node
/**
 * Effect boundary lint for the HSWM runtime (no dependencies).
 *
 * The runtime's functional-core / Effect-shell split is enforced here rather
 * than by convention:
 *   R1  no module-level `let`
 *   R2  no `Effect.run*` outside the single process boundary helper and the
 *       import.meta.url guard of *-process.ts / *-cli.ts executables
 *   R3  no `throw` statements outside the allowlisted adapter, historical,
 *       and deferred-lane files
 *   R4  no module-level mutable `new Map/Set/WeakMap/WeakSet` unless the
 *       declaration is typed ReadonlyMap/ReadonlySet or allowlisted
 *   R5  no `async` functions outside the POSIX adapter and allowlisted files
 *
 * Allowlisted files carry a reason and a lane; the lint prints per-rule counts
 * so the allowlist can only shrink deliberately.  Exit code 1 on any violation
 * or on a stale allowlist entry (a file or rule that no longer hits).
 *
 *   --all    print every violation instead of the first 80
 *   --json   print the full machine-readable report (per file, per rule) on
 *            stdout; the KG bundle builder consumes this shape
 */
import { readdirSync, readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const here = dirname(fileURLToPath(import.meta.url))
const srcRoot = join(here, "..", "src")
const allowlist = JSON.parse(readFileSync(join(here, "effect-boundary-allowlist.json"), "utf8"))

const files = readdirSync(srcRoot).filter((name) => name.endsWith(".ts")).sort()
const violations = []
const counts = { R1: 0, R2: 0, R3: 0, R4: 0, R5: 0 }
const perFile = {}
const allowed = (rule, file) => {
  const entry = allowlist.files[file]
  return entry !== undefined && entry.rules.includes(rule)
}
const report = (rule, file, line, text) => {
  counts[rule] += 1
  const bucket = (perFile[file] ??= { R1: 0, R2: 0, R3: 0, R4: 0, R5: 0 })
  bucket[rule] += 1
  if (!allowed(rule, file)) violations.push(`${rule} ${file}:${line}: ${text.trim().slice(0, 120)}`)
}

const RUN_BOUNDARY_FILES = new Set(["effect-process-main.ts"])
const isExecutable = (file) => /-process\.ts$|-cli\.ts$/.test(file)

for (const file of files) {
  const source = readFileSync(join(srcRoot, file), "utf8")
  const lines = source.split("\n")
  const guardIndex = lines.findIndex((line) => line.includes("import.meta.url === pathToFileURL"))
  lines.forEach((line, index) => {
    const number = index + 1
    if (/^let\s/.test(line)) report("R1", file, number, line)
    if (/Effect\.run(Promise|Sync|PromiseExit|SyncExit|Fork|Callback)\b/.test(line) && !RUN_BOUNDARY_FILES.has(file)) {
      const inGuard = isExecutable(file) && guardIndex >= 0 && index > guardIndex
      if (!inGuard) report("R2", file, number, line)
    }
    if (/(^|[^\w"'`.])throw\s/.test(line) && !/^\s*(\*|\/\/)/.test(line)) report("R3", file, number, line)
    if (/^(export\s+)?const\s+\w+(\s*:\s*[^=]+)?\s*=\s*new\s+(Weak)?(Map|Set)\b/.test(line) && !/:\s*Readonly(Map|Set)</.test(line)) {
      report("R4", file, number, line)
    }
    if (/(^|[^.\w])async\b/.test(line) && !/^\s*(\*|\/\/)/.test(line)) report("R5", file, number, line)
  })
}

// A stale allowlist entry is itself a violation: the list may only shrink.
const stale = []
for (const [file, entry] of Object.entries(allowlist.files)) {
  if (!files.includes(file)) { stale.push(`STALE ${file}: allowlisted file does not exist`); continue }
  for (const rule of entry.rules) {
    if ((perFile[file]?.[rule] ?? 0) === 0) stale.push(`STALE ${file}: rule ${rule} no longer hits; drop it from the allowlist`)
  }
}
const cleanFiles = files.filter((file) => perFile[file] === undefined).length
const summary = {
  schema_version: "hswm-effect-boundary-lint/v1",
  files: files.length,
  clean_files: cleanFiles,
  counts,
  allowlisted_files: Object.keys(allowlist.files).length,
  violations: violations.length,
  stale_allowlist_entries: stale.length
}
if (process.argv.includes("--json")) {
  const lanes = {}
  for (const [file, entry] of Object.entries(allowlist.files)) (lanes[entry.lane] ??= []).push(file)
  process.stdout.write(JSON.stringify({ ...summary, per_file: perFile, allowlist: allowlist.files, lanes }, null, 2) + "\n")
} else {
  process.stdout.write(JSON.stringify(summary) + "\n")
}
if (violations.length > 0 || stale.length > 0) {
  const limit = process.argv.includes("--all") ? violations.length : 80
  process.stderr.write([...stale, ...violations.slice(0, limit)].join("\n") + (violations.length > limit ? `\n... ${violations.length - limit} more` : "") + "\n")
  process.exitCode = 1
}
