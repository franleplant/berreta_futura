from types import SimpleNamespace

from magazine.render import (
    BODY_LEADING,
    HEADING_SPACE_BEFORE,
    OUTER_MARGIN,
    RUNNING_HEADER_BASELINE_INSET,
    RUNNING_HEADER_SECONDARY_OFFSET,
    TEXT_TOP_INSET,
    FrameUsage,
    _Typesetter,
    _content_mode_label,
    _markdown_blocks,
    _opening_sentence,
    _plain,
    _section_label,
    _terminal_balance_plans,
)


class FixedWidthMetrics:
    @staticmethod
    def stringWidth(text, font, size):
        return len(text)


def test_plain_renders_markdown_link_as_linked_words():
    assert _plain("Read [the source](https://example.com/a/very/long/path).") == "Read the source."


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


def test_spanish_colophon_label_is_localized_in_contents_and_opener():
    edition = SimpleNamespace(language="es")

    assert _section_label(edition, "colophon") == "COLOFÓN"


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


def test_continuation_label_has_clearance_before_the_text_frame():
    label_baseline_inset = RUNNING_HEADER_BASELINE_INSET + RUNNING_HEADER_SECONDARY_OFFSET

    assert TEXT_TOP_INSET - label_baseline_inset >= 18.0


def test_headings_have_deliberate_space_before_them():
    assert HEADING_SPACE_BEFORE["h1"] > HEADING_SPACE_BEFORE["h2"]
    assert HEADING_SPACE_BEFORE["h2"] >= BODY_LEADING
    assert HEADING_SPACE_BEFORE["h3"] >= 10.0


def test_terminal_balance_quantizes_a_stranded_tail_without_changing_page_count():
    height = 511.2756
    layout = SimpleNamespace(
        article_pages={"article": 5},
        article_frame_usage={
            "article": (
                FrameUsage(4, 0, height, height),
                FrameUsage(4, 1, height, height),
                FrameUsage(5, 0, 2 * BODY_LEADING, height),
                FrameUsage(5, 1, 0, height),
            )
        },
    )

    plan = _terminal_balance_plans(layout)["article"]

    assert plan.page_count == 5
    assert plan.frame_height < height
    assert abs(plan.frame_height / BODY_LEADING - round(plan.frame_height / BODY_LEADING)) < 1e-9


def test_terminal_balance_leaves_an_already_used_second_column_alone():
    height = 511.2756
    layout = SimpleNamespace(
        article_pages={"article": 5},
        article_frame_usage={
            "article": (
                FrameUsage(4, 0, height, height),
                FrameUsage(4, 1, height, height),
                FrameUsage(5, 0, height, height),
                FrameUsage(5, 1, 4 * BODY_LEADING, height),
            )
        },
    )

    assert _terminal_balance_plans(layout) == {}
