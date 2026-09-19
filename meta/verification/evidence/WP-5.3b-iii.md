# WP-5.3b-iii the checks

## Base

`f7361c2` (`docs(plans): typst parity plan revision 68, the gate accepted and
69,071 retired`), branch `art_directed`. Built on `9acc797` in
`git worktree add --detach <scratch>/wp53biii art_directed` and REBASED FIVE
TIMES before landing, onto `f127381`, `389ad0b`, `a489d52`, `0cd65b2` and
`f7361c2` (the last after a refused CAS, answered by rebasing rather than
re-reading the tip),
because revisions 51 to 67, WP-5.4c, WP-2.2b, WP-0.2k's and WP-0.2i's
acceptances, WP-5.3b-ii's acceptance, WP-5.4b-ii, WP-5.5a and WP-5.1f/g's
acceptance landed while this WP ran, and two rate-limit kills sat between
them. The scratch worktree was deleted by the second kill; the commit
survived and was re-checked-out at a new path, and the one uncommitted edit
lost with it, this section and the two revision-67 paragraphs, was rewritten.

What each rebase could have moved was CHECKED rather than assumed, because the
critic reads its text from the tracer and the tracer is comparator territory:

- `9acc797` to `f127381`: `mag/src/parity.rs` gained 839 lines and
  `mag/src/model/shared.rs` 98, both upstream of this critic's text source,
  while `mag/src/critic/**`, `mag/src/impose.rs`, `mag/tests/rust_helpers.rs`
  and the Cargo files were untouched. The live oracle was therefore
  REGENERATED on the rebased tree and came back at the same sha256,
  `d7fdb44a...915c45`, so those tracer changes do not reach the critic's
  decisions on 010. Every number in `## Metrics` and every probe outcome was
  re-measured on that tree; nothing is carried over from the `9acc797` run.
- `f127381` to `f7361c2`: `git diff --stat` over `mag/src/critic`,
  `mag/src/model/shared.rs`, `mag/src/impose.rs`, `mag/src/parity*`,
  `mag/tests/rust_helpers.rs`, both Cargo files and
  `src/magazine/render_critic.py` is EMPTY at every step, so nothing this WP
  reads or ports changed. The intervening commits are plan revisions,
  `mag/src/typeset/**`, `mag/src/web/**`, `mag/src/cover/**`,
  `mag/tests/cover_*` and verify files. The live comparison (block 5, MODE
  full) was re-run at `a489d52` and passed; block 2 was re-run at `0cd65b2`
  before landing, and `0cd65b2` to `f7361c2` is one plan-document commit, so
  the gate re-run there was fmt, clippy, nocomments and this WP's own suite. The 49 fixture probes and the live probes were last run at
  `389ad0b`, and the empty diff over everything they exercise is why they were
  not run again. That scope decision is recorded here rather than left
  implicit.

## What was built

`mag/src/critic/rules.rs` (2073 lines) ports, from
`src/magazine/render_critic.py`:

- **Void geometry**: `_annotate_void_geometry` (:1222) as
  `annotate_void_geometry`, `_largest_empty_rectangle` (:1355) as
  `largest_empty_rectangle`, the live-area union over body pages, the
  `VOID_REPORT_LIMIT` loop with its mask-out step, and the height/width-fraction
  filter.
- **Tail bands**: `_locate_tail_band` (:1300), `_abuts_tail_band` (:1344),
  `_printed_tail_bands` (:272).
- **Opener offset colour detection**: `_opener_frame_bbox` (:1050) as
  `opener_frame_bbox`, `_inspect_opener_offset` (:1137).
- **Crop fidelity**: `_inspect_opener_crop_fidelity` (:1082), and the crop
  pipeline it consumes because a fidelity row cannot exist without it:
  `_figure_crop_regions` (:1420), `_review_crop_plan` (:1445),
  `_write_review_crops` (:1510), `_render_crop_page` (:1568).
- **The 31 issue sites**: `_issue_recorder` (:123), `_imposition_checks` (:133,
  11 sites), `_opener_offset_checks` (:230, 2), `_page_row_issues` (:284, 6),
  `_stub_and_tail_issues` (:375, 2), `_opener_crop_fidelity_checks` (:407, 1),
  `_booklet_side_issues` (:441, 4), `_contents_issues` (:496, 5). Thirty-one
  sites, thirty distinct codes; `article-opener-offset-shadow` has two sites.
- The supporting leaves those need: `_all_a4_landscape` (:865),
  `_booklet_spread_checks` (:873), `_declared_editorial_cap` (:1214),
  `_manifest_layout` (:1015), `_manifest_opener_article_ids` (:1028),
  `_PageTexts.normalized` (:111).
- `inspect_render` (:551) as the orchestrator, minus the three parts listed
  under NOT PROVEN.

**Owns EXTENSION used, exactly as granted**: `mag/src/critic/metrics.rs:411`
`fn resize` becomes `pub(crate) fn resize`. One word, one line, and the whole
diff to that file is that word. `_inspect_opener_crop_fidelity` calls PIL's
`Image.resize` with LANCZOS, which `resize` already is, verified by WP-5.3a.

**Owns EXTENSION declared, not self-granted as behaviour**: `mag/src/critic.rs`
gains the one line `pub mod rules;`, as `5d9d154`, `26391ab` and `20adcfb` did
for their modules. The reason is revision 61's, not the one those three gave:
the line is load-bearing for VERIFIABILITY, not compilation. Without it the
file still builds and every `#[path]` test still passes, because the includes
route around the crate's module tree; what the line does is make `rules.rs`
part of what `cargo clippy -D warnings` on the BINARY checks, and make its
`use crate::critic::metrics::resize` an ordinary in-crate import that the
binary compiles. **That import is the consumer test for the `resize`
extension**, in rule 12's sense: it proves `pub(crate) fn resize` is reachable
from `mag/src/critic/rules.rs` the ordinary way, which no `#[path]` include
could show. The diff is exactly `+pub mod rules;`.

**Two duplications the audit caught and I removed rather than allowlisted.**
The first draft copied `division_multiplier` out of `metrics.rs` verbatim and
re-derived PIL's `Image.reduce` fixed-point average, and copied `executable`
out of `inspect.rs` under the name `which`. `cargo test --test rust_helpers`
failed on both, correctly. Neither is allowlisted and neither file is mine, so
both are gone: `render_crop_page` now spawns `pdftoppm` by name and maps a
spawn failure to Python's message, and the reduce is replaced by `mask_cells`,
a deliberate divergence argued under `## Residuals`. Three further name
collisions (`row`, `page_count`, `truthy`) were renamed to `as_row`, `pages`
and `json_truthy`.
## Commands

Every block below was extracted PROGRAMMATICALLY from this file and executed in
a clean shell from a directory that is not the one the work was developed in.
`$PWD` is the repository checkout root. The 010 corpus is untracked and exists
only in a working tree, never in a fresh worktree, so it arrives by rule 2b's
env gate through `MAG_010_RENDER`, which is the only path here that is not
`$PWD`-relative and is overridable.

Block 1, the committed fixtures and their oracle. Regenerating must leave every
committed byte unchanged. Rule 10h: that is an ABSENCE claim, so the check is
EMITTED by a wrapper that inspects `git status`'s own exit status (2 or more
aborts as UNKNOWN rather than reading as clean), and it carries a POSITIVE
CONTROL: the block first corrupts the committed oracle and requires the wrapper
to report CHANGED, then regenerates and requires UNCHANGED. A wrapper that
reported UNCHANGED for a corrupted file fails the block. The expected output
ends `FIXTURES CHANGED against HEAD`, ` M mag/tests/critic_rules_expected.json`,
`FIXTURES UNCHANGED against HEAD`, then the digest:

