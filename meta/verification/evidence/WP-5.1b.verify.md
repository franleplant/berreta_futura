# WP-5.1b verification

Verdict: **ACCEPTED** (third verification, second rework).

## Base

Worker commit `57d6929` (`fix(model): WP-5.1b isinstance divergence and
self-weakening oracle`). Verified in a fresh worktree at that commit.

## Rejection history

| submission | verdict | cause |
|---|---|---|
| `f044b99` | rejected at `44fb08c` | `canonicalize_url` kept an explicit port `0` (Python's `if parts.port` treats the integer as falsy), so `source_id` hashed a different canonical URL and the two sides minted different record ids for the same page; `py_repr` did not escape non-printables |
| `b39ccf3` | rejected at `2f1886a` | an isinstance divergence (absent or null `figures:`/`extracts:` where Python's `if not isinstance(rows, list)` refuses but the port normalized to empty); and a self-weakening oracle: replaying `## Commands` deleted the regression fixtures, and `canonical_urls_match_python` iterated the oracle file's own keys, so a shrunken oracle silently became a smaller test |
| `57d6929` | **accepted** | both causes fixed and proven; see below |

## Owns

`git show --stat 57d6929` lists exactly five paths: `mag/src/model/records.rs`,
`mag/tests/model_records.rs`, `mag/tests/model_records_cases_expected.json`,
`mag/tests/model_records_fixtures/cases.yaml`, and this WP's evidence file.
No Cargo files, no `mag/src/model.rs`, no `doc.rs` or `manifest.rs`, no
`*.verify.md`, no `baseline.json`.

## Baseline

`cargo fmt --check`, `cargo clippy --all-targets -- -D warnings` and
`cargo test` all exit 0 in the worktree: 69 unit tests, 8 records tests,
`nocomments`, and `parity_faults` at 21.20 s.

## The round trip

This is the heart of this verification, because the second rejection was
precisely that the documented commands did not reproduce the artifacts. All
five documented blocks were replayed from the worktree. Every one of the six
committed oracles regenerates **byte-identically**, and `git diff` over
`mag/tests/` is empty afterwards.

| oracle | sha256 after replay | matches committed |
|---|---|---|
| `model_records_expected.json` | `611d885cb7f67269790110a2e6447be855657b9d9495e95ae7f47aa7c5452d2d` | yes |
| `model_records_records_expected.json` | `1e9bc57520012bc3013a6d7a3e1c0d24b825b964d6fad1cf4ae024e14735181f` | yes |
| `model_records_urls_expected.json` | `271f1aed2dc84e10fa172e5ed3c07c6cd7a4ce74af67af63609c19d0b01ae8c7` | yes |
| `model_records_create_expected.json` | `be1563b161c129fedc88789322a8bec74382e8dd6f9c107e9cef6f1cae20ffe7` | yes |
| `model_records_ports_expected.json` | `331c78f351061f0db6fef3f7579f6ea4a4b146e628c04aec8a065ecbeee93288` | yes |
| `model_records_cases_expected.json` | `34feb1a9c45901513bbffa724476815b8660aa932c77c9c6cf7d0c933d027e2f` | yes |

Counts reported by the generators: 96 records, 11 record fixtures, 25 URLs,
8 create cases, 4 `source_id` cases, 8 ports, 54 matrix cases of which 44
refuse. These match the evidence.

## The structural fix, proven in both directions

The claim is that `canonical_urls_match_python` and
`port_refusal_messages_match_python` now iterate Rust-side `URL_CASES` and
`PORT_CASES` constants and compare the whole table, so a missing *or* extra
oracle key fails loudly. Proven by mutation rather than by reading:

| mutation | test | result |
|---|---|---|
| drop `http://e.com:0/x` from the URL oracle | `canonical_urls_match_python` | FAILED |
| add a spurious `https://spurious.example/zz` | `canonical_urls_match_python` | FAILED |
| drop `https://e.com:65536/` from the ports oracle | `port_refusal_messages_match_python` | FAILED |
| add a spurious `https://e.com:777777/` | `port_refusal_messages_match_python` | FAILED |
| both restored | both | ok |

Under the previous shape the drop case passed silently. That is the defect
closed.

## Revert proofs

Each fix reverted in place, its named test rerun, then restored:

| reverted fix | test | result |
|---|---|---|
| float-zero coercion in `python_text` | `figure_and_extract_refusals_match_python` | FAILED |
| isinstance arms in both `localize_*` | `figure_and_extract_refusals_match_python` | FAILED |
| restored | both above, plus `canonical_urls_match_python` | ok |

Working tree clean after restoration.

## Reading the two fixes against the Python

- `media_schema.py` carries **four** `isinstance(rows, list)` guards, at
  lines 43, 135, 203 and 331, not two. The two `resolve_*` sites (43, 203)
  are preceded by `if rows in (None, []): return ()`, which the port matches
  with `is_absent` (true for `None`, `Null` and an empty sequence). The two
  `localize_*` sites (135, 331) have **no** such short-circuit once `base` is
  non-empty, so `None` falls through to the isinstance guard and refuses.
  That asymmetry is exactly what the fix turns on, and the port now mirrors
  it: only `Some(Value::Sequence(_))` counts as a Python list.
- The empty-`base` branch of `localize_*` is separately correct: Python's
  `if rows not in (None, [])` raises "absent from English", and the port
  guards the same branch with `is_absent`, which agrees on all three inputs.
- Python falsiness confirmed directly: `str(v or "")` yields `""` for `0`,
  `0.0`, `-0.0`, `""`, `[]`, `{}` and `False`, and `"0.5"`/`"1.0"` for
  non-zero floats. The port's `python_text` matches, including
  `Bool(true) -> "True"` (Python's `str(True)`) and empty sequence or mapping
  to `""`. Rust's `float == 0.0` also covers `-0.0`, as claimed.

## Extended sweep, third angle

Two previous sweeps each found a divergence the previous one missed
(truthiness, then float falsiness), so the class was probed again end to end
rather than by reading: 13 new cases were appended to the fixture, the Python
oracle regenerated over them, and the port run against it. **All 13 agree.**
They are discriminating rather than trivially equal, producing five distinct
behaviours:

| probe | Python behaviour |
|---|---|
| `caption` as `false`, `[]`, `{}`, `0` | coerced to `""`, then refused: "requires caption, alt_text, and anchor" |
| row `id` as `0`, `""`, `false` | dropped by the `by_id` truthiness filter, then "is missing figures: f1" |
| `credit: 0` with a base credit | falls through the double fallback to `BaseCredit` |
| `localize` rows as `false` or `0` | "Translation 'es' article a1 figures must be a list" |
| `resolve` rows as `false`, `0`, `{}` | "Article a1 figures must be a list" |

The falsy-`id` and `credit`-fallback positions were reached by no previous
sweep. On this evidence the falsiness and isinstance class now looks closed;
the fixtures were restored afterwards and the tree left clean.

## Deliberate divergences, checked against the recorded list

The evidence enumerates three, each in the refuse-rather-than-guess
direction and none reachable from the current corpus. One deserves note
because the sweep reached it independently: a figure or extract row field
holding a **non-empty** sequence or mapping is refused by the port, where
Python would stringify it (`"['a']"`) and usually fail a later validation
with different text. It is recorded, so it is a declared divergence rather
than a surprise. The port-65536 divergence (Rust `ValidationError` where
Python raises an uncaught `ValueError`, identical message text) was judged
sound at the previous verification and is pinned by
`model_records_ports_expected.json`.

## U+2014

Five occurrences in the corpus oracle are real captured source titles, which
the repo rule permits verbatim. The `unicode_title` fixture string appears in
`model_records_create_expected.json` and `model_records.rs`; it is fixture
data that must byte-match the Python oracle, it mirrors the em dashes that
genuinely occur in captured titles, and `git show f044b99` confirms it
predates this rework. Not authored prose; the rule is satisfied.

## Residuals

- `WP-5.1c`'s private `py_repr` copy is the pre-fix body, which this WP's
  non-printable escaping makes a live divergence between two copies of one
  helper. That is WP-5.1c's rejection and the WP-5.1d consolidation
  follow-up, not this WP's.
- The corpus remains uniformly happy-path; every non-corpus branch is
  covered by fixture, which is what the three sweeps have been establishing.

## Status

accepted
