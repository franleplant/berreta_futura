import type {
  ActorId,
  AnswerArtifact,
  ArtifactId,
  ArticleRunSpec,
  DecisionId,
  EditorialRunSpec,
  EditionRunSpec,
  IterationId,
  JsonObject,
  JsonValue,
  ModelPolicy,
  RegisteredArtSpec,
  ReleaseRunSpec,
  RenderRunSpec,
  RevisionId,
  SourceRunSpec,
  TranslationRunSpec,
  WorkOfferId,
  WorkRole,
  OfferRequirements,
  WorkerCapability,
} from "../contracts/index.ts";
import type { DurableLogicalItem, InputRevisionRef } from "../durable/types.ts";
import {
  initialTransition,
  transition,
  type AnyStateMachine,
  type EventFromLogic,
  type InputFrom,
  type SnapshotFrom,
  type SnapshotStatus,
  type StateValue,
} from "xstate";
import type {
  OrchestrationRouteId,
  OrchestrationSpawnId,
} from "./orchestration.ts";

export const MACHINE_SEMANTIC_VERSION = "1.0.0" as const;
export const DURABLE_EFFECT_ACTION = "durableEffect" as const;

export type MachineKind =
  | "article"
  | "cover_art"
  | "edition"
  | "edition_review"
  | "editorial"
  | "interior_art"
  | "release"
  | "render"
  | "source"
  | "translation";

export type MachineInputBase = {
  readonly actorId: ActorId;
  readonly logicalKey: string;
  readonly parentActorId?: ActorId;
};

export type EditionReviewRunSpec = {
  readonly editionId: string;
  readonly editionBrief: ArtifactId;
  readonly articleArtifacts: readonly {
    readonly articleId: string;
    readonly artifactId: ArtifactId;
  }[];
  readonly editorialArtifact: ArtifactId;
  readonly modelPolicy: ModelPolicy;
};

export type MachineSpawnSpec =
  | ArticleRunSpec
  | EditionReviewRunSpec
  | EditorialRunSpec
  | RegisteredArtSpec
  | ReleaseRunSpec
  | RenderRunSpec
  | SourceRunSpec
  | TranslationRunSpec;

export type CreateWorkOfferEffect = {
  readonly type: "create_work_offer";
  readonly actorId: ActorId;
  readonly actorKey: string;
  readonly state: string;
  readonly slot: string;
  readonly role: WorkRole;
  readonly subjectArtifactId?: ArtifactId;
  readonly iterationId?: IterationId;
  readonly iterationOrdinal?: number;
  readonly parentManuscriptArtifactId?: ArtifactId;
  readonly revisionId?: RevisionId;
  readonly inputArtifacts: readonly ArtifactId[];
  readonly taskArtifactId: ArtifactId;
  readonly contractVersion: string;
  /**
   * The authoritative eligibility policy for v3 offers. It is optional only
   * while replaying and migrating legacy effects that have the compatibility
   * field below.
   */
  readonly requirements?: OfferRequirements;
  /** @deprecated Compatibility field while stored v1 offer rows are migrated. */
  readonly allowedWorkerCapabilities: readonly WorkerCapability[];
};

export type SpawnActorEffect = {
  readonly type: "spawn_actor";
  readonly relationship: OrchestrationSpawnId;
  readonly parentActorId: ActorId;
  readonly machine: Exclude<MachineKind, "edition">;
  readonly logicalKey: string;
  readonly spec: MachineSpawnSpec;
};

export type SendActorEventEffect = {
  readonly type: "send_actor_event";
  readonly route: OrchestrationRouteId;
  readonly actorId: ActorId;
  readonly target:
    | { readonly actorId: ActorId }
    | { readonly childKey: string };
  readonly event: JsonObject & { readonly type: string };
};

export type RegisterArtifactEffect = {
  readonly type: "register_artifact";
  readonly actorId: ActorId;
  readonly slot: string;
  readonly artifact: AnswerArtifact;
};

/**
 * The machine identifies the accepted output and logical item. RunEngine
 * materializes the exact durable task from committed artifact/decision
 * lineage, reserving promotion and durable revision identities atomically.
 */
export type OpenDurableCheckpointEffect = {
  readonly type: "open_durable_checkpoint";
  readonly actorId: ActorId;
  readonly actorKey: string;
  readonly state: string;
  readonly logicalItem: DurableLogicalItem;
  readonly acceptedArtifactId: ArtifactId;
  readonly expectedParentRevisionId?: RevisionId;
  readonly inputRevisions?: readonly InputRevisionRef[];
};

