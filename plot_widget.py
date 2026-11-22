"""Qt-native scatter plotting with drag-to-zoom and reset support."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QApplication,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from plot_data import ScatterGraph
from theme import chart_colors
from user_config import DEFAULT_MARKER_SIZE, DEFAULT_SERIES_COLORS


def _expanded_range(low: float, high: float) -> tuple[float, float]:
    if high > low:
        padding = (high - low) * 0.06
        return low - padding, high + padding
    padding = abs(low) * 0.06 or 1.0
    return low - padding, high + padding


def _format_tick(value: float) -> str:
    if value == 0:
        return "0"
    return f"{value:.4g}"


def _plot_font(size_delta: int, weight: QFont.Weight) -> QFont:
    font = QFont(QApplication.font())
    font.setPointSize(max(6, font.pointSize() + size_delta))
    font.setWeight(weight)
    return font


class _SelectionOverlay(QWidget):
    """Draw only the rubber band so mouse movement never repaints the chart."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._selection: QRectF | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

    def set_selection(self, selection: QRectF | None) -> None:
        self._selection = selection
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        del event
        if self._selection is None:
            return
        tokens = chart_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selection_color = QColor(tokens["selection"])
        painter.setPen(QPen(selection_color, 1.2, Qt.PenStyle.DashLine))
        selection_color.setAlpha(48)
        painter.setBrush(selection_color)
        painter.drawRect(self._selection)


