from __future__ import annotations

from datetime import date

from afterwork.domain import (
    FlowTarget,
    MonthlyRecord,
    Plan,
    RecurringFlow,
    SimulationResult,
    add_months,
    month_index,
)


class SimulationEngine:
    def run(self, plan: Plan) -> SimulationResult:
        records: list[MonthlyRecord] = []
        cash_balance = plan.starting_cash_balance
        portfolio_balance = plan.portfolio.starting_balance
        active_recurring_flows = [flow for flow in plan.recurring_flows if flow.enabled]
        active_one_off_events = [event for event in plan.one_off_events if event.enabled]
        replacement_starts = self._replacement_starts(active_recurring_flows)

        for offset in range(plan.simulation_months()):
            current_month = add_months(plan.start_month, offset)
            period_index = month_index(plan.start_month, current_month)

            applied_names: list[str] = []
            cash_flow_nominal = 0.0
            portfolio_contribution_nominal = 0.0
            flow_present_value = 0.0

            for flow in active_recurring_flows:
                if not flow.occurs_in_month(current_month):
                    continue
                successor_start = replacement_starts.get(id(flow))
                if successor_start is not None and current_month >= successor_start:
                    continue
                adjusted_amount = flow.nominal_amount_for_period(period_index)

                if flow.target == FlowTarget.CASH:
                    cash_flow_nominal += adjusted_amount
                else:
                    cash_flow_nominal -= adjusted_amount
                    portfolio_contribution_nominal += adjusted_amount

                flow_present_value += flow.present_value(adjusted_amount, period_index)
                applied_names.append(flow.display_label)

            for event in active_one_off_events:
                if not event.occurs_in_month(current_month):
                    continue

                if event.target == FlowTarget.CASH:
                    cash_flow_nominal += event.amount
                else:
                    cash_flow_nominal -= event.amount
                    portfolio_contribution_nominal += event.amount

                flow_present_value += event.amount
                applied_names.append(event.display_label)

            cash_balance += cash_flow_nominal
            portfolio_balance += portfolio_contribution_nominal
            portfolio_growth_nominal = portfolio_balance * plan.portfolio.monthly_growth_rate
            portfolio_balance += portfolio_growth_nominal
            portfolio_transfer_nominal = 0.0

            if cash_balance <= 0:
                portfolio_transfer_nominal = -cash_balance
                cash_balance += portfolio_transfer_nominal
                portfolio_balance -= portfolio_transfer_nominal

            portfolio_underflow = portfolio_balance < 0
            total_balance = cash_balance + portfolio_balance
            age_years = plan.person.age_years_at(current_month)

            records.append(
                MonthlyRecord(
                    month=current_month,
                    age_years=age_years,
                    cash_flow_nominal=cash_flow_nominal,
                    portfolio_contribution_nominal=portfolio_contribution_nominal,
                    portfolio_growth_nominal=portfolio_growth_nominal,
                    portfolio_transfer_nominal=portfolio_transfer_nominal,
                    flow_present_value=flow_present_value,
                    cash_balance=cash_balance,
                    portfolio_balance=portfolio_balance,
                    total_balance=total_balance,
                    portfolio_underflow=portfolio_underflow,
                    applied_flow_names=tuple(applied_names),
                )
            )

        return SimulationResult(records=records)

    def _replacement_starts(self, flows: list[RecurringFlow]) -> dict[int, date]:
        grouped: dict[tuple[str, str], list[RecurringFlow]] = {}
        for flow in flows:
            grouped.setdefault(flow.replacement_key, []).append(flow)

        result: dict[int, object] = {}
        for group in grouped.values():
            ordered = sorted(group, key=lambda item: item.starts_on)
            for index, flow in enumerate(ordered[:-1]):
                result[id(flow)] = ordered[index + 1].starts_on
        return result
