import assert from "node:assert/strict";
import { describe, test } from "node:test";

import type {
  ActorId,
  ArtifactId,
  ModelPolicy,
} from "../contracts/index.ts";
import {
  coverArtInitial,
  coverArtTransition,
  interiorArtInitial,
  interiorArtTransition,
  type ArtMachineInput,
} from "../machines/art-machines.ts";
import {
  editorialInitial,
  editorialTransition,
  type EditorialMachineInput,
} from "../machines/editorial-machine.ts";
import {
  releaseInitial,
  releaseTransition,
  type ReleaseMachineInput,
} from "../machines/release-machine.ts";
import {
  renderInitial,
  renderTransition,
  type RenderMachineInput,
} from "../machines/render-machine.ts";
import type {
  JsonMachineSnapshot,
  MachineEffect,
  MachineTransitionResult,
} from "../machines/runtime.ts";
import {
  sourceInitial,
  sourceTransition,
  type SourceMachineInput,
} from "../machines/source-machine.ts";
import {
  translationInitial,
  translationTransition,
  type TranslationMachineInput,
} from "../machines/translation-machine.ts";

function actorId(value: string): ActorId {
  return value as ActorId;
}

function artifactId(value: string): ArtifactId {
  return value as ArtifactId;
}

const modelPolicy: ModelPolicy = {
  default: {
    adapter: "test",
    model: "deterministic",
  },
};

function state(result: MachineTransitionResult, expected: string): void {
  assert.equal(result.snapshot.value, expected);
}

function effectsOfType<EffectType extends MachineEffect["type"]>(
  result: MachineTransitionResult,
  type: EffectType,
): Extract<MachineEffect, { readonly type: EffectType }>[] {
  return result.effects.filter(
    (effect): effect is Extract<MachineEffect, { readonly type: EffectType }> =>
      effect.type === type,
  );
}

function assertNoOffer(result: MachineTransitionResult): void {
  assert.deepEqual(effectsOfType(result, "create_work_offer"), []);
}

function assertSingleOffer(
  result: MachineTransitionResult,
  slot: string,
): void {
  const offers = effectsOfType(result, "create_work_offer");
  assert.equal(offers.length, 1);
  assert.equal(offers[0]?.slot, slot);
}

function assertHumanRequest(result: MachineTransitionResult, slot: string): void {
  assertSingleOffer(result, slot);
  const offer = effectsOfType(result, "create_work_offer")[0];
  const request = effectsOfType(result, "register_artifact").find(
    (candidate) => candidate.artifact.kind === "human_decision_request",
  );
  assert.ok(offer);
  assert.ok(request);
  assert.equal(offer.taskArtifactId, request.artifact.id);
  assert.equal(offer.inputArtifacts[0], request.artifact.id);
}

function context(snapshot: JsonMachineSnapshot): Record<string, unknown> {
  return snapshot.context;
}

function sourceInput(overrides: Partial<SourceMachineInput["spec"]> = {}): SourceMachineInput {
  return {
    actorId: actorId("actor-source"),
    logicalKey: "source:one",
    spec: {
      sourceId: "source-one",
      leadArtifact: artifactId("lead"),
      ...overrides,
    },
  };
}

function editorialInput(
  overrides: Partial<EditorialMachineInput["spec"]> = {},
): EditorialMachineInput {
  return {
    actorId: actorId("actor-editorial"),
    logicalKey: "editorial:opening",
    spec: {
      editorialId: "opening",
      briefArtifact: artifactId("editorial-brief"),
      writingRules: artifactId("writing-rules"),
      modelPolicy,
      ...overrides,
    },
  };
}

function translationInput(
  overrides: Partial<TranslationMachineInput["spec"]> = {},
): TranslationMachineInput {
  return {
    actorId: actorId("actor-translation"),
    logicalKey: "translation:es",
    spec: {
      language: "es",
      sourceLanguage: "en",
      englishArtifacts: [artifactId("english-article")],
      promptArtifact: artifactId("translation-prompt"),
      maximumReaderPages: 7,
      modelPolicy,
      ...overrides,
    },
  };
}

