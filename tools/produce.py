#!/usr/bin/env python3
"""produce.py — sources in, edition content out.

One file, no state outside memory and plain output files. If it dies, rerun it
(`--resume <run-dir>` skips pieces whose final.md already exists).

  python3 tools/produce.py plan 005
  python3 tools/produce.py run editions/005-unreleased/plan.yaml
  python3 tools/produce.py run plan.yaml --resume runs/005/2026-08-04T18-00-00
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML missing. Run under the project env: uv run python tools/produce.py ...")

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"
DOCS = ROOT / "docs"
LIBRARY = ROOT / "library" / "sources"
RUNS = ROOT / "runs"

CONFIG = {
    "writer_model": "opus",
    "judge_model": "sonnet",
    "plan_model": "opus",
    "max_rewrite_rounds": 2,
    "concurrency": 8,
    "call_timeout": 600,
    "call_retries": 2,
}

# Which lenses run on what, and which may see the source. Source-blindness is
# enforced by construction: a blind lens's prompt simply never contains the
# source text, and headless calls run with every tool denied.
ARTICLE_LENSES = {
    "worth": {"file": "worth-review.md", "sources": True},
    "evidence": {"file": "evidence-review.md", "sources": True},
    "mechanics": {"file": "mechanics-review.md", "sources": False},
    "shape": {"file": "shape-review.md", "sources": False},
    "craft": {"file": "craft-review.md", "sources": False},
}
EXPLAINER_LENSES = {"teaching": {"file": "teaching-review.md", "sources": True}}
EDITORIAL_LENSES = {k: ARTICLE_LENSES[k] for k in ("mechanics", "shape", "craft")}

WRITER_PROMPTS = {
    "faithful_synthesis": "faithful-synthesis.md",
    "faithful_edit": "faithful-edit.md",
    "in_a_nutshell": "in-a-nutshell.md",
}

LOOP_SEVERITIES = {"blocking", "major"}

INLINE_PREAMBLE = (
    "You are running non-interactively with NO file access and NO tools. Every\n"
    "document you need is inlined below. If an included instruction tells you to\n"
    "read a file or path, the content of that file is already included here —\n"
    "never claim to have read anything that is not inlined."
)


def section(title: str, body: str) -> str:
    return f"\n\n========== {title} ==========\n\n{body.strip()}\n"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def source_text(source_id: str) -> str:
    path = LIBRARY / source_id / "extracted.md"
    if not path.exists():
        raise FileNotFoundError(f"no extraction for source '{source_id}' at {path}")
    return read(path)


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")


class Caller:
    """Serializes model access through `claude -p` with everything denied."""

    def __init__(self, run_dir: Path):
        self.sem = asyncio.Semaphore(CONFIG["concurrency"])
        self.log_path = run_dir / "log.jsonl"
        self.total_cost = 0.0
        self.calls = 0

    async def llm(self, label: str, model: str, prompt: str, parse=None):
        """Run one headless call; `parse` failures count as retryable failures,
        with the parse error fed back into the retry prompt."""
        last_error = None
        for attempt in range(CONFIG["call_retries"] + 1):
            sent = prompt if not last_error else (
                prompt + f"\n\nYour previous reply was rejected: {last_error}. "
                "Reply again following the required output format exactly."
            )
            async with self.sem:
                started = time.monotonic()
                proc = await asyncio.create_subprocess_exec(
                    "claude", "-p", "--model", model,
                    "--output-format", "json",
                    "--no-session-persistence",
                    "--disallowedTools", "*",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(ROOT),
                )
                try:
                    out, err = await asyncio.wait_for(
                        proc.communicate(sent.encode()), CONFIG["call_timeout"]
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    last_error = f"timeout after {CONFIG['call_timeout']}s"
                    continue
                seconds = time.monotonic() - started
            try:
                data = json.loads(out.decode())
            except json.JSONDecodeError:
                last_error = f"non-JSON output (exit {proc.returncode}): {err.decode()[:300]}"
                continue
            if data.get("is_error") or data.get("subtype") != "success":
                last_error = f"call failed: {json.dumps(data)[:300]}"
                continue
            cost = float(data.get("total_cost_usd") or 0.0)
            self.total_cost += cost
            self.calls += 1
            if parse is not None:
                try:
                    parsed = parse(data["result"])
                except Exception as e:  # noqa: BLE001 — feed back into retry
                    last_error = str(e)
                    continue
            with self.log_path.open("a") as f:
                f.write(json.dumps({
                    "label": label, "model": model, "seconds": round(seconds, 1),
                    "usd": round(cost, 4), "attempt": attempt,
                }) + "\n")
            print(f"    {label} [{model}] {seconds:.0f}s ${cost:.2f}", flush=True)
            return parsed if parse is not None else data["result"]
        raise RuntimeError(f"{label}: model call failed after retries — {last_error}")


SCRATCH_MARKER = "<!-- SCRATCH: not part of the manuscript -->"


def extract_manuscript(reply: str, label: str) -> str:
    matches = re.findall(r"<manuscript>(.*?)</manuscript>", reply, re.DOTALL)
    if not matches:
        raise RuntimeError(f"{label}: reply contained no <manuscript> block")
    return matches[-1].split(SCRATCH_MARKER)[0].strip() + "\n"


def extract_findings(reply: str, label: str) -> dict:
    fences = re.findall(r"```ya?ml\s*\n(.*?)```", reply, re.DOTALL)
    # A bare yaml document is accepted: a complete report is not worth
    # rejecting over a missing fence.
    data = yaml.safe_load(fences[-1] if fences else reply.strip())
    if not isinstance(data, dict) or "findings" not in data:
        raise RuntimeError(f"{label}: yaml block has no findings key")
    data["findings"] = data.get("findings") or []
    return data


def loop_findings(reports: dict[str, dict]) -> list[dict]:
    hits = []
    for lens, report in reports.items():
        for finding in report["findings"]:
            if str(finding.get("severity", "")).lower() in LOOP_SEVERITIES:
                hits.append({"lens": lens, **finding})
    return hits


def writing_pack() -> str:
    return (
        section("docs/WRITING_STYLE.md", read(DOCS / "WRITING_STYLE.md"))
        + section("docs/WRITING_RULES.md", read(DOCS / "WRITING_RULES.md"))
    )


def writer_prompt(article: dict, sources: dict[str, str], draft: str | None,
                  findings: list[dict] | None) -> str:
    mode = article["content_mode"]
    parts = [INLINE_PREAMBLE,
             section(f"prompts/{WRITER_PROMPTS[mode]}", read(PROMPTS / WRITER_PROMPTS[mode])),
             writing_pack(),
             section("edition.yaml article row", yaml.safe_dump(article, sort_keys=False))]
    for sid, text in sources.items():
        parts.append(section(f"source extraction: {sid}", text))
    if draft is not None:
        parts.append(section("current manuscript (to revise)", draft))
        parts.append(section("review findings to address", yaml.safe_dump(findings, sort_keys=False)))
        parts.append(
            "\nRevise the manuscript to resolve every finding above without breaking "
            "the writing rules. Return the complete revised manuscript between "
            "<manuscript> and </manuscript> tags."
        )
    else:
        parts.append(
            "\nFollow the production prompt above (including its pre-draft answers, "
            "written before the manuscript). Return the complete manuscript between "
            "<manuscript> and </manuscript> tags."
        )
    return "".join(parts)


def judge_prompt(lens: str, spec: dict, piece_label: str, manuscript: str,
                 article: dict | None, sources: dict[str, str]) -> str:
    parts = [INLINE_PREAMBLE,
             section(f"prompts/{spec['file']}", read(PROMPTS / spec["file"]))]
    if article is not None:
        parts.append(section("edition.yaml article row", yaml.safe_dump(article, sort_keys=False)))
    parts.append(section(f"manuscript: {piece_label}", manuscript))
    if spec["sources"]:
        for sid, text in sources.items():
            parts.append(section(f"pinned source extraction: {sid}", text))
    parts.append(
        "\nApply your lens exactly as specified. End your reply with the yaml "
        "findings block in the format the lens prompt defines (```yaml ... ```), "
        "with `findings: []` for a clean pass."
    )
    return "".join(parts)


async def judge(caller: Caller, model: str, piece_label: str, manuscript: str,
                lenses: dict, article: dict | None, sources: dict[str, str],
                round_no: int) -> dict[str, dict]:
    async def one(lens: str, spec: dict) -> tuple[str, dict]:
        report = await caller.llm(f"{piece_label} r{round_no} judge:{lens}", model,
                                  judge_prompt(lens, spec, piece_label, manuscript, article, sources),
                                  parse=lambda r: extract_findings(r, f"{piece_label}:{lens}"))
        return lens, report

    results = await asyncio.gather(*(one(k, v) for k, v in lenses.items()))
    return dict(results)


async def produce_piece(caller: Caller, run_dir: Path, piece_id: str, article: dict | None,
                        lenses: dict, sources: dict[str, str],
                        writer_model: str, judge_model: str,
                        first_draft: "str | None" = None) -> dict:
    """Write → judge → rewrite loop for one article or the editorial."""
    out = run_dir / ("editorial" if article is None else f"articles/{piece_id}")
    out.mkdir(parents=True, exist_ok=True)
    final_path = out / "final.md"
    if final_path.exists():
        print(f"  {piece_id}: final.md exists, skipping (resume)")
        return yaml.safe_load(read(out / "status.yaml"))

    status = {"piece": piece_id, "rounds": [], "state": "in_progress"}
    draft, findings = first_draft, None
    for round_no in range(1, CONFIG["max_rewrite_rounds"] + 2):
        if draft is None or findings:
            label = f"{piece_id} r{round_no} {'write' if draft is None else 'rewrite'}"
            draft = await caller.llm(label, writer_model,
                                     writer_prompt(article, sources, draft, findings)
                                     if article is not None else editorial_prompt(draft, findings, sources),
                                     parse=lambda r: extract_manuscript(r, label))
        (out / f"draft-{round_no}.md").write_text(draft)

        reports = await judge(caller, judge_model, piece_id, draft, lenses, article, sources, round_no)
        (out / f"findings-{round_no}.yaml").write_text(yaml.safe_dump(reports, sort_keys=False))
        findings = loop_findings(reports)
        status["rounds"].append({
            "round": round_no,
            "words": len(draft.split()),
            "loop_findings": len(findings),
            "all_findings": sum(len(r["findings"]) for r in reports.values()),
        })
        if not findings:
            status["state"] = "clean"
            break
        if round_no > CONFIG["max_rewrite_rounds"]:
            status["state"] = "rounds_exhausted"
            break
    final_path.write_text(draft)
    status["open_findings"] = findings or []
    (out / "status.yaml").write_text(yaml.safe_dump(status, sort_keys=False))
    print(f"  {piece_id}: {status['state']} after {len(status['rounds'])} round(s)")
    return status


def editorial_prompt(draft: str | None, findings: list[dict] | None,
                     articles_final: dict[str, str]) -> str:
    parts = [INLINE_PREAMBLE,
             section("prompts/opening-editorial.md", read(PROMPTS / "opening-editorial.md")),
             writing_pack()]
    for aid, text in articles_final.items():
        parts.append(section(f"accepted article: {aid}", text))
    if draft is not None:
        parts.append(section("current editorial (to revise)", draft))
        parts.append(section("review findings to address", yaml.safe_dump(findings, sort_keys=False)))
        parts.append("\nRevise the editorial to resolve every finding. Return it between "
                     "<manuscript> and </manuscript> tags.")
    else:
        parts.append("\nWrite the opening editorial per the prompt above. Return it between "
                     "<manuscript> and </manuscript> tags.")
    return "".join(parts)


async def run_edition(plan_path: Path, resume: Path | None, only: set[str] | None,
                      writer_model: str, judge_model: str) -> int:
    plan = yaml.safe_load(read(plan_path))
    edition = str(plan["edition"]["id"])
    run_dir = resume or RUNS / edition / now_stamp()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "plan.yaml").write_text(yaml.safe_dump(plan, sort_keys=False))
    caller = Caller(run_dir)
    started = time.monotonic()
    print(f"run dir: {run_dir}")

    articles = [a for a in plan["articles"] if not only or a["id"] in only]

    async def one_article(article: dict):
        lenses = dict(ARTICLE_LENSES)
        if article["content_mode"] == "in_a_nutshell":
            lenses.update(EXPLAINER_LENSES)
        sources = {sid: source_text(sid) for sid in article["source_ids"]}
        return await produce_piece(caller, run_dir, article["id"], article, lenses,
                                   sources, writer_model, judge_model)

    results = await asyncio.gather(*(one_article(a) for a in articles), return_exceptions=True)
    statuses, failures = [], []
    for article, res in zip(articles, results):
        if isinstance(res, BaseException):
            failures.append((article["id"], str(res)))
            print(f"  FAILED {article['id']}: {res}", file=sys.stderr)
        else:
            statuses.append(res)

    editorial_status = None
    finals = {a["id"]: read(run_dir / f"articles/{a['id']}/final.md")
              for a in articles if (run_dir / f"articles/{a['id']}/final.md").exists()}
    if finals and not failures:
        try:
            editorial_status = await produce_piece(
                caller, run_dir, "editorial", None, EDITORIAL_LENSES, finals,
                writer_model, judge_model)
        except Exception as e:  # noqa: BLE001 — record and keep the run's artifacts
            failures.append(("editorial", str(e)))
            print(f"  FAILED editorial: {e}", file=sys.stderr)

    edition_report = None
    if finals:
        pieces = dict(finals)
        editorial_final = run_dir / "editorial/final.md"
        if editorial_final.exists():
            pieces["editorial"] = read(editorial_final)
        prompt = INLINE_PREAMBLE + section(
            "prompts/edition-review.md", read(PROMPTS / "edition-review.md"))
        prompt += section("edition plan", yaml.safe_dump(plan["edition"], sort_keys=False))
        for pid, text in pieces.items():
            prompt += section(f"piece: {pid}", text)
        prompt += ("\nReview the edition as specified. End with the yaml findings "
                   "block (```yaml ... ```).")
        try:
            edition_report = await caller.llm(
                "edition-review", judge_model, prompt,
                parse=lambda r: extract_findings(r, "edition-review"))
            (run_dir / "edition-review.yaml").write_text(
                yaml.safe_dump(edition_report, sort_keys=False))
        except Exception as e:  # noqa: BLE001
            failures.append(("edition-review", str(e)))
            print(f"  FAILED edition-review: {e}", file=sys.stderr)

    minutes = (time.monotonic() - started) / 60
    lines = [f"# Run summary — edition {edition}", "",
             f"- {caller.calls} model calls, ${caller.total_cost:.2f}, {minutes:.1f} minutes",
             f"- writer `{writer_model}`, judges `{judge_model}`", "",
             "| piece | state | rounds | words | open findings |", "|---|---|---|---|---|"]
    for st in statuses + ([editorial_status] if editorial_status else []):
        last = st["rounds"][-1] if st["rounds"] else {}
        lines.append(f"| {st['piece']} | {st['state']} | {len(st['rounds'])} | "
                     f"{last.get('words', '—')} | {len(st['open_findings'])} |")
    for pid, err in failures:
        lines.append(f"| {pid} | **FAILED** | — | — | {err[:80]} |")
    if edition_report is not None:
        lines += ["", f"Edition review: {len(edition_report['findings'])} finding(s) "
                      f"— see edition-review.yaml"]
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n")
    print(f"\n{run_dir / 'summary.md'}")
    print("\n".join(lines))
    return 1 if failures else 0


async def propose_plan(edition: str, model: str) -> int:
    edition_dirs = sorted(ROOT.glob(f"editions/{edition}*"))
    out_path = (edition_dirs[0] if edition_dirs else ROOT / f"editions/{edition}") / "plan.yaml"
    if out_path.exists():
        sys.exit(f"{out_path} already exists; edit it or delete it first")
    excerpts = []
    for src_dir in sorted(LIBRARY.iterdir()):
        extract = src_dir / "extracted.md"
        if extract.exists():
            body = read(extract)
            excerpts.append(section(f"source: {src_dir.name}",
                                    " ".join(body.split()[:600])))
    past = [read(p) for p in sorted(ROOT.glob("editions/00*/edition.yaml"))]
    prompt = (
        INLINE_PREAMBLE
        + section("task", (
            f"Propose the plan for edition {edition} of this magazine. Pick the 7 "
            "strongest, most complementary unpublished sources below (skip any "
            "already used by a past edition), pair related sources where it makes "
            "one better article, and assign each article a content_mode: "
            "faithful_synthesis (retell at ~1/3 length), faithful_edit (light edit "
            "at source length), or in_a_nutshell (explainer). Derive authors from "
            "the sources. Return exactly one yaml document between <plan> and "
            "</plan> tags with this shape:\n\n"
            "edition:\n  id: <id>\n  title: ...\n  subtitle: ...\n"
            "articles:\n- id: <slug>\n  title: ...\n  short_title: ...\n"
            "  author: ...\n  author_note: ...\n  content_mode: ...\n"
            "  source_ids: [ ... ]\n  rationale: <one line>"))
        + section("past edition specs (for used sources and tone)", "\n---\n".join(past))
        + "".join(excerpts)
    )
    run_dir = RUNS / edition
    run_dir.mkdir(parents=True, exist_ok=True)
    caller = Caller(run_dir)
    reply = await caller.llm(f"plan {edition}", model, prompt)
    match = re.findall(r"<plan>(.*?)</plan>", reply, re.DOTALL)
    if not match:
        sys.exit("plan reply contained no <plan> block")
    plan = yaml.safe_load(match[-1])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(plan, sort_keys=False, allow_unicode=True))
    print(f"\nwrote {out_path} — edit it, then: python3 tools/produce.py run {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_plan = sub.add_parser("plan", help="propose a plan.yaml for an edition")
    p_plan.add_argument("edition")
    p_plan.add_argument("--model", default=CONFIG["plan_model"])
    p_run = sub.add_parser("run", help="produce an edition from a plan.yaml")
    p_run.add_argument("plan", type=Path)
    p_run.add_argument("--resume", type=Path, default=None,
                       help="existing run dir; pieces with final.md are skipped")
    p_run.add_argument("--only", default=None, help="comma-separated article ids")
    p_run.add_argument("--writer-model", default=CONFIG["writer_model"])
    p_run.add_argument("--judge-model", default=CONFIG["judge_model"])
    args = parser.parse_args()
    if args.cmd == "plan":
        return asyncio.run(propose_plan(args.edition, args.model))
    return asyncio.run(run_edition(
        args.plan, args.resume, set(args.only.split(",")) if args.only else None,
        args.writer_model, args.judge_model))


if __name__ == "__main__":
    sys.exit(main())