```sh
set -eu
check() {
  status=0
  changed=$(git status --porcelain mag/tests/critic_rules_fixtures mag/tests/critic_rules_expected.json) || status=$?
  if [ "$status" -ne 0 ]; then
    echo "STATUS CHECK DID NOT RUN, git exited $status"
    exit 2
  fi
  if [ -n "$changed" ]; then
    echo "FIXTURES CHANGED against HEAD:"
    echo "$changed"
    return 1
  fi
  echo "FIXTURES UNCHANGED against HEAD"
}
echo "POSITIVE CONTROL: corrupting the committed oracle, the check must report CHANGED"
printf '\n' >> mag/tests/critic_rules_expected.json
if check; then
  echo "POSITIVE CONTROL FAILED: the check cannot see a changed oracle"
  exit 1
fi
uv run python - <<'PY'
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, "src")
from PIL import Image, ImageOps
import magazine.render_critic as critic

root = Path("mag/tests/critic_rules_fixtures")
root.mkdir(parents=True, exist_ok=True)

def save(name, image):
    image.save(root / name)
    return name

def canvas(size, colour=(255, 255, 255)):
    return Image.new("RGB", size, colour)

def rect(image, box, colour):
    pixels = image.load()
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            pixels[x, y] = colour

FRAME = critic.OPENER_FRAME_RGB
ORANGE = critic.OPENER_OFFSET_RGB

def framed(size, box, colour=FRAME, background=(255, 255, 255)):
    image = canvas(size, background)
    rect(image, box, colour)
    return image

def opener(name, *, frame=FRAME, offset=None, orange_sides="both", narrow=()):
    image = canvas((200, 300))
    if offset is not None:
        box = (20 + offset, 30 + offset, 170 + offset, 100 + offset)
        if orange_sides == "both":
            rect(image, box, ORANGE)
        if orange_sides == "right":
            rect(image, (170, 30 + offset, 170 + offset + 12, 100), ORANGE)
    if frame is not None:
        rect(image, (20, 30, 170, 100), frame)
        for row, shrink in narrow:
            rect(image, (170 - shrink, row, 170, row + 1), (255, 255, 255))
    return save(name, image)

cases_offset = [
    ("pass", opener("opener_pass.png", offset=8)),
    ("fail_far", opener("opener_far.png", offset=20)),
    ("offset_inside_tolerance", opener("opener_offset_7.png", offset=7)),
    ("offset_outside_tolerance", opener("opener_offset_6.png", offset=6)),
    ("run_at_minimum", save("opener_run_130.png", framed((200, 300), (20, 30, 150, 100)))),
    ("run_below_minimum", save("opener_run_129.png", framed((200, 300), (20, 30, 149, 100)))),
    ("no_frame", opener("opener_no_frame.png", frame=None, offset=8)),
    ("no_orange", opener("opener_no_orange.png")),
    ("right_only", opener("opener_right_only.png", offset=8, orange_sides="right")),
    ("short_run", save("opener_short_run.png", framed((200, 300), (20, 30, 90, 100)))),
    ("tolerant_frame", opener("opener_tolerant.png", frame=(40, 40, 40), offset=8)),
    ("narrow_rows", opener("opener_narrow.png", offset=8, narrow=((30, 1), (31, 2), (32, 9)))),
]
offset_rows = [
    {"name": name, "png": png, "row": critic._inspect_opener_offset(root / png)}
    for name, png in cases_offset
]

save("fidelity_reference.png", framed((100, 140), (10, 20, 90, 60)))
save("fidelity_crop_scaled.png", framed((300, 420), (30, 60, 270, 180)))
save("fidelity_crop_shifted.png", framed((300, 420), (30, 66, 270, 186)))
save("fidelity_noisy_crop.png", framed((300, 420), (30, 60, 270, 180), background=(226, 226, 226)))
save("fidelity_flat_reference.png", canvas((100, 140), (255, 255, 255)))
save("fidelity_flat_at_budget.png", canvas((100, 140), (247, 247, 247)))
save("fidelity_flat_over_budget.png", canvas((100, 140), (246, 246, 246)))
save("fidelity_shift_one.png", framed((100, 140), (10, 21, 90, 61)))
save("fidelity_shift_two.png", framed((100, 140), (10, 22, 90, 62)))
save("fidelity_plain_reference.png", canvas((100, 140), (200, 200, 200)))
save("fidelity_plain_crop.png", canvas((100, 140), (200, 200, 200)))
save("fidelity_loud_crop.png", canvas((300, 420), (40, 200, 90)))

fidelity_rows = [
    {"name": name, "crop": crop, "reference": reference,
     "row": critic._inspect_opener_crop_fidelity(root / crop, root / reference)}
    for name, crop, reference in [
        ("scaled_match", "fidelity_crop_scaled.png", "fidelity_reference.png"),
        ("frame_delta", "fidelity_crop_shifted.png", "fidelity_reference.png"),
        ("no_frames", "fidelity_plain_crop.png", "fidelity_plain_reference.png"),
        ("one_frame", "fidelity_loud_crop.png", "fidelity_reference.png"),
        ("crop_frame_only", "fidelity_crop_scaled.png", "fidelity_plain_reference.png"),
        ("mae_over_budget", "fidelity_noisy_crop.png", "fidelity_reference.png"),
        ("mae_at_budget", "fidelity_flat_at_budget.png", "fidelity_flat_reference.png"),
        ("mae_one_over_budget", "fidelity_flat_over_budget.png", "fidelity_flat_reference.png"),
        ("frame_delta_one_pixel", "fidelity_shift_one.png", "fidelity_reference.png"),
        ("frame_delta_two_pixels", "fidelity_shift_two.png", "fidelity_reference.png"),
    ]
]

frame_rows = [
    {"name": f"{png}@{tolerance}", "png": png, "tolerance": tolerance,
     "bbox": (lambda box: list(box) if box else None)(
         critic._opener_frame_bbox(Image.open(root / png).convert("RGB"), color_tolerance=tolerance))}
    for png in ("opener_pass.png", "opener_no_frame.png", "opener_tolerant.png",
                "opener_short_run.png", "opener_narrow.png", "fidelity_reference.png",
                "opener_run_130.png", "opener_run_129.png")
    for tolerance in (0, 24)
]

def mask_case(name, size, dots, box):
    image = canvas(size)
    pixels = image.load()
    for x, y in dots:
        pixels[x, y] = (0, 0, 0)
    save(name, image)
    with Image.open(root / name) as opened:
        gray = ImageOps.grayscale(opened)
        presence = gray.point(lambda value: 255 if value < critic.PAPER_WHITE else 0)
        cells = presence.crop(tuple(box)).reduce(critic.VOID_DOWNSAMPLE)
        data = cells.tobytes()
    return {"name": name, "png": name, "box": box,
            "size": list(cells.size), "bytes": list(data),
            "sha256": hashlib.sha256(data).hexdigest()}

mask_rows = [
    mask_case("mask_grid.png", (64, 48),
              [(x, y) for x in range(0, 64, 9) for y in range(0, 48, 7)], [0, 0, 64, 48]),
    mask_case("mask_ragged.png", (37, 29),
              [(x, x % 29) for x in range(37)], [0, 0, 37, 29]),
    mask_case("mask_offset_box.png", (64, 48),
              [(x, y) for x in range(10, 50) for y in (12, 13, 30)], [5, 7, 61, 45]),
    mask_case("mask_outside_box.png", (32, 24),
              [(x, 5) for x in range(32)], [0, 0, 48, 40]),
    mask_case("mask_empty.png", (32, 24), [], [0, 0, 32, 24]),
]

def grid(rows):
    flat = [255 if cell else 0 for row in rows for cell in row]
    return flat, len(rows[0]), len(rows)

rectangle_cases = []
for name, rows in [
    ("empty", [[0] * 6 for _ in range(4)]),
    ("full", [[1] * 6 for _ in range(4)]),
    ("band", [[0] * 6, [1] * 6, [0] * 6, [0] * 6]),
    ("stairs", [[1, 0, 0, 0, 0, 0], [1, 1, 0, 0, 0, 0], [0, 0, 0, 1, 1, 1], [0, 0, 0, 0, 0, 1]]),
    ("single", [[1, 1, 1], [1, 0, 1], [1, 1, 1]]),
    ("tie", [[0, 0, 1, 0, 0], [0, 0, 1, 0, 0], [0, 0, 1, 0, 0]]),
]:
    flat, columns, rows_count = grid(rows)
    rectangle_cases.append({
        "name": name, "data": flat, "columns": columns, "rows": rows_count,
        "best": list(critic._largest_empty_rectangle(bytes(flat), columns, rows_count)),
    })

SYMMETRY_NEAR = [[1] * 4] + [[0] * 4] * 9 + [[1] * 4] * 4 + [[0] * 4] + [[1] * 4]
SYMMETRY_FAR = [[1] * 4] + [[0] * 4] * 10 + [[1] * 4] * 4 + [[0] * 4] + [[1] * 4]

band_cases = []
for name, rows, declared in [
    ("no_run", [[0] * 4 for _ in range(6)], 112.0),
    ("no_match", [[1] * 4, [0] * 4, [0] * 4, [0] * 4], 112.0),
    ("first_run", [[1] * 4, [1] * 4, [1] * 4, [1] * 4, [0] * 4, [1] * 4], 16.0),
    ("last_run_trailing", [[0] * 4, [1] * 4, [0] * 4, [1] * 4, [1] * 4, [1] * 4, [1] * 4], 16.0),
    ("middle_run", [[1] * 4, [0] * 4, [1] * 4, [1] * 4, [1] * 4, [1] * 4, [0] * 4, [1] * 4], 16.0),
    ("last_match_wins", [[1] * 4, [1] * 4, [1] * 4, [1] * 4, [0] * 4, [1] * 4, [1] * 4, [1] * 4, [1] * 4], 16.0),
    ("symmetry_at_tolerance", SYMMETRY_NEAR, 28.0),
    ("symmetry_past_tolerance", SYMMETRY_FAR, 28.0),
    ("height_at_tolerance", SYMMETRY_NEAR, 28.0),
    ("height_past_tolerance", SYMMETRY_NEAR, 28.1),
]:
    flat, columns, rows_count = grid(rows)
    live = [40, 24, 400, 560]
    produced = critic._locate_tail_band(bytes(flat), columns, rows_count, tuple(live), 0.5, declared)
    band_cases.append({"name": name, "data": flat, "columns": columns, "rows": rows_count,
                       "live": live, "scale": 0.5, "declared_height": declared, "band": produced})

abuts_cases = []
for name, void, band in [
    ("bottom_touches_top", {"y_points": 100.0, "height_points": 50.0}, {"y_points": 152.0, "height_points": 60.0}),
    ("top_touches_bottom", {"y_points": 210.0, "height_points": 50.0}, {"y_points": 140.0, "height_points": 64.0}),
    ("far_apart", {"y_points": 100.0, "height_points": 20.0}, {"y_points": 400.0, "height_points": 60.0}),
    ("edge_of_tolerance", {"y_points": 100.0, "height_points": 50.0}, {"y_points": 158.0, "height_points": 60.0}),
    ("just_past_tolerance", {"y_points": 100.0, "height_points": 50.0}, {"y_points": 158.1, "height_points": 60.0}),
]:
    abuts_cases.append({"name": name, "void": void, "band": band,
                        "abuts": critic._abuts_tail_band(void, band)})

editorial_cases = []
for name, layout in [
    ("missing", {}),
    ("null", {"maximum_editorial_pages": None}),
    ("one", {"maximum_editorial_pages": 1}),
    ("two", {"maximum_editorial_pages": 2}),
    ("many", {"maximum_editorial_pages": 9}),
    ("zero", {"maximum_editorial_pages": 0}),
    ("negative", {"maximum_editorial_pages": -3}),
    ("float", {"maximum_editorial_pages": 2.0}),
    ("text", {"maximum_editorial_pages": "2"}),
]:
    editorial_cases.append({"name": name, "layout": layout,
                            "cap": critic._declared_editorial_cap(layout)})

band_layout_cases = []
for name, layout, lasts in [
    ("plain", {"tail_arts": [{"article": "a", "printed": True, "height_points": 108.3333}]}, {"a": 9}),
    ("dropped", {"tail_arts": [{"article": "a", "printed": False, "height_points": None}]}, {"a": 9}),
    ("no_height", {"tail_arts": [{"article": "a", "printed": True, "height_points": None}]}, {"a": 9}),
    ("unknown_article", {"tail_arts": [{"article": "z", "printed": True, "height_points": 12.0}]}, {"a": 9}),
    ("null_article", {"tail_arts": [{"article": None, "printed": True, "height_points": 12.0}]}, {"None": 4}),
    ("not_a_dict", {"tail_arts": ["nope", {"article": "a", "printed": True, "height_points": 5}]}, {"a": 9}),
    ("missing_key", {}, {"a": 9}),
    ("null_key", {"tail_arts": None}, {"a": 9}),
    ("two_for_one_page", {"tail_arts": [{"article": "a", "printed": True, "height_points": 1.0},
                                        {"article": "b", "printed": True, "height_points": 2.0}]},
     {"a": 9, "b": 9}),
]:
    produced = critic._printed_tail_bands(layout, lasts)
    band_layout_cases.append({"name": name, "layout": layout, "article_last_pages": lasts,
                              "bands": {str(page): value for page, value in produced.items()}})

Path("mag/tests/critic_rules_expected.json").write_text(
    json.dumps({"opener_offset": offset_rows, "crop_fidelity": fidelity_rows,
                "frame_bbox": frame_rows,
                "masks": mask_rows, "rectangles": rectangle_cases, "tail_bands": band_cases,
                "abuts": abuts_cases, "editorial_caps": editorial_cases,
                "printed_tail_bands": band_layout_cases},
               indent=1, ensure_ascii=False, sort_keys=True) + "\n",
    encoding="utf-8")
print("opener offset rows", len(offset_rows), "fidelity", len(fidelity_rows),
      "masks", len(mask_rows), "rectangles", len(rectangle_cases),
      "tail bands", len(band_cases), "abuts", len(abuts_cases))
for row in offset_rows:
    print(" offset", row["name"], row["row"]["pass"], row["row"].get("offset_pixels"))
for row in fidelity_rows:
    print(" fidelity", row["name"], row["row"]["pass"], row["row"]["rgb_mae"],
          row["row"]["frame_edge_delta_inches"], "|", row["row"]["message"])
for row in frame_rows:
    print(" frame", row["name"], row["bbox"])
PY
uv run python - <<'PY'
import ast, json, sys, types
from pathlib import Path
sys.path.insert(0, "src")
import magazine.render_critic as critic

root = Path("mag/tests/critic_rules_fixtures")
expected_path = Path("mag/tests/critic_rules_expected.json")
oracle = json.loads(expected_path.read_text())


class Texts(critic._PageTexts):
    def __init__(self, raw, normalized):
        self._raw_rows, self._norm_rows = raw, normalized

    @property
    def page_count(self):
        return len(self._raw_rows)

    def raw(self, page_number):
        return self._raw_rows[page_number - 1]

    def normalized(self, page_number):
        return self._norm_rows[page_number - 1]


def leg(spec):
    return Texts(spec["raw"], spec["normalized"]), types.SimpleNamespace(
        pages=[
            types.SimpleNamespace(
                mediabox=types.SimpleNamespace(width=media[0], height=media[1])
            )
            for media in spec["media"]
        ]
    )


def collect(function, *args, **kwargs):
    issues = []
    value = function(critic._issue_recorder(issues), *args, **kwargs)
    return issues, value


A4 = [841.8898, 595.2756]
A5 = [419.5276, 595.2756]


def pages(count, text="body text here"):
    return {"raw": [text] * count, "normalized": [text] * count, "media": [A5] * count}


def sides(pairs, media=A4):
    return {"raw": [text for text in pairs], "normalized": [text for text in pairs],
            "media": [media] * len(pairs)}


def imposition_case(name, reader, booklet, interior, cover, rendered):
    reader_texts, reader_doc = leg(reader)
    booklet_texts, booklet_doc = leg(booklet)
    interior_texts, interior_doc = leg(interior)
    cover_texts, cover_doc = leg(cover)
    issues, value = collect(
        critic._imposition_checks,
        types.SimpleNamespace(
            texts=(reader_texts, booklet_texts, interior_texts, cover_texts),
            pdfs=(reader_doc, booklet_doc, interior_doc, cover_doc),
            rendered=tuple([f"p{index}" for index in range(count)] for count in rendered),
            page_count=len(reader["raw"]),
        ),
    )
    return {"name": name, "reader": reader, "booklet": booklet, "interior": interior,
            "cover": cover, "rendered": rendered, "issues": issues,
            "spreads": value.spread_checks,
            "interior_spreads": value.interior_spread_checks,
            "cover_spreads": value.cover_spread_checks,
            "interior_pages": list(value.interior_pages),
            "cover_pages": list(value.cover_pages)}


def matching(page_count):
    reader = pages(page_count)
    reader["raw"] = [f"page {index + 1} words" for index in range(page_count)]
    reader["normalized"] = list(reader["raw"])
    plan = critic.imposed_reader_page_plan(critic.section_reader_pages(page_count, "all"))
    booklet_text = [
        " ".join(reader["normalized"][page - 1] for page in pair if page is not None)
        for pair in plan
    ]
    interior_plan = critic.imposed_reader_page_plan(critic.section_reader_pages(page_count, "interior"))
    interior_text = [
        " ".join(reader["normalized"][page - 1] for page in pair if page is not None)
        for pair in interior_plan
    ]
    cover_plan = critic.cover_wrap_plan(page_count)
    cover_text = [
        " ".join(reader["normalized"][page - 1] for page in pair if page is not None)
        for pair in cover_plan
    ]
    return reader, sides(booklet_text), sides(interior_text), sides(cover_text)


imposition_cases = []
reader, booklet, interior, cover = matching(8)
imposition_cases.append(
    imposition_case("clean", reader, booklet, interior, cover, [8, len(booklet["raw"]), 1])
)
broken_booklet = sides(["wrong order here"] * 4)
broken_interior = sides(["nope"], media=[419.0, 595.0])
broken_cover = sides(["nope", "extra"], media=[419.0, 595.0])
A4_IN = [841.8898 + 0.74, 595.2756]
A4_OUT = [841.8898 + 0.76, 595.2756]
imposition_cases.append(
    imposition_case(
        "every_fault",
        pages(6, "x"),
        broken_booklet,
        broken_interior,
        broken_cover,
        [1, 2, 0],
    )
)
imposition_cases.append(
    imposition_case("too_small", pages(2, "x"), sides(["a"]), sides([]), sides([]), [2, 1, 0])
)
reader, booklet, interior, cover = matching(8)
interior["media"] = [A4_IN] * len(interior["raw"])
cover["media"] = [A4_OUT] * len(cover["raw"])
imposition_cases.append(
    imposition_case("geometry_tolerance", reader, booklet, interior, cover,
                    [8, len(booklet["raw"]), 1])
)

row_defaults = {
    "blank": False, "ink_free": False, "sparse": False, "ink_ratio": 0.5,
    "standalone_punctuation_lines": [], "voids": [], "tail_band": None,
    "body_text_lines": 30,
}


def row(page, **overrides):
    out = dict(row_defaults, page=page)
    out.update(overrides)
    return out


def void(y, height, *, width=353.5, fraction=1.0, trailing=False):
    return {"x_points": 35.0, "y_points": y, "width_points": width,
            "height_points": height, "width_fraction": fraction, "trailing": trailing}


BAND = {"y_points": 438.5, "height_points": 112.0, "declared_height_points": 108.3333,
        "gap_above_points": 24.0, "gap_below_points": 16.0, "centered": True}

row_cases = []
for name, rows, inside, lasts, live, article_lasts in [
    ("inside_cover_not_blank", [row(2, blank=False)], [2], [], None, {}),
    ("inside_cover_blank", [row(2, blank=True)], [2], [], None, {}),
    ("blank_page", [row(5, ink_free=True)], [], [], None, {}),
    ("sparse_page", [row(5, sparse=True, ink_ratio=0.00123456)], [], [], None, {}),
    ("orphan_punctuation", [row(5, standalone_punctuation_lines=[",", "..."])], [], [], None, {}),
    ("whitespace_void", [row(5, voids=[void(150.5, 288.0)])], [], [], [35.0, 14.5, 388.5, 576.0], {}),
    ("void_abuts_band_above", [row(5, voids=[void(150.5, 288.0)], tail_band=BAND)], [], [],
     [35.0, 14.5, 388.5, 576.0], {}),
    ("void_abuts_band_below", [row(5, voids=[void(550.5, 20.0)], tail_band=BAND)], [], [],
     [35.0, 14.5, 388.5, 576.0], {}),
    ("void_near_band_but_not_abutting", [row(5, voids=[void(100.0, 100.0)], tail_band=BAND)], [], [],
     [35.0, 14.5, 388.5, 576.0], {}),
    ("tail_gap", [row(9, voids=[void(300.0, 240.0, trailing=True)])], [], [9],
     [35.0, 14.5, 388.5, 576.0], {"an-article": 9}),
    ("tail_gap_unknown_slug", [row(9, voids=[void(300.0, 240.0, trailing=True)])], [], [9],
     [35.0, 14.5, 388.5, 576.0], {"other": 4}),
    ("tail_gap_too_small", [row(9, voids=[void(300.0, 100.0, trailing=True)])], [], [9],
     [35.0, 14.5, 388.5, 576.0], {"an-article": 9}),
    ("tail_gap_at_threshold", [row(9, voids=[void(300.0, 196.525, trailing=True)])], [], [9],
     [35.0, 14.5, 388.5, 576.0], {"an-article": 9}),
    ("tail_gap_below_threshold", [row(9, voids=[void(300.0, 196.5, trailing=True)])], [], [9],
     [35.0, 14.5, 388.5, 576.0], {"an-article": 9}),
    ("tail_gap_with_band", [row(9, voids=[void(300.0, 240.0, trailing=True)], tail_band=BAND)], [], [9],
     [35.0, 14.5, 388.5, 576.0], {"an-article": 9}),
    ("tail_gap_without_live_area", [row(9, voids=[void(300.0, 240.0, trailing=True)])], [], [9],
     None, {"an-article": 9}),
    ("trailing_void_not_last_page", [row(5, voids=[void(442.5, 128.0, trailing=True)])], [], [9],
     [35.0, 14.5, 388.5, 576.0], {}),
    ("three_voids", [row(5, voids=[void(100.0, 100.0), void(250.0, 96.0), void(400.0, 120.0)])],
     [], [], [35.0, 14.5, 388.5, 576.0], {}),
]:
    issues, flags = collect(
        critic._page_row_issues, rows, set(inside), set(lasts), live, article_lasts
    )
    row_cases.append({"name": name, "rows": rows, "inside_cover_pages": inside,
                      "last_page_numbers": lasts, "live_area_points": live,
                      "article_last_pages": article_lasts, "issues": issues,
                      "flag_crops": flags})

stub_cases = []
for name, article_lasts, rows, layout in [
    ("stub", {"an-article": 2}, [row(1), row(2, body_text_lines=4)], {}),
    ("no_stub", {"an-article": 2}, [row(1), row(2, body_text_lines=5)], {}),
    ("out_of_range", {"an-article": 9}, [row(1)], {}),
    ("zero_lines", {"an-article": 1}, [row(1, body_text_lines=0)], {}),
    ("dropped_tail", {}, [row(1)],
     {"tail_arts": [{"article": "a", "declared": True, "printed": False, "drop_reason": "too tight"}]}),
    ("dropped_tail_bare", {}, [row(1)],
     {"tail_arts": [{"declared": True, "printed": False}]}),
    ("declared_and_printed", {}, [row(1)],
     {"tail_arts": [{"article": "a", "declared": True, "printed": True}]}),
    ("not_declared", {}, [row(1)], {"tail_arts": [{"article": "a", "printed": False}]}),
    ("declared_zero", {}, [row(1)], {"tail_arts": [{"article": "a", "declared": 0, "printed": False}]}),
    ("not_a_dict", {}, [row(1)], {"tail_arts": ["x"]}),
    ("two_stubs", {"a": 1, "b": 2}, [row(1, body_text_lines=1), row(2, body_text_lines=2)], {}),
]:
    flags = []
    issues = []
    critic._stub_and_tail_issues(
        critic._issue_recorder(issues), article_lasts, rows, layout, flags
    )
    stub_cases.append({"name": name, "article_last_pages": article_lasts, "rows": rows,
                       "layout": layout, "issues": issues, "flag_crops": flags})


def spread(side, left, right):
    return {"side": side, "sheet": (side + 1) // 2,
            "face": "outside" if side % 2 else "inside",
            "left_reader_page": left, "right_reader_page": right,
            "text_order_matches": True}


side_cases = []
for name, spreads, booklet_rows, cover_spreads, cover_rows, inside in [
    ("inside_side_not_blank", [spread(1, 2, 7)], [row(1, blank=False)], [], [], [2, 7]),
    ("inside_side_blank", [spread(1, 2, 7)], [row(1, blank=True)], [], [], [2, 7]),
    ("blank_booklet_side", [spread(1, 3, 6)], [row(1, ink_free=True)], [], [], [2, 7]),
    ("cover_inside_not_blank", [], [], [spread(1, 2, 7)], [row(1, blank=False)], [2, 7]),
    ("blank_cover_outside", [], [], [spread(1, 8, 1)], [row(1, ink_free=True)], [2, 7]),
    ("all_quiet", [spread(1, 3, 6)], [row(1)], [spread(1, 8, 1)], [row(1)], [2, 7]),
]:
    issues, value = collect(
        critic._booklet_side_issues, spreads, booklet_rows, cover_spreads, cover_rows, set(inside)
    )
    side_cases.append({"name": name, "spreads": spreads, "booklet_rows": booklet_rows,
                       "cover_spreads": cover_spreads, "cover_booklet_rows": cover_rows,
                       "inside_cover_pages": inside, "issues": issues,
                       "cover_inside_sides": sorted(value)})

contents_cases = []
for name, cover_text, toc, page_count, article_pages, editorial, layout, actual, maximum in [
    ("clean", "BERRETA FUTURA", {"a": 4}, 8, {"a": 2}, None, {}, 1, 1),
    ("placeholder_ellipsis", "The title ...", {"a": 4}, 8, {}, None, {}, 1, 1),
    ("placeholder_todo", "TODO write this", {"a": 4}, 8, {}, None, {}, 1, 1),
    ("placeholder_insert", "[insert deck]", {"a": 4}, 8, {}, None, {}, 1, 1),
    ("placeholder_case", "tbd", {"a": 4}, 8, {}, None, {}, 1, 1),
    ("placeholder_word_boundary", "TODOS are fine", {"a": 4}, 8, {}, None, {}, 1, 1),
    ("no_pages", "", {}, 0, {}, None, {}, 1, 1),
    ("pagination_zero", "", {"a": 4}, 8, {}, None, {}, 0, 1),
    ("pagination_over", "", {"a": 4}, 8, {}, None, {}, 3, 2),
    ("folio_low", "", {"a": 3}, 8, {}, None, {}, 1, 1),
    ("folio_high", "", {"a": 9}, 8, {}, None, {}, 1, 1),
    ("cap_error", "", {"a": 4}, 8, {"a": 9}, None, {}, 1, 1),
    ("cap_review", "", {"a": 4}, 8, {"a": 9}, None,
     {"article_content_modes": {"a": "verbatim"}}, 1, 1),
    ("cap_declared", "", {"a": 4}, 8, {"a": 9}, None, {"article_page_caps": {"a": 10}}, 1, 1),
    ("cap_boundary", "", {"a": 4}, 8, {"a": 7}, None, {}, 1, 1),
    ("cap_just_over", "", {"a": 4}, 8, {"a": 8}, None, {}, 1, 1),
    ("editorial_over", "", {"a": 4}, 8, {}, 3, {}, 1, 1),
    ("editorial_at_cap", "", {"a": 4}, 8, {}, 2, {}, 1, 1),
    ("editorial_over_declared_one", "", {"a": 4}, 8, {}, 2, {"maximum_editorial_pages": 1}, 1, 1),
]:
    texts = Texts([cover_text] * page_count, [cover_text] * page_count)
    issues, cap = collect(
        critic._contents_issues, texts, toc, page_count, article_pages, editorial,
        layout, actual, maximum,
    )
    contents_cases.append({"name": name, "cover_text": cover_text, "toc": toc,
                           "page_count": page_count, "article_pages": article_pages,
                           "editorial_pages": editorial, "layout": layout,
                           "actual_contents_pages": actual, "maximum_contents_pages": maximum,
                           "issues": issues, "editorial_page_cap": cap})

offset_check_cases = []
for name, illustrated, toc, rendered in [
    ("missing_from_toc", ["a"], {}, ["opener_pass.png"]),
    ("page_out_of_range", ["a"], {"a": 9}, ["opener_pass.png"]),
    ("page_zero", ["a"], {"a": 0}, ["opener_pass.png"]),
    ("passes", ["a"], {"a": 1}, ["opener_pass.png"]),
    ("fails", ["a"], {"a": 1}, ["opener_far.png"]),
    ("no_frame", ["a"], {"a": 1}, ["opener_no_frame.png"]),
    ("two_articles", ["a", "b"], {"a": 1, "b": 2}, ["opener_pass.png", "opener_far.png"]),
    ("none_declared", [], {"a": 1}, ["opener_pass.png"]),
]:
    issues, checks = collect(
        critic._opener_offset_checks, illustrated, toc, [root / name for name in rendered]
    )
    offset_check_cases.append({"name": name, "illustrated": illustrated, "toc": toc,
                               "rendered": rendered, "issues": issues, "checks": checks})

fidelity_check_cases = []
for name, crops, rendered in [
    ("not_an_opener", [{"kind": "figure", "page": 1, "path": "fidelity_crop_scaled.png",
                        "region_points": [0.0, 0.0, 50.0, 70.0]}], ["fidelity_reference.png"]),
    ("page_out_of_range", [{"kind": "opener", "page": 4, "path": "fidelity_crop_scaled.png",
                            "region_points": [0.0, 0.0, 50.0, 70.0]}], ["fidelity_reference.png"]),
    ("size_mismatch", [{"kind": "opener", "page": 1, "path": "fidelity_crop_scaled.png",
                        "region_points": [0.0, 0.0, 419.5, 595.3]}], ["fidelity_reference.png"]),
    ("passes", [{"kind": "opener", "page": 1, "path": "fidelity_crop_scaled.png",
                 "region_points": [0.0, 0.0, 50.0, 70.0]}], ["fidelity_reference.png"]),
    ("fails", [{"kind": "opener", "page": 1, "path": "fidelity_noisy_crop.png",
                "region_points": [0.0, 0.0, 50.0, 70.0]}], ["fidelity_reference.png"]),
]:
    issues, checks = collect(
        critic._opener_crop_fidelity_checks, crops, [root / name for name in rendered], root
    )
    fidelity_check_cases.append({"name": name, "crops": crops, "rendered": rendered,
                                 "issues": issues, "checks": checks})

normalized_cases = [
    {"name": name, "raw": raw, "normalized": " ".join(raw.split())}
    for name, raw in [
        ("plain", "one two three"),
        ("double_space", "one  two"),
        ("leading_and_trailing", "  one two  "),
        ("tabs_and_newlines", "one\ttwo\nthree\r\nfour"),
        ("only_whitespace", " \t\n "),
        ("empty", ""),
        ("vertical_tab_and_formfeed", "one\x0btwo\x0cthree"),
        ("file_and_group_separators", "one\x1ctwo\x1dthree\x1efour\x1ffive"),
        ("next_line_and_nbsp", "one\x85two\xa0three"),
        ("unicode_spaces", "one\u2000two\u2028three\u3000four"),
        ("joined_shows", "BERRETA FUTURA  LOOP CLOSED"),
        ("empty_show_between", "one  three"),
    ]
]

issue_site_rows = []
for node in ast.walk(ast.parse(Path("src/magazine/render_critic.py").read_text())):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "issue":
        first = node.args[0] if node.args else None
        issue_site_rows.append({
            "line": node.lineno,
            "code": first.value if isinstance(first, ast.Constant) else None,
        })
issue_site_rows.sort(key=lambda row: row["line"])

oracle.update({
    "issue_sites": issue_site_rows,
    "normalized": normalized_cases,
    "imposition": imposition_cases,
    "page_rows": row_cases,
    "stub_and_tail": stub_cases,
    "booklet_sides": side_cases,
    "contents": contents_cases,
    "opener_offset_checks": offset_check_cases,
    "opener_crop_fidelity_checks": fidelity_check_cases,
})
expected_path.write_text(
    json.dumps(oracle, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
)
codes = sorted({issue["code"] for group in
                (imposition_cases, row_cases, stub_cases, side_cases, contents_cases,
                 offset_check_cases, fidelity_check_cases)
                for case in group for issue in case["issues"]})
print("issue codes exercised:", len(codes))
for code in codes:
    print("  ", code)
PY
uv run python - <<'PY'
import hashlib, json, sys, tempfile, types
from pathlib import Path
sys.path.insert(0, "src")
from PIL import Image
import magazine.render_critic as critic

expected_path = Path("mag/tests/critic_rules_expected.json")
oracle = json.loads(expected_path.read_text())
A5 = [419.5276, 595.2756]


def doc(media):
    return types.SimpleNamespace(
        pages=[
            types.SimpleNamespace(
                mediabox=types.SimpleNamespace(width=size[0], height=size[1])
            )
            for size in media
        ]
    )


BAND = {"y_points": 438.5, "height_points": 112.0, "declared_height_points": 108.3333,
        "gap_above_points": 24.0, "gap_below_points": 16.0, "centered": True}


def page_row(page, band=None):
    return {"page": page, "tail_band": band}


plan_cases = []
for name, toc, layout, bands, rows, flags, page_count in [
    ("openers", {"b": 4, "a": 4, "c": 5}, {}, {}, [page_row(n) for n in range(1, 7)], [], 6),
    ("opener_out_of_range", {"a": 9}, {}, {}, [page_row(n) for n in range(1, 7)], [], 6),
    ("figures", {}, {"figures": [
        {"page": 2, "id": "one", "box_points": [64.454, 248.276, 289.14, 205.0]},
        {"page": 2, "figure_id": "two", "box_points": [10, 20, 30, 40]},
        {"page": 2, "box_points": [10, 20, 30, 40]},
        {"page": 99, "id": "off", "box_points": [10, 20, 30, 40]},
        {"page": "x", "id": "bad", "box_points": [10, 20, 30, 40]},
        {"page": 2, "id": "short", "box_points": [10, 20, 30]},
        {"page": 2, "id": "nobox"},
        "not a dict",
    ]}, {}, [page_row(n) for n in range(1, 7)], [], 6),
    ("tails", {}, {}, {3: 108.3333, 4: 108.3333, 9: 108.3333},
     [page_row(1), page_row(2), page_row(3, BAND), page_row(4), page_row(5), page_row(6)], [], 6),
    ("flags", {}, {}, {}, [page_row(n) for n in range(1, 7)],
     [{"page": 2, "kind": "sparse", "span": None},
      {"page": 3, "kind": "void", "span": (100.0, 300.0)},
      {"page": 4, "kind": "stub", "span": (0.0, 220.0)},
      {"page": 99, "kind": "void", "span": (0.0, 10.0)}], 6),
    ("clamping", {}, {"figures": [
        {"page": 1, "id": "wide", "box_points": [-500.0, -500.0, 5000.0, 5000.0]}]}, {},
     [page_row(n) for n in range(1, 7)], [], 6),
    ("empty", {}, {}, {}, [page_row(n) for n in range(1, 7)], [], 6),
]:
    specs = critic._review_crop_plan(
        doc([A5] * 6), toc=toc, manifest_layout=layout,
        printed_tail_bands={int(k): v for k, v in bands.items()},
        page_rows=rows, flag_crops=[dict(flag) for flag in flags], page_count=page_count,
    )
    plan_cases.append({
        "name": name, "toc": toc, "layout": layout,
        "printed_tail_bands": {str(k): v for k, v in bands.items()},
        "rows": rows,
        "flag_crops": [{"page": f["page"], "kind": f["kind"],
                        "span": list(f["span"]) if f["span"] else None} for f in flags],
        "media": [A5] * 6,
        "specs": [{"page": s["page"], "kind": s["kind"], "subject": s["subject"],
                   "region": list(s["region"])} for s in specs],
    })

pdf = Path("mag/tests/critic_inspect_fixtures/pages12.pdf")
write_cases = []
for name, specs in [
    ("dedup_and_degenerate", [
        {"page": 3, "kind": "opener", "subject": "a", "region": (0.0, 0.0, 419.5276, 595.2756)},
        {"page": 3, "kind": "opener", "subject": "b", "region": (0.0, 0.0, 200.0, 300.0)},
        {"page": 3, "kind": "opener", "subject": "c", "region": (0.0, 0.0, 0.0, 300.0)},
        {"page": 3, "kind": "opener", "subject": "d", "region": (0.0, 0.0, 419.5276, 0.0)},
        {"page": 5, "kind": "void", "subject": None, "region": (0.0, 40.0, 419.5276, 260.0)},
    ]),
    ("single", [
        {"page": 1, "kind": "tail", "subject": None, "region": (0.0, 295.2756, 419.5276, 595.2756)},
    ]),
]:
    destination = Path(tempfile.mkdtemp(prefix="wp53biii-crops-"))
    paths, rows = critic._write_review_crops(pdf, destination / "crops", destination, specs)
    write_cases.append({
        "name": name,
        "specs": [{"page": s["page"], "kind": s["kind"], "subject": s["subject"],
                   "region": list(s["region"])} for s in specs],
        "rows": rows,
        "pixels": {
            path.name: hashlib.sha256(Image.open(path).convert("RGB").tobytes()).hexdigest()
            for path in paths
        },
        "left_over": sorted(p.name for p in (destination / "crops").iterdir()),
    })

oracle.update({"crop_plan": plan_cases, "crop_writing": write_cases})
expected_path.write_text(
    json.dumps(oracle, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
)
for case in plan_cases:
    print("plan", case["name"], [(s["page"], s["kind"], s["subject"]) for s in case["specs"]])
for case in write_cases:
    print("write", case["name"], [r["path"] for r in case["rows"]], case["left_over"])
PY
uv run python - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, "src")
from PIL import Image
import magazine.render_critic as critic

root = Path("mag/tests/critic_rules_fixtures")
expected_path = Path("mag/tests/critic_rules_expected.json")
oracle = json.loads(expected_path.read_text())

W, H = 160, 240


def page(name, stripes, width=W, height=H, columns=()):
    image = Image.new("RGB", (width, height), (255, 255, 255))
    pixels = image.load()
    for top, bottom in stripes:
        for y in range(top, bottom):
            for x in range(width):
                pixels[x, y] = (0, 0, 0)
    for left, right in columns:
        for y in range(height):
            for x in range(left, right):
                pixels[x, y] = (0, 0, 0)
    image.save(root / name)
    return name


LIVE = [0, 0, W, H]
TALL = [0, 0, W, 856]
page("void_band_192.png", [(0, 8), (200, 208), (232, 240)])
page("void_band_184.png", [(0, 8), (192, 200), (232, 240)])
page("void_narrow_18.png", [(0, 8), (200, 208)], columns=[(0, 16)])
page("void_narrow_17.png", [(0, 8), (200, 208)], columns=[(0, 24)])
page("void_trailing_32.png", [(0, 8), (208, 216)])
page("void_trailing_40.png", [(0, 8), (200, 208)])
page("void_three.png", [(0, 8), (224, 232), (440, 448), (648, 656), (848, 856)], height=856)
page("void_full.png", [(0, 240)])
page("void_blank.png", [])
page("void_band_and_tail.png", [(0, 8), (96, 104), (200, 208), (232, 240)])

cases = []
for name, rasters, rows, body, bands in [
    ("height_at_threshold", ["void_band_192.png"], [(1, LIVE)], [1], {}),
    ("height_below_threshold", ["void_band_184.png"], [(1, LIVE)], [1], {}),
    ("width_at_threshold", ["void_narrow_18.png"], [(1, LIVE)], [1], {}),
    ("width_below_threshold", ["void_narrow_17.png"], [(1, LIVE)], [1], {}),
    ("trailing_at_tolerance", ["void_trailing_32.png"], [(1, LIVE)], [1], {}),
    ("trailing_past_tolerance", ["void_trailing_40.png"], [(1, LIVE)], [1], {}),
    ("three_voids", ["void_three.png"], [(1, TALL)], [1], {}),
    ("fully_inked", ["void_full.png"], [(1, LIVE)], [1], {}),
    ("all_blank", ["void_blank.png"], [(1, LIVE)], [1], {}),
    ("with_tail_band", ["void_band_and_tail.png"], [(1, LIVE)], [1], {1: 4.0}),
    ("tail_band_not_found", ["void_band_and_tail.png"], [(1, LIVE)], [1], {1: 400.0}),
    ("no_body_boxes", ["void_band_192.png"], [(1, LIVE)], [], {}),
    ("no_presence_bbox", ["void_band_192.png"], [(1, None), (2, LIVE)], [1, 2], {}),
    ("tiny_live_area", ["void_band_192.png"], [(1, [0, 0, 4, 4])], [1], {}),
    ("page_beyond_rasters", ["void_band_192.png"], [(1, LIVE), (2, LIVE)], [1, 2], {}),
    ("two_pages_widen_live", ["void_band_192.png", "void_band_184.png"],
     [(1, [10, 20, 100, 200]), (2, [0, 0, 160, 240])], [1, 2], {}),
    ("live_width_not_a_cell_multiple", ["void_band_192.png"], [(1, [0, 0, 158, 240])], [1], {}),
]:
    page_rows = [
        {"page": number, "presence_bbox": box, "largest_void": None, "voids": [], "tail_band": None}
        for number, box in rows
    ]
    live = critic._annotate_void_geometry(
        [root / raster for raster in rasters], page_rows, set(body),
        {int(k): v for k, v in bands.items()},
    )
    cases.append({
        "name": name, "rasters": rasters,
        "rows": [{"page": number, "presence_bbox": box} for number, box in rows],
        "body_pages": body, "tail_bands": {str(k): v for k, v in bands.items()},
        "live_area_points": live,
        "annotated": [{"page": row["page"], "largest_void": row["largest_void"],
                       "voids": row["voids"], "tail_band": row["tail_band"]}
                      for row in page_rows],
    })

oracle["void_geometry"] = cases
expected_path.write_text(
    json.dumps(oracle, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
)
for case in cases:
    first = case["annotated"][0]
    print(case["name"], "live", case["live_area_points"],
          "largest", first["largest_void"], "voids", len(first["voids"]),
          "band", first["tail_band"] is not None)
PY
uv run python - <<'PY'
import json, struct
from pathlib import Path

EXPECTED = {
    "opener_offset": ["row"],
    "crop_fidelity": ["row"],
    "frame_bbox": ["bbox"],
    "masks": ["size"],
    "rectangles": ["best"],
    "tail_bands": ["band"],
    "abuts": ["abuts"],
    "editorial_caps": ["cap"],
    "printed_tail_bands": ["bands"],
    "imposition": ["issues", "spreads", "interior_spreads", "cover_spreads",
                   "interior_pages", "cover_pages"],
    "page_rows": ["issues", "flag_crops"],
    "stub_and_tail": ["issues", "flag_crops"],
    "booklet_sides": ["issues", "cover_inside_sides"],
    "contents": ["issues", "editorial_page_cap"],
    "opener_offset_checks": ["issues", "checks"],
    "opener_crop_fidelity_checks": ["issues", "checks"],
    "crop_plan": ["specs"],
    "crop_writing": ["rows"],
    "normalized": ["normalized"],
    "void_geometry": ["live_area_points", "annotated"],
}


def canon(value):
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return f"i{value}"
    if isinstance(value, float):
        return "f" + struct.pack(">d", value).hex()
    if isinstance(value, dict):
        return {key: canon(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canon(item) for item in value]
    raise TypeError(value)


path = Path("mag/tests/critic_rules_expected.json")
oracle = json.loads(path.read_text())
for group, keys in EXPECTED.items():
    for case in oracle[group]:
        for key in keys:
            case[key] = canon(case[key])
path.write_text(json.dumps(oracle, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8")
print("canonicalised", len(EXPECTED), "groups in", path)
PY
echo "REGENERATED: the check must now report UNCHANGED"
check
shasum -a 256 mag/tests/critic_rules_expected.json
```

