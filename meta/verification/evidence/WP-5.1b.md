# WP-5.1b records port

## Base

`7d79b9d02ab3ec30e920442f4c08e30a95a676c0` on `art_directed`.

Ports `src/magazine/records.py` and `src/magazine/media_schema.py` to
`mag/src/model/records.rs`. Both originals stay until WP-6.1.

## Commands

Every command runs from the repository root. `library/sources/` is tracked, so
the corpus oracle needs no untracked input and `cargo test` proves it directly.

Regenerate the corpus oracle (96 records):

```
uv run python -c "
import json, sys
sys.path.insert(0, 'src')
from pathlib import Path
from magazine.records import load_records
records = load_records(Path('library/sources'))
print(json.dumps([r.to_dict() for r in records], indent=2, sort_keys=True, ensure_ascii=False), file=open('mag/tests/model_records_expected.json','w'))
print('records:', len(records))
"
```

Regenerate the record-loader fixtures oracle (11 documents under
`mag/tests/model_records_fixtures/records/`) and the URL table (19 inputs):

```
uv run python -c "
import json, sys
sys.path.insert(0, 'src')
from pathlib import Path
from magazine.errors import ValidationError
from magazine.records import SourceRecord, canonicalize_url
from magazine.io import load_structured
records_dir = Path('mag/tests/model_records_fixtures/records')
out = {}
for path in sorted(records_dir.glob('*.yaml')):
    try:
        out[path.stem] = {'ok': SourceRecord.from_dict(load_structured(path)).to_dict()}
    except ValidationError as exc:
        out[path.stem] = {'errors': exc.errors}
Path('mag/tests/model_records_records_expected.json').write_text(
    json.dumps(out, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
urls = ['https://Example.COM/a//b/?utm_source=x&b=2&a=1&ref=z','http://example.com:80/p/','https://example.com:8443/',
        'https://x.com/a/b/','https://e.com','https://e.com/?q=a b&q=c+d','https://e.com/path/?empty=',
        'HTTPS://E.com:443/A/','ftp://e.com/x','not a url','https:///nohost','  https://e.com/pad  ',
        'https://user:pw@e.com/x','https://e.com/a?Utm_Campaign=1&UTM_x=2&Ref=3&keep=4','https://e.com/%7Euser/',
        'https://e.com/a#frag','https://e.com/a?b=%C3%A9','https://e.com//////','https://e.com/a/b/../c']
table = {}
for u in urls:
    try: table[u] = {'ok': canonicalize_url(u)}
    except ValidationError as exc: table[u] = {'errors': exc.errors}
Path('mag/tests/model_records_urls_expected.json').write_text(
    json.dumps(table, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
print('records:', len(out), 'urls:', len(table))
"
```

Regenerate the constructor oracle (`SourceRecord.create` and `source_id`):

```
uv run python -c "
import json, sys
sys.path.insert(0, 'src')
from pathlib import Path
from magazine.errors import ValidationError
from magazine.records import SourceRecord, source_id
cases = [
  {'name':'plain','url':'https://Example.com/a/?utm_source=x','title':'A Fine Title','author':'  Writer  ','published_at':'2026-01-02','captured_at':'2026-03-04T05:06:07Z','tags':['  Beta ','alpha','ALPHA','  '],'synopsis':'  S  ','notes':'  N  '},
  {'name':'no_title','url':'https://example.com/b','title':None,'author':None,'published_at':None,'captured_at':'2026-03-04T05:06:07Z','tags':[],'synopsis':'','notes':''},
  {'name':'blank_author','url':'https://example.com/c','title':'T','author':'   ','published_at':None,'captured_at':'2026-03-04T05:06:07Z','tags':None,'synopsis':'','notes':''},
  {'name':'unicode_title','url':'https://example.com/d','title':'Ünïcode — Tïtle!!','author':None,'published_at':None,'captured_at':'2026-03-04T05:06:07Z','tags':['x'],'synopsis':'','notes':''},
  {'name':'bad_url','url':'ftp://example.com/e','title':'T','author':None,'published_at':None,'captured_at':'2026-03-04T05:06:07Z','tags':[],'synopsis':'','notes':''},
]
out = {}
for c in cases:
    try:
        rec = SourceRecord.create(c['url'], title=c['title'], author=c['author'], published_at=c['published_at'],
                                  captured_at=c['captured_at'], tags=c['tags'], synopsis=c['synopsis'], notes=c['notes'])
        out[c['name']] = {'ok': rec.to_dict()}
    except ValidationError as exc:
        out[c['name']] = {'errors': exc.errors}
ids = {f'{t}|{u}': source_id(t, u) for t, u in
       [('A Fine Title','https://example.com/a'), ('!!!','https://example.com/b'),
        ('x'*60,'https://example.com/c'), ('Ünïcode','https://example.com/d')]}
Path('mag/tests/model_records_create_expected.json').write_text(
    json.dumps({'create': out, 'source_id': ids}, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
print('create cases:', len(out), 'source_id cases:', len(ids))
"
```

