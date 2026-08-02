import type { RendererAdapter, RenderResult } from "./protocol.ts";

export type InMemoryRender = (
  manifestPath: string,
  destination: string,
  signal: AbortSignal,
) => Promise<RenderResult> | RenderResult;

export class InMemoryRendererAdapter implements RendererAdapter {
  private readonly implementation: InMemoryRender;

  constructor(implementation: InMemoryRender) {
    this.implementation = implementation;
  }

  async render(
    manifestPath: string,
    destination: string,
    signal: AbortSignal,
  ): Promise<RenderResult> {
    return await this.implementation(manifestPath, destination, signal);
  }
}
