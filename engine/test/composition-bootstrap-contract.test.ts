import assert from "node:assert/strict";
import test from "node:test";

import type { ArtifactId, JsonObject, KnownWorkRole } from "../contracts/index.ts";
import { KNOWN_WORK_ROLES } from "../contracts/index.ts";
import { validateWorkResult } from "../run-engine/work-result-contracts.ts";

const artifactId = (value: string) => value as ArtifactId;
const REVISION = "rev_20260802T200641636Z_aaaaaaaaaaaa";

test("composition bootstrap contract requires exact immutable evidence and an exhaustive role map", () => {
  const result = {
    bootstrapRevision: {
      kind: "run_bootstrap",
      editionId: "004",
      logicalId: "fresh-v2",
      revisionId: REVISION,
    },
    compositionRevision: {
      revisionRef: {
        kind: "composition",
        editionId: "004",
        compositionId: "fresh-v2",
        revisionId: REVISION,
      },
      manifestDigest: `sha256:${"c".repeat(64)}`,
      gitCommitOid: "a".repeat(40),
      gitBlobOids: { "durable/editions/004/compositions/fresh-v2/revisions/x/manifest.yaml": "b".repeat(40) },
    },
    configuredLanguages: ["en", "es"],
    selectedImageRevisionRefs: [{
      kind: "image",
      editionId: "004",
      logicalId: "cover",
      revisionId: REVISION,
    }],
    imageGenerationAllowed: false,
    rendererContractVersion: "magazine-renderer/1",
    promptSet: {
      id: "fresh-v2-prompt-set",
      roleInputs: roleInputs(),
    },
  } as JsonObject;
  const evidence = {
    id: artifactId("art-composition-bootstrap-evidence"),
    kind: "composition_bootstrap_evidence",
    schemaVersion: "composition-bootstrap/1",
    mediaType: "application/json",
    payload: { kind: "json" as const, value: result },
  };

  assert.doesNotThrow(() =>
    validateWorkResult("composition_bootstrap", "composition-bootstrap/1", result, [evidence]),
  );
  assert.throws(
    () => validateWorkResult("composition_bootstrap", "composition-bootstrap/1", result, []),
    { code: "ANSWER_ARTIFACTS_INVALID" },
  );
  assert.throws(
    () => validateWorkResult("composition_bootstrap", "composition-bootstrap/1", {
      ...result,
      promptSet: {
        ...result.promptSet as JsonObject,
        roleInputs: { ...roleInputs(), writer: { kind: "human", authority: "human" } },
      },
    }, [evidence]),
    { code: "ANSWER_RESULT_INVALID" },
  );
});

function roleInputs(): Record<KnownWorkRole, JsonObject> {
  return Object.fromEntries(KNOWN_WORK_ROLES.map((role) => [role, roleInput(role)])) as
    Record<KnownWorkRole, JsonObject>;
}

function roleInput(role: KnownWorkRole): JsonObject {
  const contracts: Partial<Record<KnownWorkRole, string>> = {
    measure_edition: "measure-edition/1",
    render: "render-edition/1",
    render_inspection: "render-inspection/1",
    composition_bootstrap: "composition-bootstrap/1",
  };
  if (contracts[role] !== undefined) {
    return { kind: "contract", contractVersion: contracts[role]! };
  }
  if (role === "visual_review") {
    return {
      kind: "human",
      authority: "human",
      policyRevision: { kind: "policy", policyId: "render-review", revisionId: REVISION },
    };
  }
  const reasons: Partial<Record<KnownWorkRole, string>> = {
    capture_source: "bootstrap_committed_inputs",
    extract_source: "bootstrap_committed_inputs",
    review_source: "bootstrap_committed_inputs",
    writer: "bootstrap_existing_manuscripts",
    editorial_writer: "bootstrap_existing_manuscripts",
    translation_writer: "bootstrap_existing_translations",
    language_review: "bootstrap_existing_translations",
    language_fit: "bootstrap_existing_translations",
    cover_image: "bootstrap_existing_images",
    interior_image: "bootstrap_existing_images",
    select_art: "bootstrap_existing_images",
    render_reconciliation: "bootstrap_forces_fresh_render",
    release_approval: "stop_unreleased",
  };
  return {
    kind: "disabled",
    reason: reasons[role] ?? "bootstrap_committed_composition",
  };
}
