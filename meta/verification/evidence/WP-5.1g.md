# WP-5.1g the null-label guard, a class B defect in `content_label`

## Base

`160c39e` (WP-5.1f's extension, "pin content_label to Python whitespace
too"), which is the commit whose evidence raised this divergence, committed
it as fixture data and tripwired it. This WP is the tripwire being answered.

## Commands

Which YAML spellings are null, on both sides, and what each engine then
prints. Python first:

```
uv run python - <<'PY'
import sys, types
sys.path.insert(0, "src")
from magazine.html_edition import _content_label
from magazine.publication_document import parse_publication_document
edition = types.SimpleNamespace(language="en")
for line in ["label:", "label: ~", "label: null", "label: Null", "label: NULL",
             'label: "None"', "label: None", 'label: ""', 'label: "   "',
             "label: false", "label: 0", "label: Dispatch"]:
    doc = parse_publication_document(f"---\n{line}\n---\n\nBody.\n")
    raw = doc.metadata.get("label")
    got = _content_label(edition, doc, "article")
    print(f"{line!r:20} raw={raw!r:12} python={got!r}")
PY
```

Python's agreement with the committed values. **This is corroboration, not
the fixture's basis**, and it is the block that retires at WP-6.1 when the
oracle is deleted; the fixture and its tests survive it:

```
uv run python - <<'PY'
import json, sys, types
sys.path.insert(0, "src")
from magazine.html_edition import _content_label
from magazine.publication_document import parse_publication_document
edition = types.SimpleNamespace(language="en")
cases = json.load(open("mag/tests/model_shared_label_expected.json"))["cases"]
bad = []
for case in cases:
    front = case["frontmatter"]
    doc = parse_publication_document(f"---\n{front}\n---\n\nBody.\n")
    got = _content_label(edition, doc, case["content_mode"])
    expected = case["expected"]
    flag = "" if got == expected else "  <-- PYTHON DISAGREES"
    if flag:
        bad.append(case["name"])
    print(f"{front!r:34} expected={expected!r:11} python={got!r}{flag}")
print(f"\ncases={len(cases)} python_disagreements={len(bad)} {bad}")
PY
```

Whether the defect has ever fired, over every tracked `label:` key in
`editions/` and `library/sources/`. The second and third counts are the ones
that matter: a null spelling would have printed `None`, and a boolean would
hit the class C case below:

```
echo "total: $(grep -rh --include='*.md' --include='*.yaml' -E '^[[:space:]]*label:' \
  editions library/sources | wc -l | tr -d ' ')"
echo "distinct: $(grep -rh --include='*.md' --include='*.yaml' -E '^[[:space:]]*label:' \
  editions library/sources | sort -u | wc -l | tr -d ' ')"
echo "null spellings: $({ grep -rh --include='*.md' --include='*.yaml' \
  -E '^[[:space:]]*label:[[:space:]]*(~|[Nn]ull|NULL)?[[:space:]]*$' \
  editions library/sources || true; } | wc -l | tr -d ' ')"
echo "booleans: $({ grep -rh --include='*.md' --include='*.yaml' \
  -E '^[[:space:]]*label:[[:space:]]*(true|false|True|False|yes|no)[[:space:]]*$' \
  editions library/sources || true; } | wc -l | tr -d ' ')"
```

The demonstration, both directions. `160c39e` is the commit before the fix,
so the first run must FAIL naming all four null spellings while the four
tests that do not depend on the guard pass; the second must pass:

```
cp mag/src/model/shared.rs /tmp/wp51g-fixed.rs
git show 160c39e:mag/src/model/shared.rs > mag/src/model/shared.rs
cd mag && cargo test --test model_shared_label; cd ..
cp /tmp/wp51g-fixed.rs mag/src/model/shared.rs
cd mag && cargo test --test model_shared_label
```

Every whitespace-handling and null-handling site in
`mag/src/model/shared.rs`, which is the boundary this WP's sweep establishes.
The pattern covers the pinned spellings as well as the std ones, because
after WP-5.1f and this WP the fixed sites no longer say `trim` and a
std-only pattern would report them absent rather than fixed:

```
grep -n 'trim\|split_whitespace\|is_whitespace\|py_strip\|is_python_space\|is_null' \
  mag/src/model/shared.rs
```

Every implementation and every call site of `content_label`, across all of
`mag/src/`:

```
grep -rn 'content_label' --include='*.rs' mag/src/
```

Repository gate:

```
cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

## Tool versions

python 3.12.11 (Unicode 15.0.0, via `uv run python`), rustc 1.96.0. No crate
added; `Cargo.toml` and `Cargo.lock` untouched.

## Metrics

### The defect, and why it is class B rather than class A

`html_edition.py::_content_label` guards on `value is not None`:

```
value = document.metadata.get("label")
return str(value).strip() if value is not None and str(value).strip() else _ui(...)
```

The port had no such guard, and `py_str(Value::Null)` is the string `"None"`,
which is non-empty, so a null label took the declared branch and printed
itself.

Measured on both sides rather than read off the source. All four YAML
spellings of null parse to null in **both** engines, and unquoted `None` is
a **string** in both, because YAML has no `None` literal:

| frontmatter | parsed, both engines | Python | Rust before | Rust after |
|---|---|---|---|---|
| `label:` | null | `ARTICLE` | `"None"` | `ARTICLE` |
| `label: ~` | null | `ARTICLE` | `"None"` | `ARTICLE` |
| `label: null` | null | `ARTICLE` | `"None"` | `ARTICLE` |
| `label: NULL` | null | `ARTICLE` | `"None"` | `ARTICLE` |
| `label: None` | string `None` | `None` | `None` | `None` |
| `label: ""` | string, empty | `ARTICLE` | `ARTICLE` | `ARTICLE` |

The classification matters because the remedy does not distinguish it. Per
rule 6a this is **class B, a live product defect surfacing as a divergence**,
not class A: the fix is identical to a port-fidelity fix, which is exactly
how it hides inside one. Two things follow, and both are acted on here.

**Reachability decides schedule.** This is not a gap in a branch that
edition 010 cannot reach. It ships wrong output the day a writer types
`label:` with nothing after it -- a plausible keystroke, not a pathological
input -- and what it ships is the literal word **None** as the section label
on a reader page.

**The regression test must outlive the oracle.** Handled below.

### Severity, stated honestly

It is **reachable from an ordinary manuscript**. Frontmatter is parsed with
`yaml.safe_load` on the Python side and `serde_yaml` on the Rust side, and
both turn a bare `label:` into null, so nothing exotic is required: an author
who writes the key and leaves the value for later gets `None` printed where
the label belongs.

It is **latent only by corpus accident**. The tracked corpus carries **548
`label:` keys across 20 distinct values, of which zero are any null spelling
and zero are booleans**. That is a fact about what has been written so far,
not a property of the system, and nothing prevents the next manuscript from
containing one. The unreachability that made WP-5.1f's whitespace defects
quiet was of the same kind, but the U+001E cases were at least implausible as
real input; a bare `label:` is not.

### The fix

One line, a `filter` before the `map`:

```
.get(Value::String("label".to_string()))
.filter(|value| !value.is_null())
.map(py_str)
```

A null now behaves exactly as an absent key does, which is what Python's
guard says and what the product wants. Nothing else in `content_label`
changed, and nothing else in `shared.rs` was touched.

### The fixture's basis changed: values, not agreement

The WP-5.1f fixture carried a `python` field and every test asserted
"matches Python". Per rule 6a that is the wrong basis for a class B
regression test, because after WP-6.1 deletes the Python a matches-Python
assertion documents nothing and no reader can recover **why** the value was
right. The file was rewritten accordingly:

- `python` is gone. The field is now `expected`, and it is the **correct
  output**, asserted as such.
- Every case carries a `why` string giving the reason the value is correct
  in terms of the product, not the oracle -- "a null label declares nothing,
  so the section takes the UI label for its content mode", not "Python
  returns this". A test refuses to load a case whose `why` is empty.
- The fixture is **hand-authored**, not generated. There is no longer a
  regeneration command, because a generator would make Python the definition
  again through the back door: the file would silently follow Python if
  Python changed.
- Python's agreement is measured **separately**, in the corroboration block
  above, and reported here: **13 cases, 0 Python disagreements**. That block
  is the part that retires at WP-6.1. The fixture and its seven tests do not
  depend on it and will still say what they mean when the oracle is gone.

### The straddle pair, replacing the tripwire

WP-5.1f's `the_null_label_divergence_is_known_and_still_open` said, in its
own failure message, "if this changed, the divergence was fixed; clear
`known_divergence` in the fixture and delete this test". That instruction was
followed literally: the flag is gone from the file, the test is deleted, and
`the_null_label_straddles_the_string_none` stands in its place.

The straddle is the sharpest available, and the reason is the defect's own
shape: **the bug made a null impersonate one specific legal value.**

| input | before the guard | after |
|---|---|---|
| `label:` | `"None"` | `ARTICLE` |
| `label: None` | `"None"` | `"None"` |

Before the fix those two inputs were **indistinguishable in the output**.
After it they differ, and each is pinned to its own correct value with its
own reason. The `assert_ne!` between them carries the message that they
rendered alike before the guard existed, which is what made the defect
invisible to anyone reading rendered pages rather than code.

`every_spelling_of_null_declares_nothing` covers the other three spellings
and adds `label: ""`, which reaches the same fallback by a different route
and so must keep passing even with the guard removed -- it is the case that
proves the guard is not doing more than it should.

### A fixture flaw inherited from WP-5.1f, and corrected

WP-5.1f's padded case is `label: "<U+001E>ARTICLE<U+001E>"` expecting
`ARTICLE`. **That expected value is also the fallback**, so the case passes
whether the code strips the padding and returns the declared label or throws
the label away and returns `ui("en", "article")`. It cannot tell the two
branches apart, and it was the only padded case.

The case is kept, with its `why` now recording the limitation, and a second
padded case `label: "<U+001E>Dispatch<U+001E>"` expecting `Dispatch` is added
beside it. `a_padded_label_proves_the_declared_branch_was_taken` asserts both
that the value is `Dispatch` and, with `assert_ne!`, that it differs from
`ui("en", "article")` -- so the case cannot silently decay into the
indistinguishable shape if the fallback ever changes.

Generalised, and offered as a fixture rule: **an expected value that equals
the fallback proves only that one of the two branches ran.** It is the same
family as the short-circuit findings from WP-5.1f, in that the test looks
like it discriminates and does not.

### Class C: `label: false` prints "False" in both engines

Both engines were executed, not read:

```
'label: false'   expected='False'   python='False'     (rust: "False")
```

Python's guard is `value is not None`, and `False is not None`, so it
stringifies and returns `"False"`. The Rust does the same. **Parity is blind
to this by construction**, because the two engines agree, and agreement is
what parity measures.

**It was not fixed.** Changing it would change the Python oracle, which is a
plan-level decision and not this WP's. But it is committed rather than left
in prose, in the form WP-5.1f established for exactly this purpose: the case
carries `status: "agreed_but_suspect"` instead of `"correct"`, its `why`
states plainly that it is pinned as the behaviour both engines have and
**not** as a correct value, and
`the_class_c_case_is_flagged_rather_than_asserted_correct` asserts the
current value with the message "pinned as current behaviour, not endorsed;
if this changed, the plan-level decision was taken and this case needs
rewriting". The same test asserts every case declares one of the two
statuses, so a future case cannot be added without choosing.

This is the flag being used for its second purpose. WP-5.1f's was class B
awaiting an owner; this one is class C awaiting a plan decision. The
mechanism is the same and the distinction is in the status string, which is
why the field is a string rather than a boolean.

**Why it is committed at all**: it is the plan's one named instance of
"equality is not correctness", and the whole reason it needs recording is
that no amount of parity work will ever surface it. A fixture entry is the
only place it can live where it will be seen again.

### The boundary this sweep establishes

The grep in the Commands block returns **eight lines and only eight**, which
is the enumeration behind the claim, and the boundary is: *every site in
`mag/src/model/shared.rs` that handles whitespace or null*.

| line | site | verdict |
|---|---|---|
| 184-185 | `is_python_space` (definition) | correct, pinned over the whole plane by WP-5.1f |
| 188-189 | `py_strip` (definition) | correct |
| 250 | `is_name_roster`, segment strip | pinned, WP-5.1f |
| 255 | `is_name_roster`, word split | pinned, WP-5.1f |
| 330 | `content_label`, the null guard | **added here** |
| 332 | `content_label`, the strip | pinned, WP-5.1f |

**What the boundary excludes, so the next reader does not repeat the sweep
to find out**: it covers `shared.rs` only, and within it whitespace and null
only. It says nothing about the other `py_*` helpers' fidelity on other
axes, nothing about `ui` or `clamp_roster` beyond their containing no
whitespace or null handling, and nothing about the roughly 180
`trim`/`split_whitespace` sites elsewhere under `mag/src/`. Those were not
audited. Within the boundary, `shared.rs` is complete.

### Suite

**207 tests across 22 binaries after rebasing**, all passing, which is the
number a replay at this commit reports. At this WP's base `160c39e` it was
192 across 20; the difference is not this WP's, it is WP-0.2k, WP-2.2a and
the plan revisions that landed alongside them while this was in flight. This WP's own
contribution is the same either way: the label binary goes from three tests
to seven, net **+4**, even though WP-5.1f's tripwire was deleted as
instructed.

`cargo fmt --check` and `cargo clippy --all-targets -- -D warnings` clean,
re-run after the rebase rather than only before it.

Three figures, three corrections. The section first read 190, copied from a gate
run taken while the label binary still had five tests; re-deriving by summing
the per-binary `test result` lines gave 192. Then two rebases moved it again, to 202 and then 207, as WP-0.2k and WP-2.2a landed under this WP. The first CAS was refused for exactly that reason and the remedy was to rebase onto the new tip rather than to re-read and retry.
The lesson is the one the file-count error already taught: **a total is a
measurement with a timestamp, and the timestamp is the commit.**

## Verdicts

No parity verdict is produced by this WP. `mag/tests/model_shared_label_expected.json`
changed, deliberately and substantially: it is no longer an oracle of
Python's output but a specification of correct output, which is the point of
rule 6a. No other committed oracle was touched.

## Residuals

- **`label: false` is class C and unfixed**, pinned as `agreed_but_suspect`.
  It needs a plan-level decision about whether a boolean label should
  stringify, fall through to the UI label, or be refused at load. Whatever is
  decided, the Python changes too, so it cannot be an agent-local fix.
- **The fixture is hand-authored, so an error in it is an error in the
  specification** and no generator will catch it. The corroboration block is
  the only cross-check, and it dies at WP-6.1. After that point the values
  stand on their `why` strings and on review.
- **Rule 10, what this cannot discriminate**: the corroboration shows Python
  and Rust now agree on 13 cases, which does not establish that the 13 are
  the right 13. `content_label` has inputs nobody has enumerated -- sequences,
  mappings, floats, dates -- and this WP added no case for any of them.
  Agreement on the covered set is not coverage.
- **The corpus counts are a snapshot.** 548 `label:` keys, zero null
  spellings, zero booleans, measured today. Nothing enforces that, and the
  class C case in particular would begin printing `False` on reader pages the
  first time someone writes `label: false`.
- **`ui` and `clamp_roster` were not re-verified** beyond the boundary
  statement above: they contain no whitespace or null handling, which is all
  that is claimed.

## Status

done
