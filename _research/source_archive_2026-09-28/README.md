# HSWM external source archive

2026-09-28 capture: **810 of 852 canonical citation URLs captured**, with **42
unavailable exact URLs** retained explicitly. Supplementary full-text retrievals
bring the archive to **390 distinct parsed PDF bodies**, 735 ordinary HTML bodies
and 21 other bodies. Another 14 distinct HTML challenge bodies are preserved for
audit and excluded from source coverage. The 1,160 distinct stored bodies occupy
1,240,343,457 bytes (about 1.16 GiB). All physical copies passed SHA-256 and size
checks. A captured landing page alone does not establish that a paper's full text
was obtained.

This is an additive archive of the external sources cited by HSWM research,
canon, and their directly linked source maps. The inventory declares the exact
local corpus and citation locations. It does not crawl links from external
websites or download model weights, datasets, or entire software dependency trees.

The existing dated research documents and their historical hashes remain intact.
A retrieval made now fixes the bytes observed now; it does not retroactively
prove which version a previous researcher read. An unversioned source remains
labelled as a current observation unless an explicit version is recovered from
the archived source. A citation page and a full-text paper are separate resources.

Original response bodies are kept under the ignored local directory
`.hswm-local/research-source-archive-20260928/`, keyed by SHA-256. Public manifests
contain URLs, citation locations, timestamps, media types, byte lengths, digests,
and failure records. Third-party bodies and extracted paper text are not committed.
Their individual licences are not inferred from public accessibility.

The hash identifies the downloaded HTTP representation after transport content
decoding. It is not a hash of the rendered page, its external assets, or a promise
that the remote URL will serve these bytes again. Failures, challenge pages,
landing pages, and verified PDF bodies must remain distinguishable.

