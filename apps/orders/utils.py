import re

ORDER_NUMBER_RE = re.compile(r"^M-(\d{1,9})$", re.IGNORECASE)


def parse_order_number(value: str) -> int | None:
    match = ORDER_NUMBER_RE.match(value.strip())
    return int(match.group(1)) if match else None


def order_number(pk) -> str:
    # Hisobotlar ham shu funksiyadan foydalanadi: format bir joyda turadi
    return f"M-{pk:06d}"
