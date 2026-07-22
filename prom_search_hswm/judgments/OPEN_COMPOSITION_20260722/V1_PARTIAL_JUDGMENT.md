# Open HSWM composition v1 — partial judgment and supersession trigger

> tree: `LakatosTree_HSWM_SolidMultiAgent_20260722`  
> node: `ENG-open-composition-kernel-v1`  
> server verdict: `partial`  
> prediction receipt: `09237fc3d8645bf17b31cfd9ea108afa1e703c37d5885beb7106df0d8e7b931d`  
> verdict receipt: `78db21960d8e80d4123cd337bd3ad1cce940ebfdb4ed2be2aa7ed6bbb8d95a08`

## What v1 established

- preregistered deterministic fixture: 13/13 structural laws, 31/31 collected cases
- adjacent B2/hypergraph regression: 19/19
- server receipt fold: `ok=true`, rederived/cache both `partial`
- no retrieval-quality or scientific-progress claim

The registered `python` command failed before collection because this host has no `python`
alias. The environment-equivalent `python3` replay passed; both actions are recorded.

## Why v1 is not the final kernel

Independent post-judgment review produced three counterexamples not covered by its frozen
test contract.

1. **Local interface-name collision**: two valid operands may both expose a natural local
   port id such as `p`. v1 normalizes `InterfacePort` globally by that unqualified id, so
   their composition raises a conflict. This violates the intended arbitrary finite closure.
2. **Raw-constructor admission bypass**: `compose()` checks that a new connector addresses
   exposed operand ports, but direct public `OpenHSWM(...)` construction can install a
   connector over non-exposed public ports. Visibility alone is not an admission proof.
3. **Mutable snapshot drift**: a `Mount` retains a live legacy `Field` and only snapshots its
   digest. Mutating the field after mounting leaves `semantic_digest()` stale until explicit
   materialization checks the mismatch.

These are engineering falsifiers, not reasons to rewrite the v1 receipt. v1 remains an honest
`partial` historical result and is superseded for deployment by the v2 repair programme:

- mount-qualified default interface IDs;
- factory-sealed canonical `OpenHSWM` construction;
- immutable `FrozenFieldSnapshot`, with thawing only at explicit materialization.

Still-open scientific/agent gates remain unchanged: relation compatibility, cyclic bounded
readout, learned agent plasticity, and B2.1 interference control.

