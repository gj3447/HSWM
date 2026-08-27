#!/usr/bin/env node

/**
 * HSWM-DNRD drand verifier boundary.
 *
 * The exact official runtime bundle is hashed and checked for ordinary ESM
 * dependencies before an exact file-URL import; package export metadata cannot
 * redirect the verified code path.
 *
 * Offline mode injects a recorded pulse through a local client and guards the
 * global fetch path. The public drand-client fetchBeacon API validates SHA256(signature)
 * and the Quicknet BLS signature before returning the beacon.  Online mode is
 * explicit and uses quicknetClient plus the same fetchBeacon verifier path.
 */

import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HELPER_VERSION = "hswm-swm0w-drand-node-verifier/v1";
const FIXTURE_SCHEMA = "hswm-swm0w-drand-official-pulse-fixture/v1";
const RECEIPT_SCHEMA = "hswm-swm0w-drand-verification-receipt/v1";
const MAX_FIXTURE_BYTES = 65_536;
const MAX_RUNTIME_BUNDLE_BYTES = 1_048_576;
const OFFICIAL_RUNTIME_BUNDLE_SHA256 = "c5f6eff0d5692efd8f2e19953a49713d17554739016f9d0f3235380aab9ea904";
const OFFICIAL_NODE_EXECUTABLE_SHA256 = "53fb205ae78805130177e24bcb459a69a1518c8d98f8965f31d85aae7ea840fc";
const OFFICIAL_NODE_VERSION = "v24.13.0";

const CHAIN = Object.freeze({
  beacon_id: "quicknet",
  genesis_time: 1692803367,
  group_hash: "f477d5c89f21a17c863a7f937c6a6d15859414d2be09cd448d4279af331c5d3e",
  hash: "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971",
  period: 3,
  public_key: "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a",
  scheme_id: "bls-unchained-g1-rfc9380",
});

const CLIENT = Object.freeze({
  git_commit: "ef8c9260294f8699b5e8c27a6b764f8f0d768bea",
  git_tag_url: "https://github.com/drand/drand-client/tree/v1.4.2",
  npm_integrity: "sha512-jeNJmrVplfgIA/GVndxxJ5mo8y63BS2pEdNhk1siU4pQ+z/BnxsqRnxjH9ag1ip887s12SEgo0MTZPbQNz27NA==",
  npm_shasum: "f9108eef6881e62c0c0f154f30f7bd0a818ea809",
  package: "drand-client",
  source_tarball: "https://registry.npmjs.org/drand-client/-/drand-client-1.4.2.tgz",
  version: "1.4.2",
});

const HELPER_ROOT = dirname(fileURLToPath(import.meta.url));
const TOOL_ROOT = resolve(HELPER_ROOT, "..", "..", "tools", "swm0w_drand");

function canonicalize(value) {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("canonical JSON rejects non-finite numbers");
    return value;
  }
  if (Array.isArray(value)) return value.map(canonicalize);
  if (typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]),
    );
  }
  throw new Error(`canonical JSON rejects ${typeof value}`);
}

function canonicalJson(value) {
  return JSON.stringify(canonicalize(value));
}

function sha256Bytes(value) {
  return createHash("sha256").update(value).digest("hex");
}

function sha256Canonical(value) {
  return sha256Bytes(Buffer.from(canonicalJson(value), "utf8"));
}

async function sha256File(path) {
  return await new Promise((resolveHash, rejectHash) => {
    const hash = createHash("sha256");
    const stream = createReadStream(path);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("error", rejectHash);
    stream.on("end", () => resolveHash(hash.digest("hex")));
  });
}

