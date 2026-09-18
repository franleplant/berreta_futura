# WP-5.3b-i the critic's text source

## Base

96f1dd1 (plan revision 37). The previous submission recorded a0714c3, which
was five commits stale and, worse, the gap spanned the commit that changed
`GLYPH_QUANTUM` from `0.0001` to `GLYPH_DRIFT_PT / 8.0` — the constant
denominating the operand the defect below turns on. Rule 9 with teeth: the
configuration moved underneath the number.

## Status

done (rework after rejection at 3f45d31).

The rejected code is LIVE on the branch. Commit 26391ab is an ancestor of
a537a24, so the broken join rule shipped and this rework repairs shipped code
rather than landing new code. Verified with
`git merge-base --is-ancestor 26391ab a537a24` and by reading HEAD's copy of
`mag/src/critic/text.rs`, which carries the unconverted width. Worth stating
because a rejection does not by itself remove anything from the tree.

All figures below were re-measured at a537a24 rather than carried from the
pre-rejection run, because the comparator this WP reads through has been under
concurrent edit.

## The defect that was rejected, and the fix

`separator` subtracted two quantities in DIFFERENT UNITS.

`Show.x` comes from the text matrix, built as `m: trm.map(qc)` at
`streams.rs:432`, in hundredths of a point. `Show.width` derived from `offs`,
built with `qo` at `streams.rs:423`, in `GLYPH_QUANTUM` units of
9.1552734375e-05 pt. One qc unit is 0.01 pt and one qo unit is
9.1552734375e-05 pt, so **one qc unit is 109.2267 qo units** and `width`
entered the subtraction inflated by that factor, driving `gap` far negative
and suppressing almost every space.

Fixed by converting the span to qc where the width is computed, so
`Show.width` is in qc throughout:

    let span = (last[0] - first[0]) * count as i64 / (count as i64 - 1);
    (span as f64 * GLYPH_QUANTUM * 100.0).round() as i64

`GLYPH_QUANTUM` is now re-exported from `mag/src/parity.rs` alongside the
types this WP already consumed.

Measured over all 56 pages with one counter, so the two are comparable:

| rule | spaces | empties |
|---|---|---|
| shipped (broken) | 9 | 231 |
| fixed | 118 | 122 |

### What the fix changes downstream, re-measured

Configuration: base 96f1dd1, post-WP-0.2h standard-14 decode, WP-0.2i
per-glyph offsets at this base, `GLYPH_QUANTUM = GLYPH_DRIFT_PT / 8.0`,
geometric join with the qc conversion, pinned `py_islower`. Corpus
`editions/010/render-2026-09-14T01-47-59/en/reader.pdf`, 56 pages.

| field | broken rule | fixed rule | label |
|---|---|---|---|
| text-emptiness | 56 of 56 | **56 of 56** | DISCRIMINATING, partition identical |
| `body_text_lines` | 49 of 56 | **49 of 56** | same seven differences |
| `text_characters` | 16 of 56 | **43 of 56** | feeds no issue site |

So the fix materially improves the only field the join rule governs, from 16
to 43 of 56, and leaves both decision-relevant fields untouched. The seven
`body_text_lines` differences are unchanged: pages 4, 11, 31, 36, 40, 46, 50,
each with the tracer counting one line more, total 1117 against pypdf's 1110,
and 1117 − 1110 = 7 accounts for all of it. Confirmed on two pages by reading
pypdf's own output: `'Government Rails Site HitHours After CVE Patch'` and
`'The third era of AI softwaredevelopment'` are two-line headlines pypdf
merges, and the tracer keeping them apart is correct.

### The rule-10 label, restated honestly

The previous evidence said the join rule is non-discriminating on 010 and that
the rule "is chosen because it is PRINCIPLED, not because this corpus can
tell". The first half was true; the second was false, because the shipped rule
was not the principled rule. **The label belonged to the code, not the
corpus.**

What is true now, with a rule that computes what it claims: the join rule is
still non-discriminating for the two DECISION-RELEVANT fields on 010 — an
unconditional space, an unconditional empty, and the corrected geometric rule
all produce the same emptiness partition and the same `body_text_lines`. It is
NOT non-discriminating overall: it moves `text_characters` by 27 pages, and
`text_characters` feeds no issue site, which is why no decision moves.

