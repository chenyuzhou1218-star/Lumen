"""Shipments, priced by weight."""

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
