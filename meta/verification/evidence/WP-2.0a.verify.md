# WP-2.0a verification

Verdict: **ACCEPTED**, with two non-blocking findings recorded below.

Verifier acceptance per protocol rule 3, critique duty folded in. Plan revision
14 (`b8bd499`).

## Subject

WP commit `fb693d9`, 8 files: `mag/src/main.rs`, `mag/src/render.rs`,
`mag/src/typeset/mod.rs`, `magazine.toml`, `mag/Cargo.toml`, `mag/Cargo.lock`,
`meta/verification/parity.yaml`, `meta/verification/evidence/WP-2.0a.md`.

## Owns check

Clean. All 8 paths are within the WP's Owns list. No `*.verify.md`, no
`baseline.json`, no comparator code, no `mag/src/model/**`. The `parity.yaml`
change is confined to the nested `tools.typst_crates` record; no top-level key
was added or removed.

## Engine resolution: all six cases reproduced

Run against the built binary in a fresh worktree at `fb693d9`.

| # | `[render] engine` | `--engine` | observed | exit |
|---|---|---|---|---|
| 1 | weasyprint | typst | typst stub, loud | 1 |
| 2 | weasyprint | reportlab | `unknown render engine 'reportlab' from --engine` | 1 |
| 3 | bogus | absent | `unknown render engine 'bogus' from magazine.toml [render] engine` | 1 |
| 4 | typst | absent | typst stub, loud | 1 |
| 5 | bogus | weasyprint | past selection, fails at the edition lookup | 1 |
| 6 | key absent | absent | past selection, fails at the edition lookup | 1 |

Case 4 is the load-bearing one and it holds: with no flag at all, the toml value
alone reaches the typst stub, so the key decides rather than merely being read.
Case 3 proves the value is validated, and cases 1 and 5 prove the flag overrides
in both directions.

Reading the code confirms the ordering behind cases 5 and 6: `select_engine` is
called before `load_edition`, so a bad engine value fails ahead of the edition
lookup, while the `match engine` dispatch sits at the end of `run`.

## Unchanged weasyprint output: reproduced independently

I built the parent commit `17eb66b` in a second worktree and rendered edition
010 from both binaries with `--no-model` against the same run directory, rather
than accepting the evidence's comparison.

| artifact | observed |
|---|---|
| reader, booklet-a4, booklet-a4-cover, booklet-a4-interior | `pdftotext -raw` identical, all four |
| `en/web/` | byte-identical, whole tree (`diff -r`) |
| `en/edition-manifest.json` | byte-equal |
| `request.json` `renderer` | `weasyprint` on both sides |

### The 48 request.json leaves

The evidence claims all 48 are the worktree's own absolute path rather than a
substantive difference. Confirmed exactly, by leaf-wise comparison of the two
`request.json` files:

- 150 leaves total, 48 differing
- differing leaf names: `artifactRoot` x1, `inputs[*].sourcePath` x47
- leaves NOT explained by the worktree path: **0**
- leaves collapsing under substitution of one worktree path for the other:
  **48 of 48**, remainder empty

So the characterisation is accurate and the difference is an artifact of
comparing two checkouts, which is what a before/after across a commit requires.

## Crate pins

- `mag/Cargo.toml` declares exactly five direct typst dependencies, each pinned
  `=0.15.1`: typst, typst-layout, typst-library, typst-pdf, typst-syntax
- every typst-family crate resolved in `Cargo.lock` is at 0.15.1 (a single
  distinct version line across the family)
- lock package count 203 to 397, as claimed
- `parity.yaml tools.typst_crates` records the five pins, attributes the proof
  to WP-1.4, and notes the MSRV and the not-optional status of typst-layout and
  typst-syntax

## The three judgment calls

**1. `Cmd::Render` fields moved into `render::RenderArgs`: right, evidence
slightly imprecise.** `mag render --help` shows every pre-existing argument
retaining its exact long name, default and arity, with help text unchanged
verbatim: `--operation` (default `render_edition`), `--article`, `--langs`,
`--run`, `--anchor-model` (default `haiku`), `--no-model`, and the positional
`<EDITION>`. `--engine` is the only addition. The refactor is therefore
behaviour-preserving at the CLI.

One imprecision, recorded rather than held against the WP: the subcommand's own
about line also changed, from "Render an edition via the Python renderer seam
(mag-render-adapter)" to "Render an edition: weasyprint via the Python seam,
typst natively". That is an accurate and necessary correction, since the old
text would now be false, but the evidence's "`--help` is unchanged but for the
new `--engine` line" overstates it by one line.

