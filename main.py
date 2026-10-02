import asyncio
import os
import sqlite3
from contextlib import asynccontextmanager, closing
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

KST = timezone(timedelta(hours=9))
MEMBERS = ["JH", "PH", "SH", "BK", "DJ", "MW", "TS", "HS", "HM", "JS"]
STATUSES = ("먹음", "미정", "안먹음")
CUTOFF_HOUR = 8   # 당일 08:00 까지 미정이면 패널티
MAX_AHEAD = 5     # 오늘 + 5일
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "meal.db"))
# DATABASE_URL 이 있으면 Postgres(외부 DB, 재시작해도 데이터 유지), 없으면 로컬 SQLite
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    import psycopg2
    import psycopg2.extras


class Conn:
    def __init__(self):
        self.pg = bool(DATABASE_URL)
        if self.pg:
            self.c = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        else:
            self.c = sqlite3.connect(DB_PATH, timeout=10)
            self.c.row_factory = sqlite3.Row

    def execute(self, sql, params=()):
        if self.pg:
            cur = self.c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql.replace("?", "%s"), params)
            return cur
        return self.c.execute(sql, params)

    def commit(self):
        self.c.commit()

    def close(self):
        self.c.close()


def db():
    return Conn()


def now_kst():
    return datetime.now(KST)


def init_db():
    with closing(db()) as c:
        auto_id = "SERIAL PRIMARY KEY" if c.pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        for ddl in (
            "CREATE TABLE IF NOT EXISTS meals(date TEXT NOT NULL, member TEXT NOT NULL, "
            "status TEXT NOT NULL, PRIMARY KEY(date, member))",
            "CREATE TABLE IF NOT EXISTS penalties(date TEXT NOT NULL, member TEXT NOT NULL, "
            "PRIMARY KEY(date, member))",
            "CREATE TABLE IF NOT EXISTS snapshots(date TEXT PRIMARY KEY)",
            f"CREATE TABLE IF NOT EXISTS changes(id {auto_id}, date TEXT NOT NULL, "
            "member TEXT NOT NULL, old_status TEXT NOT NULL, new_status TEXT NOT NULL, "
            "reason TEXT NOT NULL, changed_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)",
        ):
            c.execute(ddl)
        if not c.execute("SELECT 1 FROM meta WHERE k='start_date'").fetchone():
            now = now_kst()
            cur = c.execute(
                "INSERT INTO meta VALUES('start_date', ?) ON CONFLICT DO NOTHING",
                (now.date().isoformat(),),
            )
            # 최초 가동이 08:00 이후면 오늘분은 패널티 없이 넘김
            if cur.rowcount == 1 and now.hour >= CUTOFF_HOUR:
                c.execute(
                    "INSERT INTO snapshots VALUES(?) ON CONFLICT DO NOTHING",
                    (now.date().isoformat(),),
                )
        c.commit()


def run_snapshot(now=None):
    """08:00 시점 미정인 팀원에게 패널티 1회 부여(평일만, 날짜당 1회).
    백그라운드 루프뿐 아니라 모든 요청 시작 시에도 호출한다(슬립 서버 대비).
    08:00 이후 첫 요청이 변경보다 먼저 이 함수를 실행하므로 판정 시점이 어긋나지 않는다.
    놓친 과거 평일도 한꺼번에 처리한다(과거 날짜는 수정 불가라 값이 확정돼 있음)."""
    now = now or now_kst()
    today = now.date()
    end = today if now.hour >= CUTOFF_HOUR else today - timedelta(days=1)
    penalized = []
    with closing(db()) as c:
        start = datetime.strptime(
            c.execute("SELECT v FROM meta WHERE k='start_date'").fetchone()["v"], "%Y-%m-%d"
        ).date()
        done = {r["date"] for r in c.execute("SELECT date FROM snapshots")}
        d = start
        while d <= end:
            ds = d.isoformat()
            if ds not in done and d.weekday() < 5:
                # 먼저 스냅샷 행을 선점(동시 요청 시 한 쪽만 성공) 후 패널티 기록
                cur = c.execute("INSERT INTO snapshots VALUES(?) ON CONFLICT DO NOTHING", (ds,))
                if cur.rowcount == 1:
                    rows = c.execute("SELECT member, status FROM meals WHERE date=?", (ds,)).fetchall()
                    decided = {r["member"] for r in rows if r["status"] != "미정"}
                    for m in MEMBERS:
                        if m not in decided:
                            c.execute("INSERT INTO penalties VALUES(?,?) ON CONFLICT DO NOTHING", (ds, m))
                            penalized.append(m)
            d += timedelta(days=1)
        c.commit()
    return penalized


async def snapshot_loop():
    while True:
        try:
            await asyncio.to_thread(run_snapshot)
        except Exception as e:  # 루프는 죽지 않게
            print("snapshot error:", e)
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app):
    init_db()
    task = asyncio.create_task(snapshot_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


class Meal(BaseModel):
    member: str
    date: str
    status: str
    reason: str = ""


@app.get("/")
def index():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))


