import { afterEach, expect, it, vi } from "vitest"

import { main } from "../src/g0-occurrence-temporal-worker-process.js"

const configure = (): void => {
  vi.stubEnv("HSWM_G0_TEMPORAL_ADDRESS", "127.0.0.1:7233")
  vi.stubEnv("HSWM_G0_TEMPORAL_NAMESPACE", "default")
  vi.stubEnv("HSWM_G0_TEMPORAL_TASK_QUEUE", "hswm-g0-rehearsal")
  vi.stubEnv("HSWM_G0_TEMPORAL_SIGNAL_AUTHORIZATION_BINDING", "4".padStart(64, "0"))
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
})

it("reports a redacted rehearsal-only preflight", async () => {
  configure()
  let output = ""
  vi.spyOn(process.stdout, "write").mockImplementation((chunk) => {
    output += String(chunk)
    return true
  })
  expect(await main(["--preflight"])).toBe(0)
  expect(JSON.parse(output)).toEqual({
    schema_version: "hswm-g0-temporal-typescript-worker-preflight/v1",
    status: "CONFIGURED_NOT_CONNECTED_NOT_EXECUTED_NOT_G0",
    address_configured: true,
    namespace_configured: true,
    task_queue_configured: true,
    signal_authorization_binding_configured: true,
    credentials_accepted: false,
    live_external_admission: false
  })
  expect(output).not.toContain("127.0.0.1")
})

it("refuses the live serve spelling before any connection", async () => {
  configure()
  let error = ""
  vi.spyOn(process.stderr, "write").mockImplementation((chunk) => {
    error += String(chunk)
    return true
  })
  expect(await main(["--serve"])).toBe(2)
  expect(error).toContain("live external admission is blocked")
})
