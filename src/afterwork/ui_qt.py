from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QCloseEvent, QColor, QFont, QFontMetrics, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QSizePolicy,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from afterwork import (
    FlowTarget,
    Frequency,
    OneOffEvent,
    Person,
    Plan,
    Portfolio,
    RecurringFlow,
    SimulationEngine,
    plan_from_dict,
    plan_to_dict,
)
from afterwork.app_settings import SettingsStore
from afterwork.domain import add_months, month_index


SCENARIO_HEADERS = ["Active", "Type", "Category", "Amount", "Target", "Frequency", "Start", "End", "Yearly Adj. %"]
RESULT_HEADERS = [
    "Month",
    "Age",
    "Cash Flow",
    "Portfolio In",
    "Portfolio Growth",
    "Portfolio Out",
    "Cash Balance",
    "Portfolio Value",
    "Total Value",
    "Flows",
]
FREQUENCY_OPTIONS = [frequency.value for frequency in Frequency]
TARGET_OPTIONS = [target.value for target in FlowTarget]
ASSET_DIR = Path(__file__).resolve().parent / "assets"
STEP_PLUS_ICON = (ASSET_DIR / "step-plus.svg").as_posix()
STEP_MINUS_ICON = (ASSET_DIR / "step-minus.svg").as_posix()

APP_BACKGROUND = "#eef3f9"
SURFACE_COLOR = "#fbfdff"
SURFACE_ALT_COLOR = "#f5f8fc"
BORDER_COLOR = "#d7e1ee"
TEXT_COLOR = "#132033"
MUTED_TEXT_COLOR = "#617086"
ACCENT_COLOR = "#2563eb"
ACCENT_HOVER_COLOR = "#1d4ed8"
ACCENT_SOFT_COLOR = "#dbeafe"
SUCCESS_COLOR = "#2f8f63"
INFO_COLOR = "#2e6ea6"
WARNING_COLOR = "#d9822b"
DANGER_COLOR = "#c2410c"
PLOT_BACKGROUND = "#f7faff"

APP_STYLESHEET = f"""
QMainWindow {{
    background-color: {APP_BACKGROUND};
}}

QWidget {{
    color: {TEXT_COLOR};
    selection-background-color: {ACCENT_COLOR};
    selection-color: #ffffff;
}}

QWidget#AppRoot,
QWidget#WorkspacePage {{
    background: transparent;
}}

QFrame#SectionCard {{
    background-color: {SURFACE_COLOR};
    border: 1px solid {BORDER_COLOR};
    border-radius: 18px;
}}

QWidget#FieldBlock {{
    background-color: {SURFACE_ALT_COLOR};
    border: 1px solid {BORDER_COLOR};
    border-radius: 14px;
}}

QLabel#FieldLabel {{
    color: {MUTED_TEXT_COLOR};
    font-size: 11px;
    font-weight: 600;
}}

QLabel#SummaryLabel {{
    color: {MUTED_TEXT_COLOR};
    font-weight: 600;
    padding: 4px 2px 8px 2px;
}}

QPushButton {{
    min-height: 40px;
    padding: 0 16px;
    border-radius: 12px;
    border: 1px solid {BORDER_COLOR};
    background-color: {SURFACE_COLOR};
    color: {TEXT_COLOR};
    font-weight: 600;
}}

QPushButton:hover {{
    border-color: #b7c6da;
    background-color: {SURFACE_ALT_COLOR};
}}

QPushButton:pressed {{
    background-color: #edf3fb;
}}

QLineEdit,
QComboBox,
QAbstractSpinBox {{
    min-height: 22px;
    padding: 8px 10px;
    background-color: #ffffff;
    border: 1px solid #ccd7e5;
    border-radius: 10px;
}}

QLineEdit:focus,
QComboBox:focus,
QAbstractSpinBox:focus {{
    border: 1px solid {ACCENT_COLOR};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QSpinBox::up-button,
QSpinBox::down-button,
QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button {{
    width: 20px;
    background-color: #475569;
    border-left: 1px solid #475569;
}}

QSpinBox::up-button,
QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    border-top-right-radius: 10px;
}}

QSpinBox::down-button,
QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    border-top: 1px solid #64748b;
    border-bottom-right-radius: 10px;
}}

QSpinBox::up-button:hover,
QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover {{
    background-color: #334155;
}}

QSpinBox::up-arrow,
QDoubleSpinBox::up-arrow {{
    image: url({STEP_PLUS_ICON});
    width: 12px;
    height: 12px;
}}

QSpinBox::down-arrow,
QDoubleSpinBox::down-arrow {{
    image: url({STEP_MINUS_ICON});
    width: 12px;
    height: 12px;
}}

QTableWidget {{
    background-color: transparent;
    alternate-background-color: {SURFACE_ALT_COLOR};
    gridline-color: transparent;
    border: 1px solid {BORDER_COLOR};
    border-radius: 14px;
}}

QTableCornerButton::section,
QHeaderView::section {{
    background-color: {SURFACE_ALT_COLOR};
    color: {MUTED_TEXT_COLOR};
    border: none;
    border-bottom: 1px solid {BORDER_COLOR};
    padding: 10px 12px;
    font-weight: 600;
}}

QTableWidget::item {{
    padding: 8px 10px;
    border-bottom: 1px solid #ebf0f6;
}}

QTableWidget::item:selected {{
    background-color: {ACCENT_SOFT_COLOR};
    color: {TEXT_COLOR};
    border-top: 1px solid transparent;
    border-bottom: 1px solid transparent;
}}

QTableWidget::item:selected:active,
QTableWidget::item:selected:!active {{
    background-color: {ACCENT_SOFT_COLOR};
    color: {TEXT_COLOR};
}}

QTableWidget::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #94a3b8;
    background-color: #ffffff;
}}

QTableWidget::indicator:checked {{
    background-color: #334155;
    border-color: #334155;
}}

QTableWidget::indicator:unchecked {{
    background-color: #ffffff;
    border-color: #94a3b8;
}}

QTabWidget::pane {{
    margin-top: -1px;
    background-color: {SURFACE_COLOR};
    border-top: 1px solid {BORDER_COLOR};
}}

QTabBar::tab {{
    background-color: #dde6f0;
    border: 1px solid {BORDER_COLOR};
    border-bottom: none;
    border-top-left-radius: 0px;
    border-top-right-radius: 0px;
    color: {MUTED_TEXT_COLOR};
    font-weight: 600;
    padding: 10px 18px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    color: {TEXT_COLOR};
    background-color: {SURFACE_COLOR};
    border-color: {BORDER_COLOR};
}}

QTabBar::tab:hover:!selected {{
    background-color: #e7eef7;
    color: {TEXT_COLOR};
}}

QSplitter::handle {{
    background-color: #d6e0ec;
    margin: 6px 0;
    border-radius: 3px;
}}

QSplitter::handle:hover {{
    background-color: #bed0e5;
}}

QScrollArea {{
    background: transparent;
    border: none;
}}

QScrollBar:vertical,
QScrollBar:horizontal {{
    background: transparent;
    border: none;
    margin: 0;
}}

QScrollBar::handle:vertical,
QScrollBar::handle:horizontal {{
    background: #c7d4e4;
    border-radius: 6px;
    min-height: 24px;
    min-width: 24px;
}}

QScrollBar::handle:vertical:hover,
QScrollBar::handle:horizontal:hover {{
    background: #aebfd4;
}}

QScrollBar::add-line,
QScrollBar::sub-line,
QScrollBar::add-page,
QScrollBar::sub-page {{
    background: transparent;
    border: none;
}}
"""


