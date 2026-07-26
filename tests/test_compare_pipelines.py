from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # `tools` is a script directory, not a package on the path.
    sys.path.insert(0, str(ROOT))

from tools.compare_pipelines import (  # noqa: E402
    A4_LANDSCAPE_MEDIABOX,
    A4_LANDSCAPE_PAGE_BOX,
    A5_PAGE_BOX,
    ADAPTER_PAD_MARKER,
    COLOR_VALUE_TOLERANCE,
    DEFAULT_MAX_CHROMA_MEAN_ABS_DIFFERENCE,
    DEFAULT_TEXT_BAND_TOLERANCE,
    IMPOSITION_POSITION_TOLERANCE,
    MEDIABOX_TOLERANCE,
    PAD_FURNITURE_SLACK,
    PLATE_TEXT_MAX_CHARS,
    REFERENCE_DPI,
    REFERENCE_PALETTE,
    TITLE_PREFIX_CHARS,
    Gate,
    PlacedWord,
    WorkDir,
    aggregate_gates,
    assert_outside_protected,
    band_rows,
    blank_booklet_side_failures,
    build_parser,
    canonical_page_text,
    channel_raster_metrics,
    color_operations,
    color_operator_failures,
    colors_match,
    colour_rows_for,
    compare_colour,
    compare_content,
    compare_geometry,
    compare_imposition,
    compare_ink,
    compare_page_texts,
    compare_visual,
    contents_folios,
    find_signature_pads,
    gate_residuals,
    imposition_mapping,
    inside_cover_report,
    integrity_failures,
    is_chromatic,
    is_within,
    longest_increasing_run,
    measured_imposition,
    merge_surface_gates,
    name_color,
    normalize_text,
    overlap_reason,
    pad_marker_lines,
    parse_bbox_xml,
    placement_mismatches,
    protected_trees,
    raster_is_pure_white,
    raster_page_metrics,
    redistribution_note,
    redistribution_report,
    residual_line,
    resolve_dpi_sensitive_tolerances,
    signature_coda,
    spans_from_texts,
    structural_starts,
    structural_tail_start,
    text_unified_diff,
    title_occurrences,
    tree_hashes,
    visual_rows_for,
)


# --------------------------------------------------------------------------- #
# Write guards: no path may overlap the frozen baseline or output/ either way.
# --------------------------------------------------------------------------- #


def _protected(tmp_path: Path) -> dict[str, Path]:
    (tmp_path / "baseline").mkdir()
    (tmp_path / "repo" / "output").mkdir(parents=True)
    return protected_trees(root=tmp_path / "repo", baseline_root=tmp_path / "baseline")


def test_is_within_covers_identity_and_descent(tmp_path: Path) -> None:
    assert is_within(tmp_path, tmp_path)
    assert is_within(tmp_path / "a" / "b", tmp_path)
    assert not is_within(tmp_path, tmp_path / "a")


@pytest.mark.parametrize("relative", ["baseline", "baseline/002/es", "repo/output", "repo", "."])
def test_work_dir_refuses_every_overlap_with_a_protected_tree(
    tmp_path: Path, relative: str
) -> None:
    protected = _protected(tmp_path)

    with pytest.raises(SystemExit) as excinfo:
        WorkDir(tmp_path / relative, protected)

    assert "Refusing to run" in str(excinfo.value)


def test_work_dir_refuses_a_parent_of_the_baseline_not_only_a_child(tmp_path: Path) -> None:
    # This is the hole that let `--baseline-dir X --work-dir X` overwrite
    # `X/<edition>/<language>/reader.pdf` and then compare it with itself.
    protected = _protected(tmp_path)

    assert overlap_reason("frozen baseline", tmp_path / "baseline", tmp_path) is not None
    assert (
        overlap_reason("frozen baseline", tmp_path / "baseline", tmp_path / "baseline")
        is not None
    )
    assert overlap_reason("frozen baseline", tmp_path / "baseline", tmp_path / "work") is None
    WorkDir(tmp_path / "work", protected)  # the disjoint sibling is accepted


def test_work_dir_resolves_symlinks_before_deciding(tmp_path: Path) -> None:
    protected = _protected(tmp_path)
    sneaky = tmp_path / "sneaky"
    sneaky.symlink_to(tmp_path / "baseline")

    with pytest.raises(SystemExit):
        WorkDir(sneaky, protected)


def test_work_dir_mints_only_paths_under_itself(tmp_path: Path) -> None:
    work = WorkDir(tmp_path / "work", _protected(tmp_path))

    assert work.path("002", "en", "reader.pdf") == tmp_path / "work" / "002" / "en" / "reader.pdf"
    assert work.relative(work.path("002", "en")) == "002/en"
    with pytest.raises(SystemExit) as excinfo:
        work.path("..", "escaped.pdf")
    assert "escapes --work-dir" in str(excinfo.value)


def test_json_report_may_not_land_in_a_protected_tree(tmp_path: Path) -> None:
    protected = _protected(tmp_path)

    assert_outside_protected("--json report", tmp_path / "work" / "r.json", protected)
    with pytest.raises(SystemExit):
        assert_outside_protected("--json report", tmp_path / "baseline" / "r.json", protected)
    with pytest.raises(SystemExit):
        assert_outside_protected(
            "--json report", tmp_path / "repo" / "output" / "r.json", protected
        )


# --------------------------------------------------------------------------- #
# Frozen baseline integrity.
# --------------------------------------------------------------------------- #


def test_tree_hashes_fingerprints_every_file_but_ds_store(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "reader.pdf").write_bytes(b"pdf")
    (tmp_path / ".DS_Store").write_bytes(b"finder noise")

    hashes = tree_hashes(tmp_path)

    assert list(hashes) == ["nested/reader.pdf"]


def test_integrity_failures_reports_modified_added_and_deleted() -> None:
    before = {"a": "1", "b": "2"}
    after = {"a": "9", "c": "3"}

    failures = integrity_failures(before, after)

    assert any("modified during the run: a" in line for line in failures)
    assert any("deleted during the run: b" in line for line in failures)
    assert any("appeared during the run: c" in line for line in failures)
    assert integrity_failures(before, dict(before)) == []


def test_baseline_integrity_violation_fails_the_verdict() -> None:
    verdict = aggregate_gates(
        {"en": [_gate("G1", hard=True, passed=True)]},
        extra_hard_failures=["baseline-integrity"],
    )

    assert verdict["result"] == "fail"
    assert verdict["exit_code"] == 1
    assert verdict["hard_gate_failures"] == ["baseline-integrity"]


# --------------------------------------------------------------------------- #
# Text normalization, position-canonical extraction, per-page text comparison.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  leading and trailing  ", "leading and trailing"),
        ("hard\nwrapped\ttext", "hard wrapped text"),
        ("collapse     every    run", "collapse every run"),
        (" non breaking space ", "non breaking space"),
        (None, ""),
        ("", ""),
        ("\n\n\n", ""),
    ],
)
def test_normalize_text_collapses_whitespace(raw: str | None, expected: str) -> None:
    assert normalize_text(raw) == expected


def test_parse_bbox_xml_reads_word_boxes_and_unescapes_entities() -> None:
    xml = (
        '<doc><page width="419.5" height="595.2">'
        '<word xMin="1.5" yMin="2.5" xMax="3.5" yMax="4.5">TAI &amp; GAO</word>'
        "</page>"
        '<page width="419.5" height="595.2"></page></doc>'
    )

    pages = parse_bbox_xml(xml)

    assert len(pages) == 2
    assert pages[0] == [PlacedWord(1.5, 2.5, 3.5, 4.5, "TAI & GAO")]
    assert pages[1] == []


def _word(text: str, x: float, y: float) -> PlacedWord:
    return PlacedWord(x, y, x + 10, y + 8, text)


def test_canonical_page_text_reads_by_geometry_not_by_content_stream_order() -> None:
    # ReportLab emits the running head and folio first; WeasyPrint's @page margin
    # boxes emit them last.  Both must canonicalize to the same reading order.
    reportlab_order = [
        _word("FEATURE", 44, 45),
        _word("01", 80, 45),
        _word("BERRETA", 42, 569),
        _word("05", 368, 569),
        _word("Software", 44, 87),
        _word("Factories", 180, 87),
    ]
    weasyprint_order = [
        _word("Software", 44, 87),
        _word("Factories", 180, 87),
        _word("FEATURE", 44, 45),
        _word("01", 80, 45),
        _word("BERRETA", 42, 569),
        _word("05", 368, 569),
    ]

    expected = "FEATURE 01 Software Factories BERRETA 05"
    assert canonical_page_text(reportlab_order, tolerance=4.0) == expected
    assert canonical_page_text(weasyprint_order, tolerance=4.0) == expected


def test_band_rows_group_a_line_together_and_keep_lines_apart() -> None:
    words = [
        _word("head", 44, 45.0),
        _word("folio", 368, 47.0),  # 2pt of intra-line jitter
        _word("body", 44, 57.6),  # a genuine next line
    ]

    bands = band_rows(words, tolerance=4.0)

    assert [[word.text for word in band] for band in bands] == [["head", "folio"], ["body"]]


def test_canonical_text_is_insensitive_to_a_whole_page_vertical_offset() -> None:
    words = [_word("head", 44, 45), _word("body", 44, 90), _word("folio", 368, 569)]
    shifted = [PlacedWord(w.x0, w.y0 + 5, w.x1, w.y1 + 5, w.text) for w in words]

    assert canonical_page_text(words, tolerance=4.0) == canonical_page_text(
        shifted, tolerance=4.0
    )


def test_compare_page_texts_reports_first_difference_and_a_diff() -> None:
    baseline = ["cover", "", "contents 04", "editorial body", "feature one"]
    candidate = ["cover", "", "contents 04", "editorial body", "feature ONE"]

    result = compare_page_texts(baseline, candidate)

    assert result["first_differing_page"] == 5
    assert result["differing_pages"] == [5]
    assert result["matching_pages"] == 4
    assert any("feature ONE" in line for line in result["first_difference_diff"])
    assert any(line.startswith("--- baseline") for line in result["first_difference_diff"])