function artInput(
  role: "cover" | "interior",
  overrides: Partial<ArtMachineInput["spec"]> = {},
): ArtMachineInput {
  return {
    actorId: actorId(`actor-${role}`),
    logicalKey: `art:${role}`,
    spec: {
      key: `${role}-one`,
      role,
      briefArtifact: artifactId(`${role}-brief`),
      required: true,
      ...overrides,
    },
  };
}

function renderInput(): RenderMachineInput {
  return {
    actorId: actorId("actor-render"),
    logicalKey: "render:edition",
    spec: {
      renderManifestArtifact: artifactId("render-manifest-v1"),
      rendererContractVersion: "renderer-test/1",
      printerProfileArtifact: artifactId("printer-profile"),
      configuredLanguages: ["en", "es"],
      studioPolicy: "home_ready_studio_blocked",
    },
  };
}

function releaseInput(overrides: Partial<ReleaseMachineInput["spec"]> = {}): ReleaseMachineInput {
  return {
    actorId: actorId("actor-release"),
    logicalKey: "release:edition",
    spec: {
      publicationArtifact: artifactId("publication-v1"),
      sourceArtifacts: [artifactId("source-a"), artifactId("source-b")],
      dryRun: false,
      target: "private",
      ...overrides,
    },
  };
}

describe("SourceMachine", () => {
  test("ignores a stale slot, retries capture, and revises a reviewed extraction", () => {
    let result = sourceInitial(sourceInput());
    state(result, "idle");

    result = sourceTransition(result.snapshot, { type: "START" });
    state(result, "capturing");
    assertSingleOffer(result, "capture");

    const beforeStale = result.snapshot;
    result = sourceTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "extract",
      artifacts: [{ kind: "source_extraction", artifactId: artifactId("stale-extraction") }],
      result: {},
    });
    state(result, "capturing");
    assert.deepEqual(result.snapshot.context, beforeStale.context);
    assert.deepEqual(result.effects, []);

    result = sourceTransition(result.snapshot, {
      type: "WORK_FAILED",
      slot: "capture",
      classification: "timeout",
      message: "capture timed out",
    });
    state(result, "capture_failed");
    assert.equal(context(result.snapshot).lastFailure, "capture timed out");

    result = sourceTransition(result.snapshot, { type: "RETRY" });
    state(result, "capturing");
    assertSingleOffer(result, "capture");

    result = sourceTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "capture",
      artifacts: [
        { kind: "raw_source_bundle", artifactId: artifactId("raw-v1") },
        { kind: "raw_evidence", artifactId: artifactId("raw-evidence-v1") },
        { kind: "source_metadata", artifactId: artifactId("metadata-v1") },
      ],
      result: {},
    });
    state(result, "extracting");
    assertSingleOffer(result, "extract");

    result = sourceTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "extract",
      artifacts: [{ kind: "source_extraction", artifactId: artifactId("extraction-v1") }],
      result: {},
    });
    state(result, "awaiting_source_review");
    assertHumanRequest(result, "review");

    result = sourceTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "review",
      artifacts: [{ kind: "source_review_decision", artifactId: artifactId("review-v1") }],
      result: { decision: "revise" },
    });
    state(result, "extracting");
    assert.equal(context(result.snapshot).revision, 1);
    assertSingleOffer(result, "extract");
    assert.equal(effectsOfType(result, "record_decision")[0]?.choice, "revise");
  });

  test("prepared extraction still requires a fresh human source review", () => {
    let result = sourceInitial(
      sourceInput({
        extractionArtifact: artifactId("extraction-approved"),
        rawBundleArtifact: artifactId("raw-approved"),
        rawEvidenceArtifacts: [artifactId("raw-evidence-approved")],
        metadataArtifact: artifactId("metadata-approved"),
        approvalArtifact: artifactId("source-review-approved"),
      }),
    );
    result = sourceTransition(result.snapshot, { type: "START" });
    state(result, "awaiting_source_review");
    assertHumanRequest(result, "review");
    assert.equal(effectsOfType(result, "complete_actor").length, 0);
  });
});

