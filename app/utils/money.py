# app/utils/money.py

from decimal import Decimal, ROUND_HALF_UP

Money = Decimal

def D(x) -> Money:
    return x if isinstance(x, Decimal) else Decimal(str(x or "0"))

def round_money(x: Money) -> Money:
    return D(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def to_string_money(x) -> str:
    return str(D(x))
