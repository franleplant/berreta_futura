# 04 Faster deploys

## What actually happens today (observed)

A release is: `cargo build --release` (about 3 min cold in a fresh worktree,
~11 s incremental), `mag site` (about 2.5 s), `npx wrangler@4 deploy`.
Wrangler already hashes every file and uploads only new ones: the deploy on
2026-10-03 uploaded 42 of 392 files ("350 already uploaded") in 1.9 s; the very
first deploy uploaded 156 files in 28.6 s. So "re-uploading everything" is not
what wrangler does; the slow parts are around it:

1. Fresh worktree builds start cold (3 min).
2. `npx wrangler@4` resolves/installs the CLI on every run.
3. Any change to an image encoder or site CSS changes content-hashed names of
   many files, which then all upload once.
4. The PDF/EPUB upload (rclone to Drive today; GitHub Releases after plan 02)
   re-uploads the full file on every publish, even if unchanged.
5. git push of new issue art (fixed going forward by 3e2da80 and plan 01).

## Steps

1. One command for a release: `tools/release.sh NNN` (or `mag release NNN`):
   build release with the shared target dir of the main checkout (no cold
   worktree builds), `mag site`, `wrangler deploy`, print what was uploaded and
   the live URL. Uses a pinned local wrangler (`deploy/web/package.json` with
   wrangler in devDependencies and a lockfile) instead of `npx wrangler@4`.
2. `mag publish` skips the upload when the remote asset's sha256 (publish.yaml)
   equals the local file, and says so.
3. `mag site` caches image variants by source hash under `.magazine/site/`
   (skip re-encoding unchanged images; output stays byte-identical).
4. Keep content-hashed names stable: hash the source bytes and the encoder
   settings, not incidental metadata; add a test that two builds of an
   unchanged edition produce identical file names (one exists for bytes).
5. Report: deploy prints "N changed files, X MB" before uploading.

## Verification

Time each step before/after on: (a) no-op redeploy, (b) one article text fix,
(c) one new issue. Target: no-op release under 20 s end to end on a warm
checkout, text fix under 30 s, no re-upload of unchanged PDFs.
Numbers from the performance audit (plan 05) replace the observed ones above
when it lands.
