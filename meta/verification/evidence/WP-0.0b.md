# WP-0.0b manifest amendment (sanctioned oracle change)

## Base

06bc76410437d4546d96f6fa3dcce27bb68a2fc7

## Commands

All commands run from the repo root. The 010 run directory
`editions/010/run-2026-09-13T01-34-51` is untracked; a verifier replaying
from a fresh worktree must first copy it in:

    cp -R /Users/franguijarro/code/magazine/editions/010/run-2026-09-13T01-34-51 editions/010/

Lint:

    uvx ruff format --check src/magazine/engine_render_bridge.py
    uvx ruff check src/magazine/engine_render_bridge.py

Before/after renders (before = worktree at base, after = with this WP's
diff; each prints its own out dir, substituted as $A and $B below):

    cargo run -q --manifest-path mag/Cargo.toml -- render 010 --run editions/010/run-2026-09-13T01-34-51 --no-model

Manifest diff is exactly the two new keys (prints new/removed/changed leaf
paths; expected: new keys all under `.layout.toc.`, nothing removed or
changed; `layout.article_opener_fits` is present in $B and empty, so it
contributes no leaf):

    python3 - "$A" "$B" <<'EOF'
    import json, sys
    a, b = (json.load(open(f"{r}/en/edition-manifest.json")) for r in sys.argv[1:3])
    def leaves(o, p=""):
        if isinstance(o, dict):
            for k, v in o.items(): yield from leaves(v, f"{p}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o): yield from leaves(v, f"{p}[{i}]")
        else: yield p, o
    la, lb = dict(leaves(a)), dict(leaves(b))
    print("new:", sorted(set(lb) - set(la)))
    print("removed:", sorted(set(la) - set(lb)))
    print("changed:", sorted(k for k in set(la) & set(lb) if la[k] != lb[k]))
    print("keys:", sorted(set(b["layout"]) - set(a["layout"])))
    EOF

Expected `keys:` line: `['article_opener_fits', 'toc']`.

pdftotext dumps and pdfinfo boxes unchanged:

    for p in reader.pdf booklet-a4.pdf booklet-a4-interior.pdf booklet-a4-cover.pdf; do
      cmp <(pdftotext "$A/en/$p" -) <(pdftotext "$B/en/$p" -)
      cmp <(pdfinfo -box "$A/en/$p" | grep -E "Box|Pages") <(pdfinfo -box "$B/en/$p" | grep -E "Box|Pages")
    done
    cmp "$A/request.json" "$B/request.json"

Critic report and preflight unchanged modulo the run-to-run noise recorded
in WP-0.0 Residuals (leaves ending `_sha256`, and `.path` leaves containing
`mag-engine-render-stage-`); the script exits nonzero on any other diff:

    python3 - "$A" "$B" <<'EOF'
    import json, sys
    a_root, b_root = sys.argv[1], sys.argv[2]
    def leaves(o, p=""):
        if isinstance(o, dict):
            for k, v in o.items(): yield from leaves(v, f"{p}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o): yield from leaves(v, f"{p}[{i}]")
        else: yield p, o
    bad = []
    for j in ["en/render-critic.json", "en/preflight.json"]:
        a = dict(leaves(json.load(open(f"{a_root}/{j}"))))
        b = dict(leaves(json.load(open(f"{b_root}/{j}"))))
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                ok = k.endswith("_sha256") or (k.endswith(".path") and "mag-engine-render-stage-" in str(b.get(k, "")))
                if not ok: bad.append((j, k))
    print("critic result A/B:", json.load(open(f"{a_root}/en/render-critic.json"))["result"], json.load(open(f"{b_root}/en/render-critic.json"))["result"])
    sys.exit(1 if bad else 0)
    EOF

## Tool versions

- python 3.9.6 (system), uv 0.8.17, weasyprint 69.0 (via uv)
- poppler pdftotext/pdfinfo 25.08.0
- cargo/rustc 1.96.0

## Metrics

- Before render: editions/010/render-2026-09-14T01-40-18; after:
  editions/010/render-2026-09-14T01-41-32 (both untracked, left in place).
- Manifest leaf diff: 9 new `.layout.toc.*` entries (one per 010 article),
  0 removed, 0 changed; new key set exactly
  `['article_opener_fits', 'toc']`.
- `layout.toc` values (article id: reader page): government-rails 4,
  countering-misuse 7, alignment-assessment 11, dario-amodei 17,
  scenarios 31, third-era 36, self-driving 40, deepseek 46, rapidly-scaling
  50.
- `layout.article_opener_fits`: `{}` (see Residuals).
- Text dumps, boxes, request.json: byte-equal. Critic result pass/pass;
  only known-noise leaves differed (2 `_sha256`, 4 stage `.path`).

## Verdicts

No parity verdict.json exists yet (comparator lands in WP-0.2a); the
comparisons above stand in for it.

## Residuals

- `layout.article_opener_fits` is `{}` on full renders: the reader HTML
  emits `<header class="article-opener">` with no `data-article-id`
  (html_edition.py:393; the id sits on the parent `<article>`), and
  `_note_box` (weasyprint_adapter.py:2303) only notes opener pages when the
  header element itself carries `data-article-id`. So opener fits are empty
  in the bridge stdout rows too, and the plan's premise that they exist
  there today is not borne out by 010. The key is now carried faithfully,
  but WP-2.3's `article_opener_fits` comparison and WP-3.2's "opener-fit
  booleans exact" clause are vacuous ({} vs {}) until the adapter populates
  it, which is a `src/magazine/` behavioral change no current WP owns.
  Flagged to the orchestrator for a plan-level decision.

## Status

done
