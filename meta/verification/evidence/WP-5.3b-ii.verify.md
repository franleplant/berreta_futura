# WP-5.3b-ii page inspection, verification

**Verdict: ACCEPTED**, with four findings, none of them a code defect. The
port is correct, the evidence reproduces exactly, and **WP-5.3b-iii should
keep building on it.**

## What was verified, and where

Commit under test `20adcfb`, parent `0fafae1`. Worktree
`git worktree add <scratch>/vwp53bii 20adcfb`, which is not the directory the
work was developed in (rule 12). Branch tip at the start of this pass was
`a911ff1`; it moved to `746a6492` during the pass and the consequences are
adjudicated under `## What the moving branch changes`.

The six `## Commands` blocks were extracted PROGRAMMATICALLY from
`meta/verification/evidence/WP-5.3b-ii.md` with the evidence's own recorded
extractor, giving six blocks of 182 / 65 / 5 / 11 / 57 / 30 lines, and each
was run with `bash /tmp/blocks/block<n>.sh`. No command was retyped from
this shell.

Tool versions, all matching `## Tool versions` exactly: poppler `pdftoppm`
25.08.0, `uv run python` 3.12.11, Unicode 15.0.0, Pillow 12.3.0, pypdf
6.14.2, cargo/rustc 1.96.0.

## The headline claims, each reproduced

