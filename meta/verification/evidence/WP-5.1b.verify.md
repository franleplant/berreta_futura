# WP-5.1b verification

## Scope

Re-verification of the records port after rework. Protocol rule 3, critique
duty folded in.

- First submission `f044b99`: REJECTED at `44fb08c` for two material
  divergences found by a 41-case differential sweep. `canonicalize_url` kept
  an explicit port `0` where Python's `if parts.port` treats the integer as
  falsy, and because `source_id` hashes the canonical URL the two sides minted
  different record ids for the same page. `py_repr` did not escape
  non-printable characters, diverging on 5 of 13 probes and governing eight
  message sites.
- Rework under verification: `b39ccf3`.

## Verdict

**REJECTED.** The three code fixes are correct and well proven, and every
oracle digest reproduces. Two material findings block acceptance: a behavioural
divergence in `localize_figures` and `localize_extracts` that no oracle covers,
and an evidence section which, replayed as written, destroys the regression
coverage for the very defects that caused the first rejection.

## Owns

`b39ccf3` touches exactly eight files, all within Owns: `mag/src/model/records.rs`,
`mag/tests/model_records.rs`, four committed oracle JSON files, one fixture
file, and `meta/verification/evidence/WP-5.1b.md`. No Cargo files, no
`mag/src/model.rs`, no `doc.rs` or `manifest.rs`, no `*.verify.md`, no
`baseline.json`. PASS.

## Baseline

In a clean worktree at `b39ccf3`: `cargo fmt --check` exit 0,
`cargo clippy --all-targets -- -D warnings` exit 0, `cargo test` green
(8 records tests, `nocomments`, `parity_faults` 21.09 s).

All six oracle digests match the evidence table exactly, including
`model_records_expected.json` at 58040 bytes.

## Finding 1, material: absent figure and extract rows diverge

Found by my own probe; no existing oracle covers it.

When `base` is non-empty and `rows` is absent (`None`) or YAML null:

| side | message |
|---|---|
| Python | `Translation 'es' article a1 figures must be a list` |
| Rust | `Translation 'es' article a1 is missing figures: f1` |

The same divergence holds for extracts (`extracts must be a list` against
`is missing extracts: e1`). Both sides refuse, so nothing is silently
accepted, but the messages differ and full-message comparison is exactly the
discipline this WP's oracles are built on.

The cause is a Python truthiness translation of the kind the rework swept for
and missed here. `media_schema.py` reads:

```
if not isinstance(rows, list):
    raise ValidationError(f"Translation {language!r} article {article_id} figures must be a list")
```

`None` is not a list, so Python raises. `records.rs` reads:

```
None | Some(Value::Null) => Vec::new(),
```

which treats an absent key as an empty list and falls through to the
missing-ids comparison.

Reachability is ordinary rather than exotic: a translated `edition.yaml`
whose article omits the `figures:` or `extracts:` key while English carries
them. Forgetting to translate a figures block is among the likelier authoring
mistakes this validator exists to catch.

## Finding 2, material: replaying ## Commands destroys regression coverage

The evidence states its own acceptance check: "Regenerating every oracle above
and rerunning `cargo test --test model_records` must leave the four committed
JSON files byte-identical and the seven tests green; that is the whole
acceptance check for this WP."

That check fails as written. I extracted the four documented `uv run python`
blocks programmatically and ran them. Two committed files changed:

- `model_records_urls_expected.json` lost six cases: `http://e.com:0/x`,
  `https://e.com:/`, `https://e.com:0/`, `https://e.com:00/`,
  `https://e.com:000/`, `https://e.com:080/`.
- `model_records_create_expected.json` lost three cases: `empty_title`,
  `whitespace_title`, `empty_author`.

Those nine are precisely the regression fixtures for the port-`0` and
empty-title defects. The documented URL list is still the pre-fix 19 inputs
and the documented create list is still the pre-fix 5 cases.

