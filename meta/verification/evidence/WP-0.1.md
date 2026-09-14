# WP-0.1 oracle determinism proof

## Base

8f9596d3f5c8592f45d5f7be0a4ae0e557ac206d

## Commands

From a worktree at this WP's commit, with the untracked run dir copied in
first:

```sh
cp -R /Users/franguijarro/code/magazine/editions/010/run-2026-09-13T01-34-51 editions/010/
cd mag && cargo build && cd ..
./mag/target/debug/mag render 010 --no-model --langs en --run editions/010/run-2026-09-13T01-34-51
./mag/target/debug/mag render 010 --no-model --langs en --run editions/010/run-2026-09-13T01-34-51
```

Each render prints `pending anchors: 0` and `out dir: editions/010/render-<ts>`.
With the two out dirs as `A` and `B`:

```sh
A=editions/010/render-<ts1> B=editions/010/render-<ts2>
for p in reader booklet-a4 booklet-a4-interior booklet-a4-cover; do
  cmp <(pdftotext -raw $A/en/$p.pdf -) <(pdftotext -raw $B/en/$p.pdf -) && echo "pdftotext $p identical"
  diff <(pdfinfo -box $A/en/$p.pdf | grep -v -E "CreationDate|ModDate|File size") \
       <(pdfinfo -box $B/en/$p.pdf | grep -v -E "CreationDate|ModDate|File size") && echo "pdfinfo $p identical"
done
for j in request.json en/edition-manifest.json en/preflight.json en/render-critic.json; do
  cmp -s $A/$j $B/$j && echo "$j byte-equal" || echo "$j differs"
done
python3 - "$A" "$B" <<'EOF'
import json, sys
def leaves(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items(): yield from leaves(v, f"{p}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from leaves(v, f"{p}[{i}]")
    else: yield p, o
a, b = sys.argv[1], sys.argv[2]
for j in ("en/preflight.json", "en/render-critic.json"):
    da = dict(leaves(json.load(open(f"{a}/{j}"))))
    db = dict(leaves(json.load(open(f"{b}/{j}"))))
    assert da.keys() == db.keys()
    for k in [k for k in da if da[k] != db[k]]: print(j, k)
EOF
```

Expected: every pdftotext and pdfinfo comparison identical; request.json and
edition-manifest.json byte-equal; the leaf diff prints exactly the six
whitelisted leaves below and nothing else.

Tool version measurement:

```sh
uv run python -c "from importlib.metadata import version; [print(p, version(p)) for p in ('weasyprint','pydyf','pyphen','pypdf','pygments','pillow')]"
uv run python --version; uv --version; pdftotext -v; rustc --version; sw_vers -productVersion
```

## Tool versions

python 3.12.11 (uv-managed venv), uv 0.8.17, weasyprint 69.0, pydyf 0.12.1,
pyphen 0.17.2, pypdf 6.14.2, pygments 2.21.0, pillow 12.3.0,
poppler 25.08.0 (pdftotext/pdftoppm/pdfinfo), rustc 1.96.0, macOS 26.6.2.
Recorded in `meta/verification/parity.yaml tools:`; mutool and typst crate
entries are pending their owning WPs (0.2b, 1.4/2.0a).

## Metrics

Two renders of edition 010 (en), same run dir
(`editions/010/run-2026-09-13T01-34-51`), both `--no-model`:
`render-2026-09-14T01-47-59` (A) and `render-2026-09-14T01-49-02` (B),
left in place for the verifier.

- pdftotext raw dumps: byte-identical for all four PDFs (reader, booklet-a4,
  booklet-a4-interior, booklet-a4-cover).
- pdfinfo boxes and metadata: identical excluding CreationDate/ModDate/File
  size.
- request.json, edition-manifest.json: byte-equal.
- preflight.json: exactly 4 differing leaves, all staged scratch paths under
  `/private/var/folders/.../mag-engine-render-stage-<rand>/`:
  `.cover_art.path`, `.figures[0].path`, `.figures[1].path`,
  `.figures[2].path`.
- render-critic.json: exactly 2 differing leaves, both PDF-byte hashes:
  `.visual_review.booklet_sha256`, `.visual_review.reader_sha256`. Critic
  result and every other leaf equal (pass/pass).
- SHA256SUMS: differs only in entries derived from PDF bytes
  (reader.pdf, booklet-a4.pdf, booklet-a4-interior.pdf) and from the two
  JSONs above; booklet-a4-cover.pdf is byte-stable run to run.
- Pending anchors: 0 on both renders (each printed `pending anchors: 0`;
  under `--no-model` a nonzero count aborts the render). No model call
  occurred; nothing to resolve, nothing committed for anchors.

The closed whitelist recorded as `normalization.strip_pdf_keys`: PDF-level
dates/trailer ID/Producer dates; the 4 preflight scratch-path leaves; the 2
render-critic PDF-hash leaves; SHA256SUMS/package.zip/web-output.zip as
derived-from-PDF-bytes artifacts never compared directly.

## Verdicts

No verdict.json exists yet (comparator lands in WP-0.2a). The determinism
verdict is the Metrics section above, reproducible via ## Commands.

## Residuals

- PDF files themselves are not byte-identical run to run (embedded dates and
  trailer ID), which is why SHA256SUMS and the packaged zips differ; this is
  exactly the noise the parity ladder's "never compared" clause covers.
- render-review PNGs, studio/, and web/ trees were not compared here (out of
  this WP's target); WP-5.5 owns web-tree equality.
- Bare `uv run python -c "import weasyprint"` fails outside the renderer's
  environment (libgobject dlopen); the renderer sets its own library path.
  Versions were read from importlib.metadata instead. Not a repo bug.

## Status

done
