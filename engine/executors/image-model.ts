import type { WorkOfferView, WorkerIdentity } from "../contracts/index.ts";
import { SubprocessExecutor, type SubprocessCommand } from "./subprocess.ts";

export type ImageModelCommandFactory = (
  task: string,
  offer: WorkOfferView,
) => SubprocessCommand;

export class ImageModelExecutor extends SubprocessExecutor {
  constructor(
    id: string,
    worker: WorkerIdentity,
    commandFactory: ImageModelCommandFactory,
  ) {
    super(
      id,
      worker,
      (context, task) => commandFactory(task, context.offer),
      (offer) => offer.role === "cover_image" || offer.role === "interior_image",
    );
  }
}
