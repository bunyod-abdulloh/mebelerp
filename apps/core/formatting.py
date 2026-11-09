from decimal import Decimal


def format_money(value):
    """250000.00 -> '250 000', 1234.50 -> '1 234,50'"""
    if value is None:
        return "—"

    text = f"{Decimal(value):,.2f}".replace(",", " ")
    return text.removesuffix(".00").replace(".", ",")