describe("EditorialMachine", () => {
  test("binds an editor escalation to one immutable request", () => {
    let result = editorialInitial(editorialInput());
    result = editorialTransition(result.snapshot, { type: "START" });
    result = editorialTransition(result.snapshot, {
      type: "EDITOR_DECISION_REQUIRED",
      findingArtifacts: [artifactId("editorial-finding")],
    });
    state(result, "awaiting_editor");
    assertHumanRequest(result, "editor_decision");
  });

  test("retries a draft and reopens a settled manuscript with exact findings", () => {
    let result = editorialInitial(editorialInput());
    result = editorialTransition(result.snapshot, { type: "START" });
    state(result, "drafting");
    assertSingleOffer(result, "draft");

    result = editorialTransition(result.snapshot, {
      type: "WORK_FAILED",
      slot: "draft",
      classification: "retryable",
      message: "writer unavailable",
    });
    state(result, "draft_failed");

    result = editorialTransition(result.snapshot, { type: "RETRY" });
    state(result, "drafting");
    assertSingleOffer(result, "draft");

    result = editorialTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "draft",
      artifacts: [{ kind: "editorial_manuscript", artifactId: artifactId("editorial-v1") }],
      result: {},
    });
    state(result, "settled");
    assert.equal(effectsOfType(result, "complete_actor")[0]?.outputs[0], "editorial-v1");

    result = editorialTransition(result.snapshot, {
      type: "REVISION_REQUESTED",
      findingArtifacts: [artifactId("finding-1"), artifactId("finding-2")],
      reason: "edition review",
    });
    state(result, "drafting");
    assert.equal(context(result.snapshot).revision, 1);
    assert.deepEqual(context(result.snapshot).revisionArtifacts, ["finding-1", "finding-2"]);
    const offer = effectsOfType(result, "create_work_offer")[0];
    assert.deepEqual(offer?.inputArtifacts.slice(-2), ["finding-1", "finding-2"]);
  });

  test("ignores a completion for an inactive editor slot", () => {
    let result = editorialInitial(editorialInput());
    result = editorialTransition(result.snapshot, { type: "START" });
    const before = result.snapshot;
    result = editorialTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "editor_decision",
      artifacts: [],
      result: { choice: "accept" },
    });
    state(result, "drafting");
    assert.deepEqual(result.snapshot.context, before.context);
    assert.deepEqual(result.effects, []);
  });
});

describe("TranslationMachine", () => {
  test("initial translation skips drafting, editor revision returns to drafting, and fit settles", () => {
    let result = translationInitial(
      translationInput({ initialTranslationArtifacts: [artifactId("translation-v1")] }),
    );
    result = translationTransition(result.snapshot, { type: "START" });
    state(result, "language_review");
    assertSingleOffer(result, "language_review");

    result = translationTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "language_review",
      artifacts: [
        { kind: "language_review", artifactId: artifactId("language-review-v1") },
        { kind: "finding", artifactId: artifactId("translation-finding") },
      ],
      result: { decision: "editor_decision" },
    });
    state(result, "awaiting_editor");
    assertHumanRequest(result, "editor_decision");

    result = translationTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "editor_decision",
      artifacts: [{ kind: "editor_decision", artifactId: artifactId("translation-ruling") }],
      result: { choice: "revise" },
    });
    state(result, "drafting");
    assertSingleOffer(result, "draft");
    assert.equal(effectsOfType(result, "record_decision")[0]?.choice, "revise");

    result = translationTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "draft",
      artifacts: [{ kind: "translation_bundle", artifactId: artifactId("translation-v2") }],
      result: {},
    });
    state(result, "language_review");

    result = translationTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "language_review",
      artifacts: [{ kind: "language_review", artifactId: artifactId("language-review-v2") }],
      result: { decision: "approved" },
    });
    state(result, "language_fit");

    result = translationTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "language_fit",
      artifacts: [{ kind: "language_measurement", artifactId: artifactId("fit-v2") }],
      result: { fits: true },
    });
    state(result, "settled");
    assert.deepEqual(effectsOfType(result, "complete_actor")[0]?.outputs, ["translation-v2"]);

    result = translationTransition(result.snapshot, {
      type: "REVISION_REQUESTED",
      englishArtifacts: [artifactId("english-article-v2")],
      findingArtifacts: [artifactId("translation-finding-v2")],
      reason: "English changed",
    });
    state(result, "drafting");
    assert.equal(context(result.snapshot).revision, 1);
    const offer = effectsOfType(result, "create_work_offer")[0];
    assert.ok(offer?.inputArtifacts.includes(artifactId("english-article-v2")));
    assert.ok(offer?.inputArtifacts.includes(artifactId("translation-finding-v2")));
  });

  test("ignores a late fit answer while drafting", () => {
    let result = translationInitial(translationInput());
    result = translationTransition(result.snapshot, { type: "START" });
    const before = result.snapshot;
    result = translationTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "language_fit",
      artifacts: [{ kind: "language_measurement", artifactId: artifactId("late-fit") }],
      result: { fits: true },
    });
    state(result, "drafting");
    assert.deepEqual(result.snapshot.context, before.context);
    assert.deepEqual(result.effects, []);
  });
});

