import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import ELK from "elkjs/lib/elk.bundled.js";

import "@xyflow/react/dist/style.css";
import "./styles.css";

import type { ArtifactView, RunView, WorkOfferView } from "../../contracts/index.ts";
import { projectRunFlow } from "../projections.ts";

type ElkNode = { readonly id: string; readonly x?: number; readonly y?: number };
type ElkResult = { readonly children?: readonly ElkNode[] };
type ElkConstructor = new () => {
  layout(graph: unknown): Promise<ElkResult>;
};
const elk = new (ELK as unknown as ElkConstructor)();

function runIdFromLocation(): string {
  return new URLSearchParams(window.location.search).get("run") ?? "";
}

async function layout(nodes: readonly Node[], edges: readonly Edge[]): Promise<Node[]> {
  const graph = await elk.layout({
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.layered.spacing.nodeNodeBetweenLayers": "80",
      "elk.spacing.nodeNode": "40",
    },
    children: nodes.map((node) => ({ id: node.id, width: 190, height: 72 })),
    edges: edges.map((edge) => ({
      id: edge.id,
      sources: [edge.source],
      targets: [edge.target],
    })),
  });
  const positions = new Map(
    (graph.children ?? []).map((node) => [node.id, { x: node.x ?? 0, y: node.y ?? 0 }]),
  );
  return nodes.map((node) => ({
    ...node,
    position: positions.get(node.id) ?? node.position,
  }));
}

function App(): React.JSX.Element {
  const [runId, setRunId] = useState(runIdFromLocation());
  const [view, setView] = useState<RunView | null>(null);
  const [nodes, setNodes] = useState<readonly Node[]>([]);
  const [edges, setEdges] = useState<readonly Edge[]>([]);
  const [error, setError] = useState("");

  const refresh = async (): Promise<void> => {
    if (!runId) {
      return;
    }
    try {
      const response = await fetch(`/api/runs/${encodeURIComponent(runId)}`);
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const next = (await response.json()) as RunView;
      const flow = projectRunFlow(next);
      setView(next);
      setEdges(flow.edges);
      setNodes(await layout(flow.nodes, flow.edges));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  };

  useEffect(() => {
    void refresh();
  }, [runId]);

  const activeOffers = useMemo(
    () =>
      view?.offers.filter(
        (offer) =>
          offer.status === "offered" &&
          offer.allowedWorkerCapabilities.includes("human"),
      ) ?? [],
    [view],
  );

  return (
    <main>
      <header>
        <div>
          <p className="eyebrow">Magazine execution</p>
          <h1>{view?.kind ?? "Run viewer"}</h1>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const url = new URL(window.location.href);
            url.searchParams.set("run", runId);
            window.history.replaceState({}, "", url);
            void refresh();
          }}
        >
          <input value={runId} onChange={(event) => setRunId(event.target.value)} placeholder="run id" />
          <button type="submit">Inspect</button>
        </form>
      </header>
      {error && <p className="error">{error}</p>}
      <section className="summary">
        <strong>{view?.status ?? "not loaded"}</strong>
        <span>head {view?.headSequence ?? 0}</span>
        <span>{view?.actors.length ?? 0} actors</span>
        <span>{view?.iterations.length ?? 0} iterations</span>
        <span>{activeOffers.length} open offers</span>
      </section>
      <div className="workspace">
        <section className="graph" aria-label="Run graph">
          <ReactFlow nodes={[...nodes]} edges={[...edges]} fitView nodesDraggable={false}>
            <MiniMap />
            <Controls />
            <Background gap={18} size={1} />
          </ReactFlow>
        </section>
        <aside>
          <h2>Human inbox</h2>
          {activeOffers.length === 0 ? (
            <p className="muted">No open offers.</p>
          ) : (
            activeOffers.map((offer) => (
              <OfferForm key={offer.id} offer={offer} afterAnswer={refresh} />
            ))
          )}
          {view !== null && <ArtifactInspector view={view} />}
          <h2>Attempts</h2>
          <ol className="events">
            {(view?.attempts ?? []).slice().reverse().map((attempt) => (
              <li key={attempt.id}>
                <span>{attempt.status}</span>
                <div>
                  <strong>{attempt.worker.principalId}</strong>
                  <small>{attempt.offerId}</small>
                </div>
              </li>
            ))}
          </ol>
          <h2>Unresolved findings</h2>
          <ul className="artifact-ids">
            {(view?.artifacts ?? [])
              .filter((artifact) => artifact.kind === "finding" || artifact.kind.endsWith("_review"))
              .map((artifact) => <li key={artifact.id}>{artifact.kind} / {artifact.id}</li>)}
          </ul>
          <h2>Iteration causes</h2>
          <ol className="events">
            {(view?.iterations ?? []).map((iteration) => {
              const opened = view?.events.find((event) => event.id === iteration.openedEventId);
              return (
                <li key={iteration.id}>
                  <span>{iteration.ordinal}</span>
                  <div>
                    <strong>{opened?.type ?? "opened"}</strong>
                    <small>{opened?.previousState ?? "initial iteration"}</small>
                  </div>
                </li>
              );
            })}
          </ol>
          <h2>Recent events</h2>
          <ol className="events">
            {(view?.events ?? []).slice(-20).reverse().map((event) => (
              <li key={event.id}>
                <span>{event.sequence}</span>
                <div><strong>{event.type}</strong><small>{event.nextState}</small></div>
              </li>
            ))}
          </ol>
          <h2>Decisions</h2>
          <ol className="events">
            {(view?.decisions ?? []).slice().reverse().map((decision) => (
              <li key={decision.id}>
                <span>{decision.authority}</span>
                <div>
                  <strong>{decision.choice}</strong>
                  <small>{decision.principalId}</small>
                </div>
              </li>
            ))}
          </ol>
          <h2>Retryable actors</h2>
          {(view?.actors.filter((actor) => isRetryableState(actor.state)) ?? []).map(
            (actor) => (
              <button
                className="retry-actor"
                key={actor.id}
                type="button"
                onClick={async () => {
                  const response = await fetch(
                    `/api/runs/${encodeURIComponent(view?.id ?? "")}/actors/${encodeURIComponent(actor.id)}/retry`,
                    {
                      method: "POST",
                      headers: { "content-type": "application/json" },
                      body: JSON.stringify({ expectedState: actor.state }),
                    },
                  );
                  if (!response.ok) {
                    throw new Error(await response.text());
                  }
                  await refresh();
                }}
              >
                Retry {actor.logicalKey}
              </button>
            ),
          )}
        </aside>
      </div>
    </main>
  );
}

