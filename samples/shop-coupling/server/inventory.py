from server import db


def add_item(player, item_id):
    player.items.append(item_id)
    db.execute("INSERT INTO inventory (player_id, item_id) VALUES (?, ?)", player.id, item_id)