The defect was found because BOTH EXTREMES PASSED. The previous evidence ran
the unconditional-space probe and concluded the field was non-discriminating;
it never ran the unconditional-empty probe, which also passes. Two opposite
rules both passing is evidence about the TEST, not about the corpus, and the
lesson is now a committed test rather than a note.

## What is and is not proven

**Proven.**

- The join rule computes a gap in consistent units, and a real word gap yields
  a space. Test: `a_real_word_gap_yields_a_space` in
  `mag/tests/critic_text.rs`, on synthetic shows at 23 pt with a 10.7 pt gap
  against the 5.75 pt threshold. SHOWN TO DISCRIMINATE: restoring the unit bug
  (dropping the qo-to-qc conversion) makes it FAIL with
  `left: "GovernmentRails"`; restored, it passes. This is the regression test
  the rejected submission lacked.
- An adjoining run does not gain a space. Test:
  `a_kerned_join_yields_no_space`, asserting `"software"` from two shows whose
  gap is below threshold. Together the two tests exercise both branches of
  `separator`, which no corpus assertion did.
- `py_islower` matches Python's `str.islower()` on every codepoint. Test:
  `islower_matches_python_over_the_whole_plane` against the committed oracle
  `mag/tests/critic_text_islower_expected.txt` (2,544 codepoints). SHOWN TO
  DISCRIMINATE: deleting one entry (U+0295) makes it FAIL.
- The pinning is necessary rather than decorative. Test:
  `islower_differs_from_rust_std_on_the_recorded_codepoints`, which asserts
  Python's answer AND, with `assert_ne!`, that `char::is_lowercase` gives the
  opposite for U+0295, U+1C8A, U+A7CD and U+10D70. Self-invalidating by
  design: if a future rustc agrees with Python, it fails and says the pin is
  no longer needed.
- Line reconstruction reproduces pypdf's empty/non-empty partition and the two
  confirmed headline-merge pages. Test: `reconstructs_edition_010_text`,
  asserting the exact empty-page list, page 4 at 10 body lines, page 36 at 4,
  and 1117 total. SHOWN TO DISCRIMINATE: widening `SAME_LINE_TOLERANCE` from
  100 to 1200 makes it FAIL (1111 against 1117).

**Not proven, with what would prove it.**

- **The corpus test cannot see the join rule at all.** `reconstructs_edition_010_text`
  passes under the unit bug, under an unconditional space and under an
  unconditional empty. That is why the defect shipped, and why the two new unit
  tests exist. Proving the join rule against the corpus would need a page where
  a decision depends on it; edition 010 has none.
- **The y-tolerance is proven only in the widening direction.** At
  `SAME_LINE_TOLERANCE = 0` the corpus test still passes, because shows sharing
  a line in 010 carry exactly equal y. A fixture with shows a fraction of a
  point apart on one line would prove the other direction; WP-5.3b-ii or
  WP-5.3c owns it if it matters to them.
- **The pinning is not exercised by edition 010.** Swapping `py_islower` for
  `char::is_lowercase` leaves the corpus test passing, so no page of 010
  contains any of the 53 divergent codepoints. The pin is proven by the
  whole-plane sweep, not by the corpus — exactly what the corpus rule warns
  about.
- **The width estimate is an estimate.** `offs` gives glyph ORIGINS, so the
  final glyph's own advance is unknown and is approximated by the mean advance
  (`span * n / (n - 1)`). For a run ending in a narrow glyph this overshoots
  and for a wide one it undershoots, by at most one glyph advance. This is why
  the first fixture attempt was wrong by inspection: a run whose offsets span
  120 pt ends at roughly 133 pt, not 120. Proving it exactly would need
  per-glyph advances, which the display list does not carry; WP-0.2j's exact-
  number path is the place that could supply them.
- `text_characters` (43 of 56) is reported as evidence about the text source
  rather than as a gate, per the WP-5.3d decision, and feeds no issue site.

