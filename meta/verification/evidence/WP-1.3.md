# WP-1.3 hyphenation measurement and recommendation

## Base

0bd7cc0e6ab2a4dc74caec6c89bf0155afe07b30 (feat(parity): WP-0.2d fault suite,
raster bound and critic tolerances)

Phase 1 spike: all instrumentation was uncommitted and is stashed away at WP
end; this evidence file is the only committed artifact.

## Commands

Run from a clean worktree at the base commit. The run directory is untracked
and must be copied in.

```
git worktree add /tmp/spike-wp13 0bd7cc0
cd /tmp/spike-wp13
cp -R <repo>/editions/010/run-2026-09-13T01-34-51 editions/010/
(cd mag && cargo build)
```

Instrumentation (uncommitted). In `src/magazine/weasyprint_adapter.py`, add a
call after the existing ladder report at the `_report_hyphen_ladders(document,
edition)` line:

```
    _report_hyphen_ladders(document, edition)
    _dump_prose_lines(document)
```

and define, immediately above `_report_hyphen_ladders`:

```python
def _dump_prose_lines(document: Any) -> None:
    import json
    import os

    target = os.environ.get("MAG_HYPHEN_DUMP")
    if not target:
        return
    blocks: dict[str, dict[str, Any]] = {}
    for page_number, page in enumerate(document.pages, start=1):
        for box in _walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            key = getattr(element, "attrib", {}).get(_RUNT_KEY) if element is not None else None
            if key is None or type(box).__name__ != "BlockBox":
                continue
            entry = blocks.setdefault(
                key,
                {
                    "hyphens": str(box.style["hyphens"]),
                    "character": str(box.style["hyphenate_character"]),
                    "lines": [],
                },
            )
            entry["lines"].extend(
                {"text": _box_text(line), "page": page_number, "width": float(line.width)}
                for line in _walk_boxes(box)
                if type(line).__name__ == "LineBox"
            )
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(blocks, handle, ensure_ascii=False, sort_keys=True, indent=1)
```

Baseline render, hyphenation on (the shipping configuration):

```
MAG_HYPHEN_DUMP=/tmp/hyph-on.json ./mag/target/debug/mag render 010 \
  --no-model --run editions/010/run-2026-09-13T01-34-51 2>/tmp/render-on.err
```

The hyphenation-off switch. `src/magazine/assets/weasyprint-a5.css` line 639 is
the only live `hyphens: auto` declaration in the stylesheet (lines 645, 652 and
655 are already `manual` carve-outs; line 565 is comment prose):

```
sed -i '' '639s/  hyphens: auto;/  hyphens: manual;/' src/magazine/assets/weasyprint-a5.css
grep -n "hyphens:" src/magazine/assets/weasyprint-a5.css
MAG_HYPHEN_DUMP=/tmp/hyph-off.json ./mag/target/debug/mag render 010 \
  --no-model --run editions/010/run-2026-09-13T01-34-51 2>/tmp/render-off.err
```

Measurement (the analysis script is reproduced in full below the metrics):

```
python3 analyze.py /tmp/hyph-on.json /tmp/hyph-off.json \
  <on-render>/en/edition-manifest.json <off-render>/en/edition-manifest.json
pdfinfo <on-render>/en/reader.pdf | grep Pages
pdfinfo <off-render>/en/reader.pdf | grep Pages
grep -c "hyphen ladder" /tmp/render-on.err /tmp/render-off.err
grep -i "cap" /tmp/render-on.err /tmp/render-off.err
./mag/target/debug/mag parity 010 --pre-rendered <on-render> <off-render>
```

## Tool versions