Separately, `publication_name` was generalised into `toml_value`. I read both:
the fallback behaviour is preserved (unreadable file, absent key, or empty value
all yield `Magazine`), and key matching cannot be confused by a longer key
sharing the prefix, because the `=` check fails. The render comparison above
exercises it, since `publicationName` rides in `request.json`.

**2. `reportlab` no longer selectable: right, and it was already unreachable.**
Confirmed by tracing the dispatch rather than accepting the claim.
`engine_render_bridge.py:305` calls `reader_renderer(request["renderer"], ...)`,
so `request["renderer"]` is the only input to `render_engine.py`'s `_ENGINES`
table. The pre-change Rust set that field from `const RENDERER: &str =
"weasyprint"` (`render.rs:13`, used at `:565`), and nothing on either side read
`magazine.toml [render] engine` to feed it. So reportlab could not be selected
through `mag render` before this WP either.

Nothing in the plan depends on it being selectable: its references are the
reportlab `render.py` as a consumer of `image_contrast.py`, WP-5.4's use of the
reportlab *library* for cover placement (a different thing), a historical
analogy in WP-4.2, the Non-goals entry, and Appendix A's deletion row. Worth
noting the direction of travel: WP-4.2 requires weasyprint to stay selectable as
the rollback, and this WP is what makes any engine genuinely selectable for the
first time.

**3. The typst stub fails loud: right. It writes one empty directory.** The
failure is an `anyhow::bail!` naming what is unimplemented, where it lands
(WP-2.2a), the plan file, and the workaround; exit code 1; it cannot be mistaken
for a successful no-op.

Finding, non-blocking: because the `match engine` dispatch sits at the end of
`run`, a `--engine typst` invocation stages inputs and creates its timestamped
render directory before bailing. I checked what it leaves: the directory is
**empty**, 0 files, no manifest and no PDFs, and neither `mag/src/` nor
`src/magazine/` globs `render-*`, so nothing downstream can pick it up or
mistake it for a render. The worker's reasoning for dispatching late (that is
where the real engine will consume staged inputs) is sound and WP-2.2a will
write into exactly that directory. Recorded so WP-2.2a knows the directory
already exists by the time it runs, and so repeated stub invocations
accumulating empty directories is a known, harmless effect rather than a
surprise.

## Rule 9 check (revision 12)

Passes. The evidence's `## Metrics` explicitly records 56 pages, nine articles
and 363 manifest leaves as observations of edition 010 as it stands today and
states that no verify clause tests them. I confirmed the clauses are structural:
every one compares two legs of the same input (byte-equal, identical, N of N),
and none uses a corpus figure as a threshold.

## Coupling check

`mag/src/parity.rs` shells only the pinned poppler tools and does not invoke
`mag render`, so the CLI refactor breaks no existing comparator coupling.
Rendering both legs is WP-2.0b's work and will consume the new `--engine` flag.

## Baseline

In a clean worktree at `fb693d9`: `cargo test` green (including
`no_comments_in_codebase` and the `parity_faults` seeded-fault suite),
`cargo fmt --check` exit 0, `cargo clippy --all-targets -- -D warnings` exit 0.

## Commands

    git worktree add <wt> fb693d9
    cd <wt>/mag && cargo build && cargo test && cargo fmt --check \
      && cargo clippy --all-targets -- -D warnings
    cp -R <repo>/editions/010/run-2026-09-13T01-34-51 <wt>/editions/010/
    # six resolution cases, editing magazine.toml between them
    mag render 010 --engine typst --no-model --run editions/010/run-2026-09-13T01-34-51
    mag render 010 --engine reportlab
    mag render 999
    sed -i '' 's/^engine = "weasyprint"/engine = "bogus"/' magazine.toml && mag render 010
    mag render 999 --engine weasyprint
    sed -i '' 's/^engine = "bogus"/engine = "typst"/' magazine.toml \
      && mag render 010 --no-model --run editions/010/run-2026-09-13T01-34-51
    # unchanged-output leg
    git worktree add <wt-pre> 17eb66b && cd <wt-pre>/mag && cargo build
    # render 010 from both binaries, then compare
    pdftotext -raw <dir>/en/<name>.pdf ; diff -r <pre>/en/web <post>/en/web
    cmp <pre>/en/edition-manifest.json <post>/en/edition-manifest.json
    # 48-leaf characterisation: flatten both request.json to leaves, diff,
    # then substitute the pre worktree path for the post one and re-compare

## Status

`accepted`
