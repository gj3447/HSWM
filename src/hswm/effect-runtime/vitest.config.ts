import { fileURLToPath } from "node:url"
import { defineConfig } from "vitest/config"

// New tests live in the repository's typed tests directory. Existing runtime
// tests keep their compatibility path and the same include/exclude behavior.
export default defineConfig({
  resolve: {
    alias: Object.fromEntries(["effect", "@effect/vitest", "vitest", "neo4j-driver", "n3"].map((name) => [name, fileURLToPath(import.meta.resolve(name))]))
  },
  test: {
    include: ["test/**/*.test.ts", "../../../tests/effect-runtime/**/*.test.ts"]
  }
})
