# WP-2.1 verification: content pipeline, staged inputs to Typst source tree

**Verdict: ACCEPTED**

Commit under test: `f00e4c7`, base `f7ca38e`. Replayed from a fresh worktree at
`f00e4c7` created with `git worktree add`, which is not the tree the work was
developed in. The branch had moved to `20adcfb` while this ran; verification is
against `f00e4c7` throughout, and later landings are noted rather than verified.

**WP-2.2a should keep building on this as it stands.** The seam it consumes is
the one the evidence describes: `Vec<File>`, `main.typ` first with one
`#include "/<path>"` per piece in document order, 47 undefined function names,
reader text in markup content and structural data in code-mode string
arguments. Every finding below is a disclosure or labelling gap in the
evidence, or a bound on what the comparison can see. None of them changes the
emitted tree, and none of them is a reason to wait.

---

## 1. Replay

Rule 12: the `## Commands` block was extracted from the evidence file
PROGRAMMATICALLY and executed, rather than retyped from a shell.

**My first extractor was wrong, and recording it because it is rule 12's own
failure mode landing on the verifier.** A non-greedy ` ```sh\n(.*?)``` ` regex
stops at the literal three backticks inside the last heredoc's
`len(re.findall(r"^```", ...))`, truncating the block mid-string; the truncated
block ran everything up to that point and then died with

```
  File "<stdin>", line 12
    len(re.findall(r"^
SyntaxError: unterminated string literal (detected at line 12)
```

