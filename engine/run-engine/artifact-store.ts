import {
  closeSync,
  constants,
  existsSync,
  fstatSync,
  fsyncSync,
  lstatSync,
  mkdirSync,
  openSync,
  readFileSync,
  readdirSync,
  readSync,
  renameSync,
  rmdirSync,
  unlinkSync,
  writeSync,
} from "node:fs";
import { basename, isAbsolute, join, relative, resolve, sep } from "node:path";

import type { ArtifactId, ArtifactPayload } from "../contracts/index.ts";
import type { FailpointController } from "./types.ts";
import { RunEngineError } from "./types.ts";

const SAFE_ID = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,200}$/;
const COPY_BUFFER_BYTES = 1024 * 1024;

export type PreparedPayload = {
  readonly storageKind: "file" | "inline";
  readonly inlinePayload: Buffer | null;
  readonly relativePath: string | null;
  readonly sizeBytes: number;
  readonly writeIntent?: {
    readonly holderId: string;
    readonly fence: number;
  };
};

export class ArtifactStore {
  readonly root: string;
  readonly artifactsRoot: string;
  readonly temporaryRoot: string;
  readonly failpoints: FailpointController;

  constructor(root: string, failpoints: FailpointController) {
    this.root = resolve(root);
    this.artifactsRoot = join(this.root, "artifacts");
    this.temporaryRoot = join(this.root, "tmp");
    this.failpoints = failpoints;
    mkdirSync(this.root, { recursive: true, mode: 0o700 });
    mkdirSync(this.artifactsRoot, { recursive: true, mode: 0o700 });
    mkdirSync(this.temporaryRoot, { recursive: true, mode: 0o700 });
    syncDirectory(this.root);
  }

  prepare(id: ArtifactId, payload: ArtifactPayload): PreparedPayload {
    validateArtifactId(id);
    if (payload.kind === "file") {
      return this.copyFile(id, payload.path);
    }
    const bytes = payloadBytes(payload);
    return {
      storageKind: "inline",
      inlinePayload: bytes,
      relativePath: null,
      sizeBytes: bytes.byteLength,
    };
  }

  read(relativePath: string): Buffer {
    const path = this.resolveStoredPath(relativePath);
    const noFollow = "O_NOFOLLOW" in constants ? constants.O_NOFOLLOW : 0;
    const descriptor = openSync(path, constants.O_RDONLY | noFollow);
    try {
      const metadata = fstatSync(descriptor);
      if (!metadata.isFile()) {
        throw new RunEngineError(
          "ARTIFACT_PAYLOAD_INVALID",
          `Artifact payload is not a regular owned file: ${relativePath}`,
        );
      }
      return readFileSync(descriptor);
    } finally {
      closeSync(descriptor);
    }
  }

  collectUnreferenced(referencedRelativePaths: ReadonlySet<string>): readonly ArtifactId[] {
    const collected: ArtifactId[] = [];
    for (const entry of readdirSync(this.artifactsRoot, { withFileTypes: true })) {
      if (!entry.isDirectory() || entry.isSymbolicLink() || !SAFE_ID.test(entry.name)) {
        continue;
      }
      const artifactId = entry.name as ArtifactId;
      const relativePayload = `artifacts/${artifactId}/payload`;
      if (referencedRelativePaths.has(relativePayload)) {
        continue;
      }
      const directory = join(this.artifactsRoot, artifactId);
      const children = readdirSync(directory, { withFileTypes: true });
      if (
        children.length !== 1 ||
        children[0]?.name !== "payload" ||
        !children[0].isFile() ||
        children[0].isSymbolicLink()
      ) {
        continue;
      }
      unlinkSync(join(directory, "payload"));
      rmdirSync(directory);
      syncDirectory(this.artifactsRoot);
      collected.push(artifactId);
    }
    return collected;
  }

