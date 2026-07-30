from __future__ import annotations

import argparse
from dataclasses import fields, is_dataclass
import json
import sys
from pathlib import Path
from typing import Any

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
    capture.add_argument("--author", required=True)
    author_profile = capture.add_mutually_exclusive_group(required=True)
    author_profile.add_argument(
        "--author-note",
        help=(
            "Edition-ready identity or CV context; never an article synopsis. "
            "Requires at least one --author-evidence."
        ),
    )
    author_profile.add_argument(
        "--institutional-author",
        action="store_true",
        help="Explicitly omit a biography for a self-explanatory institutional byline",
    )
    capture.add_argument(
        "--author-evidence",
        action="append",
        nargs=2,
        default=[],
        metavar=("URL", "SNAPSHOT"),
        help=(
            "Official/profile URL and sanitized snapshot supporting the author note; "
            "repeat for additional authors or affiliations"
        ),
    )
    capture.add_argument("--published-at")
    capture.add_argument("--captured-at")
    capture.add_argument("--tag", action="append", default=[])
    capture.add_argument("--primary-material", action="append", default=[])
    capture.add_argument("--synopsis", default="")
    capture.add_argument("--notes", default="")
    capture.add_argument(
        "--edition",
        help=(
            "Collecting edition to receive this source "
            "(default: the release ledger's intake edition)"
        ),
    )
    actions.add_parser("sources", help="Regenerate sources.md")
    actions.add_parser(
        "media-index",
        help="Regenerate deterministic media inventories for all raw captures",
    )
    collect = actions.add_parser(
        "collect",
        help="Open a collecting edition and select it for subsequent intake",
    )
    collect.add_argument("edition_id")
    collect.add_argument("--issue-number", required=True, type=int)
    actions.add_parser(
        "queue",
        help="Assign every unassigned source to the selected intake edition",
    )
    status = actions.add_parser(
        "status",
        help="Explain every edition checkpoint and its exact next action",
    )
    status.add_argument("edition_id")
    status.add_argument("--json", action="store_true", help="Emit stable JSON")
    run = actions.add_parser(
        "run",
        help="Advance safe clerical work, then stop before authorship or judgment",
    )
    run.add_argument("edition_id")
    run.add_argument("--json", action="store_true", help="Emit stable JSON")

    article = actions.add_parser(
        "article",
        help="Stage source-backed article work from a versioned brief",
    )
    article_actions = article.add_subparsers(dest="article_command", required=True)
    article_stage = article_actions.add_parser(
        "stage",
        help="Create a manuscript slot, fidelity skeleton, and translation placeholders",
    )
    article_stage.add_argument("brief", type=Path)
    article_stage.add_argument("--dry-run", action="store_true")

    cover_art = actions.add_parser(
        "cover-art",
        help="Manage immutable cover rounds, proofs, and selection",
    )
    cover_actions = cover_art.add_subparsers(dest="cover_art_command", required=True)
    cover_status = cover_actions.add_parser("status")
    cover_status.add_argument("edition_id")
    cover_round = cover_actions.add_parser("next-round")
    cover_round.add_argument("edition_id")
    cover_round.add_argument("--editorial-reading")
    cover_round.add_argument("--dry-run", action="store_true")
    cover_prompts = cover_actions.add_parser("prompts")
    cover_prompts.add_argument("edition_id")
    cover_prompts.add_argument("round_number", type=int)
    cover_prompts.add_argument("--dry-run", action="store_true")
    cover_register = cover_actions.add_parser("register")
    cover_register.add_argument("edition_id")
    cover_register.add_argument("round_number", type=int)
    cover_register.add_argument(
        "--image",
        action="append",
        required=True,
        metavar="VARIANT=PNG",
        help="Supply synthetic, art_directed, and wildcard once each",
    )
    cover_register.add_argument("--dry-run", action="store_true")
    cover_plan = cover_actions.add_parser("proof-plan")
    cover_plan.add_argument("edition_id")
    cover_plan.add_argument("--language", action="append")
    cover_plan.add_argument("--round", action="append", type=int)
    cover_proofs = cover_actions.add_parser("proof")
    cover_proofs.add_argument("edition_id")
    cover_proofs.add_argument("--language", action="append")
    cover_proofs.add_argument("--round", action="append", type=int)
    cover_proofs.add_argument("--dry-run", action="store_true")
    cover_compare = cover_actions.add_parser("compare")
    cover_compare.add_argument("edition_id")
    cover_compare.add_argument("--dry-run", action="store_true")
    cover_select = cover_actions.add_parser("select")
    cover_select.add_argument("edition_id")
    cover_select.add_argument("round_number", type=int)
    cover_select.add_argument("variant")
    cover_select.add_argument("--dry-run", action="store_true")

    interior_art = actions.add_parser(
        "interior-art",
        help="Manage explicit interior illustration briefs and registered assets",
    )
    interior_actions = interior_art.add_subparsers(
        dest="interior_art_command",
        required=True,
    )
    interior_status = interior_actions.add_parser("status")
    interior_status.add_argument("edition_id")
    interior_scaffold = interior_actions.add_parser("scaffold")
    interior_scaffold.add_argument("brief", type=Path)
    interior_scaffold.add_argument("--dry-run", action="store_true")
    interior_prompts = interior_actions.add_parser("prompts")
    interior_prompts.add_argument("edition_id")
    interior_prompts.add_argument("--dry-run", action="store_true")
    interior_register = interior_actions.add_parser("register")
    interior_register.add_argument("edition_id")
    interior_register.add_argument("asset_id")
    interior_register.add_argument("source", type=Path)
    interior_register.add_argument("--dry-run", action="store_true")
    interior_plan = interior_actions.add_parser("review-plan")
    interior_plan.add_argument("edition_id")
    interior_sheet = interior_actions.add_parser("review-sheet")
    interior_sheet.add_argument("edition_id")
    interior_sheet.add_argument("--dry-run", action="store_true")

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
    illustrate = actions.add_parser(
        "illustrate",
        help=(
            "Compile an edition's illustration direction and asset briefs into "
            "deterministic authoring prompts"
        ),
    )
    illustrate.add_argument("edition_id")
    web = actions.add_parser(
        "web",
        help=(
            "Write the browsable web edition for each configured language "
            "(a private screen profile; never part of a build or release)"
        ),
    )
    web.add_argument("edition_id")
    web.add_argument("--language", help="Write one configured language (default: all)")
    fit = actions.add_parser(
        "fit",
        help=(
            "Fast page-budget verdict: paginate the reader without writing "
            "anything and fail on any budget breach"
        ),
    )
    fit.add_argument("edition_id")
    fit.add_argument("--language", help="Measure one configured language (default: all)")
    measure = actions.add_parser(
        "measure",
        help="Full pagination measurement as JSON, for agents and scripts",
    )
    measure.add_argument("edition_id")
    measure.add_argument(
        "--language", help="Measure one configured language (default: all)"
    )
    measure.add_argument(
        "--json",
        type=Path,
        metavar="PATH",
        help="Write the JSON dump to PATH instead of stdout",
    )
    pin = actions.add_parser(
        "pin",
        help=(
            "Recompute every derivable hash pin in the edition's authored "
            "files and report each digest moved"
        ),
    )
    pin.add_argument("edition_id")
    translate = actions.add_parser(
        "translate",
        help=(
            "Stage a language overlay: scaffold or reconcile its structure "
            "and pins, and report the untranslated backlog"
        ),
    )
    translate.add_argument("edition_id")
    translate.add_argument("language")
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
        "record", help="Bind an independent review decision to the exact bytes it inspected"
    )
    review_record.add_argument("edition_id")
    review_record.add_argument(
        "--kind",
        choices=("render", "evidence"),
        default="render",
        help=(
            "render binds a visual decision to the current PDFs (default); evidence "
            "binds a manuscript-versus-source audit to the manuscripts, fidelity "
            "ledgers, and extraction bodies it compared"
        ),
    )
    review_record.add_argument("--reviewer", required=True)
    review_record.add_argument(
        "--result", required=True, choices=("approved", "changes_required")
    )
    review_record.add_argument("--finding", action="append", default=[])
    review_record.add_argument("--notes", default="")
    review_record.add_argument(
        "--articles",
        help=(
            "Evidence only: comma-separated article ids whose audit was actually "
            "repeated. Only they are re-bound from current disk state; every other "
            "article keeps the existing record's binding and reviewed_at. Omit to "
            "record the full audit."
        ),
    )
    review_record.add_argument(
        "--rebuild",
        action="store_true",
        help=(
            "Render only: after recording, re-typeset every language with the "
            "recorded engine and error if any byte differs from the record. By "
            "default the decision is exposed in the existing package in place, "
            "without rebuilding."
        ),
    )
    review_record.add_argument(
        "--engine",
        choices=ENGINES,
        help=(
            "Renderer that produced the reviewed PDFs, when they were built with "
            "`mag build --engine` rather than the configured [render] engine. "
            "The record names it and the rebuild reuses it. Note that `mag release` "
            "always rebuilds with the CONFIGURED engine, so an approval recorded "
            "under an off-config engine will be stale at release."
        ),
    )
    release = actions.add_parser("release", help="Build and freeze the complete open edition")
    release.add_argument("edition_id")
    release.add_argument("--next-edition-id", help="Override the next empty edition id")
    return command


