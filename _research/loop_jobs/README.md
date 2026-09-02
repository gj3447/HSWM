# Standard LE-0 research-job profiles

This directory contains future-launch sidecars for the HSWM GE-2/LE-0 standard.
They preserve the frozen DGX runner and verifier source files as historical
evidence; they do not alter, rerun, or upgrade a prior occurrence.

`HSWM_STANDARD_RESEARCH_JOB_PROFILES.v1.json` registers three role-separated,
one-shot profiles:

- `dgx-q1-live`: `_research.dgx_q1.live_experiment` followed by the unfrozen
  `hswm.experiments.dgx_q1_le0_verifier` bridge to the independent Q1 reader.
- `dgx-mi`: `_research.dgx_mi.experiment` followed by its existing independent
  verifier CLI.
- `dgx-mi2`: `_research.dgx_mi2.experiment` followed by its existing
  independent verifier CLI.

An operator supplies one strict JSON binding document containing the exact
absolute runtime paths, frozen closure/plan/source files, identities, and
control-journal root. Materialize it and feed it to the no-shell Node process:

```bash
uv run python -m hswm.experiments.graph_loop_job_profiles \
  --binding /absolute/job-binding.json \
  | hswm-graph-loop-job
```

The materializer fixes each profile's action/verifier modules and one-shot
budget. The job process content-addresses the schema, grants, and each declared
frozen input before it starts the action. It then records trigger, snapshot,
action, verifier, and stop or escalation in the LE-0 journal.

Verifier exit `0` means only that its protocol reader completed and emitted a
bounded verdict. Its stdout artifact, not the exit code, contains the protocol
terminal. A `VOID`/refusal exit is recorded as a rejected operational verdict;
neither is a scientific-success or graph-learning admission.

Remaining runners require a dedicated profile before a new scientific
occurrence. Do not use this directory to rewrite hash-bound protocol sources or
to retrofit a prior result.
