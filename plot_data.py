"""Convert merged tables into lightweight scatter-plot data."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

from electrochem_core import ElectrochemMergeResult
from spectrum_core import MergeResult

CD_CHANNEL_ORDER = ("CD", "HT", "Abs", "G")
_FILE_SUFFIX_RE = re.compile(r"^(?P<channel>.*?)(?P<index>\d+)$")


@dataclass(frozen=True)
class ScatterSeries:
    name: str
    x: tuple[float, ...]
    y: tuple[float, ...]


@dataclass(frozen=True)
class ScatterGraph:
    title: str
    x_label: str
    y_label: str
    series: tuple[ScatterSeries, ...]
    color_index: int = 0
    reverse_x: bool = False


def _series_values(
    rows: tuple[tuple[str, ...], ...],
    x_index: int,
    y_index: int,
    name: str,
) -> ScatterSeries | None:
    points: list[tuple[float, float]] = []
    for row in rows:
        x_text = row[x_index]
        y_text = row[y_index]
        if not x_text or not y_text:
            continue
        try:
            x = float(x_text)
            y = float(y_text)
        except ValueError:
            continue
        if math.isfinite(x) and math.isfinite(y):
            points.append((x, y))
    if not points:
        return None
    return ScatterSeries(
        name=name,
        x=tuple(point[0] for point in points),
        y=tuple(point[1] for point in points),
    )


def _cd_header_channel(header: str) -> str | None:
    match = _FILE_SUFFIX_RE.match(header)
    if match:
        return match.group("channel")
    return None


def cd_plot_graphs(
    result: MergeResult,
    enabled_channels: Iterable[str],
) -> tuple[ScatterGraph, ...]:
    enabled = set(enabled_channels)
    graphs: list[ScatterGraph] = []
    for color_index, channel in enumerate(CD_CHANNEL_ORDER):
        if channel not in enabled:
            continue
        series: list[ScatterSeries] = []
        for index, header in enumerate(result.header[1:], start=1):
            if _cd_header_channel(header) != channel:
                continue
            values = _series_values(result.export_rows, 0, index, header)
            if values is not None:
                series.append(values)
        if series:
            graphs.append(
                ScatterGraph(
                    title="G 因子" if channel == "G" else channel,
                    x_label=result.header[0],
                    y_label="G" if channel == "G" else channel,
                    series=tuple(series),
                    color_index=color_index,
                    reverse_x=True,
                )
            )
    return tuple(graphs)


def electrochem_plot_graphs(
    result: ElectrochemMergeResult,
    enabled_channels: Iterable[str],
) -> tuple[ScatterGraph, ...]:
    enabled = set(enabled_channels)
    graphs: list[ScatterGraph] = []
    for color_index, channel in enumerate(result.channels):
        if channel not in enabled:
            continue
        series: list[ScatterSeries] = []
        for descriptor in result.series:
            if descriptor.channel != channel:
                continue
            index = result.header.index(descriptor.header)
            values = _series_values(
                result.rows, 0, index, descriptor.header
            )
            if values is not None:
                series.append(values)
        if series:
            graphs.append(
                ScatterGraph(
                    title=channel,
                    x_label=result.axis_label,
                    y_label=channel,
                    series=tuple(series),
                    color_index=color_index,
                )
            )
    return tuple(graphs)
