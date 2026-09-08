/**
 * A bounded research-only OpenAI-compatible chat boundary.
 *
 * This module records a declared model-identity proof separately from provider
 * metadata.  A `/v1/models` row can confirm only what the provider reported;
 * it never upgrades `PROVIDER_REPORTED_ID_ONLY` into a weight attestation.
 * It is deliberately independent of adaptive routing, canonical admission,
 * and outcome learning.
 * OpenAI's chat-completions contract treats `seed` as best-effort/deprecated,
 * and its `system_fingerprint` as provider metadata, not a checkpoint hash:
 * https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
 */
import { createHash } from "node:crypto";
import { Context, Data, Effect, Either } from "effect";
import { type AdaptiveHttpRequest, AdaptiveExecutorError, NativeAdaptiveHttpClient } from "./adaptive-executor.js";

export const RESEARCH_PINNED_CHAT_SCHEMA = "hswm-research-pinned-chat/v1" as const;
const MAX_REQUEST_BYTES = 1_000_000;
const MAX_RESPONSE_BYTES = 64_000;
const SHA256 = /^[0-9a-f]{64}$/;

export type IdentityProof = Readonly<{
  readonly level: "VERIFIED_DEPLOYMENT_DIGEST";
  readonly deploymentDigest: string;
}> | Readonly<{
  /** A caller supplied digest is not verification without an endpoint binding. */
  readonly level: "DECLARED_DEPLOYMENT_DIGEST";
  readonly deploymentDigest: string;
  readonly proofVerification: "NOT_INDEPENDENTLY_VERIFIED";
}> | Readonly<{
  readonly level: "PROVIDER_REPORTED_ID_ONLY";
}>;

export type DecodingConfig = Readonly<{
  readonly temperature: number;
  readonly topP: number;
  readonly seed: number | null;
}>;

export type TokenLimit = Readonly<{
  readonly field: "max_completion_tokens" | "max_tokens";
  readonly value: number;
}>;

export type PinnedChatConfig = Readonly<{
  readonly endpoint: string;
  readonly modelId: string;
  readonly apiKeyEnv: string | null;
  readonly tokenLimit: TokenLimit;
  readonly timeoutMs: number;
  readonly decoding: DecodingConfig;
  readonly identityProof: IdentityProof;
  /** Provider identity-only observations are explicitly exploratory. */
  readonly researchMode: "PINNED_DEPLOYMENT_COMPARATOR" | "EXPLORATORY_PROVIDER_IDENTITY_ONLY";
  readonly preflight: "NONE" | "MODEL_LIST_AND_VERSION";
  readonly expectedProviderVersion: string | null;
}>;

export type ResearchHttpRequest = Readonly<{
  readonly url: string;
  readonly headers: Readonly<Record<string, string>>;
  readonly timeoutMs: number;
  readonly maximumResponseBytes: number;
}>;

export interface ResearchPinnedChatHttpShape {
  readonly postJson: (request: AdaptiveHttpRequest) => Effect.Effect<Uint8Array, AdaptiveExecutorError>;
  readonly getJson?: (request: ResearchHttpRequest) => Effect.Effect<Uint8Array, AdaptiveExecutorError>;
  /** Must bind this endpoint's current deployment to the supplied digest. */
  readonly verifyDeploymentDigest?: (input: Readonly<{ readonly endpoint: string; readonly modelId: string; readonly deploymentDigest: string }>) => Effect.Effect<boolean, AdaptiveExecutorError>;
}

export class ResearchPinnedChatHttp extends Context.Tag("hswm/ResearchPinnedChatHttp")<ResearchPinnedChatHttp, ResearchPinnedChatHttpShape>() {}

export interface ResearchPinnedChatCredentials {
  /** Resolves a configured environment-name without exposing its value in a record. */
  readonly resolve: (environmentName: string) => Effect.Effect<string | undefined>;
}

export class ResearchPinnedChatCredentialSource extends Context.Tag("hswm/ResearchPinnedChatCredentialSource")<ResearchPinnedChatCredentialSource, ResearchPinnedChatCredentials>() {}

