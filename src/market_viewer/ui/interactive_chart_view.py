from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtCharts import QChartView
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QWheelEvent


class InteractiveChartView(QChartView):
    pan_requested = Signal(float)
    zoom_requested = Signal(float)
    reset_requested = Signal()
    hover_position_changed = Signal(float, float)
    hover_left = Signal()
    geometry_changed = Signal()

    def __init__(self, chart) -> None:
        super().__init__(chart)
        self._ui_active = True
        self._drag_origin: QPoint | None = None
        self._volume_overlay: list[tuple[float, float, bool]] = []
        self._bottom_axis_labels: list[tuple[float, str]] = []
        self._overlay_max_volume = 0.0
        self._hover_x: float | None = None
        self._hover_y: float | None = None
        self._hover_lines: list[str] = []
        self._hover_visible = False
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRubberBand(QChartView.RubberBand(0))

    def begin_shutdown(self) -> None:
        if not self._ui_active:
            return
        self._ui_active = False
        self._drag_origin = None
        self._volume_overlay = []
        self._bottom_axis_labels = []
        self._overlay_max_volume = 0.0
        self._hover_x = None
        self._hover_y = None
        self._hover_lines = []
        self._hover_visible = False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self._ui_active:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._ui_active:
            return
        self.hover_position_changed.emit(float(event.position().x()), float(event.position().y()))
        if self._drag_origin is not None:
            delta_x = event.position().toPoint().x() - self._drag_origin.x()
            width = max(1, self.viewport().width())
            self.pan_requested.emit(-(delta_x / width))
            self._drag_origin = event.position().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if not self._ui_active:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if not self._ui_active:
            return
        self.reset_requested.emit()
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self._ui_active:
            event.ignore()
            return
        factor = 0.8 if event.angleDelta().y() > 0 else 1.25
        self.zoom_requested.emit(factor)
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._ui_active:
            self.geometry_changed.emit()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._ui_active:
            self.geometry_changed.emit()

    def leaveEvent(self, event) -> None:
        if not self._ui_active:
            super().leaveEvent(event)
            return
        self._hover_visible = False
        self.hover_left.emit()
        self.viewport().update()
        super().leaveEvent(event)

    def set_volume_overlay(self, bars: list[tuple[float, float, bool]], max_volume: float) -> None:
        if not self._ui_active:
            return
        self._volume_overlay = bars
        self._overlay_max_volume = max_volume
        self.viewport().update()

    def set_bottom_axis_labels(self, labels: list[tuple[float, str]]) -> None:
        if not self._ui_active:
            return
        self._bottom_axis_labels = labels
        self.viewport().update()

    def set_hover_payload(self, x_pos: float | None, y_pos: float | None, lines: list[str]) -> None:
        if not self._ui_active:
            return
        self._hover_x = x_pos
        self._hover_y = y_pos
        self._hover_lines = lines
        self._hover_visible = bool(lines and x_pos is not None)
        self.viewport().update()

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawForeground(painter, rect)
        if not self._ui_active:
            return
        plot_area = self.chart().plotArea()
        if plot_area.isEmpty():
            return
        self._draw_volume_overlay(painter, plot_area)
        self._draw_hover_overlay(painter, plot_area)
        self._draw_bottom_axis_labels(painter, plot_area)

    def _draw_volume_overlay(self, painter: QPainter, plot_area: QRectF) -> None:
        if not self._volume_overlay or self._overlay_max_volume <= 0:
            return
        bottom = plot_area.bottom()
        height = plot_area.height() * 0.22
        top = bottom - height

        painter.save()
        painter.setBrush(QColor(12, 16, 22, 92))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(plot_area.left(), top, plot_area.width(), height))
        painter.setPen(QPen(QColor(90, 102, 118, 150), 1))
        painter.drawLine(QPointF(plot_area.left(), top), QPointF(plot_area.right(), top))
        painter.setPen(Qt.PenStyle.NoPen)

        visible_bars = [bar for bar in self._volume_overlay if plot_area.left() - 4 <= bar[0] <= plot_area.right() + 4]
        if not visible_bars:
            painter.restore()
            return

        estimated_width = max(4.0, plot_area.width() / max(18.0, len(visible_bars) * 1.15))
        for x_pos, volume, is_up in visible_bars:
            bar_height = 0 if self._overlay_max_volume <= 0 else (volume / self._overlay_max_volume) * height
            color = QColor("#d84f45" if is_up else "#2d7f5e")
            color.setAlpha(215)
            painter.setBrush(color)
            painter.drawRect(QRectF(x_pos - estimated_width / 2, bottom - bar_height, estimated_width, bar_height))
        painter.restore()

    def _draw_hover_overlay(self, painter: QPainter, plot_area: QRectF) -> None:
        if not self._hover_visible or self._hover_x is None:
            return

        x_pos = self._hover_x
        painter.save()
        painter.setPen(QPen(QColor("#9aa6b2"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(x_pos, plot_area.top()), QPointF(x_pos, plot_area.bottom()))
        if self._hover_y is not None and plot_area.top() <= self._hover_y <= plot_area.bottom():
            painter.drawLine(QPointF(plot_area.left(), self._hover_y), QPointF(plot_area.right(), self._hover_y))

        if self._hover_lines:
            font_metrics = painter.fontMetrics()
            padding = 8
            line_height = font_metrics.height()
            text_width = max(font_metrics.horizontalAdvance(line) for line in self._hover_lines)
            box_width = text_width + padding * 2
            box_height = line_height * len(self._hover_lines) + padding * 2
            info_rect = QRectF(plot_area.left() + 10, plot_area.top() + 10, box_width, box_height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(20, 24, 28, 210))
            painter.drawRoundedRect(info_rect, 6, 6)
            painter.setPen(QColor("#f1f5f9"))
            for index, line in enumerate(self._hover_lines):
                text_y = info_rect.top() + padding + line_height * (index + 0.8)
                painter.drawText(QPointF(info_rect.left() + padding, text_y), line)
        painter.restore()

    def _draw_bottom_axis_labels(self, painter: QPainter, plot_area: QRectF) -> None:
        if not self._bottom_axis_labels:
            return
        painter.save()
        painter.setPen(QColor("#6b778c"))
        font_metrics = painter.fontMetrics()
        text_top = plot_area.bottom() + font_metrics.height() + 4
        previous_right = float("-inf")
        for x_pos, label in self._bottom_axis_labels:
            text_width = font_metrics.horizontalAdvance(label)
            left = x_pos - text_width / 2
            right = x_pos + text_width / 2
            if right < plot_area.left() or left > plot_area.right():
                continue
            if left <= previous_right + 10:
                continue
            painter.drawText(QPointF(left, text_top), label)
            previous_right = right
        painter.restore()
