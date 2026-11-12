"""No-network regression tests for Tiny Family's one-time test-data copy."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "custom_components" / "tiny_family" / "migration.py"
spec = importlib.util.spec_from_file_location("_tiny_family_migration", FILE)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class OneTimeMigrationTests(unittest.TestCase):
    def test_copy_is_once_only_and_does_not_delete_legacy_archive(self):
        with TemporaryDirectory() as dirname:
            root = Path(dirname)
            old = root / "person_timeline_historik.json"
            new = root / "tiny_family_historik.json"
            old.write_text('{"system":[{"tekst":"demo"}]}', encoding="utf-8")
            self.assertEqual(migration.migrate_local_json_once(root),
                             ("tiny_family_historik.json",))
            self.assertEqual(new.read_text(encoding="utf-8"), old.read_text(encoding="utf-8"))
            self.assertTrue(old.is_file())
            new.write_text('{"system":[]}', encoding="utf-8")
            self.assertEqual(migration.migrate_local_json_once(root), ())
            self.assertEqual(new.read_text(encoding="utf-8"), '{"system":[]}')

    def test_places_and_missing_sources(self):
        with TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "person_timeline_places.json").write_text('{"demo":[]}', encoding="utf-8")
            self.assertEqual(migration.migrate_local_json_once(root),
                             ("tiny_family_places.json",))
            self.assertEqual((root / "tiny_family_places.json").read_text(encoding="utf-8"),
                             '{"demo":[]}')


if __name__ == "__main__":
    unittest.main()
