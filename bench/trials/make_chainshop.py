"""D:/CodeDoctor/trials/chainshop: a small shop whose 13 planted defects form chains and loops - fixing one exposes the
next (orders -> events -> inventory/shipping/loyalty -> orders; orders -> payments -> reports). Local git repository.
Answer key: chainshop_truth.md in the scratchpad."""
import subprocess
from pathlib import Path

ROOT = Path("D:/CodeDoctor/trials/chainshop")
FILES = {
"README.md": """# chainshop

A small online shop: catalogue with prices and weights, wallets, coupons, loyalty points (earned on what you pay,
spent as a discount), stock reservation, shipping by weight, cancellations, refunds and a revenue report.
Modules talk through an event bus (shop/events.py): order_paid, order_cancelled, order_refunded.
Policy numbers live in shop/policy.py.
""",
"shop/__init__.py": '''"""Importing the package registers every module's event handlers."""

from shop import inventory, loyalty, shipping  # noqa: F401
''',
"shop/policy.py": '''"""Shop policy."""

POINT_VALUE_CENTS = 10     # one loyalty point is worth 10 cents when spent
POINTS_PER_YUAN = 1        # one point per full yuan (100 cents) actually paid
COUPONS = {"TEN": 10, "HALF": 50}           # percent off the subtotal
SHIPPING_TIERS_KG = [(1, 500), (3, 900), (None, 1500)]   # (up to this many kg, cost in cents)
''',
"shop/catalog.py": '''"""Products. Keys are upper-case SKUs."""

PRODUCTS = {
    "SKU-A": {"name": "Kettle", "price_cents": 2500, "weight_g": 1200, "stock": 5},
    "SKU-B": {"name": "Mug", "price_cents": 800, "weight_g": 300, "stock": 20},
    "SKU-C": {"name": "Teapot", "price_cents": 4000, "weight_g": 2500, "stock": 2},
}
''',
"shop/db.py": '''"""In-memory state."""

wallets = {"u1": 20000, "u2": 1000}   # cents
points = {"u1": 300, "u2": 500}
orders = {}
payments = []        # (user, cents, kind)
shipments = {}       # order_id -> {"weight_g", "cost"}
''',
"shop/events.py": '''"""A tiny event bus."""

_handlers = {}


def subscribe(event, fn):
    _handlers.setdefault(event, {})[fn.__name__] = fn


def emit(event, **payload):
    for fn in list(_handlers.get(event, {}).values()):
        fn(**payload)
''',
"shop/pricing.py": '''"""Prices and coupons."""

from shop import catalog, policy


def unit_price(sku):
    return catalog.PRODUCTS[sku.upper()]["price_cents"]


def subtotal(lines):
    return sum(unit_price(l["sku"]) * l["qty"] for l in lines)


def coupon_discount(cents, code):
    if not code:
        return 0
    pct = policy.COUPONS[code]
    return cents * (pct // 100)
''',
"shop/loyalty.py": '''"""Loyalty points: earned on what the customer paid, spent as a discount."""

from shop import db, events, policy


def balance(user):
    return db.points.get(user, 0)


def redeem(user, points):
    """Spend points; returns the discount they are worth."""
    if points > balance(user):
        raise ValueError("not enough points")
    db.points[user] -= points
    return points


def on_paid(order):
    db.points[order["user"]] = balance(order["user"]) + order["subtotal"] // 100 * policy.POINTS_PER_YUAN


def on_refunded(order):
    earned = order["subtotal"] // 100 * policy.POINTS_PER_YUAN
    db.points[order["user"]] = max(0, balance(order["user"]) - earned)


events.subscribe("order_paid", on_paid)
events.subscribe("order_refunded", on_refunded)
''',
"shop/inventory.py": '''"""Stock reservation."""

from shop import catalog, events


class OutOfStock(Exception):
    pass


def stock(sku):
    return catalog.PRODUCTS[sku.upper()]["stock"]


def reserve(lines):
    for l in lines:
        if catalog.PRODUCTS[l["sku"]]["stock"] < l["qty"]:
            raise OutOfStock(l["sku"])
    for l in lines:
        catalog.PRODUCTS[l["sku"]]["stock"] -= l["qty"]


def release(lines):
    for l in lines:
        catalog.PRODUCTS[l["sku"].lower()]["stock"] += l["qty"]


def on_cancelled(items=None, **_):
    if items:
        release(items)


events.subscribe("order_cancelled", on_cancelled)
''',
"shop/payments.py": '''"""Wallet payments."""

from shop import db


class Declined(Exception):
    pass


def charge(user, cents):
    if db.wallets.get(user, 0) < cents:
        raise Declined(user)
    db.wallets[user] -= cents
    db.payments.append((user, cents, "charge"))


def refund(order):
    amount = order["subtotal"]
    db.wallets[order["user"]] += amount
    db.payments.append((order["user"], amount, "refund"))
''',
"shop/shipping.py": '''"""Shipments, priced by weight."""

from shop import catalog, db, events, policy


def cost(weight_g):
    for limit_kg, cents in policy.SHIPPING_TIERS_KG:
        if limit_kg is None or weight_g <= limit_kg:
            return cents


def on_paid(order):
    weight = sum(catalog.PRODUCTS[l["sku"]]["weight_g"] for l in order["lines"])
    db.shipments[order["id"]] = {"weight_g": weight, "cost": cost(weight)}


def on_cancelled(order=None, **_):
    if order:
        db.shipments.pop(order["id"], None)


events.subscribe("order_paid", on_paid)
events.subscribe("order_cancelled", on_cancelled)
''',
"shop/orders.py": '''"""Placing, cancelling and refunding orders."""

import uuid

from shop import db, events, inventory, loyalty, payments, pricing


def _lines(items):
    return [{"sku": i["sku"].strip().upper(), "qty": int(i["qty"])} for i in items]


def create(user, items, coupon=None, use_points=0):
    lines = _lines(items)
    subtotal = pricing.subtotal(lines)
    discount = pricing.coupon_discount(subtotal, coupon)
    points_discount = loyalty.redeem(user, use_points) if use_points else 0
    total = subtotal - discount - points_discount
    inventory.reserve(lines)
    payments.charge(user, total)
    order = {"id": "o-" + uuid.uuid4().hex[:8], "user": user, "lines": lines, "subtotal": subtotal,
             "discount": discount, "points_used": use_points, "total": total, "status": "paid"}
    db.orders[order["id"]] = order
    events.emit("order_paid", order=order)
    return order


def cancel(order_id):
    order = db.orders[order_id]
    if order["status"] != "paid":
        raise ValueError("only paid orders can be cancelled")
    order["status"] = "cancelled"
    payments.refund(order)
    events.emit("order_cancelled", order=order)
    return order


def refund(order_id):
    order = db.orders[order_id]
    if order["status"] != "paid":
        raise ValueError("only paid orders can be refunded")
    order["status"] = "refunded"
    payments.refund(order)
    events.emit("order_refunded", order=order)
    return order
''',
"shop/reports.py": '''"""Revenue."""

from shop import db


def revenue():
    """Money kept: charges minus refunds."""
    return sum(cents for _, cents, _ in db.payments)
''',
"tests/test_orders.py": '''import shop  # noqa: F401  (registers event handlers)
from shop import db, orders


def test_an_order_is_paid():
    o = orders.create("u1", [{"sku": "SKU-B", "qty": 1}])
    assert db.orders[o["id"]]["status"] == "paid"


def test_an_order_can_be_cancelled():
    o = orders.create("u1", [{"sku": "SKU-B", "qty": 1}])
    assert orders.cancel(o["id"])["status"] == "cancelled"
''',
}

