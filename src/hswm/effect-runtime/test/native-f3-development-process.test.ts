import { randomBytes } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve as resolvePath } from "node:path";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { Pool, type PoolConfig } from "pg";
import { Either } from "effect";
import { expect, it } from "vitest";
import { decodeNativeF3DevelopmentRequest } from "../src/native-f3-development-process.js";

const request = (configPath: string, schema = "hswm_f3", endpoint = "http://127.0.0.1:1/v1") => ({
  schema_version: "hswm-native-f3-development-request/v1", mode: "DEVELOPMENT_ONLY",
  config_path: configPath, database_schema: schema,
  run: { runId: "development", configDigest: "a".repeat(64), maxCalls: 1 }, client_id: "f3v2-donor",
  request: { endpoint, model: "fixture", system: "system", user: "user", seed: 42, maxTokens: 16 }, timeout_seconds: 5
});

it("refuses non-development, unknown fields and malformed run/request inputs before I/O", () => {
  const base = request("/private/test.json");
  expect(Either.isRight(decodeNativeF3DevelopmentRequest(base))).toBe(true);
  for (const input of [{ ...base, mode: "SEALED" }, { ...base, extra: true }, { ...base, config_path: "relative" },
    { ...base, database_schema: "bad;sql" }, { ...base, run: { ...base.run, maxCalls: -1 } },
    { ...base, request: { ...base.request, seed: "42" } }, { ...base, timeout_seconds: Infinity }]) {
    expect(Either.isLeft(decodeNativeF3DevelopmentRequest(input))).toBe(true);
  }
});

