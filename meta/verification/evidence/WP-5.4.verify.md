# WP-5.4 verification

## Verdict

REJECTED, on two material findings. The port's central claim is true and I
reproduced it independently; both findings are about fidelity of a helper and
accuracy of the evidence, and one of them has already propagated into the plan.

Commits verified: 5a3fa71 (port) and 78711a5 (eXIf guard + held-back test),
against pre-land HEAD 24de8d9.

## What is confirmed, independently

**The central raster claim holds.** I regenerated the Python side from scratch
rather than reusing the worker's artefacts: compiled edition 010's covers with a
spy on `resvg.usvg.Tree.from_str`, captured the post-rewrite SVG, and rendered
it through resvg. Against the Rust test's PNG:

    python RGB sha256: be0e32c07330367e0adc9a3e2f09d329bf9f7e4e0d6a64dd4d206dd9b4a1a3d3
    rust   RGB sha256: be0e32c07330367e0adc9a3e2f09d329bf9f7e4e0d6a64dd4d206dd9b4a1a3d3
    differing pixels: 0 of 4335040, diff bbox None, both 1748x2480

**WP-5.3a's oracle did not move.** Stronger than a re-run: the git blob for
`mag/tests/critic_metrics_expected.json` is `39be9e81` at 24de8d9, 5a3fa71 and
78711a5 alike, so the file is byte-identical across the guard change by
construction. Its 6 tests pass in my worktree.

**The eXIf narrowing is correct, including big-endian.** I extracted
`exif_orientation` into a standalone probe and tested the MM path the committed
fixtures omit: BE SHORT orientation 6, 1 and 8 all read correctly, BE tag 34665
returns None, truncated and bad-magic blobs return None.

**Divergence 2 is real and exact.** Transposing the white tail's parameters to
the orange tail's (106.6/0.15 for 105.1/0.30) fails the test and produces
bbox (428, 221, 967, 326) with 10,768 differing pixels, matching the evidence to
the pixel.

**Cargo.lock only gained, and gained nothing**: zero removed, zero gained, zero
version-changed. `mag/src/cover/text.rs` is untouched by both commits. Full
suite green, 11 binaries; `fmt --check` and `clippy --all-targets -D warnings`
clean.

## Finding 1, material: `art.rs::grey` is not a faithful port

`cover.py:495` computes the art-zone statistics as

    grey = image.crop(box).convert("L")

which is PIL's fixed-point ITU-R 601, `(r*19595 + g*38470 + b*7471 + 0x8000) >> 16`.
`mag/src/cover/art.rs:13` computes per-mille instead,
`(r*299 + g*587 + b*114 + 500) / 1000`, and `zone()` at :33 feeds `grey()` into
both the mean and the stddev.

The two round differently. Measured on edition 010's actual cover art
(`cover-wildcard-sign-punched-v3.png`, 1440x2160): **540 of 3,110,400 pixels
disagree**, 0.0174%. Carried through `cover.py`'s own crop and zone boxes:

| zone | PIL mean | per-mille mean | delta |
|---|---|---|---|
| top | 109.5668994940 | 109.5670233096 | 1.238e-04 |
| bottom | 128.2224356312 | 128.2224921558 | 5.652e-05 |

with stddev deltas 8.195e-05 and 1.483e-05.

The correct implementation already exists in the tree as `metrics.rs::luma601`.

The defect is currently INERT: the zone statistics feed a threshold decision
about caption treatment, and a 1e-4 shift does not flip it on this art, so the
final raster still matches. That is a pass by aggregation and threshold margin,
not by correctness, and it is the pattern rule 10 and the corpus rule exist to
catch.

**Compounding it, the evidence's compensating claim is not true.** It states the
zone statistics are "proven against PYTHON rather than against the sibling copy,
which is the stronger comparison of the two". No test compares zone statistics
to Python. The only assertion in `mag/tests/cover_footer_caption.rs` is the final
raster hash against a committed constant (line 104). The zone statistics are
exercised only indirectly, through a decision that happens not to flip.

Remedy: use the PIL fixed-point formula in `art.rs` (importing `luma601` once
WP-5.1e exposes it, or replicating it exactly meanwhile), and add a test
comparing the two zone statistics to Python directly, which is what the evidence
already claims exists.

## Finding 2, material: divergence 1's causal claim is false, and it is in the plan

The evidence states that `ttf-parser`'s redundant closing lineto is "identical"
for filled paths but not for stroked ones, that "the wordmark is the only stroked
element on the cover, and it was the only thing that differed", and that
`Builder::close` dropping the trailing lineto is what closed the gap.

I reverted that pop in my worktree and re-ran the cover test. The generated SVG
changed (4,234,729 bytes against 4,233,478, consistent with the extra lineto
commands) and **the PNG was byte-identical**; the test still passed. So the
redundant closing lineto does not reach the raster at all, under fill or stroke.

