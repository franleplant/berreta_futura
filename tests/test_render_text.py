from types import SimpleNamespace

from magazine.render import _Typesetter, _edition_label, _markdown_blocks, _plain


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


def test_edition_label_comes_from_cover_configuration():
    edition = SimpleNamespace(
        cover={"edition_label": "Private library copy"},
        raw={"distribution": "private"},
    )

    assert _edition_label(edition) == "Private library copy"


def test_private_edition_label_fallback_is_finished_not_prototype():
    edition = SimpleNamespace(cover={}, raw={"distribution": "private"})

    assert _edition_label(edition) == "Private edition - Not for sale"
