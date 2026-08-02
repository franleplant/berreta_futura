import type { JsonObject } from "../contracts/index.ts";
import {
  articleInitial,
  articleMachineVersion,
  articleTransition,
  type ArticleMachineEvent,
  type ArticleMachineInput,
} from "../machines/article-machine.ts";
import {
  editionInitial,
  editionMachineVersion,
  editionTransition,
  type EditionMachineEvent,
  type EditionMachineInput,
} from "../machines/edition-machine.ts";
import {
  editionReviewInitial,
  editionReviewMachineVersion,
  editionReviewTransition,
  type EditionReviewMachineEvent,
  type EditionReviewMachineInput,
} from "../machines/edition-review-machine.ts";
import {
  coverArtInitial,
  coverArtMachineVersion,
  coverArtTransition,
  interiorArtInitial,
  interiorArtMachineVersion,
  interiorArtTransition,
  type ArtMachineEvent,
  type ArtMachineInput,
} from "../machines/art-machines.ts";
import {
  editorialInitial,
  editorialMachineVersion,
  editorialTransition,
  type EditorialMachineEvent,
  type EditorialMachineInput,
} from "../machines/editorial-machine.ts";
import {
  releaseInitial,
  releaseMachineVersion,
  releaseTransition,
  type ReleaseMachineEvent,
  type ReleaseMachineInput,
} from "../machines/release-machine.ts";
import {
  renderInitial,
  renderMachineVersion,
  renderTransition,
  type RenderMachineEvent,
  type RenderMachineInput,
} from "../machines/render-machine.ts";
import type {
  JsonMachineSnapshot,
  MachineKind,
  MachineTransitionResult,
} from "../machines/runtime.ts";
import {
  sourceInitial,
  sourceMachineVersion,
  sourceTransition,
  type SourceMachineEvent,
  type SourceMachineInput,
} from "../machines/source-machine.ts";
import {
  translationInitial,
  translationMachineVersion,
  translationTransition,
  type TranslationMachineEvent,
  type TranslationMachineInput,
} from "../machines/translation-machine.ts";

export function currentMachineVersion(machine: MachineKind): string {
  switch (machine) {
    case "article":
      return articleMachineVersion;
    case "cover_art":
      return coverArtMachineVersion;
    case "edition":
      return editionMachineVersion;
    case "edition_review":
      return editionReviewMachineVersion;
    case "editorial":
      return editorialMachineVersion;
    case "interior_art":
      return interiorArtMachineVersion;
    case "release":
      return releaseMachineVersion;
    case "render":
      return renderMachineVersion;
    case "source":
      return sourceMachineVersion;
    case "translation":
      return translationMachineVersion;
  }
}

export function initialSnapshotFor(
  machine: MachineKind,
  input: JsonObject,
): MachineTransitionResult {
  switch (machine) {
    case "article":
      return articleInitial(input as unknown as ArticleMachineInput);
    case "cover_art":
      return coverArtInitial(input as unknown as ArtMachineInput);
    case "edition":
      return editionInitial(input as unknown as EditionMachineInput);
    case "edition_review":
      return editionReviewInitial(input as unknown as EditionReviewMachineInput);
    case "editorial":
      return editorialInitial(input as unknown as EditorialMachineInput);
    case "interior_art":
      return interiorArtInitial(input as unknown as ArtMachineInput);
    case "release":
      return releaseInitial(input as unknown as ReleaseMachineInput);
    case "render":
      return renderInitial(input as unknown as RenderMachineInput);
    case "source":
      return sourceInitial(input as unknown as SourceMachineInput);
    case "translation":
      return translationInitial(input as unknown as TranslationMachineInput);
  }
}

export function transitionSnapshotFor(
  machine: MachineKind,
  snapshot: JsonMachineSnapshot,
  event: JsonObject,
): MachineTransitionResult {
  switch (machine) {
    case "article":
      return articleTransition(snapshot, event as unknown as ArticleMachineEvent);
    case "cover_art":
      return coverArtTransition(snapshot, event as unknown as ArtMachineEvent);
    case "edition":
      return editionTransition(snapshot, event as unknown as EditionMachineEvent);
    case "edition_review":
      return editionReviewTransition(
        snapshot,
        event as unknown as EditionReviewMachineEvent,
      );
    case "editorial":
      return editorialTransition(snapshot, event as unknown as EditorialMachineEvent);
    case "interior_art":
      return interiorArtTransition(snapshot, event as unknown as ArtMachineEvent);
    case "release":
      return releaseTransition(snapshot, event as unknown as ReleaseMachineEvent);
    case "render":
      return renderTransition(snapshot, event as unknown as RenderMachineEvent);
    case "source":
      return sourceTransition(snapshot, event as unknown as SourceMachineEvent);
    case "translation":
      return translationTransition(snapshot, event as unknown as TranslationMachineEvent);
  }
}
