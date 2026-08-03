import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";

import { z } from "zod";
import { parse } from "yaml";

import {
  KNOWN_WORK_ROLES,
  type JsonObject,
  type KnownWorkRole,
  type WorkAnswer,
  type WorkOfferView,
  type WorkerIdentity,
} from "../contracts/index.ts";
import {
  GitCliDurableGit,
  resolveCompositionRevision,
  resolveInputRevision,
  type CompositionRevisionBinding,
  type DurableGit,
  type DurableRevisionRef,
  type InputRevisionRef,
} from "../durable/index.ts";
import { permanentAdapterError } from "./adapter-workspace.ts";
import type { Executor, ExecutorContext } from "./types.ts";

type RunBootstrapRevision = Extract<InputRevisionRef, { readonly kind: "run_bootstrap" }>;
type PromptRevision = Extract<InputRevisionRef, { readonly kind: "prompt" }>;
type PolicyRevision = Extract<InputRevisionRef, { readonly kind: "policy" }>;
type ImageRevision = Extract<DurableRevisionRef, { readonly kind: "image" }>;

export type BootstrapRoleInput =
  | {
      readonly kind: "prompt";
      readonly revisionRef: {
        readonly kind: "prompt";
        readonly promptId: string;
        readonly revisionId: string;
      };
    }
  | {
      readonly kind: "contract";
      readonly contractVersion: string;
    }
  | {
      readonly kind: "policy";
      readonly revisionRef: {
        readonly kind: "policy";
        readonly policyId: string;
        readonly revisionId: string;
      };
    }
  | {
      readonly kind: "human";
      readonly authority: "human";
      readonly policyRevision?: {
        readonly kind: "policy";
        readonly policyId: string;
        readonly revisionId: string;
      };
    }
  | {
      readonly kind: "disabled";
      readonly reason: string;
    };

export type CompositionBootstrapResult = {
  readonly bootstrapRevision: RunBootstrapRevision;
  readonly compositionRevision: CompositionRevisionBinding;
  readonly configuredLanguages: readonly string[];
  readonly selectedImageRevisionRefs: readonly ImageRevision[];
  readonly imageGenerationAllowed: false;
  readonly rendererContractVersion: "magazine-renderer/1";
  readonly promptSet: {
    readonly id: string;
    readonly roleInputs: Readonly<Record<KnownWorkRole, BootstrapRoleInput>>;
  };
};

export type CompositionBootstrapExecutorOptions = {
  readonly repositoryRoot: string;
  readonly git?: Pick<DurableGit, "assertCommitted">;
  readonly id?: string;
  readonly principalId?: string;
};

const nonEmpty = z.string().trim().min(1);
const revisionId = nonEmpty;
const oid = z.string().regex(/^[0-9a-f]{40}(?:[0-9a-f]{24})?$/u);
const digest = z.string().regex(/^sha256:[0-9a-f]{64}$/u);

const promptRevisionSchema = z.object({
  kind: z.literal("prompt"),
  prompt_id: nonEmpty,
  revision_id: revisionId,
}).strict();

const policyRevisionSchema = z.object({
  kind: z.literal("policy"),
  policy_id: nonEmpty,
  revision_id: revisionId,
}).strict();

const roleInputSchema = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("prompt"), revision_ref: promptRevisionSchema }).strict(),
  z.object({ kind: z.literal("contract"), contract_version: nonEmpty }).strict(),
  z.object({ kind: z.literal("policy"), revision_ref: policyRevisionSchema }).strict(),
  z.object({
    kind: z.literal("human"),
    authority: z.literal("human"),
    policy_revision: policyRevisionSchema.optional(),
  }).strict(),
  z.object({ kind: z.literal("disabled"), reason: nonEmpty }).strict(),
]);

