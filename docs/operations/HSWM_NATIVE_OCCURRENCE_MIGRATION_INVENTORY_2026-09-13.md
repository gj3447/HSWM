# Native occurrence command migration — 2026-09-13

The twelve commands of `occurrence_cli.py` now have native TypeScript/Effect
implementations and emitted-process checks. The active native entrypoint is
`src/hswm/effect-runtime/bin/hswm-g0-occurrence`; build the pinned runtime before
using it. Command preparation and structural validation do not establish an
external audit, a completed occurrence, or HSWM efficacy.

| Commands | Native behavior | Evidence |
| --- | --- | --- |
| `describe`, `workflow-options`, `statement`, `parse-dsse` | Bounded local input and exact descriptor, launch-option and in-toto/DSSE projections | Full process output contracts and invalid input refusals |
| `external-handoff-template`, `external-handoff-validate` | Fixed candidate-file binding, canonical bytes, descriptor slots and structural validation | Canonical byte, duplicate key, stale pin and process checks; template preserves its no-newline wire form |
| `preflight` | Checks declared environment presence and bounded executable versions; missing qualification stays blocked with exit 3 | Source-bound preflight fixtures, malformed/missing/duplicate executable refusals, secret-free output |
| `osf-readback` | Validates supplied registration, file metadata and exact package readback bytes locally | Candidate/VOID exit codes, mismatch precedence, calendar/offset/microsecond timestamps and integer size checks |
| `worm-command`, `cosign-attest-command`, `rfc3161-query-command`, `rfc3161-verify-command` | Emits the original external command argument arrays | Exact arguments; absent inputs and existing or inaccessible output paths rejected |

The process tests compile current sources with the real strict build options
and run the emitted JavaScript from a foreign working directory. The fixed
candidate file is also packaged in `assets`; fallback is allowed only when the
checkout copy is absent. No command in this surface creates an OSF registration,
submits a WORM claim, signs an artifact, or executes the generated argument array.

`occurrence_completion.py`, `occurrence_integrity.py`, the dual evaluator,
workflow and publication replay have additional contracts beyond these twelve
commands. Their native migration has a separate completion criterion: exact
source-bound assessment digests, immutable one-shot history, fresh qualified
external verification and publication replay. Draft modules for those contracts
must not be used to assert that the whole occurrence path has migrated.

The Python source and checked-in research evidence remain available for
historical comparison. The command migration does not change any scientific
success criterion or promote a blocked external qualification.