That is my bug, not the evidence's: CommonMark closes a fence only on a
line-initial run of backticks, and the evidence's block is well-formed. Re-read
line-wise (close only on a line whose content is exactly ` ``` `) the block is
3,100 bytes against the truncated 2,940, runs end to end and exits 0.

```sh
git worktree add /Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp21 f00e4c7
cd /Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp21
uv run python - <<'PY'
import pathlib
lines = pathlib.Path("meta/verification/evidence/WP-2.1.md").read_text().split("\n")
blocks, cur, inb = [], [], False
for ln in lines:
    if not inb and ln.rstrip() == "```sh":
        inb, cur = True, []
        continue
    if inb and ln.rstrip() == "```":
        blocks.append("\n".join(cur) + "\n"); inb = False
        continue
    if inb: cur.append(ln)
pathlib.Path("/tmp/block1_full.sh").write_text(blocks[0])
PY
MAG_TYPESET_REQUEST=/Users/franguijarro/code/magazine/editions/010/render-2026-09-14T01-49-02/request.json \
  bash -x /tmp/block1_full.sh
```

Exit 0. Results, in block order:

| step | result |
| --- | --- |
| regenerate `expected-900.json`, `diff -u` | no output, byte-identical |
| regenerate `expected-901.json`, `diff -u` | no output, byte-identical |
| `cargo fmt --check` | clean |
| `cargo clippy --all-targets -- -D warnings` | clean |
| `cargo test` | 17 suites, 171 tests, 0 failed |
| live edition, env-gated | `compared the live edition: 69097 characters of reader text, 0 verbatim runs`, pass |
| oracle tampered (`The Speed Limit` to `The Speed Limits`) | FAILED, no `UNEXPECTED PASS` |
| oracle truncated (last 40 chars) | FAILED, no `UNEXPECTED PASS` |
| corpus facts | six numbers, all reproduced |

**Hermeticity of the block.** Its one input from outside the checkout is
`MAG_TYPESET_REQUEST`, gated `${VAR:?...}` so a missing value fails loud. I
checked all 47 `inputs[]` rows of the request against a fresh worktree: **0 are
missing**, including the 21 files under the untracked-looking
`editions/010/run-2026-09-13T01-34-51/`, which are in fact tracked
(`git ls-files` lists 151 files under `editions/010/`). `--artifact-root .`
redirects every read into the checkout under test. So this is NOT the
gitignored-`$PWD`-relative form rule 12 names three times: the request is a
manifest naming tracked files, and the data comes from the worktree. The
residual weakness is that a fresh clone must first produce a `request.json`
with a weasyprint render before the live leg can run. Recorded, not a rejection;
weighed as the last two verifiers weighed the same shape.

`mag parity` was never invoked by this WP and no `verdict.json` is produced, so
the concurrent-overwrite hazard does not apply. Everything ran inside the
private worktree.

**Base chain.** `c1253d8..f7ca38e` is exactly two commits: `be64415` (only
`WP-0.2g.verify.md`) and `f7ca38e` (only the plan). Neither is read by this WP.
It does not matter either way, because the full block was replayed from
`f00e4c7` itself.

---

## 2. Every number re-derived

Rule 9 binds verifiers. Nothing below is cited; each was produced here.

| quantity | evidence | re-derived | how |
| --- | --- | --- | --- |
| 010 reader text, characters | 68,758 | **68,758** | twice: the block's own snippet, and an independent staging of my own into a different directory |
| 010 reader text, bytes | 69,097 | **69,097** | same, `len(text.encode("utf-8"))` |
| 010 articles | 9 | **9** | manifest, and `yaml.safe_load` |
| 010 extracts rows | 0 | **0** | manifest, and `yaml.safe_load` |
| 010 fenced-code fence lines | 0 | **0** | regex over staged manuscripts |
| 010 verbatim runs in the projection | 0 | **0** | oracle JSON |
| fixture 900 characters | 1,751 | **1,751** | `expected-900.json` |
| fixture 900 verbatim runs | 2 | **2** | `expected-900.json` |
| fixture 901 characters | 456 | **456** | `expected-901.json` |
| in-crate tests passing | 89 | **89** | `cargo test` output |

The independent derivation of 68,758 / 69,097 did not go through the evidence's
script path at all: I staged the request into my own directory and called
`render_html_edition` plus `typeset_oracle.project_html` directly.

**Two counts in my brief are wrong, and the evidence is not the source of
either.**

- **Template function names: 47, not 46.** Extracted programmatically from the
  enumeration: 47 backticked names, 0 duplicates. Cross-checked against the
  emitter: the sets match exactly. `source-link` is emitted (it is built in
  `source_link_call` without a leading `#` in the same literal, which is why a
  naive `#([a-z-]+)` regex misses it); `emph` and `strong` are correctly
  excluded as Typst's own; `import` and `include` are keywords, not functions.
  The evidence states no number, so the evidence is not wrong.
- **Test suites: 17, not 18.** One `unittests src/main.rs` plus 16 integration
  binaries, 171 tests, all `ok`. Counted from `Running ` lines and from
  `test result: ok` lines independently; both give 17, and the per-suite pass
  counts sum to 171. Eighteen would require counting the separate
  `cargo test --bin mag the_live_edition` invocation, which re-runs the same
  binary under a filter. The evidence claims only "in-crate tests passing: 89",
  which is exact.

**One number the evidence states wrongly (finding).** The rule-2b announcement
prints `projection.text.len()`, which in Rust is BYTES, labelled "characters":
`compared the live edition: 69097 characters of reader text`. The true
character count is 68,758. The Metrics table has both right; the Verdicts
section quotes the printed line verbatim and so carries the mislabel into the
evidence. Cosmetic, one-line fix in `content.rs:1170`, and worth fixing before
someone quotes 69,097 as a character count downstream.

---

## 3. The central claim: is "pre-layout = `render_html_edition`'s text nodes"
the right boundary?

The comparison passes. The question is whether the boundary was drawn to make
it pass. **It was not**, and I tested that rather than arguing it. But the
evidence's characterisation of the boundary is measurably false in both
directions, and that is the finding.

### 3.1 The characterisation is wrong in both directions

The evidence says the oracle's "text nodes are the reader-visible text before
any layout exists". Measured against `weasyprint-a5.css`, they are not.

