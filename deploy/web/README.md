# deploy/web

Scaffold for serving assembled web editions from Cloudflare, designed in
docs/WEB_DEPLOY.md. The order below matters: a Worker with `workers_dev`
enabled is public — live, unauthenticated, and on a guessable subdomain —
the moment `wrangler deploy` returns. `wrangler.jsonc` therefore ships with
`"workers_dev": false`, so the first deploy has no URL at all until the
Access policy exists.

## 1. Access, before the Worker has any URL

The content is private (docs/EDITORIAL_POLICY.md). Put Cloudflare Access in
front first:

1. Zero Trust dashboard → Access → Applications → Add an application →
   Self-hosted.
2. Application domain: the Worker's `workers.dev` URL (and any custom domain
   you later attach). Cover the whole zone path (`/*`).
3. Policy: Allow, with an include rule listing the specific reader emails —
   default deny for everyone else. Keep the session length short.
4. Only after the policy is active: set `"workers_dev": true` (or attach a
   custom domain the policy covers), run `wrangler deploy` again, and confirm
   an incognito request is challenged before sharing the URL.

The exact way Access attaches to a `workers.dev` URL has shifted over time
(a dashboard toggle on the Worker versus a self-hosted Zero Trust
application) — verify this recipe against current Cloudflare docs before
relying on it.

Removing Access is an editorial/rights decision recorded against the sources
(public reprint clearance), never a convenience.

## 2. Assemble and deploy

```sh
uv run python deploy/web/assemble.py            # released editions → deploy/web/dist
uv run python deploy/web/assemble.py --allow 003-unreleased   # include a preview
cd deploy/web && npx wrangler deploy            # requires a Cloudflare account login
```

`dist/` is generated scratch, like `output/`: never commit it.

## Files

- `assemble.py` — gathers `output/*/web/*` for ledger-released editions (plus
  explicit `--allow` previews) into `dist/`, and writes `dist/editions.json`.
  Previews never become `latest`: with no released edition assembled the
  manifest's `latest` is null and the Worker answers `/` with 404, so a
  preview is reachable only by its explicit URL. The destination must be
  absent, empty, or a previous assembly output; anything else is refused.
- `worker.js` — root redirect to the latest released edition, `/editions`
  index, language-less edition redirects, and cache headers (immutable for
  released editions, `no-store` for previews and the manifest). Runs on every
  request (`run_worker_first`), otherwise asset responses would bypass it and
  the headers would never attach.
- `wrangler.jsonc` — Worker + Static Assets configuration; `dist/` is the
  asset directory.