Synthetic probes agree. Rendering `M40 40 L160 40 L160 160 Z` against
`M40 40 L160 40 L160 160 L40 40 Z` through the same resvg gives identical hashes
for fill and for stroke, across a miter-sharp triangle, a round-cap/round-join
variant, and a curve-closed path.

The `close()` pop is therefore harmless and arguably right (it makes the markup
match fontTools' formatting), but it is raster-inert, and divergence 2 alone
accounts for the gap the worker closed.

This matters beyond the WP because plan revision 23 records a general method
lesson on this premise, that "a fill-only outline probe is not evidence about
stroked elements". The lesson is not supported by this measurement: the fill-only
834-glyph probe was not insufficient here, because the difference never reached
any raster. The orchestrator should correct the plan.

Note the claim may still hold for the back cover, which I did not test; the
evidence's own framing is about the front.

## Non-blocking observations

- **Three hash bases, one label.** "pixmap sha256 4b4549e9b97ead36..." is the
  Rust test's own basis (tiny-skia pixmap data). PIL-decoded RGB is `be0e32c0...`
  and RGBA is `3f853a0a...`. All three are consistent; the evidence should say
  which basis it quotes.
- **The committed test is a regression guard, not the Python oracle.** It
  compares Rust against a constant, so it would pass even if the constant were
  wrong. Python equality rests on the procedure in ## Commands, which I ran.
- **"oracle digest c519fdfb764af26a9ff2664545eb846a"** is the first 32 hex of the
  sha256 (`c519fdfb...eeca57`), not an MD5, which is what its length suggests.
- **`#[allow(dead_code)]` is on the whole `Outlined` struct**, not on `.width` as
  the evidence says. Broader than described: it would also mask a genuinely
  unused field added later. Narrowing it to the field is the smaller hammer.
- **Structural comparison, stated precisely.** Both SVGs from the transposed
  probe contain the same stroke-width tokens (7.3143 and 14.6286); only their
  assignment differs. So the plan's second limit on structural comparison is
  accurate for a coarse token-set or skeleton check, and a full markup diff would
  have caught it. Worth the precision, since it is now a plan rule.
- **A replay hazard worth adding to ## Commands.** `CoverCompiler.compile()`
  skips regeneration when the output directory already holds `cover.svg`,
  rewriting only `proof.json`. Replaying the evidence into the worker's own probe
  directory therefore captures nothing and the spy returns an empty list, which
  looks like a broken method rather than a cache hit. Use a fresh output
  directory.
- **Cargo.lock count.** I count 398 `(name, version)` entries before and after,
  where the evidence says 397. A counting-method difference, not substance; the
  only-gained property holds either way.
- **Big-endian edge, recorded not held against it.** An off-spec LONG-typed
  orientation misreads in big-endian (high half read, giving 0), but 0 != 1 so it
  bails. The failure direction is conservative and EXIF mandates SHORT.

## Cross-WP finding

WP-5.1e concluded `luma601` needed no action on the strength of
`grep -rn "luma601\|19595"` matching only `metrics.rs`. That search cannot match
`art.rs`'s per-mille constants, so the conclusion rested on a query too narrow to
see the second implementation. Whether or not the two implementations were both
correct, the reasoning was unsound; as Finding 1 shows, they are not both
correct. WP-5.1e's verifier should know, and the lift should carry `art.rs` to
`luma601` rather than allowlisting a divergence.

## Commands

    git worktree add <wt> 78711a5
    cp -R <repo>/editions/010/run-2026-09-13T01-34-51 editions/010/
    mkdir -p editions/010/articles
    for d in editions/010/run-2026-09-13T01-34-51/articles/*/; do \
      n=$(basename "$d"); cp "$d/final.md" "editions/010/articles/$n.md"; done

    # Python reference, into a FRESH directory (see the replay hazard above)
    uv run python -c "... spy on resvg.usvg.Tree.from_str, compile, write raster_N.svg ..."
    uv run python -c "... render raster_0.svg -> py_0.png ..."

    cd mag && MAG_COVER_SVG_OUT=<p>/rs_cover.svg MAG_COVER_PNG_OUT=<p>/rs_cover.png \
      cargo test --test cover_footer_caption

    # divergence 1 probe: revert the pop in Builder::close, rerun, compare
    # divergence 2 probe: set the white tail to 106.6 / 0.15, rerun
    # luma probe: compare (r*19595+g*38470+b*7471+0x8000)>>16 against
    #   (r*299+g*587+b*114+500)//1000 over the cover art, then through
    #   cover.py's crop and zone boxes with ImageStat

    cargo test; cargo fmt --check; cargo clippy --all-targets -- -D warnings

## Tool versions

python 3.12.11 via `uv run python` (the system python3 is 3.9.6 on Unicode
13.0.0 and must not be used), uv 0.8.17, Pillow via the project venv,
resvg-py 0.2.0 wrapping resvg/usvg 0.47.0, rustc 1.96.0.

## Status

rejected
