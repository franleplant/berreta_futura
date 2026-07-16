from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .compiler import Magazine
from .errors import MagazineError


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="mag", description="Compile a private faithful-edit magazine.")
    command.add_argument("--root", type=Path, default=Path.cwd(), help="Project root (default: current directory)")
    actions = command.add_subparsers(dest="command", required=True)
    capture = actions.add_parser("capture", help="Record source metadata; does not download content")
    capture.add_argument("url")
    capture.add_argument("--title")
    capture.add_argument("--author")
    capture.add_argument("--published-at")
    capture.add_argument("--captured-at")
    capture.add_argument("--tag", action="append", default=[])
    capture.add_argument("--primary-material", action="append", default=[])
    capture.add_argument("--synopsis", default="")
    capture.add_argument("--notes", default="")
    actions.add_parser("sources", help="Regenerate sources.md")
    actions.add_parser("queue", help="Assign every unassigned source to the open edition")
    validate = actions.add_parser("validate", help="Validate an edition and its fidelity ledgers")
    validate.add_argument("edition_id")
    build = actions.add_parser("build", help="Render, impose, and package an edition")
    build.add_argument("edition_id")
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    magazine = Magazine(args.root)
    try:
        if args.command == "capture":
            record = magazine.capture(
                args.url, title=args.title, author=args.author, published_at=args.published_at,
                captured_at=args.captured_at, tags=args.tag, primary_material=args.primary_material,
                synopsis=args.synopsis, notes=args.notes,
            )
            print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
        elif args.command == "sources":
            print(magazine.write_sources())
        elif args.command == "queue":
            state = magazine.sync_release_queue()
            print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2))
        elif args.command == "validate":
            magazine.validate(args.edition_id)
            print(f"valid: {args.edition_id}")
        elif args.command == "build":
            result = magazine.build(args.edition_id)
            print(result.output_dir)
        return 0
    except MagazineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
