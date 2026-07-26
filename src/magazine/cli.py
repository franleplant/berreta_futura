from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .compiler import Magazine
from .errors import MagazineError
from .render_engine import DEFAULT_ENGINE, ENGINES


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="mag", description="Compile a private faithful-edit magazine.")
    command.add_argument("--root", type=Path, default=Path.cwd(), help="Project root (default: current directory)")
    actions = command.add_subparsers(dest="command", required=True)
    capture = actions.add_parser("capture", help="Archive a raw snapshot, record it, and queue the source")
    capture.add_argument("url")
    capture.add_argument("--snapshot", type=Path, required=True, help="Raw file or directory to copy into the source archive")
    capture.add_argument("--capture-method", default="caller_supplied", help="How the supplied snapshot was acquired")
    capture.add_argument("--title")
    capture.add_argument("--author")
    capture.add_argument("--published-at")
    capture.add_argument("--captured-at")
    capture.add_argument("--tag", action="append", default=[])
    capture.add_argument("--primary-material", action="append", default=[])
    capture.add_argument("--synopsis", default="")
    capture.add_argument("--notes", default="")
    actions.add_parser("sources", help="Regenerate sources.md")
    actions.add_parser(
        "media-index",
        help="Regenerate deterministic media inventories for all raw captures",
    )
    actions.add_parser("queue", help="Assign every unassigned source to the open edition")
    validate = actions.add_parser("validate", help="Validate an edition and its fidelity ledgers")
    validate.add_argument("edition_id")
    build = actions.add_parser("build", help="Render, impose, and package an edition")
    build.add_argument("edition_id")
    build.add_argument(
        "--engine",
        choices=ENGINES,
        help=(
            "Reader renderer for this build only, overriding [render] engine "
            f"(default {DEFAULT_ENGINE}). Nothing is written back to configuration."
        ),
    )
    cover_proof = actions.add_parser(
        "cover-proof",
        help="Compile a fast cover-only SVG, PDF, PNG, and comparison report",
    )
    cover_proof.add_argument("edition_id")
    cover_languages = cover_proof.add_mutually_exclusive_group()
    cover_languages.add_argument("--language", help="Compile one configured language")
    cover_languages.add_argument(
        "--all-languages",
        action="store_true",
        help="Compile every configured publication language",
    )
    cover_proof.add_argument(
        "--reference",
        type=Path,
        help="Approved reference image used by the visual comparison",
    )
    cover_proof.add_argument(
        "--check",
        action="store_true",
        help="Fail when cover parity or the supplied reference comparison fails",
    )
    back_cover_proof = actions.add_parser(
        "back-cover-proof",
        help="Compile a fast back-cover SVG, PDF, PNG, and comparison report",
    )
    back_cover_proof.add_argument("edition_id")
    back_cover_languages = back_cover_proof.add_mutually_exclusive_group()
    back_cover_languages.add_argument("--language", help="Compile one configured language")
    back_cover_languages.add_argument(
        "--all-languages",
        action="store_true",
        help="Compile every configured publication language",
    )
    back_cover_proof.add_argument(
        "--reference",
        type=Path,
        help="Approved reference image used by the visual comparison",
    )
    back_cover_proof.add_argument(
        "--check",
        action="store_true",
        help="Fail when back-cover parity or the supplied reference comparison fails",
    )
    review = actions.add_parser("review", help="Inspect or record independent render review state")
    review_actions = review.add_subparsers(dest="review_command", required=True)
    review_status = review_actions.add_parser("status", help="Show current hash-bound review status")
    review_status.add_argument("edition_id")
    review_record = review_actions.add_parser(
        "record", help="Bind an independent visual decision to the current PDFs"
    )
    review_record.add_argument("edition_id")
    review_record.add_argument("--reviewer", required=True)
    review_record.add_argument(
        "--result", required=True, choices=("approved", "changes_required")
    )
    review_record.add_argument("--finding", action="append", default=[])
    review_record.add_argument("--notes", default="")
    release = actions.add_parser("release", help="Build and freeze the complete open edition")
    release.add_argument("edition_id")
    release.add_argument("--next-edition-id", help="Override the next empty edition id")
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        # Inside the handler: configuration is validated during construction, so
        # a bad magazine.toml is a reported error rather than a traceback.
        magazine = Magazine(args.root)
        if args.command == "capture":
            record = magazine.capture(
                args.url, snapshot=args.snapshot, capture_method=args.capture_method,
                title=args.title, author=args.author, published_at=args.published_at,
                captured_at=args.captured_at, tags=args.tag, primary_material=args.primary_material,
                synopsis=args.synopsis, notes=args.notes,
            )
            print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
        elif args.command == "sources":
            print(magazine.write_sources())
        elif args.command == "media-index":
            for path in magazine.index_media():
                print(path)
        elif args.command == "queue":
            state = magazine.sync_release_queue()
            print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2))
        elif args.command == "validate":
            magazine.validate(args.edition_id)
            print(f"valid: {args.edition_id}")
        elif args.command == "build":
            result = magazine.build(args.edition_id, engine=args.engine)
            print(result.output_dir)
        elif args.command == "cover-proof":
            languages = (
                None
                if args.all_languages
                else (args.language or magazine.primary_language,)
            )
            for artifact in magazine.cover_proof(
                args.edition_id,
                languages=languages,
                reference=args.reference,
                check=args.check,
            ):
                print(artifact.proof_json)
        elif args.command == "back-cover-proof":
            languages = (
                None
                if args.all_languages
                else (args.language or magazine.primary_language,)
            )
            for artifact in magazine.back_cover_proof(
                args.edition_id,
                languages=languages,
                reference=args.reference,
                check=args.check,
            ):
                print(artifact.proof_json)
        elif args.command == "review" and args.review_command == "status":
            print(
                json.dumps(
                    magazine.render_review_status(args.edition_id),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "review" and args.review_command == "record":
            path, result = magazine.record_render_review(
                args.edition_id,
                reviewer=args.reviewer,
                result=args.result,
                findings=args.finding,
                notes=args.notes,
            )
            print(f"recorded: {path}\noutput: {result.output_dir}")
        elif args.command == "release":
            result, transition = magazine.release(
                args.edition_id, next_edition_id=args.next_edition_id
            )
            print(
                f"released: {transition.released_edition_id}\n"
                f"output: {result.output_dir}\n"
                f"open: {transition.next_edition_id}"
            )
        return 0
    except MagazineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
