import type { ActorId, ArtifactId, JsonObject } from "../contracts/index.ts";
import type {
  MachineKind,
  MachineSpawnSpec,
  SendActorEventEffect,
  SpawnActorEffect,
} from "./runtime.ts";

export type OrchestrationMachineDeclaration = {
  readonly kind: MachineKind;
  readonly label: string;
  readonly responsibility: string;
};

export type OrchestrationSpawnDeclaration = {
  readonly id: string;
  readonly owner: "edition";
  readonly child: Exclude<MachineKind, "edition">;
  readonly cardinality: "many" | "one_per_cycle" | "single";
  readonly condition: string;
  readonly completionEvent: "CHILD_STATUS";
};

export type OrchestrationRouteDeclaration = {
  readonly id: string;
  readonly owner: "edition";
  readonly source: MachineKind;
  readonly target: Exclude<MachineKind, "edition">;
  readonly event: "RETRY" | "REVISION_REQUESTED";
  readonly condition: string;
};

export type OrchestrationJoinDeclaration = {
  readonly id: string;
  readonly owner: "edition";
  readonly participants: readonly Exclude<MachineKind, "edition">[];
  readonly targets: readonly Exclude<MachineKind, "edition">[];
  readonly mode: "all_settled" | "declared_artifact_dependencies";
  readonly condition: string;
};

const machines = [
  { kind: "edition", label: "EditionMachine", responsibility: "lifecycle owner and durable joins" },
  { kind: "source", label: "SourceMachine", responsibility: "capture, extraction, and source approval" },
  { kind: "article", label: "ArticleMachine", responsibility: "article drafting, judgment, and fit" },
  { kind: "editorial", label: "EditorialMachine", responsibility: "opening editorial" },
  { kind: "edition_review", label: "EditionReviewMachine", responsibility: "English issue review and finding routes" },
  { kind: "translation", label: "TranslationMachine", responsibility: "per-language, per-piece translation, review, fit, and durable promotion" },
  { kind: "cover_art", label: "CoverArtMachine", responsibility: "registered cover selection" },
  { kind: "interior_art", label: "InteriorArtMachine", responsibility: "registered interior art selection" },
  { kind: "render", label: "RenderMachine", responsibility: "measurement, render, inspection, and visual review" },
  { kind: "release", label: "ReleaseMachine", responsibility: "exact publication approval" },
] as const satisfies readonly OrchestrationMachineDeclaration[];

const spawns = {
  sources: {
    id: "edition.spawn.sources",
    owner: "edition",
    child: "source",
    cardinality: "many",
    condition: "each accepted lead while collection is open",
    completionEvent: "CHILD_STATUS",
  },
  articles: {
    id: "edition.spawn.articles",
    owner: "edition",
    child: "article",
    cardinality: "many",
    condition: "an approved plan assigns every ready source",
    completionEvent: "CHILD_STATUS",
  },
  editorial: {
    id: "edition.spawn.editorial",
    owner: "edition",
    child: "editorial",
    cardinality: "single",
    condition: "all current articles settle",
    completionEvent: "CHILD_STATUS",
  },
  editionReviews: {
    id: "edition.spawn.edition_reviews",
    owner: "edition",
    child: "edition_review",
    cardinality: "one_per_cycle",
    condition: "editorial and every required art actor settle",
    completionEvent: "CHILD_STATUS",
  },
  translations: {
    id: "edition.spawn.translations",
    owner: "edition",
    child: "translation",
    cardinality: "many",
    condition: "the current English issue is approved; one actor is spawned per configured language and exact piece",
    completionEvent: "CHILD_STATUS",
  },
  coverArt: {
    id: "edition.spawn.cover_art",
    owner: "edition",
    child: "cover_art",
    cardinality: "many",
    condition: "an approved plan declares cover art and its dependencies are ready",
    completionEvent: "CHILD_STATUS",
  },
  interiorArt: {
    id: "edition.spawn.interior_art",
    owner: "edition",
    child: "interior_art",
    cardinality: "many",
    condition: "an approved plan declares interior art and its dependencies are ready",
    completionEvent: "CHILD_STATUS",
  },
  renders: {
    id: "edition.spawn.renders",
    owner: "edition",
    child: "render",
    cardinality: "one_per_cycle",
    condition: "approved English and every configured translation are assembled",
    completionEvent: "CHILD_STATUS",
  },
  releases: {
    id: "edition.spawn.releases",
    owner: "edition",
    child: "release",
    cardinality: "one_per_cycle",
    condition: "machine inspection and exact visual review approve the render set",
    completionEvent: "CHILD_STATUS",
  },
} as const satisfies Readonly<Record<string, OrchestrationSpawnDeclaration>>;

