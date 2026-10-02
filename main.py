import asyncio, os, re, sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone, date
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from kr_holidays import HOLIDAYS

MEMBERS = ["JH","PH","SH","BK","DJ","MW","TS","HS","HM","JS"]
STATUSES = ("먹음","미정","안먹음")
CUTOFF = 8
AHEAD = 5
DB_URL = os.environ.get("DATABASE_URL")
KST = timezone(timedelta(hours=9))
app = FastAPI()

class Conn:
    def __init__(self):
        if DB_URL:
            import psycopg2, psycopg2.extras
            self.pg = True
            self.c = psycopg2.connect(DB_URL).cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            self.pg = False
            db = sqlite3.connect(os.environ.get("DB_PATH", "meal.db"))
            db.row_factory = sqlite3.Row
            self.db = db; self.c = db
    def q(self, sql, p=()):
        if self.pg: sql = sql.replace("?", "%s")
        cur = self.c.execute(sql, p) if not self.pg else (self.c.execute(sql, p) or self.c)
        return cur
    def commit(self):
        (self.c.connection if self.pg else self.db).commit()
    def close(self):
        (self.c.connection if self.pg else self.db).close()

def conn():
    return closing(Conn())

def init_db():
    with conn() as c:
        ai = "SERIAL PRIMARY KEY" if c.pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        c.q("CREATE TABLE IF NOT EXISTS meals(member TEXT, d TEXT, status TEXT, PRIMARY KEY(member,d))")
        c.q("CREATE TABLE IF NOT EXISTS penalties(member TEXT, d TEXT, PRIMARY KEY(member,d))")
        c.q("CREATE TABLE IF NOT EXISTS done(d TEXT PRIMARY KEY)")
        c.q(f"CREATE TABLE IF NOT EXISTS logs(id {ai}, at TEXT, member TEXT, d TEXT, old TEXT, new TEXT, reason TEXT)")
        c.q("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
        now = datetime.now(KST)
        c.q("INSERT INTO meta VALUES('start',?) ON CONFLICT DO NOTHING", (now.date().isoformat(),))
        c.commit()

def now_kst(): return datetime.now(KST)
def workday(d: date): return d.weekday() < 5 and d.isoformat() not in HOLIDAYS

def open_dates(today: date):
    out, d = [], today
    if workday(d): out.append(d)
    n = 0
    while n < AHEAD:
        d += timedelta(days=1)
        if workday(d): out.append(d); n += 1
    return out

def snapshot():
    now = now_kst()
    with conn() as c:
        start = datetime.strptime(c.q("SELECT v FROM meta WHERE k='start'").fetchone()["v"], "%Y-%m-%d").date()
        d = start
        while d <= now.date():
            passed = d < now.date() or now.hour >= CUTOFF
            ds = d.isoformat()
            skip = d == start and d == now.date()
            if passed and workday(d) and not skip:
                cur = c.q("INSERT INTO done VALUES(?) ON CONFLICT DO NOTHING", (ds,))
                if cur.rowcount == 1:
                    got = {r["member"] for r in c.q("SELECT member FROM meals WHERE d=? AND status IN ('먹음','안먹음')", (ds,)).fetchall()}
                    for m in MEMBERS:
                        if m not in got:
                            c.q("INSERT INTO penalties VALUES(?,?) ON CONFLICT DO NOTHING", (m, ds))
            d += timedelta(days=1)
        c.commit()

async def loop():
    while True:
        try: snapshot()
        except Exception as e: print("snapshot", e)
        await asyncio.sleep(30)

@app.on_event("startup")
async def _s():
    init_db(); asyncio.create_task(loop())

@app.get("/")
def index(): return FileResponse("index.html")

@app.get("/api/state")
def state():
    snapshot(); now = now_kst()
    with conn() as c:
        pen = {m: 0 for m in MEMBERS}
        for r in c.q("SELECT member, COUNT(*) n FROM penalties GROUP BY member").fetchall(): pen[r["member"]] = r["n"]
        start = c.q("SELECT v FROM meta WHERE k='start'").fetchone()["v"]
    return {"today": now.date().isoformat(), "hour": now.hour, "members": MEMBERS, "penalties": pen, "start": start,
            "open": [x.isoformat() for x in open_dates(now.date())]}

def nxt(ym):
    y, m = map(int, ym.split("-")); return f"{y+1}-01" if m == 12 else f"{y}-{m+1:02d}"

@app.get("/api/month")
def month(ym: str, member: str):
    if member not in MEMBERS or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", ym): raise HTTPException(400)
    snapshot(); a, b = ym + "-01", nxt(ym) + "-01"
    with conn() as c:
        st = {r["d"]: r["status"] for r in c.q("SELECT d,status FROM meals WHERE member=? AND d>=? AND d<?", (member, a, b)).fetchall()}
        pn = [r["d"] for r in c.q("SELECT d FROM penalties WHERE member=? AND d>=? AND d<?", (member, a, b)).fetchall()]
    return {"ym": ym, "status": st, "penalty": pn, "off": sorted(d for d in HOLIDAYS if d.startswith(ym))}

@app.get("/api/all")
def allv():
    snapshot(); days = [x.isoformat() for x in open_dates(now_kst().date())]
    with conn() as c:
        rows = c.q("SELECT member,d,status FROM meals WHERE d>=? AND d<=?", (days[0], days[-1])).fetchall() if days else []
    t = {m: {} for m in MEMBERS}
    for r in rows: t[r["member"]][r["d"]] = r["status"]
    return {"days": days, "table": t}

@app.get("/api/monthly")
def monthly():
    with conn() as c:
        rows = c.q("SELECT substr(d,1,7) ym, member, COUNT(*) n FROM meals WHERE status='먹음' GROUP BY 1,2 ORDER BY 1").fetchall()
    ms = {}
    for r in rows: ms.setdefault(r["ym"], {})[r["member"]] = r["n"]
    out, prev = [], None
    for ym in sorted(ms):
        tot = sum(ms[ym].values())
        out.append({"ym": ym, "total": tot, "by": ms[ym], "diff": None if prev is None else tot - prev}); prev = tot
    return {"months": out[::-1], "now": now_kst().strftime("%Y-%m")}

class Put(BaseModel):
    member: str; date: str; status: str; reason: str = ""

@app.put("/api/meal")
def put(p: Put):
    if p.member not in MEMBERS or p.status not in STATUSES: raise HTTPException(400, "잘못된 값")
    snapshot(); now = now_kst()
    if p.date not in [x.isoformat() for x in open_dates(now.date())]: raise HTTPException(400, "변경할 수 없는 날짜")
    late = p.date == now.date().isoformat() and now.hour >= CUTOFF
    if late and not p.reason.strip(): raise HTTPException(422, "사유 필요")
    with conn() as c:
        r = c.q("SELECT status FROM meals WHERE member=? AND d=?", (p.member, p.date)).fetchone()
        old = r["status"] if r else "미정"
        if p.status == "미정": c.q("DELETE FROM meals WHERE member=? AND d=?", (p.member, p.date))
        else:
            c.q("INSERT INTO meals VALUES(?,?,?) ON CONFLICT(member,d) DO UPDATE SET status=excluded.status", (p.member, p.date, p.status))
        if late and old != p.status:
            c.q("INSERT INTO logs(at,member,d,old,new,reason) VALUES(?,?,?,?,?,?)",
                (now.strftime("%m-%d %H:%M"), p.member, p.date, old, p.status, p.reason.strip()))
        c.commit()
    return {"ok": True, "late": late}

@app.get("/api/logs")
def logs():
    with conn() as c:
        return c.q("SELECT at,member,d,old,new,reason FROM logs ORDER BY id DESC LIMIT 30").fetchall() and [dict(r) for r in c.q("SELECT at,member,d,old,new,reason FROM logs ORDER BY id DESC LIMIT 30").fetchall()] or []


class Price(BaseModel):
    price: int

@app.get("/api/price")
def get_price():
    with conn() as c:
        r = c.q("SELECT v FROM meta WHERE k='price'").fetchone()
    return {"price": int(r["v"]) if r else 0}

@app.put("/api/price")
def set_price(p: Price):
    if p.price < 0 or p.price > 10_000_000: raise HTTPException(400)
    with conn() as c:
        c.q("INSERT INTO meta VALUES('price',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (str(p.price),))
        c.commit()
    return {"ok": True}
