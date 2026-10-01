from decimal import Decimal

from app.units import WeightUnit, to_troy_ounces


def test_one_troy_ounce_in_grams_is_one_ounce():
    assert to_troy_ounces(Decimal("31.1034768"), WeightUnit.GRAM) == Decimal("1")


def test_grams_are_converted_and_rounded_to_8_places():
    assert to_troy_ounces(Decimal("100"), WeightUnit.GRAM) == Decimal("3.21507466")


def test_one_kilogram_in_troy_ounces():
    assert to_troy_ounces(Decimal("1"), WeightUnit.KILOGRAM) == Decimal("32.15074657")


def test_troy_ounces_are_unchanged():
    assert to_troy_ounces(Decimal("2.5"), WeightUnit.TROY_OUNCE) == Decimal("2.5")


def test_result_is_a_decimal():
    result = to_troy_ounces(Decimal("10"), WeightUnit.GRAM)
    assert isinstance(result, Decimal)