## Commands

    # the islower oracle (regenerates mag/tests/critic_text_islower_expected.txt)
    uv run python -c "
    out=[cp for cp in range(0x110000)
         if not (0xD800 <= cp <= 0xDFFF) and chr(cp).islower()]
    print(len(out))
    open('mag/tests/critic_text_islower_expected.txt','w').write('\n'.join(map(str,out)))"

    # the pypdf reference for the comparison table
    uv run python -c "
    import json
    from pypdf import PdfReader
    r = PdfReader('editions/010/render-2026-09-14T01-47-59/en/reader.pdf')
    rows = []
    for i, p in enumerate(r.pages, 1):
        t = p.extract_text() or ''
        lines = [l.strip() for l in t.splitlines()]
        body = sum(1 for l in lines if l and any(c.islower() for c in l))
        rows.append({'page': i, 'body': body, 'chars': len(t.strip()),
                     'empty': not t.strip()})
    print(json.dumps({'rows': rows}))"

    # the committed tests, skip mode (announces MODE: skipped)
    cargo test --manifest-path mag/Cargo.toml --test critic_text -- --nocapture

    # the committed tests, full mode against the untracked render tree.
    # The render tree is UNTRACKED and exists only in the main working tree, so
    # run this from there, or copy the tree into a worktree first. Rule 12
    # caught an earlier $PWD form here that resolved to a worktree and silently
    # found nothing.
    MAG_CRITIC_READER_PDF=/Users/franguijarro/code/magazine/editions/010/render-2026-09-14T01-47-59/en/reader.pdf \
      cargo test --manifest-path mag/Cargo.toml --test critic_text -- --nocapture

    cargo fmt --manifest-path mag/Cargo.toml --check
    cargo clippy --manifest-path mag/Cargo.toml --all-targets -- -D warnings

    # the unit ratio the defect turned on
    uv run python -c "
    q = 0.000732421875 / 8.0
    print('GLYPH_QUANTUM pt =', q)
    print('qo units per qc unit =', 0.01 / q)"

    # the headline-merge mechanism
    uv run python -c "
    from pypdf import PdfReader
    r = PdfReader('editions/010/render-2026-09-14T01-47-59/en/reader.pdf')
    for pg in (4, 36):
        t = r.pages[pg-1].extract_text() or ''
        for l in [l.strip() for l in t.splitlines() if l.strip()][:5]:
            print(pg, repr(l[:70]))"

`reconstructs_edition_010_text` is env-gated on `MAG_CRITIC_READER_PDF` and
announces its mode per rule 2b: `MODE: skipped, MAG_CRITIC_READER_PDF unset`
or `MODE: full, tracing <path>`. If the variable is set but the file is
missing it ASSERTS rather than skipping, so a typo cannot pass silently. The
previous submission hard-coded an absolute path, which traced the main tree's
PDF while exercising a worktree's code and would have skipped anywhere else.

## Tool versions

rustc 1.96.0, lopdf 0.45.0, `uv run python` 3.12.11 on Unicode 15.0.0, pypdf
6.14.2. This machine also carries system python3 3.9.6 on Unicode 13.0.0,
which yields a DIFFERENT islower set; every command here uses `uv run python`.

## Verdicts

No `mag parity` verdicts: the Phase 5 preamble forbids the comparator for
oracle tests and this WP produces none.

## Residuals

- `py_islower` and its 671-range table sit in `mag/src/critic/text.rs` rather
  than `mag/src/model/shared.rs`. The verifier planted a divergent second copy
  in `shared.rs` and confirmed the duplicate audit FAILS on name plus
  signature, so the dangerous case has a mechanical backstop; this is tidiness
  with a residual rather than exposure. Whoever next owns shared.rs may lift
  it.
- The width estimate's one-glyph-advance uncertainty is described above and is
  inherent to what `offs` carries.
- WP-5.3b-ii inherits `page_text`, `body_text_lines` and `trace_text` as its
  text source, and the fact that `metrics.rs` exposes `decode_rgb`, PIL-exact
  `thumbnail`, `round_half_even`, `round_places`, `ordered_map` and
  `worker_count` but NOT PIL-exact grayscale or `getbbox`, which
  `_inspect_page` needs and which are `render_critic.py`'s own raster helpers.
- WP-5.3b-iii inherits the five text-derived fields across their eleven issue
  sites, with only `body_text_lines` differing from pypdf.
- WP-5.3c still owes fault coverage on all five text-derived fields. For
  `standalone_punctuation_lines` that coverage is the ONLY evidence there will
  be: the field is zero on every page of 010 under both implementations, so
  its agreement is empty-set.