export type RecordDecisionEffect = {
  readonly type: "record_decision";
  readonly actorId: ActorId;
  readonly iterationId?: IterationId;
  readonly choice: string;
  readonly authority: string;
  readonly artifactId?: ArtifactId;
  readonly details?: JsonObject;
};

export type CancelOfferEffect = {
  readonly type: "cancel_offer";
  readonly actorId: ActorId;
  readonly slot: string;
  readonly reason: string;
};

export type CompleteActorEffect = {
  readonly type: "complete_actor";
  readonly actorId: ActorId;
  readonly accepting: boolean;
  readonly outputs: readonly ArtifactId[];
  readonly result: JsonObject;
};

export type FailActorEffect = {
  readonly type: "fail_actor";
  readonly actorId: ActorId;
  readonly classification: string;
  readonly message: string;
  readonly details?: JsonObject;
};

export type MachineEffect =
  | CancelOfferEffect
  | CompleteActorEffect
  | CreateWorkOfferEffect
  | FailActorEffect
  | RecordDecisionEffect
  | OpenDurableCheckpointEffect
  | RegisterArtifactEffect
  | SendActorEventEffect
  | SpawnActorEffect;

export type ResultArtifactRef = {
  readonly artifactId: ArtifactId;
  readonly kind: string;
};

export type StartEvent = { readonly type: "START" };

export type WorkCompletedEvent = {
  readonly type: "WORK_COMPLETED";
  readonly slot: string;
  readonly offerId?: WorkOfferId;
  readonly artifacts: readonly ResultArtifactRef[];
  readonly result: JsonObject;
};

export type WorkFailedEvent = {
  readonly type: "WORK_FAILED";
  readonly slot: string;
  readonly classification: "canceled" | "permanent" | "retryable" | "timeout";
  readonly message: string;
};

export type ChildSpawnedEvent = {
  readonly type: "CHILD_SPAWNED";
  readonly relationship: OrchestrationSpawnId;
  readonly childActorId: ActorId;
  readonly childKey: string;
  readonly machine: Exclude<MachineKind, "edition">;
};

export type ChildStatusEvent = {
  readonly type: "CHILD_STATUS";
  readonly relationship: OrchestrationSpawnId;
  readonly childActorId: ActorId;
  readonly childKey: string;
  readonly status: "accepting" | "active" | "done" | "failed";
  readonly outputs: readonly ArtifactId[];
  readonly result: JsonObject;
};

export type RevisionRequestedEvent = {
  readonly type: "REVISION_REQUESTED";
  readonly findingArtifacts: readonly ArtifactId[];
  readonly rulingArtifacts?: readonly ArtifactId[];
  readonly reason: string;
};

export type CommonMachineEvent =
  | ChildSpawnedEvent
  | ChildStatusEvent
  | RevisionRequestedEvent
  | StartEvent
  | WorkCompletedEvent
  | WorkFailedEvent;

export type JsonMachineSnapshot = {
  readonly status: SnapshotStatus;
  readonly value: JsonValue;
  readonly context: JsonObject;
  readonly output?: JsonValue;
  readonly error?: JsonValue;
  readonly historyValue?: JsonObject;
  readonly children?: JsonObject;
};

export type MachineTransitionResult = {
  readonly snapshot: JsonMachineSnapshot;
  readonly effects: readonly MachineEffect[];
};

export type DurableEffectAction = {
  readonly type: typeof DURABLE_EFFECT_ACTION;
  readonly params: MachineEffect;
};

export function emitEffect(effect: MachineEffect): DurableEffectAction {
  return { type: DURABLE_EFFECT_ACTION, params: effect };
}

type EffectFactoryArgs = {
  readonly context: any;
  readonly event: any;
};

type EffectFactory = (
  args: EffectFactoryArgs,
) => readonly MachineEffect[];

type EffectActionImplementation = (
  args: EffectFactoryArgs,
  params: unknown,
) => void;

const effectFactoryMarker = Symbol("magazine.machineEffectFactory");

type MarkedEffectAction = EffectActionImplementation & {
  readonly [effectFactoryMarker]: EffectFactory;
};