Block 2, the repository checks:

```sh
set -eu
cargo fmt --manifest-path mag/Cargo.toml --check
cargo clippy --manifest-path mag/Cargo.toml --all-targets -- -D warnings
uv run python tools/nocomments.py
cargo test --manifest-path mag/Cargo.toml 2>&1 | grep -E "^test result|^error" | sort | uniq -c
```

Blocks 3 and 4, the two phases the live oracle needs. Phase one dumps the RUST
tracer's text for each of the four PDFs; phase two runs Python's own
`inspect_render` TWICE on staged copies, once with its pypdf `_PageTexts` and
once with `_PageTexts` replaced by that dump, and cross-checks the pypdf run
against the shipped `render-critic.json`. Nothing in the repository depends on
the output, which is written outside the checkout:

```sh
set -eu
MAG_010_RENDER="${MAG_010_RENDER:-$HOME/code/magazine/editions/010/render-2026-09-14T01-49-02/en}"
MAG_CRITIC_RULES_TEXT="${MAG_CRITIC_RULES_TEXT:-${TMPDIR:-/tmp}/wp53biii-tracer-text.json}"
export MAG_CRITIC_RULES_TEXT
MAG_CRITIC_RENDER_DIR="$MAG_010_RENDER" \
  cargo test --manifest-path mag/Cargo.toml --test critic_rules dumps_the_tracer -- --nocapture 2>&1 \
  | grep -E "^MODE|^TRACED|^WROTE|^test result" || true
shasum -a 256 "$MAG_CRITIC_RULES_TEXT"
```

