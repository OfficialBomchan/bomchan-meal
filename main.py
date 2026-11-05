import asyncio, bisect, os, re, sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone, date
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from kr_holidays import HOLIDAYS

MEMBERS = ["JH","PH","SH","BK","DJ","MW","TS","HS","HM","JS","헬퍼1","헬퍼2","헬퍼3"]
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
        # 퇴사/신입 반영용. active=0 은 숨기기만 할 뿐 meals/penalties 기록은 그대로 남긴다(월별 정산이 깨지면 안 돼서).
        c.q(f"CREATE TABLE IF NOT EXISTS members(id {ai}, name TEXT UNIQUE NOT NULL, active INTEGER NOT NULL DEFAULT 1)")
        for m in MEMBERS:
            c.q("INSERT INTO members(name,active) VALUES(?,1) ON CONFLICT(name) DO NOTHING", (m,))
        # 단가가 월 중간에도 바뀔 수 있어서(업체 변경 등, 11/3) 날짜 단위로 저장한다. 특정 날짜엔 그 날짜 이전
        # 가장 가까운 행의 단가가 적용되고, 그마저도 없으면(prices가 비어있던 옛날) meta 'price'(레거시 단일 단가)로 떨어진다.
        c.q("CREATE TABLE IF NOT EXISTS prices(d TEXT PRIMARY KEY, price INTEGER NOT NULL)")
        # 단체 외식일. 식대·패널티 계산에서 빠지고, 그날 개인별 체크는 잠긴다.
        c.q("CREATE TABLE IF NOT EXISTS eatout(d TEXT PRIMARY KEY)")
        c.q("INSERT INTO meta VALUES('admin_pin','0000') ON CONFLICT DO NOTHING")
        now = datetime.now(KST)
        c.q("INSERT INTO meta VALUES('start',?) ON CONFLICT DO NOTHING", (now.date().isoformat(),))
        st = c.q("SELECT v FROM meta WHERE k='start'").fetchone()["v"]
        if st == now.date().isoformat() and now.hour >= CUTOFF:
            c.q("INSERT INTO done VALUES(?) ON CONFLICT DO NOTHING", (st,))  # 시작일이 08:00 이후면 그날은 패널티 제외
        c.commit()

def active_names(c):
    return [r["name"] for r in c.q("SELECT name FROM members WHERE active=1 ORDER BY id").fetchall()]

def all_names(c):
    return {r["name"] for r in c.q("SELECT name FROM members").fetchall()}

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
        members = active_names(c)  # 퇴사자는 새 패널티가 안 쌓이게 활성 인원만 본다
        eo = {r["d"] for r in c.q("SELECT d FROM eatout").fetchall()}  # 외식일은 패널티 대상 제외
        d = start
        while d <= now.date():
            passed = d < now.date() or now.hour >= CUTOFF
            ds = d.isoformat()
            if passed and workday(d):
                cur = c.q("INSERT INTO done VALUES(?) ON CONFLICT DO NOTHING", (ds,))
                if cur.rowcount == 1 and ds not in eo:
                    got = {r["member"] for r in c.q("SELECT member FROM meals WHERE d=? AND status IN ('먹음','안먹음')", (ds,)).fetchall()}
                    for m in members:
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
        members = active_names(c)
        pen = {m: 0 for m in members}
        for r in c.q("SELECT member, COUNT(*) n FROM penalties GROUP BY member").fetchall():
            if r["member"] in pen: pen[r["member"]] = r["n"]
        start = c.q("SELECT v FROM meta WHERE k='start'").fetchone()["v"]
    return {"today": now.date().isoformat(), "hour": now.hour, "members": members, "penalties": pen, "start": start,
            "open": [x.isoformat() for x in open_dates(now.date())]}

def nxt(ym):
    y, m = map(int, ym.split("-")); return f"{y+1}-01" if m == 12 else f"{y}-{m+1:02d}"

