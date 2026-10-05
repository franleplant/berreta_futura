# 05 Pipeline performance

Brief: squeeze waiting time out of every step (writing, art, render, publish,
deploy, push) without turning the code into unmaintainable special cases.
Depends on nothing: it starts from the code at 3ebf70a. The audit below
(2026-10-04, measurement only) replaces yesterday's candidate list; every
candidate is either ranked or dropped with its reason.

## Rules

- Measure before and after each item; keep items independent so they can land
  one by one.
- No caching without an explicit key (source bytes + settings) and a test that
  a changed input invalidates it.
- Reject ideas that add a second code path for the same output.

## How it was measured

- Machine: Apple M4 Pro, 14 cores, 24 GB. Other agents were building in
  parallel: load average 30 to 70 during the build runs, 6 to 12 during the
  runtime runs. Build numbers are therefore pessimistic; runtime numbers are
  clean. Every number is the median of 3 runs unless noted.
- Everything ran in a scratch clone at 3ebf70a with its own target dirs, never
  in the shared worktree.
- Render phases: timestamps inserted into a scratch copy of the crate
  (`util::lap` at phase boundaries), plus `sample` for hot functions.
- Model-bound steps: run against a fake `claude` on PATH and a fake
  `--gen-cmd` (copies a 5 MB PNG) to get the non-model overhead; real model
  and image latencies come from the logs already on disk (`log.jsonl` in run
  and round dirs, `.magazine/capture/log.jsonl`, and 1,121 `codex` image
  sessions under `~/.codex/sessions`). No paid calls were made.
- Three render prototypes were built in scratch to turn estimates into
  measurements (items 1 to 3 below); their outputs were compared with the
  baseline render.

## Baseline

### Dev loop

| Step | Time | Notes |
|------|------|-------|
| `cargo build --release`, cold | 56.6 s | 683 s CPU; critical path is typst-library (31 s), hayagriva/citationberg, wasmi (Typst default features). Yesterday's "3 min" is stale. |
| `cargo build --release`, after touching one file | 10.6 s | release profile has no incremental compilation |
| same with `CARGO_PROFILE_RELEASE_INCREMENTAL=true` | 2.8 s | render and site output byte-identical, render speed unchanged (18.5 s) |
| `cargo build` (dev), cold | 95.6 s | deps at opt-level 3 plus debuginfo |
| `cargo build` (dev), after a real edit | 4.1 s | touch only: 1.6 s |
| `cargo test --no-run`, cold | 52.7 s | |
| `cargo test --no-run`, after a real edit | 4.4 s (light load) to 11 s (loaded) | 25 integration test binaries each link the crate |
| `cargo test` run (built) | 17.4 s | `tests/site.rs` 10.2 s (builds the real site twice with the dev binary), unit tests 2.7 s, `pdf_text` 1.6 s, rest under 1.1 s |
| pre-commit hook, after an edit | 5.4 s | fmt+clippy 2.0 s, ruff 0.05 s, `--test nocomments` 3.3 s |

### Release and publishing steps

| Step | Time | Notes |
|------|------|-------|
| `mag render 012` (release, warm OCR cache) | 18.65 s | 76 pages, en only; reader/booklets/render-critic.json byte-identical across runs |
| `mag render 012`, first render in a fresh clone | 24.7 s | +5.1 s tesseract; cached in `.magazine/legibility` after that |
| `mag render 012 --no-legibility` | 17.2 s | |
| `mag render 012` with the dev binary | 24.4 s | dev rebuild 4 s + 24 s equals release rebuild 10.6 s + 18.6 s today |
| `mag site --out` (3 editions) | 2.22 s | load issues 0.93 s (git, staging, tone decode, serial per edition), image variants 1.20 s, html 0.12 s; output identical with `diff -r` |
| `mag epub 012` | 2.12 s | serial Lanczos resize + JPEG per image; deterministic |
| `mag source-codes 012 --check` | 0.01 s | |
| `mag publish 012 --dry-run` | 0.01 s | hashing 27 MB is free; a real publish is network-bound (plan 04) |
| `npx wrangler@4 --version` | 1.2 s | npx resolution alone, cached package |
| `npx wrangler@4 deploy --dry-run` | 1.6 s | 431 files read; a real deploy uploaded 42 changed files in 1.9 s (plan 04) |
| `git push --dry-run` | 3.5 s | handshake only |

### Render 012 by phase (warm, 18.65 s total)

