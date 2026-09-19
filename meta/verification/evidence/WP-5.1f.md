# WP-5.1f pin `is_name_roster`, and then `content_label`, to Python whitespace

## Base

`3b57c36` (WP-5.5a, "refactor(model): lift the four shared edition-text
helpers"), which is where `is_name_roster` acquired its current home in
`mag/src/model/shared.rs`. Work was done in a detached worktree at that
commit and rebased onto `art_directed` at landing.

The `content_label` half was added afterwards, under a **scoped Owns
extension granted in response to this WP raising the finding and asking
rather than widening**. Its conditions were the same as the original grant:
only that helper, only its whitespace handling, declared here, with a
committed fixture showing both directions.

## Commands

The roster oracle, regenerating `mag/tests/model_shared_roster_expected.json`
from the Python function itself rather than from a reimplementation of it:

```
uv run python -c '
import json, sys
sys.path.insert(0, "src")
from magazine.html_edition import _is_name_roster
RS = chr(0x1E)
BULLET = "\N{BULLET}"
cases = [
    ("seven words, but only when U+001E splits", f"a b c d e f{RS}g {BULLET} C D {BULLET} E F"),
    ("a segment that is empty only after a Python strip", f"{RS} {BULLET} C D {BULLET} E F"),
    ("control: U+001E inside a segment, both agree", f"A{RS}B {BULLET} C D {BULLET} E F"),
]
out = {"separator": "U+2022", "cases": [
    {"name": n, "text": t, "python": _is_name_roster(t)} for n, t in cases]}
print(json.dumps(out, indent=1, ensure_ascii=True, sort_keys=True))
' > mag/tests/model_shared_roster_expected.json
cat mag/tests/model_shared_roster_expected.json
```

The label oracle, regenerating `mag/tests/model_shared_label_expected.json`
through the real frontmatter parse and the real `_content_label`, so the
verdicts are Python's rather than a restatement of Python's rule:

```
uv run python -c '
import json, sys, types
sys.path.insert(0, "src")
from magazine.html_edition import _content_label
from magazine.publication_document import parse_publication_document
edition = types.SimpleNamespace(language="en")
NOT_WHITESPACE = "the value-is-not-None guard, not whitespace; see WP-5.1f residuals"
frontmatters = [
    ("a label that is whitespace only under Python", "label: \"\\u001E\"", ""),
    ("a label padded with U+001E", "label: \"\\u001EARTICLE\\u001E\"", ""),
    ("control: an ordinary label", "label: Dispatch", ""),
    ("control: an ASCII-space-padded label", "label: \"  Dispatch  \"", ""),
    ("a null label, a divergence this WP did not own", "label:", NOT_WHITESPACE),
]
cases = []
for name, line, known_divergence in frontmatters:
    doc = parse_publication_document(f"---\n{line}\n---\n\nBody.\n")
    cases.append({"name": name, "frontmatter": line, "content_mode": "article",
                  "known_divergence": known_divergence,
                  "python": _content_label(edition, doc, "article")})
print(json.dumps({"language": "en", "cases": cases}, indent=1, ensure_ascii=True, sort_keys=True))
' > mag/tests/model_shared_label_expected.json
cat mag/tests/model_shared_label_expected.json
```

The whitespace oracle, regenerating
`mag/tests/model_shared_isspace_expected.txt`, and the sweep that produces
the two counts this WP cites, as enumerations rather than as totals:

```
uv run python -c "
import sys, unicodedata
print('python', sys.version.split()[0], 'unicode', unicodedata.unidata_version)
out = [cp for cp in range(0x110000) if not (0xD800 <= cp <= 0xDFFF) and chr(cp).isspace()]
open('mag/tests/model_shared_isspace_expected.txt','w').write('\n'.join(map(str,out))+'\n')
print('python isspace count:', len(out))
print(' '.join(f'U+{c:04X}' for c in out))
"
```

That `str.isspace()` is the right oracle for `str.strip()` and `str.split()`,
checked over every codepoint rather than assumed from the CPython source:

```
uv run python -c "
bad_split, bad_strip = [], []
for cp in range(0x110000):
    if 0xD800 <= cp <= 0xDFFF: continue
    c = chr(cp)
    if (f'a{c}b'.split() == ['a','b']) != c.isspace(): bad_split.append(cp)
    if (f'{c}a{c}'.strip() == 'a') != c.isspace(): bad_strip.append(cp)
print('split() disagrees with isspace() on:', bad_split)
print('strip() disagrees with isspace() on:', bad_strip)
"
```

The Rust half of the same sweep, enumerated:

```
mkdir -p /tmp/wp51f-sweep && cat > /tmp/wp51f-sweep/sweep.rs <<'RS'
fn main() {
    let mut v = vec![];
    for cp in 0u32..0x110000 {
        if let Some(c) = char::from_u32(cp) {
            if c.is_whitespace() { v.push(cp); }
        }
    }
    println!("rust is_whitespace count: {}", v.len());
    let names: Vec<String> = v.iter().map(|c| format!("U+{c:04X}")).collect();
    println!("{}", names.join(" "));
}
RS
rustc -O /tmp/wp51f-sweep/sweep.rs -o /tmp/wp51f-sweep/sweep && /tmp/wp51f-sweep/sweep
```

Corpus reachability, over every `.yaml`, `.yml` and `.md` file under
`editions/` and `library/sources/` **that git tracks**, which is what a
replay directory contains. The untracked run directories are covered by the
second invocation below, which is NOT hermetic and is labelled as such:

```
uv run python -c '
import collections, pathlib, sys
root = pathlib.Path(sys.argv[1])
bad = set(range(0x1C, 0x20))
files = sorted(p for r in ("editions", "library/sources")
               for p in (root / r).rglob("*")
               if p.is_file() and p.suffix in {".yaml", ".yml", ".md"})
by_dir = collections.Counter(p.relative_to(root).parts[0] for p in files)
hits = sum(sum(1 for ch in p.read_text(encoding="utf-8", errors="surrogateescape")
               if ord(ch) in bad) for p in files)
print(f"root={root}")
print(f"files={len(files)} by_top_dir={dict(by_dir)}")
print(f"occurrences_of_U+001C_to_U+001F={hits}")
' .
```

Whether the null-label divergence below has ever fired, over every tracked
`label:` key in `editions/` and `library/sources/`:

```
grep -rh --include='*.md' --include='*.yaml' -E '^[[:space:]]*label:' editions library/sources \
  | sort | uniq -c | sort -rn
echo "total: $(grep -rh --include='*.md' --include='*.yaml' -E '^[[:space:]]*label:' \
  editions library/sources | wc -l | tr -d ' ')"
echo "bare: $({ grep -rh --include='*.md' --include='*.yaml' \
  -E '^[[:space:]]*label:[[:space:]]*$' editions library/sources || true; } \
  | wc -l | tr -d ' ')"
```

Whether the roster helper fires on the corpus at all, which is what makes
the zero above a statement about the four codepoints rather than about the
function being dead:

```
uv run python -c '
import pathlib
files = [p for r in ("editions", "library/sources") for p in pathlib.Path(r).rglob("*")
         if p.is_file() and p.suffix in {".yaml", ".yml", ".md"}]
texts = [p.read_text(encoding="utf-8", errors="surrogateescape") for p in files]
print("U+2022 occurrences:", sum(t.count(chr(0x2022)) for t in texts),
      "in", sum(1 for t in texts if chr(0x2022) in t), "files")
'
```

The demonstration, both directions, for both helpers. `0978ebb` is the
commit before either fix, so the first run restores a `shared.rs` with
neither and must FAIL in both binaries, naming the two disagreeing roster
cases and the two disagreeing label cases and neither control; the second
restores the fixed one and must pass:

```
git show 0978ebb:mag/src/model/shared.rs > mag/src/model/shared.rs
cd mag && cargo test --test model_shared_roster; cargo test --test model_shared_label; cd ..
git show HEAD:mag/src/model/shared.rs > mag/src/model/shared.rs
cd mag && cargo test --test model_shared_roster && cargo test --test model_shared_label
```

The two binaries are run as separate commands rather than as
`cargo test --test a --test b`, because cargo stops at the first binary that
fails. The combined form was written first and it silently produced only the
label failures, so the caption claimed four failing cases and the output
showed two. That is the same short-circuiting trap as the one below, one
level up: **a harness that aborts on first failure evidences only the first
failure, whichever layer the aborting happens at.** It was caught by
replaying the block and reading its output against the caption, which is the
check rule 12 exists for.

Every whitespace-handling site in `mag/src/model/shared.rs`, which is the
scope of the sibling-helper audit below. The pattern covers the pinned
spellings (`py_strip`, `is_python_space`) as well as the std ones, because
after this WP the fixed sites no longer say `trim` and a std-only pattern
would report them as absent rather than as fixed. The wider `mag/src/` sweep
is reported in the audit section but is not this WP's Owns:

```
grep -n 'trim\|split_whitespace\|is_whitespace\|py_strip\|is_python_space' \
  mag/src/model/shared.rs
```

Every implementation of, and every call site of, the two helpers this WP
changed, across all of `mag/src/`:

```
grep -rn 'name_roster\|ROSTER' --include='*.rs' mag/src/
grep -rn 'content_label' --include='*.rs' mag/src/
```

Repository gate:

```
cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

## Tool versions

python 3.12.11 (Unicode 15.0.0, via `uv run python`; the system `python3` is
3.9.6 with Unicode 13.0.0 and was not used), rustc 1.96.0. No crate added;
`Cargo.toml` and `Cargo.lock` untouched.

## Metrics

### The defect, confirmed rather than taken on trust

`is_name_roster` ported Python's

```
names = [segment.strip() for segment in text.split(_ROSTER_SEPARATOR)]
... all(name and len(name.split()) <= _ROSTER_MAX_NAME_WORDS for name in names)
```

using `str::trim` and `split_whitespace()`. Both of those are Rust's
`char::is_whitespace`; both of Python's are `str.isspace`. The two sets are
not the same set.

Enumerated over all 1,114,112 codepoints, skipping the surrogate range on
both sides:

| set | count | members |
|---|---|---|
| Python `str.isspace()` | **29** | U+0009 U+000A U+000B U+000C U+000D **U+001C U+001D U+001E U+001F** U+0020 U+0085 U+00A0 U+1680 U+2000-U+200A U+2028 U+2029 U+202F U+205F U+3000 |
| Rust `char::is_whitespace` | **25** | the same list with the four bolded entries removed |

The relation is one-directional: Python's set strictly contains Rust's, and
the difference is exactly the four ASCII field separators U+001C FILE
SEPARATOR, U+001D GROUP SEPARATOR, U+001E RECORD SEPARATOR and U+001F UNIT
SEPARATOR. No codepoint is whitespace to Rust and not to Python.

`str.isspace()` being the correct oracle for `.strip()` and `.split()` was
measured rather than assumed: over every codepoint, `f"a{c}b".split()` and
`f"{c}a{c}".strip()` agree with `c.isspace()` with **zero** exceptions on
this interpreter. That matters because the port's two defects are in
`strip` and `split`, not in `isspace`, and an argument that routed through
the CPython source instead of through measurement would have been the weaker
one.

### It changes the answer, not only the internals

Three committed cases, with `<RS>` standing for U+001E, verdicts taken from
the Python function itself:

| case | Python | Rust before | Rust after |
|---|---|---|---|
| `a b c d e f<RS>g • C D • E F` | `False` | `true` | `false` |
| `<RS> • C D • E F` | `False` | `true` | `false` |
| `A<RS>B • C D • E F` (control) | `True` | `true` | `true` |

The first isolates the **split** defect: the first segment is seven Python
words and six Rust words, so it crosses `ROSTER_MAX_NAME_WORDS`. The second
isolates the **strip** defect: the first segment strips to empty in Python
and does not in Rust, so Python's `name and ...` guard fails and Rust's
`!name.is_empty()` does not. The third is WP-5.5a's control and is kept
unchanged: it has the same shape, the same separator, the same `<RS>`, and
the two agree, which is what rules out the fixture shape as the thing
producing the disagreement.

Before the fix, `the_roster_test_matches_python_on_the_committed_cases`
fails naming **both** disagreeing cases and not the control:

```
seven words, but only when U+001E splits: python false, rust true, for "a b c d e f\u{1e}g • C D • E F"
a segment that is empty only after a Python strip: python false, rust true, for "\u{1e} • C D • E F"
```

The test was written to accumulate rather than to `assert_eq!` per case
precisely so that this message shows both; a short-circuiting version showed
only the first and would have left the second direction unevidenced.

### The fix

`str::trim` becomes `py_strip` and `split_whitespace()` becomes
`split(is_python_space)` with the empty runs filtered, which is Python's
no-argument `split`. Both halves, as the brief requires: fixing only one
leaves the other case red.

`is_python_space` was already in the same file, written for exactly this and
simply not called here. Nothing was added to `shared.rs` and no new helper
was introduced; the change is four lines inside one function.

Rule 11, the cause removed and the effect measured: with the pre-fix
`shared.rs` restored over the fixed one, the test fails as above; restoring
the fixed one turns all four green. The two runs are in the Commands block
and are the only difference between them.

### The guard, and what would make it fail

`python_space_exceeds_rust_std_by_exactly_the_four_field_separators` does not
assert the claim as a constant. It recomputes both sets at test time, from
the committed Python oracle on one side and from `char::is_whitespace` on the
other, and asserts three things:

- the Python-only set **equals** `[0x1C, 0x1D, 0x1E, 0x1F]`, so a fifth
  divergence fails rather than being absorbed;
- the std-only set is **empty**, so the one-directionality is pinned too, and
  a codepoint Rust starts calling whitespace and Python does not fails here;
- for each of the four, `!character.is_whitespace()` holds, with the failure
  message *"std must disagree, else this test proves nothing"*.

That last assertion is the one the brief asks for. If a future Rust release
adds the field separators to `char::is_whitespace`, the fixtures above stop
discriminating anything: they would pass against the unfixed code, and a
test that passes for the wrong reason is worse than no test. The guard turns
that into a red build naming the codepoint. The symmetric risk is covered by
`the_disagreeing_cases_are_ones_rust_std_whitespace_gets_wrong`, which
re-evaluates the **old** `trim`/`split_whitespace` expression against the
committed cases and asserts that exactly two of the three still disagree
with Python, so a fixture edited into harmlessness also fails.

`is_python_space_matches_python_over_the_whole_plane` pins the third leg:
`is_python_space` reproduces the 29-codepoint oracle exactly, over the whole
plane. Without it the guard could pass while `is_python_space` itself drifted.

### Corpus unreachability, verified here rather than cited

Over every `.yaml`, `.yml` and `.md` file under `editions/` and
`library/sources/`:

| scope | files | occurrences of U+001C-U+001F |
|---|---|---|
| tracked (what a replay directory sees) | 1,433 (1,241 editions, 192 library) | **0** |
| main working tree, incl. untracked `run-*` dirs | 1,874 (1,682 editions, 192 library) | **0** |

Zero in both. **The brief's file count of 833 does not reproduce**, against
either scope. The counts above are this WP's own enumeration and the brief's
is not carried anywhere, per rule 9's citation clause, which now binds briefs
and coordination messages and not only evidence files: a brief is where a
number enters a WP's reasoning, so it is a citation like any other, and the
one document nobody audits is the worst place to exempt. The correction was
accepted by the coordinator and the same duty was applied in the other
direction while doing this extension: the coordinator's note that the branch
had moved again did not reproduce at the time it was read (`art_directed`
was still at this WP's own `02f1d35`), which changed nothing, because `B` is
captured immediately before rebasing either way.

The load-bearing number, zero, does reproduce under both scopes, and that is
what makes the unreachability claim survive the file-count error.

The zero is a statement about the four codepoints and not about a dead
function: the separator U+2022 occurs **195 times across 8 tracked files**,
so `is_name_roster` does fire on real content. It has simply never been
handed a field separator. The two are different reasons for a test to be
quiet and the pairing is what tells them apart.

Status per rule 3b: both defects were **LIVE on the branch** in
`mag/src/model/shared.rs` and are now fixed. Both were **latent, not
firing**, because no corpus input reaches either. Consumers who must not
build on the old behaviour: WP-2.1's contents-entry author rendering,
WP-2.2a, and WP-5.5a's web port. There is exactly one implementation and
exactly one call site of each -- `is_name_roster` at
`mag/src/typeset/content.rs:535` and `content_label` at
`mag/src/typeset/content.rs:365` -- both confirmed by the repository-wide
greps in the Commands block.

### Sibling helpers, and `mag/src/model/shared.rs` is now fully swept

The grep in the Commands block returns **seven lines and only seven**, and
they are the enumeration behind the sweep claim. Two are the definitions of
the pinned primitives and five are uses:

| line | site | Python original | Rust after | verdict |
|---|---|---|---|---|
| 184-185 | `is_python_space` (definition) | `str.isspace` | `is_whitespace() \|\| '\u{1c}'..='\u{1f}'` | correct, pinned by a whole-plane test |
| 188-189 | `py_strip` (definition) | `str.strip` | `trim_matches(is_python_space)` | correct |
| 250 | `is_name_roster`, the segment strip | `segment.strip()` | `map(py_strip)` | **fixed here** |
| 255 | `is_name_roster`, the word split | `name.split()` | `split(is_python_space)`, empties filtered | **fixed here** |
| 331 | `content_label` | `str(value).strip()` | `py_strip(&value).to_string()` | **fixed here (extension)** |

Three of the five uses were wrong and all three are now pinned to the two
primitives, which are themselves pinned to Python over the whole plane.

**`mag/src/model/shared.rs` is swept, not merely fixed twice.** The other two helpers
WP-5.5a lifted are clean because they do no whitespace handling at all --
`ui` does none, and `clamp_roster` does none either (its `len`/slice/`rfind`
are codepoint- and byte-correct against the Python, which is a separate
question and was not re-verified here). The next reader does not need to
re-open this question for this file.

Outside `shared.rs` the same grep over all of `mag/src/` finds roughly 180
`trim`/`split_whitespace` sites. **No claim is made about them.** They were
not audited, most are not ports of a Python string operation at all, and a
whole-tree audit is a different WP.

### `content_label`, fixed under a scoped Owns extension

The extension was granted explicitly after this WP raised the finding and
asked rather than widening, on the reasoning that the sweep and the oracle
were already built and the alternative was filing a one-word fix for a
future agent to rediscover the context. The conditions were the same: only
that helper, only its whitespace handling, declared here, with a committed
fixture showing both directions.

`html_edition.py::_content_label` reads `str(value).strip()`; the Rust read
`.trim()`. One word, `py_strip`, is the whole change.

Five cases are committed in `mag/tests/model_shared_label_expected.json`,
each parsed through the real frontmatter path and labelled by the real
`_content_label`:

| frontmatter | Python | Rust before | Rust after |
|---|---|---|---|
| `label: "\u001E"` | `ARTICLE` | `"\u{1e}"` | `ARTICLE` |
| `label: "\u001EARTICLE\u001E"` | `ARTICLE` | `"\u{1e}ARTICLE\u{1e}"` | `ARTICLE` |
| `label: Dispatch` (control) | `Dispatch` | `Dispatch` | `Dispatch` |
| `label: "  Dispatch  "` (control) | `Dispatch` | `Dispatch` | `Dispatch` |
| `label:` (**known divergence, not owned**) | `ARTICLE` | `"None"` | `"None"` |

The first case is the one named when the finding was raised: a label that
is whitespace only under Python falls through to `ui()` there and printed
the bare separator here. The second is the sharper one and was not
anticipated: a **padded** label shows the strip changing the *returned
value* rather than only the empty test, so the defect was never confined to
the fall-through branch. The two controls are the reason the fixtures
discriminate: `Dispatch` and `"  Dispatch  "` have the same shape and the
same code path, ASCII space is whitespace to both languages, and both agreed
before the fix and after.

Before the fix `the_label_matches_python_on_every_case_this_wp_owns` fails
naming both owned cases and neither control:

```
a label that is whitespace only under Python: python "ARTICLE", rust "\u{1e}"
a label padded with U+001E: python "ARTICLE", rust "\u{1e}ARTICLE\u{1e}"
```

`the_disagreeing_labels_are_ones_rust_std_trim_gets_wrong` is the same
tripwire the roster fixtures carry: it re-evaluates the **old** `.trim()`
expression against the committed cases and requires exactly two of the four
owned cases to still disagree, so a fixture edited into harmlessness fails
rather than going quiet.

### A second divergence in `content_label`, found and deliberately not fixed

Probing `content_label` turned up a defect that is **not** whitespace
handling and therefore outside even the extended grant. Python guards on
`value is not None`; the Rust does not, and `py_str(Value::Null)` is the
string `"None"`. Measured, not reasoned:

```
"label:" raw=Some(Null) rust="None"       (python: "ARTICLE")
```

It is reachable from an ordinary manuscript, because frontmatter is parsed
with `yaml.safe_load` and a bare `label:` is a YAML null on both sides. So a
manuscript with an empty `label:` key prints the literal word **None** as its
section label in the Rust typeset output and the correct UI label in Python.

It has not fired, for the same reason the whitespace defects have not:
the tracked corpus carries **548 `label:` keys across 20 distinct values,
and zero bare ones**, every one of them a non-empty scalar (`FAITHFUL
SYNTHESIS` 242, `FAITHFUL EDIT` 101, `ARTICLE` 68, and so on down to a
tail of eight values occurring once each). Latent, like the rest of this
WP, and for a different reason: the codepoints are absent in one case, the
empty key is absent in the other.

That 548 is a correction to this WP's own first count of 536, which was
summed off a `head`-truncated listing and dropped the tail. It was caught by
the rule 12 replay, which ran the enumeration in full. Rule 9 is not only
about other people's numbers.

It was not fixed. The grant said whitespace handling only, and the whole
sequence this WP is part of exists because a narrow grant is what stops a
fix from quietly becoming a rewrite. Instead it is committed as data:
the fixture carries the case with a `known_divergence` reason string, and
`the_null_label_divergence_is_known_and_still_open` asserts that Rust still
returns `"None"` with the failure message *"if this changed, the divergence
was fixed; clear `known_divergence` in the fixture and delete this test"*.

That shape was chosen deliberately over the two alternatives. Committing the
case with the Rust value as its expected value would cement the bug and make
the eventual fixer edit a green test. Leaving it out of the fixture entirely
would put the finding only in prose, where it is exactly the one-word fix
awaiting rediscovery that the extension was granted to avoid. A tripwire
does neither: the divergence is visible in committed data, and the day
someone fixes it the build tells them what to delete.

### A methodological finding, from the fixtures rather than about them

The roster test was first written with `assert_eq!` per case inside a loop.
It failed on the first disagreeing case and stopped, which meant the second
direction -- the strip defect, as distinct from the split defect -- was never
actually evidenced by the run that was supposed to evidence it. Rewriting it
to accumulate every mismatch and assert once at the end produced the
two-line failure message quoted earlier.

Generalised: **a short-circuiting assertion over a fixture set proves only
its first failure, so a test whose purpose is to demonstrate more than one
direction must accumulate rather than assert per case.** Both fixture tests
added here accumulate, for that reason. It belongs beside the guard rule,
since both are about a test proving what it claims rather than merely going
red.

### Suite

188 tests across 20 binaries, all passing. `cargo fmt --check` and
`cargo clippy --all-targets -- -D warnings` clean. Seven tests added, in two
new binaries `mag/tests/model_shared_roster.rs` (four) and
`mag/tests/model_shared_label.rs` (three).

## Verdicts

No parity verdict is produced by this WP. No committed oracle changed: the
three fixture files added are new, and no existing `mag/tests/*_expected.*`
was touched, which is the expected shape for a fix whose effect the corpus
cannot reach.

## Residuals

- **`content_label` carries a second divergence that is NOT whitespace and
  was deliberately not fixed**: Python guards on `value is not None`, the
  Rust does not, and `py_str(Value::Null)` is `"None"`, so a bare `label:`
  prints the word **None** as a section label. Measured, latent (zero bare
  `label:` keys in 548 tracked ones), committed as a fixture case with a
  `known_divergence` reason, and tripwired by
  `the_null_label_divergence_is_known_and_still_open`. It needs an owner and
  the test says what to delete when it gets one.
- **Neither fix is observable in any rendered output**, because the corpus
  contains none of the four codepoints and no bare `label:` key. Rule 10:
  this evidence cannot discriminate between "the fixes are correct in
  production" and "the fixes are correct on fixtures and production never
  exercises them". Only the second is shown. Nothing in the reader PDF or
  the web edition changes, and no before/after render is offered, because
  there would be nothing to see.
- **The Python measurements are from one interpreter**, CPython 3.12.11 with
  Unicode 15.0.0. The `isspace` set is Unicode-version-dependent and the
  `strip`/`split` equivalence is CPython-implementation-dependent; neither
  was checked against another Python version or another implementation. If
  the project's Python moves, `mag/tests/model_shared_isspace_expected.txt`
  must be regenerated, and the guard will say so by failing.
- **Every U+001E case is synthetic.** No captured source has ever contained
  one, so the fixtures show what the two functions *would* do, not what they
  have done. That is unavoidable for a latent defect and is the reason each
  set keeps agreeing controls: they are the only fixtures whose shape is also
  plausible as real content.
- **The brief's corpus file count (833) does not reproduce**; the measured
  counts are 1,433 tracked and 1,874 on disk. The discrepancy is unexplained
  and may indicate the earlier scan used a narrower scope. It does not affect
  the conclusion, which is zero under every scope measured. Recorded here
  rather than silently corrected, because rule 9's citation clause now binds
  briefs and coordination messages and the correction is the useful artifact.
- **`clamp_roster` was not re-verified.** It handles no whitespace, which is
  all this WP's sweep of `shared.rs` claims about it; whether its
  `len`/slice/`rfind` are codepoint-correct against the Python is a separate
  question that no test here covers.
- **The `mag/src/` sweep outside `shared.rs` is unaudited.** Roughly 180
  `trim`/`split_whitespace` sites exist. Most are not ports of a Python
  string operation, but which ones are has not been determined, and the
  `shared.rs` sweep says nothing about them.

## Status

done
