import { randomBytes } from "node:crypto";

import type { RevisionId } from "../contracts/index.ts";

const BASE32 = "abcdefghijklmnopqrstuvwxyz234567";
const REVISION_ID = /^rev_(\d{8})T(\d{9})Z_([a-z2-7]{12})$/u;

export function newRevisionId(
  now: Date = new Date(),
  entropy: Uint8Array = randomBytes(8),
): RevisionId {
  if (!Number.isFinite(now.valueOf())) {
    throw new Error("revision time must be a valid Date");
  }
  if (entropy.byteLength < 8) {
    throw new Error("revision identity needs at least 64 bits of entropy");
  }
  const timestamp = now.toISOString()
    .replaceAll("-", "")
    .replaceAll(":", "")
    .replace(".", "");
  return `rev_${timestamp}_${base32(entropy).slice(0, 12)}` as RevisionId;
}

export function parseRevisionId(value: string): RevisionId {
  const match = REVISION_ID.exec(value);
  if (match === null) {
    throw new Error(`invalid RevisionId: ${value}`);
  }
  const [, date, time] = match;
  const iso = `${date?.slice(0, 4)}-${date?.slice(4, 6)}-${date?.slice(6, 8)}`
    + `T${time?.slice(0, 2)}:${time?.slice(2, 4)}:${time?.slice(4, 6)}`
    + `.${time?.slice(6, 9)}Z`;
  if (new Date(iso).toISOString() !== iso) {
    throw new Error(`invalid RevisionId timestamp: ${value}`);
  }
  return value as RevisionId;
}

function base32(bytes: Uint8Array): string {
  let accumulator = 0;
  let bits = 0;
  let output = "";
  for (const byte of bytes) {
    accumulator = (accumulator << 8) | byte;
    bits += 8;
    while (bits >= 5) {
      bits -= 5;
      output += BASE32[(accumulator >>> bits) & 31];
      accumulator &= (1 << bits) - 1;
    }
  }
  if (bits > 0) {
    output += BASE32[(accumulator << (5 - bits)) & 31];
  }
  return output;
}
