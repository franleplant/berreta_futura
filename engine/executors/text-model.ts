import type { WorkOfferView, WorkerIdentity } from "../contracts/index.ts";
import { SubprocessExecutor, type SubprocessCommand } from "./subprocess.ts";

const TEXT_ROLES = new Set([
  "extract_source",
  "worth",
  "mechanics",
  "evidence",
  "shape",
  "teaching",
  "craft",
  "editorial_writer",
  "edition_review",
  "translation_writer",
  "language_review",
]);

export type TextModelCommandFactory = (
  task: string,
  offer: WorkOfferView,
) => SubprocessCommand;

export class TextModelExecutor extends SubprocessExecutor {
  constructor(
    id: string,
    worker: WorkerIdentity,
    commandFactory: TextModelCommandFactory,
  ) {
    super(
      id,
      worker,
      (context, task) => commandFactory(task, context.offer),
      (offer) => TEXT_ROLES.has(offer.role),
    );
  }
}
