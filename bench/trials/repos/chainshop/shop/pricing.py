"""Prices and coupons."""

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