| Phase | Time |
|-------|------|
| request, staging copy (88 inputs), edition load, tesseract check | 0.06 s |
| tone pass (print copies of dark figures) | 0.14 s |
| legibility (OCR cache hit) / art JPEG copies (picks are already JPEG) | 0.00 s / 0.00 s |
| cover source + compose (x2) | 0.32 s |
| Typst compiles: 5 in total (standfirst 0.21, three runt/flow passes 0.06/0.09/0.07, plated 0.11) | 0.53 s |
| `cover.png` at 300 dpi (typst_render) | 0.36 s |
| reader PDF export | 0.09 s |
| three impositions (lopdf) | 0.04 s |
| critic: pdftoppm rasters at 144 dpi (reader 2.11, booklet 1.82, cover booklet 0.86) | 4.79 s |
| critic: `inspect_leg` x3 (PNG decode + ink stats, serial) | 1.33 s |
| critic: void geometry and row issues | 0.27 s |
| critic: crops: 40 pdftoppm runs at 300 dpi 3.27, emit 41 crops 1.68, opener crop fidelity 0.77 | 5.73 s |
| contact sheets (serial decode, resize, PNG) | 1.27 s |
| preflight / SHA256SUMS / result rows | 0.38 / 0.10 / 0.03 s |
| `package.zip` (deflate of the whole output dir, 219 MB) | 2.94 s |

Key measurement: `pdftoppm -png` spends about 80% of its time in libpng
compression. All 76 reader pages at 144 dpi: 12.9 s as PNG, 2.7 s as PPM (one
process); one page at 300 dpi: 0.36 s as PNG, 0.11 s as PPM.

Disk: one render dir is about 500 MB, and `package.zip` is 219 MB of it. The
shared worktree holds 274 render dirs, 127 GiB.

### Model- and network-bound steps

| Step | Non-model overhead (fake backend) | Real wait (from logs) |
|------|-----------------------------------|------------------------|
| `mag capture --html` | 0.19 s (13 images from localhost), 0.39 s (41 images) | model call median 41 s, p90 163 s (79 calls, 8 retries); images download one at a time with `curl`: 0.64 to 1.37 s each from real CDNs (mean 0.96 s), so 12 s for 13 images, about 40 s for 41 |
| `mag produce` | 0.13 s for 11 articles | writes 20 to 75 s each, all articles in parallel behind `CONCURRENCY = 8`; trims add one serial full-length call (about 31 s) per overshooting piece; front matter about 20 s after all. 012 (11 articles): 104 s wall with 8 slots, 85 s with 11 |
| `mag art` briefs | 0.07 s (`--dry-run`) | the `art-briefs` call: median 158 s, 38 to 449 s; full rounds sit at 300 to 450 s |
| `mag art` generation | 2.3 s for 120 fake candidates on the first round, growing to 5.2 s by the fourth (see item 9) | `tools/imagegen` (a `codex exec` session per candidate): median 125 s, p10 80 s, p90 241 s. 30 briefs x 4 = 120 candidates over 8 workers is 15 waves, about 31 min. Session durations stay flat up to 15 overlapping sessions (median 104 to 141 s) and rise at 16+ (167 s) |
| `mag art --showcase` | 6.2 s with 4 rounds whose names match the 28 picks | `picks::picked_from` decodes the candidate PNG and re-encodes it as JPEG to compare bytes, about 55 ms per name match, serial |
| `mag cast-check` | | 10 to 20 s per candidate call, parallel behind the caller semaphore |
| `mag translate` | | no logged runs; one call per piece, parallel behind the same semaphore |

### Git

`.git` is 4.1 GB: pack 3.12 GiB plus 955 MiB in 3,979 loose objects. HEAD
tracks 3,609 files, 2.5 GiB (editions 005 to 009 hold 1.8 GiB). Edition
commits before 3e2da80 added 440 to 480 MiB of new blobs each (candidate
rounds); no commit since has added more than 12 MiB. Push size is now small
per commit; the remaining cost is history, which is plan 01's job.

## Ranked improvements

Expected render total after items 1 to 3: 18.65 s to 7.7 s, measured on a
scratch prototype (reader.pdf, all three booklets, render-critic.json,
edition-manifest.json byte-identical to the baseline; contact sheets
byte-identical; all 164 review PNGs pixel-identical). Item 7 should take it
to about 6.5 s.

