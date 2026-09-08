"""Read-only compatibility probe using installed USL and an authored HSWM fixture."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from hswm.cells.conditional import Reject, digest
from hswm.infrastructure.usl_cli import preview_usl_request


NODE_PROBE = r'''
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
const [uslRoot, fixturePath, sourcePath] = process.argv.slice(2);
const load = (p) => import(pathToFileURL(join(uslRoot, p)).href);
const [language, resolver, locator, effect] = await Promise.all([
  load("src/language/index.ts"), load("src/resolve.ts"), load("src/locator.ts"),
  load("node_modules/effect/dist/esm/index.js"),
]);
const { Effect, Either, Layer } = effect;
const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));
const original = readFileSync(sourcePath, "utf8");
const sources = [original, original.replace(
  '함께 지정한다";',
  '함께 지정한다" applies "development reference review" check inspect(code, target) = "inspect supplied evidence";',
)];
const result = [];
for (const source of sources) {
  const plan = Either.getOrThrow(language.compileSource(source));
  const calls = [];
  const layer = Layer.succeed(resolver.Resolvers, { resolve: (loc) => {
    calls.push(locator.formatLocator(loc));
    const row = fixture.report.resources.find((r) => JSON.stringify(r.resolution.locator) === JSON.stringify(loc));
    if (!row) throw new Error("unexpected injected locator");
    return Effect.succeed(structuredClone(row.resolution));
  }});
  const report = await Effect.runPromise(language.observeProgram(plan, { sourceText: source }).pipe(Effect.provide(layer)));
  result.push({ plan, report, resolverCalls: calls.length });
}
process.stdout.write(JSON.stringify(result));
'''


def main() -> None:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usl-root", type=Path, default=here.parents[2] / "USL")
    parser.add_argument("--out", type=Path, default=here / "review_v2_hswm_compat_2026-09-08.json")
    args = parser.parse_args()
    fixture_path = here / "examples/preview.v1.json"
    source_path = here / "examples/development_reference.usl"
    fixture = json.loads(fixture_path.read_text())
    old_result = preview_usl_request(deepcopy(fixture))
    with tempfile.TemporaryDirectory(prefix="hswm-usl-v2-review-") as directory:
        program = Path(directory) / "probe.mts"
        program.write_text(NODE_PROBE)
        run = subprocess.run([
            str(args.usl_root / "node_modules/.bin/tsx"), str(program),
            str(args.usl_root), str(fixture_path), str(source_path),
        ], capture_output=True, text=True, check=True)
    results = []
    for observed in json.loads(run.stdout):
        request = deepcopy(fixture)
        request.update(plan=observed["plan"], report=observed["report"])
        request["policy"]["plan_digest"] = digest(request["plan"])
        try:
            preview_usl_request(request)
            status, error = "ACCEPTED", None
        except Reject as rejection:
            status, error = "REJECTED", str(rejection)
        results.append({
            "meaning_has_contract": "contract" in request["plan"]["meanings"][0],
            "report_schema": request["report"]["schema"],
            "resolver_calls": observed["resolverCalls"], "status": status, "error": error,
        })
    record = {
        "schema": "hswm-usl-v2-compatibility-review/v1", "observed_on": "2026-09-08",
        "injected_resolvers_only": True, "external_network_requests": 0,
        "legacy_v1_preview": old_result["preview"], "current_usl_results": results,
        "source_sha256": {
            str(p.relative_to(here.parent.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__).resolve(), fixture_path, source_path,
                      here.parent.parent / "src/hswm/infrastructure/usl_adapter.py",
                      here.parent.parent / "src/hswm/infrastructure/usl_cli.py"]
        },
        "interpretation": "The existing HSWM v1 path works and fails closed on current USL v2; explicit contract-aware version migration is required.",
    }
    args.out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
