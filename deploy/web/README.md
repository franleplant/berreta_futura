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

## PDFs on R2

PDFs exceed the 25 MiB asset limit, so they live in the R2 bucket
`berreta-pdfs`, served at https://files.berreta.franleplant.com.

`mag publish` refuses a file without a `%PDF-` header, names the object
`011/en/berreta-futura-011-en-<first 8 hex of sha256>.pdf` (new content gets
a new URL, so a re-publish never serves a cached old copy), and merges the
language into `publish.yaml`. `--dry-run` prints the upload command without
running it. Wrangler uploads at most 315 MB per object
([Upload objects](https://developers.cloudflare.com/r2/objects/upload-objects/)).

One-time setup on this laptop:

1. `npx wrangler login` (opens the browser; deploy and publish use it).
2. Dashboard, **R2 object storage**, enable R2.
3. `npx wrangler r2 bucket create berreta-pdfs`
   ([Wrangler commands](https://developers.cloudflare.com/r2/reference/wrangler-commands/)).
4. Dashboard, **R2 object storage**, the bucket, **Settings**, under
   **Custom Domains** select **Add**, enter `files.berreta.franleplant.com`,
   **Continue**, **Connect Domain**
   ([Public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/)).
   Leave the `r2.dev` development URL disabled.