**In the compared text and NEVER PRINTED** (`display: none` in the print CSS):

| run | CSS | 010 characters |
| --- | --- | --- |
| `.edition-header` (publication name, issue line, title, subtitle, date) | `weasyprint-a5.css:266` | 314 |
| `.source-link` x 9 | `weasyprint-a5.css:1416` | 521 |
| **total** | | **835 of 68,758 = 1.21%** |

(`.provenance`, `weasyprint-a5.css:803`, is also `display:none`; 010 emits none
because every article takes the illustrated path. Fixture 900 exercises it.)

**PRINTED and NOT in the compared text** (CSS `content: attr(...)` on
`::before`, which is generated content, not layout):

| run | CSS | 010 instances |
| --- | --- | --- |
| figure label, `attr(data-figure-label) " " counter(magazine-figure, ...)` | `weasyprint-a5.css:1024` | 3 |
| extract label, `attr(data-extract-label)` | `weasyprint-a5.css:925` | 0 in 010, 2 in fixture 900 |

The genuinely-layout exclusions are correct and uncontroversial: folios
(`counter(page)`, line 153), the running head (`element(runhead, first-except)`,
line 171), the masthead string (line 145) and the TOC page numbers
(`target-counter(attr(href), page, ...)`, line 364).

### 3.2 It is not a boundary drawn to succeed

Two measurements settle it.

**Everything included-but-unprinted makes the comparison HARDER.** 835
characters of edition header and source URLs that a reader never sees are in
the compared text, and both legs must agree on them. A boundary chosen to make
a comparison succeed drops such text; this one carries it.

**Everything excluded-but-printed reduces to exactly one emitted value**, the
`word:` argument, and I verified it cannot hide a divergence. I extracted the
complete set of named arguments from the live 010 tree (10 files):

```
alt anchor destination figure-layouts id index kind layout level opener
ordered references roster short-title source-id source-ids standfirst start
tight title word
```

Every one maps to an HTML attribute in the oracle, not a text node, **except
`word`**. `word` is `ui("figure")` on the Rust side and `_ui(edition,
"figure")` on the Python side. I compared the two tables entry for entry:
`content.rs::ui` carries 20 English and 20 Spanish keys, and
`html_edition._ui` carries the same 20 keys with the same values in both
languages, with the same fallback (`key.replace("_"," ").replace("-"," ")
.upper()` against `py_upper(&key.replace(['_','-'], " "))`). The only two keys
that reach `word:` are `figure` ("Figure"/"Figura") and `verbatim`
("VERBATIM"/"TEXTUAL"). They agree.

### 3.3 The right name for the boundary, and what it costs

The correct description is **"the text content of the pre-layout HTML
document"**, not "the reader-visible text". That is the right seam for a
CONTENT pipeline: `display:none` and `::before` are template and CSS decisions,
which is WP-2.2's territory, and `content.rs` correctly carries the hidden runs
as markup content so the template can decide to hide them. There is no
alternative boundary available: the Typst side has no CSS, so the exclusions
cannot be applied symmetrically.

What it costs, and what WP-2.2 must carry:

- `word:` is the only reader-visible string in the emitted tree that **no test
  pins**. `ui("figure")` and `ui("verbatim")` are correct today by table
  comparison, not by assertion. If WP-2.2c drops the argument or the value
  drifts, this WP's comparison stays green. Tier S's per-page extracted-text
  clause against the rendered PDF is what will catch it.
- The per-article figure counter (`counter(magazine-figure)`, reset on
  `article`) is not in the tree at all. It is derivable from document order, so
  this is a template obligation, not a content-pipeline gap, but nobody has
  written it down until now.

The evidence's `## What is and is not proven` says "Nothing about layout". That
is true and insufficient: the figure and extract labels are not layout, and
their absence from the comparison is not covered by that sentence.

---

## 4. The fail-loud guard fires (rule 10, vacuity)