const routes = {
  reviewFindingsToArticles: {
    id: "edition.route.review_findings_to_articles",
    owner: "edition",
    source: "edition_review",
    target: "article",
    event: "REVISION_REQUESTED",
    condition: "edition review routes a finding to a named article",
  },
  articleChangesToEditorial: {
    id: "edition.route.article_changes_to_editorial",
    owner: "edition",
    source: "article",
    target: "editorial",
    event: "REVISION_REQUESTED",
    condition: "a routed article revision changes the current English inputs",
  },
  editorialChangesToCoverArt: {
    id: "edition.route.editorial_changes_to_cover_art",
    owner: "edition",
    source: "editorial",
    target: "cover_art",
    event: "REVISION_REQUESTED",
    condition: "declared cover dependencies change",
  },
  editorialChangesToInteriorArt: {
    id: "edition.route.editorial_changes_to_interior_art",
    owner: "edition",
    source: "editorial",
    target: "interior_art",
    event: "REVISION_REQUESTED",
    condition: "declared interior-art dependencies change",
  },
  releaseRetry: {
    id: "edition.route.release_retry",
    owner: "edition",
    source: "edition",
    target: "release",
    event: "RETRY",
    condition: "a rejected release receives an explicit retry",
  },
} as const satisfies Readonly<Record<string, OrchestrationRouteDeclaration>>;

const joins = {
  readySourcesToArticles: {
    id: "edition.join.ready_sources_to_articles",
    owner: "edition",
    participants: ["source"],
    targets: ["article"],
    mode: "all_settled",
    condition: "all frozen sources are ready, then collection close and planning are approved",
  },
  readyArticlesToEditorial: {
    id: "edition.join.ready_articles_to_editorial",
    owner: "edition",
    participants: ["article"],
    targets: ["editorial"],
    mode: "all_settled",
    condition: "every planned article settles",
  },
  contentAndArtToEditionReview: {
    id: "edition.join.content_and_art_to_edition_review",
    owner: "edition",
    participants: ["article", "editorial", "cover_art", "interior_art"],
    targets: ["edition_review"],
    mode: "all_settled",
    condition: "the current articles, editorial, and every required registered art actor settle",
  },
  approvedReviewToLanguages: {
    id: "edition.join.approved_review_to_languages",
    owner: "edition",
    participants: ["edition_review"],
    targets: ["translation", "render"],
    mode: "all_settled",
    condition: "the current English issue receives exact approval",
  },
  readyLanguagesToRender: {
    id: "edition.join.ready_languages_to_render",
    owner: "edition",
    participants: ["translation"],
    targets: ["render"],
    mode: "all_settled",
    condition: "every configured non-English language and exact translated piece settles durably",
  },
  declaredContentToArt: {
    id: "edition.join.declared_content_to_art",
    owner: "edition",
    participants: ["article", "editorial"],
    targets: ["cover_art", "interior_art"],
    mode: "declared_artifact_dependencies",
    condition: "all explicitly declared content artifact dependencies exist",
  },
  approvedRenderToRelease: {
    id: "edition.join.approved_render_to_release",
    owner: "edition",
    participants: ["render"],
    targets: ["release"],
    mode: "all_settled",
    condition: "inspection and independent visual review approve the exact render artifacts",
  },
} as const satisfies Readonly<Record<string, OrchestrationJoinDeclaration>>;

export const editionOrchestration = { machines, spawns, routes, joins } as const;

export type OrchestrationSpawnId =
  (typeof editionOrchestration.spawns)[keyof typeof editionOrchestration.spawns]["id"];
export type OrchestrationRouteId =
  (typeof editionOrchestration.routes)[keyof typeof editionOrchestration.routes]["id"];

export function spawnOrchestratedChild(
  declaration: OrchestrationSpawnDeclaration,
  parentActorId: ActorId,
  logicalKey: string,
  spec: MachineSpawnSpec,
): SpawnActorEffect {
  return {
    type: "spawn_actor",
    relationship: declaration.id as OrchestrationSpawnId,
    parentActorId,
    machine: declaration.child,
    logicalKey,
    spec,
  };
}

