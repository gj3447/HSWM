/** Native checkout CLI. Python is neither an interpreter nor a service of this path. */
import { createHash, randomUUID } from "node:crypto";
import { dirname, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { Data, Effect, Either, Layer } from "effect";
import { parseJson, type Context } from "./adaptive-domain.js";
import { AdaptiveHttpClient, NativeAdaptiveHttpClient } from "./adaptive-executor.js";
import { makeAdaptiveRuntime } from "./adaptive-runtime.js";
import { makeAdaptiveStoreSqliteLayer } from "./adaptive-store.js";
import { PosixFileSystem } from "./effect-posix-filesystem.js";
import type { BoundedSubprocess } from "./effect-bounded-subprocess.js";
import type { ProcessReply } from "./effect-process-main.js";
import { makeAdaptiveOtlpTelemetryLayer, parseAdaptiveOtlpConfiguration } from "./adaptive-telemetry-otlp.js";
export const ADAPTIVE_CHECKOUT_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
export const DEVELOPMENT_PROFILES: Readonly<Record<string, string>> = Object.freeze({
    game: "adaptive_game_development.v2.json",
    maplelineage: "adaptive_maplelineage_development.v1.json",
    supullim: "adaptive_supullim_development.v1.json",
    reluvator: "adaptive_reluvator_development.v2.json",
    hswm: "adaptive_hswm_development.v3.json"
});
const ALIASES: Readonly<Record<string, string>> = Object.freeze({
    "the-excel-tycoon": "game", "버엑시": "game", "메이플리니지": "maplelineage"
});
const RUN_EXIT_CODES: Readonly<Record<string, number>> = Object.freeze({
    SUCCEEDED: 0, FAILED: 1, UNKNOWN: 3, WITHHOLD: 4, RUNNING: 5, FEEDBACK_RECORDED: 0
});
export class AdaptiveCliError extends Data.TaggedError("AdaptiveCliError")<{
    readonly detail: string;
}> {
}
const failure = (detail: string) => new AdaptiveCliError({ detail });
const describe = (error: unknown): string => {
    if (typeof error === "object" && error !== null && "detail" in error)
        return String(error.detail);
    return error instanceof Error ? error.message : String(error);
};
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown, fallback = ""): string => typeof value === "string" ? value : fallback;
const integer = (value: unknown): number => typeof value === "number" ? value : 0;
const counted = (items: ReadonlyArray<string>): Record<string, number> => {
    const counts: Record<string, number> = {};
    for (const key of items)
        counts[key] = (counts[key] ?? 0) + 1;
    return counts;
};
export const developmentStatePath = (project: string, workspace: string, explicit?: string, root = ADAPTIVE_CHECKOUT_ROOT): string => {
    if (explicit !== undefined)
        return isAbsolute(explicit) ? explicit : resolve(workspace, explicit);
    const suffix = createHash("sha256").update(workspace).digest("hex").slice(0, 16);
    return resolve(root, ".hswm-local/projects", `${ALIASES[project] ?? project}-${suffix}.sqlite3`);
};
export const adaptiveStatus = (graph: Record<string, unknown>, development: boolean): Record<string, unknown> => {
    const atoms = Array.isArray(graph["atoms"]) ? graph["atoms"].filter(object) : [];
    const episodes = atoms.filter((atom) => atom["kind"] === "episode");
    const payload = (atom: Record<string, unknown>): Record<string, unknown> => object(atom["payload"]) ? atom["payload"] : {};
    const pending = episodes.filter((atom) => {
        const p = payload(atom);
        return p["feedback"] == null && (!object(p["result"]) || typeof p["result"]["success"] !== "boolean");
    }).map((atom) => {
        const p = payload(atom);
        return { episode: p["episode_id"], task: object(p["intent"]) ? p["intent"]["task"] : null,
            status: p["status"], started_at: p["started_at"] };
    }).sort((a, b) => integer(b.started_at) - integer(a.started_at)).slice(0, 10);
    const graphId = text(graph["graph_id"]);
    return {
        backend: "typescript-effect", schema_version: graph["schema_version"],
        ...(development ? { project: graphId, pending_feedback: pending } : { graph_id: graphId }),
        atom_kinds: counted(atoms.map((atom) => text(atom["kind"]))),
        episode_statuses: counted(episodes.map((atom) => text(payload(atom)["status"], "UNKNOWN"))),
        event_count: Array.isArray(graph["events"]) ? graph["events"].length : 0,
        relations: atoms.filter((atom) => atom["kind"] === "relation").map((atom) => {
            const p = payload(atom);
            return { uid: atom["uid"], revision: atom["revision"],
                observations: object(p["model"]) ? p["model"]["n"] : null,
                ...(!development ? { active: p["active"], reads: p["reads"] } : {}) };
        }),
        claim: !development ? "LOCAL_RUNTIME_STATE_NOT_REFERENCE_KG"
            : graphId.includes("reluvator") ? "LOCAL_DEVELOPMENT_FEEDBACK_NOT_FIELD_OR_INFERENCE_AUTHORITY"
                : graphId.includes("hswm-self") ? "LOCAL_DEVELOPMENT_FEEDBACK_NOT_SELF_VALIDATION_OR_EFFICACY"
                    : "LOCAL_DEVELOPMENT_FEEDBACK_NOT_GAME_OR_PLATFORM_AUTHORITY"
    };
};
const OPTIONS = {
    program: { type: "string" }, workspace: { type: "string" }, state: { type: "string" },
    context: { type: "string" }, focus: { type: "string" }, stage: { type: "string" },
    task: { type: "string" }, episode: { type: "string" }, budget: { type: "string" },
    cell: { type: "string" }, route: { type: "string" }, allow: { type: "string", multiple: true },
    "max-calls": { type: "string" }, frozen: { type: "boolean" },
    success: { type: "string" }, source: { type: "string" }, relation: { type: "string" },
    revision: { type: "string" }, event: { type: "string" },
    "otel-endpoint": { type: "string" }, "otel-token-env": { type: "string" }, help: { type: "boolean", short: "h" }
} as const;
export const runAdaptiveCli = (mode: "live" | "development", argv: ReadonlyArray<string>, checkoutRoot = ADAPTIVE_CHECKOUT_ROOT): Effect.Effect<ProcessReply, AdaptiveCliError, PosixFileSystem | BoundedSubprocess> => Effect.gen(function* () {
    const parsed = yield* Effect.try({
        try: () => parseArgs({ args: [...argv], options: OPTIONS, allowPositionals: true, strict: true }),
        catch: (error) => failure(describe(error))
    });
    const { values, positionals } = parsed;
    if (values.help === true)
        return {
            stdout: mode === "development"
                ? "hswm-dev <game|maplelineage|supullim|reluvator|hswm> <plan|run|status|feedback> [--workspace PATH] [--focus VALUE] [--task TEXT]\nNative TypeScript + Effect; local observational adaptation.\n"
                : "hswm-live --program FILE <plan|run|graph|status|feedback|restore> [--context JSON] [--workspace PATH] [--state FILE]\nNative TypeScript + Effect; local observational adaptation.\n",
            exitCode: 0
        };
    const development = mode === "development";
    const projectInput = positionals[0] ?? "";
    const project = ALIASES[projectInput] ?? projectInput;
    const action = positionals[development ? 1 : 0] ?? "";
    const actions = development ? ["plan", "run", "status", "feedback"] : ["plan", "run", "status", "graph", "feedback", "restore"];
    if (positionals.length !== (development ? 2 : 1) || !actions.includes(action))
        return yield* Effect.fail(failure("unknown or missing command; use --help"));
    const profile = DEVELOPMENT_PROFILES[project];
    if (development && profile === undefined)
        return yield* Effect.fail(failure("unknown development project"));
    if (!development && values.program === undefined)
        return yield* Effect.fail(failure("--program is required"));
    const fs = yield* PosixFileSystem;
    const workspace = yield* fs.realpath(resolve(values.workspace ?? process.cwd()), "adaptive-workspace");
    const workspaceIdentity = yield* fs.identity(workspace, "adaptive-workspace");
    if (workspaceIdentity.kind !== "DIRECTORY")
        return yield* Effect.fail(failure("workspace must be a directory"));
    if (development && project === "hswm") {
        const manifest = yield* fs.readRegularBounded(resolve(workspace, "pyproject.toml"), { maximumBytes: 100000, operation: "hswm-workspace-marker" });
        if (!/\[project\][\s\S]*?\bname\s*=\s*"hswm"/.test(Buffer.from(manifest.bytes).toString("utf8")))
            return yield* Effect.fail(failure("hswm workspace marker mismatch"));
        for (const directory of ["src/hswm", "tests", "scripts"]) {
            if ((yield* fs.identity(resolve(workspace, directory), "hswm-workspace-marker")).kind !== "DIRECTORY")
                return yield* Effect.fail(failure("hswm workspace marker mismatch"));
        }
    }
    const programPath = development
        ? resolve(checkoutRoot, "_research/causal_composition/examples", profile ?? "")
        : resolve(values.program ?? "");
    const raw = yield* fs.readRegularBounded(programPath, { maximumBytes: 1000000, operation: "adaptive-program" });
    const program = yield* parseJson(Buffer.from(raw.bytes).toString("utf8"));
    if (!object(program))
        return yield* Effect.fail(failure("program must be a JSON object"));
    const domain = object(program["context_domain"]) ? program["context_domain"] : {};
    const focusValues = Array.isArray(domain["focus"]) ? domain["focus"] : [];
    const context = development
        ? { focus: values.focus ?? text(focusValues[0]), stage: values.stage ?? "development" }
        : values.context === undefined ? {} : yield* parseJson(values.context);
    if (!object(context))
        return yield* Effect.fail(failure("context must be a JSON object"));
    const state = development ? developmentStatePath(project, workspace, values.state, checkoutRoot)
        : resolve(workspace, values.state ?? ".hswm-local/runtime.sqlite3");
    const tokenEnvironment = values["otel-token-env"] ?? "HSWM_OTLP_BEARER_TOKEN";
    if (!/^[A-Z][A-Z0-9_]{0,127}$/.test(tokenEnvironment))
        return yield* Effect.fail(failure("OTLP token environment name"));
    const parsedTelemetry = parseAdaptiveOtlpConfiguration(values["otel-endpoint"] ?? process.env["HSWM_OTLP_TRACES_ENDPOINT"], process.env[tokenEnvironment]);
    if (Either.isLeft(parsedTelemetry))
        return yield* Effect.fail(failure(`OTLP ${parsedTelemetry.left}`));
    const telemetry = parsedTelemetry.right;
    const execute = Effect.gen(function* () {
        const runtime = yield* makeAdaptiveRuntime(program, workspace);
        const budget = Number(values.budget ?? "60");
        const common = { budget, ...(values.route === undefined ? {} : { forceRoute: values.route }),
            ...(values.allow === undefined ? {} : { allowed: values.allow }) };
        if (action === "plan")
            return yield* runtime.plan(context as Context, {
                ...common, ...(values.cell === undefined ? {} : { cellId: values.cell })
            });
        if (action === "run") {
            if (values.task === undefined)
                return yield* Effect.fail(failure("--task is required"));
            return yield* runtime.run(values.task, context as Context, {
                ...common, episodeId: values.episode ?? randomUUID(), learn: values.frozen !== true,
                maxCalls: Number(values["max-calls"] ?? "16")
            });
        }
        if (action === "feedback") {
            if (values.episode === undefined || values.source === undefined || !["true", "false"].includes(values.success ?? ""))
                return yield* Effect.fail(failure("feedback requires --episode, --source and --success true|false"));
            return yield* runtime.feedback(values.episode, values.success === "true", values.source);
        }
        if (action === "restore") {
            if (values.relation === undefined || values.revision === undefined)
                return yield* Effect.fail(failure("restore requires --relation and --revision"));
            const uid = values.relation.startsWith("relation:") ? values.relation : `relation:${values.relation}`;
            return yield* runtime.restore(uid, Number(values.revision), values.event ?? randomUUID());
        }
        const graph = yield* runtime.graph();
        return action === "graph" ? graph : adaptiveStatus(graph, development);
    }).pipe(Effect.provide(Layer.mergeAll(
        makeAdaptiveStoreSqliteLayer(state),
        Layer.succeed(AdaptiveHttpClient, NativeAdaptiveHttpClient),
        telemetry === null ? Layer.empty : makeAdaptiveOtlpTelemetryLayer(telemetry)
    )));
    const result = yield* Effect.scoped(execute);
    return { stdout: `${JSON.stringify(result)}\n`, exitCode: action === "run" ? RUN_EXIT_CODES[text(result["status"])] ?? 2 : 0 };
}).pipe(Effect.mapError((error) => failure(describe(error))));
export const describeAdaptiveCliError = (error: AdaptiveCliError): string => JSON.stringify({ status: "ERROR", code: 2, error: error.detail, backend: "typescript-effect" });
