import { expect, it } from "@effect/vitest"

import * as publicApi from "../src/index.js"
import { S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES } from "../src/s2s-evidence-profile.js"
import {
  S2S_STAGE_ARTIFACT_SPECS,
  s2sStageArtifactSpecForRole
} from "../src/s2s-stage-artifact-spec.js"
import {
  S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MAX_BYTES,
  S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MEMBER_NAME,
  S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES,
  S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MAX_BYTES,
  S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MEMBER_NAME,
  S2S_STAGE_UPLOAD_POSTCONDITION_REPRESENTATION,
  S2S_STAGE_UPLOAD_POSTCONDITION_SCHEMA_VERSION,
  S2S_STAGE_UPLOAD_POSTCONDITION_ZIP_FRAMING_BYTES,
  s2sStageUploadPostconditionObservationCount,
  s2sStageUploadPostconditionRawBodyMaximumBytes
} from "../src/s2s-stage-upload-postcondition-contract.js"

it("owns one exact internally derived stage artifact mapping", () => {
  expect(S2S_STAGE_ARTIFACT_SPECS).toEqual({
    REGISTER: {
      stage: "REGISTER",
      role: "REGISTRATION",
      jobId: "register",
      jobName: "register",
      artifactName: "s2s-registration",
      archiveLogicalName: "upload/registration_archive.zip",
      archiveProfileRole: "REGISTRATION_UPLOAD_ARCHIVE",
      postconditionLogicalName: "upload/registration_postcondition.zip",
      postconditionProfileRole: "REGISTRATION_UPLOAD_POSTCONDITION",
      carrierSchemaVersion: "hswm-swm0w-s2s-registration-carrier/v1",
      postconditionSchemaVersion:
        "hswm-swm0w-s2s-stage-upload-postcondition/v1",
      maximumArchiveBytes: 4 * 1_048_576,
      maximumExpandedBytes: 4 * 1_048_576,
      postconditionCarrierMaximumBytes: 12_583_176,
      postconditionProfileMaximumBytes: 16 * 1_048_576,
      expectedMembers: [
        { name: "control_receipt.json", maximumBytes: 1_048_576 }
      ]
    },
    CONFIRM: {
      stage: "CONFIRM",
      role: "CANDIDATE",
      jobId: "confirm",
      jobName: "confirm",
      artifactName: "s2s-candidate",
      archiveLogicalName: "upload/candidate_archive.zip",
      archiveProfileRole: "CANDIDATE_UPLOAD_ARCHIVE",
      postconditionLogicalName: "upload/candidate_postcondition.zip",
      postconditionProfileRole: "CANDIDATE_UPLOAD_POSTCONDITION",
      carrierSchemaVersion: "hswm-swm0w-s2s-candidate-carrier/v1",
      postconditionSchemaVersion:
        "hswm-swm0w-s2s-stage-upload-postcondition/v1",
      maximumArchiveBytes: 64 * 1_048_576,
      maximumExpandedBytes: 64 * 1_048_576,
      postconditionCarrierMaximumBytes: 12_583_176,
      postconditionProfileMaximumBytes: 16 * 1_048_576,
      expectedMembers: [
        { name: "control_receipt.json", maximumBytes: 1_048_576 },
        { name: "numeric_candidate.json", maximumBytes: 60 * 1_048_576 }
      ]
    },
    ADJUDICATE: {
      stage: "ADJUDICATE",
      role: "ADJUDICATION",
      jobId: "adjudicate",
      jobName: "adjudicate",
      artifactName: "s2s-adjudication",
      archiveLogicalName: "upload/adjudication_archive.zip",
      archiveProfileRole: "ADJUDICATION_UPLOAD_ARCHIVE",
      postconditionLogicalName: "upload/adjudication_postcondition.zip",
      postconditionProfileRole: "ADJUDICATION_UPLOAD_POSTCONDITION",
      carrierSchemaVersion: "hswm-swm0w-s2s-adjudication-carrier/v1",
      postconditionSchemaVersion:
        "hswm-swm0w-s2s-stage-upload-postcondition/v1",
      maximumArchiveBytes: 4 * 1_048_576,
      maximumExpandedBytes: 4 * 1_048_576,
      postconditionCarrierMaximumBytes: 12_583_176,
      postconditionProfileMaximumBytes: 16 * 1_048_576,
      expectedMembers: [
        { name: "control_receipt.json", maximumBytes: 1_048_576 },
        { name: "numeric_adjudication.json", maximumBytes: 3 * 1_048_576 }
      ]
    }
  })
  expect(s2sStageArtifactSpecForRole("REGISTRATION")).toBe(
    S2S_STAGE_ARTIFACT_SPECS.REGISTER
  )
  expect(s2sStageArtifactSpecForRole("CANDIDATE")).toBe(
    S2S_STAGE_ARTIFACT_SPECS.CONFIRM
  )
  expect(s2sStageArtifactSpecForRole("ADJUDICATION")).toBe(
    S2S_STAGE_ARTIFACT_SPECS.ADJUDICATE
  )
})