export const NativeResearchPinnedChatHttp: ResearchPinnedChatHttpShape = Object.freeze({
  postJson: NativeAdaptiveHttpClient.postJson
});

export class ResearchPinnedChatError extends Data.TaggedError("ResearchPinnedChatError")<{
  readonly code: "CONFIG_INVALID" | "CREDENTIAL_UNAVAILABLE" | "PREFLIGHT_UNAVAILABLE" | "PREFLIGHT_REJECTED" | "HTTP_FAILED" | "RESPONSE_INVALID" | "MODEL_ID_MISMATCH";
}> {}

export type UsageObservation = Readonly<{
  readonly status: "REPORTED" | "UNAVAILABLE" | "INVALID";
  readonly promptTokens: number | null;
  readonly completionTokens: number | null;
  readonly totalTokens: number | null;
}>;

export type PreflightObservation = Readonly<{
  readonly status: "NOT_REQUESTED" | "PROVIDER_METADATA_VERIFIED";
  readonly modelListResponseSha256: string | null;
  readonly versionResponseSha256: string | null;
  readonly providerVersion: string | null;
  readonly modelListIsWeightAttestation: false;
}>;

export type PinnedChatRecord = Readonly<{
  readonly schemaVersion: typeof RESEARCH_PINNED_CHAT_SCHEMA;
  readonly configurationSha256: string;
  readonly identityProof: IdentityProof;
  readonly configuredModelId: string;
  readonly reportedModelId: string;
  /** Provider supplied metadata only; never a model-byte or weight hash. */
  readonly systemFingerprint: string | null;
  readonly requestSha256: string;
  readonly responseSha256: string;
  /** Exact serialised POST body; authentication headers are never included. */
  readonly requestBodyUtf8: string;
  /** Exact bounded provider response bytes decoded as UTF-8. */
  readonly rawResponseUtf8: string;
  readonly content: string;
  readonly usage: UsageObservation;
  readonly preflight: PreflightObservation;
}>;

const sha256 = (bytes: Uint8Array | string): string => createHash("sha256").update(bytes).digest("hex");
const error = (code: ResearchPinnedChatError["code"]) => new ResearchPinnedChatError({ code });
const nonempty = (value: unknown, limit = 256): value is string => typeof value === "string" && value.trim().length > 0 && value.length <= limit;
const safeInteger = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value);
const record = (value: unknown): value is Readonly<Record<string, unknown>> => typeof value === "object" && value !== null && !Array.isArray(value);
const frozenJson = (value: unknown): string => JSON.stringify(value);
const liftEither = <A>(value: Either.Either<A, ResearchPinnedChatError>): Effect.Effect<A, ResearchPinnedChatError> => Either.isLeft(value) ? Effect.fail(value.left) : Effect.succeed(value.right);
const exactKeys = (value: Readonly<Record<string, unknown>>, keys: readonly string[]): boolean => Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key));
const environmentName = (value: unknown): value is string => typeof value === "string" && /^[A-Z_][A-Z0-9_]{0,127}$/.test(value);

const normalizedEndpoint = (endpoint: string): Either.Either<string, ResearchPinnedChatError> => {
  try {
    const parsed = new URL(endpoint);
    if ((parsed.protocol !== "http:" && parsed.protocol !== "https:") || !parsed.host || parsed.username || parsed.password || parsed.search || parsed.hash || !["", "/", "/v1"].includes(parsed.pathname.replace(/\/$/, "")))
      return Either.left(error("CONFIG_INVALID"));
    return Either.right(`${parsed.protocol}//${parsed.host}`);
  } catch { return Either.left(error("CONFIG_INVALID")); }
};

