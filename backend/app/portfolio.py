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


@dataclass
class Holding:
    """One metal's position on a day."""

    metal: Metal
    weight_oz: Decimal
    value: Decimal | None
    cost: Decimal | None
    # Kept so shares add up correctly; not sent to the frontend.
    unrounded_value: Decimal | None = None
    gain: Decimal | None = None
    gain_percent: Decimal | None = None
    share_percent: Decimal | None = None  # of the whole portfolio's value


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


class Market:
    """Stored prices and exchange rates, for working out values in one display currency."""

    def __init__(self, session: Session, currency: Currency):
        self.currency = currency
        self.prices = {
            metal: DailySeries(
                {
                    p.date: p.spot_price_usd
                    for p in session.exec(select(MetalPrice).where(MetalPrice.metal == metal))
                }
            )
            for metal in Metal
        }
        self.rates = DailySeries(
            {r.date: r.usd_to_cad for r in session.exec(select(ExchangeRate))}
        )

    def convert(
        self, amount: Decimal, from_currency: Currency, day: datetime.date
    ) -> Decimal | None:
        """Convert an amount into the display currency using the rate on `day`."""
        if from_currency == self.currency:
            return amount
        rate = self.rates.on_or_before(day)
        if rate is None:
            return None
        return amount * rate if from_currency == Currency.USD else amount / rate

    def value(self, purchases: list[Purchase], day: datetime.date) -> Decimal | None:
        """What these purchases were worth on `day`, unrounded, or None if unknown."""
        if not purchases:
            return Decimal(0)  # nothing owned: worth 0, no price or rate needed

        value_usd = Decimal(0)
        for purchase in purchases:
            price = self.prices[purchase.metal].on_or_before(day)
            if price is None:
                return None
            value_usd += purchase.weight_oz * price
        return self.convert(value_usd, Currency.USD, day)

    def cost(self, purchases: list[Purchase]) -> Decimal | None:
        """What was paid for these purchases, unrounded, or None if unknown.

        Each purchase is converted at the rate on its own purchase date.
        """
        total = Decimal(0)
        for purchase in purchases:
            paid = self.convert(purchase.price_paid, purchase.currency, purchase.purchase_date)
            if paid is None:
                return None
            total += paid
        return total


def gain_and_percent(
    value: Decimal | None, cost: Decimal | None
) -> tuple[Decimal | None, Decimal | None]:
    """Gain (value - cost) and gain as a percentage of cost, from rounded amounts."""
    if value is None or cost is None:
        return None, None
    gain = value - cost
    gain_percent = None if cost == 0 else round_money(gain / cost * 100)
    return gain, gain_percent


def portfolio_history(
    session: Session, currency: Currency, start: datetime.date, end: datetime.date
) -> list[PortfolioDay]:
    """The portfolio's value, cost and gain for every day from start to end (inclusive)."""
    purchases = session.exec(select(Purchase)).all()
    market = Market(session, currency)

    history = []
    day = start
    while day <= end:
        held = [p for p in purchases if p.purchase_date <= day]
        value = market.value(held, day)
        cost = market.cost(held)

        value = None if value is None else round_money(value)
        cost = None if cost is None else round_money(cost)
        gain, gain_percent = gain_and_percent(value, cost)

        history.append(PortfolioDay(day, value, cost, gain, gain_percent))
        day += datetime.timedelta(days=1)

    return history


def holdings_on(session: Session, currency: Currency, day: datetime.date) -> list[Holding]:
    """What's held of each metal on `day`, with its value, cost, gain and share.

    Only metals with at least one purchase on or before `day` are included,
    in the usual metal order (gold, silver, platinum, palladium).
    """
    purchases = session.exec(select(Purchase).where(Purchase.purchase_date <= day)).all()
    market = Market(session, currency)

    holdings = []
    for metal in Metal:
        held = [p for p in purchases if p.metal == metal]
        if not held:
            continue
        value = market.value(held, day)
        cost = market.cost(held)
        holdings.append(
            Holding(
                metal=metal,
                weight_oz=sum((p.weight_oz for p in held), Decimal(0)),
                value=None if value is None else round_money(value),
                cost=None if cost is None else round_money(cost),
                unrounded_value=value,
            )
        )

    # Share of the total value, worked out only when every metal's value is known.
    values = [h.unrounded_value for h in holdings]
    if holdings and None not in values and sum(values) > 0:
        total = sum(values)
        for holding in holdings:
            holding.share_percent = round_money(holding.unrounded_value / total * 100)

    for holding in holdings:
        holding.gain, holding.gain_percent = gain_and_percent(holding.value, holding.cost)
    return holdings