```sh
set -eu
MAG_010_RENDER="${MAG_010_RENDER:-$HOME/code/magazine/editions/010/render-2026-09-14T01-49-02/en}"
MAG_CRITIC_RULES_TEXT="${MAG_CRITIC_RULES_TEXT:-${TMPDIR:-/tmp}/wp53biii-tracer-text.json}"
MAG_CRITIC_RULES_ORACLE="${MAG_CRITIC_RULES_ORACLE:-${TMPDIR:-/tmp}/wp53biii-rules-010.json}"
export MAG_010_RENDER MAG_CRITIC_RULES_TEXT MAG_CRITIC_RULES_ORACLE
uv run python - <<'PY'
import hashlib, json, os, shutil, struct, sys, tempfile
from pathlib import Path
sys.path.insert(0, "src")
from PIL import Image
import magazine.render_critic as critic

render = Path(os.environ["MAG_010_RENDER"])
traced = json.loads(Path(os.environ["MAG_CRITIC_RULES_TEXT"]).read_text())
names = {"reader": "reader.pdf", "booklet": "booklet-a4.pdf",
         "interior": "booklet-a4-interior.pdf", "cover": "booklet-a4-cover.pdf"}
by_pages = {len(traced[leg]["raw"]): traced[leg] for leg in names}
assert len(by_pages) == 4, sorted(by_pages)

original = critic._PageTexts

class Tracer(original):
    def __init__(self, document):
        self._rows = by_pages[len(document.pages)]

    @property
    def page_count(self):
        return len(self._rows["raw"])

    def raw(self, page_number):
        return self._rows["raw"][page_number - 1]

    def normalized(self, page_number):
        return self._rows["normalized"][page_number - 1]

manifest = json.loads((render / "edition-manifest.json").read_text())
layout = manifest["layout"]

def run(tag):
    destination = Path(tempfile.mkdtemp(prefix=f"wp53biii-py-{tag}-"))
    for name in names.values():
        shutil.copyfile(render / name, destination / name)
    shutil.copyfile(render / "edition-manifest.json", destination / "edition-manifest.json")
    report, _ = critic.inspect_render(
        destination / "reader.pdf",
        destination / "booklet-a4.pdf",
        destination,
        interior_booklet_pdf=destination / "booklet-a4-interior.pdf",
        cover_booklet_pdf=destination / "booklet-a4-cover.pdf",
        language="en",
        toc=layout["toc"],
        article_pages=layout["article_pages"],
        editorial_pages=layout.get("editorial_pages"),
        edition_id="010",
        recorded_review=None,
    )
    return destination, report

def canon(value):
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return f"i{value}"
    if isinstance(value, float):
        return "f" + struct.pack(">d", value).hex()
    if isinstance(value, dict):
        return {key: canon(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canon(item) for item in value]
    raise TypeError(value)


def project(destination, report):
    crops = report["visual_review"]["crops"]
    pixels = {}
    for crop in crops:
        path = destination / crop["path"]
        with Image.open(path) as opened:
            pixels[path.name] = hashlib.sha256(opened.convert("RGB").tobytes()).hexdigest()
    return canon({
        "decisions": {"result": report["result"], "issues": report["issues"]},
        "geometry": [{"page": row["page"], "largest_void": row["largest_void"],
                      "voids": row["voids"], "tail_band": row["tail_band"]}
                     for row in report["pages"]],
        "spreads": report["home_booklet"]["spreads"],
        "interior_spreads": report["home_booklet_interior"]["spreads"],
        "cover_spreads": report["home_booklet_cover"]["spreads"],
        "live_area_points": report["checks"]["live_area_points"],
        "crops": crops,
        "opener_crop_fidelity": report["checks"]["article_opener_crop_fidelity"],
        "opener_offsets": report["checks"]["article_opener_offsets"],
        "crop_pixels": pixels,
    })

critic._PageTexts = Tracer
tracer_dir, tracer_report = run("tracer")
critic._PageTexts = original
pypdf_dir, pypdf_report = run("pypdf")

out = {"tracer_text": project(tracer_dir, tracer_report),
       "pypdf_text": project(pypdf_dir, pypdf_report)}
target = Path(os.environ["MAG_CRITIC_RULES_ORACLE"])
target.write_text(json.dumps(out, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
print("oracle", target, target.stat().st_size,
      hashlib.sha256(target.read_bytes()).hexdigest())
print("tracer result", tracer_report["result"], "issues", len(tracer_report["issues"]))
print("pypdf  result", pypdf_report["result"], "issues", len(pypdf_report["issues"]))
print("decision sets equal across the text swap:",
      out["tracer_text"]["decisions"] == out["pypdf_text"]["decisions"])
print("geometry equal across the text swap:",
      out["tracer_text"]["geometry"] == out["pypdf_text"]["geometry"])
published = json.loads((render / "render-critic.json").read_text())
print("pypdf run reproduces the shipped render-critic.json issues:",
      pypdf_report["issues"] == published["issues"],
      "| result", pypdf_report["result"] == published["result"],
      "| pages", pypdf_report["pages"] == published["pages"],
      "| crops", pypdf_report["visual_review"]["crops"] == published["visual_review"]["crops"])
for handle in (tracer_dir, pypdf_dir):
    print("left", handle)
PY
```

