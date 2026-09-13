#!/usr/bin/env node
/** Process boundary for the pinned RDF 1.1 N-Quads successor runner. */
import { pathToFileURL } from "node:url";
import { Effect } from "effect";
import { runArgvProcessMain, refuse } from "./effect-process-main.js";
import { NativeNQuadsSuiteError, runNativeRdf11NQuadsSuite } from "./native-graph-standards-suite-runner.js";
import { bindPinnedSuiteRoot } from "./native-pinned-suite-binding.js";
const usage = "usage: native-graph-standards-suite-runner --profile rdf11-nquads-n3-native-ts --suite-root PATH";
const COMMIT = "369a90d1a60c021b746df2e411da0ff36258a758", SUITE_PATH = "rdf/rdf11/rdf-n-quads", TREE = "15ea3f8713598aecc2cdf16d44487e43eeacb146", ARCHIVE = "192534988e00895f5d4be9fe0dc3e5b72d1b11fcabf1858060fcf833a701b784", MANIFEST = "4c658a4e111adff512e89ff2c39acf9195109592f54711ce06823dac544c62ca", N3_VERSION = "2.7.2";
const value = (argv: readonly string[], name: string): string | undefined => { const index = argv.indexOf(name); return index < 0 ? undefined : argv[index + 1]; };
export const runNativeNQuadsSuiteProcess = (argv: readonly string[]) => Effect.gen(function* () {
    if (argv.length === 1 && argv[0] === "--help")
        return { stdout: `${usage}\n`, exitCode: 0 };
    const profile = value(argv, "--profile"), suiteRoot = value(argv, "--suite-root");
    if (argv.length !== 4 || profile !== "rdf11-nquads-n3-native-ts" || suiteRoot === undefined)
        return yield* Effect.fail(refuse(usage));
    const binding = yield* bindPinnedSuiteRoot(suiteRoot, { commit: COMMIT, suitePath: SUITE_PATH, tree: TREE, archiveSha256: ARCHIVE }).pipe(Effect.mapError(error => refuse(error.detail)));
    const result = yield* runNativeRdf11NQuadsSuite(binding.root, binding.fileSha256);
    if (result.manifest_sha256 !== MANIFEST || result.adapter.version !== N3_VERSION || result.counts.positive !== 53 || result.counts.negative !== 32 || result.counts.total !== 85)
        return yield* Effect.fail(refuse("pinned suite manifest, engine, or denominator drift"));
    yield* bindPinnedSuiteRoot(binding.root, { commit: COMMIT, suitePath: SUITE_PATH, tree: TREE, archiveSha256: ARCHIVE }).pipe(Effect.mapError(error => refuse(error.detail)));
    return { stdout: `${JSON.stringify({ ...result, profile: "rdf11-nquads-n3-native-ts", source_commit: COMMIT })}\n`, exitCode: result.status === "PASS" ? 0 : 1 };
}).pipe(Effect.mapError(error => error instanceof NativeNQuadsSuiteError ? refuse(error.detail) : error));
if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href)
    process.exitCode = await runArgvProcessMain({ program: runNativeNQuadsSuiteProcess, describeFailure: error => error.detail }, process.argv.slice(2));
