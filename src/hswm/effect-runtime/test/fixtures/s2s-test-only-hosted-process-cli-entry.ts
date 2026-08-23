import { runS2STestOnlyHostedProcessCli } from "../../src/s2s-test-only-hosted-process-cli.js"

void runS2STestOnlyHostedProcessCli(process.argv.slice(2)).then((exitCode) => {
  process.exitCode = exitCode
})