function isRetryableState(state: string): boolean {
  return (
    state.endsWith("_failed") ||
    state.endsWith("_rejected") ||
    state === "rejected" ||
    state === "source_failed" ||
    state === "visual_changes_required"
  );
}

function OfferForm({
  offer,
  afterAnswer,
}: {
  readonly offer: WorkOfferView;
  readonly afterAnswer: () => Promise<void>;
}): React.JSX.Element {
  const [answer, setAnswer] = useState('{"choice":"approve"}');
  const [task, setTask] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    void fetch(artifactUrl(offer.runId, offer.taskArtifactId))
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(await response.text());
        }
        return await response.text();
      })
      .then((value) => {
        if (active) {
          setTask(value);
        }
      })
      .catch((cause: unknown) => {
        if (active) {
          setTask(cause instanceof Error ? cause.message : String(cause));
        }
      });
    return () => {
      active = false;
    };
  }, [offer.runId, offer.taskArtifactId]);
  return (
    <article className="offer-card">
      <strong>{offer.role}</strong>
      <small>{offer.actorKey} / {offer.state}</small>
      <details open>
        <summary>Decision request</summary>
        <pre>{task || "Loading exact request..."}</pre>
      </details>
      <details>
        <summary>Exact immutable inputs</summary>
        <ul className="artifact-ids">
          {offer.inputArtifacts.map((artifactId) => (
            <li key={artifactId}>{artifactId}</li>
          ))}
        </ul>
      </details>
      <textarea value={answer} onChange={(event) => setAnswer(event.target.value)} rows={5} />
      <button
        type="button"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            const result = JSON.parse(answer) as unknown;
            const response = await fetch(`/api/offers/${encodeURIComponent(offer.id)}/answer`, {
              method: "POST",
              headers: { "content-type": "application/json" },
              body: JSON.stringify({
                runId: offer.runId,
                expectedOfferId: offer.id,
                result,
              }),
            });
            if (!response.ok) {
              throw new Error(await response.text());
            }
            await afterAnswer();
          } finally {
            setBusy(false);
          }
        }}
      >
        Submit decision
      </button>
    </article>
  );
}

