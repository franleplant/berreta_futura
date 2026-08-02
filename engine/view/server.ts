import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { extname, relative, resolve } from "node:path";

import type {
  ActorId,
  JsonObject,
  RunId,
  WorkerCapability,
  WorkOfferId,
} from "../contracts/index.ts";
import type { RunEngine } from "../run-engine/types.ts";

const MAX_REQUEST_BYTES = 1024 * 1024;
const LOOPBACK_HOSTS = new Set(["127.0.0.1", "::1", "localhost"]);

export type RunViewerServerOptions = {
  readonly host?: string;
  readonly port?: number;
  readonly staticDirectory: string;
};

export type RunningViewer = {
  readonly host: string;
  readonly port: number;
  readonly server: Server;
  close(): Promise<void>;
};

export async function serveRunViewer(
  engine: RunEngine,
  options: RunViewerServerOptions,
): Promise<RunningViewer> {
  const host = options.host ?? "127.0.0.1";
  if (!LOOPBACK_HOSTS.has(host)) {
    throw new Error("the run viewer may bind only to a loopback address");
  }
  const staticRoot = resolve(options.staticDirectory);
  const server = createServer((request, response) => {
    void handleRequest(engine, staticRoot, request, response).catch((error: unknown) => {
      if (!response.headersSent) {
        writeJson(response, statusForError(error), {
          error: error instanceof Error ? error.message : String(error),
        });
      } else {
        response.destroy(error instanceof Error ? error : new Error(String(error)));
      }
    });
  });
  await new Promise<void>((resolveListening, reject) => {
    server.once("error", reject);
    server.listen(options.port ?? 0, host, () => {
      server.off("error", reject);
      resolveListening();
    });
  });
  const address = server.address();
  if (address === null || typeof address === "string") {
    server.close();
    throw new Error("viewer did not receive a TCP address");
  }
  return {
    host,
    port: address.port,
    server,
    close: async () => {
      await new Promise<void>((resolveClosed, reject) => {
        server.close((error) => error === undefined ? resolveClosed() : reject(error));
      });
    },
  };
}

async function handleRequest(
  engine: RunEngine,
  staticRoot: string,
  request: IncomingMessage,
  response: ServerResponse,
): Promise<void> {
  const url = new URL(request.url ?? "/", "http://localhost");
  const runMatch = /^\/api\/runs\/([^/]+)$/.exec(url.pathname);
  if (request.method === "GET" && runMatch?.[1] !== undefined) {
    const view = await engine.inspect(decodeURIComponent(runMatch[1]) as RunId);
    writeJson(response, 200, view);
    return;
  }
  const artifactMatch = /^\/api\/runs\/([^/]+)\/artifacts\/([^/]+)$/.exec(url.pathname);
  if (
    (request.method === "GET" || request.method === "HEAD") &&
    artifactMatch?.[1] !== undefined &&
    artifactMatch[2] !== undefined
  ) {
    const runId = decodeURIComponent(artifactMatch[1]) as RunId;
    const artifactId = decodeURIComponent(artifactMatch[2]);
    const view = await engine.inspect(runId);
    const visible = view.artifacts.find((artifact) => artifact.id === artifactId);
    if (visible === undefined) {
      writeJson(response, 404, { error: "artifact is not part of the run" });
      return;
    }
    const stored = await engine.readArtifact(visible.id);
    response.writeHead(200, {
      "cache-control": "no-store",
      "content-disposition": `inline; filename="${safeFilename(visible.kind)}"`,
      "content-length": String(stored.bytes.byteLength),
      "content-type": visible.mediaType,
      "x-content-type-options": "nosniff",
    });
    response.end(request.method === "HEAD" ? undefined : Buffer.from(stored.bytes));
    return;
  }
  const retryMatch = /^\/api\/runs\/([^/]+)\/actors\/([^/]+)\/retry$/.exec(url.pathname);
  if (request.method === "POST" && retryMatch?.[1] !== undefined && retryMatch[2] !== undefined) {
    const runId = decodeURIComponent(retryMatch[1]) as RunId;
    const actorId = decodeURIComponent(retryMatch[2]) as ActorId;
    const body = await readJsonObject(request);
    const view = await engine.inspect(runId);
    const actor = view.actors.find((candidate) => candidate.id === actorId);
    if (actor === undefined) {
      writeJson(response, 404, { error: "actor is not part of the run" });
      return;
    }
    if (body.expectedState !== actor.state) {
      writeJson(response, 409, { error: "actor state changed before retry" });
      return;
    }
    writeJson(response, 200, await engine.retry(runId, actorId));
    return;
  }
  const answerMatch = /^\/api\/offers\/([^/]+)\/answer$/.exec(url.pathname);
  if (request.method === "POST" && answerMatch?.[1] !== undefined) {
    const offerId = decodeURIComponent(answerMatch[1]) as WorkOfferId;
    const body = await readJsonObject(request);
    if (body.expectedOfferId !== offerId) {
      writeJson(response, 409, { error: "expectedOfferId does not name the active route offer" });
      return;
    }
    if (!isJsonObject(body.result)) {
      writeJson(response, 400, { error: "result must be a JSON object" });
      return;
    }
    if (typeof body.runId !== "string" || !body.runId) {
      writeJson(response, 400, { error: "runId must be a non-empty string" });
      return;
    }
    const offer = await findOffer(engine, body.runId as RunId, offerId);
    if (!offer.allowedWorkerCapabilities.includes("human")) {
      writeJson(response, 403, { error: "offer does not permit human authority" });
      return;
    }
    const claim = await engine.claim(offerId, {
      principalId: "local-human",
      displayName: "Local reviewer",
      authority: "human",
      capabilities: humanCapabilities(offer.allowedWorkerCapabilities),
    });
    await engine.answer(claim, {
      contractVersion: offer.contractVersion,
      result: body.result,
      artifacts: [{
        kind: humanDecisionKind(offer.role),
        schemaVersion: offer.contractVersion,
        mediaType: "application/json",
        origin: "human",
        payload: {
          kind: "json",
          value: humanDecisionPayload(offer.role, body.result),
        },
        metadata: {
          offerId: offer.id,
          reviewer: "local-human",
        },
      }],
      metadata: { surface: "local-viewer" },
    });
    const outcome = await engine.advance(offer.runId);
    writeJson(response, 200, outcome);
    return;
  }
  if (request.method !== "GET" && request.method !== "HEAD") {
    writeJson(response, 405, { error: "method not allowed" });
    return;
  }
  await serveStatic(staticRoot, url.pathname, request.method === "HEAD", response);
}

