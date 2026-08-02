import type {
  AnswerArtifact,
  ArtifactId,
  ArtifactView,
  JsonObject,
  JsonValue,
  WorkAnswer,
  WorkOfferView,
  WorkerIdentity,
} from "../contracts/index.ts";
import { permanentAdapterError } from "./adapter-workspace.ts";
import type { Executor, ExecutorContext } from "./types.ts";

export type RenderInspectionExecutorOptions = {
  readonly id?: string;
  readonly principalId?: string;
};

/**
 * Converts the renderer's committed machine-critic reports into the exact
 * inspection decision consumed by RenderMachine. It performs no visual or
 * editorial judgment; independent human visual review remains a later offer.
 */
export class RenderInspectionExecutor implements Executor {
  readonly id: string;
  readonly worker: WorkerIdentity;
  readonly capabilities = ["subprocess"] as const;

  constructor(options: RenderInspectionExecutorOptions = {}) {
    this.id = options.id ?? "render-inspection";
    this.worker = {
      principalId: options.principalId ?? this.id,
      authority: "tool",
      capabilities: this.capabilities,
      displayName: "Deterministic render critic inspection",
    };
  }

  accepts(offer: WorkOfferView): boolean {
    return offer.role === "render_inspection";
  }

  async execute(context: ExecutorContext): Promise<WorkAnswer> {
    if (!this.accepts(context.offer)) {
      throw permanentAdapterError(`executor ${this.id} does not accept ${context.offer.role}`);
    }
    if (context.artifacts.readArtifact === undefined) {
      throw permanentAdapterError("render inspection requires artifact lineage access");
    }
    const records = await Promise.all(context.offer.inputArtifacts.map(async (artifactId) =>
      (await context.artifacts.readArtifact?.(artifactId))?.artifact
    ));
    if (records.some((record) => record === undefined)) {
      throw permanentAdapterError("render inspection could not resolve every immutable input");
    }
    const artifacts = records as readonly ArtifactView[];
    const reports = artifacts.filter((artifact) =>
      artifact.kind === "render_critic_report" &&
      typeof artifact.metadata.relativePath === "string" &&
      artifact.metadata.relativePath.endsWith("render-critic.json")
    );
    if (reports.length === 0) {
      throw permanentAdapterError("render inspection found no committed render-critic reports");
    }
    const producingOffers = [...new Set(reports.map((report) => report.producingOfferId))];
    if (producingOffers.length !== 1 || producingOffers[0] === undefined) {
      throw permanentAdapterError(
        "render inspection reports do not identify one exact render attempt",
      );
    }
    const renderOfferId = producingOffers[0];
    const renderArtifacts = artifacts.filter(
      (artifact) => artifact.producingOfferId === renderOfferId,
    );
    if (renderArtifacts.length === 0) {
      throw permanentAdapterError("render inspection found no exact render result set");
    }
    if (!renderArtifacts.some((artifact) => artifact.kind === "reader_pdf")) {
      throw permanentAdapterError("render inspection result set contains no reader PDF");
    }
    if (reports.some((report) => report.producingOfferId !== renderOfferId)) {
      throw permanentAdapterError("render inspection mixed reports from different renders");
    }
    const preflights = renderArtifacts.filter(
      (artifact) => artifact.kind === "printer_preflight",
    );

    const inspected = await Promise.all(reports.map(async (report) => {
      let value: unknown;
      try {
        value = JSON.parse(await context.artifacts.readText(report.id));
      } catch (error) {
        throw permanentAdapterError(
          `render critic ${report.id} is invalid JSON: ${error instanceof Error ? error.message : String(error)}`,
        );
      }
      if (!isRecord(value) || (value.result !== "pass" && value.result !== "fail")) {
        throw permanentAdapterError(
          `render critic ${report.id} has no deterministic pass/fail result`,
        );
      }
      return {
        artifactId: report.id,
        relativePath: report.metadata.relativePath as string,
        result: value.result,
        findings: criticFindings(value),
      };
    }));
    requireUnique(
      inspected.map((report) => report.relativePath),
      "render critic paths",
    );
    const inspectedPreflights = await Promise.all(preflights.map(async (preflight) => {
      let value: unknown;
      try {
        value = JSON.parse(await context.artifacts.readText(preflight.id));
      } catch (error) {
        throw permanentAdapterError(
          `printer preflight ${preflight.id} is invalid JSON: ${error instanceof Error ? error.message : String(error)}`,
        );
      }
      if (
        !isRecord(value) ||
        !isRecord(value.studio) ||
        typeof value.studio.ready !== "boolean"
      ) {
        throw permanentAdapterError(
          `printer preflight ${preflight.id} has no deterministic studio.ready result`,
        );
      }
      return {
        artifactId: preflight.id,
        studioReady: value.studio.ready,
        blockers: Array.isArray(value.studio.blockers)
          ? value.studio.blockers.filter(isJsonValue)
          : [],
      };
    }));
    const result: "fail" | "pass" = inspected.every((report) => report.result === "pass")
      ? "pass"
      : "fail";
    const findings = inspected.flatMap((report) => report.findings.map((finding) => ({
      reportArtifactId: report.artifactId,
      path: report.relativePath,
      finding,
    })));
    const studioReady =
      inspectedPreflights.length > 0 &&
      inspectedPreflights.every((preflight) => preflight.studioReady);
    const printerPreflightArtifactIds = inspectedPreflights.map(
      (preflight) => preflight.artifactId,
    );
    const renderArtifactIds = renderArtifacts.map((artifact) => artifact.id);
    const value: JsonObject = {
      schemaVersion: 1,
      result,
      renderArtifactIds,
      reports: inspected,
      printerPreflights: inspectedPreflights,
      printerPreflightArtifactIds,
      studioReady,
      findings,
    };
    const artifact: AnswerArtifact = {
      kind: "render_inspection",
      schemaVersion: context.offer.contractVersion,
      mediaType: "application/json",
      payload: { kind: "json", value },
      parents: [
        ...renderArtifactIds.map((artifactId) => ({
          artifactId,
          relation: "inspected_render",
        })),
        ...context.offer.inputArtifacts
          .filter((artifactId) => !renderArtifactIds.includes(artifactId))
          .map((artifactId) => ({
            artifactId,
            relation: "inspection_context",
          })),
      ],
      metadata: {
        executorId: this.id,
        renderOfferId,
        reportCount: reports.length,
      },
    };
    return {
      contractVersion: context.offer.contractVersion,
      result: {
        result,
        renderArtifactIds,
        printerPreflightArtifactIds,
        studioReady,
        ...(findings.length === 0 ? {} : { findings }),
      },
      artifacts: [artifact],
      metadata: { executorId: this.id },
    };
  }
}

function criticFindings(report: Readonly<Record<string, unknown>>): readonly JsonValue[] {
  const candidates = [report.findings, report.errors, report.issues];
  return candidates.flatMap((candidate) =>
    Array.isArray(candidate) ? candidate.filter(isJsonValue) : []
  );
}

function requireUnique(values: readonly string[], label: string): void {
  if (new Set(values).size !== values.length) {
    throw permanentAdapterError(`${label} must be unique`);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isJsonValue(value: unknown): value is JsonValue {
  if (
    value === null ||
    typeof value === "boolean" ||
    typeof value === "string" ||
    (typeof value === "number" && Number.isFinite(value))
  ) {
    return true;
  }
  if (Array.isArray(value)) {
    return value.every(isJsonValue);
  }
  return isRecord(value) && Object.values(value).every(isJsonValue);
}
