from __future__ import annotations

from dataclasses import replace

import pandas as pd
from PySide6.QtCore import QThreadPool, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QSplitter, QStatusBar

from market_viewer.analysis.condition_parser import summarize_conditions
from market_viewer.analysis.filter_models import ParsedFilter
from market_viewer.analysis.indicators import add_indicators
from market_viewer.config.app_config_store import (
    load_kiwoom_config,
    load_llm_config,
    load_screening_report_config,
    load_screening_conditions,
    load_telegram_config,
    save_app_configs,
    save_screening_conditions,
    save_screening_report_config,
)
from market_viewer.config.session_store import load_session, save_session
from market_viewer.data.market_registry import list_market_scopes
from market_viewer.data.market_service import MarketService
from market_viewer.models import AppSessionState, FundamentalSnapshot, StockReference
from market_viewer.prompt_layers.layer_registry import get_prompt_layer, list_prompt_layers
from market_viewer.services.context_service import build_workspace_context_markdown
from market_viewer.services.intelligence_service import build_report_rows
from market_viewer.services.llm_service import run_connection_test, run_stock_analysis
from market_viewer.services.request_gate import RequestGate
from market_viewer.services.rate_limiter import AdaptiveRateLimiter
from market_viewer.services.screening_service import (
    build_resolved_filter_markdown,
    execute_screening,
    parse_local_screening_prompt,
)
from market_viewer.services.screening_report_service import (
    ScreeningReportSummary,
    generate_screening_llm_reports,
)
from market_viewer.telegram.client import send_telegram_report
from market_viewer.ui.analysis_panel import AnalysisPanel
from market_viewer.ui.chart_window import ChartWindow
from market_viewer.ui.kiwoom_settings_dialog import KiwoomSettingsDialog
from market_viewer.ui.llm_settings_dialog import LLMSettingsDialog
from market_viewer.ui.screening_dialog import ScreeningDialog
from market_viewer.ui.screening_report_settings_dialog import ScreeningReportSettingsDialog
from market_viewer.ui.stock_list_panel import StockListPanel
from market_viewer.ui.telegram_settings_dialog import TelegramSettingsDialog
from market_viewer.ui.worker import Worker, WorkerTask


