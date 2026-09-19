# WP-5.1f pin `is_name_roster`'s whitespace handling to Python

## Base

`3b57c36` (WP-5.5a, "refactor(model): lift the four shared edition-text
helpers"), which is where `is_name_roster` acquired its current home in
`mag/src/model/shared.rs`. Work was done in a detached worktree at that
commit and rebased onto `art_directed` at landing.

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

Whether the helper fires on the corpus at all, which is what makes the
zero above a statement about the four codepoints rather than about the
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

The demonstration, both directions. The first run restores the pre-fix
`shared.rs` and must FAIL naming both disagreeing cases while the control
passes; the second restores the fixed one and must pass:

```
git show HEAD~1:mag/src/model/shared.rs > mag/src/model/shared.rs
cd mag && cargo test --test model_shared_roster; cd ..
git show HEAD:mag/src/model/shared.rs > mag/src/model/shared.rs
cd mag && cargo test --test model_shared_roster
```

Every whitespace-handling site in `mag/src/model/shared.rs`, which is the
scope of the sibling-helper audit below. The wider `mag/src/` sweep is
reported in the audit section but is not this WP's Owns:

```
grep -n 'trim\|split_whitespace\|is_whitespace' mag/src/model/shared.rs
```

Every implementation of, and every call site of, the roster helper, across
all of `mag/src/`:

```
grep -rn 'name_roster\|ROSTER' --include='*.rs' mag/src/
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
either scope, and the count is recorded here as measured rather than as
inherited. The load-bearing number, zero, does reproduce.

The zero is a statement about the four codepoints and not about a dead
function: the separator U+2022 occurs **195 times across 8 tracked files**,
so `is_name_roster` does fire on real content. It has simply never been
handed a field separator.

Status per rule 3b: the defect was **LIVE on the branch** in
`mag/src/model/shared.rs` and is now fixed. It was **latent, not firing**,
because no corpus input reaches it. Consumers who must not build on the old
behaviour: WP-2.1's contents-entry author rendering, WP-2.2a, and WP-5.5a's
web port. There is exactly one implementation and exactly one call site,
`mag/src/typeset/content.rs:535`, both confirmed by the repository-wide
grep in the Commands block.

### Sibling helpers: one has the same omission

`mag/src/model/shared.rs` has three whitespace-handling sites. After this
fix:

| site | Python original | Rust | verdict |
|---|---|---|---|
| `is_python_space` (line 185) | `str.isspace` | `is_whitespace() \|\| '\u{1c}'..='\u{1f}'` | correct, and pinned by a whole-plane test |
| `py_strip` (line 189) | `str.strip` | `trim_matches(is_python_space)` | correct |
| `content_label` (line 331) | `str(value).strip()` | `value.trim().to_string()` | **same omission** |

`content_label` is the pattern repeating, and it is trivially identical:
`html_edition.py::_content_label` reads `str(value).strip()`, the Rust reads
`.trim()`, and the one-word change to `py_strip(&value)` is the whole fix.
Its reachable consequence has the same shape as the one fixed here: a
`label:` of `"\u{1e}"` strips to empty in Python and falls through to
`ui(language, content_mode)`, while Rust keeps it non-empty and prints the
separator as the label.

**It was not fixed, because it is not in this WP's Owns**, and widening a
narrow grant silently is the failure WP-5.5a avoided when it declined to fix
`is_name_roster` during a lift. It is raised rather than done, and it needs
an owner.

The other two helpers WP-5.5a lifted are clean: `ui` does no whitespace
handling at all, and `clamp_roster` does none either (its `len`/slice/`rfind`
are codepoint- and byte-correct against the Python, which is a separate
question from this one and was not re-verified here).

Outside `shared.rs` the same grep over all of `mag/src/` finds roughly 180
`trim`/`split_whitespace` sites. **No claim is made about them.** They were
not audited, most are not ports of a Python string operation at all, and
scoping a whole-tree audit into this WP is exactly the widening the previous
paragraph declines.

### Suite

185 tests across 19 binaries, all passing. `cargo fmt --check` and
`cargo clippy --all-targets -- -D warnings` clean. Four tests added, in one
new binary `mag/tests/model_shared_roster.rs`.

## Verdicts

No parity verdict is produced by this WP. No committed oracle changed: the
two files added are new, and no existing `mag/tests/*_expected.*` was
touched, which is the expected shape for a fix whose effect the corpus
cannot reach.

## Residuals

- **`content_label` in `mag/src/model/shared.rs` carries the identical
  omission** and is left for its owner. It is a one-word change.
- **The fix is not observable in any rendered output**, because the corpus
  contains none of the four codepoints. Rule 10: this evidence cannot
  discriminate between "the fix is correct in production" and "the fix is
  correct on fixtures and production never exercises it". Only the second is
  shown. Nothing in the reader PDF or the web edition changes, and no
  before/after render is offered, because there would be nothing to see.
- **The Python measurements are from one interpreter**, CPython 3.12.11 with
  Unicode 15.0.0. The `isspace` set is Unicode-version-dependent and the
  `strip`/`split` equivalence is CPython-implementation-dependent; neither
  was checked against another Python version or another implementation. If
  the project's Python moves, `mag/tests/model_shared_isspace_expected.txt`
  must be regenerated, and the guard will say so by failing.
- **The `<RS>` cases are synthetic.** No captured source has ever contained
  one, so the fixtures show what the function *would* do, not what it has
  done. That is unavoidable for a latent defect and is the reason the
  agreeing control is kept: it is the only fixture whose shape is also
  plausible as real content.
- **The brief's corpus file count (833) does not reproduce**; the measured
  counts are 1,433 tracked and 1,874 on disk. The discrepancy is unexplained
  and may indicate the earlier scan used a narrower scope. It does not affect
  the conclusion, which is zero under every scope measured.

## Status

done
