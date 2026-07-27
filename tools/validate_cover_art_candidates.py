from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from magazine.cover_art_candidates import validate_cover_art_candidates
from magazine.errors import ValidationError


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate an edition's three hash-pinned cover-art candidates."
    )
    parser.add_argument("edition_dir", type=Path)
    args = parser.parse_args()

    edition_dir = args.edition_dir.resolve()
    manifest_path = edition_dir / "edition.yaml"
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        selected = manifest["cover"]["art_path"]
        result = validate_cover_art_candidates(
            edition_dir,
            selected_art_path=selected,
        )
    except (OSError, KeyError, TypeError, yaml.YAMLError, ValidationError) as exc:
        parser.error(str(exc))

    print(f"Validated {len(result['variants'])} cover-art candidates for {edition_dir.name}")
    print(f"Selected production art remains {selected}")


if __name__ == "__main__":
    main()
