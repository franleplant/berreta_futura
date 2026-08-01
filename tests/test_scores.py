"""Tests for the derived cross-edition score rollup.

Fixture records are written with ``yaml.safe_dump`` directly rather than
through each kind's recorder: the rollup's whole claim is that it reads
committed records as raw data, and a test that built them with the kind
modules would be testing the loaders' agreement with themselves instead.
"""

from pathlib import Path
from shutil import which
from subprocess import run
from tempfile import TemporaryDirectory
import unittest

import yaml

from magazine.scores import (
    PER_ARTICLE_KINDS,
    SCORED_REVIEW_KINDS,
    SCORES_SCHEMA_VERSION,
    WHOLE_ISSUE_ARTICLE_ID,
    ScoreRow,
    collect_score_rows,
    render_scores,
    scores_are_current,
    scores_path,
    write_scores,
)


TIMESTAMP = "2026-08-01T10:00:00+00:00"
MANUSCRIPT_SHA = "a" * 64


def write_record(editions_dir: Path, edition_id: str, kind: str, record: dict) -> Path:
    path = editions_dir / edition_id / "reviews" / f"{kind}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    return path


def write_raw(editions_dir: Path, edition_id: str, kind: str, text: str) -> Path:
    path = editions_dir / edition_id / "reviews" / f"{kind}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def per_article_record(
    edition_id: str,
    *,
    result: str = "changes_required",
    articles: dict | None = None,
) -> dict:
    return {
        "schema_version": 3,
        "edition_id": edition_id,
        "reviewer": "Line editor",
        "reviewed_at": TIMESTAMP,
        "result": result,
        "findings": [],
        "notes": "",
        "articles": articles
        if articles is not None
        else {
            "eval-engineering": {
                "reviewed_at": TIMESTAMP,
                "manuscript_sha256": MANUSCRIPT_SHA,
                "scores": {"structure": 4, "flow": 3, "sentence_craft": 4},
            }
        },
    }


def whole_issue_record(
    edition_id: str, *, result: str = "approved", scores: object = None
) -> dict:
    return {
        "schema_version": 1,
        "edition_id": edition_id,
        "reviewer": "Edition critic",
        "reviewed_at": TIMESTAMP,
        "result": result,
        "findings": [],
        "notes": "",
        "scores": scores
        if scores is not None
        else {"through_line": 2, "editorial_strength": 1, "running_order": 4},
    }


