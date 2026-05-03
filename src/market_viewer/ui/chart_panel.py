from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import math

import pandas as pd
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget


@dataclass(slots=True)
class ChartSeries:
    dates: list[pd.Timestamp]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]
    ma5: list[float | None]
    ma20: list[float | None]
    ma60: list[float | None]

    @property
    def count(self) -> int:
        return len(self.close)


class PriceChartWidget(QWidget):
    range_changed = Signal(float, float)
    reset_requested = Signal()

    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode
        self._series: ChartSeries | None = None
        self._title = ""
        self._visible_start = 0.0
        self._visible_end = 0.0
        self._drag_origin: QPoint | None = None
        self._hover_pos: QPointF | None = None
        self._ui_active = True
        self.setMouseTracking(True)
        self.setMinimumSize(620, 420)

    def begin_shutdown(self) -> None:
        self._ui_active = False
        self._series = None
        self._drag_origin = None
        self._hover_pos = None

    def set_chart_data(self, title: str, series: ChartSeries) -> None:
        self._title = title
        self._series = series
        self._visible_start = 0.0
        self._visible_end = float(max(0, series.count - 1))
        self.update()

    def set_visible_range(self, start: float, end: float) -> None:
        series = self._series
        if not self._ui_active or series is None or series.count == 0:
            return
        full_min = 0.0
        full_max = float(max(0, series.count - 1))
        full_span = max(1.0, full_max - full_min)
        requested_span = min(max(5.0, end - start), max(5.0, full_span))
        start = max(full_min, start)
        end = start + requested_span
        if end > full_max:
            end = full_max
            start = max(full_min, end - requested_span)
        self._visible_start = float(start)
        self._visible_end = float(end)
        self.range_changed.emit(self._visible_start, self._visible_end)
        self.update()

    def visible_range(self) -> tuple[float, float]:
        return self._visible_start, self._visible_end

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f8fafc"))
        if not self._ui_active or self._series is None or self._series.count == 0:
            self._draw_empty(painter)
            return

        plot = self._plot_rect()
        painter.setPen(QPen(QColor("#d8dee8"), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(plot)

        start = max(0, int(math.floor(self._visible_start)))
        end = min(self._series.count - 1, int(math.ceil(self._visible_end)))
        if end <= start:
            self._draw_empty(painter)
            return

        y_min, y_max = self._price_range(start, end)
        self._draw_grid(painter, plot, y_min, y_max)
        self._draw_title(painter)
        self._draw_dates(painter, plot, start, end)
        self._draw_volume(painter, plot, start, end)
        if self.mode == "candles":
            self._draw_candles(painter, plot, start, end, y_min, y_max)
            self._draw_ma_lines(painter, plot, start, end, y_min, y_max)
        else:
            self._draw_line(painter, plot, start, end, y_min, y_max, self._series.close, QColor("#1d3557"), 2.0)
        self._draw_hover(painter, plot, start, end, y_min, y_max)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._hover_pos = event.position()
        if self._drag_origin is not None and self._series is not None:
            delta_x = event.position().x() - self._drag_origin.x()
            span = self._visible_end - self._visible_start
            shift = -(delta_x / max(1, self._plot_rect().width())) * span
            self.set_visible_range(self._visible_start + shift, self._visible_end + shift)
            self._drag_origin = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.reset_requested.emit()

    def leaveEvent(self, event) -> None:
        self._hover_pos = None
        self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._series is None:
            return
        factor = 0.8 if event.angleDelta().y() > 0 else 1.25
        center = (self._visible_start + self._visible_end) / 2
        half = max(5.0, ((self._visible_end - self._visible_start) * factor) / 2)
        self.set_visible_range(center - half, center + half)
        event.accept()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update()

    def _plot_rect(self) -> QRectF:
        return QRectF(58, 42, max(120, self.width() - 82), max(120, self.height() - 98))

    def _draw_empty(self, painter: QPainter) -> None:
        painter.setPen(QColor("#64748b"))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "차트 데이터 없음")

    def _draw_title(self, painter: QPainter) -> None:
        painter.setPen(QColor("#111827"))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QPointF(58, 26), self._title)
        font.setBold(False)
        painter.setFont(font)

    def _draw_grid(self, painter: QPainter, plot: QRectF, y_min: float, y_max: float) -> None:
        painter.setPen(QPen(QColor("#e5eaf0"), 1))
        for step in range(5):
            ratio = step / 4
            y = plot.bottom() - plot.height() * ratio
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            value = y_min + (y_max - y_min) * ratio
            painter.setPen(QColor("#64748b"))
            painter.drawText(QPointF(6, y + 4), f"{value:,.0f}")
            painter.setPen(QPen(QColor("#e5eaf0"), 1))

    def _draw_dates(self, painter: QPainter, plot: QRectF, start: int, end: int) -> None:
        series = self._series
        if series is None:
            return
        painter.setPen(QColor("#64748b"))
        seen: set[int] = set()
        for step in range(6):
            ratio = step / 5
            index = round(self._visible_start + (self._visible_end - self._visible_start) * ratio)
            index = max(start, min(end, index))
            if index in seen:
                continue
            seen.add(index)
            x = self._x_for_index(plot, index)
            text = series.dates[index].strftime("%y.%m.%d")
            painter.drawText(QPointF(x - 24, plot.bottom() + 24), text)

    def _draw_volume(self, painter: QPainter, plot: QRectF, start: int, end: int) -> None:
        series = self._series
        if series is None:
            return
        max_volume = max(series.volume[start : end + 1] or [0])
        if max_volume <= 0:
            return
        top = plot.bottom() - plot.height() * 0.22
        painter.fillRect(QRectF(plot.left(), top, plot.width(), plot.bottom() - top), QColor(12, 16, 22, 36))
        bar_width = max(2.0, plot.width() / max(18.0, (end - start + 1) * 1.25))
        for index in range(start, end + 1):
            x = self._x_for_index(plot, index)
            height = (series.volume[index] / max_volume) * (plot.bottom() - top)
            color = QColor("#d84f45" if series.close[index] >= series.open[index] else "#2d7f5e")
            color.setAlpha(150)
            painter.fillRect(QRectF(x - bar_width / 2, plot.bottom() - height, bar_width, height), color)

    def _draw_candles(self, painter: QPainter, plot: QRectF, start: int, end: int, y_min: float, y_max: float) -> None:
        series = self._series
        if series is None:
            return
        candle_width = max(3.0, plot.width() / max(20.0, (end - start + 1) * 1.35))
        for index in range(start, end + 1):
            x = self._x_for_index(plot, index)
            o = self._y_for_price(plot, series.open[index], y_min, y_max)
            h = self._y_for_price(plot, series.high[index], y_min, y_max)
            l = self._y_for_price(plot, series.low[index], y_min, y_max)
            c = self._y_for_price(plot, series.close[index], y_min, y_max)
            up = series.close[index] >= series.open[index]
            color = QColor("#d84f45" if up else "#2d7f5e")
            painter.setPen(QPen(color, 1))
            painter.drawLine(QPointF(x, h), QPointF(x, l))
            top = min(o, c)
            body_height = max(1.0, abs(c - o))
            painter.fillRect(QRectF(x - candle_width / 2, top, candle_width, body_height), color)

    def _draw_ma_lines(self, painter: QPainter, plot: QRectF, start: int, end: int, y_min: float, y_max: float) -> None:
        series = self._series
        if series is None:
            return
        self._draw_optional_line(painter, plot, start, end, y_min, y_max, series.ma5, QColor("#f4a261"), "MA5")
        self._draw_optional_line(painter, plot, start, end, y_min, y_max, series.ma20, QColor("#457b9d"), "MA20")
        self._draw_optional_line(painter, plot, start, end, y_min, y_max, series.ma60, QColor("#6a4c93"), "MA60")

    def _draw_optional_line(
        self,
        painter: QPainter,
        plot: QRectF,
        start: int,
        end: int,
        y_min: float,
        y_max: float,
        values: list[float | None],
        color: QColor,
        label: str,
    ) -> None:
        points = []
        for index in range(start, end + 1):
            value = values[index]
            if value is None or math.isnan(value):
                continue
            points.append(QPointF(self._x_for_index(plot, index), self._y_for_price(plot, value, y_min, y_max)))
        if len(points) < 2:
            return
        painter.setPen(QPen(color, 1.4))
        for left, right in zip(points, points[1:]):
            painter.drawLine(left, right)
        painter.drawText(points[-1] + QPointF(5, -4), label)

    def _draw_line(
        self,
        painter: QPainter,
        plot: QRectF,
        start: int,
        end: int,
        y_min: float,
        y_max: float,
        values: list[float],
        color: QColor,
        width: float,
    ) -> None:
        points = [QPointF(self._x_for_index(plot, index), self._y_for_price(plot, values[index], y_min, y_max)) for index in range(start, end + 1)]
        painter.setPen(QPen(color, width))
        for left, right in zip(points, points[1:]):
            painter.drawLine(left, right)

    def _draw_hover(self, painter: QPainter, plot: QRectF, start: int, end: int, y_min: float, y_max: float) -> None:
        series = self._series
        if series is None or self._hover_pos is None or not plot.contains(self._hover_pos):
            return
        ratio = (self._hover_pos.x() - plot.left()) / max(1.0, plot.width())
        index = round(self._visible_start + (self._visible_end - self._visible_start) * ratio)
        index = max(start, min(end, index))
        x = self._x_for_index(plot, index)
        y = self._y_for_price(plot, series.close[index], y_min, y_max)
        painter.setPen(QPen(QColor("#94a3b8"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
        painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        previous = series.close[index - 1] if index > 0 else series.close[index]
        change = ((series.close[index] / previous) - 1) * 100 if previous else 0.0
        lines = [
            series.dates[index].strftime("%Y-%m-%d"),
            f"O {series.open[index]:,.0f}  H {series.high[index]:,.0f}",
            f"L {series.low[index]:,.0f}  C {series.close[index]:,.0f} ({change:+.2f}%)",
            f"V {series.volume[index]:,.0f}",
        ]
        metrics = painter.fontMetrics()
        width = max(metrics.horizontalAdvance(line) for line in lines) + 16
        height = metrics.height() * len(lines) + 16
        box = QRectF(plot.left() + 10, plot.top() + 10, width, height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(15, 23, 42, 218))
        painter.drawRoundedRect(box, 6, 6)
        painter.setPen(QColor("#f8fafc"))
        for line_index, line in enumerate(lines):
            painter.drawText(QPointF(box.left() + 8, box.top() + 12 + metrics.height() * (line_index + 0.8)), line)

    def _price_range(self, start: int, end: int) -> tuple[float, float]:
        series = self._series
        if series is None:
            return 0.0, 1.0
        values = series.close[start : end + 1] if self.mode == "line" else series.low[start : end + 1] + series.high[start : end + 1]
        values = [value for value in values if value == value]
        y_min = min(values) if values else 0.0
        y_max = max(values) if values else 1.0
        if y_min == y_max:
            padding = y_max * 0.05 if y_max else 1.0
        else:
            padding = (y_max - y_min) * 0.08
        return y_min - padding, y_max + padding

    def _x_for_index(self, plot: QRectF, index: int) -> float:
        span = max(1.0, self._visible_end - self._visible_start)
        return plot.left() + ((index - self._visible_start) / span) * plot.width()

    @staticmethod
    def _y_for_price(plot: QRectF, value: float, y_min: float, y_max: float) -> float:
        span = max(1.0, y_max - y_min)
        return plot.bottom() - ((value - y_min) / span) * plot.height()


class ChartPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.current_preset = "1Y"
        self._ui_active = True
        self._frame: pd.DataFrame | None = None
        self._series: ChartSeries | None = None
        self._visible_start_index: float | None = None
        self._visible_end_index: float | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs)
        self.candles_view = PriceChartWidget("candles")
        self.line_view = PriceChartWidget("line")
        self.candles_view.range_changed.connect(self._sync_visible_range_from_child)
        self.line_view.range_changed.connect(self._sync_visible_range_from_child)
        self.candles_view.reset_requested.connect(self.reset_range)
        self.line_view.reset_requested.connect(self.reset_range)
        self.tabs.addTab(self.candles_view, "봉차트")
        self.tabs.addTab(self.line_view, "선 그래프")

    def begin_shutdown(self) -> None:
        if not self._ui_active:
            return
        self._ui_active = False
        self.candles_view.begin_shutdown()
        self.line_view.begin_shutdown()

    def set_price_data(self, stock_name: str, frame, preset: str = "1Y") -> None:
        if not self._ui_active:
            return
        self._frame = frame.reset_index(drop=True).copy()
        self._series = self._to_series(self._frame)
        self.candles_view.set_chart_data(f"{stock_name} 봉차트", self._series)
        self.line_view.set_chart_data(f"{stock_name} 종가 추이", self._series)
        self.current_preset = preset
        self.apply_preset(preset)

    def current_tab_index(self) -> int:
        return self.tabs.currentIndex()

    def set_tab_index(self, index: int) -> None:
        self.tabs.setCurrentIndex(max(0, min(index, self.tabs.count() - 1)))

    def apply_preset(self, preset: str) -> None:
        if not self._ui_active or self._frame is None or self._frame.empty:
            return
        self.current_preset = preset
        total_rows = len(self._frame)
        end_index = float(max(0, total_rows - 1))
        if preset == "ALL":
            self._apply_visible_range(0.0, end_index)
            return

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
        if None in (self._visible_start_index, self._visible_end_index):
            return
        span = self._visible_end_index - self._visible_start_index
        shift = span * delta_ratio
        self._apply_visible_range(self._visible_start_index + shift, self._visible_end_index + shift)

    def zoom_relative(self, factor: float) -> None:
        if None in (self._visible_start_index, self._visible_end_index):
            return
        center = (self._visible_start_index + self._visible_end_index) / 2
        half_span = max(5.0, ((self._visible_end_index - self._visible_start_index) * factor) / 2)
        self._apply_visible_range(center - half_span, center + half_span)

    def reset_range(self) -> None:
        self.apply_preset(self.current_preset)

    def set_visible_range_from_iso(self, start_iso: str | None, end_iso: str | None) -> None:
        if self._frame is None or self._frame.empty or not start_iso or not end_iso:
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

    def _apply_visible_range(self, start: float, end: float) -> None:
        self.candles_view.set_visible_range(start, end)
        self.line_view.set_visible_range(start, end)

    def _sync_visible_range_from_child(self, start: float, end: float) -> None:
        self._visible_start_index = start
        self._visible_end_index = end
        sender = self.sender()
        if sender is not self.candles_view:
            self.candles_view.blockSignals(True)
            self.candles_view.set_visible_range(start, end)
            self.candles_view.blockSignals(False)
        if sender is not self.line_view:
            self.line_view.blockSignals(True)
            self.line_view.set_visible_range(start, end)
            self.line_view.blockSignals(False)

    @staticmethod
    def _to_series(frame: pd.DataFrame) -> ChartSeries:
        def optional(column: str) -> list[float | None]:
            if column not in frame:
                return [None] * len(frame)
            values: list[float | None] = []
            for value in frame[column]:
                if pd.isna(value):
                    values.append(None)
                else:
                    values.append(float(value))
            return values

        return ChartSeries(
            dates=[pd.Timestamp(value) for value in frame["Date"]],
            open=[float(value) for value in frame["Open"]],
            high=[float(value) for value in frame["High"]],
            low=[float(value) for value in frame["Low"]],
            close=[float(value) for value in frame["Close"]],
            volume=[float(value) for value in frame["Volume"]],
            ma5=optional("MA5"),
            ma20=optional("MA20"),
            ma60=optional("MA60"),
        )