Block 5, the gated live run. Both modes, as rule 2b requires, plus the
both-or-neither refusal:

```sh
set -eu
MAG_010_RENDER="${MAG_010_RENDER:-$HOME/code/magazine/editions/010/render-2026-09-14T01-49-02/en}"
MAG_CRITIC_RULES_TEXT="${MAG_CRITIC_RULES_TEXT:-${TMPDIR:-/tmp}/wp53biii-tracer-text.json}"
MAG_CRITIC_RULES_ORACLE="${MAG_CRITIC_RULES_ORACLE:-${TMPDIR:-/tmp}/wp53biii-rules-010.json}"
export MAG_010_RENDER MAG_CRITIC_RULES_TEXT MAG_CRITIC_RULES_ORACLE
cargo test --manifest-path mag/Cargo.toml --test critic_rules -- --nocapture 2>&1 \
  | grep -E "^MODE|^COMPARED|^TEXT SOURCE|^test result" || true
MAG_CRITIC_RENDER_DIR="$MAG_010_RENDER" \
  cargo test --manifest-path mag/Cargo.toml --test critic_rules dumps_the_tracer -- --nocapture 2>&1 \
  | grep -E "^MODE|^TRACED|^WROTE|^test result" || true
MAG_CRITIC_RENDER_DIR="$MAG_010_RENDER" MAG_CRITIC_RULES_ORACLE="$MAG_CRITIC_RULES_ORACLE" \
  cargo test --manifest-path mag/Cargo.toml --test critic_rules -- --nocapture 2>&1 \
  | grep -E "^MODE|^COMPARED|^TEXT SOURCE|^test result" || true
MAG_CRITIC_RULES_ORACLE="$MAG_CRITIC_RULES_ORACLE" \
  cargo test --manifest-path mag/Cargo.toml --test critic_rules decides_edition 2>&1 \
  | grep -E "set both|test result" | head -2 || true
```

Block 6, the discrimination probes. Each rewrites one unique string in
`mag/src/critic/rules.rs`, runs the fixture-only suite, and puts the file back
from a pristine copy taken before the first probe:

```sh
set -u
PRISTINE="${TMPDIR:-/tmp}/wp53biii-pristine-rules.rs"
TARGET="$PWD/mag/src/critic/rules.rs"
cp "$TARGET" "$PRISTINE"
probe() {
  cp "$PRISTINE" "$TARGET"
  MAG_PROBE_OLD="$2" MAG_PROBE_NEW="$3" uv run python - "$TARGET" <<'PY'
import os, pathlib, sys
path = pathlib.Path(sys.argv[1])
body = path.read_text()
old, new = os.environ["MAG_PROBE_OLD"], os.environ["MAG_PROBE_NEW"]
assert body.count(old) == 1, (old, body.count(old))
path.write_text(body.replace(old, new))
PY
  result=$(cargo test --manifest-path mag/Cargo.toml --test critic_rules 2>&1 \
    | grep -E "^test result" | head -1)
  echo "PROBE $1 -> $result"
  cp "$PRISTINE" "$TARGET"
}
probe "void min height 96 -> 92" \
  "VOID_MIN_HEIGHT_POINTS: f64 = 96.0;" "VOID_MIN_HEIGHT_POINTS: f64 = 92.0;"
probe "void min width fraction 0.9 -> 0.85" \
  "VOID_MIN_WIDTH_FRACTION: f64 = 0.9;" "VOID_MIN_WIDTH_FRACTION: f64 = 0.85;"
probe "void report limit 3 -> 2" \
  "VOID_REPORT_LIMIT: usize = 3;" "VOID_REPORT_LIMIT: usize = 2;"
probe "void trailing tolerance 16 -> 12" \
  "VOID_TRAILING_TOLERANCE_POINTS: f64 = 16.0;" "VOID_TRAILING_TOLERANCE_POINTS: f64 = 12.0;"
probe "void downsample 8 -> 4" \
  "VOID_DOWNSAMPLE: u32 = 8;" "VOID_DOWNSAMPLE: u32 = 4;"
probe "tail band height tolerance 12 -> 11.9" \
  "TAIL_BAND_HEIGHT_TOLERANCE_POINTS: f64 = 12.0;" "TAIL_BAND_HEIGHT_TOLERANCE_POINTS: f64 = 11.9;"
probe "tail band height tolerance 12 -> 12.2" \
  "TAIL_BAND_HEIGHT_TOLERANCE_POINTS: f64 = 12.0;" "TAIL_BAND_HEIGHT_TOLERANCE_POINTS: f64 = 12.2;"
probe "tail band adjacency 8 -> 7.9" \
  "TAIL_BAND_ADJACENCY_TOLERANCE_POINTS: f64 = 8.0;" "TAIL_BAND_ADJACENCY_TOLERANCE_POINTS: f64 = 7.9;"
probe "tail band symmetry 32 -> 36" \
  "TAIL_BAND_SYMMETRY_TOLERANCE_POINTS: f64 = 32.0;" "TAIL_BAND_SYMMETRY_TOLERANCE_POINTS: f64 = 36.0;"
probe "tail band symmetry 32 -> 28" \
  "TAIL_BAND_SYMMETRY_TOLERANCE_POINTS: f64 = 32.0;" "TAIL_BAND_SYMMETRY_TOLERANCE_POINTS: f64 = 28.0;"
probe "tail gap fraction 0.35 -> 0.3501" \
  "TAIL_GAP_MIN_LIVE_FRACTION: f64 = 0.35;" "TAIL_GAP_MIN_LIVE_FRACTION: f64 = 0.3501;"
probe "stub minimum 5 -> 4" \
  "STUB_BODY_LINE_MINIMUM: usize = 5;" "STUB_BODY_LINE_MINIMUM: usize = 4;"
probe "stub minimum 5 -> 6" \
  "STUB_BODY_LINE_MINIMUM: usize = 5;" "STUB_BODY_LINE_MINIMUM: usize = 6;"
probe "frame minimum run 0.65 -> 0.655" \
  "OPENER_FRAME_MIN_RUN_FRACTION: f64 = 0.65;" "OPENER_FRAME_MIN_RUN_FRACTION: f64 = 0.655;"
probe "frame minimum run 0.65 -> 0.645" \
  "OPENER_FRAME_MIN_RUN_FRACTION: f64 = 0.65;" "OPENER_FRAME_MIN_RUN_FRACTION: f64 = 0.645;"
probe "offset tolerance 2 -> 2.5" \
  "OPENER_OFFSET_TOLERANCE_PIXELS: f64 = 2.0;" "OPENER_OFFSET_TOLERANCE_PIXELS: f64 = 2.5;"
probe "offset tolerance 2 -> 1.0" \
  "OPENER_OFFSET_TOLERANCE_PIXELS: f64 = 2.0;" "OPENER_OFFSET_TOLERANCE_PIXELS: f64 = 1.0;"
probe "crop fidelity mae budget 8 -> 9" \
  "OPENER_CROP_FIDELITY_MAX_RGB_MAE: f64 = 8.0;" "OPENER_CROP_FIDELITY_MAX_RGB_MAE: f64 = 9.0;"
probe "crop fidelity mae budget 8 -> 7" \
  "OPENER_CROP_FIDELITY_MAX_RGB_MAE: f64 = 8.0;" "OPENER_CROP_FIDELITY_MAX_RGB_MAE: f64 = 7.0;"
probe "frame edge budget 0.01 -> 0.014" \
  "OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES: f64 = 0.01;" "OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES: f64 = 0.014;"
probe "frame edge budget 0.01 -> 0.006" \
  "OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES: f64 = 0.01;" "OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES: f64 = 0.006;"
probe "crop margin 24 -> 25" "CROP_MARGIN_POINTS: f64 = 24.0;" "CROP_MARGIN_POINTS: f64 = 25.0;"
probe "caption allowance 48 -> 49" \
  "CROP_CAPTION_ALLOWANCE_POINTS: f64 = 48.0;" "CROP_CAPTION_ALLOWANCE_POINTS: f64 = 49.0;"
probe "stub crop height 220 -> 221" \
  "STUB_CROP_HEIGHT_POINTS: f64 = 220.0;" "STUB_CROP_HEIGHT_POINTS: f64 = 221.0;"
probe "tail fallback crop 300 -> 301" \
  "TAIL_FALLBACK_CROP_HEIGHT_POINTS: f64 = 300.0;" "TAIL_FALLBACK_CROP_HEIGHT_POINTS: f64 = 301.0;"
probe "crop dpi 300 -> 301" "CROP_DPI: u32 = 300;" "CROP_DPI: u32 = 301;"
probe "article page cap 7 -> 8" \
  "DEFAULT_ARTICLE_PAGE_CAP: i64 = 7;" "DEFAULT_ARTICLE_PAGE_CAP: i64 = 8;"
probe "article page cap 7 -> 6" \
  "DEFAULT_ARTICLE_PAGE_CAP: i64 = 7;" "DEFAULT_ARTICLE_PAGE_CAP: i64 = 6;"
probe "editorial cap 2 -> 3" \
  "DEFAULT_EDITORIAL_PAGE_CAP: i64 = 2;" "DEFAULT_EDITORIAL_PAGE_CAP: i64 = 3;"
probe "geometry tolerance 0.75 -> 0.765" \
  "GEOMETRY_TOLERANCE: f64 = 0.75;" "GEOMETRY_TOLERANCE: f64 = 0.765;"
probe "geometry tolerance 0.75 -> 0.735" \
  "GEOMETRY_TOLERANCE: f64 = 0.75;" "GEOMETRY_TOLERANCE: f64 = 0.735;"
probe "opener offset points 4.1 -> 4.2" \
  "OPENER_OFFSET_POINTS: f64 = 4.1;" "OPENER_OFFSET_POINTS: f64 = 4.2;"
probe "frame colour blue 28 -> 29" \
  "OPENER_FRAME_RGB: [u8; 3] = [23, 25, 28];" "OPENER_FRAME_RGB: [u8; 3] = [23, 25, 29];"
probe "offset colour blue 56 -> 57" \
  "OPENER_OFFSET_RGB: [u8; 3] = [240, 87, 56];" "OPENER_OFFSET_RGB: [u8; 3] = [240, 87, 57];"
probe "tail band takes the first match instead of the last" \
  "            matched = Some(index);" \
  "            matched = matched.or(Some(index));"
probe "adjacency drops the below-band arm" \
  "    (void_bottom - band.y_points).abs() <= TAIL_BAND_ADJACENCY_TOLERANCE_POINTS
        || (void.y_points - band_bottom).abs() <= TAIL_BAND_ADJACENCY_TOLERANCE_POINTS" \
  "    (void_bottom - band.y_points).abs() <= TAIL_BAND_ADJACENCY_TOLERANCE_POINTS"
probe "the empty-rectangle break never fires, so a fully inked page reports a zero void" \
  "        if cell[0] == 0 {
            break;
        }" \
  "        if false {
            break;
        }"
probe "largest rectangle prefers a later tie" \
  "                if area > best[0] {" "                if area >= best[0] {"
probe "mask cells drop the ragged edge" \
  "    let width = gray.width.div_ceil(factor);" "    let width = gray.width / factor;"
probe "mask cells demand every pixel inked" \
  "            if gray.data[y as usize * gray.width as usize + x as usize] != 0 {" \
  "            if gray.data[y as usize * gray.width as usize + x as usize] == 0 {"
probe "json truthiness calls zero true" \
  "        Some(Value::Number(number)) => number.as_f64().is_some_and(|value| value != 0.0)," \
  "        Some(Value::Number(_)) => true,"
probe "a4 landscape accepts an empty document" \
  "        !self.media.is_empty()
            && self.media.iter().all(|media| {" \
  "        self.media.iter().all(|media| {"
probe "inside covers move to the last page" \
  "    let inside_cover_pages: BTreeSet<usize> = [2, page_count - 1].into_iter().collect();" \
  "    let inside_cover_pages: BTreeSet<usize> = [2, page_count].into_iter().collect();"
probe "normalisation keeps empty pieces" \
  "    raw.split(is_python_space)
        .filter(|piece| !piece.is_empty())" \
  "    raw.split(is_python_space)"
probe "normalisation splits on rust whitespace" \
  "    raw.split(is_python_space)" "    raw.split(char::is_whitespace)"
probe "crop clamps instead of padding" \
  "            if source_x < 0
                || source_y < 0
                || source_x >= gray.width as i64
                || source_y >= gray.height as i64
            {
                continue;
            }" \
  "            let (source_x, source_y) = (
                source_x.clamp(0, gray.width as i64 - 1),
                source_y.clamp(0, gray.height as i64 - 1),
            );"
probe "border rows demand the exact longest run" \
  "        .filter(|(from, to, _)| to - from + 2 >= longest)" \
  "        .filter(|(from, to, _)| to - from >= longest)"
probe "void width is not clamped to the live area" \
  "    let width_px = (cell[1] as i64 * step).min(live_width);" \
  "    let width_px = cell[1] as i64 * step;"
probe "spread text joins without a separator" \
  "        .collect::<Vec<_>>()
        .join(\" \")
}

#[derive(Debug, Clone)]
pub struct Leg {" \
  "        .collect::<Vec<_>>()
        .join(\"\")
}

#[derive(Debug, Clone)]
pub struct Leg {"
cmp "$PRISTINE" "$TARGET" && echo "RESTORED"
```