/** Decodes, deep-copies, and freezes the complete public configuration boundary. */
export const decodePinnedChatConfig = (input: unknown): Either.Either<PinnedChatConfig, ResearchPinnedChatError> => {
  if (!record(input) || !exactKeys(input, ["endpoint", "modelId", "apiKeyEnv", "tokenLimit", "timeoutMs", "decoding", "identityProof", "researchMode", "preflight", "expectedProviderVersion"])) return Either.left(error("CONFIG_INVALID"));
  const tokenLimit = input["tokenLimit"], decoding = input["decoding"];
  if (!record(tokenLimit) || !record(decoding)) return Either.left(error("CONFIG_INVALID"));
  const tokenField = tokenLimit["field"], tokenValue = tokenLimit["value"], temperature = decoding["temperature"], topP = decoding["topP"], seed = decoding["seed"];
  if (!nonempty(input["endpoint"], 4096) || !nonempty(input["modelId"]) || (input["apiKeyEnv"] !== null && !environmentName(input["apiKeyEnv"])) || !exactKeys(tokenLimit, ["field", "value"]) || (tokenField !== "max_completion_tokens" && tokenField !== "max_tokens") || !safeInteger(tokenValue) || tokenValue < 1 || !safeInteger(input["timeoutMs"]) || input["timeoutMs"] < 1 || !exactKeys(decoding, ["temperature", "topP", "seed"]) || typeof temperature !== "number" || !Number.isFinite(temperature) || temperature < 0 || temperature > 2 || typeof topP !== "number" || !Number.isFinite(topP) || topP <= 0 || topP > 1 || (seed !== null && (!safeInteger(seed) || seed < 0)) || (input["researchMode"] !== "PINNED_DEPLOYMENT_COMPARATOR" && input["researchMode"] !== "EXPLORATORY_PROVIDER_IDENTITY_ONLY") || (input["preflight"] !== "NONE" && input["preflight"] !== "MODEL_LIST_AND_VERSION") || (input["expectedProviderVersion"] !== null && !nonempty(input["expectedProviderVersion"]))) return Either.left(error("CONFIG_INVALID"));
  const proof = input["identityProof"];
  let identityProof: IdentityProof;
  if (!record(proof)) return Either.left(error("CONFIG_INVALID"));
  if (proof["level"] === "PROVIDER_REPORTED_ID_ONLY" && exactKeys(proof, ["level"])) identityProof = Object.freeze({ level: "PROVIDER_REPORTED_ID_ONLY" });
  else if (proof["level"] === "VERIFIED_DEPLOYMENT_DIGEST" && exactKeys(proof, ["level", "deploymentDigest"]) && typeof proof["deploymentDigest"] === "string" && SHA256.test(proof["deploymentDigest"])) identityProof = Object.freeze({ level: "VERIFIED_DEPLOYMENT_DIGEST", deploymentDigest: proof["deploymentDigest"] });
  else if (proof["level"] === "DECLARED_DEPLOYMENT_DIGEST" && exactKeys(proof, ["level", "deploymentDigest", "proofVerification"]) && typeof proof["deploymentDigest"] === "string" && SHA256.test(proof["deploymentDigest"]) && proof["proofVerification"] === "NOT_INDEPENDENTLY_VERIFIED") identityProof = Object.freeze({ level: "DECLARED_DEPLOYMENT_DIGEST", deploymentDigest: proof["deploymentDigest"], proofVerification: "NOT_INDEPENDENTLY_VERIFIED" });
  else return Either.left(error("CONFIG_INVALID"));
  if (((identityProof.level === "VERIFIED_DEPLOYMENT_DIGEST" || identityProof.level === "DECLARED_DEPLOYMENT_DIGEST") && input["researchMode"] !== "PINNED_DEPLOYMENT_COMPARATOR") || (identityProof.level === "PROVIDER_REPORTED_ID_ONLY" && input["researchMode"] !== "EXPLORATORY_PROVIDER_IDENTITY_ONLY")) return Either.left(error("CONFIG_INVALID"));
  return Either.right(Object.freeze({ endpoint: input["endpoint"], modelId: input["modelId"], apiKeyEnv: input["apiKeyEnv"], tokenLimit: Object.freeze({ field: tokenField, value: tokenValue }), timeoutMs: input["timeoutMs"], decoding: Object.freeze({ temperature, topP, seed }), identityProof, researchMode: input["researchMode"], preflight: input["preflight"], expectedProviderVersion: input["expectedProviderVersion"] } as PinnedChatConfig));
};