describe("ArtMachine", () => {
  test("registered cover and interior art take the zero-offer fast path", () => {
    for (const role of ["cover", "interior"] as const) {
      const registered = artifactId(`${role}-registered`);
      const initial = role === "cover" ? coverArtInitial : interiorArtInitial;
      const transition = role === "cover" ? coverArtTransition : interiorArtTransition;
      let result = initial(artInput(role, { artifactId: registered }));
      result = transition(result.snapshot, { type: "START" });
      state(result, "registered");
      assertNoOffer(result);
      const completion = effectsOfType(result, "complete_actor");
      assert.equal(completion.length, 1);
      assert.deepEqual(completion[0]?.outputs, [registered]);
    }
  });

  test("unknown selection is not registered, retry works, and a revision discards old art", () => {
    let result = coverArtInitial(artInput("cover"));
    result = coverArtTransition(result.snapshot, { type: "START" });
    state(result, "generating");

    result = coverArtTransition(result.snapshot, {
      type: "WORK_FAILED",
      slot: "generate",
      classification: "timeout",
      message: "image timeout",
    });
    state(result, "generation_failed");

    result = coverArtTransition(result.snapshot, { type: "RETRY" });
    state(result, "generating");
    assertSingleOffer(result, "generate");

    result = coverArtTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "generate",
      artifacts: [
        { kind: "cover_art_candidate", artifactId: artifactId("cover-candidate-1") },
        { kind: "cover_art_candidate", artifactId: artifactId("cover-candidate-2") },
      ],
      result: {},
    });
    state(result, "awaiting_selection");
    assertHumanRequest(result, "select");

    result = coverArtTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "select",
      artifacts: [{ kind: "art_selection", artifactId: artifactId("selection-stale") }],
      result: { choice: "select", selectedArtifactId: "unknown-candidate" },
    });
    state(result, "generating");
    assertSingleOffer(result, "generate");
    assert.deepEqual(effectsOfType(result, "complete_actor"), []);

    result = coverArtTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "generate",
      artifacts: [{ kind: "cover_art_candidate", artifactId: artifactId("cover-candidate-3") }],
      result: {},
    });
    result = coverArtTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "select",
      artifacts: [{ kind: "art_selection", artifactId: artifactId("selection-current") }],
      result: { choice: "select", selectedArtifactId: "cover-candidate-3" },
    });
    state(result, "registered");
    assert.deepEqual(effectsOfType(result, "complete_actor")[0]?.outputs, ["cover-candidate-3"]);

    result = coverArtTransition(result.snapshot, {
      type: "REVISION_REQUESTED",
      reason: "new direction",
    });
    state(result, "generating");
    assert.equal(context(result.snapshot).registeredArtifact, undefined);
    assert.deepEqual(context(result.snapshot).candidates, []);
    assert.equal(context(result.snapshot).revision, 1);
    assertSingleOffer(result, "generate");
  });

  test("optional interior art can be explicitly dropped after selection", () => {
    let result = interiorArtInitial(artInput("interior", { required: false }));
    result = interiorArtTransition(result.snapshot, { type: "START" });
    result = interiorArtTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "generate",
      artifacts: [{ kind: "interior_art_candidate", artifactId: artifactId("interior-candidate") }],
      result: {},
    });
    result = interiorArtTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "select",
      artifacts: [{ kind: "art_selection", artifactId: artifactId("drop-decision") }],
      result: { choice: "drop" },
    });
    state(result, "not_required");
    assertNoOffer(result);
    const completion = effectsOfType(result, "complete_actor")[0];
    assert.equal(completion?.accepting, true);
    assert.deepEqual(completion?.outputs, []);
    assert.equal(completion?.result.status, "not_required");
  });
});

