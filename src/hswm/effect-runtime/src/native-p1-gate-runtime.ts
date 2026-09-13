/** Bounded readonly inputs for the offline P1 post-hoc gate diagnostic. */
import { DatabaseSync } from "node:sqlite";
import { createHash } from "node:crypto";
import { join, resolve } from "node:path";
import { Data, Effect, Either } from "effect";
import { PosixFileSystem } from "./effect-posix-filesystem.js";
import { decodeNativeTaskJson, taskJsonRecord, type TaskJson } from "./native-task-json-domain.js";
import { parseNativeP1Snapshot, type NativeP1Snapshot } from "./native-p1-snapshot-domain.js";
import { decodeNativeP1EmbeddingCache, type NativeP1NpyArray } from "./native-p1-npy-domain.js";
import { embedNativeP1Texts, NATIVE_P1_EMBEDDING_BACKEND_PROVENANCE } from "./native-p1-embedding-runtime.js";
import { nativeP1AccurateSum, bootstrapLowerPython, decideFreshGate, type NativeP1GateError } from "./native-p1-gate-domain.js";
import { buildNativeP1Graph, nativeP1CachedRecall, nativeP1TraceGolds, splitNativeP1Questions, type NativeP1Article, type NativeP1Question, type NativeP1RetrievalError } from "./native-p1-retrieval-domain.js";
export class NativeP1GateRuntimeError extends Data.TaggedError("NativeP1GateRuntimeError")<{
    readonly detail: string;
}> {
}
const failure = (detail: string) => new NativeP1GateRuntimeError({ detail });
export interface NativeP1GateCandidate {
    readonly armId: string;
    readonly base: NativeP1Snapshot;
    readonly candidate: NativeP1Snapshot;
    readonly candidateId: string;
    readonly episodeIndex: number;
    readonly finalState: string;
}
const record = (value: TaskJson, label: string): Either.Either<Readonly<Record<string, TaskJson>>, NativeP1GateRuntimeError> => taskJsonRecord(value) ? Either.right(value) : Either.left(failure(`${label} must be an object`));
const text = (value: TaskJson | undefined, label: string): Either.Either<string, NativeP1GateRuntimeError> => typeof value === "string" && value.length > 0 ? Either.right(value) : Either.left(failure(`${label} must be non-empty text`));
const positive = (value: TaskJson | undefined, label: string): Either.Either<number, NativeP1GateRuntimeError> => typeof value === "number" && Number.isInteger(value) && value > 0 ? Either.right(value) : Either.left(failure(`${label} must be a positive integer`));
const lift = <Value>(value: Either.Either<Value, NativeP1GateRuntimeError>): Effect.Effect<Value, NativeP1GateRuntimeError> => Either.match(value, { onLeft: Effect.fail, onRight: Effect.succeed });
const sqlite = <A>(read: () => A): Effect.Effect<A, NativeP1GateRuntimeError> => Effect.try({
    try: read, catch: error => failure(error instanceof Error ? `cannot read P1 SQLite: ${error.message}` : "cannot read P1 SQLite"),
});
const snapshots = (databasePath: string, baseId: string, candidateId: string): Effect.Effect<readonly [
    NativeP1Snapshot,
    NativeP1Snapshot
], NativeP1GateRuntimeError> => Effect.acquireUseRelease(sqlite(() => new DatabaseSync(databasePath, { readOnly: true })), database => Effect.gen(function* () {
    const staged = yield* sqlite(() => database.prepare("SELECT snapshot_id FROM staged_weight_candidates WHERE candidate_id = ?").get(candidateId));
    if (typeof staged?.["snapshot_id"] !== "string")
        return yield* Effect.fail(failure(`missing staged candidate ${candidateId}`));
    const fetch = (snapshotId: string) => Effect.gen(function* () {
        const row = yield* sqlite(() => database.prepare("SELECT canonical_snapshot FROM weight_snapshots WHERE snapshot_id = ?").get(snapshotId));
        if (!(row?.["canonical_snapshot"] instanceof Uint8Array))
            return yield* Effect.fail(failure(`missing snapshot ${snapshotId}`));
        const parsed = parseNativeP1Snapshot(row["canonical_snapshot"]);
        if (Either.isLeft(parsed))
            return yield* Effect.fail(failure(parsed.left.detail));
        return parsed.right;
    });
    return Object.freeze([yield* fetch(baseId), yield* fetch(staged["snapshot_id"])] as const);
}), database => Effect.sync(() => database.close()));
export const loadNativeP1GateCandidates = (evidencePath: string, experimentDirectory: string): Effect.Effect<readonly NativeP1GateCandidate[], NativeP1GateRuntimeError, PosixFileSystem> => Effect.gen(function* () {
    const fs = yield* PosixFileSystem, bytes = yield* fs.readRegularBounded(evidencePath, { maximumBytes: 64 * 1024 * 1024, minimumBytes: 1, operation: "P1 evidence" }).pipe(Effect.map(value => value.bytes), Effect.mapError(error => failure(error.detail))), decoded = decodeNativeTaskJson(bytes, { maximumBytes: 64 * 1024 * 1024 });
    if (Either.isLeft(decoded))
        return yield* Effect.fail(failure("invalid P1 evidence JSON"));
    const root = yield* lift(record(decoded.right, "P1 evidence"));
    const experiment = yield* lift(record(root["experiment_receipt"] ?? null, "experiment_receipt"));
    const arms = experiment["arms"];
    if (!Array.isArray(arms))
        return yield* Effect.fail(failure("experiment_receipt.arms must be an array"));
    const out: NativeP1GateCandidate[] = [];
    for (const armValue of arms) {
        const arm = yield* lift(record(armValue, "arm"));
        const armId = yield* lift(text(arm["arm_id"], "arm_id"));
        const episodes = arm["episodes"];
        if (!Array.isArray(episodes))
            return yield* Effect.fail(failure(`episodes must be an array for ${armId}`));
        const databasePath = join(resolve(experimentDirectory), "arms", `${armId}.weights.sqlite3`);
        for (const episodeValue of episodes) {
            const episode = yield* lift(record(episodeValue, "episode"));
            const candidate = episode["candidate_id"];
            if (candidate === null)
                continue;
            const candidateId = yield* lift(text(candidate, "candidate_id"));
            const baseId = yield* lift(text(episode["base_snapshot_id"], "base_snapshot_id"));
            const episodeIndex = yield* lift(positive(episode["episode_index"], "episode_index"));
            const finalState = yield* lift(text(episode["fsm_final_state"], "fsm_final_state"));
            const loaded = yield* snapshots(databasePath, baseId, candidateId);
            out.push(Object.freeze({ armId, base: loaded[0], candidate: loaded[1], candidateId, episodeIndex, finalState }));
        }
    }
    return Object.freeze(out);
});
export const decodeNativeP1GateCommand = (argv: readonly string[]): Either.Either<Readonly<{
    readonly datasetRoot: string;
    readonly embeddingCacheFolder: string;
    readonly evidence: string;
    readonly experimentDirectory: string;
    readonly output: string;
}>, NativeP1GateRuntimeError> => {
    const values: Record<string, string> = {};
    for (let index = 0; index < argv.length; index += 2) {
        const key = argv[index], value = argv[index + 1];
        if (!["--evidence", "--dataset-root", "--experiment-directory", "--embedding-cache-folder", "--output"].includes(key ?? "") || value === undefined || values[key!] !== undefined)
            return Either.left(failure("usage: --evidence FILE --dataset-root DIR --experiment-directory DIR --embedding-cache-folder DIR --output FILE"));
        values[key!] = value;
    }
    return Object.keys(values).length === 5 ? Either.right(Object.freeze({ datasetRoot: values["--dataset-root"]!, embeddingCacheFolder: values["--embedding-cache-folder"]!, evidence: values["--evidence"]!, experimentDirectory: values["--experiment-directory"]!, output: values["--output"]! })) : Either.left(failure("usage: --evidence FILE --dataset-root DIR --experiment-directory DIR --embedding-cache-folder DIR --output FILE"));
};
export interface NativeP1GateDiagnostic {
    readonly embedding_backend?: TaskJson;
    readonly candidate_gates: readonly Readonly<{
        readonly arm_id: string;
        readonly candidate_id: string;
        readonly episode_index: number;
        readonly fresh_gate_pass: boolean;
        readonly recorded_fsm_final_state: string;
        readonly unseen_ci_low: number;
        readonly unseen_delta: number;
    }>[];
    readonly frozen_split_manifest_sha256: string;
    readonly source_evidence_sha256: string;
}
const shaBytes = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex");
const canonical = (value: unknown): string => value === null || typeof value !== "object" ? JSON.stringify(value) : Array.isArray(value) ? `[${value.map(canonical).join(",")}]` : `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical((value as Readonly<Record<string, unknown>>)[key])}`).join(",")}}`;
const canonicalSha = (value: unknown): string => shaBytes(new TextEncoder().encode(canonical(value)));
const runtimeLift = <A>(value: Either.Either<A, NativeP1GateRuntimeError | NativeP1GateError | NativeP1RetrievalError>): Effect.Effect<A, NativeP1GateRuntimeError> => Either.match(value, { onLeft: error => Effect.fail(failure(error.detail)), onRight: Effect.succeed });
const taskArray = (value: TaskJson, label: string): Either.Either<readonly TaskJson[], NativeP1GateRuntimeError> => Array.isArray(value) ? Either.right(value) : Either.left(failure(`${label} must be an array`));
const article = (value: TaskJson): Either.Either<NativeP1Article, NativeP1GateRuntimeError> => {
    const row = record(value, "article");
    if (Either.isLeft(row))
        return Either.left(row.left);
    const title = text(row.right["title"], "article.title"), body = text(row.right["article"], "article.article"), facts = taskArray(row.right["facts"] ?? null, "article.facts");
    if (Either.isLeft(title) || Either.isLeft(body) || Either.isLeft(facts) || facts.right.some(item => typeof item !== "string"))
        return Either.left(failure("invalid PhantomWiki article"));
    return Either.right(Object.freeze({ title: title.right, article: body.right, facts: Object.freeze(facts.right as readonly string[]) }));
};
const question = (value: TaskJson): Either.Either<NativeP1Question, NativeP1GateRuntimeError> => {
    const row = record(value, "question");
    if (Either.isLeft(row))
        return Either.left(row.left);
    const id = text(row.right["id"], "question.id"), body = text(row.right["question"], "question.question");
    if (Either.isLeft(id) || Either.isLeft(body))
        return Either.left(failure("invalid PhantomWiki question"));
    const answer = row.right["answer"], aggregation = row.right["is_aggregation_question"], traces = row.right["solution_traces"];
    return Either.right(Object.freeze({ id: id.right, question: body.right, is_aggregation_question: aggregation === true, ...(Array.isArray(answer) ? { answer: Object.freeze(answer) } : {}), ...(traces === undefined ? {} : { solution_traces: traces }) }));
};
const loadDataset = (datasetRoot: string): Effect.Effect<Readonly<{
    readonly articles: readonly NativeP1Article[];
    readonly questions: readonly NativeP1Question[];
    readonly splitManifestSha: string;
}>, NativeP1GateRuntimeError, PosixFileSystem> => Effect.gen(function* () {
    const fs = yield* PosixFileSystem, universe = join(resolve(datasetRoot), "sparse_t200_fk1"), articlePath = join(universe, "articles.json"), articleBytes = yield* fs.readRegularBounded(articlePath, { maximumBytes: 512 * 1024 * 1024, minimumBytes: 1, operation: "P1 articles" }).pipe(Effect.mapError(error => failure(error.detail))), decoded = decodeNativeTaskJson(articleBytes.bytes, { maximumBytes: 512 * 1024 * 1024 });
    if (Either.isLeft(decoded) || !Array.isArray(decoded.right))
        return yield* Effect.fail(failure("invalid P1 articles JSON"));
    const parsedArticles: NativeP1Article[] = [];
    for (const value of decoded.right) {
        const parsed = article(value);
        if (Either.isLeft(parsed))
            return yield* Effect.fail(parsed.left);
        parsedArticles.push(parsed.right);
    }
    const questionDirectory = join(universe, "questions"), entries = yield* fs.listDirectory(questionDirectory, "P1 questions").pipe(Effect.mapError(error => failure(error.detail)));
    const names = entries.filter(entry => entry.kind === "FILE" && /^type.*\.json$/.test(entry.name)).map(entry => entry.name).sort();
    let questions: readonly NativeP1Question[] = [];
    const hashes: Readonly<{
        readonly path: string;
        readonly sha256: string;
    }>[] = [];
    for (const name of names) {
        const path = join(questionDirectory, name), bytes = yield* fs.readRegularBounded(path, { maximumBytes: 512 * 1024 * 1024, minimumBytes: 1, operation: "P1 questions" }).pipe(Effect.mapError(error => failure(error.detail))), value = decodeNativeTaskJson(bytes.bytes, { maximumBytes: 512 * 1024 * 1024 });
        if (Either.isLeft(value) || !Array.isArray(value.right))
            return yield* Effect.fail(failure("invalid P1 questions JSON"));
        const next: NativeP1Question[] = [];
        for (const raw of value.right) {
            const parsed = question(raw);
            if (Either.isLeft(parsed))
                return yield* Effect.fail(parsed.left);
            next.push(parsed.right);
        }
        questions = Object.freeze([...questions, ...next]);
        hashes.push(Object.freeze({ path: name, sha256: shaBytes(bytes.bytes) }));
    }
    const split = yield* runtimeLift(splitNativeP1Questions(questions, parsedArticles));
    const splitManifest = { episodes: split.episodeQuestions.map(group => group.map(question => question.id)), fresh_gates: split.gateQuestions.map(group => group.map(question => question.id)), schema_version: "hswm-p1-phantom-split/v1", universe: "sparse_t200_fk1", boot_seed: 9173, dataset_files: { "articles.json": shaBytes(articleBytes.bytes), question_files_root: canonicalSha(hashes) } };
    return Object.freeze({ articles: parsedArticles, questions, splitManifestSha: canonicalSha(splitManifest) });
});
export const evaluateNativeP1Gate = (evidencePath: string, datasetRoot: string, experimentDirectory: string, embeddingCacheFolder?: string): Effect.Effect<NativeP1GateDiagnostic, NativeP1GateRuntimeError, PosixFileSystem> => Effect.gen(function* () {
    const fs = yield* PosixFileSystem, evidenceBytes = yield* fs.readRegularBounded(evidencePath, { maximumBytes: 64 * 1024 * 1024, minimumBytes: 1, operation: "P1 evidence" }).pipe(Effect.mapError(error => failure(error.detail))), dataset = yield* loadDataset(datasetRoot), graph = yield* runtimeLift(buildNativeP1Graph(dataset.articles)), split = yield* runtimeLift(splitNativeP1Questions(dataset.questions, dataset.articles)), cacheRead = yield* Effect.either(fs.readRegularBounded(join(resolve(experimentDirectory), "p1_phantom_embeddings.npz"), { maximumBytes: 2 * 1024 * 1024 * 1024, minimumBytes: 1, operation: "P1 embedding cache" }));
    const ordered = dataset.articles.slice().sort((left, right) => left.title < right.title ? -1 : left.title > right.title ? 1 : 0), allQuestions = Object.freeze([...split.episodeQuestions.flat(), ...split.gateQuestions.flat()]), manifest = canonicalSha({ model: "all-MiniLM-L6-v2", documents: ordered.map(item => canonicalSha(item.article)), questions: allQuestions.map(item => ({ id: item.id, sha256: canonicalSha(item.question) })) });
    let embeddingBackend: TaskJson | undefined;
    let cached: Readonly<{
        readonly documents: NativeP1NpyArray;
        readonly questionIds: NativeP1NpyArray;
        readonly questions: NativeP1NpyArray;
    }>;
    if (Either.isRight(cacheRead)) {
        const cache = decodeNativeP1EmbeddingCache(cacheRead.right.bytes, manifest);
        if (Either.isLeft(cache))
            return yield* Effect.fail(failure(cache.left.detail));
        cached = cache.right;
    }
    else {
        if (cacheRead.left.code !== "ENOENT" || embeddingCacheFolder === undefined)
            return yield* Effect.fail(failure(cacheRead.left.detail));
        const vectors = yield* embedNativeP1Texts(join(resolve(embeddingCacheFolder), "native-p1-onnx"), Object.freeze([...ordered.map(item => item.article), ...allQuestions.map(item => item.question)])).pipe(Effect.mapError(error => failure(error.detail)));
        const documents = Object.freeze(vectors.slice(0, ordered.length).flat()), questions = Object.freeze(vectors.slice(ordered.length).flat());
        const vectorBytes = Buffer.alloc(vectors.length * 384 * 8);
        vectors.forEach((row, i) => row.forEach((value, j) => vectorBytes.writeDoubleLE(value, (i * 384 + j) * 8)));
        embeddingBackend = Object.freeze({ ...NATIVE_P1_EMBEDDING_BACKEND_PROVENANCE, input_manifest_sha256: manifest,
            document_count: ordered.length, question_count: allQuestions.length, ordered_vectors_f64le_sha256: shaBytes(vectorBytes) });
        cached = Object.freeze({ documents: Object.freeze({ dtype: "f8", shape: Object.freeze([ordered.length, 384]), values: documents }), questionIds: Object.freeze({ dtype: "unicode", shape: Object.freeze([allQuestions.length]), values: Object.freeze(allQuestions.map(item => item.id)) }), questions: Object.freeze({ dtype: "f8", shape: Object.freeze([allQuestions.length, 384]), values: questions }) });
    }
    const candidates = yield* loadNativeP1GateCandidates(evidencePath, experimentDirectory), titles = Object.freeze(Object.fromEntries(dataset.articles.map(item => [item.title, 1])));
    const rows = [] as {
        arm_id: string;
        candidate_id: string;
        episode_index: number;
        fresh_gate_pass: boolean;
        recorded_fsm_final_state: string;
        unseen_ci_low: number;
        unseen_delta: number;
    }[];
    for (const item of candidates) {
        const questions = split.gateQuestions[item.episodeIndex - 1];
        if (questions === undefined)
            return yield* Effect.fail(failure(`invalid episode index ${item.episodeIndex}`));
        const baseWeights = Object.freeze(Object.fromEntries(item.base.weights.map(weight => [weight.edge_id, weight.log_salience]))), candidateWeights = Object.freeze(Object.fromEntries(item.candidate.weights.map(weight => [weight.edge_id, weight.log_salience])));
        const deltas: number[] = [];
        for (const fresh of questions) {
            const golds = nativeP1TraceGolds(fresh, titles), base = yield* runtimeLift(nativeP1CachedRecall(graph, cached.documents, cached.questionIds, cached.questions, fresh, baseWeights, golds)), candidate = yield* runtimeLift(nativeP1CachedRecall(graph, cached.documents, cached.questionIds, cached.questions, fresh, candidateWeights, golds));
            deltas.push(candidate - base);
        }
        const delta = nativeP1AccurateSum(deltas) / deltas.length, seed = BigInt(`0x${canonicalSha({ arm: item.armId, episode: item.episodeIndex }).slice(0, 16)}`), low = yield* runtimeLift(bootstrapLowerPython(deltas, seed)), decision = yield* runtimeLift(decideFreshGate(delta, low));
        rows.push(Object.freeze({ arm_id: item.armId, candidate_id: item.candidateId, episode_index: item.episodeIndex, fresh_gate_pass: decision.fresh_gate_pass, recorded_fsm_final_state: item.finalState, unseen_ci_low: decision.unseen_ci_low, unseen_delta: decision.unseen_delta }));
    }
    return Object.freeze({ candidate_gates: Object.freeze(rows), frozen_split_manifest_sha256: dataset.splitManifestSha, source_evidence_sha256: shaBytes(evidenceBytes.bytes),
        ...(embeddingBackend === undefined ? {} : { embedding_backend: embeddingBackend }) });
});
