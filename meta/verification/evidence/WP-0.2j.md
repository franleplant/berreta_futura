# WP-0.2j the exact number path, plus the span cap on glyph steps

Base `art_directed` `4a78cdc`. Owns `mag/src/parity*` and tests. Scratch:
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02j-run/`.

## What changed

1. **One exact number path for the tracer and its consumers**
   (`mag/src/parity/exact.rs`, new). lopdf still parses. Every
   `Object::Real` lopdf produced is then bound to the decimal token it came
   from, by position: a small lexer (skips comments, literal and hex
   strings, names, stream bodies) collects the real tokens of the object's
   authored text in order, zips them with the lopdf reals in depth-first
   order, and requires that each token parsed as f32 is bit-equal to the
   real lopdf holds there. Count or bit mismatch fails loud, naming the
   object. The value served is the token parsed as f64 (the same number
   Python's `float` gives the oracle).
   - Document objects: `exact::authored(doc, raw)` binds every object that
     carries a real. Plain objects are read at their xref offset; objects
     inside **object streams are handled**: the container is decoded, its
     header offsets give each object's span. A container lopdf did not
     keep, or an object with no xref entry, fails loud by name.
   - Content streams: `exact::content(ops, bytes)` binds each decoded
     stream (page and form XObject) for the length of its `run`. `BI`
     fails loud (the tracer already refuses inline images).
   - `exact::num` is the only conversion. A real it never bound (a clone,
     an in-memory object) is an error ("has no authored decimal"), never a
     silent f32. Binding is keyed by object address in a thread-local map;
     each `Scope` removes its keys on drop and borrows what it bound, so a
     key cannot outlive its object.
   - The consumers stopped cloning what they read, so the bound objects are
     the ones they read (`page_resources`, font dict, XObject stream, form
     Matrix/BBox/Resources, `page_attr`, the annotation array). The form
     BBox no longer goes through `Object::Real(n as f32)`: `path_op` takes
     f64s.
   - `display::extract` and `trace_elements` load from the raw bytes and
     hold the document scope for the whole pass.
2. **Span cap on glyph steps** (`display.rs`, `steps`). The drift model
   gives one tick of allowance per advance that moves the pen. An advance
   cannot move the pen less than a real glyph does, so a line whose inked
   span is S cannot contain more than `S / MIN_ADVANCE_PT + 1` steps. k at
   each glyph is now capped by that, with S the largest distance from the
   line start to any of its glyphs on either leg, keyed by the same line
   pair as k. `MIN_ADVANCE_PT = 0.5`. Measured on 010 (probe binary, see
   commands): the smallest nonzero advance is 1.2518 pt (typst) / 1.2580 pt
   (WeasyPrint), p0.1 1.598 pt, zero advances under 1 pt among 133,938
   (WvW) and 133,986 (TvT); the tightest honest line has span/k = 2.822 pt;
   max k per line 104, widest span 341.8 pt. So 0.5 pt leaves 2.5x on the
   advance and 5.6x on span/k, and the cap never binds on any 010 line or
   floor fixture.
3. Tests: six test crates that `#[path]`-include `streams.rs`/`display.rs`
   also include `exact.rs`; `rust_helpers.rs` allows the trait-required
   `Drop::drop` name in `parity/exact.rs` (23 entries). Two box tests now
   round-trip their in-memory document through bytes before reading it,
   and the link-border test parses its dictionaries from PDF text: all
   three failed loud ("no authored decimal") until then, which is the guard
   working.

New tests:
- `the_010_media_boxes_keep_their_authored_decimals_in_plain_and_object_streams`:
  a plain PDF and an object-stream PDF (xref stream, object 3 asserted
  `Compressed { container: 5 }`) with 010's two MediaBox spellings recover
  `[0 0 419.527559 595.275591]` and `[0 0 419.5276 595.2756]` exactly;
  scale `595.2756 / h` = 1.0000000151 (within 1e-10). Guard clause, known
  bad still diverges: through f32 the same scale is exactly 1.0, and
  `f32("419.527559") != 419.527559`. A string `(1.5 [2.5])` in the page
  dict checks the lexer skips strings.