const roleInputsSchema = z.record(z.string(), roleInputSchema).superRefine((inputs, context) => {
  const actual = Object.keys(inputs).sort();
  const expected = [...KNOWN_WORK_ROLES].sort();
  const unexpected = actual.filter((role) => !expected.includes(role as KnownWorkRole));
  const missing = expected.filter((role) => !actual.includes(role));
  for (const role of unexpected) {
    context.addIssue({ code: "custom", path: [role], message: `unknown work role ${role}` });
  }
  for (const role of missing) {
    context.addIssue({ code: "custom", path: [role], message: `missing work role ${role}` });
  }
  for (const role of KNOWN_WORK_ROLES) {
    const input = inputs[role];
    if (input !== undefined && !roleInputIsCompatible(role, input)) {
      context.addIssue({
        code: "custom",
        path: [role],
        message: `${input.kind} role input is not compatible with ${role}`,
      });
    }
  }
});

const compositionBindingSchema = z.object({
  revision_ref: z.object({
    kind: z.literal("composition"),
    edition_id: nonEmpty,
    composition_id: nonEmpty,
    revision_id: revisionId,
  }).strict(),
  manifest_digest: digest,
  git_commit_oid: oid,
  git_blob_oids: z.record(nonEmpty, oid).refine(
    (entries) => Object.keys(entries).length > 0,
    "git_blob_oids must bind at least one file",
  ),
}).strict();

const imageRevisionSchema = z.object({
  kind: z.literal("image"),
  edition_id: nonEmpty,
  logical_id: nonEmpty,
  revision_id: revisionId,
}).strict();

const bootstrapDocumentSchema = z.object({
  schema_version: z.literal(1),
  edition_id: nonEmpty,
  composition_revision: compositionBindingSchema,
  configured_languages: z.array(nonEmpty).min(1),
  selected_image_revision_refs: z.array(imageRevisionSchema),
  image_generation_allowed: z.literal(false),
  renderer_contract_version: z.literal("magazine-renderer/1"),
  prompt_set: z.object({
    id: nonEmpty,
    role_inputs: roleInputsSchema,
  }).strict(),
}).strict();

const bootstrapTaskSchema = z.object({
  requestKind: z.literal("composition_bootstrap"),
  requestSchemaVersion: z.literal("composition-bootstrap-request/1"),
  actorKey: nonEmpty,
  subjectArtifactId: z.null(),
  inputArtifactIds: z.array(nonEmpty).min(1),
  choices: z.tuple([z.literal("verify")]),
  allowedChoices: z.tuple([z.literal("verify")]),
  bootstrapRevision: z.object({
    kind: z.literal("run_bootstrap"),
    editionId: nonEmpty,
    logicalId: nonEmpty,
    revisionId,
  }).strict(),
  imageGenerationAllowed: z.literal(false),
}).strict();

const contractRoles = new Map<KnownWorkRole, string>([
  ["measure_edition", "measure-edition/1"],
  ["render", "render-edition/1"],
  ["render_inspection", "render-inspection/1"],
  ["composition_bootstrap", "composition-bootstrap/1"],
]);

const disabledRoles = new Map<KnownWorkRole, string>([
  ["capture_source", "bootstrap_committed_inputs"],
  ["extract_source", "bootstrap_committed_inputs"],
  ["review_source", "bootstrap_committed_inputs"],
  ["close_collection", "bootstrap_committed_composition"],
  ["plan_edition", "bootstrap_committed_composition"],
  ["writer", "bootstrap_existing_manuscripts"],
  ["measure_article", "bootstrap_committed_composition"],
  ["worth", "bootstrap_committed_composition"],
  ["mechanics", "bootstrap_committed_composition"],
  ["evidence", "bootstrap_committed_composition"],
  ["shape", "bootstrap_committed_composition"],
  ["teaching", "bootstrap_committed_composition"],
  ["craft", "bootstrap_committed_composition"],
  ["editorial_writer", "bootstrap_existing_manuscripts"],
  ["edition_review", "bootstrap_committed_composition"],
  ["translation_writer", "bootstrap_existing_translations"],
  ["language_review", "bootstrap_existing_translations"],
  ["language_fit", "bootstrap_existing_translations"],
  ["cover_image", "bootstrap_existing_images"],
  ["interior_image", "bootstrap_existing_images"],
  ["select_art", "bootstrap_existing_images"],
  ["render_reconciliation", "bootstrap_forces_fresh_render"],
  ["release_approval", "stop_unreleased"],
  ["durable_checkpoint", "bootstrap_committed_composition"],
  ["editor_decision", "bootstrap_committed_composition"],
]);