def test_compare_page_texts_on_identical_input_is_clean() -> None:
    pages = ["a", "b", "c"]

    result = compare_page_texts(pages, list(pages))

    assert result["first_differing_page"] is None
    assert result["differing_pages"] == []
    assert result["first_difference_diff"] == []
    assert result["matching_pages"] == 3


def test_compare_page_texts_counts_extra_candidate_pages_as_differing() -> None:
    result = compare_page_texts(["a", "b"], ["a", "b", "c"])

    assert result["differing_pages"] == [3]
    assert result["first_differing_page"] == 3
    assert result["baseline_pages"] == 2
    assert result["candidate_pages"] == 3


def test_text_unified_diff_truncates_long_output() -> None:
    baseline = " ".join(f"word{index}" for index in range(400))
    candidate = " ".join(f"other{index}" for index in range(400))

    diff = text_unified_diff(baseline, candidate, max_lines=10)

    assert len(diff) == 11
    assert diff[-1].startswith("... (")


# --------------------------------------------------------------------------- #
# G1 geometry: full box geometry, not just width and height.
# --------------------------------------------------------------------------- #


def _boxes(count: int, box: tuple[float, ...], *, rotate: int = 0) -> list[dict[str, object]]:
    return [
        {
            "mediabox": box,
            "cropbox": box,
            "trimbox": box,
            "bleedbox": box,
            "artbox": box,
            "rotate": rotate,
            "declared_boxes": ("/MediaBox",),
        }
        for _ in range(count)
    ]


def test_compare_geometry_passes_on_matching_boxes() -> None:
    gate = compare_geometry(
        baseline_reader=_boxes(8, A5_PAGE_BOX),
        candidate_reader=_boxes(8, A5_PAGE_BOX),
        baseline_booklet=_boxes(4, A4_LANDSCAPE_PAGE_BOX),
        candidate_booklet=_boxes(4, A4_LANDSCAPE_PAGE_BOX),
    )

    assert gate.passed
    assert gate.hard
    assert gate.name == "G1"
    assert "0 geometry problem(s)" in gate.summary


def test_compare_geometry_catches_a_shifted_mediabox_origin_of_the_right_size() -> None:
    # The demonstrated false PASS: identical width and height, origin 20pt off, so
    # pdftoppm crops to the box and every reader raster is identical while every
    # imposed booklet side is 20pt out of position.
    shifted = (20.0, 20.0, 20.0 + A5_PAGE_BOX[2], 20.0 + A5_PAGE_BOX[3])
    gate = compare_geometry(
        baseline_reader=_boxes(4, A5_PAGE_BOX),
        candidate_reader=_boxes(4, shifted),
        baseline_booklet=_boxes(2, A4_LANDSCAPE_PAGE_BOX),
        candidate_booklet=_boxes(2, A4_LANDSCAPE_PAGE_BOX),
    )

    assert not gate.passed
    assert any("candidate reader page 1 mediabox" in line for line in gate.failures)
    assert any("baseline [0.0000 0.0000" in line for line in gate.failures)


def test_compare_geometry_catches_a_trimbox_and_a_rotate_divergence() -> None:
    candidate = _boxes(2, A5_PAGE_BOX)
    candidate[1]["trimbox"] = (10.0, 10.0, 400.0, 580.0)
    candidate[0]["rotate"] = 90
    gate = compare_geometry(
        baseline_reader=_boxes(2, A5_PAGE_BOX),
        candidate_reader=candidate,
        baseline_booklet=_boxes(2, A4_LANDSCAPE_PAGE_BOX),
        candidate_booklet=_boxes(2, A4_LANDSCAPE_PAGE_BOX),
    )

    assert not gate.passed
    assert any("page 2 trimbox" in line for line in gate.failures)
    assert any("/Rotate is 90" in line for line in gate.failures)


def test_compare_geometry_flags_page_counts_on_both_surfaces() -> None:
    gate = compare_geometry(
        baseline_reader=_boxes(8, A5_PAGE_BOX),
        candidate_reader=_boxes(7, A5_PAGE_BOX),
        baseline_booklet=_boxes(4, A4_LANDSCAPE_PAGE_BOX),
        candidate_booklet=_boxes(3, A4_LANDSCAPE_PAGE_BOX),
    )

    assert not gate.passed
    assert any("reader page count 7" in line for line in gate.failures)
    assert any("booklet page count 3" in line for line in gate.failures)


def test_compare_geometry_accepts_sub_hundredth_point_drift() -> None:
    drifted = tuple(value + 0.009 for value in A5_PAGE_BOX)
    gate = compare_geometry(
        baseline_reader=_boxes(1, A5_PAGE_BOX),
        candidate_reader=_boxes(1, drifted),
        baseline_booklet=_boxes(1, A4_LANDSCAPE_PAGE_BOX),
        candidate_booklet=_boxes(1, A4_LANDSCAPE_PAGE_BOX),
    )

    assert gate.passed


# --------------------------------------------------------------------------- #
# G2 imposition, measured from the booklet PDF.
# --------------------------------------------------------------------------- #


HALF = A4_LANDSCAPE_MEDIABOX[0] / 2


def _reader_pages(count: int) -> list[list[PlacedWord]]:
    """Four distinguishable reader pages plus a blank one."""
    pages: list[list[PlacedWord]] = []
    for page in range(1, count + 1):
        if page == 2:  # the inside cover is blank in both pipelines
            pages.append([])
            continue
        pages.append([_word(f"page{page}", 44, 100), _word(f"body{page}", 44, 200)])
    return pages


def _impose(reader_pages: list[list[PlacedWord]], *, shift: float = 0.0) -> list[list[PlacedWord]]:
    sides: list[list[PlacedWord]] = []
    for left, right in imposition_mapping(len(reader_pages)):
        side: list[PlacedWord] = []
        for page, origin in ((left, 0.0), (right, HALF)):
            for word in reader_pages[page - 1]:
                side.append(
                    PlacedWord(
                        word.x0 + origin + shift,
                        word.y0,
                        word.x1 + origin + shift,
                        word.y1,
                        word.text,
                    )
                )
        sides.append(side)
    return sides


def test_imposition_mapping_is_saddle_stitch_order() -> None:
    assert imposition_mapping(8) == [(8, 1), (2, 7), (6, 3), (4, 5)]


def test_measured_imposition_reads_the_mapping_out_of_the_booklet() -> None:
    reader = _reader_pages(4)
    rows = measured_imposition(
        booklet_words=_impose(reader), reader_words=reader, plan=imposition_mapping(4)
    )

    assert [row["observed_mapping"] for row in rows] == [[4, 1], [2, 3]]
    assert all(not slot["mismatches"] for row in rows for slot in row["slots"])


def test_measured_imposition_catches_a_uniform_positional_shift() -> None:
    # A reader mediabox origin of (20, 20) leaves every reader raster identical and
    # every text order intact, but shifts every imposed word.  Only a positional
    # comparison against the reader page's own coordinates sees it.
    reader = _reader_pages(4)
    rows = measured_imposition(
        booklet_words=_impose(reader, shift=20.0),
        reader_words=reader,
        plan=imposition_mapping(4),
    )

    assert [row["observed_mapping"] for row in rows] == [[None, None], [2, None]]
    gate = compare_imposition(
        baseline_reader_pages=4,
        candidate_reader_pages=4,
        baseline_measured=measured_imposition(
            booklet_words=_impose(reader), reader_words=reader, plan=imposition_mapping(4)
        ),
        candidate_measured=rows,
        baseline_spreads=_spread_rows(4),
        candidate_spreads=_spread_rows(4),
        baseline_inside_covers=_ink_free(),
        candidate_inside_covers=_ink_free(),
    )
    assert not gate.passed
    assert any("dx +20.000" in line for line in gate.failures)


def test_measured_imposition_catches_two_slots_swapped_left_to_right() -> None:
    reader = _reader_pages(4)
    sides = _impose(reader)
    swapped = [
        PlacedWord(
            word.x0 + (HALF if word.x0 < HALF else -HALF),
            word.y0,
            word.x1 + (HALF if word.x0 < HALF else -HALF),
            word.y1,
            word.text,
        )
        for word in sides[0]
    ]
    rows = measured_imposition(
        booklet_words=[swapped, sides[1]], reader_words=reader, plan=imposition_mapping(4)
    )

    assert rows[0]["observed_mapping"] == [1, 4]


def test_placement_mismatches_reports_a_missing_word_and_a_wrong_position() -> None:
    source = [_word("alpha", 44, 100), _word("beta", 100, 100)]
    imposed = [_word("alpha", 44, 100)]

    problems = placement_mismatches(imposed, source, x_offset=0.0)

    assert any("carries 1 words" in line for line in problems)
    assert placement_mismatches(source, source, x_offset=0.0) == []
    assert placement_mismatches(
        [_word("alpha", 44.04, 100)], [_word("alpha", 44, 100)], x_offset=0.0
    ) == []
    assert placement_mismatches(
        [_word("alpha", 44.3, 100)], [_word("alpha", 44, 100)], x_offset=0.0
    )


def _spread_rows(page_count: int, *, broken_side: int | None = None) -> list[dict[str, object]]:
    rows = []
    for side, (left, right) in enumerate(imposition_mapping(page_count), 1):
        rows.append(
            {
                "side": side,
                "left_reader_page": left,
                "right_reader_page": right,
                "text_order_matches": side != broken_side,
            }
        )
    return rows


def _ink_free(*failures: str) -> dict[str, object]:
    return {"pages": [2, 7], "ink_free": not failures, "failures": list(failures), "detail": {}}


def _measured(page_count: int) -> list[dict[str, object]]:
    reader = _reader_pages(page_count)
    return measured_imposition(
        booklet_words=_impose(reader),
        reader_words=reader,
        plan=imposition_mapping(page_count),
    )


