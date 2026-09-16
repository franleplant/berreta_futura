# WP-5.4a verification

## Verdict

**ACCEPTED.** Commit `abaa9aa` (rework), verified at that commit.

## Rejection record

The first submission, commit `6a84018`, was REJECTED at verify `ff5cd21` for
two linked defects:

- `python_str`'s `Mapping` and `Tagged` arms were reached by no fixture, sitting
  under a blanket heading "Branches edition 010 cannot reach, all covered by
  fixture". That is the shape WP-5.3a was rejected for and which protocol
  rule 10 forbids.
- The `Tagged` arm had already DRIFTED from `manifest.rs`'s `py_str`: the cover
  copy yielded `x` where the manifest copy yields `'x'`, str against repr.

Everything substantive in that submission was confirmed independently at
`ff5cd21` and was not re-verified here: the Unicode 15.0.0 divergence across
55 codepoints, the three whole-plane sweeps at 1530 / 1525 / 29 over 1,112,064
codepoints, the load-bearing dedup, three reproduced probes, and the
eighth-probe correction.

## Owns

`abaa9aa` touches exactly three paths:

| path | |
|---|---|
| `mag/tests/cover_text.rs` | +15 |
| `mag/tests/cover_text_expected.json` | +1 |
| `meta/verification/evidence/WP-5.4a.md` | +84 / -7 |

`mag/src/cover/text.rs` is byte-identical between `6a84018` and `abaa9aa`
(`git diff 6a84018 abaa9aa -- mag/src/cover/text.rs` is empty), so the rework
is fixtures and evidence only, with no behaviour change. No `*.verify.md`, no
`baseline.json`, nothing else under `mag/src/cover/`.

## The `Tagged` reachability argument

This is the crux of the rework and it holds in both directions, measured
rather than accepted.

The Python oracle REFUSES the input that produces the arm:

```
uv run python -c "import yaml; yaml.safe_load('deck: !mytag x')"
-> ConstructorError: could not determine a constructor for the tag '!mytag'
```

Standard tags do NOT reach the arm, on either side. Python resolves
`!!str 5` to a plain `str` of value `'5'`. A probe through the port's own
`serde_yaml` confirms the Rust side agrees, and isolates which documents do
reach `Tagged`:

| document | serde_yaml variant | `python_str` |
|---|---|---|
| `!!str 5` | `String` | `"5"` |
| `!!int 7` | `Number` | `"7"` |
| `!!bool true` | `Bool` | `"True"` |
| `!mytag x` | **`Tagged`** | `"x"` |

So `Tagged` is reachable only from a custom tag, which is exactly the document
PyYAML's `safe_load` rejects. No Python-equality row can exist for it, and the
worker's decision to test the arm without an oracle row is correct.

## The chosen behaviour, and `manifest.rs`'s fall-through

The worker's reading of `manifest.rs` is accurate. Its `py_str` (at :2142) has
arms for `Null`, `Bool`, `Number` and `String`, then `other => py_repr_value(other)`
with NO `Tagged` arm. `py_repr_value` (at :2153) carries
`Value::Tagged(tagged) => py_repr_value(&tagged.value)`, and for a string that
reaches `py_repr`, producing `'x'`.

So the manifest copy's `'x'` is INCIDENTAL: the fall-through bundles `Sequence`,
`Mapping` and `Tagged` together, which is right for the first two (Python's
`str(dict)` reprs its contents) and wrong for a tagged scalar.

Keeping `x` in the cover copy is the better choice, and the WP argues it
correctly: `python_str` models Python's `str()`, and `str()` of a string never
adds quotes. The `Tagged` wrapper is a YAML-parser artifact with no Python
counterpart, so unwrapping to the underlying value's `str()` is the coherent
reading. Neither copy is a port here, because there is nothing to port; the
cover copy is a decision, the manifest copy is a side effect.

## Per-arm coverage

The blanket claim is replaced by an arm-by-arm table. The enumeration is
complete against `serde_yaml::Value`'s seven variants as `python_str` matches
them (the source splits `Bool` into `Bool(true)` and `Bool(false)`, which the
table correctly treats as one arm):

