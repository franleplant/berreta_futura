from __future__ import annotations

from .records import SourceRecord
from .release import ReleaseState


def render_sources(records: list[SourceRecord], release_state: ReleaseState | None = None) -> str:
    lines = ["# Sources", "", "_Generated from structured source records. Do not edit by hand._", ""]
    assignments = release_state.assignments() if release_state else {}
    if release_state:
        lines.extend([
            f"_Open edition: `{release_state.open_edition_id}`; {len(release_state.queued_source_ids)} queued sources._",
            "",
        ])
    if not records:
        return "\n".join(lines + ["No sources captured yet.", ""])
    for record in records:
        byline = f" — {record.author}" if record.author else ""
        lines.extend([
            f"## {record.title}{byline}", "",
            f"- ID: `{record.id}`",
            f"- Source: {record.canonical_url}",
            f"- Kind / status: {record.kind} / {record.status}",
            f"- Captured: {record.captured_at}",
            f"- Content hash: `{record.content_hash or 'not captured'}`",
            f"- Raw captures: {len(record.raw_captures)} committed bundle(s)",
        ])
        if record.id in assignments:
            state, edition_id = assignments[record.id].split(":", 1)
            lines.append(f"- Release: {state} for `{edition_id}`")
        if record.published_at:
            lines.append(f"- Published: {record.published_at}")
        if record.tags:
            lines.append(f"- Tags: {', '.join(record.tags)}")
        if record.author_profile is not None:
            if record.author_profile.note:
                lines.append(f"- Author biography: {record.author_profile.note}")
                lines.append("- Author biography evidence:")
                lines.extend(
                    [
                        f"  - {evidence.url} "
                        f"(raw bundle `{evidence.capture_id}`)"
                        for evidence in record.author_profile.evidence
                    ]
                )
            else:
                lines.append("- Author biography: omitted for institutional byline")
        elif record.schema_version >= 2:
            lines.append("- Author biography: pending; source cannot enter an edition")
        if record.primary_material:
            lines.extend(["- Primary material:", *[f"  - {url}" for url in record.primary_material]])
        rights = record.rights or {}
        lines.extend([
            f"- Rights status: {rights.get('status', 'unknown')}",
            f"- Intended use: {rights.get('intended_use', 'private_reference')}",
            f"- Public reprint: {'allowed' if rights.get('public_reprint_allowed') is True else 'not cleared'}",
        ])
        if record.provenance:
            lines.append("- Provenance:")
            for edge in record.provenance:
                if not isinstance(edge, dict):
                    lines.append(f"  - {edge}")
                    continue
                relation = edge.get("relation", "related_to")
                target = (
                    edge.get("target")
                    or edge.get("target_id")
                    or edge.get("target_url")
                    or edge.get("canonical_url")
                    or edge.get("url")
                    or "unspecified target"
                )
                lines.append(f"  - {relation} -> {target}")
        if record.synopsis:
            lines.extend(["", record.synopsis])
        if record.notes:
            lines.extend(["", f"**Editorial note:** {record.notes}"])
        lines.append("")
    return "\n".join(lines)