def test_compare_imposition_passes_when_the_measured_mapping_matches() -> None:
    gate = compare_imposition(
        baseline_reader_pages=8,
        candidate_reader_pages=8,
        baseline_measured=_measured(8),
        candidate_measured=_measured(8),
        baseline_spreads=_spread_rows(8),
        candidate_spreads=_spread_rows(8),
        baseline_inside_covers=_ink_free(),
        candidate_inside_covers=_ink_free(),
    )

    assert gate.passed
    assert gate.details["candidate_sides_matching_reader_text"] == 4


def test_compare_imposition_detects_a_side_whose_text_is_out_of_order() -> None:
    gate = compare_imposition(
        baseline_reader_pages=8,
        candidate_reader_pages=8,
        baseline_measured=_measured(8),
        candidate_measured=_measured(8),
        baseline_spreads=_spread_rows(8),
        candidate_spreads=_spread_rows(8, broken_side=3),
        baseline_inside_covers=_ink_free(),
        candidate_inside_covers=_ink_free(),
    )

    assert not gate.passed
    assert any("candidate booklet sides [3]" in line for line in gate.failures)


def test_compare_imposition_detects_a_different_plan_and_a_dirty_inside_cover() -> None:
    gate = compare_imposition(
        baseline_reader_pages=8,
        candidate_reader_pages=12,
        baseline_measured=_measured(8),
        candidate_measured=_measured(12),
        baseline_spreads=_spread_rows(8),
        candidate_spreads=_spread_rows(12),
        baseline_inside_covers=_ink_free(),
        candidate_inside_covers=_ink_free("inside-cover reader page 2 raster is not pure white"),
    )

    assert not gate.passed
    assert any("plan" in line for line in gate.failures)
    assert any("candidate inside-cover reader page 2" in line for line in gate.failures)


# --------------------------------------------------------------------------- #
# Inside covers: strict blankness, looked up by page number.
# --------------------------------------------------------------------------- #


def _raster(path: Path, *, ink: int | None = None) -> Path:
    image = Image.new("L", (12, 12), color=255)
    if ink is not None:
        image.putpixel((5, 5), ink)
    image.save(path, format="PNG")
    return path


def _rows(page_count: int, **overrides: dict[str, object]) -> list[dict[str, object]]:
    rows = [
        {"page": page, "ink_ratio": 0.0, "text_characters": 0} for page in range(1, page_count + 1)
    ]
    for page, values in overrides.items():
        rows[int(page) - 1].update(values)
    return rows


def test_inside_cover_report_accepts_only_pure_white_rasters(tmp_path: Path) -> None:
    rasters = [_raster(tmp_path / f"page-{page:03d}.png") for page in range(1, 5)]

    report = inside_cover_report(_rows(4), rasters, page_count=4)

    assert report["ink_free"]
    assert report["pages"] == [2, 3]
    assert report["detail"]["2"]["pure_white_raster"] is True


def test_inside_cover_report_catches_a_light_tint_that_scores_zero_ink(tmp_path: Path) -> None:
    # WHITE_THRESHOLD is 245, so a 250-grey tint has an ink ratio of exactly 0.0
    # and passes an `ink_ratio == 0.0` test while carrying ink.
    rasters = [_raster(tmp_path / f"page-{page:03d}.png") for page in range(1, 5)]
    _raster(rasters[1], ink=250)

    report = inside_cover_report(_rows(4), rasters, page_count=4)

    assert not report["ink_free"]
    assert any("page 2 raster is not pure white" in line for line in report["failures"])


def test_inside_cover_report_catches_extracted_text_on_an_inside_cover(tmp_path: Path) -> None:
    rasters = [_raster(tmp_path / f"page-{page:03d}.png") for page in range(1, 5)]

    report = inside_cover_report(
        _rows(4, **{"2": {"text_characters": 2}}), rasters, page_count=4
    )

    assert not report["ink_free"]
    assert any("carries 2 extracted characters" in line for line in report["failures"])


def test_inside_cover_report_refuses_to_check_the_wrong_pages(tmp_path: Path) -> None:
    # A short raster list used to make the positional indexing inspect page 2 of a
    # different page's raster; now the gap itself is the failure.
    rasters = [_raster(tmp_path / f"page-{page:03d}.png") for page in range(1, 3)]

    report = inside_cover_report(_rows(4), rasters, page_count=4)

    assert not report["ink_free"]
    assert any("was not inspected" in line for line in report["failures"])


def test_inside_cover_report_needs_at_least_four_pages(tmp_path: Path) -> None:
    rasters = [_raster(tmp_path / "page-001.png")]

    report = inside_cover_report(_rows(1), rasters, page_count=1)

    assert not report["ink_free"]


def test_raster_is_pure_white_is_stricter_than_the_ink_threshold(tmp_path: Path) -> None:
    assert raster_is_pure_white(_raster(tmp_path / "white.png"))
    assert not raster_is_pure_white(_raster(tmp_path / "tinted.png", ink=250))
    assert not raster_is_pure_white(_raster(tmp_path / "inked.png", ink=0))


def test_blank_booklet_side_failures_checks_the_inside_cover_side(tmp_path: Path) -> None:
    measured = [
        {"side": 1, "expected_mapping": [8, 1], "slots": []},
        {"side": 2, "expected_mapping": [2, 7], "slots": []},
    ]
    rasters = [_raster(tmp_path / "side-001.png", ink=0), _raster(tmp_path / "side-002.png")]

    assert (
        blank_booklet_side_failures(
            measured=measured, rasters=rasters, inside_cover_pages=[2, 7], label="candidate"
        )
        == []
    )
    _raster(rasters[1], ink=250)
    failures = blank_booklet_side_failures(
        measured=measured, rasters=rasters, inside_cover_pages=[2, 7], label="candidate"
    )
    assert failures == [
        "candidate booklet side 2 carries both inside covers but is not pure white"
    ]


# --------------------------------------------------------------------------- #
# G3 helpers: filler pages, contents folios, starts and spans.
# --------------------------------------------------------------------------- #


def test_find_signature_pads_matches_a_pad_that_also_carries_furniture() -> None:
    coda = "Berreta Futura — The Systems That Build"
    texts = [
        "cover",
        "",
        "contents",
        "x" * 300 + " Berreta Futura — The Systems That Build " + "y" * 300,
        "Berreta   Futura  —  The Systems That Build",
        "BERRETA FUTURA 32 BERRETA FUTURA — THE SYSTEMS THAT BUILD",
        "Berreta Futura — The Systems That Build 34",
        "",
    ]

    assert find_signature_pads(texts, coda) == [5, 6, 7]
    assert find_signature_pads(texts, "") == []


def test_find_signature_pads_length_bound_excludes_a_body_page_quoting_the_coda() -> None:
    coda = "Berreta Futura — The Systems That Build"
    body = "The editors named this issue Berreta Futura — The Systems That Build because " + (
        "body copy " * 30
    )

    assert find_signature_pads([body], coda) == []


def test_signature_coda_is_the_frozen_historical_literal() -> None:
    # The adapter no longer emits pads; the coda is kept so a *reintroduced* pad is
    # still recognised on the page, and it no longer depends on the adapter's source.
    class Edition:
        publication_name = "Berreta Futura"
        title = "The Systems That Build"

    assert signature_coda(Edition()) == "Berreta Futura — The Systems That Build"


def test_pad_marker_lines_finds_reintroduced_signature_pad_machinery() -> None:
    clean = "def _closing_plates(edition):\n    return 2\n"
    regressed = (
        "def _pad(edition):\n"
        '    html = "<section class=\\"signature-pad\\">"\n'
        "    return html\n"
        '    # signature-pad again\n'
    )

    assert pad_marker_lines(clean) == []
    assert pad_marker_lines(regressed) == [2, 4]


def test_the_adapter_carries_no_signature_pad_machinery() -> None:
    # The invariant the structural package established: the padding loop is gone,
    # replaced by signature arithmetic that closes with plates.
    from tools.compare_pipelines import adapter_source

    assert ADAPTER_PAD_MARKER not in adapter_source()
    assert pad_marker_lines(adapter_source()) == []


def test_contents_folios_reads_interleaved_reportlab_contents() -> None:
    contents = (
        "BERRETA FUTURA 03 ISSUE 2 / CONTENTS Contents "
        "04 EDITORIAL The Expensive Box THE EDITORS "
        "05 FEATURE 01 Software Factories, Light and Dark ADDY OSMANI "
        "10 FEATURE 02 The Building Block Economy MITCHELL HASHIMOTO"
    )

    folios = contents_folios(
        contents,
        ["editorial", "software-factories", "building-block"],
        first_body_page=4,
        page_count=36,
    )

    assert folios == {"editorial": 4, "software-factories": 5, "building-block": 10}


def test_contents_folios_reads_weasyprint_grid_contents() -> None:
    contents = (
        "4 5 9 Contents The Expensive Box Software Factories, Light and Dark "
        "The Building Block Economy 3"
    )

    folios = contents_folios(
        contents,
        ["editorial", "software-factories", "building-block"],
        first_body_page=4,
        page_count=36,
    )

    assert folios == {"editorial": 4, "software-factories": 5, "building-block": 9}


def test_contents_folios_discards_interleaved_label_numbering() -> None:
    contents = (
        "BERRETA FUTURA 03 ISSUE 2 / CONTENTS Contents 04 EDITORIAL A THE EDITORS "
        "05 FEATURE 01 B 10 FEATURE 02 C 13 FEATURE 03 D 19 FEATURE 04 E "
        "22 FEATURE 05 F 25 FEATURE 06 G"
    )

    folios = contents_folios(
        contents,
        ["editorial", "f1", "f2", "f3", "f4", "f5", "f6"],
        first_body_page=4,
        page_count=36,
    )

    assert folios == {
        "editorial": 4,
        "f1": 5,
        "f2": 10,
        "f3": 13,
        "f4": 19,
        "f5": 22,
        "f6": 25,
    }


def test_contents_folios_refuses_to_guess_when_the_count_is_wrong() -> None:
    folios = contents_folios(
        "4 5 9 12 Contents A B C 3",
        ["one", "two", "three"],
        first_body_page=4,
        page_count=36,
    )

    assert folios == {"one": None, "two": None, "three": None}


