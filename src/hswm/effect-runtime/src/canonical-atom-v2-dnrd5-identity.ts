/**
 * Dependency-free DNRD-5 schema identity.
 *
 * Generic durable infrastructure imports this identity only to enforce that a
 * DNRD-5 journal cannot use the public raw submit surface.  Keeping the value
 * here avoids a dependency from the generic runtime to the DNRD-5 schema
 * validator and its domain machinery.
 */
export const DNRD5_SCHEMA_VERSION =
  "hswm:dnrd5:causal-macroplasticity:v1" as const
