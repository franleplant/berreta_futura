import { randomBytes, randomUUID, scrypt as scryptCallback, timingSafeEqual } from "node:crypto";
import {
  chmod,
  lstat,
  mkdir,
  open,
  rename,
  rm,
  stat,
} from "node:fs/promises";
import { constants as fsConstants } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { promisify } from "node:util";

import type { WorkOfferId, WorkClaim, WorkerCapability } from "../contracts/index.ts";

/**
 * The local authority store is deliberately separate from RunEngine's durable
 * database. It stores enrollment and credential material in an ignored,
 * owner-private directory; the engine receives only an authorization snapshot.
 */

const SCHEMA_VERSION = 1;
const SECRET_BYTES = 32;
const HASH_BYTES = 64;
const STATE_FILE = "authority.json";
const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/u;
const KNOWN_CAPABILITIES = new Set<WorkerCapability>([
  "image_model",
  "source_access",
  "source_blind",
  "subprocess",
  "text_model",
]);
const scrypt = promisify(scryptCallback);

type Authority = "human" | "machine" | "model" | "tool";
type NonHumanCapability = Exclude<WorkerCapability, "human">;
const authorizedWorkerToken = Symbol("authorized-worker-token");

export type AuthorityErrorCode =
  | "AUTHORIZATION_DENIED"
  | "CREDENTIAL_REVOKED"
  | "DUPLICATE_IDENTIFIER"
  | "IDENTITY_REVOKED"
  | "INVALID_ARGUMENT"
  | "INVALID_STORE"
  | "STORE_INSECURE"
  | "STORE_SYMLINK";

export class LocalAuthorityError extends Error {
  readonly code: AuthorityErrorCode;

  constructor(code: AuthorityErrorCode, message: string) {
    super(message);
    this.name = "LocalAuthorityError";
    this.code = code;
  }
}

export type HumanEnrollment = {
  readonly principalId: string;
  readonly displayName?: string;
  /** Extra non-human capabilities granted to this human principal. */
  readonly capabilities?: readonly NonHumanCapability[];
};

export type WorkerEnrollment = {
  readonly principalId: string;
  readonly authority: Exclude<Authority, "human">;
  readonly capabilities: readonly NonHumanCapability[];
  readonly displayName?: string;
};

export type CredentialProfileInput = {
  readonly principalId: string;
  readonly credentialProfileId?: string;
  readonly label?: string;
};

export type IssuedCredential = {
  readonly credentialProfileId: string;
  readonly principalId: string;
  readonly secret: string;
};

export type AuthorizationGrantInput = {
  readonly credentialProfileId: string;
  readonly grantId?: string;
  readonly capabilities: readonly WorkerCapability[];
};

export type AuthorityPrincipal = {
  readonly principalId: string;
  readonly authority: Authority;
  readonly capabilities: readonly WorkerCapability[];
  readonly displayName?: string;
  readonly revoked: boolean;
};

export type CredentialProfile = {
  readonly credentialProfileId: string;
  readonly principalId: string;
  readonly label?: string;
  readonly revoked: boolean;
};

export type AuthorizationGrant = {
  readonly grantId: string;
  readonly credentialProfileId: string;
  readonly capabilities: readonly WorkerCapability[];
  readonly revoked: boolean;
};

/** A canonical, sorted, secret-free view of the local authority state. */
export type AuthorizationSnapshot = {
  readonly schemaVersion: 1;
  readonly revision: number;
  readonly principals: readonly AuthorityPrincipal[];
  readonly credentialProfiles: readonly CredentialProfile[];
  readonly grants: readonly AuthorizationGrant[];
};

export type CredentialAuthentication = {
  readonly credentialProfileId: string;
  readonly secret: string;
};

export type Revocation =
  | { readonly principalId: string }
  | { readonly credentialProfileId: string }
  | { readonly grantId: string };

export type AuthorizedWorkerDescription = {
  readonly principalId: string;
  readonly credentialProfileId: string;
  readonly authority: Authority;
  readonly capabilities: readonly WorkerCapability[];
  readonly grantIds: readonly string[];
};

/**
 * An authenticated session, not a caller-constructible WorkerIdentity.
 *
 * The WorkerIdentity passed to the engine is held in a private field and is
 * freshly reconstructed from the persisted grants on every claim. Callers can
 * inspect the authorization, but cannot supply authority or capabilities to
 * claim work through this interface.
 */
export class AuthorizedWorker {
  readonly #store: LocalAuthorityStore;
  readonly #credentialProfileId: string;

