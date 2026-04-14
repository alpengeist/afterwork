from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from afterwork.app_settings import SettingsStore
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

    def test_amount_header_sorts_rows_numerically(self) -> None:
        for amount in ("100", "20", "-5.5"):
            self.window.add_one_off_event()
            row = self.window.scenario_table.rowCount() - 1
            self.window.scenario_table.item(row, self.window.SCENARIO_AMOUNT_COLUMN).setText(amount)

        self.window._on_scenario_header_clicked(self.window.SCENARIO_AMOUNT_COLUMN)
        ascending = [
            self.window._scenario_value(row, self.window.SCENARIO_AMOUNT_COLUMN)
            for row in range(self.window.scenario_table.rowCount())
        ]
        self.assertEqual(ascending, ["-5.5", "20", "100"])

        self.window._on_scenario_header_clicked(self.window.SCENARIO_AMOUNT_COLUMN)
        descending = [
            self.window._scenario_value(row, self.window.SCENARIO_AMOUNT_COLUMN)
            for row in range(self.window.scenario_table.rowCount())
        ]
        self.assertEqual(descending, ["100", "20", "-5.5"])

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