The committed test `the_projection_refuses_markup_it_cannot_account_for` uses a
Typst heading. I exercised **twelve further markup leaf kinds**, all different
from it, by appending a temporary probe module to `content.rs` in the worktree:

```
star *bold*          underscore _emph_     list marker -      enum marker +
term marker /        label <mylabel>       ref @mylabel       smartquote "x"
shorthand --         math $x + y$          line comment //    block comment /* */
```

**All twelve refused** with `unprojectable markup`. None projected silently.
The guard is not vacuous.

**Rule 11, on the mechanism the guard protects.** I replaced `escape_markup`
with the identity function and re-ran `typeset::content::tests`:

```
test result: FAILED. 12 passed; 5 failed
  the_plain_opener_fixture_projects_to_the_python_text            FAILED
  the_illustrated_opener_fixture_projects_to_the_python_text      FAILED
  every_extract_run_is_byte_exact_against_the_captured_source     FAILED
  the_live_edition_projection_matches_the_oracle                  FAILED
  escaping_round_trips_every_text_atom_the_fixtures_carry         FAILED
ValidationError(["pieces/article-01-... is not valid Typst: expected colon"])
ValidationError(["main.typ is not valid Typst: unclosed delimiter"])
```

Removing the cause removes the effect, loudly. Total escaping is load-bearing
and its removal is refused rather than absorbed. `content.rs` was then restored
with `git show HEAD:mag/src/typeset/content.rs > mag/src/typeset/content.rs`;
`git status --porcelain` empty afterwards.

---

## 5. Markup content versus code-mode strings: discipline, not guard

The evidence discloses that this is a discipline the walker cannot enforce.
**The disclosure is accurate in both directions and I reproduced both.**

```
DISCIPLINE content="A caption." argument=""
   #figure-caption[A caption\.]           projects "A caption."
   #figure-block(caption: "A caption.")   projects ""

DISCIPLINE ok="A caption." wrong="fig-01A caption."
   #figure-block(id: "fig-01")[A caption\.]  projects "A caption."
   #figure-block[fig\-01][A caption\.]       projects "fig-01A caption."
```

A caption in a string argument silently leaves the reader text; an id in a
content block silently joins it. Exactly as stated.

**Is anything currently on the wrong side?** I audited the complete argument
set of the live 010 tree (section 3.2). The answer is: nothing is on the wrong
side **as the oracle draws the line**, and exactly one item (`word`) is on the
wrong side as a READER would draw it, which is section 3's finding rather than
a discipline breach. In the other direction every markup-content emission maps
to an oracle text node, including `#provenance[...]` and `#source-link(...)[url]`,
which are text nodes in the HTML even though the print CSS hides them.

One structural detail WP-2.2 must not regularise: the byline space moved sides.
The oracle writes `<span class="byline-prefix">By</span> {author}` with the
space OUTSIDE the span; the emitter writes
`#byline[#byline-prefix[By]#byline-name[ Anthropic]]` with the space INSIDE
`byline-name`. The projected text is identical, so this comparison cannot see
it, but a template that trims `byline-name` or inserts its own gap will diverge.

---

## 6. Discrimination, and the opposite extreme (rule 10)

The evidence runs a word-level tamper and a truncation. Both fail on replay. I
ran three more, from both extremes:

| oracle | result | which assertion |
| --- | --- | --- |
| identity (control) | **pass** | equality |
| one character (`Limit` to `Limlt`) | **FAILED** | equality |
| whitespace doubled in first 200 chars | **FAILED** | equality |
| **empty text** (the vacuity extreme) | **FAILED** | `the live oracle carries 0 characters, too few to be edition 010` |

The empty case fails on the cardinality guard with its own distinct message
before the equality assertion is reached, so a stub or empty oracle cannot
satisfy the clause. The clause discriminates down to a single character.

**But it is blind to a large class, and this is the finding.** I built a tree
with two `#doc-paragraph` calls and a tree with the same text merged into one
call. Their projections are byte-identical:

```
NON-DISCRIMINATION block structure: both project "First sentence. Second sentence."
```

`normalize_reader_text` collapses whitespace runs, so **block boundaries carry
no signal at all**. A pipeline that merged every paragraph into one, or that
emitted every heading's text without its `doc-heading` wrapper, would pass this
comparison unchanged. So would any reordering-free change to figure or extract
PLACEMENT that preserved text order. The target clause proves same text in same
order, and nothing about structure. The evidence's `## What is and is not
proven` does not name this; it should, because the phrase "byte for byte" reads
much stronger than what the check can see.

---

## 7. The two declared boundary exceptions

### 7.1 `mod content;` outside Owns: the necessity argument HOLDS

`git diff --name-only f7ca38e f00e4c7` is 31 files: `content.rs`, `mod.rs`, 27
under `mag/tests/typeset_fixtures/`, `mag/tests/typeset_oracle.py`, and the
evidence file. No verify file, no `baseline.json`, no Cargo file, nothing under
`mag/src/parity*`, `mag/src/typeset/template.rs` or `mag/src/web/`. The single
out-of-Owns file is the declared one.

Rust compiles `mag/src/typeset/content.rs` only if a parent declares
`mod content;`, and the only parent is `mag/src/typeset/mod.rs`. No path inside
Owns reaches it; declaring from `main.rs` would touch a larger blast radius.
The necessity argument is sound. The edit is three lines plus a `#[cfg(test)]`
consumer test that imports `crate::typeset::content` the ordinary way, which is
what rule 12's first clause asks for and is explicitly not a `#[path]` include.

Form deviation, recorded not penalised: rule 1 says a non-owner asks for an
Owns extension "however small", and this WP self-granted. Mitigating: the file
has no live owner (WP-2.0a is landed and accepted), the change is a
declaration with no behaviour, and it is declared in the evidence. **Flag for
WP-2.2a:** it needs `mod template;` in the same file, so expect a one-line
mechanical conflict there.

### 7.2 The `normalize` duplicate: pinning verified, with one correction

**Verified.** `content.rs::normalize_reader_text` is pinned to Python, through
`typeset_oracle.py::normalize`: the live and fixture clauses compare
Rust-normalized projection text against Python-normalized oracle text. And it
is **not** pinned to its sibling: no test anywhere asserts that the two Rust
copies agree, so the weak form revision 26 deprecates is not in use.

**Correction to my brief's framing, in the evidence's favour.** The brief says
"each copy is pinned to its own Python oracle". That is true of one copy only.
`mag/src/parity/text.rs::normalize` is pinned to no Python oracle at all: it
normalizes both legs of a Rust-to-Rust `pdftotext` comparison, and I searched
the repository for a Python original (`def normalize` appears in exactly two
places: `typeset_oracle.py`, added by this WP, and
`render_critic.py::normalized`, a different function). There is no Python
`normalize` for the parity copy to be pinned to; it implements a plan-specified
Tier S rule symmetrically, where a wrong-but-symmetric normalization is
invisible. **The evidence is careful about this and does not overclaim** — it
writes "the parity copy to the PDF text path", not "to Python". That is
accurate.

**The audit cannot see the pair, and the evidence says so.** `rust_helpers.rs`
keys on function NAME against a 22-entry allow-list; the WP renamed `normalize`
to `normalize_reader_text` "to clear the crate-wide duplicate audit". That is a
candid disclosure of an evasion of a scanner that revision 26 already records
cannot close this class. I read both bodies: they are character-for-character
identical modulo local names (`nfc`/`composed`, `no_soft`/`stripped`,
`rejoin_line_end_hyphens`/`rejoin_hyphenated_words`, `is_hyphenate` inlined as
a `matches!`), over the same three-codepoint hyphen set. That is a read, not a
measurement; the crate's module privacy (`mod text;` is private in
`mag/src/parity.rs`) blocks a differential test from inside the crate, which is
the same wall the WP hit.