function humanDecisionPayload(role: string, result: JsonObject) {
  if (role === "plan_edition") {
    return result.productionPlan ?? null;
  }
  return result;
}

function humanDecisionKind(role: string): string {
  switch (role) {
    case "close_collection":
      return "collection_decision";
    case "plan_edition":
      return "edition_plan";
    case "release_approval":
      return "release_decision";
    case "review_source":
      return "source_review_decision";
    case "select_art":
      return "art_selection";
    case "visual_review":
      return "visual_review_decision";
    default:
      return "editor_decision";
  }
}

function humanCapabilities(
  required: ReadonlyArray<WorkerCapability>,
): ReadonlyArray<WorkerCapability> {
  return [
    "human" as const,
    ...(required.includes("source_access") ? ["source_access" as const] : []),
  ];
}

async function findOffer(engine: RunEngine, runId: RunId, offerId: WorkOfferId) {
  const view = await engine.inspect(runId);
  const offer = view.offers.find((candidate) => candidate.id === offerId);
  if (offer === undefined) {
    throw new Error(`offer ${offerId} is not part of run ${runId}`);
  }
  return offer;
}

async function serveStatic(
  staticRoot: string,
  rawPath: string,
  headOnly: boolean,
  response: ServerResponse,
): Promise<void> {
  const requested = rawPath === "/" ? "/index.html" : decodeURIComponent(rawPath);
  const path = resolve(staticRoot, `.${requested}`);
  const relation = relative(staticRoot, path);
  if (relation.startsWith("..") || relation === "") {
    writeJson(response, 404, { error: "not found" });
    return;
  }
  let file = path;
  try {
    if (!(await stat(file)).isFile()) {
      throw new Error("not a file");
    }
  } catch {
    file = resolve(staticRoot, "index.html");
    if (!(await stat(file)).isFile()) {
      writeJson(response, 404, { error: "viewer assets are not built" });
      return;
    }
  }
  response.writeHead(200, {
    "cache-control": file.endsWith("index.html") ? "no-store" : "public, max-age=31536000, immutable",
    "content-type": mediaType(file),
    "x-content-type-options": "nosniff",
  });
  if (headOnly) {
    response.end();
    return;
  }
  createReadStream(file).pipe(response);
}

async function readJsonObject(request: IncomingMessage): Promise<JsonObject> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of request) {
    const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk as Uint8Array);
    size += bytes.length;
    if (size > MAX_REQUEST_BYTES) {
      throw new Error("request body is too large");
    }
    chunks.push(bytes);
  }
  const value: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  if (!isJsonObject(value)) {
    throw new Error("request body must be a JSON object");
  }
  return value;
}

function isJsonObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function writeJson(response: ServerResponse, status: number, value: unknown): void {
  response.writeHead(status, {
    "cache-control": "no-store",
    "content-type": "application/json; charset=utf-8",
    "x-content-type-options": "nosniff",
  });
  response.end(`${JSON.stringify(value)}\n`);
}

function statusForError(error: unknown): number {
  if (error instanceof SyntaxError) {
    return 400;
  }
  if (error instanceof Error && /stale|active|claimed|offer/i.test(error.message)) {
    return 409;
  }
  return 500;
}

function mediaType(path: string): string {
  switch (extname(path)) {
    case ".css":
      return "text/css; charset=utf-8";
    case ".html":
      return "text/html; charset=utf-8";
    case ".js":
      return "text/javascript; charset=utf-8";
    case ".json":
      return "application/json; charset=utf-8";
    case ".svg":
      return "image/svg+xml";
    default:
      return "application/octet-stream";
  }
}

function safeFilename(value: string): string {
  return value.replace(/[^A-Za-z0-9._-]+/g, "_").slice(0, 120) || "artifact";
}