- python 3.9.6 (system, for the analysis script); the renderer runs under uv
- uv 0.8.17
- weasyprint 69.0
- pyphen 0.17.2
- poppler 25.08.0 (pdfinfo, and the comparator's pinned assertion)
- rustc 1.96.0

## Metrics

### Hyphenation incidence (edition 010, en)

Prose blocks are the stylesheet's own definition of prose: the blocks the
adapter stamps with `data-runt-key`, which are exactly the blocks the
`hyphens: auto` rule matches.

| measure | hyphens on | hyphens off |
|---|---|---|
| prose blocks | 155 | 155 |
| prose lines | 967 | 976 |
| lines ending in a hyphen | 141 | 15 |
| hyphen ladders (more than 2 consecutive) | 3 | 0 |

**Soft-hyphen breaks: 126** (141 minus the 15 lines that end in a real
compound hyphen and do so in both renders). They fall in **81 of 155 prose
blocks**. Hyphenation reclaims **9 prose lines** (976 to 967).

The three ladders, all reported by the adapter's existing audit, sit on reader
pages 19 (4 consecutive), 24 (3) and 38 (3). The audit reports zero on the
unhyphenated render, exactly as the stylesheet's comment predicts.

### Page-count changes per article

| article | on | off | cap |
|---|---|---|---|
| an-alignment-assessment-of-recent-cybersecurity | 6 | 6 | 7 |
| countering-misuse-of-ai-september-2026-anthropic | 3 | 3 | 7 |
| dario-amodei-we-must-pace-the-frontier | 13 | 13 | 10 |
| deepseek-v4-1-flash-pushing-the-limits-of-kv-cac | 4 | 4 | 7 |
| government-rails-site-hit-hours-after-cve-patch | 3 | 3 | 7 |
| rapidly-scaling-online-storage-to-serve-over-1-b | 4 | 4 | 7 |
| scenarios-for-our-economic-future | 4 | 4 | 7 |
| the-third-era-of-ai-software-development | 4 | 4 | 10 |
| towards-self-driving-codebases | 5 | 5 | 7 |

**Articles with a changed page count: 0.** Total reader pages: **56 both
ways** (pdfinfo, not engine-reported JSON).

### Page-cap violations

**Violations introduced by disabling hyphenation: 0.**

One violation exists and is identical in both renders: the Dario verbatim
article sets 13 pages against its cap of 10, and both renders emit the same
warning (`verbatim article past the page cap, rendering anyway`). It is a
pre-existing condition of edition 010, not a consequence of the switch.

### Changed line breaks

| measure | value |
|---|---|
| prose blocks whose line set changed | 83 of 155 |
| prose blocks whose line count changed | 9 |
| differing lines (including count deltas) | 428 |

Cross-checked mechanically with the accepted comparator, hyphens-on tree
against hyphens-off tree (`mag parity 010 --pre-rendered`, exit 1):

```
tier S page_count: pass (56 vs 56)
tier S boxes: pass (0 mismatches)
tier S text: fail (26 pages differ)
tier G: max dx 327.565 pt, max dy 367.871 pt, beyond G1 140, beyond G2 140, structure mismatches 88
tier S color: fail (36 pages differ)
tier S navigation: fail (10 mismatches)
tier E display list: fail (36 pages differ)
tier V: dims pass (mismatches 0), V1 fail, V2 fail, worst page fraction 0.180534, max channel delta 241
tier E raster: not_evaluated (WP-0.2d raster_bound derivation)
```

The two independent measurements agree: pagination and page geometry are
untouched, while roughly half the prose blocks and about a quarter to two
thirds of the interior pages change their setting.

### Analysis script

```python
import json
import sys

on_dump, off_dump, on_man, off_man = sys.argv[1:5]
with open(on_dump) as h:
    on = json.load(h)
with open(off_dump) as h:
    off = json.load(h)
with open(on_man) as h:
    mon = json.load(h)
with open(off_man) as h:
    moff = json.load(h)


def hyphen_ended(blocks):
    total = 0
    per_block = {}
    for key, entry in blocks.items():
        endings = (entry["character"], "-")
        n = sum(1 for line in entry["lines"] if line["text"].rstrip().endswith(endings))
        per_block[key] = n
        total += n
    return total, per_block


def line_count(blocks):
    return sum(len(entry["lines"]) for entry in blocks.values())


on_h, on_pb = hyphen_ended(on)
off_h, off_pb = hyphen_ended(off)
print(f"prose blocks: on {len(on)}, off {len(off)}")
print(f"prose lines: on {line_count(on)}, off {line_count(off)}")
print(f"hyphen-ended lines: on {on_h}, off {off_h}")
print(f"soft-hyphen breaks: {on_h - off_h}")
print(f"blocks with a hyphen break: {sum(1 for k, v in on_pb.items() if v > off_pb.get(k, 0))}")

shared = sorted(set(on) & set(off), key=int)
changed_blocks = changed_lines = count_changed = 0
for key in shared:
    a = [line["text"] for line in on[key]["lines"]]
    b = [line["text"] for line in off[key]["lines"]]
    if a != b:
        changed_blocks += 1
        changed_lines += sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))
    if len(a) != len(b):
        count_changed += 1
print(f"blocks whose line set changed: {changed_blocks}")
print(f"blocks whose line count changed: {count_changed}")
print(f"changed line breaks: {changed_lines}")

lon, loff = mon["layout"], moff["layout"]
pon, poff = lon.get("article_pages", {}), loff.get("article_pages", {})
caps = lon.get("article_page_caps", {})
diffs = 0
for key in sorted(set(pon) | set(poff)):
    a, b = pon.get(key), poff.get(key)
    diffs += a != b
    print(f"{key}: on={a} off={b} cap={caps.get(key)}")
print(f"articles with changed page count: {diffs}")
```

## Verdicts

`mag parity 010 --pre-rendered <hyphens-on> <hyphens-off>`, exit 1,
verdict.json sha256
`f163755ad648defac3ca329885eb316363a73b37fc5327077630e89f4b0c2d17`.
Tier summary as quoted under Changed line breaks: Tier S page_count and boxes
pass; Tier S text, color and navigation fail; Tier E display list fails; Tier
E raster is `not_evaluated` pending WP-0.2d's blocked derivation.

This verdict measures the hyphenation switch against itself on one engine. It
is not a parity verdict between engines and gates nothing.

## Residuals

- **The switch is global, and Spanish pays more than English.** The
  stylesheet's comment records that without hyphenation the same manuscripts
  set about four pages longer in Spanish (edition 003 measured en 36 / es 40)
  and that es article 3 sat exactly on the seven-page cap with hyphenation on.
  Translations are out of parity scope, but a `hyphens: manual` switch landed
  by WP-1.5 applies to every language, so any Spanish edition rendered between
  WP-1.5 and WP-4.3 would set longer and could breach a cap. A mitigation
  exists and is cheap: scope the parity switch to English (the `html lang`
  attribute is already set per language by `html_edition.py`, so a
  `:lang(en)` qualifier or an en-only override confines it). This is a
  decision for WP-1.5, not for this spike.
- The 15 hyphen-ended lines present in both renders are real compound hyphens
  ending a line naturally; they are not hyphenation and are excluded from the
  126.
- `_box_text` joins a line's text boxes; a line whose break falls inside an
  inline element still reports its full text, so the line-set comparison is
  over rendered line content, not over break opportunities.
- Both renders emitted `pending anchors: 0`, so neither leg called a model.
- The analysis uses the adapter's laid-out line boxes rather than extracted
  PDF text, so it is unaffected by `pdftotext` reading order.

## Status

`awaiting-fran`.

**Recommendation: option (b), disable hyphenation in both engines for the
parity phase, re-enabling native hyphenation post-flip via WP-4.3.**

The measured cost of (b) is zero on both metrics the plan defines as
negligible: zero page-count changes across all nine articles, and zero cap
violations introduced (the one violation present is pre-existing and identical
in both renders). The edition is 56 pages either way, and the adapter's ladder
audit goes quiet rather than reporting anything new.

The measured cost of (a) is the reason to avoid it: hyphenation decides 126
breaks across 81 of 155 prose blocks, and toggling it changes the setting of
26 pages of text and 88 Tier G structure groups. Under (a) every one of those
126 decisions must be reproduced exactly by a Rust port of Pyphen's Liang
pattern matching plus WeasyPrint's `hyphenate-limit-chars 6 3 3` application,
and any single mismatch surfaces as a Tier E failure. That port is also
throwaway work: the post-flip design wants Typst's native hypher, not
injected soft hyphens, so (a) buys a large new correctness surface for a
mechanism that is discarded at the flip.

Consequences, stated for each option as required:

- If Fran chooses **(b)**: WP-1.5 lands the CSS switch in the oracle (and
  should decide the language scoping noted in Residuals), both parity legs run
  unhyphenated, and **WP-4.3 becomes mandatory** as the measurement of the
  shipped design's deliberate divergence. The honest weakness: Tier E equality
  is then proven against a configuration that does not ship, and the shipping
  configuration is covered by WP-4.3's page-count and cap checks rather than
  by display-list equality.
- If Fran chooses **(a)**: WP-1.5 records the decision only, WP-2.1 injects
  soft hyphens into both engines' input, and Pyphen's en dictionary lookup is
  ported to Rust. Parity is then proven against the configuration that
  actually ships, at the cost of that port's fidelity being on the critical
  path for 126 breaks per edition.
