"""Design tokens, light/dark palettes, and mandatory Qt styling rules."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QPainter,
    QPalette,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle, QTabBar, QWidget

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
    "accent": "#39c5bb",
    "accent_hover": "#2fafa6",
    "accent_soft": "#e8faf8",
    "selection": "#d9f6f3",
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
    "accent": "#8f8f8f",
    "accent_hover": "#b5b5b5",
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
        "selection": tokens["accent"],
    }


class SignalWeaveStyle(QProxyStyle):
    """Fusion styling with outlined check marks instead of filled boxes."""

    def __init__(self) -> None:
        super().__init__("Fusion")

    def drawPrimitive(
        self,
        element,
        option,
        painter: QPainter,
        widget: QWidget | None = None,
    ) -> None:
        check_elements = {
            QStyle.PrimitiveElement.PE_IndicatorCheckBox,
            QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck,
            QStyle.PrimitiveElement.PE_IndicatorMenuCheckMark,
        }
        if element in check_elements:
            self._draw_check_mark(option, painter)
            return
        super().drawPrimitive(element, option, painter, widget)

    @staticmethod
    def _draw_check_mark(option, painter: QPainter) -> None:
        tokens = colors(active_mode())
        rect = QRectF(option.rect)
        side = min(15.0, rect.width() - 2.0, rect.height() - 2.0)
        if side < 7:
            return
        box = QRectF(
            rect.center().x() - side / 2,
            rect.center().y() - side / 2,
            side,
            side,
        )
        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
        checked = bool(option.state & QStyle.StateFlag.State_On)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        background = QColor(tokens["surface"])
        if hovered and enabled:
            background = QColor(tokens["accent_soft"])
        border = QColor(tokens["accent"] if checked else tokens["border_strong"])
        check = QColor(tokens["accent_hover"])
        if not enabled:
            background = QColor(tokens["surface_subtle"])
            border = QColor(tokens["text_disabled"])
            check = QColor(tokens["text_disabled"])

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(background)
        painter.setPen(QPen(border, 1.4))
        painter.drawRoundedRect(box.adjusted(0.7, 0.7, -0.7, -0.7), 3, 3)
        if checked:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(
                QPen(
                    check,
                    max(1.7, side * 0.12),
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            painter.drawPolyline(
                QPolygonF(
                    [
                        QPointF(box.left() + side * 0.24, box.top() + side * 0.52),
                        QPointF(box.left() + side * 0.43, box.top() + side * 0.70),
                        QPointF(box.left() + side * 0.77, box.top() + side * 0.31),
                    ]
                )
            )
        painter.restore()


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
QToolBar::separator {{
    background: {tokens["border"]};
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
QTabBar#recentTabs::tab:disabled, QTabWidget#previewTabs QTabBar::tab:disabled {{
    background: {tokens["surface_alt"]};
    color: {tokens["text_disabled"]};
    border-color: {tokens["border"]};
}}
QTabBar#recentTabs::tab:selected, QTabWidget#previewTabs QTabBar::tab:selected {{
    background: {tokens["surface"]};
    color: {tokens["accent"]};
}}
QTabBar#recentTabs::tab:hover:!selected, QTabWidget#previewTabs QTabBar::tab:hover:!selected {{
    background: {tokens["surface_subtle"]};
    color: {tokens["text"]};
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
QSplitter::handle:hover {{
    background: {tokens["border_strong"]};
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
    background: #343434;
    color: #f0f0f0;
    border-color: #565656;
}}
QPushButton#primaryButton:hover {{
    background: #404040;
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
QMenu {{
    background: {tokens["surface"]};
    color: {tokens["text"]};
    border-color: {tokens["border"]};
}}
QMenu::item {{
    color: {tokens["text"]};
    background: transparent;
}}
QMenu::item:selected {{
    background: {tokens["accent_soft"]};
    color: {tokens["text_heading"]};
}}
QMenu::item:disabled {{
    color: {tokens["text_disabled"]};
}}
"""


BASE_STYLE = build_base_style("light")
_CHECK_STYLE: SignalWeaveStyle | None = None


def apply_theme(
    app: QApplication,
    screen_stylesheet: str,
    mode: str = "light",
    font_family: str = FONT_FAMILY,
    font_size: int = 10,
) -> None:
    global _CHECK_STYLE
    mode = "dark" if mode == "dark" else "light"
    app.setProperty("dataMergerTheme", mode)
    if _CHECK_STYLE is None:
        _CHECK_STYLE = SignalWeaveStyle()
        _CHECK_STYLE.setParent(app)
    app.setStyle(_CHECK_STYLE)
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
