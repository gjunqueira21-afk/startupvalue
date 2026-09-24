from __future__ import annotations

import pytest

from app.insights.formatting import compact_money, multiplier, percent, share


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (8_400_000.0, "R$ 8,4 milhões"),
        (1_040_000.0, "R$ 1,0 milhão"),
        (1_960_000.0, "R$ 2,0 milhões"),
        (125_300_000.0, "R$ 125 milhões"),
        (919_272.0, "R$ 919 mil"),
        (2_400_000_000.0, "R$ 2,4 bilhões"),
        (1_200_000_000.0, "R$ 1,2 bilhão"),
        (512.4, "R$ 512"),
        (0.0, "R$ 0"),
        (-1_230_000.0, "-R$ 1,2 milhão"),
        (999_600.0, "R$ 1,0 milhão"),
        (960_000_000.0, "R$ 960 milhões"),
        (999_700_000.0, "R$ 1,0 bilhão"),
        (999.7, "R$ 1 mil"),
    ],
)
def test_compact_money_in_brazilian_portuguese(value: float, expected: str) -> None:
    assert compact_money(value, "BRL") == expected


def test_other_currencies_keep_their_symbol() -> None:
    assert compact_money(3_500_000.0, "USD") == "US$ 3,5 milhões"


def test_percent_multiplier_and_share() -> None:
    assert percent(0.274) == "27,4%"
    assert percent(0.25, decimals=0) == "25%"
    assert multiplier(1.184) == "1,18x"
    assert share(0.0999) == "10%"


def test_exact_extremes_drop_the_decimal() -> None:
    assert percent(0.0) == "0%"
    assert percent(1.0) == "100%"
    assert percent(0.145) == "14,5%"
