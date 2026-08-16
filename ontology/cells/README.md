# LLM function cells

A cell is a logical semantic function with a role, typed ports, local state,
position, and authority. One foundation model may execute many cells; a cell is
not required to own a separate checkpoint.

The cell network is described in the
[architecture note](../../docs/canon/HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md)
and exercised by the canonical [`hswm.cells`](../../src/hswm/cells/) package.
The old flat imports are installed from the source-pinned
[`_research/root_compat/`](../../_research/root_compat/) cluster. New code must
use `hswm.cells`; exact root-era paths are recovered only through the detached,
source-pinned legacy replay path.
