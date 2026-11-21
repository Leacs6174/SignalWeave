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
)


class ProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_project_round_trip_keeps_paths_and_checks(self) -> None:
        project = self.root / "experiment.dmproj"
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
        self.assertEqual(saved.suffix, ".dmproj")

    def test_invalid_project_fails_clearly(self) -> None:
        path = self.root / "bad.dmproj"
        path.write_text('{"format":"wrong"}', encoding="utf-8")
        with self.assertRaises(ProjectError):
            load_project(path)

    def test_recent_projects_are_deduplicated_and_ordered(self) -> None:
        config = self.root / "recent.json"
        first = self.root / "first.dmproj"
        second = self.root / "second.dmproj"
        record_recent_project(config, first)
        record_recent_project(config, second)
        result = record_recent_project(config, first)
        self.assertEqual(result, [str(first.resolve()), str(second.resolve())])
        self.assertEqual(load_recent_projects(config), result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
