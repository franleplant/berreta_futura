# WP-5.4a cover text helpers

## Base

First submission: `1f60fd7`, plan revision 20 (`7684445`).
Rework base: `24de8d9`, plan revision 23, after rejection at `ff5cd21`.

## Commands

Oracle generation. Both dumps are produced by these two inline invocations
and nothing else; replaying them must reproduce the committed JSON
byte-for-byte.

**Use `uv run python`, not a bare `python3`.** This machine has two
interpreters on different Unicode versions: the system `python3` is 3.9.6 on
Unicode 13.0.0, while `uv run python` is 3.12.11 on 15.0.0. Regenerating the
Unicode oracle or the packed tables with the system interpreter comes out
roughly forty entries short in each map, and the sweeps then fail against the
committed data. Every command below is pinned to `uv run python` for that
reason.

The four-function oracle, including the live edition 010 row:

```
uv run python -c '
import json, sys, yaml
sys.path.insert(0, "src")
from magazine.cover import _cover_date, _cover_contributors, cover_tab_issue, cover_tab_identity
from types import SimpleNamespace as NS

def ed(articles=(), cover=None, language="en", issue="010", name="Berreta Futura"):
    return NS(articles=[NS(author=a) for a in articles], cover={} if cover is None else cover,
              language=language, issue_number=issue, publication_name=name)

dates = ["2026-09-13", "2026-09", "2026", "2026--13", "-09-13", "2026-09-13-14", "", "2026-09-"]
contrib = {
 "010_shape": ed(["Ada Lovelace", "Grace Hopper"]), "single": ed(["Ada Lovelace"]),
 "dup_exact": ed(["Ada Lovelace", "Ada Lovelace"]), "dup_case": ed(["Ada Lovelace", "ADA LOVELACE"]),
 "dup_casefold_sharp_s": ed(["Strasse", "STRAßE"]), "strip_ascii": ed(["  Ada Lovelace  "]),
 "strip_u001f": ed(["Ada\x1f", "Grace"]), "blank_skipped": ed(["   ", "Ada"]),
 "sharp_s_upper": ed(["Straße"]), "ligature_upper": ed(["ﬁre Ada"]),
 "deck_string": ed([], {"deck": "  A deck  "}), "deck_absent": ed([], {}),
 "deck_null": ed([], {"deck": None}), "deck_int": ed([], {"deck": 5}),
 "deck_bool": ed([], {"deck": True}), "deck_list": ed([], {"deck": ["a", "b"]}),
 "deck_empty": ed([], {"deck": "   "}),
 "deck_map": ed([], {"deck": yaml.safe_load("{a: 1, b: x}")}),
}
issues = {
 "en_010": ed(language="en", issue="010"), "en_us": ed(language="en-US", issue="010"),
 "es": ed(language="es", issue="010"), "es_ar": ed(language="es-AR", issue="7"),
 "pad_1": ed(language="en", issue="1"), "wide": ed(language="en", issue="1234"),
 "negative": ed(language="en", issue="-1"), "empty_issue": ed(language="en", issue=""),
 "empty_lang": ed(language="", issue="010"),
}
idents = {"plain": ed(name="Berreta Futura"), "sharp_s": ed(name="Straße"), "lower": ed(name="berreta futura")}

raw = yaml.safe_load(open("editions/010/edition.yaml"))
live = ed([a.get("author", "") for a in raw.get("articles", [])], raw.get("cover") or {},
          raw.get("language") or "en", str(raw.get("issue_number")), "Berreta Futura")
contrib["edition_010"] = live
issues["edition_010"] = live
idents["edition_010"] = live
dates.append(str(raw.get("publication_date")))

out = {
 "cover_date": {d: _cover_date(d) for d in dates},
 "cover_contributors": {k: _cover_contributors(v) for k, v in contrib.items()},
 "cover_tab_issue": {k: cover_tab_issue(v) for k, v in issues.items()},
 "cover_tab_identity": {k: cover_tab_identity(v) for k, v in idents.items()},
}
json.dump(out, open("mag/tests/cover_text_expected.json", "w"), indent=1, sort_keys=True, ensure_ascii=False)
'
```

The Unicode oracle (casefold map, uppercase map, and the `str.isspace()`
codepoint set):

```
uv run python -c '
import json
casefold = {str(c): chr(c).casefold() for c in range(0x110000) if chr(c).casefold() != chr(c)}
upper = {str(c): chr(c).upper() for c in range(0x110000) if chr(c).upper() != chr(c)}
spaces = [c for c in range(0x110000) if chr(c).isspace()]
json.dump({"casefold": casefold, "upper": upper, "python_space": spaces},
          open("mag/tests/cover_text_unicode_expected.json", "w"), indent=1, sort_keys=True, ensure_ascii=False)
'
```

The two packed tables embedded in `mag/src/cover/text.rs` are generated from
the same Python, so the source data and the oracle cannot drift apart by
transcription:

```
uv run python -c '
def pack(mapping):
    return ";".join("%x:%s" % (c, ",".join("%x" % ord(ch) for ch in v)) for c, v in mapping)
fold = [(c, chr(c).casefold()) for c in range(0x110000) if chr(c).casefold() != chr(c)]
upper = [(c, chr(c).upper()) for c in range(0x110000) if chr(c).upper() != chr(c)]
print(pack(fold))
print(pack(upper))
'
```

Verification: `cargo test --test cover_text`, `cargo test`, `cargo fmt --check`,
`cargo clippy --all-targets -- -D warnings`.

## Tool versions

python 3.12.11 (`unicodedata.unidata_version` 15.0.0), uv 0.8.17, rustc 1.96.0.

## Metrics

Four ports, 41 committed oracle rows: `cover_date` 8, `cover_contributors` 19,
`cover_tab_issue` 10, `cover_tab_identity` 4. All agree byte-for-byte with the
Python originals. Plus three whole-plane sweeps over 1,112,064 codepoints each
(casefold, uppercase, `python_strip`), and one Rust-only assertion for the
`Tagged` arm, which has no Python oracle (see below).

The first submission said 41 while its own breakdown summed to 40; the
`deck_map` fixture added in this rework makes the total genuinely 41.

### Branch enumeration, read from the Python

`_cover_date` (3 branches): 3 non-empty parts joined; fewer or more than 3
parts returned unchanged; exactly 3 parts with one empty returned unchanged
(`all(parts)` is false on `""`). Covered by `2026-09-13`, `2026-09`, `2026`,
`2026-09-13-14`, `2026--13`, `-09-13`, `2026-09-`, `""`.

`_cover_contributors` (7 branches): at least one author, joined and uppercased;
empty author skipped; duplicate-by-casefold skipped keeping the first casing;
and the deck fallback, whose value is handed to `python_str` and is enumerated
arm by arm below.

`cover_tab_issue` (4 branches): language prefix `en` versus anything else;
`zfill` padding versus no padding; and `zfill`'s sign branch.

`cover_tab_identity` (1 branch): uppercase of the publication name.

### `python_str`, arm by arm

The first submission put this function under a blanket "all covered by
fixture", which was false for two arms and is the shape rule 10 forbids. Every
arm, with its status:

| arm | status |
|---|---|
| `Null` | reached by fixture `deck_null`, yields the literal `"None"` |
| `Bool` | reached by fixture `deck_bool` |
| `Number` | reached by fixture `deck_int` |
| `String` | reached by fixture `deck_string` and by edition 010 |
| `Sequence` | reached by fixture `deck_list` |
| `Mapping` | reached by fixture `deck_map`, ADDED IN THIS REWORK |
| `Tagged` | UNREACHABLE from safe-loaded YAML; no Python oracle exists |

`Tagged` is unreachable because the input that produces it is one the Python
oracle refuses outright: `yaml.safe_load("deck: !mytag x")` raises
`ConstructorError`, while `serde_yaml` parses the same document into
`Value::Tagged`. Standard tags do not reach the arm either, since both sides
resolve `!!str 5` to a plain string. So no fixture can establish equality for
it, and the arm is kept only for fidelity to the Python's own `match`
structure over the value type.

### Branches edition 010 cannot reach

010 has nine authored articles, so it reaches ONLY the authored branch of
`_cover_contributors`, the `en` label, the padding branch of `zfill`, and the
three-part date. Every other branch is unreachable from the corpus and is
covered by fixture: all six reachable deck-fallback shapes, the empty-author
skip, the `zfill` sign branch, the non-`en` label, the non-padding and
over-width issue numbers, and all four non-canonical date shapes. The one
exception is `python_str`'s `Tagged` arm, which is covered by no fixture for
the reason given above rather than by oversight.

010 does reach one branch worth naming, and it is not vacuous: `Anthropic`
authors two of its nine articles, so the real edition exercises the dedup path
and the committed row shows eight names, not nine.

### Rows that do not discriminate (protocol rule 10)

`deck_empty` (`"   "`) and `deck_absent` both produce `""`, as does
`blank_skipped` on its skipped element. Those three rows agree by producing an
empty string, so each is weak evidence on its own; they are kept because
together they separate three distinct code paths that all happen to end at the
same value, and probe G below shows the absent-versus-present distinction is
load-bearing.

### Discrimination proofs

Each perturbation was applied to the shipped source, the named test run, and
the source restored. All seven fire:

| probe | perturbation | result |
|---|---|---|
| A | `python_casefold` to `to_lowercase` | `cover_contributors` FAILED |
| F | same, against the sweep | `casefold` sweep FAILED |
| C | `python_upper` to `to_uppercase` | `uppercase` sweep FAILED |
| B | `is_python_space` drops U+001C-U+001F | `cover_contributors` FAILED |
| D | `python_zfill` loses the sign branch | `zfill` FAILED |
| E | `deck: null` yields `""` instead of `"None"` | `cover_contributors` FAILED |
| G | absent deck yields `"None"` instead of `""` | `cover_contributors` FAILED |
| H | `Mapping` keys via `python_str` not `python_repr` | `cover_contributors` FAILED |
| I | `Mapping` values via `python_str` not `python_repr` | `cover_contributors` FAILED |
| J | `Tagged` routed through repr, as `manifest.rs` does | `tagged_arm` FAILED |

