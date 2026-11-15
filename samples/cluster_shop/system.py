"""Controlled business fixture, never installed into a user's production project."""
import asyncio


def unit_price(amount, discount, double_discount=False):
    discounted = amount * (100 - discount) // 100
    return discounted * (100 - discount) // 100 if double_discount else discounted


def cart(amount, discount, double_discount=False):
    return unit_price(amount, discount, double_discount)


def invoice(amount, discount, double_discount=False):
    return unit_price(amount, discount, double_discount)


def purchase(db, request_id, amount, idempotent=True):
    if idempotent and db.execute("SELECT 1 FROM orders WHERE request_id=?", (request_id,)).fetchone():
        return
    db.execute("UPDATE wallet SET balance=balance-?", (amount,))
    db.execute("INSERT INTO orders(request_id, amount) VALUES (?,?)", (request_id, amount))


async def debit(wallet, amount, *, gate=None, lock=None):
    async def update():
        previous = wallet["balance"]
        if gate:
            await gate()
        else:
            await asyncio.sleep(0)
        wallet["balance"] = previous - amount
        wallet["ledger"].append(amount)
    if lock:
        async with lock:
            await update()
    else:
        await update()
