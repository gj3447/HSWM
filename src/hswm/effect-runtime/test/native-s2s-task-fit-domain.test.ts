import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { Either } from "effect";
import { expect, it } from "vitest";
import { fitNativeS2STask } from "../src/native-s2s-task-fit-domain.js";
import { parseNativeS2STaskArchiveEntry } from "../src/native-s2s-task-archive-domain.js";

type History = { readonly update: number; readonly train_loss_hex: string; readonly dev_loss_hex: string; readonly gradient_norm_hex: string | null; readonly clipped: boolean; readonly improved: boolean };
type Optimization = { readonly config: Readonly<Record<string, string | number>>; readonly history: readonly History[]; readonly initial_parameters_sha256: string; readonly best_parameters_sha256: string; readonly best_update: number; readonly stopped_update: number; readonly update_count: number; readonly clipped_update_count: number; readonly termination_reason: string; readonly train_dataset_sha256: string; readonly dev_dataset_sha256: string };
type Oracle = { readonly source_pins: Readonly<Record<string, string>>; readonly task: unknown; readonly results: readonly { readonly arm: string; readonly parameters: Readonly<Record<string, readonly number[]>>; readonly optimization: Optimization }[] };
const oracle = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/s2s_fit_v1/original_full_task_three_updates.json", import.meta.url), "utf8")) as Oracle;
const fromHex = (source: string): number => {
  const match = /^(-?)0x([01])\.([0-9a-f]+)p([+-]?\d+)$/.exec(source)!;
  const mantissa = Number(BigInt(`0x${match[2]}${match[3]}`));
  return (match[1] === "-" ? -1 : 1) * mantissa * 2 ** (Number(match[4]) - 4 * match[3]!.length);
};
const close = (actual: number, expected: number, label: string) => expect(Math.abs(actual - expected), label).toBeLessThanOrEqual(5e-14 * Math.max(1, Math.abs(expected)));

it("compares the complete native task fit against unmocked original Python runs", () => {
  for (const [path, sha] of Object.entries(oracle.source_pins)) expect(createHash("sha256").update(readFileSync(new URL(`../../../hswm/experiments/${path}`, import.meta.url))).digest("hex")).toBe(sha);
  const task = Either.getOrThrow(parseNativeS2STaskArchiveEntry(oracle.task));
  for (const row of oracle.results) {
    const original = row.optimization, config = original.config;
    const actual = Either.getOrThrow(fitNativeS2STask(task, row.arm, {
      seed: config["seed"], maxUpdates: config["max_updates"], patience: config["patience"],
      learningRate: fromHex(String(config["learning_rate_hex"])), beta1: fromHex(String(config["beta1_hex"])), beta2: fromHex(String(config["beta2_hex"])),
      epsilon: fromHex(String(config["epsilon_hex"])), gradientClip: fromHex(String(config["gradient_clip_hex"])), minDelta: fromHex(String(config["min_delta_hex"])),
    }));
    expect(actual.protocolReceiptStatus).toBe("NOT_ISSUED_NATIVE_BACKEND_QUALIFICATION_REQUIRED");
    expect(actual.trainDatasetSha256).toBe(original.train_dataset_sha256);
    expect(actual.devDatasetSha256).toBe(original.dev_dataset_sha256);
    expect(actual.fit.initialParametersSha256).toBe(original.initial_parameters_sha256);
    expect([actual.fit.bestUpdate, actual.fit.stoppedUpdate, actual.fit.updateCount, actual.fit.clippedUpdateCount, actual.fit.terminationReason]).toEqual([original.best_update, original.stopped_update, original.update_count, original.clipped_update_count, original.termination_reason]);
    expect(actual.fit.history).toHaveLength(original.history.length);
    for (let index = 0; index < original.history.length; index += 1) {
      const expected = original.history[index]!, observed = actual.fit.history[index]!;
      expect([observed.update, observed.clipped, observed.improved]).toEqual([expected.update, expected.clipped, expected.improved]);
      close(observed.trainLoss, fromHex(expected.train_loss_hex), `${row.arm} train loss ${index}`);
      close(observed.devLoss, fromHex(expected.dev_loss_hex), `${row.arm} dev loss ${index}`);
      if (expected.gradient_norm_hex === null) expect(observed.gradientNorm).toBeNull();
      else close(observed.gradientNorm!, fromHex(expected.gradient_norm_hex), `${row.arm} gradient norm ${index}`);
    }
    const parameters = Object.fromEntries(Object.entries(actual.fit.parameters));
    for (const [name, expected] of Object.entries(row.parameters)) {
      const key = name.replace(/_([a-z])/g, (_, character: string) => character.toUpperCase());
      const observed = parameters[key] as readonly number[];
      expect(observed).toHaveLength(expected.length);
      for (let index = 0; index < expected.length; index += 1) close(observed[index]!, expected[index]!, `${row.arm} ${key}[${index}]`);
    }
  }
}, 120_000);