Regenerate the refusal-matrix oracle (42 cases over
`mag/tests/model_records_fixtures/cases.yaml`). The absolute fixture root is
replaced by the literal `<ROOT>` so the committed file is machine independent;
the Rust test applies the same substitution.

```
uv run python -c "
import json, sys, yaml
sys.path.insert(0, 'src')
from pathlib import Path
from magazine.errors import ValidationError
from magazine.media_schema import (resolve_figures, resolve_extracts, localize_figures,
                                   localize_extracts, Figure, Extract)
base_dir = Path('mag/tests/model_records_fixtures')
root = base_dir / 'root'
cases = yaml.safe_load((base_dir / 'cases.yaml').read_text(encoding='utf-8'))
rel = lambda p: Path(p).relative_to(root).as_posix()
fig_json = lambda f: {'id': f.id, 'source_id': f.source_id, 'path': rel(f.path), 'caption': f.caption,
                      'credit': f.credit, 'alt_text': f.alt_text, 'anchor': f.anchor, 'layout': f.layout}
ext_json = lambda x: {'id': x.id, 'source_id': x.source_id, 'text': x.text, 'style': x.style,
                      'caption': x.caption, 'anchor': x.anchor}
def base_figures(case):
    return tuple(Figure(r['id'], r['source_id'], root / 'library' / 'sources' / r['source_id'] / r['path'],
                        r['caption'], r['credit'], r['alt_text'], r['anchor'], r['layout'])
                 for r in case.get('base') or [])
def base_extracts(case):
    return tuple(resolve_extracts(root, article_id='seed', article_source_ids=(r['source_id'],),
                 manuscript=root / 'manuscripts' / 'en.md', rows=[r], allow_unanchored=True)[0]
                 for r in case.get('base') or [])
results = {}
for case in cases:
    name, kind = case['name'], case['kind']
    manuscript = root / 'manuscripts' / case['manuscript']
    translated = root / 'manuscripts' / case.get('translated_manuscript', case['manuscript'])
    try:
        if kind == 'figures':
            value = [fig_json(f) for f in resolve_figures(root, article_id=case['article_id'],
                     article_source_ids=tuple(case['source_ids']), manuscript=manuscript,
                     rows=case.get('rows'), allow_unanchored=case.get('allow_unanchored', False))]
        elif kind == 'extracts':
            value = [ext_json(x) for x in resolve_extracts(root, article_id=case['article_id'],
                     article_source_ids=tuple(case['source_ids']), manuscript=manuscript,
                     rows=case.get('rows'), allow_unanchored=case.get('allow_unanchored', False))]
        elif kind == 'localize_figures':
            value = [fig_json(f) for f in localize_figures(base_figures(case), case.get('rows'),
                     article_id=case['article_id'], manuscript=translated, language=case['language'])]
        else:
            value = [ext_json(x) for x in localize_extracts(base_extracts(case), case.get('rows'),
                     article_id=case['article_id'], manuscript=translated, language=case['language'])]
        results[name] = {'ok': value}
    except ValidationError as exc:
        results[name] = {'errors': [e.replace(str(root), '<ROOT>') for e in exc.errors]}
Path('mag/tests/model_records_cases_expected.json').write_text(
    json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
print('cases:', len(results), 'errors:', sum(1 for v in results.values() if 'errors' in v))
"
```

Verification:

```
cd mag && cargo fmt --check
cd mag && cargo clippy --all-targets -- -D warnings
cd mag && cargo test
cd mag && cargo test --test model_records
```

Regenerating every oracle above and rerunning `cargo test --test model_records`
must leave the four committed JSON files byte-identical and the seven tests
green; that is the whole acceptance check for this WP.

## Tool versions

- python 3.12.11, uv 0.8.17, PyYAML 6.0.3
- rustc 1.96.0, cargo 1.96.0
- new crates: none. `serde`, `serde_yaml`, `serde_json`, `regex`, `sha2`, `hex`
  were already in `mag/Cargo.toml`, so `Cargo.toml` and `Cargo.lock` are
  unchanged by this WP.

## Metrics

Corpus oracle, `library/sources/`:

- 96 records loaded by both sides, 58040 bytes of sorted JSON, equal.
- Corpus shape surveyed before porting: every value a string except `tags`
  (list of strings); zero nulls; zero `notes`; zero `metadata` blocks; zero
  `canonical_url` / `submitted_url` / `publication_date` fallbacks; 81 of 96
  carry `published_at`. So the corpus alone exercises only the happy path,
  which is why the four fixture oracles below exist.

