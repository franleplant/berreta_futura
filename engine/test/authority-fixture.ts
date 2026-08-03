import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  LocalAuthorityStore,
  type AuthorizedWorker,
  type WorkerClaimPort,
} from "../authority/local-authority.ts";
import type {
  WorkAuthority,
  WorkClaim,
  WorkOfferView,
  WorkerCapability,
} from "../contracts/index.ts";
import type { Executor, ExecutorRegistration } from "../executors/index.ts";

export type FixtureWorkerOptions = {
  /** Reuse this principal across claims, including a restarted engine. */
  readonly principalId?: string;
  readonly authority?: WorkAuthority;
  readonly capabilities?: readonly WorkerCapability[];
};

/**
 * Test-only issuer for claims that cross the public RunEngine boundary.
 *
 * It deliberately exercises the same enrollment, credential issuance, grant,
 * and authentication sequence as a configured local worker. Sessions are
 * cached by their exact immutable authority shape so a test can use stable
 * principals across engine restarts without constructing WorkerIdentity.
 */
export class AuthorityTestHarness {
  readonly root: string;
  readonly store: LocalAuthorityStore;
  readonly #sessions = new Map<string, AuthorizedWorker>();

  private constructor(root: string, store: LocalAuthorityStore) {
    this.root = root;
    this.store = store;
  }

  static async create(root?: string): Promise<AuthorityTestHarness> {
    const fixtureRoot = root ?? await mkdtemp(join(tmpdir(), "mag-authority-fixture-"));
    return new AuthorityTestHarness(fixtureRoot, await LocalAuthorityStore.init(join(fixtureRoot, "authority")));
  }

  async dispose(): Promise<void> {
    await rm(this.root, { recursive: true, force: true });
  }

  async workerFor(offer: WorkOfferView, options: FixtureWorkerOptions = {}): Promise<AuthorizedWorker> {
    const authority = options.authority ?? offer.requirements?.authority ??
      (offer.allowedWorkerCapabilities.includes("human") ? "human" : "tool");
    const requested = options.capabilities ?? offer.requirements?.capabilities ??
      offer.allowedWorkerCapabilities.filter((capability) => capability !== "human");
    // A human session still needs a non-human grant to authenticate. It is an
    // issuer requirement, not a spoofable `human` capability.
    const capabilities = canonicalCapabilities(authority === "human" && requested.length === 0
      ? ["source_access"]
      : requested);
    const principalId = options.principalId ?? `fixture-${authority}-${capabilities.join("-")}`;
    const key = `${principalId}\u0000${authority}\u0000${capabilities.join(",")}`;
    const cached = this.#sessions.get(key);
    if (cached !== undefined) return cached;

    if (authority === "human") {
      await this.store.enrollHuman({ principalId, capabilities });
    } else {
      await this.store.enrollWorker({ principalId, authority, capabilities });
    }
    const credential = await this.store.createCredentialProfile({
      principalId,
      credentialProfileId: `${principalId}-credential`,
    });
    await this.store.grant({
      credentialProfileId: credential.credentialProfileId,
      grantId: `${principalId}-grant`,
      capabilities,
    });
    const session = await this.store.authenticate({
      credentialProfileId: credential.credentialProfileId,
      secret: credential.secret,
    });
    this.#sessions.set(key, session);
    return session;
  }

  async claim(
    engine: WorkerClaimPort,
    offer: WorkOfferView,
    options: FixtureWorkerOptions = {},
  ): Promise<WorkClaim> {
    return await (await this.workerFor(offer, options)).claim(engine, offer.id);
  }

  async human(principalId = "fixture-human"): Promise<AuthorizedWorker> {
    return await this.workerFor({
      id: "fixture-human-offer",
      allowedWorkerCapabilities: ["human"],
      requirements: { authority: "human", capabilities: [], minimumAssurance: "local_bearer" },
    } as unknown as WorkOfferView, { principalId });
  }

  async registration(
    executor: Executor,
    options: Omit<ExecutorRegistration, "executor" | "authorizedWorker"> = {},
  ): Promise<ExecutorRegistration> {
    const capabilities = executor.worker.capabilities.filter((capability) => capability !== "human");
    const authority = executor.worker.authority;
    const offer = {
      id: executor.id,
      allowedWorkerCapabilities: capabilities,
      requirements: { authority, capabilities, minimumAssurance: "local_bearer" },
    } as unknown as WorkOfferView;
    return {
      executor,
      authorizedWorker: await this.workerFor(offer, {
        principalId: executor.worker.principalId,
        authority,
        capabilities,
      }),
      ...options,
    };
  }
}

function canonicalCapabilities(capabilities: readonly WorkerCapability[]): WorkerCapability[] {
  return [...new Set(capabilities)].sort();
}