const validate = (input: PinnedChatConfig): Either.Either<{ readonly config: PinnedChatConfig; readonly endpoint: string; readonly configSha256: string }, ResearchPinnedChatError> => {
  const config = decodePinnedChatConfig(input);
  if (Either.isLeft(config)) return Either.left(config.left);
  const endpoint = normalizedEndpoint(config.right.endpoint);
  if (Either.isLeft(endpoint)) return Either.left(endpoint.left);
  const configuration = { schemaVersion: RESEARCH_PINNED_CHAT_SCHEMA, ...config.right, endpoint: endpoint.right };
  return Either.right(Object.freeze({ config: config.right, endpoint: endpoint.right, configSha256: sha256(frozenJson(configuration)) }));
};

const usage = (body: Readonly<Record<string, unknown>>): UsageObservation => {
  const candidate = body["usage"];
  if (candidate === undefined) return Object.freeze({ status: "UNAVAILABLE", promptTokens: null, completionTokens: null, totalTokens: null });
  if (!record(candidate) || !safeInteger(candidate["prompt_tokens"]) || candidate["prompt_tokens"] < 0 || !safeInteger(candidate["completion_tokens"]) || candidate["completion_tokens"] < 0 || !safeInteger(candidate["total_tokens"]) || candidate["total_tokens"] < 0 || candidate["total_tokens"] !== candidate["prompt_tokens"] + candidate["completion_tokens"])
    return Object.freeze({ status: "INVALID", promptTokens: null, completionTokens: null, totalTokens: null });
  return Object.freeze({ status: "REPORTED", promptTokens: candidate["prompt_tokens"], completionTokens: candidate["completion_tokens"], totalTokens: candidate["total_tokens"] });
};

const decodeObject = (bytes: Uint8Array): Either.Either<Readonly<Record<string, unknown>>, ResearchPinnedChatError> => {
  try {
    const parsed: unknown = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    return record(parsed) ? Either.right(parsed) : Either.left(error("RESPONSE_INVALID"));
  } catch { return Either.left(error("RESPONSE_INVALID")); }
};

const headers = (credential: string | undefined): Readonly<Record<string, string>> => Object.freeze({ "content-type": "application/json", ...(credential === undefined ? {} : { authorization: `Bearer ${credential}` }) });
const chatContent = (body: Readonly<Record<string, unknown>>): string | null => {
  const choices = body["choices"];
  if (!Array.isArray(choices) || !record(choices[0]) || !record(choices[0]["message"]) || typeof choices[0]["message"]["content"] !== "string") return null;
  return choices[0]["message"]["content"] as string;
};

const preflight = (config: PinnedChatConfig, endpoint: string, headersValue: Readonly<Record<string, string>>): Effect.Effect<PreflightObservation, ResearchPinnedChatError, ResearchPinnedChatHttp> => Effect.gen(function* () {
  if (config.preflight === "NONE") return Object.freeze({ status: "NOT_REQUESTED" as const, modelListResponseSha256: null, versionResponseSha256: null, providerVersion: null, modelListIsWeightAttestation: false as const });
  const http = yield* ResearchPinnedChatHttp;
  if (http.getJson === undefined) return yield* Effect.fail(error("PREFLIGHT_UNAVAILABLE"));
  const request = (url: string): ResearchHttpRequest => ({ url, headers: headersValue, timeoutMs: config.timeoutMs, maximumResponseBytes: MAX_RESPONSE_BYTES });
  const modelsRaw = yield* http.getJson(request(`${endpoint}/v1/models`)).pipe(Effect.mapError(() => error("HTTP_FAILED")));
  const versionRaw = yield* http.getJson(request(`${endpoint}/version`)).pipe(Effect.mapError(() => error("HTTP_FAILED")));
  const models = yield* liftEither(decodeObject(modelsRaw));
  const version = yield* liftEither(decodeObject(versionRaw));
  const entries = models["data"];
  const matches = Array.isArray(entries) ? entries.filter((entry): entry is Readonly<Record<string, unknown>> => record(entry) && entry["id"] === config.modelId) : [];
  if (matches.length !== 1 || !nonempty(version["version"]) || (config.expectedProviderVersion !== null && version["version"] !== config.expectedProviderVersion)) return yield* Effect.fail(error("PREFLIGHT_REJECTED"));
  return Object.freeze({ status: "PROVIDER_METADATA_VERIFIED" as const, modelListResponseSha256: sha256(modelsRaw), versionResponseSha256: sha256(versionRaw), providerVersion: version["version"] as string, modelListIsWeightAttestation: false as const });
});