def apply_app_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    font = QFont("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(APP_STYLESHEET)


@dataclass(frozen=True)
class ChartPoint:
    month: date
    value: float


@dataclass(frozen=True)
class ChartSeries:
    name: str
    color: QColor
    points: list[ChartPoint]
    series_type: str


class TableTextDelegate(QStyledItemDelegate):
    EDITOR_X_OFFSET = 0
    EDITOR_Y_OFFSET = -2

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.setFrame(False)
            editor.setTextMargins(0, 0, 0, 0)
        return editor

    def updateEditorGeometry(self, editor, option, index) -> None:
        text_option = QStyleOptionViewItem(option)
        self.initStyleOption(text_option, index)
        text_rect = option.widget.style().subElementRect(
            QStyle.SubElement.SE_ItemViewItemText,
            text_option,
            option.widget,
        )
        editor.setGeometry(text_rect.adjusted(self.EDITOR_X_OFFSET, self.EDITOR_Y_OFFSET, 0, 0))


class ScenarioTableDelegate(TableTextDelegate):
    ITEM_TYPE_COLUMN = 1
    TARGET_COLUMN = 4
    FREQUENCY_COLUMN = 5
    START_COLUMN = 6
    END_COLUMN = 7

    def __init__(self, parent: QWidget | None = None, *, date_reference_options: callable | None = None):
        super().__init__(parent)
        self._date_reference_options = date_reference_options

    def createEditor(self, parent, option, index):
        if index.column() == self.TARGET_COLUMN:
            editor = QComboBox(parent)
            editor.addItems(TARGET_OPTIONS)
            editor.setFrame(False)
            return editor

        if index.column() == self.FREQUENCY_COLUMN:
            item_type = (index.siblingAtColumn(self.ITEM_TYPE_COLUMN).data() or "").strip()
            if item_type != "RecurringFlow":
                return None

            editor = QComboBox(parent)
            editor.addItems(FREQUENCY_OPTIONS)
            editor.setFrame(False)
            return editor

        if index.column() in {self.START_COLUMN, self.END_COLUMN}:
            editor = QComboBox(parent)
            editor.setEditable(True)
            editor.setFrame(False)
            if index.column() == self.END_COLUMN:
                editor.addItem("")
            if self._date_reference_options is not None:
                editor.addItems(self._date_reference_options())
            return editor

        return super().createEditor(parent, option, index)

    def setEditorData(self, editor, index) -> None:
        if isinstance(editor, QComboBox):
            value = (index.data() or "").strip()
            combo_index = editor.findText(value)
            if combo_index >= 0:
                editor.setCurrentIndex(combo_index)
            elif editor.isEditable():
                editor.setEditText(value)
            elif editor.count() > 0:
                editor.setCurrentIndex(0)
            return

        super().setEditorData(editor, index)

    def setModelData(self, editor, model, index) -> None:
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText())
            return

        super().setModelData(editor, model, index)


class CollapsibleSection(QWidget):
    expanded_changed = Signal(bool)

    def __init__(self, title: str, content: QWidget, *, expanded: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.content = content

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        self.toggle_button = QToolButton()
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setStyleSheet(
            """
            QToolButton {
                background: transparent;
                border: none;
                color: #1f2937;
                padding: 2px 0;
            }
            QToolButton:checked {
                background: transparent;
                border: none;
                color: #1f2937;
            }
            QToolButton:hover {
                background: transparent;
                border: none;
                color: #111827;
            }
            """
        )
        self.toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.toggle_button.clicked.connect(self._set_expanded)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content)

        self._set_expanded(expanded)

    def _set_expanded(self, expanded: bool) -> None:
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.content.setVisible(expanded)
        if expanded:
            self.setMinimumHeight(0)
            self.setMaximumHeight(16_777_215)
            self.setSizePolicy(self.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Preferred)
        else:
            collapsed_height = self.toggle_button.sizeHint().height()
            margins = self.layout().contentsMargins()
            collapsed_height += margins.top() + margins.bottom()
            self.setMinimumHeight(collapsed_height)
            self.setMaximumHeight(collapsed_height)
            self.setSizePolicy(self.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Fixed)
        self.updateGeometry()
        self.expanded_changed.emit(expanded)