def test_contents_folios_ignores_numbers_outside_the_body_range() -> None:
    folios = contents_folios(
        "3 2026 4 5 9 Contents A B C 1200",
        ["one", "two", "three"],
        first_body_page=4,
        page_count=36,
    )

    assert folios == {"one": 4, "two": 5, "three": 9}


def test_longest_increasing_run_reports_ambiguity() -> None:
    assert longest_increasing_run([4, 5, 10]) == ([4, 5, 10], 1)
    assert longest_increasing_run([4, 5, 10, 4, 22, 5, 25, 6]) == ([4, 5, 10, 22, 25], 1)
    _, ways = longest_increasing_run([4, 6, 5, 10])
    assert ways == 2
    assert longest_increasing_run([]) == ([], 0)


def test_contents_folios_refuses_to_guess_an_ambiguous_contents_page() -> None:
    folios = contents_folios(
        "4 6 5 10 Contents A B C",
        ["one", "two", "three"],
        first_body_page=4,
        page_count=36,
    )

    assert folios == {"one": None, "two": None, "three": None}


def test_structural_starts_skips_the_contents_page() -> None:
    texts = [
        "cover",
        "",
        "contents 04 The Expensive Box 05 Deep Work",
        "The Expensive Box body",
        "Deep Work opener",
        "Deep Work continued",
    ]
    titles = {"editorial": "The Expensive Box", "deep-work": "Deep Work", "gone": "Absent"}

    assert structural_starts(texts, titles, first_body_page=4) == {
        "editorial": 4,
        "deep-work": 5,
        "gone": None,
    }


def test_structural_starts_ignores_a_title_quoted_inside_an_earlier_page() -> None:
    texts = [
        "cover",
        "",
        "contents",
        "FEATURE 01 5 The Expensive Box " + ("editorial body copy " * 20) + " Deep Work is next",
        "FEATURE 02 5 Deep Work BY SOMEONE opening paragraph",
    ]
    titles = {"editorial": "The Expensive Box", "deep-work": "Deep Work"}

    assert structural_starts(texts, titles, first_body_page=4) == {
        "editorial": 4,
        "deep-work": 5,
    }


def test_structural_starts_survives_an_uppercasing_stylesheet() -> None:
    texts = ["cover", "", "contents", "FEATURE 01 THE EXPENSIVE BOX BY THE EDITORS"]

    assert structural_starts(texts, {"editorial": "The Expensive Box"}, first_body_page=4) == {
        "editorial": 4
    }


def test_title_occurrences_records_every_page_that_mentions_a_title() -> None:
    texts = ["cover", "", "contents The Expensive Box", "The Expensive Box", "as The Expensive Box"]

    assert title_occurrences(texts, {"editorial": "The Expensive Box"}, first_body_page=4) == {
        "editorial": [4, 5]
    }


def test_structural_tail_start_is_the_trailing_plate_run_only() -> None:
    texts = [
        "cover " * 20,
        "",
        "contents " * 20,
        "body " * 60,
        "x",  # a near-empty *interior* page: must not end the last span
        "body " * 60,
        "Systems in Motion",
        "Berreta Futura — Title",
        "",
        "back cover " * 20,
    ]

    assert structural_tail_start(texts, pad_pages=[8]) == 7


def test_spans_from_texts_uses_the_next_start_then_the_trailing_tail() -> None:
    texts = [
        "cover copy that is long enough to look like real content on the page",
        "",
        "contents listing several entries with enough characters to pass the plate test",
        "editorial body text long enough to be a real body page in this fixture",
        "first feature opener text long enough to be a real body page in this fixture",
        "first feature continued text long enough to be a real body page in this fixture",
        "second feature opener text long enough to be a real body page in this fixture",
        "second feature continued long enough to be a real body page in this fixture",
        "Systems in Motion",
        "",
    ]
    starts = {"editorial": 4, "one": 5, "two": 7, "missing": None}

    assert spans_from_texts(texts, starts) == {
        "editorial": 1,
        "one": 2,
        "two": 2,
        "missing": None,
    }


def test_spans_from_texts_is_not_truncated_by_a_near_empty_interior_page() -> None:
    # The candidate's p19 holds two characters and sits inside loop-engineering's
    # span; a forward scan for the first short page reported a span of 1.
    texts = [
        "cover " * 20,
        "",
        "contents " * 20,
        "opener " * 60,
        "19",  # near-empty interior page
        "continued " * 60,
        "Systems in Motion",
        "",
        "back cover " * 20,
    ]

    assert spans_from_texts(texts, {"only": 4}) == {"only": 3}


def test_spans_from_texts_runs_to_the_end_when_no_plate_or_cover_follows() -> None:
    texts = ["x" * 200, "y" * 200, "z" * 200]

    assert spans_from_texts(texts, {"only": 1}, trailing_cover_pages=0) == {"only": 3}
    # With this publication's two trailing cover slots, the last two pages are
    # never body pages even though the back cover carries copy.
    assert spans_from_texts(texts, {"only": 1}) == {"only": 1}


def test_spans_from_texts_refuses_when_the_start_is_inside_the_tail() -> None:
    texts = ["x" * 200, "y" * 200, "", ""]

    assert spans_from_texts(texts, {"only": 3}) == {"only": None}


# --------------------------------------------------------------------------- #
# G3: a refusal is never agreement.
# --------------------------------------------------------------------------- #


def _content_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "text_comparison": compare_page_texts(["a", "b"], ["a", "b"]),
        "baseline_layout_spans": {"one": 5, "two": 3},
        "candidate_layout_spans": {"one": 5, "two": 3},
        "baseline_editorial_pages": 1,
        "candidate_editorial_pages": 1,
        "baseline_pdf_starts": {"one": 5, "two": 10},
        "candidate_pdf_starts": {"one": 5, "two": 10},
        "baseline_pdf_spans": {"one": 5, "two": 3},
        "candidate_pdf_spans": {"one": 5, "two": 3},
        "baseline_folios": {"one": 5, "two": 10},
        "candidate_folios": {"one": 5, "two": 10},
        "candidate_layout_toc": {"one": 5, "two": 10},
        "signature_pad_pages": [],
    }
    base.update(overrides)
    return base


def test_compare_content_passes_on_full_agreement() -> None:
    gate = compare_content(**_content_kwargs())

    assert gate.passed
    assert gate.name == "G3"
    assert gate.hard


def test_compare_content_reports_short_spans_and_filler_pages() -> None:
    gate = compare_content(
        **_content_kwargs(
            text_comparison=compare_page_texts(["a", "b"], ["a", "z"]),
            candidate_layout_spans={"one": 4, "two": 2},
            candidate_pdf_spans={"one": 4, "two": 2},
            signature_pad_pages=[32, 33, 34],
        )
    )

    assert not gate.passed
    assert any("first differing reader page is 2" in line for line in gate.failures)
    assert any("layout span for one: candidate 4 pages, baseline 5" in line for line in gate.failures)
    assert any("PDF span for two: candidate 2 pages, baseline 3" in line for line in gate.failures)
    assert any("signature-pad filler pages at 32, 33, 34" in line for line in gate.failures)


def test_compare_content_flags_a_contents_folio_and_layout_toc_disagreement() -> None:
    gate = compare_content(
        **_content_kwargs(
            candidate_folios={"one": 6, "two": 10}, candidate_pdf_starts={"one": 6, "two": 10}
        )
    )

    assert not gate.passed
    assert any("contents folio for one: candidate 6, baseline 5" in line for line in gate.failures)
    assert any("contents page prints folio 6" in line for line in gate.failures)


def test_compare_content_flags_an_editorial_span_change() -> None:
    gate = compare_content(**_content_kwargs(candidate_editorial_pages=2))

    assert not gate.passed
    assert any("layout editorial span" in line for line in gate.failures)


@pytest.mark.parametrize(
    "clause",
    ["baseline_folios", "candidate_folios", "baseline_pdf_starts", "candidate_pdf_spans"],
)
def test_compare_content_treats_none_as_a_refusal_not_as_agreement(clause: str) -> None:
    # ``contents_folios`` returns {key: None} on an ambiguous contents page and
    # ``structural_starts`` returns None when no page opens with the title; both
    # used to compare equal to the other side's None and be reported as verified.
    kwargs = _content_kwargs()
    both = dict(kwargs[clause])  # type: ignore[arg-type]
    both["one"] = None
    other = clause.replace("baseline", "candidate") if clause.startswith("baseline") else clause.replace("candidate", "baseline")
    kwargs[clause] = both
    kwargs[other] = {**dict(kwargs[other]), "one": None}  # type: ignore[arg-type]

    gate = compare_content(**kwargs)

    assert not gate.passed
    assert any("could not be parsed" in line for line in gate.failures)
    assert any(entry["key"] == "one" for entry in gate.details["unparsed"])


def test_compare_content_flags_a_wholly_unparsed_contents_page() -> None:
    gate = compare_content(
        **_content_kwargs(
            baseline_folios={"one": None, "two": None},
            candidate_folios={"one": None, "two": None},
        )
    )

    assert not gate.passed
    assert len([line for line in gate.failures if "could not be parsed" in line]) == 2
    assert [entry["unparsed_sides"] for entry in gate.details["unparsed"]] == [
        ["baseline", "candidate"],
        ["baseline", "candidate"],
    ]


def test_compare_content_corroborates_folios_against_the_measured_starts() -> None:
    gate = compare_content(
        **_content_kwargs(
            baseline_folios={"one": 6, "two": 10}, candidate_folios={"one": 6, "two": 10}
        )
    )

    assert not gate.passed
    assert any(
        "baseline contents folio for one is 6 but its title opens reader page 5" in line
        for line in gate.failures
    )
    assert any(
        "candidate contents folio for one is 6 but its title opens reader page 5" in line
        for line in gate.failures
    )


def test_compare_content_fails_when_the_adapter_reintroduces_pad_machinery() -> None:
    gate = compare_content(**_content_kwargs(adapter_pad_marker_lines=[259, 263]))

    assert not gate.passed
    assert any(
        "reintroduces signature-pad machinery at source line(s) 259, 263" in line
        for line in gate.failures
    )
    assert gate.details["adapter_pad_marker_lines"] == [259, 263]


