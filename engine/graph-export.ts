import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

import { Resvg } from "@resvg/resvg-js";
import ELK from "elkjs/lib/elk.bundled.js";

import {
  articleMachine,
  coverArtMachine,
  editionMachine,
  editionReviewMachine,
  editorialMachine,
  interiorArtMachine,
  releaseMachine,
  renderMachine,
  sourceMachine,
  translationMachine,
} from "./machines/index.ts";
import {
  editionOrchestration,
  runtimeOrchestrationEdges,
  type RuntimeOrchestrationEdge,
} from "./machines/orchestration.ts";
import type { MachineKind } from "./machines/runtime.ts";

type ElkPoint = { readonly x: number; readonly y: number };
type ElkNode = { readonly id: string; readonly x?: number; readonly y?: number };
type ElkLabel = {
  readonly id?: string;
  readonly text?: string;
  readonly x?: number;
  readonly y?: number;
  readonly width?: number;
  readonly height?: number;
};
type ElkEdgeSection = {
  readonly startPoint: ElkPoint;
  readonly endPoint: ElkPoint;
  readonly bendPoints?: readonly ElkPoint[];
};
type ElkEdge = {
  readonly id: string;
  readonly labels?: readonly ElkLabel[];
  readonly sections?: readonly ElkEdgeSection[];
};
type ElkResult = {
  readonly children?: readonly ElkNode[];
  readonly edges?: readonly ElkEdge[];
  readonly width?: number;
  readonly height?: number;
};
type ElkConstructor = new () => { layout(graph: unknown): Promise<ElkResult> };
type MachineConfig = {
  readonly id?: string;
  readonly initial?: string;
  readonly states?: Record<string, StateConfig>;
};
type StateConfig = {
  readonly type?: string;
  readonly on?: Record<string, Transition | readonly Transition[]>;
  readonly always?: Transition | readonly Transition[];
};
type Transition = string | { readonly target?: string };
type GraphNode = { readonly id: string; readonly label: string; readonly machine: string; readonly final: boolean };
type GraphEdge = { readonly source: string; readonly target: string; readonly label: string };
type PositionedNode = GraphNode & { readonly x: number; readonly y: number };
type PositionedEdge = GraphEdge & {
  readonly labelBox: { readonly x: number; readonly y: number; readonly width: number; readonly height: number };
  readonly sections: readonly (readonly ElkPoint[])[];
};

const machinePadding = { x: 30, y: 28 } as const;
const eventLabelHeight = 18;

const elk = new (ELK as unknown as ElkConstructor)();

const machines = [
  ["EditionMachine", editionMachine],
  ["SourceMachine", sourceMachine],
  ["ArticleMachine", articleMachine],
  ["EditorialMachine", editorialMachine],
  ["EditionReviewMachine", editionReviewMachine],
  ["TranslationMachine", translationMachine],
  ["CoverArtMachine", coverArtMachine],
  ["InteriorArtMachine", interiorArtMachine],
  ["RenderMachine", renderMachine],
  ["ReleaseMachine", releaseMachine],
] as const;

export type MachineTopologyExport = {
  readonly html: string;
  readonly svg: string;
  readonly png: Uint8Array;
  readonly json: string;
};

export type MagazineOrchestrationExport = MachineTopologyExport;

/**
 * Projects the actual XState machine configs. No parallel diagram definition
 * exists: states and transitions are read from the same machine objects the
 * durable driver transitions at runtime.
 */