| # | Where | What | Expected gain | Effort | Structure risk | Within boundaries |
|---|-------|------|---------------|--------|----------------|-------------------|
| 1 (done) | `critic/inspect.rs` `rasterize`/`render_pages`; `critic/rules.rs` `render_crop_page` | Ask pdftoppm for PPM (drop `-png`), then encode each page to PNG in-process with `CompressionType::Fast` in parallel (`ordered_map`) and delete the PPM. One small P6 reader (the `image` crate has no pnm feature enabled). | Measured: 18.7 s to 13.2 s (rasters 4.79 to 1.45 s, crop pages 3.27 to 0.99 s). Review PNGs are 16% larger. | S | Low: same rasterizer, same pixels, same file names | Yes |
| 2 (done) | `typeset/release.rs` `publish`, `package/archive.rs` | Stop writing `package.zip`. Nothing in the repo reads it (only `archive_tree`'s own test); it re-deflates already-compressed PDFs and PNGs. Delete `archive.rs` and its test with it. | Measured: 2.9 s per render and 219 MB per render dir (45% of the disk a render takes) | S | Low: one artifact kind and one `result.json` row go away | Yes |
| 3 (done) | `critic/rules.rs` `inspect_leg`, `emit_crops`; `package/contact.rs` `write_contact_sheets` | Run the three per-page loops through the existing `ordered_map`; in `emit_crops` decode each 300 dpi page once instead of once per crop. | Measured with 1+2: inspect 1.33 to 0.22 s, contact sheets 1.27 to 0.43 s, crop emit 1.68 to 1.33 s; total 13.2 s to 11.0 s with the zip, 7.7 s without | S | Low: order kept by `ordered_map` | Yes |
| 4 | `art.rs` `GEN_CONCURRENCY`, `generate_all`, round `log.jsonl` | Raise image generation from 8 to 14 workers (behind a `--jobs` flag defaulting to 14), and log each candidate's seconds and exit status to the round's `log.jsonl` so the next change is measured, not guessed. | 120-candidate round: about 31 min to about 18 min (session durations are flat to 15 overlapping) | S | Low; the provider may throttle, which the new log shows at once | Yes |
| 5 | `capture.rs` `localize_images` | Download images with a bounded pool (8) via `util::parallel`-style workers; keep numbering by first appearance so names stay deterministic. | 13 images: 12 s to about 2 s; 41 images: about 40 s to about 6 s | S | Low | Yes |
| 6 | `mag/Cargo.toml` | `[profile.release] incremental = true` | Release rebuild 10.6 s to 2.8 s; render and site unchanged in speed and bytes (measured) | S | Low: cold builds unaffected | Yes |
| 7 (done) | `critic/rules.rs` `emit_crops`, `opener_crop_fidelity_checks` | Write crops in parallel; let the fidelity check use the page already decoded for the crop instead of decoding again. | About 1.2 s (emit 1.33 s, fidelity 0.77 s) | S | Low | Yes |
| 8 | `site/mod.rs` `run`/`issue`, `site/images.rs` `encode_all` | Load issues in parallel; cache encoded variants under `.magazine/site/` keyed by source sha256 + width + quality + encoder version (the same cache as plan 04 step 3, land it once); switch `encode_all` from static chunks to a work queue. | `mag site` 2.2 s to about 0.5 s warm; grows linearly with editions today | M | Low with the key and an invalidation test | Yes |
| 9 | `art.rs` `collect_showcase_items`, `picks.rs` `picked_from` | Check each pick at most once (newest round first, stop at the first match) and run the checks in parallel. | About 1.5 s per round or `--showcase` with one matching round; 6 s observed with re-rolled names | S | Low | Yes |
| 10 | `caller.rs` `CONCURRENCY` | 8 to 16. Only issues with more than 8 articles gain. | 012: 104 s to 85 s | S | Low; same throttling caveat as item 4 | Yes |
| 11 | `site/epub.rs` `images` | Encode EPUB images in parallel (`util::parallel`). | 2.1 s to about 0.5 s | S | Low | Yes |

### Done: items 1, 2, 3, 7 (2026-10-04)

`mag render 012 --run editions/012/run-2026-10-01T14-52-53`, release build, warm, load average about 20, median of 3 after one warm-up: 18.62 s before (HEAD 5b69845), 6.05 s after (runs 6.94, 6.01, 6.05). The render dir drops from 442 MB to 241 MB. reader.pdf, the three booklets, render-critic.json and edition-manifest.json are byte-identical; preflight.json is identical modulo the render dir; all 165 PNGs under the render dir decode to identical pixels; the file list and `result.json` lose only `package.zip`. No per-phase timings were taken for the new code. Notes: the 144 dpi review pages and the 300 dpi crop pages are PPMs read by `read_ppm` (`critic/metrics.rs`); contact sheets and crops keep the default PNG compression (item 1 scope is the review pages); `inspect_opener_crop_fidelity` now takes the decoded reference page.

### How to verify each item

- Items 1, 3, 7 (critic): `mag render 012 --run editions/012/run-2026-10-01T14-52-53`
  before and after; `cmp` reader.pdf, booklet-a4*.pdf, render-critic.json,
  edition-manifest.json; compare `preflight.json` with the `render-<stamp>`
  path removed (it embeds the render dir, so it and SHA256SUMS differ on every
  run, including two baseline runs); decode every PNG under `render-review/`
  and require identical pixels (bytes may differ for item 1). Timings: 3 runs.
- Item 2: the file list of `en/` equals the baseline minus `package.zip`;
  everything else as above.
- Items 4, 9: fake `--gen-cmd` round (as in this audit) produces the same
  `round.yaml`, proof sheet and showcase as before; item 4's first real round
  reports per-candidate seconds; compare its median with the 125 s baseline.
- Item 5: capture the same saved page against a local image server serially
  and in parallel; `article.md`, `record.yaml` and `media/` byte-identical.
- Item 6: render 012 and `mag site` with both profiles; byte-identical
  outputs (done once in this audit), rebuild timings 3 runs.
- Item 8: `diff -r` of two site builds, cold cache and warm cache, identical;
  a test that changing a source image or the encoder settings re-encodes it.
- Items 10, 11: same outputs with the fake backend; EPUB byte-identical.

## Later (crosses module boundaries)

- Keep the critic's rasters decoded in memory from rasterization through
  inspection, void geometry, contact sheets and fidelity, instead of
  re-reading PNGs in each stage: about 1 s more, but it changes the critic's
  data flow between functions.
- Rasterize the reader pages in-process with `typst_render` from the
  `PagedDocument` already in memory: no pdftoppm process for the reader and
  crops. Pixels change, so critic numbers change: needs a reviewed baseline
  update. Booklets would still need a PDF rasterizer.
- One image cache shared by render (tone copies), site and EPUB, keyed by
  source bytes and settings.
- A render-dir retention rule (for example keep the newest N per edition):
  127 GiB of render dirs is disk, not time, but it is the largest cost this
  audit found.

## Dropped (with the reason)

- Reuse the first Typst compile / cheaper standfirst pre-pass: stale. Render
  runs 5 compiles totalling 0.53 s of 18.65 s.
- Cache staged art JPEGs across renders: stale. Picks are committed JPEGs
  since 3e2da80; the JPEG step measures 0.000 s.
- OCR legibility: already cached by image sha256; only a fresh checkout pays
  (5.1 s once).
- Opt-in flags for review PNGs, booklets, package: rejected. Two render modes
  are two code paths for the critic; after items 1 to 3 the critic costs about
  5 s and the booklets 0.04 s. Item 2 removes the package outright.
- Parallel language renders: only editions up to 004 have translations.
- Produce cache by prompt hash: `--resume` already skips finished pieces; a
  second skip mechanism is not worth it.
- Fewer candidates per brief: an editorial choice, not a speed fix; item 4
  gets most of the time back without it.
- Thin LTO, faster linker: rebuild time is codegen, not linking (dev rebuild
  1.6 to 4 s), and LTO slows release builds for no measured runtime gain
  (render is pdftoppm- and PNG-bound).
- Trimming Typst default features (bibliography, plugins) to speed cold
  builds: not exposed as features in typst 0.15; cold builds are rare once
  the shared target dir is used (plan 04).
- Consolidating the 25 integration test binaries: the post-edit test build is
  4 to 11 s depending on load; `tests/site.rs` (10 s of the 17 s run) shrinks
  with item 8 instead.
- Publish skip of unchanged uploads, pinned wrangler, one release command:
  owned by plan 04; measured here (dry-run 0.01 s, npx 1.2 s, deploy dry-run
  1.6 s) and nothing to add.
- Push size: owned by plan 01; commits since 3e2da80 are small.

## Side findings (not performance)

- `mag site` copies `editions/NNN/epub/*.epub` from the working tree
  (`tracked_epubs`) without the dirty check `require_committed` applies to the
  other inputs, so a locally modified EPUB ships.
- `preflight.json` embeds the timestamped render path, which makes
  SHA256SUMS differ between identical renders.
