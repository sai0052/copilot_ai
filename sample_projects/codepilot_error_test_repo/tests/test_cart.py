from app.cart import apply_discount


def test_zero_percent_keeps_price():
    assert apply_discount(100, 0) == 100