export async function exportMachineTopology(): Promise<MachineTopologyExport> {
  const projections = await Promise.all(machines.map(async ([name, machine]) => {
    const config = machine.config as unknown as MachineConfig;
    return layoutMachine(name, config);
  }));
  const width = Math.max(...projections.map((projection) => projection.width), 920);
  let cursor = 70;
  const nodes: PositionedNode[] = [];
  const edges: PositionedEdge[] = [];
  const groups: Array<{ readonly name: string; readonly y: number; readonly height: number }> = [];
  for (const projection of projections) {
    groups.push({ name: projection.name, y: cursor, height: projection.height });
    nodes.push(...projection.nodes.map((node) => ({ ...node, y: node.y + cursor })));
    edges.push(...projection.edges.map((edge) => ({
      ...edge,
      labelBox: { ...edge.labelBox, y: edge.labelBox.y + cursor },
      sections: edge.sections.map((section) => section.map((point) => ({ ...point, y: point.y + cursor }))),
    })));
    cursor += projection.height + 86;
  }
  const height = cursor;
  const svg = renderSvg(width, height, groups, nodes, edges);
  const json = JSON.stringify({
    schemaVersion: 1,
    description: "Generated from live XState machine.config state topology.",
    machines: projections.map((projection) => ({
      name: projection.name,
      states: projection.nodes.map((node) => node.label),
      transitions: projection.edges.map((edge) => ({ from: edge.source, to: edge.target, event: edge.label })),
    })),
  }, null, 2) + "\n";
  const html = renderHtml(svg, json);
  return { html, svg, png: rasterizeSvg(svg, width), json };
}

export async function writeMachineTopology(destination: string): Promise<MachineTopologyExport> {
  const output = resolve(destination);
  const [topology, orchestration] = await Promise.all([
    exportMachineTopology(),
    exportMagazineOrchestration(),
  ]);
  await mkdir(output, { recursive: true });
  await Promise.all([
    writeFile(resolve(output, "machine-topology.html"), topology.html),
    writeFile(resolve(output, "machine-topology.svg"), topology.svg),
    writeFile(resolve(output, "machine-topology.png"), topology.png),
    writeFile(resolve(output, "machine-topology.json"), topology.json),
    writeFile(resolve(output, "magazine-orchestration.html"), orchestration.html),
    writeFile(resolve(output, "magazine-orchestration.svg"), orchestration.svg),
    writeFile(resolve(output, "magazine-orchestration.png"), orchestration.png),
    writeFile(resolve(output, "magazine-orchestration.json"), orchestration.json),
  ]);
  return topology;
}

/**
 * Renders the cross-machine lifecycle as a separate overview. Every edge is
 * projected from a declaration consumed by EditionMachine or RunEngine.
 */
export async function exportMagazineOrchestration(): Promise<MagazineOrchestrationExport> {
  const declaredEdges = runtimeOrchestrationEdges();
  const nodeWidth = 250;
  const nodeHeight = 82;
  const labels = new Map(declaredEdges.map((edge) => [edge.id, overviewEdgeLabel(edge)]));
  const result = await elk.layout({
    id: "magazine-orchestration",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.edgeLabels.inline": "false",
      "elk.layered.spacing.nodeNodeBetweenLayers": "230",
      "elk.layered.spacing.edgeEdgeBetweenLayers": "28",
      "elk.layered.spacing.edgeNodeBetweenLayers": "38",
      "elk.spacing.nodeNode": "90",
      "elk.spacing.edgeEdge": "20",
      "elk.spacing.edgeNode": "32",
      "elk.spacing.edgeLabel": "14",
    },
    children: editionOrchestration.machines.map((machine) => ({
      id: machine.kind,
      width: nodeWidth,
      height: nodeHeight,
      layoutOptions: machine.kind === "edition"
        ? { "elk.layered.layering.layerConstraint": "FIRST" }
        : undefined,
    })),
    edges: declaredEdges.map((edge) => ({
      id: edge.id,
      sources: [edge.source],
      targets: [edge.target],
      labels: [{
        id: `${edge.id}:label`,
        text: labels.get(edge.id),
        width: Math.max(88, (labels.get(edge.id)?.length ?? 0) * 7 + 16),
        height: eventLabelHeight,
        layoutOptions: { "elk.edgeLabels.placement": "CENTER" },
      }],
    })),
  });
  const padding = 72;
  const width = Math.ceil((result.width ?? 0) + padding * 2);
  const height = Math.ceil((result.height ?? 0) + padding * 2);
  const positions = new Map((result.children ?? []).map((node) => [node.id, node]));
  const routed = new Map((result.edges ?? []).map((edge) => [edge.id, edge]));
  const svg = renderOrchestrationSvg(
    width,
    height,
    nodeWidth,
    nodeHeight,
    padding,
    positions,
    routed,
    declaredEdges,
    labels,
  );
  const json = JSON.stringify({
    schemaVersion: 1,
    description: "Connected overview projected from runtime-enforced orchestration declarations.",
    lifecycleOwner: "edition",
    machines: editionOrchestration.machines,
    declarations: {
      spawns: editionOrchestration.spawns,
      routes: editionOrchestration.routes,
      joins: editionOrchestration.joins,
    },
    edges: declaredEdges,
  }, null, 2) + "\n";
  const html = renderOrchestrationHtml(svg, json);
  return { html, svg, png: rasterizeSvg(svg, width), json };
}

