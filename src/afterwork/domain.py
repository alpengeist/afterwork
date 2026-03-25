from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class Frequency(StrEnum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class FlowTarget(StrEnum):
    CASH = "cash"
    PORTFOLIO = "portfolio"


def month_index(start_month: date, current_month: date) -> int:
    return (current_month.year - start_month.year) * 12 + (current_month.month - start_month.month)


def add_months(current: date, months: int) -> date:
    year = current.year + (current.month - 1 + months) // 12
    month = (current.month - 1 + months) % 12 + 1
    return date(year, month, 1)


@dataclass(frozen=True)
class Person:
    current_age_years: int
    target_age_years: int

    @property
    def simulation_months(self) -> int:
        if self.target_age_years < self.current_age_years:
            raise ValueError("target_age_years must be greater than or equal to current_age_years")
        return (self.target_age_years - self.current_age_years) * 12


@dataclass(frozen=True)
class Portfolio:
    starting_balance: float = 0.0
    annual_growth_rate: float = 0.0

    @property
    def monthly_growth_rate(self) -> float:
        return (1 + self.annual_growth_rate) ** (1 / 12) - 1


@dataclass(frozen=True)
class RecurringFlow:
    name: str
    amount: float
    frequency: Frequency
    starts_on: date
    ends_on: date | None = None
    category: str = "general"
    target: FlowTarget = FlowTarget.CASH
    annual_adjustment_rate: float = 0.0
    enabled: bool = True

    def occurs_in_month(self, current_month: date) -> bool:
        if current_month < self.starts_on:
            return False
        if self.ends_on is not None and current_month > self.ends_on:
            return False
        if self.frequency == Frequency.MONTHLY:
            return True
        return current_month.month == self.starts_on.month

    @property
    def replacement_key(self) -> tuple[str, str]:
        return (self.__class__.__name__, self.category)

    @property
    def monthly_adjustment_rate(self) -> float:
        return (1 + self.annual_adjustment_rate) ** (1 / 12) - 1

    def nominal_amount_for_period(self, periods: int) -> float:
        return self.amount * ((1 + self.monthly_adjustment_rate) ** periods)

    def present_value(self, nominal_amount: float, periods: int) -> float:
        return nominal_amount / ((1 + self.monthly_adjustment_rate) ** periods)


@dataclass(frozen=True)
class OneOffEvent:
    name: str
    amount: float
    occurs_on: date
    category: str = "general"
    target: FlowTarget = FlowTarget.CASH
    enabled: bool = True

    def occurs_in_month(self, current_month: date) -> bool:
        return self.occurs_on.year == current_month.year and self.occurs_on.month == current_month.month


@dataclass(frozen=True)
class Plan:
    person: Person
    start_month: date
    starting_cash_balance: float = 0.0
    portfolio: Portfolio = field(default_factory=Portfolio)
    recurring_flows: list[RecurringFlow] = field(default_factory=list)
    one_off_events: list[OneOffEvent] = field(default_factory=list)

    def simulation_months(self) -> int:
        return self.person.simulation_months


@dataclass(frozen=True)
class MonthlyRecord:
    month: date
    age_years: float
    cash_flow_nominal: float
    portfolio_contribution_nominal: float
    portfolio_growth_nominal: float
    portfolio_transfer_nominal: float
    flow_present_value: float
    cash_balance: float
    portfolio_balance: float
    total_balance: float
    portfolio_underflow: bool
    applied_flow_names: tuple[str, ...]


@dataclass(frozen=True)
class SimulationResult:
    records: list[MonthlyRecord]

    @property
    def final_cash_balance(self) -> float:
        return self.records[-1].cash_balance if self.records else 0.0

    @property
    def final_portfolio_balance(self) -> float:
        return self.records[-1].portfolio_balance if self.records else 0.0

    @property
    def final_total_balance(self) -> float:
        return self.records[-1].total_balance if self.records else 0.0
