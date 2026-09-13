import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { Either } from "effect";
import { expect, it } from "vitest";
import { decodeNativeTaskJson, renderNativeTaskJson } from "../src/native-task-json-domain.js";
import { parseNativeS2STaskArchive, parseNativeS2STaskArchiveEntry, serializeNativeS2STaskArchive } from "../src/native-s2s-task-archive-domain.js";
import { nativeS2STaskManifestPayload } from "../src/native-s2s-family-domain.js";

type Oracle = { readonly source_pins: Readonly<Record<string, string>>; readonly cases: readonly { readonly name: string; readonly kind: string; readonly input_json: string; readonly accepted: boolean; readonly canonical_json?: string }[] };
const oracle = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_family_v2/archive.original.v1.json", import.meta.url), "utf8")) as Oracle;

it("matches original source-bound task and batch archive acceptance, including resealed duplicate loss", () => {
  for (const [path, sha] of Object.entries(oracle.source_pins)) expect(createHash("sha256").update(readFileSync(new URL(`../../../../${path}`, import.meta.url))).digest("hex")).toBe(sha);
  for (const row of oracle.cases) {
    const input = Either.getOrThrow(decodeNativeTaskJson(new TextEncoder().encode(row.input_json)));
    if (row.kind === "task") {
      const result = parseNativeS2STaskArchiveEntry(input);
      expect(Either.isRight(result), row.name).toBe(row.accepted);
      if (Either.isRight(result)) {
        const payload = Either.getOrThrow(nativeS2STaskManifestPayload(result.right));
        expect(renderNativeTaskJson({ ...payload, manifest_sha256: result.right.manifestSha256 }), row.name).toBe(row.canonical_json);
      }
    } else {
      const result = parseNativeS2STaskArchive(input);
      expect(Either.isRight(result), row.name).toBe(row.accepted);
      if (Either.isRight(result)) {
        expect(renderNativeTaskJson(Either.getOrThrow(serializeNativeS2STaskArchive(result.right.tasks))), row.name).toBe(row.canonical_json);
        if (row.name === "retained-structural-duplicates") {
          expect(result.right.tasks).toHaveLength(4);
          expect(result.right.duplicateStructuralTaskDraws).toEqual([[1, 0], [2, 0], [3, 0]]);
        }
      }
    }
  }
});
