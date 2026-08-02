import type {
  ArtifactId,
  ArtifactView,
  JsonObject,
  WorkAnswer,
  WorkClaim,
  WorkFailure,
  WorkOfferView,
  WorkerCapability,
  WorkerIdentity,
} from "../contracts/index.ts";

export interface ArtifactReader {
  readArtifact?(artifactId: ArtifactId): Promise<{
    readonly artifact: ArtifactView;
    readonly bytes: Uint8Array;
  }>;
  readBytes(artifactId: ArtifactId): Promise<Uint8Array>;
  readText(artifactId: ArtifactId): Promise<string>;
}

export type ExecutorContext = {
  readonly claim: WorkClaim;
  readonly offer: WorkOfferView;
  readonly artifacts: ArtifactReader;
  readonly signal: AbortSignal;
};

export interface Executor {
  readonly id: string;
  readonly worker: WorkerIdentity;
  readonly capabilities: readonly WorkerCapability[];
  accepts(offer: WorkOfferView): boolean;
  execute(context: ExecutorContext): Promise<WorkAnswer>;
  release?(context: ExecutorContext): Promise<void>;
}

export type ExecutorFailure = WorkFailure & {
  readonly executorId: string;
  readonly diagnostics?: JsonObject;
};

export class WorkUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "WorkUnavailableError";
  }
}