| claim | reproduced |
| --- | --- |
| block 1 regenerates every fixture and both oracles with `git status --porcelain` EMPTY | yes, no output |
| the 14 committed digests in `## Metrics` | all 14 match byte for byte |
| 15 fixture cases, 12 render-oracle pages, 139 disagreeing luma triples | yes (evidence uses 64 of the 139) |
| block 2 live oracle `sha256 3444cdd4…711e6b`, 206117 bytes | exact |
| reader rows cross-checked against the published `render-critic.json` | **0 field mismatches** |
| 85 rows | **re-derived from the enumeration**: 56 reader + 28 booklet + 1 cover booklet = 85, printed per leg |
| branch counts: sparse 0, blank 3, ink_free 3, ink_bbox None 3, punctuation 0, pure-white-with-text 0 | all exact |
| `splitlines` separators beyond `\n` present in the 010 text | `[]`, so the `str::lines` residual is MEASURED, not assumed |
| block 3: fmt, clippy `-D warnings`, nocomments | all clean |
| block 4: `MODE: skipped`, then `MODE: full` with `COMPARED: 85 rasters, 85 inspection rows`, then the both-or-neither panic | exact, all three |
| tracer-text report 43 of 56 identical, 56 of 56 raster fields, `body_text_lines` 49 of 56, `text_characters` 43 of 56 | exact |
| block 5: 15 fixture probes, every one FAILS | yes: 14 at `FAILED 1`, the shard-window probe at `FAILED 2`, then `RESTORED` |
| both extremes of the punctuation filter fail (rule 10's diagnostic) | yes, "accepts every line" and "accepts nothing" both `FAILED 1` |
| block 6: 2 live probes | exact, including both assertion messages (`inspection row for reader page 1`, `raster bytes for reader page 1`), then `RESTORED` |
| 17 probes | **re-derived**: 15 fixture + 2 live = 17 |

`git status --porcelain` was empty after blocks 5 and 6 and after every probe
of my own, so no mutation leaked.

### The test total, with its domain and its timestamp

`cargo test --manifest-path mag/Cargo.toml` at `20adcfb` emits **18 `test
result` lines** and **181 passed tests**, counting the `passed` field of each
line. `mag/tests/` holds **17 `.rs` files**. Both numbers are right and they
count different things: 18 is test BINARIES, the eighteenth being the `mag`
binary target's in-crate `#[cfg(test)]` modules; 17 is integration test
FILES. The evidence's "18 result lines" is the binary count and is correct.
181 is a measurement at `20adcfb` and is not comparable to the 190/192/202/207
totals in circulation, which were taken after WP-0.2k, WP-2.2a and WP-5.1g
landed.

Rule 12's abort clause: `cargo test` stops at the first failing BINARY, so an
18-line output is itself only evidence that no binary failed. All 18 lines
read `ok`, so nothing was truncated here.

## Shard invariance, reproduced and then strengthened

This was the claim most worth checking, because a sharded oracle that is not
shard-invariant is machine-specific and fails first on someone else's machine.
The evidence proves it by comparing outputs; I also proved the parameter is
HONOURED, which is what stops the comparison being vacuous.

I put a counting shim for `pdftoppm` on `PATH` and ran
`render_pages_output_does_not_depend_on_the_shard_count`. It logged **27
poppler invocations in five genuinely different patterns**:

| `shards` | invocations | windows |
| --- | --- | --- |
| `Some(1)` | 1 | unsharded, no `-f`/`-l` (exercises `shard_count < 2`) |
| `Some(3)` | 3 | (1,4) (5,8) (9,12) |
| `Some(5)` | 5 | (1,2) (3,4) (5,7) (8,9) (10,12) |
| `Some(12)` | 12 | (1,1) … (12,12) |
| `None` | 6 | (1,2) (3,4) (5,6) (7,8) (9,10) (11,12) |

1 + 3 + 5 + 12 + 6 = 27, matching the log. Every window set is exactly
Python's `cuts[i] = page_count * i // shard_count`,
`windows[i] = (cuts[i] + 1, cuts[i+1])` recomputed by hand. The default of 6
is `worker_count(12 // 2, None)` on this 14-core host, and Python's
`max(1, min(6, 14, 8))` gives 6 too. All five runs produced **byte-identical
PNG sets**.

Going beyond the committed set, I temporarily widened the sweep to **every
shard count 1 through 13** plus the default, including 13 > page count, and
all fourteen runs still agreed byte for byte. The committed set omits 2 and 4,
which are the counts a 2- or 4-core host would choose; they agree too. The
file was restored and the tree left clean.

Non-vacuity is independently established by block 5's off-by-one window probe,
which `FAILED 2`: it fails the shard-invariance test as well as the oracle
test, which can only happen if the shard parameter changes the code path.

## The corpus-unreachability table, re-derived from the Python

I enumerated branches by parsing `src/magazine/render_critic.py` with `ast`
and listing every `If`, `IfExp`, `Try`, `BoolOp`, chained `Compare` and
comprehension filter inside `_render_pages` and `_inspect_page`, rather than
reading the corpus for cases. That yields **22 branch sites**: 8 in
`_render_pages`, 14 in `_inspect_page`.

**Every one of the 22 is accounted for by the table, and nothing the table
claims is wrong about coverage.** Mapping, with the sites the table does not
give their own row called out:

- `_render_pages`: `if not executable` (row 14, uncovered, named);
  `try/except PdfReader` (row 17, uncovered, named); `if shard_count < 2`
  (row 13, BOTH sides covered, and I exercised every count 1-13);
  `if completed.returncode` (row 15, covered by
  `render_pages_reports_the_python_message_when_poppler_fails`, which I saw
  pass); `try/except page_number` (row 18, uncovered, named);
  `if path != target` (row 19, uncovered on the false side, and the TRUE side
  IS exercised because a 12-page PDF makes poppler emit `page-01.png`, which
  is why the zero-padding probe fails); the `detail` or-chain (row 16, stderr
  arm covered, other two named uncovered); and **the `window is None` ternary,
  which gets no row of its own** but is the same decision as row 13 and is
  covered both ways.
- `_inspect_page`: `texts is None` and its `or ""` (row 1, eliminated by
  construction); both `if total_pixels` ternaries (row 12, declared
  unreachable because PNG forbids a zero dimension); the punctuation
  comprehension filter (row 2, fixture, both extremes fail); `list(bbox) if
  bbox` (row 8); **`list(presence_bbox) if presence_bbox`, which gets no row
  of its own** but is covered both ways, and `paper_tint_no_text` is precisely
  the case where the two ternaries COME APART (ink_bbox `None`,
  presence_bbox `[0,0,128,128]`); `pure_white and not strip` (rows 5, 7);
  `ink_pixels == 0 and not strip` (rows 6, 7); the chained
  `0 < ratio < SPARSE_INK_RATIO` (rows 3, 4, all three outcomes exercised at
  0.0 / 0.001953 / 0.0078125); both `point` threshold ternaries (row 9,
  `threshold_bands`); and the `body_text_lines` filter, which is WP-5.3b-i's
  and is nonetheless exercised both ways here by `tie_down` ("lowercase line"
  → 1) against `tie_up` ("UPPER ONLY" → 0).

So the table is **complete on coverage and short by two rows on enumeration**,
both of the missing sites being fully covered. That is the good direction for
this error to point.

The nine-branch and five-uncovered readings in the brief both check out
against the table as written.

## Rule 10c sweep: no unguarded fallback coincidence

Nobody had swept this WP for the class. I swept both oracle files and all 15
fixture rows, field by field, asking for each whether any claim rests ONLY on
a value a wrong branch would also produce.

**Result: no live field is left on a coincident value.** Every field that
takes a default-looking value in some cases takes a non-coincident value in at
least one other, and the probes confirm the separation:

- `ink_ratio` `0.0` coincides with the `total_pixels == 0` fallback in 4 rows,
  but 8 distinct non-zero ratios pin it.
- `ink_bbox` / `presence_bbox` `None` is the falsy fallback in 4 rows; 11 real
  bboxes pin them, and the right-edge probe fails.
- `body_text_lines` `0` and `text_characters` `0` are the empty defaults in 9
  and 7 rows; both are pinned by non-zero cases, and the bytes-versus-
  codepoints probe fails on `astral_text`.
- `blank` is `true` in exactly one row and `ink_free` in two; both conjunct-
  dropping probes fail, and `paper_tint_no_text` separates the two fields.
- `standalone_punctuation_lines` is `[]` in **14 of 15** rows, the sharpest
  exposure in the set, and it is the one the WP anticipated: the 14 empties
  pin "accepts everything" and the single non-empty row pins "accepts
  nothing", and **both extremes fail**. Pinned in both directions.
- The `difference` oracle carries a `rgb_mae` of exactly `0.0`, the all-zero
  fallback, and the test **asserts** the oracle holds both a zero and a
  non-zero case so it cannot decay into all-zero.
- `grayscale` carries an explicit assertion that the naive float formula must
  disagree somewhere, which is the same guard shape.
- The render oracle's 12 page digests are **12 distinct shas**, so an ordering
  defect cannot hide, and the padding probe fails.

Two things worth naming rather than burying:

1. **`whitespace_only_text`'s expected row is byte-identical to
   `corner_ink`'s** on every field but `page` — its expected value equals the
   empty-input result, which is exactly the 10c shape. It survives because one
   field separates the branches: a no-op strip would give
   `text_characters = 5`, not 0. I verified that by probe rather than by
   argument — replacing `py_strip(text)` with `text` fails on
   `paper_tint_with_text`. So the case is thin but genuinely discriminating.
2. **`largest_void`, `voids` and `tail_band` are `null` / `[]` in all 15 rows
   and all 85 live rows**, coincident with the default everywhere and pinned
   by nothing. This is a real 10c coincidence, and it is correctly disclosed:
   they are Python's placeholders, declared under NOT PROVEN, and owned by
   WP-5.3b-iii.

**Answer to the question asked: the fallback-coincidence class does NOT appear
unguarded in these fixtures.**

## The two disclosed findings, both assessed

**1. `serde_json`'s float parser.** Both halves verified in
`serde_json_parses_every_oracle_float_exactly`
(`mag/tests/critic_inspect.rs:114`). The first half walks every float literal
outside strings in both committed oracles and asserts `str::parse` and
`Value::as_f64` agree bit for bit. The second half asserts the known-bad
literal `97.71500651041667` **still diverges**, so the guard cannot go vacuous
if the parser is fixed underneath it. That second clause is rule 10 applied to
a GUARD, and it is the right shape. `rgb_mae` is correctly carried as TEXT and
read through `exact()`, which parses from `as_str()`. The knock-on report
about `mag/tests/critic_metrics.rs:30` is accurately scoped: no measured
disagreement exists, the wording there is stronger than the mechanism, and the
WP correctly declined to edit a file it does not own.

**2. The stale 16-of-56 figure.** Reproduced. `text_characters` measures
**43 of 56** and `body_text_lines` **49 of 56** here, on
`render-2026-09-14T01-49-02`, against WP-5.3b-i's measurement on
`render-2026-09-14T01-47-59` — a different render with a different
`reader.pdf` sha256 — and the counts are identical. That is a real result
about the evidence regime and not just a corrected number: it shows these two
figures are base-invariant, where revision 49's named-commit rule warns that
some are not. The rule is about knowing which, and this WP established which
for these two.

## The Owns question, adjudicated

`mag/src/critic.rs` gained exactly `+pub mod inspect;`. I verified the diff is
one line and one insertion, that the whole file is three module declarations,
and that both cited predecessors did exactly the same (`5d9d154` adds
`+pub mod metrics;`, `26391ab` adds `+pub mod text;`, one insertion each).

**The necessity argument holds, and I tested it rather than accepting it**
(rule 11: remove the supposed cause and measure). With the line deleted:

- `cargo build` finishes **clean**;
- `cargo clippy --all-targets -- -D warnings` finishes **clean**;
- `cargo test --test critic_inspect` reports **9 passed, 0 failed**.

So without that one line the module file sits in the tree as dead code,
unlinted and uncompiled by the binary, **while every check in the repository
stays green** — because the test's `#[path]` includes route around the real
module graph. That is precisely the WP-0.2h failure mode rule 12 names, and
the WP's `## Residuals` already says so. The line is what makes the WP
verifiable at all, and the claim is stronger than the WP stated it.

**Does declaring-and-landing meet the rule? Strictly, no.** Rule 1's shape is
"name the one item and the one word, ASK for the extension, never duplicate,
never self-grant", and this landed first and offered the extension
retroactively. That approximates the rule; it is a self-grant with a full
disclosure attached. What would have met it is asking before landing, or
landing the module and reporting `blocked` on one line.

**It should nonetheless STAND, and the extension should be recorded**, on four
grounds: rule 1 already settled the identical question for WP-5.3b-i's
`GLYPH_QUANTUM` with "It STAYS; this is a rule for next time"; the change ADDS
a module rather than altering an existing public surface, which is the very
distinction rule 1 uses to explain why a `pub use` was not behaviour-free;
`mag/src/critic.rs` is not comparator territory and rule 1c assigns it to
nobody; and it is measurably load-bearing for verifiability.

**Recommendation to the plan**, since this has now arisen three times
identically and will arise again with `rules.rs`: assign the `mod` lines of a
module-declaration file to whoever CREATES the module, i.e. treat
`pub mod <name>;` as part of creating `mag/src/critic/<name>.rs` rather than
as a change to someone else's file. That retires the question instead of
re-adjudicating it per WP.

The WP's refusal to make `metrics.rs:411 fn resize` public, or to write a
second LANCZOS, was correct for the reason it gave — two copies would be
pinned to each other rather than each to Python — and the plan has since
granted that extension to WP-5.3b-iii.

## Findings

**Finding 1 (fixture tightness, not named by the evidence):
`SPARSE_INK_RATIO` is not tightly straddled.** The Phase 5 preamble requires a
numeric guard's fixture pair to straddle the boundary at the finest
granularity the guard can distinguish, and this one does not. Measured by
probe:

| `SPARSE_INK_RATIO` | fixture suite |
| --- | --- |
| 0.004 → 0.003 | **ok, 9 passed** |
| 0.004 → 0.006 | **ok, 9 passed** |
| 0.004 → 0.0005 | FAILED 1 |
| 0.004 → 0.5 | FAILED 1 |

The nearest sparse ratio below is 0.001953125 and the nearest non-sparse above
is 0.0078125, so the constant is unpinned across at least a 25% move in either
direction. The evidence demonstrates the guard is NOT INERT and is entitled to
claim no more; it claims no more explicitly, but it does not label this guard
as half-verified the way rule 10 asks. Not a defect: the ported value 0.004 is
exactly Python's `SPARSE_INK_RATIO` at `render_critic.py:34`, and on 010 the
field is 0 of 85, which the evidence does label. By contrast `WHITE_THRESHOLD`
and `PAPER_WHITE` ARE tight — `threshold_bands` puts columns at 244/245 and
254/255, one gray level apart, the finest granularity a u8 threshold has, and
both ±1 probes fail. Two of three numeric guards tight. **Inherited by
WP-5.3b-iii** if it consumes `sparse`.

**Finding 2 (citation accuracy): eight of the branch table's line numbers are
wrong, three of them landing on the adjacent field.** `render_critic.py` is
byte-identical at the WP's base and at its commit (blob
`0356bb88…`), so this is not drift. Resolved against the real file:

