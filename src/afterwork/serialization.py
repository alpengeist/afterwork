from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from afterwork.domain import FlowTarget, Frequency, OneOffEvent, Person, Plan, Portfolio, RecurringFlow


def _date_to_str(value: date) -> str:
    return value.isoformat()


def _date_from_str(value: str) -> date:
    return date.fromisoformat(value)


def plan_to_dict(plan: Plan) -> dict[str, Any]:
    return {
        "person": {
            "current_age_years": plan.person.current_age_years,
            "target_age_years": plan.person.target_age_years,
        },
        "start_month": _date_to_str(plan.start_month),
        "starting_cash_balance": plan.starting_cash_balance,
        "portfolio": {
            "starting_balance": plan.portfolio.starting_balance,
            "annual_growth_rate": plan.portfolio.annual_growth_rate,
        },
        "recurring_flows": [
            {
                "name": flow.name,
                "amount": flow.amount,
                "frequency": flow.frequency.value,
                "starts_on": _date_to_str(flow.starts_on),
                "ends_on": _date_to_str(flow.ends_on) if flow.ends_on else None,
                "category": flow.category,
                "target": flow.target.value,
                "annual_adjustment_rate": flow.annual_adjustment_rate,
                "enabled": flow.enabled,
            }
            for flow in plan.recurring_flows
        ],
        "one_off_events": [
            {
                "name": event.name,
                "amount": event.amount,
                "occurs_on": _date_to_str(event.occurs_on),
                "category": event.category,
                "target": event.target.value,
                "enabled": event.enabled,
            }
            for event in plan.one_off_events
        ],
    }


def plan_from_dict(data: dict[str, Any]) -> Plan:
    recurring_flows = [
        RecurringFlow(
            name=item["name"],
            amount=float(item["amount"]),
            frequency=Frequency(item["frequency"]),
            starts_on=_date_from_str(item["starts_on"]),
            ends_on=_date_from_str(item["ends_on"]) if item.get("ends_on") else None,
            category=item.get("category", "general"),
            target=FlowTarget(item.get("target", FlowTarget.CASH.value)),
            annual_adjustment_rate=float(item.get("annual_adjustment_rate", 0.0)),
            enabled=bool(item.get("enabled", True)),
        )
        for item in data.get("recurring_flows", [])
    ]
    one_off_events = [
        OneOffEvent(
            name=item["name"],
            amount=float(item["amount"]),
            occurs_on=_date_from_str(item["occurs_on"]),
            category=item.get("category", "general"),
            target=FlowTarget(item.get("target", FlowTarget.CASH.value)),
            enabled=bool(item.get("enabled", True)),
        )
        for item in data.get("one_off_events", [])
    ]
    person_data = data["person"]
    portfolio_data = data.get("portfolio", {})
    return Plan(
        person=Person(
            current_age_years=int(person_data["current_age_years"]),
            target_age_years=int(person_data["target_age_years"]),
        ),
        start_month=_date_from_str(data["start_month"]),
        starting_cash_balance=float(data.get("starting_cash_balance", 0.0)),
        portfolio=Portfolio(
            starting_balance=float(portfolio_data.get("starting_balance", 0.0)),
            annual_growth_rate=float(portfolio_data.get("annual_growth_rate", 0.0)),
        ),
        recurring_flows=recurring_flows,
        one_off_events=one_off_events,
    )


def plan_to_json(plan: Plan, path: str | Path) -> None:
    Path(path).write_text(json.dumps(plan_to_dict(plan), indent=2), encoding="utf-8")


def plan_from_json(path: str | Path) -> Plan:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return plan_from_dict(data)
