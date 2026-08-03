import { extname } from "node:path";

import { z } from "zod";

import {
  newArtifactId,
  type AnswerArtifact,
  type ArtifactId,
  type JsonObject,
  type WorkAnswer,
  type WorkOfferView,
  type WorkerIdentity,
} from "../contracts/index.ts";
import {
  SOURCE_CONTRACT_VERSION,
  type SourceAdapter,
  type SourceCaptureProfile,
  type SourceRequest,
} from "../source-adapter/index.ts";
import {
  AdapterWorkspaceOwner,
  permanentAdapterError,
  readJsonArtifact,
  requireExactSequence,
  requireOwnedOutputFile,
  requireSafeTargetPath,
  stageArtifact,
  writeAdapterRequest,
} from "./adapter-workspace.ts";
import type { Executor, ExecutorContext } from "./types.ts";

const profileSchema = z.object({
  schemaVersion: z.literal(1),
  sourceContractVersion: z.literal(SOURCE_CONTRACT_VERSION),
  sourceId: z.string().min(1),
  leadArtifactId: z.string().min(1),
  files: z.array(z.object({
    artifactId: z.string().min(1),
    targetPath: z.string().min(1),
  }).strict()).min(1),
  metadata: z.record(z.string(), z.json()).optional(),
}).strict();

export type SourceArchiveExecutorOptions = {
  readonly id?: string;
  readonly principalId?: string;
  readonly workDirectory: string;
};

export class SourceArchiveExecutor implements Executor {
  readonly id: string;
  readonly worker: WorkerIdentity;
  readonly capabilities = ["subprocess", "source_access"] as const;
  private readonly adapter: SourceAdapter;
  private readonly workspaces: AdapterWorkspaceOwner;

  constructor(adapter: SourceAdapter, options: SourceArchiveExecutorOptions) {
    this.adapter = adapter;
    this.id = options.id ?? "source-archive";
    this.workspaces = new AdapterWorkspaceOwner(options.workDirectory);
    this.worker = {
      principalId: options.principalId ?? this.id,
      authority: "tool",
      capabilities: this.capabilities,
      displayName: "Source archive adapter",
    };
  }

  accepts(offer: WorkOfferView): boolean {
    return offer.role === "capture_source";
  }

