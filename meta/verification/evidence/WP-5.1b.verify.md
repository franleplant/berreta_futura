# WP-5.1b records port, verification

## Verdict

**REJECTED.** Two material divergences from the Python originals, both in code
paths the committed oracles do not reach, plus one undocumented behavioural
divergence and two unexercised raise sites.

The port itself is strong: 96 records byte-identical, five oracles, a 42-case
refusal matrix comparing messages in full, and two divergences the worker found
and fixed before submitting. Everything the oracles cover reproduces exactly.
The rejection is for what the oracles do not cover, which is the same failure
shape that rejected WP-5.1a: a defect masked because no committed input
contains an instance.

## Base

WP commit `f044b99` (parent `7d79b9d`), evidence
`meta/verification/evidence/WP-5.1b.md`. Verified in a clean worktree at
`f044b99`. Verify file committed from a temp branch based on `8acb042`.

## Owns check

PASS. `git show --stat f044b99` lists 26 files, all within Owns:
`mag/src/model.rs` (one line), `mag/src/model/records.rs`,
`mag/tests/model_records*` (tests, four oracle dumps, 16 fixtures), and
`meta/verification/evidence/WP-5.1b.md`. No `*.verify.md`, no `baseline.json`,
no comparator territory (`mag/src/parity*`, `parity.yaml`), no
`mag/src/typeset/**`, no `mag/src/render.rs`, no `mag/src/model/doc.rs`.
`Cargo.toml` and `Cargo.lock` are untouched, matching the claim that no crate
was added.

## Commands

```
git worktree add /Users/franguijarro/.claude/jobs/7d99e27f/tmp/verify-wp51b f044b99
cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

Differential harness (scratch, not committed): a `mag/tests/zzscratch.rs`
integration test calling `canonicalize_url` on 28 URLs and `resolve_figures`
with 13 figure-path values chosen to exercise `py_repr`, dumping JSON; and a
mirror Python script calling the same two functions on byte-identical inputs
via `uv run python`. Both dumps diffed key by key. Both files are preserved at
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/{zzscratch.rs.bak,py_scratch.py}`
for the rework agent.