export function emitEffects(factory: EffectFactory): EffectActionImplementation;
export function emitEffects(
  ...effects: readonly MachineEffect[]
): readonly DurableEffectAction[];
export function emitEffects(
  factoryOrEffect: EffectFactory | MachineEffect,
  ...remainingEffects: readonly MachineEffect[]
): EffectActionImplementation | readonly DurableEffectAction[] {
  if (typeof factoryOrEffect !== "function") {
    return [factoryOrEffect, ...remainingEffects].map(emitEffect);
  }
  const implementation = ((_args: EffectFactoryArgs, _params: unknown) => {
    // XState actor execution deliberately has no side effect here. Pure
    // transitions collect the marked factory from the executable action.
  }) as MarkedEffectAction;
  Object.defineProperty(implementation, effectFactoryMarker, {
    value: factoryOrEffect,
  });
  return implementation;
}

type ExecutableActionLike = {
  readonly type: string;
  readonly info?: unknown;
  readonly params?: unknown;
  readonly exec?: unknown;
};

function isMachineEffect(value: unknown): value is MachineEffect {
  if (typeof value !== "object" || value === null || !("type" in value)) {
    return false;
  }
  const type = (value as { readonly type: unknown }).type;
  return (
    type === "cancel_offer" ||
    type === "complete_actor" ||
    type === "create_work_offer" ||
    type === "fail_actor" ||
    type === "record_decision" ||
    type === "register_artifact" ||
    type === "send_actor_event" ||
    type === "spawn_actor"
  );
}

function collectEffects(actions: readonly ExecutableActionLike[]): MachineEffect[] {
  const effects: MachineEffect[] = [];
  for (const action of actions) {
    if (
      typeof action.exec === "function" &&
      effectFactoryMarker in action.exec
    ) {
      const marked = action.exec as MarkedEffectAction;
      const info = action.info as EffectFactoryArgs;
      effects.push(...marked[effectFactoryMarker](info));
      continue;
    }
    if (action.type !== DURABLE_EFFECT_ACTION) {
      continue;
    }
    if (!isMachineEffect(action.params)) {
      throw new TypeError("durableEffect action has an invalid effect payload");
    }
    effects.push(action.params);
  }
  return effects;
}

function jsonClone<Value>(value: Value): Value {
  return JSON.parse(JSON.stringify(value)) as Value;
}

function persistSnapshot<TMachine extends AnyStateMachine>(
  machine: TMachine,
  snapshot: SnapshotFrom<TMachine>,
): JsonMachineSnapshot {
  return jsonClone(machine.getPersistedSnapshot(snapshot)) as unknown as JsonMachineSnapshot;
}

function restoreSnapshot<TMachine extends AnyStateMachine>(
  machine: TMachine,
  snapshot: JsonMachineSnapshot,
): SnapshotFrom<TMachine> {
  const config: {
    value: StateValue;
    context: unknown;
    status: SnapshotStatus;
    historyValue?: unknown;
    output?: unknown;
    error?: unknown;
  } = {
    value: snapshot.value as StateValue,
    context: snapshot.context,
    status: snapshot.status,
  };
  if (snapshot.historyValue !== undefined) {
    config.historyValue = snapshot.historyValue;
  }
  if (snapshot.output !== undefined) {
    config.output = snapshot.output;
  }
  if (snapshot.error !== undefined) {
    config.error = snapshot.error;
  }
  return machine.resolveState(config as never) as SnapshotFrom<TMachine>;
}

export function initialMachineTransition<TMachine extends AnyStateMachine>(
  machine: TMachine,
  input: InputFrom<TMachine>,
): MachineTransitionResult {
  const [snapshot, actions] = initialTransition(machine, input);
  return {
    snapshot: persistSnapshot(machine, snapshot),
    effects: collectEffects(actions),
  };
}

export function transitionMachine<TMachine extends AnyStateMachine>(
  machine: TMachine,
  snapshot: JsonMachineSnapshot,
  event: EventFromLogic<TMachine>,
): MachineTransitionResult {
  const restored = restoreSnapshot(machine, snapshot);
  const [nextSnapshot, actions] = transition(machine, restored, event);
  return {
    snapshot: persistSnapshot(machine, nextSnapshot),
    effects: collectEffects(actions),
  };
}

export type RootMachineInput =
  | (MachineInputBase & { readonly kind: "article"; readonly spec: ArticleRunSpec })
  | (MachineInputBase & { readonly kind: "edition"; readonly spec: EditionRunSpec });

export type MachineDecisionReference = {
  readonly decisionId: DecisionId;
  readonly choice: string;
};
