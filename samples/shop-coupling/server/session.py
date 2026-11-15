from server.app import app
from server.rewards import settle


@app.post("/api/session/reconnect")
def reconnect(request, player):
    # Replays every request that never got a response before the disconnect.
    for pending in player.pending_requests:
        if pending["path"] == "/api/match/settle":
            settle(pending, player)
    player.online = True
    return {"status": 200, "body": {}}
