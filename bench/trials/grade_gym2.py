"""Grade a fixed copy of gym-booking2: python grade_gym2.py <repo>. Each check runs in a fresh process in <repo>."""
import subprocess
import sys

CHECKS = {
    "G1 满员拒绝预约": """
from server import bookings
bookings.book("ann","yoga-mon"); bookings.book("bob","yoga-mon")
try: bookings.book("cat","yoga-mon"); ok=False
except Exception as e: ok="full" in str(e).lower() or type(e).__name__=="ClassFull"
assert ok""",
    "G2 取消后由替补付费": """
from server import bookings, db
db.classes["spin-tue"]["capacity"]=1
b=bookings.book("ann","spin-tue"); db.waitlists["spin-tue"]=["dan"]
a,d=db.credits["ann"],db.credits["dan"]; bookings.cancel(b["id"])
assert db.credits["ann"]>=a and db.credits["dan"]==d-1""",
    "G3 提前两天取消能退课时": """
from server import bookings, db
b=bookings.book("ann","yoga-mon"); a=db.credits["ann"]; bookings.cancel(b["id"])
assert db.credits["ann"]==a+1""",
    "G4 提醒按 UTC 计算": """
from datetime import timedelta
from server import bookings, classes, reminders
bookings.book("ann","yoga-mon"); st=classes.starts_at("yoga-mon")
assert any(c=="yoga-mon" for _,c in reminders.due(st-timedelta(minutes=30)))""",
    "G5 扣课时记录为负": """
from server import bookings, db
bookings.book("ann","yoga-mon")
assert [d for u,d,r in db.history if u=="ann"]==[-1]""",
    "G6 网页取消字段对上": """
import re
js=open("web/timetable.js",encoding="utf-8").read(); app=open("server/app.py",encoding="utf-8").read()
sent=re.search(r"api/cancel.*?JSON.stringify\\(\\{\\s*(\\w+)\\s*:",js,re.S).group(1)
assert f'b["{sent}"]' in app or f"b['{sent}']" in app or f'b.get("{sent}"' in app""",
    "G7 候补从第 1 位开始": """
from server import bookings
bookings.book("ann","yoga-mon"); bookings.book("bob","yoga-mon")
try: bookings.book("cat","yoga-mon")
except Exception as e: msg=str(e)
assert "1" in msg and "number 0" not in msg""",
    "G8 spin 课剩余名额不报错": """
from server import classes
assert classes.remaining("spin-tue")==3""",
    "G9 提前一小时提醒": """
from datetime import timedelta
from server import reminders
assert reminders.REMIND_BEFORE==timedelta(hours=1)""",
    "G10 网页剩余名额拼写": """
assert "cls.remainig" not in open("web/timetable.js",encoding="utf-8").read()""",
    "G11 同一人不能重复约": """
from server import bookings
bookings.book("ann","spin-tue")
try: bookings.book("ann","spin-tue"); ok=False
except Exception: ok=True
assert ok""",
}

repo = sys.argv[1]
passed = 0
for name, code in CHECKS.items():
    r = subprocess.run([sys.executable, "-c", code], cwd=repo, capture_output=True, text=True, timeout=60)
    passed += r.returncode == 0
    print(("对  " if r.returncode == 0 else "错  ") + name + ("" if r.returncode == 0 else "  | " + (r.stderr.strip().splitlines() or ["?"])[-1][:120]))
t = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "--rootdir", ".", "tests"], cwd=repo, capture_output=True, text=True)
print(f"\n{passed}/{len(CHECKS)} 个 bug 修对；仓库自带测试：{(t.stdout.strip().splitlines() or ['?'])[-1]}")