@app.get("/api/month")
def month(ym: str, member: str):
    with conn() as c0:
        names = all_names(c0)  # 퇴사자 과거 기록도 조회는 되게 활성 여부 안 가린다
    if member not in names or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", ym): raise HTTPException(400)
    snapshot(); a, b = ym + "-01", nxt(ym) + "-01"
    with conn() as c:
        st = {r["d"]: r["status"] for r in c.q("SELECT d,status FROM meals WHERE member=? AND d>=? AND d<?", (member, a, b)).fetchall()}
        pn = [r["d"] for r in c.q("SELECT d FROM penalties WHERE member=? AND d>=? AND d<?", (member, a, b)).fetchall()]
        eo = [r["d"] for r in c.q("SELECT d FROM eatout WHERE d>=? AND d<?", (a, b)).fetchall()]
    return {"ym": ym, "status": st, "penalty": pn, "off": sorted(d for d in HOLIDAYS if d.startswith(ym)), "eatout": eo}

@app.get("/api/all")
def allv():
    snapshot(); days = [x.isoformat() for x in open_dates(now_kst().date())]
    with conn() as c:
        members = active_names(c)
        rows = c.q("SELECT member,d,status FROM meals WHERE d>=? AND d<=?", (days[0], days[-1])).fetchall() if days else []
        eo = [r["d"] for r in c.q("SELECT d FROM eatout WHERE d>=? AND d<=?", (days[0], days[-1])).fetchall()] if days else []
    t = {m: {} for m in members}
    for r in rows:
        if r["member"] in t: t[r["member"]][r["d"]] = r["status"]
    return {"days": days, "table": t, "eatout": eo}

@app.get("/api/monthly")
def monthly():
    with conn() as c:
        meal_rows = c.q("SELECT d, member FROM meals WHERE status='먹음' ORDER BY d").fetchall()
        price_rows = c.q("SELECT d, price FROM prices ORDER BY d").fetchall()
        legacy = c.q("SELECT v FROM meta WHERE k='price'").fetchone()
        eo_rows = c.q("SELECT d FROM eatout").fetchall()
    legacy_price = int(legacy["v"]) if legacy else 0
    pds = [r["d"] for r in price_rows]; pps = [r["price"] for r in price_rows]
    def price_on(d):
        i = bisect.bisect_right(pds, d) - 1  # 그 날짜 이전(포함) 가장 가까운 단가
        return pps[i] if i >= 0 else legacy_price
    ms, ams = {}, {}  # ym -> {member: 식수} / ym -> {member: 금액}
    for r in meal_rows:
        d, m = r["d"], r["member"]; ym = d[:7]
        ms.setdefault(ym, {}); ms[ym][m] = ms[ym].get(m, 0) + 1
        ams.setdefault(ym, {}); ams[ym][m] = ams[ym].get(m, 0) + price_on(d)
    eo_counts = {}  # ym -> 외식 일수 (식수·식대 집계에는 안 들어감)
    for r in eo_rows:
        ym = r["d"][:7]; eo_counts[ym] = eo_counts.get(ym, 0) + 1
    out, prev = [], None
    for ym in sorted(set(ms) | set(eo_counts)):
        tot = sum(ms.get(ym, {}).values())
        out.append({"ym": ym, "total": tot, "by": ms.get(ym, {}), "amount": sum(ams.get(ym, {}).values()), "by_amount": ams.get(ym, {}),
                     "eatout": eo_counts.get(ym, 0),
                     "diff": None if prev is None else tot - prev}); prev = tot
    return {"months": out[::-1], "now": now_kst().strftime("%Y-%m")}

class Put(BaseModel):
    member: str; date: str; status: str; reason: str = ""

@app.put("/api/meal")
def put(p: Put):
    with conn() as c0:
        active = set(active_names(c0))  # 퇴사자는 더 이상 체크를 못 하게 막는다
    if p.member not in active or p.status not in STATUSES: raise HTTPException(400, "잘못된 값")
    snapshot(); now = now_kst()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.date): raise HTTPException(400, "잘못된 날짜")
    with conn() as c0:
        start = c0.q("SELECT v FROM meta WHERE k='start'").fetchone()["v"]
    today = now.date().isoformat()
    try: dd = datetime.strptime(p.date, "%Y-%m-%d").date()
    except ValueError: raise HTTPException(400, "잘못된 날짜")
    past = start <= p.date < today and workday(dd)
    if p.date not in [x.isoformat() for x in open_dates(now.date())] and not past:
        raise HTTPException(400, "변경할 수 없는 날짜")
    late = past or (p.date == today and now.hour >= CUTOFF)
    if late and not p.reason.strip(): raise HTTPException(422, "사유 필요")
    with conn() as c0:
        if c0.q("SELECT 1 FROM eatout WHERE d=?", (p.date,)).fetchone(): raise HTTPException(400, "외식으로 표시된 날짜입니다")
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


