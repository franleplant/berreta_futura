# Local authority store

`local-authority.ts` keeps local enrollment identities, credential profiles,
credential hashes, and capability grants below an ignored `.magazine/` path.
The state file has no plaintext credential secret. `createCredentialProfile`
returns a random 256-bit secret exactly once; it persists a salted scrypt hash.

The store is a local-user authority boundary, not a network authentication
service or a defense against a hostile process running as the same operating
system user. On POSIX, initialization enforces a 0700 directory and 0600 state
file, rejects symbolic links for the store directory and state file, and checks
current-user ownership. Windows does not expose an equivalent portable POSIX
mode check through Node, so its protection depends on the directory ACL selected
by the user. Callers should put the store beneath `.magazine/authority`, never
in Git-tracked inputs or durable revisions.

An `AuthorizedWorker` can be minted only with a module-private construction
token and enters RunEngine only through its `claim` method. The authenticated
session is rechecked on each claim, so revoking its principal, credential
profile, or last grant prevents future claims.
