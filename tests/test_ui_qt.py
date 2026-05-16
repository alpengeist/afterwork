from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractItemView, QComboBox, QLineEdit

from afterwork.app_settings import SettingsStore
from afterwork.domain import Plan
from afterwork.engine import SimulationEngine
from afterwork.ui_qt import PlannerWindow


class PlannerWindowScenarioSortingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        settings_path = Path(self.temp_dir.name) / "settings.json"
        self.window = PlannerWindow(SettingsStore(settings_path))
        self.window.autosave_timer.stop()

    def tearDown(self) -> None:
        self.window.close()
        self.temp_dir.cleanup()

    def _visible_line_editor_for_item(self, item) -> QLineEdit | None:
        rect = self.window.scenario_table.visualItemRect(item)
        return next(
            (
                editor
                for editor in self.window.scenario_table.viewport().findChildren(QLineEdit)
                if editor.isVisible() and editor.geometry().intersects(rect)
            ),
            None,
        )

    def _visible_combo_editor_for_item(self, item) -> QComboBox | None:
        rect = self.window.scenario_table.visualItemRect(item)
        return next(
            (
                editor
                for editor in self.window.scenario_table.viewport().findChildren(QComboBox)
                if editor.isVisible() and editor.geometry().intersects(rect)
            ),
            None,
        )

    def test_amount_header_sorts_rows_numerically(self) -> None:
        for amount in ("100", "20", "-5"):
            self.window.add_one_off_event()
            row = self.window.scenario_table.rowCount() - 1
            self.window.scenario_table.item(row, self.window.SCENARIO_AMOUNT_COLUMN).setText(amount)

        self.window._on_scenario_header_clicked(self.window.SCENARIO_AMOUNT_COLUMN)
        ascending = [
            self.window._scenario_value(row, self.window.SCENARIO_AMOUNT_COLUMN)
            for row in range(self.window.scenario_table.rowCount())
        ]
        self.assertEqual(ascending, ["-5", "20", "100"])

        self.window._on_scenario_header_clicked(self.window.SCENARIO_AMOUNT_COLUMN)
        descending = [
            self.window._scenario_value(row, self.window.SCENARIO_AMOUNT_COLUMN)
            for row in range(self.window.scenario_table.rowCount())
        ]
        self.assertEqual(descending, ["100", "20", "-5"])

    def test_frequency_header_sorts_rows_by_option_order_with_blank_last(self) -> None:
        self.window.add_recurring_flow()
        monthly_row = self.window.scenario_table.rowCount() - 1
        monthly_combo = self.window.scenario_table.cellWidget(monthly_row, self.window.SCENARIO_FREQUENCY_COLUMN)
        monthly_combo.setCurrentText("monthly")

        self.window.add_recurring_flow()
        yearly_row = self.window.scenario_table.rowCount() - 1
        yearly_combo = self.window.scenario_table.cellWidget(yearly_row, self.window.SCENARIO_FREQUENCY_COLUMN)
        yearly_combo.setCurrentText("yearly")

        self.window.add_one_off_event()

        self.window._on_scenario_header_clicked(self.window.SCENARIO_FREQUENCY_COLUMN)
        ascending = [
            self.window._scenario_value(row, self.window.SCENARIO_FREQUENCY_COLUMN)
            for row in range(self.window.scenario_table.rowCount())
        ]
        self.assertEqual(ascending, ["monthly", "yearly", ""])

        self.window._on_scenario_header_clicked(self.window.SCENARIO_FREQUENCY_COLUMN)
        descending = [
            self.window._scenario_value(row, self.window.SCENARIO_FREQUENCY_COLUMN)
            for row in range(self.window.scenario_table.rowCount())
        ]
        self.assertEqual(descending, ["yearly", "monthly", ""])

    def test_basis_and_target_headers_sort_by_option_order(self) -> None:
        self.window.add_recurring_flow()
        real_row = self.window.scenario_table.rowCount() - 1
        real_basis_combo = self.window.scenario_table.cellWidget(real_row, self.window.SCENARIO_AMOUNT_BASIS_COLUMN)
        real_basis_combo.setCurrentText("Real")

        self.window.add_recurring_flow()
        nominal_row = self.window.scenario_table.rowCount() - 1
        nominal_basis_combo = self.window.scenario_table.cellWidget(nominal_row, self.window.SCENARIO_AMOUNT_BASIS_COLUMN)
        nominal_basis_combo.setCurrentText("Nominal")
        portfolio_target_combo = self.window.scenario_table.cellWidget(nominal_row, self.window.SCENARIO_TARGET_COLUMN)
        portfolio_target_combo.setCurrentText("portfolio")

        self.window.add_recurring_flow()
        invest_row = self.window.scenario_table.rowCount() - 1
        invest_target_combo = self.window.scenario_table.cellWidget(invest_row, self.window.SCENARIO_TARGET_COLUMN)
        invest_target_combo.setCurrentText("invest")

        self.window.add_one_off_event()

        self.window._on_scenario_header_clicked(self.window.SCENARIO_AMOUNT_BASIS_COLUMN)
        basis_ascending = [
            self.window._scenario_value(row, self.window.SCENARIO_AMOUNT_BASIS_COLUMN)
            for row in range(self.window.scenario_table.rowCount())
        ]
        self.assertEqual(basis_ascending, ["Real", "Nominal", "Nominal", ""])

        self.window._on_scenario_header_clicked(self.window.SCENARIO_AMOUNT_BASIS_COLUMN)
        basis_descending = [
            self.window._scenario_value(row, self.window.SCENARIO_AMOUNT_BASIS_COLUMN)
            for row in range(self.window.scenario_table.rowCount())
        ]
        self.assertEqual(basis_descending, ["Nominal", "Nominal", "Real", ""])

        self.window._on_scenario_header_clicked(self.window.SCENARIO_TARGET_COLUMN)
        target_ascending = [
            self.window._scenario_value(row, self.window.SCENARIO_TARGET_COLUMN)
            for row in range(self.window.scenario_table.rowCount())
        ]
        self.assertEqual(target_ascending, ["cash", "cash", "invest", "portfolio"])

        self.window._on_scenario_header_clicked(self.window.SCENARIO_TARGET_COLUMN)
        target_descending = [
            self.window._scenario_value(row, self.window.SCENARIO_TARGET_COLUMN)
            for row in range(self.window.scenario_table.rowCount())
        ]
        self.assertEqual(target_descending, ["portfolio", "invest", "cash", "cash"])

    def test_loading_legacy_recurring_portfolio_target_maps_to_invest(self) -> None:
        path = Path(self.temp_dir.name) / "legacy.json"
        payload = {
            "person": {"birth_date": "1980-01-01", "target_age_years": 47},
            "start_month": "2026-01-01",
            "starting_cash_balance": 1000.0,
            "portfolio": {"starting_balance": 5000.0, "annual_growth_rate": 0.0},
            "recurring_flows": [
                {
                    "amount": 400.0,
                    "frequency": "monthly",
                    "starts_on": "2026-01-01",
                    "category": "legacy-invest",
                    "target": "portfolio",
                    "amount_basis": "Nominal",
                    "annual_adjustment_rate": 0.0,
                    "enabled": True,
                    "color": "#2563EB",
                }
            ],
            "_ui": {
                "parameters": {"retirement_month": "2030-01-01"},
                "scenario_rows": [
                    {
                        "enabled": True,
                        "type": "RecurringFlow",
                        "category": "legacy-invest",
                        "color": "#2563EB",
                        "amount": "400",
                        "amount_basis": "Nominal",
                        "target": "portfolio",
                        "frequency": "monthly",
                        "start": "2026-01-01",
                        "end": "",
                        "adjustment_rate": "0",
                    }
                ],
                "shock_rows": [],
            },
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

        self.assertTrue(self.window.load_plan_from_path(path))
        self.assertEqual(self.window._scenario_value(0, self.window.SCENARIO_TARGET_COLUMN), "invest")

    def test_scenario_combo_ignores_mouse_wheel_when_closed(self) -> None:
        self.window.add_recurring_flow()
        row = self.window.scenario_table.rowCount() - 1
        combo = self.window.scenario_table.cellWidget(row, self.window.SCENARIO_FREQUENCY_COLUMN)
        combo.setCurrentText("yearly")

        event = QWheelEvent(
            QPointF(5.0, 5.0),
            QPointF(5.0, 5.0),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(combo, event)

        self.assertEqual(combo.currentText(), "yearly")

    def test_active_toggle_recalculates_results_immediately(self) -> None:
        self.window.add_one_off_event()
        row = self.window.scenario_table.rowCount() - 1
        self.window.scenario_table.item(row, self.window.SCENARIO_AMOUNT_COLUMN).setText("500")

        self.window.run_simulation()
        self.assertEqual(self.window.current_result.records[0].cash_balance, 25_500.0)

        self.window._on_scenario_cell_pressed(row, 0)
        self.assertEqual(self.window.current_result.records[0].cash_balance, 25_000.0)

        self.window._on_scenario_cell_pressed(row, 0)
        self.assertEqual(self.window.current_result.records[0].cash_balance, 25_500.0)

    def test_result_amounts_render_without_decimal_places(self) -> None:
        self.window.add_one_off_event()
        row = self.window.scenario_table.rowCount() - 1
        self.window.scenario_table.item(row, self.window.SCENARIO_AMOUNT_COLUMN).setText("500")

        self.window.run_simulation()

        record = self.window.current_result.records[0]
        self.assertEqual(self.window.results_table.item(0, 2).text(), "500")
        self.assertEqual(self.window.results_table.item(0, 6).text(), "25500")
        self.assertEqual(self.window.results_table.item(0, 7).text(), f"{record.portfolio_balance:.0f}")
        self.assertEqual(self.window.results_table.item(0, 8).text(), f"{record.total_balance:.0f}")
        self.assertNotIn(".00", self.window.summary_label.text())

    def test_amount_editor_commits_on_enter_and_next_click_works(self) -> None:
        self.window.show()
        QApplication.processEvents()
        self.window.add_one_off_event()
        row = self.window.scenario_table.rowCount() - 1
        amount_column = self.window.SCENARIO_AMOUNT_COLUMN
        category_column = self.window.SCENARIO_CATEGORY_COLUMN
        amount_item = self.window.scenario_table.item(row, amount_column)

        self.window.scenario_table.setCurrentCell(row, amount_column)
        self.window.scenario_table.editItem(amount_item)
        QApplication.processEvents()

        editor = self.window.scenario_table.viewport().findChild(QLineEdit)
        self.assertIsInstance(editor, QLineEdit)
        editor.selectAll()
        QTest.keyClicks(editor, "123.4")
        QTest.keyClick(editor, Qt.Key.Key_Return)
        QApplication.processEvents()

        self.assertEqual(self.window.scenario_table.item(row, amount_column).text(), "123")
        self.assertNotEqual(self.window.scenario_table.state(), QAbstractItemView.State.EditingState)

        rect = self.window.scenario_table.visualItemRect(self.window.scenario_table.item(row, category_column))
        QTest.mouseClick(self.window.scenario_table.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, rect.center())
        QApplication.processEvents()

        self.assertEqual(self.window.scenario_table.currentColumn(), category_column)

    def test_date_editor_commits_on_enter_and_next_click_works(self) -> None:
        self.window.show()
        QApplication.processEvents()
        self.window.add_one_off_event()
        row = self.window.scenario_table.rowCount() - 1
        start_column = self.window.SCENARIO_START_COLUMN
        category_column = self.window.SCENARIO_CATEGORY_COLUMN
        start_item = self.window.scenario_table.item(row, start_column)

        self.window.scenario_table.setCurrentCell(row, start_column)
        self.window.scenario_table.editItem(start_item)
        QApplication.processEvents()

        start_rect = self.window.scenario_table.visualItemRect(start_item)
        editor = next(
            (
                combo
                for combo in self.window.scenario_table.viewport().findChildren(QComboBox)
                if combo.isVisible() and combo.geometry().intersects(start_rect)
            ),
            None,
        )
        self.assertIsInstance(editor, QComboBox)
        self.assertIsNotNone(editor.lineEdit())
        editor.lineEdit().selectAll()
        QTest.keyClicks(editor.lineEdit(), "2027-04-01")
        QTest.keyClick(editor.lineEdit(), Qt.Key.Key_Return)
        QApplication.processEvents()

        self.assertEqual(self.window.scenario_table.item(row, start_column).text(), "2027-04-01")
        self.assertNotEqual(self.window.scenario_table.state(), QAbstractItemView.State.EditingState)

        rect = self.window.scenario_table.visualItemRect(self.window.scenario_table.item(row, category_column))
        QTest.mouseClick(self.window.scenario_table.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, rect.center())
        QApplication.processEvents()

        self.assertEqual(self.window.scenario_table.currentColumn(), category_column)

    def test_date_combo_selection_closes_editor_and_next_cell_edits(self) -> None:
        self.window.show()
        QApplication.processEvents()
        self.window.add_recurring_flow()
        row = self.window.scenario_table.rowCount() - 1
        end_column = self.window.SCENARIO_END_COLUMN
        category_column = self.window.SCENARIO_CATEGORY_COLUMN
        end_item = self.window.scenario_table.item(row, end_column)

        self.window.scenario_table.setCurrentCell(row, end_column)
        self.window.scenario_table.editItem(end_item)
        QApplication.processEvents()

        editor = self._visible_combo_editor_for_item(end_item)
        self.assertIsInstance(editor, QComboBox)
        retirement_index = editor.findText(self.window.RETIREMENT_MONTH_LABEL)
        self.assertGreaterEqual(retirement_index, 0)
        editor.setCurrentIndex(retirement_index)
        editor.activated.emit(retirement_index)
        QApplication.processEvents()

        self.assertEqual(self.window.scenario_table.item(row, end_column).text(), self.window.RETIREMENT_MONTH_LABEL)
        self.assertNotEqual(self.window.scenario_table.state(), QAbstractItemView.State.EditingState)

        category_item = self.window.scenario_table.item(row, category_column)
        self.window.scenario_table.setCurrentCell(row, category_column)
        self.window.scenario_table.editItem(category_item)
        QApplication.processEvents()

        category_editor = self._visible_line_editor_for_item(category_item)
        self.assertIsInstance(category_editor, QLineEdit)
        QTest.keyClick(category_editor, Qt.Key.Key_Escape)
        QApplication.processEvents()

    def test_zero_balance_warning_includes_age(self) -> None:
        self.window.birthday_edit.setText("1986-01-01")
        self.window._update_zero_balance_warning(date(2050, 7, 1))

        self.assertEqual(
            self.window.zero_balance_warning_label.text(),
            "Warning: total value reaches zero on 2050-07-01 at age 64.5.",
        )

    def test_build_plan_and_ui_payload_include_market_shocks(self) -> None:
        self.window.add_market_shock()
        editor = self.window._shock_editors[0]
        editor.label_edit.setText("Crash 2028")
        editor.start_edit.setText("start")
        editor.drawdown_spin.setValue(35.0)
        editor.drawdown_months_spin.setValue(9)
        editor.recovery_months_spin.setValue(24)

        plan = self.window._build_plan()
        payload = self.window._save_payload(plan)

        self.assertEqual(len(plan.market_shocks), 1)
        self.assertEqual(plan.market_shocks[0].label, "Crash 2028")
        self.assertEqual(plan.market_shocks[0].starts_on.isoformat(), self.window.start_month_edit.text())
        self.assertAlmostEqual(plan.market_shocks[0].drawdown_pct, 0.35)
        self.assertEqual(payload["_ui"]["shock_rows"][0]["start"], "start")

    def test_capital_gains_tax_round_trips_through_plan_save_load(self) -> None:
        self.window.capital_gains_tax_spin.setValue(26.38)

        plan = self.window._build_plan()
        payload = self.window._save_payload(plan)
        path = Path(self.temp_dir.name) / "plan.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

        other_window = PlannerWindow(SettingsStore(Path(self.temp_dir.name) / "other-settings.json"))
        other_window.autosave_timer.stop()
        try:
            self.assertTrue(other_window.load_plan_from_path(path))
            loaded_plan = other_window._build_plan()
            self.assertIsInstance(loaded_plan, Plan)
            self.assertAlmostEqual(plan.capital_gains_tax_rate, 0.2638)
            self.assertAlmostEqual(loaded_plan.capital_gains_tax_rate, 0.2638)
            self.assertAlmostEqual(other_window.capital_gains_tax_spin.value(), 26.38)
        finally:
            other_window.close()

    def test_balance_chart_series_includes_starting_point_before_month_one_shock(self) -> None:
        self.window.add_market_shock()
        editor = self.window._shock_editors[0]
        editor.start_edit.setText("start")
        editor.drawdown_spin.setValue(50.0)
        editor.drawdown_months_spin.setValue(1)
        editor.recovery_months_spin.setValue(18)

        plan = self.window._build_plan()
        result = SimulationEngine().run(plan)
        plan_end = plan.start_month.replace(year=plan.start_month.year + 1)
        _, balance_series = self.window._chart_series(plan, result, plan_end)

        portfolio_series = next(series for series in balance_series if series.name == "Portfolio")
        self.assertEqual(portfolio_series.points[0].value, plan.portfolio.starting_balance)
        self.assertLess(portfolio_series.points[1].value, portfolio_series.points[0].value * 0.6)


if __name__ == "__main__":
    unittest.main()