function exactKeys(value, expected, name) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${name} must be an object`);
  }
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (canonicalJson(actual) !== canonicalJson(wanted)) {
    throw new Error(`${name} keys do not match the frozen schema`);
  }
}

function exactCanonical(actual, expected, name) {
  if (canonicalJson(actual) !== canonicalJson(expected)) {
    throw new Error(`${name} does not match pinned Quicknet data`);
  }
}

function requireHex(value, bytes, name) {
  if (typeof value !== "string" || !new RegExp(`^[0-9a-f]{${bytes * 2}}$`).test(value)) {
    throw new Error(`${name} must be ${bytes} lowercase hex bytes`);
  }
}

function requireRound(value) {
  if (!Number.isSafeInteger(value) || value < 1) {
    throw new Error("expected round must be a positive safe integer");
  }
}

function validateRuntimeBundleSource(bundleBytes) {
  if (bundleBytes.length < 1 || bundleBytes.length > MAX_RUNTIME_BUNDLE_BYTES) {
    throw new Error("verifier runtime bundle exceeds its exact byte boundary");
  }
  const source = new TextDecoder("utf-8", { fatal: true }).decode(bundleBytes);
  const ordinaryEsmDependencies = [
    /^[ \t]*import(?:[ \t\r\n({*"']|$)/m,
    /\bimport[ \t\r\n]*\(/,
    /^[ \t]*export[ \t\r\n]+(?:\*|\{)[\s\S]{0,4096}?\bfrom[ \t\r\n]*["']/m,
  ];
  if (source.includes("\0") || ordinaryEsmDependencies.some((pattern) => pattern.test(source))) {
    throw new Error("verifier runtime bundle contains an ordinary external ESM dependency");
  }
  if (sha256Bytes(bundleBytes) !== OFFICIAL_RUNTIME_BUNDLE_SHA256) {
    throw new Error("verifier runtime bundle is not the Source-A-pinned official artifact");
  }
}

function officialChainInfo() {
  return {
    public_key: CHAIN.public_key,
    period: CHAIN.period,
    genesis_time: CHAIN.genesis_time,
    hash: CHAIN.hash,
    groupHash: CHAIN.group_hash,
    schemeID: CHAIN.scheme_id,
    metadata: { beaconID: CHAIN.beacon_id },
  };
}

function roundTime(round) {
  requireRound(round);
  return CHAIN.genesis_time + (round - 1) * CHAIN.period;
}

function validatePulse(pulse, expectedRound) {
  exactKeys(pulse, ["randomness", "round", "signature"], "pulse");
  requireRound(pulse.round);
  if (pulse.round !== expectedRound) throw new Error("pulse round differs from expected round");
  requireHex(pulse.randomness, 32, "pulse.randomness");
  requireHex(pulse.signature, 48, "pulse.signature");
  const derived = sha256Bytes(Buffer.from(pulse.signature, "hex"));
  if (derived !== pulse.randomness) {
    throw new Error("pulse randomness is not SHA256(signature bytes)");
  }
}

async function verifierProvenance() {
  const lockPath = resolve(TOOL_ROOT, "package-lock.json");
  const packagePath = resolve(TOOL_ROOT, "node_modules", "drand-client", "package.json");
  const bundlePath = resolve(TOOL_ROOT, "node_modules", "drand-client", "build", "esm", "index.mjs");
  const helperPath = fileURLToPath(import.meta.url);
  const [lockBytes, packageBytes, bundleBytes, helperBytes, runtimeExecSha256] = await Promise.all([
    readFile(lockPath),
    readFile(packagePath),
    readFile(bundlePath),
    readFile(helperPath),
    sha256File(process.execPath),
  ]);
  const lock = JSON.parse(lockBytes.toString("utf8"));
  const installed = JSON.parse(packageBytes.toString("utf8"));
  const locked = lock?.packages?.["node_modules/drand-client"];
  validateRuntimeBundleSource(bundleBytes);
  if (
    runtimeExecSha256 !== OFFICIAL_NODE_EXECUTABLE_SHA256 ||
    process.version !== OFFICIAL_NODE_VERSION
  ) {
    throw new Error("Node runtime is not the Source-A-pinned official executable");
  }
  if (
    lock.lockfileVersion !== 3 ||
    lock?.packages?.[""]?.dependencies?.[CLIENT.package] !== CLIENT.version ||
    locked?.version !== CLIENT.version ||
    locked?.resolved !== CLIENT.source_tarball ||
    locked?.integrity !== CLIENT.npm_integrity ||
    installed.version !== CLIENT.version ||
    installed?.repository?.url !== "git+https://github.com/drand/drand-client.git"
  ) {
    throw new Error("installed drand-client does not match the pinned lock/source/integrity");
  }
  return {
    bundlePath,
    provenance: {
      git_commit: CLIENT.git_commit,
      git_tag_url: CLIENT.git_tag_url,
      helper_sha256: sha256Bytes(helperBytes),
      npm_integrity: CLIENT.npm_integrity,
      npm_shasum: CLIENT.npm_shasum,
      package: CLIENT.package,
      package_json_sha256: sha256Bytes(packageBytes),
      package_lock_sha256: sha256Bytes(lockBytes),
      runtime_bundle_sha256: sha256Bytes(bundleBytes),
      runtime_engine: "Node.js",
      runtime_exec_sha256: runtimeExecSha256,
      runtime_trust_status: "TRUSTED_LOCAL_OS_AND_NODE_RUNTIME_REQUIRED",
      runtime_version: process.version,
      source_tarball: CLIENT.source_tarball,
      version: CLIENT.version,
    },
  };
}

async function loadVerifierRuntime(bundlePath) {
  const loaded = await import(pathToFileURL(bundlePath).href);
  if (typeof loaded.fetchBeacon !== "function" || typeof loaded.quicknetClient !== "function") {
    throw new Error("pinned verifier runtime does not expose the required API");
  }
  return Object.freeze({ fetchBeacon: loaded.fetchBeacon, quicknetClient: loaded.quicknetClient });
}

function offlineClient(pulse) {
  const info = officialChainInfo();
  const chain = {
    baseUrl: "offline://pinned-quicknet",
    async info() { return structuredClone(info); },
  };
  return {
    options: {
      disableBeaconVerification: false,
      noCache: true,
      chainVerificationParams: { chainHash: CHAIN.hash, publicKey: CHAIN.public_key },
    },
    async get(round) {
      if (round !== pulse.round) throw new Error("offline client round mismatch");
      return structuredClone(pulse);
    },
    async latest() { throw new Error("offline verifier forbids latest-round lookup"); },
    chain() { return chain; },
  };
}

async function loadOfflineFixture(path, expectedRound) {
  const resolvedPath = resolve(path);
  const metadata = await stat(resolvedPath);
  if (!metadata.isFile() || metadata.size > MAX_FIXTURE_BYTES) {
    throw new Error("offline pulse fixture must be a bounded regular file");
  }
  const bytes = await readFile(resolvedPath);
  const fixture = JSON.parse(bytes.toString("utf8"));
  exactKeys(fixture, ["chain_hash", "pulse", "schema_version", "source_url"], "fixture");
  if (fixture.schema_version !== FIXTURE_SCHEMA || fixture.chain_hash !== CHAIN.hash) {
    throw new Error("offline fixture schema/chain mismatch");
  }
  const expectedUrl = `https://api.drand.sh/${CHAIN.hash}/public/${expectedRound}`;
  if (fixture.source_url !== expectedUrl) throw new Error("offline fixture source URL mismatch");
  validatePulse(fixture.pulse, expectedRound);
  return { fixture, fixtureSha256: sha256Bytes(bytes) };
}