| arm | evidence status | confirmed |
|---|---|---|
| `Null` | fixture `deck_null`, literal `"None"` | yes |
| `Bool` | fixture `deck_bool` | yes |
| `Number` | fixture `deck_int` | yes |
| `String` | fixture `deck_string` and edition 010 | yes |
| `Sequence` | fixture `deck_list` | yes |
| `Mapping` | fixture `deck_map`, added in the rework | yes |
| `Tagged` | unreachable from safe-loaded YAML, no oracle | yes, above |

Each disposition is accurate. No arm is unaccounted for.

## Row count

The oracle now carries 41 rows, and the breakdown reported (8 / 19 / 10 / 4)
sums to 41:

```
cover_contributors: 19
cover_date:          8
cover_tab_identity:  4
cover_tab_issue:    10
TOTAL:              41
```

The evidence states explicitly that the previous breakdown summed to 40 and
that `deck_map` makes it 41, rather than renumbering quietly.

## Discrimination probes

Reproduced independently by perturbing `mag/src/cover/text.rs` in the
verification worktree and restoring from the committed blob afterwards.

| probe | perturbation | result |
|---|---|---|
| H | `Mapping` keys via `python_str` (unquoted) | `cover_contributors_matches_python` FAILED |
| J | `Tagged` routed through repr, as `manifest.rs` does | `tagged_arm_has_no_python_oracle_and_unwraps` FAILED, `left: "'x'"` against `right: "x"` |

Probe J fails with exactly the divergence the rejection identified, which is
what pins the decision rather than merely asserting it. `deck_map` reproduces
against Python directly: `str(yaml.safe_load("{a: 1, b: x}"))` gives
`{'a': 1, 'b': 'x'}`, matching the committed row.

## Round trip

The four-function oracle regenerates BYTE-IDENTICALLY from the command
recorded in `## Commands`, driving the real `magazine.cover` functions and
including the live edition-010 row read from the tracked `edition.yaml`:

```
cmp mag/tests/cover_text_expected.json <backup>  -> identical
```

The two-Pythons hazard is explicit at the head of `## Commands` (lines 14-19):
this machine carries system Python 3.9.6 on Unicode 13.0.0 alongside
`uv run python` 3.12.11 on 15.0.0, and a bare `python3` yields maps about forty
entries short. Every recorded command is pinned to `uv run python`, which is
why the method reproduces. I used `uv run python` throughout.

## Baseline

In a clean worktree at `abaa9aa`: `cargo fmt --check` clean,
`cargo clippy --all-targets -- -D warnings` clean, full `cargo test` green at
108 tests across 11 binaries, 0 failures. `cover_text` alone: 9 passed.

## The forward finding: the manifest loader should refuse tagged values

Assessed as asked, not acted on. The worker's claim is RIGHT.

`yaml.safe_load` raises `ConstructorError` on a custom tag; `serde_yaml` parses
the same document happily. So the Rust loader is currently MORE PERMISSIVE than
its oracle, accepting documents Python rejects. That is a divergence in the bad
direction under revision 11's policy, which permits divergence only toward more
diagnosis.

Making the manifest loader refuse tagged values MATCHES PyYAML rather than
exceeding it, so it does not run into revision 23's rule that a port may not be
stricter than its oracle. It also makes both copies' `Tagged` handling moot,
which is a better outcome than two copies disagreeing about behaviour neither
can reach from a valid document.

This is a named obligation on WP-5.1e. Confirmed sound.

## Residual: WP-5.1e has since lifted these helpers

Verification is pinned to `abaa9aa` as submitted, which is correct under
protocol rule 3. Note for the record that the concurrent WP-5.1e has since
landed its lift in the main tree, so `mag/src/cover/text.rs` there now imports
`py_casefold`, `py_str`, `py_strip`, `py_upper` and `py_zfill` from
`crate::model::shared`. The `Tagged` decision verified here therefore moves into
the shared module, where it becomes the single definition rather than one of
two. That is the intended outcome and it does not affect this verdict, but
WP-5.1e's own verification should confirm the decision survived the lift
unchanged.