def _json_value(value: Any, *, root: Path | None = None) -> Any:
    if isinstance(value, Path):
        if root is not None:
            try:
                return value.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                pass
        return value.as_posix()
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _json_value(getattr(value, field.name), root=root)
            for field in fields(value)
            if not field.name.startswith("_")
        }
    if isinstance(value, dict):
        return {
            str(key): _json_value(item, root=root)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_value(item, root=root) for item in value]
    return value


def _print_json(value: Any, *, root: Path) -> None:
    if hasattr(value, "to_dict"):
        try:
            value = value.to_dict(root)
        except TypeError:
            value = value.to_dict()
    print(
        json.dumps(
            _json_value(value, root=root),
            ensure_ascii=False,
            indent=2,
        )
    )


def _cover_images(values: list[str]) -> dict[str, Path]:
    images: dict[str, Path] = {}
    for raw in values:
        variant, separator, path = raw.partition("=")
        variant = variant.strip()
        if not separator or not variant or not path.strip():
            raise MagazineError(
                f"Invalid --image {raw!r}; expected VARIANT=PNG"
            )
        if variant in images:
            raise MagazineError(f"Duplicate cover image variant: {variant}")
        images[variant] = Path(path)
    return images


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
                author_note=args.author_note,
                author_evidence=[
                    (source_url, Path(snapshot))
                    for source_url, snapshot in args.author_evidence
                ],
                institutional_author=args.institutional_author,
                edition_id=args.edition,
            )
            print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
        elif args.command == "sources":
            print(magazine.write_sources())
        elif args.command == "media-index":
            for path in magazine.index_media():
                print(path)
        elif args.command == "collect":
            state = magazine.open_collection(
                args.edition_id,
                issue_number=args.issue_number,
            )
            print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2))
        elif args.command == "queue":
            state = magazine.sync_release_queue()
            print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2))
        elif args.command == "status":
            report = magazine.workflow_status(args.edition_id)
            if args.json:
                _print_json(report, root=magazine.root)
            else:
                checkpoint = report.next_checkpoint
                print(
                    f"{report.edition_id}: {report.lifecycle}; "
                    f"release_ready={str(report.release_ready).lower()}"
                )
                if checkpoint is None:
                    print("next: none")
                else:
                    print(f"next: {checkpoint.id} ({checkpoint.next_action.classification})")
                    print(checkpoint.next_action.instruction)
                    if checkpoint.next_action.command:
                        print(f"command: {checkpoint.next_action.command}")
        elif args.command == "run":
            result = magazine.workflow_run(args.edition_id)
            if args.json:
                _print_json(result, root=magazine.root)
            else:
                for action in result.actions:
                    print(f"done: {action}")
                checkpoint = result.report.next_checkpoint
                if checkpoint is None:
                    print("stopped: no unresolved checkpoint")
                else:
                    print(
                        f"stopped: {checkpoint.id} "
                        f"({checkpoint.next_action.classification})"
                    )
                    print(checkpoint.next_action.instruction)
        elif args.command == "article" and args.article_command == "stage":
            result = magazine.stage_article(args.brief, dry_run=args.dry_run)
            _print_json(result, root=magazine.root)
        elif args.command == "cover-art" and args.cover_art_command == "status":
            _print_json(
                magazine.cover_studio_status(args.edition_id),
                root=magazine.root,
            )
        elif args.command == "cover-art" and args.cover_art_command == "next-round":
            _print_json(
                magazine.cover_studio_scaffold(
                    args.edition_id,
                    editorial_reading=args.editorial_reading,
                    dry_run=args.dry_run,
                ),
                root=magazine.root,
            )
        elif args.command == "cover-art" and args.cover_art_command == "prompts":
            _print_json(
                magazine.cover_studio_prompts(
                    args.edition_id,
                    args.round_number,
                    dry_run=args.dry_run,
                ),
                root=magazine.root,
            )
        elif args.command == "cover-art" and args.cover_art_command == "register":
            _print_json(
                magazine.cover_studio_register(
                    args.edition_id,
                    args.round_number,
                    _cover_images(args.image),
                    dry_run=args.dry_run,
                ),
                root=magazine.root,
            )
        elif args.command == "cover-art" and args.cover_art_command == "proof-plan":
            _print_json(
                magazine.cover_studio_proof_plan(
                    args.edition_id,
                    languages=args.language,
                    rounds=args.round,
                ),
                root=magazine.root,
            )
        elif args.command == "cover-art" and args.cover_art_command == "proof":
            action, comparison = magazine.cover_studio_render_proofs(
                args.edition_id,
                languages=args.language,
                rounds=args.round,
                dry_run=args.dry_run,
            )
            _print_json(
                {"action": action, "full_cover_comparison": comparison},
                root=magazine.root,
            )
        elif args.command == "cover-art" and args.cover_art_command == "compare":
            _print_json(
                magazine.cover_studio_compare(
                    args.edition_id,
                    dry_run=args.dry_run,
                ),
                root=magazine.root,
            )
        elif args.command == "cover-art" and args.cover_art_command == "select":
            _print_json(
                magazine.cover_studio_select(
                    args.edition_id,
                    args.round_number,
                    args.variant,
                    dry_run=args.dry_run,
                ),
                root=magazine.root,
            )
        elif args.command == "interior-art" and args.interior_art_command == "status":
            _print_json(
                magazine.illustration_studio_status(args.edition_id),
                root=magazine.root,
            )
        elif args.command == "interior-art" and args.interior_art_command == "scaffold":
            _print_json(
                magazine.illustration_studio_scaffold(
                    args.brief,
                    dry_run=args.dry_run,
                ),
                root=magazine.root,
            )
        elif args.command == "interior-art" and args.interior_art_command == "prompts":
            _print_json(
                magazine.illustration_studio_prompts(
                    args.edition_id,
                    dry_run=args.dry_run,
                ),
                root=magazine.root,
            )
        elif args.command == "interior-art" and args.interior_art_command == "register":
            _print_json(
                magazine.illustration_studio_register(
                    args.edition_id,
                    args.asset_id,
                    args.source,
                    dry_run=args.dry_run,
                ),
                root=magazine.root,
            )
        elif args.command == "interior-art" and args.interior_art_command == "review-plan":
            _print_json(
                magazine.illustration_studio_review_plan(args.edition_id),
                root=magazine.root,
            )
        elif args.command == "interior-art" and args.interior_art_command == "review-sheet":
            _print_json(
                magazine.illustration_studio_review_sheet(
                    args.edition_id,
                    dry_run=args.dry_run,
                ),
                root=magazine.root,
            )
        elif args.command == "validate":
            magazine.validate(args.edition_id)
            print(f"valid: {args.edition_id}")
        elif args.command == "build":
            result = magazine.build(args.edition_id, engine=args.engine)
            print(result.output_dir)
        elif args.command == "illustrate":
            print(magazine.illustration_package(args.edition_id))
        elif args.command == "web":
            for written in magazine.web(args.edition_id, language=args.language):
                print(f"{written.language}: {written.index}")
        elif args.command == "fit":
            # A breach is the command's answer, not a failure to answer, so it
            # exits 1 where a MagazineError below exits 2.
            table, ok = magazine.fit(args.edition_id, language=args.language)
            print(table)
            if not ok:
                return 1
        elif args.command == "measure":
            payload = magazine.measure(
                args.edition_id, language=args.language
            ).to_json()
            if args.json is not None:
                args.json.parent.mkdir(parents=True, exist_ok=True)
                args.json.write_text(payload, encoding="utf-8")
                print(args.json)
            else:
                print(payload, end="")
        elif args.command == "pin":
            report = magazine.pin(args.edition_id)
            for change in report.changes:
                print(f"{change.path}: {change.pin} {change.old} -> {change.new}")
            print(f"repinned: {len(report.changes)} pin(s) across {len(report.files)} file(s)")
        elif args.command == "translate":
            report = magazine.stage_translation(args.edition_id, args.language)
            for path in report.created:
                print(f"created: {path}")
            for path in report.updated:
                print(f"updated: {path}")
            for change in report.pin_changes:
                print(f"repinned: {change.path}: {change.pin} {change.old} -> {change.new}")
            for advisory in report.advisories:
                print(f"re-translate: {advisory.pointer} ({advisory.reason})")
            for dropped in report.dropped:
                print(f"dropped: {dropped.pointer}: {dropped.content!r} ({dropped.note})")
            for field in report.placeholders:
                print(f"untranslated: {field.path}: {field.pointer}")
            for note in report.notes:
                print(f"note: {note}")
            for error in report.validation_errors:
                print(f"still invalid: {error}")
            print(
                f"staged {args.language}: {len(report.placeholders)} field(s) awaiting "
                f"translation, {len(report.advisories)} advisory(ies)"
            )
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
            status = magazine.render_review_status(args.edition_id)
            status["evidence"] = magazine.evidence_review_status(args.edition_id)
            print(json.dumps(status, ensure_ascii=False, indent=2))
        elif args.command == "review" and args.review_command == "record":
            if args.kind == "evidence":
                if args.engine:
                    raise MagazineError(
                        "--engine applies only to render reviews; an evidence review "
                        "binds to manuscripts and extractions, not rendered PDFs"
                    )
                if args.rebuild:
                    raise MagazineError(
                        "--rebuild applies only to render reviews; an evidence review "
                        "touches no package"
                    )
                articles = None
                if args.articles is not None:
                    articles = [
                        item.strip() for item in args.articles.split(",") if item.strip()
                    ]
                path = magazine.record_evidence_review(
                    args.edition_id,
                    reviewer=args.reviewer,
                    result=args.result,
                    findings=args.finding,
                    notes=args.notes,
                    articles=articles,
                )
                print(f"recorded: {path}")
            else:
                # ``is not None`` mirrors the evidence branch: even an empty
                # ``--articles ""`` expresses the intent to narrow and must be
                # refused, not silently ignored.
                if args.articles is not None:
                    raise MagazineError(
                        "--articles applies only to evidence reviews; a render review "
                        "binds whole-language PDFs, not individual articles"
                    )
                path, output_dir = magazine.record_render_review(
                    args.edition_id,
                    reviewer=args.reviewer,
                    result=args.result,
                    findings=args.finding,
                    notes=args.notes,
                    engine=args.engine,
                    rebuild=args.rebuild,
                )
                print(f"recorded: {path}\noutput: {output_dir}")
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
