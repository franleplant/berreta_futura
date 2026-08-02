import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { writeMachineTopology } from "../graph-export.ts";

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
    assert.deepEqual([...png.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  } finally {
    await rm(output, { recursive: true, force: true });
  }
});
