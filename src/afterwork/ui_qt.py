from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
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


SCENARIO_HEADERS = ["Type", "Name", "Amount", "Target", "Frequency", "Start", "Category", "Discount Rate"]
RESULT_HEADERS = [
    "Month",
    "Age",
    "Cash Flow",
    "Portfolio In",
    "Portfolio Growth",
    "Discounted Flow",
    "Cash Balance",
    "Portfolio Value",
    "Total Value",
    "Flows",
]


class PlannerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.current_file: Path | None = None
        self.setWindowTitle("Afterwork Planner")
        self.resize(1500, 900)

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)

        splitter = QSplitter(Qt.Orientation.Vertical)
        root_layout.addWidget(splitter)

        splitter.addWidget(self._build_scenario_panel())
        splitter.addWidget(self._build_results_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        self._populate_demo_data()
        self.run_simulation()

    def _build_scenario_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        settings = QWidget()
        settings_layout = QHBoxLayout(settings)

        self.start_month_edit = QLineEdit("2026-01-01")
        self.current_age_spin = QSpinBox()
        self.current_age_spin.setRange(0, 130)
        self.current_age_spin.setValue(40)
        self.target_age_spin = QSpinBox()
        self.target_age_spin.setRange(0, 130)
        self.target_age_spin.setValue(95)
        self.starting_cash_spin = QDoubleSpinBox()
        self.starting_cash_spin.setRange(-1_000_000_000, 1_000_000_000)
        self.starting_cash_spin.setDecimals(2)
        self.starting_cash_spin.setValue(25_000)
        self.portfolio_start_spin = QDoubleSpinBox()
        self.portfolio_start_spin.setRange(-1_000_000_000, 1_000_000_000)
        self.portfolio_start_spin.setDecimals(2)
        self.portfolio_start_spin.setValue(50_000)
        self.portfolio_growth_spin = QDoubleSpinBox()
        self.portfolio_growth_spin.setRange(-1.0, 10.0)
        self.portfolio_growth_spin.setDecimals(4)
        self.portfolio_growth_spin.setSingleStep(0.005)
        self.portfolio_growth_spin.setValue(0.05)

        for label, widget in [
            ("Start Month", self.start_month_edit),
            ("Current Age", self.current_age_spin),
            ("Target Age", self.target_age_spin),
            ("Starting Cash", self.starting_cash_spin),
            ("Starting Portfolio", self.portfolio_start_spin),
            ("Portfolio Growth", self.portfolio_growth_spin),
        ]:
            field = QWidget()
            field_layout = QFormLayout(field)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.addRow(label, widget)
            settings_layout.addWidget(field)

        layout.addWidget(settings)

        toolbar = QHBoxLayout()
        for label, handler in [
            ("Add Flow", self.add_recurring_flow),
            ("Add Event", self.add_one_off_event),
            ("Delete Row", self.delete_selected_row),
            ("Run Simulation", self.run_simulation),
            ("Save JSON", self.save_plan),
            ("Load JSON", self.load_plan),
        ]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            toolbar.addWidget(button)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.scenario_table = QTableWidget(0, len(SCENARIO_HEADERS))
        self.scenario_table.setHorizontalHeaderLabels(SCENARIO_HEADERS)
        self.scenario_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.scenario_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.scenario_table.horizontalHeader().setStretchLastSection(True)
        self.scenario_table.verticalHeader().setVisible(False)
        layout.addWidget(self.scenario_table)

        hint = QLabel(
            "Rows with the same type and category automatically replace earlier rows from their start month onward."
        )
        layout.addWidget(hint)
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

    def _populate_demo_data(self) -> None:
        rows = [
            ["RecurringFlow", "Salary", "4500", "cash", "monthly", "2026-01-01", "income", "0.02"],
            ["RecurringFlow", "Rent", "-1500", "cash", "monthly", "2026-01-01", "housing", "0.02"],
            ["RecurringFlow", "ETF Savings", "900", "portfolio", "monthly", "2026-01-01", "savings", "0.02"],
            ["RecurringFlow", "ETF Savings", "1200", "portfolio", "monthly", "2035-01-01", "savings", "0.02"],
            ["OneOffEvent", "Inheritance", "75000", "cash", "", "2035-06-01", "windfall", ""],
        ]
        for row in rows:
            self._append_scenario_row(row)

    def _append_scenario_row(self, values: list[str]) -> None:
        row = self.scenario_table.rowCount()
        self.scenario_table.insertRow(row)
        for column, value in enumerate(values):
            self.scenario_table.setItem(row, column, QTableWidgetItem(value))

    def add_recurring_flow(self) -> None:
        self._append_scenario_row(
            ["RecurringFlow", "New flow", "0", "cash", "monthly", self.start_month_edit.text(), "general", "0.0"]
        )

    def add_one_off_event(self) -> None:
        self._append_scenario_row(
            ["OneOffEvent", "New event", "0", "cash", "", self.start_month_edit.text(), "general", ""]
        )

    def delete_selected_row(self) -> None:
        row = self.scenario_table.currentRow()
        if row >= 0:
            self.scenario_table.removeRow(row)

    def _scenario_value(self, row: int, column: int) -> str:
        item = self.scenario_table.item(row, column)
        return item.text().strip() if item is not None else ""

    def _build_plan(self) -> Plan:
        recurring_flows: list[RecurringFlow] = []
        one_off_events: list[OneOffEvent] = []

        for row in range(self.scenario_table.rowCount()):
            item_type = self._scenario_value(row, 0)
            name = self._scenario_value(row, 1)
            amount = self._scenario_value(row, 2)
            target = self._scenario_value(row, 3)
            frequency = self._scenario_value(row, 4)
            start = self._scenario_value(row, 5)
            category = self._scenario_value(row, 6) or "general"
            discount_rate = self._scenario_value(row, 7)

            if item_type == "RecurringFlow":
                recurring_flows.append(
                    RecurringFlow(
                        name=name,
                        amount=float(amount),
                        target=FlowTarget(target),
                        frequency=Frequency(frequency),
                        starts_on=date.fromisoformat(start),
                        category=category,
                        annual_discount_rate=float(discount_rate or 0.0),
                    )
                )
            elif item_type == "OneOffEvent":
                one_off_events.append(
                    OneOffEvent(
                        name=name,
                        amount=float(amount),
                        target=FlowTarget(target),
                        occurs_on=date.fromisoformat(start),
                        category=category,
                    )
                )
            else:
                raise ValueError(f"Unsupported row type: {item_type!r}")

        return Plan(
            person=Person(
                current_age_years=self.current_age_spin.value(),
                target_age_years=self.target_age_spin.value(),
            ),
            start_month=date.fromisoformat(self.start_month_edit.text().strip()),
            starting_cash_balance=self.starting_cash_spin.value(),
            portfolio=Portfolio(
                starting_balance=self.portfolio_start_spin.value(),
                annual_growth_rate=self.portfolio_growth_spin.value(),
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
                f"{record.discounted_flow_real:.2f}",
                f"{record.cash_balance:.2f}",
                f"{record.portfolio_balance:.2f}",
                f"{record.total_balance:.2f}",
                ", ".join(record.applied_flow_names),
            ]
            for column, value in enumerate(values):
                self.results_table.setItem(row, column, QTableWidgetItem(value))

        self.summary_label.setText(
            f"Months: {len(result.records)}   Cash: {result.final_cash_balance:.2f}   "
            f"Portfolio: {result.final_portfolio_balance:.2f}   Total: {result.final_total_balance:.2f}"
        )

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
        self.setWindowTitle(f"Afterwork Planner - {self.current_file}")

    def load_plan(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load Scenario", "", "JSON files (*.json)")
        if not path:
            return

        try:
            plan = plan_from_json(path)
        except Exception as exc:
            QMessageBox.critical(self, "Load error", str(exc))
            return

        self.start_month_edit.setText(plan.start_month.isoformat())
        self.current_age_spin.setValue(plan.person.current_age_years)
        self.target_age_spin.setValue(plan.person.target_age_years)
        self.starting_cash_spin.setValue(plan.starting_cash_balance)
        self.portfolio_start_spin.setValue(plan.portfolio.starting_balance)
        self.portfolio_growth_spin.setValue(plan.portfolio.annual_growth_rate)

        self.scenario_table.setRowCount(0)
        for flow in plan.recurring_flows:
            self._append_scenario_row(
                [
                    "RecurringFlow",
                    flow.name,
                    str(flow.amount),
                    flow.target.value,
                    flow.frequency.value,
                    flow.starts_on.isoformat(),
                    flow.category,
                    str(flow.annual_discount_rate),
                ]
            )
        for event in plan.one_off_events:
            self._append_scenario_row(
                [
                    "OneOffEvent",
                    event.name,
                    str(event.amount),
                    event.target.value,
                    "",
                    event.occurs_on.isoformat(),
                    event.category,
                    "",
                ]
            )

        self.current_file = Path(path)
        self.setWindowTitle(f"Afterwork Planner - {self.current_file}")
        self.run_simulation()


def main() -> None:
    app = QApplication(sys.argv)
    window = PlannerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
