# Afterwork Architecture

## Purpose

Afterwork is a desktop retirement-planning application built around a small, UI-independent simulation core.

At a high level, the system does three things:

1. Capture a financial scenario as structured inputs.
2. Simulate balances month by month until a target age.
3. Present the result in tables, charts, and warnings.

The design is intentionally split into a pure domain/simulation layer and a Qt desktop shell.


## High-Level Architecture

The codebase is organized into five main building blocks:

- `src/afterwork/domain.py`
  - Core data model and time utilities.
- `src/afterwork/engine.py`
  - Simulation algorithm.
- `src/afterwork/serialization.py`
  - JSON import/export for plans.
- `src/afterwork/ui_qt.py`
  - PySide6 desktop UI, editing, visualization, and orchestration.
- `src/afterwork/app_settings.py`
  - Local app settings and autosave location management.

Supporting pieces:

- `src/afterwork/__init__.py`
  - Public package exports.
- `run_ui.py`
  - Convenience launcher for local execution.
- `tests/test_engine.py`
  - Engine behavior tests.
- `tests/test_ui_qt.py`
  - UI behavior tests for scenario editing and chart-related logic.


## Layered View

### 1. Domain Layer

The domain layer defines the business vocabulary and keeps the core model independent from the UI.

Key concepts:

- `Person`
  - Birth date and target age.
  - Computes current age and simulation horizon in months.
- `Portfolio`
  - Starting balance and annual growth rate.
  - Exposes monthly growth rate derived from annual growth.
- `RecurringFlow`
  - Repeating income or expense.
  - Supports monthly or yearly frequency.
  - Can target either cash or portfolio.
  - Can be nominal or real, with annual adjustment.
- `OneOffEvent`
  - Single event affecting cash or portfolio in one month.
- `MarketShock`
  - Piecewise portfolio stress event with drawdown and recovery phases.
- `Plan`
  - Aggregates all user inputs into one simulation-ready object.
- `MonthlyRecord`
  - One simulated month of outputs.
- `SimulationResult`
  - Collection of monthly records and final balance helpers.

Supporting utilities:

- `month_index(start_month, current_month)`
  - Converts two dates into a month offset.
- `add_months(current, months)`
  - Advances a date by whole months.


### 2. Simulation Layer

`SimulationEngine` is the computational core. It takes a `Plan` and returns a `SimulationResult`.

Important properties of this layer:

- Deterministic
- Stateless between runs
- Independent of Qt and UI widgets
- Built around a monthly discrete-time simulation


### 3. Persistence Layer

`serialization.py` translates between in-memory domain objects and JSON.

Responsibilities:

- Convert `Plan` to a plain dictionary
- Reconstruct `Plan` from a dictionary
- Save and load JSON files
- Encode enums and dates into serializable forms

This layer exists to keep JSON concerns out of the engine and UI logic.


### 4. UI Layer

`ui_qt.py` is the application shell.

Responsibilities:

- Build and style the main window
- Let the user edit scenario rows and market shocks
- Convert UI state into a `Plan`
- Run the simulation
- Render result tables, timeline views, and balance charts
- Show warnings such as the first month where total balance reaches zero
- Save, load, and autosave scenarios

The UI is large because it contains both presentation code and application orchestration, but the core financial behavior still lives in `domain.py` and `engine.py`.


### 5. Local Settings Layer

`SettingsStore` manages lightweight user-local settings:

- Last opened scenario path
- Autosave path under the user's home directory

This is separate from scenario persistence. Scenario data lives in plan JSON files; app preferences live in settings JSON.


## Data Flow

The main execution path is:

1. The user edits a scenario in the Qt UI.
2. The UI builds a `Plan`.
3. `SimulationEngine.run(plan)` simulates the scenario month by month.
4. The UI consumes `SimulationResult`.
5. The UI derives table rows, chart series, and timeline items from the result.
6. The scenario can be written to JSON through the serialization layer.

