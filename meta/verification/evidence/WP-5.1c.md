# WP-5.1c manifest port

## Base

First submission: 6e8abb8 (`feat(parity): WP-0.0c opener header carries
data-article-id`), on `art_directed`, plan revision 9. That submission was
REJECTED by verify commit `66f6f90` for a stale `py_repr` copy.

Rework: 9a5c1cb, plan revision 11. The rework changes `py_repr` in
`manifest.rs`, adds five non-printable fixture cases with their oracle
entries, and corrects the claims in clauses 3, 8, 9, 10 and `## Metrics`.
Nothing else in the port changed, and the clauses the verifier confirmed
sound (the 010 oracle chain, refusal coverage, the shared `ValidationError`,
ordering, both declared divergences) were deliberately left alone.

## Commands

Every command runs from the repository root. The edition 010 run directory
`editions/010/run-2026-09-13T01-34-51` is UNTRACKED and must be present; a
verifier working in a fresh worktree copies it in first:

    cp -R /Users/franguijarro/code/magazine/editions/010/run-2026-09-13T01-34-51 <worktree>/editions/010/

### 1. Build the staged root the 010 oracle loads from

`edition.yaml` names manuscripts at `editions/010/articles/<slug>.md`, but
those files exist only inside the run directory, so `mag render` stages them
(`stage_manuscripts` in `mag/src/render.rs` maps `run/articles/<id>/final.md`
onto the declared path). Both legs of the oracle must therefore load from a
staged root, not from the repository root. Build one:

    STAGE=$(mktemp -d)/wp51c-stage && python3 - "$STAGE" <<'PY'
    import shutil, sys, yaml
    from pathlib import Path
    root = Path(".").resolve()
    stage = Path(sys.argv[1])
    (stage / "editions/010/articles").mkdir(parents=True)
    shutil.copy2(root / "editions/010/edition.yaml", stage / "editions/010/edition.yaml")
    shutil.copytree(root / "library", stage / "library")
    data = yaml.safe_load((root / "editions/010/edition.yaml").read_text())
    run = root / "editions/010/run-2026-09-13T01-34-51"
    staged = 0
    for article in data.get("articles") or []:
        dst = stage / article["manuscript"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(run / "articles" / article["id"] / "final.md", dst)
        staged += 1
    art = []
    if (data.get("cover") or {}).get("art_path"):
        art.append(data["cover"]["art_path"])
    for article in data.get("articles") or []:
        if article.get("tail_art_path"):
            art.append(article["tail_art_path"])
        if (article.get("opener_art") or {}).get("path"):
            art.append(article["opener_art"]["path"])
    for plate in data.get("closing_plates") or []:
        if plate.get("art_path"):
            art.append(plate["art_path"])
    for rel in art:
        dst = stage / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, dst)
    print(f"manuscripts={staged} art={len(art)}")
    PY

Expect `manuscripts=9 art=24`, about 135 MB.

### 2. Python oracle for edition 010 (the loader-owned subset)

Run from inside `$STAGE` so the loader's root is the staged tree:

    cd "$STAGE" && uv run --project /Users/franguijarro/code/magazine python -c '
    import json, sys
    from pathlib import Path
    sys.path.insert(0, "/Users/franguijarro/code/magazine/src")
    from magazine.manifest import load_edition
    from magazine.records import load_records
    from magazine.reader_layout import declared_editorial_page_cap
    root = Path(".").resolve()
    records = {r.id: r for r in load_records(root / "library" / "sources")}
    e = load_edition(root, "010", set(records), publication_name="Magazine", source_records=records)
    print(json.dumps({
      "edition": e.raw,
      "layout": {
        "maximum_article_pages": int((e.raw.get("format") or {}).get("max_article_pages", 7)),
        "article_page_caps": {a.id: (10 if a.content_mode == "verbatim" else 7) for a in e.articles},
        "article_content_modes": {a.id: a.content_mode for a in e.articles},
        "maximum_editorial_pages": declared_editorial_page_cap(e.raw, 2),
      },
    }, sort_keys=True, default=str))
    ' > /tmp/wp51c_python.json