function advanceRenderToVisualReview(): MachineTransitionResult {
  let result = renderInitial(renderInput());
  result = renderTransition(result.snapshot, { type: "START" });
  result = renderTransition(result.snapshot, {
    type: "WORK_COMPLETED",
    slot: "measure_edition",
    artifacts: [{ kind: "edition_measurement", artifactId: artifactId("measurement-v1") }],
    result: { result: "pass" },
  });
  result = renderTransition(result.snapshot, {
    type: "WORK_COMPLETED",
    slot: "render",
    artifacts: [
      { kind: "reader_pdf", artifactId: artifactId("reader-v1") },
      { kind: "booklet_pdf", artifactId: artifactId("booklet-v1") },
    ],
    result: { renderedLanguages: ["es", "en"] },
  });
  result = renderTransition(result.snapshot, {
    type: "WORK_COMPLETED",
    slot: "inspection",
    artifacts: [{ kind: "render_inspection", artifactId: artifactId("inspection-v1") }],
    result: {
      result: "pass",
      renderArtifactIds: ["booklet-v1", "reader-v1"],
    },
  });
  state(result, "awaiting_visual_review");
  return result;
}

describe("RenderMachine", () => {
  test("moves a partial-language render completion into a retryable failure", () => {
    let result = renderInitial(renderInput());
    result = renderTransition(result.snapshot, { type: "START" });
    result = renderTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "measure_edition",
      artifacts: [{ kind: "edition_measurement", artifactId: artifactId("measurement-v1") }],
      result: { result: "pass" },
    });
    result = renderTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "render",
      artifacts: [{ kind: "reader_pdf", artifactId: artifactId("reader-en") }],
      result: { renderedLanguages: ["en"] },
    });
    state(result, "render_failed");
    assert.equal(context(result.snapshot).lastFailure, "Render answer did not cover every configured language and required output kind");
  });

  test("retry preserves stage and stale visual approval cannot approve a different render", () => {
    let result = renderInitial(renderInput());
    result = renderTransition(result.snapshot, { type: "START" });
    result = renderTransition(result.snapshot, {
      type: "WORK_FAILED",
      slot: "measure_edition",
      classification: "retryable",
      message: "renderer busy",
    });
    state(result, "measurement_failed");
    result = renderTransition(result.snapshot, { type: "RETRY" });
    state(result, "measuring");
    assertSingleOffer(result, "measure_edition");

    result = advanceRenderToVisualReview();
    result = renderTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "visual_review",
      artifacts: [
        { kind: "visual_review_decision", artifactId: artifactId("visual-decision-stale") },
      ],
      result: {
        decision: "approved",
        renderArtifactIds: ["reader-v1", "booklet-v0"],
      },
    });
    state(result, "visual_changes_required");
    assert.deepEqual(effectsOfType(result, "complete_actor"), []);
    assert.equal(effectsOfType(result, "record_decision")[0]?.choice, "approved");

    result = renderTransition(result.snapshot, {
      type: "REVISION_REQUESTED",
      findingArtifacts: [artifactId("visual-finding")],
      reason: "approval named an obsolete booklet",
      renderManifestArtifact: artifactId("render-manifest-v2"),
    });
    state(result, "measuring");
    assert.equal(context(result.snapshot).revision, 1);
    assert.equal(context(result.snapshot).renderManifestArtifact, "render-manifest-v2");
    assert.deepEqual(context(result.snapshot).renderArtifacts, []);
    assertSingleOffer(result, "measure_edition");
  });

  test("visual approval for the exact set completes the actor", () => {
    let result = advanceRenderToVisualReview();
    result = renderTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "visual_review",
      artifacts: [
        { kind: "visual_review_decision", artifactId: artifactId("visual-decision-v1") },
      ],
      result: {
        decision: "approved",
        renderArtifactIds: ["booklet-v1", "reader-v1"],
      },
    });
    state(result, "approved");
    const completion = effectsOfType(result, "complete_actor")[0];
    assert.equal(completion?.accepting, true);
    assert.deepEqual(completion?.outputs, ["reader-v1", "booklet-v1"]);
  });

  test("ignores an inspection answer received while rendering", () => {
    let result = renderInitial(renderInput());
    result = renderTransition(result.snapshot, { type: "START" });
    result = renderTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "measure_edition",
      artifacts: [{ kind: "edition_measurement", artifactId: artifactId("measurement") }],
      result: { fits: true },
    });
    state(result, "rendering");
    const before = result.snapshot;
    result = renderTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "inspection",
      artifacts: [{ kind: "render_inspection", artifactId: artifactId("late-inspection") }],
      result: { result: "pass", renderArtifactIds: [] },
    });
    state(result, "rendering");
    assert.deepEqual(result.snapshot.context, before.context);
    assert.deepEqual(result.effects, []);
  });
});

