import { execFile as execFileCallback } from "node:child_process";
import { createHash } from "node:crypto";
import {
  access,
  lstat,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  realpath,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { promisify } from "node:util";

import type { ArtifactId, DecisionId, RunId, WorkOfferId } from "../contracts/index.ts";
import type { RunEngine } from "./types.ts";
import { RunEngineError } from "./types.ts";

const execFile = promisify(execFileCallback);

/**
 * A requested friendly filename is deliberately separate from an artifact's
 * storage path.  It is an export projection, never workflow state.
 */
export type ApprovedRenderExportFile = {
  readonly artifactId: ArtifactId;
  readonly destination: string;
  readonly kind: string;
  readonly mediaType: string;
  readonly pageCount?: number;
  readonly unpack?: {
    readonly destination: string;
    readonly requiredFiles?: readonly string[];
  };
};

export type ApprovedRenderExportPlan = {
  readonly runId: RunId;
  /** Immutable artifact produced by the human visual-review decision. */
  readonly approvedDecisionArtifactId: ArtifactId;
  readonly destinationDirectory: string;
  readonly files: readonly ApprovedRenderExportFile[];
  readonly manifestFile?: "export.json" | "manifest.json";
  readonly manifest?: Readonly<Record<string, unknown>>;
  readonly expectedHeadSequence?: number;
  /** Refuse replacement by default.  An explicit overwrite replaces atomically. */
  readonly overwrite?: boolean;
};

export type ApprovedRenderExportResult = {
  readonly destinationDirectory: string;
  readonly manifestPath: string;
  readonly decisionId: DecisionId;
  readonly decisionArtifactId: ArtifactId;
  readonly offerId: WorkOfferId;
  readonly files: readonly {
    readonly artifactId: ArtifactId;
    readonly destination: string;
  }[];
};

export type RenderProjectionPlan = {
  readonly destinationDirectory: string;
  readonly files: readonly ApprovedRenderExportFile[];
  readonly auxiliaryFiles?: readonly RenderProjectionAuxiliaryFile[];
  readonly manifestFile: "export.json" | "manifest.json";
  readonly manifest: Readonly<Record<string, unknown>>;
  readonly overwrite?: boolean;
  readonly verifyPdfPageCounts?: boolean;
  /** Called after every byte and PDF page count is verified, immediately before publish. */
  readonly verifyBeforePublish: () => Promise<void>;
};

export type RenderProjectionAuxiliaryFile = {
  readonly destination: string;
  readonly mediaType: "application/json" | "image/png" | "image/svg+xml" | "text/html";
  readonly bytes: Uint8Array;
};

export type RenderProjectionResult = {
  readonly destinationDirectory: string;
  readonly manifestPath: string;
  readonly physicalFileCount: number;
  readonly outputs: readonly {
    readonly destination: string;
    readonly artifactId: ArtifactId;
    readonly kind: string;
    readonly mediaType: string;
    readonly digest: string;
    readonly pageCount: number | null;
    readonly unpackedTo?: string;
  }[];
  readonly auxiliaryOutputs: readonly {
    readonly destination: string;
    readonly mediaType: RenderProjectionAuxiliaryFile["mediaType"];
    readonly digest: string;
    readonly sizeBytes: number;
  }[];
};

type ExportEngine = Pick<RunEngine, "inspect" | "readArtifact">;

/**
 * Materialize a named export from artifacts explicitly named by an approved
 * visual-review decision.  This uses only public RunEngine reads and does not
 * infer authority from artifact paths, timestamps, or filenames.
 */
export async function exportApprovedRender(
  engine: ExportEngine,
  plan: ApprovedRenderExportPlan,
): Promise<ApprovedRenderExportResult> {
  const run = await engine.inspect(plan.runId);
  const decision = run.decisions.find(
    (candidate) => candidate.artifactId === plan.approvedDecisionArtifactId,
  );
  if (
    decision === undefined ||
    decision.choice !== "approved" ||
    decision.authority !== "human" ||
    decision.offerId === undefined
  ) {
    throw new RunEngineError(
      "RENDER_NOT_APPROVED",
      `Artifact ${plan.approvedDecisionArtifactId} is not a human approved visual-review decision for run ${plan.runId}`,
    );
  }
  const offer = run.offers.find((candidate) => candidate.id === decision.offerId);
  if (offer?.role !== "visual_review") {
    throw new RunEngineError(
      "RENDER_NOT_APPROVED",
      `Decision ${decision.id} is not bound to a visual-review offer in run ${plan.runId}`,
    );
  }
  const approval = approvedRenderArtifacts(decision.details);
  if (approval === undefined) {
    throw new RunEngineError(
      "RENDER_APPROVAL_INVALID",
      `Decision ${decision.id} does not persist an exact accepted render artifact set`,
    );
  }
  const submitted = new Set(approval.submitted);
  if (plan.files.length === 0) {
    throw new RunEngineError("RENDER_EXPORT_EMPTY", "An approved render export needs at least one file");
  }

  const destinationDirectory = resolve(plan.destinationDirectory);
  const manifestFile = plan.manifestFile ?? "manifest.json";
  // The manifest is generated by this export, so callers cannot shadow it
  // with an artifact or unpacked tree.
  const seenDestinations = new Set<string>([filesystemCollisionKey(manifestFile)]);
  const seenArtifacts = new Set<ArtifactId>();
  const unpackDestinations: string[] = [];
  for (const file of plan.files) {
    const destination = safeRelativePath(file.destination, "export destination");
    const destinationKey = filesystemCollisionKey(destination);
    if (seenDestinations.has(destinationKey)) {
      throw new RunEngineError("RENDER_EXPORT_DUPLICATE", `Duplicate export destination ${destination}`);
    }
    seenDestinations.add(destinationKey);
    if (seenArtifacts.has(file.artifactId)) {
      throw new RunEngineError("RENDER_EXPORT_DUPLICATE", `Duplicate export artifact ${file.artifactId}`);
    }
    seenArtifacts.add(file.artifactId);
    assertFriendlyExtension(destination, file.mediaType);
    if (!submitted.has(file.artifactId)) {
      throw new RunEngineError(
        "RENDER_NOT_APPROVED",
        `Artifact ${file.artifactId} was not named by approved decision ${decision.id}`,
      );
    }
    if (file.unpack !== undefined) {
      const unpackDestination = safeRelativePath(file.unpack.destination, "unpack destination");
      unpackDestinations.push(unpackDestination);
      for (const required of file.unpack.requiredFiles ?? []) {
        safeRelativePath(required, "required unpacked file");
      }
    }
  }
  for (const unpackDestination of unpackDestinations) {
    const unpackKey = filesystemCollisionKey(unpackDestination);
    if (
      [...seenDestinations].some(
        (destinationKey) => pathsOverlap(destinationKey, unpackKey),
      )
    ) {
      throw new RunEngineError(
        "RENDER_EXPORT_PATH",
        `Unpack destination ${unpackDestination} collides with an exported file`,
      );
    }
  }
  for (let index = 0; index < unpackDestinations.length; index += 1) {
    const left = unpackDestinations[index];
    if (left === undefined) continue;
    const leftKey = filesystemCollisionKey(left);
    for (const right of unpackDestinations.slice(index + 1)) {
      if (pathsOverlap(leftKey, filesystemCollisionKey(right))) {
        throw new RunEngineError(
          "RENDER_EXPORT_PATH",
          `Unpack destinations ${left} and ${right} overlap`,
        );
      }
    }
  }

  await mkdir(dirname(destinationDirectory), { recursive: true });
  if (await pathExists(destinationDirectory)) {
    if (plan.overwrite !== true) {
      throw new RunEngineError(
        "RENDER_EXPORT_EXISTS",
        `Export destination ${destinationDirectory} already exists; set overwrite to replace it`,
      );
    }
    const existing = await lstat(destinationDirectory);
    if (!existing.isDirectory()) {
      throw new RunEngineError("RENDER_EXPORT_EXISTS", `Export destination ${destinationDirectory} is not a directory`);
    }
  }

  const staging = await mkdtemp(join(dirname(destinationDirectory), ".approved-render-export-"));
  try {
    const exportedFiles: Array<{
      readonly destination: string;
      readonly artifactId: ArtifactId;
      readonly kind: string;
      readonly mediaType: string;
      readonly digest: string;
      readonly pageCount: number | null;
      readonly unpackedTo?: string;
    }> = [];
    for (const file of plan.files) {
      const loaded = await engine.readArtifact(file.artifactId);
      if (loaded.artifact.kind !== file.kind || loaded.artifact.mediaType !== file.mediaType) {
        throw new RunEngineError(
          "RENDER_EXPORT_MISMATCH",
          `Artifact ${file.artifactId} is ${loaded.artifact.kind}/${loaded.artifact.mediaType}, not ${file.kind}/${file.mediaType}`,
        );
      }
      if (loaded.bytes.byteLength === 0) {
        throw new RunEngineError("RENDER_EXPORT_EMPTY", `Artifact ${file.artifactId} has an empty payload`);
      }
      validateMediaMagic(loaded.bytes, file.mediaType, file.artifactId);
      const output = stagedPath(staging, file.destination);
      await mkdir(dirname(output), { recursive: true });
      await writeFile(output, loaded.bytes);
      if (file.unpack !== undefined) {
        await unpackZip(output, stagedPath(staging, file.unpack.destination), file.unpack.requiredFiles ?? []);
      }
      exportedFiles.push({
        destination: safeRelativePath(file.destination, "export destination"),
        artifactId: file.artifactId,
        kind: file.kind,
        mediaType: file.mediaType,
        digest: `sha256:${createHash("sha256").update(loaded.bytes).digest("hex")}`,
        pageCount: file.pageCount ?? null,
        ...(file.unpack === undefined
          ? {}
          : { unpackedTo: safeRelativePath(file.unpack.destination, "unpack destination") }),
      });
    }
    if (plan.expectedHeadSequence !== undefined) {
      const current = await engine.inspect(plan.runId);
      if (current.headSequence !== plan.expectedHeadSequence) {
        throw new RunEngineError(
          "RENDER_EXPORT_STALE",
          `Run ${plan.runId} changed while its approved render export was staged`,
        );
      }
    }
    const manifest = plan.manifest === undefined
      ? {
          schemaVersion: "approved-render-export/2",
          runId: plan.runId,
          approvedDecision: {
            decisionId: decision.id,
            decisionArtifactId: plan.approvedDecisionArtifactId,
            offerId: decision.offerId,
          },
          files: exportedFiles,
        }
      : { ...plan.manifest, outputs: exportedFiles };
    await writeFile(join(staging, manifestFile), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
    await replaceDirectory(staging, destinationDirectory, plan.overwrite === true);
  } catch (error) {
    await rm(staging, { recursive: true, force: true });
    throw error;
  }

  return {
    destinationDirectory,
    manifestPath: join(destinationDirectory, manifestFile),
    decisionId: decision.id,
    decisionArtifactId: plan.approvedDecisionArtifactId,
    offerId: decision.offerId,
    files: plan.files.map((file) => ({ artifactId: file.artifactId, destination: safeRelativePath(file.destination, "export destination") })),
  };
}

/**
 * Atomically materialize immutable render artifacts without assigning any
 * workflow authority to the projection. Callers own the exact artifact set
 * and must revalidate their own workflow fence in verifyBeforePublish.
 */
export async function materializeRenderProjection(
  engine: Pick<RunEngine, "readArtifact">,
  plan: RenderProjectionPlan,
): Promise<RenderProjectionResult> {
  if (plan.files.length === 0) {
    throw new RunEngineError("RENDER_EXPORT_EMPTY", "A render projection needs at least one file");
  }
  const destinationDirectory = resolve(plan.destinationDirectory);
  const manifestFile = safeRelativePath(plan.manifestFile, "projection manifest");
  const auxiliaryFiles = (plan.auxiliaryFiles ?? []).map((file) => ({
    ...file,
    bytes: Buffer.from(file.bytes),
  }));
  const seenDestinations = new Set<string>([filesystemCollisionKey(manifestFile)]);
  const seenArtifacts = new Set<ArtifactId>();
  const unpackDestinations: string[] = [];
  for (const file of plan.files) {
    const destination = safeRelativePath(file.destination, "projection destination");
    const destinationKey = filesystemCollisionKey(destination);
    if (seenDestinations.has(destinationKey)) {
      throw new RunEngineError(
        "RENDER_EXPORT_DUPLICATE",
        `Duplicate projection destination ${destination}`,
      );
    }
    if (seenArtifacts.has(file.artifactId)) {
      throw new RunEngineError(
        "RENDER_EXPORT_DUPLICATE",
        `Duplicate projection artifact ${file.artifactId}`,
      );
    }
    seenDestinations.add(destinationKey);
    seenArtifacts.add(file.artifactId);
    assertFriendlyExtension(destination, file.mediaType);
    if (file.unpack !== undefined) {
      const unpackDestination = safeRelativePath(file.unpack.destination, "unpack destination");
      unpackDestinations.push(unpackDestination);
      for (const required of file.unpack.requiredFiles ?? []) {
        safeRelativePath(required, "required unpacked file");
      }
    }
  }
  for (const file of auxiliaryFiles) {
    const destination = safeRelativePath(file.destination, "projection auxiliary destination");
    const destinationKey = filesystemCollisionKey(destination);
    if ([...seenDestinations].some((existing) => pathsOverlap(existing, destinationKey))) {
      throw new RunEngineError(
        "RENDER_EXPORT_DUPLICATE",
        `Projection auxiliary destination ${destination} collides with another output`,
      );
    }
    if (file.bytes.byteLength === 0) {
      throw new RunEngineError(
        "RENDER_EXPORT_EMPTY",
        `Projection auxiliary output ${destination} has an empty payload`,
      );
    }
    assertFriendlyExtension(destination, file.mediaType);
    validateAuxiliaryBytes(file.bytes, file.mediaType, destination);
    seenDestinations.add(destinationKey);
  }
  validateUnpackDestinations(seenDestinations, unpackDestinations);

  await mkdir(dirname(destinationDirectory), { recursive: true });
  if (await pathExists(destinationDirectory)) {
    if (plan.overwrite !== true) {
      throw new RunEngineError(
        "RENDER_EXPORT_EXISTS",
        `Projection destination ${destinationDirectory} already exists; set overwrite to replace it`,
      );
    }
    const existing = await lstat(destinationDirectory);
    if (!existing.isDirectory() || existing.isSymbolicLink()) {
      throw new RunEngineError(
        "RENDER_EXPORT_EXISTS",
        `Projection destination ${destinationDirectory} is not an owned directory`,
      );
    }
  }

  const staging = await mkdtemp(join(dirname(destinationDirectory), ".render-projection-"));
  try {
    const outputs: Array<RenderProjectionResult["outputs"][number]> = [];
    for (const file of plan.files) {
      const loaded = await engine.readArtifact(file.artifactId);
      if (loaded.artifact.kind !== file.kind || loaded.artifact.mediaType !== file.mediaType) {
        throw new RunEngineError(
          "RENDER_EXPORT_MISMATCH",
          `Artifact ${file.artifactId} is ${loaded.artifact.kind}/${loaded.artifact.mediaType}, not ${file.kind}/${file.mediaType}`,
        );
      }
      if (loaded.bytes.byteLength === 0) {
        throw new RunEngineError(
          "RENDER_EXPORT_EMPTY",
          `Artifact ${file.artifactId} has an empty payload`,
        );
      }
      validateMediaMagic(loaded.bytes, file.mediaType, file.artifactId);
      const output = stagedPath(staging, file.destination);
      await mkdir(dirname(output), { recursive: true });
      await writeFile(output, loaded.bytes);
      if (plan.verifyPdfPageCounts === true && file.mediaType === "application/pdf") {
        if (file.pageCount === undefined) {
          throw new RunEngineError(
            "RENDER_EXPORT_PAGE_COUNTS",
            `PDF projection ${file.destination} does not declare its expected page count`,
          );
        }
        await verifyPdfPageCount(output, file.pageCount, file.artifactId);
      }
      if (file.unpack !== undefined) {
        await unpackZip(
          output,
          stagedPath(staging, file.unpack.destination),
          file.unpack.requiredFiles ?? [],
        );
      }
      outputs.push({
        destination: safeRelativePath(file.destination, "projection destination"),
        artifactId: file.artifactId,
        kind: file.kind,
        mediaType: file.mediaType,
        digest: `sha256:${createHash("sha256").update(loaded.bytes).digest("hex")}`,
        pageCount: file.pageCount ?? null,
        ...(file.unpack === undefined
          ? {}
          : { unpackedTo: safeRelativePath(file.unpack.destination, "unpack destination") }),
      });
    }
    const auxiliaryOutputs: Array<RenderProjectionResult["auxiliaryOutputs"][number]> = [];
    for (const file of auxiliaryFiles) {
      const destination = safeRelativePath(
        file.destination,
        "projection auxiliary destination",
      );
      const output = stagedPath(staging, destination);
      await mkdir(dirname(output), { recursive: true });
      await writeFile(output, file.bytes);
      auxiliaryOutputs.push({
        destination,
        mediaType: file.mediaType,
        digest: `sha256:${createHash("sha256").update(file.bytes).digest("hex")}`,
        sizeBytes: file.bytes.byteLength,
      });
    }
    const physicalFileCount = await countRegularFiles(staging) + 1;
    await writeFile(
      join(staging, manifestFile),
      `${JSON.stringify({ ...plan.manifest, outputs, auxiliaryOutputs, physicalFileCount }, null, 2)}\n`,
      "utf8",
    );
    await plan.verifyBeforePublish();
    await replaceDirectory(staging, destinationDirectory, plan.overwrite === true);
    return {
      destinationDirectory,
      manifestPath: join(destinationDirectory, manifestFile),
      physicalFileCount,
      outputs,
      auxiliaryOutputs,
    };
  } catch (error) {
    await rm(staging, { recursive: true, force: true });
    throw error;
  }
}

function approvedRenderArtifacts(
  details: Readonly<Record<string, unknown>>,
): { readonly submitted: readonly ArtifactId[]; readonly expected: readonly ArtifactId[] } | undefined {
  const submitted = artifactIdArray(details.submittedRenderArtifactIds);
  const expected = artifactIdArray(details.expectedRenderArtifactIds);
  if (
    details.accepted !== true ||
    submitted === undefined ||
    expected === undefined ||
    !sameArtifactSequence(submitted, expected)
  ) {
    return undefined;
  }
  return { submitted, expected };
}

function artifactIdArray(value: unknown): readonly ArtifactId[] | undefined {
  if (!Array.isArray(value) || value.some((artifactId) => typeof artifactId !== "string")) {
    return undefined;
  }
  return value as readonly ArtifactId[];
}

function sameArtifactSequence(left: readonly ArtifactId[], right: readonly ArtifactId[]): boolean {
  return left.length === right.length && left.every((artifactId, index) => artifactId === right[index]);
}

function safeRelativePath(value: string, label: string): string {
  if (!value || isAbsolute(value) || value.includes("\0")) {
    throw new RunEngineError("RENDER_EXPORT_PATH", `${label} must be a non-empty relative path`);
  }
  const normalized = value.split(/[\\/]+/).join(sep);
  const relativePath = relative(".", normalized);
  if (
    relativePath === "" ||
    relativePath === ".." ||
    relativePath.startsWith(`..${sep}`) ||
    relativePath.includes(`${sep}..${sep}`) ||
    relativePath.endsWith(`${sep}..`)
  ) {
    throw new RunEngineError("RENDER_EXPORT_PATH", `${label} must stay under the export directory`);
  }
  return relativePath;
}

function stagedPath(staging: string, destination: string): string {
  const relativePath = safeRelativePath(destination, "export destination");
  const candidate = resolve(staging, relativePath);
  if (candidate !== staging && !candidate.startsWith(`${staging}${sep}`)) {
    throw new RunEngineError("RENDER_EXPORT_PATH", "Export path escapes staging directory");
  }
  return candidate;
}

async function unpackZip(zipPath: string, destination: string, requiredFiles: readonly string[]): Promise<void> {
  try {
    inspectZipEntries(await readFile(zipPath));
  } catch (error) {
    if (error instanceof RunEngineError) throw error;
    throw new RunEngineError("RENDER_EXPORT_ZIP", `Cannot inspect web ZIP ${zipPath}`, { cause: error });
  }
  await mkdir(destination, { recursive: true });
  try {
    await execFile("unzip", ["-qq", zipPath, "-d", destination], { encoding: "utf8" });
  } catch (error) {
    throw new RunEngineError("RENDER_EXPORT_ZIP", `Cannot unpack web ZIP ${zipPath}`, { cause: error });
  }
  await validateExtractedTree(destination, zipPath);
  for (const required of requiredFiles) {
    const requiredPath = stagedPath(destination, required);
    let requiredStat;
    try {
      requiredStat = await lstat(requiredPath);
    } catch {
      throw new RunEngineError("RENDER_EXPORT_ZIP", `Web ZIP ${zipPath} is missing ${required}`);
    }
    if (!requiredStat.isFile()) {
      throw new RunEngineError("RENDER_EXPORT_ZIP", `Web ZIP ${zipPath} has a non-regular required file ${required}`);
    }
    await assertRealPathWithin(destination, requiredPath, zipPath);
  }
}

const ZIP_CENTRAL_HEADER = 0x02014b50;
const ZIP_END_OF_CENTRAL_DIRECTORY = 0x06054b50;
const ZIP_LOCAL_HEADER = 0x04034b50;
const ZIP64_SENTINEL_16 = 0xffff;
const ZIP64_SENTINEL_32 = 0xffffffff;
const DOS_ATTRIBUTE_HOST_SYSTEMS = new Set([0, 6, 10, 14]);
const UNIX_HOST_SYSTEMS = new Set([3, 19]);
const UNIX_FILE_TYPE_MASK = 0xf000;
const UNIX_DIRECTORY = 0x4000;
const UNIX_REGULAR_FILE = 0x8000;

function inspectZipEntries(bytes: Buffer): void {
  const endOffset = findEndOfCentralDirectory(bytes);
  const diskNumber = bytes.readUInt16LE(endOffset + 4);
  const centralDisk = bytes.readUInt16LE(endOffset + 6);
  const entriesOnDisk = bytes.readUInt16LE(endOffset + 8);
  const entryCount = bytes.readUInt16LE(endOffset + 10);
  const centralSize = bytes.readUInt32LE(endOffset + 12);
  const centralOffset = bytes.readUInt32LE(endOffset + 16);
  if (
    diskNumber !== 0 ||
    centralDisk !== 0 ||
    entriesOnDisk !== entryCount ||
    entryCount === 0 ||
    entryCount === ZIP64_SENTINEL_16 ||
    centralSize === ZIP64_SENTINEL_32 ||
    centralOffset === ZIP64_SENTINEL_32 ||
    centralOffset + centralSize > endOffset
  ) {
    throw new RunEngineError("RENDER_EXPORT_ZIP", "Web ZIP has an unsupported central directory");
  }

  let offset = centralOffset;
  const centralEnd = centralOffset + centralSize;
  const seenEntries = new Set<string>();
  for (let index = 0; index < entryCount; index += 1) {
    if (offset + 46 > centralEnd || bytes.readUInt32LE(offset) !== ZIP_CENTRAL_HEADER) {
      throw new RunEngineError("RENDER_EXPORT_ZIP", "Web ZIP has a malformed central-directory entry");
    }
    const versionMadeBy = bytes.readUInt16LE(offset + 4);
    const flags = bytes.readUInt16LE(offset + 8);
    const filenameLength = bytes.readUInt16LE(offset + 28);
    const extraLength = bytes.readUInt16LE(offset + 30);
    const commentLength = bytes.readUInt16LE(offset + 32);
    const startDisk = bytes.readUInt16LE(offset + 34);
    const externalAttributes = bytes.readUInt32LE(offset + 38);
    const localOffset = bytes.readUInt32LE(offset + 42);
    const entryEnd = offset + 46 + filenameLength + extraLength + commentLength;
    if (
      filenameLength === 0 ||
      entryEnd > centralEnd ||
      startDisk !== 0 ||
      localOffset === ZIP64_SENTINEL_32 ||
      (flags & 0x1) !== 0
    ) {
      throw new RunEngineError("RENDER_EXPORT_ZIP", "Web ZIP has an unsupported archive entry");
    }
    const name = decodeZipName(bytes.subarray(offset + 46, offset + 46 + filenameLength));
    if (!safeZipEntry(name) || !allowedZipEntryType(name, versionMadeBy, externalAttributes)) {
      throw new RunEngineError("RENDER_EXPORT_ZIP", `Web ZIP contains unsafe entry ${JSON.stringify(name)}`);
    }
    const entryKey = filesystemCollisionKey(name.endsWith("/") ? name.slice(0, -1) : name);
    if (seenEntries.has(entryKey)) {
      throw new RunEngineError(
        "RENDER_EXPORT_ZIP",
        `Web ZIP contains colliding entry ${JSON.stringify(name)}`,
      );
    }
    seenEntries.add(entryKey);
    verifyLocalEntryName(bytes, localOffset, name);
    offset = entryEnd;
  }
  if (offset !== centralEnd) {
    throw new RunEngineError("RENDER_EXPORT_ZIP", "Web ZIP central-directory size does not match its entries");
  }
}

function findEndOfCentralDirectory(bytes: Buffer): number {
  const minimumLength = 22;
  const searchStart = Math.max(0, bytes.length - minimumLength - ZIP64_SENTINEL_16);
  for (let offset = bytes.length - minimumLength; offset >= searchStart; offset -= 1) {
    if (
      bytes.readUInt32LE(offset) === ZIP_END_OF_CENTRAL_DIRECTORY &&
      offset + minimumLength + bytes.readUInt16LE(offset + 20) === bytes.length
    ) {
      return offset;
    }
  }
  throw new RunEngineError("RENDER_EXPORT_ZIP", "Web ZIP has no valid end-of-central-directory record");
}

function decodeZipName(bytes: Uint8Array): string {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch (error) {
    throw new RunEngineError("RENDER_EXPORT_ZIP", "Web ZIP has a non-UTF-8 entry name", { cause: error });
  }
}

function allowedZipEntryType(name: string, versionMadeBy: number, externalAttributes: number): boolean {
  const hostSystem = versionMadeBy >>> 8;
  if (UNIX_HOST_SYSTEMS.has(hostSystem)) {
    const unixType = (externalAttributes >>> 16) & UNIX_FILE_TYPE_MASK;
    if (unixType === UNIX_DIRECTORY) return name.endsWith("/");
    if (unixType === UNIX_REGULAR_FILE) return !name.endsWith("/");
    return false;
  }
  if (!DOS_ATTRIBUTE_HOST_SYSTEMS.has(hostSystem)) return false;
  const dosDirectory = (externalAttributes & 0x10) !== 0;
  return dosDirectory === name.endsWith("/");
}

function verifyLocalEntryName(bytes: Buffer, offset: number, expectedName: string): void {
  if (offset + 30 > bytes.length || bytes.readUInt32LE(offset) !== ZIP_LOCAL_HEADER) {
    throw new RunEngineError("RENDER_EXPORT_ZIP", "Web ZIP has a malformed local entry header");
  }
  const filenameLength = bytes.readUInt16LE(offset + 26);
  const extraLength = bytes.readUInt16LE(offset + 28);
  if (offset + 30 + filenameLength + extraLength > bytes.length) {
    throw new RunEngineError("RENDER_EXPORT_ZIP", "Web ZIP local entry header extends past the payload");
  }
  const localName = decodeZipName(bytes.subarray(offset + 30, offset + 30 + filenameLength));
  if (localName !== expectedName || !safeZipEntry(localName)) {
    throw new RunEngineError("RENDER_EXPORT_ZIP", "Web ZIP local and central entry names do not match");
  }
}

async function validateExtractedTree(root: string, zipPath: string): Promise<void> {
  const rootRealPath = await realpath(root);
  const pending = [root];
  while (pending.length > 0) {
    const directory = pending.pop();
    if (directory === undefined) continue;
    for (const name of await readdir(directory)) {
      const path = join(directory, name);
      const entry = await lstat(path);
      if (!entry.isFile() && !entry.isDirectory()) {
        throw new RunEngineError("RENDER_EXPORT_ZIP", `Web ZIP ${zipPath} extracted a non-regular entry ${path}`);
      }
      const resolved = await realpath(path);
      if (!pathWithin(rootRealPath, resolved)) {
        throw new RunEngineError("RENDER_EXPORT_ZIP", `Web ZIP ${zipPath} extracted outside its unpack root`);
      }
      if (entry.isDirectory()) pending.push(path);
    }
  }
}

async function assertRealPathWithin(root: string, path: string, zipPath: string): Promise<void> {
  const [rootRealPath, pathRealPath] = await Promise.all([realpath(root), realpath(path)]);
  if (!pathWithin(rootRealPath, pathRealPath)) {
    throw new RunEngineError("RENDER_EXPORT_ZIP", `Web ZIP ${zipPath} required file escapes its unpack root`);
  }
}

function pathWithin(root: string, candidate: string): boolean {
  return candidate === root || candidate.startsWith(`${root}${sep}`);
}

/**
 * Default macOS APFS volumes are case-insensitive and normalization-insensitive.
 * NFD mirrors Finder's canonical-equivalence behavior; lowercasing gives every
 * validation pass one stable collision key before anything reaches the disk.
 */
function filesystemCollisionKey(path: string): string {
  return path.normalize("NFD").toLowerCase().normalize("NFD");
}

function pathsOverlap(left: string, right: string): boolean {
  return left === right || left.startsWith(`${right}${sep}`) || right.startsWith(`${left}${sep}`);
}

function validateUnpackDestinations(
  fileDestinations: ReadonlySet<string>,
  unpackDestinations: readonly string[],
): void {
  for (const unpackDestination of unpackDestinations) {
    const unpackKey = filesystemCollisionKey(unpackDestination);
    if ([...fileDestinations].some((destinationKey) => pathsOverlap(destinationKey, unpackKey))) {
      throw new RunEngineError(
        "RENDER_EXPORT_PATH",
        `Unpack destination ${unpackDestination} collides with a projected file`,
      );
    }
  }
  for (let index = 0; index < unpackDestinations.length; index += 1) {
    const left = unpackDestinations[index];
    if (left === undefined) continue;
    const leftKey = filesystemCollisionKey(left);
    for (const right of unpackDestinations.slice(index + 1)) {
      if (pathsOverlap(leftKey, filesystemCollisionKey(right))) {
        throw new RunEngineError(
          "RENDER_EXPORT_PATH",
          `Unpack destinations ${left} and ${right} overlap`,
        );
      }
    }
  }
}

function safeZipEntry(entry: string): boolean {
  if (
    !entry ||
    isAbsolute(entry) ||
    entry.includes("\0") ||
    entry.includes("\\") ||
    [...entry].some((character) => character.codePointAt(0)! < 0x20)
  ) {
    return false;
  }
  const components = entry.split("/");
  if (components.at(-1) === "") components.pop();
  return components.length > 0 && !components.some(
    (component) => component === "" || component === "." || component === "..",
  );
}

function validateMediaMagic(bytes: Uint8Array, mediaType: string, artifactId: ArtifactId): void {
  if (mediaType === "application/pdf") {
    if (bytes.byteLength < 5 || Buffer.from(bytes.subarray(0, 5)).toString("ascii") !== "%PDF-") {
      throw new RunEngineError("RENDER_EXPORT_MAGIC", `Artifact ${artifactId} does not have PDF magic`);
    }
  }
  if (mediaType === "application/zip") {
    const signature = Buffer.from(bytes.subarray(0, 4)).toString("hex");
    if (!new Set(["504b0304", "504b0506", "504b0708"]).has(signature)) {
      throw new RunEngineError("RENDER_EXPORT_MAGIC", `Artifact ${artifactId} does not have ZIP magic`);
    }
  }
  if (mediaType === "image/png") {
    const signature = Buffer.from(bytes.subarray(0, 8)).toString("hex");
    if (signature !== "89504e470d0a1a0a") {
      throw new RunEngineError("RENDER_EXPORT_MAGIC", `Artifact ${artifactId} does not have PNG magic`);
    }
  }
}

function validateAuxiliaryBytes(
  bytes: Uint8Array,
  mediaType: RenderProjectionAuxiliaryFile["mediaType"],
  destination: string,
): void {
  if (mediaType === "image/png") {
    if (Buffer.from(bytes.subarray(0, 8)).toString("hex") !== "89504e470d0a1a0a") {
      throw new RunEngineError(
        "RENDER_EXPORT_MAGIC",
        `Projection auxiliary output ${destination} does not have PNG magic`,
      );
    }
    return;
  }
  const text = Buffer.from(bytes).toString("utf8");
  if (mediaType === "application/json") {
    try {
      JSON.parse(text);
    } catch (error) {
      throw new RunEngineError(
        "RENDER_EXPORT_MAGIC",
        `Projection auxiliary output ${destination} is not valid JSON`,
        { cause: error },
      );
    }
    return;
  }
  if (mediaType === "image/svg+xml") {
    if (!/<svg(?:\s|>)/u.test(text)) {
      throw new RunEngineError(
        "RENDER_EXPORT_MAGIC",
        `Projection auxiliary output ${destination} is not SVG`,
      );
    }
    return;
  }
  if (mediaType === "text/html") {
    if (!/<html(?:\s|>)/iu.test(text)) {
      throw new RunEngineError(
        "RENDER_EXPORT_MAGIC",
        `Projection auxiliary output ${destination} is not HTML`,
      );
    }
    return;
  }
  const exhaustive: never = mediaType;
  throw new RunEngineError(
    "RENDER_EXPORT_MAGIC",
    `Projection auxiliary output ${destination} has unsupported media type ${exhaustive}`,
  );
}

async function verifyPdfPageCount(
  path: string,
  expected: number,
  artifactId: ArtifactId,
): Promise<void> {
  let stdout: string;
  try {
    ({ stdout } = await execFile("pdfinfo", [path], { encoding: "utf8" }));
  } catch (error) {
    throw new RunEngineError(
      "RENDER_EXPORT_PDFINFO",
      `Cannot inspect PDF artifact ${artifactId} with pdfinfo`,
      { cause: error },
    );
  }
  const match = /^Pages:\s+([0-9]+)\s*$/mu.exec(stdout);
  const actual = match === null ? undefined : Number.parseInt(match[1]!, 10);
  if (actual !== expected) {
    throw new RunEngineError(
      "RENDER_EXPORT_PAGE_COUNTS",
      `PDF artifact ${artifactId} has ${actual ?? "an unreadable"} page count, expected ${expected}`,
    );
  }
}

function assertFriendlyExtension(destination: string, mediaType: string): void {
  const expected = mediaType === "application/pdf"
    ? ".pdf"
    : mediaType === "application/zip"
      ? ".zip"
      : mediaType === "application/json"
        ? ".json"
        : mediaType === "image/png"
          ? ".png"
          : mediaType === "image/svg+xml"
            ? ".svg"
            : mediaType === "text/html"
              ? ".html"
              : undefined;
  if (expected !== undefined && !destination.toLowerCase().endsWith(expected)) {
    throw new RunEngineError(
      "RENDER_EXPORT_EXTENSION",
      `${destination} must use ${expected} for ${mediaType}`,
    );
  }
}

async function replaceDirectory(staging: string, destination: string, overwrite: boolean): Promise<void> {
  if (!overwrite || !(await pathExists(destination))) {
    await rename(staging, destination);
    return;
  }
  const backup = `${destination}.previous-${process.pid}-${Date.now()}`;
  await rename(destination, backup);
  try {
    await rename(staging, destination);
  } catch (error) {
    await rename(backup, destination);
    throw error;
  }
  await rm(backup, { recursive: true, force: true });
}

async function pathExists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

async function countRegularFiles(root: string): Promise<number> {
  let count = 0;
  const pending = [root];
  while (pending.length > 0) {
    const directory = pending.pop();
    if (directory === undefined) continue;
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        pending.push(join(directory, entry.name));
      } else if (entry.isFile()) {
        count += 1;
      }
    }
  }
  return count;
}
