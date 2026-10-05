# Public web site

Releases run from the owner's laptop, never from CI. `mag site` builds
`output/site` from committed state (`edition.yaml`, the newest git-tracked
run, library media) and `wrangler deploy` uploads it to
https://berreta.franleplant.com as Cloudflare Workers static assets. PDF and EPUB
links come from `editions/NNN/publish.yaml`.

`wrangler.jsonc` is assets-only: no Worker script, no `workers.dev` URL, the
custom domain attached by `routes`, and unknown paths answered by the nearest
`404.html` with status 404. Cloudflare caps each asset at 25 MiB and a version
at 20,000 files on the free plan.

## Release

```sh
mag/target/release/mag publish 011 --pdf editions/011/render-.../en/reader.pdf --epub editions/011/epub/berreta-futura-011-en.epub
mag/target/release/mag site --out output/site
npx wrangler@4 deploy --config deploy/web/wrangler.jsonc
git add editions/011/publish.yaml && git commit && git push
```

## Downloads on GitHub Releases

PDFs exceed the 25 MiB asset limit, so each issue's downloads are assets of a
GitHub Release in `[site] repo`: tag `issue-NNN`, assets
`berreta-futura-NNN-<lang>.pdf` and `.epub`. `mag publish` refuses a file
without a `%PDF-` header (or an EPUB that is not a zip), creates the release
when missing, and uploads with `gh release upload --clobber`, so only the
latest file exists. An asset whose sha256 already matches the release's digest
is skipped. It writes the stable download URL, bytes, and sha256 into
`publish.yaml` (`<lang>: {pdf: {...}, epub: {...}}`); the site links each with
`?v=<first 8 hex of sha256>` so a replaced file is not served stale.
`--dry-run` prints what would be uploaded and calls nothing.

One-time setup on this laptop: `npx wrangler login` (deploys) and `gh auth
login` (uploads).
