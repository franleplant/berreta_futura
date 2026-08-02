import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { writeMachineTopology } from "../graph-export.ts";
import {
  editionOrchestration,
  runtimeOrchestrationEdges,
} from "../machines/orchestration.ts";

test("machine topology export is generated from the actual XState configs", async () => {
  const output = await mkdtemp(join(tmpdir(), "mag-machine-topology-"));
  try {
    await writeMachineTopology(output);
    const [html, svg, json, png] = await Promise.all([
      readFile(join(output, "machine-topology.html"), "utf8"),
      readFile(join(output, "machine-topology.svg"), "utf8"),
      readFile(join(output, "machine-topology.json"), "utf8"),
      readFile(join(output, "machine-topology.png")),
    ]);
    for (const name of ["EditionMachine", "SourceMachine", "ArticleMachine", "EditorialMachine", "EditionReviewMachine", "TranslationMachine", "CoverArtMachine", "InteriorArtMachine", "RenderMachine", "ReleaseMachine"]) {
      assert.match(svg, new RegExp(name));
    }
    assert.match(svg, /awaiting_release_approval/);
    assert.match(svg, /inspecting/);
    assert.match(svg, /awaiting_visual_review/);
    assert.match(json, /"always"/);
    assert.match(html, /generated directly from the live machine configs/);
    const topology = JSON.parse(json) as { machines: Array<{ transitions: unknown[] }> };
    const transitionCount = topology.machines.reduce((count, machine) => count + machine.transitions.length, 0);
    assert.equal([...svg.matchAll(/<g class="transition-label"/g)].length, transitionCount);
    assert.ok(svg.indexOf('<g class="transition-label"') > svg.lastIndexOf('<path class="edge"'));
    assert.deepEqual([...png.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
    assert.ok(png.readUInt32BE(16) >= 2_500);
    assert.ok(png.readUInt32BE(20) >= 3_500);
    assert.ok(png.byteLength > 200_000);
  } finally {
    await rm(output, { recursive: true, force: true });
  }
});

test("the export includes a connected runtime orchestration overview", async () => {
  const output = await mkdtemp(join(tmpdir(), "mag-orchestration-topology-"));
  try {
    await writeMachineTopology(output);
    const detailed = JSON.parse(
      await readFile(join(output, "machine-topology.json"), "utf8"),
    ) as {
      readonly machines: readonly {
        readonly name: string;
        readonly transitions: readonly {
          readonly from: string;
          readonly to: string;
        }[];
      }[];
    };
    assert.equal(detailed.machines.length, 10);
    const machineForState = new Map(
      detailed.machines.flatMap((machine) =>
        machine.transitions.flatMap((transition) => [
          [transition.from, machine.name] as const,
          [transition.to, machine.name] as const,
        ]),
      ),
    );
    const crossMachineEdges = detailed.machines.flatMap((machine) =>
      machine.transitions.filter(
        (transition) =>
          machineForState.get(transition.from) !== machineForState.get(transition.to),
      ),
    );
    assert.equal(crossMachineEdges.length, 0);

    const [overviewJson, overviewSvg, overviewHtml, overviewPng] = await Promise.all([
      readFile(join(output, "magazine-orchestration.json"), "utf8"),
      readFile(join(output, "magazine-orchestration.svg"), "utf8"),
      readFile(join(output, "magazine-orchestration.html"), "utf8"),
      readFile(join(output, "magazine-orchestration.png")),
    ]);
    const overview = JSON.parse(overviewJson) as {
      readonly lifecycleOwner: string;
      readonly machines: readonly { readonly kind: string }[];
      readonly declarations: {
        readonly spawns: Readonly<Record<string, {
          readonly id: string;
          readonly child: string;
        }>>;
        readonly routes: Readonly<Record<string, { readonly id: string }>>;
        readonly joins: Readonly<Record<string, { readonly id: string }>>;
      };
      readonly edges: readonly {
        readonly id: string;
        readonly declarationId: string;
        readonly kind: string;
        readonly source: string;
        readonly target: string;
      }[];
    };
    assert.equal(overview.machines.length, 10);
    assert.equal(overview.lifecycleOwner, "edition");
    assert.deepEqual(overview.edges, runtimeOrchestrationEdges());
    const machineIds = new Set(overview.machines.map((machine) => machine.kind));
    assert.equal(machineIds.size, 10);
    assert.deepEqual(
      [...new Set(Object.values(overview.declarations.spawns).map(({ child }) => child))]
        .sort(),
      [...machineIds].filter((machine) => machine !== "edition").sort(),
    );
    assert.equal(Object.values(overview.declarations.spawns).length, machineIds.size - 1);
    for (const edge of overview.edges) {
      assert.ok(machineIds.has(edge.source), edge.source);
      assert.ok(machineIds.has(edge.target), edge.target);
      assert.ok(overviewSvg.includes(`data-edge="${edge.id}"`), edge.id);
    }
    assert.equal(
      [...overviewSvg.matchAll(/<g class="edge-label /g)].length,
      overview.edges.length,
    );
    const reachable = new Set(["edition"]);
    while (true) {
      const before = reachable.size;
      for (const edge of overview.edges) {
        if (reachable.has(edge.source)) reachable.add(edge.target);
        if (reachable.has(edge.target)) reachable.add(edge.source);
      }
      if (reachable.size === before) break;
    }
    assert.deepEqual([...reachable].sort(), [...machineIds].sort());
    const represented = new Set(overview.edges.map((edge) => edge.declarationId));
    for (const collection of [
      editionOrchestration.spawns,
      editionOrchestration.routes,
      editionOrchestration.joins,
    ]) {
      for (const declaration of Object.values(collection)) {
        assert.ok(represented.has(declaration.id), declaration.id);
        assert.ok(
          overviewSvg.includes(`data-declaration="${declaration.id}"`),
          declaration.id,
        );
      }
    }
    assert.match(overviewSvg, /EditionMachine/);
    for (const machine of editionOrchestration.machines) {
      assert.match(overviewSvg, new RegExp(machine.label));
    }
    assert.match(overviewSvg, /lifecycle owner and durable router/);
    assert.match(overviewSvg, /edition join:/);
    assert.match(overviewSvg, /edition route:/);
    assert.match(overviewHtml, /projected from the same typed declarations enforced by the runtime/);
    assert.deepEqual([...overviewPng.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
    assert.ok(overviewPng.readUInt32BE(16) > 1_000);
    assert.ok(overviewPng.readUInt32BE(20) > 1_000);
  } finally {
    await rm(output, { recursive: true, force: true });
  }
});
