import { strict as assert } from 'node:assert';
import { Effect, Either, read, write, loadSnapshot, loadCuration } from './io.mts';
import { base, cut, queryBase, output, catalogPath, entityPath, topicPages, sha, json, makeCatalog, makeEntityIndex, construct } from './domain.mts';
const { decodeKgBundleSource } = await import('../../src/hswm/effect-runtime/dist/native-kg-bundle-domain.js');
const topicRegistry = 'ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_TOPICS_2026-09-13.v1.json';
const previousMap = 'ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_2026-09-13.v1.json';

export const build = () => Effect.gen(function* () {
  const snapshot = yield* loadSnapshot(), records = yield* loadCuration();
  const topics = JSON.parse(snapshot.files.get(topicRegistry)!.toString()).topics;
  const oldTopics = JSON.parse(snapshot.files.get(previousMap)!.toString());
  const catalog = makeCatalog(snapshot.tree,snapshot.files,records,topics), entities = makeEntityIndex(catalog,snapshot.files);
  const artifacts = new Map([[catalogPath,Buffer.from(json(catalog))],[entityPath,Buffer.from(json(entities))]]);
  // Native artifact_bindings allow ASCII paths only. Unicode paths retain exact names/hashes
  // in the SHA-bound catalog and SOURCE_VIEW, and are verified against Git bytes there.
  const bindings = catalog.documents.filter(d => d.native_binding_compatible).map(d => ({ path:d.path,sha256:d.sha256 }));
  for (const path of [topicRegistry,previousMap]) if (!bindings.some(b => b.path === path)) bindings.push({ path,sha256:sha(snapshot.files.get(path)!) });
  for (const [path,bytes] of artifacts) bindings.push({ path,sha256:sha(bytes) });
  for (const path of [
    ...['domain.mts','io.mts','build.mts','cli.mts','verify.mts','curation-a.v1.json','curation-b.v1.json','curation-c.v1.json'].map(p => `${base}/${p}`),
    `${queryBase}/shapes.ttl`,...Array.from({ length:8 },(_,i) => `${queryBase}/q${i+1}.rq`)
  ]) bindings.push({ path,sha256:sha(yield* read(path)) });
  const bundle = construct(catalog,records,oldTopics,bindings), bytes = Buffer.from(json(bundle));
  const decoded = decodeKgBundleSource({ sourceId:'research-atlas',rawBytes:bytes },'v2');
  if (Either.isLeft(decoded)) throw new Error(decoded.left.detail);
  artifacts.set(output,bytes);
  // Derived human views share exactly the same curation as RDF and the local reader.
  for (const topic of topics) {
    const selected = records.filter(r => r.topics.includes(topic.id));
    const lines = [`# ${topic.title}`, '', `기존 주제 ID: \`${topic.id}\`. 정리: 2026-10-02, \`SECONDARY_AI\`.`, '',
      '[전체 연구 지도](../HSWM_RESEARCH_ATLAS_2026-10-02.md) · [이전 주제 registry](../../../ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_TOPICS_2026-09-13.v1.json)', '',
      '주제별 배치는 탐색 해석이다. 원문 권위·역사적 상태·실험 판정은 원문에 남으며, 같은 문서가 여러 주제에 나타날 수 있다.', '',
      `조사 대상 Git cut: \`${cut}\`. 아래 ${selected.length}개 요약은 이 cut의 원문에 결속된다.`, ''];
    for (const r of selected) lines.push(`## [${r.title.replace(/\[/g,'(').replace(/\]/g,')')}](../../../${r.path})`, '', r.summary, '',
      `- 자료 역할: \`${r.kind}\` · 관점: ${r.facets.map(f => `\`${f}\``).join(', ') || '미지정'}`,
      `- 원문 상태: ${r.source_status}`, `- 주장 한계: ${r.boundary}`,
      `- 원문 위치: ${r.locator.replace(/\n/g,' / ')}`, '');
    lines.push('## 역사적 열린 질문', '', '아래 질문은 2026-09-13 registry의 기록이며 이번 정리로 해결 판정하지 않았다.', '', ...topic.open_questions.map(q => `- ${q}`), '');
    artifacts.set(`${topicPages}/${topic.id}.md`,Buffer.from(lines.join('\n')));
  }
  return { ...snapshot,records,catalog,entities,bundle,bytes,artifacts };
});
if (import.meta.main) await Effect.runPromise(Effect.gen(function* () {
  assert.deepEqual(process.argv.slice(2),['--write'],`Usage: node ${base}/build.mts --write`);
  const result = yield* build(); for (const [path,bytes] of result.artifacts) yield* write(path,bytes);
  console.log(json({ source_revision:cut,...result.catalog.coverage,...result.bundle.expected_counts,entity_occurrences:result.entities.occurrences.length,outputs:result.artifacts.size }));
}));
