import type { WorkOfferView, WorkerIdentity } from "../contracts/index.ts";
import type { Executor, ExecutorContext } from "./types.ts";
import { WorkUnavailableError } from "./types.ts";

export class HumanExecutor implements Executor {
  readonly id = "human";
  readonly capabilities;
  readonly worker: WorkerIdentity;

  constructor(worker: WorkerIdentity) {
    this.worker = worker;
    this.capabilities = worker.capabilities;
  }

  accepts(offer: WorkOfferView): boolean {
    return offer.allowedWorkerCapabilities.includes("human");
  }

  execute(context: ExecutorContext): Promise<never> {
    return Promise.reject(new WorkUnavailableError(
      `offer ${context.offer.id} requires an explicit human answer`,
    ));
  }
}
