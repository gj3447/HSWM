import { readFile } from "node:fs/promises"
import { resolve } from "node:path"
import { Either } from "effect"
import { expect, it } from "vitest"
import { nativeTaskDigest, probeNativeTask, previewNativeTask, replayNativeTaskDemo, synthesizeNativeTask, validateNativeTaskRelation } from "../src/native-task-domain.js"
import type { Json } from "../src/native-task-domain.js"
import { decodeNativeTaskJson, renderNativeTaskJson } from "../src/native-task-json-domain.js"
const example=async()=>JSON.parse(await readFile(resolve(import.meta.dirname,"../../../../_research/causal_composition/examples/conditional_task_demo.v1.json"),"utf8"))
it("retains insertion order for numeric object keys in relation references", () => {
  const input = decodeNativeTaskJson(Buffer.from('{"2":1.0,"1":9007199254740993}'));
  if (Either.isLeft(input)) throw input.left;
  expect(renderNativeTaskJson(input.right, "relation")).toBe('{"2": 1.0, "1": 9007199254740993}');
  expect(Either.isLeft(decodeNativeTaskJson(Buffer.from("1".repeat(4301))))).toBe(true);
});
it("keeps role/field tuple identities distinct even when names contain NUL", () => {
  const domain = [{role: "a\u0000b", field: "c", values: [true]}, {role: "a", field: "b\u0000c", values: [true]}];
  const input = {domain, examples: [{values: domain.map(row => ({role: row.role, field: row.field, value: true})), outcome: true, source: "tuple-identity"}]};
  const result = synthesizeNativeTask(input);
  expect(Either.isRight(result)).toBe(true);
  if (Either.isRight(result)) expect(result.right).toMatchObject({candidate_space_size: 3});
});
it("refuses non-JSON domain values from direct TypeScript callers", () => {
  for (const value of [NaN, Infinity, {nested: NaN}, [undefined]]) expect(Either.isLeft(synthesizeNativeTask({domain: [{role: "r", field: "f", values: [true, value]}], examples: [{values: [{role: "r", field: "f", value: true}], outcome: true, source: "s"}]} as Json))).toBe(true);
});
it("preserves integer/float/bool distinctions, arbitrary integers, and exact numeric provenance bytes", async () => {
  const cases = JSON.parse(await readFile(resolve(import.meta.dirname, "../../../../tests/fixtures/native_migration/conditional_task_v1/numeric-contracts.json"), "utf8")) as readonly {name: string; request_json: string; expected_stdout: string}[];
  for (const row of cases) {
    const input = decodeNativeTaskJson(Buffer.from(row.request_json));
    if (Either.isLeft(input)) throw input.left;
    const result = synthesizeNativeTask(input.right);
    if (Either.isLeft(result)) throw result.left;
    expect(renderNativeTaskJson(result.right, "pretty") + "\n", row.name).toBe(row.expected_stdout);
  }
});
it("preserves the historical complete outputs and refusal boundaries", async () => {
  const cases = JSON.parse(await readFile(resolve(import.meta.dirname, "../../../../tests/fixtures/native_migration/conditional_task_v1/contracts.json"), "utf8")) as readonly {name: string; command: "preview" | "synthesize" | "probe" | "demo"; request: Json; expected: {ok: boolean; value?: Json; reason?: string}}[];
  const handlers = {preview: previewNativeTask, synthesize: synthesizeNativeTask, probe: probeNativeTask, demo: replayNativeTaskDemo};
  for (const row of cases) {
    const result = handlers[row.command](row.request);
    expect(Either.isRight(result), row.name).toBe(row.expected.ok);
    if (Either.isRight(result)) expect(result.right, row.name).toEqual(row.expected.value);
  }
});
it("matches the complete historical Python authored-demo output, including every provenance digest", async () => {
  const result = replayNativeTaskDemo(await example());
  if (Either.isLeft(result)) throw result.left;
  const expected = JSON.parse(await readFile(resolve(import.meta.dirname, "../../../../tests/fixtures/native_migration/conditional_task_v1/demo.expected.json"), "utf8"));
  expect(result.right).toEqual(expected);
});
it("ports bounded conditional synthesis without an execution or admission result",async()=>{const fixture=await example();const result=synthesizeNativeTask({domain:fixture.domain,examples:fixture.examples,candidate_limit:1});expect(Either.isRight(result)).toBe(true);if(Either.isRight(result)){expect(result.right).toMatchObject({status:"PROPOSED_NOT_ADMITTED",stop_reason:"CANDIDATE_LIMIT",input_provenance_digest:"92d6fca81a06a9eaa7dd7e65a0c671a0e252a6d1a1af0d5a0f1fbcc1f5182e66"});expect((result.right as Record<string,unknown>)["candidates"]).toHaveLength(1)}})
it("binds a continuation cursor and rejects tampering",async()=>{const fixture=await example();const first=synthesizeNativeTask({domain:fixture.domain,examples:fixture.examples,candidate_limit:1});if(Either.isLeft(first)) throw first.left;const row=first.right as Record<string,unknown>;const cursor=row["resume_cursor"] as Record<string,unknown>;const next=synthesizeNativeTask({domain:fixture.domain,examples:fixture.examples,resume_cursor:cursor as never,candidate_limit:1});expect(Either.isRight(next)).toBe(true);const bad=synthesizeNativeTask({domain:fixture.domain,examples:fixture.examples,resume_cursor:{...cursor,integrity:"0".repeat(64)} as never});expect(Either.isLeft(bad)).toBe(true)})
it("keeps AST validation pure and bounded",async()=>{const fixture=await example();expect(Either.isRight(validateNativeTaskRelation({domain:fixture.domain,ast:fixture.initial_relation.ast}))).toBe(true);expect(nativeTaskDigest({x:true})).toHaveLength(64)})
it("ports preview and finite discrimination as non-executing proposals",async()=>{const fixture=await example();const preview=previewNativeTask({domain:fixture.domain,relation:fixture.initial_relation,observations:fixture.query,action:fixture.action,checks:fixture.checks});expect(Either.isRight(preview)).toBe(true);if(Either.isRight(preview))expect((preview.right as Record<string,unknown>)["hypothetical_next_step"]).toMatchObject({kind:"ACTION_PROPOSAL"});const candidates=synthesizeNativeTask({domain:fixture.domain,examples:fixture.examples});if(Either.isLeft(candidates))throw candidates.left;const probe=probeNativeTask({domain:fixture.domain,candidates:((candidates.right as Record<string,unknown>)["candidates"] as Array<Record<string,unknown>>).map((candidate)=>({relation_ast:candidate["relation_ast"],source:candidate["input_provenance_digest"]})),contexts:fixture.contexts,allowed_reads:fixture.checks.allowed_reads,allowed_probe_ids:fixture.allowed_probe_ids,budget:fixture.probe_budget} as never);expect(Either.isRight(probe)).toBe(true);if(Either.isRight(probe))expect((probe.right as Record<string,unknown>)["selected_probe"]).toMatchObject({probe_id:"ready-dirty"})})
it("replays the declared demo without converting it to causal credit",async()=>{const result=replayNativeTaskDemo(await example());expect(Either.isRight(result)).toBe(true);if(Either.isRight(result)){const row=result.right as Record<string,unknown>;expect(row).toMatchObject({status:"AUTHORED_EPISODE_REPLAY_NOT_EFFICACY",credit:"UNIDENTIFIED_CREDIT",canonical_revision:null});expect((row["after"] as Record<string,unknown>)["hypothetical_next_step"]).toMatchObject({kind:"WITHHOLD"})}})