function ArtifactInspector({ view }: { readonly view: RunView }): React.JSX.Element {
  const comparable = view.artifacts.filter((artifact) => isTextArtifact(artifact));
  const images = view.artifacts.filter((artifact) => artifact.mediaType.startsWith("image/"));
  const [leftId, setLeftId] = useState(comparable[0]?.id ?? "");
  const [rightId, setRightId] = useState(comparable[1]?.id ?? comparable[0]?.id ?? "");
  const [texts, setTexts] = useState<readonly [string, string]>(["", ""]);

  useEffect(() => {
    if (!leftId || !rightId) {
      setTexts(["", ""]);
      return;
    }
    void Promise.all([
      fetch(artifactUrl(view.id, leftId)).then(async (response) => await response.text()),
      fetch(artifactUrl(view.id, rightId)).then(async (response) => await response.text()),
    ]).then(([left, right]) => setTexts([left, right]));
  }, [leftId, rightId, view.id]);

  return (
    <>
      {images.length > 0 && (
        <section>
          <h2>Art at original resolution</h2>
          <div className="art-grid">
            {images.map((artifact) => (
              <a
                href={artifactUrl(view.id, artifact.id)}
                key={artifact.id}
                rel="noreferrer"
                target="_blank"
              >
                <img alt={artifact.kind} loading="lazy" src={artifactUrl(view.id, artifact.id)} />
                <small>{artifact.kind}</small>
              </a>
            ))}
          </div>
        </section>
      )}
      {comparable.length > 0 && (
        <section>
          <h2>Manuscript and prompt comparison</h2>
          <div className="diff-selectors">
            <ArtifactSelect artifacts={comparable} value={leftId} onChange={setLeftId} />
            <ArtifactSelect artifacts={comparable} value={rightId} onChange={setRightId} />
          </div>
          <div className="text-diff">
            <pre>{textDiff(texts[0], texts[1])}</pre>
          </div>
        </section>
      )}
    </>
  );
}

function ArtifactSelect({
  artifacts,
  value,
  onChange,
}: {
  readonly artifacts: readonly ArtifactView[];
  readonly value: string;
  readonly onChange: (value: string) => void;
}): React.JSX.Element {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value)}>
      {artifacts.map((artifact) => (
        <option key={artifact.id} value={artifact.id}>
          {artifact.kind} / {artifact.id.slice(0, 12)}
        </option>
      ))}
    </select>
  );
}

function isTextArtifact(artifact: ArtifactView): boolean {
  return (
    artifact.mediaType.startsWith("text/") ||
    artifact.mediaType.includes("json") ||
    artifact.mediaType.includes("yaml")
  );
}

function textDiff(left: string, right: string): string {
  const before = left.split("\n");
  const after = right.split("\n");
  const lines: string[] = [];
  const count = Math.max(before.length, after.length);
  for (let index = 0; index < count; index += 1) {
    const previous = before[index];
    const next = after[index];
    if (previous === next) {
      lines.push(`  ${previous ?? ""}`);
    } else {
      if (previous !== undefined) {
        lines.push(`- ${previous}`);
      }
      if (next !== undefined) {
        lines.push(`+ ${next}`);
      }
    }
  }
  return lines.join("\n");
}

function artifactUrl(runId: string, artifactId: string): string {
  return `/api/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}`;
}

const root = document.getElementById("root");
if (root === null) {
  throw new Error("viewer root is missing");
}
createRoot(root).render(<App />);
