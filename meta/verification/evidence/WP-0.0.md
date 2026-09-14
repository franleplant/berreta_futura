# WP-0.0 render determinism switches

## Base

e127cb0de2fc371d63b76d18f41baf230c2bcb12

## Commands

All commands run from the repo root.

Build, lint, test:

    cargo fmt --manifest-path mag/Cargo.toml --check
    cargo clippy --manifest-path mag/Cargo.toml --all-targets -- -D warnings
    cargo test --manifest-path mag/Cargo.toml

Fixture clause (one unresolvable anchor fails under --no-model naming the
figure). The fixture is scratch, created inline and removed after:

    mkdir -p editions/zz-wp00fx/run-fx/articles/a1
    printf 'id: zz-wp00fx\nlanguage: en\narticles:\n  - id: a1\n    manuscript: does-not-matter.md\n    figures:\n      - id: fig-x\n        source_id: none\n        path: media/none.png\n        caption: fixture\n        alt_text: fixture\n        anchor: Missing Heading\n' > editions/zz-wp00fx/edition.yaml
    printf '## Real Heading\n\nbody text\n' > editions/zz-wp00fx/run-fx/articles/a1/final.md
    cargo run -q --manifest-path mag/Cargo.toml -- render zz-wp00fx --run editions/zz-wp00fx/run-fx --no-model
    mv editions/zz-wp00fx <scratch>/zz-wp00fx-removed

Expected: exit 1; stderr contains
`--no-model: 1 figure anchor(s) need model patching:` and
`a1:fig-x (anchor 'Missing Heading')`; no render-* directory is created
under editions/zz-wp00fx.

010 identity clause (renders identically with and without the flag):

    cargo run -q --manifest-path mag/Cargo.toml -- render 010 --run editions/010/run-2026-09-13T01-34-51 --no-model
    cargo run -q --manifest-path mag/Cargo.toml -- render 010 --run editions/010/run-2026-09-13T01-34-51

Both print `pending anchors: 0` and exit 0. With A and B the two render
output directories:

    for p in reader.pdf booklet-a4.pdf booklet-a4-interior.pdf booklet-a4-cover.pdf; do
      cmp <(pdftotext "$A/en/$p" -) <(pdftotext "$B/en/$p" -)
      cmp <(pdfinfo -box "$A/en/$p" | grep -E "Box|Pages") <(pdfinfo -box "$B/en/$p" | grep -E "Box|Pages")
    done
    cmp $A/request.json $B/request.json
    cmp $A/en/edition-manifest.json $B/en/edition-manifest.json

render-critic.json and preflight.json are compared field by field with this
inline script; every differing leaf must end in `_sha256` or be a `.path`
leaf whose value contains `mag-engine-render-stage-`:

    python3 - "$A" "$B" <<'EOF'
    import json, sys
    a_root, b_root = sys.argv[1], sys.argv[2]
    def leaves(o, p=""):
        if isinstance(o, dict):
            for k, v in o.items(): yield from leaves(v, f"{p}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o): yield from leaves(v, f"{p}[{i}]")
        else: yield p, o
    for j in ["en/render-critic.json", "en/preflight.json"]:
        a = dict(leaves(json.load(open(f"{a_root}/{j}"))))
        b = dict(leaves(json.load(open(f"{b_root}/{j}"))))
        assert a.keys() == b.keys()
        diffs = [k for k in a if a[k] != b[k]]
        bad = [k for k in diffs if not (k.endswith("_sha256") or (k.endswith(".path") and "mag-engine-render-stage-" in str(a[k])))]
        print(j, "differing:", len(diffs), "outside whitelist shape:", bad)
    EOF

Expected: `bad` empty for both files.

## Tool versions

- rustc 1.96.0 (ac68faa20 2026-05-25)
- cargo 1.96.0 (30a34c682 2026-05-25)
- poppler (pdftotext/pdfinfo) 25.08.0
- uv 0.8.17 / uv-managed Python 3.12.11
- weasyprint 69.0 (uv.lock)

## Metrics

- Fixture render under --no-model: exit 1, names `a1:fig-x (anchor
  'Missing Heading')`, no render dir created.
- 010 renders: A = editions/010/render-2026-09-14T01-32-52 (--no-model),
  B = editions/010/render-2026-09-14T01-33-59 (without). Both report
  `pending anchors: 0`, so edition 010 has zero pending figure anchors and
  neither render invoked the model.
- pdftotext dumps: byte-identical for all four PDFs.
- pdfinfo boxes and page counts: identical for all four PDFs.
- request.json, edition-manifest.json: byte-identical.
- render-critic.json: 2 differing leaves, both `*_sha256` of PDF bytes
  (PDF byte-determinism is not assumed).
- preflight.json: 4 differing leaves, all `.path` values under the
  per-render scratch stage root `mag-engine-render-stage-*`.

## Verdicts

None (no parity verdict.json exists yet; the comparator arrives in
WP-0.2a).

## Residuals

- Run-to-run noise found, for WP-0.1's `normalization.strip_pdf_keys`
  whitelist: `*_sha256` leaves in render-critic.json (hashes of PDF
  bytes), `.path` leaves in preflight.json under the scratch stage root.
- When a render uses committed edition files (no content run),
  patch_anchors is not invoked, so no pending-anchor count is printed and
  --no-model has nothing to refuse; parity renders always pass --run per
  the plan, so this branch is out of the flag's scope. Behavior of that
  branch is unchanged.

## Status

done
