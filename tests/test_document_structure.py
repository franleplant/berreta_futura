"""The gates read the same document the renderer typesets.

Edition 003's primary source vocabulary includes ordered lists, nested
bullets, and thematic breaks -- constructs the old hand-rolled gate scanners
folded silently into paragraphs while the reader printed real ``<ol>``,
nested ``<ul>`` and ``<hr>`` markup.  These tests pin the agreement: for one
parsed document, the content view (:func:`visible_blocks`, which the
code-fence check in :mod:`magazine.code_blocks` reads), the translation view
(:func:`block_signature`) and the semantic HTML the renderer emits all
describe the same structure.
"""

import unittest

from magazine.document_structure import block_signature, visible_blocks
from magazine.html_edition import _render_block
from magazine.publication_document import parse_publication_document


MANUSCRIPT = """\
# Title

An opening paragraph with [a link](https://example.com/x) and *emphasis*.

1. First point
2. Second point

---

- Outer point
  - Inner point

> A quoted claim.
>
> Its continuation.

```python
if ready:
    publish()
```

4. Renumbered point
"""


class GateRendererAgreementTests(unittest.TestCase):
    def setUp(self):
        self.document = parse_publication_document(MANUSCRIPT)

    def test_visible_blocks_carry_every_reader_visible_word_and_no_furniture(self):
        blocks = visible_blocks(self.document.blocks)

        self.assertEqual(blocks, [
            ("h1", "Title"),
            ("p", "An opening paragraph with a link and emphasis."),
            ("ordered", "First point"),
            ("ordered", "Second point"),
            # The thematic break contributes nothing visible.
            ("bullet", "Outer point"),
            ("bullet", "Inner point"),
            ("quote", "A quoted claim."),
            ("quote", "Its continuation."),
            ("code", "if ready:\n    publish()\n"),
            ("ordered", "Renumbered point"),
        ])

    def test_block_signature_spells_the_structure_the_renderer_prints(self):
        self.assertEqual(block_signature(self.document.blocks), [
            "h1",
            "body",
            "ol[body;body]",
            "rule",
            "ul[body,ul[body]]",
            "quote[body,body]",
            "code",
            "ol@4[body]",
        ])

    def test_the_renderer_agrees_an_ordered_list_is_ordered(self):
        # The historical failure: the gates read `1. …` as a paragraph while
        # the reader printed an <ol>.  Both now come from the same block.
        ordered = self.document.blocks[2]
        renumbered = self.document.blocks[7]

        self.assertTrue(_render_block(ordered).startswith("<ol>"))
        self.assertTrue(_render_block(renumbered).startswith('<ol start="4">'))
        self.assertEqual(_render_block(self.document.blocks[3]), "<hr>")

    def test_a_flattened_ordered_list_no_longer_matches_the_signature(self):
        flattened = parse_publication_document(
            MANUSCRIPT.replace("1. First point\n2. Second point", "First point. Second point.")
        )

        self.assertNotEqual(
            block_signature(self.document.blocks), block_signature(flattened.blocks)
        )

    def test_a_dropped_thematic_break_no_longer_matches_the_signature(self):
        without_break = parse_publication_document(MANUSCRIPT.replace("---\n\n", ""))

        self.assertNotEqual(
            block_signature(self.document.blocks), block_signature(without_break.blocks)
        )

    def test_a_regrouped_nested_list_no_longer_matches_the_signature(self):
        regrouped = parse_publication_document(
            MANUSCRIPT.replace("- Outer point\n  - Inner point", "- Outer point\n- Inner point")
        )

        self.assertNotEqual(
            block_signature(self.document.blocks), block_signature(regrouped.blocks)
        )

    def test_a_changed_ordered_start_number_no_longer_matches_the_signature(self):
        restarted = parse_publication_document(
            MANUSCRIPT.replace("4. Renumbered point", "1. Renumbered point")
        )

        self.assertNotEqual(
            block_signature(self.document.blocks), block_signature(restarted.blocks)
        )


if __name__ == "__main__":
    unittest.main()
