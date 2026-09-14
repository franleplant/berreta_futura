# WP-2.0a engine dispatch

## Base

`5d9d154` (feat(critic): WP-5.3a raster metrics port), plan revision 13.

The before/after render comparison below was taken at `2f498a0`, the commit
this work was originally branched from, with BOTH legs at that commit; the
branch was then rebased onto `5d9d154` when the Cargo lane freed. Nothing
between those commits touches the render path (they are the WP-5.1b/5.1c model
ports, WP-5.3a's critic metrics, and plan revisions), and the comparison's
claim is that this WP's diff leaves weasyprint output unchanged, which a
same-commit pair is what establishes.

## Commands

All commands run from a worktree at `## Base` with the untracked run directory
copied in:

    git worktree add $TMP/wp20a 2f498a0
    git worktree add $TMP/wp20a-base 2f498a0
    for d in wp20a wp20a-base; do
      cp -R /Users/franguijarro/code/magazine/editions/010/run-2026-09-13T01-34-51 \
            $TMP/$d/editions/010/
    done

`mag` builds from `mag/Cargo.toml` but `render` resolves the repo root from the
process working directory, so the binary is built with `--manifest-path` and
invoked from the worktree root:

    cd $TMP/wp20a && cargo build --manifest-path mag/Cargo.toml --quiet

### Lints and tests

    cd $TMP/wp20a/mag && cargo fmt && cargo clippy --all-targets -- -D warnings && cargo test

### Engine resolution, six cases

`M=./mag/target/debug/mag`, `RUN=--run editions/010/run-2026-09-13T01-34-51`.
Note for replay: in zsh an unquoted variable holding several flags does NOT
word-split, so the flags are written out in full below.

    # 1 toml=weasyprint, flag forces typst
    $M render 010 --no-model $RUN --engine typst
    # 2 unknown flag value
    $M render 010 --no-model $RUN --engine reportlab
    # 3 unknown toml value, no flag
    sed -i '' 's/^engine = "weasyprint"/engine = "bogus"/' magazine.toml
    $M render 010 --no-model $RUN
    # 4 toml=typst, no flag
    sed -i '' 's/^engine = "bogus"/engine = "typst"/' magazine.toml
    $M render 010 --no-model $RUN
    # 5 bad toml overridden by flag: reaches the edition lookup, so past selection
    sed -i '' 's/^engine = "typst"/engine = "bogus"/' magazine.toml
    $M render 999zzz --engine weasyprint
    # 6 key absent, no flag: same, so the default is weasyprint
    sed -i '' 's/^engine = "bogus"/#gone/' magazine.toml
    $M render 999zzz
    sed -i '' 's/^#gone/engine = "weasyprint"/' magazine.toml

### Unchanged weasyprint output, before vs after

    cd $TMP/wp20a-base && cargo build --manifest-path mag/Cargo.toml --quiet \
      && ./mag/target/debug/mag render 010 --no-model --run editions/010/run-2026-09-13T01-34-51
    cd $TMP/wp20a && ./mag/target/debug/mag render 010 --no-model --run editions/010/run-2026-09-13T01-34-51

    B=$TMP/wp20a-base/editions/010/render-<before>; A=$TMP/wp20a/editions/010/render-<after>
    for f in reader booklet-a4 booklet-a4-cover booklet-a4-interior; do
      pdftotext -raw $B/en/$f.pdf /tmp/b.txt; pdftotext -raw $A/en/$f.pdf /tmp/a.txt; cmp /tmp/b.txt /tmp/a.txt
      pdfinfo -box $B/en/$f.pdf | grep -vE "^(CreationDate|ModDate|File size|ID):" > /tmp/b.box
      pdfinfo -box $A/en/$f.pdf | grep -vE "^(CreationDate|ModDate|File size|ID):" > /tmp/a.box
      cmp /tmp/b.box /tmp/a.box
    done
    diff -rq $B/en/web $A/en/web

JSON leaf comparison (inline, whitelist per WP-0.1: `*_sha256` leaves and
`.path` leaves under `mag-engine-render-stage-`):

    python3 -c '
    import json
    def leaves(o,p=""):
        if isinstance(o,dict):
            for k,v in o.items(): yield from leaves(v,f"{p}.{k}")
        elif isinstance(o,list):
            for i,v in enumerate(o): yield from leaves(v,f"{p}[{i}]")
        else: yield p,o
    for name in ["request.json","en/edition-manifest.json","en/render-critic.json","en/preflight.json"]:
        b=json.load(open(f"{B}/{name}")); a=json.load(open(f"{A}/{name}"))
        lb=dict(leaves(b)); la=dict(leaves(a))
        diff=[k for k in sorted(set(lb)|set(la)) if lb.get(k)!=la.get(k)]
        print(name, len(diff), "differing leaves")
    '

## Tool versions

    rustc 1.96.0, cargo 1.96.0
    poppler 25.08.0 (pdftotext, pdfinfo)
    python 3.12.11, uv 0.8.17, weasyprint 69.0

## Metrics

Observations of edition 010 as it stands today, recorded per protocol rule 9 as
observations and NOT as pass conditions: the render is 56 pages over nine
articles, and `edition-manifest.json` carries 363 JSON leaves. Nothing in this
WP's verify clauses tests any of those numbers; every clause compares two legs
of the same input.

### Engine resolution

| # | `[render] engine` | `--engine` | result |
|---|---|---|---|
| 1 | weasyprint | typst | typst stub, loud |
| 2 | weasyprint | reportlab | `unknown render engine 'reportlab' from --engine` |
| 3 | bogus | absent | `unknown render engine 'bogus' from magazine.toml [render] engine` |
| 4 | typst | absent | typst stub, loud |
| 5 | bogus | weasyprint | past selection, fails at the edition lookup |
| 6 | key absent | absent | past selection, fails at the edition lookup |

Case 4 is what proves the key is live rather than merely present: the toml alone
changes behaviour with no flag involved. Case 3 proves it is read and that the
value is validated. Cases 1 and 5 prove the flag overrides the toml in both
directions, case 5 additionally proving that a bad toml value is irrelevant once
overridden. Case 6 proves the default is weasyprint when the key is absent.

The typst stub message:

    error: --engine typst is not implemented: the Typst reader template lands in
    WP-2.2a (meta/plans/typst-parity-and-rust-migration.md). Use --engine weasyprint.

### Unchanged weasyprint output

Before `render-2026-09-14T17-57-48` (base binary), after `render-2026-09-14T17-57-37`
(this WP's binary, default engine).

| artifact | result |
|---|---|
| reader.pdf, booklet-a4.pdf, booklet-a4-cover.pdf, booklet-a4-interior.pdf | `pdftotext -raw` identical, all four |
| the same four | `pdfinfo -box` identical after stripping dates, size and trailer ID |
| `en/web/` | byte-identical across every file |
| `en/edition-manifest.json` | byte-equal, 363 of 363 leaves |
| `en/render-critic.json` | 2 differing leaves, both whitelisted `*_sha256` |
| `en/preflight.json` | 4 differing leaves, all whitelisted scratch-stage paths |
| `request.json` | 48 differing leaves, every one the worktree's own absolute path (`artifactRoot` and 47 `inputs[*].sourcePath`); substituting the base worktree path for the after one collapses all but `artifactRoot`, which is that path itself |

`request.json`'s `renderer` field is `weasyprint` on both sides, so the bridge
receives exactly what it received before.

The 48 request.json leaves are an artifact of comparing two worktrees rather
than two runs in one tree, which is what a before/after across a commit
requires. They are not whitelisted and are not claimed to be; they are
identified exhaustively instead.

### Typst crate pins

The five exact direct dependencies WP-1.4 proved, added to `mag/Cargo.toml`
only after the Cargo lane freed (rule 1a: Cargo-file owners are pairwise
serial; WP-5.3a held it and landed as `5d9d154`, which this branch is rebased
onto):

    typst = "=0.15.1"
    typst-layout = "=0.15.1"
    typst-library = "=0.15.1"
    typst-pdf = "=0.15.1"
    typst-syntax = "=0.15.1"

`mag/Cargo.lock` goes from 203 to 397 packages, all typst-family entries
resolving to 0.15.1. Build after adding them: 36.7 s wall, 175 s CPU, warm
registry cache (WP-1.4's spike had already fetched the tree). `cargo clippy
--all-targets -- -D warnings` clean and every `cargo test` target green with
them present, including the fault suite (21.2 s) and `nocomments`.

The crates are pinned but not yet referenced: `mag/src/typeset/mod.rs` is a
stub. Nothing warns about that, since `unused_crate_dependencies` is not
enabled in this crate.

## Verdicts

No `mag parity` verdict is produced by this WP: it renders one engine and stubs
the other, so there is nothing to compare at the ladder. The before/after
comparison above is the WP's evidence.

## Residuals

- The typst branch dispatches AFTER staging and anchor patching, because that is
  where the real engine will consume the staged inputs (WP-2.1 turns exactly
  those into a Typst source tree). Consequence today: `mag render --engine typst`
  without `--no-model` would patch anchors, possibly calling a model, before
  failing. Edition 010 has zero pending anchors so no call occurs in practice,
  and every parity render passes `--no-model` by construction.
- `reportlab` is no longer selectable. It was already unreachable: nothing read
  `[render] engine` before this WP, and the Rust side hardcoded `weasyprint`
  into `request.renderer`, which is the only thing `render_engine.py` dispatches
  on. The plan's Non-goals retire reportlab at WP-6.1 and Appendix A records
  `render_engine.py` as superseded by this Rust dispatch, so the vocabulary here
  is weasyprint plus typst. `magazine.toml`'s comment described reportlab as a
  live rollback and would have become false, so it is corrected in the same
  commit.
- `Cmd::Render`'s inline clap fields moved into `render::RenderArgs`, a
  `clap::Args` struct in `mag/src/render.rs`, and `run` now takes `&RenderArgs`.
  This was forced: adding the eighth parameter tripped `clippy::too_many_arguments`
  and pushed both `render::run` and `main::run_visual` past
  `clippy::too_many_lines`. `--help` output is unchanged except for the new
  `--engine` line. Help strings are `#[arg(help = "...")]` rather than doc
  comments because `tools/nocomments.py` permits `///` only in files containing
  `#[derive(Parser` or `#[derive(Subcommand`, and it is not a file this WP owns.
- Edition loading moved out of `render::run` into `load_edition` returning
  `EditionInputs`, to bring the function back under the length lint. No
  behaviour change: the block is transcribed, not rewritten.
- `toml_value(repo_root, section, key)` generalizes the former bespoke reader
  inside `publication_name`, which now calls it. Both keep the previous
  behaviour of ignoring an empty value. It is a line scanner, not a TOML parser:
  it would mis-read a key whose name is a prefix of another in the same section,
  and `[render]` has no such pair today.

## Status

done
