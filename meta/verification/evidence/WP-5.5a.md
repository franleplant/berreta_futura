# WP-5.5a web edition

## Base

4f20801 (plan revision 29 at branch time; revision 30 decided the QR question mid-WP)

## Status

blocked, with one landed increment

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
same asset, so Tier E is satisfied without reproducing a bug. Leg 2 of that
decision is proven below; leg 1 is not, and is what this WP owes next.

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
Leg 2 is answered here; leg 1 is not (see Residuals).

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
level with the LARGEST module. Every input is a constant
(`room = _CODE_OPENER_SIDE_POINTS = 55.5`, `_MODULE_EPSILON = 1e-9`), so the
fit is a pure function of the payload and its result is recordable.

**So an asset must record more than the payload and the chosen level.** It
needs the payload, the chosen level, the MODULE COUNT and the matrix:
`SourceCode.modules` feeds layout (`module = room / modules`, and
`side = quiet * module`), so recording the fit RESULT bypasses the search
entirely, and the matrix is what `_source_code_source` draws.

**Print and web choose the SAME code, 9 of 9 on edition 010** — same error
level and same version for every article, so ONE asset serves both legs
rather than one per leg. That was not previously verified.

It is not coincidence. The fit maximises module size, which minimises module
count, which minimises version; among levels tying at that version the loop
keeps the earliest in `H,Q,M,L` order, since a tie never exceeds by
`_MODULE_EPSILON`. That is "smallest version, strongest level at that
version" — which is exactly segno's boost rule applied to `error="L"`. The
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
  state rather than an error, or a future edition with a URL over ~154
  characters will look like a missing asset.

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
   LEVEL — but explicitly NOT the same module matrix, since mask and data
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

Every segno call site (leg 2's enumeration):

    grep -rn "segno" src/ mag/src/

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

## Tool versions

- segno 1.6.6
- Python 3.12.11 (`uv run python`)
- qrcodegen 1.8.0
- rustc 1.96.0

## Verdicts

No parity verdicts produced; this WP wrote no Rust and ran no render.

## Residuals

- **What remains of the port**, in dependency order: `html_edition.py`'s
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
  So `_render_editorial`, `_render_section`, `_render_extract`,
  `_extracts_by_anchor`, `_render_key_ideas` and `_highlight_code` are all
  unreachable from the corpus, and the 010 oracle would prove nothing about
  any of them. Whoever builds this should expect the fixture surface to be
  larger than the corpus surface, and should inherit the blocked WP-5.5's
  per-module enumeration (commit 6a9b5cf) rather than re-deriving it.
- **LEG 1 IS NOT PROVEN and is the next thing this WP owes.** Revision 32's
  decision needs both legs pointed at the committed asset to render
  BYTE-IDENTICAL. Leg 2 is done above; leg 1 needs a sanctioned oracle change
  to `web_edition.py` and `weasyprint_adapter.py` (reading the asset instead
  of calling segno) plus a before/after render of 010 compared byte-for-byte
  across the web tree AND the reader PDF. Note the web half already has
  strong supporting evidence: the blocked WP-5.5 regenerated all nine web
  SVGs byte-identically from segno's own parameters, so serialisation is
  understood. The print half is the unproven one, and `_source_code_source`
  draws from `code.module` and `code.side` as well as the matrix, so the
  asset must reproduce the fit result exactly or the drawn geometry moves.
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
