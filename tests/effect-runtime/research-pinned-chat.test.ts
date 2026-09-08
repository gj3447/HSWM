import { Cause, Effect, Layer } from "effect";
import { expect, it } from "vitest";
import { decodePinnedChatConfig, ResearchPinnedChatCredentialSource, ResearchPinnedChatHttp, type PinnedChatConfig, runPinnedChat } from "../../src/hswm/effect-runtime/src/research-pinned-chat.js";

const encoder = new TextEncoder();
const config = (overrides: Partial<PinnedChatConfig> = {}): PinnedChatConfig => ({
  endpoint: "https://provider.example/v1", modelId: "fixed-model@rev-1", apiKeyEnv: "PINNED_CHAT_TEST_KEY",
  tokenLimit: { field: "max_completion_tokens", value: 32 }, timeoutMs: 1_000, decoding: { temperature: 0, topP: 1, seed: 7 },
  identityProof: { level: "VERIFIED_DEPLOYMENT_DIGEST", deploymentDigest: "a".repeat(64) },
  researchMode: "PINNED_DEPLOYMENT_COMPARATOR", preflight: "NONE", expectedProviderVersion: null, ...overrides
});
const credentials = Layer.succeed(ResearchPinnedChatCredentialSource, ResearchPinnedChatCredentialSource.of({ resolve: () => Effect.succeed("secret-value") }));
const transport = (post: unknown, gets?: readonly unknown[]) => {
  let index = 0;
  return Layer.succeed(ResearchPinnedChatHttp, ResearchPinnedChatHttp.of({
    postJson: () => Effect.succeed(encoder.encode(JSON.stringify(post))),
    verifyDeploymentDigest: () => Effect.succeed(true),
    ...(gets === undefined ? {} : { getJson: () => Effect.succeed(encoder.encode(JSON.stringify(gets[index++]))) })
  }));
};
const run = (input: PinnedChatConfig, post: unknown, gets?: readonly unknown[]) => Effect.runPromise(runPinnedChat(input, "solve relation").pipe(Effect.provide(Layer.merge(credentials, transport(post, gets)))));

it("pins exact reported model, frozen decoding, hashes, and declared proof without secret disclosure", async () => {
  const result = await run(config(), { model: "fixed-model@rev-1", system_fingerprint: "provider-build-id", choices: [{ message: { content: "answer" } }], usage: { prompt_tokens: 4, completion_tokens: 2, total_tokens: 6 } });
  expect(result.identityProof).toEqual({ level: "VERIFIED_DEPLOYMENT_DIGEST", deploymentDigest: "a".repeat(64) });
  expect(result.usage).toEqual({ status: "REPORTED", promptTokens: 4, completionTokens: 2, totalTokens: 6 });
  expect(result.requestSha256).toMatch(/^[0-9a-f]{64}$/);
  expect(result.responseSha256).toMatch(/^[0-9a-f]{64}$/);
  expect(result.systemFingerprint).toBe("provider-build-id");
  expect(result.requestBodyUtf8).toContain("max_completion_tokens");
  expect(result.rawResponseUtf8).toContain("provider-build-id");
  expect(JSON.stringify(result)).not.toContain("secret-value");
  expect(JSON.stringify(result)).not.toContain("Bearer ");
});

it("rejects provider model drift before returning a record", async () => {
  const exit = await Effect.runPromise(Effect.exit(runPinnedChat(config(), "x").pipe(Effect.provide(Layer.merge(credentials, transport({ model: "replacement", choices: [{ message: { content: "answer" } }] }))))));
  expect(exit._tag).toBe("Failure");
  if (exit._tag === "Failure") {
    const failure = Cause.failureOption(exit.cause);
    expect(failure._tag).toBe("Some");
    if (failure._tag === "Some") expect(failure.value).toMatchObject({ code: "MODEL_ID_MISMATCH" });
  }
  expect(JSON.stringify(exit)).not.toContain("secret-value");
});

