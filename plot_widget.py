"""Qt-native scatter plotting without an additional plotting dependency."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from plot_data import ScatterGraph

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
    def __init__(self, graph: ScatterGraph, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.graph = graph
        self.setMinimumHeight(230)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

    def sizeHint(self) -> QSize:
        return QSize(520, 260)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor("#e2e8f0"), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(bounds, 10, 10)

        all_x = [
            value for series in self.graph.series for value in series.x
        ]
        all_y = [
            value for series in self.graph.series for value in series.y
        ]
        plot = QRectF(56, 48, max(10, self.width() - 78), max(10, self.height() - 105))
        painter.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold))
        painter.setPen(QColor("#172033"))
        painter.drawText(
            QRectF(16, 10, self.width() - 32, 26),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.graph.title,
        )

        if not all_x or not all_y:
            painter.setFont(QFont("Microsoft YaHei UI", 9))
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(
                bounds,
                Qt.AlignmentFlag.AlignCenter,
                "当前通道没有可绘制的数据",
            )
            return

        x_min, x_max = _expanded_range(min(all_x), max(all_x))
        y_min, y_max = _expanded_range(min(all_y), max(all_y))

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
            x_value = x_min + (x_max - x_min) * fraction
            y_value = y_min + (y_max - y_min) * fraction
            x = plot.left() + plot.width() * fraction
            y = plot.bottom() - plot.height() * fraction
            painter.drawText(
                QRectF(x - 35, plot.bottom() + 7, 70, 18),
                Qt.AlignmentFlag.AlignHCenter,
                _format_tick(x_value),
            )
            painter.drawText(
                QRectF(2, y - 9, 49, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                _format_tick(y_value),
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
                x_fraction = (x_value - x_min) / (x_max - x_min)
                if self.graph.reverse_x:
                    x_fraction = 1.0 - x_fraction
                y_fraction = (y_value - y_min) / (y_max - y_min)
                points.append(
                    QPointF(
                        plot.left() + x_fraction * plot.width(),
                        plot.bottom() - y_fraction * plot.height(),
                    )
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


class PlotPreviewWidget(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("plotPreview")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._host = QWidget()
        self._host.setObjectName("plotHost")
        self._layout = QVBoxLayout(self._host)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        self.setWidget(self._host)
        self._plots: list[QWidget] = []
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
            layout.addWidget(plot)
            self._layout.addWidget(card)
            self._plots.append(plot)
        self._layout.addStretch(1)
