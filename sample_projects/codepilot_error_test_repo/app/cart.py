"""Cart with an intentional discount bug for CodePilot agent tests."""


def apply_discount(price: float, percent: float) -> float:
    """Return the price after a percent discount (0-100)."""
    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")
    return price * (percent / 100)
