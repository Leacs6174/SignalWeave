"""Design tokens, light/dark palettes, and mandatory Qt styling rules."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QTabBar, QWidget

from user_config import DEFAULT_SERIES_COLORS

LIGHT_COLORS = {
    "canvas": "#f3f6f9",
    "surface": "#ffffff",
    "surface_subtle": "#fbfcfe",
    "surface_alt": "#f8fafc",
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
    "danger_soft": "#fff1f2",
    "chart_grid": "#e8edf3",
    "chart_axis": "#8a99aa",
}
DARK_COLORS = {
    "canvas": "#111111",
    "surface": "#191919",
    "surface_subtle": "#222222",
    "surface_alt": "#151515",
    "border": "#333333",
    "border_strong": "#484848",
    "text": "#e5e5e5",
    "text_heading": "#fafafa",
    "text_muted": "#a3a3a3",
    "text_disabled": "#737373",
    "accent": "#d4d4d4",
    "accent_hover": "#f5f5f5",
    "accent_soft": "#2d2d2d",
    "selection": "#525252",
    "danger": "#d4d4d4",
    "danger_soft": "#2a2a2a",
    "chart_grid": "#333333",
    "chart_axis": "#666666",
}

COLORS = LIGHT_COLORS
CHANNEL_COLORS = DEFAULT_SERIES_COLORS
FONT_FAMILY = "Microsoft YaHei UI"


def colors(mode: str = "light") -> dict[str, str]:
    return DARK_COLORS if mode == "dark" else LIGHT_COLORS


def active_mode() -> str:
    app = QApplication.instance()
    value = app.property("dataMergerTheme") if app is not None else None
    return "dark" if value == "dark" else "light"


def chart_colors(mode: str | None = None) -> dict[str, str]:
    resolved_mode = mode or active_mode()
    tokens = colors(resolved_mode)
    return {
        "surface": tokens["surface"],
        "border": tokens["border"],
        "grid": tokens["chart_grid"],
        "axis": tokens["chart_axis"],
        "text": tokens["text"],
        "heading": tokens["text_heading"],
        "muted": tokens["text_muted"],
        "selection": tokens["accent"] if resolved_mode == "dark" else "#3b82f6",
    }


def font(
    size: int,
    weight: QFont.Weight = QFont.Weight.Normal,
    family: str = FONT_FAMILY,
) -> QFont:
    available = QFontDatabase.families()
    if family not in available:
        family = "Segoe UI"
    return QFont(family, size, weight)


def build_palette(mode: str = "light") -> QPalette:
    """Create a complete palette so OS theme roles cannot leak."""
    tokens = colors(mode)
    palette = QPalette()
    roles = QPalette.ColorRole
    groups = QPalette.ColorGroup
    palette.setColor(roles.Window, QColor(tokens["canvas"]))
    palette.setColor(roles.WindowText, QColor(tokens["text"]))
    palette.setColor(roles.Base, QColor(tokens["surface"]))
    palette.setColor(roles.AlternateBase, QColor(tokens["surface_subtle"]))
    palette.setColor(roles.Text, QColor(tokens["text"]))
    palette.setColor(roles.Button, QColor(tokens["surface"]))
    palette.setColor(roles.ButtonText, QColor(tokens["text"]))
    palette.setColor(roles.BrightText, QColor("#ffffff"))
    palette.setColor(roles.ToolTipBase, QColor(tokens["surface"]))
    palette.setColor(roles.ToolTipText, QColor(tokens["text"]))
    palette.setColor(roles.Highlight, QColor(tokens["selection"]))
    palette.setColor(roles.HighlightedText, QColor(tokens["text_heading"]))
    palette.setColor(roles.Link, QColor(tokens["accent"]))
    palette.setColor(roles.PlaceholderText, QColor(tokens["text_muted"]))
    for role in (
        roles.WindowText,
        roles.Text,
        roles.ButtonText,
        roles.PlaceholderText,
    ):
        palette.setColor(
            groups.Disabled, role, QColor(tokens["text_disabled"])
        )
    return palette


def build_base_style(mode: str = "light", family: str = FONT_FAMILY) -> str:
    tokens = colors(mode)
    return f"""
