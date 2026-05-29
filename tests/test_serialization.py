from __future__ import annotations

import unittest
from datetime import date

from afterwork.domain import FlowTarget, Person, Plan
from afterwork.serialization import SCHEMA_VERSION, plan_from_dict, plan_to_dict


class SerializationTests(unittest.TestCase):
    def test_plan_to_dict_writes_current_schema_version(self) -> None:
        payload = plan_to_dict(plan_from_dict(
            {
                "person": {"birth_date": "1980-01-01", "target_age_years": 47},
                "start_month": "2026-01-01",
            }
        ))

        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)

    def test_legacy_recurring_portfolio_target_loads_as_invest(self) -> None:
        plan = plan_from_dict(
            {
                "person": {"birth_date": "1980-01-01", "target_age_years": 47},
                "start_month": "2026-01-01",
                "recurring_flows": [
                    {
                        "amount": 400.0,
                        "frequency": "monthly",
                        "starts_on": "2026-01-01",
                        "target": "portfolio",
                    }
                ],
                "one_off_events": [
                    {
                        "amount": 400.0,
                        "occurs_on": "2026-01-01",
                        "target": "portfolio",
                    }
                ],
            }
        )

        self.assertEqual(plan.recurring_flows[0].target, FlowTarget.INVEST)
        self.assertEqual(plan.one_off_events[0].target, FlowTarget.PORTFOLIO)

    def test_cash_minimum_balance_round_trips(self) -> None:
        payload = plan_to_dict(
            Plan(
                person=Person(birth_date=date(1980, 1, 1), target_age_years=47),
                start_month=date(2026, 1, 1),
                cash_minimum_balance=1_500.0,
            )
        )

        self.assertEqual(payload["cash_minimum_balance"], 1_500.0)
        self.assertEqual(plan_from_dict(payload).cash_minimum_balance, 1_500.0)


if __name__ == "__main__":
    unittest.main()