Block 7, the live probes, each put back the same way:

```sh
set -u
PRISTINE="${TMPDIR:-/tmp}/wp53biii-pristine-live.rs"
TARGET="$PWD/mag/src/critic/rules.rs"
MAG_010_RENDER="${MAG_010_RENDER:-$HOME/code/magazine/editions/010/render-2026-09-14T01-49-02/en}"
MAG_CRITIC_RULES_ORACLE="${MAG_CRITIC_RULES_ORACLE:-${TMPDIR:-/tmp}/wp53biii-rules-010.json}"
cp "$TARGET" "$PRISTINE"
live() {
  MAG_PROBE_OLD="$2" MAG_PROBE_NEW="$3" uv run python - "$TARGET" <<'PY'
import os, pathlib, sys
path = pathlib.Path(sys.argv[1])
body = path.read_text()
old, new = os.environ["MAG_PROBE_OLD"], os.environ["MAG_PROBE_NEW"]
assert body.count(old) == 1, (old, body.count(old))
path.write_text(body.replace(old, new))
PY
  MAG_CRITIC_RENDER_DIR="$MAG_010_RENDER" MAG_CRITIC_RULES_ORACLE="$MAG_CRITIC_RULES_ORACLE" \
    cargo test --manifest-path mag/Cargo.toml --test critic_rules decides_edition 2>&1 \
    | grep -E "^test result|panicked at" | head -2 | sed "s/^/LIVE PROBE $1: /"
  cp "$PRISTINE" "$TARGET"
}
live "inside covers move to the last page" \
  "    let inside_cover_pages: BTreeSet<usize> = [2, page_count - 1].into_iter().collect();" \
  "    let inside_cover_pages: BTreeSet<usize> = [2, page_count].into_iter().collect();"
live "spread text joins without a separator" \
  "        .collect::<Vec<_>>()
        .join(\" \")
}

#[derive(Debug, Clone)]
pub struct Leg {" \
  "        .collect::<Vec<_>>()
        .join(\"\")
}

#[derive(Debug, Clone)]
pub struct Leg {"
live "spread text uses the y-sorted page text" \
  "            .map(|page| normalized(&spread_text(page)))" \
  "            .map(|page| normalized(&page_text(page)))"
cmp "$PRISTINE" "$TARGET" && echo "RESTORED"
```

Block 8, the oracle-blindness probes. These exist to find out WHICH assertion
catches a given defect, so the grep keeps the failing assertion's label:

```sh
set -u
PRISTINE="${TMPDIR:-/tmp}/wp53biii-pristine-blind.rs"
TARGET="$PWD/mag/src/critic/rules.rs"
MAG_010_RENDER="${MAG_010_RENDER:-$HOME/code/magazine/editions/010/render-2026-09-14T01-49-02/en}"
MAG_CRITIC_RULES_ORACLE="${MAG_CRITIC_RULES_ORACLE:-${TMPDIR:-/tmp}/wp53biii-rules-010.json}"
cp "$TARGET" "$PRISTINE"
blind() {
  MAG_PROBE_OLD="$2" MAG_PROBE_NEW="$3" uv run python - "$TARGET" <<'PY'
import os, pathlib, sys
path = pathlib.Path(sys.argv[1])
body = path.read_text()
old, new = os.environ["MAG_PROBE_OLD"], os.environ["MAG_PROBE_NEW"]
assert body.count(old) == 1, (old, body.count(old))
path.write_text(body.replace(old, new))
PY
  MAG_CRITIC_RENDER_DIR="$MAG_010_RENDER" MAG_CRITIC_RULES_ORACLE="$MAG_CRITIC_RULES_ORACLE" \
    cargo test --manifest-path mag/Cargo.toml --test critic_rules decides_edition 2>&1 \
    | grep -E "^test result|: (decision set|void geometry|crop plan|opener crop fidelity|booklet spreads|live area)" \
    | head -3 | sed "s/^/BLINDNESS $1: /" || true
  cp "$PRISTINE" "$TARGET"
}
blind "crop margin 24 -> 25" \
  "pub const CROP_MARGIN_POINTS: f64 = 24.0;" "pub const CROP_MARGIN_POINTS: f64 = 25.0;"
blind "void min height 96 -> 92" \
  "pub const VOID_MIN_HEIGHT_POINTS: f64 = 96.0;" "pub const VOID_MIN_HEIGHT_POINTS: f64 = 92.0;"
blind "tail band symmetry 32 -> 0" \
  "pub const TAIL_BAND_SYMMETRY_TOLERANCE_POINTS: f64 = 32.0;" \
  "pub const TAIL_BAND_SYMMETRY_TOLERANCE_POINTS: f64 = 0.0;"
cmp "$PRISTINE" "$TARGET" && echo "RESTORED"
```

Replay record, rule 12. The eight blocks were extracted from THIS file by

    uv run python - <<'PY'
    import pathlib, re
    text = pathlib.Path("meta/verification/evidence/WP-5.3b-iii.md").read_text()
    section = text.split("## Commands", 1)[1].split("\n## Tool versions", 1)[0]
    for index, found in enumerate(re.findall(r"```sh\n(.*?)```", section, re.S), 1):
        pathlib.Path(f"/tmp/wp53biii-block{index}.sh").write_text(found)
        print(index, len(found.splitlines()), "lines")
    PY

(dedent the heredoc before running it; it is indented here so the extractor
does not pick itself up as a ninth block) and run with
`bash /tmp/wp53biii-block<n>.sh` from a worktree created at this WP's commit,
at a path this WP was not developed in. **Block 1 is a REGENERATING command
and therefore revision 67's time bomb**: it rewrites
`mag/tests/critic_rules_expected.json` and every file under
`mag/tests/critic_rules_fixtures/`, which WP-5.3c owns from here on. The
moment WP-5.3c hand-edits or replaces any of those files, this block becomes
destructive to replay, and the obligation to mark it SUPERSEDED in this file
falls on WP-5.3c, since I cannot know when that happens. Until then the block
is safe, and its own positive control shows it cannot report clean over a
changed oracle. Two hazards worth naming for the
replayer: block 5 greps for lines that are legitimately absent in the skipped
mode, so each grep carries `|| true` rather than aborting under
`set -o pipefail`; and blocks 6 to 8 MUTATE `mag/src/critic/rules.rs` and put
it back, so nothing else may edit that file while they run. I lost one probe
run to exactly that and re-ran it.
## Tool versions

- rustc/cargo from the repository toolchain; `cargo fmt --check`,
  `cargo clippy --all-targets -D warnings`, `tools/nocomments.py` all clean on
  the rebased tree.
- `uv run python` 3.12.11, Unicode 15.0.0. Pillow 12.3.0, pypdf 6.14.2.
- `pdftoppm` (Poppler) 25.08.0, asserted by `poppler_pinned()` in every test
  that rasterises, the same pin WP-5.2 and WP-5.3b-ii use.
- Corpus: `editions/010/render-2026-09-14T01-49-02/en`, English, 56 reader
  pages, 28 booklet sides, 26 interior sides, 1 cover-booklet side, 22 review
  crops. Same render WP-5.3b-ii measured on.

## Metrics

### The decision-level oracle, live 010

`decides_edition_010_like_python`, MODE full, on the rebased tree:

| measurement | result |
| --- | --- |
| **decision set** `{result, issues[code, severity, message, page]}` identical to Python's | **pass / 4 of 4 issues, exact** |
| void geometry (`largest_void`, `voids`, `tail_band`) identical, per page | **56 of 56** |
| `live_area_points` identical | yes, `[35.0, 14.5, 388.5, 576.0]` |
| booklet spread rows identical | **28 of 28** |
| interior booklet spread rows identical | **26 of 26** |
| cover booklet spread rows identical | **1 of 1** |
| review crop rows (`path`, `page`, `kind`, `subject`, `region_points`, `ppi`) identical | **22 of 22** |
| review crop PIXELS identical to the crops Python shipped in the render | **22 of 22** |
| `article_opener_crop_fidelity` rows identical, `rgb_mae` and the message included | **9 of 9** |
| `article_opener_offsets` identical | 0 of 0, EMPTY-SET agreement, labelled under rule 10 |

Every compared number crosses the oracle as a BIT PATTERN
(`f{:016x}` of `f64::to_bits`, `i{}` for integers), on both sides, because
`serde_json`'s default float parser is not round-trip exact and a fixture
caught it doing exactly that: the figure-crop region `418.99960000000004`
came back from the oracle file as a double whose shortest form is `418.9996`.
The first version of this comparison would have passed on 010 by luck, since
every 010 float happens to round-trip. WP-5.3b-ii's finding, reproduced here
by accident, and the fix is stronger than carrying one field as text.

### The text-source swap, measured at the decision level

Python's `inspect_render` was run TWICE on the same staged inputs, once with
its own pypdf `_PageTexts` and once with `_PageTexts` replaced by the Rust
tracer's text (dumped by `dumps_the_tracer_text_the_python_oracle_needs`).
This separates "is the port faithful" from "does the text source matter":

| measurement | result |
| --- | --- |
| Python-with-pypdf reproduces the SHIPPED `render-critic.json` (issues, result, pages, crops) | **yes**, so the staging is faithful |
| Python-with-tracer decision set == Python-with-pypdf decision set | **equal** |
| Python-with-tracer void geometry == Python-with-pypdf void geometry | **equal** |
| Rust decision set == Python-with-tracer decision set | **equal** |

WP-5.3d's path-B warning was that 010's issue set survives an extractor swap
only by luck. That is now MEASURED at the decision level rather than argued:
on this corpus the swap moves nothing. It remains luck, not a guarantee, which
is why WP-5.3c owes near-threshold fault coverage on all five text fields.

### Fixtures

191 cases in 20 comparison groups plus the AST site list, over 39 committed
fixture files, `sha256
bbd77dc606ec1ed15ceb2f9a5ba2f2ae72881d66ff82512ba4a53f809ef11d2e` for
`mag/tests/critic_rules_expected.json`. Regenerating from block 1 on the
rebased tree leaves every committed byte unchanged (`git status --porcelain`
prints nothing and the digest is the same).

### Discrimination probes

49 mutations of `mag/src/critic/rules.rs`, each a single unique-string
replacement, each run against the fixture-only suite (26 tests). **47 of 49
FAIL under the mutation and PASS restored.** The two that do not
(`inside covers move to the last page`, `spread text joins without a
separator`) are labelled here rather than left to look green, and are covered
by the live probes in block 7 instead.

Every threshold I own is perturbed at the finest granularity its fixtures can
distinguish, in BOTH directions where both sides exist, and each pair's two
expected values are asserted to differ from each other by
`straddle_pairs_differ_from_each_other_and_from_the_fallback`:

| guard | fitting fixture | refusing fixture | one step |
| --- | --- | --- | --- |
| `VOID_MIN_HEIGHT_POINTS` 96.0 | `height_at_threshold` 96.0 pt | `height_below_threshold` 92.0 pt | one 8 px cell = 4 pt |
| `VOID_MIN_WIDTH_FRACTION` 0.9 | `width_at_threshold` 0.9 | `width_below_threshold` 0.85 | one cell of 20 = 0.05 |
| `VOID_TRAILING_TOLERANCE_POINTS` 16.0 | `trailing_at_tolerance` gap 16.0 pt | `trailing_past_tolerance` 20.0 pt | one cell = 4 pt |
| `TAIL_BAND_HEIGHT_TOLERANCE_POINTS` 12.0 | `height_at_tolerance` delta 12.0 | `height_past_tolerance` 12.1 | 0.1 pt |
| `TAIL_BAND_SYMMETRY_TOLERANCE_POINTS` 32.0 | `symmetry_at_tolerance` 32.0 | `symmetry_past_tolerance` 36.0 | one cell = 4 pt |
| `TAIL_BAND_ADJACENCY_TOLERANCE_POINTS` 8.0 | `edge_of_tolerance` 8.0 | `just_past_tolerance` 8.1 | 0.1 pt |
| `TAIL_GAP_MIN_LIVE_FRACTION` 0.35 | `tail_gap_at_threshold` 196.525 pt | `tail_gap_below_threshold` 196.5 | 0.025 pt |
| `STUB_BODY_LINE_MINIMUM` 5 | `no_stub` 5 lines | `stub` 4 lines | one line |
| `OPENER_FRAME_MIN_RUN_FRACTION` 0.65 | `opener_run_130.png` run 130 | `opener_run_129.png` run 129 | one pixel |
| `OPENER_OFFSET_TOLERANCE_PIXELS` 2.0 | `offset_inside_tolerance` delta 1.2 | `offset_outside_tolerance` delta 2.2 | one pixel of offset |
| `OPENER_CROP_FIDELITY_MAX_RGB_MAE` 8.0 | `mae_at_budget` 8.0 | `mae_one_over_budget` 9.0 | one channel unit |
| `OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES` 0.01 | `frame_delta_one_pixel` 0.0069 | `frame_delta_two_pixels` 0.0139 | one pixel at 144 dpi |
| `DEFAULT_ARTICLE_PAGE_CAP` 7 | `cap_boundary` 7 pages | `cap_just_over` 8 pages | one page |
| `GEOMETRY_TOLERANCE` 0.75 | interior at +0.74 pt | cover at +0.76 pt | 0.02 pt |

