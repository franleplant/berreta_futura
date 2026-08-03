import { mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
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
  HumanDecisionIntent,
  JsonObject,
  RunId,
  RunInputChange,
  SubmitLeadRequest,
  WorkOfferId,
  DecisionId,
  RevisionId,
} from "./contracts/index.ts";
import { parseRunSpec } from "./contracts/index.ts";
import { LocalAuthorityStore, type AuthorizedWorker } from "./authority/local-authority.ts";
import { EditionBootstrapRunner } from "./edition-bootstrap-run.ts";
import { EditionRunLayout } from "./edition-run-layout.ts";
import { EditionProductionRunner } from "./write-production.ts";
import { materializeEdition4TranslationPrompt, materializeEdition4WritePipeline } from "./edition4-write-pipeline.ts";
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
  npm run engine -- authority init [--authority-dir PATH]
  npm run engine -- authority enroll-human <enrollment.json> [--authority-dir PATH]
  npm run engine -- authority issue-credential <credential-profile.json> [--authority-dir PATH]
  npm run engine -- authority grant <grant.json> [--authority-dir PATH]
  npm run engine -- authority revoke <revocation.json> [--authority-dir PATH]
  npm run engine -- human decide <run-id> <offer-id> <decision.json> --credential <credential.json>
  npm run engine -- seal <run-id> [--db PATH] [--artifacts PATH]
  npm run engine -- edition plan <edition-key> --write-pipeline REVISION [--output-root PATH]
  npm run engine -- edition produce <edition-key> --write-pipeline REVISION [--output-root PATH]
  npm run engine -- edition materialize-write-pipeline 004
  npm run engine -- edition plan <edition-key> --bootstrap-revision REVISION [--output-root PATH]
  npm run engine -- edition run <edition-key> --bootstrap-revision REVISION [--output-root PATH]
  npm run engine -- edition list <edition-key> [--output-root PATH]
  npm run engine -- edition project-review <edition-key> <run-id> --expected-head NUMBER
      --expected-offer OFFER_ID --critic-note TEXT [--output-root PATH]
  npm run engine -- export <edition-key> <run-id> [--output-root PATH]
      [--expected-visual-decision ID]
  npm run engine -- serve --credential <credential.json> [--port NUMBER] [--db PATH] [--artifacts PATH]

