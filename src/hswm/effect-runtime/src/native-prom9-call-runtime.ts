/** Exactly one supplied model-port call, then typed validation and receipt sink.
 * Retries, HTTP and durable storage are separate owner capabilities.
 */
import { Context, Effect } from "effect";
import { NativeProm9CallError, prepareNativeProm9Call, type NativeProm9CompletedCall } from "./native-prom9-call-domain.js";
import { type TaskJson } from "./native-task-json-domain.js";
export interface NativeProm9ModelPortShape {
    readonly invoke: (call: Readonly<Record<string, TaskJson>>) => Effect.Effect<unknown, NativeProm9CallError>;
    readonly acceptCallReceipt?: ((receipt: Readonly<Record<string, TaskJson>>) => Effect.Effect<void, NativeProm9CallError>) | null;
    readonly acceptItemRun?: ((receipt: Readonly<Record<string, TaskJson>>) => Effect.Effect<void, NativeProm9CallError>) | null;
}
export class NativeProm9ModelPort extends Context.Tag("NativeProm9ModelPort")<NativeProm9ModelPort, NativeProm9ModelPortShape>() {
}
export const invokeNativeProm9Function = (request: unknown): Effect.Effect<NativeProm9CompletedCall, NativeProm9CallError, NativeProm9ModelPort> => Effect.gen(function* () {
    const prepared = yield* prepareNativeProm9Call(request);
    const service = yield* NativeProm9ModelPort;
    if (typeof service.invoke !== "function")
        return yield* Effect.fail(new NativeProm9CallError({ detail: "model port is not callable" }));
    const response = yield* service.invoke(prepared.modelCall);
    const completed = yield* prepared.complete(response);
    if (service.acceptCallReceipt !== undefined && service.acceptCallReceipt !== null) {
        if (typeof service.acceptCallReceipt !== "function")
            return yield* Effect.fail(new NativeProm9CallError({ detail: "model port receipt sink is not callable" }));
        yield* service.acceptCallReceipt(completed.receipt);
    }
    return completed;
});
