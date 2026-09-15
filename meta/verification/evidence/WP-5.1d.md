# WP-5.1d consolidate the model helpers

## Base

`c13187e` (verify(model): WP-5.1c third rework accepted). Precondition met:
WP-5.1b accepted at `6f607f7` and WP-5.1c accepted at `c13187e`, so no rework
was in flight against `mag/src/model/**`.

## Commands

Baseline, before any edit, from a worktree at the base commit with the
untracked run directory copied in:

```
cp -R editions/010/run-2026-09-13T01-34-51 <worktree>/editions/010/
shasum -a 256 mag/tests/*.json mag/tests/model_doc_settable.txt
```

Python projection oracle for WP-5.1a's 010 comparison, regenerated rather
than reused:

```
uv run python -c '
import json, pathlib, sys
sys.path.insert(0, "src")
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
' > /tmp/wp51d-py-projection.json
```

Full suite, before and after, with the 010 oracle wired in:

```
cd mag && MAG_MODEL_ARTICLES=$PWD/../editions/010/run-2026-09-13T01-34-51/articles \
  MAG_MODEL_ORACLE=/tmp/wp51d-py-projection.json cargo test
```

Python repr oracle for the nine `REPR_CASES`, written with `chr()` so the
source carries no literal control characters:

```
uv run python -c '
import json
cases = [
    "plain",
    "caf" + chr(233),
    "zero" + chr(0x200b) + "width",
    "bell" + chr(7) + "stop",
    "esc" + chr(0x1b) + "stop",
    "astral" + chr(0xf0000) + "stop",
    "it" + chr(39) + "s " + chr(34) + "both" + chr(34),
    "back" + chr(92) + "slash" + chr(10) + "new" + chr(13) + "ret" + chr(9) + "tab",
    "it" + chr(39) + "s plain",
]
print(json.dumps({c: repr(c) for c in cases}, sort_keys=True, indent=1, ensure_ascii=True))
' > mag/tests/model_manifest_repr_expected.json
```

Audit discrimination proofs (each restored afterwards, `git status` clean):

```
cargo test --test model_helpers
```

Style and lints:

```
cd mag && cargo fmt --all -- --check && cargo clippy --all-targets -- -D warnings
```

## Tool versions

rustc 1.96.0, cargo 1.96.0, python 3.12.11, uv 0.8.17.

## Metrics

What was lifted, into the new `mag/src/model/shared.rs`:

| item | was | now |
|---|---|---|
| `ValidationError` + `one` + `Display` + `Error` | `records.rs` only | `shared.rs`, one definition |
| `Result<T>` alias | `records.rs` only | `shared.rs`, one definition |
| `py_repr` | `records.rs` AND `manifest.rs` | `shared.rs`, one definition |
| `printable`, `nonprintable`, `escape` | `records.rs` AND `manifest.rs` | `shared.rs`, private to it |
| `normalize` | `manifest.rs` only | `shared.rs` (needed by `safe_project_path`) |
| `safe_project_path` | `manifest.rs` only | `shared.rs` |
| `load_structured` | `manifest.rs` only | `shared.rs` |

The four genuinely duplicated bodies were byte-identical before the lift
(`records.rs` 226-270 against `manifest.rs` 2232-2276, `diff` empty), so the
lift could not change behaviour by choosing between variants.

Net: 34 insertions, 172 deletions across the five modified files, plus
`shared.rs`.

Oracle digests, before and after. Every pre-existing oracle is unchanged:

| oracle | before | after |
|---|---|---|
| `critic_metrics_expected.json` | `c519fdfb` | `c519fdfb` |
| `critic_metrics_rounding_expected.json` | `1d642913` | `1d642913` |
| `model_doc_expected.json` | `4a584524` | `4a584524` |
| `model_manifest_cases_expected.json` | `1045b017` | `1045b017` |
| `model_records_cases_expected.json` | `34feb1a9` | `34feb1a9` |
| `model_records_create_expected.json` | `be1563b1` | `be1563b1` |
| `model_records_expected.json` | `611d885c` | `611d885c` |
| `model_records_ports_expected.json` | `331c78f3` | `331c78f3` |
| `model_records_records_expected.json` | `1e9bc575` | `1e9bc575` |
| `model_records_urls_expected.json` | `271f1aed` | `271f1aed` |
| `model_doc_settable.txt` | `df2687d0` | `df2687d0` |
| `model_manifest_repr_expected.json` | absent | `e7186560` (new) |

WP-5.1a's 010 projection regenerated to
`e17ca71cffabe08b08820dd268863dcbda04615a871e5feaf52c34ca907cda50` at 208,052
bytes, matching the digest WP-5.1a recorded, and
`edition_manuscripts_match_the_python_projection` passes against it.