  /** @internal Construction requires an unexported module token. */
  constructor(
    token: typeof authorizedWorkerToken,
    store: LocalAuthorityStore,
    credentialProfileId: string,
  ) {
    if (token !== authorizedWorkerToken) {
      throw new LocalAuthorityError("AUTHORIZATION_DENIED", "Authorized workers may only be minted by credential authentication");
    }
    this.#store = store;
    this.#credentialProfileId = credentialProfileId;
  }

  async describe(): Promise<AuthorizedWorkerDescription> {
    return await this.#store.describeAuthorizedCredential(this.#credentialProfileId);
  }

  async claim(port: WorkerClaimPort, offerId: WorkOfferId): Promise<WorkClaim> {
    await this.#store.describeAuthorizedCredential(this.#credentialProfileId);
    return await port.claimAuthorized(offerId, this);
  }
}

/** The narrow RunEngine boundary used by an authenticated session. */
export interface WorkerClaimPort {
  claimAuthorized(offerId: WorkOfferId, worker: AuthorizedWorker): Promise<WorkClaim>;
}

type StoredPrincipal = {
  readonly principalId: string;
  readonly authority: Authority;
  readonly capabilities: readonly WorkerCapability[];
  readonly displayName?: string;
  readonly revoked: boolean;
};

type StoredCredentialProfile = {
  readonly credentialProfileId: string;
  readonly principalId: string;
  readonly label?: string;
  readonly secretHash: string;
  readonly revoked: boolean;
};

type StoredGrant = {
  readonly grantId: string;
  readonly credentialProfileId: string;
  readonly capabilities: readonly WorkerCapability[];
  readonly revoked: boolean;
};

type StoredAuthorityState = {
  readonly schemaVersion: 1;
  readonly revision: number;
  readonly principals: readonly StoredPrincipal[];
  readonly credentialProfiles: readonly StoredCredentialProfile[];
  readonly grants: readonly StoredGrant[];
};

/**
 * File-backed local enrollment authority.
 *
 * Use a directory below `.magazine/`, which is ignored by this repository.
 * `init` creates the directory as 0700 and its state file as 0600 on POSIX.
 */
export class LocalAuthorityStore {
  readonly #directory: string;
  #mutationTail: Promise<void> = Promise.resolve();

  private constructor(directory: string) {
    this.#directory = directory;
  }

  static async init(directory: string): Promise<LocalAuthorityStore> {
    if (typeof directory !== "string" || directory.length === 0) {
      throw new LocalAuthorityError("INVALID_ARGUMENT", "Authority directory must be a non-empty string");
    }
    const store = new LocalAuthorityStore(resolve(directory));
    await store.#initialize();
    return store;
  }

  get directory(): string {
    return this.#directory;
  }

