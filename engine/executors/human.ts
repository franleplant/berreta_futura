import type { AuthorizedWorker, WorkerClaimPort } from "../authority/local-authority.ts";
import type { WorkClaim, WorkOfferId } from "../contracts/index.ts";

/**
 * A narrow authenticated boundary for human work. Human work is deliberately
 * not an automatic executor: a model or tool credential can never stand in
 * for an explicit human decision.
 */
export class HumanExecutor {
  private readonly worker: AuthorizedWorker;

  constructor(worker: AuthorizedWorker) {
    this.worker = worker;
  }

  async claim(engine: WorkerClaimPort, offerId: WorkOfferId): Promise<WorkClaim> {
    const description = await this.worker.describe();
    if (description.authority !== "human") {
      throw new Error("HumanExecutor requires an authenticated human credential");
    }
    return await this.worker.claim(engine, offerId);
  }
}
