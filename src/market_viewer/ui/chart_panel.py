from __future__ import annotations

import threading
from datetime import timedelta

from PySide6.QtCharts import QCandlestickSeries, QCandlestickSet, QChart, QLineSeries, QValueAxis
from PySide6.QtCore import QPointF, QThread, QTimer, Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from market_viewer.ui.interactive_chart_view import InteractiveChartView


class ChartPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.current_preset = "1Y"
        self._ui_active = True
        self._full_min_index: float | None = None
        self._full_max_index: float | None = None
        self._visible_start_index: float | None = None
        self._visible_end_index: float | None = None
        self._frame = None
        self._date_labels: list[str] = []
        self._pending_chart_payload: tuple[str, object, str] | None = None
        self._pending_hover_payload: tuple[InteractiveChartView, float, float] | None = None
        self._chart_update_in_progress = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs)

        self.candles_chart = QChart()
        self.candles_chart.legend().setVisible(True)
        self.candles_chart.setMargins(self.candles_chart.margins())
        margins = self.candles_chart.margins()
        margins.setBottom(28)
        self.candles_chart.setMargins(margins)
        self.candles_view = InteractiveChartView(self.candles_chart)
        self._wire_interaction(self.candles_view)

        self.line_chart = QChart()
        self.line_chart.legend().setVisible(True)
        self.line_chart.setMargins(self.line_chart.margins())
        line_margins = self.line_chart.margins()
        line_margins.setBottom(28)
        self.line_chart.setMargins(line_margins)
        self.line_view = InteractiveChartView(self.line_chart)
        self._wire_interaction(self.line_view)

        self._create_candles_chart_objects()
        self._create_line_chart_objects()

        self._chart_update_timer = QTimer(self)
        self._chart_update_timer.setSingleShot(True)
        self._chart_update_timer.setInterval(33)
        self._chart_update_timer.timeout.connect(self._flush_pending_chart_update)

        self._hover_update_timer = QTimer(self)
        self._hover_update_timer.setSingleShot(True)
        self._hover_update_timer.setInterval(16)
        self._hover_update_timer.timeout.connect(self._flush_pending_hover_update)

        self.tabs.addTab(self.candles_view, "봉차트")
        self.tabs.addTab(self.line_view, "선 그래프")

    def _create_candles_chart_objects(self) -> None:
        self._candlestick_series = QCandlestickSeries(self.candles_chart)
        self._candlestick_series.setName("일봉")
        self._candlestick_series.setIncreasingColor(QColor("#d84f45"))
        self._candlestick_series.setDecreasingColor(QColor("#2d7f5e"))
        self._candlestick_series.setBodyWidth(0.7)

        self._candles_close_reference = QLineSeries(self.candles_chart)
        self._candles_close_reference.setName("close-reference")
        self._candles_close_reference.setVisible(False)

        self._ma5_series = QLineSeries(self.candles_chart)
        self._ma5_series.setName("MA5")
        self._ma5_series.setPen(QPen(QColor("#f4a261"), 1.5))

        self._ma20_series = QLineSeries(self.candles_chart)
        self._ma20_series.setName("MA20")
        self._ma20_series.setPen(QPen(QColor("#457b9d"), 1.5))

        self._ma60_series = QLineSeries(self.candles_chart)
        self._ma60_series.setName("MA60")
        self._ma60_series.setPen(QPen(QColor("#6a4c93"), 1.5))

        self._candles_x_axis = QValueAxis(self.candles_chart)
        self._candles_x_axis.setLabelsVisible(False)
        self._candles_x_axis.setTickCount(6)
        self._candles_y_axis = QValueAxis(self.candles_chart)
        self._candles_y_axis.setLabelFormat("%.0f")

        self.candles_chart.addSeries(self._candlestick_series)
        self.candles_chart.addSeries(self._candles_close_reference)
        self.candles_chart.addSeries(self._ma5_series)
        self.candles_chart.addSeries(self._ma20_series)
        self.candles_chart.addSeries(self._ma60_series)
        self.candles_chart.addAxis(self._candles_x_axis, Qt.AlignmentFlag.AlignBottom)
        self.candles_chart.addAxis(self._candles_y_axis, Qt.AlignmentFlag.AlignLeft)

        for series in (
            self._candlestick_series,
            self._candles_close_reference,
            self._ma5_series,
            self._ma20_series,
            self._ma60_series,
        ):
            series.attachAxis(self._candles_x_axis)
            series.attachAxis(self._candles_y_axis)

    def _create_line_chart_objects(self) -> None:
        self._line_close_reference = QLineSeries(self.line_chart)
        self._line_close_reference.setName("종가")
        self._line_close_reference.setPen(QPen(QColor("#1d3557"), 2.0))

        self._line_x_axis = QValueAxis(self.line_chart)
        self._line_x_axis.setLabelsVisible(False)
        self._line_x_axis.setTickCount(6)
        self._line_y_axis = QValueAxis(self.line_chart)
        self._line_y_axis.setLabelFormat("%.0f")

        self.line_chart.addSeries(self._line_close_reference)
        self.line_chart.addAxis(self._line_x_axis, Qt.AlignmentFlag.AlignBottom)
        self.line_chart.addAxis(self._line_y_axis, Qt.AlignmentFlag.AlignLeft)
        self._line_close_reference.attachAxis(self._line_x_axis)
        self._line_close_reference.attachAxis(self._line_y_axis)

    def _wire_interaction(self, view: InteractiveChartView) -> None:
        view.pan_requested.connect(self.pan_relative)
        view.zoom_requested.connect(self.zoom_relative)
        view.reset_requested.connect(self.reset_range)
        view.hover_position_changed.connect(lambda x, y, source=view: self._queue_hover(source, x, y))
        view.hover_left.connect(self._clear_hover)
        view.geometry_changed.connect(self._update_volume_overlays)

    def begin_shutdown(self) -> None:
        if not self._ui_active:
            return
        self._ui_active = False
        self._pending_chart_payload = None
        self._pending_hover_payload = None
        self._chart_update_timer.stop()
        self._hover_update_timer.stop()
        self.candles_view.begin_shutdown()
        self.line_view.begin_shutdown()

    def set_price_data(self, stock_name: str, frame, preset: str = "1Y") -> None:
        if not self._ui_active:
            return
        self._pending_chart_payload = (stock_name, frame.copy(), preset)
        self._chart_update_timer.start()

    def current_tab_index(self) -> int:
        return self.tabs.currentIndex()

    def set_tab_index(self, index: int) -> None:
        self.tabs.setCurrentIndex(max(0, min(index, self.tabs.count() - 1)))

    def apply_preset(self, preset: str) -> None:
        if not self._ui_active or self._frame is None or self._frame.empty:
            return
        self.current_preset = preset
        total_rows = len(self._frame)
        if preset == "ALL":
            self._apply_visible_range(0.0, float(max(0, total_rows - 1)))
            return

        end_index = float(max(0, total_rows - 1))
        end_dt = self._frame.iloc[-1]["Date"].to_pydatetime()
        if preset == "3M":
            start_dt = end_dt - timedelta(days=93)
        elif preset == "6M":
            start_dt = end_dt - timedelta(days=186)
        else:
            start_dt = end_dt - timedelta(days=366)

        start_index = 0
        for index, value in enumerate(self._frame["Date"]):
            if value.to_pydatetime() >= start_dt:
                start_index = index
                break
        self._apply_visible_range(float(start_index), end_index)

    def pan_relative(self, delta_ratio: float) -> None:
        if not self._ui_active:
            return
        if None in (self._visible_start_index, self._visible_end_index, self._full_min_index, self._full_max_index):
            return
        span = self._visible_end_index - self._visible_start_index
        shift = span * delta_ratio
        self._apply_visible_range(self._visible_start_index + shift, self._visible_end_index + shift)

    def zoom_relative(self, factor: float) -> None:
        if not self._ui_active or None in (self._visible_start_index, self._visible_end_index):
            return
        center = (self._visible_start_index + self._visible_end_index) / 2
        half_span = max(5.0, ((self._visible_end_index - self._visible_start_index) * factor) / 2)
        self._apply_visible_range(center - half_span, center + half_span)

    def reset_range(self) -> None:
        if not self._ui_active:
            return
        self.apply_preset(self.current_preset)

    def set_visible_range_from_iso(self, start_iso: str | None, end_iso: str | None) -> None:
        if not self._ui_active or self._frame is None or self._frame.empty or not start_iso or not end_iso:
            return
        start_index = 0
        end_index = len(self._frame) - 1
        for index, value in enumerate(self._frame["Date"]):
            iso = value.strftime("%Y-%m-%dT00:00:00")
            if iso >= start_iso and start_index == 0:
                start_index = index
            if iso <= end_iso:
                end_index = index
        self._apply_visible_range(float(start_index), float(end_index))

    def visible_range_as_iso(self) -> tuple[str | None, str | None]:
        if self._frame is None or self._frame.empty or self._visible_start_index is None or self._visible_end_index is None:
            return None, None
        start_index = max(0, min(len(self._frame) - 1, round(self._visible_start_index)))
        end_index = max(0, min(len(self._frame) - 1, round(self._visible_end_index)))
        start = self._frame.iloc[start_index]["Date"].strftime("%Y-%m-%dT00:00:00")
        end = self._frame.iloc[end_index]["Date"].strftime("%Y-%m-%dT00:00:00")
        return start, end

    def describe_visible_range(self) -> str:
        start, end = self.visible_range_as_iso()
        if not start or not end:
            return "미설정"
        return f"{start[:10]} ~ {end[:10]}"

    def _flush_pending_chart_update(self) -> None:
        if not self._ui_active or self._pending_chart_payload is None:
            return
        if self.thread() != QThread.currentThread():
            raise RuntimeError("ChartPanel updates must run on the GUI thread.")

        stock_name, frame, preset = self._pending_chart_payload
        self._pending_chart_payload = None
        print(f"[chart] applying update on thread={threading.current_thread().name}")

        self._chart_update_in_progress = True
        self._hover_update_timer.stop()
        self._pending_hover_payload = None
        self.candles_view.setUpdatesEnabled(False)
        self.line_view.setUpdatesEnabled(False)
        try:
            self._clear_hover()
            self._frame = frame.reset_index(drop=True)
            self._date_labels = [value.strftime("%Y-%m-%d") for value in self._frame["Date"]]
            self._rebuild_chart_data(stock_name, self._frame)
            self.current_preset = preset
            self.apply_preset(preset)
            self._update_volume_overlays()
        finally:
            self._chart_update_in_progress = False
            self.candles_view.setUpdatesEnabled(True)
            self.line_view.setUpdatesEnabled(True)
            self.candles_view.viewport().update()
            self.line_view.viewport().update()

    def _queue_hover(self, source_view: InteractiveChartView, x_pos: float, y_pos: float) -> None:
        if not self._ui_active or self._chart_update_in_progress:
            return
        self._pending_hover_payload = (source_view, x_pos, y_pos)
        self._hover_update_timer.start()

    def _flush_pending_hover_update(self) -> None:
        if not self._ui_active or self._chart_update_in_progress or self._pending_hover_payload is None:
            return
        source_view, x_pos, y_pos = self._pending_hover_payload
        self._pending_hover_payload = None
        self._handle_hover(source_view, x_pos, y_pos)

    def _rebuild_chart_data(self, stock_name: str, frame) -> None:
        self._candlestick_series.clear()
        self._candles_close_reference.clear()
        self._ma5_series.clear()
        self._ma20_series.clear()
        self._ma60_series.clear()
        self._line_close_reference.clear()

        min_price = None
        max_price = None
        min_close = None
        max_close = None

        candle_sets: list[QCandlestickSet] = []
        candle_close_points: list[QPointF] = []
        ma5_points: list[QPointF] = []
        ma20_points: list[QPointF] = []
        ma60_points: list[QPointF] = []
        close_points: list[QPointF] = []

        for index, (_, row) in enumerate(frame.iterrows()):
            x_value = float(index)
            open_price = float(row["Open"])
            high_price = float(row["High"])
            low_price = float(row["Low"])
            close_price = float(row["Close"])

            candle_sets.append(QCandlestickSet(open_price, high_price, low_price, close_price, x_value))
            point = QPointF(x_value, close_price)
            candle_close_points.append(point)
            close_points.append(point)

            if row["MA5"] == row["MA5"]:
                ma5_points.append(QPointF(x_value, float(row["MA5"])))
            if row["MA20"] == row["MA20"]:
                ma20_points.append(QPointF(x_value, float(row["MA20"])))
            if row["MA60"] == row["MA60"]:
                ma60_points.append(QPointF(x_value, float(row["MA60"])))

            min_price = low_price if min_price is None else min(min_price, low_price)
            max_price = high_price if max_price is None else max(max_price, high_price)
            min_close = close_price if min_close is None else min(min_close, close_price)
            max_close = close_price if max_close is None else max(max_close, close_price)

        for candle_set in candle_sets:
            self._candlestick_series.append(candle_set)
        self._append_points(self._candles_close_reference, candle_close_points)
        self._append_points(self._ma5_series, ma5_points)
        self._append_points(self._ma20_series, ma20_points)
        self._append_points(self._ma60_series, ma60_points)
        self._append_points(self._line_close_reference, close_points)

        self._full_min_index = 0.0
        self._full_max_index = float(max(0, len(frame) - 1))
        self.candles_chart.setTitle(f"{stock_name} 봉차트")
        self.line_chart.setTitle(f"{stock_name} 종가 추이")
        self._set_axis_ranges(min_price, max_price, min_close, max_close)

    @staticmethod
    def _append_points(series: QLineSeries, points: list[QPointF]) -> None:
        for point in points:
            series.append(point)

    def _set_axis_ranges(
        self,
        min_price: float | None,
        max_price: float | None,
        min_close: float | None,
        max_close: float | None,
    ) -> None:
        if self._full_min_index is None or self._full_max_index is None:
            return
        self._candles_x_axis.setRange(self._full_min_index, self._full_max_index)
        self._line_x_axis.setRange(self._full_min_index, self._full_max_index)

        if min_price is not None and max_price is not None:
            padding = (max_price - min_price) * 0.08 if max_price > min_price else max_price * 0.05
            self._candles_y_axis.setRange(min_price - padding, max_price + padding)
        if min_close is not None and max_close is not None:
            padding = (max_close - min_close) * 0.08 if max_close > min_close else max_close * 0.05
            self._line_y_axis.setRange(min_close - padding, max_close + padding)

    def _apply_visible_range(self, start_index: float, end_index: float) -> None:
        if not self._ui_active:
            return
        if self._full_min_index is None or self._full_max_index is None:
            return

        full_span = self._full_max_index - self._full_min_index
        requested_span = max(5.0, end_index - start_index)
        requested_span = min(requested_span, max(5.0, full_span))
        start_index = max(self._full_min_index, start_index)
        end_index = start_index + requested_span
        if end_index > self._full_max_index:
            end_index = self._full_max_index
            start_index = max(self._full_min_index, end_index - requested_span)

        self._visible_start_index = float(start_index)
        self._visible_end_index = float(end_index)
        self._candles_x_axis.setRange(self._visible_start_index, self._visible_end_index)
        self._line_x_axis.setRange(self._visible_start_index, self._visible_end_index)
        self._update_bottom_axis_labels()
        self._update_volume_overlays()

    def _update_bottom_axis_labels(self) -> None:
        if self._frame is None or self._frame.empty or self._visible_start_index is None or self._visible_end_index is None:
            self.candles_view.set_bottom_axis_labels([])
            self.line_view.set_bottom_axis_labels([])
            return
        labels = self._build_bottom_axis_labels(self.candles_chart)
        self.candles_view.set_bottom_axis_labels(labels)
        self.line_view.set_bottom_axis_labels(self._build_bottom_axis_labels(self.line_chart))

    def _build_bottom_axis_labels(self, chart: QChart) -> list[tuple[float, str]]:
        if self._frame is None or self._frame.empty or self._visible_start_index is None or self._visible_end_index is None:
            return []
        span = max(1.0, self._visible_end_index - self._visible_start_index)
        tick_count = 6
        labels: list[tuple[float, str]] = []
        seen: set[int] = set()
        for step in range(tick_count):
            ratio = step / max(1, tick_count - 1)
            index = round(self._visible_start_index + span * ratio)
            index = max(0, min(len(self._date_labels) - 1, index))
            if index in seen:
                continue
            seen.add(index)
            x_pos = chart.mapToPosition(QPointF(float(index), 0.0), self._candles_close_reference if chart is self.candles_chart else self._line_close_reference).x()
            labels.append((x_pos, self._format_axis_label(index)))
        return labels

    def _format_axis_label(self, index: int) -> str:
        text = self._date_labels[index]
        if len(self._date_labels) < 2:
            return text
        return text[2:].replace("-", ".")

    def _update_volume_overlays(self) -> None:
        if not self._ui_active or self._chart_update_in_progress:
            return
        if self._frame is None or self._frame.empty:
            self.candles_view.set_volume_overlay([], 0)
            self.line_view.set_volume_overlay([], 0)
            return

        visible_rows = self._frame
        if self._visible_start_index is not None and self._visible_end_index is not None:
            start_index = max(0, int(self._visible_start_index))
            end_index = min(len(self._frame) - 1, int(self._visible_end_index) + 1)
            visible_rows = visible_rows.iloc[start_index : end_index + 1]
        max_volume = float(visible_rows["Volume"].max()) if not visible_rows.empty else 0.0
        self.candles_view.set_volume_overlay(self._build_overlay_bars(self.candles_chart), max_volume)
        self.line_view.set_volume_overlay(self._build_overlay_bars(self.line_chart), max_volume)

    def _build_overlay_bars(self, chart: QChart) -> list[tuple[float, float, bool]]:
        if not self._ui_active or self._frame is None or self._frame.empty:
            return []
        if self._visible_start_index is None or self._visible_end_index is None:
            return []

        bars: list[tuple[float, float, bool]] = []
        series = self._candles_close_reference if chart is self.candles_chart else self._line_close_reference
        start_index = max(0, int(self._visible_start_index))
        end_index = min(len(self._frame) - 1, int(self._visible_end_index) + 1)
        for index in range(start_index, end_index + 1):
            row = self._frame.iloc[index]
            x_pos = chart.mapToPosition(QPointF(float(index), float(row["Close"])), series).x()
            bars.append((x_pos, float(row["Volume"]), float(row["Close"]) >= float(row["Open"])))
        return bars

    def _handle_hover(self, source_view: InteractiveChartView, x_pos: float, y_pos: float) -> None:
        if not self._ui_active or self._chart_update_in_progress or self._frame is None or self._frame.empty:
            return
        plot_area = source_view.chart().plotArea()
        if plot_area.isEmpty() or x_pos < plot_area.left() or x_pos > plot_area.right():
            self._clear_hover()
            return
        row_index = self._nearest_index_from_x(source_view.chart(), x_pos)
        if row_index is None:
            self._clear_hover()
            return

        row = self._frame.iloc[row_index]
        previous_close = None
        if row_index > 0:
            previous_close = float(self._frame.iloc[row_index - 1]["Close"])
        prev_change_pct = 0.0
        if previous_close:
            prev_change_pct = ((float(row["Close"]) / previous_close) - 1) * 100
        lines = [
            pd_timestamp_to_text(row["Date"]),
            f"O {float(row['Open']):,.0f}  H {float(row['High']):,.0f}",
            f"L {float(row['Low']):,.0f}  C {float(row['Close']):,.0f} (전일 {prev_change_pct:+.2f}%)",
            f"V {float(row['Volume']):,.0f}",
        ]
        candles_x = self._map_index_to_x(self.candles_chart, row_index)
        line_x = self._map_index_to_x(self.line_chart, row_index)
        self.candles_view.set_hover_payload(candles_x, y_pos, lines)
        self.line_view.set_hover_payload(line_x, y_pos, lines)

    def _clear_hover(self) -> None:
        if not self._ui_active:
            return
        self._pending_hover_payload = None
        self.candles_view.set_hover_payload(None, None, [])
        self.line_view.set_hover_payload(None, None, [])

    def _nearest_index_from_x(self, chart: QChart, x_pos: float) -> int | None:
        plot_area = chart.plotArea()
        if plot_area.isEmpty() or self._visible_start_index is None or self._visible_end_index is None or self._frame is None:
            return None
        ratio = (x_pos - plot_area.left()) / max(1.0, plot_area.width())
        raw_index = self._visible_start_index + ratio * (self._visible_end_index - self._visible_start_index)
        index = round(raw_index)
        return max(0, min(len(self._frame) - 1, index))

    def _map_index_to_x(self, chart: QChart, row_index: int) -> float:
        series = self._candles_close_reference if chart is self.candles_chart else self._line_close_reference
        close_price = float(self._frame.iloc[row_index]["Close"]) if self._frame is not None else 0.0
        return chart.mapToPosition(QPointF(float(row_index), close_price), series).x()


def pd_timestamp_to_text(value) -> str:
    return value.strftime("%Y-%m-%d")