Fixture oracles, all equal:

- record loader: 11 documents, 2559 bytes, covering both timestamp paths, the
  three url fallbacks, `publication_date`, the `metadata` fallback, a full
  record with notes, an empty id, and a missing-field refusal.
- urls: 19 inputs, 1444 bytes, 2 refusals.
- constructor: 5 `create` cases plus 4 `source_id` cases, 1803 bytes.
- refusal matrix: 42 cases, 6680 bytes, of which 32 are refusals.

Test suite: 7 tests in `mag/tests/model_records.rs`, 0.04 s.
Whole `cargo test`: green (the fault suite dominates at 21 s).

Refusal sites covered. Every `ValidationError` raise site in the two modules is
listed with the case that provokes it and the Rust site that produces the same
message. Messages are compared in full, not by substring, so the mapping is
proven rather than asserted.

| Python raise site | case | Rust site |
|---|---|---|
| `records.canonicalize_url` non-http(s) | url table `ftp://e.com/x`, `not a url`, `https:///nohost`; `create` `bad_url` | `canonicalize_url` |
| `records.SourceRecord.from_dict` missing | `missing_fields`, `empty_id` | `SourceRecord::from_value` |
| `records.load_records` duplicate url | not provoked (see Residuals) | `load_records` |
| `media_schema.resolve_figures` not a list | `figures_not_a_list` | `resolve_figures` |
| `media_schema.resolve_figures` maximum 3 | `figures_too_many` | `resolve_figures` |
| `_figure_fields` row not a mapping | `figures_row_not_mapping` | `resolve_figures` |
| `_figure_fields` missing | `figures_missing_fields` (and `figures_credit_optional` proves credit is exempt) | `resolve_figures` |
| `resolve_figures` duplicate id | `figures_duplicate_id` | `resolve_figures` |
| `_resolve_figure` source_id | `figures_unknown_source_id` | `resolve_figure` |
| `_resolve_figure` unsafe path | `figures_unsafe_path`, `figures_absolute_path` | `resolve_figure` |
| `_resolve_figure` invalid layout | `figures_invalid_layout` | `resolve_figure` |
| `_resolve_figure` anchor | `figures_bad_anchor` (and `figures_bad_anchor_allowed`, `figures_opener_anchor` prove the two exemptions) | `resolve_figure` |
| `_resolve_figure` missing image | `figures_missing_image` | `resolve_figure` |
| `resolve_extracts` not a list | `extracts_not_a_list` | `resolve_extracts` |
| `resolve_extracts` maximum 2 | `extracts_too_many` | `resolve_extracts` |
| `_extract_fields` row not a mapping | `extracts_row_not_mapping` | `resolve_extracts` |
| `_extract_fields` missing | `extracts_missing_fields` | `resolve_extracts` |
| `resolve_extracts` duplicate id | `extracts_duplicate_id` | `resolve_extracts` |
| `resolve_extracts` source_id | `extracts_unknown_source_id` | `resolve_extracts` |
| `_check_extract_style` invalid style | `extracts_invalid_style` | `check_extract_style` |
| `_check_extract_style` anchor | `extracts_bad_anchor` | `check_extract_style` |
| `_extract_run` missing source article | `extracts_missing_source_article` | `extract_run` |
| `_extract_run` begin not unique | `extracts_begin_not_unique`, `extracts_begin_absent` | `extract_run` |
| `_extract_run` end not unique | `extracts_end_not_unique` | `extract_run` |
| `_check_extract_text` code whitespace | `extracts_code_whitespace` | `check_extract_text` |
| `_check_extract_text` already verbatim | `extracts_already_in_manuscript` | `check_extract_text` |
| `localize_figures` absent from English | `localize_figures_absent_base` | `localize_figures` |
| `localize_figures` not a list | `localize_figures_not_a_list` | `localize_figures` |
| `localize_figures` missing / unknown ids | `localize_figures_missing_and_unknown` (both messages in one case) | `compare_ids` |
| `localize_figures` incomplete fields | `localize_figures_incomplete_fields` | `localize_figures` |
| `localize_figures` translated anchor | `localize_figures_bad_anchor` | `localize_figures` |
| `localize_extracts` absent from English | `localize_extracts_absent_base` | `localize_extracts` |
| `localize_extracts` incomplete fields | `localize_extracts_incomplete_fields` (fires both its messages) | `localize_extracts` |

## Verdicts

This WP produces no `verdict.json`; it is a Phase 5 port whose oracle is
direct Python-to-Rust equality, not `mag parity` (Phase 5 preamble). The
committed oracle dumps stand in for verdict digests:

- `mag/tests/model_records_expected.json` sha256
  `611d885cb7f67269790110a2e6447be855657b9d9495e95ae7f47aa7c5452d2d`
- `mag/tests/model_records_records_expected.json` sha256
  `1e9bc57520012bc3013a6d7a3e1c0d24b825b964d6fad1cf4ae024e14735181f`
- `mag/tests/model_records_urls_expected.json` sha256
  `86b070c51f8567edb9a3068ee4c5e493a61abe9322ccebd326e4170d09083267`
- `mag/tests/model_records_create_expected.json` sha256
  `9d18310cb0f12b18c7111f46020a0a5816352da8790ba019655eae794abb5005`
- `mag/tests/model_records_cases_expected.json` sha256
  `acf56e755f666abd5b1208dbdb95e66e0a377092cbd349f984c0c7c397a21e09`

Regenerating each oracle from the commands above must reproduce these digests
byte for byte.

## Residuals

Two divergences found while porting, both fixed, both proven by the oracle:

1. `SourceRecord.create` with a whitespace-only author. Python evaluates
   `author.strip() if author else None`, so `"   "` is truthy and the result is
   `""`, not `None`. The first Rust draft filtered the empty result to `None`.
   Caught by the `blank_author` case.
2. A tight list item in `records.py` is not involved, but the Python error text
   uses `repr`, which quotes with `'` and switches to `"` only when the value
   contains a `'`. Rust's `{:?}` always uses `"`. A `py_repr` helper reproduces
   Python's rule; without it, seven messages differed. Caught by the refusal
   matrix.

Deliberate divergences, each strictly in the refuse-rather-than-guess
direction, none reachable from the current corpus:

- Wrong scalar types in a record (`tags: 5`, `title: []`, a non-string
  `synopsis`) are refused by Rust where Python coerces or stores them. The
  corpus has none; `record.yaml` is machine written by `mag capture`.
- Figure and extract row fields holding a non-empty sequence or mapping are
  refused by Rust; Python would stringify them (`"['a']"`) and then usually
  fail a later validation with different text.
- A YAML timestamp with a timezone offset of 24 hours or more is formatted by
  Rust; Python's `datetime.timezone` would raise. Unreachable from valid YAML
  in practice.

Behavioural notes a later WP should know:

- PyYAML types an UNQUOTED timestamp scalar as `date`/`datetime`, and
  `from_dict` then rewrites it through `isoformat()`; a QUOTED one stays a
  string untouched. `serde_yaml` returns a string either way, so the port
  detects plain scalars from the raw document text (`plain_scalar`) and applies
  `yaml_timestamp_isoformat` only then. The corpus is 100 percent quoted, so
  this path is exercised solely by the `plain_timestamp`, `plain_dates` and
  `plain_with_comment` fixtures, where Python turns `2026-07-29T00:35:54Z` into
  `2026-07-29T00:35:54+00:00` while the quoted form keeps its `Z`. The detector
  only inspects a top-level `key: value` on one line and never coerces a quoted
  or empty value; a record whose dates live in a nested or block scalar is left
  alone, as Python would also leave a non-date alone.
- `load_records` glob order differs. Python iterates `Path.glob` in filesystem
  order and the duplicate-URL message names whichever record it met first;
  Rust sorts paths, so its message is deterministic. The final sort by
  `(captured_at, id)` descending is identical on both sides and ids are unique,
  so the returned order never differs. The duplicate case is therefore not in
  the refusal matrix: reproducing Python's message would mean reproducing a
  filesystem ordering. Recorded rather than papered over.
- `SourceRecord::create` takes `captured_at` explicitly instead of defaulting
  to `datetime.now`. `mag capture` already owns clock access on the Rust side,
  and a defaulted clock cannot be oracle-compared.
- `Path.splitlines` in `semantic_headings` splits on Unicode line boundaries
  (`\v`, `\f`, ` `, ...); Rust `str::lines` splits on `\n` only. Manuscripts
  use `\n`. Likewise `str.strip()` and Rust `trim()` differ on a few control
  characters outside `White_Space`.
- `mag/src/model.rs` gains `pub mod records;`. The `#[allow(dead_code)]` on
  `mod model;` in `main.rs` (WP-5.1a) still applies and was not touched; nothing
  in the binary consumes the model yet. WP-5.1c and WP-2.1 remove it when they
  wire the model in.
- `ValidationError` is defined in `records.rs` as a `Vec<String>` mirroring
  `errors.py`. WP-5.1c ports `manifest.py`, which raises the same type; whoever
  cuts that WP should lift this into a shared module rather than define a
  second one.

## Status

done
