/** Process-local access to the one credential the closed writer may read. */
export type ClosedWriterCredentialResource = {
  readonly schemaVersion: "closed-writer-credential-resource/1";
  readonly read: () => Promise<Readonly<Record<string, string>>> | Readonly<Record<string, string>>;
};

export class ClosedWriterCredentialError extends Error {
  readonly code = "WRITER_CREDENTIAL_INVALID";
  readonly retryable = false;

  constructor() {
    super("closed writer credentials are unavailable or invalid");
    this.name = "ClosedWriterCredentialError";
  }
}

/** Read without logging, copying into workflow input, or retaining the key. */
export async function readOpenAIAPIKey(resource: ClosedWriterCredentialResource): Promise<string> {
  if (resource.schemaVersion !== "closed-writer-credential-resource/1") {
    throw new ClosedWriterCredentialError();
  }
  let environment: Readonly<Record<string, string>>;
  try {
    environment = await resource.read();
  } catch {
    throw new ClosedWriterCredentialError();
  }
  if (environment === null || typeof environment !== "object" || Array.isArray(environment)) {
    throw new ClosedWriterCredentialError();
  }
  const keys = Object.keys(environment);
  const value = environment.OPENAI_API_KEY;
  if (keys.length !== 1 || keys[0] !== "OPENAI_API_KEY" || typeof value !== "string" || value.trim().length === 0 || /[\r\n]/u.test(value)) {
    throw new ClosedWriterCredentialError();
  }
  return value;
}