- `a_real_whose_f32_crosses_a_quantum_boundary_keeps_its_exact_quantum`:
  `300.004999` quantizes to 30000 hundredths exactly; its f32
  (300.0050048828125) gives 30001.
- `a_coordinate_whose_f32_crosses_a_quantum_boundary_traces_at_its_authored_quantum`:
  the tracer on `300.004999 0 1 1 re f` emits `re 30000 0 30100 0 ...`.
- `a_real_the_exact_path_never_bound_fails_loud`: an unbound real errors; a
  truncated file errors ("xref offset past the file"); a file whose token
  moved to 419.6 errors ("is not the real lopdf parsed there").
- `a_line_buys_no_more_steps_than_its_span_can_hold`: 7000 inked advances
  of 0.0015 pt, each one tick longer on leg B (5.1 pt at the end, 10 pt
  span): **fail** (it passed before the cap: run red first, "left: pass");
  same without the tick: pass; 400 advances of exactly 0.5 pt with a tick
  each: pass; 400 of 0.25 pt: fail; 100 of 1.25 pt: pass.

Mutation check (positive control for the exact path): making `num` return
`f64::from(r)` for every real turns the three number tests red (3 failed),
restored afterwards (`grep -c "if true"` = 0).

## Commands and results

Binaries in the scratch dir: `mag-base` = `wp02t-run/mag-new` (the WP-0.2t
release; `git diff --stat 3efaf3c 4a78cdc -- mag` is empty), `mag-exact`
(release, item 1 only), `mag-new` (release, items 1 and 2).

**`mag parity 010`** `--pre-rendered editions/010/render-2026-09-24T01-56-37
editions/010/render-2026-09-24T01-58-11` (the legs of WP-0.2t), exit 1 for
all three binaries; `verdict.json` of `mag-base`, `mag-exact` and `mag-new`
are **byte-identical** (`cmp` exit 0 both ways):

| tier | before | after |
| --- | --- | --- |
| S page_count, boxes, text | pass | pass |
| S colour | fail, 9 pages | same |
| S navigation | fail, 22 mismatches | same |
| E display list | fail 58850 vs 58798, 45 pages | same |
| E glyph | fail, 58623 glyphs, 1802 shows, worst ratio 439077.1, 40 viol (capped) | same |
| G | max dx 0.0027, max dy 0.2201 | same |
| V | pass | same |

**What f32 was doing on 010** (the WP-0.2i question, measured, not
asserted). Two dump builds, identical except `num` (exact vs f32), with the
display dump extended to the glyph fields it normally skips (`origin`,
`offs`) and the violation list uncapped (`dd-exact/`, `dd-f32/`,
`pd-exact/`, `pd-f32/`):

| leg | glyph offsets moved | show origins moved | other elements moved |
| --- | --- | --- | --- |
| WeasyPrint | 1447 of 68530 (2.1%), each by 1 glyph quantum (9.16e-5 pt) | 204 of 1501, by 1 | 8 clip rects and 8 image matrices, by one 0.01 pt quantum (an edge at 44.99 where the authored 45.00 belongs, pages 9, 16, 29, 34, 39, 44, 49, 53) |
| typst | 323 of 69404, by 1 quantum | 80 of 1496, by 1 | none |

Uncapped glyph violations: 38805 exact vs 38802 f32, with 1665 / 1662
messages unique to each side, spread over nearly every page (lines pair
and k sums differently once an offset moves a quantum). The capped verdict
does not change because the first 40 violations and the worst glyph are
the same. So f32 was flipping about 2% of WeasyPrint glyph offsets at the
glyph quantum, which is exactly the shape-check exposure the plan
predicted (22% of one step), and 16 display elements at the 0.01 pt
quantum; the exact path is the authored value in every case. Real 010 file
through `exact::authored` (temporary test, not committed): page 2 and 55
MediaBox `[0, 0, 419.527559, 595.275591]` (f32: 419.5275573730469,
595.2755737304688), scale 1.0000000151 vs f32 1.0000000000; pages 1 and 56
`419.5276 595.2756`; binding the 87 MB file took 2.8 ms.