| evidence cites | actually at | `:cited` lands on |
| --- | --- | --- |
| `_render_pages` (:888) | **:909** | inside `_booklet_text_rows` |
| `shutil.which` (:890) | **:912** | a bare `)` |
| `if total_pixels` (:1001, :1002) | **:994, :995** | `presence_ratio`, `presence_bbox` |
| `bbox` falsy (:1005) | **:1000** | `"voids": []` |
| `pure_white` → blank (:1009) | **:1008** | `ink_free` |
| `ink_pixels == 0` → ink_free (:1010) | **:1009** | `sparse` |
| `0 < ratio <` sparse (:1011) | **:1010** | `standalone_punctuation_lines` |
| `inspect_render` rasterisations (:583-585) | **:580-582** | blank + two manifest calls |

Correct as cited: `:933`, `:934`, `:965`, `:986`, and `:939`/`:943`/`:952`
land inside the right construct. No claim depends on these: every branch is
identified in the table by its CODE, unambiguously and correctly, which is how
I matched all 22 sites. But this is the table the plan calls its most-cited
lesson, its purpose is to send a later reader to the Python, and three
citations point at a DIFFERENT FIELD one line later, which reads as correct
and is not. Revision 50 corrected a stale figure by locating it "by content
rather than by the cited line"; the same habit is required here.

