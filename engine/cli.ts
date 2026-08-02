import { mkdir, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { parseArgs } from "node:util";

import {
  ArticleLab,
  compareArticleRuns,
  parseArticleEvaluationCorpus,
} from "./article-lab/index.ts";
import { createConfiguredWorker, runWorker } from "./executors/index.ts";
import type {
  ActorId,
  ArticlePromotionRequest,
  JsonObject,
  RunId,
  RunInputChange,
  SubmitLeadRequest,
  WorkAnswer,
  WorkerCapability,
  WorkOfferId,
} from "./contracts/index.ts";
import { parseRunSpec } from "./contracts/index.ts";
import { SqliteRunEngine } from "./run-engine/run-engine.ts";
import { serveRunViewer } from "./view/server.ts";

const HELP = `Usage:
  npm run engine -- start <run-spec.json> [--idempotency-key KEY] [--db PATH] [--artifacts PATH]
  npm run engine -- inspect <run-id> [--db PATH] [--artifacts PATH]
  npm run engine -- continue <run-id> [--db PATH] [--artifacts PATH]
  npm run engine -- retry <run-id> <actor-id> [--db PATH] [--artifacts PATH]
  npm run engine -- submit-lead <run-id> <lead.json> [--db PATH] [--artifacts PATH]
  npm run engine -- fork <run-id> <changes.json> [--idempotency-key KEY] [--db PATH] [--artifacts PATH]
  npm run engine -- compare <run-id> <run-id> [...] [--db PATH] [--artifacts PATH]
  npm run engine -- article corpus <corpus.json> [--db PATH] [--artifacts PATH]
  npm run engine -- promote <run-id> <promotion.json> [--db PATH] [--artifacts PATH]
  npm run engine -- worker <run-id> <worker-config.json> [--once] [--poll-ms NUMBER]
      [--heartbeat-ms NUMBER] [--timeout-ms NUMBER] [--concurrency NUMBER]
  npm run engine -- answer <run-id> <offer-id> <answer.json> [--principal ID]
  npm run engine -- seal <run-id> [--db PATH] [--artifacts PATH]
  npm run engine -- serve [--port NUMBER] [--db PATH] [--artifacts PATH]

The article aliases "article run", "article inspect", "article continue",
"article fork", "article compare", "article corpus", and "article promote" use the same durable engine.`;

type ParsedCommand = {
  readonly command: string;
  readonly args: readonly string[];
  readonly databasePath: string;
  readonly artifactDirectory: string;
  readonly principal: string;
  readonly port: number;
  readonly once: boolean;
  readonly pollIntervalMs?: number;
  readonly heartbeatIntervalMs?: number;
  readonly attemptTimeoutMs?: number;
  readonly maxConcurrency?: number;
  readonly idempotencyKey?: string;
};

async function main(argv: readonly string[]): Promise<number> {
  const parsed = parseCommand(argv);
  if (parsed.command === "help") {
    process.stdout.write(`${HELP}\n`);
    return 0;
  }
  await mkdir(dirname(parsed.databasePath), { recursive: true });
  await mkdir(parsed.artifactDirectory, { recursive: true });
  const engine = new SqliteRunEngine({
    databasePath: parsed.databasePath,
    artifactDirectory: parsed.artifactDirectory,
  });
  if (parsed.command === "serve") {
    try {
      const viewer = await serveRunViewer(engine, {
        host: "127.0.0.1",
        port: parsed.port,
        staticDirectory: resolve(import.meta.dirname, "view/dist"),
      });
      process.stdout.write(`Run viewer: http://${viewer.host}:${viewer.port}\n`);
      await waitForShutdown();
      await viewer.close();
      return 0;
    } finally {
      engine.close();
    }
  }
  try {
    switch (parsed.command) {
      case "start": {
        const path = requiredArg(parsed.args, 0, "run spec path");
        writeJson(await engine.start(
          parseRunSpec(await readJson<unknown>(path)),
          parsed.idempotencyKey === undefined
            ? undefined
            : { idempotencyKey: parsed.idempotencyKey },
        ));
        return 0;
      }
      case "inspect": {
        writeJson(await engine.inspect(asRunId(requiredArg(parsed.args, 0, "run ID"))));
        return 0;
      }
      case "continue": {
        writeJson(await engine.advance(asRunId(requiredArg(parsed.args, 0, "run ID"))));
        return 0;
      }
      case "retry": {
        const runId = asRunId(requiredArg(parsed.args, 0, "run ID"));
        const actorId = requiredArg(parsed.args, 1, "actor ID") as ActorId;
        writeJson(await engine.retry(runId, actorId));
        return 0;
      }
      case "submit-lead": {
        const runId = asRunId(requiredArg(parsed.args, 0, "run ID"));
        const request = await readJson<SubmitLeadRequest>(
          requiredArg(parsed.args, 1, "lead submission path"),
        );
        writeJson(await engine.submitLead(runId, request));
        return 0;
      }
      case "fork": {
        const runId = asRunId(requiredArg(parsed.args, 0, "run ID"));
        const changes = await readJson<readonly RunInputChange[]>(
          requiredArg(parsed.args, 1, "changes path"),
        );
        writeJson(await engine.fork(
          runId,
          changes,
          parsed.idempotencyKey === undefined
            ? undefined
            : { idempotencyKey: parsed.idempotencyKey },
        ));
        return 0;
      }
      case "compare": {
        const runIds = parsed.args.map(asRunId);
        if (runIds.length < 2) {
          throw new Error("compare requires at least two run IDs");
        }
        writeJson(await compareArticleRuns(engine, runIds));
        return 0;
      }
      case "corpus": {
        const corpus = parseArticleEvaluationCorpus(
          await readJson<unknown>(requiredArg(parsed.args, 0, "corpus path")),
        );
        writeJson(await new ArticleLab(engine).startCorpus(corpus));
        return 0;
      }
      case "promote": {
        const runId = asRunId(requiredArg(parsed.args, 0, "run ID"));
        const request = await readJson<ArticlePromotionRequest>(
          requiredArg(parsed.args, 1, "promotion request path"),
        );
        writeJson(await engine.promoteArticle(runId, request));
        return 0;
      }
      case "worker": {
        const runId = asRunId(requiredArg(parsed.args, 0, "run ID"));
        const configuration = createConfiguredWorker(await readJson<unknown>(
          requiredArg(parsed.args, 1, "worker configuration path"),
        ));
        const shutdown = shutdownController();
        try {
          writeJson(await runWorker(
            engine,
            runId,
            configuration.resolver,
            shutdown.signal,
            {
              ...configuration.options,
              once: parsed.once,
              ...(parsed.pollIntervalMs === undefined
                ? {}
                : { pollIntervalMs: parsed.pollIntervalMs }),
              ...(parsed.heartbeatIntervalMs === undefined
                ? {}
                : { heartbeatIntervalMs: parsed.heartbeatIntervalMs }),
              ...(parsed.attemptTimeoutMs === undefined
                ? {}
                : { attemptTimeoutMs: parsed.attemptTimeoutMs }),
              ...(parsed.maxConcurrency === undefined
                ? {}
                : { maxConcurrency: parsed.maxConcurrency }),
            },
          ));
          return 0;
        } finally {
          shutdown.dispose();
        }
      }
      case "answer": {
        const runId = asRunId(requiredArg(parsed.args, 0, "run ID"));
        const offerId = asOfferId(requiredArg(parsed.args, 1, "offer ID"));
        const answer = await readJson<WorkAnswer>(requiredArg(parsed.args, 2, "answer path"));
        const view = await engine.inspect(runId);
        const offer = view.offers.find((candidate) => candidate.id === offerId);
        if (offer === undefined) {
          throw new Error(`offer ${offerId} is not part of run ${runId}`);
        }
        const claim = await engine.claim(offerId, {
          principalId: parsed.principal,
          displayName: parsed.principal,
          authority: "human",
          capabilities: humanCapabilities(offer.allowedWorkerCapabilities),
        });
        await engine.answer(claim, answer);
        writeJson(await engine.advance(runId));
        return 0;
      }
      case "seal": {
        const artifactId = await engine.seal(asRunId(requiredArg(parsed.args, 0, "run ID")));
        writeJson({ artifactId });
        return 0;
      }
      default:
        throw new Error(`unknown command: ${parsed.command}`);
    }
  } finally {
    engine.close();
  }
}

function parseCommand(argv: readonly string[]): ParsedCommand {
  const parsed = parseArgs({
    args: [...argv],
    allowPositionals: true,
    strict: true,
    options: {
      artifacts: { type: "string" },
      db: { type: "string" },
      help: { type: "boolean", short: "h" },
      "heartbeat-ms": { type: "string" },
      "idempotency-key": { type: "string" },
      "timeout-ms": { type: "string" },
      "poll-ms": { type: "string" },
      concurrency: { type: "string" },
      once: { type: "boolean" },
      port: { type: "string" },
      principal: { type: "string" },
    },
  });
  if (parsed.values.help === true || parsed.positionals.length === 0) {
    return defaults("help", []);
  }
  const positionals = [...parsed.positionals];
  let command = positionals.shift() ?? "help";
  if (command === "article") {
    command = positionals.shift() ?? "help";
  }
  if (command === "run") {
    command = "start";
  }
  const port = Number.parseInt(parsed.values.port ?? "4173", 10);
  if (!Number.isSafeInteger(port) || port < 0 || port > 65_535) {
    throw new Error("port must be an integer from 0 through 65535");
  }
  return {
    command,
    args: positionals,
    databasePath: resolve(parsed.values.db ?? "runs/xstate-engine.sqlite"),
    artifactDirectory: resolve(parsed.values.artifacts ?? "runs/xstate-artifacts"),
    principal: parsed.values.principal ?? "local-human",
    port,
    once: parsed.values.once ?? false,
    ...(parsed.values["idempotency-key"] === undefined
      ? {}
      : { idempotencyKey: parsed.values["idempotency-key"] }),
    ...optionalPositiveInteger("poll-ms", parsed.values["poll-ms"], "pollIntervalMs"),
    ...optionalPositiveInteger(
      "heartbeat-ms",
      parsed.values["heartbeat-ms"],
      "heartbeatIntervalMs",
    ),
    ...optionalPositiveInteger("timeout-ms", parsed.values["timeout-ms"], "attemptTimeoutMs"),
    ...optionalPositiveInteger("concurrency", parsed.values.concurrency, "maxConcurrency"),
  };
}

function defaults(command: string, args: readonly string[]): ParsedCommand {
  return {
    command,
    args,
    databasePath: resolve("runs/xstate-engine.sqlite"),
    artifactDirectory: resolve("runs/xstate-artifacts"),
    principal: "local-human",
    port: 4173,
    once: false,
  };
}

function optionalPositiveInteger<Key extends string>(
  option: string,
  value: string | undefined,
  key: Key,
): { readonly [Property in Key]?: number } {
  if (value === undefined) {
    return {};
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isSafeInteger(parsed) || parsed <= 0 || String(parsed) !== value) {
    throw new Error(`${option} must be a positive integer`);
  }
  return { [key]: parsed } as { readonly [Property in Key]: number };
}

async function readJson<T>(path: string): Promise<T> {
  const value: unknown = JSON.parse(await readFile(resolve(path), "utf8"));
  return value as T;
}

function requiredArg(args: readonly string[], index: number, label: string): string {
  const value = args[index];
  if (value === undefined || !value) {
    throw new Error(`${label} is required`);
  }
  return value;
}

function asRunId(value: string): RunId {
  return value as RunId;
}

function asOfferId(value: string): WorkOfferId {
  return value as WorkOfferId;
}

function humanCapabilities(
  required: ReadonlyArray<WorkerCapability>,
): ReadonlyArray<WorkerCapability> {
  return [
    "human" as const,
    ...(required.includes("source_access") ? ["source_access" as const] : []),
  ];
}

function writeJson(value: JsonObject | unknown): void {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

async function waitForShutdown(): Promise<void> {
  await new Promise<void>((resolveSignal) => {
    process.once("SIGINT", resolveSignal);
    process.once("SIGTERM", resolveSignal);
  });
}

function shutdownController(): AbortController & { readonly dispose: () => void } {
  const controller = new AbortController();
  const abort = (): void => controller.abort();
  process.once("SIGINT", abort);
  process.once("SIGTERM", abort);
  return Object.assign(controller, {
    dispose: () => {
      process.removeListener("SIGINT", abort);
      process.removeListener("SIGTERM", abort);
    },
  });
}

main(process.argv.slice(2)).then(
  (code) => {
    process.exitCode = code;
  },
  (error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  },
);
