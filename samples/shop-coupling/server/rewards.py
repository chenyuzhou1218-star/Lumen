from server.app import app
from server.wallet import add_gold


def compute_reward(match):
    return 50 + match["kills"] * 10


@app.post("/api/match/settle")
def settle(request, player):
    reward = compute_reward(request["match"])
    add_gold(player, reward, "match")
    player.matches_played += 1
    return {"status": 200, "body": {"reward": reward, "gold": player.gold}}
