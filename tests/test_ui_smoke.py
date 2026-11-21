from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QDropEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QTabBar, QWidget  # noqa: E402

from app import MainWindow  # noqa: E402


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.window = MainWindow()
        self.window.recent_config = Path(self.temp.name) / "recent.json"

    def tearDown(self) -> None:
        self.window._dirty = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    def test_load_merge_and_copy(self) -> None:
        self.window._add_paths(
            [str(FIXTURES / "A.txt"), str(FIXTURES / "B.txt")]
        )
        self.window._recompute_merge()
        self.app.processEvents()

        self.assertEqual(self.window.file_table.rowCount(), 2)
        self.assertIsNotNone(self.window.result)
        result = self.window.result
        assert result is not None
        self.assertEqual(result.header[:9], (
            "Wavelength (nm)", "CD1", "HT1", "Abs1", "CD2", "HT2", "Abs2"
            , "G1", "G2"
        ))
        self.assertEqual(result.rows[0][0], "900.50")
        self.assertEqual(result.rows[0][1:4], ("", "", ""))
        self.assertEqual(result.rows[0][4:9], ("5.0000", "50.50", "0.5050", "", ""))
        self.assertIn("900.00", self.window.preview.toPlainText())
        self.assertTrue(self.window.copy_button.isEnabled())

        self.window._copy_result()
        self.assertEqual(self.app.clipboard().text(), result.text)
        self.window._copy_formulas()
        self.assertEqual(self.app.clipboard().text(), result.formula_text)

    def test_channel_toggle_and_disable_file(self) -> None:
        self.window._add_paths(
            [str(FIXTURES / "A.txt"), str(FIXTURES / "B.txt")]
        )
        self.window.channel_checks["HT"].setChecked(False)
        self.window.channel_checks["Abs"].setChecked(False)
        self.window._recompute_merge()
        self.app.processEvents()
        assert self.window.result is not None
        self.assertNotIn("HT1", self.window.result.header)
        self.assertNotIn("Abs1", self.window.result.header)

        self.window.entries[1].enabled = False
        self.window._refresh_table()
        self.window._recompute_merge()
        self.app.processEvents()
        assert self.window.result is not None
        self.assertEqual(self.window.result.participating_files, 1)

    def test_drop_event_and_visible_window(self) -> None:
        mime = QMimeData()
        mime.setUrls(
            [
                QUrl.fromLocalFile(str(FIXTURES / "A.txt")),
                QUrl.fromLocalFile(str(FIXTURES / "B.txt")),
            ]
        )
        event = QDropEvent(
            QPointF(40, 40),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.window.dropEvent(event)
        self.window._recompute_merge()
        self.window.show()
        self.app.processEvents()

        self.assertTrue(self.window.isVisible())
        self.assertEqual(self.window.file_table.rowCount(), 2)
        self.assertIsNotNone(self.window.result)
        for row in range(2):
            item = self.window.file_table.item(row, 2)
            self.assertEqual(item.foreground().color(), QColor("#253044"))
        self.assertFalse(self.window.grab().isNull())
        self.window._dirty = False
        self.window.close()
        self.app.processEvents()

    def test_toolbar_and_electrochem_mode(self) -> None:
        self.assertTrue(self.window.toolbar.isVisible() or not self.window.isVisible())
        self.assertIsInstance(self.window.recent_tabs, QTabBar)
        self.assertGreaterEqual(self.window.recent_tabs.count(), 1)
        self.assertIsNone(self.window.findChild(QWidget, "logo"))
        self.assertEqual(
            [action.text() for action in self.window.file_menu.actions()],
            ["新建工程", "打开工程", "保存工程", "工程另存为", "关闭工程"],
        )
        self.assertEqual(
            [action.text() for action in self.window.type_menu.actions()],
            ["CD 光谱", "电化学"],
        )
        self.window._apply_data_type("electrochem")
        self.window._add_paths(
            [str(FIXTURES / "OER_A.txt"), str(FIXTURES / "OER_B.txt")]
        )
        self.window._recompute_merge()
        self.app.processEvents()
        assert self.window.result is not None
        self.assertEqual(
            self.window.result.header,
            ("Potential (V)", "Current1", "Current2"),
        )
        self.assertEqual(self.window.type_button.text(), "数据类型：电化学")
        self.assertFalse(self.window.channel_card.isVisible())
        self.assertFalse(self.window.formula_button.isVisible())
        self.assertEqual(self.window.file_table.rowCount(), 2)

    def test_project_round_trip_restores_disabled_file(self) -> None:
        self.window._add_paths(
            [str(FIXTURES / "A.txt"), str(FIXTURES / "B.txt")]
        )
        self.window.entries[1].enabled = False
        self.window._refresh_table()
        self.window.project_path = Path(self.temp.name) / "ui-test.dmproj"
        self.assertTrue(self.window._save_project())
        self.assertFalse(self.window._dirty)
        self.assertEqual(self.window.recent_tabs.count(), 1)
        self.assertEqual(
            self.window.recent_tabs.tabData(0),
            str(self.window.project_path.resolve()),
        )
        self.assertEqual(self.window.recent_tabs.currentIndex(), 0)

        self.assertTrue(self.window._open_project(str(self.window.project_path)))
        self.assertEqual(self.window.data_type, "cd")
        self.assertEqual([entry.enabled for entry in self.window.entries], [True, False])
        self.assertEqual(
            self.window.project_path,
            (Path(self.temp.name) / "ui-test.dmproj").resolve(),
        )

    def test_recent_tabs_switch_between_projects(self) -> None:
        first = Path(self.temp.name) / "first.dmproj"
        second = Path(self.temp.name) / "second.dmproj"
        self.window._add_paths([str(FIXTURES / "A.txt")])
        self.window.project_path = first
        self.assertTrue(self.window._save_project())

        self.window._new_project()
        self.window._add_paths([str(FIXTURES / "B.txt")])
        self.window.project_path = second
        self.assertTrue(self.window._save_project())
        self.assertEqual(self.window.recent_tabs.count(), 2)
        self.assertEqual(self.window.recent_tabs.tabText(0), "second")
        self.assertEqual(self.window.recent_tabs.tabText(1), "first")

        self.window.recent_tabs.setCurrentIndex(1)
        self.app.processEvents()
        self.assertEqual(self.window.project_path, first.resolve())
        self.assertEqual(self.window.entries[0].path.name, "A.txt")


if __name__ == "__main__":
    unittest.main(verbosity=2)