`article_page_cap` is inlined as `10 if verbatim else 7` because its home,
`weasyprint_adapter.py`, imports WeasyPrint, which does not load outside the
renderer environment (recorded by WP-0.1). The constants are
`_MAX_VERBATIM_PAGES = 10` and `_MAX_ARTICLE_PAGES = 7` at
`weasyprint_adapter.py:32-33`, and clause 3 below checks the inlined values
against a real rendered manifest rather than trusting them.

### 3. The plan's jq extraction, against a real rendered manifest

    M=editions/010/render-2026-09-14T01-47-59/en/edition-manifest.json
    jq -S '{edition, layout: (.layout | {maximum_article_pages, article_page_caps, article_content_modes, maximum_editorial_pages})}' "$M" > /tmp/from_render.json
    jq -S '.' /tmp/wp51c_python.json > /tmp/from_loader.json
    jq -e '[.layout|..|select(.==null)]|length==0' /tmp/from_render.json   # no-null sanity
    diff /tmp/from_render.json /tmp/from_loader.json

Expect the no-null check to print `true` and the diff to be empty. Any
render directory containing `en/edition-manifest.json` works; a fresh one
comes from `cargo run -- render 010 --no-model --run editions/010/run-2026-09-13T01-34-51`.

### 4. Rust side of the 010 oracle

    cd mag && MAG_MANIFEST_ROOT="$STAGE" MAG_MANIFEST_ORACLE=/tmp/wp51c_python.json \
      cargo test --test model_manifest edition_010

Both variables or neither: with neither set the test returns early and the
010 comparison is NOT exercised (plain `cargo test` is in that mode), with
exactly one set it fails loudly.

Negative check, which must FAIL:

    python3 -c "
    import json
    d=json.load(open('/tmp/wp51c_python.json'))
    d['layout']['article_page_caps']['dario-amodei-we-must-pace-the-frontier']=7
    json.dump(d,open('/tmp/wp51c_bad.json','w'))"
    cd mag && MAG_MANIFEST_ROOT="$STAGE" MAG_MANIFEST_ORACLE=/tmp/wp51c_bad.json \
      cargo test --test model_manifest edition_010

### 5. Regenerate the committed case expectations

`mag/tests/model_manifest_cases_expected.json` is generated from
`mag/tests/model_manifest_fixtures/cases.yaml` by running the Python loader
over every case. Both sides build the same temporary root from each case's
`files` map, so neither side can drift:

    uv run python -c '
    import json, sys, tempfile, yaml
    from pathlib import Path
    sys.path.insert(0, "src")
    from magazine.manifest import load_edition, load_translation
    from magazine.errors import ValidationError
    from magazine.records import SourceRecord
    def rel(path, root):
        try: return path.relative_to(root).as_posix()
        except ValueError: return str(path).replace(str(root), "<ROOT>")
    def dump(e, root):
        return {"id": e.id, "publication_name": e.publication_name, "issue_number": e.issue_number,
            "title": e.title, "publication_date": e.publication_date, "language": e.language, "locale": e.locale,
            "editorial": None if not e.editorial else {"path": rel(e.editorial.path, root), "title": e.editorial.title, "byline": e.editorial.byline, "label": e.editorial.label},
            "articles": [{"id": a.id, "title": a.title, "short_title": a.short_title, "display_emphasis": a.display_emphasis,
                "opener_variant": a.opener_variant, "author": a.author, "author_note": a.author_note, "source_ids": list(a.source_ids),
                "manuscript": rel(a.manuscript, root), "content_mode": a.content_mode, "minimum_reader_pages": a.minimum_reader_pages,
                "tail_art": None if a.tail_art is None else rel(a.tail_art, root), "source_url": a.source_url,
                "opener_art": None if not a.opener_art else {"path": rel(a.opener_art.path, root), "alt_text": a.opener_art.alt_text, "credit": a.opener_art.credit},
                "key_ideas": list(a.key_ideas), "dateline": a.dateline,
                "figures": [{"id": f.id, "source_id": f.source_id, "path": str(f.path), "caption": f.caption, "credit": f.credit, "alt_text": f.alt_text, "anchor": f.anchor, "layout": f.layout} for f in a.figures],
                "extracts": [{"id": x.id, "source_id": x.source_id, "style": x.style, "caption": x.caption, "anchor": x.anchor} for x in a.extracts]} for a in e.articles],
            "sections": [{"kind": s.kind, "title": s.title, "path": rel(s.path, root)} for s in e.sections],
            "cover": e.cover, "cover_art": None if e.cover_art is None else rel(e.cover_art, root),
            "closing_plates": [{"title": p.title, "art_path": rel(p.art_path, root)} for p in e.closing_plates], "raw": e.raw}
    cases = yaml.safe_load(Path("mag/tests/model_manifest_fixtures/cases.yaml").read_text())
    out = {}
    for case in cases:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            for name, content in (case.get("files") or {}).items():
                t = root / name; t.parent.mkdir(parents=True, exist_ok=True); t.write_text(content, encoding="utf-8")
            records = {k: SourceRecord(id=k, url=v["url"], title=v["title"], captured_at="2026-01-01T00:00:00Z", published_at=v.get("published_at")) for k, v in (case.get("records") or {}).items()}
            try:
                ed = load_edition(root, case["edition_id"], set(case.get("known_sources") or []), publication_name="Magazine",
                    source_records=records, allow_missing_art=case.get("allow_missing_art", False),
                    allow_unanchored_figures=case.get("allow_unanchored_figures", False))
                if case.get("translation"): ed = load_translation(root, ed, case["translation"])
                outcome = {"ok": dump(ed, root)}
            except ValidationError as exc:
                outcome = {"errors": [str(m).replace(str(root), "<ROOT>") for m in exc.errors]}
            except Exception as exc:
                outcome = {"crash": f"{type(exc).__name__}: {exc}"}
            out[case["name"]] = outcome
    print(json.dumps(out, indent=1, sort_keys=True, default=str))
    ' > mag/tests/model_manifest_cases_expected.json