`DEFAULT_EDITORIAL_PAGE_CAP` 2 is straddled by `editorial_at_cap` (2, silent)
and `editorial_over` (3, faulting), one page apart.

**`SPARSE_INK_RATIO` is the one threshold behind my sites that is NOT tightly
straddled here, and it is INHERITED rather than mine.** `sparse-page` (:302)
fires on `row["sparse"]`, which `_inspect_page` computes from
`0 < ratio < SPARSE_INK_RATIO`; that field and that constant are
WP-5.3b-ii's, and its verification records that moving 0.004 to 0.003 or to
0.006 leaves its suite green. My `sparse_page` and `sparse` fixtures supply the
BOOLEAN as input, so they pin the SITE and say nothing about the threshold.
Labelled rather than inherited quietly: the issue site discriminates, the
ratio behind it does not, and tightening it belongs to whoever next owns
`mag/src/critic/inspect.rs`.

Live probes, block 6, each mutating one line and running the live comparison:

| probe | result |
| --- | --- |
| inside covers move from `{2, n-1}` to `{2, n}` | FAILS at `decision set` |
| `spread_text` joins shows with `""` instead of `" "` | FAILS at `decision set` |
| the spread text uses `page_text` (y-sorted) instead of `spread_text` (paint order) | FAILS at `decision set` |
## Verdicts

No `verdict.json` is produced or consumed by this WP. It adds no comparator
clause, touches no `parity.yaml`, and moves no baseline.

## Fixture provenance: authored from the spec, or transcribed from the output

Revision 57's axis, applied honestly to every row here. **By hand or by script
is not the distinction; where the value came from is.**

**AUTHORED FROM THE SPEC** (the Python SOURCE, not its output):

- `every_threshold_is_read_from_the_python_source_not_from_an_oracle` parses
  `src/magazine/render_critic.py` for its module-level constants and compares
  **24 named thresholds** plus the inline `page_caps.get(slug, 7)` default
  against the Rust constants. No oracle file is involved; a transcription
  error in a constant fails here even where a fixture would inherit it.
  DISCRIMINATES, measured: `OPENER_FRAME_MIN_RUN_FRACTION` 0.65 -> 0.655 fails
  it with `python says 0.65, rust says 0.655`.
- `every_issue_code_in_the_python_critic_is_exercised_by_a_fixture` derives the
  **31 issue sites and 30 distinct codes** from the Python source, TWO WAYS,
  and asserts the two agree before using either: block 1 walks the module with
  `ast` and records every `issue(...)` call with its line and code, and the
  Rust test scans the same source textually. Parsing beats reading for
  enumeration, and the string scan alone would have been a hand method wearing
  a script's clothes. The test then asserts the fixture set covers exactly that
  set in both directions. The count comes from the enumeration rather than beside it,
  which is what revision 38's rule asks; the plan's own prose said "eleven
  issue sites" for the text-derived subset and that number is not this one.
- Every fixture INPUT: the images, the cell grids, the layouts, the spread
  tables, the straddling pairs. Each was constructed to reach a branch I had
  identified by READING the Python, and the branch table below is likewise
  read from the source rather than from the corpus.

**TRANSCRIBED FROM PYTHON'S OUTPUT** (and this is most of the expected data):

- Every expected VALUE in `mag/tests/critic_rules_expected.json` and in the
  live oracle is produced by calling `render_critic.py`'s own functions on the
  fixture inputs. 191 fixture cases and the whole live comparison.
- **What these rows therefore cannot see: a defect in the Python itself.** If
  `_locate_tail_band` picks the wrong run, my fixture records the wrong run as
  expected and the Rust agrees with it. They prove the port REPRODUCES the
  critic; they do not prove the critic is right.
- **What WP-5.3c and WP-5.3g may lean on**: "the two critics agree, field for
  field, on these inputs". Not "this decision is correct". A fault suite that
  wants the second must author its expected issue set from the editorial rule
  the site exists to enforce, not from either critic's output.
- The offset is partial but real: the thresholds and the codes inside those
  transcribed messages are independently pinned by the two spec-authored tests
  above, so the most likely transcription errors (a wrong constant, a wrong
  code, a missing site) are caught without trusting the oracle.

## Rule 10c sweep: expected values that coincide with a fallback

Swept every group for an expected value that the WRONG branch also produces.
Five coincidences found, each now covered:

| coincidence | why it proves only one branch ran | what was added |
| --- | --- | --- |
| `issues: []` in 7 issue-site groups | a function that records nothing produces it too | `no_fixture_group_expects_only_the_fallback` asserts each group holds both a silent and a faulting case |
| `tail_band: null` | the no-run, no-match and early-return paths all produce it | the group is asserted to hold both a match and a miss |
| `live_area_points: null` | the no-body-boxes fallback and a crash both produce it | asserted that the void group holds a live area and its absence |
| `largest_void: null` in `fully_inked` | the SKIP paths (`page_beyond_rasters`, `no_presence_bbox`) produce exactly the same annotation | asserted `fully_inked` differs from `height_at_threshold`, which shares its inputs and differs only in the raster, AND PROBED the separating branch rather than reasoning about it: disabling the `if cell[0] == 0 { break }` guard fails at `annotation for fully_inked` specifically, so that row does discriminate the zero-area path |
| `specs: []` in the crop plan | an unimplemented planner produces it | asserted the group holds an empty and a non-empty plan |

The other half of the answer is the probe suite: 47 of 49 mutations move at
least one expected value OFF its fallback, so no group passes because nothing
runs.

**The INPUT limb of rule 10c, swept separately**, because an expected value
equal to the input proves only that the function did not touch it:

| coincidence with the input | what would pass wrongly | what pins it |
| --- | --- | --- |
| `normalized/plain` returns its input | a no-op normaliser | asserted the group holds rows equal to their input AND rows that are not (`double_space`, `tabs_and_newlines`, the separator rows all collapse), and the `keeps empty pieces` probe fails |
| `editorial_caps/one` and `two` return the declared input | an echo of the input | `one` is asserted to differ from the DEFAULT and `many` (input 9) to EQUAL the default, so the clamp and the read are each shown from a side the other cannot fake |
| `void_geometry/all_blank` reports the whole live area as the void | returning the live box without searching | `height_at_threshold` and friends report voids strictly inside the live box, and the `fully_inked` probe above shows the search runs |
| `printed_tail_bands` echoes each declared height under its page | an identity map | the wrong-branch value here is the EMPTY map, covered under the fallback limb; the height is meant to pass through |
| `crop_writing` `region_points` echo the spec region | an unrounded pass-through | the committed regions are `round(v, 1)` of inputs with four decimals, so echo and expected differ |

Revision 67's precision applies: a coincidence is a defect only when the
correct destination is the OTHER branch, and for `normalized/plain`,
`editorial_caps/two` and `all_blank` the coinciding value IS the correct
answer, so those rows prove what they should. The rows carrying the other side
are the LOAD-BEARING CONTROLS and are named so nobody deletes them as
redundant: `double_space` and `tabs_and_newlines` for normalisation, `one` and
`many` for the editorial cap, `height_at_threshold` for the void search,
`no_stub` against `stub`, `cap_boundary` against `cap_just_over`.

**Straddle pairs**: `straddle_pairs_differ_from_each_other_and_from_the_fallback`
asserts, for the 9 pairs it names plus the offset-tolerance and minimum-run
pairs, that the two sides' expected values DIFFER. It additionally asserts
that the refusing offset case still carries `offset_pixels`, so it is the
tolerance that refused it and not the earlier no-frame refusal, which is the
fallback that would otherwise satisfy `pass: false` for free.
## Which oracle level sees which defect, measured rather than assumed

Revision 58's point, applied to this WP's own oracles. Five levels exist here:

- **L1 decision set**, the live `{result, issues}` comparison on 010.
- **L2 issue-site fixtures**, each `_*_issues` function against Python's own
  output on authored inputs.
- **L3 spec-authored**, the thresholds and issue sites read from the Python
  SOURCE.
- **L4 crop pixels**, 22 crops decoded and compared against the crops Python
  shipped in the render.
- **L5 structural geometry**, the per-page `largest_void`/`voids`/`tail_band`
  and the three spread tables.

Three probes were run specifically to find out which level catches what. The
test asserts L1 first, so a probe failing at a LATER assertion proves L1 passed
with the defect present:

| probe | first failing assertion | what it means |
| --- | --- | --- |
| `CROP_MARGIN_POINTS` 24.0 -> 25.0 | **`crop plan`**, not `decision set` | **L1 is BLIND to crop geometry.** Opener crops are full-page so the margin never reaches `article-opener-crop-fidelity`, and figure, tail and flag crops feed no decision at all. Only L4 and the crop-plan comparison see it |
| `TAIL_BAND_SYMMETRY_TOLERANCE_POINTS` 32.0 -> 0.0 | **`void geometry`**, not `decision set` | **L1 is BLIND to `centered`.** The field is reported and never read by any issue site. Only L5 sees it |
| `VOID_MIN_HEIGHT_POINTS` 96.0 -> 92.0 | `decision set` | L1 DOES see this one: a lowered filter admits another void on 010 and `whitespace-void` fires again |

**The structural conclusion, which matters more than the three rows.** Four of
the 31 issue sites fire on 010 (`whitespace-void`, `article-stub-last-page`,
`tail-art-dropped`, `article-page-cap`). **L1 is therefore blind to 27 of 31
sites by construction**, not by accident: a site that never fires cannot
distinguish a correct implementation from an absent one. The decision-level
oracle is the WP's headline and it is the NARROWEST of the five. What reaches
the other 27 is L2, and what protects L2 from inheriting a wrong constant is
L3. Anyone reading "the decision set matches Python exactly" as covering the
critic should read this table instead.

Applied to the thing WP-5.3c will build: a fault suite that only checks issue
codes will be blind to `centered`, to every crop region, to `largest_void` on
the 52 pages whose voids cross no threshold, and to all 22 crop rasters.
## What is and is not proven

PROVEN:

- **The decision set reproduces Python's on the live edition.**
  `decides_edition_010_like_python` (MODE full): `result` and all four issue
  rows identical, with code, severity, message and page compared exactly.
  DISCRIMINATES: three live probes (inside-cover set, the spread-text join,
  the spread-text RULE) each fail at the `decision set` assertion itself, and
  the `VOID_MIN_HEIGHT_POINTS` probe above does too.
- **Void geometry reproduces Python page for page.** Same test, 56 of 56 rows
  of `largest_void`, `voids` and `tail_band`, plus `live_area_points`.
  DISCRIMINATES: 17 `void_geometry` fixtures pin the threshold pairs, the
  report limit, the skip paths and the fully-inked case, and five probes
  (`VOID_MIN_HEIGHT_POINTS`, `VOID_MIN_WIDTH_FRACTION`, `VOID_REPORT_LIMIT`,
  `VOID_TRAILING_TOLERANCE_POINTS`, `VOID_DOWNSAMPLE`) each fail them.
- **Tail bands reproduce Python.** 8 located bands on 010 inside the 56-row
  comparison, plus 10 `tail_bands` fixtures covering the no-run, no-match,
  first-run, last-run, middle-run and last-match-wins paths and both tolerance
  pairs. DISCRIMINATES: the first-match-wins mutation fails
  `last_match_wins`; both tolerance directions fail their pairs.
- **The opener frame detector and the offset measurement reproduce Python.**
  12 `opener_offset` fixtures and 16 `frame_bbox` rows across two tolerances.
  DISCRIMINATES: the tolerance itself is shown non-inert by asserting the
  near-black frame is INVISIBLE at tolerance 0 and visible at 24; the
  minimum-run pair flips at one pixel; the frame and offset colours each fail
  when one channel moves by one.
- **Crop fidelity reproduces Python**, 9 of 9 rows on 010 including `rgb_mae`
  at four decimals and the rendered message, plus 10 `crop_fidelity` fixtures
  covering both-frames, neither-frame and each one-frame direction.
  DISCRIMINATES: the MAE budget and the frame-edge budget each have a pair one
  step apart, and one fixture fails on the frame leg alone while another fails
  on the MAE leg alone, so neither leg is carried by the other.
- **The crops themselves are pixel-identical to Python's**, 22 of 22, compared
  both against the oracle digests and against the crops sitting in the shipped
  render directory. This is the only level that sees the 300 dpi rasterisation
  and the floor/ceil crop arithmetic; see the blindness table.
- **All 31 issue sites are covered and behave identically**, by the seven
  issue-site fixture groups. `every_issue_code_in_the_python_critic_is_exercised_by_a_fixture`
  derives the site and code sets from the Python source and asserts the
  coverage is exact in both directions, so a site added to the Python without a
  fixture fails the build.
- **Every threshold matches the Python source**, not an oracle file, by
  `every_threshold_is_read_from_the_python_source_not_from_an_oracle`.
- **The text-source swap moves no decision on 010**, measured by running
  Python twice; see `## Metrics`.
- **`mask_cells` reproduces PIL's `Image.reduce` truthiness exactly** on five
  fixtures including ragged sizes and an out-of-bounds crop, asserted cell by
  cell against PIL's actual reduced bytes, and implied on 010 by the 56-page
  geometry agreement. DISCRIMINATES: dropping `div_ceil` and inverting the
  occupancy test each fail.

NOT PROVEN:

- **That any of these decisions is CORRECT.** Every expected value except the
  thresholds and the code set is transcribed from Python's output. See
  `## Fixture provenance`. Owner for correctness: nobody currently; it is an
  editorial question, and WP-5.3c is the natural place to author expected issue
  sets from the rule rather than from either critic.
- **`_write_contact_sheets` (:1384), `_visual_review_status` (:815) and the
  report-dict assembly** are NOT ported. `inspect_render` here returns a
  `Critique` carrying the decisions, rows, spreads, crops and check values;
  it does not build `render-critic.json`. **This is a FINDING for WP-5.5c**,
  escalated in `## Status`.
- **Crop PNG BYTES.** The crops are written with the `png` crate, so the
  pixels match PIL exactly and the bytes do not. `SHA256SUMS` digests those
  files. Owner: WP-5.5c.
