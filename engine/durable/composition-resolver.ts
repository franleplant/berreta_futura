import { readFile } from "node:fs/promises";

import type {
  DurableGit,
  DurableRevisionRef,
  GitRevisionBinding,
  InputRevisionRef,
  ResolvedDurableRevision,
} from "./types.ts";
import {
  compositionDurableRefs,
  parseCompositionDocument,
  type CompositionDocument,
} from "./composition-schema.ts";
import { resolveDurableRevision } from "./durable-store.ts";
import {
  resolveInputRevision,
  type ResolvedInputRevision,
} from "./input-revision.ts";

export type CompositionRevisionBinding = {
  readonly revisionRef: Extract<DurableRevisionRef, { readonly kind: "composition" }>;
  readonly manifestDigest: string;
  readonly gitCommitOid: string;
  readonly gitBlobOids: Readonly<Record<string, string>>;
};

export type RenderStage = {
  readonly schemaVersion: "render-stage/1";
  readonly composition: ResolvedDurableRevision;
  readonly compositionDocument: CompositionDocument;
  readonly durableInputs: readonly ResolvedDurableRevision[];
  readonly inputRevisions: readonly ResolvedInputRevision[];
};

export class CompositionResolutionError extends Error {
  readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "CompositionResolutionError";
    this.code = code;
  }
}

/**
 * Produces the complete read-only render stage from one exact committed
 * CompositionRevision. Array order remains the editorial composition order.
 */
export async function resolveCompositionRevision(
  repositoryRoot: string,
  binding: CompositionRevisionBinding,
  git: Pick<DurableGit, "assertCommitted">,
): Promise<RenderStage> {
  validateBinding(binding);
  const composition = await resolveDurableRevision(
    repositoryRoot,
    binding.revisionRef,
    git,
    {
      manifestDigest: binding.manifestDigest,
      gitBinding: {
        commitOid: binding.gitCommitOid,
        blobOids: binding.gitBlobOids,
      },
    },
  );
  const compositionPath = composition.payloadPaths["composition.yaml"];
  if (compositionPath === undefined || Object.keys(composition.payloadPaths).length !== 1) {
    throw invalid("CompositionRevision must contain exactly composition.yaml");
  }
  const document = parseCompositionDocument(await readFile(compositionPath), {
    editionId: binding.revisionRef.editionId,
    compositionId: binding.revisionRef.compositionId,
  });

  const durableInputs: ResolvedDurableRevision[] = [];
  const durableCache = new Map<string, Promise<ResolvedDurableRevision>>();
  for (const ref of compositionDurableRefs(document)) {
    const key = revisionKey(ref);
    let resolved = durableCache.get(key);
    if (resolved === undefined) {
      resolved = resolveDurableRevision(repositoryRoot, ref, git);
      durableCache.set(key, resolved);
    }
    durableInputs.push(await resolved);
  }

  const inputRevisions: ResolvedInputRevision[] = [];
  const inputCache = new Map<string, Promise<ResolvedInputRevision>>();
  const inputRefs = [
    ...document.layout_inputs.map((pin) => pin.revision),
    ...composition.manifest.input_revisions,
    ...durableInputs.flatMap((revision) => revision.manifest.input_revisions),
  ];
  const seenInputs = new Set<string>();
  for (const ref of inputRefs) {
    const key = inputKey(ref);
    if (seenInputs.has(key)) continue;
    seenInputs.add(key);
    let resolved = inputCache.get(key);
    if (resolved === undefined) {
      resolved = resolveInputRevision(repositoryRoot, ref, git);
      inputCache.set(key, resolved);
    }
    inputRevisions.push(await resolved);
  }
  return {
    schemaVersion: "render-stage/1",
    composition,
    compositionDocument: document,
    durableInputs,
    inputRevisions,
  };
}

function validateBinding(binding: CompositionRevisionBinding): void {
  if (
    binding.revisionRef.kind !== "composition" ||
    !/^sha256:[0-9a-f]{64}$/u.test(binding.manifestDigest) ||
    !validOid(binding.gitCommitOid) ||
    Object.keys(binding.gitBlobOids).length === 0 ||
    Object.values(binding.gitBlobOids).some((oid) => !validOid(oid))
  ) {
    throw invalid("CompositionRevision binding is incomplete or malformed");
  }
}

function revisionKey(ref: DurableRevisionRef): string {
  switch (ref.kind) {
    case "article":
    case "editorial":
      return `${ref.kind}:${ref.editionId}:${ref.logicalId}:${ref.language}:${ref.revisionId}`;
    case "image":
      return `image:${ref.editionId}:${ref.logicalId}:${ref.revisionId}`;
    case "composition":
      return `composition:${ref.editionId}:${ref.compositionId}:${ref.revisionId}`;
  }
}

function inputKey(ref: InputRevisionRef): string {
  return `${ref.kind}:${ref.editionId ?? ""}:${ref.logicalId}:${ref.revisionId}`;
}

function validOid(value: string): boolean {
  return /^[0-9a-f]{40}(?:[0-9a-f]{24})?$/u.test(value);
}

function invalid(message: string, cause?: unknown): CompositionResolutionError {
  return new CompositionResolutionError(
    "COMPOSITION_RESOLUTION_INVALID",
    message,
    cause === undefined ? undefined : { cause },
  );
}