# --------------------------------------------------------------------------- #
# G3's summary: a clause count is never a residual.
# --------------------------------------------------------------------------- #


def test_g3_summary_carries_the_clause_count_and_the_page_residual_together() -> None:
    # The failure mode this pins: seventeen clauses retiring took G3 from 18
    # failures to 1 while the surviving aggregate clause still reported 32 of 36
    # pages differing.  "1 failure" alone reads as nearly converged.
    baseline = [f"page {number} body copy" for number in range(1, 37)]
    candidate = list(baseline)
    for index in range(3, 35):  # 32 differing pages, 4 through 35
        candidate[index] = f"page {index + 1} rewritten"

    gate = compare_content(
        **_content_kwargs(text_comparison=compare_page_texts(baseline, candidate))
    )

    assert not gate.passed
    assert len(gate.failures) == 1
    assert "1 clause(s) failing" in gate.summary
    assert "32 of 36 reader pages differ" in gate.summary
    assert gate.details["residual"] == {
        "clause_failures": 1,
        "reader_pages_differing": 32,
        "reader_pages_compared": 36,
        "first_differing_page": 4,
    }


def test_g3_summary_states_the_residual_even_when_the_gate_passes() -> None:
    gate = compare_content(**_content_kwargs())

    assert gate.passed
    assert "0 clause(s) failing" in gate.summary
    assert "0 of 2 reader pages differ" in gate.summary


def test_compare_page_texts_reports_the_differing_count_as_a_scalar() -> None:
    result = compare_page_texts(["a", "b", "c"], ["a", "z", "y"])

    assert result["differing_page_count"] == 2
    assert result["compared_pages"] == 3


# --------------------------------------------------------------------------- #
# Same spans, different distribution: the per-page word-count delta.
# --------------------------------------------------------------------------- #


def _words(count: int) -> str:
    return " ".join("w" for _ in range(count))


def test_redistribution_report_separates_moved_copy_from_wrong_spans() -> None:
    baseline_texts = ["cover", "", "contents", _words(10), _words(184), _words(120)]
    candidate_texts = ["cover", "", "contents", _words(10), _words(124), _words(180)]
    starts = {"clean": 4, "moved": 5, "short": None}
    spans = {"clean": 1, "moved": 2, "short": None}

    rows = redistribution_report(
        baseline_texts=baseline_texts,
        candidate_texts=candidate_texts,
        baseline_starts=starts,
        candidate_starts=starts,
        baseline_spans=spans,
        candidate_spans=spans,
    )
    by_entry = {row["entry"]: row for row in rows}

    assert by_entry["clean"]["start_and_span_match"]
    assert by_entry["clean"]["redistributes"] is False
    assert by_entry["moved"]["redistributes"] is True
    assert by_entry["moved"]["worst_page_delta"] == 60
    assert by_entry["moved"]["total_word_delta"] == 0
    assert by_entry["moved"]["page_word_counts"][0] == {
        "page": 5,
        "baseline_words": 184,
        "candidate_words": 124,
        "delta": -60,
    }
    # An entry whose span is unparsed or disagrees is not "same spans, moved copy".
    assert by_entry["short"]["start_and_span_match"] is False
    assert by_entry["short"]["page_word_counts"] == []


def test_redistribution_report_ignores_entries_whose_spans_disagree() -> None:
    rows = redistribution_report(
        baseline_texts=[_words(50), _words(50)],
        candidate_texts=[_words(90), _words(10)],
        baseline_starts={"one": 1},
        candidate_starts={"one": 1},
        baseline_spans={"one": 2},
        candidate_spans={"one": 1},
    )

    assert rows[0]["start_and_span_match"] is False
    assert rows[0]["redistributes"] is False


def test_redistribution_note_names_the_worst_pages_or_says_nothing() -> None:
    rows = redistribution_report(
        baseline_texts=["cover", "", "contents", _words(184), _words(120)],
        candidate_texts=["cover", "", "contents", _words(124), _words(180)],
        baseline_starts={"one": 4},
        candidate_starts={"one": 4},
        baseline_spans={"one": 2},
        candidate_spans={"one": 2},
    )

    note = redistribution_note(rows)

    assert "1 of 1 entries with matching start and span" in note
    assert "one p4 184->124" in note
    assert redistribution_note([]) == ""


# --------------------------------------------------------------------------- #
# G4 ink geometry and G5 visual metrics.
# --------------------------------------------------------------------------- #


def _ink_row(page: int, ratio: float, bbox: list[int] | None) -> dict[str, object]:
    return {"page": page, "ink_ratio": ratio, "ink_bbox": bbox}


def test_compare_ink_passes_inside_tolerance_and_is_soft() -> None:
    gate = compare_ink(
        baseline_rows=[_ink_row(1, 0.1000, [10, 10, 100, 100])],
        candidate_rows=[_ink_row(1, 0.1005, [12, 10, 100, 101])],
        ratio_tolerance=0.002,
        bbox_tolerance=4,
    )

    assert gate.passed
    assert not gate.hard
    assert gate.details["pages"][0]["ink_bbox_worst_edge_delta"] == 2


def test_compare_ink_reports_every_out_of_tolerance_page() -> None:
    gate = compare_ink(
        baseline_rows=[
            _ink_row(1, 0.10, [10, 10, 100, 100]),
            _ink_row(2, 0.20, [10, 10, 100, 100]),
        ],
        candidate_rows=[
            _ink_row(1, 0.30, [10, 10, 100, 100]),
            _ink_row(2, 0.20, [10, 10, 100, 140]),
        ],
        ratio_tolerance=0.002,
        bbox_tolerance=4,
    )

    assert not gate.passed
    assert len(gate.failures) == 2
    assert gate.details["worst_ink_ratio_delta"] == pytest.approx(0.2)
    assert gate.details["worst_ink_bbox_edge_delta"] == 40


def test_compare_ink_labels_the_booklet_surface_and_counts_sides() -> None:
    gate = compare_ink(
        baseline_rows=[_ink_row(1, 0.10, [10, 10, 100, 100])],
        candidate_rows=[
            _ink_row(1, 0.30, [10, 10, 100, 100]),
            _ink_row(2, 0.30, [10, 10, 100, 100]),
        ],
        ratio_tolerance=0.002,
        bbox_tolerance=4,
        surface="booklet side",
    )

    assert not gate.passed
    assert any("booklet side 1: ink ratio" in line for line in gate.failures)
    assert any("rasterized 2 candidate booklet sides against 1" in line for line in gate.failures)


def test_compare_ink_treats_one_sided_blank_pages_as_a_mismatch() -> None:
    gate = compare_ink(
        baseline_rows=[_ink_row(1, 0.0, None)],
        candidate_rows=[_ink_row(1, 0.0005, [4, 4, 5, 5])],
        ratio_tolerance=0.002,
        bbox_tolerance=4,
    )

    assert not gate.passed


def test_raster_page_metrics_is_zero_for_identical_images() -> None:
    image = Image.new("L", (10, 10), color=255)
    image.putpixel((3, 3), 0)

    metrics = raster_page_metrics(image, image.copy(), channel_threshold=8)

    assert metrics["comparable"] is True
    assert metrics["diff_fraction"] == 0.0
    assert metrics["mean_abs_difference"] == 0.0


def test_raster_page_metrics_threshold_is_exclusive_at_the_boundary() -> None:
    # Deltas of 8 and 255 would also pass an off-by-one threshold; 8 and 9 pin it.
    baseline = Image.new("L", (10, 10), color=255)
    candidate = baseline.copy()
    candidate.putpixel((0, 0), 247)  # delta 8: equal to the threshold, not differing
    candidate.putpixel((1, 1), 246)  # delta 9: exceeds the threshold

    metrics = raster_page_metrics(baseline, candidate, channel_threshold=8)

    assert metrics["diff_fraction"] == pytest.approx(1 / 100)
    assert metrics["mean_abs_difference"] == pytest.approx((8 + 9) / 100)


def test_raster_page_metrics_marks_mismatched_sizes_incomparable() -> None:
    metrics = raster_page_metrics(
        Image.new("L", (10, 10)), Image.new("L", (11, 10)), channel_threshold=8
    )

    assert metrics["comparable"] is False
    assert metrics["diff_fraction"] == 1.0


def test_compare_visual_reports_every_page_never_only_an_average() -> None:
    gate = compare_visual(
        page_metrics=[
            {"page": 1, "diff_fraction": 0.001, "mean_abs_difference": 0.4, "comparable": True},
            {"page": 2, "diff_fraction": 0.4, "mean_abs_difference": 30.0, "comparable": True},
            {"page": 3, "diff_fraction": 0.002, "mean_abs_difference": 0.9, "comparable": True},
        ],
        max_diff_fraction=0.01,
        max_mean_abs_difference=2.0,
        baseline_count=3,
        candidate_count=3,
    )

    assert not gate.passed
    assert not gate.hard
    assert [row["page"] for row in gate.details["pages"]] == [1, 2, 3]
    assert gate.details["worst_pages"][0] == 2
    assert len(gate.failures) == 1


def test_compare_visual_records_a_page_count_mismatch() -> None:
    # A 40-page candidate must not produce a green G5 over 36 compared pages.
    gate = compare_visual(
        page_metrics=[
            {"page": 1, "diff_fraction": 0.0, "mean_abs_difference": 0.0, "comparable": True}
        ],
        max_diff_fraction=0.01,
        max_mean_abs_difference=2.0,
        baseline_count=1,
        candidate_count=2,
    )

    assert not gate.passed
    assert any("candidate has 2, baseline 1" in line for line in gate.failures)


def test_visual_rows_for_marks_pages_only_one_side_has(tmp_path: Path) -> None:
    baseline = [_raster(tmp_path / "b1.png"), _raster(tmp_path / "b2.png")]
    candidate = [_raster(tmp_path / "c1.png")]

    rows = visual_rows_for(
        baseline_rasters=baseline, candidate_rasters=candidate, channel_threshold=8
    )

    assert [row["page"] for row in rows] == [1, 2]
    assert rows[0]["comparable"] is True
    assert rows[1]["comparable"] is False
    assert rows[1]["diff_fraction"] == 1.0


