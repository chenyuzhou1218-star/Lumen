from server import db


def add_gold(player, amount, reason):
    # No idempotency key: calling this twice for the same event credits twice.
    player.gold += amount
    db.execute("INSERT INTO ledger (player_id, delta, reason) VALUES (?, ?, ?)", player.id, amount, reason)


def spend_gold(player, amount, reason):
    if player.gold < amount:
        return None
    player.gold -= amount
    db.execute("UPDATE players SET gold = ? WHERE id = ?", player.gold, player.id)
    db.execute("INSERT INTO ledger (player_id, delta, reason) VALUES (?, ?, ?)", player.id, -amount, reason)
    return True
