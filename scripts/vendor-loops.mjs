import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const sourceDirectory = resolve(process.env.LOOPS_SOURCE_DIR ?? "/Users/franguijarro/code/loopsv2");
const requestedCommit = process.env.LOOPS_COMMIT ?? "19f03c7ba2c1f21062891aaa1f0213fb514b6631";
const repositoryRoot = resolve(new URL("..", import.meta.url).pathname);

const status = execFileSync("git", ["status", "--porcelain"], { cwd: sourceDirectory, encoding: "utf8" });
if (status.trim() !== "") {
  throw new Error(`Loops source is dirty; refusing to vendor ${sourceDirectory}`);
}
const commit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: sourceDirectory, encoding: "utf8" }).trim();
const expectedCommit = execFileSync("git", ["rev-parse", requestedCommit], { cwd: sourceDirectory, encoding: "utf8" }).trim();
if (commit !== expectedCommit) {
  throw new Error(`Loops source is ${commit}; expected pinned commit ${expectedCommit}`);
}
const nodeVersion = process.version;
const npmVersion = execFileSync("npm", ["--version"], { cwd: sourceDirectory, encoding: "utf8" }).trim();
const temporary = await mkdtemp(join(tmpdir(), "magazine-loops-vendor-"));
const destination = join(repositoryRoot, "vendor", "loops", commit);
try {
  await mkdir(temporary, { recursive: true, mode: 0o700 });
  const packedOutput = execFileSync(
    "npm",
    ["pack", "--workspace", "@loops/core", "--workspace", "loops", "--workspace", "@loops/workflow", "--pack-destination", temporary, "--json"],
    {
      cwd: sourceDirectory,
      encoding: "utf8",
      env: { ...process.env, npm_config_cache: join(temporary, "npm-cache") },
    },
  );
  await rm(destination, { recursive: true, force: true });
  await mkdir(destination, { recursive: true, mode: 0o755 });
  const packed = JSON.parse(packedOutput);
  if (!Array.isArray(packed) || packed.length !== 3) {
    throw new Error("Loops npm pack did not return exactly the three expected packages");
  }
  const packageEntries = [];
  for (const packageInfo of packed) {
    const name = packageInfo.name;
    const version = packageInfo.version;
    const file = packageInfo.filename;
    if (
      (name !== "@loops/core" && name !== "loops" && name !== "@loops/workflow")
      || typeof version !== "string"
      || typeof file !== "string"
      || !/^[A-Za-z0-9._-]+\.tgz$/u.test(file)
    ) {
      throw new Error("Loops npm pack returned an unexpected package descriptor");
    }
    const source = join(temporary, file);
    const target = join(destination, file);
    const bytes = await readFile(source);
    await writeFile(target, bytes, { mode: 0o644 });
    packageEntries.push({
      name,
      version,
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
