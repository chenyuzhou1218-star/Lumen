import { bus } from "./bus.js";
import { retryFetch } from "./net.js";

export class ShopUI {
  async onBuyClick(item) {
    const res = await retryFetch("/api/shop/buy", { method: "POST", body: JSON.stringify({ item }) });
    const data = await res.json();
    if (data.item) {
      this.gold = data.gold;
      bus.emit("purchase_success", data);
    }
  }
}