The file must regenerate byte-for-byte; `git diff --stat` is the check.

### 6. Refusal-site coverage

    python3 - <<'PY'
    import ast, json
    def sites_of(path):
        tree = ast.parse(open(path).read()); found = []
        class V(ast.NodeVisitor):
            def visit_Call(self, node):
                a1 = (isinstance(node.func, ast.Attribute) and node.func.attr == "append" and getattr(node.func.value, "id", "") == "errors")
                a2 = (isinstance(node.func, ast.Name) and node.func.id == "ValidationError")
                if a1 or a2:
                    for a in node.args: found.append((path, node.lineno, a))
                self.generic_visit(node)
        V().visit(tree); return found
    def segments(node):
        out = []
        if isinstance(node, ast.Constant) and isinstance(node.value, str): out.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str): out.append(v.value)
        elif isinstance(node, ast.BinOp): out += segments(node.left) + segments(node.right)
        return out
    msgs = []
    for v in json.load(open("mag/tests/model_manifest_cases_expected.json")).values():
        msgs += v.get("errors", [])
    msgs += ["Edition cover must be a mapping","Edition tail_art_fit must be cover or contain",
             "Edition closing_plates must be a list",
             "Article a1 requires a non-empty opener_art mapping for format.article_opener illustrated_paper_spots_v1"]
    all_sites = sites_of("src/magazine/manifest.py") + sites_of("src/magazine/io.py")
    cov, unc, dyn = [], [], []
    for path, lineno, node in all_sites:
        segs = [s.strip() for s in segments(node) if len(s.strip()) >= 8]
        if not segs: dyn.append((path, lineno)); continue
        probe = max(segs, key=len)
        (cov if any(probe in m for m in msgs) else unc).append((path, lineno, probe))
    print(f"raise sites: {len(all_sites)} | covered {len(cov)} | uncovered {len(unc)} | aggregate-raise {len(dyn)}")
    for p,l,probe in unc: print(f"  UNCOVERED {p.split('/')[-1]}:{l} {probe[:70]!r}")
    PY

### 7. Repo gate

    cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test

### 7. Rework: the discriminating proof for the `py_repr` fix

Regenerating the oracle (clause 5, unchanged) must be purely additive
against the committed file:

    git diff --numstat mag/tests/model_manifest_cases_expected.json
    # expect: 29	0   (five new entries, no pre-existing case altered)

