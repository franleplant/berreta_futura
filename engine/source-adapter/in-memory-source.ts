import type { SourceAdapter, SourceResult } from "./protocol.ts";

export type InMemoryArchive = (
  requestPath: string,
  destination: string,
  signal: AbortSignal,
) => Promise<SourceResult> | SourceResult;

export class InMemorySourceAdapter implements SourceAdapter {
  private readonly implementation: InMemoryArchive;

  constructor(implementation: InMemoryArchive) {
    this.implementation = implementation;
  }

  async archive(
    requestPath: string,
    destination: string,
    signal: AbortSignal,
  ): Promise<SourceResult> {
    return await this.implementation(requestPath, destination, signal);
  }
}