The two halves fail differently, and the asymmetry is the dangerous part:

- `create_and_source_id_match_python` builds its cases on the Rust side, so
  the shrunken oracle fails loudly.
- `canonical_urls_match_python` iterates `expected.as_object().keys()`, so the
  oracle file *is* the case list. Shrinking it shrinks the test. After
  regeneration that test passes with the port-`0` coverage gone.

So an agent following this evidence to regenerate oracles silently removes the
guard on one of the two defects that caused the rejection, and the suite still
reports green.

## Finding 3, minor: the ports oracle has no regeneration command

`model_records_ports_expected.json` is pinned in the digest table and asserted
by `port_refusal_messages_match_python`, but `## Commands` carries no command
that produces it. It cannot be regenerated from the worktree alone, which rule
3 requires.

## Finding 4, minor: stale counts in ## Commands

The refusal-matrix header says "42 cases" where the file holds 49 (39 errors),
and the closing paragraph says "the four committed JSON files" where six are
committed.

## Verified sound

**The three fixes are correct, and each is discriminating.** I reverted each
in place and confirmed the named test fails, then restored and confirmed green:

| reverted fix | test | result |
|---|---|---|
| port-`0` filtering | `canonical_urls_match_python` | FAILED |
| `printable` escaping | `figure_and_extract_refusals_match_python` | FAILED |
| empty-title fallback | `create_and_source_id_match_python` | FAILED |

**The `printable` predicate genuinely matches `str.isprintable()`.** I swept 28
codepoints through `py_repr` by way of the public `localize_figures` language
argument, against a Python mirror. All 28 agree, covering Cc (U+0000, U+0007,
U+001B, U+001F, U+007F), Cf (U+00AD, U+200B, U+200E, U+2060, U+FEFF, U+180E,
U+1D173), Cn unassigned and noncharacter (U+0378, U+0605, U+FDD0, U+10FFFF),
Co (U+E000), Zl (U+2028), Zp (U+2029), Zs (U+00A0, U+202F, U+3000), and
printables (U+0020, U+00E9, U+4E2D, U+1F600, U+115F). The regex class
`[\p{C}\p{Z}]` with space excepted therefore covers exactly Python's exclusion
set, Cn included, which was the specific doubt worth testing. Five quote-
selection cases (`it's`, `say "hi"`, `both'"q`, backslash, tab and newline)
also agree.

**Ten further URL probes agree exactly**: empty string, scheme-relative
`//e.com/x`, bare `e.com/x`, lowercase and uppercase percent-encoding
(`%7e` and `%7E` both preserved), uppercase scheme and host with `%2F`,
`%c3%a9` upcased to `%C3%A9`, `?=novalue`, and duplicate query keys sorted.

**Two tag probes agree**: an empty string among tags is dropped, a
whitespace-only tag yields an empty list.

**The deliberate divergence is adequately handled and correctly judged.** For
`https://e.com:65536/` Python raises an uncaught `ValueError` and Rust returns
`ValidationError`, but the message text is identical
(`Port out of range 0-65535`). Refusing rather than crashing is the better
behaviour, matching it would mean panicking, and the message is pinned by
`model_records_ports_expected.json`. Recording it as a divergence rather than
hiding it is right.

**The corpus oracle is not vacuous.** My own mutation, record index 40's
`captured_at` set to `1999-12-31T23:59:59Z`, a field and index no previous
agent used, fails `library_sources_match_the_python_dump`.

## Required to clear

1. Match Python for absent `figures:` and `extracts:` rows in `localize_figures`
   and `localize_extracts`, and add both to the refusal matrix. While there,
   re-sweep the remaining `isinstance` translations the same way the truthiness
   sweep was done, since this defect is an `isinstance` case rather than a
   truthiness case and the earlier sweep was scoped to the latter.
