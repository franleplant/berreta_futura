import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { parse } from "yaml";

import type { RevisionId } from "../contracts/index.ts";
import {
  buildLegacyMigrationAttestation,
  serializeLegacyMigrationAttestation,
  verifyLegacyMigrationAttestation,
  verifyManifestSourceCommitProofs,
  verifyLegacySourceBlobDigests,
} from "../migration/legacy-migration-attestation.ts";
import type { LegacyRootMigrationPlan } from "../migration/legacy-root-migration.ts";

const SOURCE_COMMIT = "5097aab2154be41b9315adfc1bf737898217be73";
const TARGET_COMMIT = "423030b15a96fc1355591c5ced19f41a987035bd";
const PLAN_REVISION = "rev_20260803T054439271Z_bg2bfnprnbd4" as RevisionId;
const PLAN_PATH = `inputs/migrations/legacy-four-root/revisions/${PLAN_REVISION}/inventory.yaml`;
const planPromise = readFile(PLAN_PATH, "utf8").then((value) => parse(value) as LegacyRootMigrationPlan);
const attestationPromise = buildLegacyMigrationAttestation(
  process.cwd(),
  SOURCE_COMMIT,
  PLAN_REVISION,
  TARGET_COMMIT,
);

test("legacy cutover attestation binds every source row and preserves Edition 4 image blobs", async () => {
  const [plan, attestation] = await Promise.all([planPromise, attestationPromise]);

  verifyLegacyMigrationAttestation(attestation, plan);
  assert.equal(attestation.targetSnapshotCommitOid, TARGET_COMMIT);
  assert.equal(attestation.sourceRows.length, 933);
  assert.equal(attestation.summary.sourceBytes, 525_474_841);
  assert.deepEqual(attestation.summary.dispositions, {
    import_exact: 212,
    reuse_existing: 683,
    archive_non_authoritative: 38,
    retire_housekeeping: 0,
  });
  assert.equal(attestation.generatedFiles.length, 15);
  assert.equal(attestation.historicalCompositions.length, 4);
  assert.equal(attestation.preExistingEdition4ImageFiles.length, 26);
  assert.equal(attestation.sourceRows.every((row) =>
    row.source.gitBlobOid === row.target.payload.gitBlobOid &&
    row.source.sha256 === row.target.payload.sha256 &&
    row.source.sizeBytes === row.target.payload.sizeBytes
  ), true);
  assert.equal(attestation.sourceRows.filter((row) =>
    row.target.payloadPathResolution === "committed_reuse_binding"
  ).length, 108);
  assert.equal(attestation.preExistingEdition4ImageFiles.every((entry) =>
    entry.source.gitBlobOid === entry.target.gitBlobOid && entry.source.sha256 === entry.target.sha256
  ), true);
  assert.equal(attestation.cutover.releaseAuthorityImported, false);
  assert.equal(attestation.cutover.freshRunEngineReviewStillRequired, true);
});

test("legacy cutover attestation serializes without YAML alias ordering", async () => {
  const [plan, attestation] = await Promise.all([planPromise, attestationPromise]);
  const payload = serializeLegacyMigrationAttestation(attestation);
  const decoded = parse(payload.toString("utf8"));
  verifyLegacyMigrationAttestation(decoded, plan);
  assert.doesNotMatch(payload.toString("utf8"), /(?:^|\s)[&*]a\d+(?:\s|$)/u);
});

test("legacy cutover attestation verifier rejects a target digest mismatch", async () => {
  const [plan, attestation] = await Promise.all([planPromise, attestationPromise]);
  const first = attestation.sourceRows[0]!;
  const tampered = {
    ...attestation,
    sourceRows: [{
      ...first,
      target: {
        ...first.target,
        payload: { ...first.target.payload, sha256: `sha256:${"0".repeat(64)}` },
      },
    }, ...attestation.sourceRows.slice(1)],
  };
  assert.throws(
    () => verifyLegacyMigrationAttestation(tampered, plan),
    /attestation row differs from its plan/u,
  );
});

test("legacy cutover attestation rejects a tampered protected-blob SHA", async () => {
  const [plan, attestation] = await Promise.all([planPromise, attestationPromise]);
  const first = plan.sourceSnapshot.files[0]!;
  const tampered = {
    ...plan,
    sourceSnapshot: {
      ...plan.sourceSnapshot,
      files: [{ ...first, sha256: `sha256:${"0".repeat(64)}` }, ...plan.sourceSnapshot.files.slice(1)],
    },
  };
  const actualDigests = new Map(attestation.sourceRows.map((row) => [row.source.gitBlobOid, {
    sha256: row.source.sha256,
    sizeBytes: row.source.sizeBytes,
  }] as const));
  assert.throws(
    () => verifyLegacySourceBlobDigests(tampered, actualDigests),
    /protected source blob digest differs from migration plan/u,
  );
});

test("legacy cutover attestation rejects the wrong manifest source commit", async () => {
  const [plan, attestation] = await Promise.all([planPromise, attestationPromise]);
  const index = attestation.sourceRows.findIndex((row) => row.disposition === "import_exact");
  assert.notEqual(index, -1);
  const row = attestation.sourceRows[index]!;
  const tampered = {
    ...attestation,
    sourceRows: [
      ...attestation.sourceRows.slice(0, index),
      {
        ...row,
        target: {
          ...row.target,
          manifestSourceBinding: {
            ...row.target.manifestSourceBinding,
            gitCommitOid: "0".repeat(40),
          },
        },
      },
      ...attestation.sourceRows.slice(index + 1),
    ],
  };
  assert.throws(
    () => verifyLegacyMigrationAttestation(tampered, plan),
    /manifest source proof is invalid/u,
  );
});

test("legacy cutover attestation resolves a reuse manifest source commit through Git", async () => {
  const attestation = await attestationPromise;
  const index = attestation.sourceRows.findIndex((row) => row.disposition === "reuse_existing");
  assert.notEqual(index, -1);
  const row = attestation.sourceRows[index]!;
  const nonexistentCommit = "0".repeat(40);
  const tamperedRows = [
    ...attestation.sourceRows.slice(0, index),
    {
      ...row,
      target: {
        ...row.target,
        manifestSourceBinding: {
          ...row.target.manifestSourceBinding,
          gitCommitOid: nonexistentCommit,
        },
        manifestSourceCommitProof: {
          ...row.target.manifestSourceCommitProof,
          gitCommitOid: nonexistentCommit,
        },
      },
    },
    ...attestation.sourceRows.slice(index + 1),
  ];
  await assert.rejects(
    verifyManifestSourceCommitProofs(process.cwd(), tamperedRows, SOURCE_COMMIT),
    /manifest source commit is not recoverable/u,
  );
});
