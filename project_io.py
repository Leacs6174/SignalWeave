"""Small JSON project and recent-project persistence helpers."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

PROJECT_VERSION = 1
PROJECT_EXTENSION = ".dmproj"
VALID_DATA_TYPES = {"cd", "electrochem"}


class ProjectError(ValueError):
    """A user-facing project-file error."""


@dataclass(frozen=True)
class ProjectFile:
    path: str
    enabled: bool = True


@dataclass(frozen=True)
class ProjectDocument:
    data_type: str
    files: tuple[ProjectFile, ...]


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def save_project(
    path: str | Path,
    data_type: str,
    files: list[ProjectFile],
) -> Path:
    target = Path(path)
    if target.suffix.lower() != PROJECT_EXTENSION:
        target = target.with_suffix(PROJECT_EXTENSION)
    if data_type not in VALID_DATA_TYPES:
        raise ProjectError(f"未知数据类型：{data_type}")
    payload = {
        "format": "DataMergerProject",
        "version": PROJECT_VERSION,
        "data_type": data_type,
        "files": [
            {
                "path": str(Path(item.path).resolve(strict=False)),
                "enabled": bool(item.enabled),
            }
            for item in files
        ],
    }
    _write_json_atomic(target, payload)
    return target


def load_project(path: str | Path) -> ProjectDocument:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProjectError(f"无法读取工程文件：{exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProjectError("工程文件不是有效的 DataMerger JSON") from exc
    if payload.get("format") != "DataMergerProject":
        raise ProjectError("不是 DataMerger 工程文件")
    if payload.get("version") != PROJECT_VERSION:
        raise ProjectError("工程文件版本不受支持")
    data_type = payload.get("data_type")
    if data_type not in VALID_DATA_TYPES:
        raise ProjectError("工程文件中的数据类型无效")
    raw_files = payload.get("files")
    if not isinstance(raw_files, list):
        raise ProjectError("工程文件缺少文件列表")

    files: list[ProjectFile] = []
    for item in raw_files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ProjectError("工程文件中的路径记录无效")
        files.append(
            ProjectFile(
                path=item["path"],
                enabled=bool(item.get("enabled", True)),
            )
        )
    return ProjectDocument(data_type=data_type, files=tuple(files))


def load_recent_projects(path: str | Path) -> list[str]:
    source = Path(path)
    if not source.is_file():
        return []
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    projects = payload.get("projects", [])
    if not isinstance(projects, list):
        return []
    return [item for item in projects if isinstance(item, str)]


def record_recent_project(
    config_path: str | Path,
    project_path: str | Path,
    limit: int = 8,
) -> list[str]:
    """Append a new project without changing the order of existing tabs."""
    config = Path(config_path)
    normalized = str(Path(project_path).resolve(strict=False))
    projects = load_recent_projects(config)
    if not any(
        os.path.normcase(item) == os.path.normcase(normalized)
        for item in projects
    ):
        projects.append(normalized)
    projects = projects[:limit]
    _write_json_atomic(config, {"projects": projects})
    return projects


def save_recent_project_order(
    config_path: str | Path,
    projects: list[str],
) -> list[str]:
    config = Path(config_path)
    ordered = list(
        dict.fromkeys(
            str(Path(item).resolve(strict=False))
            for item in projects
            if item
        )
    )
    _write_json_atomic(config, {"projects": ordered})
    return ordered
