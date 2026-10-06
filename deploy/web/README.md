# Public web site

The built site is committed at `site/`, and Cloudflare Workers Builds deploys it
on every push to `main` that changes `site/**`. `mag site` builds `site/` from
committed state (`edition.yaml`, the newest git-tracked run, library media).
Nothing builds in CI: the build command is empty and the deploy command only
uploads the committed files as Cloudflare Workers static assets at
https://berreta.franleplant.com. PDF and EPUB links come from
`editions/NNN/publish.yaml`. `mag site --check` rebuilds into a temp dir and
fails, listing differing paths, when `site/` is stale; `cargo test` runs the
same comparison.

`wrangler.jsonc` is assets-only: no Worker script, no `workers.dev` URL, the
custom domain attached by `routes`, and unknown paths answered by the nearest
`404.html` with status 404. Cloudflare caps each asset at 25 MiB and a version
at 20,000 files on the free plan; both still apply to `site/`. `assets.directory`
is resolved relative to the config file, so `../../site` is the repo's `site/`.

## Release

```sh
mag/target/release/mag publish 011 --pdf editions/011/render-.../en/reader.pdf --epub editions/011/epub/berreta-futura-011-en.epub
mag/target/release/mag site
git add site editions/011/publish.yaml && git commit && git push
uv run tools/deploy.py
```

`tools/deploy.py` waits for the Workers Build of the pushed commit and fails
if it fails. GitHub push events are occasionally dropped (2026-10-06: the push
of 97d4cce9 never produced a build); when no build appears within three
minutes it deploys `site/` with wrangler from the laptop instead.

Run `publish` only when there is a new PDF or EPUB. The push to `main` triggers
Workers Builds, which deploys when `site/**` changed. Fallback from the laptop:
`npx wrangler@4 deploy --config deploy/web/wrangler.jsonc`.

## One-time Cloudflare setup

Cloudflare dashboard > Workers & Pages > `berreta-futura-web` > Settings >
Builds > Connect (Git repository):

1. Authorize the GitHub app and pick repository `franleplant/berreta_futura`.
2. Production branch: `main`.
3. Root directory: `/`.
4. Build command: leave empty.
5. Deploy command: `npx wrangler deploy --config deploy/web/wrangler.jsonc`.
6. Build watch paths: Include paths `site/*`, Exclude paths empty.
7. Save, then push a change under `site/` and watch the build in the Builds tab.

Non-production branch builds: there is no wrangler config at the repo root, so
the default preview command fails without `--config`. Set the non-production
deploy command to `npx wrangler versions upload --config deploy/web/wrangler.jsonc`
(it does not touch production), or disable non-production branch builds.

## Downloads on GitHub Releases

PDFs can exceed the 25 MiB asset limit, so each issue's downloads are assets of a
GitHub Release in `[site] repo`: tag `issue-NNN`, assets
`berreta-futura-NNN-<lang>.pdf` and `.epub`. `mag publish` refuses a file
without a `%PDF-` header (or an EPUB that is not a zip), creates the release
when missing, and uploads with `gh release upload --clobber`, so only the
latest file exists. An asset whose sha256 already matches the release's digest
is skipped. It writes the stable download URL, bytes, and sha256 into
`publish.yaml` (`<lang>: {pdf: {...}, epub: {...}}`); the site links each with
`?v=<first 8 hex of sha256>` so a replaced file is not served stale.
`--dry-run` prints what would be uploaded and calls nothing.

One-time setup on this laptop: `gh auth login` (uploads) and, for the deploy
fallback, `npx wrangler login`.
