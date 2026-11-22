from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "dist" / "SignalWeave"
RELEASE = ROOT / "release"
PACKAGE_NAME = "SignalWeave Win11 x64"
PACKAGE_DIR = RELEASE / PACKAGE_NAME
ZIP_PATH = RELEASE / f"{PACKAGE_NAME}.zip"
REPORT_PATH = RELEASE / "portable-build-report.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_files() -> list[Path]:
    if not (SOURCE / "SignalWeave.exe").is_file():
        raise RuntimeError(f"缺少构建产物：{SOURCE / 'SignalWeave.exe'}")
    if not (SOURCE / "_internal").is_dir():
        raise RuntimeError("打包产物缺少 _internal 目录")

    RELEASE.mkdir(parents=True, exist_ok=True)
    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    shutil.copytree(SOURCE, PACKAGE_DIR)
    shutil.copy2(ROOT / "PORTABLE_README.txt", PACKAGE_DIR / "使用说明.txt")
    shutil.copy2(ROOT / "README.md", PACKAGE_DIR / "项目说明.md")
    certificate = ROOT / "signing" / "SignalWeave.cer"
    if certificate.is_file():
        (PACKAGE_DIR / "signing").mkdir(exist_ok=True)
        shutil.copy2(certificate, PACKAGE_DIR / "signing" / certificate.name)

    launcher = PACKAGE_DIR / "启动 SignalWeave.bat"
    launcher.write_text(
        '@echo off\r\n'
        'setlocal\r\n'
        'cd /d "%~dp0"\r\n'
        'start "" "%~dp0SignalWeave.exe"\r\n'
        'exit /b 0\r\n',
        encoding="gb18030",
        newline="",
    )

    with zipfile.ZipFile(
        ZIP_PATH,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        for path in sorted(PACKAGE_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, Path(PACKAGE_NAME) / path.relative_to(PACKAGE_DIR))
    return [path for path in PACKAGE_DIR.rglob("*") if path.is_file()]


def main() -> int:
    files = write_files()
    with zipfile.ZipFile(ZIP_PATH, "r") as archive:
        members = archive.namelist()
        bad_member = archive.testzip()
    if bad_member is not None:
        raise RuntimeError(f"ZIP 校验失败：{bad_member}")

    required = {
        f"{PACKAGE_NAME}/SignalWeave.exe",
        f"{PACKAGE_NAME}/_internal/python313.dll",
        f"{PACKAGE_NAME}/_internal/PySide6/Qt6Core.dll",
        f"{PACKAGE_NAME}/_internal/PySide6/QtCore.pyd",
        f"{PACKAGE_NAME}/_internal/PySide6/plugins/platforms/qwindows.dll",
    }
    missing = sorted(required.difference(members))
    if missing:
        raise RuntimeError(f"便携包缺少关键文件：{missing}")

    report = {
        "ok": True,
        "target": "Windows 11 x64",
        "folder": str(PACKAGE_DIR),
        "zip": str(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha256(ZIP_PATH),
        "exe_sha256": sha256(PACKAGE_DIR / "SignalWeave.exe"),
        "file_count": len(files),
        "zip_member_count": len(members),
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