  async enrollHuman(input: unknown): Promise<AuthorityPrincipal> {
    const enrollment = parseHumanEnrollment(input);
    return await this.#mutate((state) => {
      assertUnused(state.principals.map((principal) => principal.principalId), enrollment.principalId, "principal");
      const principal: StoredPrincipal = {
        principalId: enrollment.principalId,
        authority: "human",
        capabilities: canonicalCapabilities(enrollment.capabilities ?? []),
        ...(enrollment.displayName === undefined ? {} : { displayName: enrollment.displayName }),
        revoked: false,
      };
      return { state: { ...state, principals: [...state.principals, principal] }, value: publicPrincipal(principal) };
    });
  }

  async enrollWorker(input: unknown): Promise<AuthorityPrincipal> {
    const enrollment = parseWorkerEnrollment(input);
    return await this.#mutate((state) => {
      assertUnused(state.principals.map((principal) => principal.principalId), enrollment.principalId, "principal");
      const principal: StoredPrincipal = {
        ...enrollment,
        capabilities: canonicalCapabilities(enrollment.capabilities),
        revoked: false,
      };
      return { state: { ...state, principals: [...state.principals, principal] }, value: publicPrincipal(principal) };
    });
  }

  /** Issues a new 256-bit, one-time-returned secret for an enrolled principal. */
  async createCredentialProfile(input: unknown): Promise<IssuedCredential> {
    const requested = parseCredentialProfileInput(input);
    const secret = randomBytes(SECRET_BYTES).toString("base64url");
    const secretHash = await hashSecret(secret);
    return await this.#mutate((state) => {
      const principal = state.principals.find((candidate) => candidate.principalId === requested.principalId);
      if (principal === undefined || principal.revoked) {
        throw new LocalAuthorityError("IDENTITY_REVOKED", `Principal ${requested.principalId} is unavailable`);
      }
      const credentialProfileId = requested.credentialProfileId ?? `credential-${randomUUID()}`;
      assertIdentifier(credentialProfileId, "credentialProfileId");
      assertUnused(
        state.credentialProfiles.map((credential) => credential.credentialProfileId),
        credentialProfileId,
        "credential profile",
      );
      const profile: StoredCredentialProfile = {
        credentialProfileId,
        principalId: requested.principalId,
        ...(requested.label === undefined ? {} : { label: requested.label }),
        secretHash,
        revoked: false,
      };
      return {
        state: { ...state, credentialProfiles: [...state.credentialProfiles, profile] },
        value: { credentialProfileId, principalId: requested.principalId, secret },
      };
    });
  }

  async grant(input: unknown): Promise<AuthorizationGrant> {
    const requested = parseGrantInput(input);
    return await this.#mutate((state) => {
      const credential = state.credentialProfiles.find(
        (candidate) => candidate.credentialProfileId === requested.credentialProfileId,
      );
      if (credential === undefined || credential.revoked) {
        throw new LocalAuthorityError("CREDENTIAL_REVOKED", "Credential profile is unavailable");
      }
      const principal = state.principals.find((candidate) => candidate.principalId === credential.principalId);
      if (principal === undefined || principal.revoked) {
        throw new LocalAuthorityError("IDENTITY_REVOKED", `Principal ${credential.principalId} is unavailable`);
      }
      const capabilities = canonicalCapabilities(requested.capabilities);
      if (capabilities.length === 0) {
        throw new LocalAuthorityError("INVALID_ARGUMENT", "A grant must include at least one capability");
      }
      const unavailable = capabilities.filter((capability) => !principal.capabilities.includes(capability));
      if (unavailable.length > 0) {
        throw new LocalAuthorityError(
          "INVALID_ARGUMENT",
          `Grant includes capabilities not enrolled for ${principal.principalId}: ${unavailable.join(", ")}`,
        );
      }
      const grantId = requested.grantId ?? `grant-${randomUUID()}`;
      assertIdentifier(grantId, "grantId");
      assertUnused(state.grants.map((grant) => grant.grantId), grantId, "grant");
      const grant: StoredGrant = { grantId, credentialProfileId: credential.credentialProfileId, capabilities, revoked: false };
      return { state: { ...state, grants: [...state.grants, grant] }, value: publicGrant(grant) };
    });
  }

  /** Revocation is permanent. Re-enrollment uses a new identity, credential, or grant ID. */
  async revoke(input: unknown): Promise<AuthorizationSnapshot> {
    const requested = parseRevocation(input);
    return await this.#mutate((state) => {
      if ("principalId" in requested) {
        const exists = state.principals.some((principal) => principal.principalId === requested.principalId);
        if (!exists) throw new LocalAuthorityError("INVALID_ARGUMENT", `Unknown principal ${requested.principalId}`);
        return {
          state: {
            ...state,
            principals: state.principals.map((principal) =>
              principal.principalId === requested.principalId ? { ...principal, revoked: true } : principal,
            ),
          },
          valueFromState: true,
        };
      }
      if ("credentialProfileId" in requested) {
        const exists = state.credentialProfiles.some(
          (credential) => credential.credentialProfileId === requested.credentialProfileId,
        );
        if (!exists) throw new LocalAuthorityError("INVALID_ARGUMENT", "Unknown credential profile");
        return {
          state: {
            ...state,
            credentialProfiles: state.credentialProfiles.map((credential) =>
              credential.credentialProfileId === requested.credentialProfileId ? { ...credential, revoked: true } : credential,
            ),
          },
          valueFromState: true,
        };
      }
      const exists = state.grants.some((grant) => grant.grantId === requested.grantId);
      if (!exists) throw new LocalAuthorityError("INVALID_ARGUMENT", `Unknown grant ${requested.grantId}`);
      return {
        state: {
          ...state,
          grants: state.grants.map((grant) =>
            grant.grantId === requested.grantId ? { ...grant, revoked: true } : grant,
          ),
        },
        valueFromState: true,
      };
    });
  }

  async authenticate(input: unknown): Promise<AuthorizedWorker> {
    const credential = parseCredentialAuthentication(input);
    const state = await this.#readState();
    const profile = state.credentialProfiles.find(
      (candidate) => candidate.credentialProfileId === credential.credentialProfileId,
    );
    if (profile === undefined || profile.revoked || !(await verifySecret(credential.secret, profile.secretHash))) {
      throw new LocalAuthorityError("AUTHORIZATION_DENIED", "Credential authentication failed");
    }
    await this.describeAuthorizedCredential(profile.credentialProfileId);
    return new AuthorizedWorker(authorizedWorkerToken, this, profile.credentialProfileId);
  }

  async snapshot(): Promise<AuthorizationSnapshot> {
    return snapshotOf(await this.#readState());
  }

  async describeAuthorizedCredential(credentialProfileId: string): Promise<AuthorizedWorkerDescription> {
    const state = await this.#readState();
    const credential = state.credentialProfiles.find((candidate) => candidate.credentialProfileId === credentialProfileId);
    if (credential === undefined || credential.revoked) {
      throw new LocalAuthorityError("CREDENTIAL_REVOKED", "Credential profile is revoked or unknown");
    }
    const principal = state.principals.find((candidate) => candidate.principalId === credential.principalId);
    if (principal === undefined || principal.revoked) {
      throw new LocalAuthorityError("IDENTITY_REVOKED", `Principal ${credential.principalId} is revoked or unknown`);
    }
    const activeGrants = state.grants.filter(
      (grant) => grant.credentialProfileId === credentialProfileId && !grant.revoked,
    );
    const capabilities = canonicalCapabilities(activeGrants.flatMap((grant) => grant.capabilities));
    if (capabilities.length === 0) {
      throw new LocalAuthorityError("AUTHORIZATION_DENIED", "Credential has no active capability grant");
    }
    return Object.freeze({
      principalId: principal.principalId,
      credentialProfileId,
      authority: principal.authority,
      capabilities: Object.freeze(capabilities),
      grantIds: Object.freeze(activeGrants.map((grant) => grant.grantId).sort()),
    });
  }

  async #initialize(): Promise<void> {
    await mkdir(dirname(this.#directory), { recursive: true, mode: 0o700 });
    const parent = await lstat(dirname(this.#directory));
    if (parent.isSymbolicLink()) {
      throw new LocalAuthorityError("STORE_SYMLINK", "Authority directory parent may not be a symbolic link");
    }
    const existing = await lstatOrUndefined(this.#directory);
    if (existing === undefined) {
      await mkdir(this.#directory, { mode: 0o700 });
    } else if (existing.isSymbolicLink()) {
      throw new LocalAuthorityError("STORE_SYMLINK", "Authority directory may not be a symbolic link");
    } else if (!existing.isDirectory()) {
      throw new LocalAuthorityError("INVALID_STORE", "Authority path must be a directory");
    }
    await this.#secureDirectory();
    const state = await this.#readStateOrUndefined();
    if (state === undefined) {
      await this.#writeState(emptyState());
    }
  }

  async #mutate<T>(operation: (state: StoredAuthorityState) => Mutation<T>): Promise<T> {
    let release: (() => void) | undefined;
    const previous = this.#mutationTail;
    this.#mutationTail = new Promise<void>((resolveMutation) => {
      release = resolveMutation;
    });
    await previous;
    try {
      const current = await this.#readState();
      const mutation = operation(current);
      const next: StoredAuthorityState = { ...mutation.state, revision: current.revision + 1 };
      await this.#writeState(next);
      return mutation.valueFromState === true
        ? (snapshotOf(next) as T)
        : (mutation.value as T);
    } finally {
      release?.();
    }
  }

  async #readState(): Promise<StoredAuthorityState> {
    const state = await this.#readStateOrUndefined();
    if (state === undefined) {
      throw new LocalAuthorityError("INVALID_STORE", "Authority store was not initialized");
    }
    return state;
  }

  async #readStateOrUndefined(): Promise<StoredAuthorityState | undefined> {
    await this.#secureDirectory();
    const statePath = join(this.#directory, STATE_FILE);
    const entry = await lstatOrUndefined(statePath);
    if (entry === undefined) return undefined;
    if (entry.isSymbolicLink()) {
      throw new LocalAuthorityError("STORE_SYMLINK", "Authority state file may not be a symbolic link");
    }
    if (!entry.isFile()) {
      throw new LocalAuthorityError("INVALID_STORE", "Authority state path must be a regular file");
    }
    await secureExistingFile(statePath);
    const handle = await open(statePath, fsConstants.O_RDONLY | noFollowFlag());
    try {
      const file = await handle.stat();
      if (!file.isFile()) {
        throw new LocalAuthorityError("INVALID_STORE", "Authority state path must be a regular file");
      }
      return parseState(JSON.parse(await handle.readFile({ encoding: "utf8" })) as unknown);
    } catch (error) {
      if (error instanceof LocalAuthorityError) throw error;
      throw new LocalAuthorityError("INVALID_STORE", "Authority state file is not valid JSON");
    } finally {
      await handle.close();
    }
  }

  async #writeState(state: StoredAuthorityState): Promise<void> {
    await this.#secureDirectory();
    const statePath = join(this.#directory, STATE_FILE);
    const existing = await lstatOrUndefined(statePath);
    if (existing?.isSymbolicLink()) {
      throw new LocalAuthorityError("STORE_SYMLINK", "Authority state file may not be a symbolic link");
    }
    if (existing !== undefined && !existing.isFile()) {
      throw new LocalAuthorityError("INVALID_STORE", "Authority state path must be a regular file");
    }
    const temporary = join(this.#directory, `.authority-${randomUUID()}.tmp`);
    try {
      const handle = await open(
        temporary,
        fsConstants.O_WRONLY | fsConstants.O_CREAT | fsConstants.O_EXCL | noFollowFlag(),
        0o600,
      );
      try {
        await handle.writeFile(`${JSON.stringify(state)}\n`, { encoding: "utf8" });
        if (process.platform !== "win32") await handle.chmod(0o600);
        await handle.sync();
      } finally {
        await handle.close();
      }
      await rename(temporary, statePath);
      await secureExistingFile(statePath);
    } finally {
      await rm(temporary, { force: true }).catch(() => undefined);
    }
  }

  async #secureDirectory(): Promise<void> {
    const directory = await lstat(this.#directory);
    if (directory.isSymbolicLink()) {
      throw new LocalAuthorityError("STORE_SYMLINK", "Authority directory may not be a symbolic link");
    }
    if (!directory.isDirectory()) {
      throw new LocalAuthorityError("INVALID_STORE", "Authority path must be a directory");
    }
    await assertCurrentOwner(directory, this.#directory);
    if (process.platform !== "win32") {
      await chmod(this.#directory, 0o700);
      const secured = await stat(this.#directory);
      if ((secured.mode & 0o077) !== 0) {
        throw new LocalAuthorityError("STORE_INSECURE", "Authority directory is not owner-private");
      }
    }
  }
}

type Mutation<T> = {
  readonly state: Omit<StoredAuthorityState, "revision"> & { readonly revision?: number };
  readonly value?: T;
  readonly valueFromState?: boolean;
};

function emptyState(): StoredAuthorityState {
  return { schemaVersion: SCHEMA_VERSION, revision: 0, principals: [], credentialProfiles: [], grants: [] };
}

function snapshotOf(state: StoredAuthorityState): AuthorizationSnapshot {
  return Object.freeze({
    schemaVersion: SCHEMA_VERSION,
    revision: state.revision,
    principals: Object.freeze(state.principals.map(publicPrincipal).sort(by("principalId"))),
    credentialProfiles: Object.freeze(state.credentialProfiles.map(publicCredential).sort(by("credentialProfileId"))),
    grants: Object.freeze(state.grants.map(publicGrant).sort(by("grantId"))),
  });
}

function publicPrincipal(principal: StoredPrincipal): AuthorityPrincipal {
  return Object.freeze({
    principalId: principal.principalId,
    authority: principal.authority,
    capabilities: Object.freeze(canonicalCapabilities(principal.capabilities)),
    ...(principal.displayName === undefined ? {} : { displayName: principal.displayName }),
    revoked: principal.revoked,
  });
}

function publicCredential(credential: StoredCredentialProfile): CredentialProfile {
  return Object.freeze({
    credentialProfileId: credential.credentialProfileId,
    principalId: credential.principalId,
    ...(credential.label === undefined ? {} : { label: credential.label }),
    revoked: credential.revoked,
  });
}

function publicGrant(grant: StoredGrant): AuthorizationGrant {
  return Object.freeze({
    grantId: grant.grantId,
    credentialProfileId: grant.credentialProfileId,
    capabilities: Object.freeze(canonicalCapabilities(grant.capabilities)),
    revoked: grant.revoked,
  });
}

function by<Key extends string>(key: Key): (left: Record<Key, string>, right: Record<Key, string>) => number {
  return (left, right) => left[key].localeCompare(right[key] as string);
}

function parseHumanEnrollment(value: unknown): HumanEnrollment {
  const record = strictRecord(value, ["principalId", "displayName", "capabilities"], "human enrollment");
  const capabilities = record.capabilities === undefined
    ? undefined
    : parseCapabilities(record.capabilities, "human enrollment capabilities");
  return {
      principalId: parseIdentifier(record.principalId, "principalId"),
      ...(record.displayName === undefined ? {} : { displayName: parseDisplayName(record.displayName) }),
    ...(capabilities === undefined ? {} : { capabilities: capabilities as readonly NonHumanCapability[] }),
  };
}

function parseWorkerEnrollment(value: unknown): WorkerEnrollment {
  const record = strictRecord(value, ["principalId", "authority", "capabilities", "displayName"], "worker enrollment");
  const authority = record.authority;
  if (authority !== "machine" && authority !== "model" && authority !== "tool") {
    throw new LocalAuthorityError("INVALID_ARGUMENT", "Worker authority must be machine, model, or tool");
  }
  return {
    principalId: parseIdentifier(record.principalId, "principalId"),
    authority,
    capabilities: parseCapabilities(record.capabilities, "worker enrollment capabilities") as readonly NonHumanCapability[],
    ...(record.displayName === undefined ? {} : { displayName: parseDisplayName(record.displayName) }),
  };
}

function parseCredentialProfileInput(value: unknown): CredentialProfileInput {
  const record = strictRecord(value, ["principalId", "credentialProfileId", "label"], "credential profile");
  return {
    principalId: parseIdentifier(record.principalId, "principalId"),
    ...(record.credentialProfileId === undefined
      ? {}
      : { credentialProfileId: parseIdentifier(record.credentialProfileId, "credentialProfileId") }),
    ...(record.label === undefined ? {} : { label: parseLabel(record.label) }),
  };
}

function parseGrantInput(value: unknown): AuthorizationGrantInput {
  const record = strictRecord(value, ["credentialProfileId", "grantId", "capabilities"], "authorization grant");
  return {
    credentialProfileId: parseIdentifier(record.credentialProfileId, "credentialProfileId"),
    ...(record.grantId === undefined ? {} : { grantId: parseIdentifier(record.grantId, "grantId") }),
    capabilities: parseCapabilities(record.capabilities, "grant capabilities"),
  };
}

function parseCredentialAuthentication(value: unknown): CredentialAuthentication {
  const record = strictRecord(value, ["credentialProfileId", "secret"], "credential authentication");
  const secret = record.secret;
  if (typeof secret !== "string" || !/^[A-Za-z0-9_-]{43}$/u.test(secret)) {
    throw new LocalAuthorityError("AUTHORIZATION_DENIED", "Credential authentication failed");
  }
  return { credentialProfileId: parseIdentifier(record.credentialProfileId, "credentialProfileId"), secret };
}

function parseRevocation(value: unknown): Revocation {
  const record = strictRecord(value, ["principalId", "credentialProfileId", "grantId"], "revocation");
  const supplied = ["principalId", "credentialProfileId", "grantId"].filter((key) => record[key] !== undefined);
  if (supplied.length !== 1) {
    throw new LocalAuthorityError("INVALID_ARGUMENT", "Revocation must name exactly one principal, credential profile, or grant");
  }
  if (record.principalId !== undefined) return { principalId: parseIdentifier(record.principalId, "principalId") };
  if (record.credentialProfileId !== undefined) {
    return { credentialProfileId: parseIdentifier(record.credentialProfileId, "credentialProfileId") };
  }
  return { grantId: parseIdentifier(record.grantId, "grantId") };
}

function parseState(value: unknown): StoredAuthorityState {
  const record = strictRecord(value, ["schemaVersion", "revision", "principals", "credentialProfiles", "grants"], "authority state");
  const revision = record.revision;
  if (record.schemaVersion !== SCHEMA_VERSION || typeof revision !== "number" || !Number.isSafeInteger(revision) || revision < 0) {
    throw new LocalAuthorityError("INVALID_STORE", "Authority state has an unsupported schema version or revision");
  }
  const principals = parseArray(record.principals, "principals").map(parseStoredPrincipal);
  const credentialProfiles = parseArray(record.credentialProfiles, "credentialProfiles").map(parseStoredCredential);
  const grants = parseArray(record.grants, "grants").map(parseStoredGrant);
  assertUnique(principals.map((principal) => principal.principalId), "principal");
  assertUnique(credentialProfiles.map((credential) => credential.credentialProfileId), "credential profile");
  assertUnique(grants.map((grant) => grant.grantId), "grant");
  for (const credential of credentialProfiles) {
    if (!principals.some((principal) => principal.principalId === credential.principalId)) {
      throw new LocalAuthorityError("INVALID_STORE", "Credential profile refers to an unknown principal");
    }
  }
  for (const grant of grants) {
    const credential = credentialProfiles.find((candidate) => candidate.credentialProfileId === grant.credentialProfileId);
    if (credential === undefined) throw new LocalAuthorityError("INVALID_STORE", "Grant refers to an unknown credential profile");
    const principal = principals.find((candidate) => candidate.principalId === credential.principalId);
    if (principal === undefined || grant.capabilities.some((capability) => !principal.capabilities.includes(capability))) {
      throw new LocalAuthorityError("INVALID_STORE", "Grant exceeds its principal capabilities");
    }
  }
  return { schemaVersion: SCHEMA_VERSION, revision, principals, credentialProfiles, grants };
}

function parseStoredPrincipal(value: unknown): StoredPrincipal {
  const record = strictRecord(value, ["principalId", "authority", "capabilities", "displayName", "revoked"], "stored principal");
  const authority = record.authority;
  if (authority !== "human" && authority !== "machine" && authority !== "model" && authority !== "tool") {
    throw new LocalAuthorityError("INVALID_STORE", "Stored principal has an invalid authority");
  }
  const capabilities = parseCapabilities(record.capabilities, "stored principal capabilities");
  if (typeof record.revoked !== "boolean") throw new LocalAuthorityError("INVALID_STORE", "Stored principal has invalid revocation state");
  return {
    principalId: parseIdentifier(record.principalId, "principalId"),
    authority,
    capabilities,
    ...(record.displayName === undefined ? {} : { displayName: parseDisplayName(record.displayName) }),
    revoked: record.revoked,
  };
}

function parseStoredCredential(value: unknown): StoredCredentialProfile {
  const record = strictRecord(value, ["credentialProfileId", "principalId", "label", "secretHash", "revoked"], "stored credential profile");
  if (typeof record.secretHash !== "string" || !/^scrypt\$[A-Za-z0-9_-]+\$[A-Za-z0-9_-]+$/u.test(record.secretHash)) {
    throw new LocalAuthorityError("INVALID_STORE", "Credential profile has an invalid secret hash");
  }
  if (typeof record.revoked !== "boolean") throw new LocalAuthorityError("INVALID_STORE", "Credential profile has invalid revocation state");
  return {
    credentialProfileId: parseIdentifier(record.credentialProfileId, "credentialProfileId"),
    principalId: parseIdentifier(record.principalId, "principalId"),
    ...(record.label === undefined ? {} : { label: parseLabel(record.label) }),
    secretHash: record.secretHash,
    revoked: record.revoked,
  };
}

function parseStoredGrant(value: unknown): StoredGrant {
  const record = strictRecord(value, ["grantId", "credentialProfileId", "capabilities", "revoked"], "stored grant");
  if (typeof record.revoked !== "boolean") throw new LocalAuthorityError("INVALID_STORE", "Grant has invalid revocation state");
  return {
    grantId: parseIdentifier(record.grantId, "grantId"),
    credentialProfileId: parseIdentifier(record.credentialProfileId, "credentialProfileId"),
    capabilities: parseCapabilities(record.capabilities, "stored grant capabilities"),
    revoked: record.revoked,
  };
}

function strictRecord(value: unknown, allowed: readonly string[], label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new LocalAuthorityError("INVALID_ARGUMENT", `${label} must be an object`);
  }
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) {
    throw new LocalAuthorityError("INVALID_ARGUMENT", `${label} must be a plain object`);
  }
  const record = value as Record<string, unknown>;
  const unexpected = Object.keys(record).find((key) => !allowed.includes(key));
  if (unexpected !== undefined) {
    throw new LocalAuthorityError("INVALID_ARGUMENT", `${label} contains unknown field ${unexpected}`);
  }
  return record;
}

function parseArray(value: unknown, label: string): readonly unknown[] {
  if (!Array.isArray(value)) throw new LocalAuthorityError("INVALID_STORE", `${label} must be an array`);
  return value;
}

function parseIdentifier(value: unknown, label: string): string {
  if (typeof value !== "string") throw new LocalAuthorityError("INVALID_ARGUMENT", `${label} must be a string`);
  assertIdentifier(value, label);
  return value;
}

function assertIdentifier(value: string, label: string): void {
  if (!IDENTIFIER.test(value)) {
    throw new LocalAuthorityError("INVALID_ARGUMENT", `${label} has an invalid identifier`);
  }
}

function parseDisplayName(value: unknown): string {
  if (typeof value !== "string" || value.length === 0 || value.length > 200) {
    throw new LocalAuthorityError("INVALID_ARGUMENT", "displayName must be a non-empty string of at most 200 characters");
  }
  return value;
}

function parseLabel(value: unknown): string {
  if (typeof value !== "string" || value.length === 0 || value.length > 200) {
    throw new LocalAuthorityError("INVALID_ARGUMENT", "label must be a non-empty string of at most 200 characters");
  }
  return value;
}

function parseCapabilities(value: unknown, label: string): readonly WorkerCapability[] {
  if (!Array.isArray(value) || value.some((capability) => typeof capability !== "string" || !KNOWN_CAPABILITIES.has(capability as WorkerCapability))) {
    throw new LocalAuthorityError("INVALID_ARGUMENT", `${label} must contain known worker capabilities`);
  }
  return canonicalCapabilities(value as readonly WorkerCapability[]);
}

function canonicalCapabilities(capabilities: readonly WorkerCapability[]): readonly WorkerCapability[] {
  if (capabilities.includes("human")) {
    throw new LocalAuthorityError("INVALID_ARGUMENT", "Human authority is not a worker capability");
  }
  return [...new Set(capabilities)].sort();
}

function assertUnused(values: readonly string[], value: string, label: string): void {
  if (values.includes(value)) throw new LocalAuthorityError("DUPLICATE_IDENTIFIER", `Duplicate ${label} ${value}`);
}

function assertUnique(values: readonly string[], label: string): void {
  if (new Set(values).size !== values.length) throw new LocalAuthorityError("INVALID_STORE", `Duplicate ${label} ID in authority store`);
}

async function hashSecret(secret: string): Promise<string> {
  const salt = randomBytes(16);
  const derived = Buffer.from(await scrypt(secret, salt, HASH_BYTES) as Uint8Array);
  return `scrypt$${salt.toString("base64url")}$${derived.toString("base64url")}`;
}

async function verifySecret(secret: string, encoded: string): Promise<boolean> {
  const [, saltEncoded, expectedEncoded] = encoded.split("$");
  if (saltEncoded === undefined || expectedEncoded === undefined) return false;
  try {
    const expected = Buffer.from(expectedEncoded, "base64url");
    const actual = Buffer.from(
      await scrypt(secret, Buffer.from(saltEncoded, "base64url"), expected.length) as Uint8Array,
    );
    return expected.length === actual.length && timingSafeEqual(expected, actual);
  } catch {
    return false;
  }
}

function noFollowFlag(): number {
  return typeof fsConstants.O_NOFOLLOW === "number" ? fsConstants.O_NOFOLLOW : 0;
}

async function lstatOrUndefined(path: string): Promise<Awaited<ReturnType<typeof lstat>> | undefined> {
  try {
    return await lstat(path);
  } catch (error: unknown) {
    if (isErrno(error, "ENOENT")) return undefined;
    throw error;
  }
}

async function assertCurrentOwner(entry: Awaited<ReturnType<typeof lstat>>, path: string): Promise<void> {
  if (process.platform === "win32" || typeof process.getuid !== "function") return;
  if (entry.uid !== process.getuid()) {
    throw new LocalAuthorityError("STORE_INSECURE", `Authority path is not owned by the current user: ${path}`);
  }
}

async function secureExistingFile(path: string): Promise<void> {
  const entry = await lstat(path);
  if (entry.isSymbolicLink()) throw new LocalAuthorityError("STORE_SYMLINK", "Authority state file may not be a symbolic link");
  if (!entry.isFile()) throw new LocalAuthorityError("INVALID_STORE", "Authority state path must be a regular file");
  await assertCurrentOwner(entry, path);
  if (process.platform !== "win32") {
    await chmod(path, 0o600);
    const secured = await stat(path);
    if ((secured.mode & 0o077) !== 0) {
      throw new LocalAuthorityError("STORE_INSECURE", "Authority state file is not owner-private");
    }
  }
}

function isErrno(error: unknown, code: string): boolean {
  return typeof error === "object" && error !== null && "code" in error && (error as { readonly code?: unknown }).code === code;
}