const configPath = process.env["HSWM_F3_PG_TEST_CONFIG"];
it.skipIf(configPath === undefined)("actual one-shot process shares PG budget/cache across exits and never replays an uncertain dispatch", async () => {
  const source = JSON.parse(readFileSync(configPath!, "utf8")) as PoolConfig;
  const schema = `f3p_${randomBytes(10).toString("hex")}`, directory = mkdtempSync(join(tmpdir(), "f3-process-"));
  const pool = new Pool({ ...source, max: 1 });
  const migration = readFileSync(join(process.cwd(), "migrations", "0001_native_f3_pg.sql"), "utf8");
  const privatePath = join(directory, "postgres.json");
  writeFileSync(privatePath, JSON.stringify(source), { mode: 0o600 });
  let calls = 0, uncertain = false;
  const requests: unknown[] = [];
  const server = createServer((req, res) => {
    const chunks: Buffer[] = [];
    req.on("data", data => chunks.push(Buffer.from(data)));
    req.on("end", () => {
      calls++; requests.push(JSON.parse(Buffer.concat(chunks).toString("utf8")));
      if (uncertain) { req.socket.destroy(); return; }
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ model: "fixture", choices: [{ message: { content: '{"actions":[]}' }, finish_reason: "stop" }], usage: { prompt_tokens: 2, completion_tokens: 3 } }));
    });
  });
  const invoke = (input: unknown) => new Promise<{ code: number | null; out: string; err: string }>((resolve, reject) => {
    const child = spawn(process.execPath, [join(process.cwd(), "dist", "native-f3-development-process.js")], { stdio: ["pipe", "pipe", "pipe"] });
    let out = "", err = "";
    child.stdout.on("data", data => { out += String(data); }); child.stderr.on("data", data => { err += String(data); });
    child.on("error", reject); child.on("close", code => resolve({ code, out, err }));
    child.stdin.end(JSON.stringify(input));
  });
  // Cross the real Python serializer -> canonical JSON -> native process seam.
  // The Python default is a float (240.0); the wire protocol requires integer JSON.
  const invokePython = (input: ReturnType<typeof request>) => new Promise<{ code: number | null; out: string; err: string }>((resolve, reject) => {
    const root = resolvePath(process.cwd(), "../../..");
    const script = `import json,sys
from pathlib import Path
from hswm.infrastructure.native_f3_development_bridge import NativeF3DevelopmentChat, NativeF3SharedBudgetView
x=json.load(sys.stdin)
b=NativeF3SharedBudgetView(x["run"]["maxCalls"])
c=NativeF3DevelopmentChat(x["request"]["endpoint"],b,x["run"]["runId"],x["run"]["configDigest"],x["client_id"],Path(x["config_path"]),database_schema=x["database_schema"])
r=x["request"]
meta=c.chat(model=r["model"],system=r["system"],user=r["user"],seed=r["seed"],max_tokens=r["maxTokens"])
print(json.dumps({"meta":meta,"used":b.used,"observed":b.observed,"hits":c.hits,"misses":c.misses}))`;
    const child = spawn(process.env["HSWM_F3_TEST_PYTHON"] ?? "python3", ["-c", script], {
      stdio: ["pipe", "pipe", "pipe"], env: { ...process.env, PYTHONPATH: join(root, "src"), HSWM_NODE: process.execPath }
    });
    let out = "", err = "";
    child.stdout.on("data", data => { out += String(data); }); child.stderr.on("data", data => { err += String(data); });
    child.on("error", reject); child.on("close", code => resolve({ code, out, err }));
    child.stdin.end(JSON.stringify(input));
  });
  try {
    await pool.query(migration.replaceAll("hswm_f3", schema));
    await new Promise<void>(resolve => server.listen(0, "127.0.0.1", resolve));
    const address = server.address(); if (!address || typeof address === "string") throw new Error("fixture listen failed");
    const input = request(privatePath, schema, `http://127.0.0.1:${address.port}/v1`);
    const initial = await invoke(input); expect(initial.code).toBe(0);
    expect(JSON.parse(initial.out)).toMatchObject({ terminal: "COMPLETED", state: { maxCalls: 1, used: 1, misses: 1 }, response_meta: { cached: false } });
    expect(requests).toEqual([{ model: "fixture", messages: [{ role: "system", content: "system" }, { role: "user", content: "user" }], temperature: 0, top_p: 1, seed: 42, max_tokens: 16, response_format: { type: "json_object" }, chat_template_kwargs: { enable_thinking: false } }]);
    const cached = await invoke(input); expect(cached.code).toBe(0);
    expect(JSON.parse(cached.out)).toMatchObject({ terminal: "CACHE_HIT", state: { used: 1, hits: 1, misses: 1 }, response_meta: { cached: true } }); expect(calls).toBe(1);
    const exhausted = await invoke({ ...input, request: { ...input.request, user: "new" } });
    expect(JSON.parse(exhausted.out).terminal).toBe("BUDGET_EXHAUSTED"); expect(calls).toBe(1);
    const changed = await invoke({ ...input, run: { ...input.run, configDigest: "b".repeat(64) } });
    expect(changed.code).toBe(2); expect(changed.err).not.toContain(String(source.connectionString));
    const pythonInput = { ...input, run: { ...input.run, runId: "python-bridge" } };
    const pythonInitial = await invokePython(pythonInput);
    expect(pythonInitial.code, pythonInitial.err).toBe(0);
    expect(JSON.parse(pythonInitial.out)).toMatchObject({ meta: { cached: false }, used: 1, observed: true, misses: 1 });
    const pythonCached = await invokePython(pythonInput);
    expect(pythonCached.code, pythonCached.err).toBe(0);
    expect(JSON.parse(pythonCached.out)).toMatchObject({ meta: { cached: true }, used: 1, observed: true, hits: 1, misses: 1 });
    expect(calls).toBe(2);
    uncertain = true;
    const other = { ...input, run: { ...input.run, runId: "uncertain" } };
    expect(JSON.parse((await invoke(other)).out).terminal).toBe("TRANSPORT_UNCERTAIN");
    expect(JSON.parse((await invoke(other)).out).terminal).toBe("UNRESOLVED_DISPATCH"); expect(calls).toBe(3);
  } finally {
    server.closeAllConnections(); await new Promise<void>(resolve => server.close(() => resolve()));
    await pool.query(`DROP SCHEMA IF EXISTS ${schema} CASCADE`); await pool.end(); rmSync(directory, { recursive: true, force: true });
  }
}, 30000);
