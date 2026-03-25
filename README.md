# Afterwork

`afterwork` is a Python library for retirement planning simulations. The calculation core is UI-independent and models cash, portfolio, and scenario events month by month until a configurable target age.

## Design goals

- Keep the simulation engine pure Python and free of UI concerns.
- Represent regular and one-off cash flows explicitly.
- Store recurring flows in today's value and compound them forward with a per-flow yearly adjustment rate.
- Run deterministic month-based projections that are easy to test.
- Leave room for later extensions such as taxes, investment returns, and scenario comparison.
- Persist scenarios as JSON so a separate UI can save and reload them.

## Suggested architecture

Keep the project split into layers:

- `afterwork.domain`: value objects and dataclasses for people, plans, recurring flows, one-off events, and projection outputs.
- `afterwork.engine`: the monthly simulation logic.
- `afterwork.serialization`: JSON import/export for scenarios.
- `afterwork.services`: optional higher-level APIs for loading/saving plans, comparing scenarios, or generating reports.
- `ui_*` or `afterwork.ui_qt`: one or more separate desktop apps that call the core library.

The UI should only:

- collect user input,
- map it to domain models,
- call the engine,
- render `SimulationResult`.

It should not contain business logic about yearly adjustments, recurrence rules, or monthly balances.

## Core concepts

- `RecurringFlow`: a monthly or yearly pattern such as rent, salary, insurance, or savings, with its own target and yearly adjustment rate.
- `OneOffEvent`: a single cash event such as inheritance, a car purchase, or a house repair.
- `Portfolio`: a savings portfolio with a starting value and growth rate.
- `Plan`: all inputs required to simulate from the current age to the target age.
- `SimulationEngine`: iterates one month at a time and produces monthly snapshots.

Recurring flows may define an explicit end date. If a later recurring row has the same type and category, it still automatically replaces the earlier row from its start month onward, even if the earlier row's end date is later.

## Example

```python
from datetime import date

from afterwork import (
    FlowTarget,
    Frequency,
    OneOffEvent,
    Person,
    Plan,
    Portfolio,
    RecurringFlow,
    SimulationEngine,
)

plan = Plan(
    person=Person(current_age_years=40, target_age_years=95),
    start_month=date(2026, 1, 1),
    starting_cash_balance=25_000,
    portfolio=Portfolio(starting_balance=50_000, annual_growth_rate=0.05),
    recurring_flows=[
        RecurringFlow(
            name="Salary",
            amount=4_500,
            target=FlowTarget.CASH,
            frequency=Frequency.MONTHLY,
            starts_on=date(2026, 1, 1),
            category="income",
            annual_adjustment_rate=0.02,
        ),
        RecurringFlow(
            name="Rent",
            amount=-1_500,
            target=FlowTarget.CASH,
            frequency=Frequency.MONTHLY,
            starts_on=date(2026, 1, 1),
            category="housing",
            annual_adjustment_rate=0.02,
        ),
        RecurringFlow(
            name="ETF Savings",
            amount=900,
            target=FlowTarget.PORTFOLIO,
            frequency=Frequency.MONTHLY,
            starts_on=date(2026, 1, 1),
            category="savings",
            annual_adjustment_rate=0.02,
        ),
    ],
    one_off_events=[
        OneOffEvent(
            name="Inheritance",
            amount=75_000,
            occurs_on=date(2035, 6, 1),
            category="windfall",
            target=FlowTarget.CASH,
        )
    ],
)

result = SimulationEngine().run(plan)
print(result.final_total_balance)
```

## Desktop UI

A Qt desktop UI is included in [src/afterwork/ui_qt.py](C:/proj/afterwork/src/afterwork/ui_qt.py). It uses `PySide6`, while the simulation core remains UI-independent.

The layout matches your proposal:

- top pane: scenario editor,
- bottom pane: simulation output,
- rows in the scenario editor represent one recurring flow or one-off event,
- time flows downward in the scenario table.

The editor supports:

- adding recurring flows and one-off events,
- enabling and disabling rows to compare alternatives without deleting them,
- running the simulation,
- saving scenarios as JSON,
- loading scenarios from JSON.

Run it with:

```bash
python run_ui.py
```

Or during development:

```bash
afterwork-ui
```

## JSON schema

Scenarios are stored as a serialized `Plan`. The file contains:

- top-level plan settings such as `start_month`, `starting_cash_balance`, and `portfolio`,
- `person` with current and target age,
- `recurring_flows` for regular nominal cash flows and portfolio contributions,
- `one_off_events` for dated one-time cash or portfolio events.

This keeps the UI stateless with respect to persistence: it reads a plan, edits a plan, and writes a plan.

## Extension ideas

- Add account buckets such as cash, pension, brokerage, and real estate.
- Add return curves separate from yearly adjustment curves.
- Support step changes in recurring flows, for example rent ending at retirement.
- Add tax and social-security style modules as optional strategies.
- Add Monte Carlo simulation later without changing the core plan schema.
