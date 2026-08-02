import type { Edge, Node } from "@xyflow/react";

import type { RunView } from "../contracts/index.ts";

export type RunFlow = {
  readonly nodes: readonly Node[];
  readonly edges: readonly Edge[];
};

export function projectRunFlow(view: RunView): RunFlow {
  const actorNodes: Node[] = view.actors.map((actor) => ({
    id: `actor:${actor.id}`,
    type: "default",
    position: { x: 0, y: 0 },
    data: {
      label: `${actor.logicalKey}\n${actor.state}`,
      kind: "actor",
      status: actor.status,
    },
    className: `actor actor-${actor.status}`,
  }));
  const offerNodes: Node[] = view.offers
    .map((offer) => ({
      id: `offer:${offer.id}`,
      type: "default",
      position: { x: 0, y: 0 },
      data: {
        label: `${offer.role}\n${offer.status}`,
        kind: "offer",
        status: offer.status,
      },
      className: `offer offer-${offer.status}`,
    }));
  const iterationNodes: Node[] = view.iterations.map((iteration) => ({
    id: `iteration:${iteration.id}`,
    type: "default",
    position: { x: 0, y: 0 },
    data: {
      label: `iteration ${iteration.ordinal}\n${iteration.closedEventId === undefined ? "open" : "closed"}`,
      kind: "iteration",
      status: iteration.closedEventId === undefined ? "open" : "closed",
    },
    className: `iteration iteration-${iteration.closedEventId === undefined ? "open" : "closed"}`,
  }));
  const artifactNodes: Node[] = view.artifacts.map((artifact) => ({
    id: `artifact:${artifact.id}`,
    type: "default",
    position: { x: 0, y: 0 },
    data: {
      label: `${artifact.kind}\n${artifact.id.slice(0, 18)}`,
      kind: "artifact",
      status: artifact.origin,
    },
    className: `artifact artifact-${artifact.origin}`,
  }));
  const decisionNodes: Node[] = view.decisions.map((decision) => ({
    id: `decision:${decision.id}`,
    type: "default",
    position: { x: 0, y: 0 },
    data: {
      label: `${decision.choice}\n${decision.principalId}`,
      kind: "decision",
      status: decision.authority,
    },
    className: `decision decision-${decision.authority}`,
  }));
  const actorEdges: Edge[] = view.actors.flatMap((actor) =>
    actor.parentActorId === undefined
      ? []
      : [{
          id: `parent:${actor.parentActorId}:${actor.id}`,
          source: `actor:${actor.parentActorId}`,
          target: `actor:${actor.id}`,
          type: "smoothstep",
        }],
  );
  const offerEdges: Edge[] = view.offers
    .map((offer) => ({
      id: `offer:${offer.actorId}:${offer.id}`,
      source: `actor:${offer.actorId}`,
      target: `offer:${offer.id}`,
      type: "smoothstep",
      animated: offer.status === "claimed",
    }));
  const iterationEdges: Edge[] = view.iterations.map((iteration) => ({
    id: `iteration:${iteration.actorId}:${iteration.id}`,
    source: `actor:${iteration.actorId}`,
    target: `iteration:${iteration.id}`,
    type: "smoothstep",
  }));
  const artifactEdges: Edge[] = view.artifacts.flatMap((artifact) => [
    ...artifact.parents.map((parent, index) => ({
      id: `lineage:${parent.artifactId}:${artifact.id}:${parent.relation}:${index}`,
      source: `artifact:${parent.artifactId}`,
      target: `artifact:${artifact.id}`,
      label: parent.relation,
      type: "smoothstep",
    })),
    ...(artifact.producingActorId === undefined
      ? []
      : [{
          id: `produced:${artifact.producingActorId}:${artifact.id}`,
          source: `actor:${artifact.producingActorId}`,
          target: `artifact:${artifact.id}`,
          type: "smoothstep",
        }]),
  ]);
  const decisionEdges: Edge[] = view.decisions.flatMap((decision) => [
    {
      id: `decision-actor:${decision.actorId}:${decision.id}`,
      source: `actor:${decision.actorId}`,
      target: `decision:${decision.id}`,
      type: "smoothstep",
    },
    ...(decision.artifactId === undefined
      ? []
      : [{
          id: `decision-artifact:${decision.id}:${decision.artifactId}`,
          source: `artifact:${decision.artifactId}`,
          target: `decision:${decision.id}`,
          type: "smoothstep",
        }]),
  ]);
  return {
    nodes: [
      ...actorNodes,
      ...iterationNodes,
      ...offerNodes,
      ...artifactNodes,
      ...decisionNodes,
    ],
    edges: [
      ...actorEdges,
      ...iterationEdges,
      ...offerEdges,
      ...artifactEdges,
      ...decisionEdges,
    ],
  };
}
