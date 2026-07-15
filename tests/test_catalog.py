from magazine.catalog import render_sources
from magazine.records import SourceRecord


def test_catalog_renders_durable_provenance_target_fields():
    record = SourceRecord.from_dict({
        "schema_version": 1,
        "id": "lead",
        "title": "Lead",
        "canonical_url": "https://example.com/lead",
        "submitted_url": "https://example.com/lead",
        "captured_at": "2026-07-15T00:00:00Z",
        "content_hash": "abc",
        "provenance": [
            {"relation": "links_to_primary", "target": "primary"},
            {"relation": "alternate", "target_url": "https://example.com/primary"},
        ],
    })

    catalog = render_sources([record])

    assert "links_to_primary -> primary" in catalog
    assert "alternate -> https://example.com/primary" in catalog

