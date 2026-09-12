from app.products import get_price


def test_laptop_price():
    assert get_price("laptop") == 53000.0
