# WP-5.10 verification

Verdict: **ACCEPTED**

Verified at art_directed `b7f7791` (contains `0e20ab8`), fresh worktree.

## Replay

- Live package test, same oracle as the worker
  (`tmp/v4/{spec.json,py-out,py-tracer-out}`, the `tmp/verify4` symlink to
  the main tree still in place): `cargo test --release --test package --
  --test-threads 1 --nocapture` exit 0, 62 passed (the worker's 51; the
  binary has grown since), `RASTER booklet-a4-cover.pdf: 1`,
  `booklet-a4-interior.pdf: 26`, `booklet-a4.pdf: 28` pages equal at 110
  dpi, `CLASSES {"bytes": 90, "pdf": 3, "pixels": 28, "report": 1}`, same
  as the evidence.
- Python `re` `\s` over all code points: 29 matches under the project's
  `uv run python` (3.12.11) and system 3.9.6, including 0x1c-0x1f;
  consistent with White_Space (25) plus four.
- `try.md` holds the `unit: str = "k<NBSP><SNOWMAN>"` line (checked with
  `od -c`). No U+2014 left in `web/edition.rs` or `web_edition.py`
  (`grep -c` 0 on both).
- Full suite at tip: `cargo test` exit 0, 740 passed, 0 failed, 32
  binaries; fmt and clippy `-D warnings` 0.

## Injected defects (mine)

1. `impose.rs` `place`: right-hand page translated by `x + 0.5` pt. Live
   package test FAILS at `booklet-a4-cover.pdf page 1 raster`
   (tests/package.rs:157), i.e. the new raster assertion, not the page
   count, catches a half-point imposition shift.
2. `highlight/engine.rs`: remove only the `\S` arm (keep `\s`):
   `highlight` FAILS on `separators.c`. Remove only the `\s` arm: FAILS on
   `separators.c`. Each arm is pinned on its own.
3. `web/edition.rs` title joined with `" - "`: `web_port` FAILS (three
   tests panic at web_port.rs:613, including the 010 byte-identity tree).

## What is and is not proven

- Proven: every PDF page of the three booklet entries is raster-compared
  and a sub-point placement shift fails it; both whitespace arms and the
  colon title are pinned by committed tests.
- Not proven: the live package test is not a committed fixture; it needs
  the verifier oracle dir and the `verify4` symlink (disclosed by the
  worker). `\w`, `\d` and other class differences stay unprobed.