Suite: 93 tests before, 95 after. The two added are the audit; no test was
removed. Every target green in both runs.

## Verdicts

The duplicate-helper audit is `mag/tests/model_helpers.rs`, two checks over
the four model modules, parsed into (module, name, signature, normalised
body) items.

**How it distinguishes real duplicates from the known false positives.** Two
keys, deliberately different, because neither alone is sufficient:

- `no_helper_is_defined_in_two_model_modules` keys on **(name, signature)**
  with the visibility prefix normalised away. A drifted copy still shares
  both, so it fires even when the bodies have diverged, which is the case
  that matters: the WP-5.1c defect was a copy whose body had drifted from
  its original, and pure body equality would have missed it.
- `no_body_is_copied_between_model_modules` keys on the **normalised body**,
  ignoring names, and skips bodies under 40 characters. It catches a copy
  that was renamed, which the first check cannot see.

The four known false positives do not fire, and this is empirical rather
than asserted: all four are present in the tree right now and both checks
are green.

| pair | why it does not fire |
|---|---|
| `truthy` in `records.rs` and `manifest.rs` | same name, different signature (`Option<&String>` against `Option<&Value>`), so the first key differs; bodies differ, so does the second. They are different domains, as WP-5.1c's verifier established, and merging them would be wrong |
| `slashes` against `nonprintable` | different names; bodies share only the `OnceLock<Regex>` idiom and carry different patterns |
| `is_absent` against `blank_header_field` | different names; bodies genuinely differ, the latter also treating an empty string as blank |
| `mapping_get` against `insert` | different names; both bodies fall under the 40-character floor and differ anyway |

This is why the audit is not a similarity score. The three cross-name pairs
above are exactly what a similarity metric flags, and all three are correct
code. Exact normalised equality has no such hits, and the name-and-signature
key covers the drift case a body metric cannot.

**Discrimination proved in both directions, run rather than asserted.**

| perturbation | `no_helper_is_defined...` | `no_body_is_copied...` |
|---|---|---|
| none (as committed) | ok | ok |
| the WP-5.1c defect reinstated: `manifest.rs` carries its own `py_repr`, `printable`, `nonprintable`, `escape` | FAILED, naming all four | FAILED, naming all four |
| `safe_project_path` copied into `manifest.rs` as `tidy_project_path` | ok | FAILED, naming the pair |

The middle row is the original defect reproduced exactly, and both checks
catch it. The last row is the renamed-copy case that only the body check can
see, which is why both exist.

One defect in my own audit, found by running the first proof rather than by
reading it: the signature key initially included the visibility prefix, so
`pub(crate) fn py_repr` in `shared.rs` and `fn py_repr` in `manifest.rs` did
not collide and only the body check fired. Normalising visibility out fixed
it, and the proof was re-run: `py_repr` now appears in the first check's
failure list alongside the other three.

**`py_repr_copies_agree` is repointed, not deleted.** Its premise was that
two copies existed; with one definition it would compare a function against
itself and pass vacuously. Deleting it would have lost real coverage, since
WP-5.1c's verifier established that the backslash case is caught by that test
and not by `cases_match_the_python_loader`. It is now
`repr_cases_match_python`, which asserts, for each of the nine cases, that
`py_repr` matches **Python's own `repr`** from a committed oracle, and that
both the manifest route (`load_translation`) and the records route
(`localize_figures`) produce that same rendering. That is strictly stronger
than before: agreement between copies is upgraded to correctness against
Python, while the end-to-end reach through both modules is kept, which is
what proves the consolidation did not leave one module calling something
else. The nine cases still cover every escape width (`\xNN`, `\uNNNN`,
`\UNNNNNNNN`), all four literal-escape arms, and both quote selections.

## Residuals

- `py_repr_value` in `manifest.rs` is not a duplicate of `py_repr`; it
  formats a `serde_yaml::Value` and delegates. It is untouched.
- The audit parses Rust with a line scanner rather than a real parser. It
  relies on the repo's formatting being `cargo fmt` output, which the
  pre-commit hook enforces, and on a closing brace at the item's own
  indentation. It asserts it found more than 100 items, so a parser
  regression that silently matched nothing would fail rather than pass.
- The 40-character floor on the body check is a noise filter, not a
  threshold on correctness: shorter bodies are caught by the name and
  signature key when they are genuine duplicates.
- `shared.rs` is now included by the test targets through `#[path]` in
  `model_records.rs` and `model_manifest.rs`, matching the existing pattern
  that exists because `mag` has no library target.

## Status

done
