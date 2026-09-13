import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { expect, it } from "@effect/vitest";
import { Effect, Either } from "effect";
import { NativeProm9JsonEnvironmentLive, NativeProm9JsonHttpLive } from "../src/native-prom9-json-http-runtime.js";
import type { NativeProm9JsonTransportRequest } from "../src/native-prom9-json-transport-domain.js";
type Handler = (request: IncomingMessage, response: ServerResponse) => void;
const withServer = async <A>(handler: Handler, work: (url: string, server: Server) => Promise<A>): Promise<A> => {
    const server = createServer(handler);
    await new Promise<void>((resolve, reject) => {
        server.once("error", reject);
        server.listen(0, "127.0.0.1", () => resolve());
    });
    const address = server.address();
    if (address === null || typeof address === "string")
        throw new Error("loopback server did not expose a TCP address");
    try {
        return await work(`http://127.0.0.1:${address.port}`, server);
    }
    finally {
        server.closeAllConnections();
        await new Promise<void>((resolve, reject) => server.close(error => error === undefined ? resolve() : reject(error)));
    }
};
const request = (url: string, timeoutMilliseconds = 1000): NativeProm9JsonTransportRequest => Object.freeze({
    url,
    headers: Object.freeze({ "content-type": "application/json", "x-loopback": "one" }),
    body: new TextEncoder().encode('{"exact":"request-body"}'),
    timeoutMilliseconds,
});
const run = (value: NativeProm9JsonTransportRequest) => Effect.runPromise(Effect.either(NativeProm9JsonHttpLive.post(value)));
it("posts exact bytes once and preserves the successful HTTP status", async () => {
    let calls = 0;
    let body = "";
    await withServer((incoming, outgoing) => {
        calls += 1;
        incoming.setEncoding("utf8");
        incoming.on("data", chunk => { body += chunk; });
        incoming.on("end", () => { outgoing.statusCode = 201; outgoing.end("{\"ok\":true}"); });
    }, async (url) => {
        const result = await run(request(`${url}/post`));
        expect(Either.isRight(result)).toBe(true);
        if (Either.isRight(result)) {
            expect(result.right.status).toBe(201);
            expect(new TextDecoder().decode(result.right.body)).toBe('{"ok":true}');
        }
    });
    expect(calls).toBe(1);
    expect(body).toBe('{"exact":"request-body"}');
});
it("does not retry a rejected 503 POST", async () => {
    let calls = 0;
    await withServer((_incoming, outgoing) => { calls += 1; outgoing.statusCode = 503; outgoing.end("unavailable"); }, async (url) => {
        const result = await run(request(`${url}/unavailable`));
        expect(result).toMatchObject({ _tag: "Left", left: { detail: "HTTP status or response body invalid" } });
    });
    expect(calls).toBe(1);
});
it("refuses redirects without issuing the redirected request", async () => {
    let initial = 0;
    let redirected = 0;
    await withServer((incoming, outgoing) => {
        if (incoming.url === "/redirect") {
            initial += 1;
            outgoing.statusCode = 302;
            outgoing.setHeader("location", "/target");
            outgoing.end();
            return;
        }
        redirected += 1;
        outgoing.statusCode = 200;
        outgoing.end("should not happen");
    }, async (url) => {
        const result = await run(request(`${url}/redirect`));
        expect(result).toMatchObject({ _tag: "Left", left: { detail: "HTTP POST failed" } });
    });
    expect(initial).toBe(1);
    expect(redirected).toBe(0);
});
it("aborts a deadline-bound request", async () => {
    let clientClosed = false;
    await withServer((incoming, outgoing) => {
        incoming.on("aborted", () => { clientClosed = true; });
        outgoing.on("close", () => { clientClosed = true; });
    }, async (url) => {
        const result = await run(request(`${url}/slow`, 20));
        expect(result).toMatchObject({ _tag: "Left", left: { detail: "HTTP deadline exceeded" } });
        await new Promise(resolve => setTimeout(resolve, 30));
    });
    expect(clientClosed).toBe(true);
});
it("fails a streamed response above the sixteen-mebibyte body bound", async () => {
    let calls = 0;
    await withServer((_incoming, outgoing) => {
        calls += 1;
        outgoing.statusCode = 200;
        outgoing.write(Buffer.alloc(16 * 1024 * 1024, 0x61));
        outgoing.end(Buffer.from([0x62]));
    }, async (url) => {
        const result = await run(request(`${url}/large`, 5000));
        expect(result).toMatchObject({ _tag: "Left", left: { detail: "response byte bound exceeded" } });
    });
    expect(calls).toBe(1);
}, 15000);
it("reads process environment through the explicit live boundary", async () => {
    const present = await Effect.runPromise(NativeProm9JsonEnvironmentLive.read("PATH"));
    expect(typeof present === "string" || present === undefined).toBe(true);
});
