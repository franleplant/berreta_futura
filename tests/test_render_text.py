from types import SimpleNamespace

import pytest
import magazine.render as render_module

from magazine import ValidationError
from magazine.cover import _cover_date
from magazine.render import (
    BODY_LEADING,
    FOLIO_BASELINE,
    HEADING_SPACE_BEFORE,
    OUTER_MARGIN,
    READING_MEASURE,
    RUNNING_HEADER_BASELINE_INSET,
    RUNNING_HEADER_SIGNAL_LENGTH,
    SIGNAL_ORANGE,
    TEXT_TOP_INSET,
    FrameUsage,
    _Typesetter,
    _article_tail_ornament_box,
    _content_mode_label,
    _markdown_blocks,
    _opening_sentence,
    _plain,
    _section_label,
    _terminal_balance_plans,
    ArticleBalancePlan,
)


class FixedWidthMetrics:
    @staticmethod
    def stringWidth(text, font, size):
        return len(text)


def test_plain_renders_markdown_link_as_linked_words():
    assert _plain("Read [the source](https://example.com/a/very/long/path).") == "Read the source."
    assert _plain("planner → executor — synthesis") == "planner -> executor — synthesis"


def test_article_tail_ornament_requires_substantial_residual_space():
    assert _article_tail_ornament_box(44, 325, 45, 180) is None

    box = _article_tail_ornament_box(44, 325, 45, 400)

    assert box == (44, 69.0, 325, 214.0)


def test_cover_date_uses_numeric_register_without_separators():
    assert _cover_date("2026-07-21") == "2026 07 21"


def test_lines_breaks_a_token_wider_than_the_text_column():
    typesetter = object.__new__(_Typesetter)
    typesetter.metrics = FixedWidthMetrics()

    assert typesetter.lines("abcdefghij", "Font", 10, 4) == ["abcd", "efgh", "ij"]


def test_running_text_is_truncated_to_its_measured_width():
    typesetter = object.__new__(_Typesetter)
    typesetter.metrics = FixedWidthMetrics()

    assert typesetter.fit_text("abcdefghij", "Font", 10, 7) == "abcd..."


def test_markdown_parser_preserves_fenced_code_lines_and_indentation():
    blocks = list(_markdown_blocks("Before.\n\n```java\nfirst();\n    indented();\n\nlast();\n```\n\nAfter."))

    assert blocks == [
        ("body", "Before."),
        ("code", "first();\n    indented();\n\nlast();"),
        ("body", "After."),
    ]


def test_code_lines_preserve_source_breaks_and_indent_while_wrapping():
    typesetter = object.__new__(_Typesetter)
    typesetter.metrics = FixedWidthMetrics()

    assert typesetter.code_lines("  abcdefghijklmnopqrstuvwxyz\n    xy", "Font", 10, 20) == [
        "  abcdefghijklmnopqr",
        "    stuvwxyz",
        "    xy",
    ]


def test_opening_sentence_is_split_once_without_losing_the_remainder():
    assert _opening_sentence("Every technology arrives twice. Then the work begins.") == (
        "Every technology arrives twice.",
        "Then the work begins.",
    )


def test_every_supported_content_mode_has_an_explicit_label():
    edition = SimpleNamespace(language="en")

    assert _content_mode_label(edition, "selected_extracts") == "Selected extracts"
    assert _content_mode_label(edition, "original_synthesis") == "Original synthesis"


def test_monument_uses_a_fifteen_millimetre_exterior_margin():
    assert round(OUTER_MARGIN * 25.4 / 72, 2) == 15.0


def test_running_header_rule_has_clearance_before_the_text_frame():
    rule_inset = RUNNING_HEADER_BASELINE_INSET + 8.0

    assert TEXT_TOP_INSET - rule_inset >= 18.0