**And the pinning that does exist covers one clause of four.** Measured over
the entire compared corpus:

| clause | 010 | fixtures 900/901 |
| --- | --- | --- |
| NFC | no-op, raw is already NFC, 0 chars changed | - |
| rejoin line-end hyphens | 0 chars removed | - |
| strip soft hyphens U+00AD | 0 present | 0 present |
| collapse whitespace runs | 2,134 of 70,892 chars removed | live |

70,892 - 2,134 = 68,758, which closes against the headline count. So the
evidence's "both sides are normalized by the Tier S rule (NFC, rejoin line-end
hyphens, strip soft hyphens, collapse whitespace runs)" is a four-legged claim
of which **three legs pass empty against empty**. That is rule 10a's family and
the evidence does not label it. It matters for residual 1: drift between the
two Rust copies in the NFC, rejoin or soft-hyphen clauses is invisible today,
and soft hyphens become live the moment hyphenation returns (WP-1.5 chose (b),
so they are absent by decision, not by nature).

**A mechanism I asserted and measurement falsified (rule 11, applied to
myself).** I hypothesised that Python's `str.split()` and Rust's
`split_whitespace()` disagree on U+00A0, which would make the one live clause
unsound. Tested exhaustively over all 0x110000 codepoints: they disagree on
**exactly four**, U+001C to U+001F, which Python treats as separators and Rust
does not; Rust has none Python lacks; NBSP and U+2009 split in both. None of
the four occurs in 010 or the fixtures (the raw text contains only U+0020 and
U+000A). And if one did, Python would collapse it and Rust would keep it, so
the comparison would **fail loud rather than pass wrongly**. No finding; the
hypothesis was wrong.

---

## 8. Two further checks the brief asked for

**Caption/credit, contents entry and article label gluing is FAITHFUL, not a
simplification.** Read from the oracle generator:

- `html_edition.py:588` writes
  `<figcaption><span class="caption">{caption}</span><span class="credit">{credit}</span></figcaption>`
  with no separator. The emitter writes
  `[#figure-caption[...]#figure-credit[...]]` with no markup whitespace.
- `html_edition.py:184-187` writes `<span class="entry-label">` then
  `<a class="entry-title">` then `<span class="entry-author">`, adjacent, with
  an empty `aria-hidden` `entry-folio` anchor between the first two that CSS
  fills with the page number. The emitter glues label, title and author the
  same way and omits the folio, which is layout.
- `html_edition.py:246-247` (plain path) writes `label-primary` then
  `label-secondary` with **no** separator; `html_edition.py:399-401`
  (illustrated path) inserts `<span class="label-separator"> / </span>` between
  them. The emitter reproduces exactly that asymmetry, gated on `illustrated`.
  Confirmed in the fixture oracles: 900 (plain) reads `Feature 01ARTICLE / 2026 08`,
  901 (illustrated) reads `Feature 01 / ARTICLE / 2026 07`.

The evidence's warning that WP-2.2 must not change this without changing the
oracle comparison with it is correct and load-bearing.

**Parses but does not compile: the declared state, not a concealed failure.**
`main.typ` line 1 is `#import "/template.typ": *`; the live tree is 10 files
(main plus 9 article pieces) and contains no `template.typ`; all 47 called
functions are undefined. `typst_syntax::parse` returns zero errors for every
file, which the walker enforces (it refuses on any parse error, so a projection
that succeeds is a proof that every file parsed). The missing template is
visible in the first line of the entry file, which is the opposite of concealed.

**Additional check, on the oracle's own fail-loud guard.** `typeset_oracle.py`'s
`Projector` raises `SystemExit` on any tag outside `BLOCK | INLINE`. I
enumerated every tag `html_edition.py` can emit and every tag Pygments emits
(`span` only) and diffed against that classification: the only unmatched names
are regex artifacts plus `meta` and `title`, both inside `<head>`, which the
projector skips wholesale. The oracle's classification is complete for the
emitter it reads, so its guard is not vacuous either.

