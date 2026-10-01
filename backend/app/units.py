from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

GRAMS_PER_TROY_OUNCE = Decimal("31.1034768")

# weight_oz is stored with 8 decimal places (about 0.0000003 g of precision).
TROY_OUNCE_PRECISION = Decimal("0.00000001")


class WeightUnit(str, Enum):
    GRAM = "g"
    TROY_OUNCE = "troy_oz"
    KILOGRAM = "kg"


def to_troy_ounces(weight: Decimal, unit: WeightUnit) -> Decimal:
    """Convert a weight in grams, troy ounces or kilograms to troy ounces."""
    if unit == WeightUnit.GRAM:
        ounces = weight / GRAMS_PER_TROY_OUNCE
    elif unit == WeightUnit.KILOGRAM:
        ounces = weight * 1000 / GRAMS_PER_TROY_OUNCE
    else:
        ounces = weight

    return ounces.quantize(TROY_OUNCE_PRECISION, rounding=ROUND_HALF_UP)
