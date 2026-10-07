# W1 full-instrument progress view

This immutable view adds a source-bound qualification of the 2,784-request W1
instrument. It records zero measured model requests. It does not establish model
binding, learning, efficacy, or a whole-HSWM proof. T1–T4 and T6–T9 inherit their
exact selected observations from the retained runtime-conformance view; T5 order 2
remains open with `work_ready: false`.

The generator refuses working-tree bytes that differ from its supplied 40-hex git
revision. `graph-validation.v1.json` is intentionally not a bound input, avoiding
a self-referential publication cycle.
