from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDropEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QLabel,
    QSplitter,
    QTabBar,
    QWidget,
)

from app import MainWindow  # noqa: E402
from project_io import load_recent_projects  # noqa: E402
from theme import apply_theme  # noqa: E402
from ui_main import APP_STYLE, OtherSettingsDialog  # noqa: E402
from user_config import UserConfig, load_user_config  # noqa: E402


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        apply_theme(cls.app, APP_STYLE)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.window = MainWindow()
        self.window.recent_config = Path(self.temp.name) / "recent.json"
        self.window.config_path = Path(self.temp.name) / "config.json"
        self.window.user_config = UserConfig()
        self.window._apply_application_theme()
        self.window._apply_render_settings()
        self.window._sync_channel_controls()

    def tearDown(self) -> None:
        self.window._dirty = False
        self.window.user_config = UserConfig()
        self.window._apply_application_theme()
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
        self.window.merge_channel_checks["HT"].setChecked(False)
        self.window.merge_channel_checks["Abs"].setChecked(False)
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
        self.assertEqual(
            [
                name
                for name, check in self.window.preview_channel_checks.items()
                if check.isChecked()
            ],
            ["CD", "G"],
        )
        self.assertEqual(
            list(self.window.merge_channel_checks), ["CD", "HT", "Abs"]
        )
        self.assertEqual(
            list(self.window.preview_channel_checks), ["CD", "HT", "Abs", "G"]
        )
        self.assertEqual(len(self.window.plot_preview.plots), 2)
        self.assertIsNotNone(self.window.result)
        for row in range(2):
            item = self.window.file_table.item(row, 2)
            self.assertEqual(
                item.foreground().color(),
                self.window.palette().color(
                    self.window.palette().ColorRole.Text
                ),
            )
        self.assertFalse(self.window.grab().isNull())
        self.window._dirty = False
        self.window.close()
        self.app.processEvents()

    def test_preview_and_merge_channel_settings_are_persisted(self) -> None:
        self.window._add_paths([str(FIXTURES / "A.txt")])
        self.window._recompute_merge()
        self.window.merge_channel_checks["HT"].setChecked(False)
        self.window.preview_channel_checks["HT"].setChecked(True)
        config = load_user_config(self.window.config_path)
        self.assertNotIn("HT", config.cd_merge_channels)
        self.assertIn("HT", config.cd_preview_channels)
        self.assertEqual(set(config.cd_preview_channels), {"CD", "G", "HT"})
        self.assertEqual(len(self.window.plot_preview.plots), 3)

    def test_plot_drag_zoom_and_reset_button(self) -> None:
        self.window._add_paths(
            [str(FIXTURES / "A.txt"), str(FIXTURES / "B.txt")]
        )
        self.window._recompute_merge()
        self.window.show()
        self.app.processEvents()
        plot = self.window.plot_preview.plots[0]
        self.assertFalse(plot.grab().isNull())
        cached_plot = plot._static_cache
        self.assertIsNotNone(cached_plot)
        initial_x = plot.view_x_range
        initial_y = plot.view_y_range
        rect = plot._plot_rect()
        start = QPoint(int(rect.left() + 80), int(rect.bottom() + 10))
        end = QPoint(int(rect.left() + 260), int(rect.bottom() + 10))
        QTest.mousePress(plot, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(plot, end)
        self.app.processEvents()
        self.assertTrue(
            plot._selection_overlay.testAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
        )
        self.assertIsNotNone(plot._selection_overlay._selection)
        self.assertIs(plot._static_cache, cached_plot)
        QTest.mouseRelease(plot, Qt.MouseButton.LeftButton, pos=end)
        self.app.processEvents()
        self.assertTrue(plot.is_zoomed())
        self.assertNotEqual(plot.view_x_range, initial_x)
        self.assertEqual(plot.view_y_range, initial_y)
        self.assertTrue(self.window.plot_preview.reset_button.isEnabled())

        self.window.plot_preview.reset_button.click()
        self.app.processEvents()
        self.assertFalse(plot.is_zoomed())
        self.assertEqual(plot.view_x_range, initial_x)
        self.assertEqual(plot.view_y_range, initial_y)
        self.assertFalse(self.window.plot_preview.reset_button.isEnabled())

        y_start = QPoint(int(rect.left() - 20), int(rect.top() + 60))
        y_end = QPoint(int(rect.left() - 20), int(rect.top() + 180))
        QTest.mousePress(plot, Qt.MouseButton.LeftButton, pos=y_start)
        QTest.mouseMove(plot, y_end)
        QTest.mouseRelease(plot, Qt.MouseButton.LeftButton, pos=y_end)
        self.app.processEvents()
        self.assertTrue(plot.is_zoomed())
        self.assertEqual(plot.view_x_range, initial_x)
        self.assertNotEqual(plot.view_y_range, initial_y)
        self.window.plot_preview.reset_zoom()
        self.window._dirty = False
        self.window.close()
        self.app.processEvents()

    def test_toolbar_and_electrochem_mode(self) -> None:
        self.assertIn("SignalWeave", self.window.windowTitle())
        self.assertTrue(self.window.toolbar.isVisible() or not self.window.isVisible())
        self.assertIsInstance(self.window.recent_tabs, QTabBar)
        self.assertIsInstance(self.window.content_splitter, QSplitter)
        self.assertIsInstance(self.window.left_splitter, QSplitter)
        self.assertEqual(
            self.window.content_splitter.orientation(),
            Qt.Orientation.Horizontal,
        )
        self.assertEqual(
            self.window.left_splitter.orientation(),
            Qt.Orientation.Vertical,
        )
        self.assertFalse(self.window.recent_tabs.drawBase())
        self.assertTrue(
            all(
                not tab_bar.drawBase()
                for tab_bar in self.window.preview_tabs.findChildren(QTabBar)
            )
        )
        self.assertGreaterEqual(self.window.recent_tabs.count(), 1)
        self.assertIsNone(self.window.findChild(QWidget, "logo"))
        self.assertNotIn(
            "本地处理",
            " ".join(label.text() for label in self.window.findChildren(QLabel)),
        )
        visible_text = " ".join(
            label.text() for label in self.window.findChildren(QLabel)
        )
        self.assertNotIn("自动识别横坐标", visible_text)
        self.assertNotIn("拖动绘图区框选缩放", visible_text)
        self.assertEqual(
            [action.text() for action in self.window.file_menu.actions()],
            ["新建工程", "打开工程", "保存工程", "工程另存为", "关闭工程"],
        )
        self.assertEqual(
            [action.text() for action in self.window.type_menu.actions()],
            ["CD 光谱", "电化学"],
        )
        self.assertEqual(
            [action.text() for action in self.window.view_menu.actions()],
            ["字体…", "主题", "", "其它设置…"],
        )
        self.assertLessEqual(self.window.file_menu.sizeHint().height(), 150)
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
        self.assertFalse(self.window.channel_card.isHidden())
        self.assertFalse(self.window.formula_button.isVisible())
        self.assertEqual(self.window.file_table.rowCount(), 2)
        self.assertEqual(
            list(self.window.merge_channel_checks),
            ["Current"],
        )
        self.assertTrue(
            all(check.isChecked() for check in self.window.merge_channel_checks.values())
        )
        self.assertTrue(
            all(check.isChecked() for check in self.window.preview_channel_checks.values())
        )
        self.assertEqual(len(self.window.plot_preview.plots), 1)
        self.window.preview_channel_checks["Current"].setChecked(False)
        config = load_user_config(self.window.config_path)
        self.assertEqual(config.electrochem_preview_channels, ())
        self.assertEqual(len(self.window.plot_preview.plots), 0)

    def test_default_line_render_and_render_settings(self) -> None:
        self.window._apply_data_type("electrochem")
        self.window._add_paths(
            [str(FIXTURES / "OER_A.txt"), str(FIXTURES / "OER_B.txt")]
        )
        self.window._recompute_merge()
        plot = self.window.plot_preview.plots[0]
        self.assertEqual(plot.render_mode, "line")
        self.assertEqual(plot.marker_size, 1.8)
        self.assertGreaterEqual(len(set(plot.series_colors)), 4)

        self.window.user_config = UserConfig(
            render_mode="scatter",
            marker_size=1.2,
            series_colors=("#112233", "#445566", "#778899"),
        )
        self.window._apply_render_settings()
        self.assertEqual(plot.render_mode, "scatter")
        self.assertEqual(plot.marker_size, 1.2)
        self.assertEqual(
            plot.series_colors, ("#112233", "#445566", "#778899")
        )
        dialog = OtherSettingsDialog(self.window.user_config, self.window)
        self.assertEqual(dialog.render_combo.currentData(), "scatter")
        self.assertAlmostEqual(dialog.marker_size.value(), 1.2)
        self.assertEqual(len(dialog.color_buttons), 3)
        dialog.close()

    def test_theme_and_font_settings_apply_and_persist(self) -> None:
        self.assertIn("background: #2563eb;", APP_STYLE)
        self.window._set_theme("dark")
        self.assertEqual(self.app.property("dataMergerTheme"), "dark")
        self.assertEqual(load_user_config(self.window.config_path).theme_mode, "dark")
        self.window._set_theme("light")
        self.assertEqual(self.app.property("dataMergerTheme"), "light")

        configured = UserConfig(font_family="Segoe UI", font_size=13)
        self.window.user_config = configured
        self.window._apply_application_theme()
        self.assertEqual(self.app.font().pointSize(), 13)

    def test_function_panes_are_resizable(self) -> None:
        self.window.show()
        self.app.processEvents()
        self.window.content_splitter.setSizes([560, 630])
        self.window.left_splitter.setSizes([360, 240])
        self.app.processEvents()
        self.assertTrue(
            all(size > 0 for size in self.window.content_splitter.sizes())
        )
        self.assertTrue(
            all(size > 0 for size in self.window.left_splitter.sizes())
        )

    def test_project_round_trip_restores_disabled_file(self) -> None:
        self.window._add_paths(
            [str(FIXTURES / "A.txt"), str(FIXTURES / "B.txt")]
        )
        self.window.entries[1].enabled = False
        self.window._refresh_table()
        self.window.project_path = Path(self.temp.name) / "ui-test.swproj"
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
            (Path(self.temp.name) / "ui-test.swproj").resolve(),
        )

    def test_recent_tabs_switch_between_projects(self) -> None:
        first = Path(self.temp.name) / "first.swproj"
        second = Path(self.temp.name) / "second.swproj"
        self.window._add_paths([str(FIXTURES / "A.txt")])
        self.window.project_path = first
        self.assertTrue(self.window._save_project())

        self.window._new_project()
        self.window._add_paths([str(FIXTURES / "B.txt")])
        self.window.project_path = second
        self.assertTrue(self.window._save_project())
        self.assertEqual(self.window.recent_tabs.count(), 2)
        self.assertEqual(self.window.recent_tabs.tabText(0), "first")
        self.assertEqual(self.window.recent_tabs.tabText(1), "second")

        self.window.recent_tabs.setCurrentIndex(1)
        self.app.processEvents()
        self.assertEqual(self.window.project_path, second.resolve())
        self.assertEqual(self.window.entries[0].path.name, "B.txt")
        self.assertEqual(self.window.recent_tabs.tabText(0), "first")
        self.assertEqual(self.window.recent_tabs.tabText(1), "second")

        self.window.recent_tabs.moveTab(1, 0)
        self.app.processEvents()
        self.assertEqual(self.window.recent_tabs.tabText(0), "second")
        self.assertEqual(load_recent_projects(self.window.recent_config)[0], str(second.resolve()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
