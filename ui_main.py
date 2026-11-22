"""Qt user interface for DataMerger."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QSignalBlocker, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QGuiApplication,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabBar,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from electrochem_core import (
    ElectrochemError,
    ElectrochemMergeResult,
    ElectrochemSignal,
    merge_electrochem,
    read_electrochem,
)
from project_io import (
    PROJECT_EXTENSION,
    ProjectError,
    ProjectFile,
    load_project,
    load_recent_projects,
    record_recent_project,
    save_project,
)
from plot_data import cd_plot_graphs, electrochem_plot_graphs
from plot_widget import PlotPreviewWidget
from spectrum_core import (
    MergeResult,
    Spectrum,
    SpectrumError,
    merge_exact_union,
    read_spectrum,
)
from theme import enforce_design_invariants, font as _font
from user_config import (
    CD_MERGE_DEFAULT,
    CD_PREVIEW_DEFAULT,
    UserConfig,
    load_user_config,
    save_user_config,
    selected_channels,
    with_channels,
)

DATA_TYPE_NAMES = {"cd": "CD 光谱", "electrochem": "电化学"}
WINDOW_SIZE = (1240, 820)
WINDOW_MIN_SIZE = (980, 650)


@dataclass
class FileEntry:
    path: Path
    dataset: Spectrum | ElectrochemSignal | None
    enabled: bool = True
    error: str = ""


def _application_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _icon(name: str, color: str = "#334155", size: int = 18) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if name == "add":
        painter.drawRoundedRect(3, 2, 10, 14, 1.5, 1.5)
        painter.drawLine(10, 1, 14, 5)
        painter.drawLine(10, 1, 10, 5)
        painter.drawLine(10, 5, 14, 5)
        painter.drawLine(15, 10, 15, 16)
        painter.drawLine(12, 13, 18, 13)
    elif name == "copy":
        painter.drawRoundedRect(2, 5, 9, 10, 1.5, 1.5)
        painter.drawRoundedRect(6, 2, 9, 10, 1.5, 1.5)
    elif name == "up":
        painter.drawLine(9, 15, 9, 4)
        painter.drawLine(4, 9, 9, 4)
        painter.drawLine(14, 9, 9, 4)
    elif name == "down":
        painter.drawLine(9, 3, 9, 14)
        painter.drawLine(4, 9, 9, 14)
        painter.drawLine(14, 9, 9, 14)
    elif name == "trash":
        painter.drawRoundedRect(4, 6, 10, 10, 1.5, 1.5)
        painter.drawLine(2, 5, 16, 5)
        painter.drawLine(7, 2, 11, 2)
        painter.drawLine(7, 8, 7, 13)
        painter.drawLine(11, 8, 11, 13)
    elif name == "file":
        painter.drawRoundedRect(3, 2, 12, 15, 1.5, 1.5)
        painter.drawLine(8, 1, 15, 8)
        painter.drawLine(8, 1, 8, 8)
        painter.drawLine(8, 8, 15, 8)
    painter.end()
    return QIcon(pixmap)


class DropZone(QFrame):
    filesDropped = Signal(list)
    chooseRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(108)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 16, 14)
        layout.setSpacing(16)
        icon_badge = QLabel()
        icon_badge.setObjectName("dropIcon")
        icon_badge.setFixedSize(52, 52)
        icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_badge.setPixmap(_icon("file", "#2563eb", 27).pixmap(27, 27))
        layout.addWidget(icon_badge)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)
        self.title = QLabel()
        self.title.setObjectName("dropTitle")
        self.hint = QLabel()
        self.hint.setObjectName("muted")
        text_layout.addWidget(self.title)
        text_layout.addWidget(self.hint)
        layout.addLayout(text_layout, 1)
        self.choose_button = QPushButton(" 选择文件")
        self.choose_button.setObjectName("outlineButton")
        self.choose_button.setIcon(_icon("add", "#2563eb", 16))
        self.choose_button.setIconSize(QSize(16, 16))
        self.choose_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.choose_button.clicked.connect(self.chooseRequested)
        layout.addWidget(self.choose_button)
        self.set_mode("cd")

    def set_mode(self, data_type: str) -> None:
        if data_type == "electrochem":
            self.title.setText("拖入 CHI 电化学原始 TXT")
            self.hint.setText("自动识别电位、时间等横坐标；BIN 与其他文件会被忽略")
        else:
            self.title.setText("拖入 JASCO 原始 TXT")
            self.hint.setText("只接收包含 XYDATA 的光谱 .txt；可一次添加多个")

    def set_hot(self, hot: bool) -> None:
        self.setProperty("hot", hot)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def dragEnterEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.set_hot(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.set_hot(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.set_hot(False)
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.entries: list[FileEntry] = []
        self.result: MergeResult | ElectrochemMergeResult | None = None
        self.data_type = "cd"
        self.project_path: Path | None = None
        self._dirty = False
        self._refreshing_table = False
        self._refreshing_recent = False
        self.merge_channel_checks: dict[str, QCheckBox] = {}
        self.preview_channel_checks: dict[str, QCheckBox] = {}
        self.recent_config = _application_dir() / "DataMerger-recent.json"
        self.config_path = _application_dir() / "DataMerger-config.json"
        self.user_config = load_user_config(self.config_path)
        self._merge_timer = QTimer(self)
        self._merge_timer.setSingleShot(True)
        self._merge_timer.setInterval(25)
        self._merge_timer.timeout.connect(self._recompute_merge)

        self.resize(*WINDOW_SIZE)
        self.setMinimumSize(*WINDOW_MIN_SIZE)
        self.setAcceptDrops(True)
        self._build_toolbar()
        self._build_ui()
        enforce_design_invariants(self)
        self._install_shortcuts()
        self._apply_data_type("cd")
        self._refresh_recent_projects()
        self._update_window_title()
        self._recompute_merge()

    def _build_toolbar(self) -> None:
        self.toolbar = QToolBar("主工具栏", self)
        self.toolbar.setObjectName("mainToolbar")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

        self.new_action = QAction("新建工程", self)
        self.open_project_action = QAction("打开工程", self)
        self.save_action = QAction("保存工程", self)
        self.save_as_action = QAction("工程另存为", self)
        self.close_project_action = QAction("关闭工程", self)
        self.add_files_action = QAction(_icon("add", "#2563eb"), "添加数据", self)
        self.copy_action = QAction(_icon("copy", "#334155"), "复制结果", self)
        self.new_action.triggered.connect(self._new_project)
        self.open_project_action.triggered.connect(self._open_project_dialog)
        self.save_action.triggered.connect(self._save_project)
        self.save_as_action.triggered.connect(self._save_project_as)
        self.close_project_action.triggered.connect(self._close_project)
        self.add_files_action.triggered.connect(self._choose_files)
        self.copy_action.triggered.connect(self._copy_result)

        self.file_button = QToolButton()
        self.file_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.file_button.setText("文件")
        self.file_menu = QMenu(self.file_button)
        self.file_menu.setObjectName("fileMenu")
        self.file_menu.setFont(_font(10))
        for action in (
            self.new_action,
            self.open_project_action,
            self.save_action,
            self.save_as_action,
            self.close_project_action,
        ):
            self.file_menu.addAction(action)
        self.file_button.setMenu(self.file_menu)
        self.toolbar.addWidget(self.file_button)

        self.type_button = QToolButton()
        self.type_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.type_menu = QMenu(self.type_button)
        self.type_menu.setObjectName("typeMenu")
        self.type_menu.setFont(_font(10))
        self.cd_action = QAction("CD 光谱", self)
        self.electrochem_action = QAction("电化学", self)
        self.cd_action.setCheckable(True)
        self.electrochem_action.setCheckable(True)
        self.cd_action.triggered.connect(lambda: self._request_data_type("cd"))
        self.electrochem_action.triggered.connect(
            lambda: self._request_data_type("electrochem")
        )
        self.type_menu.addAction(self.cd_action)
        self.type_menu.addAction(self.electrochem_action)
        self.type_button.setMenu(self.type_menu)
        self.toolbar.addWidget(self.type_button)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.add_files_action)
        self.toolbar.addAction(self.copy_action)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.toolbar.addWidget(spacer)

        recent_host = QWidget()
        recent_host.setObjectName("recentHost")
        recent_layout = QHBoxLayout(recent_host)
        recent_layout.setContentsMargins(14, 5, 18, 5)
        recent_layout.setSpacing(9)
        recent_label = QLabel("最近工程")
        recent_label.setObjectName("recentLabel")
        self.recent_tabs = QTabBar()
        self.recent_tabs.setObjectName("recentTabs")
        self.recent_tabs.setDocumentMode(True)
        self.recent_tabs.setExpanding(False)
        self.recent_tabs.setMovable(False)
        self.recent_tabs.setTabsClosable(False)
        self.recent_tabs.setUsesScrollButtons(True)
        self.recent_tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.recent_tabs.currentChanged.connect(
            self._recent_project_selected
        )
        recent_layout.addWidget(recent_label)
        recent_layout.addWidget(self.recent_tabs, 1)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._wrap_recent_bar(recent_host))

    def _wrap_recent_bar(self, host: QWidget) -> QToolBar:
        bar = QToolBar("最近工程", self)
        bar.setObjectName("recentToolbar")
        bar.setMovable(False)
        bar.setFloatable(False)
        bar.addWidget(host)
        return bar

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(22, 16, 22, 18)
        outer.setSpacing(13)

        header = QHBoxLayout()
        header.setSpacing(12)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title = QLabel("DataMerger")
        title.setObjectName("title")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("muted")
        title_box.addWidget(title)
        title_box.addWidget(self.subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        outer.addLayout(header)

        self.drop_zone = DropZone()
        self.drop_zone.chooseRequested.connect(self._choose_files)
        self.drop_zone.filesDropped.connect(self._add_paths)
        outer.addWidget(self.drop_zone)

        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter.setObjectName("mainSplitter")
        self.content_splitter.setChildrenCollapsible(False)
        outer.addWidget(self.content_splitter, 1)
        self.left_splitter = QSplitter(Qt.Orientation.Vertical)
        self.left_splitter.setObjectName("leftSplitter")
        self.left_splitter.setChildrenCollapsible(False)
        self.content_splitter.addWidget(self.left_splitter)

        files_card = QFrame()
        files_card.setObjectName("card")
        files_card.setMinimumWidth(450)
        files_layout = QVBoxLayout(files_card)
        files_layout.setContentsMargins(16, 15, 16, 14)
        files_layout.setSpacing(9)
        files_head = QHBoxLayout()
        files_title = QLabel("文件与列顺序")
        files_title.setObjectName("sectionTitle")
        files_head.addWidget(files_title)
        files_head.addStretch(1)
        self.count_badge = QLabel("0 个文件")
        self.count_badge.setObjectName("smallBadge")
        files_head.addWidget(self.count_badge)
        files_layout.addLayout(files_head)
        self.files_hint = QLabel()
        self.files_hint.setObjectName("muted")
        files_layout.addWidget(self.files_hint)

        self.file_table = QTableWidget(0, 5)
        self.file_table.setObjectName("fileTable")
        self.file_table.setHorizontalHeaderLabels(
            ["", "#", "文件", "点数", "横坐标范围"]
        )
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.file_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.file_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.file_table.setShowGrid(False)
        self.file_table.setAcceptDrops(False)
        table_header = self.file_table.horizontalHeader()
        table_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        table_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        table_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.file_table.setColumnWidth(0, 36)
        self.file_table.setColumnWidth(1, 34)
        self.file_table.setColumnWidth(3, 64)
        self.file_table.setColumnWidth(4, 150)
        self.file_table.verticalHeader().setDefaultSectionSize(34)
        self.file_table.itemChanged.connect(self._file_item_changed)
        files_layout.addWidget(self.file_table, 1)

        file_actions = QHBoxLayout()
        file_actions.setSpacing(6)
        self.up_button = self._small_button("上移", "up")
        self.down_button = self._small_button("下移", "down")
        self.remove_button = self._small_button("移除", "trash")
        self.clear_button = self._small_button("清空")
        self.up_button.clicked.connect(lambda: self._move_selected(-1))
        self.down_button.clicked.connect(lambda: self._move_selected(1))
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button.clicked.connect(self._clear_files)
        file_actions.addWidget(self.up_button)
        file_actions.addWidget(self.down_button)
        file_actions.addWidget(self.remove_button)
        file_actions.addStretch(1)
        file_actions.addWidget(self.clear_button)
        files_layout.addLayout(file_actions)
        self.left_splitter.addWidget(files_card)

        self.channel_card = QFrame()
        self.channel_card.setObjectName("card")
        channel_layout = QVBoxLayout(self.channel_card)
        channel_layout.setContentsMargins(16, 13, 16, 13)
        channel_layout.setSpacing(6)
        channel_title = QLabel("通道设置")
        channel_title.setObjectName("sectionTitle")
        channel_layout.addWidget(channel_title)
        merge_label = QLabel("合并 / 导出")
        merge_label.setObjectName("muted")
        channel_layout.addWidget(merge_label)
        self.merge_channels_row = QHBoxLayout()
        self.merge_channels_row.setSpacing(7)
        channel_layout.addLayout(self.merge_channels_row)
        preview_label = QLabel("散点预览")
        preview_label.setObjectName("muted")
        channel_layout.addWidget(preview_label)
        self.preview_channels_row = QHBoxLayout()
        self.preview_channels_row.setSpacing(7)
        channel_layout.addLayout(self.preview_channels_row)
        config_hint = QLabel("通道勾选会自动保存到用户配置")
        config_hint.setObjectName("muted")
        channel_layout.addWidget(config_hint)
        self.left_splitter.addWidget(self.channel_card)
        self.left_splitter.setStretchFactor(0, 1)
        self.left_splitter.setSizes([430, 190])

        result_card = QFrame()
        result_card.setObjectName("card")
        self.content_splitter.addWidget(result_card)
        self.content_splitter.setStretchFactor(0, 0)
        self.content_splitter.setStretchFactor(1, 1)
        self.content_splitter.setSizes([470, 720])
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(18, 15, 18, 16)
        result_layout.setSpacing(10)
        result_head = QHBoxLayout()
        result_title = QLabel("合并结果")
        result_title.setObjectName("sectionTitle")
        result_head.addWidget(result_title)
        result_head.addStretch(1)
        self.row_badge = self._pill("0 行")
        self.column_badge = self._pill("0 列")
        self.missing_badge = self._pill("缺失 0")
        for badge in (self.row_badge, self.column_badge, self.missing_badge):
            result_head.addWidget(badge)
        result_layout.addLayout(result_head)
        self.result_hint = QLabel()
        self.result_hint.setObjectName("muted")
        result_layout.addWidget(self.result_hint)

        self.preview_tabs = QTabWidget()
        self.preview_tabs.setObjectName("previewTabs")
        self.preview_tabs.setDocumentMode(True)
        self.plot_preview = PlotPreviewWidget()
        self.preview_tabs.addTab(self.plot_preview, "数据散点")
        self.preview = QPlainTextEdit()
        self.preview.setObjectName("preview")
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.preview.setAcceptDrops(False)
        preview_font = QFont("Consolas", 9)
        if "Consolas" not in QFontDatabase.families():
            preview_font = QFontDatabase.systemFont(
                QFontDatabase.SystemFont.FixedFont
            )
        self.preview.setFont(preview_font)
        self.preview.setTabStopDistance(
            QFontMetrics(preview_font).horizontalAdvance(" ") * 8
        )
        self.preview_tabs.addTab(self.preview, "合并数据")
        result_layout.addWidget(self.preview_tabs, 1)
        self.error_label = QLabel()
        self.error_label.setObjectName("error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        result_layout.addWidget(self.error_label)

        footer = QHBoxLayout()
        self.save_check = QCheckBox("复制后同时另存为 TXT")
        self.save_check.setObjectName("plainCheck")
        footer.addWidget(self.save_check)
        footer.addStretch(1)
        self.status_label = QLabel("等待添加文件")
        self.status_label.setObjectName("status")
        footer.addWidget(self.status_label)
        self.formula_button = QPushButton("复制 G 公式")
        self.formula_button.setObjectName("smallButton")
        self.formula_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.formula_button.clicked.connect(self._copy_formulas)
        footer.addWidget(self.formula_button)
        self.copy_button = QPushButton(" 复制全部结果")
        self.copy_button.setObjectName("primaryButton")
        self.copy_button.setIcon(_icon("copy", "#ffffff", 17))
        self.copy_button.setIconSize(QSize(17, 17))
        self.copy_button.setMinimumWidth(152)
        self.copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_button.clicked.connect(self._copy_result)
        footer.addWidget(self.copy_button)
        result_layout.addLayout(footer)

    def _pill(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("pill")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _small_button(self, text: str, icon: str | None = None) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("smallButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon:
            button.setIcon(_icon(icon, "#64748b", 15))
            button.setIconSize(QSize(15, 15))
        return button

    def _install_shortcuts(self) -> None:
        shortcuts = (
            (self.new_action, "Ctrl+N"),
            (self.open_project_action, "Ctrl+O"),
            (self.save_action, "Ctrl+S"),
            (self.save_as_action, "Ctrl+Shift+S"),
            (self.close_project_action, "Ctrl+W"),
            (self.add_files_action, "Ctrl+Shift+O"),
            (self.copy_action, "Ctrl+Shift+C"),
        )
        for action, shortcut in shortcuts:
            action.setShortcut(shortcut)
            self.addAction(action)

    def _apply_data_type(self, data_type: str) -> None:
        self.data_type = data_type
        self.cd_action.setChecked(data_type == "cd")
        self.electrochem_action.setChecked(data_type == "electrochem")
        display = DATA_TYPE_NAMES[data_type]
        self.type_button.setText(f"数据类型：{display}")
        self.subtitle.setText(
            "JASCO 光谱 → 精确并集 → Origin 宽表"
            if data_type == "cd"
            else "CHI 电化学 → 自动识别横坐标 → 精确并集"
        )
        self.drop_zone.set_mode(data_type)
        self.formula_button.setVisible(data_type == "cd")
        self.files_hint.setText(
            "勾选的文件参与合并；第一份对应 CD1 / HT1 / Abs1"
            if data_type == "cd"
            else "勾选同一种横坐标的文件；各文件的数据列按顺序排列"
        )
        self.result_hint.setText(
            "按波长降序；未测量位置留空，不插值、不补点"
            if data_type == "cd"
            else "按横坐标升序；重复电位按出现次序对齐，不插值、不补点"
        )
        self._refresh_table()
        self._schedule_merge()
        self._update_window_title()

    def _request_data_type(self, data_type: str) -> None:
        if data_type == self.data_type:
            self._apply_data_type(data_type)
            return
        if self.entries and not self._confirm_discard():
            self.cd_action.setChecked(self.data_type == "cd")
            self.electrochem_action.setChecked(self.data_type == "electrochem")
            return
        self.entries.clear()
        self.project_path = None
        self._dirty = False
        self._apply_data_type(data_type)
        self._refresh_recent_projects()

    def _available_channels(self, role: str = "merge") -> tuple[str, ...]:
        if self.data_type == "cd":
            return (
                CD_MERGE_DEFAULT
                if role == "merge"
                else tuple(dict.fromkeys((*CD_MERGE_DEFAULT, "G")))
            )
        available: list[str] = []
        for entry in self.entries:
            if isinstance(entry.dataset, ElectrochemSignal):
                available.extend(entry.dataset.channel_names)
        return tuple(dict.fromkeys(available))

    def _selected_channel_names(self, role: str) -> tuple[str, ...]:
        available = self._available_channels(role)
        if self.data_type == "cd":
            configured = (
                self.user_config.cd_merge_channels
                if role == "merge"
                else self.user_config.cd_preview_channels
            )
            configured_set = set(configured)
            return tuple(name for name in available if name in configured_set)
        configured = (
            self.user_config.electrochem_merge_channels
            if role == "merge"
            else self.user_config.electrochem_preview_channels
        )
        return selected_channels(available, configured, default_all=True)

    def _clear_layout(self, layout: QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _sync_channel_controls(self) -> None:
        available = self._available_channels("merge")
        merge_selected = set(self._selected_channel_names("merge"))
        preview_selected = set(self._selected_channel_names("preview"))
        self.merge_channel_checks = {}
        self.preview_channel_checks = {}
        self._clear_layout(self.merge_channels_row)
        self._clear_layout(self.preview_channels_row)
        for name in available:
            check = QCheckBox(name)
            check.setObjectName("channelCheck")
            check.setChecked(name in merge_selected)
            check.toggled.connect(
                lambda checked, channel=name: self._channel_setting_changed(
                    "merge", channel, checked
                )
            )
            self.merge_channel_checks[name] = check
            self.merge_channels_row.addWidget(check)
        if not available:
            empty = QLabel("添加数据后显示")
            empty.setObjectName("muted")
            self.merge_channels_row.addWidget(empty)
        self.merge_channels_row.addStretch(1)

        preview_available = self._available_channels("preview")
        for name in preview_available:
            if self.data_type == "cd" and name == "G":
                label = "G 因子"
            else:
                label = name
            check = QCheckBox(label)
            check.setObjectName("channelCheck")
            check.setChecked(name in preview_selected)
            check.toggled.connect(
                lambda checked, channel=name: self._channel_setting_changed(
                    "preview", channel, checked
                )
            )
            self.preview_channel_checks[name] = check
            self.preview_channels_row.addWidget(check)
        if not preview_available:
            empty = QLabel("添加数据后显示")
            empty.setObjectName("muted")
            self.preview_channels_row.addWidget(empty)
        self.preview_channels_row.addStretch(1)

    def _channel_setting_changed(
        self, role: str, channel: str, checked: bool
    ) -> None:
        checks = (
            self.merge_channel_checks
            if role == "merge"
            else self.preview_channel_checks
        )
        selected = [
            name for name, check in checks.items() if check.isChecked()
        ]
        if role == "merge" and not selected:
            blocker = QSignalBlocker(checks[channel])
            checks[channel].setChecked(True)
            del blocker
            QMessageBox.information(
                self, "合并通道", "至少要保留一个合并/导出通道。"
            )
            return
        field = (
            "cd_merge_channels"
            if self.data_type == "cd" and role == "merge"
            else "cd_preview_channels"
            if self.data_type == "cd"
            else "electrochem_merge_channels"
            if role == "merge"
            else "electrochem_preview_channels"
        )
        self.user_config = with_channels(self.user_config, field, selected)
        try:
            save_user_config(self.config_path, self.user_config)
        except OSError as exc:
            self._show_error(f"无法保存用户配置：{exc}")
        if role == "merge":
            self._schedule_merge()
        else:
            self._update_plot_preview()

    def _choose_files(self) -> None:
        initial = (
            str(self.project_path.parent)
            if self.project_path is not None
            else str(_application_dir())
        )
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择原始 TXT",
            initial,
            "原始 TXT (*.txt);;所有文件 (*.*)",
        )
        if paths:
            self._add_paths(paths)

    def _read_dataset(
        self, path: Path
    ) -> Spectrum | ElectrochemSignal:
        if self.data_type == "electrochem":
            return read_electrochem(path)
        return read_spectrum(path)

    def _add_paths(self, paths: list[str]) -> None:
        known = {
            os.path.normcase(os.path.abspath(entry.path)) for entry in self.entries
        }
        errors: list[str] = []
        added = 0
        ignored = 0
        for raw_path in paths:
            source = Path(raw_path)
            if source.is_dir():
                errors.append(f"{source.name}：不支持拖入文件夹")
                continue
            if source.suffix.lower() != ".txt":
                ignored += 1
                continue
            normalized = os.path.normcase(os.path.abspath(source))
            if normalized in known:
                continue
            try:
                dataset = self._read_dataset(source)
            except (SpectrumError, ElectrochemError) as exc:
                errors.append(f"{source.name}：{exc}")
                continue
            self.entries.append(FileEntry(source, dataset))
            known.add(normalized)
            added += 1
        if added:
            self._dirty = True
            self._refresh_table()
            self._schedule_merge()
            self._update_window_title()
        if errors:
            self._show_error("\n".join(errors))
            QMessageBox.critical(self, "无法导入文件", "\n".join(errors))
        elif added and ignored:
            self.status_label.setText(f"已添加 {added} 个 TXT，忽略 {ignored} 个非 TXT 文件")
        elif ignored and not added:
            QMessageBox.information(self, "忽略文件", "此模式只解析 .txt 文件。")

    def _refresh_table(self) -> None:
        self._refreshing_table = True
        blocker = QSignalBlocker(self.file_table)
        self.file_table.setRowCount(len(self.entries))
        for row, entry in enumerate(self.entries):
            check = QTableWidgetItem()
            check.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            check.setCheckState(
                Qt.CheckState.Checked if entry.enabled else Qt.CheckState.Unchecked
            )
            self.file_table.setItem(row, 0, check)
            order = QTableWidgetItem(str(row + 1))
            order.setForeground(QColor("#253044"))
            order.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.file_table.setItem(row, 1, order)
            name = QTableWidgetItem(entry.path.name)
            name.setForeground(
                QColor("#b42318") if entry.error else QColor("#253044")
            )
            name.setToolTip(
                f"{entry.path}\n{entry.error}" if entry.error else str(entry.path)
            )
            self.file_table.setItem(row, 2, name)

            dataset = entry.dataset
            if dataset is None:
                points_text = "—"
                span_text = "读取失败"
            elif isinstance(dataset, Spectrum):
                points_text = f"{dataset.points:,}"
                span_text = f"{dataset.wavelength_min:g}–{dataset.wavelength_max:g} nm"
            else:
                points_text = f"{dataset.points:,}"
                span_text = f"{dataset.axis.label}  {dataset.x_min:g}–{dataset.x_max:g}"
            points = QTableWidgetItem(points_text)
            points.setForeground(QColor("#253044"))
            points.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.file_table.setItem(row, 3, points)
            span = QTableWidgetItem(span_text)
            span.setForeground(QColor("#253044"))
            span.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            span.setToolTip(span_text)
            self.file_table.setItem(row, 4, span)
        del blocker
        self._refreshing_table = False
        self.count_badge.setText(f"{len(self.entries)} 个文件")
        self._sync_channel_controls()

    def _file_item_changed(self, item: QTableWidgetItem) -> None:
        if self._refreshing_table or item.column() != 0:
            return
        row = item.row()
        if 0 <= row < len(self.entries):
            self.entries[row].enabled = item.checkState() == Qt.CheckState.Checked
            self._dirty = True
            self._update_window_title()
            self._schedule_merge()

    def _selected_rows(self) -> list[int]:
        selection = self.file_table.selectionModel()
        if selection is None:
            return []
        return sorted({index.row() for index in selection.selectedRows()})

    def _move_selected(self, direction: int) -> None:
        selected = set(self._selected_rows())
        if not selected:
            return
        if direction < 0:
            for row in sorted(selected):
                if row > 0 and row - 1 not in selected:
                    self.entries[row - 1], self.entries[row] = (
                        self.entries[row],
                        self.entries[row - 1],
                    )
                    selected.remove(row)
                    selected.add(row - 1)
        else:
            for row in sorted(selected, reverse=True):
                if row < len(self.entries) - 1 and row + 1 not in selected:
                    self.entries[row + 1], self.entries[row] = (
                        self.entries[row],
                        self.entries[row + 1],
                    )
                    selected.remove(row)
                    selected.add(row + 1)
        self._dirty = True
        self._refresh_table()
        self.file_table.clearSelection()
        model = self.file_table.model()
        if model is not None:
            for row in selected:
                self.file_table.selectionModel().select(
                    model.index(row, 2),
                    QItemSelectionModel.SelectionFlag.Select
                    | QItemSelectionModel.SelectionFlag.Rows,
                )
        self._schedule_merge()
        self._update_window_title()

    def _remove_selected(self) -> None:
        selected = set(self._selected_rows())
        if not selected:
            return
        self.entries = [
            entry for row, entry in enumerate(self.entries) if row not in selected
        ]
        self._dirty = True
        self._refresh_table()
        self._schedule_merge()
        self._update_window_title()

    def _clear_files(self) -> None:
        if not self.entries:
            return
        self.entries.clear()
        self._dirty = True
        self._refresh_table()
        self._schedule_merge()
        self._update_window_title()

    def _schedule_merge(self) -> None:
        self._merge_timer.start()

    def _recompute_merge(self) -> None:
        self._merge_timer.stop()
        selected = [
            entry for entry in self.entries if entry.enabled and entry.dataset is not None
        ]
        if not selected:
            self.result = None
            self.row_badge.setText("0 行")
            self.column_badge.setText("0 列")
            self.missing_badge.setText("缺失 0")
            self.status_label.setText("等待添加文件")
            self._set_preview(
                "添加原始 TXT 后，这里会显示完整合并结果。"
            )
            self.plot_preview.set_graphs(())
            self._set_actions_enabled(False)
            return
        try:
            if self.data_type == "electrochem":
                result = merge_electrochem(
                    [
                        entry.dataset
                        for entry in selected
                        if isinstance(entry.dataset, ElectrochemSignal)
                    ],
                    channels=[
                        name
                        for name, check in self.merge_channel_checks.items()
                        if check.isChecked()
                    ],
                )
            else:
                result = merge_exact_union(
                    [
                        entry.dataset
                        for entry in selected
                        if isinstance(entry.dataset, Spectrum)
                    ],
                    [
                        name
                        for name, check in self.merge_channel_checks.items()
                        if check.isChecked()
                    ],
                )
        except (SpectrumError, ElectrochemError) as exc:
            self.result = None
            self.status_label.setText("无法生成合并结果")
            self._set_preview("")
            self.plot_preview.set_graphs(())
            self._set_actions_enabled(False)
            self._show_error(str(exc))
            return
        self.result = result
        self._clear_error()
        self.row_badge.setText(f"{result.row_count:,} 行")
        self.column_badge.setText(f"{result.column_count:,} 列")
        self.missing_badge.setText(f"缺失 {result.missing_values:,}")
        skipped = sum(
            1 for entry in self.entries if entry.enabled and entry.dataset is None
        )
        skipped_text = f"，跳过 {skipped} 个读取失败文件" if skipped else ""
        self.status_label.setText(
            f"{result.participating_files} 个文件参与合并{skipped_text}"
        )
        self._set_preview(result.text)
        self._update_plot_preview()
        self._set_actions_enabled(True)

    def _set_preview(self, text: str) -> None:
        self.preview.setPlainText(text)
        self.preview.moveCursor(QTextCursor.MoveOperation.Start)

    def _update_plot_preview(self) -> None:
        if self.result is None:
            self.plot_preview.set_graphs(())
            return
        enabled = [
            name
            for name, check in self.preview_channel_checks.items()
            if check.isChecked()
        ]
        if isinstance(self.result, MergeResult):
            graphs = cd_plot_graphs(self.result, enabled)
        else:
            graphs = electrochem_plot_graphs(self.result, enabled)
        self.plot_preview.set_graphs(graphs)

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.copy_button.setEnabled(enabled)
        self.copy_action.setEnabled(enabled)
        formula = getattr(self.result, "formula_text", "") if self.result else ""
        self.formula_button.setEnabled(bool(enabled and formula))

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def _clear_error(self) -> None:
        self.error_label.clear()
        self.error_label.hide()

    def _copy_result(self) -> None:
        if self.result is None:
            return
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.result.text)
        self.status_label.setText(
            "已复制；请从 Origin 的“长名称”左上角单元格开始粘贴"
        )
        if not self.save_check.isChecked():
            return
        base_dir = (
            self.project_path.parent
            if self.project_path is not None
            else _application_dir()
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "另存合并结果",
            str(base_dir / "merged_data.txt"),
            "制表符文本 (*.txt)",
        )
        if not path:
            return
        try:
            Path(path).write_text(
                self.result.text, encoding="utf-8", newline="\n"
            )
            self.status_label.setText(f"已复制并保存到 {Path(path).name}")
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            self.status_label.setText("已复制，但文件保存失败")

    def _copy_formulas(self) -> None:
        formula = getattr(self.result, "formula_text", "") if self.result else ""
        if not formula:
            return
        QGuiApplication.clipboard().setText(formula)
        self.status_label.setText(
            "已复制 G 公式；请选中 G1 的 F(x)= 单元格后粘贴"
        )

    def _update_window_title(self) -> None:
        project = self.project_path.name if self.project_path else "未命名工程"
        marker = " *" if self._dirty else ""
        self.setWindowTitle(
            f"DataMerger · {DATA_TYPE_NAMES[self.data_type]} · {project}{marker}"
        )

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        result = QMessageBox.warning(
            self,
            "未保存的工程",
            "当前工程有未保存的修改。",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if result == QMessageBox.StandardButton.Cancel:
            return False
        if result == QMessageBox.StandardButton.Save:
            return self._save_project()
        return True

    def _new_project(self) -> None:
        if not self._confirm_discard():
            return
        self.entries.clear()
        self.project_path = None
        self._dirty = False
        self._refresh_table()
        self._schedule_merge()
        self._refresh_recent_projects()
        self._update_window_title()

    def _close_project(self) -> None:
        self._new_project()

    def _open_project_dialog(self) -> None:
        initial = (
            str(self.project_path.parent)
            if self.project_path is not None
            else str(_application_dir())
        )
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开 DataMerger 工程",
            initial,
            f"DataMerger 工程 (*{PROJECT_EXTENSION})",
        )
        if path:
            self._open_project(path)

    def _open_project(self, path: str) -> bool:
        if not self._confirm_discard():
            return False
        try:
            document = load_project(path)
        except ProjectError as exc:
            QMessageBox.critical(self, "无法打开工程", str(exc))
            return False
        self._apply_data_type(document.data_type)
        entries: list[FileEntry] = []
        errors: list[str] = []
        for item in document.files:
            source = Path(item.path)
            try:
                dataset = self._read_dataset(source)
                entries.append(FileEntry(source, dataset, item.enabled))
            except (OSError, SpectrumError, ElectrochemError) as exc:
                entries.append(
                    FileEntry(source, None, item.enabled, str(exc))
                )
                errors.append(f"{source.name}：{exc}")
        self.entries = entries
        self.project_path = Path(path).resolve(strict=False)
        self._dirty = bool(errors)
        self._refresh_table()
        self._schedule_merge()
        self._record_recent(self.project_path)
        self._refresh_recent_projects()
        self._update_window_title()
        if errors:
            self._show_error("\n".join(errors))
            QMessageBox.warning(
                self,
                "工程已打开，但部分文件不可用",
                "\n".join(errors),
            )
        return True

    def _project_files(self) -> list[ProjectFile]:
        return [
            ProjectFile(str(entry.path.resolve(strict=False)), entry.enabled)
            for entry in self.entries
        ]

    def _save_project(self) -> bool:
        if self.project_path is None:
            return self._save_project_as()
        try:
            saved = save_project(
                self.project_path,
                self.data_type,
                self._project_files(),
            )
        except (OSError, ProjectError) as exc:
            QMessageBox.critical(self, "保存工程失败", str(exc))
            return False
        self.project_path = saved
        self._dirty = False
        self._record_recent(saved)
        self._refresh_recent_projects()
        self._update_window_title()
        self.status_label.setText(f"工程已保存到 {saved.name}")
        return True

    def _save_project_as(self) -> bool:
        initial = (
            str(self.project_path)
            if self.project_path is not None
            else str(_application_dir() / f"未命名{PROJECT_EXTENSION}")
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存 DataMerger 工程",
            initial,
            f"DataMerger 工程 (*{PROJECT_EXTENSION})",
        )
        if not path:
            return False
        self.project_path = Path(path)
        return self._save_project()

    def _record_recent(self, path: Path) -> None:
        try:
            record_recent_project(self.recent_config, path)
        except OSError:
            pass

    def _refresh_recent_projects(self) -> None:
        self._refreshing_recent = True
        blocker = QSignalBlocker(self.recent_tabs)
        while self.recent_tabs.count():
            self.recent_tabs.removeTab(0)
        recent = load_recent_projects(self.recent_config)
        if not recent:
            index = self.recent_tabs.addTab("暂无最近工程")
            self.recent_tabs.setTabData(index, "")
            self.recent_tabs.setTabEnabled(index, False)
        for path in recent:
            source = Path(path)
            index = self.recent_tabs.addTab(source.stem)
            self.recent_tabs.setTabData(index, path)
            self.recent_tabs.setTabToolTip(index, str(source))
        self._select_current_recent_tab()
        del blocker
        self._refreshing_recent = False

    def _select_current_recent_tab(self) -> None:
        if self.project_path is None:
            self.recent_tabs.setCurrentIndex(-1)
            return
        current = os.path.normcase(str(self.project_path.resolve(strict=False)))
        for index in range(self.recent_tabs.count()):
            path = self.recent_tabs.tabData(index)
            if (
                isinstance(path, str)
                and path
                and os.path.normcase(str(Path(path).resolve(strict=False))) == current
            ):
                self.recent_tabs.setCurrentIndex(index)
                return
        self.recent_tabs.setCurrentIndex(-1)

    def _recent_project_selected(self, index: int) -> None:
        if self._refreshing_recent or index < 0:
            return
        path = self.recent_tabs.tabData(index) if index >= 0 else ""
        if isinstance(path, str) and path:
            if not self._open_project(path):
                self._select_current_recent_tab()

    def dragEnterEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.mimeData().hasUrls() and any(
            url.isLocalFile() for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()
            self.drop_zone.set_hot(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.drop_zone.set_hot(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.drop_zone.set_hot(False)
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if paths:
            self._add_paths(paths)
            event.acceptProposedAction()
        else:
            event.ignore()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if not self._confirm_discard():
            event.ignore()
            return
        event.accept()


APP_STYLE = """
QWidget#root {
    background: #f3f6f9;
    color: #0f172a;
}
QToolBar#mainToolbar, QToolBar#recentToolbar {
    background: #ffffff;
    border: none;
    border-bottom: 1px solid #dfe7ef;
    padding: 5px 12px;
    spacing: 7px;
}
QToolBar#recentToolbar {
    background: #f8fafc;
    padding: 0;
}
QToolBar QToolButton {
    color: #253044;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 6px 10px;
    font-family: "Microsoft YaHei UI";
    font-size: 12px;
}
QToolBar QToolButton:hover {
    background: #f1f5f9;
    border-color: #dbe3ec;
}
QToolBar::separator {
    background: #e2e8f0;
    width: 1px;
    margin: 4px 5px;
}
QWidget#recentHost {
    background: #f8fafc;
}
QLabel#recentLabel {
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
}
QTabBar#recentTabs {
    background: transparent;
    border: none;
    qproperty-drawBase: 0;
}
QTabBar#recentTabs::tab {
    background: #eef3f8;
    color: #475569;
    border: 1px solid #dbe3ec;
    border-bottom: none;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    min-width: 92px;
    max-width: 230px;
    padding: 6px 16px;
    margin-right: 3px;
}
QTabBar#recentTabs::tab:selected {
    background: #ffffff;
    color: #1d4ed8;
    border-color: #bfdbfe;
    font-weight: 600;
}
QTabBar#recentTabs::tab:hover:!selected {
    background: #f5f8fb;
}
QLabel#title {
    font-family: "Microsoft YaHei UI";
    font-size: 22px;
    font-weight: 700;
    color: #0f172a;
}
QLabel#muted {
    color: #64748b;
    font-size: 12px;
}
QLabel#smallBadge, QLabel#pill {
    background: #eff6ff;
    color: #1d4ed8;
    border: 1px solid #dbeafe;
    border-radius: 11px;
    padding: 4px 9px;
    font-size: 11px;
}
QLabel#smallBadge, QLabel#pill {
    background: #f8fafc;
    color: #64748b;
    border-color: #e2e8f0;
}
QLabel#pill {
    padding: 3px 8px;
}
QFrame#card {
    background: white;
    border: 1px solid #e5eaf0;
    border-radius: 14px;
}
QSplitter::handle {
    background: transparent;
    margin: 4px;
    border-radius: 2px;
}
QSplitter::handle:horizontal {
    width: 8px;
}
QSplitter::handle:vertical {
    height: 8px;
}
QSplitter::handle:hover {
    background: #dbeafe;
}
QFrame#dropZone {
    background: #fbfdff;
    border: 2px dashed #c6d2df;
    border-radius: 14px;
}
QFrame#dropZone[hot="true"] {
    background: #eff6ff;
    border: 2px solid #3b82f6;
}
QLabel#dropIcon {
    background: #eff6ff;
    border: 1px solid #dbeafe;
    border-radius: 15px;
}
QLabel#dropTitle {
    font-size: 15px;
    font-weight: 600;
    color: #172033;
}
QLabel#sectionTitle {
    font-size: 14px;
    font-weight: 700;
    color: #172033;
}
QLabel#error {
    background: #fff1f2;
    color: #b42318;
    border: 1px solid #fecdd3;
    border-radius: 8px;
    padding: 8px;
}
QLabel#status {
    color: #64748b;
    font-size: 11px;
}
QPushButton {
    font-family: "Microsoft YaHei UI";
    font-size: 12px;
    border-radius: 8px;
    padding: 7px 12px;
}
QPushButton#outlineButton, QPushButton#smallButton {
    background: white;
    color: #334155;
    border: 1px solid #d8e0e9;
}
QPushButton#outlineButton:hover, QPushButton#smallButton:hover {
    background: #f8fafc;
    border-color: #b8c5d5;
}
QPushButton#primaryButton {
    background: #2563eb;
    color: white;
    border: 1px solid #1d4ed8;
    padding: 9px 15px;
    font-weight: 600;
}
QPushButton#primaryButton:hover {
    background: #1d4ed8;
}
QPushButton:disabled {
    color: #94a3b8;
    background: #f1f5f9;
    border-color: #e2e8f0;
}
QTableWidget#fileTable {
    background: white;
    border: 1px solid #e5eaf0;
    border-radius: 9px;
    gridline-color: #edf1f5;
    selection-background-color: #e8f1ff;
    selection-color: #172033;
}
QHeaderView::section {
    background: #f8fafc;
    color: #64748b;
    border: none;
    border-bottom: 1px solid #e5eaf0;
    padding: 7px 6px;
    font-size: 11px;
    font-weight: 600;
}
QPlainTextEdit#preview {
    background: #fbfcfe;
    color: #253044;
    border: 1px solid #e2e8f0;
    border-radius: 9px;
    padding: 9px;
    selection-background-color: #dbeafe;
}
QTabWidget#previewTabs::pane {
    border: 1px solid #e2e8f0;
    border-radius: 9px;
    background: #fbfcfe;
    top: -1px;
}
QTabWidget#previewTabs QTabBar::tab {
    background: #f1f5f9;
    color: #64748b;
    border: 1px solid #e2e8f0;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 4px 12px;
    margin-right: 2px;
}
QTabWidget#previewTabs QTabBar {
    qproperty-drawBase: 0;
    border: none;
    background: transparent;
}
QTabWidget#previewTabs QTabBar::tab:selected {
    background: #ffffff;
    color: #1d4ed8;
}
QScrollArea#plotPreview, QWidget#plotHost {
    background: transparent;
    border: none;
}
QFrame#plotCard {
    background: #ffffff;
    border: 1px solid #e6edf5;
    border-radius: 10px;
}
QCheckBox {
    color: #334155;
    font-size: 12px;
    spacing: 6px;
}
QMenu {
    background: white;
    color: #253044;
    border: 1px solid #dfe7ef;
    border-radius: 8px;
    padding: 3px;
    font-family: "Microsoft YaHei UI";
    font-size: 12px;
}
QMenu::item {
    color: #253044;
    background: transparent;
    font-family: "Microsoft YaHei UI";
    font-size: 12px;
    min-height: 14px;
    padding: 3px 24px 3px 18px;
    margin: 0px 1px;
    border-radius: 5px;
}
QMenu::item:selected {
    background: #eff6ff;
    color: #1d4ed8;
}
QMenu::item:disabled {
    color: #94a3b8;
}
QMenu::indicator:checked {
    background: #2563eb;
    border-radius: 4px;
}
"""
