import { dirname, resolve } from "node:path";
import { mkdirSync } from "node:fs";

import Database from "better-sqlite3";

import { applySchema } from "./schema.ts";
import { RunEngineError } from "./types.ts";

export type OpenDatabaseOptions = {
  readonly path: string;
  readonly busyTimeoutMs: number;
  readonly now: string;
};

export function openRunDatabase(options: OpenDatabaseOptions): Database.Database {
  const path = resolve(options.path);
  mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
  const db = new Database(path, {
    fileMustExist: false,
    timeout: options.busyTimeoutMs,
  });

  try {
    db.pragma("foreign_keys = ON");
    db.pragma("trusted_schema = OFF");
    db.pragma(`busy_timeout = ${options.busyTimeoutMs}`);
    const journalMode = String(db.pragma("journal_mode = WAL", { simple: true })).toLowerCase();
    if (journalMode !== "wal") {
      throw new RunEngineError(
        "WAL_UNAVAILABLE",
        `RunEngine requires SQLite WAL mode, but SQLite selected ${journalMode}`,
      );
    }
    db.pragma("synchronous = FULL");
    if (Number(db.pragma("foreign_keys", { simple: true })) !== 1) {
      throw new RunEngineError("FOREIGN_KEYS_DISABLED", "SQLite foreign keys are disabled");
    }
    if (Number(db.pragma("synchronous", { simple: true })) !== 2) {
      throw new RunEngineError("SYNC_NOT_FULL", "SQLite synchronous mode is not FULL");
    }
    applySchema(db, options.now);
    return db;
  } catch (error) {
    db.close();
    throw error;
  }
}

export function immediateTransaction<Result>(
  db: Database.Database,
  body: () => Result,
): () => Result {
  const transaction = db.transaction(body);
  return (): Result => transaction.immediate() as Result;
}

export function assertDatabaseIntegrity(db: Database.Database): void {
  const row = db.prepare("PRAGMA quick_check").get() as { readonly quick_check: string };
  if (row.quick_check !== "ok") {
    throw new RunEngineError(
      "SQLITE_INTEGRITY",
      `SQLite quick_check failed: ${row.quick_check}`,
    );
  }
}
