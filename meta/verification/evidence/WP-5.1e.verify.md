# WP-5.1e verification

## Base

Worker commit `10d705d` (base `abaa9aa`). Verified in a fresh worktree at
`10d705d`. Plan revision 23.

## Verdict

**REJECTED**, narrowly and on one paragraph of reasoning. No code defect was
found: the lift is behaviour-preserving, the tagged fix is correct, both
planted-duplicate proofs fire, and every oracle is byte-identical. The
rejection is that the `luma601` conclusion rests on a search that could not
have found what it claims is absent, recorded as proof of absence.

## The defect

The evidence concludes no action is needed on `luma601` because
`grep -rn "luma601\|19595"` matches only `critic/metrics.rs`. That search
cannot see the second implementation. `mag/src/cover/art.rs:12` defines
`fn grey`, computing per-mille `r*299 + g*587 + b*114` rounded by
`(value + 500) / 1000`, while `mag/src/critic/metrics.rs:541` defines
`luma601` computing PIL's fixed-point
`(r*19595 + g*38470 + b*7471 + 0x8000) >> 16`. Different name, different
constants, different rounding, so neither grep term could match it.

The conclusion may well survive: these are two different formulas and are
plausibly two faithful ports of two different Python originals, in which
case leaving them separate is right, and the worker's stated instinct that
`model/shared.rs` is Python semantics while ITU-R 601 luma is colour science
still holds. The WP-5.4 verifier is separately checking whether `art.rs`
matches its own original in `cover.py`. What cannot stand is the evidence
recording a search as proof of absence when the search was incapable of
detecting presence, in the very WP whose purpose is to close the duplication
class. A later reader would cite it as precedent.

This is also a live instance of the blind spot the WP itself records, and a
sharper one than the example it gives: two implementations of one concept
with different names AND different bodies, so neither audit key fires, and
here even a manual grep missed it because the constants differ too.

**Remedy**, evidence-only, no code change: correct the reasoning to state
what was actually searched and what it could not reach; name `art.rs`'s
`grey` explicitly; state the conclusion as conditional on both being
faithful ports of different Python formulas, deferring the confirmation to
WP-5.4's verification; and cite the pair as the blind-spot example.

## Commands

All Python run through `uv run python` (this machine carries system 3.9.6 on
Unicode 13.0.0 alongside uv's 3.12.11 on 15.0.0; a bare `python3` yields case
maps about forty entries short).

```
git worktree add .../verify-wp51e 10d705d
cd mag && cargo test && cargo fmt --check && cargo clippy --all-targets -- -D warnings
```

Packed tables moved verbatim:

```
git show abaa9aa:mag/src/cover/text.rs | awk '/(FOLD_DATA|UPPER_DATA)/,/;$/' | shasum -a 256
git show 10d705d:mag/src/model/shared.rs | awk '/(FOLD_DATA|UPPER_DATA)/,/;$/' | shasum -a 256
```

PyYAML tagged-node rejection:

```
uv run python -c "
import yaml
for doc in ['!foo x', 'a: !foo x', 'deck: !mytag x']:
    try: yaml.safe_load(doc); print(repr(doc), '-> LOADED')
    except Exception as e: print(repr(doc), '->', type(e).__name__, '|', str(e).splitlines()[0])
"
```

010 projection regenerated from the evidence's own inline command, then
compared:

```
MAG_MODEL_ARTICLES=$PWD/../editions/010/run-2026-09-13T01-34-51/articles \
  MAG_MODEL_ORACLE=/tmp/py-projection-51e.json \
  cargo test --test model_doc edition_manuscripts
```

## Tool versions

rustc 1.96.0, uv python 3.12.11, PyYAML via `uv run`.

## Metrics

**Baseline**: `cargo test` green across 11 binaries including
`rust_helpers` 2/2 and `parity_faults` 1/1; `cargo fmt --check` clean;
`cargo clippy --all-targets -- -D warnings` clean (exit 0).

**Packed tables verbatim**: both extractions hash
`f3bdd3768c6efa473686a94d00f1b12108b7cee4e0962866c66115230da1d3ec`, 30,556
bytes each. A changed parse would have been silent; it did not change.

**PyYAML rejection**, all three shapes:

| document | result |
|---|---|
| `!foo x` | ConstructorError, `could not determine a constructor for the tag '!foo'` |
| `a: !foo x` | ConstructorError, same wording |
| `deck: !mytag x` | ConstructorError, `... the tag '!mytag'` |