class CollectScoreRowsTest(unittest.TestCase):
    def test_per_article_record_yields_one_row_per_article_dimension(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            write_record(editions, "004-systems", "line", per_article_record("004-systems"))
            rows = collect_score_rows(editions)
            self.assertEqual(
                [(row.article, row.dimension, row.score) for row in rows],
                [
                    ("eval-engineering", "flow", 3),
                    ("eval-engineering", "sentence_craft", 4),
                    ("eval-engineering", "structure", 4),
                ],
            )
            for row in rows:
                self.assertEqual(row.edition, "004-systems")
                self.assertEqual(row.kind, "line")
                self.assertEqual(row.round, 1)
                self.assertEqual(row.result, "changes_required")
                self.assertEqual(row.reviewed_at, TIMESTAMP)

    def test_per_article_row_falls_back_to_record_timestamp(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            record = per_article_record(
                "004-systems",
                articles={
                    "opener": {
                        "manuscript_sha256": MANUSCRIPT_SHA,
                        "scores": {"structure": 5},
                    }
                },
            )
            write_record(editions, "004-systems", "evidence", record)
            (row,) = collect_score_rows(editions)
            self.assertEqual(row.reviewed_at, TIMESTAMP)
            self.assertEqual(row.article, "opener")

    def test_whole_issue_record_keys_rows_to_the_edition(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            write_record(editions, "004-systems", "edition", whole_issue_record("004-systems"))
            rows = collect_score_rows(editions)
            self.assertEqual({row.article for row in rows}, {WHOLE_ISSUE_ARTICLE_ID})
            self.assertEqual(
                [(row.dimension, row.score) for row in rows],
                [("editorial_strength", 1), ("running_order", 4), ("through_line", 2)],
            )
            self.assertEqual({row.result for row in rows}, {"approved"})

    def test_edition_id_comes_from_the_directory_not_the_record(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            write_record(
                editions, "004-systems", "edition", whole_issue_record("some-other-edition")
            )
            rows = collect_score_rows(editions)
            self.assertTrue(rows)
            self.assertEqual({row.edition for row in rows}, {"004-systems"})

    def test_many_editions_and_kinds_sort_deterministically(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            write_record(editions, "005-later", "line", per_article_record("005-later"))
            write_record(editions, "004-systems", "edition", whole_issue_record("004-systems"))
            write_record(editions, "004-systems", "line", per_article_record("004-systems"))
            write_record(
                editions,
                "004-systems",
                "learning",
                whole_issue_record("004-systems", scores={"transfer": 3}),
            )
            rows = collect_score_rows(editions)
            keys = [
                (row.edition, row.kind, row.article, row.round, row.dimension)
                for row in rows
            ]
            self.assertEqual(keys, sorted(keys))
            self.assertEqual(
                sorted({(row.edition, row.kind) for row in rows}),
                [
                    ("004-systems", "edition"),
                    ("004-systems", "learning"),
                    ("004-systems", "line"),
                    ("005-later", "line"),
                ],
            )
            self.assertEqual(render_scores(rows), render_scores(collect_score_rows(editions)))

    def test_render_is_byte_identical_across_regeneration(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            write_record(editions, "004-systems", "line", per_article_record("004-systems"))
            write_record(editions, "004-systems", "edition", whole_issue_record("004-systems"))
            self.assertEqual(
                render_scores(collect_score_rows(editions)),
                render_scores(collect_score_rows(editions)),
            )

    def test_a_record_with_no_scores_contributes_nothing(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            write_record(
                editions,
                "004-systems",
                "line",
                per_article_record(
                    "004-systems",
                    articles={"opener": {"manuscript_sha256": MANUSCRIPT_SHA}},
                ),
            )
            write_record(
                editions,
                "004-systems",
                "edition",
                {
                    "schema_version": 1,
                    "edition_id": "004-systems",
                    "reviewed_at": TIMESTAMP,
                    "result": "approved",
                    "findings": [],
                },
            )
            self.assertEqual(collect_score_rows(editions), ())

    def test_render_review_records_are_never_read(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            # ``render.yaml`` carries no scores; if one somehow appeared there
            # the rollup must still ignore the kind entirely.
            write_record(
                editions,
                "004-systems",
                "render",
                whole_issue_record("004-systems", scores={"beauty": 5}),
            )
            self.assertNotIn("render", SCORED_REVIEW_KINDS)
            self.assertEqual(collect_score_rows(editions), ())

    def test_missing_editions_directory_is_empty_not_an_error(self) -> None:
        with TemporaryDirectory() as directory:
            self.assertEqual(collect_score_rows(Path(directory) / "editions"), ())


class ResilienceTest(unittest.TestCase):
    """A broken record must degrade the report, never break the command."""

    def assert_no_rows(self, build) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            build(editions)
            self.assertEqual(collect_score_rows(editions), ())

    def test_unparseable_record(self) -> None:
        self.assert_no_rows(
            lambda editions: write_raw(
                editions, "004-systems", "edition", "scores: {through_line: 3\n  bad: ["
            )
        )

    def test_record_that_is_not_a_mapping(self) -> None:
        self.assert_no_rows(
            lambda editions: write_raw(
                editions, "004-systems", "edition", "- a list, not a record\n"
            )
        )

    def test_empty_record_file(self) -> None:
        self.assert_no_rows(
            lambda editions: write_raw(editions, "004-systems", "edition", "")
        )

    def test_non_mapping_scores(self) -> None:
        self.assert_no_rows(
            lambda editions: write_record(
                editions,
                "004-systems",
                "edition",
                whole_issue_record("004-systems", scores=["through_line"]),
            )
        )

    def test_non_mapping_articles(self) -> None:
        self.assert_no_rows(
            lambda editions: write_record(
                editions,
                "004-systems",
                "line",
                {**per_article_record("004-systems"), "articles": "eval-engineering"},
            )
        )

    def test_article_row_that_is_not_a_mapping(self) -> None:
        self.assert_no_rows(
            lambda editions: write_record(
                editions,
                "004-systems",
                "line",
                per_article_record("004-systems", articles={"opener": "approved"}),
            )
        )

    def test_string_score(self) -> None:
        self.assert_no_rows(
            lambda editions: write_record(
                editions,
                "004-systems",
                "edition",
                whole_issue_record("004-systems", scores={"through_line": "4"}),
            )
        )

    def test_score_below_range(self) -> None:
        self.assert_no_rows(
            lambda editions: write_record(
                editions,
                "004-systems",
                "edition",
                whole_issue_record("004-systems", scores={"through_line": 0}),
            )
        )

    def test_score_above_range(self) -> None:
        self.assert_no_rows(
            lambda editions: write_record(
                editions,
                "004-systems",
                "edition",
                whole_issue_record("004-systems", scores={"through_line": 6}),
            )
        )

    def test_boolean_score_is_not_an_integer(self) -> None:
        self.assert_no_rows(
            lambda editions: write_record(
                editions,
                "004-systems",
                "edition",
                whole_issue_record("004-systems", scores={"through_line": True}),
            )
        )

    def test_a_broken_record_does_not_suppress_a_good_one(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            write_raw(editions, "004-systems", "edition", "{ broken\n")
            write_record(
                editions,
                "004-systems",
                "learning",
                whole_issue_record("004-systems", scores={"transfer": 5}),
            )
            (row,) = collect_score_rows(editions)
            self.assertEqual((row.kind, row.dimension, row.score), ("learning", "transfer", 5))


class RenderScoresTest(unittest.TestCase):
    def test_empty_input_still_produces_a_banner_and_an_empty_rows_list(self) -> None:
        text = render_scores([])
        self.assertTrue(text.startswith("# Generated by `mag scores` from"))
        self.assertIn("Do not edit by hand.", text)
        self.assertIn("rows: []", text)
        document = yaml.safe_load(text)
        self.assertEqual(document["schema_version"], SCORES_SCHEMA_VERSION)
        self.assertEqual(document["rows"], [])
        self.assertEqual(
            document["generated_from"],
            "editions/*/reviews/{evidence,line,edition,learning}.yaml",
        )

    def test_rows_keep_a_fixed_key_order(self) -> None:
        row = ScoreRow(
            edition="004-systems",
            kind="line",
            article="eval-engineering",
            round=1,
            dimension="structure",
            score=4,
            result="changes_required",
            reviewed_at=TIMESTAMP,
            rounds_to_approval=2,
        )
        self.assertEqual(
            list(row.to_dict()),
            [
                "edition",
                "kind",
                "article",
                "round",
                "dimension",
                "score",
                "result",
                "reviewed_at",
                "rounds_to_approval",
            ],
        )
        text = render_scores([row])
        self.assertEqual(yaml.safe_load(text)["rows"], [row.to_dict()])
        self.assertLess(text.index("- edition:"), text.index("  kind:"))
        self.assertLess(text.index("  score:"), text.index("  rounds_to_approval:"))

    def test_an_unapproved_pair_renders_a_null_rounds_to_approval(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            write_record(editions, "004-systems", "line", per_article_record("004-systems"))
            document = yaml.safe_load(render_scores(collect_score_rows(editions)))
            self.assertEqual(
                {row["rounds_to_approval"] for row in document["rows"]}, {None}
            )


class WriteScoresTest(unittest.TestCase):
    def test_writes_the_rollup_and_is_idempotent(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            write_record(editions, "004-systems", "line", per_article_record("004-systems"))
            path = write_scores(editions)
            self.assertEqual(path, scores_path(editions))
            self.assertEqual(path, editions / "scores.yaml")
            first = path.read_text(encoding="utf-8")
            self.assertEqual(write_scores(editions).read_text(encoding="utf-8"), first)
            self.assertEqual(first, render_scores(collect_score_rows(editions)))

    def test_the_rollup_file_is_not_mistaken_for_an_edition(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            write_record(editions, "004-systems", "edition", whole_issue_record("004-systems"))
            before = collect_score_rows(editions)
            write_scores(editions)
            self.assertEqual(collect_score_rows(editions), before)

    def test_scores_are_current_tracks_the_file_on_disk(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            write_record(editions, "004-systems", "line", per_article_record("004-systems"))
            self.assertFalse(scores_are_current(editions))
            path = write_scores(editions)
            self.assertTrue(scores_are_current(editions))
            path.write_text(
                path.read_text(encoding="utf-8").replace("score: 4", "score: 5"),
                encoding="utf-8",
            )
            self.assertFalse(scores_are_current(editions))
            path.unlink()
            self.assertFalse(scores_are_current(editions))

    def test_a_new_record_makes_the_rollup_stale(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            write_record(editions, "004-systems", "line", per_article_record("004-systems"))
            write_scores(editions)
            self.assertTrue(scores_are_current(editions))
            write_record(editions, "005-later", "edition", whole_issue_record("005-later"))
            self.assertFalse(scores_are_current(editions))


class RoundsWithoutGitTest(unittest.TestCase):
    """The fallback path: a plain directory is one round per record, always."""

    def test_every_record_is_round_one(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            write_record(editions, "004-systems", "line", per_article_record("004-systems"))
            write_record(editions, "004-systems", "edition", whole_issue_record("004-systems"))
            rows = collect_score_rows(editions)
            self.assertTrue(rows)
            self.assertEqual({row.round for row in rows}, {1})

    def test_rounds_to_approval_is_one_when_approved_and_none_otherwise(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            write_record(
                editions, "004-systems", "edition", whole_issue_record("004-systems")
            )
            write_record(
                editions,
                "004-systems",
                "line",
                per_article_record("004-systems", result="changes_required"),
            )
            by_kind = {}
            for row in collect_score_rows(editions):
                by_kind.setdefault(row.kind, set()).add(row.rounds_to_approval)
            self.assertEqual(by_kind["edition"], {1})
            self.assertEqual(by_kind["line"], {None})

    def test_an_explicit_root_outside_any_repository_still_degrades(self) -> None:
        with TemporaryDirectory() as directory:
            editions = Path(directory) / "editions"
            write_record(editions, "004-systems", "edition", whole_issue_record("004-systems"))
            rows = collect_score_rows(editions, root=Path(directory))
            self.assertTrue(rows)
            self.assertEqual({row.round for row in rows}, {1})


def git(root: Path, *arguments: str) -> None:
    completed = run(
        ["git", "-C", str(root), *arguments], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"git {' '.join(arguments)} failed: {completed.stderr.strip()}"
        )


def init_repository(root: Path) -> None:
    if which("git") is None:
        raise unittest.SkipTest("git is not on PATH")
    git(root, "init", "--quiet")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    git(root, "config", "commit.gpgsign", "false")


def commit(root: Path, message: str) -> None:
    git(root, "add", "--all")
    git(root, "commit", "--quiet", "--no-gpg-sign", "-m", message)


class RoundsWithGitTest(unittest.TestCase):
    def test_a_re_record_becomes_a_second_round(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            editions = root / "editions"
            write_record(
                editions,
                "004-systems",
                "line",
                per_article_record(
                    "004-systems",
                    result="changes_required",
                    articles={
                        "eval-engineering": {
                            "reviewed_at": TIMESTAMP,
                            "manuscript_sha256": MANUSCRIPT_SHA,
                            "scores": {"structure": 2},
                        }
                    },
                ),
            )
            commit(root, "First line review")
            write_record(
                editions,
                "004-systems",
                "line",
                per_article_record(
                    "004-systems",
                    result="approved",
                    articles={
                        "eval-engineering": {
                            "reviewed_at": TIMESTAMP,
                            "manuscript_sha256": MANUSCRIPT_SHA,
                            "scores": {"structure": 5},
                        }
                    },
                ),
            )
            commit(root, "Line review after revisions")

            rows = collect_score_rows(editions)
            self.assertEqual([row.round for row in rows], [1, 2])
            self.assertEqual([row.score for row in rows], [2, 5])
            self.assertEqual([row.result for row in rows], ["changes_required", "approved"])
            self.assertEqual({row.rounds_to_approval for row in rows}, {2})

    def test_a_commit_that_does_not_change_the_record_is_not_a_round(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            editions = root / "editions"
            path = write_record(
                editions, "004-systems", "edition", whole_issue_record("004-systems")
            )
            commit(root, "Edition review")
            # A second commit that touches the path without changing a byte of
            # it -- here a mode change, elsewhere a rename or a tree rewrite --
            # is not a judge having another look, so the two identical contents
            # collapse into one round.
            git(root, "update-index", "--chmod=+x", path.relative_to(root).as_posix())
            # Committing the staged index directly: ``git add`` would restore
            # the recorded mode and undo the very thing under test.
            git(root, "commit", "--quiet", "--no-gpg-sign", "-m", "Make the record executable")
            rows = collect_score_rows(editions)
            self.assertTrue(rows)
            self.assertEqual({row.round for row in rows}, {1})

    def test_an_uncommitted_re_record_is_a_final_extra_round(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            editions = root / "editions"
            write_record(
                editions,
                "004-systems",
                "edition",
                whole_issue_record(
                    "004-systems", result="changes_required", scores={"through_line": 2}
                ),
            )
            commit(root, "Edition review")
            write_record(
                editions,
                "004-systems",
                "edition",
                whole_issue_record(
                    "004-systems", result="approved", scores={"through_line": 4}
                ),
            )
            rows = collect_score_rows(editions)
            self.assertEqual([(row.round, row.score) for row in rows], [(1, 2), (2, 4)])
            self.assertEqual({row.rounds_to_approval for row in rows}, {2})

    def test_an_untracked_record_in_a_repository_is_a_single_round(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            editions = root / "editions"
            write_record(editions, "004-systems", "edition", whole_issue_record("004-systems"))
            rows = collect_score_rows(editions)
            self.assertTrue(rows)
            self.assertEqual({row.round for row in rows}, {1})
            self.assertEqual({row.rounds_to_approval for row in rows}, {1})


class ConstantsTest(unittest.TestCase):
    def test_the_per_article_kinds_are_scored_kinds(self) -> None:
        self.assertEqual(set(PER_ARTICLE_KINDS) - set(SCORED_REVIEW_KINDS), set())
        self.assertEqual(PER_ARTICLE_KINDS, ("evidence", "line"))
        self.assertEqual(SCORED_REVIEW_KINDS, ("evidence", "line", "edition", "learning"))
        self.assertEqual(WHOLE_ISSUE_ARTICLE_ID, "edition")


if __name__ == "__main__":
    unittest.main()
