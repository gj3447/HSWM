# HSWM Serena development tool

This is an optional, isolated MCP tool for symbol-level TypeScript code
navigation. It is not part of the HSWM runtime, research evidence, or a
canonical write path.

The lock pins Oraios Serena `v1.7.0` (commit `949a27ef1e5fda1a6e7b561e777bcece345c6ffd`),
whose tag is MIT licensed. The project-level MCP surface is deliberately
limited to symbol overview, definition, references, and file diagnostics.
`package-lock.json` separately pins the TypeScript language-server process;
the launcher makes Serena's managed lookup path point at that local executable,
so it cannot download an unpinned npm package.

Install once from the checkout root:

```sh
uv sync --locked --project src/hswm/development/serena
npm --prefix src/hswm/development/serena ci --ignore-scripts --no-audit --no-fund
```

Run the server through `src/hswm/development/bin/hswm-serena`. Missing dependencies
produce setup instructions; MCP startup does not install packages. The wrapper fixes
the project to this checkout and supplies Serena's `ide` context. Its
`SERENA_HOME` is an ignored `.state-v1` directory here, so it does not use or
modify the user-level `~/.serena`. Do not use `serena setup`, which writes
user-level client configuration.
