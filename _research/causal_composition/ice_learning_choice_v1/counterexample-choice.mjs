#!/usr/bin/env node
// Synthetic, standard-library-only command fixture. It is not an ICE resolver.
const task = "synthetic counterexample investigation"
const claim = "n*n>=n+1 for nonnegative integers"
const phase = process.argv[2]

let raw = ""
process.stdin.setEncoding("utf8")
process.stdin.on("data", (chunk) => { raw += chunk })
process.stdin.on("end", () => {
  try {
    const payload = JSON.parse(raw)
    const context = payload.context ?? {}
    if (payload.task !== task || context.evidence !== "available" || context.goal !== "counterexample") throw new Error("required synthetic premise missing")
    const prior = payload.previous_output === undefined ? {} : JSON.parse(payload.previous_output)
    const witness = (n) => ({ n, lhs: n * n, rhs: n + 1, is_counterexample: n * n < n + 1 })
    const valid = (value) => value !== null && typeof value === "object" && Number.isSafeInteger(value.n) && value.n >= 0 && value.lhs === value.n * value.n && value.rhs === value.n + 1 && value.is_counterexample === (value.lhs < value.rhs) && value.is_counterexample
    if (phase === "check-existing") {
      const found = witness(context.candidate_n)
      if (!valid(found)) throw new Error("declared witness does not refute claim")
      process.stdout.write(JSON.stringify({ check_existing: found, construct_new: prior.construct_new ?? null }))
      return
    }
    if (phase === "construct-new") {
      const found = Array.from({ length: 5 }, (_, n) => witness(n)).find(valid)
      if (!valid(found)) throw new Error("bounded construction found no counterexample")
      process.stdout.write(JSON.stringify({ check_existing: prior.check_existing ?? null, construct_new: found }))
      return
    }
    if (phase === "complete") {
      if (!valid(prior.check_existing) || !valid(prior.construct_new)) throw new Error("both independent synthetic checks are required")
      process.stdout.write(JSON.stringify({ schema_version: "ice-learning-choice-artifact/v1", claim, witnesses: [{ method: "check-existing", n: prior.check_existing.n }, { method: "construct-new", n: prior.construct_new.n }], status: "VALIDATED_SYNTHETIC_COUNTEREXAMPLE" }))
      return
    }
    throw new Error("unknown phase")
  } catch (error) {
    process.stderr.write(`synthetic-fixture-error:${error instanceof Error ? error.message : "unknown"}`)
    process.exitCode = 2
  }
})
