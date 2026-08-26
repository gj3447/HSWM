import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"

import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  decodeHSWMCoreResponsibilityOntology,
  decodeHSWMCoreResponsibilityOntologyBytes,
  type HSWMCoreOntologyErrorCode
} from "../src/hswm-core-ontology.js"
import type { HSWMCoreResponsibilityOntology } from "../src/hswm-core-ontology-schema.js"

const validateHSWMCoreResponsibilityOntology =
  decodeHSWMCoreResponsibilityOntology

const ONTOLOGY_URL = new URL(
  "../../../../ontology/identity/hswm_core/HSWM_CORE_RESPONSIBILITY_ONTOLOGY.v1.json",
  import.meta.url
)

const parseOntology = (): HSWMCoreResponsibilityOntology => {
  const bytes = new Uint8Array(readFileSync(ONTOLOGY_URL))
  const decoded = decodeHSWMCoreResponsibilityOntologyBytes(bytes)
  if (Either.isLeft(decoded)) {
    throw new Error(`${decoded.left.code}: ${decoded.left.detail}`)
  }
  return decoded.right
}

const expectFailure = (
  result: ReturnType<typeof decodeHSWMCoreResponsibilityOntology>,
  code: HSWMCoreOntologyErrorCode
): void => {
  if (Either.isRight(result)) throw new Error(`expected ${code}`)
  expect(result.left.code).toBe(code)
}

const expectSemanticFailure = (
  result: ReturnType<typeof validateHSWMCoreResponsibilityOntology>,
  code: HSWMCoreOntologyErrorCode
): void => {
  if (Either.isRight(result)) throw new Error(`expected ${code}`)
  expect(result.left.code).toBe(code)
}

const firstPrimitive = (ontology: HSWMCoreResponsibilityOntology) => {
  const first = ontology.primitive_kinds[0]
  if (first === undefined) throw new Error("ontology has no primitive kinds")
  return first
}

const firstProjection = (ontology: HSWMCoreResponsibilityOntology) => {
  const first = ontology.projection_classes[0]
  if (first === undefined) throw new Error("ontology has no projections")
  return first
}

const firstRelation = (ontology: HSWMCoreResponsibilityOntology) => {
  const first = ontology.relations[0]
  if (first === undefined) throw new Error("ontology has no relations")
  return first
}

const firstTransition = (ontology: HSWMCoreResponsibilityOntology) => {
  const first = ontology.transition_families[0]
  if (first === undefined) throw new Error("ontology has no transitions")
  return first
}

it("decodes the checked-in ontology through the strict Effect v3 boundary", () => {
  const ontology = parseOntology()
  expect(ontology.schema_version).toBe(
    "hswm-core-responsibility-ontology/v1"
  )
  expect(ontology.scientific_status).toBe("UNJUDGED")
  expect(ontology.roles.map((role) => role.symbol)).toEqual([
    "H",
    "W",
    "A",
    "F",
    "Pi"
  ])
})

it("returns a recursively immutable validated ontology snapshot", () => {
  const ontology = parseOntology()
  const hRole = ontology.roles[0]
  const transition = ontology.transition_families[0]
  if (hRole === undefined || transition === undefined) {
    throw new Error("ontology nested records are absent")
  }
  expect(Object.isFrozen(ontology)).toBe(true)
  expect(Object.isFrozen(ontology.roles)).toBe(true)
  expect(Object.isFrozen(hRole)).toBe(true)
  expect(Object.isFrozen(hRole.owns)).toBe(true)
  expect(Object.isFrozen(transition.write_contracts)).toBe(true)
  expect(Object.isFrozen(transition.write_contracts[0])).toBe(true)
  expect(Reflect.set(hRole, "canonical_meaning", "permission is H")).toBe(
    false
  )
})

it("binds every declared canonical source to its exact checked-in bytes", () => {
  const ontology = parseOntology()
  for (const source of ontology.source_bindings) {
    const sourceUrl = new URL(`../../../../${source.path}`, import.meta.url)
    const digest = createHash("sha256")
      .update(readFileSync(sourceUrl))
      .digest("hex")
    expect(digest).toBe(source.sha256)
  }
})