class MainWindow(QMainWindow):
    CHANNEL_LISTING = "listing"
    CHANNEL_SCREEN = "screen"
    CHANNEL_PRICE = "price"
    CHANNEL_KIWOOM_TEST = "kiwoom_test"
    CHANNEL_LLM_TEST = "llm_test"
    CHANNEL_LLM_ANALYSIS = "llm_analysis"
    CHANNEL_TELEGRAM = "telegram"
    CHANNEL_SCREEN_REPORT = "screen_report"

    def __init__(self) -> None:
        super().__init__()
        self.kiwoom_config = load_kiwoom_config()
        self.market_service = MarketService(self.kiwoom_config)
        self.thread_pool = QThreadPool.globalInstance()
        self.session_state = AppSessionState()
        self.session_state.llm_config = load_llm_config()
        self.telegram_config = load_telegram_config()
        self.screening_report_config = load_screening_report_config()
        self.current_listing = pd.DataFrame()
        self.last_screening_listing = pd.DataFrame()
        self.last_screening_filter = ParsedFilter(original_prompt="", normalized_prompt="")
        self.current_stock: StockReference | None = None
        self.current_price_frame: pd.DataFrame | None = None
        self.current_fundamental_snapshot: FundamentalSnapshot | None = None
        self.current_filter = ParsedFilter(original_prompt="", normalized_prompt="")
        self.screening_conditions = load_screening_conditions()
        self.session_path: str | None = None
        self._pending_restore: AppSessionState | None = None
        self._restore_screen_pending = False
        self._prompt_layer_actions: dict[str, QAction] = {}
        self._request_gate = RequestGate()
        self._is_closing = False
        self._screen_cancel_requested = False
        self._screen_running = False
        self._report_cancel_requested = False
        self._report_running = False
        self._report_queue: list[pd.Series] = []
        self._report_queue_filter = ParsedFilter(original_prompt="", normalized_prompt="")
        self._report_queue_total = 0
        self._report_queue_saved = 0
        self._report_queue_sent = 0
        self._report_queue_failed = 0
        self._active_workers: set[Worker] = set()
        self._listing_loading = False

        self.setWindowTitle("Multi-Market Screener")
        self.resize(1180, 840)
        self._setup_ui()
        self._create_actions()
        self._create_menus()
        self._setup_timers()
        self._sync_prompt_layer_actions()
        self._set_current_screening_conditions(self.screening_conditions, apply_to_panel=True)
        self._refresh_workspace_context()
        self._load_listing(self.session_state.market_scope)

    def _setup_ui(self) -> None:
        self.stock_panel = StockListPanel()
        self.stock_panel.set_market_options(list_market_scopes())
        self.stock_panel.set_market_scope(self.session_state.market_scope)

        self.chart_window: ChartWindow | None = None
        self.analysis_panel = AnalysisPanel()

        self.splitter = QSplitter()
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.stock_panel)
        self.splitter.addWidget(self.analysis_panel)
        self.splitter.setStretchFactor(0, 5)
        self.splitter.setStretchFactor(1, 4)
        self.splitter.setSizes(self.session_state.splitter_sizes)
        self.setCentralWidget(self.splitter)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        self.stock_panel.market_scope_changed.connect(self._on_market_scope_changed)
        self.stock_panel.refresh_requested.connect(self._refresh_current_scope)
        self.stock_panel.stock_activated.connect(self._load_price_history)
        self.stock_panel.search_failed.connect(lambda message: self.statusBar().showMessage(message, 4000))
        self.stock_panel.stop_screen_requested.connect(self._stop_screening)

        self.analysis_panel.analyze_requested.connect(self._run_llm_analysis)
        self.analysis_panel.clear_requested.connect(lambda: self.analysis_panel.set_result_markdown(""))
        self.analysis_panel.send_context_requested.connect(self._send_context_report)
        self.analysis_panel.send_result_requested.connect(self._send_llm_report)

    def _create_actions(self) -> None:
        self.open_session_action = self._make_action(
            "세션 불러오기",
            self._open_session,
            shortcut=QKeySequence.StandardKey.Open,
        )
        self.save_session_action = self._make_action(
            "세션 저장",
            self._save_session,
            shortcut=QKeySequence.StandardKey.Save,
        )

        self.refresh_market_action = self._make_action(
            "시장 새로고침",
            self._refresh_current_scope,
            shortcut="Ctrl+R",
        )

        self.focus_filter_action = self._make_action(
            "스크리너 조건 설정",
            self._open_screening_dialog,
            shortcut="Ctrl+F",
            register_shortcut=True,
        )
        self.focus_search_action = self._make_action(
            "검색 포커스",
            self.stock_panel.focus_search,
            shortcut="/",
            register_shortcut=True,
        )
        self.focus_market_action = self._make_action(
            "시장 선택 포커스",
            self.stock_panel.focus_market_scope,
            shortcut="Ctrl+Shift+M",
            register_shortcut=True,
        )
        self.focus_list_action = self._make_action(
            "종목 패널 포커스",
            self.stock_panel.focus_table,
            shortcut="Ctrl+1",
            register_shortcut=True,
        )
        self.focus_chart_action = self._make_action(
            "차트 창 열기",
            self._reveal_chart_window,
            shortcut="Ctrl+2",
            register_shortcut=True,
        )
        self.focus_analysis_action = self._make_action(
            "분석 패널 포커스",
            self.analysis_panel.focus_prompt_editor,
            shortcut="Ctrl+3",
            register_shortcut=True,
        )

        self.screen_settings_action = self._make_action(
            "조건 설정",
            self._open_screening_dialog,
            shortcut="Ctrl+Return",
            register_shortcut=True,
        )
        self.apply_screen_action = self._make_action(
            "조건 적용",
            self._apply_resolved_screen,
            shortcut="Ctrl+Shift+Return",
            register_shortcut=True,
        )
        self.clear_screen_action = self._make_action(
            "스크리너 초기화",
            self._clear_screen,
            shortcut="Escape",
            register_shortcut=True,
        )
        self.generate_screen_reports_action = self._make_action(
            "스크리닝 결과 LLM 보고서 생성/발송",
            self._generate_screening_reports,
        )
        self.stop_report_queue_action = self._make_action(
            "LLM 보고서 큐 중지",
            self._stop_report_queue,
        )
        self.clear_report_queue_action = self._make_action(
            "LLM 보고서 큐 비우기",
            self._clear_report_queue,
        )
        self.screen_report_settings_action = self._make_action(
            "보고서/스케줄 설정...",
            self._open_screen_report_settings,
        )
        self.auto_screen_reports_action = QAction("스크리닝 완료 후 LLM 보고서 자동 생성/발송", self)
        self.auto_screen_reports_action.setCheckable(True)
        self.auto_screen_reports_action.setChecked(self.screening_report_config.auto_llm_reports)
        self.auto_screen_reports_action.toggled.connect(self._toggle_auto_screening_reports)
        self.scheduled_screening_action = QAction("1시간마다 자동 스크리닝 실행", self)
        self.scheduled_screening_action.setCheckable(True)
        self.scheduled_screening_action.setChecked(self.screening_report_config.scheduled_screening_enabled)
        self.scheduled_screening_action.toggled.connect(self._toggle_scheduled_screening)

        self.next_stock_action = self._make_action(
            "다음 종목",
            lambda: self.stock_panel.select_relative_row(1, activate=True),
            shortcut="Alt+J",
            register_shortcut=True,
        )
        self.previous_stock_action = self._make_action(
            "이전 종목",
            lambda: self.stock_panel.select_relative_row(-1, activate=True),
            shortcut="Alt+K",
            register_shortcut=True,
        )

        self.preset_actions: dict[str, QAction] = {}
        for preset, shortcut in [("3M", "Alt+1"), ("6M", "Alt+2"), ("1Y", "Alt+3"), ("ALL", "Alt+4")]:
            action = self._make_action(
                f"{preset} 보기",
                lambda checked=False, current=preset: self._set_chart_preset(current),
                shortcut=shortcut,
                register_shortcut=True,
            )
            self.preset_actions[preset] = action
        self.pan_left_action = self._make_action(
            "차트 왼쪽 이동",
            lambda: self._ensure_chart_window().chart_panel.pan_relative(-0.2),
            shortcut="Alt+H",
            register_shortcut=True,
        )
        self.pan_right_action = self._make_action(
            "차트 오른쪽 이동",
            lambda: self._ensure_chart_window().chart_panel.pan_relative(0.2),
            shortcut="Alt+L",
            register_shortcut=True,
        )
        self.zoom_in_action = self._make_action(
            "차트 확대",
            lambda: self._ensure_chart_window().chart_panel.zoom_relative(0.8),
            shortcut="Ctrl+=",
            register_shortcut=True,
        )
        self.zoom_out_action = self._make_action(
            "차트 축소",
            lambda: self._ensure_chart_window().chart_panel.zoom_relative(1.25),
            shortcut="Ctrl+-",
            register_shortcut=True,
        )
        self.reset_chart_action = self._make_action(
            "차트 리셋",
            lambda: self._ensure_chart_window().chart_panel.reset_range(),
            shortcut="Ctrl+0",
            register_shortcut=True,
        )

        self.llm_settings_action = self._make_action(
            "LLM 연결 설정",
            self._open_llm_settings,
            shortcut="Ctrl+,",
        )
        self.llm_test_action = self._make_action("LLM 연결 테스트", self._test_llm_connection)
        self.llm_run_action = self._make_action(
            "LLM 분석 실행",
            lambda: self._run_llm_analysis(self.analysis_panel.user_request_text()),
            shortcut="Ctrl+Alt+Return",
            register_shortcut=True,
        )
        self.llm_clear_action = self._make_action(
            "LLM 응답 지우기",
            lambda: self.analysis_panel.set_result_markdown(""),
        )
        self.telegram_settings_action = self._make_action(
            "Telegram 설정",
            self._open_telegram_settings,
        )
        self.telegram_send_context_action = self._make_action(
            "세션 리포트 발송",
            self._send_context_report,
        )
        self.telegram_send_result_action = self._make_action(
            "LLM 결과 발송",
            self._send_llm_report,
        )
        self.kiwoom_settings_action = self._make_action(
            "Kiwoom REST 설정",
            self._open_kiwoom_settings,
        )
        self.kiwoom_test_action = self._make_action(
            "Kiwoom REST 연결 테스트",
            self._test_kiwoom_connection,
        )

    def _create_menus(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        file_menu.addAction(self.open_session_action)
        file_menu.addAction(self.save_session_action)

        market_menu = menu_bar.addMenu("Market")
        market_menu.addAction(self.refresh_market_action)
        market_menu.addSeparator()
        market_menu.addAction(self.kiwoom_settings_action)
        market_menu.addAction(self.kiwoom_test_action)

        screening_menu = menu_bar.addMenu("Screening")
        screening_menu.addAction(self.focus_market_action)
        screening_menu.addAction(self.focus_search_action)
        screening_menu.addSeparator()
        screening_menu.addAction(self.screen_settings_action)
        screening_menu.addAction(self.apply_screen_action)
        screening_menu.addAction(self.clear_screen_action)
        screening_menu.addSeparator()
        screening_menu.addAction(self.generate_screen_reports_action)
        screening_menu.addAction(self.stop_report_queue_action)
        screening_menu.addAction(self.clear_report_queue_action)
        screening_menu.addAction(self.auto_screen_reports_action)
        screening_menu.addAction(self.scheduled_screening_action)
        screening_menu.addAction(self.screen_report_settings_action)

        chart_menu = menu_bar.addMenu("Chart")
        chart_menu.addAction(self.focus_chart_action)
        chart_menu.addSeparator()
        for preset in ["3M", "6M", "1Y", "ALL"]:
            chart_menu.addAction(self.preset_actions[preset])
        chart_menu.addSeparator()
        chart_menu.addAction(self.pan_left_action)
        chart_menu.addAction(self.pan_right_action)
        chart_menu.addAction(self.zoom_in_action)
        chart_menu.addAction(self.zoom_out_action)
        chart_menu.addAction(self.reset_chart_action)

        llm_menu = menu_bar.addMenu("LLM")
        llm_menu.addAction(self.llm_settings_action)
        llm_menu.addAction(self.llm_test_action)
        llm_menu.addAction(self.llm_run_action)
        llm_menu.addAction(self.llm_clear_action)

        telegram_menu = menu_bar.addMenu("Telegram")
        telegram_menu.addAction(self.telegram_settings_action)
        telegram_menu.addSeparator()
        telegram_menu.addAction(self.telegram_send_context_action)
        telegram_menu.addAction(self.telegram_send_result_action)

        navigate_menu = menu_bar.addMenu("Navigate")
        navigate_menu.addAction(self.focus_list_action)
        navigate_menu.addAction(self.focus_chart_action)
        navigate_menu.addAction(self.focus_analysis_action)
        navigate_menu.addSeparator()
        navigate_menu.addAction(self.previous_stock_action)
        navigate_menu.addAction(self.next_stock_action)

        prompt_layers_menu = menu_bar.addMenu("Prompt Layers")
        for layer in list_prompt_layers():
            action = QAction(layer.name, self)
            action.setCheckable(True)
            if layer.shortcut:
                action.setShortcut(QKeySequence(layer.shortcut))
            action.setStatusTip(layer.description)
            action.toggled.connect(lambda checked, layer_id=layer.id: self._toggle_prompt_layer(layer_id, checked))
            prompt_layers_menu.addAction(action)
            self._prompt_layer_actions[layer.id] = action
            self.addAction(action)

        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("현재 상태", self)
        about_action.triggered.connect(self._show_current_status)
        help_menu.addAction(about_action)

    def _setup_timers(self) -> None:
        self.report_queue_timer = QTimer(self)
        self.report_queue_timer.setSingleShot(True)
        self.report_queue_timer.timeout.connect(self._process_next_queued_report)

        self.scheduled_screening_timer = QTimer(self)
        self.scheduled_screening_timer.timeout.connect(self._run_scheduled_screening)
        if self.screening_report_config.scheduled_screening_enabled:
            self._restart_scheduled_screening_timer()

    def _make_action(self, text: str, slot, shortcut=None, register_shortcut: bool = False) -> QAction:
        action = QAction(text, self)
        if shortcut is not None:
            if isinstance(shortcut, QKeySequence.StandardKey):
                action.setShortcut(shortcut)
            else:
                action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
        if register_shortcut:
            self.addAction(action)
        return action

    def _run_worker(self, fn, task_name: str, on_success, on_failure=None, on_progress=None, accepts_progress: bool = False) -> None:
        worker = Worker(fn, task_name, accepts_progress=accepts_progress)
        self._active_workers.add(worker)
        # Worker threads must emit plain Python data only. All Qt UI and chart
        # mutations are funneled back to the GUI thread through queued delivery.
        def finish_and_cleanup(task: WorkerTask) -> None:
            self._active_workers.discard(worker)
            on_success(task)

        def fail_and_cleanup(message: str) -> None:
            self._active_workers.discard(worker)
            (on_failure or self._show_error)(message)

        worker.signals.finished.connect(finish_and_cleanup, Qt.ConnectionType.QueuedConnection)
        worker.signals.failed.connect(fail_and_cleanup, Qt.ConnectionType.QueuedConnection)
        if on_progress is not None:
            worker.signals.progress.connect(on_progress, Qt.ConnectionType.QueuedConnection)
        self.thread_pool.start(worker)

    def _run_scoped_worker(
        self,
        *,
        channel: str,
        task_name: str,
        fn,
        on_success,
        status_message: str | None = None,
        on_failure=None,
        on_progress=None,
        modal_error: bool = False,
        accepts_progress: bool = False,
    ) -> None:
        request_id = self._request_gate.begin(channel)
        if status_message:
            self.statusBar().showMessage(status_message)

        def wrapped_fn(progress_emit=None):
            if accepts_progress:
                return request_id, fn(progress_emit)
            return request_id, fn()

        def wrapped_success(task: WorkerTask) -> None:
            try:
                current_request_id, payload = task.payload
                if self._is_closing:
                    return
                if not self._request_gate.is_current(channel, current_request_id):
                    return
                on_success(WorkerTask(task.name, payload))
            except Exception as exc:
                self._handle_background_error(f"{task_name} 완료 처리 실패: {exc}", modal=modal_error)

        def wrapped_failure(message: str) -> None:
            try:
                if self._is_closing:
                    return
                if not self._request_gate.is_current(channel, request_id):
                    return
                if on_failure is not None:
                    on_failure(message)
                else:
                    self._handle_background_error(message, modal=modal_error)
            except Exception as exc:
                self._handle_background_error(f"{task_name} 실패 처리 중 추가 오류: {exc}", modal=False)

        def wrapped_progress(payload: object) -> None:
            if self._is_closing or not self._request_gate.is_current(channel, request_id):
                return
            if on_progress is not None:
                on_progress(payload)

        self._run_worker(
            wrapped_fn,
            task_name,
            wrapped_success,
            wrapped_failure,
            on_progress=wrapped_progress if on_progress is not None else None,
            accepts_progress=accepts_progress,
        )

    def _persist_app_configs(self) -> None:
        save_app_configs(self.session_state.llm_config, self.telegram_config, self.kiwoom_config)

    def _ensure_chart_window(self) -> ChartWindow:
        if self.chart_window is None:
            self.chart_window = ChartWindow()
        return self.chart_window

    def _chart_range_text(self) -> str:
        if self.chart_window is None:
            return "차트 미표시"
        return self.chart_window.chart_panel.describe_visible_range()

    def _clear_active_stock_context(self) -> None:
        self.current_stock = None
        self.current_price_frame = None
        self.current_fundamental_snapshot = None

    def _restore_pending_selection_after_listing(self) -> None:
        if self._pending_restore is None:
            return
        state = self._pending_restore
        if state.filter_prompt and not self._restore_screen_pending:
            self._restore_screen_pending = True
            self.stock_panel.set_filter_prompt(state.filter_prompt)
            self.current_filter = parse_local_screening_prompt(state.filter_prompt, state.market_scope)
            self.stock_panel.set_resolved_preview(build_resolved_filter_markdown(self.current_filter, state.market_scope))
            self._apply_resolved_screen()
            return
        if state.selected_stock:
            self.stock_panel.select_stock(state.selected_stock)
            self._load_price_history(state.selected_stock)
            return
        self._pending_restore = None

    def _finalize_restore_after_price_load(self) -> None:
        if self._pending_restore is None:
            return
        chart_panel = self._ensure_chart_window().chart_panel
        chart_panel.set_tab_index(self._pending_restore.chart_tab_index)
        chart_panel.set_visible_range_from_iso(
            self._pending_restore.chart_visible_start,
            self._pending_restore.chart_visible_end,
        )
        self.analysis_panel.set_user_request_text(self._pending_restore.user_request_text)
        self.splitter.setSizes(self._pending_restore.splitter_sizes)
        self._pending_restore = None
        self._restore_screen_pending = False

    def _load_listing_into_table(self, frame: pd.DataFrame) -> None:
        self.current_listing = frame
        self.stock_panel.set_listing(frame, auto_activate=False)

    def _on_market_scope_changed(self, market_scope: str) -> None:
        self.session_state.market_scope = market_scope
        self._load_listing(market_scope)

    def _refresh_current_scope(self) -> None:
        self._load_listing(self.stock_panel.current_market_scope())

    def _load_listing(self, market_scope: str) -> None:
        if self._listing_loading:
            self.statusBar().showMessage("이미 종목 목록을 불러오는 중입니다.", 3000)
            return
        if not self.kiwoom_config.connection_ready:
            self._load_listing_into_table(pd.DataFrame())
            self.statusBar().showMessage("Kiwoom REST 설정 후 시장 새로고침을 실행하세요.", 6000)
            self._refresh_workspace_context()
            return
        self._set_listing_loading(True)
        self._run_scoped_worker(
            channel=self.CHANNEL_LISTING,
            task_name="listing",
            status_message=f"{market_scope} 종목 목록을 불러오는 중입니다...",
            accepts_progress=True,
            fn=lambda progress_emit: (
                market_scope,
                *self.market_service.load_listing_with_warnings(market_scope, progress_callback=progress_emit),
            ),
            on_success=self._on_listing_loaded,
            on_failure=self._on_listing_failed,
            on_progress=self._on_listing_progress,
        )

    def _on_listing_loaded(self, task: WorkerTask) -> None:
        self._set_listing_loading(False)
        market_scope, frame, warnings = task.payload
        self._load_listing_into_table(frame)
        current_scope = self.stock_panel.current_market_scope()
        self.statusBar().showMessage(f"{current_scope} 종목 {len(frame)}개를 불러왔습니다.", 4000)
        if warnings:
            self.statusBar().showMessage(" | ".join(warnings[:2]), 5000)
            self.analysis_panel.set_result_markdown("## 시장 목록 로딩 경고\n\n- " + "\n- ".join(warnings))
        self._refresh_workspace_context()
        self._restore_pending_selection_after_listing()

    def _on_listing_failed(self, message: str) -> None:
        self._set_listing_loading(False)
        self._handle_background_error(message)

    def _on_listing_progress(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        source = payload.get("source", "")
        index = payload.get("index", 0)
        total = payload.get("total", 0)
        stage = payload.get("stage", "")
        count = payload.get("count", 0)
        if stage == "start":
            message = f"{source} 종목 목록을 불러오는 중입니다... ({index}/{total})"
        elif stage == "done":
            message = f"{source} 종목 {count}개 완료 ({index}/{total})"
        elif stage == "failed":
            message = f"{source} 종목 목록 로딩 실패 ({index}/{total})"
        elif stage == "empty":
            message = f"{source} 종목 목록이 비어 있습니다 ({index}/{total})"
        else:
            message = f"{source} 종목 목록 처리 중... ({index}/{total})"
        self.statusBar().showMessage(message)

    def _set_listing_loading(self, loading: bool) -> None:
        self._listing_loading = loading
        self.stock_panel.set_listing_loading(loading)
        self.refresh_market_action.setEnabled(not loading)

    def _clear_screen(self) -> None:
        self.current_filter = ParsedFilter(original_prompt="", normalized_prompt="")
        self._clear_active_stock_context()
        self.stock_panel.set_filter_prompt("")
        self.stock_panel.set_resolved_preview("조건이 비어 있습니다. 현재 시장 범위 전체를 표시합니다.")
        self.stock_panel.set_apply_enabled(True)
        self.stock_panel.set_screening_progress("스크리닝 대기")
        market_scope = self.stock_panel.current_market_scope()
        self._refresh_workspace_context()
        self.statusBar().showMessage("스크리너 조건을 초기화하고 종목 목록을 다시 불러오는 중입니다...")
        self._load_listing(market_scope)

    def _open_screening_dialog(self) -> None:
        dialog = ScreeningDialog(self.screening_conditions, self)
        if not dialog.exec():
            return
        self.screening_conditions = dialog.conditions()
        save_screening_conditions(self.screening_conditions)
        self._set_current_screening_conditions(self.screening_conditions, apply_to_panel=True)
        self._apply_resolved_screen()

    def _set_current_screening_conditions(self, conditions, apply_to_panel: bool = False) -> None:
        market_scope = self.stock_panel.current_market_scope() or self.session_state.market_scope
        summary = summarize_conditions(conditions)
        self.current_filter = ParsedFilter(
            original_prompt=summary,
            normalized_prompt=summary,
            markets=[] if market_scope == "KRX_ALL" else [market_scope],
            custom_conditions=conditions,
            resolution_source="custom",
        )
        if apply_to_panel:
            self.stock_panel.set_filter_prompt(summary)
            self.stock_panel.set_resolved_preview(build_resolved_filter_markdown(self.current_filter, market_scope))

    def _resolve_screen_prompt(self, prompt: str) -> None:
        market_scope = self.stock_panel.current_market_scope()
        parsed = parse_local_screening_prompt(prompt, market_scope)
        self.current_filter = parsed
        self.stock_panel.set_resolved_preview(build_resolved_filter_markdown(parsed, market_scope))
        self.stock_panel.set_apply_enabled(True)
        self.statusBar().showMessage("스크리너 조건을 갱신했습니다.", 4000)

    def _apply_resolved_screen(self) -> None:
        prompt = self.stock_panel.filter_prompt()
        if self.current_filter.custom_conditions:
            self._set_current_screening_conditions(self.screening_conditions, apply_to_panel=True)
        elif prompt != self.current_filter.original_prompt:
            self._resolve_screen_prompt(prompt)

        market_scope = self.stock_panel.current_market_scope()
        parsed = self.current_filter
        self._screen_cancel_requested = False
        self._screen_running = True
        self.stock_panel.set_screening_running(True)
        self.stock_panel.set_screening_progress("0 / 0 처리 중 · 매칭 0 · 실패 0 · 0.0%")
        self._run_scoped_worker(
            channel=self.CHANNEL_SCREEN,
            task_name="screen",
            status_message="조건 스크리닝을 실행하는 중입니다...",
            accepts_progress=True,
            fn=lambda progress_emit: (
                parsed,
                execute_screening(
                    market_service=self.market_service,
                    market_scope=market_scope,
                    parsed_filter=parsed,
                    listing=self.current_listing,
                    progress_callback=progress_emit,
                    cancel_checker=lambda: self._screen_cancel_requested,
                    rate_limiter=AdaptiveRateLimiter(
                        max_samples_per_second=self.screening_report_config.max_samples_per_second,
                        min_samples_per_second=self.screening_report_config.min_samples_per_second,
                        adaptive=self.screening_report_config.adaptive_speed_down,
                    ),
                ),
            ),
            on_success=self._on_screen_loaded,
            on_progress=self._on_screen_progress,
            on_failure=self._on_screen_failed,
        )

    def _stop_screening(self) -> None:
        if self._report_running or self._report_queue:
            self._report_cancel_requested = True
            self.report_queue_timer.stop()
            self.stock_panel.set_screening_progress("보고서 중지 요청됨 · 현재 종목 처리 후 멈춥니다.")
            self.statusBar().showMessage("LLM 보고서 생성을 중지 요청했습니다.", 4000)
            if not self._report_running:
                self._finish_report_queue("중지됨")
            return
        self._screen_cancel_requested = True
        self.stock_panel.set_screening_progress("중지 요청됨 · 현재 종목 처리 후 멈춥니다.")
        self.statusBar().showMessage("스크리닝 중지를 요청했습니다.", 4000)

    def _on_screen_progress(self, progress) -> None:
        remaining = progress.remaining_seconds
        remaining_text = "--:--" if remaining is None else self._format_duration(remaining)
        text = (
            f"{progress.done} / {progress.total} 처리 · 매칭 {progress.matched} · 실패 {progress.failures} · "
            f"{progress.percent:.1f}% · 경과 {self._format_duration(progress.elapsed_seconds)} · 남은 {remaining_text}"
        )
        if progress.samples_per_second:
            text += f" · 속도 {progress.samples_per_second:.1f}/sec"
        if progress.adaptive_slowdown:
            text += " · 자동 감속"
        if progress.current_code:
            text += f" · {progress.current_name}({progress.current_code})"
        if progress.stopped:
            text = "중지됨 · " + text
        self.stock_panel.set_screening_progress(text)
        self.statusBar().showMessage(text)

    def _on_screen_loaded(self, task: WorkerTask) -> None:
        parsed, payload = task.payload
        frame, warnings = payload
        self.stock_panel.set_screening_running(False)
        self._screen_running = False
        self._screen_cancel_requested = False
        self._clear_active_stock_context()
        self.current_listing = frame
        self.last_screening_listing = frame.copy()
        self.last_screening_filter = parsed
        self.stock_panel.set_listing(frame, auto_activate=False)
        warning_text = "\n".join(warnings[:3])
        status = f"{len(frame)}개 종목이 조건에 일치했습니다."
        if warning_text:
            status += " 일부 종목은 스크리닝에 실패했습니다."
        self.statusBar().showMessage(status, 5000)
        if warning_text:
            self.analysis_panel.set_result_markdown(f"## 스크리닝 경고\n\n- " + "\n- ".join(warnings))
        self._refresh_workspace_context()

        if self._pending_restore is not None and self._pending_restore.selected_stock:
            self.stock_panel.select_stock(self._pending_restore.selected_stock)
            self._load_price_history(self._pending_restore.selected_stock)

        stopped = any("중지" in warning for warning in warnings)
        if self.screening_report_config.auto_llm_reports and not stopped and not frame.empty:
            self._generate_screening_reports()

    def _on_screen_failed(self, message: str) -> None:
        self.stock_panel.set_screening_running(False)
        self._screen_running = False
        self._screen_cancel_requested = False
        self.stock_panel.set_screening_progress(f"실패 · {message}")
        self._handle_background_error(message)

    def _toggle_auto_screening_reports(self, enabled: bool) -> None:
        if enabled and not self._screen_report_ready(show_error=True):
            self.auto_screen_reports_action.blockSignals(True)
            self.auto_screen_reports_action.setChecked(False)
            self.auto_screen_reports_action.blockSignals(False)
            self.screening_report_config.auto_llm_reports = False
            save_screening_report_config(self.screening_report_config)
            return
        self.screening_report_config.auto_llm_reports = enabled
        save_screening_report_config(self.screening_report_config)
        message = "자동 LLM 보고서 생성/발송을 켰습니다." if enabled else "자동 LLM 보고서 생성/발송을 껐습니다."
        self.statusBar().showMessage(message, 4000)

    def _toggle_scheduled_screening(self, enabled: bool) -> None:
        self.screening_report_config.scheduled_screening_enabled = enabled
        save_screening_report_config(self.screening_report_config)
        if enabled:
            self._restart_scheduled_screening_timer()
            self.statusBar().showMessage("자동 스크리닝 스케줄러를 켰습니다.", 4000)
        else:
            self.scheduled_screening_timer.stop()
            self.statusBar().showMessage("자동 스크리닝 스케줄러를 껐습니다.", 4000)

    def _restart_scheduled_screening_timer(self) -> None:
        interval_ms = self.screening_report_config.scheduled_screening_interval_minutes * 60 * 1000
        self.scheduled_screening_timer.start(interval_ms)

    def _run_scheduled_screening(self) -> None:
        if self._listing_loading or self._screen_running or self._report_running or self._report_queue:
            self.statusBar().showMessage("자동 스크리닝 tick skipped: 작업이 진행 중입니다.", 5000)
            return
        self.statusBar().showMessage("자동 스크리닝을 실행합니다.", 5000)
        self._apply_resolved_screen()

    def _open_screen_report_settings(self) -> None:
        dialog = ScreeningReportSettingsDialog(self.screening_report_config, self)
        if not dialog.exec():
            return
        self.screening_report_config = dialog.get_config()
        save_screening_report_config(self.screening_report_config)
        self.scheduled_screening_action.blockSignals(True)
        self.scheduled_screening_action.setChecked(self.screening_report_config.scheduled_screening_enabled)
        self.scheduled_screening_action.blockSignals(False)
        if self.screening_report_config.scheduled_screening_enabled:
            self._restart_scheduled_screening_timer()
        else:
            self.scheduled_screening_timer.stop()
        self.statusBar().showMessage("보고서/스케줄 설정을 저장했습니다.", 4000)

    def _screen_report_ready(self, *, show_error: bool = False) -> bool:
        if not self.session_state.llm_config.connection_ready:
            if show_error:
                self._show_error("LLM 연결 설정을 먼저 입력하세요.")
            return False
        if self.screening_report_config.telegram_after_llm_reports and not self.telegram_config.connection_ready:
            if show_error:
                self._show_error("Telegram Bot Token과 Chat ID를 먼저 설정하세요.")
            return False
        return True

    def _generate_screening_reports(self) -> None:
        if self._report_running:
            self.statusBar().showMessage("이미 LLM 보고서를 생성/전송하는 중입니다.", 4000)
            return
        if self._report_queue:
            self.statusBar().showMessage("이미 LLM 보고서 큐가 대기 중입니다.", 4000)
            return
        if self.last_screening_listing.empty:
            self._show_error("LLM 보고서를 생성할 스크리닝 결과가 없습니다. 조건 스크리닝을 먼저 실행하세요.")
            return
        if not self._screen_report_ready(show_error=True):
            return
        limit = min(len(self.last_screening_listing), self.screening_report_config.max_llm_report_stocks)
        self._report_queue = [row.copy() for _, row in self.last_screening_listing.head(limit).iterrows()]
        self._report_queue_filter = self.last_screening_filter
        self._report_queue_total = len(self._report_queue)
        self._report_queue_saved = 0
        self._report_queue_sent = 0
        self._report_queue_failed = 0
        self._report_cancel_requested = False
        self.stock_panel.set_screening_running(True)
        interval = self.screening_report_config.llm_report_interval_minutes
        self.stock_panel.set_screening_progress(
            f"LLM 보고서 큐 대기 {self._report_queue_total}개 · {interval}분 간격 전송 준비"
        )
        self._process_next_queued_report()

    def _process_next_queued_report(self) -> None:
        if self._is_closing or self._report_running:
            return
        if self._report_cancel_requested:
            self._finish_report_queue("중지됨")
            return
        if not self._report_queue:
            self._finish_report_queue("완료")
            return
        row = self._report_queue.pop(0)
        stock_name = str(row.get("Name", ""))
        stock_code = str(row.get("Code", ""))
        self._report_cancel_requested = False
        self._report_running = True
        self.stock_panel.set_screening_running(True)
        done = self._report_queue_total - len(self._report_queue) - 1
        self.stock_panel.set_screening_progress(
            f"LLM 보고서 생성/전송 {done} / {self._report_queue_total} · "
            f"대기 {len(self._report_queue)} · {stock_name}({stock_code})"
        )
        self._run_scoped_worker(
            channel=self.CHANNEL_SCREEN_REPORT,
            task_name="screen_report",
            status_message="스크리닝 결과 LLM 보고서를 생성/전송하는 중입니다...",
            accepts_progress=True,
            fn=lambda progress_emit: generate_screening_llm_reports(
                market_service=self.market_service,
                llm_config=self.session_state.llm_config,
                telegram_config=self.telegram_config,
                report_config=replace(self.screening_report_config, send_summary_to_telegram=False),
                matched_listing=pd.DataFrame([row]),
                parsed_filter=self._report_queue_filter,
                progress_callback=progress_emit,
                cancel_checker=lambda: self._report_cancel_requested,
            ),
            on_success=self._on_screening_reports_done,
            on_progress=self._on_screening_report_progress,
            on_failure=self._on_screening_reports_failed,
        )

    def _finish_report_queue(self, state: str) -> None:
        self.report_queue_timer.stop()
        self._report_queue.clear()
        self.stock_panel.set_screening_running(False)
        self._report_running = False
        self._report_cancel_requested = False
        text = (
            f"LLM 보고서 큐 {state} · 저장 {self._report_queue_saved} · "
            f"전송 {self._report_queue_sent} · 실패 {self._report_queue_failed}"
        )
        self.stock_panel.set_screening_progress(text)
        self.statusBar().showMessage(text, 6000)

    def _stop_report_queue(self) -> None:
        self._report_cancel_requested = True
        self.report_queue_timer.stop()
        self.statusBar().showMessage("LLM 보고서 큐 중지를 요청했습니다.", 4000)

    def _clear_report_queue(self) -> None:
        self._report_queue.clear()
        self.report_queue_timer.stop()
        if not self._report_running:
            self._finish_report_queue("비움")

    def _on_screening_report_progress(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        done = int(payload.get("done", 0))
        total = int(payload.get("total", 0))
        saved = int(payload.get("saved", 0))
        telegram_sent = int(payload.get("telegram_sent", 0))
        failures = int(payload.get("failures", 0))
        current_name = str(payload.get("current_name", ""))
        current_code = str(payload.get("current_code", ""))
        stopped = bool(payload.get("stopped", False))
        prefix = "보고서 중지됨 · " if stopped else "LLM 보고서 생성/전송 "
        text = f"{prefix}{done} / {total} · 저장 {saved} · 전송 {telegram_sent} · 실패 {failures}"
        if current_code:
            text += f" · {current_name}({current_code})"
        self.stock_panel.set_screening_progress(text)
        self.statusBar().showMessage(text)

    def _on_screening_reports_done(self, task: WorkerTask) -> None:
        summary: ScreeningReportSummary = task.payload
        self._report_running = False
        self._report_queue_saved += summary.saved
        self._report_queue_sent += summary.telegram_sent
        self._report_queue_failed += summary.failures
        processed = self._report_queue_total - len(self._report_queue)
        text = (
            f"LLM 보고서 {processed} / {self._report_queue_total} · "
            f"대기 {len(self._report_queue)} · 저장 {self._report_queue_saved} · "
            f"전송 {self._report_queue_sent} · 실패 {self._report_queue_failed}"
        )
        if summary.deleted_old_reports:
            text += f" · 오래된 파일 {summary.deleted_old_reports}개 정리"
        self.stock_panel.set_screening_progress(text)
        self.statusBar().showMessage(f"{text} · {summary.summary_path}", 7000)
        if self._report_cancel_requested or not self._report_queue:
            self._finish_report_queue("완료" if not self._report_cancel_requested else "중지됨")
            return
        if self.screening_report_config.llm_report_queue_enabled:
            interval_ms = self.screening_report_config.llm_report_interval_minutes * 60 * 1000
            self.report_queue_timer.start(interval_ms)
        else:
            self._process_next_queued_report()

    def _on_screening_reports_failed(self, message: str) -> None:
        self._report_running = False
        self._report_queue_failed += 1
        self.stock_panel.set_screening_progress(f"LLM 보고서 실패 · {message}")
        self._handle_background_error(message)
        if self._report_queue and not self._report_cancel_requested:
            if self.screening_report_config.llm_report_queue_enabled:
                interval_ms = self.screening_report_config.llm_report_interval_minutes * 60 * 1000
                self.report_queue_timer.start(interval_ms)
            else:
                self._process_next_queued_report()
        else:
            self._finish_report_queue("실패")

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = max(0, int(seconds))
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{sec:02d}"
        return f"{minutes:02d}:{sec:02d}"

    def _load_price_history(self, stock: StockReference) -> None:
        self.current_stock = stock
        self._run_scoped_worker(
            channel=self.CHANNEL_PRICE,
            task_name="price_history",
            status_message=f"{stock.display_name} 가격 데이터를 불러오는 중입니다...",
            fn=lambda: (
                stock,
                add_indicators(self.market_service.load_price_history(stock)),
                self.market_service.load_fundamental_snapshot(stock),
            ),
            on_success=self._on_price_history_loaded,
            on_failure=lambda message, current_stock=stock: self._handle_price_history_failure(current_stock, message),
        )

    def _on_price_history_loaded(self, task: WorkerTask) -> None:
        stock, frame, snapshot = task.payload
        if frame.empty:
            raise ValueError("표시할 가격 데이터가 없습니다.")

        self.current_stock = stock
        self.current_price_frame = frame
        self.current_fundamental_snapshot = snapshot
        chart_window = self._ensure_chart_window()
        chart_window.setWindowTitle(f"차트 - {stock.display_name}")
        chart_window.chart_panel.set_price_data(stock.display_name, frame, preset=self.session_state.chart_preset)
        chart_window.reveal()

        self._finalize_restore_after_price_load()

        self._refresh_workspace_context()
        self.statusBar().showMessage(f"{stock.display_name} 차트와 리포트를 갱신했습니다.", 4000)

    def _handle_price_history_failure(self, stock: StockReference, message: str) -> None:
        self.statusBar().showMessage(f"{stock.display_name} 종목을 목록에서 제외했습니다. {message}", 6000)
        self._clear_active_stock_context()
        self.current_listing = self.current_listing[
            ~(
                (self.current_listing["Code"].astype(str) == stock.code)
                & (self.current_listing["Market"].astype(str) == stock.market)
            )
        ].reset_index(drop=True)
        self.stock_panel.set_listing(self.current_listing, auto_activate=False)
        self._refresh_workspace_context()

    def _open_llm_settings(self) -> None:
        dialog = LLMSettingsDialog(self.session_state.llm_config, self)
        if dialog.exec():
            self.session_state.llm_config = dialog.get_config()
            self._persist_app_configs()
            self.statusBar().showMessage("LLM 연결 설정을 갱신했습니다.", 4000)
            self._refresh_workspace_context()

    def _open_telegram_settings(self) -> None:
        dialog = TelegramSettingsDialog(self.telegram_config, self)
        if dialog.exec():
            self.telegram_config = dialog.get_config()
            self._persist_app_configs()
            self.statusBar().showMessage("Telegram 설정을 갱신했습니다.", 4000)

    def _open_kiwoom_settings(self) -> None:
        dialog = KiwoomSettingsDialog(self.kiwoom_config, self)
        if dialog.exec():
            self.kiwoom_config = dialog.get_config()
            self.market_service = MarketService(self.kiwoom_config)
            self._persist_app_configs()
            self.statusBar().showMessage("Kiwoom REST 설정을 갱신했습니다.", 4000)
            if self.kiwoom_config.connection_ready:
                self._load_listing(self.stock_panel.current_market_scope())

    def _test_kiwoom_connection(self) -> None:
        if not self.kiwoom_config.connection_ready:
            self._show_error("Kiwoom REST appkey/secretkey와 backend 사용 여부를 확인하세요.")
            return
        self._run_scoped_worker(
            channel=self.CHANNEL_KIWOOM_TEST,
            task_name="kiwoom_test",
            status_message="Kiwoom REST 연결 테스트 중입니다...",
            fn=self.market_service.test_connection,
            on_success=self._on_kiwoom_test_completed,
            modal_error=True,
        )

    def _on_kiwoom_test_completed(self, task: WorkerTask) -> None:
        self.analysis_panel.set_result_markdown(f"## Kiwoom REST 연결 테스트\n\n{task.payload}")
        self.statusBar().showMessage("Kiwoom REST 연결 테스트가 완료되었습니다.", 4000)

    def _test_llm_connection(self) -> None:
        if not self.session_state.llm_config.connection_ready:
            self._show_error("LLM 연결 정보를 먼저 입력하세요.")
            return
        self._run_scoped_worker(
            channel=self.CHANNEL_LLM_TEST,
            task_name="llm_test",
            status_message="LLM 연결 테스트 중입니다...",
            fn=lambda: run_connection_test(self.session_state.llm_config),
            on_success=self._on_llm_test_completed,
        )

    def _on_llm_test_completed(self, task: WorkerTask) -> None:
        self.analysis_panel.set_result_markdown(f"## LLM 연결 테스트\n\n{task.payload}")
        self.statusBar().showMessage("LLM 연결 테스트가 완료되었습니다.", 4000)

    def _run_llm_analysis(self, user_request: str) -> None:
        if self.current_stock is None or self.current_price_frame is None:
            self._show_error("먼저 차트에 표시할 종목을 선택하세요.")
            return
        if not self.session_state.llm_config.connection_ready:
            self._show_error("LLM 연결 설정이 필요합니다.")
            return

        stock = self.current_stock
        frame = self.current_price_frame.copy()
        snapshot = self.current_fundamental_snapshot
        filter_prompt = self.stock_panel.filter_prompt()
        config = self.session_state.llm_config
        active_layers = self.session_state.active_prompt_layers.copy()
        self._run_scoped_worker(
            channel=self.CHANNEL_LLM_ANALYSIS,
            task_name="llm_analysis",
            status_message="LLM 분석 요청을 전송하는 중입니다...",
            fn=lambda: run_stock_analysis(
                config=config,
                active_layer_ids=active_layers,
                stock=stock,
                frame=frame,
                filter_prompt=filter_prompt,
                user_request=user_request,
                fundamental_snapshot=snapshot,
            ),
            on_success=self._on_llm_analysis_completed,
        )

    def _on_llm_analysis_completed(self, task: WorkerTask) -> None:
        self.analysis_panel.set_result_markdown(task.payload)
        self.statusBar().showMessage("LLM 분석이 완료되었습니다.", 4000)

    def _send_context_report(self) -> None:
        self._send_markdown_to_telegram("Market Viewer 세션 리포트", self.analysis_panel.context_markdown())

    def _send_llm_report(self) -> None:
        self._send_markdown_to_telegram("Market Viewer LLM 리포트", self.analysis_panel.result_markdown())

    def _send_markdown_to_telegram(self, title: str, markdown: str) -> None:
        if not self.telegram_config.connection_ready:
            self._show_error("Telegram Bot Token과 Chat ID를 먼저 설정하세요.")
            return
        if not markdown.strip():
            self._show_error("전송할 리포트 내용이 없습니다.")
            return

        self._run_scoped_worker(
            channel=self.CHANNEL_TELEGRAM,
            task_name="telegram_send",
            status_message="Telegram으로 리포트를 전송하는 중입니다...",
            fn=lambda: send_telegram_report(self.telegram_config, title, markdown),
            on_success=self._on_telegram_send_completed,
        )

    def _on_telegram_send_completed(self, task: WorkerTask) -> None:
        chunk_count = int(task.payload)
        self.statusBar().showMessage(f"Telegram 전송이 완료되었습니다. ({chunk_count}개 메시지)", 5000)

    def _toggle_prompt_layer(self, layer_id: str, checked: bool) -> None:
        active = self.session_state.active_prompt_layers
        if checked and layer_id not in active:
            active.append(layer_id)
        if not checked and layer_id in active:
            active.remove(layer_id)
        self._refresh_workspace_context()

    def _sync_prompt_layer_actions(self) -> None:
        active = set(self.session_state.active_prompt_layers)
        for layer_id, action in self._prompt_layer_actions.items():
            action.blockSignals(True)
            action.setChecked(layer_id in active)
            action.blockSignals(False)

    def _reveal_chart_window(self) -> None:
        self._ensure_chart_window().reveal()

    def _set_chart_preset(self, preset: str) -> None:
        self.session_state.chart_preset = preset
        if self.chart_window is not None:
            self.chart_window.chart_panel.apply_preset(preset)
        self._refresh_workspace_context()

    def _build_session_state(self) -> AppSessionState:
        chart_start: str | None = None
        chart_end: str | None = None
        chart_tab_index = 0
        if self.chart_window is not None:
            chart_panel = self.chart_window.chart_panel
            chart_start, chart_end = chart_panel.visible_range_as_iso()
            chart_tab_index = chart_panel.current_tab_index()
        return AppSessionState(
            market_scope=self.stock_panel.current_market_scope(),
            selected_stock=self.current_stock,
            filter_prompt=self.stock_panel.filter_prompt(),
            user_request_text=self.analysis_panel.user_request_text(),
            active_prompt_layers=self.session_state.active_prompt_layers.copy(),
            chart_preset=self.session_state.chart_preset,
            chart_visible_start=chart_start,
            chart_visible_end=chart_end,
            chart_tab_index=chart_tab_index,
            splitter_sizes=self.splitter.sizes(),
            llm_config=self.session_state.llm_config,
        )

    def _save_session(self) -> None:
        path = self.session_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "세션 저장", "session.yaml", "YAML Files (*.yaml *.yml)")
        if not path:
            return
        state = self._build_session_state()
        save_session(path, state)
        self.session_path = path
        self.statusBar().showMessage(f"세션을 저장했습니다: {path}", 4000)

    def _open_session(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "세션 불러오기", "", "YAML Files (*.yaml *.yml)")
        if not path:
            return
        state = load_session(path)
        state.llm_config = self.session_state.llm_config
        self.session_path = path
        self._pending_restore = state
        self.session_state = state
        self.stock_panel.set_market_scope(state.market_scope)
        self.stock_panel.set_filter_prompt(state.filter_prompt)
        self.analysis_panel.set_user_request_text(state.user_request_text)
        self._sync_prompt_layer_actions()
        self._load_listing(state.market_scope)

    def _refresh_workspace_context(self) -> None:
        if self._is_closing:
            return
        active_layer_names = []
        for layer_id in self.session_state.active_prompt_layers:
            layer = get_prompt_layer(layer_id)
            if layer:
                active_layer_names.append(layer.name)
        markdown = build_workspace_context_markdown(
            market_scope=self.stock_panel.current_market_scope() or self.session_state.market_scope,
            stock=self.current_stock,
            filter_prompt=self.stock_panel.filter_prompt(),
            active_layer_names=active_layer_names,
            llm_config=self.session_state.llm_config,
            chart_range_text=self._chart_range_text(),
            price_frame=self.current_price_frame,
            fundamental_snapshot=self.current_fundamental_snapshot,
        )
        self.analysis_panel.set_context_markdown(markdown)
        self.analysis_panel.set_context_table_rows(
            build_report_rows(self.current_stock, self.current_price_frame, self.current_fundamental_snapshot)
        )

    def _show_current_status(self) -> None:
        if self._is_closing:
            return
        QMessageBox.information(
            self,
            "현재 상태",
            "Current_Status.md 파일에 현재 구현 상태와 남은 작업을 기록했습니다.",
        )

    def _show_error(self, message: str) -> None:
        self.statusBar().showMessage("오류가 발생했습니다.", 4000)
        if self._is_closing:
            return
        QMessageBox.critical(self, "오류", message)

    def _handle_background_error(self, message: str, *, modal: bool = False) -> None:
        self.statusBar().showMessage(message, 6000)
        if self._is_closing or not modal:
            return
        QMessageBox.critical(self, "오류", message)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._is_closing = True
        if self.chart_window is not None:
            self.chart_window.prepare_for_shutdown()
        self.thread_pool.clear()
        self.thread_pool.waitForDone(2000)
        self._active_workers.clear()
        super().closeEvent(event)
