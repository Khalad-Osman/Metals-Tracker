"""Work out what the portfolio was worth on each day.

Value on a day = sum of (troy ounces held x that day's spot price in USD),
converted to the display currency with that day's USD to CAD rate.

Prices and rates are missing on some days (weekends, holidays, or today before
the data is published), so we use the most recent one on or before the day,
as long as it's no more than MAX_DAYS_OLD old. If there's nothing recent
enough, that day's value is unknown (None) rather than quietly wrong.

Cost is what was paid. A purchase paid in the other currency is converted at
the exchange rate on its purchase date, so the cost doesn't change over time.
"""

import datetime
from bisect import bisect_right
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlmodel import Session, select

from app.models import Currency, ExchangeRate, Metal, MetalPrice, Purchase

# Covers weekends and long holiday weekends, but not data that stopped updating.
MAX_DAYS_OLD = 7
CENTS = Decimal("0.01")


@dataclass
class PortfolioDay:
    date: datetime.date
    value: Decimal | None  # None when there's no recent enough price or rate
    cost: Decimal | None
    gain: Decimal | None
    gain_percent: Decimal | None  # None when nothing had been bought yet


class DailySeries:
    """Values by date, answering "what was the latest value on or before this day?"."""

    def __init__(self, values: dict[datetime.date, Decimal]):
        self.values = values
        self.dates = sorted(values)

    def on_or_before(self, day: datetime.date) -> Decimal | None:
        position = bisect_right(self.dates, day)
        if position == 0:
            return None  # nothing on or before this day
        latest = self.dates[position - 1]
        if (day - latest).days > MAX_DAYS_OLD:
            return None  # too old to trust
        return self.values[latest]


def round_money(amount: Decimal) -> Decimal:
    return amount.quantize(CENTS, rounding=ROUND_HALF_UP)


def portfolio_history(
    session: Session, currency: Currency, start: datetime.date, end: datetime.date
) -> list[PortfolioDay]:
    """The portfolio's value, cost and gain for every day from start to end (inclusive)."""
    purchases = session.exec(select(Purchase)).all()

    prices = {
        metal: DailySeries(
            {
                p.date: p.spot_price_usd
                for p in session.exec(select(MetalPrice).where(MetalPrice.metal == metal))
            }
        )
        for metal in Metal
    }
    rates = DailySeries({r.date: r.usd_to_cad for r in session.exec(select(ExchangeRate))})

    def to_display_currency(amount: Decimal, from_currency: Currency, day: datetime.date):
        """Convert an amount into the display currency using the rate on `day`."""
        if from_currency == currency:
            return amount
        rate = rates.on_or_before(day)
        if rate is None:
            return None
        return amount * rate if from_currency == Currency.USD else amount / rate

    history = []
    day = start
    while day <= end:
        held = [p for p in purchases if p.purchase_date <= day]

        # Market value in USD, then converted with today's rate.
        value_usd = Decimal(0)
        for purchase in held:
            price = prices[purchase.metal].on_or_before(day)
            if price is None:
                value_usd = None
                break
            value_usd += purchase.weight_oz * price
        if not held:
            value = Decimal(0)  # nothing owned yet: worth 0, no price or rate needed
        elif value_usd is None:
            value = None
        else:
            value = to_display_currency(value_usd, Currency.USD, day)

        # Cost, with each purchase converted at the rate on its own purchase date.
        cost = Decimal(0)
        for purchase in held:
            paid = to_display_currency(purchase.price_paid, purchase.currency, purchase.purchase_date)
            if paid is None:
                cost = None
                break
            cost += paid

        value = None if value is None else round_money(value)
        cost = None if cost is None else round_money(cost)
        gain = None if value is None or cost is None else value - cost
        gain_percent = None if gain is None or cost == 0 else round_money(gain / cost * 100)

        history.append(PortfolioDay(day, value, cost, gain, gain_percent))
        day += datetime.timedelta(days=1)

    return history