it("keeps primitive ownership total, exclusive, and populated for all roles", () => {
  const ontology = parseOntology()
  const ownerCounts = new Map<string, number>(
    ontology.roles.map((role): readonly [string, number] => [role.uid, 0])
  )
  for (const kind of ontology.primitive_kinds) {
    expect(ownerCounts.has(kind.owner_role_uid)).toBe(true)
    ownerCounts.set(
      kind.owner_role_uid,
      (ownerCounts.get(kind.owner_role_uid) ?? 0) + 1
    )
  }
  expect([...ownerCounts.values()].every((count) => count > 0)).toBe(true)
})

it("rejects excess fields before semantic validation", () => {
  const ontology = parseOntology()
  expectFailure(
    decodeHSWMCoreResponsibilityOntology({
      ...ontology,
      implicit_cognitive_router: true
    }),
    "SCHEMA_INVALID"
  )
})

it("binds meaning-bearing prose to the complete canonical v1 content", () => {
  const ontology = parseOntology()
  const hRole = ontology.roles[0]
  const firstInvariant = ontology.invariants[0]
  if (hRole === undefined || firstInvariant === undefined) {
    throw new Error("ontology semantic records are absent")
  }

  expectFailure(
    decodeHSWMCoreResponsibilityOntology({
      ...ontology,
      roles: [
        {
          ...hRole,
          owns: ["learned causal efficacy", "effective permission"],
          must_not_own: ["stable identity"]
        },
        ...ontology.roles.slice(1)
      ]
    }),
    "CONTENT_DIGEST_INVALID"
  )
  expectFailure(
    decodeHSWMCoreResponsibilityOntology({
      ...ontology,
      invariants: [
        {
          ...firstInvariant,
          statement: "No admitted atom needs an owner.",
          validation: "Accept missing ownership."
        },
        ...ontology.invariants.slice(1)
      ]
    }),
    "CONTENT_DIGEST_INVALID"
  )
})

it("rejects duplicate JSON keys before Effect Schema can observe last-write-wins data", () => {
  const source = readFileSync(ONTOLOGY_URL, "utf8")
  const marker = '"scientific_status": "UNJUDGED",'
  if (!source.includes(marker)) throw new Error("scientific status marker is absent")
  const duplicated = source.replace(marker, `${marker}\n  ${marker}`)
  const result = decodeHSWMCoreResponsibilityOntologyBytes(
    new TextEncoder().encode(duplicated)
  )
  expectFailure(result, "JSON_INVALID")
})

it("rejects an unknown owner instead of defaulting the primitive to H", () => {
  const ontology = parseOntology()
  const first = firstPrimitive(ontology)
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    primitive_kinds: [
      { ...first, owner_role_uid: "hswm:role:Unknown" },
      ...ontology.primitive_kinds.slice(1)
    ]
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "OWNER_INVALID"
  )
})

it("rejects a new same-owner kind inside the closed v1 registry", () => {
  const ontology = parseOntology()
  const first = firstPrimitive(ontology)
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    primitive_kinds: [
      ...ontology.primitive_kinds,
      {
        ...first,
        uid: "hswm:kind:H:permission-shortcut",
        name: "PermissionShortcut"
      }
    ]
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "OWNER_INVALID"
  )
})

it("rejects duplicate primitive identity", () => {
  const ontology = parseOntology()
  const first = firstPrimitive(ontology)
  const second = ontology.primitive_kinds[1]
  if (second === undefined) throw new Error("ontology has fewer than two kinds")
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    primitive_kinds: [
      first,
      { ...second, uid: first.uid },
      ...ontology.primitive_kinds.slice(2)
    ]
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "UID_DUPLICATE"
  )
})

it("rejects role collapse or a sixth responsibility coordinate", () => {
  const ontology = parseOntology()
  const wRole = ontology.roles[1]
  if (wRole === undefined) throw new Error("W role is absent")
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    roles: [
      ontology.roles[0] ?? wRole,
      { ...wRole, symbol: "H" },
      ...ontology.roles.slice(2)
    ]
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "ROLE_SET_INVALID"
  )
})

