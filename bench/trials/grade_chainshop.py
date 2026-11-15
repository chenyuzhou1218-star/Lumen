"""Grade a fixed copy of chainshop: python grade_chainshop.py <repo>. Each check runs in a fresh process in <repo>."""
import subprocess
import sys

PRE = "import sys; sys.path.insert(0, '.')\nimport shop\nfrom shop import db, orders, catalog, inventory, loyalty, payments, pricing, reports, shipping\n"
CHECKS = {
    "C1 积分按实付金额送": """
o = orders.create("u1", [{"sku": "SKU-A", "qty": 1}], use_points=50)
assert db.points["u1"] == 300 - 50 + o["total"] // 100, (db.points["u1"], o["total"])""",
    "C2 退款退回用掉的积分": """
o = orders.create("u1", [{"sku": "SKU-A", "qty": 1}], use_points=50)
orders.refund(o["id"])
assert db.points["u1"] == 300, db.points["u1"]""",
    "C3 1 积分抵 10 分钱": """
o = orders.create("u1", [{"sku": "SKU-A", "qty": 1}], use_points=50)
assert o["total"] == 2000, o["total"]""",
    "C4 付款后既送积分又建物流单": """
o = orders.create("u1", [{"sku": "SKU-B", "qty": 1}])
assert o["id"] in db.shipments and db.points["u1"] > 300""",
    "C5 还库存不崩溃": """
inventory.release([{"sku": "SKU-A", "qty": 1}])
assert catalog.PRODUCTS["SKU-A"]["stock"] == 6""",
    "C6 付款失败不占库存不扣积分": """
try: orders.create("u2", [{"sku": "SKU-C", "qty": 1}], use_points=10)
except Exception: pass
assert catalog.PRODUCTS["SKU-C"]["stock"] == 2 and db.points["u2"] == 500, (catalog.PRODUCTS["SKU-C"]["stock"], db.points["u2"])""",
    "C7 取消订单还库存": """
o = orders.create("u1", [{"sku": "SKU-A", "qty": 2}])
orders.cancel(o["id"])
assert catalog.PRODUCTS["SKU-A"]["stock"] == 5""",
    "C8 运费按公斤分档": """
assert shipping.cost(800) == 500 and shipping.cost(2500) == 900 and shipping.cost(5000) == 1500""",
    "C9 运费重量算数量": """
o = orders.create("u1", [{"sku": "SKU-B", "qty": 3}])
shipping.on_paid(o) if o["id"] not in db.shipments else None
assert db.shipments[o["id"]]["weight_g"] == 900""",
    "C10 退款只退实付金额": """
before = db.wallets["u1"]
o = orders.create("u1", [{"sku": "SKU-A", "qty": 1}], use_points=50)
orders.refund(o["id"])
assert db.wallets["u1"] == before, (db.wallets["u1"], before)""",
    "C11 报表扣除退款": """
o = orders.create("u1", [{"sku": "SKU-B", "qty": 1}]); orders.refund(o["id"])
assert reports.revenue() == 0, reports.revenue()""",
    "C12 优惠券打折": """
assert pricing.coupon_discount(1000, "TEN") == 100 and pricing.coupon_discount(1000, "HALF") == 500""",
    "C13 抵扣不会变成负数": """
before = db.wallets["u1"]
o = orders.create("u1", [{"sku": "SKU-B", "qty": 1}], use_points=200)
assert o["total"] == 0 and db.wallets["u1"] == before, (o["total"], db.wallets["u1"] - before)""",
}

repo = sys.argv[1]
passed = 0
for name, code in CHECKS.items():
    r = subprocess.run([sys.executable, "-c", PRE + code], cwd=repo, capture_output=True, text=True, timeout=60)
    passed += r.returncode == 0
    print(("对  " if r.returncode == 0 else "错  ") + name + ("" if r.returncode == 0 else "  | " + (r.stderr.strip().splitlines() or ["?"])[-1][:110]))
t = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "--rootdir", ".", "tests"], cwd=repo, capture_output=True, text=True)
print(f"\n{passed}/{len(CHECKS)} 个 bug 修对；仓库自带测试：{(t.stdout.strip().splitlines() or ['?'])[-1]}")