Conceptually:

`UI state -> Plan -> SimulationEngine -> SimulationResult -> tables/charts/warnings`


## Core Building Blocks

### Plan

`Plan` is the aggregate root of the simulation. It contains:

- person
- start month
- starting cash balance
- portfolio settings
- recurring flows
- one-off events
- market shocks

Everything the engine needs is passed in through this one object.


### Cash and Portfolio as Separate Buckets

The model explicitly separates:

- `cash_balance`
- `portfolio_balance`

This is the most important conceptual modeling choice in the app.

It allows flows and events to target either bucket, makes liquidity visible, and supports policies such as:

- transfer money explicitly between cash and portfolio

Without this separation, the planner would lose the distinction between solvency and liquidity.


### Scenario Inputs

The scenario is composed from three input types:

- `RecurringFlow`
- `OneOffEvent`
- `MarketShock`

These map cleanly to the user-facing planning concepts:

- salary, rent, living costs, pension, subscriptions
- inheritance, insurance payout, sale proceeds
- market crash and recovery scenarios


## Conceptual Description of the Algorithms

### 1. Time Horizon Algorithm

The simulation horizon is derived from the person's birth date and target age.

Process:

1. Compute age at the plan start month.
2. Compute the difference between current age and target age.
3. Convert that difference into months.

This makes the simulation length user-centric rather than event-centric.


### 2. Monthly Simulation Algorithm

The engine uses a monthly loop.

For each simulated month:

1. Determine which recurring flows occur in the month.
2. Determine which one-off events occur in the month.
3. Apply flow amounts to cash and/or portfolio contributions.
4. Discount flows into present value for reporting.
5. Update cash balance.
6. Update portfolio with contributions.
7. Apply any explicit cash-portfolio transfer rows, including taxed portfolio withdrawals.
8. Apply normal portfolio growth.
9. Apply market shock multiplier for the month.
10. Record the resulting balances and metadata.

This is effectively a discrete-event financial simulation with fixed monthly time steps.


### 3. Recurring Flow Scheduling

Each recurring flow has:

- start month
- optional end month
- frequency
- enabled flag

Scheduling rules:

- If the current month is before `starts_on`, the flow is inactive.
- If the current month is on or after `ends_on`, the flow is inactive.
- Monthly flows occur every month while active.
- Yearly flows occur when the calendar month matches the start month.

This makes yearly payments behave like annual anniversaries.


### 4. Flow Replacement Algorithm

Recurring flows are grouped by a replacement key:

- `(class name, category)`

Within a group, flows are ordered by `starts_on`.
If a later flow starts, it replaces the earlier one from that month onward.

Conceptually, this is used for transitions such as:

- pre-retirement salary -> post-retirement pension
- one cost regime -> another cost regime

This avoids double-counting overlapping versions of what is logically the same stream.


### 5. Nominal vs Real Amount Adjustment

Recurring flows support two adjustment bases:

- `Nominal`
- `Real`

The adjustment rate is applied monthly using the annual adjustment rate converted into a monthly rate.

The difference is the anchor point:

- `Nominal`
  - Growth starts from the flow's own start date.
- `Real`
  - Growth is anchored to the overall plan start date.

Conceptually:

- nominal amounts preserve the amount defined at the flow's start
- real amounts preserve purchasing-power intent relative to the whole plan start

This is an important modeling choice because it allows future-starting flows to be expressed either in today's terms or in their own start-period terms.


### 6. Present Value Calculation

For reporting, the engine also computes `flow_present_value`.

Approach:

- Each flow or event amount in a given month is discounted back to the plan start.
- The portfolio monthly growth rate is reused as the discount rate.

This lets the app track a present-value view of future inflows and outflows alongside nominal balances.


### 7. Market Shock Algorithm

`MarketShock` defines a time-varying factor applied to the portfolio path.

It has:

- start month
- drawdown percentage
- drawdown duration in months
- recovery duration in months

