from decimal import Decimal, ROUND_HALF_UP

def to_minor_units(amount: Decimal, currency: str = "INR") -> int:
    """
    Converts a Decimal major unit amount (e.g. ₹3,898.00) to integer minor currency units (e.g. 389800 paise).
    Enforces exact integer conversion with no floating-point arithmetic.
    """
    if currency.upper() in ("INR", "USD", "EUR", "GBP"):
        multiplier = Decimal("100")
    else:
        multiplier = Decimal("100")

    quantized = (amount * multiplier).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(quantized)

def from_minor_units(amount_minor: int, currency: str = "INR") -> Decimal:
    """
    Converts integer minor currency units (e.g. 389800 paise) back to Decimal major units (e.g. Decimal('3898.00')).
    """
    if currency.upper() in ("INR", "USD", "EUR", "GBP"):
        divisor = Decimal("100")
    else:
        divisor = Decimal("100")

    return (Decimal(str(amount_minor)) / divisor).quantize(Decimal("0.01"))
