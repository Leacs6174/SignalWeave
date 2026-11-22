from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from project_io import (
    ProjectError,
    ProjectFile,
    load_project,
    load_recent_projects,
    record_recent_project,
    save_project,
    save_recent_project_order,
)


class ProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_project_round_trip_keeps_paths_and_checks(self) -> None:
        project = self.root / "experiment.swproj"
        saved = save_project(
            project,
            "electrochem",
            [
                ProjectFile(str(self.root / "A.txt"), True),
                ProjectFile(str(self.root / "B.txt"), False),
            ],
        )
        document = load_project(saved)
        self.assertEqual(document.data_type, "electrochem")
        self.assertEqual([item.enabled for item in document.files], [True, False])
        self.assertEqual(Path(document.files[0].path).name, "A.txt")
        self.assertEqual(document.files[0].path, str((self.root / "A.txt").resolve()))

    def test_project_extension_is_added(self) -> None:
        saved = save_project(self.root / "plain", "cd", [])
        self.assertEqual(saved.suffix, ".swproj")

    def test_invalid_project_fails_clearly(self) -> None:
        path = self.root / "bad.swproj"
        path.write_text('{"format":"wrong"}', encoding="utf-8")
        with self.assertRaises(ProjectError):
            load_project(path)

    def test_legacy_project_format_remains_readable(self) -> None:
        path = self.root / "legacy.dmproj"
        path.write_text(
            (
                '{"format":"DataMergerProject","version":1,'
                '"data_type":"cd","files":[]}'
            ),
            encoding="utf-8",
        )
        document = load_project(path)
        self.assertEqual(document.data_type, "cd")
        self.assertEqual(document.files, ())

    def test_recent_projects_are_deduplicated_and_ordered(self) -> None:
        config = self.root / "recent.json"
        first = self.root / "first.swproj"
        second = self.root / "second.swproj"
        record_recent_project(config, first)
        record_recent_project(config, second)
        result = record_recent_project(config, first)
        self.assertEqual(result, [str(first.resolve()), str(second.resolve())])
        self.assertEqual(load_recent_projects(config), result)

    def test_recent_reorder_is_persisted_without_opening_side_effects(self) -> None:
        config = self.root / "recent.json"
        first = self.root / "first.swproj"
        second = self.root / "second.swproj"
        ordered = save_recent_project_order(config, [str(second), str(first)])
        self.assertEqual(ordered, [str(second.resolve()), str(first.resolve())])
        self.assertEqual(load_recent_projects(config), ordered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
