/**
 * Durable, trusted-local persistence for the adaptive prototype. This is not a
 * Canonical Atom v2 admission path.
 */
import { createHash, randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { Context, Data, Effect, Either, Layer } from "effect";
export interface AdaptiveAtomReference {
    readonly role: string;
    readonly uid: string;
}
export interface AdaptiveAtom {
    readonly uid: string;
    readonly kind: string;
    readonly owner: string;
    readonly refs: ReadonlyArray<AdaptiveAtomReference>;
    readonly payload: unknown;
}
export interface AdaptiveAtomHead {
    readonly uid: string;
    readonly revision: number;
    readonly kind: string;
    readonly owner: string;
    readonly digest: string;
}
export interface AdaptiveAtomRevision extends AdaptiveAtom {
    readonly revision: number;
    readonly digest: string;
    readonly eventId: string | null;
}
export interface AdaptiveStoreEvent {
    readonly eventId: string;
    readonly intentDigest: string;
    readonly source: Record<string, unknown>;
    readonly consumed: ReadonlyArray<AdaptiveAtomHead>;
    readonly produced: ReadonlyArray<AdaptiveAtomHead>;
    readonly outputHeads: ReadonlyArray<AdaptiveAtomHead>;
}
export interface AdaptiveRewrite {
    readonly graphId: string;
    readonly eventId: string;
    readonly expected: Readonly<Record<string, number>>;
    readonly atoms: ReadonlyArray<AdaptiveAtom>;
    readonly source: Readonly<Record<string, unknown>>;
}
export class AdaptiveStoreError extends Data.TaggedError("AdaptiveStoreError")<{
    readonly operation: "INITIALIZE" | "HEAD" | "HEADS" | "GET_REVISION" | "REWRITE" | "GET_EVENT" | "EVENTS" | "ACQUIRE_RUNTIME_LOCK" | "RELEASE_RUNTIME_LOCK" | "CLOSE";
    readonly detail: string;
}> {
}
export class AdaptiveStore extends Context.Tag("hswm/AdaptiveStore")<AdaptiveStore, {
    readonly initialize: (graphId: string, manifestDigest: string, atoms: ReadonlyArray<AdaptiveAtom>) => Effect.Effect<ReadonlyArray<AdaptiveAtomHead>, AdaptiveStoreError>;
    readonly head: (graphId: string, uid: string) => Effect.Effect<AdaptiveAtomHead, AdaptiveStoreError>;
    readonly heads: (graphId: string, kind?: string) => Effect.Effect<ReadonlyArray<AdaptiveAtomHead>, AdaptiveStoreError>;
    readonly getRevision: (graphId: string, uid: string, revision: number) => Effect.Effect<AdaptiveAtomRevision, AdaptiveStoreError>;
    readonly rewrite: (input: AdaptiveRewrite) => Effect.Effect<AdaptiveStoreEvent, AdaptiveStoreError>;
    readonly getEvent: (graphId: string, eventId: string) => Effect.Effect<AdaptiveStoreEvent, AdaptiveStoreError>;
    readonly events: (graphId: string) => Effect.Effect<ReadonlyArray<AdaptiveStoreEvent>, AdaptiveStoreError>;
    readonly acquireRuntimeLock: (graphId: string) => Effect.Effect<string, AdaptiveStoreError>;
    readonly releaseRuntimeLock: (graphId: string, token: string) => Effect.Effect<void, AdaptiveStoreError>;
}>() {
}
type Op = AdaptiveStoreError["operation"];
type Row = Record<string, unknown>;
type Result<A> = Either.Either<A, AdaptiveStoreError>;
const fail = <A = never>(operation: Op, detail: string): Result<A> => Either.left(new AdaptiveStoreError({ operation, detail }));
const message = (cause: unknown, fallback: string) => cause instanceof Error ? cause.message : fallback;
const db = <A>(operation: Op, action: () => A): Result<A> => Either.try({ try: action, catch: (cause) => new AdaptiveStoreError({ operation, detail: message(cause, "SQLite operation failed") }) });
const toEffect = <A>(result: Result<A>): Effect.Effect<A, AdaptiveStoreError> => Either.match(result, { onLeft: Effect.fail, onRight: Effect.succeed });
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const hash = (value: string) => createHash("sha256").update(value, "utf8").digest("hex");
const row = (value: unknown) => value as Row | undefined;
const rows = (value: unknown) => value as ReadonlyArray<Row>;
const string = (value: unknown) => String(value);
const numeric = (value: unknown) => typeof value === "number" ? value : Number(value);
const head = (value: Row): AdaptiveAtomHead => Object.freeze({ uid: string(value["uid"]), revision: numeric(value["revision"]), kind: string(value["kind"]), owner: string(value["owner"]), digest: string(value["digest"] ?? value["atom_digest"]) });
const blob = (value: unknown) => Buffer.from(value as Uint8Array).toString("utf8");
const json = (value: unknown, operation: Op, depth = 0): Result<string> => {
    if (depth > 64)
        return fail(operation, "JSON nesting exceeds the bounded store surface");
    if (value === null || typeof value === "string" || typeof value === "boolean")
        return Either.right(JSON.stringify(value));
    if (typeof value === "number")
        return Number.isFinite(value) ? Either.right(JSON.stringify(value)) : fail(operation, "value is not canonical JSON");
    if (Array.isArray(value))
        return Either.all(value.map((item) => json(item, operation, depth + 1))).pipe(Either.map((items) => `[${items.join(",")}]`));
    if (!record(value))
        return fail(operation, "value is not canonical JSON");
    return Either.all(Object.keys(value).sort().map((key) => json(value[key], operation, depth + 1).pipe(Either.map((item) => `${JSON.stringify(key)}:${item}`)))).pipe(Either.map((items) => `{${items.join(",")}}`));
};
const atom = (value: unknown, operation: Op): Result<AdaptiveAtom> => Either.gen(function* () {
    if (!record(value) || Object.keys(value).length !== 5 || !["uid", "kind", "owner", "refs", "payload"].every((key) => key in value))
        return yield* fail(operation, "atom shape is invalid");
    const { uid, kind, owner, refs, payload } = value;
    if (typeof uid !== "string" || !uid || typeof kind !== "string" || !kind || typeof owner !== "string" || !owner || !Array.isArray(refs))
        return yield* fail(operation, "atom identity or refs are invalid");
    const checked = yield* Either.all(refs.map((ref) => record(ref) && Object.keys(ref).length === 2 && typeof ref["role"] === "string" && !!ref["role"] && typeof ref["uid"] === "string" && !!ref["uid"] ? Either.right(Object.freeze({ role: ref["role"], uid: ref["uid"] })) : fail<AdaptiveAtomReference>(operation, "atom reference is invalid")));
    if (new Set(checked.map((ref) => `${ref["role"]}\u0000${ref["uid"]}`)).size !== checked.length)
        return yield* fail(operation, "duplicate role reference");
    yield* json(payload, operation);
    return Object.freeze({ uid, kind, owner, refs: Object.freeze(checked), payload });
});
// Stored Python JSON bytes are intentional: a historic 1.0 must not become 1.
const rawAtom = (uid: string, kind: string, owner: string, refs: string, payload: string) => `{\"kind\":${JSON.stringify(kind)},\"owner\":${JSON.stringify(owner)},\"payload\":${payload},\"refs\":${refs},\"uid\":${JSON.stringify(uid)}}`;
const digest = (value: AdaptiveAtom, operation: Op) => json(value, operation).pipe(Either.map(hash));
const schema = `CREATE TABLE IF NOT EXISTS adaptive_graphs (graph_id TEXT PRIMARY KEY, manifest_digest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS adaptive_atoms (graph_id TEXT NOT NULL, uid TEXT NOT NULL, revision INTEGER NOT NULL, kind TEXT NOT NULL, owner TEXT NOT NULL, refs_json BLOB NOT NULL, payload_json BLOB NOT NULL, atom_digest TEXT NOT NULL, event_id TEXT, PRIMARY KEY (graph_id, uid, revision), FOREIGN KEY (graph_id) REFERENCES adaptive_graphs(graph_id));
CREATE TABLE IF NOT EXISTS adaptive_heads (graph_id TEXT NOT NULL, uid TEXT NOT NULL, revision INTEGER NOT NULL, kind TEXT NOT NULL, owner TEXT NOT NULL, atom_digest TEXT NOT NULL, PRIMARY KEY (graph_id, uid), FOREIGN KEY (graph_id, uid, revision) REFERENCES adaptive_atoms(graph_id, uid, revision));
CREATE TABLE IF NOT EXISTS adaptive_events (graph_id TEXT NOT NULL, event_id TEXT NOT NULL, intent_digest TEXT NOT NULL, source_json BLOB NOT NULL, consumed_json BLOB NOT NULL, produced_json BLOB NOT NULL, PRIMARY KEY (graph_id, event_id), FOREIGN KEY (graph_id) REFERENCES adaptive_graphs(graph_id));
CREATE TABLE IF NOT EXISTS adaptive_runtime_locks (graph_id TEXT PRIMARY KEY, token TEXT NOT NULL, pid INTEGER NOT NULL, FOREIGN KEY (graph_id) REFERENCES adaptive_graphs(graph_id));`;
const openDatabase = (path: string): Effect.Effect<DatabaseSync, AdaptiveStoreError> => {
    if (!path)
        return Effect.fail(new AdaptiveStoreError({ operation: "INITIALIZE", detail: "store path is invalid" }));
    const directory: Effect.Effect<void, AdaptiveStoreError> = path === ":memory:" ? Effect.succeed(undefined) : Effect.try({ try: () => mkdirSync(dirname(path), { recursive: true }), catch: (cause) => new AdaptiveStoreError({ operation: "INITIALIZE", detail: message(cause, "store directory initialization failed") }) }).pipe(Effect.asVoid);
    return directory.pipe(Effect.flatMap(() => Effect.suspend(() => toEffect(db("INITIALIZE", () => new DatabaseSync(path, { timeout: 10000, allowExtension: false }))))));
};
export const makeAdaptiveStoreSqliteLayer = (path: string) => Layer.scoped(AdaptiveStore, Effect.acquireRelease(openDatabase(path), (database) => toEffect(db("CLOSE", () => database.close())).pipe(Effect.orDie)).pipe(Effect.tap((database) => Effect.suspend(() => toEffect(db("INITIALIZE", () => database.exec("PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL;"))))), Effect.tap((database) => Effect.suspend(() => toEffect(db("INITIALIZE", () => database.exec(schema))))), Effect.map((database) => AdaptiveStore.of(service(database)))));
const service = (database: DatabaseSync) => {
    const native = <A>(operation: Op, action: () => A) => db(operation, action);
    const graph = (operation: Op, graphId: string): Result<void> => native(operation, () => row(database.prepare("SELECT 1 FROM adaptive_graphs WHERE graph_id=?").get(graphId))).pipe(Either.flatMap((found) => found ? Either.right(undefined) : fail(operation, "graph does not exist")));
    const storedJson = (operation: Op, value: unknown, label: string): Result<unknown> => native(operation, () => row(database.prepare("SELECT json_valid(CAST(? AS TEXT)) AS valid").get(value as Uint8Array))).pipe(Either.flatMap((valid) => numeric(valid?.["valid"]) === 1 ? Either.right(JSON.parse(blob(value))) : fail(operation, `stored ${label} is malformed`)));
    const allHeads = (operation: Op, graphId: string, kind?: string): Result<ReadonlyArray<AdaptiveAtomHead>> => Either.gen(function* () {
        yield* graph(operation, graphId);
        const found = yield* native(operation, () => kind === undefined ? rows(database.prepare("SELECT uid,revision,kind,owner,atom_digest AS digest FROM adaptive_heads WHERE graph_id=? ORDER BY uid").all(graphId)) : rows(database.prepare("SELECT uid,revision,kind,owner,atom_digest AS digest FROM adaptive_heads WHERE graph_id=? AND kind=? ORDER BY uid").all(graphId, kind)));
        return Object.freeze(found.map(head));
    });
    const event = (operation: Op, graphId: string, eventId: string): Result<AdaptiveStoreEvent> => Either.gen(function* () {
        yield* graph(operation, graphId);
        const found = yield* native(operation, () => row(database.prepare("SELECT * FROM adaptive_events WHERE graph_id=? AND event_id=?").get(graphId, eventId)));
        if (!found)
            return yield* fail(operation, "event does not exist");
        const source = yield* storedJson(operation, found["source_json"], "source");
        const consumed = yield* storedJson(operation, found["consumed_json"], "consumed");
        const produced = yield* storedJson(operation, found["produced_json"], "produced");
        const parse = (items: unknown): Result<ReadonlyArray<AdaptiveAtomHead>> => Array.isArray(items) ? Either.all(items.map((item) => record(item) ? Either.right(head(item)) : fail<AdaptiveAtomHead>(operation, "stored event is malformed"))).pipe(Either.map((items) => Object.freeze(items))) : fail(operation, "stored event is malformed");
        if (!record(source))
            return yield* fail(operation, "stored event is malformed");
        const outputHeads = yield* parse(produced);
        return Object.freeze({ eventId, intentDigest: string(found["intent_digest"]), source, consumed: yield* parse(consumed), produced: outputHeads, outputHeads });
    });
    const transaction = <A>(operation: Op, body: () => Result<A>): Result<A> => Either.gen(function* () {
        yield* native(operation, () => database.exec("BEGIN IMMEDIATE"));
        const outcome = body();
        if (Either.isRight(outcome)) {
            const committed = native(operation, () => database.exec("COMMIT"));
            if (Either.isRight(committed))
                return outcome.right;
            native(operation, () => database.exec("ROLLBACK"));
            return yield* Either.map(committed, () => outcome.right);
        }
        native(operation, () => database.exec("ROLLBACK"));
        return yield* outcome;
    });
    const effect = <A>(evaluate: () => Result<A>): Effect.Effect<A, AdaptiveStoreError> => Effect.suspend(() => toEffect(evaluate()));
    const live = (pid: number) => { try {
        process.kill(pid, 0);
        return true;
    }
    catch (cause) {
        return !(record(cause) && cause["code"] === "ESRCH");
    } };
    return {
        initialize: (graphId: string, manifestDigest: string, input: ReadonlyArray<AdaptiveAtom>) => effect(() => Either.gen(function* () {
            if (!graphId || !manifestDigest)
                return yield* fail("INITIALIZE", "graph identity is invalid");
            const atoms = yield* Either.all(input.map((item) => atom(item, "INITIALIZE")));
            if (!atoms.length || new Set(atoms.map((item) => item["uid"])).size !== atoms.length)
                return yield* fail("INITIALIZE", "initial atoms must be unique and non-empty");
            const uids = new Set(atoms.map((item) => item["uid"]));
            if (atoms.some((item) => item.refs.some((ref) => !uids.has(ref["uid"]))))
                return yield* fail("INITIALIZE", "initial reference is unresolved");
            return yield* transaction("INITIALIZE", () => Either.gen(function* () {
                const old = yield* native("INITIALIZE", () => row(database.prepare("SELECT manifest_digest FROM adaptive_graphs WHERE graph_id=?").get(graphId)));
                if (old)
                    return string(old["manifest_digest"]) === manifestDigest ? yield* allHeads("INITIALIZE", graphId) : yield* fail("INITIALIZE", "graph manifest digest conflict");
                yield* native("INITIALIZE", () => database.prepare("INSERT INTO adaptive_graphs VALUES(?,?)").run(graphId, manifestDigest));
                const putAtom = yield* native("INITIALIZE", () => database.prepare("INSERT INTO adaptive_atoms VALUES(?,?,?,?,?,?,?,?,?)"));
                const putHead = yield* native("INITIALIZE", () => database.prepare("INSERT INTO adaptive_heads VALUES(?,?,?,?,?,?)"));
                for (const item of atoms) {
                    const refs = yield* json(item.refs, "INITIALIZE");
                    const payload = yield* json(item.payload, "INITIALIZE");
                    const itemDigest = yield* digest(item, "INITIALIZE");
                    yield* native("INITIALIZE", () => putAtom.run(graphId, item["uid"], 1, item["kind"], item["owner"], Buffer.from(refs), Buffer.from(payload), itemDigest, null));
                    yield* native("INITIALIZE", () => putHead.run(graphId, item["uid"], 1, item["kind"], item["owner"], itemDigest));
                }
                return yield* allHeads("INITIALIZE", graphId);
            }));
        })),
        head: (graphId: string, uid: string) => effect(() => Either.gen(function* () { yield* graph("HEAD", graphId); const found = yield* native("HEAD", () => row(database.prepare("SELECT uid,revision,kind,owner,atom_digest AS digest FROM adaptive_heads WHERE graph_id=? AND uid=?").get(graphId, uid))); return found ? head(found) : yield* fail("HEAD", "atom head does not exist"); })),
        heads: (graphId: string, kind?: string) => effect(() => allHeads("HEADS", graphId, kind)),
        getRevision: (graphId: string, uid: string, revision: number) => effect(() => Either.gen(function* () {
            if (!Number.isInteger(revision) || revision < 1)
                return yield* fail("GET_REVISION", "atom revision is invalid");
            yield* graph("GET_REVISION", graphId);
            const found = yield* native("GET_REVISION", () => row(database.prepare("SELECT * FROM adaptive_atoms WHERE graph_id=? AND uid=? AND revision=?").get(graphId, uid, revision)));
            if (!found)
                return yield* fail("GET_REVISION", "atom revision does not exist");
            const refsRaw = blob(found["refs_json"]);
            const payloadRaw = blob(found["payload_json"]);
            const refs = yield* storedJson("GET_REVISION", found["refs_json"], "refs");
            const payload = yield* storedJson("GET_REVISION", found["payload_json"], "payload");
            const item = yield* atom({ uid: string(found["uid"]), kind: string(found["kind"]), owner: string(found["owner"]), refs, payload }, "GET_REVISION");
            if (hash(rawAtom(item["uid"], item["kind"], item["owner"], refsRaw, payloadRaw)) !== string(found["atom_digest"]))
                return yield* fail("GET_REVISION", "stored atom digest mismatch");
            return Object.freeze({ ...item, revision: numeric(found["revision"]), digest: string(found["atom_digest"]), eventId: found["event_id"] === null ? null : string(found["event_id"]) });
        })),
        rewrite: (input: AdaptiveRewrite) => effect(() => Either.gen(function* () {
            if (!input.graphId || !input.eventId || !record(input.expected) || !record(input.source))
                return yield* fail("REWRITE", "rewrite identity is invalid");
            if (Object.entries(input.expected).some(([uid, revision]) => !uid || !Number.isInteger(revision) || revision < 0))
                return yield* fail("REWRITE", "rewrite expectations are invalid");
            const atoms = yield* Either.all(input.atoms.map((item) => atom(item, "REWRITE")));
            if (!atoms.length || new Set(atoms.map((item) => item["uid"])).size !== atoms.length || Object.keys(input.expected).length !== atoms.length || atoms.some((item) => !(item["uid"] in input.expected)))
                return yield* fail("REWRITE", "rewrite atoms must exactly match expectations");
            const intent = hash(yield* json({ expected: input.expected, atoms, source: input.source }, "REWRITE"));
            return yield* transaction("REWRITE", () => Either.gen(function* () {
                yield* graph("REWRITE", input.graphId);
                const previousEvent = yield* native("REWRITE", () => row(database.prepare("SELECT intent_digest FROM adaptive_events WHERE graph_id=? AND event_id=?").get(input.graphId, input.eventId)));
                if (previousEvent)
                    return string(previousEvent["intent_digest"]) === intent ? yield* event("REWRITE", input.graphId, input.eventId) : yield* fail("REWRITE", "event id was reused with a different intent");
                const currentRows = yield* native("REWRITE", () => rows(database.prepare("SELECT * FROM adaptive_heads WHERE graph_id=?").all(input.graphId)));
                const current = new Map(currentRows.map((item) => [string(item["uid"]), item]));
                const touched = new Set(atoms.map((item) => item["uid"]));
                const valid = atoms.every((item) => { const old = current.get(item["uid"]); const expected = input.expected[item["uid"]]; return (!old ? expected === 0 : numeric(old["revision"]) === expected && string(old["owner"]) === item["owner"] && string(old["kind"]) === item["kind"]) && item.refs.every((ref) => current.has(ref["uid"]) || touched.has(ref["uid"])); });
                if (!valid)
                    return yield* fail("REWRITE", "head compare-and-swap conflict, immutable identity conflict, or unresolved reference");
                const consumed = Object.freeze(currentRows.filter((item) => string(item["uid"]) in input.expected).map(head));
                const produced: AdaptiveAtomHead[] = [];
                const putAtom = yield* native("REWRITE", () => database.prepare("INSERT INTO adaptive_atoms VALUES(?,?,?,?,?,?,?,?,?)"));
                const putHead = yield* native("REWRITE", () => database.prepare("INSERT INTO adaptive_heads VALUES(?,?,?,?,?,?)"));
                const updateHead = yield* native("REWRITE", () => database.prepare("UPDATE adaptive_heads SET revision=?,kind=?,owner=?,atom_digest=? WHERE graph_id=? AND uid=?"));
                for (const item of atoms) {
                    const old = current.get(item["uid"]);
                    const next = old ? numeric(old["revision"]) + 1 : 1;
                    const itemDigest = yield* digest(item, "REWRITE");
                    const refs = yield* json(item.refs, "REWRITE");
                    const payload = yield* json(item.payload, "REWRITE");
                    yield* native("REWRITE", () => putAtom.run(input.graphId, item["uid"], next, item["kind"], item["owner"], Buffer.from(refs), Buffer.from(payload), itemDigest, input.eventId));
                    yield* native("REWRITE", () => old ? updateHead.run(next, item["kind"], item["owner"], itemDigest, input.graphId, item["uid"]) : putHead.run(input.graphId, item["uid"], next, item["kind"], item["owner"], itemDigest));
                    produced.push(Object.freeze({ uid: item["uid"], revision: next, kind: item["kind"], owner: item["owner"], digest: itemDigest }));
                }
                const source = yield* json(input.source, "REWRITE");
                const consumedJson = yield* json(consumed, "REWRITE");
                const producedJson = yield* json(produced, "REWRITE");
                yield* native("REWRITE", () => database.prepare("INSERT INTO adaptive_events VALUES(?,?,?,?,?,?)").run(input.graphId, input.eventId, intent, Buffer.from(source), Buffer.from(consumedJson), Buffer.from(producedJson)));
                const outputHeads = Object.freeze(produced);
                return Object.freeze({ eventId: input.eventId, intentDigest: intent, source: input.source, consumed, produced: outputHeads, outputHeads });
            }));
        })),
        getEvent: (graphId: string, eventId: string) => effect(() => event("GET_EVENT", graphId, eventId)),
        events: (graphId: string) => effect(() => Either.gen(function* () { yield* graph("EVENTS", graphId); const found = yield* native("EVENTS", () => rows(database.prepare("SELECT event_id FROM adaptive_events WHERE graph_id=? ORDER BY rowid").all(graphId))); return yield* Either.all(found.map((item) => event("EVENTS", graphId, string(item["event_id"])))); })),
        acquireRuntimeLock: (graphId: string) => effect(() => Either.gen(function* () { if (!graphId)
            return yield* fail("ACQUIRE_RUNTIME_LOCK", "graph identity is invalid"); const token = randomUUID(); return yield* transaction("ACQUIRE_RUNTIME_LOCK", () => Either.gen(function* () { yield* graph("ACQUIRE_RUNTIME_LOCK", graphId); const holder = yield* native("ACQUIRE_RUNTIME_LOCK", () => row(database.prepare("SELECT token,pid FROM adaptive_runtime_locks WHERE graph_id=?").get(graphId))); if (holder && live(numeric(holder["pid"])))
            return yield* fail("ACQUIRE_RUNTIME_LOCK", "adaptive runtime lock is held by a live process"); if (holder)
            yield* native("ACQUIRE_RUNTIME_LOCK", () => database.prepare("DELETE FROM adaptive_runtime_locks WHERE graph_id=?").run(graphId)); yield* native("ACQUIRE_RUNTIME_LOCK", () => database.prepare("INSERT INTO adaptive_runtime_locks(graph_id,token,pid) VALUES(?,?,?)").run(graphId, token, process.pid)); return token; })); })),
        releaseRuntimeLock: (graphId: string, token: string) => effect(() => Either.gen(function* () { if (!graphId || !token)
            return yield* fail("RELEASE_RUNTIME_LOCK", "runtime lock identity is invalid"); return yield* transaction("RELEASE_RUNTIME_LOCK", () => Either.gen(function* () { yield* graph("RELEASE_RUNTIME_LOCK", graphId); const result = yield* native("RELEASE_RUNTIME_LOCK", () => database.prepare("DELETE FROM adaptive_runtime_locks WHERE graph_id=? AND token=?").run(graphId, token)); return numeric(result["changes"]) === 1 ? undefined : yield* fail("RELEASE_RUNTIME_LOCK", "adaptive runtime lock token does not match"); })); }))
    };
};