async function layoutMachine(name: string, config: MachineConfig): Promise<{
  readonly name: string;
  readonly width: number;
  readonly height: number;
  readonly nodes: readonly PositionedNode[];
  readonly edges: readonly PositionedEdge[];
}> {
  const states = config.states ?? {};
  const nodes = Object.entries(states).map(([state, definition]) => ({
    id: `${name}:${state}`,
    label: state,
    machine: name,
    final: definition.type === "final",
  }));
  const edges = Object.entries(states).flatMap(([state, definition]) => transitions(name, state, definition));
  const result = await elk.layout({
    id: name,
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.edgeLabels.inline": "false",
      "elk.layered.edgeLabels.sideSelection": "SMART_UP",
      "elk.layered.edgeLabels.centerLabelPlacementStrategy": "SPACE_EFFICIENT_LAYER",
      "elk.layered.spacing.nodeNodeBetweenLayers": "140",
      "elk.layered.spacing.edgeEdgeBetweenLayers": "18",
      "elk.layered.spacing.edgeNodeBetweenLayers": "24",
      "elk.spacing.nodeNode": "58",
      "elk.spacing.edgeEdge": "14",
      "elk.spacing.edgeNode": "20",
      "elk.spacing.edgeLabel": "10",
      "elk.spacing.labelLabel": "14",
    },
    children: nodes.map((node) => ({ id: node.id, width: Math.max(128, node.label.length * 8 + 36), height: 44 })),
    edges: edges.map((edge, index) => ({
      id: `${name}:edge:${index}`,
      sources: [edge.source],
      targets: [edge.target],
      labels: [{
        id: `${name}:edge:${index}:label`,
        text: edge.label,
        width: eventWidth(edge.label),
        height: eventLabelHeight,
        layoutOptions: { "elk.edgeLabels.placement": "CENTER" },
      }],
    })),
  });
  const positions = new Map((result.children ?? []).map((node) => [node.id, node]));
  const routedEdges = new Map((result.edges ?? []).map((edge) => [edge.id, edge]));
  return {
    name,
    width: (result.width ?? 0) + machinePadding.x * 2,
    height: Math.max((result.height ?? 0) + machinePadding.y * 2, 64),
    nodes: nodes.map((node) => {
      const position = positions.get(node.id);
      return { ...node, x: (position?.x ?? 0) + machinePadding.x, y: (position?.y ?? 0) + machinePadding.y };
    }),
    edges: edges.map((edge, index) => positionEdge(name, index, edge, routedEdges.get(`${name}:edge:${index}`))),
  };
}

function positionEdge(name: string, index: number, edge: GraphEdge, routed: ElkEdge | undefined): PositionedEdge {
  const label = routed?.labels?.[0];
  if (label?.x === undefined || label.y === undefined || label.width === undefined || label.height === undefined) {
    throw new Error(`ELK did not position the label for ${name} transition ${index} (${edge.label})`);
  }
  const sections = routed?.sections;
  if (sections === undefined || sections.length === 0) {
    throw new Error(`ELK did not route ${name} transition ${index} (${edge.label})`);
  }
  return {
    ...edge,
    labelBox: {
      x: label.x + machinePadding.x,
      y: label.y + machinePadding.y,
      width: label.width,
      height: label.height,
    },
    sections: sections.map((section) => [section.startPoint, ...(section.bendPoints ?? []), section.endPoint]
      .map((point) => ({ x: point.x + machinePadding.x, y: point.y + machinePadding.y }))),
  };
}

