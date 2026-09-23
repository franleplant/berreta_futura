# WP-5.5a web edition

## Base

4f20801 (plan revision 29 at branch time; revision 30 decided the QR question mid-WP)

## Status

port complete for 010's surface and a fixture edition (increment 2, below);
not wired into the binary, which is WP-5.6's `render.rs`; pygments
highlighting still refuses loudly. Earlier status, kept for history:
blocked on the port itself; both committed-asset legs proven

The four brittle matchers from WP-0.0c are PORTED, tested and landed as
`mag/src/web/markup.rs`. The rest of the WP is not: `html_edition.py`'s web
path and `web_edition.py`'s document pipeline remain, and a SECOND
sub-project blocker was found in the former (pygments, below).

Both blockers are now DECIDED, and neither asks for a Python library to be
reproduced.

**QR (revision 30, then revision 32).** Revision 30 first chose to reproduce
segno's deviation, on the ground that `weasyprint_adapter.py` calls segno too
(`_fitted_source_code` at :1902, `_source_code_matrix` at :1918), so the QR
modules are inside Tier E's compared domain and a different matrix is
different path geometry. Revision 32 then changed route once the real cost
was known (no padding hook in `qrcodegen`, so reproducing the deviation means
owning bitstream, ECC, mask selection and layout): COMMITTED ASSETS for the
compared edition, a spec-correct encoder for new work. Both legs read the
same asset, so Tier E is satisfied without reproducing a bug.

**Both legs are now proven.** Leg 2 is below, with a correction: it first
traced a measurement call site and so measured the fit at the wrong room.
Leg 1 follows, with the asset-reading oracle change in place. Two findings
came out of leg 1 that the coordinator needs before this lands:

- the reader PDF is NOT byte-reproducible run to run (cairo XObject names),
  so "compare byte-for-byte on the PDF" is unsatisfiable by any change; the
  comparison was done with `mag parity --pre-rendered`, against a
  render-to-render noise floor, with negative controls on both legs;
- the asset-reading change **cannot land by itself**. The renderer works from
  a staged copy of declared inputs only, so `mag/src/render.rs` must also
  declare `editions/<id>/source-codes`. Owns was extended to that file for
  the staging row, and the two Python files and the Rust row landed together
  for that reason.

**pygments (revision 32).** Decided on its own terms: no ladder clause
inspects the web tree's spans, and the plan had ALREADY settled the analogous
question for print, where pygments is compared against syntect at the
(text-run, fill colour) level and never at markup level. So the web-tree
oracle is byte-identical EXCEPT those spans, which is consistency with an
existing decision rather than a new concession. The sizing below was taken
before that decision and is kept as context.

### The second blocker, found before building against it

`html_edition.py:681` `_highlight_code` calls **pygments**
(`HtmlFormatter(nowrap=True)`), so byte-identical web HTML requires
reproducing pygments' token markup exactly. Edition 010 does NOT exercise it:
its web tree contains **zero** `<pre>` blocks and **zero** pygments token
classes across all eleven files. So the corpus cannot reach the branch, the
corpus rule requires covering it by fixture, and covering it means
reproducing a second Python library byte-for-byte. Measured in five minutes
rather than discovered after building 600 lines, which is the discipline this
execution keeps paying for.

This one is NOT settled by revision 30's reasoning. That decision turned on
the QR modules being inside Tier E's compared domain; highlighted code is
`<span class="...">` markup in the WEB tree only, which no ladder clause
inspects. So it needs its own disposition and should not inherit the QR
answer by analogy.

### Sizing the pygments problem, measured rather than estimated

The question is not whether to reproduce a library. It splits cleanly, and
the two halves have very different costs.

**The FORMATTER is trivial.** `HtmlFormatter(nowrap=True)` emits nothing but
`<span class="TOKEN">escaped text</span>` concatenated, newlines preserved,
no wrapper element, no line numbers. Verified structurally over all 106
corpus blocks: stripping every span leaves only HTML-escaped text, with no
other markup anywhere. That half is a few lines.

**The LEXERS are the whole problem.** Over the 106 fenced blocks in
`library/sources/*/article.md`, pygments emits **8,559 spans** drawing on
**31 distinct token classes**. The class set is small and enumerable, but
producing the right class per token means reproducing pygments' lexer state
machines. Per language: ts 19 distinct classes, js 14, rust 10, sh 10, toml
9, sql 8, yaml 7, json 6, bash 4.

| language | blocks |
|---|---|
| ts | 47 |
| sh | 19 |
| js | 12 |
| jsonc | 7 |
| toml | 6 |
| rust | 5 |
| bash | 3 |
| txt, sql, json | 2 each |
| yaml | 1 |

Four measurements that bear on the decision:

- **Two languages need no lexer at all.** `jsonc` and `txt` raise
  `ClassNotFound`, so `_highlight_code` falls through to
  `escape(folded, quote=False)` and emits plain escaped text with no spans.
  Nine languages need faithful lexers.
- **`syntect` is not a shortcut.** It uses Sublime syntax definitions with a
  different token model and different class names, so it would not match
  pygments' output. As with segno, there is no off-the-shelf path.
- **Some tokens are compound**: yaml emits `class="l l-Scalar l-Scalar-Plain"`
  and `class="p p-Indicator"`, so the formatter writes multi-class strings.
- **`err` appears 6 times**, meaning pygments' own lexers give up on some
  corpus input. Byte-identity requires reproducing WHERE each lexer fails,
  not only where it succeeds.

**This is LIVE, not counterfactual.** WP-5.7 could be re-scoped because
committed `article.md` files are never re-derived, making byte-identity a
claim about future captures only. Here the opposite holds: web trees are
untracked build artifacts, so nothing is frozen, and while edition 010
happens to carry no fenced code, editions 004 through 008 all do (004 alone
has 17 manuscripts with fenced blocks). Any future edition with a code block
hits this path the moment it is rendered to web.

So the disposition is a real choice with a measured price: nine lexers
reproduced faithfully including their failure points, against changing what
the web tree's oracle guarantees for highlighted code. Not sized here, and
deliberately not built.

## Metrics

### Leg 2 of the committed-asset decision: what regenerates a code

Revision 32 asks this WP to prove two legs before any asset is committed.
Leg 2 is answered here; leg 1 is answered further below.

> **CORRECTION, after leg 1.** This section as first landed traced the wrong
> call site and therefore measured the fit at the wrong room. The numbers
> below that depend on `room = 55.5` are corrected in "The room correction"
> immediately after this section; the 9-of-9 agreement survives, the 154/155
> boundary does not. Read the two sections together.

**Exactly three segno call sites exist**, and the print path uses segno
TWICE per code, for two different purposes:

| site | purpose |
|---|---|
| `web_edition.py:236` | the web SVG, `error="L"` (segno boosts it) |
| `weasyprint_adapter.py:1907` | inside `_fitted_source_code`, a SEARCH over levels |
| `weasyprint_adapter.py:1920` | `_source_code_matrix`, redraws from the chosen level |

The search is the part an asset must satisfy, not just the output. It loops
`_CODE_ERROR_LEVELS = ("H","Q","M","L")`, takes each symbol's module count
via `symbol_size(border=4)`, computes `module = room / modules`, skips any
level below `_CODE_MIN_MODULE_POINTS` (0.35 mm = 0.9921 pt) and keeps the
level with the LARGEST module. `_MODULE_EPSILON` is 1e-9. The room is NOT a
constant (corrected below), but the fit result is a pure function of the
payload regardless, and so is recordable.

**So an asset must record more than the payload and the chosen level.** It
needs the payload, the chosen level, the MODULE COUNT and the matrix:
`SourceCode.modules` feeds layout (`module = room / modules`, and
`side = quiet * module`), so recording the fit RESULT bypasses the search
entirely, and the matrix is what `_source_code_source` draws.

