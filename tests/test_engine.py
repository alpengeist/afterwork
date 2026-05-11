from __future__ import annotations

from dataclasses import replace
import unittest
from datetime import date

from afterwork.domain import FlowTarget, Frequency, MarketShock, OneOffEvent, Person, Plan, Portfolio, RecurringFlow
from afterwork.engine import SimulationEngine


class SimulationEngineTests(unittest.TestCase):
    def test_positive_portfolio_target_recurring_flow_moves_cash_into_portfolio(self) -> None:
        plan_base = Plan(
            person=Person(birth_date=date(1980, 1, 1), target_age_years=47),
            start_month=date(2026, 1, 1),
            starting_cash_balance=1_000.0,
            portfolio=Portfolio(starting_balance=5_000.0, annual_growth_rate=0.0),
        )

        cash_result = SimulationEngine().run(
            replace(
                plan_base,
                recurring_flows=[
                    RecurringFlow(
                        amount=400.0,
                        frequency=Frequency.MONTHLY,
                        starts_on=date(2026, 1, 1),
                        target=FlowTarget.CASH,
                    )
                ],
            )
        )
        portfolio_result = SimulationEngine().run(
            replace(
                plan_base,
                recurring_flows=[
                    RecurringFlow(
                        amount=400.0,
                        frequency=Frequency.MONTHLY,
                        starts_on=date(2026, 1, 1),
                        target=FlowTarget.PORTFOLIO,
                    )
                ],
            )
        )

        cash_record = cash_result.records[0]
        portfolio_record = portfolio_result.records[0]

        self.assertEqual(cash_record.cash_balance, 1_400.0)
        self.assertEqual(portfolio_record.cash_balance, 600.0)
        self.assertEqual(cash_record.portfolio_balance, 5_000.0)
        self.assertEqual(portfolio_record.portfolio_balance, 5_400.0)
        self.assertEqual(cash_record.total_balance, 6_400.0)
        self.assertEqual(portfolio_record.total_balance, 6_000.0)

    def test_positive_portfolio_target_recurring_flow_can_undercut_minimum_cash(self) -> None:
        plan = Plan(
            person=Person(birth_date=date(1980, 1, 1), target_age_years=47),
            start_month=date(2026, 1, 1),
            starting_cash_balance=1_000.0,
            minimal_cash_level=1_000.0,
            portfolio_withdrawal=300.0,
            portfolio=Portfolio(starting_balance=5_000.0, annual_growth_rate=0.0),
            recurring_flows=[
                RecurringFlow(
                    amount=400.0,
                    frequency=Frequency.MONTHLY,
                    starts_on=date(2026, 1, 1),
                    target=FlowTarget.PORTFOLIO,
                )
            ],
        )

        record = SimulationEngine().run(plan).records[0]

        self.assertEqual(record.cash_balance, 600.0)
        self.assertEqual(record.portfolio_balance, 5_400.0)
        self.assertEqual(record.portfolio_transfer_nominal, 0.0)

    def test_negative_portfolio_target_recurring_flow_reduces_portfolio_without_changing_cash(self) -> None:
        plan = Plan(
            person=Person(birth_date=date(1980, 1, 1), target_age_years=47),
            start_month=date(2026, 1, 1),
            starting_cash_balance=1_000.0,
            portfolio=Portfolio(starting_balance=5_000.0, annual_growth_rate=0.0),
            recurring_flows=[
                RecurringFlow(
                    amount=-400.0,
                    frequency=Frequency.MONTHLY,
                    starts_on=date(2026, 1, 1),
                    target=FlowTarget.PORTFOLIO,
                )
            ],
        )

        record = SimulationEngine().run(plan).records[0]

        self.assertEqual(record.cash_balance, 1_000.0)
        self.assertEqual(record.portfolio_balance, 4_600.0)

    def test_portfolio_target_one_off_event_changes_total_like_cash_target(self) -> None:
        plan_base = Plan(
            person=Person(birth_date=date(1980, 1, 1), target_age_years=47),
            start_month=date(2026, 1, 1),
            starting_cash_balance=1_000.0,
            portfolio=Portfolio(starting_balance=5_000.0, annual_growth_rate=0.0),
        )

        cash_result = SimulationEngine().run(
            replace(
                plan_base,
                one_off_events=[
                    OneOffEvent(
                        amount=400.0,
                        occurs_on=date(2026, 1, 1),
                        target=FlowTarget.CASH,
                    )
                ],
            )
        )
        portfolio_result = SimulationEngine().run(
            replace(
                plan_base,
                one_off_events=[
                    OneOffEvent(
                        amount=400.0,
                        occurs_on=date(2026, 1, 1),
                        target=FlowTarget.PORTFOLIO,
                    )
                ],
            )
        )

        cash_record = cash_result.records[0]
        portfolio_record = portfolio_result.records[0]

        self.assertEqual(cash_record.total_balance, portfolio_record.total_balance)
        self.assertEqual(cash_record.cash_balance, 1_400.0)
        self.assertEqual(portfolio_record.cash_balance, 1_000.0)
        self.assertEqual(cash_record.portfolio_balance, 5_000.0)
        self.assertEqual(portfolio_record.portfolio_balance, 5_400.0)

    def test_one_off_event_flow_present_value_is_discounted_for_future_months(self) -> None:
        plan = Plan(
            person=Person(birth_date=date(1980, 1, 1), target_age_years=48),
            start_month=date(2026, 1, 1),
            portfolio=Portfolio(starting_balance=0.0, annual_growth_rate=0.12),
            one_off_events=[
                OneOffEvent(
                    amount=1_200.0,
                    occurs_on=date(2027, 1, 1),
                    target=FlowTarget.CASH,
                )
            ],
        )

        result = SimulationEngine().run(plan)
        event_record = next(record for record in result.records if record.month == date(2027, 1, 1))

        self.assertAlmostEqual(event_record.flow_present_value, 1_200.0 / 1.12, places=6)

    def test_market_shock_drawdown_and_recovery_adjust_portfolio_path(self) -> None:
        plan = Plan(
            person=Person(birth_date=date(1980, 1, 1), target_age_years=50),
            start_month=date(2026, 1, 1),
            portfolio=Portfolio(starting_balance=1_000.0, annual_growth_rate=0.0),
            market_shocks=[
                MarketShock(
                    starts_on=date(2026, 1, 1),
                    drawdown_pct=0.2,
                    drawdown_months=2,
                    recovery_months=2,
                    label="Crash",
                )
            ],
        )

        result = SimulationEngine().run(plan)

        self.assertEqual([record.portfolio_balance for record in result.records[:4]], [900.0, 800.0, 900.0, 1000.0])
        self.assertEqual(result.records[0].applied_flow_names, ("Crash",))
        self.assertEqual(result.records[1].applied_flow_names, ("Crash",))
        self.assertEqual(result.records[2].applied_flow_names, ("Crash",))
        self.assertEqual(result.records[3].applied_flow_names, ("Crash",))


if __name__ == "__main__":
    unittest.main()
