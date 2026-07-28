from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from magazine import Magazine
from magazine.cover import CoverCompiler
from magazine.cover_art_candidates import validate_cover_art_candidates


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Render every recorded cover candidate in every configured language "
            "without changing edition or translation manifests."
        )
    )
    parser.add_argument("edition_id")
    parser.add_argument(
        "--record",
        type=Path,
        help="Candidate record path relative to the edition directory.",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        help="Proof directory; defaults to output/<edition>/cover-candidate-proofs.",
    )
    args = parser.parse_args()

    root = Path.cwd().resolve()
    magazine = Magazine(root)
    edition_dir = root / "editions" / args.edition_id
    record_path = edition_dir / args.record if args.record else None
    candidates = validate_cover_art_candidates(
        edition_dir,
        record_path=record_path,
    )["variants"]
    editions = magazine._load_cover_languages(  # noqa: SLF001
        args.edition_id,
        purpose="Cover-candidate proof",
    )
    destination = (
        args.destination.resolve()
        if args.destination
        else root / "output" / args.edition_id / "cover-candidate-proofs"
    )
    compiler = CoverCompiler(root)

    for variant, art_path in candidates.items():
        for language, edition in editions.items():
            reference = (
                root
                / "design"
                / "covers"
                / "canto-vivo"
                / "references"
                / f"{language}.png"
            )
            artifact = compiler.compile(
                replace(edition, cover_art=art_path),
                destination / variant / language,
                reference=reference,
            )
            print(f"{variant}/{language}: {artifact.proof_json}")


if __name__ == "__main__":
    main()