def effective_price(c, d):
    r = c.q("SELECT price FROM prices WHERE d<=? ORDER BY d DESC LIMIT 1", (d,)).fetchone()
    if r: return r["price"]
    r = c.q("SELECT v FROM meta WHERE k='price'").fetchone()  # prices에 아직 아무 값도 없던 날짜(레거시)
    return int(r["v"]) if r else 0

class Price(BaseModel):
    d: str; price: int

@app.get("/api/price")
def get_price(d: str = None):
    if d is None: d = now_kst().date().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d): raise HTTPException(400)
    with conn() as c:
        price = effective_price(c, d)
    return {"d": d, "price": price}

@app.put("/api/price")
def set_price(p: Price):
    if p.price < 0 or p.price > 10_000_000: raise HTTPException(400)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.d): raise HTTPException(400, "잘못된 날짜")
    with conn() as c:
        c.q("INSERT INTO prices VALUES(?,?) ON CONFLICT(d) DO UPDATE SET price=excluded.price", (p.d, p.price))
        c.commit()
    return {"ok": True}


class Eatout(BaseModel):
    d: str; pin: str; on: bool = True

@app.put("/api/eatout")
def set_eatout(p: Eatout):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.d): raise HTTPException(400, "잘못된 날짜")
    with conn() as c0:
        check_pin(p.pin, c0)
    if p.d not in [x.isoformat() for x in open_dates(now_kst().date())]:
        raise HTTPException(400, "지정할 수 없는 날짜")
    with conn() as c:
        if p.on:
            c.q("INSERT INTO eatout VALUES(?) ON CONFLICT(d) DO NOTHING", (p.d,))
            c.q("DELETE FROM meals WHERE d=?", (p.d,))
            c.q("DELETE FROM penalties WHERE d=?", (p.d,))
        else:
            c.q("DELETE FROM eatout WHERE d=?", (p.d,))
        c.commit()
    return {"ok": True}

def check_pin(pin, c):
    r = c.q("SELECT v FROM meta WHERE k='admin_pin'").fetchone()
    real = r["v"] if r else "0000"
    if pin != real: raise HTTPException(403, "PIN이 틀렸습니다")

class MemberAdd(BaseModel):
    name: str; pin: str

class MemberToggle(BaseModel):
    active: bool; pin: str

@app.get("/api/members")
def list_members():
    with conn() as c:
        rows = c.q("SELECT name, active FROM members ORDER BY id").fetchall()
    return [{"name": r["name"], "active": bool(r["active"])} for r in rows]

@app.post("/api/members")
def add_member(p: MemberAdd):
    name = p.name.strip()
    if not name or len(name) > 10: raise HTTPException(400, "이름을 확인하세요")
    with conn() as c:
        check_pin(p.pin, c)
        if c.q("SELECT 1 FROM members WHERE name=?", (name,)).fetchone():
            c.q("UPDATE members SET active=1 WHERE name=?", (name,))  # 이미 있던 이름이면 재입사로 보고 되살린다
        else:
            c.q("INSERT INTO members(name,active) VALUES(?,1)", (name,))
        c.commit()
    return {"ok": True}

@app.put("/api/members/{name}")
def toggle_member(name: str, p: MemberToggle):
    with conn() as c:
        check_pin(p.pin, c)
        if not c.q("SELECT 1 FROM members WHERE name=?", (name,)).fetchone(): raise HTTPException(404, "없는 사람입니다")
        c.q("UPDATE members SET active=? WHERE name=?", (1 if p.active else 0, name))
        c.commit()
    return {"ok": True}