describe("ReleaseMachine", () => {
  test("rejects approval naming stale source artifacts and can retry with the exact set", () => {
    let result = releaseInitial(releaseInput());
    result = releaseTransition(result.snapshot, { type: "START" });
    state(result, "awaiting_release_approval");
    assertSingleOffer(result, "release_approval");

    result = releaseTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "release_approval",
      artifacts: [{ kind: "release_decision", artifactId: artifactId("release-stale") }],
      result: {
        choice: "approve",
        publicationArtifactId: "publication-v1",
        sourceArtifactIds: ["source-a", "source-old"],
      },
    });
    state(result, "rejected");
    const rejected = effectsOfType(result, "complete_actor")[0];
    assert.equal(rejected?.accepting, false);
    assert.deepEqual(rejected?.outputs, []);

    result = releaseTransition(result.snapshot, { type: "RETRY" });
    state(result, "awaiting_release_approval");
    assertSingleOffer(result, "release_approval");

    result = releaseTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "release_approval",
      artifacts: [{ kind: "release_decision", artifactId: artifactId("release-current") }],
      result: {
        choice: "approve",
        publicationArtifactId: "publication-v1",
        sourceArtifactIds: ["source-b", "source-a"],
      },
    });
    state(result, "released");
    const released = effectsOfType(result, "complete_actor")[0];
    assert.equal(released?.accepting, true);
    assert.deepEqual(released?.outputs, ["publication-v1"]);
  });

  test("requires a decision artifact and keeps dry-run completion non-accepting", () => {
    let result = releaseInitial(releaseInput({ dryRun: true }));
    result = releaseTransition(result.snapshot, { type: "START" });
    result = releaseTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "release_approval",
      artifacts: [],
      result: {
        choice: "approve",
        publicationArtifactId: "publication-v1",
        sourceArtifactIds: ["source-a", "source-b"],
      },
    });
    state(result, "rejected");

    result = releaseTransition(result.snapshot, { type: "RETRY" });
    result = releaseTransition(result.snapshot, {
      type: "WORK_COMPLETED",
      slot: "release_approval",
      artifacts: [{ kind: "release_decision", artifactId: artifactId("dry-run-decision") }],
      result: {
        choice: "approve",
        publicationArtifactId: "publication-v1",
        sourceArtifactIds: ["source-a", "source-b"],
      },
    });
    state(result, "dry_run_complete");
    const completion = effectsOfType(result, "complete_actor")[0];
    assert.equal(completion?.accepting, false);
    assert.equal(completion?.result.status, "dry_run_complete");
  });

  test("retries a transient approval failure", () => {
    let result = releaseInitial(releaseInput());
    result = releaseTransition(result.snapshot, { type: "START" });
    result = releaseTransition(result.snapshot, {
      type: "WORK_FAILED",
      slot: "release_approval",
      classification: "timeout",
      message: "editor disconnected",
    });
    state(result, "approval_failed");
    result = releaseTransition(result.snapshot, { type: "RETRY" });
    state(result, "awaiting_release_approval");
    assertSingleOffer(result, "release_approval");
  });
});