/**
 * Resolves an exact committed bootstrap revision into the immutable composition
 * and prompt/policy authority it names. It performs no image generation or
 * rendering, and is deliberately safe to run as a deterministic subprocess.
 */
export async function resolveCompositionBootstrap(
  repositoryRoot: string,
  bootstrapRevision: RunBootstrapRevision,
  git: Pick<DurableGit, "assertCommitted">,
): Promise<CompositionBootstrapResult> {
  const resolvedBootstrap = await resolveInputRevision(repositoryRoot, bootstrapRevision, git);
  const bootstrapPath = join(repositoryRoot, resolvedBootstrap.relativeDirectory, "bootstrap.yaml");
  const document = parseBootstrapDocument(await readFile(bootstrapPath));
  if (document.edition_id !== bootstrapRevision.editionId) {
    throw invalid("bootstrap edition_id does not match its run-bootstrap revision");
  }

  const compositionRevision = compositionBinding(document.composition_revision);
  if (compositionRevision.revisionRef.editionId !== bootstrapRevision.editionId) {
    throw invalid("bootstrap CompositionRevision edition does not match its run-bootstrap revision");
  }
  const stage = await resolveCompositionRevision(repositoryRoot, compositionRevision, git);
  if (document.prompt_set.role_inputs.render?.kind !== "contract" ||
      document.prompt_set.role_inputs.render.contract_version !== "render-edition/1") {
    throw invalid("bootstrap renderer contract bridge must be render-edition/1 to magazine-renderer/1");
  }
  assertLanguages(document.configured_languages, stage.compositionDocument);
  const selectedImages = selectedImageRefs(stage.compositionDocument);
  if (!sameImageRefs(document.selected_image_revision_refs, selectedImages)) {
    throw invalid("bootstrap selected images do not exactly match CompositionRevision image pins");
  }
  await resolveRoleInputRevisions(repositoryRoot, document.prompt_set.role_inputs, git);

  return {
    bootstrapRevision,
    compositionRevision,
    configuredLanguages: document.configured_languages,
    selectedImageRevisionRefs: selectedImages,
    imageGenerationAllowed: false,
    rendererContractVersion: document.renderer_contract_version,
    promptSet: {
      id: document.prompt_set.id,
      roleInputs: Object.fromEntries(
        KNOWN_WORK_ROLES.map((role) => [role, camelRoleInput(document.prompt_set.role_inputs[role]!)]),
      ) as Record<KnownWorkRole, BootstrapRoleInput>,
    },
  };
}

/** A read-only deterministic executor for the composition bootstrap offer. */
export class CompositionBootstrapExecutor implements Executor {
  readonly id: string;
  readonly worker: WorkerIdentity;
  readonly capabilities = ["subprocess"] as const;

  private readonly repositoryRoot: string;
  private readonly git: Pick<DurableGit, "assertCommitted">;

  constructor(options: CompositionBootstrapExecutorOptions) {
    this.repositoryRoot = resolve(options.repositoryRoot);
    this.git = options.git ?? new GitCliDurableGit(this.repositoryRoot);
    this.id = options.id ?? "composition-bootstrap";
    this.worker = {
      principalId: options.principalId ?? this.id,
      authority: "tool",
      capabilities: this.capabilities,
      displayName: "Committed composition bootstrap resolver",
    };
  }

