/**
 * One shared identity for the post-commit receipt of a DNRD-5 v2 main effect.
 *
 * The effect journal record descriptor already commits the exact canonical
 * command receipt, write envelopes, predecessor, and state digests.  The
 * remaining fields make the semantic effect tuple explicit.  Deriving this
 * identity does not prove that any referenced record exists or is durable.
 */
import { Either } from "effect"

import { canonicalJsonSha256, type CanonicalJsonError } from "./canonical-atom-v2-json.js"

export const DNRD5_V2_POSTCOMMIT_RECEIPT_IDENTITY_V1 =
  "hswm-dnrd5-v2-postcommit-receipt-identity/v1" as const

export interface Dnrd5V2PostcommitReceiptIdentityInput {
  readonly effectRecordDescriptorSha256: string
  readonly journalLineageId: string
  readonly transitionId: string
  readonly decisionAtomKeyId: string
  readonly effectConsumptionAtomKeyId: string
  readonly effectAtomKeyId: string
}

export const deriveDnrd5V2PostcommitReceiptIdentity = (
  input: Dnrd5V2PostcommitReceiptIdentityInput
): Either.Either<string, CanonicalJsonError> =>
  canonicalJsonSha256({
    contractVersion: DNRD5_V2_POSTCOMMIT_RECEIPT_IDENTITY_V1,
    effectRecordDescriptorSha256: input.effectRecordDescriptorSha256,
    journalLineageId: input.journalLineageId,
    transitionId: input.transitionId,
    decisionAtomKeyId: input.decisionAtomKeyId,
    effectConsumptionAtomKeyId: input.effectConsumptionAtomKeyId,
    effectAtomKeyId: input.effectAtomKeyId
  })