Provenance follows the existing [PROV-O](https://www.w3.org/TR/2013/REC-prov-o-20130430/)
model: the retrieval is an activity; the stored copy is an entity; the local
document's citation is an explicit reference. A citation does not imply that the
document was mechanically derived from the paper or that its claims are true.
The repository's RDF 1.1, SHACL 1.0 and SPARQL 1.1 tooling validates and queries
the additive archive projection. This archive changes no HSWM efficacy judgment.

The TypeScript/Effect archiver records immutable per-source receipts, limits each
download, and rehashes local files when verifying an existing collection. A later
retry or replacement source is a new collection rather than an overwritten receipt.

## Scope and records

[inventory.v2.json](inventory.v2.json) is the authoritative request inventory:
261 hashed local input files, 852 external URLs, and 1,473 citation occurrences.
Its scope includes every tracked Markdown file under `docs/research` and
`docs/canon`, three named operations documents, and directly linked source-map
JSON files. External full-text links are expanded only from identified primary
pages; this is a finite cited-source archive, not a crawl of the Internet.

The initial Markdown extractor accidentally included trailing Korean prose in
some URLs. [The correction map](inventory.v1-to-v2-correction-map.v1.json)
preserves 128 malformed initial requests and 48 newly exposed correct requests.
The first inventory and its receipts remain intact for audit; malformed request
failures are not counted as unavailable sources in the final 852-URL inventory.
Their receipts and any captured bodies remain audit records, included in the
archive-wide body totals but excluded from the corrected source graph.

The numbered supplement manifests preserve later full-text discovery, explicit
arXiv versions, declared size increases, alternate editions, and retries. Most
requests use native fetch. The last collection explicitly uses ordinary curl
because some author sites time out through native fetch but respond to curl.
Transport is recorded per receipt; its absence in earlier receipts means native
fetch. [toolchain.v1.json](toolchain.v1.json) records the existing executable
versions and digests; no tools or packages were installed for this archive.

- [catalogue.v1.json](catalogue.v1.json): canonical source coverage, citation bindings, content
  status, alternate/full-text links, and unresolved retrievals.
- `receipts/`: public metadata projections of immutable private collection
  receipts; each projection binds its original private receipt by SHA-256.
- `captures-validation.v1.json`: every physical blob copy rehashed; unique PDF
  bodies parsed with `pdfinfo`; HTML titles checked for known challenge/error
  pages. Readable HTML is not automatically classified as full-text research.
- `pdf-validation.v1.json` and `html-validation.v1.json`: preserved intermediate
  audits before the later collections; the combined audit is authoritative.
- [Archive KG](../../ontology/development/HSWM_EXTERNAL_SOURCE_ARCHIVE_2026-09-28.v1.json):
  source, retrieval attempt, immutable content, and local citation occurrence
  nodes; [SHACL and SPARQL](../../ontology/queries/hswm_source_archive_2026-09-28/).
- [retrieval-provenance.v1.jsonld](retrieval-provenance.v1.jsonld): PROV-O
  retrieval activities and individual captured copies, linked to shared byte
  identities without treating a citation as a derivation.

`ARCHIVED` in a receipt means that bytes were captured. The independent content
audit can still exclude those bytes as a challenge page. Canonical URL coverage
requires an accepted capture of that exact request; obtaining an alternate
edition does not silently turn an inaccessible original into a success.

## Recheck the local archive

Run from the repository root. Raw originals remain locally available even though
Git contains only the metadata. A fresh clone needs its own retrieval; it cannot
recover a private body from a SHA-256 digest alone.

```sh
npm --prefix src/hswm/effect-runtime run build
node src/hswm/effect-runtime/dist/research-source-archive-process.js verify \
  --root .hswm-local/research-source-archive-20260928
python3 _research/source_archive_2026-09-28/audit-captures.py \
  --root .hswm-local/research-source-archive-20260928 \
  --output .hswm-local/source-archive-recheck.json
node src/hswm/effect-runtime/dist/native-kg-process.js validate \
  --source archive=ontology/development/HSWM_EXTERNAL_SOURCE_ARCHIVE_2026-09-28.v1.json \
  --profile v2 --shapes ontology/queries/hswm_source_archive_2026-09-28/archive-shapes.ttl
node src/hswm/effect-runtime/dist/native-kg-process.js query \
  --source archive=ontology/development/HSWM_EXTERNAL_SOURCE_ARCHIVE_2026-09-28.v1.json \
  --profile v2 --query ontology/queries/hswm_source_archive_2026-09-28/coverage.rq
```

Run `verify` separately on each numbered `supplement-*` directory to verify its
manifest and receipt bindings as well. The Python audit discovers all collections
and verifies their body copies but does not replace the runtime receipt verifier.
The source's collection and digest locate its original at
`<collection>/blobs/sha256/<sha256>`.

For a new bounded collection, pass a new manifest and a new private root to
`archive --manifest FILE --root DIRECTORY`; add `--transport curl` only when
desired. Reusing a root with a changed manifest is refused. Default limits are
four concurrent requests, 30 seconds per request and 32 MiB per response; a
manifest may explicitly raise an individual response limit to at most 256 MiB.
Later retrievals can produce different bytes and must receive their own receipts.

An archive command's successful exit means that its attempt receipts were saved;
inspect the reported failure count and catalogue for source coverage. `verify`
checks integrity, including faithful failure records, rather than completeness.

## Validation recorded on 2026-09-28

All four private collections passed runtime receipt/blob verification (1,438
attempts), and the combined audit rehashed every stored copy. All 261 input-file
hashes and all 14 public KG artifact bindings match. `npm run check`, the eight
focused archive tests, the runtime build, and portable Markdown compilation pass.

The 5,152-node / 5,611-relation KG passes the existing v2 SHACL profile and the
archive shapes. The five SPARQL queries return 1,473 citation bindings, two
coverage groups (810 captured / 42 unavailable), 34 excluded capture references,
120 failed valid-source attempts, and 1,190 archived valid-source attempts.
Repeated attempts and references are not distinct source or body counts.
The independent JSON-LD-to-RDF check accepts the retrieval provenance, including
1,190 separately identified copy entities and 1,310 retrieval activities.

Runtime and audit code is pinned by this Git change. The observed local toolchain
uses Node 24.20.0; the repository CI pins Node 24.13.0. These are local validation
results and do not assert that hosted CI or a live graph server was run.
