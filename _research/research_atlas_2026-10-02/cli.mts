/** Read-only multiscale research navigation. Explicit scope; exact, untruncated source fallback. */
import { strict as assert } from 'node:assert';
import { Effect, loadBoundCatalog, loadBoundEntities, readOriginal } from './io.mts';
import { base, json, selectUnits, localContext } from './domain.mts';
const help = `node ${base}/cli.mts <command>
  overview                               Topic map and declared coverage
  gaps                                   Explicit citations missing from the fixed source cut
  topic TOPIC                            Curated units in one topic
  search TEXT                            Literal term conjunction over research summaries
  context TOPIC FACET|- QUERY|- BYTES     Whole summaries within an explicit byte budget
  show SOURCE_ID|PATH                    Summary, headings and explicit source citations
  read SOURCE_ID|PATH [SECTION_ID]        Exact pinned UTF-8 source; full by default
  entities UID [SOURCE_PATH]             Exact UID occurrences; select source to read node
No network, model calls, graph writes, runtime state or learned Semantic Weight.
Summaries are AI navigation views. Source sections may omit conditions in other sections; read full before relying on a claim.\n`;
export const run = (args: string[]) => Effect.gen(function* () {
  const [command,...rest] = args;
  if (!command || ['help','--help'].includes(command)) { assert(rest.length === 0); return help; }
  const { catalog,bundle } = yield* loadBoundCatalog();
  const locate = (value: string) => {
    const row = catalog.documents.find(d => d.id === value || d.path === value) ?? catalog.files.find(d => d.id === value || d.path === value);
    assert(row,'Unknown source ID/path at the fixed cut'); return row;
  };
  const brief = (d: any) => ({ id:d.id,path:d.path,title:d.title,...d.curation });
  switch (command) {
    case 'overview': assert.equal(rest.length,0); return json({ coverage:catalog.coverage,source_revision:catalog.source_revision,topics:catalog.topics.map(t => ({ id:t.id,title:t.title,units:selectUnits(catalog,{topic:t.id}).length })), scope:catalog.scope });
    case 'gaps': assert.equal(rest.length,0); return json({ status:'HISTORICAL_CITATION_GAPS_NOT_SILENTLY_REPAIRED',items:catalog.documents.flatMap(d => d.citations.filter(c => c.status !== 'AT_SOURCE_CUT').map(c => ({ source:d.path,...c }))) });
    case 'topic': assert.equal(rest.length,1); return json(selectUnits(catalog,{topic:rest[0]}).map(brief));
    case 'search': assert(rest.length > 0 && rest.join(' ').trim()); return json({ method:'LEXICAL_CANDIDATES_NOT_SEMANTIC_MATCH_OR_W',items:selectUnits(catalog,{query:rest.join(' ')}).map(brief) });
    case 'context': {
      assert.equal(rest.length,4); const [topic,facet,query,budget] = rest;
      return json(localContext(catalog,{...(topic === '-' ? {} : {topic}),...(facet === '-' ? {} : {facet}),...(query === '-' ? {} : {query})},Number(budget)));
    }
    case 'show': assert.equal(rest.length,1); return json(locate(rest[0]));
    case 'read': {
      assert(rest.length === 1 || rest.length === 2); const row = locate(rest[0]), bytes = yield* readOriginal(row);
      const section = rest[1] ?? 'full';
      const span = row.sections?.find(s => s.id === section) ?? (section === 'full' ? { start_byte:0,end_byte:bytes.length } : null);
      assert(span,'Unknown section ID');
      return new TextDecoder('utf-8',{fatal:true}).decode(bytes.subarray(span.start_byte,span.end_byte));
    }
    case 'entities': {
      assert(rest.length === 1 || rest.length === 2); const index = yield* loadBoundEntities(bundle);
      const occurrences = index.occurrences.filter(o => o.uid === rest[0] && (!rest[1] || o.path === rest[1]));
      if (occurrences.length !== 1) return json({ status:occurrences.length ? 'SOURCE_SELECTION_REQUIRED' : 'NOT_FOUND',occurrences });
      const o = occurrences[0], row = locate(o.path), bytes = yield* readOriginal(row);
      const original = JSON.parse(bytes.toString()).nodes[Number(o.pointer.split('/').at(-1))]; assert.equal(original.uid,o.uid);
      return json({ status:'EXACT_SOURCE_OCCURRENCE',occurrence:o,original,nonclaim:'No identity merge, live presence, authority upgrade or neighborhood activation.' });
    }
    default: throw new Error(`Unknown command.\n${help}`);
  }
});
if (import.meta.main) {
  try { process.stdout.write(await Effect.runPromise(run(process.argv.slice(2)))); }
  catch (e) { process.stderr.write(`${String(e)}\n`); process.exitCode = 1; }
}
