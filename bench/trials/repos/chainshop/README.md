# chainshop

A small online shop: catalogue with prices and weights, wallets, coupons, loyalty points (earned on what you pay,
spent as a discount), stock reservation, shipping by weight, cancellations, refunds and a revenue report.
Modules talk through an event bus (shop/events.py): order_paid, order_cancelled, order_refunded.
Policy numbers live in shop/policy.py.
An order's total is what the customer pays for the goods (after coupon and points); shipping is billed
separately and is not part of the total.
