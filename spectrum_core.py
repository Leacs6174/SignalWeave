"""JASCO raw-spectrum parsing and exact union merging.

This module intentionally has no third-party dependencies. It keeps the
original numeric text from the source file so merging never changes precision.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_TOLERANCE = 1e-6
DEFAULT_CHANNELS = ("CD", "HT", "Abs")
G_FACTOR_DIVISOR = 32982.0
_CHANNELS_BY_COLUMN_COUNT = {
    2: ("CD",),
    3: ("CD", "HT"),
    4: ("CD", "HT", "Abs"),
}
_SPLIT_RE = re.compile(r"[\s,;]+")


class SpectrumError(ValueError):
    """A user-facing input or merge error."""


class DuplicateWavelengthError(SpectrumError):
    """Raised when one file contains wavelengths inside the matching tolerance."""


@dataclass(frozen=True)
class Spectrum:
    path: Path
    wavelengths: tuple[float, ...]
    wavelength_text: tuple[str, ...]
    channels: dict[str, tuple[str, ...]]
    data_line_numbers: tuple[int, ...]

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def points(self) -> int:
        return len(self.wavelengths)

    @property
    def wavelength_min(self) -> float:
        return min(self.wavelengths)

    @property
    def wavelength_max(self) -> float:
        return max(self.wavelengths)

    @property
    def channel_names(self) -> tuple[str, ...]:
        return tuple(self.channels)


@dataclass(frozen=True)
class MergeResult:
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    missing_values: int
    participating_files: int
    g_columns: int = 0

    @property
    def formula_row(self) -> tuple[str, ...]:
        formulas = [""] * len(self.header)
        for index in range(1, self.g_columns + 1):
            column_name = f"G{index}"
            if column_name not in self.header:
                continue
            formulas[self.header.index(column_name)] = (
                f'col("CD{index}")/(32982*col("Abs{index}"))'
            )
        return tuple(formulas)

    @property
    def formula_text(self) -> str:
        """Return the G-column formulas as one Origin label-row paste.

        After the data table has been pasted, select the G1 cell in the
        ``F(x)=`` row and paste this one-line value. Origin then stores real
        column formulas rather than literal text in the data area.
        """

        if not self.g_columns:
            return ""
        return "\t".join(self.formula_row[-self.g_columns :])

    def _row_with_g_values(self, row: tuple[str, ...]) -> tuple[str, ...]:
        """Return one data row with calculated g-factor values.

        Origin's plain-text clipboard cannot carry a column-formula row.
        Shipping the calculated values in the ordinary paste keeps the table
        directly plottable, while ``formula_text`` is available for users who
        also want live Origin column formulas.
        """

        if not self.g_columns:
            return row

        values = list(row)
        for index in range(1, self.g_columns + 1):
            cd_name = f"CD{index}"
            abs_name = f"Abs{index}"
            if cd_name not in self.header or abs_name not in self.header:
                continue
            cd_text = row[self.header.index(cd_name)]
            abs_text = row[self.header.index(abs_name)]
            if not cd_text or not abs_text:
                continue
            try:
                abs_value = float(abs_text)
                if abs_value == 0.0:
                    continue
                value = float(cd_text) / (G_FACTOR_DIVISOR * abs_value)
            except (ValueError, OverflowError):
                continue
            if not math.isfinite(value):
                continue
            rendered = format(value, ".12g")
            values[self.header.index(f"G{index}")] = "0" if rendered == "-0" else rendered
        return tuple(values)

    @property
    def text(self) -> str:
        # Origin's plain-text paste maps the first three TSV rows to Long Name,
        # Units, and Comments. The special F(x)= row is never populated by a
        # plain-text paste, so two blank label rows are required before data.
        lines = ["\t".join(self.header)]
        blank_row = "\t" * (len(self.header) - 1)
        lines.append(blank_row)
        lines.append(blank_row)
        lines.extend("\t".join(self._row_with_g_values(row)) for row in self.rows)
        return "\n".join(lines)

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        return len(self.header)


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def read_spectrum(path: str | Path, tolerance: float = DEFAULT_TOLERANCE) -> Spectrum:
    """Read one JASCO TXT containing exactly one XYDATA block."""
    source = Path(path)
    if source.suffix.lower() != ".txt":
        raise SpectrumError("只支持 JASCO 原始 .txt 文件")
    try:
        text = _decode(source.read_bytes())
    except OSError as exc:
        raise SpectrumError(f"无法读取文件：{exc}") from exc

    lines = text.splitlines()
    starts = [
        index for index, line in enumerate(lines)
        if line.strip().upper().startswith("XYDATA")
    ]
    if not starts:
        raise SpectrumError("未找到 XYDATA 数据区，这不是原始 JASCO TXT")
    if len(starts) > 1:
        raise SpectrumError("文件包含多个 XYDATA 数据区，最小版仅支持单光谱文件")

    rows: list[list[str]] = []
    numeric_rows: list[list[float]] = []
    line_numbers: list[int] = []
    expected_columns: int | None = None

    for line_number, raw_line in enumerate(lines[starts[0] + 1 :], start=starts[0] + 2):
        stripped = raw_line.strip()
        if not stripped:
            continue
        parts = [part for part in _SPLIT_RE.split(stripped) if part]
        try:
            values = [float(part) for part in parts]
        except ValueError:
            if rows:
                break
            raise SpectrumError(f"第 {line_number} 行不是有效数值数据")

        if not 2 <= len(values) <= 4:
            raise SpectrumError(
                f"第 {line_number} 行有 {len(values)} 列；仅支持 波长 + CD/HT/Abs 的 2～4 列"
            )
        if not all(math.isfinite(value) for value in values):
            raise SpectrumError(f"第 {line_number} 行包含 NaN 或无穷大")
        if expected_columns is None:
            expected_columns = len(values)
        elif len(values) != expected_columns:
            raise SpectrumError(
                f"第 {line_number} 行有 {len(values)} 列，前一行有 {expected_columns} 列"
            )
        rows.append(parts)
        numeric_rows.append(values)
        line_numbers.append(line_number)

    if not rows or expected_columns is None:
        raise SpectrumError("XYDATA 后没有可用的数值数据")

    wavelengths = [values[0] for values in numeric_rows]
    ordered = sorted(range(len(wavelengths)), key=wavelengths.__getitem__)
    for left, right in zip(ordered, ordered[1:]):
        delta = abs(wavelengths[right] - wavelengths[left])
        if delta <= tolerance:
            raise DuplicateWavelengthError(
                "同一文件存在重复波长："
                f"{wavelengths[left]:g}（第 {line_numbers[left]} 行）与 "
                f"{wavelengths[right]:g}（第 {line_numbers[right]} 行），"
                f"相差 {delta:g} nm"
            )

    channel_names = _CHANNELS_BY_COLUMN_COUNT[expected_columns]
    channels = {
        name: tuple(row[column_index] for row in rows)
        for column_index, name in enumerate(channel_names, start=1)
    }
    return Spectrum(
        path=source,
        wavelengths=tuple(wavelengths),
        wavelength_text=tuple(row[0] for row in rows),
        channels=channels,
        data_line_numbers=tuple(line_numbers),
    )


@dataclass(frozen=True)
class _Point:
    wavelength: float
    file_index: int
    point_index: int


@dataclass
class _Group:
    points: list[_Point]


def _build_exact_union(
    spectra: Sequence[Spectrum], tolerance: float
) -> list[_Group]:
    points = [
        _Point(wavelength, file_index, point_index)
        for file_index, spectrum in enumerate(spectra)
        for point_index, wavelength in enumerate(spectrum.wavelengths)
    ]
    points.sort(key=lambda item: item.wavelength)
    groups: list[_Group] = []
    current: _Group | None = None

    for point in points:
        if current is None or point.wavelength - current.points[0].wavelength > tolerance:
            current = _Group([point])
            groups.append(current)
        else:
            current.points.append(point)

    for group in groups:
        seen_files: set[int] = set()
        for point in group.points:
            if point.file_index in seen_files:
                spectrum = spectra[point.file_index]
                wavelengths = sorted(
                    item.wavelength
                    for item in group.points
                    if item.file_index == point.file_index
                )
                raise DuplicateWavelengthError(
                    f"文件「{spectrum.name}」中存在重复波长："
                    + "、".join(f"{value:g}" for value in wavelengths)
                )
            seen_files.add(point.file_index)
    return groups


def _representative(group: _Group, spectra: Sequence[Spectrum]) -> _Point:
    return min(group.points, key=lambda item: (item.file_index, item.point_index))


def merge_exact_union(
    spectra: Iterable[Spectrum],
    channels: Sequence[str] = DEFAULT_CHANNELS,
    tolerance: float = DEFAULT_TOLERANCE,
) -> MergeResult:
    """Merge spectra side by side without interpolation.

    Wavelengths within ``tolerance`` form one row. A missing measurement is
    emitted as an empty cell. The output wavelength order is descending.
    """
    selected = list(spectra)
    if not selected:
        raise SpectrumError("没有参与合并的文件")

    selected_channels: list[str] = []
    for channel in channels:
        if channel not in DEFAULT_CHANNELS:
            raise SpectrumError(f"未知通道：{channel}")
        if channel not in selected_channels:
            selected_channels.append(channel)
    if not selected_channels:
        raise SpectrumError("至少选择一个通道")
    if tolerance < 0 or not math.isfinite(tolerance):
        raise SpectrumError("波长容差必须是非负有限数")

    groups = _build_exact_union(selected, tolerance)
    groups.sort(key=lambda group: group.points[0].wavelength, reverse=True)

    header = ["Wavelength (nm)"]
    for file_index in range(1, len(selected) + 1):
        header.extend(f"{channel}{file_index}" for channel in selected_channels)
    g_columns = int("CD" in selected_channels and "Abs" in selected_channels)
    if g_columns:
        header.extend(f"G{index}" for index in range(1, len(selected) + 1))

    rows: list[tuple[str, ...]] = []
    missing_values = 0
    for group in groups:
        representative = _representative(group, selected)
        row = [selected[representative.file_index].wavelength_text[representative.point_index]]
        point_index_by_file = {
            point.file_index: point.point_index for point in group.points
        }
        for file_index, spectrum in enumerate(selected):
            for channel in selected_channels:
                channel_values = spectrum.channels.get(channel)
                if channel_values is None:
                    cell = ""
                else:
                    point_index = point_index_by_file.get(file_index)
                    cell = "" if point_index is None else channel_values[point_index]
                if cell == "":
                    missing_values += 1
                row.append(cell)
        if g_columns:
            row.extend("" for _ in range(len(selected)))
        rows.append(tuple(row))

    return MergeResult(
        header=tuple(header),
        rows=tuple(rows),
        missing_values=missing_values,
        participating_files=len(selected),
        g_columns=(len(selected) if g_columns else 0),
    )