- **`article_opener_offsets` on the live edition.** 0 of 0: 010's manifest has
  no `inputs.articles`, so `_manifest_opener_article_ids` returns empty and
  neither offset site can fire. EMPTY-SET agreement in exactly rule 10's
  sense, worth nothing beyond showing nothing was invented. The real evidence
  is the 12 `opener_offset` and 8 `opener_offset_checks` fixtures.
- **`sparse`, `blank`, `ink_free`, `standalone_punctuation_lines` and
  `body_text_lines` themselves** are WP-5.3b-i's and WP-5.3b-ii's; this WP
  consumes them and fixtures the ISSUE SITES they feed, not the fields.
- **`WORD_GAP_FRACTION = 0.25`** is untouched here and still unproven over any
  other value, as WP-5.3b-i's verifier and WP-5.3b-ii both recorded.
- **Anything outside edition 010 English.** Spanish, other editions, other
  page geometries: untested.
- **A search that found nothing**: none is offered as proof of absence.
## Branches of the Python that edition 010 cannot reach

Enumerated by READING `src/magazine/render_critic.py` for branches, then
measured against the corpus, in that order, because reading the corpus for
cases finds only the branches the corpus has. Every line number below was then
VERIFIED against the file by `ast`, not carried from memory: the 29
function-definition citations all resolve to their `def`, and the 31 issue-site
lines are the `ast.Call` nodes of `issue(...)`, which caught four of my own
off-by-ones landing on the code string instead of the call. None of these
numbers is quoted from WP-5.3b-ii's evidence, whose table revision 61 records
as partly wrong; where the two WPs cite the same site they agree because both
now derive from the parse. The two branch sites -ii's verifier found without
rows, the `presence_bbox` ternary and the `window is None` ternary, are in
`_inspect_page` and `_render_pages` and are -ii's; the `not row["presence_bbox"]`
skip that THIS module takes at :1248 has its own row, `no_presence_bbox`.

**Twenty-seven of the 31 issue sites never fire on 010.** Only
`whitespace-void` (page 17), `article-stub-last-page` (page 29),
`tail-art-dropped` and `article-page-cap` do. The 27 silent sites are covered
by the seven issue-site fixture groups, and
`every_issue_code_in_the_python_critic_is_exercised_by_a_fixture` fails the
build if one loses its fixture.

| branch in the Python | 010 | covered by |
| --- | --- | --- |
| all 11 `_imposition_checks` sites (:139-213) | never: 010 imposes correctly | fixture `every_fault` fires all eleven at once, `clean` fires none, `too_small` takes the `page_count < 4` guards, `geometry_tolerance` straddles the A4 tolerance |
| both `article-opener-offset-shadow` sites (:245, :260) | never: `inputs.articles` is absent, so `illustrated_articles` is empty | fixtures `missing_from_toc`, `page_out_of_range`, `page_zero` for the first site, `fails` and `no_frame` for the second |
| `_inspect_opener_offset` ENTIRELY (:1137) | never, same cause | 12 `opener_offset` fixtures: pass, offset straddle, no frame, no orange, right-orange-only, run-at-minimum pair, near-black frame, narrowed border rows |
| `inside-cover-reader-not-blank` (:292) | never: pages 2 and 55 are blank | fixtures `inside_cover_not_blank` / `inside_cover_blank` |
| `blank-page` (:300) | never: no non-cover page is ink-free | fixture `blank_page` |
| `sparse-page` (:302) | never: 0 of 56 pages are sparse | fixture `sparse_page` |
| `orphan-punctuation` (:310) | never: the field is empty on every page | fixture `orphan_punctuation` |
| `article-tail-gap` (:330) and its `continue` (:349) | never: 010's only trailing void sits on page 17, which is not an article's last page | fixtures `tail_gap`, `tail_gap_unknown_slug`, `tail_gap_too_small`, `tail_gap_with_band`, `tail_gap_without_live_area`, and the threshold pair |
| `_abuts_tail_band` second disjunct, void BELOW the band (:1351) | never: all six abutting voids on 010 touch the band's TOP | fixture `top_touches_bottom`, plus the tolerance pair |
| both `_stub_and_tail_issues` out-of-range guards (:378) | never | fixture `out_of_range` |
| `tail-art-dropped` with a missing article or drop reason (:397-398) | never: 010's dropped entry carries both | fixture `dropped_tail_bare` |
| `article-opener-crop-fidelity` (:430) | never: all nine openers pass | fixture `fails`, and five `crop_fidelity` rows that fail on each leg separately |
| the crop-fidelity size-mismatch `continue` (:418) and page-range guard (:413) | never | fixtures `size_mismatch`, `page_out_of_range` |
| `_opener_frame_bbox` returning None (:1070) | never on an opener crop | fixtures `opener_no_frame.png`, `opener_short_run.png`, `opener_run_129.png` at both tolerances |
| both frames None, and exactly one frame present (:1106-1110) | never | fixtures `no_frames`, `one_frame`, `crop_frame_only` |
| all four `_booklet_side_issues` sites (:453, :461, :477, :485) | never: the inside sides are blank and no side is ink-free | fixtures `inside_side_not_blank`, `blank_booklet_side`, `cover_inside_not_blank`, `blank_cover_outside` |
| all five `_contents_issues` sites except the `article-page-cap` review arm | never | 19 `contents` fixtures: four placeholder shapes plus a word-boundary negative, both pagination directions, both folio directions, the cap error/review/declared/boundary/just-over set, and three editorial-cap cases |
| `_declared_editorial_cap` non-default arms (:1216-1218) | never: 010 declares 2, which is the default | 9 `editorial_caps` fixtures: missing, null, 1, 2, 9, 0, negative, float, string |
| `_printed_tail_bands` filters (:275-280) | partly: 010 has one `printed: false` entry with a null height | 9 fixtures adding unknown article, null article, non-dict, missing key, null key, two-for-one-page, and falsy-but-not-false `printed` |
| `_figure_crop_regions` rejection arms (:1422-1429) | never: 010's three figures are all well formed | fixture `figures` carries a non-dict, a bad page type, an out-of-range page, a three-element box and a missing id |
| `_review_crop_plan` tail fallback when the band was not located (:1490) | never: all 8 printed bands are located | fixture `tails` includes a printed band on a page whose `tail_band` is null |
| `_review_crop_plan` page-range guards (:1477, :1485, :1501) | never | fixtures `opener_out_of_range`, `tails` (page 9 of 6), `flags` (page 99) |
| the crop NAME collision loop (:1536) | never: no two 010 crops share page and kind | fixture `dedup_and_degenerate` produces `crop-p03-opener` and `crop-p03-opener-2` |
| the degenerate-box `continue` (:1549) | never | same fixture: two zero-area specs are skipped AND still consume their names, so the following crop keeps its own |
| `_write_review_crops` empty-spec early return (:1514) | never | fixture `empty` in the crop plan, and the writer is not called with an empty list |
| `_largest_empty_rectangle` returning zero area (:1360) | reachable: 5 of 56 pages | also fixture `full` |
| `_locate_tail_band` no-run and no-match returns (:1319, :1327) | never on a page with a declared band | fixtures `no_run`, `no_match`, `height_past_tolerance` |
| `_annotate_void_geometry` returning None for want of boxes (:1235) | never | fixture `no_body_boxes` |
| the `live_width < VOID_DOWNSAMPLE` early return (:1244) | never | fixture `tiny_live_area` |
| `min(cell_width * VOID_DOWNSAMPLE, live_width)` actually CLAMPING (:1266) | reachable on 010, whose live width is not a multiple of 8 | also fixture `live_width_not_a_cell_multiple` |
| `_all_a4_landscape` on an empty document (:866) | never | fixture `too_small` |
| `_render_crop_page` poppler failure (:1593) | not reachable where poppler works on a valid PDF | NOT COVERED. The port raises the same message; nothing asserts it |
| `_manifest_layout` / `_manifest_opener_article_ids` unreadable or malformed manifest (:1018-1025) | never | NOT COVERED, and both return the empty value that the missing-file path returns, so a fixture would be a rule 10c coincidence unless it distinguished them. Stated rather than faked |
## Residuals

- **`mask_cells` is a DECLARED DIVERGENCE from `_annotate_void_geometry`'s
  `presence.crop(live).reduce(VOID_DOWNSAMPLE)`.** Python reduces the binary
  presence mask to PIL's fixed-point block AVERAGE; this port computes each
  cell's OCCUPANCY directly. Argued rather than assumed: the reduced bytes are
  never read as numbers, only for truth (`_largest_empty_rectangle`'s
  `0 if data[...]`, `_locate_tail_band`'s `any(...)`), and for a 0/255 mask at
  factor 8 a single inked pixel reduces to 4 while an empty cell reduces to 0,
  so the two agree on truth everywhere. PINNED TO PIL, not to a sibling: the
  fixture test asserts cell for cell against PIL's ACTUAL reduced bytes on five
  masks including ragged dimensions and an out-of-bounds crop. Why not port the
  arithmetic: it needs `metrics.rs`'s private `division_multiplier` and
  `block_average`, my Owns extension covers `resize` and nothing else in that
  file, and copying them failed `rust_helpers.rs` exactly as the
  duplicate-helper rule intends. **The clean fix for whoever next owns
  `metrics.rs` is to make `reduce` generic over the channel count and
  `pub(crate)`**; that is the fourth instance of the private-sibling wall.
- **`truthy` now exists twice in the tree**, `model/manifest.rs` over
  `serde_yaml::Value` and `critic/rules.rs::json_truthy` over
  `serde_json::Value`. Both encode Python truthiness; neither can import the
  other because the types differ. The name audit fired and I renamed rather
  than allowlisted, which resolves the tooling but not the duplication. **For
  WP-5.1e's registry**: Python truthiness belongs in the shared module,
  parameterised over the value type, alongside `py_repr` and `is_python_space`.
- **`format_g` reproduces `f"{4.1:g}"` and not `%g` in general.** It formats to
  six DECIMALS and trims, where `:g` uses six SIGNIFICANT digits; the two agree
  for every value `OPENER_OFFSET_POINTS` can plausibly hold and diverge above
  1e6. Used at exactly one site, whose message is pinned by fixture and by the
  `4.1 -> 4.2` probe.
- **`Leg` conflates `len(pdf.pages)` with `_PageTexts.page_count`.** Python
  reads the first from the `PdfReader` and the second from the text object, and
  they are always the same object's page count in practice. A PDF whose
  traced-page count differed from its media-box count would diverge. Not
  reachable through `inspect_render`, which builds both from one file.
- **Media boxes come from `lopdf`, which parses PDF reals as f32.** `impose.rs`
  refuses that and recovers the authored text; this port does not, because its
  two consumers tolerate it: the A4 check has a 0.75 pt tolerance, and the crop
  box is floor/ceil'd at 300/72 where 010's values sit 0.0017 from the nearest
  integer. MEASURED, not argued: all 22 crop rows and all 22 crop rasters match
  Python exactly on 010. A page whose media box landed within 1e-4 of a crop
  boundary would diverge. Stated because WP-5.5c reads the same boxes.
- **The 300 dpi scratch directory is removed with `std::fs::remove_dir_all`,**
  mirroring Python's `shutil.rmtree(scratch, ignore_errors=True)`, and
  `inspect_render` removes an existing `render-review` exactly as Python does.
  Both only ever touch directories the caller named; the tests point them at
  temporary directories.
- **The live oracle needs two phases**, because the Python side must be fed the
  RUST tracer's text to isolate the port from the text source. Block 3 runs the
  dump, block 4 the Python oracle, block 5 the comparison. A single-phase
  version would have compared two things at once.
- **`serde_json`'s float parser cost this WP a real fixture failure**, not a
  hypothetical: `418.99960000000004` in the oracle file came back as a
  different double. Every compared number now crosses as a bit pattern on both
  sides. The crate-wide alternative, `serde_json`'s `float_roundtrip` feature,
  was NOT taken: it would make WP-5.3b-ii's
  `serde_json_parses_every_oracle_float_exactly` guard fail, since that guard
  asserts the parser is still inexact, and that file is not mine. **Recorded
  for whoever owns the decision**, since the feature is the right fix and it
  needs one coordinated edit to that guard.
- **`mag/tests/critic_rules.rs` is a `#[path]` test and carries eight
  `#[allow(dead_code)]` lines**, one per include, which revision 64 counts as a
  lint switched off for a mechanical reason. Declared so nobody reads the file
  as lint-clean: the includes are the only mechanism a binary-only crate gives
  an integration test, every test in it is a FILE-level algorithm test, and the
  one MODULE-tree claim this WP makes, that `resize` is reachable in-crate, is
  carried by the binary build rather than by this file (see the Owns note
  above). No in-crate `#[cfg(test)]` module was added to `rules.rs`, so the
  `super::`-not-`crate::` constraint of revision 63 has nothing to bind on.
- The brief offered `editions/010/run-2026-09-13T01-34-51` for re-rendering. It
  was not needed and not copied: the oracle is Python's own `inspect_render`
  run on the PDFs already in `render-2026-09-14T01-49-02/en`, staged into a
  temporary directory so nothing writes into the shipped render.

## Status

`done`, with two findings that belong to others:

1. **WP-5.5c cannot build `render-critic.json` from this WP alone.**
   `_write_contact_sheets`, `_visual_review_status` and the report dict are not
   ported. `_visual_review_status` is trivial. `_write_contact_sheets` is NOT:
   it composes thumbnails with `ImageOps.fit` at BICUBIC and draws labels with
   `ImageDraw.text` in Pillow's default font, which on Pillow 12 is a FreeType
   face, and saves PNG with `optimize=True`. Reproducing those bytes means
   reproducing FreeType's rasterisation and PIL's PNG filter choice. Since
   `SHA256SUMS` digests the contact sheets AND the crops, **WP-5.5c's
   byte-equality oracle has a dependency nobody has costed**, and the same
   applies to this WP's crop PNGs, whose pixels match and whose bytes do not.
   Raised here rather than absorbed.
2. **`metrics.rs::reduce` should become generic and `pub(crate)`**, the fourth
   instance of the private-sibling wall; see `## Residuals`.

Neither blocks this WP. Nothing here is blocked.
