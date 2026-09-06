# B2 external text-lesson comparator — frozen prospective v3

[Protocol v3](protocol.v3.json), SHA-256
`49c73264dfce59c3db56f4013ad91dacc66988d4bfdcdeb2ec37af7d278027ee`, freezes a new occurrence and deterministic selection before
its own task, model request, or outcome.

The [v2 result](../../../../results/HSWM_EXPEL_B2_TEXT_LESSON_V2_RESULTS_2026-09-06.md)
is `INCONCLUSIVE_MEASUREMENT_NOT_READY`: ALFworld delivered a valid initial
actor frame, but the first tokenize POST returned HTTP 400 because the pinned
Qwen chat template rejects a second system message. There were no completion
requests, actions, reflections, or completed episodes. V2 is consumed and its
protocol, private prefix, public receipt, and wrapper archive remain intact.

V3 concatenates the identical action instructions, two newline separator,
and lesson wrapper into one leading system message followed by the user
observation. The pinned snapshot chat-template SHA-256 is
`e84f32a23fdda27689f868aa4a1a5621f41133e51a48d7f3efcbea2839574259`.
This changes message serialization; it introduces no new lesson algorithm,
model, runtime, task selection criterion, success criterion, or claim ceiling.
The protocol binds the amended source bytes and both earlier protocols.

The same 8 train + 4 descriptive `valid_seen` groups, 20-action horizon,
240 action + 8 reflection POST caps per phase, successful-terminal-only
reflection, evaluation freeze, no retry/refill rule, and final host attestation
remain mandatory. Failed or incomplete prefixes never become success rates.
A fresh B0 successor is separately registered; any comparison is descriptive
and unpaired, with action and reflection costs reported separately.

Run the selection and live entrypoints through `hswm-run` with the correct
locator-relative asset root, fresh output/cache/service roots, and a clean
committed source tree. No v1 or v2 occurrence is retried or resumed. This
external text-state comparator is not direct ExpeL, canonical HSWM admission,
independent custody, G0 passage, G1 evaluation, or efficacy evidence.
