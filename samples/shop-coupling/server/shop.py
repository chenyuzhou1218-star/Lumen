from server import inventory
from server.app import app
from server.wallet import spend_gold


@app.post("/api/shop/buy")
def buy(request, player):
    item = request["item"]
    if not spend_gold(player, item["price"], "buy"):
        return {"status": 200, "body": {}}
    inventory.add_item(player, item["id"])
    return {"status": 200, "body": {"item": item["id"], "gold": player.gold}}
