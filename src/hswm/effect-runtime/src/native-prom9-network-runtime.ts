/** Supplied Effect model service owns calls and sinks; no implicit transport or retry. */
import { Context, Effect } from "effect";
import { NativeProm9CallError } from "./native-prom9-call-domain.js";
import { invokeNativeProm9Function, NativeProm9ModelPort } from "./native-prom9-call-runtime.js";
import { prepareNativeProm9Network, type NativeProm9NetworkStage, type NativeProm9RequestIdProfile } from "./native-prom9-network-domain.js";
import { type NativeProm9TokenMeter } from "./native-prom9-token-meter-domain.js";
import { type TaskJson } from "./native-task-json-domain.js";
export class NativeProm9NetworkMeter extends Context.Tag("NativeProm9NetworkMeter")<NativeProm9NetworkMeter, NativeProm9TokenMeter>() {
}
type JsonRecord = Readonly<Record<string, TaskJson>>;
const stage = (value: NativeProm9NetworkStage | JsonRecord): value is NativeProm9NetworkStage => typeof value["advance"] === "function";
export const runNativeProm9Item = (raw: unknown, requestIdProfile: NativeProm9RequestIdProfile = "CURRENT_8_HEX"): Effect.Effect<JsonRecord, NativeProm9CallError, NativeProm9ModelPort | NativeProm9NetworkMeter> => Effect.gen(function* () {
    const meter = yield* NativeProm9NetworkMeter;
    const initial = yield* prepareNativeProm9Network(raw, meter, requestIdProfile);
    const execute = (current: NativeProm9NetworkStage): Effect.Effect<JsonRecord, NativeProm9CallError, NativeProm9ModelPort> => Effect.gen(function* () {
        const call = yield* invokeNativeProm9Function(current.request);
        const next = yield* current.advance(call);
        if (stage(next))
            return yield* execute(next);
        const port = yield* NativeProm9ModelPort;
        if (port.acceptItemRun !== undefined && port.acceptItemRun !== null) {
            if (typeof port.acceptItemRun !== "function")
                return yield* Effect.fail(new NativeProm9CallError({ detail: "model port item-run sink is not callable" }));
            yield* port.acceptItemRun(next);
        }
        return next;
    });
    return yield* execute(initial);
});
