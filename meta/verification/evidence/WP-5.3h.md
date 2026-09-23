# WP-5.3h booklet spread order by position

## Base

Worktree `git worktree add --detach <scratch>/wp53h art_directed` at
`977c5eb`. Changed `mag/src/critic/rules.rs` and `mag/tests/critic_faults.rs`
only. The Python critic (`src/magazine/render_critic.py`) is unchanged.

## What changed

- `rules.rs::spread_text` now takes the page's MediaBox. On a landscape page
  (a booklet side) it splits the text shows at the horizontal middle by the
  x of each show's origin (`m[4]`, the text rendering matrix in page space).
  The left half's text comes first, then the right half's. Paint order is
  kept inside each half. A portrait page (reader) has no split, so reader
  text is unchanged. `read_leg` passes each page's MediaBox.
- `critic_faults.rs`: the WP-5.3c `missed`/`spurious` gap fields are renamed
  `python_missed`/`python_spurious`, and there is a new `python_probes`
  override. On faulted inputs the Rust critic now deliberately differs from
  Python, so:
  - Rust issue keys must equal the rule-authored set (`by_rule`) on every
    variant, with no gaps.
  - Python issue keys must equal the rule set with its declared gaps
    (`python_expectation`).
  - The two critics must agree on `result` and on every issue row, whole
    rows, except the declared Python gap rows.
  - Probes pin the rule-correct value for Rust. `python_probes` pins the
    stale Python value where it differs.
  - The test is renamed `rust_decides_every_fault_by_the_rule`.
  - In half-swaps the probes now want Rust spreads 5 false, interior 3 true,
    cover 1 false. Python keeps true, false, true.

## Commands and results

With `CARGO_TARGET_DIR` set to a scratch target, from the worktree root.
`R=editions/010/render-2026-09-14T01-49-02/en` in the main checkout.

| command | exit | observed |
| --- | --- | --- |
| `cargo fmt --check` | 0 | |
| `cargo clippy --all-targets -- -D warnings` | 0 | no output |
| `uv run python tools/nocomments.py` | 0 | `no comments` |
| `cargo test` (gates unset) | 0 | 27 binaries, 434 passed, 0 failed |
| `MAG_CRITIC_RENDER_DIR=$R MAG_CRITIC_RULES_TEXT=text-new.json cargo test --test critic_rules dumps_the_tracer`, new code and again with `HEAD`'s rules.rs (text-old.json) | 0, 0 | `cmp text-old.json text-new.json` exit 0: on the real 010 render all four legs trace to byte-identical text under position order and paint order |
| WP-5.3b-iii block 4 oracle script on text-new.json | 0 | tracer and pypdf both `pass`, 4 issues; pypdf run reproduces the shipped render-critic.json (issues, result, pages, crops True) |
| `MAG_CRITIC_RENDER_DIR=$R MAG_CRITIC_RULES_ORACLE=oracle.json cargo test --release --test critic_rules` | 0 | 51 passed; `COMPARED: 4 issues, result pass`; 22 crops pixel for pixel; `TEXT SOURCE SWAP: python-with-pypdf EQUALS python-with-tracer, rust equals tracer: true` |
| `MAG_CRITIC_FAULTS_RENDER_DIR=$R cargo test --release --test critic_faults` | 0 | 28 passed, 135.9 s |

Fault suite, Python / Rust issue counts: resaved 4/4, swapped-sheets 7/7,
half-swaps 5/6, missing-tail-band 5/5, low-ppi-figure 4/4, text-fields
16/16, raster-halves 6/6. In half-swaps Rust now reports `booklet-page-order`
and `cover-booklet-page-order` (the mirrored sides are wrong on paper) and no
`interior-booklet-page-order` (the repainted side is correct on paper). This
is the rule's decision. Python keeps its declared gaps: it misses both of those
rows and wrongly reports the interior row. Swapped-sheets still fires all
three order codes on both critics.

### Discrimination probe

The partition was changed to `*x < middle || true`, which is paint order
again. Then `cargo test --release --test critic_faults rust_decides` exited
FAILED (0 passed, 1 failed). The half-swaps failures: "the critics disagree
beyond the declared python gaps", all three spread probes, and "rust decided
[... interior-booklet-page-order ...] the rule wants [... booklet-page-order,
cover-booklet-page-order ...]". The file was restored from a copy, and `cmp`
against the pre-probe copy exited 0.

## What is and is not proven

PROVEN:

- The Rust critic decides booklet, interior and cover spread order by
  position on the page. It catches a side whose halves are exchanged on paper
  but painted in the original order. It passes a side that is correct on paper
  but painted right half first. Both are shown on edition 010 faults, on all
  three order sites.
- On the real 010 render the change does nothing: the traced text is
  byte-identical, and the live Rust-vs-Python parity test is green.
- The Python critic still reads paint order (class C, now fixed on the Rust
  side only). Its gaps are pinned as declared Python-only gaps, so a Python
  fix, or a Rust regression, fails the suite.

NOT PROVEN:

- The split uses each text show's origin x. A single show that crosses the
  fold would be assigned whole to its starting half. Imposed A5 halves do not
  produce such shows, but no fault exercises one.
- Rotated imposition (a CTM with rotation) is not handled or tested. The
  imposer places halves by translation only (`halves` in the fault suite
  checks for this).
- Only 010 English.