Confirm the five new cases carry the intended codepoints on the Python side
before trusting any comparison:

    uv run python -c '
    import yaml
    from pathlib import Path
    for c in yaml.safe_load(Path("mag/tests/model_manifest_fixtures/cases.yaml").read_text()):
        if not c["name"].startswith("nonprintable"): continue
        for k, v in (c.get("records") or {}).items():
            print(c["name"], "record title", [hex(ord(x)) for x in v["title"] if ord(x) < 32 or ord(x) > 126])
        for name, content in (c.get("files") or {}).items():
            inner = yaml.safe_load(content)
            if not isinstance(inner, dict): continue
            for key in ("id", "language"):
                if isinstance(inner.get(key), str):
                    print(c["name"], key, [hex(ord(x)) for x in inner[key]])
            for s in inner.get("sections") or []:
                if isinstance(s, dict) and isinstance(s.get("kind"), str):
                    print(c["name"], "section kind", [hex(ord(x)) for x in s["kind"]])
    '
    # expect 0x200b (edition id), 0x7 (section kind), 0x1b and 0xf0000
    # (record titles), 0x200b (translation language)

The fix is discriminating in both directions. Revert the two escaping arms
of `py_repr` in `mag/src/model/manifest.rs`, leaving `printable`,
`nonprintable` and `escape` present but unused (add `#[allow(dead_code)]` to
each so `-D warnings` does not mask the result), then:

    cd mag && cargo test --test model_manifest 2>&1 | grep -E "diverge|nonprintable|test result"
    # expect: 5 cases diverge, naming exactly the five nonprintable_* cases,
    # and NO other case. Restore the arms and expect 4 passed.

That the other 74 cases pass in both states is the rejection's diagnosis
confirmed rather than merely accepted.

### 8. Rework 2: the cross-copy agreement test

`py_repr_copies_agree` in `mag/tests/model_manifest.rs` drives one shared
case list through a public refusal in each module and asserts the escaped
renderings are identical. Both refusals repr their argument before touching
the filesystem, so the test is pure and needs no fixture root:

    cd mag && cargo test --test model_manifest py_repr_copies_agree
    # expect: 1 passed

It discriminates in both directions. Perturb the copy in
`mag/src/model/manifest.rs` and rerun:

    # A: revert the two escaping arms of py_repr to the pre-fix body
    #    (replace the printable/escape arms with `other => out.push(other),`)
    # expect: FAILED, naming "zero\u{200b}width"

    # B: drop the astral branch of escape()
    #    (fold `point < 0x10000` and the else arm into one \u branch)
    # expect: FAILED, naming "astral\u{f0000}stop"

    # restore manifest.rs and expect: 1 passed

Both perturbations were run and both failed as stated, each naming exactly
the case that distinguishes it.

## Tool versions

    python 3.12.11, pyyaml 6.0.3, uv 0.8.17, rustc 1.96.0, jq 1.8.1

No crates were added. `serde_yaml`, `serde_json` and `regex` were already
dependencies; `mag/Cargo.toml` and `mag/Cargo.lock` are untouched.

## Metrics

Edition 010 oracle, clause 4:

| quantity | value |
|---|---|
| articles compared | 9 |
| content modes | 7 `article`, 2 `verbatim` |
| page caps | 7 for `article`, 10 for `verbatim` |
| `maximum_article_pages` | 7 (no `format.max_article_pages` in 010) |
| `maximum_editorial_pages` | 2 (no `format.max_editorial_pages` in 010) |
| oracle bytes compared | 12,926 |
| result | EQUAL |

Clause 3 chains the oracle to the shipped artifact: the subset extracted from
`editions/010/render-2026-09-14T01-47-59/en/edition-manifest.json` with the
plan's `jq -S` filter is IDENTICAL to the subset from a fresh Python load, and
the no-null sanity check passes. So the comparison runs
Rust port == Python loader == real rendered manifest, not merely against a
convenient re-derivation.

Case suite:

| quantity | value |
|---|---|
| cases | 79 (66 base path, 13 translation) |
| cases loading successfully | 5 |
| cases refusing | 71 |
| distinct error messages compared | 131 |
| cases where Python crashes | 3 |
| non-printable cases (rework) | 5 |

