import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { deflateSync } from "node:zlib";

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

type ElkNode = { readonly id: string; readonly x?: number; readonly y?: number };
type ElkResult = { readonly children?: readonly ElkNode[]; readonly width?: number; readonly height?: number };
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
  const edges: GraphEdge[] = [];
  const groups: Array<{ readonly name: string; readonly y: number; readonly height: number }> = [];
  for (const projection of projections) {
    groups.push({ name: projection.name, y: cursor, height: projection.height });
    nodes.push(...projection.nodes.map((node) => ({ ...node, y: node.y + cursor })));
    edges.push(...projection.edges);
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
  return { html, svg, png: rasterOverview(width, height, groups, nodes), json };
}

export async function writeMachineTopology(destination: string): Promise<MachineTopologyExport> {
  const output = resolve(destination);
  const topology = await exportMachineTopology();
  await mkdir(output, { recursive: true });
  await Promise.all([
    writeFile(resolve(output, "machine-topology.html"), topology.html),
    writeFile(resolve(output, "machine-topology.svg"), topology.svg),
    writeFile(resolve(output, "machine-topology.png"), topology.png),
    writeFile(resolve(output, "machine-topology.json"), topology.json),
  ]);
  return topology;
}

async function layoutMachine(name: string, config: MachineConfig): Promise<{
  readonly name: string;
  readonly width: number;
  readonly height: number;
  readonly nodes: readonly PositionedNode[];
  readonly edges: readonly GraphEdge[];
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
      "elk.layered.spacing.nodeNodeBetweenLayers": "72",
      "elk.spacing.nodeNode": "28",
    },
    children: nodes.map((node) => ({ id: node.id, width: Math.max(128, node.label.length * 8 + 36), height: 44 })),
    edges: edges.map((edge, index) => ({ id: `${name}:edge:${index}`, sources: [edge.source], targets: [edge.target] })),
  });
  const positions = new Map((result.children ?? []).map((node) => [node.id, node]));
  return {
    name,
    width: result.width ?? 0,
    height: Math.max(result.height ?? 0, 64),
    nodes: nodes.map((node) => {
      const position = positions.get(node.id);
      return { ...node, x: (position?.x ?? 0) + 30, y: (position?.y ?? 0) + 28 };
    }),
    edges,
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
  edges: readonly GraphEdge[],
): string {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const groupSvg = groups.map((group) => `<g><rect class="group" x="12" y="${group.y - 26}" width="${width - 24}" height="${group.height + 50}" rx="12"/><text class="machine" x="28" y="${group.y - 6}">${escapeXml(group.name)}</text></g>`).join("");
  const edgeSvg = edges.map((edge) => {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (source === undefined || target === undefined) return "";
    const x1 = source.x + nodeWidth(source.label);
    const y1 = source.y + 22;
    const x2 = target.x;
    const y2 = target.y + 22;
    const middle = (x1 + x2) / 2;
    return `<path class="edge" d="M ${x1} ${y1} C ${middle} ${y1}, ${middle} ${y2}, ${x2} ${y2}" marker-end="url(#arrow)"/><text class="event" x="${middle}" y="${Math.min(y1, y2) - 5}">${escapeXml(edge.label)}</text>`;
  }).join("");
  const nodeSvg = nodes.map((node) => `<g data-machine="${escapeXml(node.machine)}" data-state="${escapeXml(node.label)}"><rect class="node ${node.final ? "final" : ""}" x="${node.x}" y="${node.y}" width="${nodeWidth(node.label)}" height="44" rx="7"/><text class="state" x="${node.x + 14}" y="${node.y + 27}">${escapeXml(node.label)}</text></g>`).join("");
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="title description">
<title id="title">Magazine XState machine topology</title><desc id="description">Generated from the implemented XState machine configs.</desc>
<style>text{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.group{fill:#f7f7fb;stroke:#b8bdd4;stroke-width:1.2}.machine{font-size:18px;font-weight:700;fill:#1e2450}.node{fill:#fff;stroke:#4a5aa7;stroke-width:1.4}.node.final{fill:#e7f8ed;stroke:#27854d}.state{font-size:13px;fill:#1b2040}.edge{fill:none;stroke:#6975aa;stroke-width:1.15}.event{font-size:10px;fill:#5a638d;text-anchor:middle;paint-order:stroke;stroke:#f7f7fb;stroke-width:4px;stroke-linejoin:round}</style>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#6975aa"/></marker></defs>${groupSvg}${edgeSvg}${nodeSvg}</svg>`;
}

function renderHtml(svg: string, json: string): string {
  return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Magazine XState topology</title><style>body{margin:0;background:#eceef7;color:#171a31;font:16px system-ui,sans-serif}header{padding:1rem 1.5rem;background:#171a31;color:#fff}p{max-width:75ch}main{overflow:auto;padding:1rem}svg{display:block;background:#fff;box-shadow:0 2px 20px #0002}.toolbar{position:fixed;right:1rem;top:1rem}button{padding:.5rem .75rem}</style><header><h1>Magazine XState topology</h1><p>This diagram is generated directly from the live machine configs. Hover a state to inspect its owning machine; use the SVG for scalable review and the PNG for a portable fallback.</p></header><div class="toolbar"><button onclick="document.documentElement.requestFullscreen?.()">Fullscreen</button></div><main>${svg}</main><script type="application/json" id="machine-topology">${escapeScript(json)}</script></html>`;
}

function rasterOverview(width: number, height: number, groups: readonly { readonly y: number; readonly height: number }[], nodes: readonly PositionedNode[]): Uint8Array {
  const scale = Math.min(1, 1800 / width, 5000 / height);
  const pixelWidth = Math.max(1, Math.ceil(width * scale));
  const pixelHeight = Math.max(1, Math.ceil(height * scale));
  const bytes = new Uint8Array(pixelWidth * pixelHeight * 4);
  for (let index = 0; index < bytes.length; index += 4) bytes.set([247, 248, 253, 255], index);
  for (const group of groups) fill(bytes, pixelWidth, pixelHeight, 8, Math.floor((group.y - 25) * scale), pixelWidth - 16, Math.ceil((group.height + 50) * scale), [229, 232, 246, 255]);
  for (const node of nodes) fill(bytes, pixelWidth, pixelHeight, Math.floor(node.x * scale), Math.floor(node.y * scale), Math.max(2, Math.ceil(nodeWidth(node.label) * scale)), Math.max(2, Math.ceil(44 * scale)), node.final ? [191, 235, 204, 255] : [112, 132, 205, 255]);
  return png(pixelWidth, pixelHeight, bytes);
}

function fill(bytes: Uint8Array, width: number, height: number, x: number, y: number, boxWidth: number, boxHeight: number, color: readonly number[]): void {
  for (let row = Math.max(0, y); row < Math.min(height, y + boxHeight); row += 1) for (let column = Math.max(0, x); column < Math.min(width, x + boxWidth); column += 1) bytes.set(color, (row * width + column) * 4);
}

function png(width: number, height: number, rgba: Uint8Array): Uint8Array {
  const scanlines = new Uint8Array(height * (width * 4 + 1));
  for (let row = 0; row < height; row += 1) scanlines[row * (width * 4 + 1)] = 0;
  for (let row = 0; row < height; row += 1) scanlines.set(rgba.subarray(row * width * 4, (row + 1) * width * 4), row * (width * 4 + 1) + 1);
  const signature = Uint8Array.from([137, 80, 78, 71, 13, 10, 26, 10]);
  return concat([signature, pngChunk("IHDR", Uint8Array.from([width >>> 24, width >>> 16, width >>> 8, width, height >>> 24, height >>> 16, height >>> 8, height, 8, 6, 0, 0, 0])), pngChunk("IDAT", deflateSync(scanlines)), pngChunk("IEND", new Uint8Array())]);
}

function pngChunk(type: string, data: Uint8Array): Uint8Array {
  const typeBytes = new TextEncoder().encode(type);
  const length = data.length;
  const chunk = new Uint8Array(length + 12);
  chunk.set([length >>> 24, length >>> 16, length >>> 8, length], 0);
  chunk.set(typeBytes, 4); chunk.set(data, 8);
  const checksum = crc32(chunk.subarray(4, 8 + length));
  chunk.set([checksum >>> 24, checksum >>> 16, checksum >>> 8, checksum], 8 + length);
  return chunk;
}

function crc32(bytes: Uint8Array): number { let value = 0xffffffff; for (const byte of bytes) { value ^= byte; for (let bit = 0; bit < 8; bit += 1) value = (value >>> 1) ^ (value & 1 ? 0xedb88320 : 0); } return (value ^ 0xffffffff) >>> 0; }
function concat(parts: readonly Uint8Array[]): Uint8Array { const length = parts.reduce((total, part) => total + part.length, 0); const output = new Uint8Array(length); let offset = 0; for (const part of parts) { output.set(part, offset); offset += part.length; } return output; }
function nodeWidth(label: string): number { return Math.max(128, label.length * 8 + 36); }
function escapeXml(value: string): string { return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;"); }
function escapeScript(value: string): string { return value.replaceAll("</", "<\\/"); }

if (import.meta.main) {
  const destination = process.argv[2] ?? "output/machine-topology";
  await writeMachineTopology(destination);
  process.stdout.write(`${resolve(destination)}\n`);
}
