import { dirname, join } from "node:path";

import type { RevisionId } from "../contracts/index.ts";
import type {
  DurableLogicalItem,
  DurableRevisionRef,
  InputRevisionRef,
} from "./types.ts";
import { parseRevisionId } from "./revision-id.ts";

const PORTABLE_COMPONENT = /^[a-z0-9][a-z0-9._-]{0,127}$/u;

export function durableRevisionRelativeDirectory(ref: DurableRevisionRef): string {
  const edition = portableComponent(ref.editionId, "edition ID");
  const revision = parseRevisionId(ref.revisionId);
  switch (ref.kind) {
    case "article": {
      const logical = portableComponent(ref.logicalId, "logical ID");
      return join("editions", edition, "articles", logical, requiredLanguage(ref), "revisions", revision);
    }
    case "editorial": {
      const logical = portableComponent(ref.logicalId, "logical ID");
      return join("editions", edition, "editorials", logical, requiredLanguage(ref), "revisions", revision);
    }
    case "image": {
      const logical = portableComponent(ref.logicalId, "logical ID");
      rejectLanguage(ref);
      return join("editions", edition, "images", logical, "revisions", revision);
    }
    case "composition":
      rejectLanguage(ref);
      return join(
        "editions",
        edition,
        "compositions",
        portableComponent(ref.compositionId, "composition ID"),
        "revisions",
        revision,
      );
  }
}

export function durableRevisionParentRelativeDirectory(item: DurableLogicalItem): string {
  const placeholder = "rev_20000101T000000000Z_aaaaaaaaaaaa" as RevisionId;
  const revisionDirectory = durableRevisionRelativeDirectory({ ...item, revisionId: placeholder });
  return dirname(revisionDirectory);
}

export function inputRevisionRelativeDirectory(ref: InputRevisionRef): string {
  const logical = portableComponent(ref.logicalId, "input logical ID");
  const revision = parseRevisionId(ref.revisionId);
  switch (ref.kind) {
    case "source_capture":
      return join("sources", logical, "captures", revision);
    case "source_extraction":
      return join("sources", logical, "extractions", revision);
    case "prompt":
      return join("prompts", logical, "revisions", revision);
    case "policy":
      return join("policies", logical, "revisions", revision);
    case "article_production_profile":
      return join("article-production-profiles", logical, "revisions", revision);
    case "article_review_plan":
      return join("article-review-plans", logical, "revisions", revision);
    case "review_material_schema":
      return join("review-material-schemas", logical, "revisions", revision);
    case "migration_archive":
    case "migration_attestation":
    case "migration_plan":
      return join("migrations", logical, "revisions", revision);
    case "write_pipeline":
      return join(
        "editions",
        portableComponent(ref.editionId ?? "", "input edition ID"),
        "specs",
        "write-pipeline",
        "revisions",
        revision,
      );
    case "edition_spec":
    case "run_bootstrap":
      return join(
        "editions",
        portableComponent(ref.editionId ?? "", "input edition ID"),
        "specs",
        logical,
        "revisions",
        revision,
      );
  }
}

export function portableComponent(value: string, label: string): string {
  if (!PORTABLE_COMPONENT.test(value) || value === "." || value === "..") {
    throw new Error(`${label} is not a portable lowercase path component: ${value}`);
  }
  return value;
}

function requiredLanguage(item: DurableLogicalItem): string {
  return portableComponent(item.language ?? "", "language");
}

function rejectLanguage(item: DurableLogicalItem): void {
  if (item.language !== undefined) {
    throw new Error(`${item.kind} revisions must not declare a language`);
  }
}
