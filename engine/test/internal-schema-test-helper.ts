import Database from "better-sqlite3";

import type { RunId } from "../contracts/index.ts";

// This deliberately lives outside the RunEngine interface. It is used only to
// manufacture an impossible old-machine database for migration refusal tests.
export function corruptStoredMachineVersion(
  databasePath: string,
  runId: RunId,
  version: string,
): void {
  const database = new Database(databasePath);
  try {
    database.prepare("UPDATE runs SET machine_version = ? WHERE id = ?").run(
      version,
      runId,
    );
  } finally {
    database.close();
  }
}