it("is deeply frozen and exactly agrees with the current profile descriptors", () => {
  expect(Object.isFrozen(S2S_STAGE_ARTIFACT_SPECS)).toBe(true)
  for (const stage of ["REGISTER", "CONFIRM", "ADJUDICATE"] as const) {
    const spec = S2S_STAGE_ARTIFACT_SPECS[stage]
    expect(Object.isFrozen(spec)).toBe(true)
    expect(Object.isFrozen(spec.expectedMembers)).toBe(true)
    expect(spec.expectedMembers.every(Object.isFrozen)).toBe(true)

    const profile = S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES[stage]
    const archive = profile.find(
      (entry) => entry.logicalName === spec.archiveLogicalName
    )
    const postcondition = profile.find(
      (entry) => entry.logicalName === spec.postconditionLogicalName
    )
    expect(archive).toEqual({
      logicalName: spec.archiveLogicalName,
      role: spec.archiveProfileRole,
      schemaVersion: spec.carrierSchemaVersion,
      mediaType: "application/zip",
      maximumBytes: spec.maximumArchiveBytes
    })
    expect(postcondition).toEqual({
      logicalName: spec.postconditionLogicalName,
      role: spec.postconditionProfileRole,
      schemaVersion: spec.postconditionSchemaVersion,
      mediaType: "application/zip",
      maximumBytes: spec.postconditionProfileMaximumBytes
    })
  }
})

it("freezes the postcondition representation and byte-budget skeleton", () => {
  expect(S2S_STAGE_UPLOAD_POSTCONDITION_SCHEMA_VERSION).toBe(
    "hswm-swm0w-s2s-stage-upload-postcondition/v1"
  )
  expect(S2S_STAGE_UPLOAD_POSTCONDITION_REPRESENTATION).toBe(
    "STORED_ZIP_COMPACT_MANIFEST_CONTIGUOUS_OBSERVATIONS_CURRENT_STAGE_ARCHIVE_REFERENCE"
  )
  expect(S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MEMBER_NAME).toBe(
    "manifest.json"
  )
  expect(S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MEMBER_NAME).toBe(
    "observations.bin"
  )
  expect(S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MAX_BYTES).toBe(1_048_576)
  expect(S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MAX_BYTES).toBe(
    11 * 1_048_576
  )
  expect(S2S_STAGE_UPLOAD_POSTCONDITION_ZIP_FRAMING_BYTES).toBe(264)
  expect(S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES).toBe(12_583_176)
  expect(
    [
      s2sStageUploadPostconditionObservationCount(1),
      s2sStageUploadPostconditionObservationCount(2),
      s2sStageUploadPostconditionObservationCount(3)
    ]
  ).toEqual([7, 9, 11])
  expect(s2sStageUploadPostconditionRawBodyMaximumBytes(3)).toBe(
    11 * 1_048_576
  )
  expect(S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES).toBeLessThan(
    S2S_STAGE_ARTIFACT_SPECS.REGISTER.postconditionProfileMaximumBytes
  )
  expect(
    S2S_STAGE_ARTIFACT_SPECS.REGISTER.postconditionCarrierMaximumBytes
  ).toBe(S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES)
})

it("keeps the production-intended specification and budget skeleton root-private", () => {
  for (const key of [
    "S2S_STAGE_ARTIFACT_SPECS",
    "s2sStageArtifactSpecForRole",
    "S2S_STAGE_UPLOAD_POSTCONDITION_SCHEMA_VERSION",
    "S2S_STAGE_UPLOAD_POSTCONDITION_REPRESENTATION",
    "S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES"
  ]) {
    expect(key in publicApi).toBe(false)
  }
})