/** One bounded call.  The returned record never contains authorization material. */
export const runPinnedChat = (config: PinnedChatConfig, prompt: string): Effect.Effect<PinnedChatRecord, ResearchPinnedChatError, ResearchPinnedChatHttp | ResearchPinnedChatCredentialSource> => Effect.gen(function* () {
  const valid = yield* liftEither(validate(config));
  const pinned = valid.config;
  if (!nonempty(prompt, MAX_REQUEST_BYTES)) return yield* Effect.fail(error("CONFIG_INVALID"));
  const credentials = yield* ResearchPinnedChatCredentialSource;
  const credential = pinned.apiKeyEnv === null ? undefined : yield* credentials.resolve(pinned.apiKeyEnv);
  if (pinned.apiKeyEnv !== null && !credential) return yield* Effect.fail(error("CREDENTIAL_UNAVAILABLE"));
  const requestHeaders = headers(credential);
  const http = yield* ResearchPinnedChatHttp;
  if (pinned.identityProof.level === "VERIFIED_DEPLOYMENT_DIGEST") {
    if (http.verifyDeploymentDigest === undefined) return yield* Effect.fail(error("PREFLIGHT_UNAVAILABLE"));
    const verified = yield* http.verifyDeploymentDigest({ endpoint: valid.endpoint, modelId: pinned.modelId, deploymentDigest: pinned.identityProof.deploymentDigest }).pipe(Effect.mapError(() => error("HTTP_FAILED")));
    if (!verified) return yield* Effect.fail(error("PREFLIGHT_REJECTED"));
  }
  const preflightRecord = yield* preflight(pinned, valid.endpoint, requestHeaders);
  const requestText = frozenJson({ model: pinned.modelId, messages: [{ role: "user", content: prompt }], [pinned.tokenLimit.field]: pinned.tokenLimit.value, temperature: pinned.decoding.temperature, top_p: pinned.decoding.topP, ...(pinned.decoding.seed === null ? {} : { seed: pinned.decoding.seed }) });
  const requestBytes = new TextEncoder().encode(requestText);
  if (requestBytes.byteLength > MAX_REQUEST_BYTES) return yield* Effect.fail(error("CONFIG_INVALID"));
  const responseBytes = yield* http.postJson({ url: `${valid.endpoint}/v1/chat/completions`, headers: requestHeaders, body: requestBytes, timeoutMs: pinned.timeoutMs, maximumResponseBytes: MAX_RESPONSE_BYTES }).pipe(Effect.mapError(() => error("HTTP_FAILED")));
  const response = yield* liftEither(decodeObject(responseBytes));
  if (response["model"] !== pinned.modelId) return yield* Effect.fail(error("MODEL_ID_MISMATCH"));
  const content = chatContent(response);
  if (content === null) return yield* Effect.fail(error("RESPONSE_INVALID"));
  const rawResponseUtf8 = new TextDecoder("utf-8", { fatal: true }).decode(responseBytes);
  return Object.freeze({ schemaVersion: RESEARCH_PINNED_CHAT_SCHEMA, configurationSha256: valid.configSha256, identityProof: pinned.identityProof, configuredModelId: pinned.modelId, reportedModelId: pinned.modelId, systemFingerprint: nonempty(response["system_fingerprint"]) ? response["system_fingerprint"] : null, requestSha256: sha256(requestBytes), responseSha256: sha256(responseBytes), requestBodyUtf8: requestText, rawResponseUtf8, content, usage: usage(response), preflight: preflightRecord });
});
