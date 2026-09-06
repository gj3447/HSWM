# B2 text-lesson v2 — sealed initial-request measurement failure

The source-pinned B2 v2 occurrence reached and validated its first train
actor frame. Its first tokenizer request received HTTP 400 because the model
chat template rejected the two-system-message form: “System message must be at
the beginning.” No completion, environment action, terminal outcome,
reflection, lesson freeze, or evaluation followed.

This is `INCONCLUSIVE_MEASUREMENT_NOT_READY`: one issued tokenizer request had
unknown token usage, while completion count zero is observed (not generated).
It is a runtime prompt-serialization failure, not a negative result for the
lesson algorithm and supplies no performance estimate or B0/B2 comparison.

Artifacts: [selection](raw/hswm_expel_b2_text_lesson_v2_2026-09-06/selection.public.json), [public occurrence](raw/hswm_expel_b2_text_lesson_v2_2026-09-06/b2.public.json), and [evidence](../evidence/EVIDENCE_HSWM_EXPEL_B2_TEXT_LESSON_V2_2026-09-06.json).