def test_running_header_uses_cover_orange_as_a_short_signal_tick():
    class RecordingPDF:
        def __init__(self):
            self.stroke_colors = []
            self.lines = []

        def setFillColorRGB(self, *_args):
            pass

        def setFont(self, *_args):
            pass

        def drawString(self, *_args):
            pass

        def drawRightString(self, *_args):
            pass

        def setStrokeColorRGB(self, *color):
            self.stroke_colors.append(color)

        def setLineWidth(self, *_args):
            pass

        def line(self, x1, y1, x2, y2):
            self.lines.append((x1, y1, x2, y2))

    typesetter = object.__new__(_Typesetter)
    typesetter.pdf = RecordingPDF()
    typesetter.metrics = FixedWidthMetrics()
    typesetter.edition = SimpleNamespace(publication_name="Berreta Futura")
    typesetter.section = "Light and Dark"
    typesetter.width = 420.0
    typesetter.height = 595.0
    typesetter.left = 44.0
    typesetter.right = OUTER_MARGIN

    typesetter._running_header()

    assert typesetter.pdf.stroke_colors[-1] == SIGNAL_ORANGE
    assert typesetter.pdf.lines[-1][2] - typesetter.pdf.lines[-1][0] == RUNNING_HEADER_SIGNAL_LENGTH


def test_headings_have_deliberate_space_before_them():
    assert HEADING_SPACE_BEFORE["h1"] > HEADING_SPACE_BEFORE["h2"]
    assert HEADING_SPACE_BEFORE["h2"] >= BODY_LEADING
    assert HEADING_SPACE_BEFORE["h3"] >= 10.0


def test_quiet_standard_continuations_use_one_centered_reading_measure():
    typesetter = object.__new__(_Typesetter)
    typesetter.width = 420.0
    typesetter.height = 595.0
    typesetter.left = 44.0
    typesetter.right = OUTER_MARGIN
    typesetter.top = TEXT_TOP_INSET
    typesetter.bottom = 45.0

    typesetter._configure_frames(1, role="continuation")

    assert typesetter.frame_count == 1
    assert typesetter.frame_width == min(READING_MEASURE, typesetter.live_width)
    assert typesetter.frame_left == pytest.approx(
        typesetter.left + (typesetter.live_width - typesetter.frame_width) / 2
    )


def test_folios_share_one_invariant_lower_right_position():
    class RecordingPDF:
        def __init__(self):
            self.right_strings = []

        def setFillColorRGB(self, *_args):
            pass

        def setFont(self, *_args):
            pass

        def drawString(self, *_args):
            pass

        def drawRightString(self, x, y, text):
            self.right_strings.append((x, y, text))

    typesetter = object.__new__(_Typesetter)
    typesetter.pdf = RecordingPDF()
    typesetter.metrics = FixedWidthMetrics()
    typesetter.edition = SimpleNamespace(publication_name="Berreta Futura")
    typesetter.width = 420.0
    typesetter.left = 44.0
    typesetter.right = OUTER_MARGIN
    typesetter.page = 6
    typesetter._folio()
    typesetter.left, typesetter.right = OUTER_MARGIN, 44.0
    typesetter.page = 7
    typesetter._folio()

    assert typesetter.pdf.right_strings == [
        (420.0 - OUTER_MARGIN, FOLIO_BASELINE, "06"),
        (420.0 - OUTER_MARGIN, FOLIO_BASELINE, "07"),
    ]