**Finding 3 (enumeration): two branch sites have no row of their own** — the
`presence_bbox` ternary and the `window is None` ternary. Both are covered
both ways; the table is short on enumeration, not on coverage.

**Finding 4 (undeclared divergence, benign): the page count feeding the shard
derivation comes from a different library in each leg** — Python
`len(PdfReader(pdf).pages)`, Rust `lopdf::Document::load(pdf).get_pages()`.
The two could disagree on a malformed PDF. It cannot affect output, because
the shard count does not, and I measured that across every count 1-13. Worth a
line in evidence that it is neutralized by shard-invariance rather than left
for a reader to notice.

## What the moving branch changes

`art_directed` moved from `a911ff1` to `746a6492` during this pass, adding
WP-5.4c, WP-0.2k's acceptance, WP-2.2b and four plan revisions. Rule 5b asks
what arrived in the new base, not only where my commit sits.

One arrival touches WP-5.3b-ii's dependencies: `mag/src/model/shared.rs` gained
98 lines (`is_name_roster`, `clamp_roster`, `ui`, roster constants) from
WP-5.1f, WP-5.1g and the shared-helper lift. `inspect.rs` consumes `py_strip`
from that file. **I checked the three functions it actually depends on —
`py_strip`, `is_python_space`, `py_islower` — and all three are byte-identical
at `20adcfb` and at the tip.** Nothing WP-5.3b-ii rests on moved, so no
re-verification is owed.