function transitions(machine: string, source: string, definition: StateConfig): GraphEdge[] {
  const result: GraphEdge[] = [];
  for (const [event, transition] of Object.entries(definition.on ?? {})) {
    for (const target of targets(transition)) result.push(edge(machine, source, target, event));
  }
  for (const target of targets(definition.always)) result.push(edge(machine, source, target, "always"));
  return result;
}

function targets(value: Transition | readonly Transition[] | undefined): readonly string[] {
  if (value === undefined) return [];
  const items = Array.isArray(value) ? value : [value];
  return items.flatMap((item) => {
    const target = typeof item === "string" ? item : item.target;
    return target === undefined ? [] : [target.replace(/^\./, "").split(".")[0] ?? target];
  });
}

function edge(machine: string, source: string, target: string, label: string): GraphEdge {
  return { source: `${machine}:${source}`, target: `${machine}:${target}`, label };
}

function renderSvg(
  width: number,
  height: number,
  groups: readonly { readonly name: string; readonly y: number; readonly height: number }[],
  nodes: readonly PositionedNode[],
  edges: readonly PositionedEdge[],
): string {
  const groupSvg = groups.map((group) => `<g><rect class="group" x="12" y="${group.y - 26}" width="${width - 24}" height="${group.height + 50}" rx="12"/><text class="machine" x="28" y="${group.y - 6}">${escapeXml(group.name)}</text></g>`).join("");
  const edgePathSvg = edges.flatMap((edge) => edge.sections
    .map((section) => `<path class="edge" d="${polylinePath(section)}" marker-end="url(#arrow)"/>`)).join("");
  const edgeLabelSvg = edges.map((edge) => {
    const { x, y, width: labelWidth, height: labelHeight } = edge.labelBox;
    return `<g class="transition-label" data-event="${escapeXml(edge.label)}"><rect class="event-bg" x="${x - 5}" y="${y - 3}" width="${labelWidth + 10}" height="${labelHeight + 6}" rx="4"/><text class="event" x="${x + labelWidth / 2}" y="${y + 13}">${escapeXml(edge.label)}</text></g>`;
  }).join("");
  const nodeSvg = nodes.map((node) => `<g data-machine="${escapeXml(node.machine)}" data-state="${escapeXml(node.label)}"><rect class="node ${node.final ? "final" : ""}" x="${node.x}" y="${node.y}" width="${nodeWidth(node.label)}" height="44" rx="7"/><text class="state" x="${node.x + 14}" y="${node.y + 27}">${escapeXml(node.label)}</text></g>`).join("");
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="title description">
<title id="title">Magazine XState machine topology</title><desc id="description">Generated from the implemented XState machine configs.</desc>
<style>text{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.group{fill:#f7f7fb;stroke:#b8bdd4;stroke-width:1.2}.machine{font-size:18px;font-weight:700;fill:#1e2450}.node{fill:#fff;stroke:#4a5aa7;stroke-width:1.4}.node.final{fill:#e7f8ed;stroke:#27854d}.state{font-size:13px;fill:#1b2040}.edge{fill:none;stroke:#6975aa;stroke-width:1.15}.event-bg{fill:#eef1ff;stroke:#c9d0f0;stroke-width:1}.event{font-size:11px;font-weight:600;fill:#46517f;text-anchor:middle}</style>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#6975aa"/></marker></defs>${groupSvg}${edgePathSvg}${nodeSvg}${edgeLabelSvg}</svg>`;
}

function renderHtml(svg: string, json: string): string {
  return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Magazine XState topology</title><style>body{margin:0;background:#eceef7;color:#171a31;font:16px system-ui,sans-serif}header{padding:1rem 1.5rem;background:#171a31;color:#fff}p{max-width:75ch}main{overflow:auto;padding:1rem}svg{display:block;background:#fff;box-shadow:0 2px 20px #0002}.toolbar{position:fixed;right:1rem;top:1rem}button{padding:.5rem .75rem}</style><header><h1>Magazine XState topology</h1><p>This diagram is generated directly from the live machine configs. Hover a state to inspect its owning machine; use the SVG for scalable review and the PNG for a portable fallback.</p></header><div class="toolbar"><button onclick="document.documentElement.requestFullscreen?.()">Fullscreen</button></div><main>${svg}</main><script type="application/json" id="machine-topology">${escapeScript(json)}</script></html>`;
}

function overviewEdgeLabel(edge: RuntimeOrchestrationEdge): string {
  const name = edge.declarationId
    .replace(/^edition\.(spawn|route|join)\./, "")
    .replaceAll("_", " ");
  return edge.kind === "completion"
    ? `status: ${name}`
    : edge.kind === "join"
      ? `edition join: ${edge.label.split(" readiness:")[0]} to ${edge.target.replaceAll("_", " ")}`
      : edge.kind === "route"
        ? `edition route: ${name}`
      : `${edge.kind}: ${name}`;
}

function renderOrchestrationSvg(
  width: number,
  height: number,
  nodeWidth: number,
  nodeHeight: number,
  padding: number,
  positions: ReadonlyMap<string, ElkNode>,
  routed: ReadonlyMap<string, ElkEdge>,
  edges: readonly RuntimeOrchestrationEdge[],
  labels: ReadonlyMap<string, string>,
): string {
  const edgePaths = edges.map((edge) => {
    const sections = routed.get(edge.id)?.sections;
    if (sections === undefined || sections.length === 0) {
      throw new Error(`ELK did not route orchestration edge ${edge.id}`);
    }
    return sections.map((section) => {
      const points = [section.startPoint, ...(section.bendPoints ?? []), section.endPoint]
        .map((point) => ({ x: point.x + padding, y: point.y + padding }));
      return `<path class="edge ${edge.kind}" data-declaration="${escapeXml(edge.declarationId)}" d="${polylinePath(points)}" marker-end="url(#arrow-${edge.kind})"/>`;
    }).join("");
  }).join("");
  const nodes = editionOrchestration.machines.map((machine) => {
    const position = positions.get(machine.kind);
    if (position?.x === undefined || position.y === undefined) {
      throw new Error(`ELK did not position orchestration machine ${machine.kind}`);
    }
    const x = position.x + padding;
    const y = position.y + padding;
    const owner = machine.kind === "edition";
    return `<g class="machine-node ${owner ? "owner" : "child"}" data-machine="${machine.kind}"><rect x="${x}" y="${y}" width="${nodeWidth}" height="${nodeHeight}" rx="12"/><text class="machine-title" x="${x + 18}" y="${y + 30}">${escapeXml(machine.label)}</text><text class="machine-kind" x="${x + 18}" y="${y + 55}">${escapeXml(owner ? "lifecycle owner and durable router" : machine.responsibility)}</text></g>`;
  }).join("");
  const edgeLabels = edges.map((edge) => {
    const label = routed.get(edge.id)?.labels?.[0];
    if (label?.x === undefined || label.y === undefined || label.width === undefined || label.height === undefined) {
      throw new Error(`ELK did not position orchestration label ${edge.id}`);
    }
    const x = label.x + padding;
    const y = label.y + padding;
    const text = labels.get(edge.id) ?? edge.kind;
    return `<g class="edge-label ${edge.kind}" data-edge="${escapeXml(edge.id)}"><title>${escapeXml(edge.label)}</title><rect x="${x - 5}" y="${y - 3}" width="${label.width + 10}" height="${label.height + 6}" rx="4"/><text x="${x + label.width / 2}" y="${y + 13}">${escapeXml(text)}</text></g>`;
  }).join("");
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="orchestration-title orchestration-description">
<title id="orchestration-title">Magazine runtime orchestration</title><desc id="orchestration-description">EditionMachine owns spawning, durable status return, joins, and feedback routes across all ten machines.</desc>
<style>text{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.machine-node rect{fill:#fff;stroke:#52618f;stroke-width:1.6}.machine-node.owner rect{fill:#1d2755;stroke:#101735;stroke-width:2.6}.machine-title{font-size:16px;font-weight:750;fill:#1a2142}.owner .machine-title{fill:#fff}.machine-kind{font-size:9.5px;fill:#657092}.owner .machine-kind{fill:#cfd7ff}.edge{fill:none;stroke-width:1.65;opacity:.9}.edge.spawn{stroke:#355fcb}.edge.completion{stroke:#58708e}.edge.join{stroke:#17845d;stroke-dasharray:7 4}.edge.route{stroke:#bd4c65;stroke-width:2}.edge-label rect{fill:#fff;stroke-width:1}.edge-label text{font-size:10px;font-weight:650;text-anchor:middle}.edge-label.spawn rect{stroke:#9bb4ef}.edge-label.completion rect{stroke:#aeb9c8}.edge-label.join rect{stroke:#7ec8ac}.edge-label.route rect{stroke:#e5a2b1}</style>
<defs>${(["spawn", "completion", "join", "route"] as const).map((kind) => `<marker id="arrow-${kind}" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="${kind === "spawn" ? "#355fcb" : kind === "completion" ? "#58708e" : kind === "join" ? "#17845d" : "#bd4c65"}"/></marker>`).join("")}</defs>
<rect width="100%" height="100%" fill="#f5f7fc"/>${edgePaths}${nodes}${edgeLabels}</svg>`;
}

function renderOrchestrationHtml(svg: string, json: string): string {
  return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Magazine runtime orchestration</title><style>body{margin:0;background:#e9edf7;color:#171a31;font:16px system-ui,sans-serif}header{padding:1rem 1.5rem;background:#171a31;color:#fff}p{max-width:82ch}main{overflow:auto;padding:1rem}svg{display:block;background:#fff;box-shadow:0 2px 20px #0002}.legend{display:flex;gap:1rem;flex-wrap:wrap}.legend span{font:13px ui-monospace,monospace}</style><header><h1>Magazine runtime orchestration</h1><p>EditionMachine is the lifecycle owner. This connected overview is projected from the same typed declarations enforced by the runtime. The detailed state topology remains in the machine-topology files.</p><div class="legend"><span>blue: spawn</span><span>gray: child status</span><span>green: join or dependency</span><span>red: feedback route</span></div></header><main>${svg}</main><script type="application/json" id="magazine-orchestration">${escapeScript(json)}</script></html>`;
}

function rasterizeSvg(svg: string, width: number): Uint8Array {
  const renderer = new Resvg(svg, {
    fitTo: { mode: "width", value: Math.ceil(width) },
    font: {
      defaultFontFamily: "monospace",
      loadSystemFonts: true,
    },
  });
  return renderer.render().asPng();
}

function nodeWidth(label: string): number { return Math.max(128, label.length * 8 + 36); }
function eventWidth(label: string): number { return Math.max(46, label.length * 7 + 12); }
function polylinePath(points: readonly ElkPoint[]): string {
  const [first, ...rest] = points;
  if (first === undefined) throw new Error("Cannot render an empty ELK edge section");
  return `M ${first.x} ${first.y}${rest.map((point) => ` L ${point.x} ${point.y}`).join("")}`;
}
function escapeXml(value: string): string { return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;"); }
function escapeScript(value: string): string { return value.replaceAll("</", "<\\/"); }

if (import.meta.main) {
  const destination = process.argv[2] ?? "output/machine-topology";
  await writeMachineTopology(destination);
  process.stdout.write(`${resolve(destination)}\n`);
}
