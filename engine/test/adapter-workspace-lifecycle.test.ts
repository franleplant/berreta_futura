import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { access, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

import {
  AdapterWorkspaceOwner,
  createAdapterWorkspace,
} from "../executors/adapter-workspace.ts";

test("an adapter workspace owner releases attempt scratch idempotently", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-adapter-owner-"));
  try {
    const owner = new AdapterWorkspaceOwner(temporary);
    const workspace = await owner.create("attempt-one", "render-attempt-one");
    await access(workspace.root);

    await owner.release("attempt-one");
    await assert.rejects(access(workspace.root));
    await owner.release("attempt-one");
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("creating adapter scratch scavenges a workspace owned by a dead process", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mag-adapter-workspace-"));
  let child: ReturnType<typeof spawn> | undefined;
  try {
    const moduleUrl = pathToFileURL(
      join(import.meta.dirname, "../executors/adapter-workspace.ts"),
    ).href;
    const script = `
      import { createAdapterWorkspace } from ${JSON.stringify(moduleUrl)};
      const workspace = await createAdapterWorkspace(
        ${JSON.stringify(temporary)},
        "crashed-attempt",
      );
      process.stdout.write(workspace.root + "\\n");
      setInterval(() => undefined, 1000);
    `;
    child = spawn(process.execPath, ["--input-type=module", "--eval", script], {
      stdio: ["ignore", "pipe", "inherit"],
    });
    const crashedRoot = await firstLine(child.stdout);
    child.kill("SIGKILL");
    await new Promise<void>((resolveClose) => child?.once("close", () => resolveClose()));

    await createAdapterWorkspace(temporary, "replacement-attempt");

    await assert.rejects(access(crashedRoot));
  } finally {
    child?.kill("SIGKILL");
    await rm(temporary, { recursive: true, force: true });
  }
});

async function firstLine(stream: NodeJS.ReadableStream | null): Promise<string> {
  assert.ok(stream);
  return await new Promise<string>((resolveLine, rejectLine) => {
    let output = "";
    stream.setEncoding("utf8");
    stream.on("data", (chunk: string) => {
      output += chunk;
      const newline = output.indexOf("\n");
      if (newline >= 0) {
        resolveLine(output.slice(0, newline));
      }
    });
    stream.on("error", rejectLine);
  });
}