One earlier probe did NOT discriminate and was corrected rather than recorded:
perturbing the uppercase table's *hit* branch left the sweep green, because the
codepoints that expose the skew have no Python uppercase at all and therefore
take the identity fallback. The probe was rewritten against the fallback branch,
where it fires. A probe that passes is not evidence that the code is right.

## Verdicts

`cargo test`: 10 suites green, including `cover_text` at 8 tests.
`cargo fmt --check` clean, `cargo clippy --all-targets -- -D warnings` clean.

## Residuals

**Python is on Unicode 15.0.0 and Rust's standard library is newer, and the
two disagree on 55 codepoints.** Measured, not assumed: `char::to_uppercase`
gives an uppercase for 55 codepoints where CPython 3.12.11 gives none, across
U+019B, U+0264, U+1C8A, U+A7CD-U+A7DB, U+10D70-U+10D85 (Garay) and
U+16EBB-U+16EC4. `char::to_lowercase` disagrees similarly on U+1C89. Rather
than accept a divergence, both case operations are pinned to Python's tables
(1530 casefold entries, 1525 uppercase entries, identity fallback), so the port
does not depend on Rust's Unicode version at all. The sweeps prove it over the
whole plane. **This deliberately freezes these two operations on Unicode 15.0.0**,
which is right while Python is the oracle and should be revisited at WP-6.1,
when Python is deleted and Rust's tables become the definition; a later Unicode
is arguably the correct behaviour then, but it is a product decision rather
than a port decision.

**The `Tagged` arm had already drifted from `manifest.rs`, and this WP decides
it rather than leaving both.** `python_str(Tagged(String("x")))` yields `x`
here and `'x'` in `manifest.rs`, str versus repr. Neither is verified, because
neither can be: the Python refuses the input. The decision taken, and the
reasoning, so WP-5.1e can adopt or overrule it deliberately:

- **This port keeps `x`, unwrapping to the underlying value's `str()`.** The
  function models Python's `str()`, and `str()` of a string never adds quotes.
  `manifest.rs` produces `'x'` incidentally rather than by choice: its `py_str`
  has no `Tagged` arm at all, so a tagged value falls through `other =>
  py_repr_value(other)`, which is the right destination for `Sequence` and
  `Mapping` (Python's `str(dict)` does repr its contents) and the wrong one for
  a scalar that a caller asked to stringify.
- **The real finding is at the loader, not in either copy.** Python and Rust
  diverge one step earlier: `safe_load` REFUSES a custom tag while `serde_yaml`
  accepts it, so the two sides disagree about whether the document loads at all.
  Whatever `python_str` does with a `Tagged` is then unreachable in the Python
  and reachable in the port. The fix that makes both copies moot is for the
  manifest loader to refuse tagged values, which MATCHES Python's strictness
  rather than exceeding it and so does not run into revision 23's rule that a
  port may not be stricter than its oracle. Recommended to WP-5.1e and to
  whoever owns `manifest.rs`; not done here, since this WP owns neither the
  loader nor `manifest.rs`.
- Probe J pins the decision: switching this arm to `manifest.rs`'s repr
  behaviour fails `tagged_arm_has_no_python_oracle_and_unwraps`.

**Two helpers are duplicated because rule 1's Owns boundary forbids importing
them.** `is_python_space` is private in `mag/src/model/doc.rs:492` and `py_str`
is private in `mag/src/model/manifest.rs:2142`; this WP owns neither file.
Per the Phase 5 preamble this is the sanctioned case for a copy, and the
preamble asks for a test that the copies agree. This WP does something stronger
instead: it pins its copies to **Python** over the whole codepoint plane and
over the value shapes `deck` can take, which is what both Rust copies are
trying to be. `py_repr` was genuinely imported from `model::shared` rather than
copied, since WP-5.1d made it `pub(crate)`.

**The seam these two helpers create should be closed the way `py_repr` was.**
`py_str`, `py_repr_value` and `is_python_space` are Python-semantics helpers of
exactly the kind WP-5.1d lifted into `mag/src/model/shared.rs`, and they were
left behind. A successor to WP-5.1d, or WP-6.1, should lift them; until then
each new port WP that needs Python's `str()` or `strip()` faces the same choice.
Note `model_helpers.rs`'s duplicate audit scans only the four model modules, so
it does not see `mag/src/cover/text.rs` and would not catch drift here.

**`cover_date` receives a `String` in Rust where Python receives `Any` and calls
`str()` on it.** The Python signature is annotated `value: str` and every call
site passes `edition.publication_date`, which the Rust model already stores as
a `String` produced by `py_str`, so the coercion has happened upstream and the
branch is unreachable from the Rust type. Recorded rather than ported.

## Status

done
