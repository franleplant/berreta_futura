# Public web site

Releases run from the owner's laptop, never from CI. `mag site` builds
`output/site` from committed state (`edition.yaml`, the newest git-tracked
run, library media) and `wrangler deploy` uploads it to
https://berreta.franleplant.com as Cloudflare Workers static assets. PDF links
come from `editions/NNN/publish.yaml`.

`wrangler.jsonc` is assets-only: no Worker script, no `workers.dev` URL, the
custom domain attached by `routes`, and unknown paths answered by the nearest
`404.html` with status 404. Cloudflare caps each asset at 25 MiB and a version
at 20,000 files on the free plan.

## Release

```sh
mag/target/release/mag publish 011 --pdf editions/011/render-.../en/reader.pdf
mag/target/release/mag site --out output/site
npx wrangler@4 deploy --config deploy/web/wrangler.jsonc
git add editions/011/publish.yaml && git commit && git push
```

## PDFs on Google Drive

PDFs exceed the 25 MiB asset limit, so they live in Google Drive under
`[site] pdf_remote` (`gdrive:berreta-futura`), shared as anyone with the link.

`mag publish` refuses a file without a `%PDF-` header, uploads it unchanged
with `rclone copyto` as `011/en/berreta-futura-011-en-<first 8 hex of
sha256>.pdf` (new content gets a new file and link), shares it with
`rclone link`, and merges the language into `publish.yaml`. `--dry-run`
prints the rclone commands without running them.

One-time setup on this laptop:

1. `npx wrangler login` (deploys).
2. rclone on PATH (official binary from https://rclone.org/downloads/; Homebrew
   has no bottle for it), then `rclone config create gdrive drive
   scope=drive.file` and approve in the browser.
