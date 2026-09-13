import { readFileSync } from "node:fs";
import { expect, it } from "@effect/vitest";
import { Either } from "effect";
import { compileNativeS2STaskData } from "../src/native-s2s-dataset-domain.js";
import { parseNativeS2STaskArchiveEntry } from "../src/native-s2s-task-archive-domain.js";
import { lossForNativeS2SReferenceParameters } from "../src/native-s2s-reference-loss-domain.js";
import { nativeS2SFloatHex } from "../src/native-s2s-dataset-domain.js";
import { parseNativeS2SLearnedModelArchive } from "../src/native-s2s-model-protocol-domain.js";
const archives = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_learned_model_v1/original.v1.json", import.meta.url), "utf8")) as {
    readonly archives: Readonly<Record<string, Record<string, unknown>>>;
};
const oracle = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_reference_loss_v1/original.v1.json", import.meta.url), "utf8")) as Readonly<Record<string, {
    readonly train_hex: string;
    readonly dev_hex: string;
}>>;
const right = <A>(v: Either.Either<A, unknown>) => { expect(Either.isRight(v)).toBe(true); return Either.isRight(v) ? v.right : expect.fail("right"); };
it("matches original NumPy loss hex for source zero and best-two checkpoints", () => {
    for (const [name, row] of Object.entries(oracle)) {
        const archive = archives.archives[name === "T16_best2" ? "T16_nonzero" : name]!;
        const model = right(parseNativeS2SLearnedModelArchive(archive));
        const task = right(parseNativeS2STaskArchiveEntry((archive["optimization_receipt"] as Record<string, unknown>)["task_spec"]));
        const data = right(compileNativeS2STaskData(task));
        expect(nativeS2SFloatHex(right(lossForNativeS2SReferenceParameters(model.arm, model.parameters, data.trainInput, data.trainTargets, data.weights)))).toBe(row.train_hex);
        expect(nativeS2SFloatHex(right(lossForNativeS2SReferenceParameters(model.arm, model.parameters, data.devInput, data.devTargets, data.weights)))).toBe(row.dev_hex);
    }
}, 60000);
