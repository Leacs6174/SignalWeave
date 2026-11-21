"""DataMerger application entry point."""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

STARTED_AT = time.perf_counter()
TRACE_PATH: Path | None = None


def _trace(message: str) -> None:
    if TRACE_PATH is None:
        return
    try:
        with TRACE_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"+{time.perf_counter() - STARTED_AT:.3f}s {message}\n")
    except OSError:
        pass


if "--smoke-test" in sys.argv:
    index = sys.argv.index("--smoke-test")
    if index + 1 < len(sys.argv):
        TRACE_PATH = Path(sys.argv[index + 1]).with_suffix(".trace.log")
        TRACE_PATH.write_text("", encoding="utf-8")
        _trace("module start")

_trace("before PySide6 import")
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui_main import APP_STYLE, MainWindow, _application_dir, _font  # noqa: E402

_trace("after all imports")


def _exception_hook(exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
    path = _application_dir() / "DataMerger-error.log"
    try:
        path.write_text(
            "".join(traceback.format_exception(exc_type, exc, tb)),
            encoding="utf-8",
        )
    except OSError:
        pass
    sys.__excepthook__(exc_type, exc, tb)


def _run_smoke_test(arguments: list[str], report_path: Path) -> int:
    _trace("smoke entered")
    data_type = "cd"
    paths: list[str] = []
    for argument in arguments:
        if argument.startswith("--type="):
            data_type = argument.split("=", 1)[1]
        else:
            paths.append(argument)
    if data_type not in {"cd", "electrochem"}:
        data_type = "cd"

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication(sys.argv[:1])
    _trace("QApplication created")
    app.setApplicationName("DataMerger")
    app.setOrganizationName("DataMerger")
    app.setStyle("Fusion")
    app.setFont(_font(10))
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    _trace("MainWindow created")
    report: dict[str, object] = {"ok": False}
    try:
        window._apply_data_type(data_type)
        window._add_paths(paths)
        _trace("paths added")
        window._recompute_merge()
        app.processEvents()
        _trace("merge computed")
        result = window.result
        if result is None:
            raise RuntimeError("没有生成合并结果")
        window._copy_result()
        clipboard_data_ok = QGuiApplication.clipboard().text() == result.text
        formula_ok: bool | None = None
        if data_type == "cd":
            window._copy_formulas()
            formula = getattr(result, "formula_text", "")
            formula_ok = QGuiApplication.clipboard().text() == formula
        _trace("clipboard verified")
        report = {
            "ok": clipboard_data_ok and formula_ok is not False,
            "data_type": data_type,
            "rows": result.row_count,
            "columns": result.column_count,
            "missing_values": result.missing_values,
            "participating_files": result.participating_files,
            "clipboard_data_ok": clipboard_data_ok,
            "preview_chars": len(window.preview.toPlainText()),
            "ready_seconds": round(time.perf_counter() - STARTED_AT, 3),
        }
        if data_type == "cd":
            report["clipboard_formula_ok"] = formula_ok
        else:
            report["formula_test"] = "not_applicable"
        return 0 if report["ok"] else 4
    except Exception as exc:
        report = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "ready_seconds": round(time.perf_counter() - STARTED_AT, 3),
        }
        return 1
    finally:
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _trace("report written")
        window._dirty = False
        window.close()
        window.deleteLater()
        app.processEvents()
        _trace("window closed")


def main() -> int:
    _trace("main entered")
    if "--smoke-test" in sys.argv:
        index = sys.argv.index("--smoke-test")
        following = sys.argv[index + 1 :]
        report_path = Path(following[0]) if following else Path("smoke-result.json")
        return _run_smoke_test(following[1:], report_path)

    sys.excepthook = _exception_hook
    app = QApplication(sys.argv)
    app.setApplicationName("DataMerger")
    app.setOrganizationName("DataMerger")
    app.setStyle("Fusion")
    app.setFont(_font(10))
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