it("rejects relations with unknown endpoints", () => {
  const ontology = parseOntology()
  const first = firstRelation(ontology)
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    relations: [
      { ...first, to_uid: "hswm:kind:H:missing" },
      ...ontology.relations.slice(1)
    ]
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "RELATION_ENDPOINT_INVALID"
  )
})

it("rejects deletion or extension of the closed v1 relation set", () => {
  const ontology = parseOntology()
  const withoutFirst: HSWMCoreResponsibilityOntology = {
    ...ontology,
    relations: ontology.relations.slice(1)
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(withoutFirst),
    "RELATION_SET_INVALID"
  )

  const withExtra: HSWMCoreResponsibilityOntology = {
    ...ontology,
    relations: [
      ...ontology.relations,
      {
        from_uid: ontology.root_uid,
        type: "COMPILES_TO",
        to_uid: "hswm:projection:repository-ontology"
      }
    ]
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(withExtra),
    "RELATION_SET_INVALID"
  )
})

it("rejects global UID collision across ontology node collections", () => {
  const ontology = parseOntology()
  const first = firstProjection(ontology)
  const transition = firstTransition(ontology)
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    projection_classes: [
      { ...first, uid: transition.uid },
      ...ontology.projection_classes.slice(1)
    ]
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "UID_DUPLICATE"
  )
})

it("rejects projection commit-back even for a lossless projection", () => {
  const ontology = parseOntology()
  const first = firstProjection(ontology)
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    projection_classes: [
      { ...first, direct_commit_back_allowed: true },
      ...ontology.projection_classes.slice(1)
    ]
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "PROJECTION_INVALID"
  )
})

it("rejects a fidelity downgrade hidden behind an unchanged projection UID", () => {
  const ontology = parseOntology()
  const first = firstProjection(ontology)
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    projection_classes: [
      { ...first, fidelity: "LOSSY_DECLARED" },
      ...ontology.projection_classes.slice(1)
    ]
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "PROJECTION_INVALID"
  )
})

it("rejects non-Pi transition authority", () => {
  const ontology = parseOntology()
  const first = firstTransition(ontology)
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    transition_families: [
      { ...first, authority_role_uid: "hswm:role:W" },
      ...ontology.transition_families.slice(1)
    ]
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "TRANSITION_INVALID"
  )
})

it("keeps outcome-bound learning conditional on a recorded outcome", () => {
  const ontology = parseOntology()
  const learningIndex = ontology.transition_families.findIndex(
    (transition) => transition.uid === "hswm:transition:outcome-bound-learning"
  )
  const learning = ontology.transition_families[learningIndex]
  if (learningIndex < 0 || learning === undefined) {
    throw new Error("outcome-bound learning transition is absent")
  }
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    transition_families: ontology.transition_families.map(
      (transition, index) =>
        index === learningIndex
          ? { ...learning, outcome_required: false }
          : transition
    )
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "TRANSITION_INVALID"
  )
})

it("covers every primitive kind through a kind/effect lifecycle contract", () => {
  const ontology = parseOntology()
  const ownerByKind = new Map(
    ontology.primitive_kinds.map((kind) => [kind.uid, kind.owner_role_uid])
  )
  const covered = new Set(
    ontology.transition_families.flatMap((transition) =>
      transition.write_contracts.map((contract) => contract.target_kind_uid)
    )
  )
  expect([...ownerByKind.keys()].every((kindUid) => covered.has(kindUid))).toBe(
    true
  )
  for (const transition of ontology.transition_families) {
    const owners = new Set(
      transition.write_contracts.map((contract) =>
        ownerByKind.get(contract.target_kind_uid)
      )
    )
    expect(
      ontology.roles
        .map((role) => role.uid)
        .filter((roleUid) => owners.has(roleUid))
    ).toEqual(transition.writes_role_uids)
  }
})

