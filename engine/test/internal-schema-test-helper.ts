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

// This deliberately manufactures a historical v1 root snapshot. It is a
// narrowly-scoped schema fixture for the public RunEngine migration contract;
// production callers never receive a database handle.
export function prepareLegacyEditionReleaseSnapshot(
  databasePath: string,
  runId: RunId,
): void {
  const database = new Database(databasePath);
  try {
    database.exec("DROP TRIGGER IF EXISTS actor_snapshots_immutable_update");
    const root = database.prepare(
      "SELECT id, current_snapshot_number FROM actors WHERE run_id = ? AND parent_actor_id IS NULL",
    ).get(runId) as { readonly id: string; readonly current_snapshot_number: number } | undefined;
    if (root === undefined) {
      throw new Error(`Missing root actor for ${runId}`);
    }
    database.prepare(
      "UPDATE runs SET machine_version = 'edition/2' WHERE id = ?",
    ).run(runId);
    database.prepare(
      `UPDATE actors SET machine_version = 'edition/2', current_state = 'awaiting_release_approval'
       WHERE id = ?`,
    ).run(root.id);
    database.prepare(
      `UPDATE actor_snapshots
       SET machine_version = 'edition/2',
           snapshot_json = json_set(snapshot_json, '$.value', json('"awaiting_release_approval"')),
           state_value_json = json('"awaiting_release_approval"')
       WHERE actor_id = ? AND snapshot_number = ?`,
    ).run(root.id, root.current_snapshot_number);

    const children = database.prepare(
      `SELECT id, machine_name, current_snapshot_number FROM actors
       WHERE run_id = ? AND parent_actor_id = ?
         AND machine_name IN ('article', 'editorial', 'cover_art', 'interior_art')`,
    ).all(runId, root.id) as readonly {
      readonly id: string;
      readonly machine_name: "article" | "editorial" | "cover_art" | "interior_art";
      readonly current_snapshot_number: number;
    }[];
    for (const child of children) {
      const legacy = child.machine_name === "article"
        ? { version: "article/2", state: "settled" }
        : child.machine_name === "editorial"
          ? { version: "editorial/1", state: "settled" }
          : { version: "art/1", state: "registered" };
      database.prepare(
        `UPDATE actors SET machine_version = ?, current_state = ?,
           current_context_json = json_remove(
             current_context_json,
             '$.boundRevisionId',
             '$.durableRevisionArtifact'
           )
         WHERE id = ?`,
      ).run(legacy.version, legacy.state, child.id);
      database.prepare(
        `UPDATE actor_snapshots
         SET machine_version = ?,
             snapshot_json = json_remove(
               json_set(snapshot_json, '$.value', json(?)),
               '$.context.boundRevisionId',
               '$.context.durableRevisionArtifact'
             ),
             state_value_json = json(?)
         WHERE actor_id = ? AND snapshot_number = ?`,
      ).run(
        legacy.version,
        JSON.stringify(legacy.state),
        JSON.stringify(legacy.state),
        child.id,
        child.current_snapshot_number,
      );
    }
  } finally {
    database.close();
  }
}
