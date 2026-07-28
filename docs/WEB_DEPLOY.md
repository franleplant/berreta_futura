# Web deployment — Cloudflare

The web edition (`mag web`, see README) is a private screen profile. This
document is the design for serving assembled web editions from Cloudflare
behind authentication. Nothing here changes the compiler; deployment consumes
`output/` artifacts and the release ledger, exactly like the packaging step it
resembles.

## Privacy is the constraint, not a feature

Captured sources lack a public redistribution basis (docs/EDITORIAL_POLICY.md;
`distribution = "private"` in magazine.toml). Every deployment target in this
design therefore sits behind Cloudflare Access with a default-deny policy.
Removing Access is an editorial and rights decision — public reprint clearance
recorded per source — not a configuration toggle, and no scaffold in this
repository will ever flip it.

## Architecture: one Worker with Static Assets

Cloudflare offers two ways to serve a static tree: Pages, and Workers with
Static Assets. This design uses **Workers with Static Assets**:

- Cloudflare's own guidance steers new projects to Workers; Pages is in
  maintenance while Workers receives the platform investment.
- One `wrangler.jsonc` holds the router and the asset tree; the root redirect
  and the editions index need a few lines of code, which Pages would push into
  `_redirects`/Functions anyway.
- Access policies attach to either the same way, so privacy costs nothing in
  the choice.

Verify against current Cloudflare docs before the first deploy — the offering
moves: developers.cloudflare.com/workers/static-assets/.

## URL structure

```text
/                                  302 → /<latest released edition>/<primary language>/; 404 when no released edition is deployed
/editions                          index of every deployed edition, per language
/<edition-id>/<language>/          the edition's web directory, served as-is
/<edition-id>/<language>/*.html    cover, per-article pages, whole-edition page
/editions.json                     build-time manifest the Worker reads
```

`latest` and the edition list come from `editions.json`, written at assembly
time from the release ledger — the Worker never guesses and never lists a
directory. An edition-id path without a language redirects to the publication's
primary language. Only a released edition can be `latest`; a previews-only
deploy carries `latest: null` and the root answers 404, so previews are
reachable only by their explicit URL.

## Assembly: `deploy/web/assemble.py`

`mag web` writes per-edition, per-language trees under `output/<id>/web/`.
Assembly gathers them into one deployable tree:

```sh
uv run python deploy/web/assemble.py                # released editions only
uv run python deploy/web/assemble.py --allow 003-unreleased   # + preview
# Access policy FIRST — see deploy/web/README.md. A workers.dev deployment
# is public the instant the next command returns; wrangler.jsonc ships with
# workers_dev disabled so the first deploy has no URL until Access exists.
wrangler deploy                                     # run from deploy/web/, by a human
```

"Released" means exactly the `released_editions` entries of
`library/release-state.yaml`, read through `magazine.release.load_release_state`
— the same authoritative reader the compiler uses, never a re-parse. A released
edition whose web output has not been generated is reported and skipped, since
editions released before this profile existed have none. `--allow` admits a
named unreleased edition for preview; it is marked `"released": false` in the
manifest so the Worker can refuse to cache it as immutable. The assembled tree
is deterministic: same inputs, same bytes, no timestamps.

## Caching

Asset names inside an edition are deterministic but not content-hashed, so
immutability is a policy fact, not a filename fact: released editions are
immutable artifacts (docs/ARCHITECTURE.md invariants), so the Worker serves
`/<released-id>/...` with `Cache-Control: public, max-age=31536000, immutable`.
Previewed unreleased editions are served `no-store` — they change on every
rebuild. `editions.json` is `no-store` so a new deploy is visible immediately.

These headers exist only because `run_worker_first` routes asset requests
through the Worker; without it the asset layer answers matching paths itself
and the header code never runs. The cost is a manifest lookup per request,
paid once per isolate — the Worker caches `editions.json` in module scope,
and a deploy replaces isolates, so the cache never outlives its deploy.

## Deliberately out of scope

Analytics, search, comments, per-article feeds, and any write path. The
deployment is a reading surface over sealed artifacts; anything interactive
would be a new editorial decision first and a design second.
