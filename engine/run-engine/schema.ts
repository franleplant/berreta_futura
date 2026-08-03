import type Database from "better-sqlite3";

export const RUN_ENGINE_SCHEMA_VERSION = 9;

const SCHEMA = String.raw`
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS machine_versions (
  id TEXT PRIMARY KEY,
  machine_name TEXT NOT NULL,
  semantic_version TEXT NOT NULL,
  xstate_version TEXT NOT NULL,
  contract_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (machine_name, semantic_version)
) STRICT;

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('article', 'edition')),
  status TEXT NOT NULL CHECK (
    status IN ('awaiting_editor', 'complete', 'escalated', 'failed', 'running', 'waiting')
  ),
  machine_name TEXT NOT NULL,
  machine_version TEXT NOT NULL,
  spec_json TEXT NOT NULL CHECK (json_valid(spec_json)),
  metadata_json TEXT NOT NULL CHECK (json_valid(metadata_json)),
  parent_run_id TEXT REFERENCES runs(id),
  forked_from_sequence INTEGER,
  head_sequence INTEGER NOT NULL DEFAULT 0 CHECK (head_sequence >= 0),
  version INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  terminal_at TEXT,
  sealed_at TEXT,
  CHECK (
    (parent_run_id IS NULL AND forked_from_sequence IS NULL)
    OR (parent_run_id IS NOT NULL AND forked_from_sequence IS NOT NULL)
  )
) STRICT;

CREATE TABLE IF NOT EXISTS run_leases (
  run_id TEXT PRIMARY KEY REFERENCES runs(id),
  holder_id TEXT NOT NULL,
  fence INTEGER NOT NULL CHECK (fence > 0),
  expires_at_ms INTEGER NOT NULL,
  heartbeat_at_ms INTEGER NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS run_starts (
  idempotency_key TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE REFERENCES runs(id),
  spec_json TEXT NOT NULL CHECK (json_valid(spec_json)),
  created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS run_migrations (
  migration_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  idempotency_key TEXT NOT NULL,
  expected_from TEXT NOT NULL,
  target_bundle_version TEXT NOT NULL,
  expected_head_event_id TEXT NOT NULL REFERENCES events(id),
  plan_json TEXT NOT NULL CHECK (json_valid(plan_json)),
  created_at TEXT NOT NULL,
  UNIQUE (run_id, idempotency_key)
) STRICT;

CREATE TABLE IF NOT EXISTS run_migration_fences (
  run_id TEXT PRIMARY KEY REFERENCES runs(id),
  fence_id TEXT NOT NULL UNIQUE,
  expected_head_sequence INTEGER NOT NULL CHECK (expected_head_sequence >= 0),
  expected_head_event_id TEXT NOT NULL REFERENCES events(id),
  idempotency_key TEXT NOT NULL UNIQUE,
  acquired_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS edition_source_submissions (
  run_id TEXT NOT NULL REFERENCES runs(id),
  source_id TEXT NOT NULL,
  source_spec_json TEXT NOT NULL CHECK (json_valid(source_spec_json)),
  lead_artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  submitted_at TEXT NOT NULL,
  PRIMARY KEY (run_id, source_id)
) STRICT;

CREATE TABLE IF NOT EXISTS actors (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  parent_actor_id TEXT REFERENCES actors(id),
  logical_key TEXT NOT NULL,
  machine_name TEXT NOT NULL,
  machine_version TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('accepting', 'active', 'done', 'failed')),
  current_state TEXT NOT NULL,
  current_context_json TEXT NOT NULL CHECK (json_valid(current_context_json)),
  current_snapshot_number INTEGER NOT NULL CHECK (current_snapshot_number >= 0),
  current_visit_id TEXT,
  input_json TEXT NOT NULL CHECK (json_valid(input_json)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (run_id, parent_actor_id, logical_key)
) STRICT;

CREATE UNIQUE INDEX IF NOT EXISTS one_root_actor_per_run
  ON actors(run_id) WHERE parent_actor_id IS NULL;

CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  sequence INTEGER NOT NULL CHECK (sequence > 0),
  actor_id TEXT NOT NULL REFERENCES actors(id),
  inbox_id TEXT,
  type TEXT NOT NULL,
  payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
  previous_snapshot_number INTEGER,
  next_snapshot_number INTEGER NOT NULL CHECK (next_snapshot_number > 0),
  previous_state TEXT,
  next_state TEXT NOT NULL,
  causation_event_id TEXT REFERENCES events(id),
  correlation_id TEXT,
  recorded_at TEXT NOT NULL,
  UNIQUE (run_id, sequence),
  UNIQUE (inbox_id)
) STRICT;

CREATE TABLE IF NOT EXISTS actor_snapshots (
  actor_id TEXT NOT NULL REFERENCES actors(id),
  snapshot_number INTEGER NOT NULL CHECK (snapshot_number > 0),
  event_id TEXT NOT NULL REFERENCES events(id),
  machine_version TEXT NOT NULL,
  snapshot_json TEXT NOT NULL CHECK (json_valid(snapshot_json)),
  state_value_json TEXT NOT NULL CHECK (json_valid(state_value_json)),
  context_json TEXT NOT NULL CHECK (json_valid(context_json)),
  created_at TEXT NOT NULL,
  PRIMARY KEY (actor_id, snapshot_number),
  UNIQUE (event_id)
) STRICT;

CREATE TABLE IF NOT EXISTS state_visits (
  id TEXT PRIMARY KEY,
  actor_id TEXT NOT NULL REFERENCES actors(id),
  state_key TEXT NOT NULL,
  visit_number INTEGER NOT NULL CHECK (visit_number > 0),
  entered_event_id TEXT NOT NULL REFERENCES events(id),
  exited_event_id TEXT REFERENCES events(id),
  created_at TEXT NOT NULL,
  UNIQUE (actor_id, visit_number)
) STRICT;

CREATE UNIQUE INDEX IF NOT EXISTS one_current_visit_per_actor
  ON state_visits(actor_id) WHERE exited_event_id IS NULL;

CREATE TABLE IF NOT EXISTS inbox (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  actor_id TEXT NOT NULL REFERENCES actors(id),
  type TEXT NOT NULL,
  payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
  idempotency_key TEXT NOT NULL,
  causation_event_id TEXT REFERENCES events(id),
  correlation_id TEXT,
  status TEXT NOT NULL CHECK (status IN ('pending', 'consumed', 'dead')),
  priority INTEGER NOT NULL DEFAULT 0,
  available_at_ms INTEGER NOT NULL,
  consumed_event_id TEXT REFERENCES events(id),
  created_at TEXT NOT NULL,
  UNIQUE (run_id, idempotency_key),
  CHECK (
    (status = 'consumed' AND consumed_event_id IS NOT NULL)
    OR (status <> 'consumed' AND consumed_event_id IS NULL)
  )
) STRICT;

CREATE INDEX IF NOT EXISTS pending_inbox_by_run
  ON inbox(run_id, available_at_ms, created_at) WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS transition_effects (
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL REFERENCES events(id),
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  effect_type TEXT NOT NULL,
  params_json TEXT NOT NULL CHECK (json_valid(params_json)),
  UNIQUE (event_id, ordinal)
) STRICT;

CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  media_type TEXT NOT NULL,
  origin TEXT NOT NULL CHECK (origin IN ('human', 'imported', 'machine', 'model', 'subprocess')),
  storage_kind TEXT NOT NULL CHECK (storage_kind IN ('inline', 'file')),
  inline_payload BLOB,
  relative_path TEXT,
  size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
  producing_run_id TEXT REFERENCES runs(id),
  producing_actor_id TEXT REFERENCES actors(id),
  producing_attempt_id TEXT,
  producing_offer_id TEXT,
  supersedes_artifact_id TEXT REFERENCES artifacts(id),
  disposition TEXT NOT NULL CHECK (disposition IN ('accepted', 'seed', 'stale', 'superseded')),
  metadata_json TEXT NOT NULL CHECK (json_valid(metadata_json)),
  created_at TEXT NOT NULL,
  CHECK (
    (storage_kind = 'inline' AND inline_payload IS NOT NULL AND relative_path IS NULL)
    OR (storage_kind = 'file' AND inline_payload IS NULL AND relative_path IS NOT NULL)
  )
) STRICT;

CREATE TABLE IF NOT EXISTS artifact_write_intents (
  artifact_id TEXT PRIMARY KEY,
  holder_id TEXT NOT NULL,
  fence INTEGER NOT NULL CHECK (fence > 0),
  expires_at_ms INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS expiring_artifact_write_intents
  ON artifact_write_intents(expires_at_ms, artifact_id);

CREATE TABLE IF NOT EXISTS artifact_edges (
  child_artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  parent_artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  relation TEXT NOT NULL,
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  PRIMARY KEY (child_artifact_id, relation, ordinal),
  UNIQUE (child_artifact_id, parent_artifact_id, relation)
) STRICT;

CREATE TABLE IF NOT EXISTS run_inputs (
  run_id TEXT NOT NULL REFERENCES runs(id),
  input_name TEXT NOT NULL,
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  PRIMARY KEY (run_id, input_name, ordinal)
) STRICT;

CREATE TABLE IF NOT EXISTS run_outputs (
  run_id TEXT NOT NULL REFERENCES runs(id),
  output_name TEXT NOT NULL,
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  PRIMARY KEY (run_id, output_name, ordinal)
) STRICT;

CREATE TABLE IF NOT EXISTS iterations (
  id TEXT PRIMARY KEY,
  actor_id TEXT NOT NULL REFERENCES actors(id),
  ordinal INTEGER NOT NULL CHECK (ordinal > 0),
  parent_manuscript_artifact_id TEXT REFERENCES artifacts(id),
  opened_event_id TEXT NOT NULL REFERENCES events(id),
  closed_event_id TEXT REFERENCES events(id),
  decision_id TEXT,
  UNIQUE (actor_id, ordinal)
) STRICT;

CREATE TABLE IF NOT EXISTS work_offers (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  actor_id TEXT NOT NULL REFERENCES actors(id),
  state_visit_id TEXT NOT NULL REFERENCES state_visits(id),
  iteration_id TEXT,
  revision_id TEXT,
  role TEXT NOT NULL,
  slot TEXT NOT NULL,
  subject_artifact_id TEXT REFERENCES artifacts(id),
  task_artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  contract_version TEXT NOT NULL,
  required_authority TEXT NOT NULL DEFAULT 'tool' CHECK (required_authority IN ('human', 'machine', 'model', 'tool')),
  minimum_assurance TEXT NOT NULL DEFAULT 'local_bearer',
  status TEXT NOT NULL CHECK (status IN ('offered', 'claimed', 'answered', 'canceled', 'failed', 'superseded')),
  offer_version INTEGER NOT NULL DEFAULT 1 CHECK (offer_version > 0),
  claim_fence INTEGER NOT NULL DEFAULT 0 CHECK (claim_fence >= 0),
  active_attempt_id TEXT,
  created_event_id TEXT NOT NULL REFERENCES events(id),
  canceled_event_id TEXT REFERENCES events(id),
  answered_event_id TEXT REFERENCES events(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (state_visit_id, role, slot)
) STRICT;

CREATE INDEX IF NOT EXISTS claimable_offers
  ON work_offers(run_id, status, created_at);

CREATE TABLE IF NOT EXISTS work_offer_inputs (
  offer_id TEXT NOT NULL REFERENCES work_offers(id),
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  PRIMARY KEY (offer_id, ordinal),
  UNIQUE (offer_id, artifact_id)
) STRICT;

CREATE TABLE IF NOT EXISTS work_offer_capabilities (
  offer_id TEXT NOT NULL REFERENCES work_offers(id),
  capability TEXT NOT NULL CHECK (
    capability IN ('human', 'image_model', 'source_access', 'source_blind', 'subprocess', 'text_model')
  ),
  PRIMARY KEY (offer_id, capability)
) STRICT;

/*
 * Authority is captured by the engine at claim time.  Credentials themselves
 * live only in the local authority store, never in this workflow database.
 */
CREATE TABLE IF NOT EXISTS authorization_snapshots (
  id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL,
  authority TEXT NOT NULL CHECK (authority IN ('human', 'machine', 'model', 'tool')),
  assurance TEXT NOT NULL,
  credential_id TEXT NOT NULL,
  capabilities_json TEXT NOT NULL CHECK (json_valid(capabilities_json)),
  roles_json TEXT NOT NULL CHECK (json_valid(roles_json)),
  snapshot_json TEXT NOT NULL CHECK (json_valid(snapshot_json)),
  created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS authorizations (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  offer_id TEXT NOT NULL UNIQUE REFERENCES work_offers(id),
  snapshot_id TEXT NOT NULL REFERENCES authorization_snapshots(id),
  principal_id TEXT NOT NULL,
  authority TEXT NOT NULL CHECK (authority IN ('human', 'machine', 'model', 'tool')),
  assurance TEXT NOT NULL,
  created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS authorization_bindings (
  authorization_id TEXT NOT NULL REFERENCES authorizations(id),
  binding_kind TEXT NOT NULL CHECK (binding_kind IN ('input', 'task', 'requirement')),
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  value_json TEXT NOT NULL CHECK (json_valid(value_json)),
  PRIMARY KEY (authorization_id, binding_kind, ordinal)
) STRICT;

CREATE TABLE IF NOT EXISTS work_claim_tickets (
  attempt_id TEXT PRIMARY KEY REFERENCES attempts(id),
  ticket_hash TEXT NOT NULL UNIQUE,
  issued_at TEXT NOT NULL,
  revoked_at TEXT,
  consumed_at TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS work_reuses (
  run_id TEXT NOT NULL REFERENCES runs(id),
  offer_id TEXT PRIMARY KEY REFERENCES work_offers(id),
  ancestor_run_id TEXT NOT NULL REFERENCES runs(id),
  ancestor_offer_id TEXT NOT NULL REFERENCES work_offers(id),
  answer_artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  created_event_id TEXT NOT NULL REFERENCES events(id),
  created_at TEXT NOT NULL,
  CHECK (run_id <> ancestor_run_id),
  UNIQUE (run_id, ancestor_offer_id)
) STRICT;

CREATE TABLE IF NOT EXISTS attempts (
  id TEXT PRIMARY KEY,
  offer_id TEXT NOT NULL REFERENCES work_offers(id),
  attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
  fence INTEGER NOT NULL CHECK (fence > 0),
  worker_principal_id TEXT NOT NULL,
  worker_authority TEXT NOT NULL CHECK (worker_authority IN ('human', 'machine', 'model', 'tool')),
  worker_capabilities_json TEXT NOT NULL CHECK (json_valid(worker_capabilities_json)),
  worker_display_name TEXT,
  authorization_id TEXT REFERENCES authorizations(id),
  status TEXT NOT NULL CHECK (status IN ('active', 'answered', 'failed', 'stale', 'timed_out')),
  claimed_at TEXT NOT NULL,
  lease_expires_at_ms INTEGER NOT NULL,
  heartbeat_at_ms INTEGER NOT NULL,
  finished_at TEXT,
  failure_classification TEXT,
  failure_message TEXT,
  failure_details_json TEXT CHECK (failure_details_json IS NULL OR json_valid(failure_details_json)),
  UNIQUE (offer_id, attempt_number),
  UNIQUE (offer_id, fence)
) STRICT;

CREATE UNIQUE INDEX IF NOT EXISTS one_active_attempt_per_offer
  ON attempts(offer_id) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS worker_exposures (
  worker_principal_id TEXT NOT NULL,
  subject_artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  exposure_class TEXT NOT NULL CHECK (exposure_class IN ('source_aware', 'source_blind')),
  first_attempt_id TEXT NOT NULL REFERENCES attempts(id),
  exposed_at TEXT NOT NULL,
  PRIMARY KEY (worker_principal_id, subject_artifact_id, exposure_class)
) STRICT;

CREATE TABLE IF NOT EXISTS attempt_submissions (
  id TEXT PRIMARY KEY,
  attempt_id TEXT NOT NULL REFERENCES attempts(id),
  offer_id TEXT NOT NULL REFERENCES work_offers(id),
  artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  disposition TEXT NOT NULL CHECK (disposition IN ('accepted', 'duplicate', 'malformed', 'stale')),
  received_at TEXT NOT NULL,
  UNIQUE (attempt_id, artifact_id)
) STRICT;

CREATE UNIQUE INDEX IF NOT EXISTS one_accepted_submission_per_offer
  ON attempt_submissions(offer_id) WHERE disposition = 'accepted';

CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  actor_id TEXT NOT NULL REFERENCES actors(id),
  offer_id TEXT REFERENCES work_offers(id),
  subject_artifact_id TEXT REFERENCES artifacts(id),
  authority TEXT NOT NULL,
  principal_id TEXT NOT NULL,
  choice TEXT NOT NULL,
  artifact_id TEXT REFERENCES artifacts(id),
  authorization_id TEXT REFERENCES authorizations(id),
  details_json TEXT NOT NULL CHECK (json_valid(details_json)),
  event_id TEXT NOT NULL REFERENCES events(id),
  created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS releases (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE REFERENCES runs(id),
  actor_id TEXT NOT NULL UNIQUE REFERENCES actors(id),
  edition_id TEXT NOT NULL UNIQUE,
  publication_artifact_id TEXT NOT NULL UNIQUE REFERENCES artifacts(id),
  decision_artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  released_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS released_source_assignments (
  source_artifact_id TEXT PRIMARY KEY REFERENCES artifacts(id),
  release_id TEXT NOT NULL REFERENCES releases(id),
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  UNIQUE (release_id, ordinal)
) STRICT;

CREATE TABLE IF NOT EXISTS released_source_identities (
  source_id TEXT PRIMARY KEY,
  release_id TEXT NOT NULL REFERENCES releases(id),
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  UNIQUE (release_id, ordinal)
) STRICT;

CREATE TABLE IF NOT EXISTS article_promotions (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE REFERENCES runs(id),
  selected_artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  policy_artifact_id TEXT NOT NULL UNIQUE REFERENCES artifacts(id),
  reviewer TEXT NOT NULL,
  rationale TEXT NOT NULL,
  compared_run_ids_json TEXT NOT NULL CHECK (json_valid(compared_run_ids_json)),
  created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS outbox (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  effect_id TEXT NOT NULL REFERENCES transition_effects(id),
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
  idempotency_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK (status IN ('pending', 'claimed', 'completed', 'failed')),
  claim_holder TEXT,
  claim_fence INTEGER NOT NULL DEFAULT 0 CHECK (claim_fence >= 0),
  claim_expires_at_ms INTEGER,
  available_at_ms INTEGER NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  last_error TEXT,
  created_at TEXT NOT NULL,
  completed_at TEXT
) STRICT;

CREATE INDEX IF NOT EXISTS pending_outbox
  ON outbox(status, available_at_ms, created_at);

CREATE TABLE IF NOT EXISTS fork_changes (
  run_id TEXT NOT NULL REFERENCES runs(id),
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  kind TEXT NOT NULL CHECK (kind IN ('replace_artifact', 'replace_spec')),
  path TEXT,
  old_artifact_id TEXT REFERENCES artifacts(id),
  new_artifact_id TEXT REFERENCES artifacts(id),
  value_json TEXT CHECK (value_json IS NULL OR json_valid(value_json)),
  PRIMARY KEY (run_id, ordinal)
) STRICT;

CREATE TABLE IF NOT EXISTS sealed_exports (
  run_id TEXT PRIMARY KEY REFERENCES runs(id),
  head_sequence INTEGER NOT NULL,
  artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  created_at TEXT NOT NULL
) STRICT;
`;

