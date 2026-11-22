from __future__ import annotations

import unittest

from PySide6.QtWidgets import QApplication

from theme import BASE_STYLE, apply_theme, build_palette


def _rgb(hex_color: str) -> tuple[float, float, float]:
    value = hex_color.lstrip("#")
    return tuple(int(value[index : index + 2], 16) / 255 for index in (0, 2, 4))


def _luminance(hex_color: str) -> float:
    channels = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in _rgb(hex_color)
    ]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(foreground: str, background: str) -> float:
    first = _luminance(foreground)
    second = _luminance(background)
    high, low = max(first, second), min(first, second)
    return (high + 0.05) / (low + 0.05)


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        apply_theme(cls.app, "")

    def test_critical_palette_pairs_meet_wcag_aa(self) -> None:
        palette = build_palette()
        roles = palette.ColorRole
        pairs = (
            (roles.WindowText, roles.Window),
            (roles.Text, roles.Base),
            (roles.ButtonText, roles.Button),
            (roles.HighlightedText, roles.Highlight),
            (roles.ToolTipText, roles.ToolTipBase),
        )
        for foreground_role, background_role in pairs:
            foreground = palette.color(foreground_role).name()
            background = palette.color(background_role).name()
            self.assertGreaterEqual(
                contrast(foreground, background),
                4.5,
                f"{foreground_role.name} on {background_role.name}",
            )

    def test_common_surfaces_always_define_foreground_and_background(self) -> None:
        for selector in (
            "QMenu",
            "QMenu::item",
            "QToolTip",
            "QDialog",
            "QMessageBox",
            "QLineEdit",
            "QComboBox QAbstractItemView",
        ):
            self.assertIn(selector, BASE_STYLE)
        self.assertIn("qproperty-drawBase: 0", BASE_STYLE)

    def test_application_font_and_palette_are_owned_by_theme(self) -> None:
        self.assertGreater(self.app.font().pointSize(), 0)
        self.assertEqual(
            self.app.palette().color(self.app.palette().ColorRole.Text).name(),
            "#253044",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
