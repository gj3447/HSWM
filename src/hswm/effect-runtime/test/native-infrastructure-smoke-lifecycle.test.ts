import { describe, expect, it, vi, beforeEach } from "vitest"
import { Effect, Either } from "effect"
const observed = vi.hoisted(() => ({ events: [] as string[], options: [] as Readonly<Record<string, unknown>>[], spans: [] as unknown[], exportCode: 0, failWorkflow: false }))
vi.mock("@temporalio/client", () => ({
  Connection: {connect: async () => { observed.events.push("client-connect"); return {close: async () => { observed.events.push("client-close") }} }},
  WorkflowClient: class {
    constructor(options: Readonly<Record<string, unknown>>) { observed.options.push(options) }
    async execute(name: string, options: Readonly<Record<string, unknown>>) {
      observed.events.push(name); observed.options.push(options)
      if (observed.failWorkflow) throw new Error("isolated workflow refusal")
      return {run_id: "fixed-run-01", status: "PASS", claim_boundary: "infrastructure smoke only"}
    }
  },
}))
vi.mock("@temporalio/worker", () => ({
  NativeConnection: {connect: async () => { observed.events.push("worker-connect"); return {close: async () => { observed.events.push("worker-close") }} }},
  Worker: {create: async (options: Readonly<Record<string, unknown>>) => {
    observed.options.push(options)
    return {runUntil: async (run: () => Promise<unknown>) => { observed.events.push("worker-run"); try {return await run()} finally {observed.events.push("worker-ended")} }, getState: () => "STOPPED", shutdown: () => {observed.events.push("worker-shutdown")} }
  }},
}))
vi.mock("@temporalio/workflow", () => ({ proxyActivities: () => ({hswm_research_fabric_smoke_activity: async (value: {run_id: string}) => ({...value, status: "PASS", claim_boundary: "infrastructure smoke only"})}) }))
vi.mock("@opentelemetry/exporter-trace-otlp-proto", () => ({OTLPTraceExporter: class {
  constructor(options: Readonly<Record<string, unknown>>) {observed.options.push(options)}
  export(spans: readonly unknown[], callback: (outcome: {code: number}) => void) {observed.spans.push(...spans);callback({code: observed.exportCode})}
  async forceFlush() {observed.events.push("export-flush")}
  async shutdown() {observed.events.push("export-close")}
}}))
import { runResearchFabricTemporalLifecycle, emitResearchFabricTrace } from "../src/native-infrastructure-smoke-runtime.js"
import { completeResearchFabricSmoke } from "../src/native-infrastructure-smoke-domain.js"
import { hswm_research_fabric_smoke_workflow } from "../src/native-infrastructure-smoke-workflow.js"
import { runNativeInfrastructureSmokeCli } from "../src/native-infrastructure-smoke-cli.js"
import { NodePosixFileSystemLive } from "../src/effect-posix-filesystem.js"
import { mkdtemp, writeFile, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { TypedSearchAttributes } from "@temporalio/common"
const runId = "fixed-run-01"
beforeEach(() => {observed.events.length=0;observed.options.length=0;observed.spans.length=0;observed.exportCode=0;observed.failWorkflow=false})

describe("native infrastructure SDK lifecycle", () => {
  it("owns worker and client connections and sends all original workflow settings", async () => {
    const result = await Effect.runPromise(runResearchFabricTemporalLifecycle(runId, "/isolated/workflow.js"))
    expect(result).toEqual({workflow_id: `hswm-infra-smoke-${runId}`, result: {run_id: runId, status: "PASS", claim_boundary: "infrastructure smoke only"}})
    expect(observed.options).toEqual(expect.arrayContaining([expect.objectContaining({namespace:"hswm-dev",taskQueue:"hswm-research-fabric-smoke",workflowsPath:"/isolated/workflow.js"}),expect.objectContaining({args:[{run_id:runId}],taskQueue:"hswm-research-fabric-smoke",workflowId:`hswm-infra-smoke-${runId}`,workflowExecutionTimeout:30000,memo:{claim_boundary:"infrastructure smoke only"}})]))
    const attributes = observed.options.find(options => options["typedSearchAttributes"] !== undefined)?.["typedSearchAttributes"]
    expect(attributes).toBeInstanceOf(TypedSearchAttributes)
    if(attributes instanceof TypedSearchAttributes) expect(attributes.getAll()).toEqual([
      {key:{name:"HswmRunId",type:"KEYWORD"},value:runId},
      {key:{name:"HswmSchemaVersion",type:"KEYWORD"},value:"none-infrastructure-smoke"},
      {key:{name:"HswmOutcome",type:"KEYWORD"},value:"PASS"},
    ])
    expect(observed.events.slice(-3)).toEqual(["worker-ended","client-close","worker-close"])
  })
  it("closes both connections after workflow rejection", async () => {
    observed.failWorkflow=true
    const result=await Effect.runPromise(Effect.either(runResearchFabricTemporalLifecycle(runId,"/isolated/workflow.js")))
    expect(Either.isLeft(result)).toBe(true)
    expect(observed.events.slice(-3)).toEqual(["worker-ended","client-close","worker-close"])
  })
  it("returns the original activity result from the workflow without adding another wrapper", async () => {
    expect(await hswm_research_fabric_smoke_workflow({run_id:runId})).toEqual({run_id:runId,status:"PASS",claim_boundary:"infrastructure smoke only"})
  })
  it("exports a real SDK span and never includes the private secret among its attributes", async () => {
    const temporal={workflow_id:`hswm-infra-smoke-${runId}`,result:{run_id:runId,status:"PASS" as const,claim_boundary:"infrastructure smoke only" as const}}
    const result=Either.getOrThrow(completeResearchFabricSmoke(runId,temporal))
    await Effect.runPromise(emitResearchFabricTrace(result,"isolated-test-secret"))
    expect(observed.spans).toHaveLength(1)
    const span=observed.spans[0] as {name:string;attributes:Readonly<Record<string,unknown>>;spanContext:()=>{traceId:string}}
    expect(span.name).toBe("hswm.infrastructure.smoke")
    expect(span.attributes).toEqual({"hswm.run.id":runId,"hswm.projection.kind":"infrastructure_smoke","hswm.claim.boundary":"infrastructure smoke only","hswm.temporal.workflow_id":temporal.workflow_id,"hswm.temporal.result_sha256":result.phoenix_result_sha256})
    expect(span.spanContext().traceId).toMatch(/^[0-9a-f]{32}$/)
    expect(observed.events).toContain("export-close")
  })
  it("rejects an unacknowledged OTLP export and closes the exporter", async () => {
    observed.exportCode=1
    const result=Either.getOrThrow(completeResearchFabricSmoke(runId,{workflow_id:`hswm-infra-smoke-${runId}`,result:{run_id:runId,status:"PASS",claim_boundary:"infrastructure smoke only"}}))
    const failure=await Effect.runPromise(Effect.either(emitResearchFabricTrace(result,"isolated-test-secret")))
    expect(Either.isLeft(failure)).toBe(true)
    expect(observed.events).toContain("export-close")
  })
})

it("executes the complete fabric CLI with original deterministic output and no secret disclosure", async () => {
  const directory=await mkdtemp(join(tmpdir(),"hswm-fabric-cli-")),secretFile=join(directory,"phoenix.json")
  try {
    await writeFile(secretFile,JSON.stringify({phoenix_admin_secret:"isolated-test-secret"}))
    const output=await Effect.runPromise(runNativeInfrastructureSmokeCli(["fabric","--secret-file",secretFile,"--run-id",runId]).pipe(Effect.provide(NodePosixFileSystemLive)))
    expect(JSON.parse(output)).toEqual(Either.getOrThrow(completeResearchFabricSmoke(runId,{workflow_id:`hswm-infra-smoke-${runId}`,result:{run_id:runId,status:"PASS",claim_boundary:"infrastructure smoke only"}})))
    expect(output).not.toContain("isolated-test-secret")
    expect(observed.spans).toHaveLength(1)
  } finally {await rm(directory,{recursive:true,force:true})}
})
it("rejects an invalid run identifier before filesystem or network I/O",async()=>{
  const result=await Effect.runPromise(Effect.either(runNativeInfrastructureSmokeCli(["fabric","--secret-file","/does-not-exist","--run-id","bad/id"]).pipe(Effect.provide(NodePosixFileSystemLive))))
  expect(Either.isLeft(result)&&result.left.code).toBe("RUN_ID_INVALID")
  expect(observed.events).toEqual([])
})
