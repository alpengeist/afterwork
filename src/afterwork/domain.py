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


class AmountBasis(StrEnum):
    REAL = "Real"
    NOMINAL = "Nominal"


def month_index(start_month: date, current_month: date) -> int:
    return (current_month.year - start_month.year) * 12 + (current_month.month - start_month.month)


def add_months(current: date, months: int) -> date:
    year = current.year + (current.month - 1 + months) // 12
    month = (current.month - 1 + months) % 12 + 1
    return date(year, month, 1)


@dataclass(frozen=True)
class Person:
    birth_date: date
    target_age_years: int

    def age_years_at(self, on_date: date) -> float:
        months = (on_date.year - self.birth_date.year) * 12 + (on_date.month - self.birth_date.month)
        if on_date.day < self.birth_date.day:
            months -= 1
        return months / 12

    def simulation_months(self, start_month: date) -> int:
        current_age_years = self.age_years_at(start_month)
        if self.target_age_years < current_age_years:
            raise ValueError("target_age_years must be greater than the age implied by birth_date")
        return max(int((self.target_age_years - current_age_years) * 12), 0)


@dataclass(frozen=True)
class Portfolio:
    starting_balance: float = 0.0
    annual_growth_rate: float = 0.0

    @property
    def monthly_growth_rate(self) -> float:
        return (1 + self.annual_growth_rate) ** (1 / 12) - 1


@dataclass(frozen=True)
class RecurringFlow:
    amount: float
    frequency: Frequency
    starts_on: date
    ends_on: date | None = None
    category: str = "general"
    target: FlowTarget = FlowTarget.CASH
    amount_basis: AmountBasis = AmountBasis.NOMINAL
    annual_adjustment_rate: float = 0.0
    enabled: bool = True
    color: str | None = None

    def occurs_in_month(self, current_month: date) -> bool:
        if current_month < self.starts_on:
            return False
        if self.ends_on is not None and current_month >= self.ends_on:
            return False
        if self.frequency == Frequency.MONTHLY:
            return True
        return current_month.month == self.starts_on.month

    @property
    def replacement_key(self) -> tuple[str, str]:
        return (self.__class__.__name__, self.category)

    @property
    def display_label(self) -> str:
        return self.category.replace("_", " ").title()

    @property
    def monthly_adjustment_rate(self) -> float:
        return (1 + self.annual_adjustment_rate) ** (1 / 12) - 1

    def adjustment_periods(self, plan_start: date, current_month: date) -> int:
        anchor = plan_start if self.amount_basis == AmountBasis.REAL else self.starts_on
        return max(month_index(anchor, current_month), 0)

    def nominal_amount_for_month(self, plan_start: date, current_month: date) -> float:
        periods = self.adjustment_periods(plan_start, current_month)
        return self.amount * ((1 + self.monthly_adjustment_rate) ** periods)

    def present_value(self, nominal_amount: float, periods: int) -> float:
        return nominal_amount / ((1 + self.monthly_adjustment_rate) ** periods)


@dataclass(frozen=True)
class OneOffEvent:
    amount: float
    occurs_on: date
    category: str = "general"
    target: FlowTarget = FlowTarget.CASH
    enabled: bool = True
    color: str | None = None

    def occurs_in_month(self, current_month: date) -> bool:
        return self.occurs_on.year == current_month.year and self.occurs_on.month == current_month.month

    @property
    def display_label(self) -> str:
        return self.category.replace("_", " ").title()


@dataclass(frozen=True)
class Plan:
    person: Person
    start_month: date
    starting_cash_balance: float = 0.0
    minimal_cash_level: float = 0.0
    portfolio_withdrawal: float = 0.0
    portfolio: Portfolio = field(default_factory=Portfolio)
    recurring_flows: list[RecurringFlow] = field(default_factory=list)
    one_off_events: list[OneOffEvent] = field(default_factory=list)

    def simulation_months(self) -> int:
        return self.person.simulation_months(self.start_month)


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