@app.get("/api/state")
def state():
    run_snapshot()
    now = now_kst()
    today = now.date()
    dates = [(today + timedelta(days=i)).isoformat() for i in range(MAX_AHEAD + 1)]
    statuses = {m: {d: "미정" for d in dates} for m in MEMBERS}
    with closing(db()) as c:
        for r in c.execute(
            "SELECT date, member, status FROM meals WHERE date>=? AND date<=?",
            (dates[0], dates[-1]),
        ):
            if r["member"] in statuses:
                statuses[r["member"]][r["date"]] = r["status"]
        penalties = {m: 0 for m in MEMBERS}
        for r in c.execute("SELECT member, COUNT(*) n FROM penalties GROUP BY member"):
            if r["member"] in penalties:
                penalties[r["member"]] = r["n"]
        start = c.execute("SELECT v FROM meta WHERE k='start_date'").fetchone()["v"]
    return {
        "now": now.isoformat(timespec="seconds"),
        "today": today.isoformat(),
        "cutoff": f"{CUTOFF_HOUR:02d}:00",
        "start_date": start,
        "members": MEMBERS,
        "dates": dates,
        "statuses": statuses,
        "penalties": penalties,
    }


def _next_month(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{y + 1}-01" if m == 12 else f"{y}-{m + 1:02d}"


@app.get("/api/monthly")
def monthly():
    """월별 식수(먹음 체크 수) 합계, 팀원별, 전월 대비 증감."""
    run_snapshot()
    today = now_kst().date().isoformat()
    with closing(db()) as c:
        start = c.execute("SELECT v FROM meta WHERE k='start_date'").fetchone()["v"][:7]
        rows = c.execute(
            "SELECT substr(date,1,7) ym, member, COUNT(*) n, "
            "SUM(CASE WHEN date>? THEN 1 ELSE 0 END) up "
            "FROM meals WHERE status='먹음' GROUP BY substr(date,1,7), member",
            (today,),
        ).fetchall()
    data = {}
    for r in rows:
        if r["member"] not in MEMBERS:
            continue
        d = data.setdefault(r["ym"], {"by": {}, "up": 0})
        d["by"][r["member"]] = int(r["n"])
        d["up"] += int(r["up"] or 0)
    last = max([today[:7]] + list(data))
    out, ym, prev = [], min(start, today[:7]), None
    while ym <= last:
        d = data.get(ym, {"by": {}, "up": 0})
        total = sum(d["by"].values())
        diff = None if prev is None else total - prev
        pct = None if not prev else round((total - prev) / prev * 100, 1)
        out.append({
            "month": ym,
            "total": total,
            "upcoming": d["up"],  # 오늘 이후 '예정' 식수 (변동 가능)
            "by_member": {m: d["by"].get(m, 0) for m in MEMBERS},
            "diff": diff,
            "pct": pct,
        })
        prev = total
        ym = _next_month(ym)
    return {"members": MEMBERS, "months": out, "current": today[:7]}


@app.put("/api/meal")
def set_meal(m: Meal):
    if m.member not in MEMBERS:
        raise HTTPException(400, "알 수 없는 팀원")
    if m.status not in STATUSES:
        raise HTTPException(400, "알 수 없는 상태")
    today = now_kst().date()
    try:
        d = datetime.strptime(m.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "날짜 형식 오류")
    if d < today or d > today + timedelta(days=MAX_AHEAD):
        raise HTTPException(400, f"오늘부터 {MAX_AHEAD}일 후까지만 체크할 수 있습니다")
    run_snapshot()  # 08:00 판정을 변경보다 먼저 확정
    now = now_kst()
    late = d == today and now.hour >= CUTOFF_HOUR  # 당일 08:00 이후 변경
    reason = (m.reason or "").strip()[:200]
    with closing(db()) as c:
        row = c.execute(
            "SELECT status FROM meals WHERE date=? AND member=?", (m.date, m.member)
        ).fetchone()
        old = row["status"] if row else "미정"
        if old == m.status:
            return {"ok": True, "late": False}
        if late:
            if not reason:
                raise HTTPException(400, "08:00 이후 변경은 사유가 필요합니다")
            c.execute(
                "INSERT INTO changes(date,member,old_status,new_status,reason,changed_at) VALUES(?,?,?,?,?,?)",
                (m.date, m.member, old, m.status, reason, now.isoformat(timespec="seconds")),
            )
        if m.status == "미정":
            c.execute("DELETE FROM meals WHERE date=? AND member=?", (m.date, m.member))
        else:
            c.execute(
                "INSERT INTO meals VALUES(?,?,?) ON CONFLICT(date,member) DO UPDATE SET status=excluded.status",
                (m.date, m.member, m.status),
            )
        c.commit()
    return {"ok": True, "late": late}


@app.get("/api/changes")
def changes():
    """08:00 이후 당일 변경 내역 (최근 30건)."""
    with closing(db()) as c:
        rows = c.execute(
            "SELECT date, member, old_status, new_status, reason, changed_at "
            "FROM changes ORDER BY id DESC LIMIT 30"
        ).fetchall()
    return [dict(r) for r in rows]
