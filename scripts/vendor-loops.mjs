import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const sourceDirectory = resolve(process.env.LOOPS_SOURCE_DIR ?? "/Users/franguijarro/code/loopsv2");
const requestedCommit = process.env.LOOPS_COMMIT ?? "44ffb8370eeb0ee85ba799dff6dbaa0b8e744b40";
const repositoryRoot = resolve(new URL("..", import.meta.url).pathname);

const status = execFileSync("git", ["status", "--porcelain"], { cwd: sourceDirectory, encoding: "utf8" });
if (status.trim() !== "") {
  throw new Error(`Loops source is dirty; refusing to vendor ${sourceDirectory}`);
}
const commit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: sourceDirectory, encoding: "utf8" }).trim();
if (commit !== requestedCommit) {
  throw new Error(`Loops source is ${commit}; expected pinned commit ${requestedCommit}`);
}
const nodeVersion = process.version;
const npmVersion = execFileSync("npm", ["--version"], { cwd: sourceDirectory, encoding: "utf8" }).trim();
const temporary = await mkdtemp(join(tmpdir(), "magazine-loops-vendor-"));
const destination = join(repositoryRoot, "vendor", "loops", commit);
try {
  await mkdir(temporary, { recursive: true, mode: 0o700 });
  execFileSync(
    "npm",
    ["pack", "--workspace", "@loops/core", "--workspace", "loops", "--workspace", "@loops/workflow", "--pack-destination", temporary],
    {
      cwd: sourceDirectory,
      stdio: "inherit",
      env: { ...process.env, npm_config_cache: join(temporary, "npm-cache") },
    },
  );
  await rm(destination, { recursive: true, force: true });
  await mkdir(destination, { recursive: true, mode: 0o755 });
  const packageFiles = ["loops-core-0.0.0.tgz", "loops-0.0.0.tgz", "loops-workflow-0.0.0.tgz"];
  const packageEntries = [];
  for (const file of packageFiles) {
    const source = join(temporary, file);
    const target = join(destination, file);
    const bytes = await readFile(source);
    await writeFile(target, bytes, { mode: 0o644 });
    const name = file.startsWith("loops-core") ? "@loops/core" : file.startsWith("loops-workflow") ? "@loops/workflow" : "loops";
    packageEntries.push({
      name,
      version: "0.0.0",
      file,
      sha256: createHash("sha256").update(bytes).digest("hex"),
    });
  }
  const remote = execFileSync("git", ["remote", "get-url", "origin"], { cwd: sourceDirectory, encoding: "utf8" }).trim();
  await writeFile(join(destination, "manifest.json"), `${JSON.stringify({
    source: { repository: remote, commit },
    toolchain: { node: nodeVersion, npm: npmVersion },
    packages: packageEntries,
  }, null, 2)}\n`, { mode: 0o644 });
  console.log(`Vendored Loops ${commit} into ${destination}`);
} finally {
  await rm(temporary, { recursive: true, force: true });
}
