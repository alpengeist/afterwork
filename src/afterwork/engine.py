from __future__ import annotations

from datetime import date

from afterwork.domain import (
    FlowTarget,
    MarketShock,
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
        monthly_discount_rate = plan.portfolio.monthly_growth_rate
        base_growth_multiplier = 1 + plan.portfolio.monthly_growth_rate
        active_recurring_flows = [flow for flow in plan.recurring_flows if flow.enabled]
        active_one_off_events = [event for event in plan.one_off_events if event.enabled]
        active_market_shocks = [shock for shock in plan.market_shocks if shock.enabled]
        replacement_starts = self._replacement_starts(active_recurring_flows)

        for offset in range(plan.simulation_months()):
            current_month = add_months(plan.start_month, offset)
            period_index = month_index(plan.start_month, current_month)

            applied_names: list[str] = []
            cash_flow_nominal = 0.0
            portfolio_contribution_nominal = 0.0
            cash_to_portfolio_nominal = 0.0
            flow_present_value = 0.0

            for flow in active_recurring_flows:
                if not flow.occurs_in_month(current_month):
                    continue
                successor_start = replacement_starts.get(id(flow))
                if successor_start is not None and current_month >= successor_start:
                    continue
                adjusted_amount = flow.nominal_amount_for_month(plan.start_month, current_month)

                if flow.target == FlowTarget.CASH:
                    cash_flow_nominal += adjusted_amount
                else:
                    portfolio_contribution_nominal += adjusted_amount
                    if adjusted_amount > 0:
                        cash_flow_nominal -= adjusted_amount
                        cash_to_portfolio_nominal += adjusted_amount

                flow_present_value += flow.present_value(adjusted_amount, period_index)
                applied_names.append(flow.display_label)

            for event in active_one_off_events:
                if not event.occurs_in_month(current_month):
                    continue

                if event.target == FlowTarget.CASH:
                    cash_flow_nominal += event.amount
                else:
                    portfolio_contribution_nominal += event.amount

                flow_present_value += event.amount / ((1 + monthly_discount_rate) ** period_index)
                applied_names.append(event.display_label)

            cash_balance += cash_flow_nominal
            portfolio_balance += portfolio_contribution_nominal
            shock_multiplier = self._shock_multiplier(
                active_market_shocks,
                current_month=current_month,
                previous_month=add_months(current_month, -1),
            )
            portfolio_growth_nominal = portfolio_balance * (base_growth_multiplier * shock_multiplier - 1.0)
            portfolio_balance += portfolio_growth_nominal
            portfolio_transfer_nominal = 0.0
            applied_names.extend(
                shock.display_label
                for shock in active_market_shocks
                if self._shock_applies_in_month(shock, current_month)
            )

            effective_cash_balance = cash_balance + cash_to_portfolio_nominal

            if effective_cash_balance < plan.minimal_cash_level and plan.portfolio_withdrawal > 0:
                while effective_cash_balance < plan.minimal_cash_level:
                    portfolio_transfer_nominal += plan.portfolio_withdrawal
                    cash_balance += plan.portfolio_withdrawal
                    portfolio_balance -= plan.portfolio_withdrawal
                    effective_cash_balance += plan.portfolio_withdrawal
            elif effective_cash_balance <= 0:
                portfolio_transfer_nominal = -effective_cash_balance
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

    def _shock_multiplier(self, shocks: list[MarketShock], *, current_month: date, previous_month: date) -> float:
        current_factor = 1.0
        previous_factor = 1.0
        for shock in shocks:
            current_factor *= shock.factor_at(current_month)
            previous_factor *= shock.factor_at(previous_month)
        if previous_factor == 0:
            return 1.0
        return current_factor / previous_factor

    def _shock_applies_in_month(self, shock: MarketShock, current_month: date) -> bool:
        if current_month < shock.starts_on:
            return False
        return abs(shock.factor_at(current_month) - shock.factor_at(add_months(current_month, -1))) > 1e-9

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