Of the 79, five were added by the rework and are the only ones carrying a
non-printable character; before them the corpus held none, which is why the
stale `py_repr` survived the first submission. They raise the refusing count
from 66 to 71 and the compared messages from 122 to 131.

Refusal-site coverage, clause 6:

| quantity | value |
|---|---|
| raise sites in `manifest.py` | 87 |
| raise sites in `io.py` reachable from the loader | 4 |
| covered by fixture | 89 |
| uncovered | 0 |
| aggregate `raise ValidationError(errors)` | 2 (`manifest.py:158`, `:702`) |

The 2 aggregate raises carry no literal text of their own; every refusing
case exercises them.

Port size: `mag/src/model/manifest.rs` 2,255 lines against `manifest.py`
1,269. `load_translation` is ported in full, not only the parity-relevant
base path, because `manifest.py` is deleted at WP-6.1 and a partial port
would silently break Spanish editions.

## Verdicts

- `edition_010_matches_the_python_loader`: PASS with real inputs, and FAILS
  on the perturbed oracle (one page cap changed from 10 to 7), so the check
  is not vacuous.
- `cases_match_the_python_loader`: PASS, 76 of 79 cases compared field for
  field. Two cases are compared by prefix (see Residuals) and three are
  handled by the crash test. Reverting the rework's `py_repr` escaping makes
  exactly the five `nonprintable_*` cases diverge and no others.
- `python_crashes_are_reported_as_validation_errors`: PASS. Asserts the exact
  diagnosis list the port produces where Python dies.
- `the_oracle_is_not_vacuous`: PASS. Altering one article title in the
  expectation makes the comparison fail.
- `py_repr_copies_agree`: PASS, seven cases. Reverting the escaping arms of
  the `manifest.rs` copy fails it naming `zero\u{200b}width`; dropping the
  astral branch of `escape` fails it naming `astral\u{f0000}stop`. Both
  perturbations were run, and the test returns to green on restore.
- `cargo test`: 88 tests pass across the suite (87 before this rework, plus
  `py_repr_copies_agree`). `cargo fmt --check` and `cargo clippy
  --all-targets -- -D warnings` clean.

## Residuals

**1. A pre-existing Python crash the port deliberately does not reproduce
(needs a plan decision).** `_check_unique_art` (`manifest.py:615-641`) runs
after the validator has already recorded shape errors but before they are
raised, and it trusts shapes the validator has just rejected:

| input | site | Python |
|---|---|---|
| `cover:` a non-mapping truthy value | `manifest.py:617` | `AttributeError: 'str' object has no attribute 'get'` |
| `opener_art:` a non-mapping truthy value | `manifest.py:623` | `AttributeError: 'str' object has no attribute 'get'` |
| `closing_plates:` a non-iterable truthy value | `manifest.py:629` | `TypeError` |

The crash destroys diagnoses Python had already accumulated. For
`cover: text` it had recorded `Edition cover must be a mapping`, and loses
it. The port returns those diagnoses instead of panicking, which the crash
test asserts exactly. This is a divergence on invalid input, recorded rather
than absorbed: exact-message equality is impossible for these three inputs
until `manifest.py` guards the three `or {}` / `or []` sites with an
`isinstance` check. That is a one-line-per-site change to `src/magazine/`,
which no WP owns, so it needs a sanctioned-oracle-change assignment in the
shape of WP-0.0b / WP-0.0c / WP-1.5. Until then the port is strictly better
behaved and the difference is pinned by fixture.

**2. Two messages embed a third-party parser's diagnostic and cannot match.**
`io.py`'s `Cannot read {path}: {exc}` and `manifest.py`'s
`Cannot parse editorial frontmatter {path}: {exc}` interpolate the YAML
parser's own error text, and PyYAML's wording differs from serde_yaml's:

    PyYAML     while scanning a quoted scalar\n  in "<unicode string>", line 2, column 8: ...
    serde_yaml found unexpected end of stream at line 3 column 1, while scanning a quoted scalar at line 2 column 8