class TimelineWidget(QWidget):
    LEFT_MARGIN = 70
    RIGHT_MARGIN = 170
    TOP_MARGIN = 34
    BOTTOM_MARGIN = 34
    MIN_CHART_HEIGHT = 280
    X_AXIS_STEP_WIDTH = 20
    X_AXIS_RESOLUTION_MONTHS = 6
    Y_AXIS_INTERVAL_HEIGHT = 20
    
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        y_axis_interval: float = 20_000.0,
        y_axis_label_interval: float = 100_000.0,
        dynamic_height: bool = True,
        include_event_values_in_scale: bool = True,
        pin_events_to_zero: bool = False,
    ) -> None:
        super().__init__(parent)
        self.plan_start: date | None = None
        self.plan_end: date | None = None
        self.series: list[ChartSeries] = []
        self._cached_pixmap: QPixmap | None = None
        self.y_axis_interval = y_axis_interval
        self.y_axis_label_interval = y_axis_label_interval
        self.dynamic_height = dynamic_height
        self.include_event_values_in_scale = include_event_values_in_scale
        self.pin_events_to_zero = pin_events_to_zero
        self._hover_pos: QPoint | None = None
        self.setMouseTracking(True)

    def set_timeline(self, plan_start: date | None, plan_end: date | None, series: list[ChartSeries]) -> None:
        self.plan_start = plan_start
        self.plan_end = plan_end
        self.series = series
        self._cached_pixmap = None
        size = self.sizeHint()
        self.setMinimumSize(size)
        self.resize(size)
        self.update()

    def sizeHint(self) -> QSize:
        steps = self._timeline_steps()
        width = self.LEFT_MARGIN + self.RIGHT_MARGIN + max(steps, 1) * self.X_AXIS_STEP_WIDTH
        height = self.TOP_MARGIN + self.BOTTOM_MARGIN + self._plot_height()
        return QSize(width, height)

    def paintEvent(self, _event) -> None:
        self._ensure_cache()
        painter = QPainter(self)
        if self._cached_pixmap is not None:
            painter.drawPixmap(0, 0, self._cached_pixmap)
        self._draw_hover_overlay(painter, QFontMetrics(painter.font()))

    def resizeEvent(self, event) -> None:
        self._cached_pixmap = None
        super().resizeEvent(event)

    def _ensure_cache(self) -> None:
        if self._cached_pixmap is not None and self._cached_pixmap.size() == self.size():
            return

        pixmap = QPixmap(self.size())
        pixmap.fill(QColor(PLOT_BACKGROUND))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.plan_start is None or self.plan_end is None:
            painter.setPen(QColor(MUTED_TEXT_COLOR))
            painter.drawText(self.rect().adjusted(16, 16, -16, -16), "Timeline is unavailable until the scenario dates are valid.")
        else:
            self._draw_axes(painter)
            self._draw_half_year_grid(painter)
            self._draw_series(painter)

        painter.end()
        self._cached_pixmap = pixmap

    def mouseMoveEvent(self, event) -> None:
        if self._is_in_plot_area(event.position().toPoint()):
            self._hover_pos = event.position().toPoint()
        else:
            self._hover_pos = None
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_pos = None
        self.update()
        super().leaveEvent(event)

    def _timeline_months(self) -> int:
        if self.plan_start is None or self.plan_end is None:
            return 1
        return max(month_index(self.plan_start, self.plan_end) + 1, 1)

    def _timeline_steps(self) -> int:
        return max(math.ceil(self._timeline_months() / self.X_AXIS_RESOLUTION_MONTHS), 1)

    def _x_for_month(self, value: date, center: bool = False) -> int:
        if self.plan_start is None:
            return self.LEFT_MARGIN
        offset = max(month_index(self.plan_start, value), 0)
        if center:
            offset += 0.5
        position = offset / self.X_AXIS_RESOLUTION_MONTHS
        return round(self.LEFT_MARGIN + position * self.X_AXIS_STEP_WIDTH)

    def _plot_top(self) -> int:
        return self.TOP_MARGIN

    def _plot_bottom(self) -> int:
        return self.TOP_MARGIN + self._plot_height()

    def _plot_height(self) -> int:
        if not self.dynamic_height:
            return self.MIN_CHART_HEIGHT
        minimum, maximum = self._value_range()
        intervals = max(int(round((maximum - minimum) / self.y_axis_interval)), 1)
        return max(self.MIN_CHART_HEIGHT, intervals * self.Y_AXIS_INTERVAL_HEIGHT)

    def _value_range(self) -> tuple[float, float]:
        values = [0.0]
        for series in self.series:
            if series.series_type == "event" and not self.include_event_values_in_scale:
                continue
            values.extend(point.value for point in series.points)
        minimum = min(values)
        maximum = max(values)
        interval = self.y_axis_interval
        minimum_tick = math.floor(minimum / interval) * interval
        maximum_tick = math.ceil(maximum / interval) * interval
        if minimum_tick == maximum_tick:
            maximum_tick = minimum_tick + interval
        return minimum_tick, maximum_tick

    def _y_for_value(self, value: float) -> int:
        minimum, maximum = self._value_range()
        plot_height = self._plot_bottom() - self._plot_top()
        position = 0.5 if maximum == minimum else (value - minimum) / (maximum - minimum)
        return round(self._plot_bottom() - position * plot_height)

    def _draw_axes(self, painter: QPainter) -> None:
        axis_pen = QPen(QColor("#a7b6c8"))
        painter.setPen(axis_pen)
        painter.drawLine(self.LEFT_MARGIN, self._plot_top(), self.LEFT_MARGIN, self._plot_bottom())
        painter.drawLine(self.LEFT_MARGIN, self._plot_bottom(), self.width() - self.RIGHT_MARGIN + 30, self._plot_bottom())
        right_axis_x = self.width() - self.RIGHT_MARGIN + 30
        painter.drawLine(right_axis_x, self._plot_top(), right_axis_x, self._plot_bottom())

        minimum, maximum = self._value_range()
        tick_pen = QPen(QColor(MUTED_TEXT_COLOR))
        grid_pen = QPen(QColor("#dde6f0"))
        grid_pen.setStyle(Qt.PenStyle.DashLine)
        major_grid_pen = QPen(QColor("#bfd0e2"))
        major_grid_pen.setStyle(Qt.PenStyle.SolidLine)
        tick_values: list[float] = []
        current = minimum
        while current <= maximum + 0.1:
            tick_values.append(current)
            current += self.y_axis_interval

        for value in tick_values:
            y = self._y_for_value(value)
            label_multiple = round(value / self.y_axis_label_interval)
            is_major = abs(value - label_multiple * self.y_axis_label_interval) < 1e-9
            painter.setPen(major_grid_pen if is_major else grid_pen)
            painter.drawLine(self.LEFT_MARGIN, y, right_axis_x, y)
            painter.setPen(tick_pen)
            painter.drawLine(self.LEFT_MARGIN - 5, y, self.LEFT_MARGIN, y)
            painter.drawLine(right_axis_x, y, right_axis_x + 5, y)
            if is_major:
                label = f"{value:,.0f}"
                painter.drawText(8, y + 5, label)
                painter.drawText(right_axis_x + 8, y + 5, label)

        if minimum < 0 < maximum:
            zero_y = self._y_for_value(0.0)
            painter.setPen(QPen(QColor("#c0cddd"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(self.LEFT_MARGIN, zero_y, right_axis_x, zero_y)

    def _draw_half_year_grid(self, painter: QPainter) -> None:
        assert self.plan_start is not None
        total_months = self._timeline_months()
        half_year_pen = QPen(QColor("#d5deea"))
        label_pen = QPen(QColor(MUTED_TEXT_COLOR))

        for month_offset in range(0, total_months + 1, self.X_AXIS_RESOLUTION_MONTHS):
            tick_date = add_months(self.plan_start, month_offset)
            x = round(self.LEFT_MARGIN + (month_offset / self.X_AXIS_RESOLUTION_MONTHS) * self.X_AXIS_STEP_WIDTH)
            painter.setPen(half_year_pen)
            painter.drawLine(x, self._plot_top(), x, self._plot_bottom())

        first_january_offset = 0
        while first_january_offset <= total_months:
            if add_months(self.plan_start, first_january_offset).month == 1:
                break
            first_january_offset += 1

        for month_offset in range(first_january_offset, total_months + 1, 12):
            tick_date = add_months(self.plan_start, month_offset)
            x = round(self.LEFT_MARGIN + (month_offset / self.X_AXIS_RESOLUTION_MONTHS) * self.X_AXIS_STEP_WIDTH)
            painter.setPen(label_pen)
            painter.drawText(x + 4, 18, f"{tick_date.year}")

    def _draw_series(self, painter: QPainter) -> None:
        font_metrics = QFontMetrics(painter.font())
        for series in self.series:
            if not series.points:
                continue

            if series.series_type == "event":
                self._draw_event_series(painter, series, font_metrics)
            else:
                self._draw_line_series(painter, series, font_metrics)

    def _draw_line_series(self, painter: QPainter, series: ChartSeries, font_metrics: QFontMetrics) -> None:
        width = 3 if series.series_type == "balance" else 2
        pen = QPen(series.color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        previous_point: tuple[int, int] | None = None
        for point in series.points:
            current = (self._x_for_month(point.month, center=True), self._y_for_value(point.value))
            if previous_point is not None:
                painter.drawLine(previous_point[0], previous_point[1], current[0], current[1])
            previous_point = current

        if previous_point is not None:
            painter.setPen(QPen(series.color.darker(135)))
            label_x = min(previous_point[0] + 10, self.width() - self.RIGHT_MARGIN + 12)
            label_y = previous_point[1] - 6
            painter.drawText(label_x, label_y, font_metrics.elidedText(series.name, Qt.TextElideMode.ElideRight, self.RIGHT_MARGIN - 18))

    def _draw_event_series(self, painter: QPainter, series: ChartSeries, font_metrics: QFontMetrics) -> None:
        painter.setPen(QPen(series.color.darker(130), 2))
        painter.setBrush(QBrush(series.color))
        for point in series.points:
            x = self._x_for_month(point.month, center=True)
            y = self._y_for_value(0.0 if self.pin_events_to_zero else point.value)
            painter.drawEllipse(x - 6, y - 6, 12, 12)
            label = f"{series.name} ({point.value:,.0f})"
            painter.drawText(x + 10, y - 8, font_metrics.elidedText(label, Qt.TextElideMode.ElideRight, 220))

    def _draw_hover_overlay(self, painter: QPainter, font_metrics: QFontMetrics) -> None:
        if self._hover_pos is None or self.plan_start is None or self.plan_end is None:
            return

        hover_text = self._hover_text(self._hover_pos)
        text_width = font_metrics.horizontalAdvance(hover_text)
        bubble_width = text_width + 16
        bubble_height = font_metrics.height() + 10
        bubble_x = self._hover_pos.x() - bubble_width // 2
        bubble_y = self._hover_pos.y() - bubble_height - 10

        if bubble_y < 4:
            bubble_x = (self.width() - bubble_width) // 2
            bubble_y = 4

        bubble_x = max(4, min(bubble_x, self.width() - bubble_width - 4))
        bubble_rect = QRect(bubble_x, bubble_y, bubble_width, bubble_height)

        painter.setPen(QPen(QColor("#334155")))
        painter.setBrush(QBrush(QColor(251, 253, 255, 242)))
        painter.drawRoundedRect(bubble_rect, 6, 6)
        painter.drawText(bubble_rect.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter, hover_text)

    def _hover_text(self, pos: QPoint) -> str:
        month_value = self._month_for_x(pos.x())
        y_value = self._value_for_y(pos.y())
        return f"{month_value.isoformat()} | {y_value:,.0f}"

    def _month_for_x(self, x_pos: int) -> date:
        assert self.plan_start is not None and self.plan_end is not None
        relative = x_pos - self.LEFT_MARGIN
        month_offset = round(relative / self.X_AXIS_STEP_WIDTH * self.X_AXIS_RESOLUTION_MONTHS)
        month_offset = max(0, min(month_offset, self._timeline_months() - 1))
        return add_months(self.plan_start, month_offset)

    def _value_for_y(self, y_pos: int) -> float:
        minimum, maximum = self._value_range()
        plot_height = self._plot_bottom() - self._plot_top()
        if plot_height <= 0:
            return minimum
        clamped_y = max(self._plot_top(), min(y_pos, self._plot_bottom()))
        position = (self._plot_bottom() - clamped_y) / plot_height
        return minimum + position * (maximum - minimum)

    def _is_in_plot_area(self, pos: QPoint) -> bool:
        return self.LEFT_MARGIN <= pos.x() <= self.width() - self.RIGHT_MARGIN + 30 and self._plot_top() <= pos.y() <= self._plot_bottom()


@dataclass(frozen=True)
class EventTimelineItem:
    name: str
    start: date
    end: date
    color: QColor
    item_type: str


class EventTimelineWidget(QWidget):
    LEFT_MARGIN = 150
    RIGHT_MARGIN = 24
    TOP_MARGIN = 20
    BOTTOM_MARGIN = 20
    ROW_HEIGHT = 28
    MONTH_WIDTH = 10
    DOT_RADIUS = 5
    BAR_HEIGHT = 10

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.plan_start: date | None = None
        self.plan_end: date | None = None
        self.items: list[EventTimelineItem] = []
        self.setMinimumHeight(self.TOP_MARGIN + self.BOTTOM_MARGIN + self.ROW_HEIGHT * 4)

    def set_timeline(self, plan_start: date | None, plan_end: date | None, items: list[EventTimelineItem]) -> None:
        self.plan_start = plan_start
        self.plan_end = plan_end
        self.items = items
        size = self.sizeHint()
        self.setMinimumSize(size)
        self.resize(size)
        self.update()

    def sizeHint(self) -> QSize:
        months = self._timeline_months()
        width = self.LEFT_MARGIN + self.RIGHT_MARGIN + max(months, 1) * self.MONTH_WIDTH
        height = self.TOP_MARGIN + self.BOTTOM_MARGIN + max(len(self.items), 1) * self.ROW_HEIGHT
        return QSize(width, height)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(PLOT_BACKGROUND))

        if self.plan_start is None or self.plan_end is None:
            painter.setPen(QColor(MUTED_TEXT_COLOR))
            painter.drawText(self.rect().adjusted(16, 16, -16, -16), "Event timeline is unavailable until the scenario dates are valid.")
            return

        self._draw_grid(painter)
        self._draw_items(painter)

    def _timeline_months(self) -> int:
        if self.plan_start is None or self.plan_end is None:
            return 1
        return max(month_index(self.plan_start, self.plan_end) + 1, 1)

    def _x_for_month(self, value: date, center: bool = False) -> int:
        if self.plan_start is None:
            return self.LEFT_MARGIN
        offset = max(month_index(self.plan_start, value), 0)
        if center:
            offset += 0.5
        return round(self.LEFT_MARGIN + offset * self.MONTH_WIDTH)

    def _row_y(self, index: int) -> int:
        return self.TOP_MARGIN + index * self.ROW_HEIGHT + self.ROW_HEIGHT // 2

    def _draw_grid(self, painter: QPainter) -> None:
        assert self.plan_start is not None
        total_months = self._timeline_months()
        plot_bottom = self.TOP_MARGIN + max(len(self.items), 1) * self.ROW_HEIGHT
        quarter_pen = QPen(QColor("#dde6f0"))
        year_pen = QPen(QColor(MUTED_TEXT_COLOR))

        for month_offset in range(0, total_months + 1, 3):
            tick_date = add_months(self.plan_start, month_offset)
            x = self.LEFT_MARGIN + month_offset * self.MONTH_WIDTH
            painter.setPen(quarter_pen)
            painter.drawLine(x, self.TOP_MARGIN - 8, x, plot_bottom)
            if tick_date.month == 1:
                painter.setPen(year_pen)
                painter.drawText(x + 4, 12, f"{tick_date.year}")

        painter.setPen(QPen(QColor("#d0dae7")))
        painter.drawLine(self.LEFT_MARGIN, plot_bottom, self.width() - self.RIGHT_MARGIN, plot_bottom)

    def _draw_items(self, painter: QPainter) -> None:
        font_metrics = QFontMetrics(painter.font())
        text_pen = QPen(QColor(TEXT_COLOR))
        for index, item in enumerate(self.items):
            y = self._row_y(index)
            label_rect = QRect(8, y - 10, self.LEFT_MARGIN - 16, 20)
            painter.setPen(text_pen)
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                font_metrics.elidedText(item.name, Qt.TextElideMode.ElideRight, label_rect.width()),
            )

            if item.item_type == "one_off":
                x = self._x_for_month(item.start, center=True)
                painter.setPen(QPen(item.color.darker(130), 2))
                painter.setBrush(QBrush(item.color))
                painter.drawEllipse(x - self.DOT_RADIUS, y - self.DOT_RADIUS, self.DOT_RADIUS * 2, self.DOT_RADIUS * 2)
                continue

            start_x = self._x_for_month(item.start)
            end_x = self._x_for_month(item.end, center=True)
            width = max(end_x - start_x, self.MONTH_WIDTH // 2)
            bar_rect = QRect(start_x, y - self.BAR_HEIGHT // 2, width, self.BAR_HEIGHT)
            painter.setPen(QPen(item.color.darker(130), 1))
            painter.setBrush(QBrush(item.color))
            painter.drawRoundedRect(bar_rect, 4, 4)


class PlannerWindow(QMainWindow):
    TOOLBAR_BUTTON_WIDTH = 132
    TOOLBAR_BUTTON_HEIGHT = 40
    AUTOSAVE_DELAY_MS = 1200
    RETIREMENT_MONTH_LABEL = "retirement"
    RETIREMENT_MONTH_REFERENCE = "retirement_month"
    SCENARIO_CATEGORY_COLUMN = 2
    SCENARIO_START_COLUMN = 6
    SCENARIO_END_COLUMN = 7

    def __init__(self, settings_store: SettingsStore) -> None:
        super().__init__()
        self.settings_store = settings_store
        self.current_file: Path | None = None
        self.current_result = None
        self.is_dirty = False
        self._suspend_change_tracking = False
        self._scenario_row_id_counter = 0
        self._scenario_sort_column: int | None = None
        self._scenario_sort_ascending = True
        self.autosave_path = self.settings_store.get_autosave_path()
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(self.AUTOSAVE_DELAY_MS)
        self.autosave_timer.timeout.connect(self._autosave_current_plan)
        self.setWindowTitle("Afterwork Planner[*]")
        self.resize(1500, 900)

        root = QWidget()
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(24, 14, 24, 24)
        root_layout.setSpacing(14)

        self._configure_menu_bar()

        self.body_splitter = QSplitter(Qt.Orientation.Vertical)
        self.body_splitter.setHandleWidth(8)
        self.body_splitter.setChildrenCollapsible(False)
        root_layout.addWidget(self.body_splitter, 1)

        self.workspace_tabs = self._build_workspace_tabs()
        self.body_splitter.addWidget(self.workspace_tabs)

        self.timeline_panel = self._build_timeline_panel()
        self.body_splitter.addWidget(self.timeline_panel)
        self.body_splitter.setStretchFactor(0, 2)
        self.body_splitter.setStretchFactor(1, 1)

        self._connect_refresh_signals()
        QTimer.singleShot(0, self._set_default_body_splitter_sizes)
        self.refresh_timeline()
        self.run_simulation()
        self._set_dirty(False)

    def _configure_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        load_action = QAction("&Load...", self)
        load_action.triggered.connect(self.load_plan)
        file_menu.addAction(load_action)

        save_action = QAction("&Save", self)
        save_action.triggered.connect(self.save_plan)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save &As...", self)
        save_as_action.triggered.connect(self.save_plan_as)
        file_menu.addAction(save_as_action)

    def _build_workspace_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setObjectName("WorkspaceTabs")
        tabs.setDocumentMode(True)
        tabs.addTab(self._build_assumptions_panel(), "Plan Assumptions")
        tabs.addTab(self._build_scenario_panel(), "Event Table")
        tabs.addTab(self._build_event_timeline_panel(), "Event Timeline")
        tabs.addTab(self._build_results_panel(), "Simulation Table")
        return tabs

    def _build_assumptions_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("WorkspacePage")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(0)

        settings_card = QFrame()
        settings_card.setObjectName("SectionCard")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(20, 18, 20, 20)
        settings_layout.setSpacing(0)

        self.start_month_edit = QLineEdit("2026-01-01")
        self.retirement_month_edit = QLineEdit("2026-01-01")
        self.birthday_edit = QLineEdit("1986-01-01")
        self.target_age_spin = QSpinBox()
        self.target_age_spin.setRange(0, 130)
        self.target_age_spin.setValue(95)
        self.starting_cash_spin = QDoubleSpinBox()
        self.starting_cash_spin.setRange(-9_999_999, 9_999_999)
        self.starting_cash_spin.setDecimals(0)
        self.starting_cash_spin.setValue(25_000)
        self.portfolio_start_spin = QDoubleSpinBox()
        self.portfolio_start_spin.setRange(-9_999_999, 9_999_999)
        self.portfolio_start_spin.setDecimals(0)
        self.portfolio_start_spin.setValue(50_000)
        self.portfolio_growth_spin = QDoubleSpinBox()
        self.portfolio_growth_spin.setRange(-1.0, 10.0)
        self.portfolio_growth_spin.setDecimals(1)
        self.portfolio_growth_spin.setSingleStep(0.1)
        self.portfolio_growth_spin.setValue(5.0)

        for widget in [
            self.target_age_spin,
            self.starting_cash_spin,
            self.portfolio_start_spin,
            self.portfolio_growth_spin,
        ]:
            widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)

        self._set_compact_width(self.start_month_edit, "2026-01-01", 34)
        self._set_compact_width(self.retirement_month_edit, "2026-01-01", 34)
        self._set_compact_width(self.birthday_edit, "1986-01-01", 34)
        self._set_compact_width(self.target_age_spin, "130", 40)
        self._set_compact_width(self.starting_cash_spin, "-9999999", 48)
        self._set_compact_width(self.portfolio_start_spin, "-9999999", 48)
        self._set_compact_width(self.portfolio_growth_spin, "-10.0", 48)

        field_row = QHBoxLayout()
        field_row.setContentsMargins(0, 0, 0, 0)
        field_row.setSpacing(12)

        fields = [
            ("Start Month", self.start_month_edit),
            ("Retirement Month", self.retirement_month_edit),
            ("Birthday", self.birthday_edit),
            ("Target Age", self.target_age_spin),
            ("Starting Cash", self.starting_cash_spin),
            ("Starting Portfolio", self.portfolio_start_spin),
            ("Portfolio Growth %", self.portfolio_growth_spin),
        ]
        for label, widget in fields:
            field_row.addWidget(
                self._create_field_block(label, widget),
                alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            )
        field_row.addStretch()

        settings_layout.addLayout(field_row)
        layout.addWidget(settings_card)
        return panel

    def _build_scenario_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("WorkspacePage")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(0)

        self.scenario_table = QTableWidget(0, len(SCENARIO_HEADERS))
        self.scenario_table.setHorizontalHeaderLabels(SCENARIO_HEADERS)
        self.scenario_table.setItemDelegate(
            ScenarioTableDelegate(self.scenario_table, date_reference_options=self._date_reference_options)
        )
        self.scenario_table.setAlternatingRowColors(True)
        self.scenario_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.scenario_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.scenario_table.setShowGrid(False)
        self.scenario_table.verticalHeader().setVisible(False)
        self.scenario_table.verticalHeader().setDefaultSectionSize(40)
        self.scenario_table.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        header = self.scenario_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        self.scenario_table.setColumnWidth(0, 82)
        self.scenario_table.setColumnWidth(1, 110)
        self.scenario_table.setColumnWidth(2, 140)
        self.scenario_table.setColumnWidth(3, 90)
        self.scenario_table.setColumnWidth(4, 90)
        self.scenario_table.setColumnWidth(5, 100)
        self.scenario_table.setColumnWidth(6, 110)
        self.scenario_table.setColumnWidth(7, 110)
        self.scenario_table.setColumnWidth(8, 110)
        scenario_table_container = QFrame()
        scenario_table_container.setObjectName("SectionCard")
        scenario_table_layout = QVBoxLayout(scenario_table_container)
        scenario_table_layout.setContentsMargins(20, 18, 20, 20)
        scenario_table_layout.setSpacing(14)

        table_toolbar = QHBoxLayout()
        table_toolbar.setSpacing(10)
        for label, handler in [
            ("Add Flow", self.add_recurring_flow),
            ("Add Event", self.add_one_off_event),
            ("Delete Row", self.delete_selected_row),
            ("Run Simulation", self.run_simulation),
        ]:
            table_toolbar.addWidget(self._create_button(label, handler))
        table_toolbar.addStretch()
        scenario_table_layout.addLayout(table_toolbar)
        scenario_table_layout.addWidget(self.scenario_table)
        layout.addWidget(scenario_table_container, 1)

        return panel

    def _build_event_timeline_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("WorkspacePage")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(0)

        self.event_timeline_widget = EventTimelineWidget()
        self.event_timeline_frame = QFrame()
        self.event_timeline_frame.setObjectName("SectionCard")
        self.event_timeline_frame.setFrameShape(QFrame.Shape.NoFrame)
        event_timeline_layout = QVBoxLayout(self.event_timeline_frame)
        event_timeline_layout.setContentsMargins(20, 18, 20, 20)
        event_timeline_layout.setSpacing(14)
        self.event_timeline_scroll = QScrollArea()
        self.event_timeline_scroll.setWidgetResizable(False)
        self.event_timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.event_timeline_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.event_timeline_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.event_timeline_scroll.setMinimumHeight(self.event_timeline_widget.minimumHeight())
        self.event_timeline_scroll.setWidget(self.event_timeline_widget)
        self.event_timeline_scroll.horizontalScrollBar().setSingleStep(self.event_timeline_widget.MONTH_WIDTH * 2)
        event_timeline_layout.addWidget(self.event_timeline_scroll)
        layout.addWidget(self.event_timeline_frame, 1)

        return panel

    def _build_timeline_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("SectionCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)

        self.chart_container = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_container)
        self.chart_layout.setContentsMargins(0, 4, 0, 4)
        self.chart_layout.setSpacing(18)

        self.timeline_widget = TimelineWidget(
            y_axis_interval=200.0,
            y_axis_label_interval=200.0,
            dynamic_height=True,
            include_event_values_in_scale=False,
            pin_events_to_zero=True,
        )
        self.chart_layout.addWidget(self.timeline_widget)

        self.balance_timeline_widget = TimelineWidget(
            y_axis_interval=20_000.0,
            y_axis_label_interval=100_000.0,
            dynamic_height=True,
            include_event_values_in_scale=False,
            pin_events_to_zero=False,
        )
        self.chart_layout.addWidget(self.balance_timeline_widget)

        self.timeline_scroll = QScrollArea()
        self.timeline_scroll.setWidgetResizable(False)
        self.timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.timeline_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.timeline_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.timeline_scroll.setWidget(self.chart_container)
        self.timeline_scroll.horizontalScrollBar().setSingleStep(self.timeline_widget.X_AXIS_STEP_WIDTH * 2)
        layout.addWidget(self.timeline_scroll)
        return panel

    def _build_results_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("WorkspacePage")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(0)

        results_card = QFrame()
        results_card.setObjectName("SectionCard")
        card_layout = QVBoxLayout(results_card)
        card_layout.setContentsMargins(20, 18, 20, 20)
        card_layout.setSpacing(14)

        self.summary_label = QLabel("No simulation results yet.")
        self.summary_label.setObjectName("SummaryLabel")

        self.results_table = QTableWidget(0, len(RESULT_HEADERS))
        self.results_table.setHorizontalHeaderLabels(RESULT_HEADERS)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.results_table.setShowGrid(False)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.verticalHeader().setDefaultSectionSize(38)
        card_layout.addWidget(self.summary_label)
        card_layout.addWidget(self.results_table, 1)
        layout.addWidget(results_card, 1)
        return panel

    def _create_button(self, label: str, handler) -> QPushButton:
        button = QPushButton(label)
        button.setMinimumWidth(self.TOOLBAR_BUTTON_WIDTH)
        button.setFixedHeight(self.TOOLBAR_BUTTON_HEIGHT)
        button.clicked.connect(handler)
        return button

    def _create_field_block(self, label: str, widget: QWidget) -> QWidget:
        block = QWidget()
        block.setObjectName("FieldBlock")
        layout = QVBoxLayout(block)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)
        label_widget = QLabel(label)
        label_widget.setObjectName("FieldLabel")
        widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(label_widget)
        layout.addWidget(widget)
        return block

    def _set_compact_width(self, widget: QWidget, sample_text: str, extra_padding: int) -> None:
        metrics = widget.fontMetrics()
        content_width = metrics.horizontalAdvance(sample_text)
        target_width = max(widget.minimumSizeHint().width(), content_width + extra_padding)
        widget.setFixedWidth(target_width)

    def _set_default_body_splitter_sizes(self) -> None:
        total_height = max(self.body_splitter.height(), 1)
        timeline_height = max(total_height // 3, 180)
        self.body_splitter.setSizes([max(total_height - timeline_height, 0), timeline_height])

    def _connect_refresh_signals(self) -> None:
        self.scenario_table.itemChanged.connect(self._on_scenario_table_changed)
        self.scenario_table.horizontalHeader().sectionClicked.connect(self._on_scenario_header_clicked)
        self.start_month_edit.editingFinished.connect(self._on_plan_input_changed)
        self.retirement_month_edit.editingFinished.connect(self._on_plan_input_changed)
        self.birthday_edit.editingFinished.connect(self._on_plan_input_changed)
        self.target_age_spin.valueChanged.connect(self._on_plan_input_changed)
        self.starting_cash_spin.valueChanged.connect(self._on_plan_input_changed)
        self.portfolio_start_spin.valueChanged.connect(self._on_plan_input_changed)
        self.portfolio_growth_spin.valueChanged.connect(self._on_plan_input_changed)

    def _on_scenario_table_changed(self, _item: QTableWidgetItem) -> None:
        if self._suspend_change_tracking:
            return
        if _item.column() == 1:
            self._sync_frequency_cell(_item.row())
        if self._scenario_sort_column is not None and _item.column() in {
            self.SCENARIO_CATEGORY_COLUMN,
            self.SCENARIO_START_COLUMN,
            self.SCENARIO_END_COLUMN,
        }:
            self._sort_scenario_table(select_row_id=self._scenario_row_id(_item.row()))
        self._mark_dirty()
        self.refresh_timeline()

    def _on_scenario_header_clicked(self, column: int) -> None:
        if column not in {self.SCENARIO_CATEGORY_COLUMN, self.SCENARIO_START_COLUMN, self.SCENARIO_END_COLUMN}:
            return

        if self._scenario_sort_column == column:
            self._scenario_sort_ascending = not self._scenario_sort_ascending
        else:
            self._scenario_sort_column = column
            self._scenario_sort_ascending = True

        self._sort_scenario_table(select_row_id=self._selected_scenario_row_id())
        self._update_scenario_sort_indicator()
        self.refresh_timeline()

    def _on_plan_input_changed(self, *_args) -> None:
        if self._suspend_change_tracking:
            return
        self._mark_dirty()
        self.refresh_timeline()

    def _mark_dirty(self) -> None:
        self._set_dirty(True)
        self.autosave_timer.start()

    def _set_dirty(self, dirty: bool) -> None:
        self.is_dirty = dirty
        self.setWindowModified(dirty)
        self._update_window_title()

    def _enabled_item(self, enabled: bool) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        item.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
        return item

    def _append_scenario_row(self, values: list[str | bool], *, row_id: int | None = None) -> int:
        if row_id is None:
            row_id = self._next_scenario_row_id()
        row = self.scenario_table.rowCount()
        self.scenario_table.insertRow(row)
        for column, value in enumerate(values):
            if column == 0:
                item = self._enabled_item(bool(value))
            else:
                item = QTableWidgetItem(str(value))
            item.setData(Qt.ItemDataRole.UserRole, row_id)
            self.scenario_table.setItem(row, column, item)
        self._sync_target_cell(row)
        self._sync_frequency_cell(row)
        return row_id

    def _next_scenario_row_id(self) -> int:
        row_id = self._scenario_row_id_counter
        self._scenario_row_id_counter += 1
        return row_id

    def _scenario_row_id(self, row: int) -> int | None:
        item = self.scenario_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _selected_scenario_row_id(self) -> int | None:
        row = self.scenario_table.currentRow()
        if row < 0:
            return None
        return self._scenario_row_id(row)

    def _focus_scenario_row(self, row_id: int | None) -> None:
        if row_id is None:
            return
        for row in range(self.scenario_table.rowCount()):
            if self._scenario_row_id(row) != row_id:
                continue
            self.scenario_table.selectRow(row)
            focus_column = 1 if self.scenario_table.columnCount() > 1 else 0
            self.scenario_table.setCurrentCell(row, focus_column)
            item = self.scenario_table.item(row, focus_column)
            if item is not None:
                self.scenario_table.scrollToItem(item, QTableWidget.ScrollHint.PositionAtCenter)
            self.scenario_table.setFocus(Qt.FocusReason.OtherFocusReason)
            return

    def _scenario_row_values(self, row: int) -> list[str | bool]:
        return [
            self._scenario_enabled(row),
            self._scenario_value(row, 1),
            self._scenario_value(row, 2),
            self._scenario_value(row, 3),
            self._scenario_value(row, 4),
            self._scenario_value(row, 5),
            self._scenario_value(row, 6),
            self._scenario_value(row, 7),
            self._scenario_value(row, 8),
        ]

    def _date_reference_options(self) -> list[str]:
        return [self.RETIREMENT_MONTH_LABEL]

    def _resolve_date_reference(self, value: str) -> date:
        text = value.strip()
        if text in {self.RETIREMENT_MONTH_LABEL, self.RETIREMENT_MONTH_REFERENCE}:
            return date.fromisoformat(self.retirement_month_edit.text().strip())
        return date.fromisoformat(text)

    def _save_payload(self, plan: Plan) -> dict[str, object]:
        return {
            **plan_to_dict(plan),
            "_ui": {
                "parameters": {
                    self.RETIREMENT_MONTH_REFERENCE: self.retirement_month_edit.text().strip(),
                },
                "scenario_rows": [
                    {
                        "enabled": bool(values[0]),
                        "type": str(values[1]),
                        "category": str(values[2]),
                        "amount": str(values[3]),
                        "target": str(values[4]),
                        "frequency": str(values[5]),
                        "start": str(values[6]),
                        "end": str(values[7]),
                        "adjustment_rate": str(values[8]),
                    }
                    for values in (
                        self._scenario_row_values(row)
                        for row in range(self.scenario_table.rowCount())
                    )
                ],
            },
        }

    def _scenario_date_sort_key(self, value: str, *, ascending: bool) -> tuple[int, int]:
        if not value:
            return (1, 0)
        try:
            ordinal = self._resolve_date_reference(value).toordinal()
        except ValueError:
            return (1, 0)
        return (0, ordinal if ascending else -ordinal)

    def _scenario_category_sort_key(self, value: str, *, ascending: bool) -> tuple[int, str]:
        normalized = value.strip().casefold()
        if not normalized:
            return (1, "")
        return (0, normalized if ascending else "".join(chr(0x10FFFF - ord(char)) for char in normalized))

    def _sort_scenario_by_category(self, rows: list[tuple[int, list[str | bool]]], *, ascending: bool) -> list[tuple[int, list[str | bool]]]:
        return sorted(
            rows,
            key=lambda row: (
                self._scenario_category_sort_key(str(row[1][self.SCENARIO_CATEGORY_COLUMN]), ascending=ascending),
                row[0],
            ),
        )

    def _sort_scenario_by_start_date(self, rows: list[tuple[int, list[str | bool]]], *, ascending: bool) -> list[tuple[int, list[str | bool]]]:
        return sorted(
            rows,
            key=lambda row: (
                self._scenario_date_sort_key(str(row[1][self.SCENARIO_START_COLUMN]), ascending=ascending),
                row[0],
            ),
        )

    def _sort_scenario_by_end_date(self, rows: list[tuple[int, list[str | bool]]], *, ascending: bool) -> list[tuple[int, list[str | bool]]]:
        return sorted(
            rows,
            key=lambda row: (
                self._scenario_date_sort_key(str(row[1][self.SCENARIO_END_COLUMN]), ascending=ascending),
                row[0],
            ),
        )

    def _sort_scenario_table(self, *, select_row_id: int | None = None) -> None:
        if self._scenario_sort_column not in {
            self.SCENARIO_CATEGORY_COLUMN,
            self.SCENARIO_START_COLUMN,
            self.SCENARIO_END_COLUMN,
        }:
            if select_row_id is not None:
                self._focus_scenario_row(select_row_id)
            return

        rows = [
            (self._scenario_row_id(row), self._scenario_row_values(row))
            for row in range(self.scenario_table.rowCount())
        ]

        if self._scenario_sort_column == self.SCENARIO_CATEGORY_COLUMN:
            ordered_rows = self._sort_scenario_by_category(rows, ascending=self._scenario_sort_ascending)
        elif self._scenario_sort_column == self.SCENARIO_START_COLUMN:
            ordered_rows = self._sort_scenario_by_start_date(rows, ascending=self._scenario_sort_ascending)
        else:
            ordered_rows = self._sort_scenario_by_end_date(rows, ascending=self._scenario_sort_ascending)

        previous_suspend = self._suspend_change_tracking
        self._suspend_change_tracking = True
        try:
            self.scenario_table.setRowCount(0)
            for row_id, values in ordered_rows:
                self._append_scenario_row(values, row_id=row_id)
        finally:
            self._suspend_change_tracking = previous_suspend

        self._focus_scenario_row(select_row_id)

    def _update_scenario_sort_indicator(self) -> None:
        header = self.scenario_table.horizontalHeader()
        if self._scenario_sort_column is None:
            return
        header.setSortIndicator(
            self._scenario_sort_column,
            Qt.SortOrder.AscendingOrder if self._scenario_sort_ascending else Qt.SortOrder.DescendingOrder,
        )

    def _sync_target_cell(self, row: int) -> None:
        item = self.scenario_table.item(row, 4)
        if item is None:
            item = QTableWidgetItem("")
            self.scenario_table.setItem(row, 4, item)

        flags = item.flags() | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        previous_suspend = self._suspend_change_tracking
        self._suspend_change_tracking = True
        try:
            if item.text().strip() not in TARGET_OPTIONS:
                item.setText(FlowTarget.CASH.value)
            item.setFlags(flags | Qt.ItemFlag.ItemIsEditable)
        finally:
            self._suspend_change_tracking = previous_suspend

    def _sync_frequency_cell(self, row: int) -> None:
        item = self.scenario_table.item(row, 5)
        if item is None:
            item = QTableWidgetItem("")
            self.scenario_table.setItem(row, 5, item)

        is_recurring_flow = self._scenario_value(row, 1) == "RecurringFlow"
        flags = item.flags() | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        previous_suspend = self._suspend_change_tracking
        self._suspend_change_tracking = True
        try:
            if is_recurring_flow:
                if item.text().strip() not in FREQUENCY_OPTIONS:
                    item.setText(Frequency.MONTHLY.value)
                item.setFlags(flags | Qt.ItemFlag.ItemIsEditable)
            else:
                if item.text():
                    item.setText("")
                item.setFlags(flags & ~Qt.ItemFlag.ItemIsEditable)
        finally:
            self._suspend_change_tracking = previous_suspend

    def add_recurring_flow(self) -> None:
        self._suspend_change_tracking = True
        try:
            row_id = self._append_scenario_row(
                [True, "RecurringFlow", "general", "0", "cash", "monthly", self.start_month_edit.text(), "", "0.0"]
            )
        finally:
            self._suspend_change_tracking = False
        self._sort_scenario_table(select_row_id=row_id)
        self._mark_dirty()
        self.refresh_timeline()

    def add_one_off_event(self) -> None:
        self._suspend_change_tracking = True
        try:
            row_id = self._append_scenario_row(
                [True, "OneOffEvent", "general", "0", "cash", "", self.start_month_edit.text(), "", ""]
            )
        finally:
            self._suspend_change_tracking = False
        self._sort_scenario_table(select_row_id=row_id)
        self._focus_scenario_row(row_id)
        self._mark_dirty()
        self.refresh_timeline()

    def delete_selected_row(self) -> None:
        row = self.scenario_table.currentRow()
        if row >= 0:
            self.scenario_table.removeRow(row)
            self._mark_dirty()
            self.refresh_timeline()

    def _scenario_value(self, row: int, column: int) -> str:
        item = self.scenario_table.item(row, column)
        return item.text().strip() if item is not None else ""

    def _scenario_enabled(self, row: int) -> bool:
        item = self.scenario_table.item(row, 0)
        return item is not None and item.checkState() == Qt.CheckState.Checked

    def _build_plan(self) -> Plan:
        recurring_flows: list[RecurringFlow] = []
        one_off_events: list[OneOffEvent] = []

        for row in range(self.scenario_table.rowCount()):
            enabled = self._scenario_enabled(row)
            item_type = self._scenario_value(row, 1)
            category = self._scenario_value(row, 2) or "general"
            amount = self._scenario_value(row, 3)
            target = self._scenario_value(row, 4)
            frequency = self._scenario_value(row, 5)
            start = self._scenario_value(row, 6)
            end = self._scenario_value(row, 7)
            adjustment_rate = self._scenario_value(row, 8)

            if item_type == "RecurringFlow":
                recurring_flows.append(
                    RecurringFlow(
                        amount=float(amount),
                        target=FlowTarget(target),
                        frequency=Frequency(frequency),
                        starts_on=self._resolve_date_reference(start),
                        ends_on=self._resolve_date_reference(end) if end else None,
                        category=category,
                        annual_adjustment_rate=float(adjustment_rate or 0.0) / 100.0,
                        enabled=enabled,
                    )
                )
            elif item_type == "OneOffEvent":
                one_off_events.append(
                    OneOffEvent(
                        amount=float(amount),
                        target=FlowTarget(target),
                        occurs_on=self._resolve_date_reference(start),
                        category=category,
                        enabled=enabled,
                    )
                )
            else:
                raise ValueError(f"Unsupported row type: {item_type!r}")

        return Plan(
            person=Person(
                birth_date=date.fromisoformat(self.birthday_edit.text().strip()),
                target_age_years=self.target_age_spin.value(),
            ),
            start_month=date.fromisoformat(self.start_month_edit.text().strip()),
            starting_cash_balance=self.starting_cash_spin.value(),
            portfolio=Portfolio(
                starting_balance=self.portfolio_start_spin.value(),
                annual_growth_rate=self.portfolio_growth_spin.value() / 100.0,
            ),
            recurring_flows=recurring_flows,
            one_off_events=one_off_events,
        )

    def run_simulation(self) -> None:
        try:
            plan = self._build_plan()
            result = SimulationEngine().run(plan)
        except Exception as exc:
            QMessageBox.critical(self, "Simulation error", str(exc))
            return

        self.current_result = result
        self.results_table.setRowCount(0)
        for record in result.records:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            values = [
                record.month.isoformat(),
                f"{record.age_years:.1f}",
                f"{record.cash_flow_nominal:.2f}",
                f"{record.portfolio_contribution_nominal:.2f}",
                f"{record.portfolio_growth_nominal:.2f}",
                f"{record.portfolio_transfer_nominal:.2f}",
                f"{record.cash_balance:.2f}",
                f"{record.portfolio_balance:.2f}",
                f"{record.total_balance:.2f}",
                ", ".join(record.applied_flow_names),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 7 and record.portfolio_underflow:
                    item.setForeground(QColor("#b22222"))
                    item.setBackground(QColor("#fdeaea"))
                self.results_table.setItem(row, column, item)

        self.summary_label.setText(
            f"Months: {len(result.records)}   Cash: {result.final_cash_balance:.2f}   "
            f"Portfolio: {result.final_portfolio_balance:.2f}   Total: {result.final_total_balance:.2f}"
        )
        self.refresh_timeline()

    def save_plan(self) -> None:
        try:
            plan = self._build_plan()
        except Exception as exc:
            QMessageBox.critical(self, "Save error", str(exc))
            return

        if self.current_file is not None:
            self._save_plan_to_path(plan, self.current_file, save_as_current=True)
            return

        self.save_plan_as()

    def save_plan_as(self) -> None:
        try:
            plan = self._build_plan()
        except Exception as exc:
            QMessageBox.critical(self, "Save error", str(exc))
            return

        initial_path = str(self.current_file) if self.current_file is not None else ""
        path, _ = QFileDialog.getSaveFileName(self, "Save Scenario", initial_path, "JSON files (*.json)")
        if not path:
            return

        self._save_plan_to_path(plan, Path(path), save_as_current=True)

    def load_plan(self) -> None:
        if not self._confirm_discard_unsaved_changes():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Load Scenario", "", "JSON files (*.json)")
        if not path:
            return

        self.load_plan_from_path(Path(path))

    def load_plan_from_path(self, path: Path) -> bool:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            plan = plan_from_dict(data)
        except Exception as exc:
            QMessageBox.critical(self, "Load error", str(exc))
            return False

        ui_state = data.get("_ui", {}) if isinstance(data, dict) else {}
        parameters = ui_state.get("parameters", {}) if isinstance(ui_state, dict) else {}
        scenario_rows = ui_state.get("scenario_rows", []) if isinstance(ui_state, dict) else []

        self._suspend_change_tracking = True
        try:
            self.start_month_edit.setText(plan.start_month.isoformat())
            retirement_month = parameters.get(self.RETIREMENT_MONTH_REFERENCE, plan.start_month.isoformat())
            self.retirement_month_edit.setText(str(retirement_month))
            self.birthday_edit.setText(plan.person.birth_date.isoformat())
            self.target_age_spin.setValue(plan.person.target_age_years)
            self.starting_cash_spin.setValue(plan.starting_cash_balance)
            self.portfolio_start_spin.setValue(plan.portfolio.starting_balance)
            self.portfolio_growth_spin.setValue(plan.portfolio.annual_growth_rate * 100.0)

            self.scenario_table.setRowCount(0)
            if isinstance(scenario_rows, list) and scenario_rows:
                for row in scenario_rows:
                    if not isinstance(row, dict):
                        continue
                    self._append_scenario_row(
                        [
                            bool(row.get("enabled", True)),
                            str(row.get("type", "")),
                            str(row.get("category", "general")),
                            str(row.get("amount", "0")),
                            str(row.get("target", FlowTarget.CASH.value)),
                            str(row.get("frequency", "")),
                            str(row.get("start", "")),
                            str(row.get("end", "")),
                            str(row.get("adjustment_rate", "")),
                        ]
                    )
            else:
                for flow in plan.recurring_flows:
                    self._append_scenario_row(
                        [
                            flow.enabled,
                            "RecurringFlow",
                            flow.category,
                            str(flow.amount),
                            flow.target.value,
                            flow.frequency.value,
                            flow.starts_on.isoformat(),
                            flow.ends_on.isoformat() if flow.ends_on else "",
                            str(flow.annual_adjustment_rate * 100.0),
                        ]
                    )
                for event in plan.one_off_events:
                    self._append_scenario_row(
                        [
                            event.enabled,
                            "OneOffEvent",
                            event.category,
                            str(event.amount),
                            event.target.value,
                            "",
                            event.occurs_on.isoformat(),
                            "",
                            "",
                        ]
                    )
        finally:
            self._suspend_change_tracking = False

        self.current_file = Path(path)
        self.settings_store.set_last_scenario_path(self.current_file)
        self._set_dirty(False)
        self._sort_scenario_table(select_row_id=self._selected_scenario_row_id())
        self._update_scenario_sort_indicator()
        self.refresh_timeline()
        self.run_simulation()
        return True

    def refresh_timeline(self) -> None:
        try:
            plan = self._build_plan()
        except Exception:
            self.timeline_widget.set_timeline(None, None, [])
            self.balance_timeline_widget.set_timeline(None, None, [])
            self.event_timeline_widget.set_timeline(None, None, [])
            return

        plan_end = add_months(plan.start_month, max(plan.simulation_months() - 1, 0))
        try:
            result = SimulationEngine().run(plan)
        except Exception:
            self.timeline_widget.set_timeline(None, None, [])
            self.balance_timeline_widget.set_timeline(None, None, [])
            self.event_timeline_widget.set_timeline(None, None, [])
            return

        scenario_series, balance_series = self._chart_series(plan, result, plan_end)
        self.timeline_widget.set_timeline(plan.start_month, plan_end, scenario_series)
        self.balance_timeline_widget.set_timeline(plan.start_month, plan_end, balance_series)
        self.event_timeline_widget.set_timeline(plan.start_month, plan_end, self._event_timeline_items(plan, plan_end))
        self._update_chart_container_size()

    def _chart_series(self, plan: Plan, result, plan_end: date) -> tuple[list[ChartSeries], list[ChartSeries]]:
        scenario_series: list[ChartSeries] = []
        balance_series: list[ChartSeries] = []
        semiannual_months = self._semiannual_months(plan.start_month, plan_end)

        for flow, effective_end in self._effective_recurring_flows(plan, plan_end):
            points: list[ChartPoint] = []
            for current_month in semiannual_months:
                if current_month < flow.starts_on or current_month > effective_end:
                    continue
                if not flow.occurs_in_month(current_month):
                    continue
                periods = month_index(plan.start_month, current_month)
                points.append(ChartPoint(current_month, flow.nominal_amount_for_period(periods)))

            if points:
                scenario_series.append(
                    ChartSeries(
                        name=flow.display_label,
                        color=QColor(SUCCESS_COLOR) if flow.target == FlowTarget.PORTFOLIO else QColor(INFO_COLOR),
                        points=points,
                        series_type="flow",
                    )
                )

        for event in plan.one_off_events:
            if not event.enabled:
                continue
            scenario_series.append(
                ChartSeries(
                    name=event.display_label,
                    color=QColor(WARNING_COLOR),
                    points=[ChartPoint(event.occurs_on, event.amount)],
                    series_type="event",
                )
            )

        balance_specs = [
            ("Cash Balance", QColor("#4a5568"), "cash_balance"),
            ("Portfolio", QColor("#7f3c8d"), "portfolio_balance"),
            ("Total", QColor(TEXT_COLOR), "total_balance"),
        ]
        for label, color, attribute in balance_specs:
            points = [
                ChartPoint(record.month, getattr(record, attribute))
                for record in result.records[::6]
            ]
            if result.records and (not points or points[-1].month != result.records[-1].month):
                points.append(ChartPoint(result.records[-1].month, getattr(result.records[-1], attribute)))
            if points:
                balance_series.append(ChartSeries(name=label, color=color, points=points, series_type="balance"))

        return scenario_series, balance_series

    def _semiannual_months(self, plan_start: date, plan_end: date) -> list[date]:
        months: list[date] = []
        offset = 0
        while True:
            current = add_months(plan_start, offset)
            if current > plan_end:
                break
            months.append(current)
            offset += 6
        if not months or months[-1] != plan_end:
            months.append(plan_end)
        return months

    def _effective_recurring_flows(self, plan: Plan, plan_end: date) -> list[tuple[RecurringFlow, date]]:
        grouped: dict[tuple[str, str], list[RecurringFlow]] = {}
        for flow in plan.recurring_flows:
            if not flow.enabled:
                continue
            grouped.setdefault((flow.__class__.__name__, flow.category), []).append(flow)

        effective_flows: list[tuple[RecurringFlow, date]] = []
        for flows in grouped.values():
            ordered = sorted(flows, key=lambda item: item.starts_on)
            for index, flow in enumerate(ordered):
                effective_end = add_months(flow.ends_on, -1) if flow.ends_on is not None else plan_end
                if index < len(ordered) - 1:
                    successor_start = ordered[index + 1].starts_on
                    effective_end = min(effective_end, add_months(successor_start, -1))
                if effective_end >= flow.starts_on:
                    effective_flows.append((flow, effective_end))
        return effective_flows

    def _event_timeline_items(self, plan: Plan, plan_end: date) -> list[EventTimelineItem]:
        items: list[EventTimelineItem] = []
        for flow, effective_end in self._effective_recurring_flows(plan, plan_end):
            items.append(
                EventTimelineItem(
                    name=flow.display_label,
                    start=flow.starts_on,
                    end=effective_end,
                    color=QColor(SUCCESS_COLOR) if flow.target == FlowTarget.PORTFOLIO else QColor(INFO_COLOR),
                    item_type="recurring",
                )
            )
        for event in plan.one_off_events:
            if not event.enabled:
                continue
            items.append(
                EventTimelineItem(
                    name=event.display_label,
                    start=event.occurs_on,
                    end=event.occurs_on,
                    color=QColor(WARNING_COLOR),
                    item_type="one_off",
                )
            )
        return sorted(items, key=lambda item: (item.start, item.end, item.name))

    def _update_chart_container_size(self) -> None:
        spacing = self.chart_layout.spacing()
        chart_width = max(self.timeline_widget.sizeHint().width(), self.balance_timeline_widget.sizeHint().width())
        chart_height = self.timeline_widget.sizeHint().height() + self.balance_timeline_widget.sizeHint().height()
        total_height = chart_height + spacing + 8
        self.chart_container.setMinimumSize(chart_width, total_height)
        self.chart_container.resize(chart_width, total_height)

    def _update_window_title(self) -> None:
        file_name = self.current_file.name if self.current_file is not None else "No scenario loaded"
        self.setWindowTitle(f"Afterwork Planner - {file_name}[*]")

    def _save_plan_to_path(self, plan: Plan, path: Path, *, save_as_current: bool, show_errors: bool = True) -> bool:
        try:
            path.write_text(json.dumps(self._save_payload(plan), indent=2), encoding="utf-8")
        except Exception as exc:
            if show_errors:
                QMessageBox.critical(self, "Save error", str(exc))
            return False

        if save_as_current:
            self.current_file = path
        self.settings_store.set_last_scenario_path(self.current_file if self.current_file is not None else path)
        self._set_dirty(False)
        return True

    def _autosave_current_plan(self) -> bool:
        if not self.is_dirty:
            return True

        try:
            plan = self._build_plan()
        except Exception:
            return False

        autosave_target = self.current_file if self.current_file is not None else self.autosave_path
        if self._save_plan_to_path(
            plan,
            autosave_target,
            save_as_current=self.current_file is None,
            show_errors=False,
        ):
            return True
        return False

    def _confirm_discard_unsaved_changes(self) -> bool:
        if not self.is_dirty:
            return True
        if self._autosave_current_plan():
            return True

        dialog = QMessageBox(self)
        dialog.setWindowTitle("Unsaved changes")
        dialog.setText("The current scenario has unsaved changes.")
        dialog.setInformativeText("Save before continuing?")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        dialog.setDefaultButton(QMessageBox.StandardButton.Save)
        choice = dialog.exec()

        if choice == QMessageBox.StandardButton.Save:
            self.save_plan()
            return not self.is_dirty
        return choice == QMessageBox.StandardButton.Discard

    def closeEvent(self, event: QCloseEvent) -> None:
        self.autosave_timer.stop()
        if self._confirm_discard_unsaved_changes():
            event.accept()
            return
        event.ignore()


def main() -> None:
    parser = argparse.ArgumentParser(prog="afterwork-ui")
    parser.add_argument("scenario", nargs="?", help="Path to a scenario JSON file")
    args = parser.parse_args()

    settings_store = SettingsStore()
    settings_store.ensure_exists()

    app = QApplication(sys.argv)
    apply_app_theme(app)
    window = PlannerWindow(settings_store)
    startup_path: Path | None = None

    if args.scenario:
        startup_path = Path(args.scenario).expanduser()
    else:
        startup_path = settings_store.get_last_scenario_path()

    if startup_path is not None:
        if startup_path.exists():
            window.load_plan_from_path(startup_path)
        elif args.scenario:
            QMessageBox.critical(window, "Load error", f"Scenario file not found: {startup_path}")

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