2. Update `## Commands` so replaying it reproduces the committed oracles: the
   URL list must carry the six port cases, the create list the three new cases,
   and the ports oracle needs its own regeneration command.
3. Consider making `canonical_urls_match_python` drive its cases from the Rust
   side, as the create test does, so a shrunken oracle fails loudly instead of
   quietly reducing coverage. This is the structural fix for finding 2.
4. Correct the stale "42 cases" and "four committed JSON files" text.

## Commands

```
git show --stat b39ccf3
git worktree add /Users/franguijarro/.claude/jobs/7d99e27f/tmp/verify-wp51b2 b39ccf3
cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

Oracle replay, extracting the documented blocks rather than retyping them:

```
python3 - <<'PY'
import re, pathlib
txt = pathlib.Path('meta/verification/evidence/WP-5.1b.md').read_text()
cmds = txt.split('## Commands')[1].split('## Tool versions')[0]
blocks = re.findall(r'```\n(.*?)```', cmds, re.S)
body = ["set -e", "cd <worktree>"] + [b.strip() for b in blocks if 'uv run python' in b]
pathlib.Path('/tmp/replay51b.sh').write_text("\n".join(body) + "\n")
PY
bash /tmp/replay51b.sh && git status --short
```

Divergence probe, Rust side, as a temporary `mag/tests/zz_probe.rs` including
the module by `#[path = "../src/model/records.rs"]` and calling
`localize_figures(&base, rows, "a1", Path::new(...), language)` with `base`
non-empty and `rows` both `None` and `Some(Value::Null)`; Python mirror:

```
uv run python -c "
import sys; sys.path.insert(0,'src')
from pathlib import Path
from magazine.errors import ValidationError
from magazine.media_schema import localize_figures, Figure
base=(Figure('f1','s1',Path('/tmp/probe51b/x.png'),'','','','',''),)
try:
    localize_figures(base, None, article_id='a1', manuscript=Path('/tmp/probe51b/m.md'), language='es')
except ValidationError as e:
    print('|'.join(e.errors))
"
```

Discriminating proofs, each reverted with `sed -i ''` then restored from a copy:

```
sed -i '' 's/if let Some(number) = port.filter(|number| \*number != 0)/if let Some(number) = port/' src/model/records.rs
sed -i '' 's/other if printable(other) => out.push(other),/other if true => out.push(other),/' src/model/records.rs
sed -i '' 's/\.filter(|title| !title.is_empty())//' src/model/records.rs
cargo test --test model_records <name>
```

Negative check:

```
python3 -c "
import json,pathlib
p=pathlib.Path('mag/tests/model_records_expected.json'); d=json.loads(p.read_text())
d[40]['captured_at']='1999-12-31T23:59:59Z'
p.write_text(json.dumps(d,indent=2,sort_keys=True,ensure_ascii=False))"
cargo test --test model_records library_sources
```

## Tool versions

python 3.12.11, uv 0.8.17, rustc 1.96.0, poppler 25.08.0 (parity_faults only).

## Metrics

- Owns: 8 files, all within scope.
- Oracle digests: 6 of 6 match the evidence table.
- Documented-command replay: 2 of 6 oracle files changed, 9 cases lost.
- Discriminating proofs: 3 of 3 fired.
- New probes: 45 total, 43 agreeing, 2 divergent (figures and extracts absent
  rows). 28 codepoint, 5 quote, 10 URL, 2 tag probes all agree.
- Negative check: fires under a previously unused mutation.

## Verdicts

No parity verdict.json is produced by this WP; its oracles are JSON dumps,
digests listed above.

## Residuals

- The `canonical_urls_match_python` pattern of driving cases from the oracle
  file is worth auditing wherever else it appears in the Phase 5 ports, since
  it converts a shrunken oracle into silent coverage loss rather than a
  failure.
- The duplicate-URL raise site remains outside the refusal matrix, correctly,
  because Python's message names whichever duplicate `Path.glob` met first.

## Status

rejected
