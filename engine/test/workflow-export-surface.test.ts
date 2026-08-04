import assert from "node:assert/strict";
import test from "node:test";

import * as workflows from "../workflows/index.ts";

test("workflow barrel exposes only the public magazine engine seam", () => {
  assert.deepEqual(Object.keys(workflows).sort(), [
    "MagazineWorkflowEngine",
    "MagazineWorkflowError",
  ]);
  assert.equal("runArticleWorkflow" in workflows, false);
  assert.equal("ArticleWorkflowPorts" in workflows, false);
  assert.equal("createDurableLoopsAdapter" in workflows, false);
  assert.equal("claimArticleModel" in workflows.MagazineWorkflowEngine.prototype, false);
  assert.equal("claimArticleTool" in workflows.MagazineWorkflowEngine.prototype, false);
  assert.equal("executeArticleModel" in workflows.MagazineWorkflowEngine.prototype, false);
  assert.equal("executeArticleTool" in workflows.MagazineWorkflowEngine.prototype, false);
});