---

## 9. What this verification CANNOT discriminate (rule 10)

1. **Whether the tree can be given a template that renders.** Nothing here
   compiles it. No `typst` CLI is on this machine's PATH and driving
   `typst::compile` needs a `World` implementation, so section 8's claim is
   structural, not a compile.
2. **Block structure.** Measured in section 6: paragraph boundaries, heading
   wrappers and figure/extract placement relative to surrounding text are all
   invisible to the projection. Order of text is all it sees.
3. **Anything about layout**: pages, folios, running heads, TOC page numbers,
   same-page equality, opener fit.
4. **Three of the four normalization clauses** (section 7.2), and therefore
   drift between the two Rust `normalize` copies in NFC, hyphen-rejoin and
   soft-hyphen handling.
5. **The `word:` and `alt:` values**, excluded by the boundary. I verified the
   `ui` table against Python by reading it entry for entry, not by a test.
6. **The Spanish table.** Same: verified by reading, exercised by nothing.
7. **Whether the two Rust `normalize` bodies are identical.** Verified by
   reading; module privacy blocks a differential test.
8. **The duplicate audit's blind spot itself.** I confirmed `rust_helpers.rs`
   keys on names and therefore cannot see a renamed copy; I did not search the
   crate for other renamed duplicates.

---

## 10. Findings for the plan and for downstream WPs

Rule 3d: these are the load-bearing reasons, restated where they will be
re-read rather than left only in this terminal document.

1. **The pre-layout boundary should be named correctly in the plan**: "the text
   content of the pre-layout HTML document", not "the reader-visible text". It
   over-includes 835 characters of `display:none` runs and under-includes the
   CSS-generated figure and extract labels, measured on 010. The boundary is
   right; the words are not, and WP-2.2/WP-3.3 will read them.
2. **`word:` is the only reader-visible string in the tree that no test pins.**
   WP-2.2c must emit it and Tier S's per-page text clause is its only guard.
   The per-article figure counter is not in the tree and is the template's to
   synthesize.
3. **The projection cannot see block structure.** Any claim built on "the text
   matches byte for byte" must not be read as "the document structure matches".
4. **`normalize_reader_text` is pinned to Python on one clause of four.** Three
   are vacuous on the whole compared corpus. The shared-module lift the
   evidence asks for has **no owner named**; some WP that owns
   `mag/src/parity*` should take it, and until then a drift in the three dead
   clauses is undetectable.
5. **`mag/src/typeset/mod.rs` now carries `mod content;`.** WP-2.2a will add
   `mod template;` to the same file.
6. **Cosmetic**: `content.rs:1170` prints bytes labelled "characters"; the
   evidence quotes the mislabel.

None of these is a code defect. **No defect is live on the branch.**

---

## 11. Verdict

**ACCEPTED.** The target clause is met and independently reproduced: the
emitted Typst source tree's plain-text projection equals the WeasyPrint leg's
pre-layout reader text for all of edition 010, 68,758 characters and 69,097
bytes, both re-derived here by a path that does not go through the evidence's
script. The fixture oracles regenerate byte-identically. The refusal matrix and
the straddles pass. The fail-loud guard fires on twelve leaf kinds beyond the
committed case, and neutering the escaping it protects fails five tests loudly.
The discipline the walker cannot enforce is disclosed accurately and nothing is
currently on the wrong side of it. The Owns diff is exactly the declared set,
and the one out-of-Owns edit is genuinely unavoidable.

The findings are disclosure and labelling gaps: a boundary described more
strongly than it is, a block-structure blindness not named, and three
normalization clauses passing empty against empty. Each belongs in the
evidence's `## What is and is not proven` and none of them changes a byte of
the emitted tree.

**WP-2.2a should keep building on this as it stands.**
