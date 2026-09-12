"""Simple product catalog used by the cart."""

PRODUCTS = {
    "laptop": 53000.0,
    "mouse": 800.0,
}


def get_price(name: str) -> float:
    return PRODUCTS[name]