class ScatterPlot(QWidget):
    zoomChanged = Signal(bool)

    def __init__(
        self,
        graph: ScatterGraph,
        parent: QWidget | None = None,
        *,
        render_mode: str = "line",
        marker_size: float = DEFAULT_MARKER_SIZE,
        series_colors: tuple[str, ...] = DEFAULT_SERIES_COLORS,
    ) -> None:
        super().__init__(parent)
        self.graph = graph
        self.render_mode = render_mode
        self.marker_size = marker_size
        self.series_colors = series_colors
        self.setMinimumHeight(230)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.setMouseTracking(True)
        all_x = [value for series in graph.series for value in series.x]
        all_y = [value for series in graph.series for value in series.y]
        self._has_data = bool(all_x and all_y)
        if self._has_data:
            self._full_x = _expanded_range(min(all_x), max(all_x))
            self._full_y = _expanded_range(min(all_y), max(all_y))
        else:
            self._full_x = (0.0, 1.0)
            self._full_y = (0.0, 1.0)
        self._view_x = self._full_x
        self._view_y = self._full_y
        self._drag_start: QPointF | None = None
        self._drag_mode = ""
        self._selection: QRectF | None = None
        self._static_cache: QPixmap | None = None
        self._selection_overlay = _SelectionOverlay(self)
        self._selection_overlay.setGeometry(self.rect())
        self._selection_overlay.show()

    def apply_render_settings(
        self,
        render_mode: str,
        marker_size: float,
        series_colors: tuple[str, ...],
    ) -> None:
        self.render_mode = render_mode
        self.marker_size = marker_size
        self.series_colors = series_colors or DEFAULT_SERIES_COLORS
        self._static_cache = None
        self.update()

    def refresh_theme(self) -> None:
        self._static_cache = None
        self._selection_overlay.update()
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(520, 260)

    def _plot_rect(self) -> QRectF:
        return QRectF(
            56,
            48,
            max(10, self.width() - 78),
            max(10, self.height() - 105),
        )

    def _raw_to_x(self, raw: float) -> float:
        x_min, x_max = self._view_x
        fraction = (raw - x_min) / (x_max - x_min)
        if self.graph.reverse_x:
            fraction = 1.0 - fraction
        return self._plot_rect().left() + fraction * self._plot_rect().width()

    def _raw_to_y(self, raw: float) -> float:
        y_min, y_max = self._view_y
        fraction = (raw - y_min) / (y_max - y_min)
        return self._plot_rect().bottom() - fraction * self._plot_rect().height()

    def _pixel_to_x(self, pixel: float) -> float:
        plot = self._plot_rect()
        fraction = min(1.0, max(0.0, (pixel - plot.left()) / plot.width()))
        if self.graph.reverse_x:
            fraction = 1.0 - fraction
        return self._view_x[0] + fraction * (
            self._view_x[1] - self._view_x[0]
        )

    def _pixel_to_y(self, pixel: float) -> float:
        plot = self._plot_rect()
        fraction = min(1.0, max(0.0, (plot.bottom() - pixel) / plot.height()))
        return self._view_y[0] + fraction * (
            self._view_y[1] - self._view_y[0]
        )

    def _x_tick(self, fraction: float) -> float:
        low, high = self._view_x
        if self.graph.reverse_x:
            return high - (high - low) * fraction
        return low + (high - low) * fraction

    def _y_tick(self, fraction: float) -> float:
        low, high = self._view_y
        return low + (high - low) * fraction

    @property
    def view_x_range(self) -> tuple[float, float]:
        return self._view_x

    @property
    def view_y_range(self) -> tuple[float, float]:
        return self._view_y

    def is_zoomed(self) -> bool:
        if not self._has_data:
            return False
        return self._view_x != self._full_x or self._view_y != self._full_y

    def reset_zoom(self) -> None:
        self._view_x = self._full_x
        self._view_y = self._full_y
        self._selection = None
        self._static_cache = None
        self.update()
        self.zoomChanged.emit(False)

    def _press_mode(self, position: QPointF) -> str:
        plot = self._plot_rect()
        near_x_axis = (
            plot.left() - 8 <= position.x() <= plot.right() + 8
            and plot.bottom() - 8 <= position.y() <= plot.bottom() + 30
        )
        near_y_axis = (
            plot.left() - 38 <= position.x() <= plot.left() + 10
            and plot.top() - 8 <= position.y() <= plot.bottom() + 8
        )
        if near_x_axis:
            return "x"
        if near_y_axis:
            return "y"
        if plot.contains(position):
            return "xy"
        return ""

    def _selection_rect(self, start: QPointF, current: QPointF, mode: str) -> QRectF:
        plot = self._plot_rect()
        if mode == "x":
            left = min(start.x(), current.x())
            width = abs(current.x() - start.x())
            return QRectF(left, plot.top(), width, plot.height())
        if mode == "y":
            top = min(start.y(), current.y())
            height = abs(current.y() - start.y())
            return QRectF(plot.left(), top, plot.width(), height)
        return QRectF(start, current).normalized().intersected(plot)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            mode = self._press_mode(event.position())
            if mode:
                self._drag_start = event.position()
                self._drag_mode = mode
                self._selection = None
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None:
            self._selection = self._selection_rect(
                self._drag_start, event.position(), self._drag_mode
            )
            self._selection_overlay.set_selection(self._selection)
            self._selection_overlay.raise_()
            event.accept()
            return
        mode = self._press_mode(event.position())
        if mode == "x":
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif mode == "y":
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif mode == "xy":
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._drag_start is not None
        ):
            selection = self._selection_rect(
                self._drag_start, event.position(), self._drag_mode
            )
            mode = self._drag_mode
            self._drag_start = None
            self._drag_mode = ""
            self._selection = None
            self._selection_overlay.set_selection(None)
            if selection.width() >= 5 or selection.height() >= 5:
                self._apply_zoom(selection, mode)
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _apply_zoom(self, selection: QRectF, mode: str) -> None:
        if mode in {"x", "xy"} and selection.width() >= 5:
            first = self._pixel_to_x(selection.left())
            second = self._pixel_to_x(selection.right())
            if abs(second - first) > 1e-15:
                self._view_x = (min(first, second), max(first, second))
        if mode in {"y", "xy"} and selection.height() >= 5:
            first = self._pixel_to_y(selection.top())
            second = self._pixel_to_y(selection.bottom())
            if abs(second - first) > 1e-15:
                self._view_y = (min(first, second), max(first, second))
        self._static_cache = None
        self.update()
        self.zoomChanged.emit(self.is_zoomed())

    def leaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._drag_start is None:
            self.unsetCursor()
        super().leaveEvent(event)

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        self._static_cache = None
        self._selection_overlay.setGeometry(self.rect())
        self._selection_overlay.raise_()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        del event
        if self._static_cache is None:
            ratio = self.devicePixelRatioF()
            cache = QPixmap(
                max(1, int(self.width() * ratio)),
                max(1, int(self.height() * ratio)),
            )
            cache.setDevicePixelRatio(ratio)
            cache.fill(Qt.GlobalColor.transparent)
            cache_painter = QPainter(cache)
            self._paint_static(cache_painter)
            cache_painter.end()
            self._static_cache = cache
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._static_cache)

    def _paint_static(self, painter: QPainter) -> None:
        tokens = chart_colors()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(tokens["border"]), 1))
        painter.setBrush(QColor(tokens["surface"]))
        painter.drawRoundedRect(bounds, 10, 10)
        plot = self._plot_rect()
        painter.setFont(_plot_font(0, QFont.Weight.DemiBold))
        painter.setPen(QColor(tokens["heading"]))
        painter.drawText(
            QRectF(16, 10, self.width() - 32, 26),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.graph.title,
        )

        if not self._has_data:
            painter.setFont(_plot_font(-1, QFont.Weight.Normal))
            painter.setPen(QColor(tokens["muted"]))
            painter.drawText(
                bounds,
                Qt.AlignmentFlag.AlignCenter,
                "当前通道没有可绘制的数据",
            )
            return

        x_min, x_max = self._view_x
        y_min, y_max = self._view_y
        painter.setFont(_plot_font(-2, QFont.Weight.Normal))
        painter.setPen(QPen(QColor(tokens["grid"]), 1))
        tick_count = 5
        for index in range(tick_count + 1):
            fraction = index / tick_count
            x = plot.left() + plot.width() * fraction
            y = plot.bottom() - plot.height() * fraction
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        painter.setPen(QPen(QColor(tokens["axis"]), 1.2))
        painter.drawLine(plot.bottomLeft(), plot.bottomRight())
        painter.drawLine(plot.bottomLeft(), plot.topLeft())
        painter.setPen(QColor(tokens["muted"]))
        for index in range(tick_count + 1):
            fraction = index / tick_count
            x = plot.left() + plot.width() * fraction
            y = plot.bottom() - plot.height() * fraction
            painter.drawText(
                QRectF(x - 35, plot.bottom() + 7, 70, 18),
                Qt.AlignmentFlag.AlignHCenter,
                _format_tick(self._x_tick(fraction)),
            )
            painter.drawText(
                QRectF(2, y - 9, 49, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                _format_tick(self._y_tick(fraction)),
            )

        painter.setPen(QColor(tokens["muted"]))
        painter.drawText(
            QRectF(plot.left(), self.height() - 26, plot.width(), 18),
            Qt.AlignmentFlag.AlignCenter,
            self.graph.x_label,
        )
        painter.drawText(
            QRectF(plot.right() - 140, 23, 136, 18),
            Qt.AlignmentFlag.AlignRight,
            self.graph.y_label,
        )

        legend_x = plot.left()
        for series_index, series in enumerate(self.graph.series):
            color = QColor(
                self.series_colors[
                    (self.graph.color_index + series_index)
                    % len(self.series_colors)
                ]
            )
            points = QPolygonF()
            for x_value, y_value in zip(series.x, series.y):
                if not (x_min <= x_value <= x_max and y_min <= y_value <= y_max):
                    continue
                points.append(
                    QPointF(self._raw_to_x(x_value), self._raw_to_y(y_value))
                )
            if self.render_mode == "scatter":
                painter.setPen(
                    QPen(
                        color,
                        self.marker_size,
                        Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap,
                    )
                )
                painter.drawPoints(points)
            else:
                painter.setPen(
                    QPen(
                        color,
                        1.8,
                        Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap,
                        Qt.PenJoinStyle.RoundJoin,
                    )
                )
                painter.drawPolyline(points)
            painter.setPen(color)
            painter.setFont(_plot_font(-1, QFont.Weight.Normal))
            legend_width = min(185, 22 + len(series.name) * 12)
            if legend_x + legend_width > plot.right():
                legend_x = plot.left()
            painter.drawText(
                QRectF(legend_x + 12, 25, legend_width - 12, 18),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                series.name,
            )
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(legend_x + 4, 34), 3.2, 3.2)
            legend_x += legend_width

class PlotPreviewWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("plotPreviewContainer")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        tools = QHBoxLayout()
        tools.addStretch(1)
        self.reset_button = QPushButton("复位")
        self.reset_button.setObjectName("smallButton")
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.setEnabled(False)
        self.reset_button.clicked.connect(self.reset_zoom)
        tools.addWidget(self.reset_button)
        outer.addLayout(tools)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("plotPreview")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._host = QWidget()
        self._host.setObjectName("plotHost")
        self._layout = QVBoxLayout(self._host)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        self._scroll.setWidget(self._host)
        outer.addWidget(self._scroll, 1)
        self._plots: list[ScatterPlot] = []
        self._render_mode = "line"
        self._marker_size = DEFAULT_MARKER_SIZE
        self._series_colors = DEFAULT_SERIES_COLORS
        self.set_graphs(())

    @property
    def plots(self) -> tuple[QWidget, ...]:
        return tuple(self._plots)

    def set_graphs(self, graphs: tuple[ScatterGraph, ...]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._plots.clear()
        self.reset_button.setEnabled(False)
        if not graphs:
            empty = QLabel("勾选预览通道并添加数据后，这里会显示散点图。")
            empty.setObjectName("muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumHeight(220)
            self._layout.addWidget(empty)
            self._layout.addStretch(1)
            return
        for graph in graphs:
            card = QFrame()
            card.setObjectName("plotCard")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(6, 6, 6, 6)
            plot = ScatterPlot(
                graph,
                render_mode=self._render_mode,
                marker_size=self._marker_size,
                series_colors=self._series_colors,
            )
            plot.zoomChanged.connect(self._zoom_changed)
            layout.addWidget(plot)
            self._layout.addWidget(card)
            self._plots.append(plot)
        self._layout.addStretch(1)

    def _zoom_changed(self, changed: bool) -> None:
        del changed
        self.reset_button.setEnabled(any(plot.is_zoomed() for plot in self._plots))

    def reset_zoom(self) -> None:
        for plot in self._plots:
            plot.reset_zoom()
        self.reset_button.setEnabled(False)

    def set_render_settings(
        self,
        render_mode: str,
        marker_size: float,
        series_colors: tuple[str, ...],
    ) -> None:
        self._render_mode = "scatter" if render_mode == "scatter" else "line"
        self._marker_size = marker_size
        self._series_colors = series_colors or DEFAULT_SERIES_COLORS
        for plot in self._plots:
            plot.apply_render_settings(
                self._render_mode, self._marker_size, self._series_colors
            )
