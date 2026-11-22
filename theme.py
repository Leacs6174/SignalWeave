"""Design tokens, native palette, and mandatory Qt styling rules."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QTabBar, QWidget

COLORS = {
    "canvas": "#f3f6f9",
    "surface": "#ffffff",
    "surface_subtle": "#fbfcfe",
    "border": "#e2e8f0",
    "border_strong": "#d8e0e9",
    "text": "#253044",
    "text_heading": "#172033",
    "text_muted": "#64748b",
    "text_disabled": "#94a3b8",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "accent_soft": "#eff6ff",
    "selection": "#e8f1ff",
    "danger": "#b42318",
}

CHANNEL_COLORS = (
    "#2563eb",
    "#0f9f81",
    "#e47524",
    "#d9467a",
    "#7c5ce5",
    "#0891b2",
    "#65a30d",
    "#b7791f",
)

FONT_FAMILY = "Microsoft YaHei UI"


def font(
    size: int,
    weight: QFont.Weight = QFont.Weight.Normal,
) -> QFont:
    family = FONT_FAMILY
    if family not in QFontDatabase.families():
        family = "Segoe UI"
    return QFont(family, size, weight)


def build_palette() -> QPalette:
    """Create a complete light palette so OS dark-theme roles cannot leak."""
    palette = QPalette()
    roles = QPalette.ColorRole
    groups = QPalette.ColorGroup
    palette.setColor(roles.Window, QColor(COLORS["canvas"]))
    palette.setColor(roles.WindowText, QColor(COLORS["text"]))
    palette.setColor(roles.Base, QColor(COLORS["surface"]))
    palette.setColor(roles.AlternateBase, QColor(COLORS["surface_subtle"]))
    palette.setColor(roles.Text, QColor(COLORS["text"]))
    palette.setColor(roles.Button, QColor(COLORS["surface"]))
    palette.setColor(roles.ButtonText, QColor(COLORS["text"]))
    palette.setColor(roles.BrightText, QColor("#ffffff"))
    palette.setColor(roles.ToolTipBase, QColor(COLORS["surface"]))
    palette.setColor(roles.ToolTipText, QColor(COLORS["text"]))
    palette.setColor(roles.Highlight, QColor(COLORS["selection"]))
    palette.setColor(roles.HighlightedText, QColor(COLORS["text_heading"]))
    palette.setColor(roles.Link, QColor(COLORS["accent"]))
    palette.setColor(roles.PlaceholderText, QColor(COLORS["text_muted"]))
    for role in (
        roles.WindowText,
        roles.Text,
        roles.ButtonText,
        roles.PlaceholderText,
    ):
        palette.setColor(
            groups.Disabled, role, QColor(COLORS["text_disabled"])
        )
    return palette


# These rules are intentionally global. New controls must not rely on the
# operating system's dark palette or draw a background without a foreground.
BASE_STYLE = f"""
QWidget {{
    color: {COLORS["text"]};
}}
QToolTip {{
    background: {COLORS["surface"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border"]};
    padding: 4px 7px;
}}
QMenu {{
    background: {COLORS["surface"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border"]};
    padding: 3px;
    font-family: "{FONT_FAMILY}";
    font-size: 12px;
}}
QMenu::item {{
    color: {COLORS["text"]};
    background: transparent;
    padding: 3px 24px 3px 18px;
}}
QMenu::item:selected {{
    background: {COLORS["accent_soft"]};
    color: {COLORS["accent_hover"]};
}}
QMenu::item:disabled {{
    color: {COLORS["text_disabled"]};
}}
QDialog, QMessageBox {{
    background: {COLORS["surface"]};
    color: {COLORS["text"]};
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {COLORS["surface"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border_strong"]};
    border-radius: 6px;
    padding: 5px 7px;
    selection-background-color: {COLORS["selection"]};
    selection-color: {COLORS["text_heading"]};
}}
QComboBox QAbstractItemView, QAbstractItemView {{
    background: {COLORS["surface"]};
    color: {COLORS["text"]};
    selection-background-color: {COLORS["selection"]};
    selection-color: {COLORS["text_heading"]};
}}
QPushButton {{
    background: {COLORS["surface"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border_strong"]};
}}
QPushButton:disabled {{
    background: {COLORS["canvas"]};
    color: {COLORS["text_disabled"]};
    border-color: {COLORS["border"]};
}}
QTabBar {{
    qproperty-drawBase: 0;
    border: none;
    background: transparent;
}}
"""


def apply_theme(app: QApplication, screen_stylesheet: str) -> None:
    app.setStyle("Fusion")
    app.setFont(font(10))
    app.setPalette(build_palette())
    app.setStyleSheet(BASE_STYLE + "\n" + screen_stylesheet)


def enforce_design_invariants(root: QWidget) -> None:
    """Disable native tab baselines that ignore Qt stylesheets."""
    for tab_bar in root.findChildren(QTabBar):
        tab_bar.setDrawBase(False)
