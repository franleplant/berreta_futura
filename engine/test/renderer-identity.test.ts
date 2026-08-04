import assert from "node:assert/strict";
import { execFile as execFileCallback } from "node:child_process";
import { mkdir, mkdtemp, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { promisify } from "node:util";

import {
  computeRendererIdentity,
  hashRendererIdentityManifest,
  readVerifiedRendererIdentity,
} from "../workflows/renderer-identity.ts";

const execFile = promisify(execFileCallback);

async function fixture(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "mag-renderer-identity-"));
  await mkdir(join(root, "src", "magazine", "nested"), { recursive: true });
  await writeFile(join(root, "pyproject.toml"), "[project]\nname = 'magazine'\n");
  await writeFile(join(root, "uv.lock"), "version = 1\n");
  await writeFile(join(root, "src", "magazine", "main.py"), "print('one')\n");
  await writeFile(join(root, "src", "magazine", "nested", "helper.py"), "print('two')\n");
  await execFile("git", ["init", "-q", "-b", "main"], { cwd: root });
  await execFile("git", ["config", "user.email", "test@example.com"], { cwd: root });
  await execFile("git", ["config", "user.name", "Magazine Test"], { cwd: root });
  await execFile("git", ["add", "pyproject.toml", "uv.lock", "src/magazine"], { cwd: root });
  await execFile("git", ["commit", "-qm", "fixture"], { cwd: root });
  return root;
}

test("renderer identity paths equal the committed Git-tracked runtime closure", async () => {
  const root = await fixture();
  try {
    const identity = await computeRendererIdentity(root);
    const tracked = (await execFile("git", ["ls-files", "--", "pyproject.toml", "uv.lock", "src/magazine"], { cwd: root })).stdout
      .trim()
      .split("\n")
      .filter(Boolean)
      .sort();
    assert.deepEqual(identity.files.map((file) => file.path), [
      "pyproject.toml",
      "src/magazine/main.py",
      "src/magazine/nested/helper.py",
      "uv.lock",
    ]);
    assert.deepEqual(identity.files.map((file) => file.path), tracked);
    assert.equal(identity.graphHash.startsWith("sha256:"), true);
    assert.equal(identity.manifestHash.startsWith("sha256:"), true);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("renderer identity detects source and lockfile changes", async () => {
  const root = await fixture();
  try {
    const before = await computeRendererIdentity(root);
    await writeFile(join(root, "src", "magazine", "main.py"), "print('changed')\n");
    const sourceChanged = await computeRendererIdentity(root);
    assert.notEqual(sourceChanged.graphHash, before.graphHash);
    await writeFile(join(root, "uv.lock"), "version = 2\n");
    const lockChanged = await computeRendererIdentity(root);
    assert.notEqual(lockChanged.graphHash, sourceChanged.graphHash);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("renderer identity rejects an arbitrary untracked machine file", async () => {
  const root = await fixture();
  try {
    await writeFile(join(root, "src", "magazine", "machine.py"), "print('untracked')\n");
    await assert.rejects(
      computeRendererIdentity(root),
      /src\/magazine\/machine\.py/iu,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("verified renderer identity rejects stale manifests and symlinks", async () => {
  const root = await fixture();
  try {
    const identity = await computeRendererIdentity(root);
    const manifestPath = join(root, "identity.json");
    await writeFile(manifestPath, `${JSON.stringify(identity, null, 2)}\n`);
    assert.equal(await hashRendererIdentityManifest(root, "identity.json").then((hash) => hash.startsWith("sha256:")), true);
    await writeFile(join(root, "src", "magazine", "main.py"), "print('changed')\n");
    await assert.rejects(readVerifiedRendererIdentity(root, "identity.json"), /identity mismatch/iu);

    const symlinkRoot = await fixture();
    try {
      await symlink(join(symlinkRoot, "src", "magazine", "main.py"), join(symlinkRoot, "src", "magazine", "linked.py"));
      await assert.rejects(computeRendererIdentity(symlinkRoot), /src\/magazine\/linked\.py/iu);
    } finally {
      await rm(symlinkRoot, { recursive: true, force: true });
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("renderer identity is reproducible from a clean checkout", async () => {
  const root = await fixture();
  const cleanRoot = await mkdtemp(join(tmpdir(), "mag-renderer-identity-clean-"));
  try {
    const expected = await computeRendererIdentity(root);
    await execFile("git", ["clone", "-q", root, cleanRoot], { cwd: root });
    const actual = await computeRendererIdentity(cleanRoot);
    assert.deepEqual(actual.files, expected.files);
    assert.equal(actual.graphHash, expected.graphHash);
  } finally {
    await rm(root, { recursive: true, force: true });
    await rm(cleanRoot, { recursive: true, force: true });
  }
});
