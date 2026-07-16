from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from magazine import Magazine
from magazine.release import load_release_state, sync_release_state


class ReleaseStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_capture_queues_new_source_in_open_edition(self):
        magazine = Magazine(self.root)
        record = magazine.capture("https://example.com/article", title="Article")

        state = load_release_state(self.root / "library" / "release-state.yaml")

        self.assertEqual(state.open_edition_id, "001-the-work-left-to-us")
        self.assertEqual(state.queued_source_ids, (record.id,))

    def test_sync_adds_unassigned_sources_but_never_requeues_released_sources(self):
        path = self.root / "library" / "release-state.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "open_edition": {"id": "002-open", "issue_number": 2, "status": "collecting", "source_ids": []},
            "released_editions": [{"id": "001-released", "issue_number": 1, "source_ids": ["old"]}],
        }, sort_keys=False), encoding="utf-8")

        state = sync_release_state(path, {"old", "new"})

        self.assertEqual(state.queued_source_ids, ("new",))
        self.assertEqual(state.assignments()["old"], "released:001-released")

    def test_sources_catalog_exposes_open_edition_assignment(self):
        magazine = Magazine(self.root)
        record = magazine.capture("https://example.com/article", title="Article")

        catalog = magazine.write_sources().read_text(encoding="utf-8")

        self.assertIn("Open edition: `001-the-work-left-to-us`", catalog)
        self.assertIn(f"Release: queued for `001-the-work-left-to-us`", catalog)
        self.assertIn(record.id, catalog)
