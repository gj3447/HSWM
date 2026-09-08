// Safe local USL v2 permission probe: injected fetch/resolver plus a temp symlink.
import { Effect, Either, Layer } from "../../../USL/node_modules/effect/dist/esm/index.js"
import { promises as fs } from "node:fs"
import * as os from "node:os"
import * as path from "node:path"
import { parseLocator } from "../../../USL/src/locator.ts"
import { Config, Resolvers, ResolversLive, resolveWith } from "../../../USL/src/resolve.ts"
import { observeProgram } from "../../../USL/src/language/runtime.ts"

const locator = (value: string) => Either.getOrThrow(parseLocator(value))
const config = (fetchImpl: typeof fetch, allowedLocators?: readonly string[]) => ({
  hostname: "hswm-usl-probe", gitRepos: {}, kgMcpUrl: "http://kg.invalid/mcp", fetchImpl,
  ...(allowedLocators === undefined ? {} : { allowedLocators }),
})
const resolve = (cfg: ReturnType<typeof config>, value: string) => Effect.runPromise(Effect.either(resolveWith(cfg)(locator(value))))
const resolveLive = (cfg: ReturnType<typeof config>, value: string, allowedLocators: readonly string[]) => Effect.runPromise(Effect.either(
  Effect.gen(function* () { return yield* (yield* Resolvers).resolve(locator(value), { allowedLocators }) }).pipe(
    Effect.provide(ResolversLive.pipe(Layer.provide(Layer.succeed(Config, cfg)))),
  ),
))

const run = async () => {
  const calls: string[] = []
  const start = "https://inside.test/start", outside = "https://outside.test/secret"
  const redirected = await resolve(config(async (url) => {
    calls.push(String(url)); return new Response(null, { status: 302, headers: { location: outside } })
  }, [start]), start)
  const intersection = await resolveLive(config(async () => new Response("ok"), [start]), outside, [outside])

  const directory = await fs.mkdtemp(path.join(os.tmpdir(), "hswm-usl-v2-probe-"))
  try {
    const target = path.join(directory, "target.txt"), link = path.join(directory, "link.txt")
    await fs.writeFile(target, "probe-only")
    await fs.symlink(target, link)
    const original = `file://hswm-usl-probe${link}`, canonical = `file://hswm-usl-probe${target}`
    const onlyOriginal = await resolve(config(fetch, [original]), original)
    const both = await resolve(config(fetch, [original, canonical]), original)

    const plan = {
      schema: "usl-semantic-plan/v1", languageVersion: "0.1", namespace: "probe",
      resources: [
        { name: "chosen", locator: { kind: "url", href: "https://chosen.test/" } },
        { name: "unused", locator: { kind: "url", href: "https://unused.test/" } },
      ],
      meanings: [{ name: "rel", roles: [{ name: "left", kind: "url" }, { name: "right", kind: "url" }], description: "probe" }],
      links: [
        { name: "selected", meaning: "rel", participants: [{ role: "left", resource: "chosen" }, { role: "right", resource: "chosen" }] },
        { name: "unused_link", meaning: "rel", participants: [{ role: "left", resource: "unused" }, { role: "right", resource: "unused" }] },
      ], declarationStatus: "DECLARED",
    } as const
    const seen: string[] = []
    const fake = Layer.succeed(Resolvers, { resolve: (item: { kind: string }) => Effect.sync(() => {
      seen.push(item.kind === "url" ? (item as { href: string }).href : "unexpected")
      return { locator: item, resolvedLocator: "https://chosen.test/", contentHash: "0".repeat(64), resolvedAt: "2026-09-08T00:00:00.000Z", guaranteeLevel: "pure" as const, matchCount: 1 }
    }) })
    const observed = await Effect.runPromise(observeProgram(plan, { links: ["selected"], allowedLocators: ["https://chosen.test/"] }).pipe(Effect.provide(fake)))
    console.log(JSON.stringify({
      redirect_target_denied_before_second_fetch: Either.isLeft(redirected) && redirected.left.reason === "DENIED" && JSON.stringify(calls) === JSON.stringify([start]),
      request_policy_cannot_broaden_config: Either.isLeft(intersection) && intersection.left.reason === "DENIED",
      symlink_needs_canonical_allowlist: Either.isLeft(onlyOriginal) && onlyOriginal.left.reason === "DENIED" && Either.isRight(both),
      selected_link_avoids_unused_resolver_call: JSON.stringify(seen) === JSON.stringify(["https://chosen.test/"]) && observed.metrics.resolverCalls === 1 && observed.readScope.links[0] === "selected",
      observation_schema: observed.schema,
    }, null, 2))
  } finally { await fs.rm(directory, { recursive: true, force: true }) }
}
void run()