Cases `manifest_unparseable` and `editorial_frontmatter_unparseable` are
therefore compared by shared prefix: same error count, same ordering, and
the messages must agree up to and including the `": "` that precedes the
foreign text, with the file path inside the agreeing part. Everything the
port itself authors is compared exactly. This mirrors WP-5.1b's precedent for
`load_records`'s filesystem-order-dependent message.

**3. `ValidationError` is reused, not duplicated.** `manifest.rs` imports it
from `super::records`, so there is one type (option (a) of the brief).
`py_repr` cannot be reused the same way: it is private in `records.rs`, which
this WP does not own, so `manifest.rs` carries a private copy.

That copy was the defect this rework exists to fix. As first submitted it was
the PRE-FIX body: it lacked the `printable` predicate and the `escape`
helper, so every non-printable character was emitted raw, and 5 of 7 probes
diverged from Python. The corrected body existed in the tree when the copy
was made (WP-5.1b's fix `b39ccf3` is an ancestor of `4120821`), so the copy
was stale rather than independently written. It now carries `printable`,
`nonprintable` and `escape` with the same bodies as `records.rs`, and the
five fixtures in clause 9 below compare them against Python.

Recommended follow-up, unchanged and now with a demonstrated defect behind
it rather than tidiness: lift `ValidationError`, `py_repr` and the `io.py`
helpers (`load_structured`, `safe_project_path`) into a shared module. That
edit spans files owned by WP-5.1b and WP-5.1c, so it belongs to whichever WP
next legitimately owns both, or to WP-6.1.

**3b. Stale-copy audit.** Every function name defined in both
`records.rs` and `manifest.rs`, and every helper `manifest.rs` ports from a
Python module that `records.rs` also draws on:

| helper | status |
|---|---|
| `py_repr` | WAS STALE, fixed by this rework; bodies now agree, fixtures added |
| `printable`, `nonprintable`, `escape` | were ABSENT from `manifest.rs`, which is what made `py_repr` stale; added with bodies identical to `records.rs` |
| `truthy` | duplicated NAME only, not a copy: `records.rs:429` takes `Option<&String>` and tests emptiness; `manifest.rs:2153` takes `Option<&Value>` and implements Python truthiness over every YAML type. Different signatures, different domains, both correct for their own |
| `load_structured` | ported from `io.py`; single copy in the Rust tree, `records.rs` has none. Not duplicated |
| `safe_project_path` | ported from `io.py`; single copy, `records.rs` has none. `records.rs:793 unsafe_path` is a different function (media_schema path validation), not a variant of this one |

Method: `grep -oP '^(pub )?fn \K\w+'` over both files, `comm -12` on the
sorted name lists, which yields exactly `py_repr` and `truthy`; then each
`io.py` helper checked against `src/magazine/io.py` and against `records.rs`
for a second copy. No third stale copy exists.

**4. Branches edition 010 alone would have missed.** The 010 comparison
exercises 9 `article`/`verbatim` rows in an illustrated-opener edition with a
cover, figures, no editorial, no sections, no closing plates, no extracts, no
key_ideas and no translation. Everything else is fixture-covered only:
`in_a_nutshell` content mode, all invalid content modes, editorial loading
and its three refusals, section loading and all four refusals, closing plates
and all four refusals, the art-repetition check, `tail_art_fit`, key_ideas
and its budget, the verbatim title rule, path escape and missing-file
handling, every header refusal, and the ENTIRE translation path (41 of the 87
raise sites). Had this WP scored only on 010, 0 of those would have been
tested, which is the WP-5.1a failure mode repeating.

**5. Semantics deliberately approximated, with the exact divergence class.**
- `casefold()` is implemented as Rust `to_lowercase()`. These differ for a
  handful of characters, notably German sharp s (Python folds to `ss`). It
  affects house-byline matching, the `display_emphasis`/`short_title`
  containment checks, `colophon` detection and closing-plate title
  uniqueness. No 010 content is affected.
- `str.strip()` is implemented as Rust `trim()`. Python also strips
  U+001C-U+001F, which Rust's `char::is_whitespace` does not, the same class
  WP-5.1a's verifier recorded for `doc.rs`.
- Python `.resolve()` resolves symlinks; the port normalizes lexically. The
  repository contains no symlinked edition paths.

**6. `EDITOR_VOICE_CONTENT_MODES` was not ported.** It is defined at
`manifest.py:35` and referenced nowhere in the repository. Porting dead
constants into a module whose original is about to be deleted adds lines
without a consumer.

**7. `mag/src/model.rs` now registers three modules.** The binary carries
`#[allow(dead_code)] mod model;` from WP-5.1a because nothing in `mag`
consumes the model yet; that still holds. The test includes the three module
files as siblings (`#[path = "../src/model/<name>.rs"]`) rather than through
`model.rs`, because child modules do not resolve through a `#[path]`-ed
parent; `manifest.rs` reaches its siblings by `super::`, which is correct in
both the binary tree and the test tree.

**8. Rework: the non-printable fixtures.** The rejection noted that the
74-case corpus contained zero non-printable characters, which is why no test
caught the stale `py_repr`. Five cases now drive non-printables through
distinct `py_repr` call sites, chosen so the character reaches the repr
because the value is wrong:

| case | character | call site | Python message |
|---|---|---|---|
| `nonprintable_edition_id` | U+200B (Cf) | `:222` `repr_option` + `:223` `py_repr(edition_id)` | `Edition id '010​' does not match directory '010'` |
| `nonprintable_section_kind` | U+0007 (Cc) | `:839` `py_repr(&kind)` | `Section 1 has unknown kind 'glossary\x07'; ...` |
| `nonprintable_verbatim_title` | U+001B (Cc) | `:770` `py_repr(&record.title)` | `Article a1 verbatim title must stay the captured source title 'Captured\x1bTitle'` |
| `nonprintable_astral_verbatim_title` | U+F0000 (Co) | `:770` | `... 'Captured\U000f0000Title'` |
| `nonprintable_translation_language` | U+200B (Cf) | `:1115` `repr_option` + `:1116` `py_repr(language)` | `Translation language 'es​' does not match directory 'es'` |

The set exercises all three escape widths Python chooses between: `\xNN`
(BEL, ESC), `\uNNNN` (ZWSP) and `\UNNNNNNNN` (U+F0000). The astral case
matters because it is the only one that reaches the `point >= 0x10000` branch
of `escape`.

The characters are carried as YAML double-quoted escapes inside each case's
`files` block scalar, so `cases.yaml` stays ASCII and the inner
`edition.yaml` is what holds the non-printable after the loader parses it.
Both parsers were checked to agree on the codepoints before the oracle was
regenerated.

Regenerating the oracle with the command in `## Commands` clause 5 is purely
additive: `git diff --numstat` reports `29 0`, so the pre-existing 74 cases
regenerate byte-for-byte and only the five new entries appear.

**9. The fix is discriminating, proven in both directions.** With the
`printable`/`escape` arms reverted in place and the three helpers left
present but unused, `cases_match_the_python_loader` fails with exactly
`5 cases diverge`, naming all five new cases and no others. Restoring the
arms returns the suite to green. That the other 74 cases pass in BOTH states
is the rejection's diagnosis confirmed: the old corpus could not see this
defect class at all.

**10. Compliance with revision 11's deliberate-divergence limits.** The plan
gained a Phase 5 policy after this WP was first submitted; both divergences
here satisfy all four limits. Note this clause addresses the
deliberate-divergence rule only; revision 12's separate requirement that a
forced helper copy carry a test asserting the two copies agree is clause 11,
and its absence was the sole ground for the second rejection.

| limit | the `_check_unique_art` crash divergence | the foreign-parser prefix divergence |
|---|---|---|
| only toward MORE diagnosis, never more permissive | the port still REFUSES all three inputs, returning the diagnoses Python accumulated and then discarded; nothing Python rejects is accepted | both sides refuse; only PyYAML's own wording is outside the compared region |
| every diverging input enumerated with both behaviors, covered by a test | the three cases are named in `PYTHON_CRASHES`, and `python_crashes_are_reported_as_validation_errors` asserts BOTH that Python recorded an `AttributeError`/`TypeError` and the exact recovered list | the two cases are named in `PARSER_DIAGNOSTIC_CASES` and compared by `compare_parser_diagnostics`, which checks count, ordering and the shared prefix |
| the oracle stays exact for every input Python handles without crashing | the other 76 cases compare whole JSON values exactly | the message template and the interpolated path stay inside the compared prefix, which must end with `": "` and contain `<ROOT>` |
| fixing the Python is available but not preferred | recorded: it needs a sanctioned oracle-change WP for a module deleted at WP-6.1, and a traceback is not a message, so exact equality is untestable either way | not applicable: the divergence is PyYAML's wording, not a crash |

**11. The forced copy carries a cross-copy agreement test.** Revision 12's
Phase 5 preamble requires a forced helper copy to "add a test asserting the
two copies agree on a shared case list". Copying `py_repr` was forced, since
it is private in `records.rs` and this WP does not own that file, and making
it public is not this WP's to do. `py_repr_copies_agree` closes the window
the rejection identified: a future change to the `records.rs` original would
otherwise leave this copy stale with `cargo test` green.

The shared list is seven cases, chosen to reach every branch of both the
quote selection and the escape width: a plain ASCII string; `caf\u{e9}`, a
non-ASCII printable that must stay raw; `\u{200b}` (Cf, the `\uNNNN` width);
`\u{7}` and `\u{1b}` (Cc, the `\xNN` width); `\u{f0000}` (Co, the only case
reaching the `\UNNNNNNNN` eight-hex branch); and a string containing both an
apostrophe and a double quote, which exercises the quote-selection branch.

Each case is driven through one public refusal per module, both of which
repr their argument before any filesystem access:

| module | entry point | refusal message |
|---|---|---|
| `manifest` | `load_translation(root, base, language)` against a root with no translation manifest | `Required {repr} translation manifest not found: {path}` |
| `records` | `localize_figures(&[], Some(&rows), "a1", manuscript, language)` with an empty English base and non-absent rows | `Translation {repr} article a1 has figures absent from English` |

The escaped form is extracted from each message by its surrounding literal
text and the two are compared. The test therefore exercises the copies as
they are actually reached in production rather than by calling the private
helper directly, and it needed no visibility change in `records.rs`.

**Rework residual: a name-based duplicate audit is not sufficient in
principle.** The verifier redid clause 3b's audit structurally, over
normalised function bodies rather than function names, and confirmed its
conclusion while noting the method's limit: a behavior duplicated under two
different names would escape a name-based comparison. Three cross-name pairs
scored high structurally and are all false positives: `slashes` and
`nonprintable` share only the `OnceLock<Regex>` idiom with different
patterns; `is_absent` and `blank_header_field` differ genuinely, the latter
also treating an empty string as blank; `mapping_get` and `insert` are noise
on two-line bodies. No second stale copy exists. WP-5.1d's duplicate-helper
audit clause should therefore be written structurally rather than by name.

**Rework residual: duplicated helpers are a demonstrated defect source.**
`py_repr` was fixed in `records.rs` and then reintroduced stale in
`manifest.rs`, in the module that actually validates `edition.yaml` and so
sees hand-authored text most often. The shared-module consolidation
(`ValidationError`, `py_repr` with `printable`/`nonprintable`/`escape`, and
`io.py`'s `load_structured`/`safe_project_path`) is no longer a tidiness
item; until it happens, any WP copying a helper between model modules must
diff it against its source and say so in evidence. The audit table in
clause 3b is the form that check should take.

**Rework residual: a uniformly well-formed corpus proves less than its case
count suggests.** 74 cases and 122 compared messages did not catch a defect
that 5 cases and 9 messages caught immediately, because the corpus contained
no non-printable character anywhere. This is the third instance of the
pattern (WP-5.1a's padded containers absent from 010, WP-5.1b's explicit
port and non-printables absent from `library/sources/`). The remaining
Phase 5 ports should treat "which inputs does my corpus structurally lack"
as a required question rather than an afterthought.

## Status

done

The port is complete, the 010 loader-owned subset matches the Python loader
and the real rendered manifest exactly, and every reachable refusal site is
covered by fixture. The forced `py_repr` copy now carries the cross-copy
agreement test revision 12 requires (clause 11), proven to fail in both
directions. Residual 1 is a finding about `src/magazine/`, not an unfinished
part of this WP: it is pinned by three fixtures and an exact assertion, and
it needs an owner for the one-line oracle fix.