QWidget {{
    color: {tokens["text"]};
}}
QToolTip {{
    background: {tokens["surface"]};
    color: {tokens["text"]};
    border: 1px solid {tokens["border"]};
    padding: 4px 7px;
}}
QMenu {{
    background: {tokens["surface"]};
    color: {tokens["text"]};
    border: 1px solid {tokens["border"]};
    padding: 3px;
}}
QMenu::item {{
    color: {tokens["text"]};
    background: transparent;
    padding: 3px 24px 3px 18px;
}}
QMenu::item:selected {{
    background: {tokens["accent_soft"]};
    color: {tokens["accent_hover"]};
}}
QMenu::item:disabled {{
    color: {tokens["text_disabled"]};
}}
QDialog, QMessageBox {{
    background: {tokens["surface"]};
    color: {tokens["text"]};
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {tokens["surface"]};
    color: {tokens["text"]};
    border: 1px solid {tokens["border_strong"]};
    border-radius: 6px;
    padding: 5px 7px;
    selection-background-color: {tokens["selection"]};
    selection-color: {tokens["text_heading"]};
}}
QComboBox QAbstractItemView, QAbstractItemView {{
    background: {tokens["surface"]};
    color: {tokens["text"]};
    selection-background-color: {tokens["selection"]};
    selection-color: {tokens["text_heading"]};
}}
QPushButton {{
    background: {tokens["surface"]};
    color: {tokens["text"]};
    border: 1px solid {tokens["border_strong"]};
}}
QPushButton:disabled {{
    background: {tokens["canvas"]};
    color: {tokens["text_disabled"]};
    border-color: {tokens["border"]};
}}
QCheckBox {{
    color: {tokens["text"]};
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    background: {tokens["surface"]};
    border: 1px solid {tokens["border_strong"]};
    border-radius: 3px;
}}
QCheckBox::indicator:checked {{
    background: {tokens["accent"]};
    border-color: {tokens["accent_hover"]};
}}
QCheckBox::indicator:disabled {{
    background: {tokens["surface_subtle"]};
    border-color: {tokens["border"]};
}}
QTabBar {{
    qproperty-drawBase: 0;
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: {tokens["surface_alt"]};
    width: 12px;
    margin: 1px;
}}
QScrollBar::handle:vertical {{
    background: {tokens["border_strong"]};
    min-height: 28px;
    border-radius: 5px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


def build_dark_overrides() -> str:
    tokens = DARK_COLORS
    return f"""
QWidget#root {{
    background: {tokens["canvas"]};
    color: {tokens["text"]};
}}
QToolBar#mainToolbar {{
    background: {tokens["surface"]};
    border-bottom-color: {tokens["border"]};
}}
QToolBar#recentToolbar, QWidget#recentHost {{
    background: {tokens["surface_alt"]};
}}
QToolBar QToolButton {{
    color: {tokens["text"]};
}}
QToolBar QToolButton:hover {{
    background: {tokens["surface_subtle"]};
    border-color: {tokens["border"]};
}}
QTabBar#recentTabs::tab, QTabWidget#previewTabs QTabBar::tab {{
    background: {tokens["surface_subtle"]};
    color: {tokens["text_muted"]};
    border-color: {tokens["border"]};
}}
QTabBar#recentTabs::tab:selected, QTabWidget#previewTabs QTabBar::tab:selected {{
    background: {tokens["surface"]};
    color: {tokens["accent"]};
}}
QLabel#title, QLabel#dropTitle, QLabel#sectionTitle {{
    color: {tokens["text_heading"]};
}}
QLabel#muted, QLabel#status, QLabel#recentLabel {{
    color: {tokens["text_muted"]};
}}
QLabel#smallBadge, QLabel#pill {{
    background: {tokens["surface_subtle"]};
    color: {tokens["text_muted"]};
    border-color: {tokens["border"]};
}}
QFrame#card, QFrame#plotCard {{
    background: {tokens["surface"]};
    border-color: {tokens["border"]};
}}
QFrame#dropZone {{
    background: {tokens["surface_subtle"]};
    border-color: {tokens["border_strong"]};
}}
QFrame#dropZone[hot="true"] {{
    background: {tokens["accent_soft"]};
    border-color: {tokens["accent"]};
}}
QLabel#dropIcon {{
    background: {tokens["accent_soft"]};
    border-color: {tokens["border"]};
}}
QLabel#error {{
    background: {tokens["danger_soft"]};
    color: {tokens["danger"]};
    border-color: {tokens["danger"]};
}}
QPushButton#outlineButton, QPushButton#smallButton {{
    background: {tokens["surface"]};
    color: {tokens["text"]};
    border-color: {tokens["border_strong"]};
}}
QPushButton#outlineButton:hover, QPushButton#smallButton:hover {{
    background: {tokens["surface_subtle"]};
    border-color: {tokens["text_muted"]};
}}
QPushButton#primaryButton {{
    background: {tokens["accent"]};
    color: #0a0a0a;
    border-color: {tokens["accent_hover"]};
}}
QPushButton:disabled {{
    background: {tokens["surface_subtle"]};
    color: {tokens["text_disabled"]};
    border-color: {tokens["border"]};
}}
QTableWidget#fileTable, QPlainTextEdit#preview {{
    background: {tokens["surface"]};
    color: {tokens["text"]};
    border-color: {tokens["border"]};
    selection-background-color: {tokens["selection"]};
    selection-color: {tokens["text_heading"]};
}}
QHeaderView::section {{
    background: {tokens["surface_subtle"]};
    color: {tokens["text_muted"]};
    border-bottom-color: {tokens["border"]};
}}
QTabWidget#previewTabs::pane {{
    background: {tokens["surface"]};
    border-color: {tokens["border"]};
}}
QScrollArea#plotPreview, QWidget#plotHost {{
    background: {tokens["surface"]};
}}
QCheckBox {{
    color: {tokens["text"]};
}}
"""


BASE_STYLE = build_base_style("light")


def apply_theme(
    app: QApplication,
    screen_stylesheet: str,
    mode: str = "light",
    font_family: str = FONT_FAMILY,
    font_size: int = 10,
) -> None:
    mode = "dark" if mode == "dark" else "light"
    app.setProperty("dataMergerTheme", mode)
    app.setStyle("Fusion")
    app.setFont(font(font_size, family=font_family))
    app.setPalette(build_palette(mode))
    stylesheet = build_base_style(mode, font_family) + "\n" + screen_stylesheet
    if mode == "dark":
        stylesheet += "\n" + build_dark_overrides()
    app.setStyleSheet(stylesheet)


def enforce_design_invariants(root: QWidget) -> None:
    """Disable native tab baselines that ignore Qt stylesheets."""
    for tab_bar in root.findChildren(QTabBar):
        tab_bar.setDrawBase(False)
