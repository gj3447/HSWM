# LLM function cells

A cell is a logical semantic function with a role, typed ports, local state,
position, and authority. One foundation model may execute many cells; a cell is
not required to own a separate checkpoint.

The cell network is described in the
[architecture note](../../HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md)
and exercised by the canonical [`hswm.cells`](../../src/hswm/cells/) package.
The old flat imports remain compatibility packages, while exact root-era source
is recovered only through the source-pinned legacy replay path.