Independent negative check (different mutation than the worker's): rewrote
`mag/tests/model_records_expected.json` record index 5 `tags` to
`["MUTATED-BY-VERIFIER"]` and ran `cargo test --test model_records
library_sources`.

## Tool versions

python 3.12.11, uv 0.8.17, PyYAML 6.0.3, rustc 1.96.0, cargo 1.96.0.

## Metrics

Baseline in the worktree, all green:

- `cargo fmt --check` clean, `cargo clippy --all-targets -- -D warnings` clean.
- `cargo test`: 7/7 in `model_records` (0.03 s), `nocomments` green,
  `parity_faults` green (21.23 s).
- Negative check: `library_sources_match_the_python_dump` FAILED on my
  mutation, so the corpus oracle is not vacuous.

Differential sweep: **41 cases compared, 8 diverge.**

| case | Rust | Python |
|---|---|---|
| `https://e.com:0/` | `https://e.com:0/` | `https://e.com/` |
| `https://e.com:65536/` | `ValidationError("Port out of range 0-65535")` | `ValueError: Port out of range 0-65535` |
| `https://e.com:abc/` | `ValidationError("Port could not be cast to integer value as \"abc\"")` | `ValueError: Port could not be cast to integer value as 'abc'` |
| repr `nul` | `'../x<U+0000>y'` raw | `'../x\x00y'` |
| repr `bell` | `'../x<U+0007>y'` raw | `'../x\x07y'` |
| repr `escape` | `'../x<U+001B>y'` raw | `'../x\x1by'` |
| repr `next_line` | `'../x<U+0085>y'` raw | `'../x\x85y'` |
| repr `zero_width_space` | `'../x<U+200B>y'` raw | `'../x\u200by'` |

The 33 agreeing cases include IPv6 with and without a port, a unicode (IDNA)
host, a trailing-dot host, a percent-encoded slash in the path, lowercase
percent-encoding preserved, tab stripping, a NUL inside a query value, multi
slash collapse with a trailing slash, blank values kept, a field with no `=`,
duplicate keys, an empty key, a semicolon treated as data rather than a
separator, userinfo stripping, default-port dropping for both schemes, query
sorting including case, `utm_`/tracking filtering with a blank value, and both
`py_repr` quote-selection branches (single quote, double quote, and a string
containing both).

## Findings

### 1. MUST FIX. `canonicalize_url` keeps an explicit port 0; Python drops it

`records.py:29` reads `if parts.port and not (...)`. For `:0`, `parts.port` is
the integer `0`, which is falsy, so the whole branch is skipped and the port
never joins the host. `records.rs:187` reads `if let Some(number) = port`,
where `Some(0)` enters the branch, `0` is neither 80 nor 443, and `:0` is
appended.

Failure: `canonicalize_url("https://e.com:0/")` returns `https://e.com:0/` in
Rust and `https://e.com/` in Python. This is not only a string difference:
`source_id` is `_slug(title)` plus the first 8 hex of the SHA256 of the
canonical URL, so the two implementations mint different record ids for the
same page, and `load_records`' duplicate-URL detection would disagree. The
corpus contains no explicit port at all, so no committed oracle can see it.

Fix: treat `Some(0)` as absent, mirroring Python's falsiness.

### 2. MUST FIX. `py_repr` does not escape non-printable characters

Python's `repr` escapes every character for which `str.isprintable()` is false,
as `\xNN` or `\uNNNN`. `records.rs:220` handles only `\\`, `\n`, `\r`, `\t` and
the active quote, emitting every other character raw. Five of my 13 probes
diverge (NUL, BEL, ESC, NEL, and zero-width space); `é` correctly stays raw,
since Python leaves printable non-ASCII alone.

`py_repr` governs eight message sites (`records.rs:860` figure path, `:876` and
`:1032` anchors, `:1026` extract style, `:1062` and `:1072` extract begin/end
markers, `:1106` and `:1185` language). Anchors and extract markers are
hand-authored in `edition.yaml` and routinely pasted from web sources, where a
zero-width space is a common invisible artifact, so this is reachable in normal
editorial work rather than only under adversarial input. The WP's own standard
is that messages match in full.

Fix: port Python's rule, escaping any character failing an `isprintable`
equivalent as `\xNN` for U+0000-U+00FF and `\uNNNN` above it. Note Python's
`isprintable` is false for all of category Cc, Cf, Cs, Co, Cn, Zl, Zp, and for
Zs other than U+0020.

### 3. SHOULD FIX or RECORD. Malformed port changes exception type and message

Python's `parts.port` raises `ValueError`, which `canonicalize_url` does not
catch, so a malformed or out-of-range port propagates as an unhandled
`ValueError` and crashes the caller. Rust returns a `ValidationError`, which
`mag capture` would treat as an ordinary refusal. The message text also
differs, because `records.rs:108` formats the port with `{port:?}` (Rust Debug,
double quotes) instead of `py_repr` (single quotes).

Rust's behaviour is arguably better, but it is a behavioural divergence absent
from the evidence's deliberate-divergences list. Either match Python, or record
it there with the message quoting fixed to `py_repr` for consistency with the
other eight sites.

### 4. SHOULD FIX. Two unmapped raise sites, not one

The evidence states every `ValidationError` raise site is mapped with a single
documented exception (`load_records` duplicate URL, unavoidable because
Python's message depends on `Path.glob` order). Two more are unexercised, both
in `localize_extracts`:

- `media_schema.py:332` "extracts must be a list". The figures analogue
  `localize_figures_not_a_list` exists; the extracts one does not.
- `media_schema.py:340-347` missing and extra ids. The figures analogue
  `localize_figures_missing_and_unknown` exists; the extracts one does not.
  `localize_extracts_incomplete_fields` cannot reach it, because the id sets
  must match for control to arrive at the field checks.

The symmetry of the missing cases suggests an oversight rather than a decision.
Adding two cases to `cases.yaml` closes it.

### 5. NOTED. The duplicate-URL exception is genuinely unavoidable as framed

I confirmed Python's message names whichever duplicate `Path.glob` met first,
so reproducing it would mean reproducing filesystem order. Recording it is
correct. If the rework wants coverage anyway, comparing the sorted set of
duplicated URLs rather than the message text would exercise the branch on both
sides without depending on iteration order.

## Verdicts

Oracle digests recomputed in the worktree, all matching the evidence:

- `model_records_expected.json` `611d885c...`
- `model_records_records_expected.json` `1e9bc575...`
- `model_records_urls_expected.json` `86b070c5...`
- `model_records_create_expected.json` `9d18310c...`
- `model_records_cases_expected.json` `acf56e75...`

## Residuals

- The worker's behavioural notes were checked and stand: the quoted/unquoted
  YAML timestamp asymmetry, the deliberate refuse-rather-than-guess divergences
  on wrong scalar types, and the `splitlines`/`lines` and `strip`/`trim`
  differences. None is contradicted by this sweep.
- `ValidationError` living in `records.rs` remains the right thing for WP-5.1c
  to lift into a shared module, as the worker noted.
- The scratch harness is preserved for the rework agent (paths in `## Commands`)
  so the eight divergences can be re-run as a regression check rather than
  rebuilt.

## Status

rejected
