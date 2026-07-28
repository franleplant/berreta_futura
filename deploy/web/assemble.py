"""Gather built web editions into one deployable static tree.

The compiler's job ends at ``output/<edition-id>/web/<language>/``; this
script's job is the deploy artifact: copy those trees under one root, one
route per edition and language, and write the ``editions.json`` manifest the
Worker routes from. It decides *which* editions ship by reading the release
ledger through the compiler's own loader — the deploy step must not have its
own opinion about what "released" means.

Run it from anywhere inside the repository::

    uv run python deploy/web/assemble.py
    uv run python deploy/web/assemble.py --allow 003-unreleased
    uv run python deploy/web/assemble.py --dist /tmp/deploy-tree

Everything it writes is deterministic: directories are walked in sorted
order, the manifest carries no timestamp, and rebuilding from the same
``output/`` produces the same bytes.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tomllib
from pathlib import Path


def repo_root(start: Path) -> Path:
    """The magazine repository containing ``start``, by its magazine.toml."""

    for candidate in (start, *start.parents):
        if (candidate / "magazine.toml").is_file():
            return candidate
    raise SystemExit("error: not inside a magazine repository (no magazine.toml)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dist",
        type=Path,
        default=None,
        help=(
            "Destination tree (default: deploy/web/dist). Replaced wholesale, "
            "so it must be absent, empty, or a previous assembly output"
        ),
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="EDITION_ID",
        help="Also assemble this unreleased edition, marked as a preview",
    )
    args = parser.parse_args(argv)

    root = repo_root(Path(__file__).resolve().parent)
    sys.path.insert(0, str(root / "src"))
    from magazine.release import load_release_state  # noqa: E402

    config = tomllib.loads((root / "magazine.toml").read_text(encoding="utf-8"))
    paths = config.get("paths", {})
    output_dir = root / str(paths.get("output", "output"))
    ledger_path = root / str(paths.get("release_state", "library/release-state.yaml"))
    primary_language = str(config.get("publication", {}).get("language", "en"))

    state = load_release_state(ledger_path)
    released = [dict(item) for item in state.released_editions]
    released_ids = [str(item["id"]) for item in released]
    for allowed in args.allow:
        if allowed in released_ids:
            print(f"note: {allowed} is released; --allow is redundant")

    # Ledger order is release order, so the last assembled released edition is
    # `latest`. Previews follow the released list and never become `latest`.
    plan = [(edition_id, True) for edition_id in released_ids]
    plan.extend((edition_id, False) for edition_id in args.allow if edition_id not in released_ids)

    dist = (args.dist or Path(__file__).resolve().parent / "dist").resolve()
    if dist == root or root in dist.parents:
        # Refuse to aim the wholesale-replace below at repository content.
        allowed_inside = Path(__file__).resolve().parent / "dist"
        if dist != allowed_inside:
            raise SystemExit(f"error: refusing to replace {dist} inside the repository")
    if dist.exists():
        # The replace below is wholesale, so the target has to look like ours:
        # absent, empty, or carrying the manifest a previous assembly wrote.
        # Anything else is someone's directory, and a typo'd --dist must not
        # delete it.
        if any(dist.iterdir()) and not (dist / "editions.json").is_file():
            raise SystemExit(
                f"error: refusing to replace {dist}: it is not empty and has no "
                "editions.json from a previous assembly; point --dist at an "
                "absent or empty directory, or at a prior assemble output"
            )
        shutil.rmtree(dist)
    dist.mkdir(parents=True)

    manifest_editions: list[dict[str, object]] = []
    # Previews are usually the open edition; its ledger entry carries the
    # issue number even before release, so the manifest need not say null.
    by_id = {str(item["id"]): item for item in released}
    open_edition = dict(state.open_edition)
    if open_edition.get("id"):
        by_id.setdefault(str(open_edition["id"]), open_edition)
    for edition_id, is_released in plan:
        web_root = output_dir / edition_id / "web"
        languages = sorted(
            entry.name
            for entry in (web_root.iterdir() if web_root.is_dir() else ())
            if entry.is_dir() and (entry / "index.html").is_file()
        )
        if not languages:
            print(f"skip: {edition_id} has no built web edition under {web_root}")
            continue
        for language in languages:
            shutil.copytree(web_root / language, dist / edition_id / language)
        entry = by_id.get(edition_id, {})
        manifest_editions.append(
            {
                "id": edition_id,
                "issue_number": entry.get("issue_number"),
                "publication_date": entry.get("publication_date"),
                "languages": languages,
                "released": is_released,
            }
        )
        state_word = "released" if is_released else "preview"
        print(f"assembled: {edition_id} ({', '.join(languages)}) [{state_word}]")

    if not manifest_editions:
        raise SystemExit("error: nothing to assemble; build one with `uv run mag web <edition-id>`")

    # Only a released edition can be `latest`; a previews-only assembly says
    # so with null, and the Worker answers `/` with 404 rather than steering
    # readers to an unreleased edition. Previews stay reachable only by their
    # explicit URL.
    latest = next(
        (item["id"] for item in reversed(manifest_editions) if item["released"]),
        None,
    )
    manifest = {
        "schema_version": 1,
        "primary_language": primary_language,
        "latest": latest,
        "editions": manifest_editions,
    }
    (dist / "editions.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"manifest: {dist / 'editions.json'} (latest: {latest or 'none — previews only'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
