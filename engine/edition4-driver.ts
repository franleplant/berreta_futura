import { resolve } from "node:path";

import type { RevisionId } from "./contracts/index.ts";
import { EditionBootstrapRunner } from "./edition-bootstrap-run.ts";

const EDITION_KEY = "004";
const BOOTSTRAP_REVISION_ID =
  "rev_20260802T230000035Z_poyigg2sur72" as RevisionId;
const projectRoot = resolve(import.meta.dirname, "..");

/**
 * The repeatable Edition 4 entrypoint. It resolves one committed bootstrap
 * revision, lets RunEngine drive all non-human offers, and stops at the
 * pending human visual-review boundary. The runner projects that exact render
 * non-authoritatively so the PDFs are available for inspection.
 */
const runner = new EditionBootstrapRunner({
  editionKey: EDITION_KEY,
  repositoryRoot: projectRoot,
  outputRoot: resolve(projectRoot, "output"),
  render: {
    primaryLanguage: "en",
    publicationName: "Berreta Futura",
    renderer: "weasyprint",
  },
});

const result = await runner.run({
  kind: "run_bootstrap",
  editionId: EDITION_KEY,
  logicalId: "fresh-v2",
  revisionId: BOOTSTRAP_REVISION_ID,
});

process.stdout.write(`${JSON.stringify(result)}\n`);
