from magazine.render import _Typesetter, _plain


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
