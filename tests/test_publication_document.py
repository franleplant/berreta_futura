from collections.abc import Mapping
from pathlib import Path

import pytest

from magazine.publication_document import (
    BlockQuote,
    DocumentParseError,
    Emphasis,
    FencedCode,
    Heading,
    HorizontalRule,
    InlineCode,
    Link,
    ListBlock,
    ListItem,
    Paragraph,
    Strong,
    Text,
    parse_publication_document,
)


def test_parse_publication_document_preserves_semantics_and_document_order():
    document = parse_publication_document(
        "---\nsource_id: artículo-ñ\ntags: [IA, investigación]\n---\n"
        "# Título — café\n\n"
        "Una *énfasis* y **fuerza**, [enlace](https://example.test/a?q=ñ) y `código`.\n\n"
        "> Cita con **peso**.\n\n"
        "- Primer elemento\n- Segundo con `id`\n\n"
        "3. Tercero\n4. Cuarto\n\n"
        "```python\n  print('¡hola!')\n```\n"
    )

    assert isinstance(document.metadata, Mapping)
    assert document.metadata == {"source_id": "artículo-ñ", "tags": ("IA", "investigación")}
    assert document.blocks[:3] == (
        Heading(1, (Text("Título — café"),)),
        Paragraph(
            (
                Text("Una "),
                Emphasis((Text("énfasis"),)),
                Text(" y "),
                Strong((Text("fuerza"),)),
                Text(", "),
                Link("https://example.test/a?q=ñ", (Text("enlace"),)),
                Text(" y "),
                InlineCode("código"),
                Text("."),
            )
        ),
        BlockQuote((Paragraph((Text("Cita con "), Strong((Text("peso"),)), Text("."))),)),
    )
    assert document.blocks[3] == ListBlock(
        ordered=False,
        items=(
            ListItem((Paragraph((Text("Primer elemento"),)),)),
            ListItem((Paragraph((Text("Segundo con "), InlineCode("id"))),)),
        ),
    )
    assert document.blocks[4] == ListBlock(
        ordered=True,
        start=3,
        items=(
            ListItem((Paragraph((Text("Tercero"),)),)),
            ListItem((Paragraph((Text("Cuarto"),)),)),
        ),
    )
    assert document.blocks[5] == FencedCode("  print('¡hola!')\n", "python")


def test_frontmatter_requires_a_structural_closing_delimiter():
    document = parse_publication_document("---\nnot: frontmatter\n\nVisible paragraph")

    assert document.metadata == {}
    assert document.blocks == (
        HorizontalRule(),
        Paragraph((Text("not: frontmatter"),)),
        Paragraph((Text("Visible paragraph"),)),
    )


def test_document_values_are_immutable():
    document = parse_publication_document(
        "---\nlabels:\n  language: es\ntags: [IA, investigación]\nflags: !!set {print, web}\n---\nBody"
    )
    metadata = document.metadata
    labels = metadata["labels"]
    tags = metadata["tags"]
    flags = metadata["flags"]

    assert isinstance(metadata, Mapping)
    assert metadata == {
        "labels": {"language": "es"},
        "tags": ("IA", "investigación"),
        "flags": frozenset({"print", "web"}),
    }
    with pytest.raises(TypeError):
        metadata["source_id"] = "other"  # type: ignore[index]
    with pytest.raises(TypeError):
        labels["language"] = "en"  # type: ignore[index]
    with pytest.raises(AttributeError):
        tags.append("archive")  # type: ignore[union-attr]
    with pytest.raises(AttributeError):
        flags.add("web")  # type: ignore[union-attr]
    with pytest.raises(AttributeError):
        document.blocks[0].children = ()  # type: ignore[misc]
    assert document.metadata["labels"]["language"] == "es"  # type: ignore[index]
    assert document.metadata["tags"] == ("IA", "investigación")
    assert document.metadata["flags"] == frozenset({"print", "web"})


def test_parser_refuses_to_drop_unsupported_inline_semantics():
    with pytest.raises(DocumentParseError, match="html_inline"):
        parse_publication_document("A <span>reader-visible</span> value.")


def test_parser_handles_nested_lists_and_nested_quotes():
    document = parse_publication_document(
        "> Outer quote.\n>\n> > Inner quote.\n> >\n> > - First\n> >   - Nested\n"
    )

    assert document.blocks == (
        BlockQuote(
            (
                Paragraph((Text("Outer quote."),)),
                BlockQuote(
                    (
                        Paragraph((Text("Inner quote."),)),
                        ListBlock(
                            ordered=False,
                            items=(
                                ListItem(
                                    (
                                        Paragraph((Text("First"),)),
                                        ListBlock(
                                            ordered=False,
                                            items=(
                                                ListItem((Paragraph((Text("Nested"),)),)),
                                            ),
                                        ),
                                    )
                                ),
                            ),
                        ),
                    )
                ),
            )
        ),
    )


def test_parser_refuses_to_drop_unsupported_block_semantics():
    with pytest.raises(DocumentParseError, match="html_block"):
        parse_publication_document("<aside>Reader-visible block</aside>")


def test_existing_edition_manuscripts_parse_through_the_public_interface():
    root = Path(__file__).resolve().parents[1]
    manuscripts = sorted((root / "editions").glob("**/*.md"))

    assert manuscripts
    for manuscript in manuscripts:
        document = parse_publication_document(manuscript.read_text(encoding="utf-8"))
        assert document.blocks, manuscript.relative_to(root)