TRUTH = """# Answer key for D:/CodeDoctor/trials/chainshop (13 defects, chained)

C1  loyalty.on_paid earns points on the subtotal, not on what was paid (total).
C2  loyalty.on_refunded does not give back the points spent on the order (and takes back points by subtotal).
C3  loyalty.redeem returns points instead of points * POINT_VALUE_CENTS -> spending points is worth 10x too little.
C4  events.subscribe keys handlers by function name: shipping.on_paid replaces loyalty.on_paid and
    shipping.on_cancelled replaces inventory.on_cancelled -> no points are ever earned, cancelling never returns stock.
C5  inventory.release looks up sku.lower() -> KeyError (keys are upper-case); hidden until C4/C7 or C6 call it.
C6  orders.create reserves stock (and spends points) before charging; a declined payment leaks both.
C7  inventory.on_cancelled expects items=, the bus sends order= -> releases nothing (hidden until C4 is fixed).
C8  shipping.cost compares grams with the kg tiers -> every parcel costs the top tier.
C9  shipping.on_paid ignores quantities when weighing.
C10 payments.refund refunds the subtotal instead of what was charged (total).
C11 reports.revenue adds refunds instead of subtracting them.
C12 pricing.coupon_discount uses pct // 100 (= 0) -> coupons give nothing.
C13 orders.create does not stop at zero: discounts above the subtotal charge a negative amount (hidden until C3/C12).
Chains: C4 -> C7 -> C5 ; C6 -> C5 ; C3/C12 -> C13 ; C1 <-> C2 <-> C10 (points and money must both round-trip).
"""

for rel, text in FILES.items():
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
subprocess.run(["git", "init", "-q"], cwd=ROOT, check=True)
subprocess.run(["git", "-c", "core.autocrlf=false", "add", "-A"], cwd=ROOT, check=True)
subprocess.run(["git", "-c", "user.name=trial", "-c", "user.email=trial@example.invalid", "commit", "-q", "-m", "chainshop"],
               cwd=ROOT, check=True)
Path(__file__).with_name("chainshop_truth.md").write_text(TRUTH, encoding="utf-8")
print("ok")
