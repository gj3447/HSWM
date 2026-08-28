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

/**
 * The durable raw-submit surface is closed for the DNRD-5 experiment family.
 *
 * This is intentionally a family prefix, rather than an enumeration of
 * successor identities: a new DNRD-5 schema cannot silently reopen the raw
 * path merely because generic durable infrastructure has not imported it.
 */
export const DNRD5_PERMIT_DISPATCH_SCHEMA_VERSION_PREFIX =
  "hswm:dnrd5:causal-macroplasticity:" as const
