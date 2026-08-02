import { spawn } from "node:child_process";
import { isAbsolute, relative, resolve, sep } from "node:path";
import process from "node:process";

import { z } from "zod";

import type { JsonObject, WorkAnswer, WorkOfferView, WorkerIdentity } from "../contracts/index.ts";
import type { Executor, ExecutorContext } from "./types.ts";

const MAX_CAPTURE_BYTES = 16 * 1024 * 1024;

const artifactPayloadSchema = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("bytes"), dataBase64: z.string() }).strict(),
  z.object({ kind: z.literal("file"), path: z.string().min(1) }).strict(),
  z.object({ kind: z.literal("json"), value: z.json() }).strict(),
  z.object({ kind: z.literal("text"), text: z.string() }).strict(),
]);

const answerArtifactSchema = z.object({
  id: z.string().min(1).optional(),
  kind: z.string().min(1),
  schemaVersion: z.string().min(1),
  mediaType: z.string().min(1),
  origin: z.enum(["human", "imported", "machine", "model", "subprocess"]).optional(),
  payload: artifactPayloadSchema,
  parents: z.array(z.object({
    artifactId: z.string().min(1),
    relation: z.string().min(1),
  }).strict()).optional(),
  metadata: z.record(z.string(), z.json()).optional(),
  supersedes: z.string().min(1).optional(),
}).strict();

const answerSchema = z.object({
  contractVersion: z.string().min(1),
  result: z.record(z.string(), z.json()),
  artifacts: z.array(answerArtifactSchema),
  metadata: z.record(z.string(), z.json()).optional(),
}).strict();

export type SubprocessCommand = {
  readonly executable: string;
  readonly args: readonly string[];
  readonly cwd: string;
  readonly env?: Readonly<Record<string, string>>;
  readonly timeoutMs: number;
  readonly terminateGraceMs?: number;
  readonly stdin: string;
  readonly outputDirectory?: string;
};

export type SubprocessCommandBuilder = (
  context: ExecutorContext,
  task: string,
) => Promise<SubprocessCommand> | SubprocessCommand;

export class SubprocessExecutionError extends Error {
  readonly classification: "permanent" | "retryable" | "timeout";
  readonly exitCode: number | null;
  readonly stderr: string;

  constructor(
    message: string,
    classification: "permanent" | "retryable" | "timeout",
    exitCode: number | null,
    stderr: string,
  ) {
    super(message);
    this.name = "SubprocessExecutionError";
    this.classification = classification;
    this.exitCode = exitCode;
    this.stderr = stderr;
  }
}

export class SubprocessExecutor implements Executor {
  readonly id: string;
  readonly worker: WorkerIdentity;
  readonly capabilities;
  private readonly buildCommand: SubprocessCommandBuilder;
  private readonly predicate: (offer: WorkOfferView) => boolean;

  constructor(
    id: string,
    worker: WorkerIdentity,
    buildCommand: SubprocessCommandBuilder,
    predicate: (offer: WorkOfferView) => boolean = () => true,
  ) {
    this.id = id;
    this.worker = worker;
    this.buildCommand = buildCommand;
    this.predicate = predicate;
    this.capabilities = worker.capabilities;
  }

  accepts(offer: WorkOfferView): boolean {
    return this.predicate(offer);
  }

  async execute(context: ExecutorContext): Promise<WorkAnswer> {
    const task = await materializeWorkPackage(context);
    const command = await this.buildCommand(context, task);
    const result = await runSubprocess(command, context.signal);
    let parsed: unknown;
    try {
      parsed = JSON.parse(result.stdout);
    } catch (error) {
      throw new SubprocessExecutionError(
        `executor ${this.id} returned invalid JSON: ${String(error)}`,
        "permanent",
        result.exitCode,
        result.stderr,
      );
    }
    const validated = answerSchema.safeParse(parsed);
    if (!validated.success) {
      throw new SubprocessExecutionError(
        `executor ${this.id} violated the work-answer contract: ${validated.error.message}`,
        "permanent",
        result.exitCode,
        result.stderr,
      );
    }
    for (const artifact of validated.data.artifacts) {
      if (artifact.payload.kind !== "file") {
        continue;
      }
      if (command.outputDirectory === undefined || !isAbsolute(artifact.payload.path)) {
        throw new SubprocessExecutionError(
          `executor ${this.id} returned a file outside an owned output directory`,
          "permanent",
          result.exitCode,
          result.stderr,
        );
      }
      const outputRoot = resolve(command.outputDirectory);
      const outputPath = resolve(artifact.payload.path);
      const relation = relative(outputRoot, outputPath);
      if (
        relation === "" ||
        relation === ".." ||
        relation.startsWith(`..${sep}`) ||
        isAbsolute(relation)
      ) {
        throw new SubprocessExecutionError(
          `executor ${this.id} returned a file outside its owned output directory`,
          "permanent",
          result.exitCode,
          result.stderr,
        );
      }
    }
    return validated.data as unknown as WorkAnswer;
  }
}

