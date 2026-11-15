# shop-coupling (sample project with known cross-module defects)

Used by the coupling-graph tests and for trying the multi-agent cluster. Known, deliberate problems:

1. `player.gold` is written by `wallet.add_gold` and `wallet.spend_gold`, reachable from three routes (buy, settle, reconnect) with no lock or transaction.
2. `session.reconnect` replays pending requests, including `/api/match/settle`, and `wallet.add_gold` has no idempotency key: reconnecting can pay a match reward twice (common root cause with the shop's retry).
3. `web/net.js retryFetch` retries `/api/shop/buy`; the buy path has no idempotency key: a lost response can charge twice.
4. `wallet.spend_gold` updates `players` and inserts into `ledger` without a transaction: a failure in between breaks gold = sum(ledger).
5. `wallet.spend_gold` returns None when gold is insufficient and `shop.buy` turns that into `200 {}`: the client sees nothing happen.
6. `web/hud.js` listens for `gold_changed`, which nothing emits.
7. `web/match.js` calls `/api/match/report`, which no server route handles.
