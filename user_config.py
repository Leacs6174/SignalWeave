"""Persistent channel preferences for merging and scatter previews."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

CD_MERGE_DEFAULT = ("CD", "HT", "Abs")
CD_PREVIEW_DEFAULT = ("CD", "G")
DEFAULT_SERIES_COLORS = (
    "#2563eb",
    "#0f9f81",
    "#e47524",
    "#d9467a",
    "#7c5ce5",
    "#0891b2",
    "#65a30d",
    "#b7791f",
)
DEFAULT_FONT_FAMILY = "Microsoft YaHei UI"
DEFAULT_FONT_SIZE = 10
DEFAULT_MARKER_SIZE = 1.8


@dataclass(frozen=True)
class UserConfig:
    cd_merge_channels: tuple[str, ...] = CD_MERGE_DEFAULT
    cd_preview_channels: tuple[str, ...] = CD_PREVIEW_DEFAULT
    electrochem_merge_channels: tuple[str, ...] | None = None
    electrochem_preview_channels: tuple[str, ...] | None = None
    theme_mode: str = "light"
    font_family: str = DEFAULT_FONT_FAMILY
    font_size: int = DEFAULT_FONT_SIZE
    render_mode: str = "line"
    marker_size: float = DEFAULT_MARKER_SIZE
    series_colors: tuple[str, ...] = DEFAULT_SERIES_COLORS


def _clean_channels(value: object) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    return tuple(
        dict.fromkeys(
            item.strip()
            for item in value
            if isinstance(item, str) and item.strip()
        )
    )


def load_user_config(path: str | Path) -> UserConfig:
    source = Path(path)
    if not source.is_file():
        return UserConfig()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return UserConfig()
    if not isinstance(payload, dict):
        return UserConfig()
    cd_merge = _clean_channels(payload.get("cd_merge_channels"))
    cd_preview = _clean_channels(payload.get("cd_preview_channels"))
    theme_mode = payload.get("theme_mode")
    if theme_mode not in {"light", "dark"}:
        theme_mode = "light"
    render_mode = payload.get("render_mode")
    if render_mode not in {"line", "scatter"}:
        render_mode = "line"
    font_family = payload.get("font_family")
    if not isinstance(font_family, str) or not font_family.strip():
        font_family = DEFAULT_FONT_FAMILY
    try:
        font_size = int(payload.get("font_size", DEFAULT_FONT_SIZE))
    except (TypeError, ValueError):
        font_size = DEFAULT_FONT_SIZE
    font_size = min(22, max(8, font_size))
    try:
        marker_size = float(payload.get("marker_size", DEFAULT_MARKER_SIZE))
    except (TypeError, ValueError):
        marker_size = DEFAULT_MARKER_SIZE
    marker_size = min(8.0, max(1.0, marker_size))
    raw_colors = payload.get("series_colors")
    series_colors = (
        tuple(
            color.upper()
            for color in raw_colors
            if isinstance(color, str)
            and len(color) == 7
            and color.startswith("#")
            and all(char in "0123456789abcdefABCDEF" for char in color[1:])
        )
        if isinstance(raw_colors, list)
        else DEFAULT_SERIES_COLORS
    )
    if not series_colors:
        series_colors = DEFAULT_SERIES_COLORS
    return UserConfig(
        cd_merge_channels=(
            CD_MERGE_DEFAULT if cd_merge is None else cd_merge
        ),
        cd_preview_channels=(
            CD_PREVIEW_DEFAULT if cd_preview is None else cd_preview
        ),
        electrochem_merge_channels=_clean_channels(
            payload.get("electrochem_merge_channels")
        ),
        electrochem_preview_channels=_clean_channels(
            payload.get("electrochem_preview_channels")
        ),
        theme_mode=theme_mode,
        font_family=font_family,
        font_size=font_size,
        render_mode=render_mode,
        marker_size=marker_size,
        series_colors=series_colors,
    )


def save_user_config(path: str | Path, config: UserConfig) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": "DataMergerUserConfig",
        "version": 1,
        "cd_merge_channels": list(config.cd_merge_channels),
        "cd_preview_channels": list(config.cd_preview_channels),
        "electrochem_merge_channels": (
            None
            if config.electrochem_merge_channels is None
            else list(config.electrochem_merge_channels)
        ),
        "electrochem_preview_channels": (
            None
            if config.electrochem_preview_channels is None
            else list(config.electrochem_preview_channels)
        ),
        "theme_mode": config.theme_mode,
        "font_family": config.font_family,
        "font_size": config.font_size,
        "render_mode": config.render_mode,
        "marker_size": config.marker_size,
        "series_colors": list(config.series_colors),
    }
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def selected_channels(
    available: Iterable[str],
    configured: tuple[str, ...] | None,
    *,
    default_all: bool,
) -> tuple[str, ...]:
    names = tuple(available)
    if configured is None:
        return names if default_all else ()
    configured_set = set(configured)
    return tuple(name for name in names if name in configured_set)


def with_channels(
    config: UserConfig,
    field_name: str,
    channels: Iterable[str] | None,
) -> UserConfig:
    value = None if channels is None else tuple(dict.fromkeys(channels))
    return replace(config, **{field_name: value})
