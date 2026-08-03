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
    const topology = JSON.parse(json) as {
      machines: Array<{ name: string; states: string[]; transitions: unknown[] }>;
    };
    const editionStates = new Set(
      topology.machines.find((machine) => machine.name === "EditionMachine")?.states,
    );
    for (const state of [
      "verifying_bootstrap",
      "composition_ready",
      "composition_accepted_pending_durable",
      "composition_durable_bound",
      "migration_durable_backfill",
      "migration_waiting_durable_children",
      "render_reconciliation",
      "rendering",
      "bootstrap_render_approved",
      "awaiting_release_approval",
    ]) {
      assert.ok(editionStates.has(state), state);
    }
    for (const [machineName, states] of [
      ["ArticleMachine", ["accepted_pending_durable", "durable_bound"]],
      ["EditorialMachine", ["accepted_pending_durable", "durable_bound"]],
      ["CoverArtMachine", ["accepted_pending_durable", "durable_bound"]],
      ["InteriorArtMachine", ["accepted_pending_durable", "durable_bound"]],
      ["RenderMachine", ["measuring", "rendering", "inspecting", "awaiting_visual_review"]],
      ["ReleaseMachine", ["awaiting_release_approval", "released"]],
    ] as const) {
      const actual = new Set(
        topology.machines.find((machine) => machine.name === machineName)?.states,
      );
      for (const state of states) assert.ok(actual.has(state), `${machineName}:${state}`);
    }
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

test("one live machine can be exported as its own standalone graph", async () => {
  const output = await mkdtemp(join(tmpdir(), "mag-article-machine-"));
  try {
    await writeMachineTopology(output, "article");
    const [html, svg, json, png] = await Promise.all([
      readFile(join(output, "article-machine.html"), "utf8"),
      readFile(join(output, "article-machine.svg"), "utf8"),
      readFile(join(output, "article-machine.json"), "utf8"),
      readFile(join(output, "article-machine.png")),
    ]);
    assert.match(html, /generated directly from the live machine configs/);
    assert.match(svg, /ArticleMachine/);
    assert.match(svg, /stage_1_decision/);
    assert.match(svg, /accepted_pending_durable/);
    assert.match(svg, /entry: offerStage1/);
    assert.match(svg, /Parallel work: measure_article, worth judge,/);
    assert.match(svg, /mechanics judge/);
    assert.match(svg, /always \[stage1Blocking\]/);
    assert.match(svg, /WORK_COMPLETED \[writerCompleted\]/);
    assert.doesNotMatch(svg, /EditionMachine/);
    const topology = JSON.parse(json) as {
      readonly machines: readonly {
        readonly name: string;
        readonly states: readonly string[];
        readonly transitions: readonly unknown[];
      }[];
    };
    assert.equal(topology.machines.length, 1);
    assert.equal(topology.machines[0]?.name, "ArticleMachine");
    assert.ok(topology.machines[0]?.states.includes("drafting"));
    assert.ok((topology.machines[0]?.transitions.length ?? 0) > 20);
    assert.equal(
      [...svg.matchAll(/<g class="transition-label/g)].length,
      topology.machines[0]?.transitions.length,
    );
    assert.deepEqual([...png.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
    assert.ok(png.readUInt32BE(20) > png.readUInt32BE(16) * 2);
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
        readonly states: readonly string[];
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
      readonly editionBranches: readonly {
        readonly id: string;
        readonly label: string;
        readonly summary: string;
        readonly states: readonly string[];
      }[];
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
    assert.deepEqual(overview.editionBranches.map((branch) => branch.id), [
      "production",
      "bootstrap",
      "migration",
    ]);
    assert.deepEqual(overview.edges, runtimeOrchestrationEdges());
    const machineIds = new Set(overview.machines.map((machine) => machine.kind));
    assert.equal(machineIds.size, 10);
    assert.deepEqual(
      [...new Set(Object.values(overview.declarations.spawns).map(({ child }) => child))]
        .sort(),
      [...machineIds].filter((machine) => machine !== "edition").sort(),
    );
    assert.equal(Object.values(overview.declarations.spawns).length, machineIds.size - 1);
    for (const child of [
      "article",
      "editorial",
      "cover_art",
      "interior_art",
      "render",
      "release",
    ]) {
      assert.ok(
        overview.edges.some((edge) =>
          edge.kind === "spawn" && edge.source === "edition" && edge.target === child
        ),
        `EditionMachine spawn path to ${child}`,
      );
    }
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
    assert.match(overviewSvg, /sole lifecycle owner and durable router/);
    for (const branch of overview.editionBranches) {
      assert.ok(branch.states.every((state) =>
        detailed.machines
          .find((machine) => machine.name === "EditionMachine")
          ?.states?.includes(state)
      ), branch.id);
      assert.ok(overviewSvg.includes(`data-branch="${branch.id}"`), branch.id);
    }
    assert.match(overviewSvg, /produce: checkpoints -&gt; composition -&gt; fresh render -&gt; QA\/visual -&gt; release/);
    assert.match(overviewSvg, /bootstrap: verify composition -&gt; fresh render -&gt; QA\/visual -&gt; unreleased/);
    assert.match(overviewSvg, /migration: durable backfill -&gt; composition -&gt; reconciliation seam -&gt; fresh QA/);
    assert.equal(machineIds.has("coordinator"), false);
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
