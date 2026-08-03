import assert from "node:assert/strict";
import { chmod, lstat, mkdtemp, readFile, rm, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import {
  AuthorizedWorker,
  LocalAuthorityError,
  LocalAuthorityStore,
  type WorkerClaimPort,
} from "../authority/local-authority.ts";
import type { WorkClaim } from "../contracts/index.ts";

async function withStore(
  name: string,
  run: (store: LocalAuthorityStore, root: string) => Promise<void>,
): Promise<void> {
  const root = await mkdtemp(join(tmpdir(), `${name}-`));
  try {
    await run(await LocalAuthorityStore.init(join(root, "authority")), root);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

test("local authority persists a hash only and derives a grant-bound worker session", async () => {
  await withStore("local-authority-hash", async (store) => {
    const principal = await store.enrollWorker({
      principalId: "layout-renderer",
      authority: "tool",
      capabilities: ["subprocess", "source_blind"],
      displayName: "Layout renderer",
    });
    assert.deepEqual(principal.capabilities, ["source_blind", "subprocess"]);

    const issued = await store.createCredentialProfile({
      principalId: principal.principalId,
      credentialProfileId: "layout-credential",
      label: "production",
    });
    assert.match(issued.secret, /^[A-Za-z0-9_-]{43}$/u);
    await store.grant({
      credentialProfileId: issued.credentialProfileId,
      grantId: "layout-grant",
      capabilities: ["subprocess"],
    });

    const serialized = await readFile(join(store.directory, "authority.json"), "utf8");
    assert.doesNotMatch(serialized, new RegExp(issued.secret, "u"));
    assert.match(serialized, /"secretHash":"scrypt\$/u);

    const session = await store.authenticate({
      credentialProfileId: issued.credentialProfileId,
      secret: issued.secret,
    });
    assert.deepEqual(await session.describe(), {
      principalId: "layout-renderer",
      credentialProfileId: "layout-credential",
      authority: "tool",
      capabilities: ["subprocess"],
      grantIds: ["layout-grant"],
    });
  });
});

test("human authority is not a grantable capability and inputs reject unknown identity fields", async () => {
  await withStore("local-authority-identity", async (store) => {
    await assert.rejects(
      store.enrollHuman({ principalId: "editor", capabilities: ["human"] }),
      (error: unknown) => error instanceof LocalAuthorityError && error.code === "INVALID_ARGUMENT",
    );
    await assert.rejects(
      store.enrollWorker({
        principalId: "tool",
        authority: "tool",
        capabilities: ["subprocess"],
        injectedAuthority: "human",
      }),
      /unknown field injectedAuthority/u,
    );

    const human = await store.enrollHuman({ principalId: "editor", capabilities: ["source_access"] });
    assert.equal(human.authority, "human");
    assert.deepEqual(human.capabilities, ["source_access"]);
    const credential = await store.createCredentialProfile({ principalId: human.principalId });
    await assert.rejects(
      store.grant({ credentialProfileId: credential.credentialProfileId, capabilities: ["human"] }),
      /worker capabilities/u,
    );
    await assert.rejects(
      store.authenticate({ credentialProfileId: credential.credentialProfileId, secret: credential.secret, extra: true }),
      /unknown field extra/u,
    );
  });
});

test("revocation disables already-authenticated sessions before the claim port is reached", async () => {
  await withStore("local-authority-revoke", async (store) => {
    await store.enrollWorker({ principalId: "measurer", authority: "tool", capabilities: ["subprocess"] });
    const credential = await store.createCredentialProfile({ principalId: "measurer", credentialProfileId: "measure-credential" });
    await store.grant({ credentialProfileId: credential.credentialProfileId, grantId: "measure-grant", capabilities: ["subprocess"] });
    const session = await store.authenticate({ credentialProfileId: credential.credentialProfileId, secret: credential.secret });
    await store.revoke({ grantId: "measure-grant" });

    let reachedPort = false;
    const port: WorkerClaimPort = {
      async claimAuthorized(): Promise<WorkClaim> {
        reachedPort = true;
        return undefined as unknown as WorkClaim;
      },
    };
    await assert.rejects(session.claim(port, "offer-1" as never), /no active capability grant/u);
    assert.equal(reachedPort, false);
  });
});

test("snapshots are canonical and authenticated workers cannot be minted with a different runtime token", async () => {
  await withStore("local-authority-snapshot", async (store) => {
    await store.enrollWorker({ principalId: "zeta", authority: "tool", capabilities: ["subprocess"] });
    await store.enrollWorker({ principalId: "alpha", authority: "model", capabilities: ["text_model"] });
    const initial = await store.snapshot();
    assert.deepEqual(initial.principals.map((principal) => principal.principalId), ["alpha", "zeta"]);
    assert.deepEqual(initial, await store.snapshot());

    assert.throws(
      () => new AuthorizedWorker(Symbol("forged") as never, store, "not-a-credential"),
      /may only be minted/u,
    );
  });
});

test("POSIX stores enforce private modes and never follow a state-file symlink", async (context) => {
  if (process.platform === "win32") {
    context.skip("Windows ACL verification is platform-specific");
    return;
  }
  await withStore("local-authority-files", async (store, root) => {
    const directory = await lstat(store.directory);
    const statePath = join(store.directory, "authority.json");
    const state = await lstat(statePath);
    assert.equal(directory.mode & 0o077, 0);
    assert.equal(state.mode & 0o077, 0);

    const target = join(root, "outside.json");
    await rm(statePath);
    await symlink(target, statePath);
    await assert.rejects(
      store.snapshot(),
      (error: unknown) => error instanceof LocalAuthorityError && error.code === "STORE_SYMLINK",
    );

    await chmod(store.directory, 0o700);
  });
});