**Floor** (`floor.sh`, the WP-0.2t script with B = this scratch dir,
`floor.txt`, exit 0): every row identical before and after. AvA and
control pass ratio 0; **stairdrift pass 0.2500, 0 violations**; drift
0.2500 / smoothdrift 0.6250 pass; kern02 fail 10.25 (7), kern001 fail
0.5625 (1), advstep fail 0.625 (2), advtail02 fail 10.25 (8), glyphsub
display fail 12 pages.

**Adversarial replay** (`h/all_j.py`, the WP-0.2t `run.py` over a copy of
its 158 cases plus two new ones from `h/gen_j.py`; `results-new.jsonl`,
`all-new.txt`, exit 0). No exit changes on the 158; the same 9 fail-louds
with the same messages (none from the exact path); the only field change
is `blank_both_real_width_7000_shift5` glyph ratio 0.97 to 55.05 (already
a fail by its per-advance rule). New pair:

| pair | px | before | after |
| --- | --- | --- | --- |
| `tick_ladder_7000_shift5` (7000 "." at 0.125 vs 0.186 units, 12 pt: one tick per advance, 5.1 pt) | 2933 | 0, glyph pass, ratio 0.9987 | 1, glyph fail, ratio 48.25 |
| `tick_ladder_7000_noshift_legit` | 0 | 0 | 0 |

Gates (worktree): `cargo fmt --check` 0; `cargo clippy --all-targets -- -D
warnings` 0; `tools/nocomments.py` 0; `cargo test --no-fail-fast` exit 0,
31 result lines, 703 passed, 0 failed, 0 ignored (`cargo-test.txt`). After rebasing onto `bc29c4a` (WP-3.3b, which touches none of
this WP's files): exit 0, 31 result lines, 713 passed, 0 failed
(`cargo-test2.txt`).

## What is and is not proven

**Proven.** Every real the tracer, the box reader, the annotation reader
and the link-border key read comes from its authored token or the run
fails loud; there is no remaining f32 path in `mag/src/parity*` (the two
former converters now call `exact::num`, and the only `Object::Real`
constructions left are in tests). Object streams parse (synthetic PDF with
an xref stream). 010's MediaBox case reproduces: authored decimals
recovered and scale 1.0000000151, not 1.0. The rounding-boundary case
flips under f32 and holds under the exact path, at both the value and the
traced path. On 010 the change is enumerated: 1447 + 323 glyph offsets,
284 show origins and 16 display elements move by one quantum, and the
capped verdict is byte-identical. The span cap closes the WP-0.2t
residual: the 7000-advance one-tick ladder fails as a real PDF pair and as
a unit test, and neither stairdrift nor any other floor row or 010 tier
moves.

**Not proven.** f64 is not decimal: an authored value exactly on a
quantum tie (x.xx5) rounds as its nearest f64 does, the same as the Python
oracle, not as the decimal would. The cap still admits back-and-forth
advances inside one line: kerns that bring the pen back keep the span
small while each advance buys a tick, so a line spanning S can hold up to
`S / 0.5 pt + 1` ticks, 841 ticks or 0.62 pt on a 420 pt line (it was
unbounded, 5.1 pt measured at 7000). A line longer than the page is capped
only by its own span, not by the page. `MIN_ADVANCE_PT` is measured on 010
alone; an edition with smaller type or tighter kerning than 1.25 pt
advances has 2.5x headroom before an honest line would fail (loudly, as a
glyph violation). Binding is by object address: correct while each
`Scope` borrows what it bound, which the types enforce; a consumer that
clones before calling `num` fails loud rather than degrades. Encrypted
object streams are not expanded by lopdf and so never reach this path. The
serde_json `as_f64` round-trip note in the plan (`critic_metrics.rs`)
concerns another WP's oracle word and is untouched here. `mag/src/impose.rs`
keeps its own per-WP recovery, which refuses object streams; it could call
this path instead, but it is not this WP's file.
