from __future__ import annotations

import argparse
from dataclasses import fields, is_dataclass
import json
import sys
from pathlib import Path
from typing import Any

from .compiler import Magazine
from .errors import MagazineError
from .io import load_structured
from .produce import MAX_ROUNDS as PRODUCE_MAX_ROUNDS
from .render_engine import DEFAULT_ENGINE, ENGINES
from .runner import TEXT_BACKENDS
from .review_findings import FINDING_SEVERITIES


# The whole review bench, in the order the pieces are judged: the machine and
# human render decision, then the four editorial judges.  ``render`` stays the
# default because it is the one review that predates ``--kind``.
REVIEW_KINDS = ("render", "evidence", "line", "edition", "learning")
# Kinds whose record carries a per-article ``articles`` mapping, so a re-record
# can be narrowed with ``--articles``.  The whole-issue kinds cannot: an
# edition-level verdict about running order or a persona's comprehension run is
# not divisible by article.
PER_ARTICLE_REVIEW_KINDS = ("evidence", "line")


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
    scores = actions.add_parser(
        "scores",
        help="Regenerate editions/scores.yaml from the committed review records",
    )
    scores.add_argument(
        "--check",
        action="store_true",
        help=(
            "Do not write; exit non-zero when the committed records would produce "
            "a different rollup than the one on disk"
        ),
    )
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

    produce = actions.add_parser(
        "produce",
        help=(
            "Draft and judge an edition's pieces: writer, deterministic gates, "
            "fact-checker and line editor in parallel, revision on their "
            "findings, then the learning personas and the managing editor"
        ),
    )
    produce.add_argument("edition_id")
    produce.add_argument(
        "--articles",
        nargs="+",
        metavar="ID",
        help=(
            "Produce only these pieces (article ids, plus `editorial`). Accepts "
            "repeated ids or one comma-separated list. Omit for every piece."
        ),
    )
    produce.add_argument(
        "--max-rounds",
        type=int,
        default=PRODUCE_MAX_ROUNDS,
        help=(
            f"Revision rounds a piece gets before it escalates to a human "
            f"(default {PRODUCE_MAX_ROUNDS})"
        ),
    )
    produce.add_argument(
        "--reviewer",
        help="Reviewer name bound into the review records (default names the backend)",
    )
    produce.add_argument(
        "--backend",
        choices=TEXT_BACKENDS,
        help=(
            "Run the writer and the judges through this text backend instead of "
            "[runner] text_backend, for this invocation only; magazine.toml is "
            "not rewritten. `agent` calls no model: it writes every ready brief "
            "under editions/<id>/production/agent/ and ingests the replies left "
            "beside them. Illustration is never a backend choice and is not "
            "affected."
        ),
    )
    produce.add_argument(
        "--submit",
        metavar="ITEM",
        help=(
            "Ingest one finished work item, named as the ready set spells it "
            "(`article/r1-writer`), then advance and report the next ready set. "
            "The text is read from --reply, or from stdin. Agent backend only."
        ),
    )
    produce.add_argument(
        "--reply",
        type=Path,
        metavar="PATH",
        help="File holding the text for --submit (default: stdin)",
    )
    produce.add_argument(
        "--graph",
        action="store_true",
        help=(
            "Print the production graph -- every declared node, its state, and "
            "what is blocking anything unreached -- and exit. Reads the files "
            "on disk, calls no model and writes nothing. Exits non-zero when "
            "the graph is incomplete."
        ),
    )
    produce.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Print the plan and exit. Resolves the model backend so a missing "
            "one still fails loudly, but calls no model and writes nothing."
        ),
    )
    produce.add_argument("--json", action="store_true", help="Emit stable JSON")

    finding = actions.add_parser(
        "finding",
        help=(
            "File a finding against one piece so its next writer brief carries "
            "it, or list what is outstanding"
        ),
    )
    finding_actions = finding.add_subparsers(dest="finding_command", required=True)
    finding_file = finding_actions.add_parser(
        "file",
        help=(
            "Record a defect found outside the produce loop -- an edition "
            "review, a reader, your own re-reading -- against one piece"
        ),
    )
    finding_file.add_argument("edition_id")
    finding_file.add_argument(
        "piece_id",
        help="Article id, or `editorial` for the opening editorial",
    )
    finding_file.add_argument(
        "--note",
        required=True,
        help="What is wrong, in the words the writer needs to fix it",
    )
    finding_file.add_argument(
        "--severity",
        default="major",
        choices=FINDING_SEVERITIES,
        help="How the reviser should triage it (default major)",
    )
    finding_file.add_argument(
        "--category",
        default="editorial",
        help="What kind of defect it is, in the judges' vocabulary",
    )
    finding_file.add_argument(
        "--locator", help="Where the defect shows: the sentence or paragraph"
    )
    finding_file.add_argument(
        "--repair-from",
        dest="repair_from",
        help="The earliest point at which it could be fixed, when that differs",
    )
    finding_file.add_argument(
        "--suggestion", help="Advisory only; the writer is judged on the defect"
    )
    finding_file.add_argument(
        "--filed-by",
        dest="filed_by",
        default="filed finding",
        help="Who found it, named in the brief (default: filed finding)",
    )
    finding_list = finding_actions.add_parser(
        "list", help="Every finding filed against an edition, open first"
    )
    finding_list.add_argument("edition_id")
    finding_list.add_argument("--json", action="store_true", help="Emit stable JSON")

    article = actions.add_parser(
        "article",
        help="Stage source-backed article work from a versioned brief",
    )
    article_actions = article.add_subparsers(dest="article_command", required=True)
    article_stage = article_actions.add_parser(
        "stage",
        help="Create a manuscript slot, source pins, and translation placeholders",
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

    validate = actions.add_parser("validate", help="Validate an edition against its pinned sources")
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
    fit.add_argument(
        "--opener",
        metavar="ARTICLE_ID",
        help=(
            "Instead of paginating: read a candidate opening paragraph on "
            "stdin and report the typeset lines it would set as against the "
            "article's illustrated-opener budget"
        ),
    )
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
        choices=REVIEW_KINDS,
        default="render",
        help=(
            "render binds a visual decision to the current PDFs (default); evidence "
            "binds a manuscript-versus-source audit to the manuscripts and "
            "extraction bodies it compared; line binds a per-piece reading verdict "
            "to the manuscripts alone; edition binds a whole-issue verdict to the "
            "editorial, edition.yaml and every manuscript; learning binds the reader "
            "personas' verdict to the editor-authored furniture and the explainer"
        ),
    )
    review_record.add_argument("--reviewer", required=True)
    review_record.add_argument(
        "--result", required=True, choices=("approved", "changes_required")
    )
    review_record.add_argument("--finding", action="append", default=[])
    review_record.add_argument("--notes", default="")
    review_record.add_argument(
        "--verdict",
        type=Path,
        help=(
            "Path to the judge's YAML verdict document, as the review prompts emit "
            "it. Supplies the structured findings, the advisory scores, and (for a "
            "learning review) the comprehension and manager_takeaways blocks; "
            "--finding and --notes still work and are merged in. A result named in "
            "the document must agree with --result."
        ),
    )
    review_record.add_argument(
        "--articles",
        help=(
            "Evidence and line only: comma-separated article ids whose review was "
            "actually repeated. Only they are re-bound from current disk state; "
            "every other article keeps the existing record's binding, reviewed_at "
            "and scores. Omit to record the full review."
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
    finish = actions.add_parser(
        "finish",
        help="Give an approved edition its stable id, freeze it, and open the next",
    )
    finish.add_argument("edition_id")
    finish.add_argument(
        "--as",
        dest="final_id",
        help="Override the stable id derived from the issue number and title",
    )
    finish.add_argument(
        "--next-edition-id",
        help="Override the next empty collecting edition id",
    )
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


def _load_verdict(path: Path | None, *, kind: str, result: str) -> dict[str, Any]:
    """Read a judge's YAML verdict document, the shape the prompts emit.

    The four editorial prompts each end with "return one YAML document and
    nothing else", so the operator's job is to hand that document to the
    recorder rather than to retype its findings as ``--finding`` strings.  The
    document supplies the structured findings, the advisory scores, and the
    learning review's ``comprehension`` and ``manager_takeaways`` blocks.

    ``--result`` stays required on the command line and stays authoritative:
    recording a verdict is a human act, and a document whose own ``result``
    disagrees with what the operator typed is a mismatch worth refusing rather
    than a preference worth resolving.
    """

    if path is None:
        return {}
    data = load_structured(path)
    declared = str(data.get("result") or "").strip()
    if declared and declared != result:
        raise MagazineError(
            f"{path} records result {declared!r} but --result says {result!r}; "
            "record the verdict the judge actually returned"
        )
    unknown = sorted(
        set(data)
        - {
            "result",
            "findings",
            "scores",
            "notes",
            "comprehension",
            "manager_takeaways",
        }
    )
    if unknown:
        raise MagazineError(
            f"{path} carries keys a {kind} review does not record: "
            + ", ".join(unknown)
        )
    return data


def _article_scores(
    scores: Any, *, articles: list[str] | None
) -> dict[str, Any] | None:
    """Resolve a per-article kind's ``scores`` block to article -> dimensions.

    The line editor and the fact-checker each read one piece at a time, so
    their prompts emit a flat dimension map for the piece in front of them.
    That map is unambiguous only when the recording names exactly one article,
    which ``--articles`` does.  A verdict covering several pieces at once must
    say so itself, by nesting the maps under article ids.
    """

    if not scores:
        return None
    if not isinstance(scores, dict):
        raise MagazineError("A verdict's scores must be a mapping")
    if all(isinstance(value, dict) for value in scores.values()):
        return scores
    if any(isinstance(value, dict) for value in scores.values()):
        raise MagazineError(
            "A verdict's scores must be either one flat dimension map or one map "
            "per article id, not a mixture"
        )
    if articles and len(articles) == 1:
        return {articles[0]: scores}
    raise MagazineError(
        "A flat scores map belongs to one article; name it with `--articles "
        "<id>`, or nest the scores under article ids in the verdict document"
    )


def _produce_articles(values: list[str] | None) -> list[str] | None:
    """Accept ``--articles a b`` and ``--articles a,b`` alike.

    The review bench spells this flag as one comma-separated string and the
    rest of the CLI spells list flags as repeats.  A human should not have to
    remember which command took which, so produce takes both.
    """

    if values is None:
        return None
    names = [
        item.strip()
        for value in values
        for item in str(value).split(",")
        if item.strip()
    ]
    if not names:
        raise MagazineError("--articles needs at least one piece id")
    return names


def _produce_submission(args: Any) -> tuple[str, str] | None:
    """Read the text for ``--submit`` from ``--reply`` or from stdin.

    Stdin is the default because that is how a driver already pipes a subagent's
    answer, and ``--reply`` is for the human who wrote the file first. Refusing
    an empty submission here keeps a mistyped redirect from being ingested as a
    blank manuscript.
    """

    if args.submit is None:
        if args.reply is not None:
            raise MagazineError("--reply names the text for --submit; pass both")
        return None
    if args.reply is not None:
        text = Path(args.reply).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()
    if not text.strip():
        raise MagazineError(
            f"--submit {args.submit} was given no text; supply it with --reply "
            "PATH or on stdin"
        )
    return str(args.submit), text


def _produce_lines(result: Any) -> list[str]:
    lines = [
        f"{result.plan.edition_id}: {result.plan.backend}"
        + (f"/{result.plan.model}" if result.plan.model else "")
        + f", max {result.plan.max_rounds} round(s)"
    ]
    if result.dry_run:
        lines.append("dry run: no model was called and nothing was written")
        for piece in result.plan.pieces:
            lines.append(
                f"plan: {piece.piece_id} ({piece.content_mode}) {piece.action} "
                f"[{piece.prompt_path}@{piece.prompt_sha256[:12]}]"
            )
    for outcome in result.outcomes:
        lines.append(
            f"{outcome.status}: {outcome.piece_id} after {outcome.rounds} round(s) "
            f"-> {outcome.record}"
        )
    for kind, path in result.recorded.items():
        lines.append(f"recorded: {kind} -> {path}")
    for item in result.ready:
        lines.append(
            f"ready: {item.key} ({item.returns}) read {item.brief_path}, "
            f"write {item.reply_path}"
        )
    if result.ready:
        lines.append(
            f"next: answer the {len(result.ready)} brief(s) above, then run "
            "produce again"
        )
    for action in result.human_actions:
        lines.append(f"human: {action}")
    lines.extend(_completion_lines(result))
    return lines


def _produce_exit_code(result: Any) -> int:
    """Zero when the graph advanced or finished; one when it stopped short.

    The distinction a driving loop reads without parsing anything, and the one
    the incident turned on.  A run that emitted briefs has *advanced*: there is
    outstanding work, it is named, and answering it is the loop.  A run that
    finished the graph is done.  Everything else is a run that stopped -- no
    brief to hand a worker, and nodes still unreached -- which is the state the
    operator read as "all pieces passed, nothing alarming" and built a PDF from.

    An escalation and an inconsistency exit one whatever else is outstanding:
    neither is cleared by answering another brief, so a loop that treats them
    as progress will spin.
    """

    if result.dry_run:
        return 0
    if result.escalated:
        return 1
    graph = getattr(result, "graph", None)
    if graph is not None and graph.inconsistent:
        return 1
    if result.complete:
        return 0
    return 1 if not result.ready else 0


def _completion_lines(result: Any) -> list[str]:
    """State, on every exit, whether the graph is complete or where it stopped.

    Last, and unconditional.  The run this exists because of ended with eight
    cheerful ``settled:`` lines and nothing else, and the operator read that as
    an edition that was finished -- correctly, because every line printed was
    true and the one fact that mattered was not a line at all.  A produce run
    now cannot end without answering the only question its caller has.
    """

    graph = getattr(result, "graph", None)
    if result.dry_run:
        return ["graph: not evaluated; this was a dry run"]
    if graph is None:
        return []
    if graph.complete:
        return [
            "COMPLETE: every declared production node has reached an accepting "
            "state; this edition may be built."
        ]
    if graph.legacy:
        return [
            "graph: this edition carries no production records and predates "
            "`mag produce`; its graph does not apply."
        ]
    unreached = graph.unreached
    lines = [
        f"INCOMPLETE: the production graph stopped with {len(unreached)} "
        f"node(s) unreached. This edition is NOT finished and must not be built."
    ]
    lines.extend(
        f"  unreached: {node.id} ({node.state}) -- "
        + (node.detail or node.spec.accepting)
        for node in unreached
    )
    lines.append(
        f"  see `mag produce {graph.edition_id} --graph` for the whole traversal"
    )
    return lines


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
        elif args.command == "scores":
            if args.check:
                if magazine.scores_are_current():
                    print(f"current: {magazine.scores_path}")
                    return 0
                raise MagazineError(
                    f"{magazine.scores_path} does not match the committed review "
                    "records; regenerate it with `mag scores`"
                )
            print(magazine.write_scores())
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
        elif args.command == "produce" and args.graph:
            # Deliberately before the runner is resolved: asking where an
            # edition stands must never depend on a model backend being
            # configured, and must never be able to move the edition.
            graph = magazine.production_graph(args.edition_id)
            if args.json:
                _print_json(graph.to_dict(), root=magazine.root)
            else:
                for line in graph.render():
                    print(line)
            return 0 if graph.complete else 1
        elif args.command == "produce":
            result = magazine.produce(
                args.edition_id,
                articles=_produce_articles(args.articles),
                dry_run=args.dry_run,
                max_rounds=args.max_rounds,
                reviewer=args.reviewer,
                backend=args.backend,
                submit=_produce_submission(args),
            )
            if args.json:
                _print_json(result.to_dict(), root=magazine.root)
            else:
                for line in _produce_lines(result):
                    print(line)
            return _produce_exit_code(result)
        elif args.command == "finding" and args.finding_command == "file":
            path = magazine.file_finding(
                args.edition_id,
                args.piece_id,
                severity=args.severity,
                category=args.category,
                note=args.note,
                locator=args.locator,
                repair_from=args.repair_from,
                suggestion=args.suggestion,
                filed_by=args.filed_by,
            )
            print(
                f"filed: {args.piece_id} -> {path}\n"
                f"next: uv run --locked mag produce {args.edition_id} "
                f"--articles {args.piece_id}"
            )
        elif args.command == "finding" and args.finding_command == "list":
            rows = magazine.filed_findings(args.edition_id)
            if args.json:
                _print_json(rows, root=magazine.root)
            else:
                for row in rows:
                    print(
                        f"{row.get('status')}: {row.get('piece')} "
                        f"[{row.get('severity')}] {row.get('category')} "
                        f"({row.get('filed_by')}) {row.get('note')}"
                    )
                print(
                    f"{sum(1 for row in rows if row.get('status') == 'open')} open, "
                    f"{len(rows)} filed"
                )
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
            if args.opener is not None:
                if args.language is not None:
                    raise MagazineError(
                        "--opener checks one authored paragraph against one "
                        "article's opener budget, which is a property of the "
                        "manuscript rather than of a language overlay; drop "
                        "--language"
                    )
                report, ok = magazine.opener_fit(
                    args.edition_id, args.opener, sys.stdin.read()
                )
            else:
                report, ok = magazine.fit(args.edition_id, language=args.language)
            print(report)
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
            status["line"] = magazine.line_review_status(args.edition_id)
            status["edition"] = magazine.edition_review_status(args.edition_id)
            status["learning"] = magazine.learning_review_status(args.edition_id)
            print(json.dumps(status, ensure_ascii=False, indent=2))
        elif args.command == "review" and args.review_command == "record":
            if args.kind != "render":
                if args.engine:
                    raise MagazineError(
                        f"--engine applies only to render reviews; a {args.kind} review "
                        "binds to authored text, not rendered PDFs"
                    )
                if args.rebuild:
                    raise MagazineError(
                        f"--rebuild applies only to render reviews; a {args.kind} review "
                        "touches no package"
                    )
                # ``is not None`` rather than truthiness: even an empty
                # ``--articles ""`` expresses the intent to narrow and must be
                # refused by a kind that cannot narrow, not silently ignored.
                if (
                    args.articles is not None
                    and args.kind not in PER_ARTICLE_REVIEW_KINDS
                ):
                    raise MagazineError(
                        "--articles applies only to evidence reviews and line "
                        f"reviews; a {args.kind} review binds the whole issue at "
                        "once, not individual articles"
                    )
                verdict = _load_verdict(args.verdict, kind=args.kind, result=args.result)
                findings = [*verdict.get("findings", []), *args.finding]
                notes = args.notes or str(verdict.get("notes") or "")
                articles = None
                if args.articles is not None:
                    articles = [
                        item.strip() for item in args.articles.split(",") if item.strip()
                    ]
                if args.kind in PER_ARTICLE_REVIEW_KINDS:
                    scores = _article_scores(verdict.get("scores"), articles=articles)
                    recorder = (
                        magazine.record_evidence_review
                        if args.kind == "evidence"
                        else magazine.record_line_review
                    )
                    path = recorder(
                        args.edition_id,
                        reviewer=args.reviewer,
                        result=args.result,
                        findings=findings,
                        scores=scores,
                        notes=notes,
                        articles=articles,
                    )
                elif args.kind == "edition":
                    path = magazine.record_edition_review(
                        args.edition_id,
                        reviewer=args.reviewer,
                        result=args.result,
                        findings=findings,
                        scores=verdict.get("scores"),
                        notes=notes,
                    )
                else:
                    path = magazine.record_learning_review(
                        args.edition_id,
                        reviewer=args.reviewer,
                        result=args.result,
                        findings=findings,
                        scores=verdict.get("scores"),
                        comprehension=verdict.get("comprehension") or (),
                        manager_takeaways=verdict.get("manager_takeaways") or (),
                        notes=notes,
                    )
                print(f"recorded: {path}")
            else:
                if args.articles is not None:
                    raise MagazineError(
                        "--articles applies only to evidence reviews and line "
                        "reviews; a render review binds whole-language PDFs, not "
                        "individual articles"
                    )
                if args.verdict is not None:
                    raise MagazineError(
                        "--verdict carries an editorial judge's findings and scores; "
                        "a render review records a visual decision with --finding"
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
        elif args.command == "finish":
            result, transition = magazine.finish(
                args.edition_id,
                final_id=args.final_id,
                next_edition_id=args.next_edition_id,
            )
            print(
                f"finished: {transition.released_edition_id}\n"
                f"pdf: {result.reader_pdf}\n"
                f"next: {transition.next_edition_id}"
            )
        return 0
    except MagazineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