it("keeps malformed usage unknown rather than inventing zero usage", async () => {
  const result = await run(config(), { model: "fixed-model@rev-1", choices: [{ message: { content: "answer" } }], usage: { prompt_tokens: 4, completion_tokens: 2, total_tokens: 99 } });
  expect(result.usage).toEqual({ status: "INVALID", promptTokens: null, completionTokens: null, totalTokens: null });
});

it("validates optional provider metadata without treating it as a weight proof", async () => {
  const result = await run(config({ identityProof: { level: "PROVIDER_REPORTED_ID_ONLY" }, researchMode: "EXPLORATORY_PROVIDER_IDENTITY_ONLY", preflight: "MODEL_LIST_AND_VERSION", expectedProviderVersion: "v-test" }), { model: "fixed-model@rev-1", choices: [{ message: { content: "answer" } }] }, [{ data: [{ id: "fixed-model@rev-1" }] }, { version: "v-test" }]);
  expect(result.preflight).toMatchObject({ status: "PROVIDER_METADATA_VERIFIED", providerVersion: "v-test", modelListIsWeightAttestation: false });
  expect(result.identityProof.level).toBe("PROVIDER_REPORTED_ID_ONLY");
});

it("fails closed when optional preflight cannot be provided", async () => {
  const exit = await Effect.runPromise(Effect.exit(runPinnedChat(config({ preflight: "MODEL_LIST_AND_VERSION" }), "x").pipe(Effect.provide(Layer.merge(credentials, transport({ model: "fixed-model@rev-1", choices: [{ message: { content: "answer" } }] }))))));
  expect(exit._tag).toBe("Failure");
  if (exit._tag === "Failure") {
    const failure = Cause.failureOption(exit.cause);
    expect(failure._tag).toBe("Some");
    if (failure._tag === "Some") expect(failure.value).toMatchObject({ code: "PREFLIGHT_UNAVAILABLE" });
  }
});

it("rejects null nested configuration and unknown identity or mode literals", () => {
  expect(decodePinnedChatConfig({ ...config(), decoding: null })._tag).toBe("Left");
  expect(decodePinnedChatConfig({ ...config(), identityProof: { level: "UNRECOGNIZED" } })._tag).toBe("Left");
  expect(decodePinnedChatConfig({ ...config(), researchMode: "UNRECOGNIZED" })._tag).toBe("Left");
  expect(decodePinnedChatConfig({ ...config(), identityProof: { level: "DECLARED_DEPLOYMENT_DIGEST", deploymentDigest: "a".repeat(64), proofVerification: "claimed" } })._tag).toBe("Left");
});

it("uses a deep frozen configuration snapshot after asynchronous credential resolution", async () => {
  const mutable = config() as { modelId: string; decoding: { temperature: number; topP: number; seed: number | null } } & PinnedChatConfig;
  let requestBody = "";
  let entered!: () => void;
  let release!: () => void;
  const enteredPromise = new Promise<void>((resolve) => { entered = resolve; });
  const releasePromise = new Promise<void>((resolve) => { release = resolve; });
  const delayedCredentials = Layer.succeed(ResearchPinnedChatCredentialSource, ResearchPinnedChatCredentialSource.of({ resolve: () => Effect.sync(entered).pipe(Effect.zipRight(Effect.promise(() => releasePromise)), Effect.as("secret-value")) }));
  const delayedTransport = Layer.succeed(ResearchPinnedChatHttp, ResearchPinnedChatHttp.of({
    verifyDeploymentDigest: () => Effect.succeed(true),
    postJson: (request) => Effect.sync(() => { requestBody = Buffer.from(request.body).toString("utf8"); return encoder.encode(JSON.stringify({ model: "fixed-model@rev-1", choices: [{ message: { content: "answer" } }] })); })
  }));
  const running = Effect.runPromise(runPinnedChat(mutable, "x").pipe(Effect.provide(Layer.merge(delayedCredentials, delayedTransport))));
  await enteredPromise;
  mutable.modelId = "mutated-model";
  mutable.decoding.temperature = 2;
  release();
  await running;
  expect(requestBody).toContain("fixed-model@rev-1");
  expect(requestBody).toContain("\"temperature\":0");
  expect(requestBody).not.toContain("mutated-model");
});