The factor is piecewise:

1. Before the shock starts: factor is `1.0`
2. During drawdown: factor declines linearly toward the trough
3. During recovery: factor rises linearly back toward `1.0`
4. After recovery: factor remains `1.0`

The engine does not apply the absolute factor directly each month.
Instead, it computes a monthly shock multiplier as:

`current_factor / previous_factor`

That means the shock changes the portfolio path incrementally month by month rather than repeatedly reapplying the full drawdown.

Multiple shocks are combined multiplicatively.


### 8. Explicit Portfolio Transfer Algorithm

Transfers between cash and portfolio are modeled as explicit scenario rows targeting `invest`.

Rules:

- Positive amounts move cash into the portfolio.
- Negative amounts move money from portfolio to cash.
- Negative transfer amounts are treated as net cash received; the engine grosses up the portfolio sale for capital-gains tax.

If portfolio goes negative, the month is marked with `portfolio_underflow`.


### 9. Result Recording Algorithm

Each month produces a `MonthlyRecord` that contains:

- month
- age
- nominal cash flow
- nominal portfolio contribution
- nominal portfolio growth
- nominal portfolio transfer
- annualized net portfolio withdrawal rate, when applicable
- flow present value
- cash balance
- portfolio balance
- total balance
- portfolio underflow flag
- names of applied flows and shocks

This keeps the simulation output explicit and traceable for both debugging and UI rendering.


## UI-Specific Derived Algorithms

The UI adds a few secondary algorithms on top of the engine.

### Effective Recurring Flow Range

For timeline rendering, the UI computes an effective end date for each recurring flow by combining:

- the flow's own end date
- any successor flow that replaces it
- the overall plan end

This produces cleaner timelines than simply drawing every configured flow at face value.


### Semiannual Chart Sampling

The scenario timeline uses semiannual points plus the final plan month.

This reduces visual density while still showing the overall path of recurring amounts.


### Zero-Balance Warning

The UI scans the simulation result for the first month where total balance is less than or equal to zero and displays that date, optionally with age.

This is a user-facing diagnostic derived from the simulation output.


## Key Design Decisions

### Pure Core, Stateful Shell

The simulation core is mostly pure and isolated; the UI is stateful and event-driven.

This is a good split because:

- financial rules stay testable
- UI changes do not require rewriting core logic
- JSON import/export can reuse the same plan model


### Immutable Domain Objects

Most domain objects are frozen dataclasses.

Benefits:

- fewer accidental mutations
- easier reasoning during simulation
- safer serialization boundaries


### Monthly Granularity

The planner simulates monthly rather than daily.

This is a deliberate simplification:

- precise enough for retirement planning
- simpler than day-level event handling
- cheaper to compute and easier to explain


## Testing Strategy

Current tests focus on high-value behavior:

- one-off events targeting cash vs portfolio
- present value discounting
- market shock drawdown and recovery path
- UI sorting
- UI-triggered recalculation
- warning text generation
- market shock payload round-trip behavior
- chart behavior around starting points

The tests reflect the architecture split: engine behavior is validated separately from UI-specific behavior.


## Limitations and Observations

- `ui_qt.py` is large and mixes several responsibilities:
  - widget construction
  - styling
  - scenario parsing
  - save/load orchestration
  - chart derivation
- Present value discounting currently reuses portfolio growth as the discount rate, which is a practical simplification rather than a separate financial model.
- Replacement logic is category-based, so category naming effectively becomes part of the simulation semantics.

These are not necessarily defects, but they are the main architectural pressure points.


## Summary

Afterwork is a layered desktop planner with:

- an immutable domain model,
- a deterministic monthly simulation engine,
- JSON-based persistence,
- and a Qt UI that edits scenarios and visualizes outcomes.

The central algorithm is a month-by-month projection of cash and portfolio balances under recurring flows, one-off events, portfolio growth, market shocks, and liquidity-withdrawal rules.
