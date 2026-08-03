import assert from "node:assert/strict";
import { resolve } from "node:path";
import test from "node:test";

import { parse } from "yaml";

import { KNOWN_WORK_ROLES, type JsonObject } from "../contracts/index.ts";
import {
  compositionDurableRefs,
  parseCompositionDocument,
  type CompositionRevisionBinding,
} from "../durable/index.ts";
import { edition4SelectedArtPaths } from "../fixtures/edition4.ts";
import {
  buildEdition4PhaseOnePlan,
  buildEdition4RunBootstrapPlan,
  edition4CompositionRef,
  edition4RunBootstrapRevisionId,
} from "../migration/edition4-bootstrap.ts";

const root = resolve(import.meta.dirname, "../..");

test("Edition 4 fresh-v2 plan is exact, graph-complete, and read-only", async () => {
  const plan = await buildEdition4PhaseOnePlan(root);
  assert.deepEqual(plan.counts, {
    inputRevisions: 35,
    durableRevisions: 30,
    sourceCaptures: 9,
    sourceExtractions: 9,
    prompts: 12,
    policies: 4,
    articles: 14,
    editorials: 2,
    selectedImages: 13,
    compositions: 1,
  });
  assert.equal(plan.inputPlan.entries.length, 35);
  assert.equal(plan.durablePlan.entries.length, 29);
  assert.equal(
    plan.inputPlan.entries.some((entry) => entry.ref.kind === "run_bootstrap"),
    false,
  );

  const inputKinds = countBy(plan.inputPlan.entries.map((entry) => entry.ref.kind));
  assert.deepEqual(inputKinds, {
    edition_spec: 1,
    policy: 4,
    prompt: 12,
    source_capture: 9,
    source_extraction: 9,
  });
  const reviewBench = plan.inputPlan.entries.find((entry) =>
    entry.ref.kind === "policy" && entry.ref.logicalId === "review-bench"
  );
  assert.equal(reviewBench?.files[0]?.sourcePath, "prompts/README.md");

  const document = parseCompositionDocument(
    Buffer.from(JSON.stringify(plan.durablePlan.composition.document)),
    { editionId: "004", compositionId: "fresh-v2" },
  );
  assert.deepEqual(plan.durablePlan.composition.ref, edition4CompositionRef());
  assert.equal(document.editorials.length, 1);
  assert.equal(document.articles.length, 7);
  assert.equal(document.images.length, 4, "only cover and closing plates belong at edition scope");
  const selectedImages = compositionDurableRefs(document).filter((ref) => ref.kind === "image");
  assert.equal(selectedImages.length, 13);
  assert.equal(new Set(selectedImages.map(revisionKey)).size, 13);

  const importedImagePaths = plan.durablePlan.entries
    .filter((entry) => entry.ref.kind === "image")
    .flatMap((entry) => entry.files.map((file) => file.sourcePath))
    .sort();
  assert.deepEqual(importedImagePaths, [...await edition4SelectedArtPaths(root)].sort());

  for (const entry of plan.durablePlan.entries.filter((candidate) =>
    candidate.ref.kind === "article"
  )) {
    const captures = entry.inputRevisions.filter((ref) => ref.kind === "source_capture");
    const extractions = entry.inputRevisions.filter((ref) => ref.kind === "source_extraction");
    assert.ok(captures.length > 0, `${entry.ref.logicalId} has raw capture provenance`);
    assert.deepEqual(
      captures.map((ref) => ref.logicalId).sort(),
      extractions.map((ref) => ref.logicalId).sort(),
      `${entry.ref.logicalId} binds each extraction to its committed capture`,
    );
  }
});

test("Edition 4 run-bootstrap plan pins phase one and disables every skipped role", async () => {
  const composition = edition4CompositionRef();
  const binding: CompositionRevisionBinding = {
    revisionRef: composition,
    manifestDigest: `sha256:${"c".repeat(64)}`,
    gitCommitOid: "a".repeat(40),
    gitBlobOids: {
      [`durable/editions/004/compositions/fresh-v2/revisions/${composition.revisionId}/composition.yaml`]: "b".repeat(40),
      [`durable/editions/004/compositions/fresh-v2/revisions/${composition.revisionId}/manifest.yaml`]: "d".repeat(40),
    },
  };
  const plan = await buildEdition4RunBootstrapPlan(root, binding);
  assert.equal(plan.entries.length, 1);
  const entry = plan.entries[0]!;
  assert.deepEqual(entry.ref, {
    kind: "run_bootstrap",
    editionId: "004",
    logicalId: "fresh-v2",
    revisionId: edition4RunBootstrapRevisionId,
  });
  assert.equal(entry.files.length, 1);
  const file = entry.files[0]!;
  assert.equal(file.sourcePath, undefined);
  const document = parse(file.content) as JsonObject;
  assert.equal(document.schema_version, 1);
  assert.equal(document.image_generation_allowed, false);
  assert.equal(document.renderer_contract_version, "magazine-renderer/1");
  const phaseOne = await buildEdition4PhaseOnePlan(root);
  const compositionImages = compositionDurableRefs(phaseOne.durablePlan.composition.document)
    .filter((ref) => ref.kind === "image")
    .map((ref) => ({
      kind: ref.kind,
      edition_id: ref.editionId,
      logical_id: ref.logicalId,
      revision_id: ref.revisionId,
    }));
  assert.deepEqual(document.selected_image_revision_refs, compositionImages);

  const promptSet = document.prompt_set as JsonObject;
  assert.equal(promptSet.id, "fresh_v2_prompt_set");
  const roleInputs = promptSet.role_inputs as Record<string, JsonObject>;
  assert.deepEqual(Object.keys(roleInputs).sort(), [...KNOWN_WORK_ROLES].sort());
  const active = new Set([
    "composition_bootstrap",
    "measure_edition",
    "render",
    "render_inspection",
    "visual_review",
  ]);
  for (const role of KNOWN_WORK_ROLES) {
    assert.equal(
      roleInputs[role]!.kind === "disabled",
      !active.has(role),
      `${role} authority must match bootstrap execution`,
    );
  }
  assert.deepEqual(roleInputs.composition_bootstrap, {
    kind: "contract",
    contract_version: "composition-bootstrap/1",
  });
  assert.deepEqual(roleInputs.render, {
    kind: "contract",
    contract_version: "render-edition/1",
  });
  assert.equal(roleInputs.visual_review!.kind, "human");
  assert.equal(roleInputs.writer!.reason, "bootstrap_existing_manuscripts");
  assert.equal(roleInputs.translation_writer!.reason, "bootstrap_existing_translations");
  assert.equal(roleInputs.cover_image!.reason, "bootstrap_existing_images");
  assert.equal(roleInputs.release_approval!.reason, "stop_unreleased");
});

function countBy(values: readonly string[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const value of values) counts[value] = (counts[value] ?? 0) + 1;
  return counts;
}

function revisionKey(ref: { readonly kind: string; readonly revisionId: string }): string {
  return `${ref.kind}:${ref.revisionId}`;
}
