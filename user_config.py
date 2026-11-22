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


@dataclass(frozen=True)
class UserConfig:
    cd_merge_channels: tuple[str, ...] = CD_MERGE_DEFAULT
    cd_preview_channels: tuple[str, ...] = CD_PREVIEW_DEFAULT
    electrochem_merge_channels: tuple[str, ...] | None = None
    electrochem_preview_channels: tuple[str, ...] | None = None


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