it("separates F, operational Pi, Pi-star, learning-A, and rollback lifecycles", () => {
  const ontology = parseOntology()
  const byUid = new Map(
    ontology.transition_families.map((transition) => [
      transition.uid,
      transition
    ])
  )
  const learning = byUid.get("hswm:transition:outcome-bound-learning")
  const functionLifecycle = byUid.get(
    "hswm:transition:function-cell-lifecycle"
  )
  const policyLifecycle = byUid.get(
    "hswm:transition:operational-policy-lifecycle"
  )
  const amendment = byUid.get("hswm:transition:constitutional-amendment")
  const rollback = byUid.get("hswm:transition:rollback")
  if (
    learning === undefined ||
    functionLifecycle === undefined ||
    policyLifecycle === undefined ||
    amendment === undefined ||
    rollback === undefined
  ) {
    throw new Error("required lifecycle transition is absent")
  }
  expect(
    learning.write_contracts.filter((contract) =>
      contract.target_kind_uid.startsWith("hswm:kind:A:")
    )
  ).toEqual([
    {
      target_kind_uid: "hswm:kind:A:eligibility-seal",
      effect: "CONSUME_AND_CLOSE"
    }
  ])
  expect(
    functionLifecycle.write_contracts.some((contract) =>
      contract.target_kind_uid.startsWith("hswm:kind:F:")
    )
  ).toBe(true)
  expect(
    policyLifecycle.write_contracts.some(
      (contract) =>
        contract.target_kind_uid ===
        "hswm:kind:Pi:constitutional-boundary"
    )
  ).toBe(false)
  expect(amendment.ratification_required).toBe(true)
  expect(
    amendment.write_contracts.find((contract) =>
      contract.target_kind_uid === "hswm:kind:Pi:constitutional-boundary"
    )?.effect
  ).toBe("AMEND_BY_EXPLICIT_RATIFICATION")
  expect(rollback.reads_role_uids).not.toContain("hswm:role:A")
  expect(rollback.writes_role_uids).not.toContain("hswm:role:A")
  expect(rollback.writes_role_uids).not.toContain("hswm:role:Pi")
})

it("rejects ordinary learning that writes Pi or F", () => {
  const ontology = parseOntology()
  const learningIndex = ontology.transition_families.findIndex(
    (transition) => transition.uid === "hswm:transition:outcome-bound-learning"
  )
  const learning = ontology.transition_families[learningIndex]
  if (learningIndex < 0 || learning === undefined) {
    throw new Error("outcome-bound learning transition is absent")
  }
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    transition_families: ontology.transition_families.map(
      (transition, index) =>
        index === learningIndex
          ? {
              ...learning,
              writes_role_uids: [
                ...learning.writes_role_uids,
                "hswm:role:Pi"
              ],
              write_contracts: [
                ...learning.write_contracts,
                {
                  target_kind_uid: "hswm:kind:Pi:constitutional-boundary",
                  effect: "AMEND_BY_EXPLICIT_RATIFICATION"
                }
              ]
            }
          : transition
    )
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "TRANSITION_INVALID"
  )
})

it("rejects post-outcome eligibility rewrite instead of one-way seal consumption", () => {
  const ontology = parseOntology()
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    transition_families: ontology.transition_families.map((transition) =>
      transition.uid === "hswm:transition:outcome-bound-learning"
        ? {
            ...transition,
            write_contracts: transition.write_contracts.map((contract) =>
              contract.target_kind_uid === "hswm:kind:A:eligibility-seal"
                ? {
                    ...contract,
                    effect: "CREATE_OR_ADVANCE_EPISODE_LOCAL" as const
                  }
                : contract
            )
          }
        : transition
    )
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "TRANSITION_INVALID"
  )
})

it("rejects rollback that attempts to revive historical A", () => {
  const ontology = parseOntology()
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    transition_families: ontology.transition_families.map((transition) =>
      transition.uid === "hswm:transition:rollback"
        ? {
            ...transition,
            reads_role_uids: [
              ...transition.reads_role_uids,
              "hswm:role:A"
            ],
            writes_role_uids: [
              ...transition.writes_role_uids,
              "hswm:role:A"
            ],
            write_contracts: [
              ...transition.write_contracts,
              {
                target_kind_uid: "hswm:kind:A:activation-packet",
                effect: "RESTORE_AS_NEW_VERSION" as const
              }
            ]
          }
        : transition
    )
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "TRANSITION_INVALID"
  )
})

it("rejects deletion of a required cross-role seam", () => {
  const ontology = parseOntology()
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    seam_contracts: ontology.seam_contracts.filter(
      (seam) => seam.uid !== "hswm:seam:W-F"
    )
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "SEAM_INVALID"
  )
})

