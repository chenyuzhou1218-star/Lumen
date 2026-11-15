"""Stock reservation."""

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