export function routeOrchestratedEvent(
  declaration: OrchestrationRouteDeclaration,
  actorId: ActorId,
  childKey: string,
  event: JsonObject & { readonly type: "RETRY" | "REVISION_REQUESTED" },
): SendActorEventEffect {
  if (event.type !== declaration.event) {
    throw new TypeError(
      `Route ${declaration.id} carries ${declaration.event}, received ${event.type}`,
    );
  }
  return {
    type: "send_actor_event",
    route: declaration.id as OrchestrationRouteId,
    actorId,
    target: { childKey },
    event,
  };
}

export function orchestrationSpawn(
  id: OrchestrationSpawnId,
): OrchestrationSpawnDeclaration | undefined {
  return Object.values(editionOrchestration.spawns).find(
    (declaration) => declaration.id === id,
  );
}

export function orchestrationRoute(
  id: OrchestrationRouteId,
): OrchestrationRouteDeclaration | undefined {
  return Object.values(editionOrchestration.routes).find(
    (declaration) => declaration.id === id,
  );
}

export function completionRelationship(
  owner: MachineKind,
  child: MachineKind,
): OrchestrationSpawnDeclaration | undefined {
  return Object.values(editionOrchestration.spawns).find(
    (declaration) => declaration.owner === owner && declaration.child === child,
  );
}

export function joinSettled(
  declaration: OrchestrationJoinDeclaration,
  statuses: readonly ("accepting" | "active" | "done" | "failed" | undefined)[],
): boolean {
  if (declaration.owner !== "edition" || declaration.mode !== "all_settled") {
    throw new TypeError(`Join ${declaration.id} is resolved from artifact dependencies`);
  }
  return statuses.every((status) => status === "accepting" || status === "done");
}

export function resolveDeclaredArtifacts(
  declaration: OrchestrationJoinDeclaration,
  artifacts: readonly (ArtifactId | undefined)[],
): readonly ArtifactId[] | undefined {
  if (declaration.owner !== "edition" || declaration.mode !== "declared_artifact_dependencies") {
    throw new TypeError(`Join ${declaration.id} is resolved from child status`);
  }
  return artifacts.every((artifactId) => artifactId !== undefined)
    ? artifacts as readonly ArtifactId[]
    : undefined;
}

export type RuntimeOrchestrationEdge = {
  readonly id: string;
  readonly declarationId: string;
  readonly kind: "completion" | "join" | "route" | "spawn";
  readonly source: MachineKind;
  readonly target: MachineKind;
  readonly label: string;
};

/**
 * Projects only declarations enforced or evaluated by runtime code. The graph
 * exporter consumes this projection and cannot add a graph-only machine edge.
 */
export function runtimeOrchestrationEdges(): readonly RuntimeOrchestrationEdge[] {
  const spawnEdges = Object.values(editionOrchestration.spawns).flatMap(
    (declaration) => [
      {
        id: `${declaration.id}:spawn`,
        declarationId: declaration.id,
        kind: "spawn" as const,
        source: declaration.owner,
        target: declaration.child,
        label: declaration.condition,
      },
      {
        id: `${declaration.id}:completion`,
        declarationId: declaration.id,
        kind: "completion" as const,
        source: declaration.child,
        target: declaration.owner,
        label: declaration.completionEvent,
      },
    ],
  );
  const routeEdges = Object.values(editionOrchestration.routes).map(
    (declaration) => ({
      id: declaration.id,
      declarationId: declaration.id,
      kind: "route" as const,
      source: declaration.owner,
      target: declaration.target,
      label: `after ${declaration.source}: ${declaration.event}: ${declaration.condition}`,
    }),
  );
  const joinEdges = Object.values(editionOrchestration.joins).flatMap(
    (declaration) => declaration.participants.flatMap((source) =>
      declaration.targets.map((target) => ({
        id: `${declaration.id}:${source}:${target}`,
        declarationId: declaration.id,
        kind: "join" as const,
        source: declaration.owner,
        target,
        label: `${source} readiness: ${declaration.condition}`,
      })),
    ),
  );
  return [...spawnEdges, ...routeEdges, ...joinEdges];
}