The article aliases "article run", "article inspect", "article continue",
"article fork", "article compare", "article corpus", and "article promote" use the same durable engine.`;

type ParsedCommand = {
  readonly command: string;
  readonly args: readonly string[];
  readonly databasePath: string;
  readonly artifactDirectory: string;
  readonly authorityDirectory: string;
  readonly credentialPath?: string;
  readonly port: number;
  readonly once: boolean;
  readonly pollIntervalMs?: number;
  readonly heartbeatIntervalMs?: number;
  readonly attemptTimeoutMs?: number;
  readonly maxConcurrency?: number;
  readonly idempotencyKey?: string;
  readonly outputRoot: string;
  readonly expectedVisualDecisionId?: DecisionId;
  readonly bootstrapRevisionId?: RevisionId;
  readonly writePipelineRevisionId?: RevisionId;
  readonly expectedHeadSequence?: number;
  readonly expectedOfferId?: WorkOfferId;
  readonly independentCriticNote?: string;
};

async function main(argv: readonly string[]): Promise<number> {
  const parsed = parseCommand(argv);
  if (parsed.command === "help") {
    process.stdout.write(`${HELP}\n`);
    return 0;
  }
  if (parsed.command.startsWith("authority-")) {
    const store = await LocalAuthorityStore.init(parsed.authorityDirectory);
    switch (parsed.command) {
      case "authority-init":
        requireArgCount(parsed.args, 0, "authority init");
        writeJson({ directory: store.directory, authorization: await store.snapshot() });
        return 0;
      case "authority-enroll-human":
        requireArgCount(parsed.args, 1, "authority enroll-human");
        writeJson(await store.enrollHuman(await readJson<unknown>(requiredArg(parsed.args, 0, "enrollment path"))));
        return 0;
      case "authority-issue-credential":
        requireArgCount(parsed.args, 1, "authority issue-credential");
        {
          const credential = await store.createCredentialProfile(
          await readJson<unknown>(requiredArg(parsed.args, 0, "credential profile path")),
          );
          const credentialFile = await writeCredentialFile(store.directory, credential);
          writeJson({
            credentialProfileId: credential.credentialProfileId,
            principalId: credential.principalId,
            credentialFile,
          });
        }
        return 0;
      case "authority-grant":
        requireArgCount(parsed.args, 1, "authority grant");
        writeJson(await store.grant(await readJson<unknown>(requiredArg(parsed.args, 0, "grant path"))));
        return 0;
      case "authority-revoke":
        requireArgCount(parsed.args, 1, "authority revoke");
        writeJson(await store.revoke(await readJson<unknown>(requiredArg(parsed.args, 0, "revocation path"))));
        return 0;
      default:
        throw new Error(`unknown authority command: ${parsed.command.slice("authority-".length)}`);
    }
  }
  if (parsed.command === "edition-plan" || parsed.command === "edition-produce" || parsed.command === "edition-run") {
    const editionKey = requiredArg(parsed.args, 0, "edition key");
    requireArgCount(parsed.args, 1, parsed.command.replace("edition-", "edition "));
    if (parsed.writePipelineRevisionId !== undefined) {
      if (parsed.bootstrapRevisionId !== undefined) {
        throw new Error("choose exactly one of --write-pipeline or --bootstrap-revision");
      }
      const pipeline = {
        kind: "write_pipeline" as const,
        editionId: editionKey,
        logicalId: "edition4-write",
        revisionId: parsed.writePipelineRevisionId,
      };
      const runner = new EditionProductionRunner({
        editionKey,
        repositoryRoot: resolve("."),
        outputRoot: parsed.outputRoot,
      });
      writeJson(parsed.command === "edition-plan"
        ? await runner.plan(pipeline)
        : await runner.produce(pipeline));
      return 0;
    }
    if (parsed.command === "edition-produce") {
      throw new Error("edition produce requires --write-pipeline REVISION");
    }
    if (parsed.bootstrapRevisionId === undefined) {
      throw new Error("bootstrap revision is required; pass --bootstrap-revision REVISION");
    }
    const bootstrapRevision = {
      kind: "run_bootstrap" as const,
      editionId: editionKey,
      logicalId: "fresh-v2",
      revisionId: parsed.bootstrapRevisionId,
    };
    const runner = new EditionBootstrapRunner({
      editionKey,
      repositoryRoot: resolve("."),
      outputRoot: parsed.outputRoot,
      render: {
        primaryLanguage: "en",
        publicationName: "Berreta Futura",
        renderer: "weasyprint",
      },
      ...(parsed.command === "edition-run"
        ? { authority: { toolWorker: await authenticateBootstrapTool(parsed) } }
        : {}),
    });
    writeJson(parsed.command === "edition-plan"
      ? await runner.plan(bootstrapRevision)
      : await runner.run(bootstrapRevision));
    return 0;
  }
  if (parsed.command === "edition-materialize-write-pipeline") {
    const editionKey = requiredArg(parsed.args, 0, "edition key");
    requireArgCount(parsed.args, 1, "edition materialize-write-pipeline");
    if (editionKey !== "004") throw new Error("edition materialize-write-pipeline currently supports Edition 004 only");
    const prompt = await materializeEdition4TranslationPrompt(resolve("."), tmpdir());
    const pipeline = await materializeEdition4WritePipeline(resolve("."), tmpdir(), prompt.ref);
    writeJson({ schemaVersion: "edition4-write-pipeline-materialization/1", prompt, pipeline });
    return 0;
  }
  if (parsed.command === "edition-list") {
    const editionKey = requiredArg(parsed.args, 0, "edition key");
    requireArgCount(parsed.args, 1, "edition list");
    if (parsed.bootstrapRevisionId !== undefined) {
      throw new Error("edition list does not accept --bootstrap-revision");
    }
    const layout = new EditionRunLayout({
      editionKey,
      repositoryRoot: resolve("."),
      outputRoot: parsed.outputRoot,
    });
    const runs = await layout.list();
    writeJson({
      schemaVersion: "edition-run-list/1",
      editionKey,
      runs: runs.map((run) => ({ ...run, ...layout.pathsFor(run) })),
    });
    return 0;
  }
  if (parsed.command === "edition-project-review") {
    const editionKey = requiredArg(parsed.args, 0, "edition key");
    const runId = asRunId(requiredArg(parsed.args, 1, "run ID"));
    requireArgCount(parsed.args, 2, "edition project-review");
    if (parsed.expectedHeadSequence === undefined) {
      throw new Error("edition project-review requires --expected-head NUMBER");
    }
    if (parsed.expectedOfferId === undefined) {
      throw new Error("edition project-review requires --expected-offer OFFER_ID");
    }
    if (parsed.independentCriticNote === undefined || !parsed.independentCriticNote.trim()) {
      throw new Error("edition project-review requires a non-empty --critic-note TEXT");
    }
    const layout = new EditionRunLayout({
      editionKey,
      repositoryRoot: resolve("."),
      outputRoot: parsed.outputRoot,
    });
    writeJson(await layout.projectReview(runId, {
      expectedHeadSequence: parsed.expectedHeadSequence,
      expectedOfferId: parsed.expectedOfferId,
      independentCritic: {
        result: "pass",
        note: parsed.independentCriticNote,
      },
    }));
    return 0;
  }
  if (parsed.command.startsWith("edition-")) {
    throw new Error(`unknown edition command: ${parsed.command.slice("edition-".length)}`);
  }
  if (parsed.command === "export") {
    const editionKey = requiredArg(parsed.args, 0, "edition key");
    const runId = asRunId(requiredArg(parsed.args, 1, "run ID"));
    const layout = new EditionRunLayout({
      editionKey,
      repositoryRoot: resolve("."),
      outputRoot: parsed.outputRoot,
    });
    writeJson(await layout.publish(runId, {
      ...(parsed.expectedVisualDecisionId === undefined
        ? {}
        : { expectedVisualDecisionId: parsed.expectedVisualDecisionId }),
    }));
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
      const worker = await authenticateHuman(parsed);
      const viewer = await serveRunViewer(engine, {
        host: "127.0.0.1",
        port: parsed.port,
        staticDirectory: resolve(import.meta.dirname, "view/dist"),
        humanWorker: worker,
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
        const configuration = await createConfiguredWorker(
          await readJson<unknown>(requiredArg(parsed.args, 1, "worker configuration path")),
          { authorityDirectory: parsed.authorityDirectory },
        );
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
      case "human-decide": {
        requireArgCount(parsed.args, 3, "human decide");
        const runId = asRunId(requiredArg(parsed.args, 0, "run ID"));
        const offerId = asOfferId(requiredArg(parsed.args, 1, "offer ID"));
        const worker = await authenticateHuman(parsed);
        await assertOfferInRun(engine, runId, offerId);
        const preparation = await engine.prepareHumanDecision(offerId, worker);
        const decision = parseHumanDecisionInput(await readJson<unknown>(
          requiredArg(parsed.args, 2, "decision path"),
        ));
        const intent: HumanDecisionIntent = {
          schemaVersion: "human-decision-intent/1",
          offerId: preparation.offerId,
          taskArtifactId: preparation.taskArtifactId,
          inputArtifactIds: preparation.inputArtifactIds,
          result: decision.result,
        };
        await engine.decide(preparation, worker, intent);
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
      "authority-dir": { type: "string" },
      credential: { type: "string" },
      "output-root": { type: "string" },
      "expected-visual-decision": { type: "string" },
      "bootstrap-revision": { type: "string" },
      "write-pipeline": { type: "string" },
      "expected-head": { type: "string" },
      "expected-offer": { type: "string" },
      "critic-note": { type: "string" },
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
  if (command === "authority" || command === "human") {
    command = `${command}-${positionals.shift() ?? "help"}`;
  }
  if (command === "edition") {
    const editionCommand = positionals.shift() ?? "help";
    command = editionCommand === "help" ? "help" : `edition-${editionCommand}`;
  }
  if (command === "run") {
    command = "start";
  }
  const port = Number.parseInt(parsed.values.port ?? "4173", 10);
  if (!Number.isSafeInteger(port) || port < 0 || port > 65_535) {
    throw new Error("port must be an integer from 0 through 65535");
  }
  const databasePath = resolve(parsed.values.db ?? ".magazine/dev/run.sqlite");
  return {
    command,
    args: positionals,
    databasePath,
    artifactDirectory: resolve(parsed.values.artifacts ?? ".magazine/dev/artifacts"),
    authorityDirectory: resolve(parsed.values["authority-dir"] ?? dirname(databasePath), "authority"),
    port,
    once: parsed.values.once ?? false,
    outputRoot: parsed.values["output-root"] ?? resolve("output"),
    ...(parsed.values["expected-visual-decision"] === undefined
      ? {}
      : {
          expectedVisualDecisionId:
            parsed.values["expected-visual-decision"] as DecisionId,
        }),
    ...(parsed.values["bootstrap-revision"] === undefined
      ? {}
      : { bootstrapRevisionId: parsed.values["bootstrap-revision"] as RevisionId }),
    ...(parsed.values["write-pipeline"] === undefined
      ? {}
      : { writePipelineRevisionId: parsed.values["write-pipeline"] as RevisionId }),
    ...(parsed.values.credential === undefined
      ? {}
      : { credentialPath: parsed.values.credential }),
    ...optionalNonNegativeInteger(
      "expected-head",
      parsed.values["expected-head"],
      "expectedHeadSequence",
    ),
    ...(parsed.values["expected-offer"] === undefined
      ? {}
      : { expectedOfferId: parsed.values["expected-offer"] as WorkOfferId }),
    ...(parsed.values["critic-note"] === undefined
      ? {}
      : { independentCriticNote: parsed.values["critic-note"] }),
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
    databasePath: resolve(".magazine/dev/run.sqlite"),
    artifactDirectory: resolve(".magazine/dev/artifacts"),
    authorityDirectory: resolve(".magazine/dev/authority"),
    port: 4173,
    once: false,
    outputRoot: resolve("output"),
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

function optionalNonNegativeInteger<Key extends string>(
  option: string,
  value: string | undefined,
  key: Key,
): { readonly [Property in Key]?: number } {
  if (value === undefined) return {};
  const parsed = Number.parseInt(value, 10);
  if (!Number.isSafeInteger(parsed) || parsed < 0 || String(parsed) !== value) {
    throw new Error(`${option} must be a non-negative integer`);
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

function requireArgCount(args: readonly string[], count: number, command: string): void {
  if (args.length !== count) {
    throw new Error(`${command} requires exactly ${count} positional argument${count === 1 ? "" : "s"}`);
  }
}

function asRunId(value: string): RunId {
  return value as RunId;
}

function asOfferId(value: string): WorkOfferId {
  return value as WorkOfferId;
}

async function authenticateHuman(parsed: ParsedCommand): Promise<AuthorizedWorker> {
  if (parsed.credentialPath === undefined) {
    throw new Error("an authenticated human session requires --credential <credential.json>");
  }
  const store = await LocalAuthorityStore.init(parsed.authorityDirectory);
  const worker = await store.authenticate(await readJson<unknown>(parsed.credentialPath));
  const description = await worker.describe();
  if (description.authority !== "human") {
    throw new Error("credential does not authenticate a human principal");
  }
  return worker;
}

async function authenticateBootstrapTool(parsed: ParsedCommand): Promise<AuthorizedWorker> {
  if (parsed.credentialPath === undefined) {
    throw new Error("edition run requires --credential for an authenticated subprocess tool");
  }
  const store = await LocalAuthorityStore.init(parsed.authorityDirectory);
  const worker = await store.authenticate(await readJson<unknown>(parsed.credentialPath));
  const description = await worker.describe();
  if (description.authority !== "tool" || !description.capabilities.includes("subprocess")) {
    throw new Error("edition run credential must authenticate a tool principal with subprocess capability");
  }
  return worker;
}

async function writeCredentialFile(
  authorityDirectory: string,
  credential: { readonly credentialProfileId: string; readonly principalId: string; readonly secret: string },
): Promise<string> {
  const directory = join(authorityDirectory, "credentials");
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const path = join(directory, `${credential.credentialProfileId}.json`);
  await writeFile(
    path,
    `${JSON.stringify({
      credentialProfileId: credential.credentialProfileId,
      secret: credential.secret,
    })}\n`,
    { encoding: "utf8", mode: 0o600, flag: "wx" },
  );
  return path;
}

async function assertOfferInRun(
  engine: SqliteRunEngine,
  runId: RunId,
  offerId: WorkOfferId,
): Promise<void> {
  const view = await engine.inspect(runId);
  if (!view.offers.some((offer) => offer.id === offerId)) {
    throw new Error(`offer ${offerId} is not part of run ${runId}`);
  }
}

function parseHumanDecisionInput(value: unknown): { readonly result: JsonObject } {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("human decision must be a JSON object with an exact result object");
  }
  const record = value as Record<string, unknown>;
  const fields = Object.keys(record);
  if (fields.some((field) => field !== "result")) {
    throw new Error("human decision permits only an exact result object");
  }
  if (!isJsonObject(record.result)) {
    throw new Error("human decision result must be a JSON object");
  }
  return { result: record.result };
}

function isJsonObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
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
