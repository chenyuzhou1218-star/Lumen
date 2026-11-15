"""Grade a fixed copy of library: python grade_library.py <repo>. Each check runs in a fresh process in <repo>."""
import subprocess
import sys

PRE = "import sys; sys.path.insert(0, '.')\nfrom datetime import timedelta\nfrom lib import db, loans, clock\n"
CHECKS = {
    "L1 还书后书能再借": """
l = loans.borrow("m1", "b1"); loans.give_back(l["id"])
from lib import catalog
assert catalog.available("b1") == 1""",
    "L2 Gold 会员能借书": """
loans.borrow("m2", "b2")""",
    "L3 还掉的书不占额度": """
for _ in range(3):
    l = loans.borrow("m1", "b2"); loans.give_back(l["id"])
loans.borrow("m1", "b2")""",
    "L4 预约人借到后出队": """
db.books["b3"]["copies"] = 1
l = loans.borrow("m1", "b3")
for m in ("m3", "m2"):
    try: loans.borrow(m, "b3")
    except Exception: pass
db.loans[l["id"]]["status"] = "active"
from lib import counters
loans.give_back(l["id"])
l3 = loans.borrow("m3", "b3"); loans.give_back(l3["id"])
loans.borrow("m2", "b3")""",
    "L5 宽限期内不罚款": """
l = loans.borrow("m1", "b2"); db.loans[l["id"]]["due"] = clock.now() - timedelta(days=2, hours=1)
loans.give_back(l["id"])
assert db.fines.get("m1", 0) == 0""",
    "L6 减免记为负收入": """
from lib import fines, reports
db.fines["m1"] = 300; fines.pay("m1", 100); fines.waive("m1", 200)
assert reports.fine_revenue() == 100""",
    "L7 通知里写会员名字": """
from lib import notifications
assert "Ann" in notifications.book_ready("m1", "b1")""",
    "L8 逾期报表不报错": """
from lib import reports
l = loans.borrow("m1", "b2"); db.loans[l["id"]]["due"] = clock.now() - timedelta(days=1)
assert reports.overdue() == [l["id"]]""",
    "L9 续借从到期日往后加": """
l = loans.borrow("m1", "b2"); due = l["due"]
assert loans.renew(l["id"])["due"] - due >= timedelta(days=13)""",
    "L10 网页借书字段对上": """
import re
js = open("web/shelf.js", encoding="utf-8").read(); api = open("lib/api.py", encoding="utf-8").read()
sent = re.search(r"api/borrow.*?JSON.stringify\\(\\{\\s*(\\w+)\\s*[:,}]", js, re.S).group(1)
assert f'b["{sent}"]' in api or f"b['{sent}']" in api or f'b.get("{sent}"' in api""",
    "L11 网页显示可借数量": """
assert "data.avail}" not in open("web/shelf.js", encoding="utf-8").read()""",
    "L12 已还的不能续借": """
l = loans.borrow("m1", "b2"); loans.give_back(l["id"])
try: loans.renew(l["id"]); ok = False
except Exception: ok = True
assert ok""",
    "L13 同一本书不能借两次": """
loans.borrow("m1", "b2")
try: loans.borrow("m1", "b2"); ok = False
except Exception: ok = True
assert ok""",
}

repo = sys.argv[1]
passed = 0
for name, code in CHECKS.items():
    r = subprocess.run([sys.executable, "-c", PRE + code], cwd=repo, capture_output=True, text=True, timeout=60)
    passed += r.returncode == 0
    print(("对  " if r.returncode == 0 else "错  ") + name + ("" if r.returncode == 0 else "  | " + (r.stderr.strip().splitlines() or ["?"])[-1][:110]))
t = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"\n{passed}/{len(CHECKS)} 个 bug 修对；仓库自带测试：{(t.stdout.strip().splitlines() or ['?'])[-1]}")