const IMMUTABLE_TABLES = [
  "actor_snapshots",
  "artifact_edges",
  "article_promotions",
  "authorization_bindings",
  "authorization_snapshots",
  "authorizations",
  "artifacts",
  "decisions",
  "edition_source_submissions",
  "events",
  "machine_versions",
  "released_source_assignments",
  "released_source_identities",
  "releases",
  "run_migrations",
  "run_starts",
  "sealed_exports",
  "transition_effects",
  "work_reuses",
] as const;

export function applySchema(db: Database.Database, now: string): void {
  const migrate = db.transaction(() => {
    db.exec(SCHEMA);
    const decisionColumns = db.pragma("table_info(decisions)") as readonly {
      readonly name: string;
    }[];
    if (!decisionColumns.some((column) => column.name === "details_json")) {
      db.exec("ALTER TABLE decisions ADD COLUMN details_json TEXT NOT NULL DEFAULT '{}'");
    }
    const inboxColumns = db.pragma("table_info(inbox)") as readonly {
      readonly name: string;
    }[];
    if (!inboxColumns.some((column) => column.name === "priority")) {
      db.exec("ALTER TABLE inbox ADD COLUMN priority INTEGER NOT NULL DEFAULT 0");
    }
    const attemptColumns = db.pragma("table_info(attempts)") as readonly {
      readonly name: string;
    }[];
    if (!attemptColumns.some((column) => column.name === "authorization_id")) {
      db.exec("ALTER TABLE attempts ADD COLUMN authorization_id TEXT REFERENCES authorizations(id)");
    }
    const decisionAuthorityColumns = db.pragma("table_info(decisions)") as readonly {
      readonly name: string;
    }[];
    if (!decisionAuthorityColumns.some((column) => column.name === "authorization_id")) {
      db.exec("ALTER TABLE decisions ADD COLUMN authorization_id TEXT REFERENCES authorizations(id)");
    }
    const offerAuthorityColumns = db.pragma("table_info(work_offers)") as readonly {
      readonly name: string;
    }[];
    if (!offerAuthorityColumns.some((column) => column.name === "required_authority")) {
      db.exec("ALTER TABLE work_offers ADD COLUMN required_authority TEXT NOT NULL DEFAULT 'tool'");
    }
    if (!offerAuthorityColumns.some((column) => column.name === "minimum_assurance")) {
      db.exec("ALTER TABLE work_offers ADD COLUMN minimum_assurance TEXT NOT NULL DEFAULT 'local_bearer'");
    }
    for (const table of IMMUTABLE_TABLES) {
      db.exec(`
        CREATE TRIGGER IF NOT EXISTS ${table}_immutable_update
        BEFORE UPDATE ON ${table}
        BEGIN
          SELECT RAISE(ABORT, '${table} rows are immutable');
        END;
        CREATE TRIGGER IF NOT EXISTS ${table}_immutable_delete
        BEFORE DELETE ON ${table}
        BEGIN
          SELECT RAISE(ABORT, '${table} rows are immutable');
        END;
      `);
    }
    db.prepare(
      "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
    ).run(RUN_ENGINE_SCHEMA_VERSION, now);
  });
  migrate.immediate();

  const versions = db
    .prepare("SELECT version FROM schema_migrations ORDER BY version")
    .all() as readonly { readonly version: number }[];
  const newest = versions.at(-1)?.version ?? 0;
  if (newest !== RUN_ENGINE_SCHEMA_VERSION) {
    throw new Error(
      `Unsupported RunEngine schema version ${newest}; expected ${RUN_ENGINE_SCHEMA_VERSION}`,
    );
  }
}