Rule 3a, the stronger form: across every commit in `20adcfb..746a6492`,
`critic_inspect_expected.json`, `critic_inspect_render_expected.json`,
`mag/src/critic/inspect.rs` and `mag/tests/critic_inspect.rs` each have
**exactly one distinct blob hash**, proving they never changed anywhere in the
range rather than merely producing the same result now.

## What this verification does and does not establish

ESTABLISHES: that the evidence reproduces, from a directory it was not
developed in, on the recorded tool versions; that the 22 Python branch sites
are enumerated and covered as claimed; that 17 of 17 probes discriminate; that
shard invariance is real, honoured and broader than claimed; that no
unguarded fallback coincidence sits in the fixtures; and that the one Owns
overstep is load-bearing, measured, and consistent with settled precedent.

DOES NOT ESTABLISH, and I say so under rule 10 as it binds verifiers:

- **Anything outside edition 010 English**, two page geometries, one poppler
  build, one host. The corpus bound the WP already states is not lifted by
  re-running it.
- **That `SPARSE_INK_RATIO` is the right constant to within 25%** — see
  finding 1. It is the right constant because it equals Python's, which is a
  different argument from the fixtures proving it.
- **That the five uncovered `_render_pages` arms behave like Python.** They
  are named, argued unreachable, and untested; I did not test them either, and
  `shutil.which`'s executable-bit check remains a genuine, disclosed, unexercised
  divergence from Rust's `is_file()`.
- **Equality is not correctness.** Everything above says the port agrees with
  `render_critic.py`. It says nothing about whether `_inspect_page`'s
  judgments are right, and class C is invisible to every check here.
- **No search is offered as proof of absence.** The 10c sweep is an
  enumeration over 15 named rows and two named oracle files, not a grep.

## Is the defect live on the branch?

No defect. Nothing is live, nothing must be quarantined, and **WP-5.3b-iii,
WP-5.3c, WP-5.3g and WP-5.5c may build on `20adcfb` as it stands.** The four
findings are one fixture-tightness label, one set of wrong line citations, one
short enumeration and one undeclared-but-benign library difference; all four
are documentation or fixture work, none changes a byte of `inspect.rs`.
