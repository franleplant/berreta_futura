import type { WorkAnswer, WorkOfferView, WorkerIdentity } from "../contracts/index.ts";
import type { Executor, ExecutorContext } from "./types.ts";

export type InMemoryHandler = (context: ExecutorContext) => Promise<WorkAnswer> | WorkAnswer;

export class InMemoryExecutor implements Executor {
  readonly id: string;
  readonly worker: WorkerIdentity;
  readonly capabilities;
  private readonly handler: InMemoryHandler;
  private readonly predicate: (offer: WorkOfferView) => boolean;

  constructor(
    id: string,
    worker: WorkerIdentity,
    handler: InMemoryHandler,
    predicate: (offer: WorkOfferView) => boolean = () => true,
  ) {
    this.id = id;
    this.worker = worker;
    this.handler = handler;
    this.predicate = predicate;
    this.capabilities = worker.capabilities;
  }

  accepts(offer: WorkOfferView): boolean {
    return this.predicate(offer);
  }

  async execute(context: ExecutorContext): Promise<WorkAnswer> {
    if (!this.accepts(context.offer)) {
      throw new Error(`executor ${this.id} does not accept ${context.offer.role}`);
    }
    return await this.handler(context);
  }
}