# --------------------------------------------------------------------------- #
# G6 colour: chromatic ink set (exact) and per-channel RGB raster (toleranced).
# --------------------------------------------------------------------------- #


def _rgb(path: Path, *, patch: tuple[int, int, int] | None = None, size: int = 12) -> Path:
    image = Image.new("RGB", (size, size), color=(255, 255, 255))
    if patch is not None:
        image.putpixel((5, 5), patch)
    image.save(path, format="PNG")
    return path


def _ops(*colors: tuple[bytes, tuple[float, ...]]) -> list[tuple[list[float], bytes]]:
    """A tokenised content stream that sets each colour once, plus noise."""
    operations: list[tuple[list[float], bytes]] = [([], b"q"), ([12.0, 4.0], b"Tm")]
    for operator, values in colors:
        operations.append(([*values], operator))
    operations.append(([], b"Q"))
    return operations


def _color_page(page: int, *colors: tuple[bytes, tuple[float, ...]]) -> dict:
    folded = color_operations(_ops(*colors))
    folded["unreadable_streams"] = 0
    folded["chromatic"] = sorted(
        key for key, entry in folded["colors"].items() if entry["chromatic"]
    )
    return {"page": page, **folded}


VIOLET_OP = (b"rg", (0.25, 0.10, 0.43))
INK_OP = (b"rg", (0.055, 0.075, 0.085))
ORANGE_OP = (b"rg", (240 / 255, 87 / 255, 56 / 255))


def test_is_chromatic_separates_a_tinted_grey_from_a_true_neutral() -> None:
    assert is_chromatic((0.88, 0.89, 0.90))  # COOL_GRAY: a tint, and it must be compared
    assert is_chromatic((0.25, 0.10, 0.43))
    assert not is_chromatic((0.0, 0.0, 0.0))
    assert not is_chromatic((1.0, 1.0, 1.0))
    assert not is_chromatic((0.5, 0.5, 0.5))


def test_name_color_resolves_the_declared_palette_and_refuses_a_near_miss() -> None:
    # VIOLET's green channel is 25.5/255, which no hex spelling can hold; the
    # nearest hex, #401A6E, is 26/255 == 0.101961.  That is 0.0020 away -- four
    # times COLOR_VALUE_TOLERANCE -- so it must not be named VIOLET.
    assert name_color((0.25, 0.10, 0.43)) == "VIOLET"
    assert name_color((0.055, 0.075, 0.085)) == "INK"
    assert name_color((0.88, 0.89, 0.90)) == "COOL_GRAY"
    assert name_color((240 / 255, 87 / 255, 56 / 255)) == "SIGNAL_ORANGE"
    assert name_color((0.25, 26 / 255, 0.43)) is None
    assert name_color((0.43, 0.10, 0.25)) is None


def test_color_value_tolerance_is_a_fraction_of_one_eight_bit_level() -> None:
    # It exists to absorb decimal formatting, never a difference that can print.
    assert COLOR_VALUE_TOLERANCE < (1 / 255) / 2
    assert colors_match((0.25, 0.1, 0.43), (0.250001, 0.099999, 0.430000))
    assert not colors_match((0.25, 0.1, 0.43), (0.25, 0.102, 0.43))


def test_color_operations_reads_fill_stroke_and_gray_but_not_gs() -> None:
    # ``gs`` ends in ``s``, and ``rg`` contains ``g``: a regex over raw stream
    # bytes counted 259 ``gs`` operators as grey fills.  Tokenised operands cannot.
    folded = color_operations(
        [
            ([0.25, 0.1, 0.43], b"rg"),
            ([0.055, 0.075, 0.085], b"RG"),
            ([1.0], b"g"),
            (["/GS0"], b"gs"),
            ([1.0, 2.0], b"Tm"),
        ]
    )

    assert set(folded["colors"]) == {
        "0.250000 0.100000 0.430000",
        "0.055000 0.075000 0.085000",
        "1.000000 1.000000 1.000000",
    }
    assert folded["colors"]["0.250000 0.100000 0.430000"]["operators"] == {"fill (rg)": 1}
    assert folded["colors"]["0.055000 0.075000 0.085000"]["operators"] == {"stroke (RG)": 1}
    assert folded["colors"]["1.000000 1.000000 1.000000"]["chromatic"] is False
    assert folded["unmodelled_operators"] == {}


def test_color_operations_records_an_unmodelled_colour_space_rather_than_ignoring_it() -> None:
    folded = color_operations(
        [([0.1, 0.2, 0.3, 0.4], b"k"), (["/CS0"], b"cs"), ([0.25, 0.1, 0.43], b"scn")]
    )

    assert folded["colors"] == {}
    assert folded["unmodelled_operators"] == {"cs": 1, "k": 1, "scn": 1}


def test_color_operator_failures_passes_when_the_same_inks_are_laid_down() -> None:
    pages = [_color_page(1, INK_OP, VIOLET_OP, ORANGE_OP)]

    failures, rows = color_operator_failures(baseline_pages=pages, candidate_pages=pages)

    assert failures == []
    assert rows[0]["identical"] is True
    assert rows[0]["matching_chromatic_inks"] == 3
    assert "0.250000 0.100000 0.430000 (VIOLET)" in rows[0]["candidate_chromatic"]


def test_color_operator_failures_catches_a_hue_error_no_pixel_metric_would() -> None:
    # The gate's whole reason to exist: one accent token emitted with a swapped
    # red and blue channel.  It covers too few pixels to move G4 or G5, and it
    # reaches the reader as a violet printed brick red.
    baseline = [_color_page(1, INK_OP, VIOLET_OP)]
    candidate = [_color_page(1, INK_OP, (b"rg", (0.43, 0.10, 0.25)))]

    failures, rows = color_operator_failures(baseline_pages=baseline, candidate_pages=candidate)

    assert len(failures) == 2
    assert any(
        "candidate sets chromatic ink 0.430000 0.100000 0.250000 (unnamed)" in line
        for line in failures
    )
    assert any(
        "baseline sets chromatic ink 0.250000 0.100000 0.430000 (VIOLET)" in line
        for line in failures
    )
    assert rows[0]["identical"] is False
    assert rows[0]["page"] == 1


def test_color_operator_failures_catches_the_nearest_hex_spelling_of_violet() -> None:
    # #401A6E is the closest hex to VIOLET; it cannot hold 25.5/255 of green.
    # A stylesheet that regresses from percentages to hex must fail here.
    baseline = [_color_page(1, VIOLET_OP)]
    candidate = [_color_page(1, (b"rg", (0x40 / 255, 0x1A / 255, 0x6E / 255)))]

    failures, _ = color_operator_failures(baseline_pages=baseline, candidate_pages=candidate)

    assert failures
    assert any("(VIOLET)" in line for line in failures)


def test_color_operator_failures_ignores_stroke_versus_fill_of_the_same_ink() -> None:
    # Measured: ReportLab strokes the hairline rules WeasyPrint fills, on 22 of 36
    # en reader pages, with byte-identical colour values.  Treating the paint
    # operator as part of the ink's identity would bury a real hue error under 22
    # spurious failures.
    baseline = [_color_page(1, (b"RG", (0.88, 0.89, 0.90)))]
    candidate = [_color_page(1, (b"rg", (0.88, 0.89, 0.90)))]

    failures, rows = color_operator_failures(baseline_pages=baseline, candidate_pages=candidate)

    assert failures == []
    assert rows[0]["baseline_paint_operators"] == {"0.880000 0.890000 0.900000": {"stroke (RG)": 1}}
    assert rows[0]["candidate_paint_operators"] == {"0.880000 0.890000 0.900000": {"fill (rg)": 1}}


def test_color_operator_failures_ignores_white_written_two_ways() -> None:
    # ``1 g`` and ``1 1 1 rg`` are the same neutral; G4/G5 bound achromatic ink.
    baseline = [_color_page(1, (b"rg", (1.0, 1.0, 1.0)), (b"g", (0.0,)))]
    candidate = [_color_page(1, (b"g", (1.0,)))]

    failures, _ = color_operator_failures(baseline_pages=baseline, candidate_pages=candidate)

    assert failures == []


def test_color_operator_failures_is_per_page_not_per_document() -> None:
    # VIOLET on the wrong page is a defect even though the document-wide set of
    # inks is unchanged.  Only a per-page comparison sees it.
    baseline = [_color_page(1, VIOLET_OP), _color_page(2, ORANGE_OP)]
    candidate = [_color_page(1, ORANGE_OP), _color_page(2, VIOLET_OP)]

    failures, rows = color_operator_failures(baseline_pages=baseline, candidate_pages=candidate)

    assert len(failures) == 4
    assert [row["identical"] for row in rows] == [False, False]


def test_color_operator_failures_reports_a_refusal_rather_than_agreement() -> None:
    baseline = [_color_page(1, VIOLET_OP)]
    candidate = [_color_page(1, VIOLET_OP)]
    candidate[0]["unmodelled_operators"] = {"scn": 3}
    candidate[0]["unreadable_streams"] = 1

    failures, rows = color_operator_failures(baseline_pages=baseline, candidate_pages=candidate)

    assert len(failures) == 2
    assert any("a colour space this check does not model" in line for line in failures)
    assert any("could not be tokenised" in line for line in failures)
    assert rows[0]["identical"] is False


def test_color_operator_failures_reports_a_page_count_mismatch() -> None:
    failures, _ = color_operator_failures(
        baseline_pages=[_color_page(1, VIOLET_OP)],
        candidate_pages=[_color_page(1, VIOLET_OP), _color_page(2, VIOLET_OP)],
        surface="booklet side",
    )

    assert any("2 candidate booklet sides against 1 baseline booklet side" in line for line in failures)


