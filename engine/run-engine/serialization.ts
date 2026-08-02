import type { JsonObject, JsonValue } from "../contracts/index.ts";
import { RunEngineError } from "./types.ts";

export function parseJson<Value extends JsonValue>(text: string, label: string): Value {
  try {
    return JSON.parse(text) as Value;
  } catch (error) {
    throw new RunEngineError("INVALID_STORED_JSON", `Cannot parse ${label}`, { cause: error });
  }
}

export function jsonObject(value: unknown, label: string): JsonObject {
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new RunEngineError("INVALID_JSON_OBJECT", `${label} must be a JSON object`);
  }
  return value as JsonObject;
}

export function stringifyJson(value: JsonValue): string {
  const encoded = JSON.stringify(value);
  if (encoded === undefined) {
    throw new RunEngineError("INVALID_JSON", "Value is not JSON serializable");
  }
  return encoded;
}

export function stableStringify(value: JsonValue): string {
  return `${JSON.stringify(sortJson(value), null, 2)}\n`;
}

export function stateKey(value: JsonValue): string {
  return typeof value === "string" ? value : JSON.stringify(sortJson(value));
}

export function sortJson(value: JsonValue): JsonValue {
  if (Array.isArray(value)) {
    return value.map((entry) => sortJson(entry));
  }
  if (value !== null && typeof value === "object") {
    const object = value as Readonly<Record<string, JsonValue>>;
    const result: Record<string, JsonValue> = {};
    for (const key of Object.keys(object).sort()) {
      const child = object[key];
      if (child !== undefined) {
        result[key] = sortJson(child);
      }
    }
    return result;
  }
  return value;
}

export function isoFromMs(milliseconds: number): string {
  return new Date(milliseconds).toISOString();
}

export function applySpecPath(
  root: JsonObject,
  path: string,
  replacement: JsonValue,
): JsonObject {
  const cloned = structuredClone(root) as Record<string, JsonValue>;
  const segments = path.startsWith("/")
    ? path
        .slice(1)
        .split("/")
        .filter((part) => part.length > 0)
        .map((part) => part.replaceAll("~1", "/").replaceAll("~0", "~"))
    : path.split(".").filter((part) => part.length > 0);
  if (segments.length === 0) {
    throw new RunEngineError("INVALID_SPEC_PATH", "Run spec replacement path is empty");
  }
  let cursor: JsonValue = cloned;
  for (const segment of segments.slice(0, -1)) {
    if (cursor === null || typeof cursor !== "object") {
      throw new RunEngineError("INVALID_SPEC_PATH", `Run spec path does not exist: ${path}`);
    }
    const next: JsonValue | undefined = Array.isArray(cursor)
      ? cursor[parseArrayIndex(segment, cursor.length, path)]
      : (cursor as Readonly<Record<string, JsonValue>>)[segment];
    if (next === undefined) {
      throw new RunEngineError("INVALID_SPEC_PATH", `Run spec path does not exist: ${path}`);
    }
    cursor = next;
  }
  const final = segments.at(-1);
  if (final === undefined || cursor === null || typeof cursor !== "object") {
    throw new RunEngineError("INVALID_SPEC_PATH", `Run spec path does not exist: ${path}`);
  }
  if (Array.isArray(cursor)) {
    const index = parseArrayIndex(final, cursor.length, path);
    (cursor as JsonValue[])[index] = replacement;
  } else {
    if (!(final in cursor)) {
      throw new RunEngineError("INVALID_SPEC_PATH", `Run spec path does not exist: ${path}`);
    }
    (cursor as Record<string, JsonValue>)[final] = replacement;
  }
  return cloned;
}

export function replaceArtifactReference(
  root: JsonObject,
  from: string,
  to: string,
): { readonly value: JsonObject; readonly replacements: number } {
  let replacements = 0;
  const walk = (value: JsonValue, path: readonly string[]): JsonValue => {
    if (typeof value === "string") {
      if (value === from && !path.includes("payload")) {
        replacements += 1;
        return to;
      }
      return value;
    }
    if (Array.isArray(value)) {
      return value.map((entry, index) => walk(entry, [...path, String(index)]));
    }
    if (value !== null && typeof value === "object") {
      const result: Record<string, JsonValue> = {};
      for (const [key, child] of Object.entries(value)) {
        result[key] = walk(child, [...path, key]);
      }
      return result;
    }
    return value;
  };
  return { value: walk(root, []) as JsonObject, replacements };
}

function parseArrayIndex(segment: string, length: number, path: string): number {
  const index = Number(segment);
  if (!Number.isInteger(index) || index < 0 || index >= length) {
    throw new RunEngineError("INVALID_SPEC_PATH", `Invalid array index in run spec path: ${path}`);
  }
  return index;
}
