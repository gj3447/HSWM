import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import { Either } from "effect"
import { expect, it } from "vitest"
import { validatePhoenixViewerProbe, type PhoenixViewerProbe } from "../src/native-infrastructure-smoke-phoenix.js"
import { renderNativeTaskJson } from "../src/native-task-json-domain.js"
const root = new URL("../../../../", import.meta.url)
const fixture = JSON.parse(readFileSync(new URL("tests/fixtures/native_migration/infrastructure_smoke_v1/phoenix-fake-vendor.original.v1.json",root),"utf8")) as {source:{path:string;sha256:string}; cases:readonly {name:string;probe:PhoenixViewerProbe;decision:string;stdout?:string}[]}
it("pins the original Phoenix client and matches all 12 mocked-vendor decisions and full positive stdout", () => {
  expect(createHash("sha256").update(readFileSync(new URL(fixture.source.path,root))).digest("hex")).toBe(fixture.source.sha256)
  for(const item of fixture.cases){const value=validatePhoenixViewerProbe(item.probe);expect(Either.isRight(value),item.name).toBe(item.decision==="ACCEPT");if(Either.isRight(value))expect(`${renderNativeTaskJson({...value.right},"pretty")}\n`,item.name).toBe(item.stdout)}
})
it("rejects holes and extra columns rather than discarding their bytes", () => {
  const baseline=fixture.cases[0]!
  expect(Either.isLeft(validatePhoenixViewerProbe({...baseline.probe,readRows:[[1,undefined]]}))).toBe(true)
  expect(Either.isLeft(validatePhoenixViewerProbe({...baseline.probe,readRows:[Array(1)]}))).toBe(true)
})