def test_channel_raster_metrics_scores_zero_for_an_achromatic_difference() -> None:
    # A shifted glyph edge moves R, G and B by the same amount, so it must not
    # consume any of the hue budget -- that is what makes the metric hue-only.
    baseline = Image.new("RGB", (10, 10), color=(255, 255, 255))
    candidate = baseline.copy()
    candidate.putpixel((0, 0), (100, 100, 100))
    candidate.putpixel((1, 1), (0, 0, 0))

    metrics = channel_raster_metrics(baseline, candidate, channel_threshold=8)

    assert metrics["comparable"] is True
    assert metrics["chroma_mean_abs_difference"] == 0.0
    assert metrics["chroma_diff_fraction"] == 0.0
    assert metrics["channel_mean_abs_difference"] == pytest.approx([(155 + 255) / 100] * 3)
    assert metrics["channel_mean_abs_difference_spread"] == pytest.approx(0.0)


def test_channel_raster_metrics_scores_a_hue_only_difference() -> None:
    baseline = Image.new("RGB", (10, 10), color=(255, 255, 255))
    candidate = baseline.copy()
    candidate.putpixel((0, 0), (255, 155, 255))  # green channel 100 low: pure hue

    metrics = channel_raster_metrics(baseline, candidate, channel_threshold=8)

    assert metrics["channel_mean_abs_difference"] == pytest.approx([0.0, 1.0, 0.0])
    assert metrics["chroma_mean_abs_difference"] == pytest.approx(1.0)
    assert metrics["chroma_diff_fraction"] == pytest.approx(1 / 100)


def test_channel_raster_metrics_cannot_cancel_three_opposite_hue_errors() -> None:
    # Three elements, each wrong in a different channel by the same amount.  The
    # three channel *means* come out identical, so their spread is exactly zero
    # and a per-channel-mean gate would call this page clean.  The per-pixel
    # spread cannot cancel, which is why it is the gated number.
    baseline = Image.new("RGB", (10, 10), color=(255, 255, 255))
    candidate = baseline.copy()
    candidate.putpixel((0, 0), (155, 255, 255))  # too cyan
    candidate.putpixel((5, 0), (255, 155, 255))  # too magenta
    candidate.putpixel((9, 9), (255, 255, 155))  # too yellow

    metrics = channel_raster_metrics(baseline, candidate, channel_threshold=8)

    assert metrics["channel_mean_abs_difference"] == pytest.approx([1.0, 1.0, 1.0])
    assert metrics["channel_mean_abs_difference_spread"] == pytest.approx(0.0)
    assert metrics["chroma_mean_abs_difference"] == pytest.approx(3.0)
    assert metrics["chroma_diff_fraction"] == pytest.approx(3 / 100)


def test_channel_raster_metrics_marks_mismatched_sizes_incomparable() -> None:
    metrics = channel_raster_metrics(
        Image.new("RGB", (10, 10)), Image.new("RGB", (11, 10)), channel_threshold=8
    )

    assert metrics["comparable"] is False
    assert metrics["chroma_mean_abs_difference"] == 255.0


def test_colour_rows_for_marks_pages_only_one_side_has(tmp_path: Path) -> None:
    rows = colour_rows_for(
        baseline_rasters=[_rgb(tmp_path / "b1.png"), _rgb(tmp_path / "b2.png")],
        candidate_rasters=[_rgb(tmp_path / "c1.png")],
        channel_threshold=8,
    )

    assert [row["page"] for row in rows] == [1, 2]
    assert rows[1]["comparable"] is False
    assert rows[1]["chroma_mean_abs_difference"] == 255.0


def _colour_metric(page: int, chroma: float, channels: tuple[float, float, float]) -> dict:
    return {
        "page": page,
        "comparable": True,
        "chroma_mean_abs_difference": chroma,
        "chroma_diff_fraction": 0.0,
        "channel_mean_abs_difference": list(channels),
        "channel_mean_abs_difference_spread": max(channels) - min(channels),
    }


def test_compare_colour_is_soft_and_reports_every_page_never_an_average() -> None:
    pages = [_color_page(page, INK_OP, VIOLET_OP) for page in (1, 2, 3)]
    gate = compare_colour(
        page_metrics=[
            _colour_metric(1, 0.01, (0.1, 0.1, 0.1)),
            _colour_metric(2, 4.0, (6.0, 0.2, 3.0)),  # one badly hued page
            _colour_metric(3, 0.02, (0.1, 0.1, 0.1)),
        ],
        baseline_operators=pages,
        candidate_operators=pages,
        max_chroma_mean_abs_difference=0.5,
        baseline_count=3,
        candidate_count=3,
    )

    assert not gate.passed
    assert not gate.hard
    assert gate.name == "G6"
    assert [row["page"] for row in gate.details["pages"]] == [1, 2, 3]
    assert len(gate.failures) == 1
    assert "reader page 2" in gate.failures[0]
    assert "R 6.000000 G 0.200000 B 3.000000" in gate.failures[0]
    assert gate.details["worst_chroma_page"] == 2
    assert gate.details["pages"][1]["channel_mean_abs_difference"] == {
        "r": 6.0,
        "g": 0.2,
        "b": 3.0,
    }


def test_compare_colour_fails_on_ink_divergence_even_with_a_clean_raster() -> None:
    # The load-bearing case: pixels agree, the ink does not.  No tolerance flag
    # can make this pass.
    gate = compare_colour(
        page_metrics=[_colour_metric(1, 0.0, (0.0, 0.0, 0.0))],
        baseline_operators=[_color_page(1, VIOLET_OP)],
        candidate_operators=[_color_page(1, (b"rg", (0.43, 0.10, 0.25)))],
        max_chroma_mean_abs_difference=1000.0,
        baseline_count=1,
        candidate_count=1,
    )

    assert not gate.passed
    assert gate.details["chromatic_ink_identical_pages"] == 0
    assert gate.details["chromatic_ink_failures"] == 2
    assert "chromatic ink identical on 0 of 1 reader page(s)" in gate.summary


def test_compare_colour_passes_and_states_both_clauses_when_clean() -> None:
    pages = [_color_page(1, INK_OP, VIOLET_OP, ORANGE_OP)]
    gate = compare_colour(
        page_metrics=[_colour_metric(1, 0.1339, (0.4049, 0.4372, 0.4231))],
        baseline_operators=pages,
        candidate_operators=pages,
        max_chroma_mean_abs_difference=0.5,
        baseline_count=1,
        candidate_count=1,
        surface="booklet side",
    )

    assert gate.passed
    assert "chromatic ink identical on 1 of 1 booklet side(s)" in gate.summary
    assert "worst chroma mean abs difference 0.133900/255 on booklet side 1" in gate.summary
    assert gate.details["worst_channel_mean_abs_difference"] == pytest.approx(0.4372)


def test_compare_colour_records_a_page_count_mismatch() -> None:
    gate = compare_colour(
        page_metrics=[_colour_metric(1, 0.0, (0.0, 0.0, 0.0))],
        baseline_operators=[_color_page(1, VIOLET_OP)],
        candidate_operators=[_color_page(1, VIOLET_OP)],
        max_chroma_mean_abs_difference=0.5,
        baseline_count=1,
        candidate_count=2,
    )

    assert not gate.passed
    assert any("candidate has 2, baseline 1" in line for line in gate.failures)


def test_reference_palette_tracks_the_production_renderer() -> None:
    # Imported, not copied: a token retuned in magazine.render must not leave a
    # stale literal here that names the wrong colour in a failure line.
    from magazine import render

    assert REFERENCE_PALETTE["VIOLET"] == tuple(render.VIOLET)
    assert REFERENCE_PALETTE["SIGNAL_ORANGE"] == tuple(render.SIGNAL_ORANGE)
    assert REFERENCE_PALETTE["INK"] == tuple(render.INK)
    assert REFERENCE_PALETTE["COOL_GRAY"] == tuple(render.COOL_GRAY)
    assert REFERENCE_PALETTE["SLATE"] == tuple(render.SLATE)


# --------------------------------------------------------------------------- #
# Tolerance defaults.  Every number a gate compares against is pinned here.
# --------------------------------------------------------------------------- #


def test_every_cli_tolerance_default_is_pinned() -> None:
    """Fail if any tolerance default is loosened without editing this test.

    Every other test in this file passes its tolerances explicitly, so before
    this test existed ``default=0.002`` could become ``default=0.02`` -- a ten-fold
    weakening of G4 on every real run -- and the whole suite stayed green.  These
    are the values quoted in the equivalence report; changing one changes what
    "PASS" means, so it must be a deliberate edit in two places.
    """
    options = build_parser().parse_args(["--edition", "002-unreleased"])

    assert options.ink_ratio_tolerance == 0.002
    assert options.ink_bbox_tolerance is None  # means "4 px at 144 DPI, scaled"
    assert options.pixel_diff_threshold == 8
    assert options.max_diff_fraction == 0.01
    assert options.max_mean_abs_difference == 2.0
    assert options.max_chroma_mean_abs_difference == 0.5
    assert options.text_band_tolerance == 4.0
    assert options.dpi == 144
    assert options.worst_diff_images == 6


def test_unset_ink_bbox_tolerance_resolves_to_four_pixels_at_the_reference_dpi() -> None:
    options = build_parser().parse_args(["--edition", "002-unreleased"])

    notes = resolve_dpi_sensitive_tolerances(options)

    assert options.effective_ink_bbox_tolerance == 4
    assert notes == []


def test_ink_bbox_tolerance_scales_with_dpi_and_says_so() -> None:
    options = build_parser().parse_args(["--edition", "002-unreleased", "--dpi", "288"])

    notes = resolve_dpi_sensitive_tolerances(options)

    assert options.effective_ink_bbox_tolerance == 8
    assert any("scaled from 4 px at 144 DPI to 8 px" in note for note in notes)


def test_module_level_tolerance_constants_are_pinned() -> None:
    """The tolerances that are constants rather than flags, pinned the same way."""
    assert MEDIABOX_TOLERANCE == 0.01
    assert IMPOSITION_POSITION_TOLERANCE == 0.05
    assert DEFAULT_TEXT_BAND_TOLERANCE == 4.0
    assert REFERENCE_DPI == 144
    assert COLOR_VALUE_TOLERANCE == 0.0005
    assert DEFAULT_MAX_CHROMA_MEAN_ABS_DIFFERENCE == 0.5
    assert TITLE_PREFIX_CHARS == 120
    assert PLATE_TEXT_MAX_CHARS == 60
    assert PAD_FURNITURE_SLACK == 48