The Rust refusal in `load_structured` emits
`Cannot read {path}: could not determine a constructor for the tag '{tag}'`,
and `tagged_values_are_refused_as_pyyaml_refuses_them` asserts the
`'!mytag'` form including the bang. Refusing is **fidelity, not caution**:
PyYAML genuinely refuses these documents, so the port matching that refusal
does not engage revision 23's stricter-than-oracle rule. It also makes the
`Tagged` arm unreachable from any loaded document, which is the fix one step
earlier that WP-5.4a identified.

**The `Tagged` decision survived the lift.** The single shared `py_str`
carries an explicit `Value::Tagged(tagged) => py_str(&tagged.value)` arm,
the unwrap behaviour, not `manifest.rs`'s incidental repr fall-through.
Probe J (`tagged_arm_has_no_python_oracle_and_unwraps`, calling
`shared::py_str`) discriminates: restoring `py_repr_value` in that arm fails
with `left: "'x'" right: "x"`; restored, it passes.

**Both planted-duplicate proofs fire, each isolating its half:**

| planted | name key | body key |
|---|---|---|
| `py_zfill` copied verbatim into `critic/metrics.rs` | FAIL | FAIL |
| `planted_a`/`planted_b`, body `x + 1`, different names | pass (correct) | FAIL |

Restored afterwards: 2 passed, `git status` clean. The second body squeezes
to five characters, an eighth of the removed 40-character floor, so with the
floor in place it would have passed silently. No length threshold remains in
`rust_helpers.rs`; the only `len()` assertion is a parser sanity check
(`items.len() > 400`).

**Allowlist honesty**: 22 entries, and the labelling is accurate. Genuine
duplicates are named as such (`read` across four modules, `resolve_edition_dir`,
`esc`/`escape_text`, `deref`/`resolve`, `prompts_path`), coincidences are
named for their mechanism (`Drop::drop`, `move_to`/`line_to`/`close` as
`ttf_parser::OutlineBuilder` trait-required names, `new` as constructor
convention). No genuine duplicate is described as a coincidence.

**`prompts_path` drift confirmed at source.** `art.rs:20` returns
`PathBuf::from("prompts").join(file)` with no fallback; `produce.rs:29`
tests `local.exists()` and otherwise falls back to
`CARGO_MANIFEST_DIR/../prompts/<file>`. The allowlist labels it
`DRIFTED copy: art.rs lacks produce.rs's installed-prompts fallback`, which
is accurate. **Severity: latent.** It bites only when `mag art` runs from a
directory without a local `prompts/`, which the repo convention (run from
the repo root) normally prevents, and it is in the existing CLI rather than
in any port, so it is outside the plan's scope. It is a real bug and now has
an owner recorded.

**`py_zfill`, the unbriefed lift: good judgment, not scope creep.** At
`abaa9aa` it was `python_zfill` at `cover/text.rs:66`, the same file, the
same Python-builtin theme and the same consumers as the three helpers the
brief did name. Leaving exactly one behind would have recreated the
condition the WP exists to remove. Renaming to the `py_` prefix matches the
convention `py_repr` already set.

**Oracles: 13 of 13 byte-identical** between base `abaa9aa` and `10d705d` —
`cover_text_expected` a1b05913, `cover_text_unicode_expected` fc379caa,
`critic_metrics_expected` c519fdfb, `critic_metrics_rounding_expected`
1d642913, `model_doc_expected` 4a584524, `model_manifest_cases_expected`
1045b017, `model_manifest_repr_expected` e7186560,
`model_records_cases_expected` 34feb1a9, `model_records_create_expected`
be1563b1, `model_records_expected` 611d885c, `model_records_ports_expected`
331c78f3, `model_records_records_expected` 1e9bc575,
`model_records_urls_expected` 271f1aed.

**010 projection**: regenerated to
`e17ca71cffabe08b08820dd268863dcbda04615a871e5feaf52c34ca907cda50` at
208,052 bytes, and `edition_manuscripts_match_the_python_projection` passes
against it. The three whole-plane sweeps run inside `cargo test` and pass
post-lift.

## Verdicts

No parity verdict.json is produced by this WP.

## Residuals

The audit's blind spot is recorded honestly by the WP as a limit rather than
a solved problem, and the `grey`/`luma601` pair is a stronger example of it
than the one the evidence gives.

`prompts_path` is a live bug in the existing CLI, outside plan scope, now
allowlisted with an accurate reason.

## Status

rejected