**Print and web choose the SAME code, 9 of 9 on edition 010**: same error
level and same version for every article, so ONE asset serves both legs
rather than one per leg. That was not previously verified.

It is not coincidence. The fit maximises module size, which minimises module
count, which minimises version; among levels tying at that version the loop
keeps the earliest in `H,Q,M,L` order, since a tie never exceeds by
`_MODULE_EPSILON`. That is "smallest version, strongest level at that
version", which is exactly segno's boost rule applied to `error="L"`. The
two arrive at the same answer by construction.

**Tested per rule 11, including where it should break.** Sweeping payload
lengths at the real geometry:

| payload length | print fit | web (`error="L"`) | agree |
|---|---|---|---|
| 20 | Q v2 | Q v2 | yes |
| 40 | M v3 | M v3 | yes |
| 60 | M v4 | M v4 | yes |
| 80 | M v5 | M v5 | yes |
| 100 | L v5 | L v5 | yes |
| 120 | L v6 | L v6 | yes |
| 154 | L v7 | L v7 | yes |
| **155** | **none (declines)** | L v8 | **NO** |
| 200 | none (declines) | L v9 | NO |

The boundary is exact and has a reason: at most `55.5 / 0.9921 = 55` modules
fit, so v8 (57 modules with the quiet zone) never fits at any level and
`_fitted_source_code` returns `None`. Above 154 characters the two legs do
not disagree about WHICH code to draw; print draws NO code at all.

