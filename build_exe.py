from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    for module in ("PyInstaller", "PySide6"):
        if importlib.util.find_spec(module) is None:
            print(
                f"缺少 {module}。请先运行："
                "python -m pip install -r requirements-build.txt",
                file=sys.stderr,
            )
            return 1

    cache = ROOT / ".pyinstaller-cache"
    temp = ROOT / ".build-temp"
    cache.mkdir(exist_ok=True)
    temp.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["PYINSTALLER_CONFIG_DIR"] = str(cache)
    env["TEMP"] = str(temp)
    env["TMP"] = str(temp)
    # The Codex host injects Poppler's ICU 78 into PATH. Qt 6.12 imports the
    # unversioned Windows ICU 72 ABI, so collecting ICU 78 breaks PySide6.
    env["PATH"] = os.pathsep.join(
        part
        for part in env.get("PATH", "").split(os.pathsep)
        if "OpenAI.CodexPrimaryRuntime" not in part
    )

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "SignalWeave",
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(ROOT / "build"),
        "--specpath",
        str(ROOT),
        str(ROOT / "app.py"),
    ]
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    exe = ROOT / "dist" / "SignalWeave" / "SignalWeave.exe"
    print(f"\n构建完成：{exe}")
    print(f"EXE 存在：{exe.is_file()}")
    return 0 if exe.is_file() else 2


if __name__ == "__main__":
    raise SystemExit(main())