export async function materializeWorkPackage(
  context: ExecutorContext,
): Promise<string> {
  const taskText = await context.artifacts.readText(context.offer.taskArtifactId);
  const inputIds = context.offer.inputArtifacts.filter(
    (artifactId, index, all) =>
      artifactId !== context.offer.taskArtifactId && all.indexOf(artifactId) === index,
  );
  const inputs = await Promise.all(
    inputIds.map(async (artifactId) => ({
      artifactId,
      text: await context.artifacts.readText(artifactId),
    })),
  );
  return JSON.stringify({
    schemaVersion: 1,
    offer: {
      id: context.offer.id,
      runId: context.offer.runId,
      actorId: context.offer.actorId,
      actorKey: context.offer.actorKey,
      state: context.offer.state,
      stateVisitId: context.offer.stateVisitId,
      role: context.offer.role,
      slot: context.offer.slot,
      contractVersion: context.offer.contractVersion,
      ...(context.offer.iterationId === undefined
        ? {}
        : { iterationId: context.offer.iterationId }),
      ...(context.offer.revisionId === undefined
        ? {}
        : { revisionId: context.offer.revisionId }),
    },
    task: {
      artifactId: context.offer.taskArtifactId,
      text: taskText,
    },
    inputs,
  });
}

export type ProcessResult = {
  readonly exitCode: number;
  readonly stdout: string;
  readonly stderr: string;
};

export async function runSubprocess(
  command: SubprocessCommand,
  signal: AbortSignal,
): Promise<ProcessResult> {
  return await new Promise<ProcessResult>((resolve, reject) => {
    const child = spawn(command.executable, [...command.args], {
      cwd: command.cwd,
      detached: process.platform !== "win32",
      env: {
        ...process.env,
        ...command.env,
      },
      shell: false,
      stdio: ["pipe", "pipe", "pipe"],
    });
    const stdout: Buffer[] = [];
    const stderr: Buffer[] = [];
    let capturedBytes = 0;
    let timedOut = false;
    let settled = false;

    const terminate = (hard: boolean): void => {
      if (child.pid === undefined) {
        return;
      }
      const target = process.platform === "win32" ? child.pid : -child.pid;
      try {
        process.kill(target, hard ? "SIGKILL" : "SIGTERM");
      } catch (error) {
        const code = (error as NodeJS.ErrnoException).code;
        if (code !== "ESRCH") {
          reject(error);
        }
      }
    };

    const timeout = setTimeout(() => {
      timedOut = true;
      terminate(false);
      setTimeout(() => terminate(true), command.terminateGraceMs ?? 2_000).unref();
    }, command.timeoutMs);
    timeout.unref();

    const abort = (): void => terminate(false);
    signal.addEventListener("abort", abort, { once: true });

    const collect = (destination: Buffer[], chunk: Buffer): void => {
      capturedBytes += chunk.length;
      if (capturedBytes > MAX_CAPTURE_BYTES) {
        terminate(true);
        reject(new SubprocessExecutionError(
          `subprocess output exceeded ${MAX_CAPTURE_BYTES} bytes`,
          "permanent",
          null,
          Buffer.concat(stderr).toString("utf8"),
        ));
        return;
      }
      destination.push(chunk);
    };

    child.stdout.on("data", (chunk: Buffer) => collect(stdout, chunk));
    child.stderr.on("data", (chunk: Buffer) => collect(stderr, chunk));
    child.once("error", (error) => {
      clearTimeout(timeout);
      signal.removeEventListener("abort", abort);
      if (!settled) {
        settled = true;
        reject(error);
      }
    });
    child.once("close", (code, closeSignal) => {
      clearTimeout(timeout);
      signal.removeEventListener("abort", abort);
      if (settled) {
        return;
      }
      settled = true;
      const stdoutText = Buffer.concat(stdout).toString("utf8");
      const stderrText = Buffer.concat(stderr).toString("utf8");
      if (timedOut) {
        reject(new SubprocessExecutionError(
          `subprocess timed out after ${command.timeoutMs}ms`,
          "timeout",
          code,
          stderrText,
        ));
      } else if (signal.aborted) {
        reject(new SubprocessExecutionError(
          "subprocess was canceled",
          "retryable",
          code,
          stderrText,
        ));
      } else if (code !== 0) {
        reject(new SubprocessExecutionError(
          `subprocess exited ${code ?? closeSignal ?? "without status"}`,
          "retryable",
          code,
          stderrText,
        ));
      } else {
        resolve({ exitCode: code, stdout: stdoutText, stderr: stderrText });
      }
    });
    child.stdin.end(command.stdin, "utf8");
  });
}