def test_curated_figures_resolve_exact_semantic_headings_and_allow_none():
    typesetter = object.__new__(_Typesetter)
    blocks = [("h2", "Capability is not deployment"), ("body", "Text.")]

    assert typesetter._validated_figures(blocks, (), "article") == ([], {})

    figure = SimpleNamespace(
        id="capability-reliability",
        anchor="Capability is not deployment",
        layout="evidence_band",
    )
    opener, anchored = typesetter._validated_figures(blocks, (figure,), "article")

    assert opener == []
    assert anchored == {"capability is not deployment": figure}

    prose_figure = SimpleNamespace(
        id="capability-prose",
        anchor="Capability is not deployment",
        layout="evidence_band_prose",
    )
    opener, anchored = typesetter._validated_figures(blocks, (prose_figure,), "article")
    assert opener == []
    assert anchored == {"capability is not deployment": prose_figure}

    for layout in (
        "adaptive_band",
        "compact_band",
        "landscape_plate",
        "landscape_plate_after",
    ):
        specialized_figure = SimpleNamespace(
            id=f"capability-{layout}",
            anchor="Capability is not deployment",
            layout=layout,
        )
        opener, anchored = typesetter._validated_figures(
            blocks,
            (specialized_figure,),
            "article",
        )
        assert opener == []
        assert anchored == {"capability is not deployment": specialized_figure}


def test_curated_figures_enforce_three_asset_cap_and_unique_anchors():
    typesetter = object.__new__(_Typesetter)
    blocks = [("h2", "Section"), ("body", "Text.")]
    rows = [
        SimpleNamespace(id=f"figure-{index}", anchor="Section", layout="column_plate")
        for index in range(4)
    ]

    with pytest.raises(ValidationError, match="maximum is 3"):
        typesetter._validated_figures(blocks, rows, "article")

    with pytest.raises(ValidationError, match="multiple figures at one semantic anchor"):
        typesetter._validated_figures(blocks, rows[:2], "article")


def test_curated_figure_anchor_must_match_one_heading_exactly():
    typesetter = object.__new__(_Typesetter)
    figure = SimpleNamespace(id="figure", anchor="Missing", layout="column_plate")

    with pytest.raises(ValidationError, match="matched 0 article headings"):
        typesetter._validated_figures([("h2", "Section")], (figure,), "article")


def test_terminal_balance_quantizes_a_stranded_tail_without_changing_page_count():
    height = 511.2756
    layout = SimpleNamespace(
        article_pages={"article": 5},
        article_frame_usage={
            "article": (
                FrameUsage(4, 0, height, height),
                FrameUsage(5, 0, 2 * BODY_LEADING, height),
            )
        },
    )

    plan = _terminal_balance_plans(layout)["article"]

    assert plan.page_count == 5
    assert plan.frame_height < height
    assert abs(plan.frame_height / BODY_LEADING - round(plan.frame_height / BODY_LEADING)) < 1e-9


def test_terminal_balance_leaves_an_already_substantial_final_page_alone():
    height = 511.2756
    layout = SimpleNamespace(
        article_pages={"article": 5},
        article_frame_usage={
            "article": (
                FrameUsage(4, 0, height, height),
                FrameUsage(5, 0, height, height),
            )
        },
    )

    assert _terminal_balance_plans(layout) == {}


def test_terminal_balance_can_relax_a_transient_over_cap_draft(monkeypatch):
    height = 511.2756
    probe = SimpleNamespace(
        toc={"article": 5},
        article_pages={"article": 7},
        article_frame_usage={
            "article": (
                FrameUsage(6, 0, height, height),
                FrameUsage(6, 1, height, height),
                FrameUsage(7, 0, 2 * BODY_LEADING, height),
                FrameUsage(7, 1, 0, height),
            )
        },
    )
    monkeypatch.setattr(
        render_module,
        "_terminal_balance_plans",
        lambda layout: {"article": ArticleBalancePlan(7, 8 * BODY_LEADING)},
    )
    calls = []

    def fake_render_pass(target, edition, toc, **kwargs):
        calls.append(kwargs["enforce_page_caps"])
        page_count = 8 if len(calls) == 1 else 7
        return SimpleNamespace(article_pages={"article": page_count})

    monkeypatch.setattr(render_module, "_render_pass", fake_render_pass)

    plans, draft = render_module._balanced_draft(
        SimpleNamespace(), probe, design="monument"
    )

    assert calls == [False, False]
    assert draft.article_pages == {"article": 7}
    assert plans["article"].frame_height == 9 * BODY_LEADING
