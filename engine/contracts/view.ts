import type { ArtifactView } from "./artifact.ts";
import type {
  ActorId,
  ArtifactId,
  DecisionId,
  EventId,
  IterationId,
  RunId,
} from "./ids.ts";
import type { SourceRunSpec } from "./run.ts";
import type { JsonObject } from "./json.ts";
import type {
  DecisionView,
  EventView,
  RunSpec,
  RunStatus,
} from "./run.ts";
import type { AttemptView, WorkOfferView } from "./work.ts";

export type ActorView = {
  readonly id: ActorId;
  readonly parentActorId?: ActorId;
  readonly logicalKey: string;
  readonly machine: string;
  readonly machineVersion: string;
  readonly state: string;
  readonly status: "accepting" | "active" | "done" | "failed";
  readonly snapshotNumber: number;
  readonly outputs: readonly ArtifactId[];
  readonly input: JsonObject;
  readonly context: JsonObject;
};

export type IterationView = {
  readonly id: IterationId;
  readonly actorId: ActorId;
  readonly ordinal: number;
  readonly parentManuscriptArtifactId?: ArtifactId;
  readonly openedEventId: EventId;
  readonly closedEventId?: EventId;
  readonly decisionId?: DecisionId;
};

export type SourceSubmissionView = {
  readonly sourceId: string;
  readonly source: SourceRunSpec;
  readonly submittedAt: string;
};

export type RunView = {
  readonly id: RunId;
  readonly kind: RunSpec["kind"];
  readonly status: RunStatus;
  readonly machineVersion: string;
  readonly parentRunId?: RunId;
  readonly headSequence: number;
  readonly actors: readonly ActorView[];
  readonly iterations: readonly IterationView[];
  readonly sourceSubmissions: readonly SourceSubmissionView[];
  readonly offers: readonly WorkOfferView[];
  readonly attempts: readonly AttemptView[];
  readonly artifacts: readonly ArtifactView[];
  readonly events: readonly EventView[];
  readonly decisions: readonly DecisionView[];
  readonly createdAt: string;
  readonly updatedAt: string;
};
