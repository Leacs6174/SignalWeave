"""Qt-native scatter plotting with drag-to-zoom and reset support."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from plot_data import ScatterGraph
from theme import CHANNEL_COLORS


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


class ScatterPlot(QWidget):
    zoomChanged = Signal(bool)

    def __init__(self, graph: ScatterGraph, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.graph = graph
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
            self.update()
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
        self.update()
        self.zoomChanged.emit(self.is_zoomed())

    def leaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._drag_start is None:
            self.unsetCursor()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor("#e2e8f0"), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(bounds, 10, 10)
        plot = self._plot_rect()
        painter.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold))
        painter.setPen(QColor("#172033"))
        painter.drawText(
            QRectF(16, 10, self.width() - 32, 26),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.graph.title,
        )

        if not self._has_data:
            painter.setFont(QFont("Microsoft YaHei UI", 9))
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(
                bounds,
                Qt.AlignmentFlag.AlignCenter,
                "当前通道没有可绘制的数据",
            )
            return

        x_min, x_max = self._view_x
        y_min, y_max = self._view_y
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QPen(QColor("#e8edf3"), 1))
        tick_count = 5
        for index in range(tick_count + 1):
            fraction = index / tick_count
            x = plot.left() + plot.width() * fraction
            y = plot.bottom() - plot.height() * fraction
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        painter.setPen(QPen(QColor("#8a99aa"), 1.2))
        painter.drawLine(plot.bottomLeft(), plot.bottomRight())
        painter.drawLine(plot.bottomLeft(), plot.topLeft())
        painter.setPen(QColor("#64748b"))
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

        painter.setPen(QColor("#64748b"))
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

        base = QColor(CHANNEL_COLORS[self.graph.color_index % len(CHANNEL_COLORS)])
        legend_x = plot.left()
        for series_index, series in enumerate(self.graph.series):
            color = QColor(base)
            if series_index:
                color = color.lighter(108 + (series_index % 4) * 10)
            painter.setPen(
                QPen(
                    color,
                    4.2,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
            )
            points = QPolygonF()
            for x_value, y_value in zip(series.x, series.y):
                if not (x_min <= x_value <= x_max and y_min <= y_value <= y_max):
                    continue
                points.append(
                    QPointF(self._raw_to_x(x_value), self._raw_to_y(y_value))
                )
            painter.drawPoints(points)
            painter.setPen(color)
            painter.setFont(QFont("Microsoft YaHei UI", 8))
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

        if self._selection is not None:
            painter.setPen(QPen(QColor("#2563eb"), 1.2, Qt.PenStyle.DashLine))
            painter.setBrush(QColor(37, 99, 235, 32))
            painter.drawRect(self._selection)


class PlotPreviewWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("plotPreviewContainer")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        tools = QHBoxLayout()
        hint = QLabel("拖动绘图区框选缩放；拖动横轴或纵轴可单轴缩放")
        hint.setObjectName("muted")
        tools.addWidget(hint)
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
            plot = ScatterPlot(graph)
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
