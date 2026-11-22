"""CHI electrochemical TXT parsing and exact-union merging."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_AXIS_TOLERANCE = 1e-9
_SPLIT_RE = re.compile(r"[\s,;\t]+")
_UNIT_RE = re.compile(
    r"^\s*(?P<name>.*?)\s*(?:/|\(|\[)\s*(?P<unit>[^/()\[\]]+?)\s*[\)\]]?\s*$"
)


class ElectrochemError(ValueError):
    """A user-facing electrochemical input or merge error."""


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _split_fields(line: str) -> list[str]:
    stripped = line.strip().strip("\ufeff")
    if not stripped:
        return []
    if "\t" in stripped:
        parts = stripped.split("\t")
    elif "," in stripped:
        parts = stripped.split(",")
    else:
        parts = _SPLIT_RE.split(stripped)
    return [part.strip().strip('"').strip("'") for part in parts if part.strip()]


def _parse_header_field(field: str) -> tuple[str, str]:
    match = _UNIT_RE.match(field)
    if match:
        name = match.group("name").strip()
        unit = match.group("unit").strip()
    else:
        name = field.strip()
        unit = ""
    name = re.sub(r"\s+", " ", name)
    if not name:
        raise ElectrochemError(f"无法识别列标题：{field}")
    return name, unit


def _is_float(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _looks_like_header(line: str) -> bool:
    fields = _split_fields(line)
    if len(fields) < 2 or all(_is_float(field) for field in fields):
        return False
    named = sum(any(char.isalpha() for char in field) for field in fields)
    has_unit = any(
        "/" in field or "(" in field or "[" in field for field in fields
    )
    return named == len(fields) and has_unit and ":" not in line


def _normalize_words(text: str) -> str:
    return re.sub(r"[\s_\-]+", " ", text.strip().lower())


def _axis_kind(name: str) -> str:
    normalized = _normalize_words(name)
    if "time" in normalized or "时间" in normalized:
        return "time"
    if (
        "potential" in normalized
        or "voltage" in normalized
        or "电位" in normalized
        or "电势" in normalized
        or "电压" in normalized
    ):
        return "potential"
    if "wavelength" in normalized or "波长" in normalized:
        return "wavelength"
    if "capacity" in normalized or "容量" in normalized:
        return "capacity"
    if "frequency" in normalized or "频率" in normalized:
        return "frequency"
    if normalized in {"x", "e"} or normalized.startswith("x "):
        return "generic"
    return ""


def _normalize_unit(unit: str) -> str:
    aliases = {
        "sec": "s",
        "secs": "s",
        "second": "s",
        "seconds": "s",
        "秒": "s",
        "v": "v",
        "volt": "v",
        "volts": "v",
        "伏": "v",
        "a": "a",
        "amp": "a",
        "amps": "a",
        "安": "a",
        "nm": "nm",
    }
    normalized = unit.strip().lower().replace(" ", "")
    return aliases.get(normalized, normalized)


@dataclass(frozen=True)
class Axis:
    name: str
    unit: str

    @property
    def label(self) -> str:
        return f"{self.name} ({self.unit})" if self.unit else self.name

    @property
    def identity(self) -> str:
        return f"{_axis_kind(self.name)}:{_normalize_unit(self.unit)}"


@dataclass(frozen=True)
class ElectrochemSignal:
    path: Path
    axis: Axis
    x_values: tuple[float, ...]
    x_text: tuple[str, ...]
    channels: dict[str, tuple[str, ...]]
    data_line_numbers: tuple[int, ...]

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def points(self) -> int:
        return len(self.x_values)

    @property
    def x_min(self) -> float:
        return min(self.x_values)

    @property
    def x_max(self) -> float:
        return max(self.x_values)

    @property
    def channel_names(self) -> tuple[str, ...]:
        return tuple(self.channels)


def _select_axis(headers: Sequence[tuple[str, str]]) -> int:
    kinds = [_axis_kind(name) for name, _ in headers]
    if kinds[0]:
        return 0
    for index, kind in enumerate(kinds):
        if kind and kind != "generic":
            return index
    for index, kind in enumerate(kinds):
        if kind:
            return index
    return 0


def _unique_channel_names(headers: Sequence[tuple[str, str]]) -> tuple[str, ...]:
    result: list[str] = []
    counts: dict[str, int] = {}
    for name, _ in headers:
        base = re.sub(r"\s+", "", name) or "Y"
        counts[base] = counts.get(base, 0) + 1
        result.append(base if counts[base] == 1 else f"{base}_{counts[base]}")
    return tuple(result)


def read_electrochem(
    path: str | Path,
    tolerance: float = DEFAULT_AXIS_TOLERANCE,
) -> ElectrochemSignal:
    """Read one CHI-style TXT table and detect its x-axis from the header."""
    source = Path(path)
    if source.suffix.lower() != ".txt":
        raise ElectrochemError("电化学模式只支持 .txt 文件")
    if tolerance < 0 or not math.isfinite(tolerance):
        raise ElectrochemError("横坐标容差必须是非负有限数")
    try:
        lines = _decode(source.read_bytes()).splitlines()
    except OSError as exc:
        raise ElectrochemError(f"无法读取文件：{exc}") from exc

    header_index = -1
    header_fields: list[str] = []
    for index, line in enumerate(lines[:300]):
        if _looks_like_header(line):
            fields = _split_fields(line)
            if len(fields) >= 2:
                header_index = index
                header_fields = fields
                break
    if header_index < 0:
        raise ElectrochemError("未找到至少包含两列的文本表头")

    headers = [_parse_header_field(field) for field in header_fields]
    x_index = _select_axis(headers)
    y_indices = [index for index in range(len(headers)) if index != x_index]
    if not y_indices:
        raise ElectrochemError("表头只有横坐标，没有可合并的数据列")

    rows: list[list[str]] = []
    line_numbers: list[int] = []
    for line_number, raw_line in enumerate(
        lines[header_index + 1 :], start=header_index + 2
    ):
        if not raw_line.strip():
            if rows:
                break
            continue
        fields = _split_fields(raw_line)
        if len(fields) != len(headers):
            if rows:
                break
            raise ElectrochemError(
                f"第 {line_number} 行有 {len(fields)} 列，应为 {len(headers)} 列"
            )
        try:
            values = [float(field) for field in fields]
        except ValueError as exc:
            if rows:
                break
            raise ElectrochemError(f"第 {line_number} 行不是有效数值数据") from exc
        if not all(math.isfinite(value) for value in values):
            raise ElectrochemError(f"第 {line_number} 行包含 NaN 或无穷大")
        rows.append(fields)
        line_numbers.append(line_number)

    if not rows:
        raise ElectrochemError("表头后没有可用数值数据")

    x_values = [float(row[x_index]) for row in rows]
    channel_names = _unique_channel_names([headers[index] for index in y_indices])
    channels = {
        name: tuple(row[index] for row in rows)
        for name, index in zip(channel_names, y_indices)
    }
    axis_name, axis_unit = headers[x_index]
    return ElectrochemSignal(
        path=source,
        axis=Axis(axis_name, axis_unit),
        x_values=tuple(x_values),
        x_text=tuple(row[x_index] for row in rows),
        channels=channels,
        data_line_numbers=tuple(line_numbers),
    )


@dataclass(frozen=True)
class ElectrochemSeries:
    channel: str
    header: str
    file_index: int
    # Export rows are sorted by x for Origin; CV previews need acquisition order.
    plot_x: tuple[float, ...]
    plot_y: tuple[float, ...]


@dataclass(frozen=True)
class ElectrochemMergeResult:
    axis_label: str
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    missing_values: int
    participating_files: int
    channels: tuple[str, ...]
    series: tuple[ElectrochemSeries, ...]

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        return len(self.header)

    @property
    def text(self) -> str:
        lines = ["\t".join(self.header)]
        blank_row = "\t" * (len(self.header) - 1)
        lines.extend((blank_row, blank_row))
        lines.extend("\t".join(row) for row in self.rows)
        return "\n".join(lines)


@dataclass(frozen=True)
class _Point:
    x: float
    file_index: int
    point_index: int


def _build_groups(
    signals: Sequence[ElectrochemSignal], tolerance: float
) -> list[list[_Point]]:
    points = sorted(
        (
            _Point(x, file_index, point_index)
            for file_index, signal in enumerate(signals)
            for point_index, x in enumerate(signal.x_values)
        ),
        key=lambda point: point.x,
    )
    groups: list[list[_Point]] = []
    current: list[_Point] | None = None
    for point in points:
        if current is None or point.x - current[0].x > tolerance:
            current = [point]
            groups.append(current)
        else:
            current.append(point)
    return groups


def merge_electrochem(
    signals: Iterable[ElectrochemSignal],
    tolerance: float = DEFAULT_AXIS_TOLERANCE,
    channels: Sequence[str] | None = None,
) -> ElectrochemMergeResult:
    """Merge same-axis signals side by side without interpolation."""
    selected = list(signals)
    if not selected:
        raise ElectrochemError("没有参与合并的文件")
    identity = selected[0].axis.identity
    mismatched = [
        signal.name
        for signal in selected[1:]
        if signal.axis.identity != identity
    ]
    if mismatched:
        raise ElectrochemError(
            "所选文件的横坐标不一致："
            f"{selected[0].axis.label} 与 {selected[1].axis.label}。"
            "请分别合并相同横坐标的数据"
        )

    available_channels = tuple(
        dict.fromkeys(
            channel
            for signal in selected
            for channel in signal.channel_names
        )
    )
    if channels is None:
        selected_channels = available_channels
    else:
        unknown = [channel for channel in channels if channel not in available_channels]
        if unknown:
            raise ElectrochemError(
                "未知或不存在的电化学通道：" + "、".join(unknown)
            )
        selected_channels = tuple(
            channel
            for channel in available_channels
            if channel in set(channels)
        )
    if not selected_channels:
        raise ElectrochemError("至少选择一个电化学数据通道")

    groups = _build_groups(selected, tolerance)
    groups.sort(key=lambda group: group[0].x)
    header = [selected[0].axis.label]
    series: list[ElectrochemSeries] = []
    for file_index, signal in enumerate(selected, start=1):
        for channel in selected_channels:
            if channel not in signal.channels:
                continue
            header_name = f"{channel}{file_index}"
            header.append(header_name)
            series.append(
                ElectrochemSeries(
                    channel=channel,
                    header=header_name,
                    file_index=file_index,
                    plot_x=signal.x_values,
                    plot_y=tuple(
                        float(value) for value in signal.channels[channel]
                    ),
                )
            )

    rows: list[tuple[str, ...]] = []
    missing_values = 0
    for group in groups:
        by_file: dict[int, list[_Point]] = {}
        for point in group:
            by_file.setdefault(point.file_index, []).append(point)
        occurrence_count = max(len(items) for items in by_file.values())
        for occurrence in range(occurrence_count):
            representative = min(
                (
                    items[min(occurrence, len(items) - 1)]
                    for items in by_file.values()
                ),
                key=lambda point: (point.file_index, point.point_index),
            )
            row = [
                selected[representative.file_index].x_text[
                    representative.point_index
                ]
            ]
            for file_index, signal in enumerate(selected):
                items = by_file.get(file_index, [])
                point = items[occurrence] if occurrence < len(items) else None
                for channel_name in selected_channels:
                    if channel_name not in signal.channels:
                        continue
                    cell = (
                        signal.channels[channel_name][point.point_index]
                        if point is not None
                        else ""
                    )
                    if cell == "":
                        missing_values += 1
                    row.append(cell)
            rows.append(tuple(row))

    return ElectrochemMergeResult(
        axis_label=selected[0].axis.label,
        header=tuple(header),
        rows=tuple(rows),
        missing_values=missing_values,
        participating_files=len(selected),
        channels=selected_channels,
        series=tuple(series),
    )
