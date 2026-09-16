# WP-5.1e lift the Python-semantics helpers and widen the duplicate audit

## Base

`abaa9aa` (WP-5.4a's rework). Work began at `804ffa7` (plan revision 22)
and was rebased twice as the branch moved: onto `24de8d9` (revision 23,
after WP-5.4 landed `5a3fa71` and the WP-5.4a verification landed
`ff5cd21`), then onto `abaa9aa`. Both rebases mattered. The first brought
`mag/src/cover/outline.rs` into existence, which the widened audit
immediately flagged. The second brought WP-5.4a's `Tagged` resolution,
which is discussed below and which arrived at the same decision this WP
had already made independently.

## Commands

Python projection for edition 010, regenerated to confirm the lift changed
nothing:

```
uv run python -c '
import json, pathlib
from magazine.publication_document import parse_publication_document
from magazine.document_structure import visible_blocks, block_signature
from magazine.reader_text import educate_reader_quotes, fold_reader_characters
root = pathlib.Path("editions/010/run-2026-09-13T01-34-51/articles")
out = {}
for d in sorted(root.iterdir()):
    p = d / "final.md"
    if not p.is_file():
        continue
    doc = parse_publication_document(p.read_text(encoding="utf-8"))
    vb = visible_blocks(doc.blocks)
    text = "\n".join(t for _, t in vb)
    educated = educate_reader_quotes(text)
    out[d.name] = {
        "metadata_keys": sorted(doc.metadata),
        "visible_blocks": [list(x) for x in vb],
        "block_signature": block_signature(doc.blocks),
        "educated": educated,
        "folded": fold_reader_characters(educated),
    }
print(json.dumps(out, sort_keys=True, indent=1, ensure_ascii=True))
' > /tmp/py-projection-51e.json
shasum -a 256 /tmp/py-projection-51e.json

cd mag && MAG_MODEL_ARTICLES=$PWD/../editions/010/run-2026-09-13T01-34-51/articles \
  MAG_MODEL_ORACLE=/tmp/py-projection-51e.json \
  cargo test --test model_doc edition_manuscripts
```

The untracked run directory must be copied into a fresh worktree first:

```
cp -R /Users/franguijarro/code/magazine/editions/010/run-2026-09-13T01-34-51 editions/010/
```

Whether PyYAML can produce a `Tagged` node at all, which decides the
`py_str` drift below:

```
uv run python -c "
import yaml
for doc in ['!foo x', 'a: !foo x']:
    try:
        print(repr(doc), '->', repr(yaml.safe_load(doc)))
    except Exception as e:
        print(repr(doc), '-> REJECTED', type(e).__name__)
print('str:', str('x'), '| repr:', repr('x'))
"
```

Oracle digests, before and after the lift:

```
ls mag/tests/*.json | while read f; do
  printf "%s  %s\n" "$(shasum -a 256 "$f" | cut -c1-16)" "$(basename $f)"
done
```

Planted-duplicate proof 1, a duplicate in a NON-MODEL module, which the old
four-file audit could not see. Append the same function to
`mag/src/critic/metrics.rs` and `mag/src/model/shared.rs`:

```
fn py_casefold_planted(value: &str) -> String {
    let mut out = String::with_capacity(value.len());
    for character in value.chars() {
        out.push(character);
    }
    out
}
```

Planted-duplicate proof 2, a SHORT-BODIED duplicate with DIFFERENT names, so
only the body key can catch it and the removed 40-character floor is what is
under test. Append `planted_a` to `mag/src/critic/metrics.rs` and
`planted_b` to `mag/src/impose.rs`, both with the body `x + 1`.

Repository gate:

```
cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

## Tool versions

python 3.12.11, uv 0.8.17, rustc 1.96.0. No crate added; Cargo files
untouched, so the revision 18 only-gained check is not applicable.

## Metrics

### What was lifted, and from where

Into `mag/src/model/shared.rs`, joining `py_repr` which WP-5.1d put there:

| helper | from | why it had to move |
|---|---|---|
| `is_python_space` | `model/doc.rs` (private) | WP-5.4a needed it, could not import it, copied it |
| `py_str`, `py_repr_value` | `model/manifest.rs` (private) | same, as `python_str`/`python_repr` |
| `FOLD_DATA`, `UPPER_DATA` and `table`/`decode`/`folds`/`uppers`/`mapped` | `cover/text.rs` | revision 22's Unicode rule guarantees WP-5.5a and WP-5.3b need them |
| `py_strip`, `py_casefold`, `py_upper` | `cover/text.rs` | the tables' only accessors; inseparable from them |
| `py_zfill` | `cover/text.rs` | judgment call, see below |

`mag/src/model/shared.rs` additionally gains `first_tag` and the tagged-node
refusal in `load_structured`, for the reason set out under the `py_str`
drift below.

`py_zfill` is not Unicode-dependent and the brief named only the case
tables. It was lifted anyway because it is a Python-builtin helper sitting
in the same file with the same consumers, and leaving exactly one behind
recreates the problem this WP exists to end. Recorded as a judgment rather
than a requirement.

Names were normalised to the `py_` prefix already established by
`py_repr`; `cover/text.rs` and `mag/tests/cover_text.rs` were updated as
call sites, which the WP bullet covers ("the call sites it updates").
`mag/tests/model_doc.rs` gained the `shared` module because `doc.rs` now
imports from it and the test target includes modules by `#[path]`.

### The `py_str` drift, decided against Python

The two copies genuinely disagreed, as the WP-5.4a verifier found:
`cover/text.rs`'s `python_str(Tagged(String))` yielded `x`, while
`model/manifest.rs`'s `py_str` yielded `'x'`, which is str versus repr.

It cannot be decided by measurement, and that is the finding: **PyYAML's
`safe_load` rejects a tagged node outright** (`ConstructorError` for both
`!foo x` and `a: !foo x`), so no Python behaviour exists on this path to
compare against, on either side. The path is unreachable from safe-loaded
YAML in both implementations.

WP-5.4a reached the same conclusion independently and in parallel, and its
rework names the test `tagged_arm_has_no_python_oracle_and_unwraps`, which
records the same absence of an oracle that the PyYAML probe above shows.
Two independent arrivals at one decision is the strongest corroboration
available for a choice that cannot be measured.

It was therefore decided by Python's *rule* rather than by picking a Rust
copy: `str()` of a scalar returns it unquoted (`str('x')` is `x`), and a
tagged scalar is still a scalar, so the transparent behaviour is the
consistent one. `manifest.rs`'s `'x'` applied Python's rule for an element
*inside a container*, which is the wrong rule for a top-level `str()`. The
shared module therefore carries the transparent form.

**The real fix is one step earlier, and this WP made it.** The arm is only
reachable from a document the oracle REFUSES: `yaml.safe_load` raises
`ConstructorError` on `deck: !mytag x` while `serde_yaml` parses it happily,
so the Rust loader was ACCEPTING input Python rejects. A port more permissive
than its oracle is a defect regardless of what it then does with the value.
`load_structured` now refuses any tagged node, reporting
`could not determine a constructor for the tag '!mytag'`, which mirrors
PyYAML's own wording. This is fidelity rather than added strictness, so it
does not run into revision 23's rule that a port may not be stricter than its
oracle: PyYAML genuinely refuses these documents. Covered by
`tagged_values_are_refused_as_pyyaml_refuses_them`. With that in place the
`Tagged` arm is unreachable from any loaded document on either side, and the
choice above is a belt-and-braces default rather than live behaviour.

The refusal is a deliberate divergence in the same family WP-5.1b recorded
for the malformed port: Python raises an uncaught `ConstructorError`, Rust
returns a `ValidationError`. Both refuse; only the mechanism differs, and
refusing beats crashing.

This is a reasoned choice on an unreachable path, not a measured one, and it
is labelled as such per rule 10. The empirical check that it broke nothing:
manifest's 79-case refusal corpus and its `python_crashes_are_reported_as_validation_errors`
test both pass unchanged against the lifted implementation, which is the
proof that the two copies agreed on every reachable input.

### The widened audit

`mag/tests/model_helpers.rs` (four files) is replaced by
`mag/tests/rust_helpers.rs`, which walks every `.rs` file under
`mag/src/` recursively and reports modules by path (`parity/streams.rs`,
`cover/outline.rs`). Both keys are kept, because a verifier proved each
catches what the other misses: `(name, signature)` with visibility
normalised away catches a DRIFTED copy, and normalised body ignoring names
catches a RENAMED copy. The 40-character body floor is removed. The
sanity assertion rises from 100 items to 400 (the scan now finds far more).

Exemptions are an `ALLOWED` table of `(module, name, reason)`, and a clash
is exempt only if EVERY member of it is listed, so a new copy of an
already-exempt helper still fails. Reasons are data rather than comments,
which the repo forbids.

### What the widening found, which the four-file audit never could

Fourteen pre-existing clashes, none introduced by this WP. Two are genuine
coincidences; the rest are real duplication that had been invisible:

| clash | modules | verdict |
|---|---|---|
| `drop` | caller.rs, capture.rs | coincidence: `Drop::drop` is trait-required, bodies differ |
| `move_to`, `line_to`, `close` | cover/outline.rs, parity/streams.rs | coincidence: `ttf_parser::OutlineBuilder` trait-required names on distinct types |
| `new` | cover/outline.rs, parity/streams.rs | coincidence: constructor convention |
| `read` | art.rs, plan_cmd.rs, produce.rs, translate.rs | GENUINE, four copies of a one-line `fs::read_to_string` helper |
| `prompts_path` | art.rs, produce.rs | GENUINE and DRIFTED: art.rs lacks produce.rs's installed-prompts fallback |
| `resolve_edition_dir` | art.rs, render.rs | GENUINE, differing only in local variable names |
| `esc` / `escape_text` | parity/report.rs, print_cmd.rs | GENUINE, renamed copy of the same HTML escape |
| `deref` / `resolve` | parity/display.rs, parity/streams.rs | GENUINE, renamed copy of the same object dereference |

`prompts_path` is the one worth an owner: the two copies have the same name
and signature and DIFFERENT bodies, which is the exact shape that caused
WP-5.1c's rejection, and `art.rs`'s shorter version will fail to find
prompts anywhere but the working directory. That is a latent defect, not
merely untidy.

None of the eight genuine duplicates is inside this WP's Owns, and three sit
in files another agent held while this ran (`parity/display.rs`,
`parity/streams.rs`, `parity/report.rs` under WP-0.2h). They are allowlisted
with a reason naming them as genuine and deferred, rather than as
coincidences. **An allowlist entry here means "known, owned by nobody yet",
not "accepted forever"**, and the distinction is written into each reason
string.

### `luma601`, decided explicitly

The coordinator raised `luma601`, private in `critic/metrics.rs` and said to
be duplicated into `cover/art.rs`. **It is not duplicated in the landed
tree**: after rebasing onto `24de8d9`, which includes WP-5.4's `5a3fa71`,
`grep -rn "luma601\|19595" mag/src/` matches only `critic/metrics.rs`. The
widened audit is green on it, so there is nothing to lift or allowlist.

Had it been duplicated, the decision would have been to make it
`pub(crate)` in `critic/metrics.rs` rather than move it: `model/shared.rs`
is a Python-semantics module under `model/`, and ITU-R 601 luma is colour
science belonging to neither, so putting it there would start the junk
drawer that kills shared modules. Recorded so the next agent does not
re-open the question.

### The audit's blind spot, stated rather than left to be found

Neither key catches a copy that has BOTH drifted and been renamed, and the
example is the very pair this WP lifted: `manifest.rs`'s `py_str` and
`cover/text.rs`'s `python_str` had different names AND different bodies, so
no key fired, yet they were the same helper and one of them was wrong. The
audit found nothing; a human verifier did.

It is sharper than it first looks: one of the two copies was reachable only
through a document the oracle rejects, so neither the audit nor the test
suite could have found it. A human verifier did.

This is not fully solvable by detection, because at some point two functions with
different names and different bodies are simply two functions. The honest
mitigation is the rule rather than the scan: revision 22 already requires
that a helper whose purpose is to match a Python builtin live in the shared
module, and this WP makes that possible by putting them all there. The audit
catches copies; the rule prevents them. Recorded as a known limit with its
example.

### Oracles, before and after

All thirteen byte-identical, as a refactor requires:

| oracle | before | after |
|---|---|---|
| cover_text_expected | 4424257df71c0781 | 4424257df71c0781 |
| cover_text_unicode_expected | fc379caa495cf2db | fc379caa495cf2db |
| critic_metrics_expected | c519fdfb764af26a | c519fdfb764af26a |
| critic_metrics_rounding_expected | 1d642913b7ae99a1 | 1d642913b7ae99a1 |
| model_doc_expected | 4a5845241374af7c | 4a5845241374af7c |
| model_manifest_cases_expected | 1045b01719fc87f7 | 1045b01719fc87f7 |
| model_manifest_repr_expected | e71865607a16c806 | e71865607a16c806 |
| model_records_cases_expected | 34feb1a9c4590151 | 34feb1a9c4590151 |
| model_records_create_expected | be1563b161c129fe | be1563b161c129fe |
| model_records_expected | 611d885cb7f67269 | 611d885cb7f67269 |
| model_records_ports_expected | 331c78f351061f0d | 331c78f351061f0d |
| model_records_records_expected | 1e9bc57520012bc3 | 1e9bc57520012bc3 |
| model_records_urls_expected | 271f1aed2dc84e10 | 271f1aed2dc84e10 |

`cover_text_expected.json` reads `4424257df71c0781` at the ORIGINAL base
`804ffa7` and `a1b05913e2ac9f01` from `abaa9aa` onward. That change belongs
to WP-5.4a's rework, not to this WP: `git show abaa9aa:mag/tests/cover_text_expected.json`
already hashes to `a1b05913e2ac9f01` before this commit exists. Against the
actual base, all thirteen are byte-identical.

Edition 010 projection: the Python side regenerates to
`e17ca71cffabe08b08820dd268863dcbda04615a871e5feaf52c34ca907cda50` at
208,052 bytes, matching WP-5.1a's recorded digest exactly, and
`edition_manuscripts_match_the_python_projection` passes against it.

### Whole-plane sweeps after the lift

The three sweeps WP-5.4a used to prove the pinned tables all pass against
the moved tables, each over 1,112,064 codepoints:
`casefold_matches_python_over_all_codepoints`,
`uppercase_matches_python_over_all_codepoints`,
`python_strip_matches_python_over_all_codepoints`. The packed-string
representation and its parse were moved verbatim; no mapping changed.

### Planted-duplicate proofs

Both fire, and each isolates the half of the widening it tests.

Proof 1, a duplicate in a non-model module (`critic/metrics.rs` against
`model/shared.rs`): BOTH keys fail, naming
`py_casefold_planted in [("critic/metrics.rs", ...), ("model/shared.rs", ...)]`.
The old four-file audit would have seen neither module.

Proof 2, a short-bodied duplicate with different names (`planted_a` in
`critic/metrics.rs`, `planted_b` in `impose.rs`, body `x + 1`, five
characters): the body key fails naming both places, and the name key
correctly passes because the names differ. The body is an eighth of the
removed 40-character floor, so this is precisely the case the floor hid.

Both plants were reverted from backups and the tree confirmed clean.

### Suite

103 tests across 10 binaries, all passing; `cargo fmt --check` and
`cargo clippy --all-targets -- -D warnings` clean.

## Verdicts

No parity verdict is produced by this WP. The oracle digests above are the
verdict-equivalent, and all are unchanged.

## Residuals

- **Eight genuine duplicates are allowlisted, not fixed**, because none is
  in this WP's Owns: `read` (four copies), `prompts_path` (drifted),
  `resolve_edition_dir`, `esc`/`escape_text`, `deref`/`resolve`. They need
  an owner. `prompts_path` is the urgent one, being a live behavioural
  difference rather than duplication alone.
- **`parity/display.rs`, `parity/streams.rs` and `parity/report.rs` were
  held by WP-0.2h** while this ran, which is why their duplicates are
  deferred rather than fixed.
- **The `Tagged` decision is reasoned, not measured**, because PyYAML cannot
  produce the input. If a future loader stops using `safe_load`, it becomes
  reachable and should be re-decided against real Python behaviour.
- **The audit parses source text rather than a syntax tree**, which is safe
  only because `cargo fmt` is hook-enforced. Unchanged from WP-5.1d.
- **The drifted-and-renamed blind spot** is unclosed by design; the shared
  module rule is the mitigation.
- WP-5.4a is **in rework** after its rejection at `ff5cd21`, and its rework
  touches `cover/text.rs`. This WP lifted first, so that rework builds on
  the shared module; its `Tagged` determination should adopt the decision
  recorded above rather than making a second one.

## Status

done