Two consequences for the asset format, neither of which is a problem for the
compared edition (010's longest payload is 67 characters):

- one asset per article serves both legs, and it should record the fit
  result rather than the inputs to a search;
- the format must be able to represent "print declines", which is a legitimate
  state rather than an error, or a future edition with a URL over the limit
  will look like a missing asset. The limit is 78 characters for an
  illustrated opener and 154 for a plain one (corrected below).

One further consequence, found while building leg 1: "print declines" is
not uniformly benign. `_opener_source_codes` RAISES on a decline ("cannot
carry a scannable source code ... Shorten the canonical URL"), while
`_opener_credit_code` returns `None` and the field floor becomes 0.0. The
asset must therefore distinguish "declines" from "absent" precisely so the
declining case still raises the ORIGINAL error rather than a
"regenerate source-codes" error. It does: a record whose `print` is null
makes `_fitted_source_code` return `None`, and each caller then behaves as
it did before.

### The room correction, and why the fit does not depend on the room

Building leg 1 falsified a premise of leg 2. The render failed, and the
probe showed the caller I had traced was never reached.

**There are two production rooms, not one.** `_opener_credit_code`
(adapter:1360) is a MEASUREMENT path that always passes
`_CODE_OPENER_SIDE_POINTS = 55.5`. The path that actually places the code is
`_opener_source_codes` (adapter:2047), which chooses per article:

```
room = _ILLUSTRATED_OPENER_CODE_SIDE_POINTS if illustrated else _CODE_OPENER_SIDE_POINTS
```

`_ILLUSTRATED_OPENER_CODE_SIDE_POINTS` is 41.0. `_is_illustrated_article`
is `opener_art is not None`, and all nine of 010's articles have opener art,
so **every code in the compared edition is fitted at 41.0 pt, not 55.5**.
The asymmetry is pre-existing in the oracle (both constants are on
`art_directed` at lines 73 and 227, used at 1362 and 2035); it is not
introduced here, and it is preserved exactly.

That is a rule 11 failure of my own asserted mechanism, caught by running
the thing rather than by reading it.

**What breaks: the boundary.** At 55.5 pt at most 55 modules fit and the
longest payload that can be placed is 154 characters. At 41.0 pt at most 41
modules fit and the longest is **78 characters**. For 010, which is entirely
illustrated, 78 is the number that matters, so the "~154" figure carried
into the plan should read 78 for illustrated openers and 154 for plain ones.

**What survives, and is now stronger than "9 of 9".** The chosen level and
module count do not depend on the room at all. The loop keeps the candidate
maximising `room / modules`, which for a fixed payload is the candidate
minimising `modules`; the room appears only in the floor test, which
discards the LARGEST candidates first. The smallest-module candidate is
therefore never the one discarded unless every candidate is discarded. Ties
break on `H,Q,M,L` order, which is also room-free. So:

> the room decides only WHETHER a symbol is placed, never WHICH symbol.

Measured, not just argued: 499 payloads (lengths 1-199 plus 300 random
URL-shaped strings) against six rooms spanning 20-120 pt. All 499 placed a
symbol at one or more rooms; **0 had a (level, modules) that differed
between rooms**. Negative control, replacing `>` with `<` so the fit prefers
the largest symbol that fits and becomes genuinely room-dependent: **387 of
499 differ**. The test discriminates.

This is why one asset record serves both rooms and both legs, and why
`codes.json` needs no room key. Regenerating 010's asset with the real
per-article room produced a tree byte-identical to the one generated at
55.5, as room-independence predicts.

### Leg 1: both legs on the committed asset render the same

Leg 1 asks that both legs, reading the committed asset, render identically
to the segno-generating code they replace.

**The specified comparison does not work, and the control says why.**
"Byte-for-byte on the reader PDF" cannot be met by ANY change, including no
change at all. Rendering the unchanged `art_directed` tree TWICE gives two
`reader.pdf` files differing in **420,296 bytes**, both diverging at the
same offset (6670476), where cairo writes its image XObject names:

```
BEFORE  /i6006c69ab0976b6591f1c6bc628bf9830 17 0 R
AFTER   /i89ba5982725d5e12cd03192cf18883570 17 0 R
```

Those names are per-run, they appear inside Flate-compressed content
streams, and every later byte shifts. Raw PDF bytes are not a determinism-
stable oracle and no threshold rescues them. The before/after difference
(421,945 bytes, same offset) is indistinguishable from this floor, so it is
reported as "the instrument cannot discriminate here" rather than as a pass
or a fail (rule 10).

**The comparison that does work** is the one the plan already built:
`mag parity --pre-rendered`, which decodes content streams. Same two
unchanged renders, compared that way:

| tier | before vs before |
|---|---|
| S page_count / boxes / text / color / navigation | pass, 0 mismatches |
| G | max dx 0.000 pt, max dy 0.000 pt |
| E glyph positions | pass, 68530 glyphs, 0 violations |
| E display list | pass, 0 pages differ |
| V | max channel delta 0 |

**Result.** Against that floor, before (segno) vs after (committed asset):

- `en/web` recursive byte diff: **identical**, every file;
- every parity tier: **identical to the noise floor**, including 68,530
  glyph positions at 0.000000 pt worst excess, display list 0 pages differ,
  and Tier V max channel delta 0.

**Two negative controls, because a pass here could be vacuous.**

1. *Print leg.* Flip ONE module in one committed matrix
   (`government-rails...`, row 16, column 16, `0` to `1`) and re-render:
   **tier E display list fails, 1 page differs**, Tier V max channel delta
   goes 0 to 241. So the comparison does see a single-module change in the
   printed code. Note Tier V still reports "pass" at worst page fraction
   0.000006, so the display list is the leg that discriminates, not V.
2. *Web leg.* The web SVG passing byte-identical proves nothing on its own,
   because the committed SVG was generated BY segno and would match even if
   `web_edition` had ignored the asset and kept generating. So: perturb the
   committed SVG (`#17191c` to `#ff0000` in one file) and re-render. Exactly
   one file in the web tree changes, the corresponding asset. The web leg
   does read the asset.

Both perturbations were reverted, and the restored asset tree was checked
equal to a fresh generation before the final render.

### Leg 1 is blocked on a file this WP does not own

The renderer never sees the repository. `engine_render_bridge.py:158`
`shutil.copyfile`s each declared input into a stage root and calls
`load_edition(stage_root, ...)`. Edition 010's request declares 47 inputs
(24 art, 9 manuscripts, records, `edition.yaml`) and `source-codes` is not
among them, so a committed asset is INVISIBLE to the renderer no matter what
the Python does.

Closing that needs a staging row in `mag/src/render.rs`, which is outside
this WP's Owns. The evidence above was produced with a 15-line
`stage_source_codes` added in the worktree to prove the mechanism; **it is
not part of this WP's landed change** and is listed as a residual. Whoever
owns `render.rs` should add it, and adding it is arguably correct on its own
terms: it makes the QR asset a declared, reproducible render input exactly
as art already is.

### The error-level boost is reproducible, which was the feared part

The plan records segno boosting the requested `error="L"` on 6 of 9 payloads.
Confirmed exactly, and the boost is NOT the obstacle: `qrcodegen`'s
`boost_ecl` reproduces segno's chosen version AND effective error level on
**9 of 9**.

| effective level | version | mask (segno) | payload len | source id |
|---|---|---|---|---|
| M | 4 | 2 | 62 | government-rails-site-hit-hours-after-cve-patch |
| M | 4 | 7 | 55 | countering-misuse-of-ai-september-2026-anthropic |
| L | 4 | 2 | 67 | an-alignment-assessment-of-recent-cybersecurity |
| L | 3 | 7 | 46 | dario-amodei-we-must-pace-the-frontier |
| M | 3 | 5 | 38 | scenarios-for-our-economic-future |
| M | 2 | 3 | 25 | the-third-era-of-ai-software-development |
| M | 3 | 5 | 38 | towards-self-driving-codebases |
| L | 3 | 2 | 46 | deepseek-v4-1-flash-pushing-the-limits-of-kv-cache |
| M | 4 | 7 | 60 | rapidly-scaling-online-storage-to-serve-over-1-b |

All nine are BYTE mode, as the plan states. Mode segmentation is not a
variable: seven payloads contain no digits at all.

### The matrices are NOT reproducible, and the cause is below the mask

Automatic encoding, `qrcodegen` against segno: **1 of 9 matrices match**.
Masks differ on 7 of 9.

Forcing segno's version, error level AND mask, so only the data layer can
differ: still **1 of 9 match**, 8 differing by 64 to 144 modules. So the
divergence is in the encoded bitstream, not in mask selection.

### Mechanism, tested per rule 11 rather than asserted

Controlled experiment at forced v4-M, same mask, varying only whether the
data stream needs pad codewords:

| case | pad bytes needed | modules differing |
|---|---|---|
| payload `"a" x 62` | none (terminator exactly fills capacity) | **0** |
| payload `"a" x 50` | 12 pad codewords | 158 |

Removing the supposed cause removes the effect. The mechanism is then visible
in `segno/encoder.py:330` `write_padding_bits`:

    buff.extend([0] * (8 - (length % 8)))

When the stream is ALREADY at a codeword boundary this appends **8 spurious
zero bits**, where ISO/IEC 18004 §7.4.10 adds none ("if the bit stream length
is such that it does not end at a codeword boundary"). segno's own docstring
quotes that clause directly above the line that violates it.

In byte mode the stream after a 4-bit terminator is `16 + n*8` bits, which is
always ≡ 0 mod 8, so segno ALWAYS injects one extra zero byte unless remaining
capacity forces the terminator to truncate. That extra byte displaces one pad
codeword and changes every ECC codeword, which is why the differences are
large and why the only natural match (`government-rails`, 508 data bits
against a 512-bit capacity) is the one case with no room for it.

Prediction tested on three FRESH cases not used to form the hypothesis, at
v4-M:

| payload | predicted | modules differing |
|---|---|---|
| `"a" x 62` (terminator truncated, no room) | MATCH | **0** |
| `"a" x 61` (room for the spurious byte) | DIFF | 68 |
| `"a" x 60` (room for the spurious byte) | DIFF | 82 |

Predicted correctly in all three.

### The four brittle matchers, ported structurally (landed)

`mag/src/web/markup.rs` replaces exact-spelling regex with a tag parser that
reads a start tag into a name and an attribute list, then classifies on the
attribute MAP and the class SET, so attribute order, extra attributes, extra
classes and indent depth no longer decide the answer.

Pinned to PYTHON, the strong form of the duplicated-helper rule: the oracle
(`mag/tests/web_markup_expected.json`) is generated by importing the four
real regexes from `magazine.web_edition` and running them over the same
lines. `corpus_shapes_match_the_python_matchers` asserts agreement on all
**12** corpus-shaped cases, so the port is not merely self-consistent.

The divergence is deliberate and enumerated. Over 10 lines carrying an extra
attribute, an extra class, a reordered attribute or a deeper indent, the
Python matchers fail to recognise **8** and the port recognises **10**:

| shape | Python | consequence in the web tree |
|---|---|---|
| `article-tail` with an extra class | not print-only | print-only figure LEAKS into the web |
| `article-tail` with an attribute before class | not print-only | leaks |
| `article-tail` with no trailing attribute | not print-only | leaks (the regex requires a trailing space) |
| `closing-plate` with an extra class | not print-only | leaks |
| source link with an attribute before class | not a source link | no QR installed |
| source link with reordered attributes | print-only, NOT a source link | link DELETED from the web tree |
| opener header with an extra class | not an opener | **the shipped defect: nine QRs vanished** |
| opener header with class last | recognised | works by luck |
| `<article>` with an attribute before id | not a piece | the page is not emitted |
| `<article>` at a deeper indent | not a piece | not emitted |

Two findings from building it, both from the port disagreeing with Python and
Python being right:

- `source_link()` must EXCLUDE an already-installed `opener-source-link`.
  My first version matched it; Python does not, and Python is right, because
  that function's job is to find links still NEEDING a QR. Caught by the
  corpus oracle, not by inspection.
- `is_print_only()` must drop `<a>` with class `source-link` but NOT
  `opener-source-link`. Verified against the shipped tree: exactly 18
  `class="source-link opener-source-link"` survive into 010's web output and
  zero `article-tail` or `closing-plate` do. A naive structural rewrite that
  dropped every `source-link` would have deleted the QR links, which is the
  same defect class this WP exists to fix, inverted.

Per rule 10 the counts are stated rather than implied: 12 corpus cases
compared, all agreeing; 10 divergence cases, 8 of which Python fails to
recognise and 2 of which it happens to handle. The 2 are kept and labelled,
because a divergence table listing only the failures would overstate the
brittleness.

### What this means for the oracle

Byte-identical QR SVGs are not reachable with an ISO-correct Rust encoder,
and neither is the plan's PRIMARY structural oracle, module-matrix equality,
because the matrices themselves differ. Both oracles fail for the same
reason.

Three dispositions, none of which a WP may choose alone:

1. Reproduce segno's spurious pad byte deliberately in a Rust encoder. This
   is the "reproduce a hack to stay equal to a tool we are deleting" category
   the plan has now rejected four times (WP-5.7's pypdf text layer, the
   `_check_unique_art` crash, the critic's text source, reportlab's
   subsetting). It is also narrower than those: one documented deviation from
   a published spec, in an encoder that is otherwise standard, and it would be
   asserted by a test rather than inferred. That makes it the cheapest option
   and the one most in tension with the plan's stated principle.
2. Restate the oracle as the plan's own fallback already anticipates:
   "byte-identical except the nine QR SVGs, which are structurally equal",
   where structurally equal means SAME PAYLOAD, VERSION AND EFFECTIVE ERROR
   LEVEL, but explicitly NOT the same module matrix, since mask and data
   layer both differ. Note this is weaker than the fallback the plan wrote,
   which assumed matrix equality would hold.
3. Keep calling segno. This defeats WP-6.1's target of no Python anywhere and
   the plan rejects it for `pdf2md.py` already.

Option 2 needs one decision the plan has not yet faced: the QR codes are
SCANNED BY READERS, so "decodes to the same URL at a legitimate error level"
may be the property that actually matters, and matrix equality may be the
wrong bar rather than an unreachable one. That is a product judgment about
what the web edition guarantees, not a verification judgment.

## Commands

Regenerate the matcher oracle (imports the four real regexes and runs them
over `mag/tests/web_markup_cases.json`, writing `web_markup_expected.json`):

    cd <worktree> && uv run python -c '
    import json, sys
    sys.path.insert(0, "src")
    from magazine.web_edition import (
        _PRINT_ONLY_LINE, _SOURCE_LINK_LINE, _PIECE_OPENING, _ILLUSTRATED_OPENER_HEADER,
    )
    cases = json.load(open("mag/tests/web_markup_cases.json"))
    out = []
    for c in cases:
        line = c["line"]
        sl = _SOURCE_LINK_LINE.match(line)
        po = _PIECE_OPENING.match(line)
        out.append({"name": c["name"], "corpus": c["corpus"],
            "print_only": bool(_PRINT_ONLY_LINE.match(line)),
            "source_link": None if sl is None else {"indent": sl.group("indent"),
                "source_id": sl.group("source_id"), "href": sl.group("href")},
            "piece_opening": None if po is None else {"kind": po.group(1), "id": po.group(2)},
            "illustrated_opener_header": bool(_ILLUSTRATED_OPENER_HEADER.search(line))})
    json.dump(out, open("mag/tests/web_markup_expected.json", "w"), indent=2, sort_keys=True)'

Then `cd mag && cargo test --test web_markup` (5 tests).

Confirm which source-link forms survive into the shipped tree:

    grep -ho 'class="source-link[^"]*"' <render>/en/web/*.html | sort | uniq -c
    grep -c 'article-tail\|closing-plate' <render>/en/web/*.html

Confirm 010 does not exercise pygments:

    grep -c "<pre" <render>/en/web/*.html
    grep -ho 'class="[a-z]\{1,2\}"' <render>/en/web/*.html | wc -l

Size the pygments surface over every captured source (needs pygments, which
is not a project dependency, hence `--with`):

    cd <worktree> && uv run --with pygments python -c '
    import re, glob, collections
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name
    from pygments.util import ClassNotFound
    FENCE = re.compile(r"^```([a-zA-Z0-9_+-]*)\n(.*?)^```", re.M | re.S)
    blocks = [(l, c) for p in glob.glob("library/sources/*/article.md")
              for l, c in FENCE.findall(open(p).read()) if l]
    classes, spans, unknown = collections.Counter(), 0, set()
    for lang, code in blocks:
        try:
            lexer = get_lexer_by_name(lang, stripnl=False, ensurenl=False)
        except ClassNotFound:
            unknown.add(lang); continue
        out = highlight(code, lexer, HtmlFormatter(nowrap=True)).rstrip("\n")
        found = re.findall(r"<span class=\"([^\"]*)\">", out)
        spans += len(found); classes.update(found)
        stripped = re.sub(r"<span class=\"[^\"]*\">|</span>", "", out)
        assert "<" not in stripped.replace("&lt;", ""), lang
    print(len(blocks), "blocks;", spans, "spans;", len(classes), "classes;",
          "no lexer:", sorted(unknown))'

Leg 2, print-versus-web fit agreement and its boundary (the sweep that
locates 154/155):

    cd <worktree> && uv run python -c '
    import sys; sys.path.insert(0, "src")
    import segno
    ROOM, LEVELS, QUIET = 55.5, ("H","Q","M","L"), 4
    MIN_MODULE, EPS = 0.35*72/25.4, 1e-9
    def fit(payload):
        best = None
        for level in LEVELS:
            sym = segno.make(payload, error=level, micro=False)
            modules = int(sym.symbol_size(border=QUIET)[0])
            if ROOM/modules < MIN_MODULE: continue
            if best is None or ROOM/modules > best[2] + EPS:
                best = (level, sym.version, ROOM/modules)
        return best
    for n in (20, 40, 60, 80, 100, 120, 154, 155, 160, 200):
        p = "a" * n
        f, w = fit(p), segno.make("a"*n, error="L", micro=False)
        print(n, "none" if f is None else "%s v%d" % (f[0], f[1]),
              "%s v%d" % (w.error, w.version))'

Every segno call site (leg 2's enumeration). The scope must include
`tools/`, or the command understates its own caption: replaying it after
`tools/sourcecodes.py` landed returned nothing from `src/ mag/src/` while
four call sites existed in the generator. That is the recorded command
drifting from the claim above it, which is the failure rule 12's replay
clause exists to catch, and it was caught by replaying rather than by
rereading.

    grep -rn "segno" src/ mag/src/ tools/

As of this WP, that returns four hits, all in `tools/sourcecodes.py`
(`import segno` plus three `segno.make` calls) and none in the renderer.
The renderer-only form is `grep -rn "segno" src/ mag/src/`, which returns
nothing and is the claim leg 1 actually makes.

Which editions carry fenced code at all:

    for d in editions/*/; do echo "$d $(grep -rlE '^```[a-zA-Z0-9]+' $d | wc -l)"; done

All Python via `uv run python` (this machine has a second Python 3.9.6 on
Unicode 13.0.0; a bare `python3` gives different answers).

Dump segno's matrices for 010's nine opener sources:

    cd <worktree> && uv run python -c '
    import sys, yaml, json
    sys.path.insert(0, "src")
    import segno
    from magazine.manifest import source_code_payload
    ed = yaml.safe_load(open("editions/010/edition.yaml"))
    rows=[]
    for a in ed["articles"]:
        if a.get("opener_art") is None: continue
        sid = (a.get("source_ids") or [a["id"]])[0]
        rec = yaml.safe_load(open(f"library/sources/{sid}/record.yaml"))
        if not rec.get("url"): continue
        if any(r[0]==sid for r in rows): continue
        rows.append((sid, rec["url"]))
    out=[]
    for sid, url in rows:
        p = source_code_payload(url)
        q = segno.make(p, error="L", micro=False)
        m = ["".join("1" if c else "0" for c in row) for row in q.matrix]
        out.append({"sid": sid, "payload": p, "error": str(q.error),
                    "version": q.version, "mask": q.mask, "size": len(m), "matrix": m})
    json.dump(out, open("/tmp/segno_matrices.json","w"))
    print("dumped", len(out))'

The Rust probe is a throwaway cargo project depending on `qrcodegen = "1.8"`
and `serde_json = "1"`, reading that JSON and calling
`QrCode::encode_segments_advanced(&segs, ecc, v, v, mask, boost)` with
`boost=true` for the automatic comparison and `boost=false` plus segno's
version and mask for the forced-parameter comparison. Full source is in
`## Residuals`; it adds nothing to `mag/` and was not committed.

Controlled padding experiment: same probe against `segno.make("a"*62,
error="M")` and `segno.make("a"*50, error="M")`, forcing each one's own
version and mask.

### Leg 1: generating the asset, rendering, comparing

The generator is committed as `tools/sourcecodes.py`, because the asset it
writes is now committed and nothing else in the tree could regenerate it: a
source URL change would otherwise dead-end, and whoever hit that would
improvise a replacement. It walks `edition.yaml`, resolves each source URL
through `source_code_payload`, writes the web SVG with segno's exact
parameters and records the print fit, choosing the room per article and
emitting a record for every article with a URL. `codes.json` is written with
`sort_keys=True` and `indent=2` so it is diffable. Paths resolve from
`Path(__file__).resolve().parent.parent`, so it reads only its own checkout
and does not depend on the working directory.

    uv run tools/sourcecodes.py 010            # regenerate in place
    uv run tools/sourcecodes.py 010 --check    # compare, touching nothing

**`--check` is verified to reproduce the committed asset byte-for-byte**, not
merely to run: it regenerates into a temporary directory and compares with
`filecmp.cmpfiles(..., shallow=False)`, and reports
`10 files reproduce byte-for-byte` (nine SVGs and `codes.json`). An
unverified generator would be worse than none, since it invites exactly the
trust it has not earned.

It discriminates in both directions, which is the other half of that claim:

| committed tree | `--check` |
|---|---|
| as committed | exit 0, "10 files reproduce byte-for-byte" |
| one field of `codes.json` changed (`error` M to H) | exit 1, "content differs: ['codes.json']" |
| one stray extra file in the directory | exit 1, "file set differs" |
| directory absent | exit 1, "no committed source codes at ..." |

Both perturbations were reverted and `--check` was re-run to exit 0 before
this landed.

The staging row the evidence depends on, added to `mag/src/render.rs` in the
worktree only, called immediately after `stage_art`:

    fn stage_source_codes(staging: &mut Staging, edition_dir: &Path, repo_root: &Path) {
        let rel = edition_dir.join("source-codes");
        let Ok(entries) = fs::read_dir(repo_root.join(&rel)) else { return };
        let mut names: Vec<_> = entries.flatten()
            .filter(|e| e.path().is_file()).map(|e| e.file_name()).collect();
        names.sort();
        for name in names { staging.add(&rel.join(name)); }
    }

The held-back Python, so it does not have to be re-derived. In
`web_edition.py`, three new module-level names and one replaced block:

    @dataclass(frozen=True, slots=True)
    class CommittedSourceCode:
        directory: Path
        payload: str
        svg: str
        error: str | None
        modules: int | None
        matrix: tuple[str, ...]

    def source_code_directory(anchor: Path) -> Path | None:
        for parent in [anchor, *anchor.parents]:
            if (parent / "edition.yaml").is_file():
                return parent / "source-codes"
        return None

    def committed_source_codes(directory: Path) -> dict[str, CommittedSourceCode]:
        reads codes.json, keyed by payload, {} when the file is absent

    def committed_source_code(anchor: Path, payload: str) -> CommittedSourceCode | None:
        directory = source_code_directory(anchor)
        return None if directory is None else committed_source_codes(directory).get(payload)

`_materialize_source_codes` then replaces its `segno.make(...).save(...)`
block with a lookup on `article.manuscript` and a `write_bytes` of the
committed SVG, raising when the asset is missing.

In `weasyprint_adapter.py`: `SourceCode` gains `anchor: Path | None = None`;
`_fitted_source_code` gains an `anchor` parameter, reads the asset instead
of looping over segno, RAISES when the asset is absent and returns `None`
when `asset.error is None` (so each caller keeps its original behaviour on a
decline); `_source_code_matrix` reads `asset.matrix` and
`_source_code_source` passes `code.anchor`. Both call sites pass
`article.manuscript` as the anchor, including `_opener_source_codes` at
:2047, which is the one the first pass missed. `import segno` disappears
from the adapter entirely.

`article.manuscript` is the anchor rather than `article.opener_art.path`
because it is total: every article has a manuscript, only illustrated ones
have opener art, and print needs an asset for articles web skips.

Baseline, from a pristine worktree at `a0714c3` so no in-progress edit can
contaminate it, rendered twice to establish the noise floor:

    git worktree add <before> a0714c3
    cd <before> && ./mag/target/debug/mag render 010     # twice
    ./mag/target/debug/mag parity 010 --pre-rendered <run1> <run2>

After, and the comparison:

    cd <after> && uv run python genasset.py 010
    ./mag/target/debug/mag render 010
    diff -rq <before>/…/en/web <after>/…/en/web
    ./mag/target/debug/mag parity 010 --pre-rendered <before-run> <after-run>

Negative controls: flip one character of one `matrix` row in `codes.json`,
re-render, expect `tier E display list: fail (1 pages differ)`; and replace
`#17191c` with `#ff0000` in one committed SVG, re-render, expect exactly one
differing file in the web tree. Revert both and check the restored tree
equals a fresh `genasset.py` run before the final render.

Room-independence sweep: for each of 499 payloads (`"h"*n` for n in 1..199,
plus 300 random strings of length 1..200 over
`[A-Za-z0-9:/.\-_?=&]`, seed 11) run the `_fitted_source_code` loop at rooms
20, 30, 41, 55.5, 80 and 120, and compare the resulting `(level, modules)`
across rooms. Negative control: flip the comparison to `<` so the loop
prefers the largest fitting symbol.

## Tool versions

- segno 1.6.6
- Python 3.12.11 (`uv run python`)
- qrcodegen 1.8.0
- rustc 1.96.0

## Verdicts

Leg 1 produced three `mag parity` runs on edition 010. All tiers reported
below are from `output/parity/010/verdict.json`; `tier E raster` is
`not_evaluated` in every run, pending WP-0.2d's `raster_bound` derivation.

| comparison | display list | glyph positions | tier V max channel delta |
|---|---|---|---|
| before vs before (noise floor) | pass, 0 pages | pass, 68530 glyphs, 0 violations | 0 |
| before vs after (committed asset) | pass, 0 pages | pass, 68530 glyphs, 0 violations | 0 |
| before vs one flipped module (control) | **fail, 1 page** | pass, 0 violations | **241** |
| re-run at the landing base | pass, 0 pages | pass, 68530 glyphs, 0 violations | 0 |
| re-run at `c1253d8`, provenance-checked | pass, 0 pages | pass, 68530 glyphs, 0 violations | 0 |

### The provenance-checked run, and the concurrency hazard

The comparator changed AGAIN after the landing-base run: WP-0.2g touched
`mag/src/parity.rs`, `display.rs` and `geometry.rs`. By the standing reason
above that invalidates the measurement, so the pair was rendered a third
time at `c1253d8`. The "before" leg is `c1253d8` with only this WP's three
code files reverted to their `a3fb35c` content, which is the true
counterfactual: the branch as it stands, minus this change alone.

**The numbers are tied to the artifacts that produced them.** The digests
computed independently with `shasum -a 256` over the two rendered PDFs are
the same two the comparator recorded in `verdict.json`'s `inputs` block:

| leg | `reader.pdf` sha256 |
|---|---|
| A, before (segno) | `0460c081226ea530fcb8431c61f202f18530b7f1d88a865a794502451dd89e83` |
| B, after (committed asset) | `15d3bd5aef0dfb1f2c989c565686fb992dc9966d517e21414b25db55c0d98200` |

`verdict.json` carries `a_reader_sha256` and `b_reader_sha256` and nothing
else scalar at top level beyond `edition`, `mode` and `self_comparison`;
there is no `staged_input_digest` field yet, so that half of the provenance
claim cannot be quoted from this comparator.

**On the shared-`out_dir` hazard.** `mag parity` refuses to run outside a
repo root, so an "isolated cwd" cannot be an arbitrary scratch directory: it
has to be a separate WORKTREE, and the isolation comes from that worktree
having its own `output/`. Every parity run behind this WP's numbers, the
three earlier ones included, was executed from `wp55a` or `wp55a-before` and
never from the main tree, so none of them shared an `out_dir` with the
agents working there. That is an argument about where the runs happened
rather than a proof the old `verdict.json` files were never overwritten,
which is why the run above was redone from scratch with digests rather than
defended.

**Rule 10a is visibly satisfied by the new comparator**, which is worth
recording because it converts three of these rows from unfalsifiable to
checkable: tier S now reports 162 boxes and 54 rotations, 1,733 colour
entries, and 85 annotations of which 85 links. A clause that says how much
it compared cannot pass by comparing nothing.

The last row matters because the first three were measured at `ee15768` with
the baseline taken from `a0714c3` (a plan-markdown-only difference, checked:
`git diff --stat ee15768 a0714c3` touches one file under `meta/plans`).
`mag/src/parity.rs` and `mag/src/parity/streams.rs` then changed under other
WPs, so the pair was rendered again at the actual landing base with the
current comparator, and the web tree is byte-identical there too.

**Re-measure after the comparator moves, and the reason is that the failure
is silent.** A parity result is a claim about a (code, comparator, corpus)
triple, and only the code is visible in the diff being reviewed. When the
comparator changes underneath a measurement, the stale number does not
become an error or a warning; it stays a passing row in a table, indexed to
a comparator that no longer exists. Nothing in the tree can detect that, and
the evidence file will read as complete. So the check is cheap insurance
against a class of defect that has no other detector: before submitting,
diff your measurement base against the landing base restricted to the code
and the comparator, and re-render if it is non-empty. That is the second
time in this execution this has mattered, which is why it is written here as
a standing reason rather than as a step that happened to be taken.

**The rule 10 diagnostic edge, applied to the instrument this WP rejected.**
Labelling the raw-PDF-byte comparison non-discriminating is a claim that
needs its own opposite-extreme test, or the label is just an excuse. Running
it across the full range of real inputs:

| input pair | raw-byte verdict |
|---|---|
| a file against itself | identical |
| two renders, no semantic change | differs |
| two renders, one flipped QR module | differs |

So it does not merely have a high noise floor; it returns "differs" for
every pair of distinct renders and "identical" only for physical identity.
The output is a constant over the inputs that matter, carrying zero bits
about semantic change. The correct reading is that the instrument does
nothing, rather than that the renderer does nothing, which is the
distinction the rule asks to be drawn explicitly.

Tier S (page_count 56 vs 56, boxes, text, color, navigation) and tier G
(max dx and dy 0.000 pt) pass in all three, including the control: a single
QR module moves no text and no box, which is why the display list rather
than S, G or V is the leg that discriminates here.

### Port increment 1: the three text helpers

`mag/src/web/text.rs` ports `html_edition.py`'s `_text`, `_verbatim` and
`_attr`, the leaves every HTML string in the web tree passes through, plus
the `html.escape` they share. `fold_reader_characters` and
`educate_reader_quotes` already existed in `model::doc` and are reused;
Python computes the settable set internally while Rust takes it as a
parameter, which is WP-5.1a's dependency injection rather than a divergence.

**The fixtures split on the AUTHORED versus TRANSCRIBED axis, and the file
says which is which.** `html.escape`'s contract is short and documented, so
its ten rows were written from the spec, BEFORE running Python, and then
checked against CPython: 20 of 20 expectations agree. Because they were
authored, a disagreement would have indicted either the port or my reading
of the spec, rather than silently inheriting whatever CPython does.

The ten `text`/`verbatim`/`attr` rows are TRANSCRIBED from CPython and the
provenance block says so, along with what they therefore cannot see: they
cannot detect a case where Python itself is wrong, because
`educate_reader_quotes`'s quote-direction algorithm is too intricate to
author by hand. What they do pin is the composition order and the quote flag
per helper, which is where a port actually goes wrong.

**Rule 10c is applied and annotated.** Four rows have an expected value
equal to the input (`double_quote_splits_on_flag` and
`single_quote_splits_on_flag` unquoted, `empty`, `no_special_characters`).
Each is marked in the file as proving only that escaping added nothing, and
each quote row is PAIRED with its quoted form, which differs. The rows
carrying the evidence are the ones where output differs from input.

**The discriminating row is `ampersand_first`.** Input `&lt;` must become
`&amp;lt;`, which holds only if `&` is replaced before `<` and `>`. A port
that replaces `<` first passes every other row in the file. It has its own
committed test with an `assert_ne!` against the wrong answer, so the guard
states what would make it fail and commits a case that does.

**Mutation sweep: 7 injected defects, 7 caught, 0 survived.**

| mutation | caught |
|---|---|
| escape `<` before `&` | yes |
| `&apos;` instead of `&#x27;` | yes |
| quote flag ignored, always quote | yes |
| quote flag ignored, never quote | yes |
| `text` drops the quote education | yes |
| `attr` uses `quote=false` | yes |
| `>` not escaped | yes |

Two rows earn their place by making the helpers non-interchangeable:
`he said "no" today` gives `he said “no” today` through `text` but keeps
straight quotes through `verbatim`, and `a 中 b` folds to `a ? b` while
`café` survives, so the settable filter is shown discriminating rather than
passing everything.

The oracle regenerator is `tools/webtextoracle.py`, which fails loudly if a
spec-authored row disagrees with CPython instead of overwriting it.

### The WP-2.1 collision, and what the lift found

WP-2.1 landed `mag/src/typeset/content.rs`, which ports the same
`render_html_edition` this WP is built on, so `ui`, `clamp_roster`,
`is_name_roster` and `content_label` already existed in Rust. Under a scoped
Owns extension they are now lifted into `mag/src/model/shared.rs` and
`content.rs` imports them.

**Why lifting rather than importing from `crate::typeset::content`.**
`content.rs` emits Typst markup; this WP's target is HTML that must be
byte-identical to `html_edition`. Importing would make the web oracle depend
on the typesetting emitter, so a change made for Typst's benefit could break
a byte-identity claim in a path that has nothing to do with typesetting, and
nobody would notice until it failed. The four helpers emit neither format:
two are string rules, one is a translation table, and `content_label` picks
a declared label or falls back to `ui`. The direction already existed
(`content.rs` imported from `crate::model::shared`, and `content_label`
already called `py_str`), and WP-5.1d and WP-5.1e set the precedent. It also
dissolves the duplicated-helper pinning problem rather than managing it: one
copy pinned to its own Python oracle beats two that can agree while both are
wrong.

The lift is behaviour-neutral, which WP-2.1's own committed projection
oracle checks: all 17 test binaries pass unchanged, including the
`content.rs` tree oracle and its `clamp_roster` straddle test. One signature
changed, because it had to: `content_label` took `&Document`, which would
have made `shared.rs` import `model::doc` while `doc.rs` already imports
`shared`. It now takes `&Mapping`, the only field it ever used.

**A LATENT DIVERGENCE found while lifting, NOT fixed here.**
`is_name_roster` uses `str::trim` and `split_whitespace()` where Python uses
`.strip()` and `.split()`. Those disagree: sweeping all 1,114,112
codepoints, Python's `str.isspace()` holds for 29 and Rust's
`char::is_whitespace()` for 25, and the difference is exactly
**U+001C, U+001D, U+001E, U+001F**, one-directional (Python calls them
space, Rust does not). `shared.rs` already carries `is_python_space` for
precisely this, so the pinned form exists and is simply not used here.

It changes the ANSWER, not just the internals. With U+001E written `<RS>`:

| input | Python | Rust |
|---|---|---|
| `a b c d e f<RS>g • C D • E F` | `False` | `true` |
| `<RS> • C D • E F` | `False` | `true` |
| `A<RS>B • C D • E F` | `True` | `true` |

The first crosses the six-word limit (Python splits into seven words, Rust
into six); the second strips to empty for Python but not for Rust. The third
agrees, and is kept as the control showing the fixture shape itself is not
what produces the disagreement.

Per rule 3b: **the defect is LIVE on the branch**, now in
`mag/src/model/shared.rs` and previously in `mag/src/typeset/content.rs`.
Consumers who must not build on the current behaviour are WP-2.1's
contents-entry author rendering, WP-2.2a (building on `content.rs` now), and
this WP's own web port. It is unreachable from the corpus: scanning all 833
YAML and Markdown files under `editions/` and `library/sources/` finds ZERO
occurrences of those four codepoints, so it cannot fire on edition 010 and
is latent rather than active. It is left unfixed because repairing it is a
behaviour change outside the lift's granted scope, and a lift that silently
alters behaviour is the thing the narrow grant existed to prevent.

### Port increment 2: `render_html_edition` and `write_web_edition`

`mag/src/web/semantic.rs` ports `html_edition.py` (semantic HTML plus the
asset inventory) and `mag/src/web/edition.rs` ports `web_edition.py` (asset
and source-code materialisation, source-code installation, print-only drop,
provenance numbering, source rewriting, figure links, document paging, cover,
masthead, colophon, page turns, index, edition.html, stylesheet and font
copy). `text.rs` gained an `Escaper` so both modules share one set of
escaping helpers. The web side's `_text` is `verbatim` (no quote education),
which the port keeps.

**The oracle shells the real Python from `cargo test`**
(`mag/tests/web_port.rs`), per the Phase 5 preamble. The test stages a root
in `CARGO_TARGET_TMPDIR` by HARD LINKS (library/sources, 010's art and
source-codes, the fixture edition) plus copies of 010's manifest and its
nine manuscripts from `editions/010/run-2026-09-13T01-34-51`. Hard links,
not symlinks, because Python's `safe_project_path` resolves symlinks and
would refuse a symlinked stage, and file URIs would then differ. The
inline Python programs are the `PYTHON` and `WEB_PYTHON` constants in that
file, recorded there verbatim.

Results, `cargo test --test web_port`: exit 0, 13 passed.

| comparison | result |
|---|---|
| 010 semantic HTML | byte-identical; 27 assets equal field by field (9 openers, 9 tails, 3 figures, 5 plates, 1 cover) |
| 010 web tree | 51 files byte-identical, 11 HTML pages, 9 source-code SVGs |
| 010 web tree vs a PRODUCTION render | `diff -rq editions/010/render-2026-09-23T22-57-54/en/web <rust tree>` exit 0 (render made by the main tree today, not by this test) |
| negative control for that diff | the `010_chrome` tree against the same render differs on every page (exit 1 from diff) |
| fixture `wfx` semantic HTML + web tree | byte-identical, 28 files |
| `chrome` (wordmark, favicon, headline lines, two alternates) | byte-identical, 30 files |
| `mismatch` (headline lines that do not re-join to the headline) | byte-identical; falls back to the plain headline |
| `010_chrome`, `010_mixed` (article 2 stripped of opener art), `nourl` (one source without an address) | byte-identical |
| `dup_keyed`, `dup_tailed` (collision refusals) | refusal messages equal to Python's, character for character |

**Corpus-unreachable branches, enumerated from the Python and covered by the
`wfx` fixture** (`mag/tests/web_port_fixtures/wfx`): `_render_editorial`,
`_render_section` (a titled glossary and an untitled try_it),
`_render_extract` (code and quote styles), `_extracts_by_anchor` (opener and
heading anchors), `_render_key_ideas`, `_highlight_code`'s no-language
branch, the non-illustrated `_render_article` path (author note, provenance,
end-of-article source link, tail art with `tail_art_fit: contain`), the
subtitle, a declared manuscript label, name rosters as standfirst and as
body, reference lists under `References` and `Referencias`, ordered lists
with and without `start`, block quotes, a titled link, inline code with
quotes, hard breaks and a rule, a roster-clamped author. `010_mixed` reaches
the non-illustrated path INSIDE an illustrated edition, which is also the
only input where `_install_illustrated_source_codes` must close its opener
window (a later source link outside the header must stay print-only).

**Straddle pairs** (rule: one step apart, one refuses, one passes):
contents title 62 passes / 63 refuses; contents density 8 entries plain / 9
tight; plate aspect 1000x586 passes / 1000x584 refuses at the upper bound
and 1000x2343 passes / 1000x2345 refuses at the lower. Each is compared
against Python, not only asserted.

**Mutation sweeps.** `semantic.rs`: 8 injected, 7 caught on the first run;
the survivor (density `>` to `>=`) exposed that no input had exactly 8
entries, so the 8/9 pair was added and it is now caught. `edition.rs`: 10
injected, 7 caught on the first run. Two survivors were real coverage gaps
and are now caught: the unaddressed provenance `<span>` branch (every corpus
source has a URL; the `nourl` spec added) and the opener window never
closing (every 010 article is illustrated; `010_mixed` added). The third,
`replace_all` to `replace` in `link_figures`, is an EQUIVALENT mutant: a
figure line carries exactly one `<img>` by construction, so no input can
tell them apart.

**Deliberate narrowings and refusals, each loud rather than silent:**

- fenced code WITH a language bails ("needs pygments highlighting, which the
  web port does not reproduce yet"); tested. Python would highlight. This is
  the revision-33 decision still open; zero editions carry fenced code.
- closing plates are read as PNG only (IHDR); Python uses PIL, which also
  reads JPEG and others. All 109 `art_path` values under `editions/` end in
  `.png` (`grep -h art_path editions/*/edition.yaml`), so no edition is
  affected, but the port is narrower than its oracle and refuses a JPEG
  plate that Python would accept. The fix is to share
  `package/preflight.rs`'s `raster_dimensions`, which is WP-5.5b's file.
- the structural matchers from `markup.rs` replace the four brittle regexes
  inside the pipeline, as the WP prescribes; on every compared input the
  outputs are identical.

**Duplicate-helper finding, for the coordinator.** The `rust_helpers` lint
caught `anchor_key`, `is_reference_heading`, `inline_text` and
`article_opener_format` also defined in `mag/src/typeset/content.rs`, which
this WP may not touch. They are NOT all the same function: `content.rs`
strips with `str::trim`, which disagrees with Python's `strip()` on
U+001C..U+001F (the same divergence recorded above for `is_name_roster`),
and its `article_opener_format` turns a YAML null into `"None"` where Python
gives `""` (harmless today, since the value is only compared against the
illustrated constant and the loader validates it). The web copies are the
Python-exact forms and are named `py_anchor_key`, `py_is_reference_heading`,
`py_article_opener_format`; `plain_text` is a genuine duplicate of
`content.rs`'s `inline_text`. Lifting all four into `model/shared.rs` and
pointing `content.rs` at them needs an Owns extension over
`typeset/content.rs`, and would fix the U+001C..U+001F divergence there.

**Equality is not correctness: shared defects looked for, none found beyond
those already recorded.** Not a proof: the two outputs are generated by the
same algorithm, so a wrong design choice common to both (for example that
illustrated articles carry no provenance line on the web, so 010's web tree
names no sources outside the QR) would pass. That one reads as design, not
defect, and is noted for Fran rather than changed.

### What is and is not proven (increment 2)

Proven: for edition 010 as staged from its committed run, and for the
fixture specs listed, the Rust semantic HTML, asset inventory and complete
web tree are byte-identical to the Python modules they port, and the 010
tree is byte-identical to a production render's `en/web`. Each threshold
the modules guard is pinned by a one-step straddle compared against Python.

Not proven: behaviour on fenced code with a language (refused), on non-PNG
plates (refused), on translated editions (not in the oracle), on inputs
that would reach the unfixtured shape refusals, and correctness of any
choice the two implementations share by construction. Nothing here says the
binary produces this tree: it does not call the port yet.

### Commands (increment 2)

    cd mag && cargo test --test web_port          # exit 0, 13 passed
    cd mag && cargo test                          # exit 0, 28 binaries ok
    cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings   # clean
    diff -rq editions/010/render-2026-09-23T22-57-54/en/web \
      mag/target/tmp/web-port-stage/rust-web/010  # exit 0

## Residuals

- **What remains after increment 2**: (1) wiring: nothing in the binary
  calls `write_web_edition`; the production web tree is still written by
  `engine_render_bridge.py`, and switching it is `render.rs`, WP-5.6's file,
  so `#[allow(dead_code)]` on `web.rs` stays until then; (2) pygments
  highlighting (refuses loudly, see above); (3) non-PNG closing plates; (4)
  translations: 010 has none, so `load_translation` output is not in the web
  oracle, though nothing in either module branches on language beyond `ui`;
  (5) unfixtured refusals that the semantic renderer cannot produce: the
  reserved-name page collision (every piece id is prefixed `article-`,
  `section-` or is `editorial`), the source-code filename collision, and
  `_parse_document`'s shape refusals, all ported and all reachable only if
  the renderer changes shape.
- *(increment 1 text, superseded by the entry above)* **What remains of the port**, in dependency order: `html_edition.py`'s
  `render_html_edition` path (~45 functions, 875 lines) produces the semantic
  HTML that `web_edition.py`'s pipeline (~30 functions, 755 lines) transforms,
  so the former comes first. The four matchers are done; the rest of
  `web_edition.py` is the document pipeline (`_parse_document`,
  `_cover_lines`, `_colophon_lines`, the page writers) and asset
  materialisation. That is roughly 1,600 lines of Python to port with a
  byte-identical bar, and it is a multi-session build rather than a long
  afternoon: it is the largest remaining port in Phase 5.
- **Edition 010 exercises a narrow slice of it**, which matters for how the
  corpus rule applies here: 9 articles, 5 closing plates, 3 figures, content
  modes `article` and `verbatim`, `cover.layout: footer_caption`, and ZERO
  editorial, ZERO sections, ZERO extracts, ZERO key_ideas, ZERO fenced code.
  So `_render_editorial` (1), `_render_section` (2), `_render_extract` (3),
  `_extracts_by_anchor` (4), `_render_key_ideas` (5) and `_highlight_code`
  (6) are all unreachable from the corpus: SIX functions, counted off the
  list rather than asserted beside it. The 010 oracle would prove nothing
  about any of them. `_render_editorial` is the worst case of the six,
  because it is dead for editions 010 and later by policy but live for 001
  through 009, so it is reachable code with zero corpus coverage rather than
  code that is merely unused. Whoever builds this should expect the fixture surface to be
  larger than the corpus surface, and should inherit the blocked WP-5.5's
  per-module enumeration (commit 6a9b5cf) rather than re-deriving it.
- **LEG 1 IS PROVEN and the oracle change is landed.** See "Leg 1" above:
  the web tree is byte-identical and every parity tier matches the
  render-to-render noise floor, with negative controls on both legs.
- **`mag/src/render.rs` carries a `stage_source_codes` row**, landed with the
  Python under an extended Owns. Without it the committed asset is never
  copied into the stage root and the renderer cannot see it, so the
  asset-reading change could not land alone: doing so breaks every render
  with "No committed source code". The function reads
  `editions/<id>/source-codes`, sorts by filename for determinism, and is a
  no-op when the directory is absent, so editions without an asset are
  unaffected. WP-5.6 inherits that shape; note it stages a DIRECTORY by
  enumeration rather than naming files from the manifest, which is unlike
  every other `stage_*` in that file. What FORCES the change is a stale or
  foreign file in `source-codes`: enumeration stages whatever is on disk, so
  an SVG left behind by a removed article, or one hand-added, silently
  becomes a declared render input and lands in `edition-manifest.json`'s
  input list. Manifest-declared membership becomes necessary the first time
  that input list is used as a provenance claim rather than as a copy
  instruction. `tools/sourcecodes.py --check` detects exactly this (its
  file-set branch), so running it in CI would hold the line meanwhile.
- **The reader PDF is not byte-reproducible across runs**, which is a
  general finding, not specific to this WP. Cairo's image XObject names
  (`/i<hex>`) are per-run and sit inside compressed streams, so two renders
  of identical inputs differ in ~420 KB. Any future WP told to compare
  "byte-for-byte on the PDF" should use `mag parity --pre-rendered` instead
  and say so rather than reporting a spurious fail. Worth checking whether
  WP-0.1's determinism proof covered the PDF bytes or only the display list;
  if the former, it needs revisiting.
- **A LATENT BUG IN THE PYTHON, recorded and deliberately NOT fixed.**
  `_opener_credit_code` computes the opener field floor from a symbol fitted
  at 55.5 pt even for illustrated articles, which `_opener_source_codes` then
  places at 41.0 pt. For 010 this is harmless because the chosen symbol is
  room-independent (proved above) and both rooms place a symbol, but a
  payload between 79 and 154 characters would make the measurement path
  reserve space for a code the production path then refuses to place, and
  `_opener_source_codes` raises rather than degrading. This is a bug in the
  ORIGINAL, not a port question: revision 23's rule is that a port may not be
  stricter than its original, so the asymmetry is reproduced exactly and the
  fix belongs to whoever owns the Python renderer.
- **`_opener_source_codes` iterates every article with a `source_url`**,
  illustrated or not, and fit-checks all of them while appending only the
  illustrated ones. `_materialize_source_codes` (web) skips non-illustrated
  articles entirely. So print's asset requirement is a SUPERSET of web's;
  they coincide on 010 only because all nine articles are illustrated. The
  generator writes a record for every article with a URL, not just the
  illustrated ones, for that reason.
- **The QR encoder is no longer the plan's route**, but if the fallback is
  ever taken: Revision 30 decided to
  reproduce the deviation; the specification is eight spurious zero bits at
  `segno/encoder.py:330` when the post-terminator stream sits on a codeword
  boundary, which in byte mode is always, since that stream is `16 + n*8`
  bits. Note `qrcodegen` cannot be used as-is: padding is internal to
  `encode_segments_advanced`, with no hook, so reproducing the deviation
  means owning the bitstream (mode, count, terminator, pad), the Reed-Solomon
  ECC, mask selection and the matrix layout. Its `boost_ecl` reproducing
  segno's version and level 9 of 9 is still useful as an independent check on
  whatever is built.
- **A structural QR check already exists and should be kept** alongside
  byte-identity, per WP-5.4's dual-oracle argument: payload, version and
  effective error level, which is what the probe in this evidence measures.
- **segno's pad-bit deviation is worth reporting upstream** and is not
  specific to this project: any encoder comparing against segno will hit it.
  It is reproducible in three lines.
- **The probe source** (throwaway, not committed):
  `Cargo.toml` with `qrcodegen = "1.8"`, `serde_json = "1"`; `src/main.rs`
  reads the dumped JSON, rebuilds each code with
  `QrSegment::make_segments(payload)` and
  `QrCode::encode_segments_advanced`, renders the matrix with
  `qr.get_module(x, y)`, and counts differing modules.
- **Cargo.lock only-gained check: not applicable.** No crates were added to
  `mag/`; the probe lived outside the repository, and the landed increment
  uses only `serde_json`, already present.
- **`mag/src/web.rs` carries `#[allow(dead_code)]`** because nothing in the
  binary consumes `markup` yet; the pipeline that will is the remaining half.
  Remove it when `web_edition.py`'s pipeline lands.
- No f32 exposure: this WP did no arithmetic on lopdf-parsed numbers.