  accepts(offer: WorkOfferView): boolean {
    return offer.role === "composition_bootstrap";
  }

  async execute(context: ExecutorContext): Promise<WorkAnswer> {
    if (!this.accepts(context.offer)) {
      throw permanentAdapterError(`executor ${this.id} does not accept ${context.offer.role}`);
    }
    if (context.offer.contractVersion !== "composition-bootstrap/1") {
      throw permanentAdapterError("composition bootstrap offer has the wrong contract version");
    }
    if (context.signal.aborted) {
      throw permanentAdapterError("composition bootstrap was canceled before resolution");
    }
    let task: z.infer<typeof bootstrapTaskSchema>;
    try {
      task = bootstrapTaskSchema.parse(JSON.parse(await context.artifacts.readText(context.offer.taskArtifactId)));
    } catch (error) {
      throw permanentAdapterError(
        `composition bootstrap task is not valid: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
    const result = await resolveCompositionBootstrap(
      this.repositoryRoot,
      task.bootstrapRevision as RunBootstrapRevision,
      this.git,
    );
    return {
      contractVersion: "composition-bootstrap/1",
      result: result as unknown as JsonObject,
      artifacts: [{
        kind: "composition_bootstrap_evidence",
        schemaVersion: "composition-bootstrap/1",
        mediaType: "application/json",
        payload: { kind: "json", value: result as unknown as JsonObject },
      }],
    };
  }
}

function roleInputIsCompatible(
  role: KnownWorkRole,
  input: z.infer<typeof roleInputSchema>,
): boolean {
  const disabledReason = disabledRoles.get(role);
  if (disabledReason !== undefined) {
    return input.kind === "disabled" && input.reason === disabledReason;
  }
  const contractVersion = contractRoles.get(role);
  if (contractVersion !== undefined) {
    return input.kind === "contract" && input.contract_version === contractVersion;
  }
  if (role === "visual_review") {
    return input.kind === "human" && input.authority === "human" &&
      input.policy_revision !== undefined;
  }
  return false;
}

function parseBootstrapDocument(bytes: Uint8Array): z.infer<typeof bootstrapDocumentSchema> {
  let decoded: unknown;
  try {
    decoded = parse(Buffer.from(bytes).toString("utf8"));
  } catch (error) {
    throw invalid("bootstrap.yaml is not valid YAML", error);
  }
  const parsed = bootstrapDocumentSchema.safeParse(decoded);
  if (!parsed.success) {
    throw invalid(`bootstrap.yaml is invalid: ${parsed.error.message}`);
  }
  const languages = parsed.data.configured_languages;
  if (!languages.includes("en") || new Set(languages).size !== languages.length) {
    throw invalid("bootstrap configured_languages must include unique English source language en");
  }
  return parsed.data;
}

function compositionBinding(
  value: z.infer<typeof compositionBindingSchema>,
): CompositionRevisionBinding {
  return {
    revisionRef: {
      kind: "composition",
      editionId: value.revision_ref.edition_id,
      compositionId: value.revision_ref.composition_id,
      revisionId: value.revision_ref.revision_id as CompositionRevisionBinding["revisionRef"]["revisionId"],
    },
    manifestDigest: value.manifest_digest,
    gitCommitOid: value.git_commit_oid,
    gitBlobOids: value.git_blob_oids,
  };
}

function assertLanguages(
  configuredLanguages: readonly string[],
  composition: {
    readonly editorials: readonly { readonly manuscripts: readonly { readonly language: string }[] }[];
    readonly articles: readonly { readonly manuscripts: readonly { readonly language: string }[] }[];
  },
): void {
  const manuscriptGroups = [
    ...composition.editorials.map((item) => item.manuscripts),
    ...composition.articles.map((item) => item.manuscripts),
  ];
  if (manuscriptGroups.some((pins) => !sameSequence(pins.map((pin) => pin.language), configuredLanguages))) {
    throw invalid("CompositionRevision manuscript languages do not exactly match bootstrap configured_languages");
  }
}

function selectedImageRefs(composition: {
  readonly articles: readonly { readonly images: readonly { readonly revision: ImageRevision }[] }[];
  readonly images: readonly { readonly revision: ImageRevision }[];
}): readonly ImageRevision[] {
  const revisions = [
    ...composition.articles.flatMap((article) => article.images.map((image) => image.revision)),
    ...composition.images.map((image) => image.revision),
  ];
  const keys = revisions.map(imageKey);
  if (new Set(keys).size !== keys.length) {
    throw invalid("CompositionRevision cannot select the same image revision more than once");
  }
  return revisions;
}

function sameImageRefs(
  declared: readonly z.infer<typeof imageRevisionSchema>[],
  selected: readonly ImageRevision[],
): boolean {
  return declared.length === selected.length && declared.every((image, index) => {
    const expected = selected[index];
    return expected !== undefined && image.kind === expected.kind &&
      image.edition_id === expected.editionId && image.logical_id === expected.logicalId &&
      image.revision_id === expected.revisionId;
  });
}

async function resolveRoleInputRevisions(
  repositoryRoot: string,
  roleInputs: z.infer<typeof roleInputsSchema>,
  git: Pick<DurableGit, "assertCommitted">,
): Promise<void> {
  const refs = KNOWN_WORK_ROLES.flatMap((role) => roleInputRevisions(roleInputs[role]!));
  const unique = new Map<string, InputRevisionRef>();
  for (const ref of refs) unique.set(`${ref.kind}:${ref.logicalId}:${ref.revisionId}`, ref);
  await Promise.all([...unique.values()].map((ref) => resolveInputRevision(repositoryRoot, ref, git)));
}

function roleInputRevisions(input: z.infer<typeof roleInputSchema>): readonly InputRevisionRef[] {
  switch (input.kind) {
    case "prompt":
      return [{ kind: "prompt", logicalId: input.revision_ref.prompt_id, revisionId: input.revision_ref.revision_id } as PromptRevision];
    case "policy":
      return [{ kind: "policy", logicalId: input.revision_ref.policy_id, revisionId: input.revision_ref.revision_id } as PolicyRevision];
    case "human":
      return input.policy_revision === undefined
        ? []
        : [{ kind: "policy", logicalId: input.policy_revision.policy_id, revisionId: input.policy_revision.revision_id } as PolicyRevision];
    case "contract":
    case "disabled":
      return [];
  }
}

function camelRoleInput(input: z.infer<typeof roleInputSchema>): BootstrapRoleInput {
  switch (input.kind) {
    case "prompt":
      return {
        kind: "prompt",
        revisionRef: {
          kind: "prompt",
          promptId: input.revision_ref.prompt_id,
          revisionId: input.revision_ref.revision_id,
        },
      };
    case "contract":
      return { kind: "contract", contractVersion: input.contract_version };
    case "policy":
      return {
        kind: "policy",
        revisionRef: {
          kind: "policy",
          policyId: input.revision_ref.policy_id,
          revisionId: input.revision_ref.revision_id,
        },
      };
    case "human":
      return input.policy_revision === undefined
        ? { kind: "human", authority: "human" }
        : {
            kind: "human",
            authority: "human",
            policyRevision: {
              kind: "policy",
              policyId: input.policy_revision.policy_id,
              revisionId: input.policy_revision.revision_id,
            },
          };
    case "disabled":
      return { kind: "disabled", reason: input.reason };
  }
}

function sameSequence(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function imageKey(image: ImageRevision): string {
  return `${image.editionId}:${image.logicalId}:${image.revisionId}`;
}

function invalid(message: string, cause?: unknown): Error {
  return new Error(message, cause === undefined ? undefined : { cause });
}
