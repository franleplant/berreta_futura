from __future__ import annotations

import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import yaml

import magazine.article_stage as article_stage_module
from magazine.article_stage import (
    ArticleBrief,
    plan_article_stage,
    stage_article,
)
from magazine.errors import ValidationError
from magazine.fidelity import fidelity_report


class ArticleStageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        _make_project(self.root)
        _add_source(self.root, "source-one")

    def brief(self, *source_ids: str, edition_id: str = "issue-a") -> ArticleBrief:
        return ArticleBrief(
            schema_version=1,
            edition_id=edition_id,
            id="article-one",
            title="Article One",
            short_title="Article One",
            display_emphasis="One",
            opener_variant="edge_medallion",
            content_mode="faithful_edit",
            source_ids=source_ids or ("source-one",),
        )

    def test_single_source_plan_and_stage_create_exact_safe_skeletons(self):
        brief = self.brief("source-one")
        manifest_path = self.root / "editions" / "issue-a" / "edition.yaml"
        before = manifest_path.read_bytes()

        plan = plan_article_stage(self.root, brief)
        dry_run = stage_article(self.root, brief, dry_run=True)

        self.assertTrue(plan.changed)
        self.assertTrue(dry_run.dry_run)
        self.assertEqual(manifest_path.read_bytes(), before)
        self.assertFalse(plan.created[0].exists())

        report = stage_article(self.root, brief)

        self.assertTrue(report.changed)
        manuscript = self.root / "editions" / "issue-a" / "articles" / "article-one.md"
        ledger_path = (
            self.root / "editions" / "issue-a" / "fidelity" / "article-one.yaml"
        )
        manuscript_text = manuscript.read_text(encoding="utf-8")
        self.assertIn("TODO(editor)", manuscript_text)
        self.assertIn("No source prose was generated", manuscript_text)
        self.assertNotIn("Substantive source body", manuscript_text)
        ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(ledger["source_ids"], ["source-one"])
        self.assertEqual(
            ledger["source_body_sha256"],
            hashlib.sha256(b"Substantive source body.\n").hexdigest(),
        )
        self.assertEqual(
            ledger["paragraphs"][0]["status"],
            "todo_editorial_mapping_required",
        )
        self.assertNotIn("source", ledger["paragraphs"][0])
        self.assertNotIn("edited", ledger["paragraphs"][0])
        with self.assertRaisesRegex(ValidationError, "invalid status"):
            fidelity_report(ledger_path, manuscript)
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["sources"], ["source-one"])
        self.assertEqual(
            manifest["articles"][0],
            {
                "id": "article-one",
                "title": "Article One",
                "short_title": "Article One",
                "display_emphasis": "One",
                "opener_variant": "edge_medallion",
                "author": "Example Author",
                "author_note": "Example Author is an engineer at Example Company.",
                "content_mode": "faithful_edit",
                "source_ids": ["source-one"],
                "manuscript": "editions/issue-a/articles/article-one.md",
                "fidelity": "editions/issue-a/fidelity/article-one.yaml",
            },
        )

    def test_multi_source_ledger_uses_ordered_mapping_and_shared_profile(self):
        _add_source(
            self.root,
            "source-two",
            body="A second source body.\n",
        )
        _assign(self.root, "issue-a", ["source-one", "source-two"])

        stage_article(self.root, self.brief("source-two", "source-one"))

        ledger = yaml.safe_load(
            (
                self.root
                / "editions"
                / "issue-a"
                / "fidelity"
                / "article-one.yaml"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(ledger["source_ids"], ["source-two", "source-one"])
        self.assertEqual(
            list(ledger["source_body_sha256"]),
            ["source-two", "source-one"],
        )
        self.assertEqual(
            ledger["source_body_sha256"]["source-two"],
            hashlib.sha256(b"A second source body.\n").hexdigest(),
        )

    def test_second_run_keeps_existing_editorial_work_without_overwriting(self):
        brief = self.brief("source-one")
        first = stage_article(self.root, brief)
        manuscript = first.created[0]
        ledger = first.created[1]
        manuscript.write_text("Human-authored manuscript.\n", encoding="utf-8")
        ledger.write_text("human: ledger work\n", encoding="utf-8")

        second = stage_article(self.root, brief)

        self.assertFalse(second.changed)
        self.assertEqual(manuscript.read_text(encoding="utf-8"), "Human-authored manuscript.\n")
        self.assertEqual(ledger.read_text(encoding="utf-8"), "human: ledger work\n")
        self.assertEqual(
            second.kept,
            (
                manuscript,
                ledger,
                self.root / "editions" / "issue-a" / "edition.yaml",
            ),
        )

    def test_untracked_existing_article_file_is_never_overwritten(self):
        manuscript = self.root / "editions" / "issue-a" / "articles" / "article-one.md"
        manuscript.parent.mkdir(parents=True)
        manuscript.write_text("Existing work.\n", encoding="utf-8")
        manifest = self.root / "editions" / "issue-a" / "edition.yaml"
        before = manifest.read_bytes()

        with self.assertRaisesRegex(ValidationError, "Refusing to overwrite"):
            stage_article(self.root, self.brief("source-one"))

        self.assertEqual(manuscript.read_text(encoding="utf-8"), "Existing work.\n")
        self.assertEqual(manifest.read_bytes(), before)

    def test_failed_second_install_rolls_back_every_file_and_manifest(self):
        brief = self.brief("source-one")
        manifest = self.root / "editions" / "issue-a" / "edition.yaml"
        before = manifest.read_bytes()
        real_link = os.link

        def fail_ledger(source, destination, *, follow_symlinks=False):
            if Path(destination).name == "article-one.yaml":
                raise OSError("injected replacement failure")
            return real_link(
                source,
                destination,
                follow_symlinks=follow_symlinks,
            )

        with patch("magazine.article_stage.os.link", side_effect=fail_ledger):
            with self.assertRaisesRegex(ValidationError, "Cannot stage article atomically"):
                stage_article(self.root, brief)

        self.assertFalse(
            (self.root / "editions" / "issue-a" / "articles" / "article-one.md").exists()
        )
        self.assertFalse(
            (self.root / "editions" / "issue-a" / "fidelity" / "article-one.yaml").exists()
        )
        self.assertEqual(manifest.read_bytes(), before)

    def test_missing_extraction_fails_before_any_write(self):
        (
            self.root / "library" / "sources" / "source-one" / "extracted.md"
        ).unlink()
        manifest = self.root / "editions" / "issue-a" / "edition.yaml"
        before = manifest.read_bytes()

        with self.assertRaisesRegex(ValidationError, "no committed extraction"):
            stage_article(self.root, self.brief("source-one"))

        self.assertEqual(manifest.read_bytes(), before)

    def test_source_assigned_to_another_collecting_edition_is_rejected(self):
        _assign(self.root, "issue-b", ["source-one"])

        with self.assertRaisesRegex(
            ValidationError, "assigned to queued:issue-b"
        ):
            stage_article(self.root, self.brief("source-one"))

    def test_multi_source_author_profiles_must_be_consistent(self):
        _add_source(
            self.root,
            "source-two",
            author="Another Author",
            note="Another Author is a researcher at Example Company.",
        )
        _assign(self.root, "issue-a", ["source-one", "source-two"])

        with self.assertRaisesRegex(ValidationError, "inconsistent author profiles"):
            stage_article(self.root, self.brief("source-one", "source-two"))

    def test_source_cannot_be_staged_into_a_second_article(self):
        stage_article(self.root, self.brief("source-one"))
        second = ArticleBrief(
            **{
                **self.brief("source-one").__dict__,
                "id": "article-two",
                "title": "Article Two",
                "short_title": "Article Two",
                "display_emphasis": "Two",
            }
        )

        with self.assertRaisesRegex(
            ValidationError, "sources already belong to another article"
        ):
            stage_article(self.root, second)

    def test_manifest_splice_preserves_comments_quoting_and_source_types(self):
        manifest_path = self.root / "editions" / "issue-a" / "edition.yaml"
        manifest_path.write_text(
            "schema_version: 1\n"
            "id: issue-a\n"
            "issue_number: 1\n"
            "title: 'Issue A' # keep title spelling\n"
            "publication_date: '2026-07-29'\n"
            "sources:\n"
            "- 7 # legacy numeric declaration\n"
            "- 'source-old' # keep source spelling\n"
            "# article inventory follows\n"
            "articles: [] # staged rows\n",
            encoding="utf-8",
        )

        stage_article(self.root, self.brief("source-one"))

        text = manifest_path.read_text(encoding="utf-8")
        self.assertIn("title: 'Issue A' # keep title spelling\n", text)
        self.assertIn("- 7 # legacy numeric declaration\n", text)
        self.assertIn("- 'source-old' # keep source spelling\n", text)
        self.assertIn("# article inventory follows\n", text)
        self.assertIn("articles: [{id: article-one", text)
        parsed = yaml.safe_load(text)
        self.assertEqual(parsed["sources"][:2], [7, "source-old"])
        self.assertEqual(parsed["sources"][2], "source-one")

    def test_symlinked_destination_parent_is_rejected(self):
        edition_dir = self.root / "editions" / "issue-a"
        external = self.root / "outside-articles"
        external.mkdir()
        (edition_dir / "articles").symlink_to(external, target_is_directory=True)

        with self.assertRaisesRegex(ValidationError, "symlink path component"):
            stage_article(self.root, self.brief("source-one"))

        self.assertFalse((external / "article-one.md").exists())

    def test_manifest_change_between_plan_and_commit_aborts_without_losing_it(self):
        manifest_path = self.root / "editions" / "issue-a" / "edition.yaml"
        real_replace = os.replace
        calls = 0

        def concurrent_edit(source, destination):
            nonlocal calls
            calls += 1
            if calls == 1:
                with manifest_path.open("a", encoding="utf-8") as handle:
                    handle.write("# concurrent editor note\n")
            return real_replace(source, destination)

        with patch("magazine.article_stage.os.replace", side_effect=concurrent_edit):
            with self.assertRaisesRegex(ValidationError, "preserved"):
                stage_article(self.root, self.brief("source-one"))

        self.assertTrue(
            manifest_path.read_text(encoding="utf-8").endswith(
                "# concurrent editor note\n"
            )
        )
        self.assertFalse(
            (self.root / "editions" / "issue-a" / "articles" / "article-one.md").exists()
        )
        self.assertFalse(
            (self.root / "editions" / "issue-a" / "fidelity" / "article-one.yaml").exists()
        )

    def test_destination_created_inside_exclusive_install_is_never_overwritten(self):
        manuscript = (
            self.root / "editions" / "issue-a" / "articles" / "article-one.md"
        )
        real_install = article_stage_module._install_exclusive
        injected = False

        def concurrent_create(staged, destination):
            nonlocal injected
            if Path(destination) == manuscript and not injected:
                injected = True
                manuscript.write_bytes(b"CONCURRENT EDIT")
            return real_install(staged, destination)

        with patch(
            "magazine.article_stage._install_exclusive",
            side_effect=concurrent_create,
        ):
            with self.assertRaisesRegex(ValidationError, "preserved"):
                stage_article(self.root, self.brief("source-one"))

        self.assertEqual(manuscript.read_bytes(), b"CONCURRENT EDIT")
        self.assertFalse(
            (self.root / "editions" / "issue-a" / "fidelity" / "article-one.yaml").exists()
        )
        manifest = yaml.safe_load(
            (
                self.root / "editions" / "issue-a" / "edition.yaml"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["articles"], [])


def _make_project(root: Path) -> None:
    (root / "library" / "sources").mkdir(parents=True)
    for edition_id, issue_number in (("issue-a", 1), ("issue-b", 2)):
        edition_dir = root / "editions" / edition_id
        edition_dir.mkdir(parents=True)
        (edition_dir / "edition.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "id": edition_id,
                    "issue_number": issue_number,
                    "title": edition_id,
                    "publication_date": "2026-07-29",
                    "sources": [],
                    "articles": [],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
    (root / "library" / "release-state.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "intake_edition_id": "issue-a",
                "collecting_editions": [
                    {
                        "id": "issue-a",
                        "issue_number": 1,
                        "status": "collecting",
                        "source_ids": ["source-one"],
                    },
                    {
                        "id": "issue-b",
                        "issue_number": 2,
                        "status": "collecting",
                        "source_ids": [],
                    },
                ],
                "released_editions": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (root / "magazine.toml").write_text(
        "[paths]\n"
        'sources = "library/sources"\n'
        'editions = "editions"\n'
        'release_state = "library/release-state.yaml"\n',
        encoding="utf-8",
    )


def _add_source(
    root: Path,
    source_id: str,
    *,
    body: str = "Substantive source body.\n",
    author: str = "Example Author",
    note: str = "Example Author is an engineer at Example Company.",
) -> None:
    capture_id = hashlib.sha256(source_id.encode("utf-8")).hexdigest()
    source_dir = root / "library" / "sources" / source_id
    bundle_dir = source_dir / "raw" / capture_id
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
    (source_dir / "record.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "id": source_id,
                "title": source_id,
                "author": author,
                "author_profile": {
                    "note": note,
                    "evidence": [
                        {
                            "url": f"https://example.com/{source_id}/author",
                            "capture_id": capture_id,
                        }
                    ],
                },
                "canonical_url": f"https://example.com/{source_id}",
                "submitted_url": f"https://example.com/{source_id}",
                "captured_at": "2026-07-29T12:00:00Z",
                "publication_date": "2026-07-28",
                "kind": "article",
                "status": "captured",
                "raw_captures": [
                    {
                        "id": capture_id,
                        "path": f"raw/{capture_id}/manifest.json",
                        "method": "test fixture",
                        "captured_at": "2026-07-29T12:00:00Z",
                        "artifact_count": 1,
                        "byte_count": 2,
                    }
                ],
                "provenance": [],
                "rights": {},
                "metadata": {},
                "notes": "",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (source_dir / "extracted.md").write_text(
        "---\n"
        "schema_version: 1\n"
        f"source_id: {source_id}\n"
        f"raw_bundle: {capture_id}\n"
        "extraction_method: test fixture transcription\n"
        "---\n"
        + body,
        encoding="utf-8",
    )


def _assign(root: Path, edition_id: str, source_ids: list[str]) -> None:
    state_path = root / "library" / "release-state.yaml"
    state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    for edition in state["collecting_editions"]:
        edition["source_ids"] = (
            list(source_ids) if edition["id"] == edition_id else []
        )
    state_path.write_text(
        yaml.safe_dump(state, sort_keys=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