  private copyFile(id: ArtifactId, sourcePath: string): PreparedPayload {
    const source = resolve(sourcePath);
    const sourceMetadata = lstatSync(source);
    if (sourceMetadata.isSymbolicLink() || !sourceMetadata.isFile()) {
      throw new RunEngineError(
        "ARTIFACT_SOURCE_INVALID",
        `Artifact source must be a regular non-symlink file: ${sourcePath}`,
      );
    }

    const finalDirectory = join(this.artifactsRoot, id);
    const finalPayload = join(finalDirectory, "payload");
    if (existsSync(finalDirectory)) {
      const directoryMetadata = lstatSync(finalDirectory);
      if (directoryMetadata.isSymbolicLink() || !directoryMetadata.isDirectory()) {
        throw new RunEngineError(
          "ARTIFACT_ID_COLLISION",
          `Owned artifact path for ${id} is not a regular directory`,
        );
      }
      if (existsSync(finalPayload)) {
        const payloadMetadata = lstatSync(finalPayload);
        if (payloadMetadata.isSymbolicLink() || !payloadMetadata.isFile()) {
          throw new RunEngineError(
            "ARTIFACT_ID_COLLISION",
            `Owned artifact payload for ${id} is not a regular file`,
          );
        }
        if (!filesEqual(source, finalPayload)) {
          throw new RunEngineError(
            "ARTIFACT_ID_COLLISION",
            `Artifact id ${id} already owns different file bytes`,
          );
        }
        return {
          storageKind: "file",
          inlinePayload: null,
          relativePath: relative(this.root, finalPayload).split(sep).join("/"),
          sizeBytes: payloadMetadata.size,
        };
      }
      try {
        rmdirSync(finalDirectory);
        syncDirectory(this.artifactsRoot);
      } catch (error) {
        throw new RunEngineError(
          "ARTIFACT_ID_COLLISION",
          `Owned artifact directory for ${id} is incomplete and not empty`,
          { cause: error },
        );
      }
    }

    const nonce = `${process.pid}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const temporaryDirectory = join(this.temporaryRoot, `${id}-${nonce}`);
    const temporaryPayload = join(temporaryDirectory, "payload.tmp");
    let sourceDescriptor: number | undefined;
    let destinationDescriptor: number | undefined;
    let renamed = false;

    mkdirSync(temporaryDirectory, { mode: 0o700 });
    try {
      const noFollow = "O_NOFOLLOW" in constants ? constants.O_NOFOLLOW : 0;
      sourceDescriptor = openSync(source, constants.O_RDONLY | noFollow);
      const openedMetadata = fstatSync(sourceDescriptor);
      if (!openedMetadata.isFile()) {
        throw new RunEngineError(
          "ARTIFACT_SOURCE_INVALID",
          `Artifact source changed while being opened: ${sourcePath}`,
        );
      }
      destinationDescriptor = openSync(
        temporaryPayload,
        constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY,
        0o600,
      );
      const buffer = Buffer.allocUnsafe(COPY_BUFFER_BYTES);
      let offset = 0;
      while (true) {
        const read = readSync(sourceDescriptor, buffer, 0, buffer.byteLength, offset);
        if (read === 0) {
          break;
        }
        let written = 0;
        while (written < read) {
          written += writeSync(destinationDescriptor, buffer, written, read - written);
        }
        offset += read;
      }
      fsyncSync(destinationDescriptor);
      this.failpoints.hit("artifact.after_file_fsync", { artifactId: id, sizeBytes: offset });
      closeSync(destinationDescriptor);
      destinationDescriptor = undefined;
      closeSync(sourceDescriptor);
      sourceDescriptor = undefined;

      syncDirectory(temporaryDirectory);
      this.failpoints.hit("artifact.before_rename", { artifactId: id });
      mkdirSync(finalDirectory, { mode: 0o700 });
      renameSync(temporaryPayload, finalPayload);
      renamed = true;
      syncDirectory(finalDirectory);
      syncDirectory(this.artifactsRoot);
      this.failpoints.hit("artifact.after_rename", { artifactId: id });
      rmdirSync(temporaryDirectory);

      return {
        storageKind: "file",
        inlinePayload: null,
        relativePath: relative(this.root, finalPayload).split(sep).join("/"),
        sizeBytes: offset,
      };
    } catch (error) {
      if (destinationDescriptor !== undefined) {
        closeSync(destinationDescriptor);
      }
      if (sourceDescriptor !== undefined) {
        closeSync(sourceDescriptor);
      }
      if (!renamed && existsSync(temporaryPayload)) {
        unlinkSync(temporaryPayload);
      }
      if (!renamed && existsSync(temporaryDirectory)) {
        rmdirSync(temporaryDirectory);
      }
      if (!renamed && existsSync(finalDirectory) && !existsSync(finalPayload)) {
        try {
          rmdirSync(finalDirectory);
          syncDirectory(this.artifactsRoot);
        } catch {
          // Another writer may have completed the directory. The original
          // operation still fails, and a retry will compare the durable bytes.
        }
      }
      // Once rename and both directory syncs have succeeded, a failure leaves
      // an orphan for later collection. File presence never means committed.
      throw error;
    }
  }

  private resolveStoredPath(storedPath: string): string {
    if (isAbsolute(storedPath) || storedPath.includes("\0")) {
      throw new RunEngineError("ARTIFACT_PATH_UNSAFE", "Artifact path is not relative");
    }
    const path = resolve(this.root, storedPath);
    const fromRoot = relative(this.artifactsRoot, path);
    if (
      fromRoot === "" ||
      fromRoot === ".." ||
      fromRoot.startsWith(`..${sep}`) ||
      isAbsolute(fromRoot) ||
      basename(path) !== "payload"
    ) {
      throw new RunEngineError(
        "ARTIFACT_PATH_UNSAFE",
        `Artifact path escapes owned storage: ${storedPath}`,
      );
    }
    return path;
  }
}

function filesEqual(leftPath: string, rightPath: string): boolean {
  const noFollow = "O_NOFOLLOW" in constants ? constants.O_NOFOLLOW : 0;
  const left = openSync(leftPath, constants.O_RDONLY | noFollow);
  const right = openSync(rightPath, constants.O_RDONLY | noFollow);
  try {
    const leftMetadata = fstatSync(left);
    const rightMetadata = fstatSync(right);
    if (
      !leftMetadata.isFile() ||
      !rightMetadata.isFile() ||
      leftMetadata.size !== rightMetadata.size
    ) {
      return false;
    }
    const leftBuffer = Buffer.allocUnsafe(COPY_BUFFER_BYTES);
    const rightBuffer = Buffer.allocUnsafe(COPY_BUFFER_BYTES);
    let offset = 0;
    while (offset < leftMetadata.size) {
      const length = Math.min(COPY_BUFFER_BYTES, leftMetadata.size - offset);
      const leftRead = readSync(left, leftBuffer, 0, length, offset);
      const rightRead = readSync(right, rightBuffer, 0, length, offset);
      if (
        leftRead !== rightRead ||
        !leftBuffer.subarray(0, leftRead).equals(rightBuffer.subarray(0, rightRead))
      ) {
        return false;
      }
      if (leftRead === 0) {
        return false;
      }
      offset += leftRead;
    }
    return true;
  } finally {
    closeSync(right);
    closeSync(left);
  }
}

function payloadBytes(payload: Exclude<ArtifactPayload, { readonly kind: "file" }>): Buffer {
  switch (payload.kind) {
    case "bytes": {
      const decoded = Buffer.from(payload.dataBase64, "base64");
      if (decoded.toString("base64") !== payload.dataBase64) {
        throw new RunEngineError(
          "ARTIFACT_BASE64_INVALID",
          "Byte artifact payload must use canonical base64 encoding",
        );
      }
      return decoded;
    }
    case "json":
      return Buffer.from(JSON.stringify(payload.value), "utf8");
    case "text":
      return Buffer.from(payload.text, "utf8");
  }
}

function validateArtifactId(id: ArtifactId): void {
  if (!SAFE_ID.test(id) || id === "." || id === "..") {
    throw new RunEngineError("ARTIFACT_ID_UNSAFE", `Unsafe artifact id: ${id}`);
  }
}

function syncDirectory(path: string): void {
  const descriptor = openSync(path, constants.O_RDONLY);
  try {
    fsyncSync(descriptor);
  } finally {
    closeSync(descriptor);
  }
}
