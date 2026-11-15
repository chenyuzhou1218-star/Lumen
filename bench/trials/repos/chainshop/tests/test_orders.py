import shop  # noqa: F401  (registers event handlers)
from shop import db, orders


def test_an_order_is_paid():
    o = orders.create("u1", [{"sku": "SKU-B", "qty": 1}])
    assert db.orders[o["id"]]["status"] == "paid"


def test_an_order_can_be_cancelled():
    o = orders.create("u1", [{"sku": "SKU-B", "qty": 1}])
    assert orders.cancel(o["id"])["status"] == "cancelled"