async function verifyOffline(path, expectedRound, verifierRuntime) {
  const { fixture, fixtureSha256 } = await loadOfflineFixture(path, expectedRound);
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error("offline verification forbids fetch"); };
  try {
    const verified = await verifierRuntime.fetchBeacon(offlineClient(fixture.pulse), expectedRound);
    exactCanonical(verified, fixture.pulse, "drand-client verified beacon");
    return {
      fixtureSha256,
      pulse: verified,
      sourceUrl: fixture.source_url,
      networkPolicy: "OFFLINE_INJECTED_CLIENT_FETCH_GUARD",
    };
  } finally {
    globalThis.fetch = originalFetch;
  }
}

async function verifyOnline(expectedRound, verifierRuntime) {
  const client = verifierRuntime.quicknetClient();
  const info = await client.chain().info();
  exactCanonical(info, officialChainInfo(), "online chain info");
  const verified = await verifierRuntime.fetchBeacon(client, expectedRound);
  validatePulse(verified, expectedRound);
  return {
    fixtureSha256: null,
    pulse: verified,
    sourceUrl: `https://api.drand.sh/${CHAIN.hash}/public/${expectedRound}`,
    networkPolicy: "ONLINE_EXPLICIT",
  };
}

function parseArguments(argv) {
  const mode = argv[0];
  if (mode !== "offline" && mode !== "online") {
    throw new Error("usage: verify-beacon.mjs offline|online --expected-round N [--pulse-file PATH]");
  }
  let expectedRound = null;
  let pulseFile = null;
  for (let index = 1; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (value === undefined) throw new Error(`missing value for ${flag}`);
    if (flag === "--expected-round") expectedRound = Number(value);
    else if (flag === "--pulse-file") pulseFile = value;
    else throw new Error(`unsupported argument ${flag}`);
  }
  requireRound(expectedRound);
  if ((mode === "offline") !== (typeof pulseFile === "string")) {
    throw new Error("offline requires --pulse-file and online forbids it");
  }
  return { expectedRound, mode, pulseFile };
}

async function main() {
  const { expectedRound, mode, pulseFile } = parseArguments(process.argv.slice(2));
  const { bundlePath, provenance } = await verifierProvenance();
  const verifierRuntime = await loadVerifierRuntime(bundlePath);
  const result = mode === "offline"
    ? await verifyOffline(pulseFile, expectedRound, verifierRuntime)
    : await verifyOnline(expectedRound, verifierRuntime);
  const pulse = {
    randomness: result.pulse.randomness,
    round: result.pulse.round,
    round_time_unix: roundTime(result.pulse.round),
    signature: result.pulse.signature,
  };
  const unsigned = {
    chain: CHAIN,
    chronology_claim_allowed: false,
    helper_version: HELPER_VERSION,
    input_fixture_sha256: result.fixtureSha256,
    mode,
    pulse,
    pulse_source_url: result.sourceUrl,
    schema_version: RECEIPT_SCHEMA,
    verification: {
      accepted_beacon_sha256: sha256Canonical(result.pulse),
      accepted_by: "drand-client.fetchBeacon",
      network_policy: result.networkPolicy,
      randomness_derivation: "SHA256(raw_signature_bytes)",
      signature_scheme: CHAIN.scheme_id,
    },
    verified_at_unix: Math.floor(Date.now() / 1000),
    verifier: provenance,
  };
  const receipt = { ...unsigned, receipt_sha256: sha256Canonical(unsigned) };
  process.stdout.write(`${canonicalJson(receipt)}\n`);
}

main().catch((error) => {
  process.stderr.write(`SWM0W_DRAND_VERIFICATION_FAILED: ${error?.message ?? String(error)}\n`);
  process.exitCode = 1;
});
