#!/usr/bin/env node
/** Reuses the existing durable loop; all model transport remains a local fixture. */
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Effect, Either } from '../../src/hswm/effect-runtime/node_modules/effect/dist/esm/index.js';
import { runCrossLayerMapRehearsal } from '../cross_layer_map_v1/run.mjs';
import { canonicalJsonBytes } from '../../src/hswm/effect-runtime/dist/canonical-atom-v2-json.js';
import { compileCrossLayerMapRdfView } from '../../src/hswm/effect-runtime/dist/cross-layer-map-rdf-view.js';
import { compareSemanticFrameRepresentations, decodeSemanticFrameRepresentationBytes } from '../../src/hswm/effect-runtime/dist/semantic-frame-representation.js';
import { queryKgBundle, validateKgShacl } from '../../src/hswm/effect-runtime/dist/native-kg-standards.js';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const right = result => {
  if (Either.isLeft(result)) throw new Error(JSON.stringify(result.left));
  return result.right;
};
const check = (condition, message) => { if (!condition) throw new Error(message); };
const usage = 'Usage: node _research/semantic_map_engineering_v1/run.mjs --output NEW_DIRECTORY\nLocal fixture only; build the Effect runtime first.\n';

export async function runSemanticMapEngineering(output) {
  await mkdir(dirname(output), { recursive: true });
  await mkdir(output); // Atomic refusal to overwrite an existing run.
  const lifecycle = await runCrossLayerMapRehearsal(join(output, 'lifecycle'));
  const query = await readFile(join(root, '_research/semantic_map_engineering_v1/queries/map-spec.rq'), 'utf8');
  const shape = new Uint8Array(await readFile(join(root, '_research/semantic_map_engineering_v1/shapes/map-spec.ttl')));
  const artifacts = [];
  const writeArtifact = async (name, bytes) => {
    await writeFile(join(output, name), bytes, { flag: 'wx' });
    const descriptor = { name, sha256: sha(bytes), byteLength: bytes.byteLength };
    artifacts.push(descriptor);
    return descriptor;
  };
  const phases = [];
  for (const [name, input] of Object.entries(lifecycle.frames)) {
    const comparison = right(compareSemanticFrameRepresentations(input.frame));
    const sourceBytes = right(canonicalJsonBytes(input.frame));
    await writeArtifact(`${name}.source-frame.json`, sourceBytes);
    const representations = [];
    for (const encoding of comparison.representations) {
      const decoded = right(decodeSemanticFrameRepresentationBytes(encoding.kind, encoding.bytes));
      check(Buffer.from(right(canonicalJsonBytes(decoded))).equals(Buffer.from(sourceBytes)), `${name}/${encoding.kind} must recover the entire canonical frame value`);
      const file = await writeArtifact(`${name}.${encoding.kind}.json`, encoding.bytes);
      representations.push({ kind: encoding.kind, ...file, fullRoundTripFidelity: true, costScope: encoding.costScope });
    }
    const view = right(compileCrossLayerMapRdfView(input));
    const canonicalGraph = new TextDecoder().decode(lifecycle.projection.projection.nquads);
    check([view.manifest.relationAtomIri, view.manifest.contextAtomIri].every(iri => canonicalGraph.includes(`<${iri}>`)), `${name} derived provenance must join the exact canonical RDF atom identifiers`);
    const graph = { nquads: view.nquads, descriptor: { dataset: view.manifest.dataset }, provO: new Uint8Array() };
    const rows = await Effect.runPromise(queryKgBundle(graph, query));
    const validation = await Effect.runPromise(validateKgShacl(graph, shape));
    check(Array.isArray(rows) && rows.length > 0, `${name} MapSpec query must expose fields`);
    check(validation.conforms, `${name} derived MapSpec SHACL profile must conform`);
    check(rows.every(row => row.sourceRef?.value === input.packet.context.source.modelRef && row.sourceDigest?.value === input.packet.context.source.digest && row.targetRef?.value === input.packet.context.target.modelRef && row.targetDigest?.value === input.packet.context.target.digest && row.contextDigest?.value === view.manifest.contextContentSha256 && row.relationKey?.value === view.manifest.relationCanonicalKeyId && row.contextKey?.value === view.manifest.contextCanonicalKeyId), `${name} query must retain source/context commitments`);
    // A join produces combinations of collection entries, not one map per row.
    // Reconstruct an ordered collection by its ordinal to check the actual query.
    const orderedValues = (valueKey, ordinalKey) => {
      const entries = new Map();
      for (const row of rows) {
        if (row[valueKey] === undefined || row[valueKey] === null) continue;
        const ordinal = Number(row[ordinalKey]?.value);
        check(Number.isSafeInteger(ordinal) && ordinal >= 0, 'invalid queried ordinal');
        check(!entries.has(ordinal) || entries.get(ordinal) === row[valueKey].value, 'conflicting values at a queried ordinal');
        entries.set(ordinal, row[valueKey].value);
      }
      return [...entries.entries()].sort(([a], [b]) => a - b).map(([, value]) => value);
    };
    for (const [valueKey, ordinalKey, expected] of [
      ['action', 'actionOrdinal', input.packet.context.actionAllowlist],
      ['loss', 'lossOrdinal', input.packet.context.declaredLosses],
      ['scopeContext', 'scopeContextOrdinal', input.packet.context.supportScope.contexts],
      ['observable', 'observableOrdinal', input.packet.context.supportScope.observableFields]
    ]) check(JSON.stringify(orderedValues(valueKey, ordinalKey)) === JSON.stringify(expected), `${name} query must preserve ${valueKey} values and order`);
    await writeArtifact(`${name}.mapspec.nq`, view.nquads);
    await writeArtifact(`${name}.mapspec-manifest.json`, right(canonicalJsonBytes(view.manifest)));
    phases.push({ name, relationRevision: input.frame.relation.key.revisionId, stateRevision: input.frame.stateRevision,
      legacyRuntimeFrameSha256: input.frame.frameSha256, sourceCanonicalSha256: comparison.sourceCanonicalSha256,
      fullRoundTripFidelity: comparison.fullRoundTripFidelity, representations,
      mapView: { manifest: view.manifest, queryRows: rows, shacl: validation } });
  }
  check(JSON.stringify(phases.map(phase => phase.relationRevision)) === '[0,1,2]', 'seed, meaning revision and input binding must remain distinct');
  const { initial, learned, rebound } = lifecycle.frames;
  check(initial.frame.relation.semantic.semanticText !== learned.frame.relation.semantic.semanticText, 'fixture must revise its semantic text');
  check(learned.frame.relation.semantic.semanticText === rebound.frame.relation.semantic.semanticText, 'recovered execution must consume the revised semantics');
  check(new Set(phases.map(phase => phase.mapView.manifest.contextContentSha256)).size === 1, 'immutable MapSpec context must survive the lifecycle');

  const paths = [
    '_research/semantic_map_engineering_v1/run.mjs', '_research/semantic_map_engineering_v1/queries/map-spec.rq',
    '_research/semantic_map_engineering_v1/shapes/map-spec.ttl', '_research/cross_layer_map_v1/run.mjs',
    'src/hswm/effect-runtime/src/semantic-frame-representation.ts', 'src/hswm/effect-runtime/dist/semantic-frame-representation.js',
    'src/hswm/effect-runtime/src/cross-layer-map-rdf-view.ts', 'src/hswm/effect-runtime/dist/cross-layer-map-rdf-view.js',
    'src/hswm/effect-runtime/package-lock.json'
  ];
  const sourceArtifacts = await Promise.all(paths.map(async path => {
    const bytes = await readFile(join(root, path));
    return { path, sha256: sha(bytes), byteLength: bytes.byteLength };
  }));
  const lock = JSON.parse(await readFile(join(root, 'src/hswm/effect-runtime/package-lock.json'), 'utf8'));
  const dependencies = ['effect', 'n3', '@comunica/query-sparql-rdfjs', 'rdf-validate-shacl'].map(name => {
    const entry = lock.packages[`node_modules/${name}`];
    check(entry?.version && entry.integrity && entry.license, `dependency pin missing for ${name}`);
    return { name, version: entry.version, integrity: entry.integrity, license: entry.license, authority: 'IMPLEMENTATION_PACKAGE_NOT_W3C_STANDARD_AUTHORITY' };
  });
  const report = {
    schema: 'hswm-semantic-map-engineering/v1', status: 'ENGINEERING_FIXTURE_PASSED',
    evidence: 'SCRIPTED_TRANSPORT_AND_SERIALIZATION_ONLY', modelCalls: 0,
    fixtureTransportCalls: lifecycle.report.fixtureTransportCalls,
    sourceArtifacts, dependencies, artifacts, phases,
    codecContract: { fidelity: 'COMPLETE_CANONICAL_FRAME_VALUE', sourceIntegrity: 'SHA256_NOT_EXTERNAL_AUTHENTICATION', legacyFrameSha256: 'PRESERVED_OPAQUE_RUNTIME_COMMITMENT' },
    cost: { measured: 'UTF8_SERIALIZED_PAYLOAD_BYTES', modelTokens: 'NOT_MEASURED', modelLatency: 'NOT_MEASURED', queryLatency: 'NOT_MEASURED', indexBuildAndUpdate: 'NOT_MEASURED', learningCost: 'NOT_MEASURED', codeAndSchemaDeployment: 'EXCLUDED_SOURCE_ARTIFACT_SIZES_REPORTED_SEPARATELY', conclusion: 'NO_UNIVERSAL_MINIMUM_WINNER' },
    lifecycle: { report: 'lifecycle/report.json', cycle: lifecycle.report.cycle, originalRdfConforms: lifecycle.report.graph.shacl.conforms, originalRdfCurrentRoles: lifecycle.report.graph.currentRoles.length },
    mappingComparison: lifecycle.report.comparison,
    claimCeiling: 'NO_REAL_MODEL_GAIN_NO_OPTIMALITY_NO_CAUSAL_OR_CR_FCL_PROMOTION'
  };
  const reportBytes = new TextEncoder().encode(JSON.stringify(report, null, 2) + '\n');
  await writeFile(join(output, 'report.json'), reportBytes, { flag: 'wx' });
  return { report, reportSha256: sha(reportBytes) };
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const args = process.argv.slice(2);
  if (args.length === 1 && ['--help', '-h'].includes(args[0])) process.stdout.write(usage);
  else if (args.length !== 2 || args[0] !== '--output' || !args[1].trim()) { process.stderr.write(usage); process.exitCode = 2; }
  else {
    const output = resolve(args[1]);
    await runSemanticMapEngineering(output).then(({ report, reportSha256 }) => {
      process.stdout.write(JSON.stringify({ status: report.status, report: join(output, 'report.json'), reportSha256,
        frames: report.phases.length, losslessRoundTrips: report.phases.reduce((n, phase) => n + phase.representations.length, 0), modelCalls: report.modelCalls }, null, 2) + '\n');
    }).catch(error => { process.stderr.write(`${error.message}\n`); process.exitCode = 1; });
  }
}