it("rejects invariant registry drift instead of accepting familiar code fragments", () => {
  const ontology = parseOntology()
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    invariants: ontology.invariants.slice(0, -1)
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "INVARIANT_SET_INVALID"
  )
})

it("keeps the v1 source paths, bytes, authority, and scope closed", () => {
  const ontology = parseOntology()
  const first = ontology.source_bindings[0]
  if (first === undefined) throw new Error("ontology has no source binding")
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    source_bindings: [
      { ...first, authority_class: "USER_PRIMARY" },
      ...ontology.source_bindings.slice(1)
    ]
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "SOURCE_BINDING_INVALID"
  )
})

it("keeps stable root identity and the nonclaim boundary closed", () => {
  const ontology = parseOntology()
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology({
      ...ontology,
      root_uid: "hswm:concept:renamed-core-state"
    }),
    "NORMAL_FORM_INVALID"
  )
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology({
      ...ontology,
      nonclaims: ontology.nonclaims.slice(1)
    }),
    "NORMAL_FORM_INVALID"
  )
})

it("rejects KG projection policy drift", () => {
  const ontology = parseOntology()
  const mutated: HSWMCoreResponsibilityOntology = {
    ...ontology,
    kg_projection_policy: {
      ...ontology.kg_projection_policy,
      node_collections: ontology.kg_projection_policy.node_collections.slice(1)
    }
  }
  expectSemanticFailure(
    validateHSWMCoreResponsibilityOntology(mutated),
    "PROJECTION_INVALID"
  )
})

it("resolves every external anchor without overlaying the source bundle", () => {
  const ontology = parseOntology()
  const anchorBundleUrl = new URL(
    "../../../../ontology/identity/human_universal_body/HSWM_HUMAN_UNIVERSAL_BODY_ONTOLOGY.v1.json",
    import.meta.url
  )
  const bundle: unknown = JSON.parse(readFileSync(anchorBundleUrl, "utf8"))
  if (typeof bundle !== "object" || bundle === null || !("nodes" in bundle)) {
    throw new Error("external anchor bundle has no nodes")
  }
  const nodes = bundle.nodes
  if (!Array.isArray(nodes)) throw new Error("external anchor nodes are invalid")
  const knownAnchors = new Map(
    nodes.flatMap((node) => {
      if (
        typeof node === "object" &&
        node !== null &&
        "uid" in node &&
        typeof node.uid === "string" &&
        "properties" in node &&
        typeof node.properties === "object" &&
        node.properties !== null &&
        "authority_class" in node.properties &&
        typeof node.properties.authority_class === "string" &&
        "canonical_scope" in node.properties &&
        typeof node.properties.canonical_scope === "string"
      ) {
        return [[
          node.uid,
          {
            authorityClass: node.properties.authority_class,
            canonicalScope: node.properties.canonical_scope
          }
        ] as const]
      }
      return []
    })
  )
  for (const anchor of ontology.external_anchors) {
    const resolved = knownAnchors.get(anchor.uid)
    expect(resolved).toBeDefined()
    expect(resolved?.authorityClass).toBe(anchor.expected_authority_class)
    expect(resolved?.canonicalScope).toBe(anchor.expected_canonical_scope)
    const sourceDigest = createHash("sha256")
      .update(readFileSync(anchorBundleUrl))
      .digest("hex")
    expect(sourceDigest).toBe(anchor.source_bundle_sha256)
  }
})

it("keeps the ontology local, non-cognitive, and non-authorizing", () => {
  const ontology = parseOntology()
  expect(ontology.kg_projection_policy.remote_publication).toBe(
    "NOT_AUTHORIZED"
  )
  expect(
    ontology.projection_classes.every(
      (projection) => !projection.direct_commit_back_allowed
    )
  ).toBe(true)
  expect(ontology.nonclaims).toContain(
    "This ontology is not the HSWM runtime graph or cognitive state."
  )
  expect(ontology.nonclaims).toContain(
    "No current checked-in evidence establishes integrated L1 HSWM causal macro-learning."
  )
})
