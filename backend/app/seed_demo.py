"""Fill an empty database with sample purchases for the public demo.

Run from the backend folder (needs METALS_DEV_API_KEY and internet access):

    uv run python -m app.seed_demo

Downloads market data for the demo period (about 3 metals.dev requests), then
adds three sample purchases dated relative to today. Each one is priced from
that day's real spot price plus a typical dealer premium, so the demo shows
believable gains and losses whenever it's set up. Refuses to run if the
database already has purchases, so it can't mix demo data into real data.
"""

import datetime
import sys
from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal

import httpx2
from sqlmodel import Session, func, select

from app import price_fetcher, rate_fetcher
from app.config import METALS_DEV_API_KEY
from app.database import engine
from app.models import Currency, Metal, Purchase
from app.portfolio import MAX_DAYS_OLD, Market
from app.units import WeightUnit, to_troy_ounces

# (metal, weight, unit, days before today, currency paid in)
DEMO_PURCHASES = [
    (Metal.GOLD, Decimal("1"), WeightUnit.TROY_OUNCE, 75, Currency.CAD),
    (Metal.SILVER, Decimal("500"), WeightUnit.GRAM, 50, Currency.USD),
    (Metal.PLATINUM, Decimal("1"), WeightUnit.TROY_OUNCE, 25, Currency.CAD),
]

# Dealers typically sell small bars and coins a few percent above spot.
DEALER_PREMIUM = Decimal("1.04")


class SeedError(Exception):
    """The demo data can't be added safely."""


def seed_demo(
    session: Session,
    today: datetime.date,
    make_rate_client: Callable[[], httpx2.Client],
    make_price_client: Callable[[], httpx2.Client],
) -> list[Purchase]:
    """Download market data for the demo period and add the sample purchases."""
    if session.exec(select(func.count()).select_from(Purchase)).one() > 0:
        raise SeedError("The database already has purchases; demo data is only added to an empty one.")

    # Start a week before the first purchase: if it falls on a weekend or holiday,
    # there's no rate that day, and the most recent earlier one is used instead.
    first_purchase = today - datetime.timedelta(days=max(days for *_, days, _ in DEMO_PURCHASES))
    start = first_purchase - datetime.timedelta(days=MAX_DAYS_OLD)
    with make_rate_client() as client:
        rate_fetcher.update_rates(session, client, start, today)
    with make_price_client() as client:
        price_fetcher.update_prices(session, client, start, today)

    purchases = []
    for metal, weight, unit, days_ago, currency in DEMO_PURCHASES:
        day = today - datetime.timedelta(days=days_ago)
        market = Market(session, currency)
        spot = market.prices[metal].on_or_before(day)
        if spot is None:
            raise SeedError(f"No {metal.value} price on or before {day}.")
        paid_usd = to_troy_ounces(weight, unit) * spot * DEALER_PREMIUM
        paid = market.convert(paid_usd, Currency.USD, day)
        if paid is None:
            raise SeedError(f"No exchange rate on or before {day}.")

        purchase = Purchase.from_entry(
            metal=metal,
            weight=weight,
            unit=unit,
            purchase_date=day,
            price_paid=paid.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            currency=currency,
        )
        session.add(purchase)
        purchases.append(purchase)
    session.commit()
    return purchases


def main() -> int:
    try:
        with Session(engine) as session:
            purchases = seed_demo(
                session,
                datetime.date.today(),
                make_rate_client=rate_fetcher.make_client,
                make_price_client=lambda: price_fetcher.make_client(METALS_DEV_API_KEY),
            )
            for p in purchases:
                print(
                    f"Added {p.original_weight.normalize():f} {p.original_unit.value} of "
                    f"{p.metal.value} on {p.purchase_date} for {p.price_paid} {p.currency.value}"
                )
    except (SeedError, rate_fetcher.RateFetchError, price_fetcher.PriceFetchError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
