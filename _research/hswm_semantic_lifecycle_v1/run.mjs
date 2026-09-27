#!/usr/bin/env node
/** Compatibility launcher. All implementation lives in the checked TypeScript runtime. */
import { semanticLifecycleMain } from '../../src/hswm/effect-runtime/dist/semantic-lifecycle-process.js';
if (import.meta.main) process.exitCode = await semanticLifecycleMain(process.argv.slice(2));
