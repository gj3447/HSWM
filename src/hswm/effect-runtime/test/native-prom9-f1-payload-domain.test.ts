import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { Either } from "effect";
import { expect, it } from "vitest";
import { nativeProm9F1AnswerContextPayload, nativeProm9F1BondScoringPayload, nativeProm9F1CandidateTableForArm, nativeProm9F1ObservableForArm, nativeProm9F1QueryEnvelopePayload, nativeProm9F1RequestId } from "../src/native-prom9-f1-payload-domain.js";
import { decodeNativeTaskJson, renderNativeTaskJson, snapshotNativeTaskJson, taskJsonRecord, type TaskJson } from "../src/native-task-json-domain.js";
type Row = {
    readonly name: string;
    readonly item_json: string;
    readonly arm_json: string;
    readonly query_plan_json: string;
    readonly result: Readonly<{
        readonly accepted: boolean;
        readonly canonical?: string;
    }>;
};
const corpus = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/prom9_f1_payload_v1/original.v1.json", import.meta.url), "utf8")) as Readonly<{
    readonly source_pins: Readonly<Record<string, string>>;
    readonly cases: readonly Row[];
}>;
const decode = (text: string): TaskJson => Either.getOrThrow(decodeNativeTaskJson(new TextEncoder().encode(text)));
const value = <A>(result: Either.Either<A, unknown>): A => Either.getOrThrow(result);
it("pins the original pure payload sources", () => { for (const [path, digest] of Object.entries(corpus.source_pins))
    expect(createHash("sha256").update(readFileSync(new URL(`../../../../${path}`, import.meta.url))).digest("hex")).toBe(digest); });
it("replays original payload construction across every arm", () => {
    for (const row of corpus.cases) {
        const item = decode(row.item_json), arm = decode(row.arm_json), plan = decode(row.query_plan_json);
        if (typeof arm !== "string" || !taskJsonRecord(item))
            throw new Error(row.name);
        const request = value(nativeProm9F1RequestId("run-😀", arm, item["item_id"]));
        const selected = item["candidates"];
        const built = Either.gen(function* () { const candidateRows = yield* nativeProm9F1CandidateTableForArm(arm, selected); const first = Array.isArray(selected) ? selected.slice(0, 1) : selected; return snapshotNativeTaskJson(Object.freeze({ request_id: request, observable: yield* nativeProm9F1ObservableForArm(arm, Array.isArray(selected) && taskJsonRecord(selected[0]) ? selected[0]["observable"] : null), candidate_table: candidateRows, query: yield* nativeProm9F1QueryEnvelopePayload(item, request, "\u001c"), bond: yield* nativeProm9F1BondScoringPayload(item, arm, request, plan, "\u001c"), answer: yield* nativeProm9F1AnswerContextPayload(item, request, plan, first, "\u001c"), answer_empty_selected: yield* nativeProm9F1AnswerContextPayload(item, request, plan, [], "") })); });
        expect(Either.isRight(built), row.name).toBe(row.result.accepted);
        if (row.result.accepted)
            expect(renderNativeTaskJson(value(built))).toBe(row.result.canonical);
    }
});
it("refuses getter and sparse-array inputs without accessor reads", () => { let read = false; const getter = Object.defineProperty({}, "bond_id", { enumerable: true, get: () => { read = true; return "bond"; } }); expect(nativeProm9F1CandidateTableForArm("typed_hswm_three_function_network", [getter])).toMatchObject({ _tag: "Left" }); expect(read).toBe(false); const sparse: unknown[] = []; sparse[1] = {}; expect(nativeProm9F1CandidateTableForArm("typed_hswm_three_function_network", sparse)).toMatchObject({ _tag: "Left" }); });
