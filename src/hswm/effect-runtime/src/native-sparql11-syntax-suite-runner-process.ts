#!/usr/bin/env node
import { pathToFileURL } from "node:url";
import { Effect } from "effect";
import { runArgvProcessMain, refuse } from "./effect-process-main.js";
import { NativeSparqlSyntaxError, runNativeSparql11SyntaxSuite } from "./native-sparql11-syntax-suite-runner.js";
import { bindPinnedSuiteRoot } from "./native-pinned-suite-binding.js";
const C = "369a90d1a60c021b746df2e411da0ff36258a758", SUITE_PATH = "sparql/sparql11/syntax-query", T = "153277fe050edd1834234c392081b072201336f4", A = "b7470b73dee6854fc42e4b2e8480b96bdcee00ce9e2c7e6b4397d4c43cfbcb40", M = "10bb104ac4823b9b3bdd356a0c07ccfc00e0b198dbd23453910576e4d538417d", TRAQULA_VERSION = "1.3.0", usage = "usage: native-sparql11-syntax-suite-runner --profile sparql11-traqula-comunica-parser-official-syntax-query --suite-root PATH";
const value = (a: readonly string[], n: string) => { const i = a.indexOf(n); return i < 0 ? undefined : a[i + 1]; };
export const runNativeSparql11SyntaxSuiteProcess = (argv: readonly string[]) => Effect.gen(function* () { if (argv.length === 1 && argv[0] === "--help")
    return { stdout: `${usage}\n`, exitCode: 0 }; const p = value(argv, "--profile"), suite = value(argv, "--suite-root"); if (argv.length !== 4 || p !== "sparql11-traqula-comunica-parser-official-syntax-query" || suite === undefined)
    return yield* Effect.fail(refuse(usage)); const binding = yield* bindPinnedSuiteRoot(suite, { commit: C, suitePath: SUITE_PATH, tree: T, archiveSha256: A }).pipe(Effect.mapError(error => refuse(error.detail))); const r = yield* runNativeSparql11SyntaxSuite(binding.root, binding.fileSha256); if (r.manifest_sha256 !== M || r.adapter.version !== TRAQULA_VERSION || r.counts.positive !== 63 || r.counts.negative !== 31 || r.counts.total !== 94)
    return yield* Effect.fail(refuse("pinned manifest, engine, or denominator drift")); yield* bindPinnedSuiteRoot(binding.root, { commit: C, suitePath: SUITE_PATH, tree: T, archiveSha256: A }).pipe(Effect.mapError(error => refuse(error.detail))); return { stdout: `${JSON.stringify({ ...r, profile: p, source_commit: C })}\n`, exitCode: r.status === "PASS" ? 0 : 1 }; }).pipe(Effect.mapError(e => e instanceof NativeSparqlSyntaxError ? refuse(e.detail) : e));
if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href)
    process.exitCode = await runArgvProcessMain({ program: runNativeSparql11SyntaxSuiteProcess, describeFailure: e => e.detail }, process.argv.slice(2));
