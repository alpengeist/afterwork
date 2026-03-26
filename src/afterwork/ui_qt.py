from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QBrush, QFontMetrics, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFileDialog,
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
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
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
    plan_from_json,
    plan_to_json,
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


class TimelineWidget(QWidget):
    LEFT_MARGIN = 70
    RIGHT_MARGIN = 170
    TOP_MARGIN = 34
    BOTTOM_MARGIN = 34
    MIN_CHART_HEIGHT = 280
    MONTH_WIDTH = 10
    Y_AXIS_INTERVAL_HEIGHT = 10
    
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
        months = self._timeline_months()
        width = self.LEFT_MARGIN + self.RIGHT_MARGIN + max(months, 1) * self.MONTH_WIDTH
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
        pixmap.fill(QColor("#ffffff"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.plan_start is None or self.plan_end is None:
            painter.setPen(QColor("#666666"))
            painter.drawText(self.rect().adjusted(16, 16, -16, -16), "Timeline is unavailable until the scenario dates are valid.")
        else:
            self._draw_axes(painter)
            self._draw_quarter_grid(painter)
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

    def _x_for_month(self, value: date, center: bool = False) -> int:
        if self.plan_start is None:
            return self.LEFT_MARGIN
        offset = max(month_index(self.plan_start, value), 0)
        if center:
            offset += 0.5
        return round(self.LEFT_MARGIN + offset * self.MONTH_WIDTH)

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
        axis_pen = QPen(QColor("#97a3b3"))
        painter.setPen(axis_pen)
        painter.drawLine(self.LEFT_MARGIN, self._plot_top(), self.LEFT_MARGIN, self._plot_bottom())
        painter.drawLine(self.LEFT_MARGIN, self._plot_bottom(), self.width() - self.RIGHT_MARGIN + 30, self._plot_bottom())
        right_axis_x = self.width() - self.RIGHT_MARGIN + 30
        painter.drawLine(right_axis_x, self._plot_top(), right_axis_x, self._plot_bottom())

        minimum, maximum = self._value_range()
        tick_pen = QPen(QColor("#657182"))
        grid_pen = QPen(QColor("#d8dde3"))
        grid_pen.setStyle(Qt.PenStyle.DashLine)
        major_grid_pen = QPen(QColor("#9aa7b8"))
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
            painter.setPen(QPen(QColor("#b8c0cb"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(self.LEFT_MARGIN, zero_y, right_axis_x, zero_y)

    def _draw_quarter_grid(self, painter: QPainter) -> None:
        assert self.plan_start is not None
        total_months = self._timeline_months()
        quarter_pen = QPen(QColor("#c1cad6"))
        label_pen = QPen(QColor("#5b6470"))

        for month_offset in range(0, total_months + 1, 3):
            tick_date = add_months(self.plan_start, month_offset)
            x = self.LEFT_MARGIN + month_offset * self.MONTH_WIDTH
            painter.setPen(quarter_pen)
            painter.drawLine(x, self._plot_top(), x, self._plot_bottom())
            if tick_date.month == 1:
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
        painter.setBrush(QBrush(QColor(255, 255, 255, 235)))
        painter.drawRoundedRect(bubble_rect, 6, 6)
        painter.drawText(bubble_rect.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter, hover_text)

    def _hover_text(self, pos: QPoint) -> str:
        month_value = self._month_for_x(pos.x())
        y_value = self._value_for_y(pos.y())
        return f"{month_value.isoformat()} | {y_value:,.0f}"

    def _month_for_x(self, x_pos: int) -> date:
        assert self.plan_start is not None and self.plan_end is not None
        relative = x_pos - self.LEFT_MARGIN
        month_offset = round(relative / self.MONTH_WIDTH)
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


class PlannerWindow(QMainWindow):
    TOOLBAR_BUTTON_WIDTH = 118
    TOOLBAR_BUTTON_HEIGHT = 36

    def __init__(self, settings_store: SettingsStore) -> None:
        super().__init__()
        self.settings_store = settings_store
        self.current_file: Path | None = None
        self.current_result = None
        self.setWindowTitle("Afterwork Planner")
        self.resize(1500, 900)

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)

        self.scenario_name_label = QLabel("No scenario loaded")
        scenario_font = self.scenario_name_label.font()
        scenario_font.setPointSize(scenario_font.pointSize() + 4)
        scenario_font.setBold(True)
        self.scenario_name_label.setFont(scenario_font)
        self.scenario_name_label.setContentsMargins(10, 6, 10, 0)
        root_layout.addWidget(self.scenario_name_label)

        splitter = QSplitter(Qt.Orientation.Vertical)
        root_layout.addWidget(splitter)

        splitter.addWidget(self._build_scenario_panel())
        splitter.addWidget(self._build_timeline_panel())
        splitter.addWidget(self._build_results_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 3)

        self._connect_refresh_signals()
        self.refresh_timeline()
        self.run_simulation()

    def _build_scenario_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        settings = QWidget()
        settings_layout = QGridLayout(settings)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setHorizontalSpacing(10)
        settings_layout.setVerticalSpacing(6)

        self.start_month_edit = QLineEdit("2026-01-01")
        self.start_month_edit.setFixedWidth(110)
        self.birthday_edit = QLineEdit("1986-01-01")
        self.birthday_edit.setFixedWidth(110)
        self.target_age_spin = QSpinBox()
        self.target_age_spin.setRange(0, 130)
        self.target_age_spin.setValue(95)
        self.target_age_spin.setFixedWidth(72)
        self.starting_cash_spin = QDoubleSpinBox()
        self.starting_cash_spin.setRange(-9_999_999, 9_999_999)
        self.starting_cash_spin.setDecimals(2)
        self.starting_cash_spin.setValue(25_000)
        self.starting_cash_spin.setFixedWidth(118)
        self.portfolio_start_spin = QDoubleSpinBox()
        self.portfolio_start_spin.setRange(-9_999_999, 9_999_999)
        self.portfolio_start_spin.setDecimals(2)
        self.portfolio_start_spin.setValue(50_000)
        self.portfolio_start_spin.setFixedWidth(118)
        self.portfolio_growth_spin = QDoubleSpinBox()
        self.portfolio_growth_spin.setRange(-1.0, 10.0)
        self.portfolio_growth_spin.setDecimals(4)
        self.portfolio_growth_spin.setSingleStep(0.005)
        self.portfolio_growth_spin.setValue(5.0)
        self.portfolio_growth_spin.setFixedWidth(96)

        fields = [
            ("Start Month", self.start_month_edit),
            ("Birthday", self.birthday_edit),
            ("Target Age", self.target_age_spin),
            ("Starting Cash", self.starting_cash_spin),
            ("Starting Portfolio", self.portfolio_start_spin),
            ("Portfolio Growth %", self.portfolio_growth_spin),
        ]
        for index, (label, widget) in enumerate(fields):
            settings_layout.addWidget(QLabel(label), 0, index * 2)
            settings_layout.addWidget(widget, 0, index * 2 + 1)
        settings_layout.setColumnStretch(len(fields) * 2, 1)

        layout.addWidget(settings)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        for label, handler in [
            ("Add Flow", self.add_recurring_flow),
            ("Add Event", self.add_one_off_event),
            ("Delete Row", self.delete_selected_row),
            ("Run Simulation", self.run_simulation),
            ("Save", self.save_plan),
            ("Load", self.load_plan),
        ]:
            button = QPushButton(label)
            button.setFixedSize(self.TOOLBAR_BUTTON_WIDTH, self.TOOLBAR_BUTTON_HEIGHT)
            button.setStyleSheet(
                """
                QPushButton {
                    background-color: #d8e7f5;
                    border: 1px solid #8eabc7;
                    border-radius: 6px;
                    color: #16324a;
                    font-weight: 600;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #c8def1;
                    border-color: #6f95bb;
                }
                QPushButton:pressed {
                    background-color: #b8d1e8;
                }
                """
            )
            button.clicked.connect(handler)
            toolbar.addWidget(button)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.scenario_table = QTableWidget(0, len(SCENARIO_HEADERS))
        self.scenario_table.setHorizontalHeaderLabels(SCENARIO_HEADERS)
        self.scenario_table.setItemDelegate(TableTextDelegate(self.scenario_table))
        self.scenario_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.scenario_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.scenario_table.horizontalHeader().setStretchLastSection(True)
        self.scenario_table.verticalHeader().setVisible(False)
        self.scenario_table.setStyleSheet(
            """
            QTableWidget::item:selected {
                background-color: #1f6aa5;
                color: #ffffff;
                border-top: 1px solid #0f3f66;
                border-bottom: 1px solid #0f3f66;
            }
            QTableWidget::item:selected:active {
                background-color: #1f6aa5;
                color: #ffffff;
            }
            QTableWidget::item:selected:!active {
                background-color: #5689b5;
                color: #ffffff;
            }
            """
        )
        layout.addWidget(self.scenario_table)

        return panel

    def _build_timeline_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Value Timeline")
        title.setContentsMargins(10, 6, 10, 0)
        layout.addWidget(title)

        self.chart_container = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_container)
        self.chart_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_layout.setSpacing(12)

        self.scenario_chart_title = QLabel("Scenario Values")
        self.scenario_chart_title.setContentsMargins(10, 0, 10, 0)
        self.chart_layout.addWidget(self.scenario_chart_title)

        self.timeline_widget = TimelineWidget(
            y_axis_interval=100.0,
            y_axis_label_interval=1_000.0,
            dynamic_height=True,
            include_event_values_in_scale=False,
            pin_events_to_zero=True,
        )
        self.chart_layout.addWidget(self.timeline_widget)

        self.balance_chart_title = QLabel("Balances")
        self.balance_chart_title.setContentsMargins(10, 0, 10, 0)
        self.chart_layout.addWidget(self.balance_chart_title)

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
        self.timeline_scroll.setWidget(self.chart_container)
        self.timeline_scroll.horizontalScrollBar().setSingleStep(self.timeline_widget.MONTH_WIDTH * 2)
        layout.addWidget(self.timeline_scroll)
        return panel

    def _build_results_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.summary_label = QLabel("No simulation results yet.")
        layout.addWidget(self.summary_label)

        self.results_table = QTableWidget(0, len(RESULT_HEADERS))
        self.results_table.setHorizontalHeaderLabels(RESULT_HEADERS)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.verticalHeader().setVisible(False)
        layout.addWidget(self.results_table)
        return panel

    def _connect_refresh_signals(self) -> None:
        self.scenario_table.itemChanged.connect(self.refresh_timeline)
        self.start_month_edit.editingFinished.connect(self.refresh_timeline)
        self.birthday_edit.editingFinished.connect(self.refresh_timeline)
        self.target_age_spin.valueChanged.connect(self.refresh_timeline)

    def _enabled_item(self, enabled: bool) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        item.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
        return item

    def _append_scenario_row(self, values: list[str | bool]) -> None:
        row = self.scenario_table.rowCount()
        self.scenario_table.insertRow(row)
        for column, value in enumerate(values):
            if column == 0:
                self.scenario_table.setItem(row, column, self._enabled_item(bool(value)))
            else:
                self.scenario_table.setItem(row, column, QTableWidgetItem(str(value)))

    def add_recurring_flow(self) -> None:
        self._append_scenario_row(
            [True, "RecurringFlow", "general", "0", "cash", "monthly", self.start_month_edit.text(), "", "0.0"]
        )
        self.refresh_timeline()

    def add_one_off_event(self) -> None:
        self._append_scenario_row(
            [True, "OneOffEvent", "general", "0", "cash", "", self.start_month_edit.text(), "", ""]
        )
        self.refresh_timeline()

    def delete_selected_row(self) -> None:
        row = self.scenario_table.currentRow()
        if row >= 0:
            self.scenario_table.removeRow(row)
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
                        starts_on=date.fromisoformat(start),
                        ends_on=date.fromisoformat(end) if end else None,
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
                        occurs_on=date.fromisoformat(start),
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

        path, _ = QFileDialog.getSaveFileName(self, "Save Scenario", "", "JSON files (*.json)")
        if not path:
            return

        plan_to_json(plan, path)
        self.current_file = Path(path)
        self.settings_store.set_last_scenario_path(self.current_file)
        self._update_scenario_name()
        self.setWindowTitle(f"Afterwork Planner - {self.current_file}")

    def load_plan(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load Scenario", "", "JSON files (*.json)")
        if not path:
            return

        self.load_plan_from_path(Path(path))

    def load_plan_from_path(self, path: Path) -> bool:
        try:
            plan = plan_from_json(path)
        except Exception as exc:
            QMessageBox.critical(self, "Load error", str(exc))
            return False

        self.start_month_edit.setText(plan.start_month.isoformat())
        self.birthday_edit.setText(plan.person.birth_date.isoformat())
        self.target_age_spin.setValue(plan.person.target_age_years)
        self.starting_cash_spin.setValue(plan.starting_cash_balance)
        self.portfolio_start_spin.setValue(plan.portfolio.starting_balance)
        self.portfolio_growth_spin.setValue(plan.portfolio.annual_growth_rate * 100.0)

        self.scenario_table.setRowCount(0)
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

        self.current_file = Path(path)
        self.settings_store.set_last_scenario_path(self.current_file)
        self._update_scenario_name()
        self.setWindowTitle(f"Afterwork Planner - {self.current_file}")
        self.refresh_timeline()
        self.run_simulation()
        return True

    def refresh_timeline(self) -> None:
        try:
            plan = self._build_plan()
        except Exception:
            self.timeline_widget.set_timeline(None, None, [])
            self.balance_timeline_widget.set_timeline(None, None, [])
            return

        plan_end = add_months(plan.start_month, max(plan.simulation_months() - 1, 0))
        try:
            result = SimulationEngine().run(plan)
        except Exception:
            self.timeline_widget.set_timeline(None, None, [])
            self.balance_timeline_widget.set_timeline(None, None, [])
            return

        scenario_series, balance_series = self._chart_series(plan, result, plan_end)
        self.timeline_widget.set_timeline(plan.start_month, plan_end, scenario_series)
        self.balance_timeline_widget.set_timeline(plan.start_month, plan_end, balance_series)
        self._update_chart_container_size()

    def _chart_series(self, plan: Plan, result, plan_end: date) -> tuple[list[ChartSeries], list[ChartSeries]]:
        scenario_series: list[ChartSeries] = []
        balance_series: list[ChartSeries] = []
        quarterly_months = self._quarterly_months(plan.start_month, plan_end)

        for flow, effective_end in self._effective_recurring_flows(plan, plan_end):
            points: list[ChartPoint] = []
            for current_month in quarterly_months:
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
                        color=QColor("#2f8f63") if flow.target == FlowTarget.PORTFOLIO else QColor("#2e6ea6"),
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
                    color=QColor("#d9822b"),
                    points=[ChartPoint(event.occurs_on, event.amount)],
                    series_type="event",
                )
            )

        balance_specs = [
            ("Cash Balance", QColor("#4a5568"), "cash_balance"),
            ("Portfolio", QColor("#7f3c8d"), "portfolio_balance"),
            ("Total", QColor("#111827"), "total_balance"),
        ]
        for label, color, attribute in balance_specs:
            points = [
                ChartPoint(record.month, getattr(record, attribute))
                for record in result.records[::3]
            ]
            if result.records and (not points or points[-1].month != result.records[-1].month):
                points.append(ChartPoint(result.records[-1].month, getattr(result.records[-1], attribute)))
            if points:
                balance_series.append(ChartSeries(name=label, color=color, points=points, series_type="balance"))

        return scenario_series, balance_series

    def _quarterly_months(self, plan_start: date, plan_end: date) -> list[date]:
        months: list[date] = []
        offset = 0
        while True:
            current = add_months(plan_start, offset)
            if current > plan_end:
                break
            months.append(current)
            offset += 3
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
                effective_end = flow.ends_on or plan_end
                if index < len(ordered) - 1:
                    successor_start = ordered[index + 1].starts_on
                    effective_end = min(effective_end, add_months(successor_start, -1))
                if effective_end >= flow.starts_on:
                    effective_flows.append((flow, effective_end))
        return effective_flows

    def _update_chart_container_size(self) -> None:
        title_heights = self.scenario_chart_title.sizeHint().height() + self.balance_chart_title.sizeHint().height()
        spacing = self.chart_layout.spacing()
        chart_width = max(self.timeline_widget.sizeHint().width(), self.balance_timeline_widget.sizeHint().width())
        chart_height = self.timeline_widget.sizeHint().height() + self.balance_timeline_widget.sizeHint().height()
        total_height = title_heights + chart_height + spacing * 3 + 8
        self.chart_container.setMinimumSize(chart_width, total_height)
        self.chart_container.resize(chart_width, total_height)

    def _update_scenario_name(self) -> None:
        self.scenario_name_label.setText(self.current_file.name if self.current_file is not None else "No scenario loaded")


def main() -> None:
    parser = argparse.ArgumentParser(prog="afterwork-ui")
    parser.add_argument("scenario", nargs="?", help="Path to a scenario JSON file")
    args = parser.parse_args()

    settings_store = SettingsStore()
    settings_store.ensure_exists()

    app = QApplication(sys.argv)
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