def test_the_hard_gates_stay_hard_and_the_soft_gates_stay_soft() -> None:
    """G6 is additive: it must not have changed which gates decide the exit code."""
    hard = {
        compare_geometry(
            baseline_reader=[], candidate_reader=[], baseline_booklet=[], candidate_booklet=[]
        ).name,
        compare_content(**_content_kwargs()).name,
    }
    assert hard == {"G1", "G3"}
    assert compare_geometry(
        baseline_reader=[], candidate_reader=[], baseline_booklet=[], candidate_booklet=[]
    ).hard
    assert compare_content(**_content_kwargs()).hard
    assert not compare_ink(
        baseline_rows=[], candidate_rows=[], ratio_tolerance=0.002, bbox_tolerance=4
    ).hard
    assert not compare_visual(
        page_metrics=[], max_diff_fraction=0.01, max_mean_abs_difference=2.0,
        baseline_count=0, candidate_count=0,
    ).hard
    assert not compare_colour(
        page_metrics=[], baseline_operators=[], candidate_operators=[],
        max_chroma_mean_abs_difference=0.5, baseline_count=0, candidate_count=0,
    ).hard
    # Only hard gates may set the exit code, whatever the soft ones say.
    verdict = aggregate_gates(
        {"en": [_gate("G4", hard=False, passed=False), _gate("G6", hard=False, passed=False)]}
    )
    assert verdict["exit_code"] == 0
    assert verdict["soft_gate_failures"] == ["en/G4", "en/G6"]


# --------------------------------------------------------------------------- #
# Gate plumbing: full failure lists, surface merging, aggregation.
# --------------------------------------------------------------------------- #


def _gate(name: str, *, hard: bool, passed: bool, failures: tuple[str, ...] = ()) -> Gate:
    return Gate(name=name, title=name, hard=hard, passed=passed, summary="", failures=failures)


def test_gate_json_keeps_every_failure_line_and_a_count() -> None:
    gate = _gate("G4", hard=False, passed=False, failures=tuple(f"page {n}" for n in range(30)))

    payload = gate.as_json()

    assert payload["failure_count"] == 30
    assert len(payload["failures"]) == 30
    assert json.dumps(payload)


def test_merge_surface_gates_fails_if_either_surface_fails() -> None:
    merged = merge_surface_gates(
        {
            "reader": _gate("G5", hard=False, passed=True),
            "booklet": _gate("G5", hard=False, passed=False, failures=("booklet side 3",)),
        }
    )

    assert merged.name == "G5"
    assert not merged.passed
    assert merged.failures == ("booklet side 3",)
    assert set(merged.details) == {"reader", "booklet"}


def _visual_gate(reader_worst: float, booklet_worst: float) -> Gate:
    def half(worst: float, surface: str) -> Gate:
        return compare_visual(
            page_metrics=[
                {
                    "page": 1,
                    "diff_fraction": worst,
                    "mean_abs_difference": 30.0,
                    "comparable": True,
                }
            ],
            max_diff_fraction=0.01,
            max_mean_abs_difference=2.0,
            baseline_count=1,
            candidate_count=1,
            surface=surface,
        )

    return merge_surface_gates(
        {"reader": half(reader_worst, "reader page"), "booklet": half(booklet_worst, "booklet side")}
    )


def _ink_gate(reader_delta: float, booklet_delta: float) -> Gate:
    def half(delta: float, surface: str) -> Gate:
        return compare_ink(
            baseline_rows=[_ink_row(1, 0.1, [0, 0, 10, 10])],
            candidate_rows=[_ink_row(1, 0.1 + delta, [0, 0, 10, 10])],
            ratio_tolerance=0.002,
            bbox_tolerance=4,
            surface=surface,
        )

    return merge_surface_gates(
        {"reader": half(reader_delta, "reader page"), "booklet": half(booklet_delta, "booklet side")}
    )


def test_gate_residuals_expose_the_residual_behind_every_clause_count() -> None:
    gates = [
        compare_content(**_content_kwargs()),
        _ink_gate(0.1234, 0.0980),
        _visual_gate(0.349, 0.301),
    ]

    residuals = gate_residuals(gates)

    assert residuals["G3"]["reader_pages_differing"] == 0
    assert residuals["G3"]["reader_pages_compared"] == 2
    assert residuals["G4"]["reader"]["worst_ink_ratio_delta"] == pytest.approx(0.1234)
    assert residuals["G4"]["booklet"]["worst_ink_ratio_delta"] == pytest.approx(0.098)
    assert residuals["G5"]["reader"]["worst_diff_fraction"] == pytest.approx(0.349)
    assert residuals["G5"]["booklet"]["out_of_tolerance"] == 1


def _colour_gate(reader_chroma: float, booklet_chroma: float, *, identical: bool = True) -> Gate:
    def half(chroma: float, surface: str) -> Gate:
        baseline = [_color_page(1, VIOLET_OP)]
        candidate = baseline if identical else [_color_page(1, (b"rg", (0.43, 0.1, 0.25)))]
        return compare_colour(
            page_metrics=[_colour_metric(1, chroma, (chroma, 0.0, 0.0))],
            baseline_operators=baseline,
            candidate_operators=candidate,
            max_chroma_mean_abs_difference=0.5,
            baseline_count=1,
            candidate_count=1,
            surface=surface,
        )

    return merge_surface_gates(
        {
            "reader": half(reader_chroma, "reader page"),
            "booklet": half(booklet_chroma, "booklet side"),
        }
    )


def test_gate_residuals_expose_the_colour_residual_for_both_surfaces() -> None:
    residuals = gate_residuals([_colour_gate(0.1339, 0.0690)])

    assert residuals["G6"]["reader"]["worst_chroma_mean_abs_difference"] == pytest.approx(0.1339)
    assert residuals["G6"]["booklet"]["worst_chroma_mean_abs_difference"] == pytest.approx(0.069)
    assert residuals["G6"]["reader"]["chromatic_ink_identical_pages"] == 1
    assert residuals["G6"]["booklet"]["chromatic_ink_compared_pages"] == 1


def test_residual_line_states_the_colour_residual_and_the_ink_agreement() -> None:
    # A clean ink comparison must not be summarised as "colour fine" without the
    # raster number, nor the raster number without the ink count.
    line = residual_line("en", gate_residuals([_colour_gate(0.1339, 0.0690)]))

    assert "G6 worst chroma 0.133900/255 on reader 1" in line
    assert "0.068964/255 on booklet 1" not in line  # booklet number is its own
    assert "0.069000/255 on booklet 1" in line
    assert "chromatic ink identical on 1 of 1 reader, 1 of 1 booklet" in line


def test_merge_surface_gates_fails_g6_when_only_one_surface_diverges() -> None:
    gate = merge_surface_gates(
        {
            "reader": compare_colour(
                page_metrics=[_colour_metric(1, 0.0, (0.0, 0.0, 0.0))],
                baseline_operators=[_color_page(1, VIOLET_OP)],
                candidate_operators=[_color_page(1, VIOLET_OP)],
                max_chroma_mean_abs_difference=0.5,
                baseline_count=1,
                candidate_count=1,
            ),
            "booklet": compare_colour(
                page_metrics=[_colour_metric(1, 0.0, (0.0, 0.0, 0.0))],
                baseline_operators=[_color_page(1, VIOLET_OP)],
                candidate_operators=[_color_page(1, (b"rg", (0.43, 0.1, 0.25)))],
                max_chroma_mean_abs_difference=0.5,
                baseline_count=1,
                candidate_count=1,
                surface="booklet side",
            ),
        }
    )

    assert not gate.passed
    assert gate.details["reader"]["chromatic_ink_identical_pages"] == 1
    assert gate.details["booklet"]["chromatic_ink_identical_pages"] == 0


def test_residual_line_quotes_both_surfaces_for_one_language() -> None:
    # The misquote this prevents: "G4 worst 0.1234, G5 34.9%" with es at 0.1253/35.1%
    # left in the JSON only.  Both languages get one of these lines, always.
    line = residual_line(
        "es",
        gate_residuals(
            [compare_content(**_content_kwargs()), _ink_gate(0.1253, 0.09), _visual_gate(0.351, 0.30)]
        ),
    )

    assert line.startswith("es: ")
    assert "0 clause(s) failing, 0 of 2 reader pages differ" in line
    assert "0.125300 reader" in line
    assert "35.10% reader" in line
    assert "0.090000 booklet" in line
    assert "30.00% booklet" in line


def test_aggregate_gates_passes_only_when_every_hard_gate_passes() -> None:
    verdict = aggregate_gates(
        {
            "en": [_gate("G1", hard=True, passed=True), _gate("G4", hard=False, passed=False)],
            "es": [_gate("G1", hard=True, passed=True)],
        }
    )

    assert verdict["result"] == "pass"
    assert verdict["exit_code"] == 0
    assert verdict["soft_gate_failures"] == ["en/G4"]
    assert verdict["hard_gate_failures"] == []


def test_aggregate_gates_fails_on_a_hard_gate_in_any_language() -> None:
    verdict = aggregate_gates(
        {
            "en": [_gate("G3", hard=True, passed=True)],
            "es": [_gate("G3", hard=True, passed=False)],
        }
    )

    assert verdict["result"] == "fail"
    assert verdict["exit_code"] == 1
    assert verdict["hard_gate_failures"] == ["es/G3"]


def test_gate_as_json_is_serializable_and_stable() -> None:
    gate = Gate(
        name="G3",
        title="Content placement",
        hard=True,
        passed=False,
        summary="one problem",
        failures=("page 5 differs",),
        details={"pages": [1, 2]},
    )

    assert gate.as_json() == {
        "gate": "G3",
        "title": "Content placement",
        "hard": True,
        "result": "fail",
        "summary": "one problem",
        "failure_count": 1,
        "failures": ["page 5 differs"],
        "details": {"pages": [1, 2]},
    }
