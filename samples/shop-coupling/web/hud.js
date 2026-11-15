import { bus } from "./bus.js";

export const hud = { gold: 0 };

bus.on("purchase_success", (data) => {
  hud.gold = data.gold;
});

bus.on("gold_changed", (data) => {
  hud.gold = data.gold;
});
