# 02 Hosting the PDF and EPUB downloads: GitHub Releases

## Question

Now that the repo and the PDFs are smaller, can the downloads live in GitHub
and be linked from the site?

## Decision (owner, 2026-10-04)

GitHub Releases (option B). One release per issue, tag `issue-NNN`; assets
`berreta-futura-NNN-<lang>.pdf` and `.epub`, replaced in place with
`gh release upload --clobber` so only the latest exists. `mag publish` uploads
there and skips identical files (sha256); publish.yaml records per language
`pdf` and `epub` as `{url, bytes, sha256}`; the site links them with
`?v=<sha8>`. Drive/rclone and `pdf_remote` are removed; EPUBs leave git
(gitignored, published as assets). Migrate 010-012 with the exact files
published today (sha256 checked before and after upload).

## Requirement

Only the latest PDF/EPUB per issue and language matters; earlier versions
must not accumulate anywhere. In git every committed version stays in history,
so any option that commits the files to `main` fails this unless history is
rewritten on every publish. Prefer storage that is overwritten in place.

## Today

- PDFs: Google Drive via rclone (`mag publish`), linked from publish.yaml.
  rclone warns that its shared Google client id is being retired in 2026;
  readers land on Drive's viewer page.
- EPUBs: committed into the repo (editions/012/epub, 11.8 MB).
- Sizes now: issue PDFs 23-33 MB, EPUB ~12 MB.

## Options to explore

| Option | For | Against | To check |
|--------|-----|---------|----------|
| A. Commit PDFs/EPUBs in the repo, link raw GitHub URLs | Simplest, everything in one place | Fails the latest-only requirement: every re-render adds 25-35 MB to history forever (works against plan 01); GitHub warns at 50 MB, rejects >100 MB per file; raw URLs serve with a generic content type | Download headers and speed of raw.githubusercontent.com for a 33 MB file; growth per year at current cadence |
| B. GitHub Releases, one release per issue | Files up to 2 GB outside git history, stable direct links, `gh` already logged in | A second place to keep in sync with publish.yaml; downloads show github.com | Content type, redirects, caching when an asset is replaced |
| C. Git LFS | Files "in the repo" without bloating normal history | Free quota 1 GB storage / 1 GB bandwidth per month: a few hundred downloads exhaust it | Quota math for expected readers |
| D. Serve from the site (Cloudflare static assets) | Same domain, fast | 25 MiB per-file limit: 012's PDF (33 MB) does not fit unless split or compressed further | Whether PDFs can stay under 25 MiB without quality loss |
| F. Orphan `downloads` branch, one commit amended and force-pushed per publish | Lives in the GitHub repo, keeps only the latest | Force-push on every publish; old blobs linger until GitHub GCs them; clones must avoid fetching it (`--single-branch`) | Raw URL behaviour, how fast old blobs disappear |
| E. Keep Drive | Works today | Client-id retirement, viewer page | Effort to own a Google client id |

## Steps

Implementation (when this plan is executed):
1. `mag publish` switches to `gh release create/upload --clobber`, with the skip-if-unchanged check and the new publish.yaml shape.
2. Remove rclone/Drive code, config and docs; untrack and gitignore editions/*/epub/*.epub.
3. Migrate 010-012, rebuild and deploy the site, verify every link with `curl -sIL` and a sha256 of the download.

Exploration notes (kept for the record):
1. For each option, measure on issue 012: upload time, download URL behaviour
   (`curl -sIL`: status, content-type, content-length), time to first byte from
   two locations, and what a re-publish of the same file costs.
2. Estimate repo growth for A and C over a year of issues.
3. Write the findings and a recommendation here; owner picks; implementation
   becomes its own plan.