  async execute(context: ExecutorContext): Promise<WorkAnswer> {
    if (!this.accepts(context.offer)) {
      throw permanentAdapterError(`executor ${this.id} does not accept ${context.offer.role}`);
    }
    const parsed = profileSchema.safeParse(await readJsonArtifact(
      context.artifacts,
      context.offer.taskArtifactId,
      "source capture profile",
    ));
    if (!parsed.success) {
      throw permanentAdapterError(`source capture profile is invalid: ${parsed.error.message}`);
    }
    const profile = parsed.data as unknown as SourceCaptureProfile;
    if (profile.leadArtifactId !== context.offer.subjectArtifactId) {
      throw permanentAdapterError("source capture profile does not name the offered lead artifact");
    }
    const offeredInputs = new Set(context.offer.inputArtifacts);
    for (const [index, file] of profile.files.entries()) {
      if (!offeredInputs.has(file.artifactId)) {
        throw permanentAdapterError(
          `source capture profile input ${file.artifactId} was not offered to this attempt`,
        );
      }
      requireSafeTargetPath(file.targetPath, `source capture files[${index}].targetPath`);
    }
    requireUnique(
      profile.files.map((file) => file.targetPath),
      "source capture target paths",
    );

    const workspace = await this.workspaces.create(
      context.claim.attemptId,
      `source-${context.claim.attemptId}`,
    );
    const files = await Promise.all(
      profile.files.map(async (file, index) => ({
        artifactId: file.artifactId,
        sourcePath: await stageArtifact(
          context.artifacts,
          file.artifactId,
          workspace.inputRoot,
          index,
        ),
        targetPath: file.targetPath,
      })),
    );
    const request: SourceRequest = {
      schemaVersion: 1,
      sourceContractVersion: SOURCE_CONTRACT_VERSION,
      sourceId: profile.sourceId,
      leadArtifactId: profile.leadArtifactId,
      artifactRoot: workspace.inputRoot,
      files,
      ...(profile.metadata === undefined ? {} : { metadata: profile.metadata }),
    };
    await writeAdapterRequest(workspace.requestPath, request);
    const result = await this.adapter.archive(
      workspace.requestPath,
      workspace.outputRoot,
      context.signal,
    );
    if (
      result.schemaVersion !== 1 ||
      result.sourceContractVersion !== SOURCE_CONTRACT_VERSION ||
      result.sourceId !== profile.sourceId
    ) {
      throw permanentAdapterError("source adapter returned the wrong contract or source identity");
    }
    requireExactSequence(
      [profile.leadArtifactId, ...profile.files.map((file) => file.artifactId)],
      result.inputArtifactIds,
      "source adapter result",
    );
    requireExactSequence(
      profile.files.map((file) => file.targetPath),
      result.files.map((file) => file.path),
      "source adapter files",
    );

    const rawArtifacts: AnswerArtifact[] = [];
    const rawRows: JsonObject[] = [];
    for (const [index, file] of result.files.entries()) {
      const binding = profile.files[index];
      if (binding === undefined) {
        throw permanentAdapterError("source adapter returned an unbound output file");
      }
      const id = newArtifactId();
      const path = await requireOwnedOutputFile(workspace.outputRoot, file.path);
      rawArtifacts.push({
        id,
        kind: file.kind,
        schemaVersion: SOURCE_CONTRACT_VERSION,
        mediaType: mediaTypeForPath(file.path),
        payload: { kind: "file", path },
        parents: [{ artifactId: binding.artifactId, relation: "archived_input" }],
        metadata: {
          relativePath: file.path,
          sourceId: profile.sourceId,
          sourceContractVersion: SOURCE_CONTRACT_VERSION,
        },
      });
      rawRows.push({ artifactId: id, path: file.path, kind: file.kind });
    }

    const bundleId = newArtifactId();
    const bundle: AnswerArtifact = {
      id: bundleId,
      kind: "raw_source_bundle",
      schemaVersion: SOURCE_CONTRACT_VERSION,
      mediaType: "application/json",
      payload: {
        kind: "json",
        value: {
          schemaVersion: 1,
          sourceContractVersion: SOURCE_CONTRACT_VERSION,
          sourceId: profile.sourceId,
          leadArtifactId: profile.leadArtifactId,
          inputArtifactIds: result.inputArtifactIds,
          files: rawRows,
        },
      },
      parents: rawArtifacts.map((artifact) => ({
        artifactId: artifact.id as ArtifactId,
        relation: "raw_evidence",
      })),
      metadata: {
        sourceId: profile.sourceId,
        sourceContractVersion: SOURCE_CONTRACT_VERSION,
      },
    };
    const metadata: AnswerArtifact = {
      kind: "source_metadata",
      schemaVersion: SOURCE_CONTRACT_VERSION,
      mediaType: "application/json",
      payload: {
        kind: "json",
        value: {
          sourceId: profile.sourceId,
          rawBundleArtifactId: bundleId,
          fileCount: rawArtifacts.length,
          inputArtifactIds: result.inputArtifactIds,
        },
      },
      parents: [{ artifactId: bundleId, relation: "describes_bundle" }],
    };
    return {
      contractVersion: context.offer.contractVersion,
      result: {
        sourceId: profile.sourceId,
        rawBundleArtifactId: bundleId,
        inputArtifactIds: result.inputArtifactIds,
      },
      artifacts: [...rawArtifacts, bundle, metadata],
      metadata: {
        adapterContractVersion: SOURCE_CONTRACT_VERSION,
        executorId: this.id,
      },
    };
  }

  async release(context: ExecutorContext): Promise<void> {
    await this.workspaces.release(context.claim.attemptId);
  }
}

function requireUnique(values: readonly string[], label: string): void {
  if (new Set(values).size !== values.length) {
    throw permanentAdapterError(`${label} must be unique`);
  }
}

function mediaTypeForPath(path: string): string {
  switch (extname(path).toLowerCase()) {
    case ".html":
    case ".htm":
      return "text/html";
    case ".json":
      return "application/json";
    case ".md":
      return "text/markdown";
    case ".png":
      return "image/png";
    case ".jpg":
    case ".jpeg":
      return "image/jpeg";
    default:
      return "application/octet-stream";
  }
}
