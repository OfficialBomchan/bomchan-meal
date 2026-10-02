[Uploading render.yaml…]()
services:
  - type: web
    name: bomchan-meal
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: "3.12.3"
      - key: DATABASE_URL   # 외부 무료 Postgres(Neon 등)의 연결 문자열 — 대시보드에서 직접 입력
        sync: false

# 쉬는 날(공휴일·대체공휴일) 목록. 토·일은 자동 제외되므로 평일에 해당하는 날만 적으면 된다.
# 임시공휴일(선거일 등)은 발표되면 직접 추가해야 한다. 파일을 수정해 GitHub에 올리면 자동 배포된다.
# 2026년 하반기~2027년까지 입력됨(자료마다 다른 항목은 맨 아래 주석 참고). 2028년 이후는 비어 있으니 연말에 추가할 것.
HOLIDAYS = {
    # 2026
    "2026-10-05": "개천절 대체공휴일",
    "2026-10-09": "한글날",
    "2026-12-25": "성탄절",
    # 2027
    "2027-01-01": "신정",
    "2027-02-08": "설 연휴",
    "2027-02-09": "설날 대체공휴일",
    "2027-03-01": "삼일절",
    "2027-05-03": "노동절 대체공휴일",  # 자료마다 다름: 노동절(5/1) 공휴일 지정 여부 확인 필요
    "2027-05-05": "어린이날",
    "2027-05-13": "부처님오신날",
    "2027-07-19": "제헌절 대체공휴일",
    "2027-08-16": "광복절 대체공휴일",
    "2027-09-14": "추석 연휴",
    "2027-09-15": "추석",
    "2027-09-16": "추석 연휴",
    "2027-10-04": "개천절 대체공휴일",
    "2027-10-11": "한글날 대체공휴일",
    "2027-12-27": "성탄절 대체공휴일",
}
# 참고: 2027-06-07(현충일 대체)은 자료마다 달라 넣지 않음. 2027 설날은 2/7(일)로 확인됨.

fastapi
uvicorn
psycopg2-binary

<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>봄찬 점심 체크</title>
<style>
:root{--g:#2e8b3d;--gd:#1f6b2c;--gl:#e8f5ea;--bg:#f4f9f4;--t:#1c2a1f;--m:#6b7a6e;--l:#d5e3d7;--r:#c0392b;--y:#b8860b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--t);font:16px/1.5 -apple-system,"Malgun Gothic",sans-serif}
.w{max-width:480px;margin:0 auto;padding:20px 16px 60px}.hide{display:none!important}
h1{font-size:28px;margin:8px 0}.sub{color:var(--m)}
.card{background:#fff;border:1px solid var(--l);border-radius:14px;padding:16px;margin:12px 0}
.btn{display:block;width:100%;padding:14px;border:0;border-radius:12px;background:var(--g);color:#fff;font-size:17px;font-weight:700;cursor:pointer}
.btn.o{background:#fff;color:var(--gd);border:1px solid var(--g)}
.names{display:grid;grid-template-columns:1fr 1fr;gap:10px}.names button{padding:18px;font-size:20px;font-weight:700;border:1px solid var(--l);background:#fff;border-radius:12px;cursor:pointer}
.names button:active{background:var(--gl)}
.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.chip{background:var(--gl);color:var(--gd);border-radius:99px;padding:2px 10px;font-size:13px;font-weight:700;margin-left:6px}
.link{background:none;border:0;color:var(--m);text-decoration:underline;cursor:pointer;font-size:14px}
.tabs{display:flex;border-bottom:1px solid var(--l);margin-bottom:10px}.tabs button{flex:1;padding:10px 0;background:none;border:0;border-bottom:3px solid transparent;color:var(--m);font-size:14px;font-weight:700;cursor:pointer}.tabs .on{color:var(--gd);border-color:var(--g)}
.nav{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.nav button{width:40px;height:40px;border-radius:10px;border:1px solid var(--l);background:#fff;color:var(--gd);font-size:18px;cursor:pointer}.nav button:disabled{opacity:.3}
.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:6px}.dow{text-align:center;color:var(--m);font-size:13px}
.c{aspect-ratio:1/1.05;border:1px solid var(--l);border-radius:10px;background:#fff;padding:4px;text-align:center;font-size:15px;font-weight:700}.c small{display:block;font-size:11px;font-weight:600}
.c.off{border:0;background:none}.c.ed{border:2px dashed var(--y);cursor:pointer}.c.eat{background:var(--g);color:#fff;border:2px solid var(--g)}.c.skip{background:#e6e9e6;color:var(--m);border:2px solid #e6e9e6}.c.pen{border-color:var(--r);color:var(--r)}
.c.ed.und{color:var(--y)}.c.sel{outline:3px solid var(--gd)}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{border-bottom:1px solid var(--l);padding:6px 2px;text-align:center}
.sheet{position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:flex-end;justify-content:center;z-index:9}
.sheet>div{background:#fff;width:100%;max-width:480px;padding:20px 16px 28px;border-radius:18px 18px 0 0}.sheet .btn{margin-top:8px}
textarea{width:100%;padding:10px;border:1px solid var(--l);border-radius:10px;font:inherit;margin:8px 0}
.c.chg{outline:3px solid var(--gd)}.row{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--l);font-size:14px}
.back{display:block;background:none;border:0;color:var(--gd);font-size:16px;font-weight:700;padding:6px 0 10px;cursor:pointer}
.warn{background:#fdecea;color:var(--r);padding:10px;border-radius:10px;font-weight:700;margin:8px 0}
.toast{position:fixed;left:16px;right:16px;bottom:20px;max-width:448px;margin:auto;background:var(--gd);color:#fff;padding:12px;border-radius:12px;z-index:20;font-weight:700}.toast.r{background:var(--r)}
</style></head><body><div class="w">

<div id="v1"><h1>봄찬 점심 체크</h1><p class="sub">봄찬 점심밥 인원을 위한 앱입니다.</p>
<div class="card"><b>이렇게 사용합니다</b><p>① 내 이름을 고릅니다.<br>② 달력에서 날짜를 눌러 먹음 / 안먹음을 선택합니다.<br>③ 오늘부터 근무일 5일 뒤까지 미리 선택할 수 있습니다.</p>
<p><b>당일 08:00까지 미정이면 패널티 +1</b>, 08:00 이후 변경은 사유 입력과 담당자께 구두 공유가 필요합니다.</p></div>
<button class="btn" onclick="go(2)">다음</button><button class="btn o" style="margin-top:10px" onclick="openCost()">식대 관리</button></div>

<div id="v2" class="hide"><button class="back" onclick="go(1)">← 뒤로</button><h1>누구세요?</h1><p class="sub">본인 이름을 선택하세요.</p><div class="names" id="names"></div></div>

<div id="v3" class="hide">
<button class="back" onclick="go(2)">← 뒤로</button>
<div class="top"><div><b id="me" style="font-size:20px"></b> 님<span class="chip" id="pen"></span></div><button class="link" onclick="go(2)">이름 변경</button></div>
<div class="tabs" id="tabs"></div>
<div id="t0"><div class="nav"><button id="pv" onclick="mv(-1)">◀</button><b id="ym" style="font-size:18px"></b><button id="nx" onclick="mv(1)">▶</button></div>
<div class="grid" id="dow"></div><div class="grid" id="cal" style="margin-top:6px"></div>
<p class="sub" style="font-size:13px">점선 날짜를 누르면 미정 → 먹음 → 안먹음 순서로 바뀝니다. 다 고른 뒤 아래 <b>저장하기</b>를 눌러야 반영됩니다.</p><p id="dn" class="sub" style="font-size:13px;margin:0"></p><button class="btn" id="sv" onclick="save()" style="margin-top:10px">저장하기</button></div>
<div id="t1" class="hide card"></div><div id="t2" class="hide"></div><div id="t3" class="hide card"></div>
</div></div>

<div id="v4" class="hide"><button class="back" onclick="go(1)">← 뒤로</button><div class="top"><b style="font-size:22px">식대 관리</b></div>
<div class="card"><b>1식 단가(원)</b><div style="display:flex;gap:8px;margin-top:8px"><input id="pr" type="number" inputmode="numeric" style="flex:1;padding:12px;border:1px solid var(--l);border-radius:10px;font:inherit"><button class="btn" style="width:90px" onclick="savePrice()">저장</button></div><p class="sub" style="font-size:13px;margin:8px 0 0">결제 금액 = 월 식수(먹음) × 단가</p></div><div id="cost"></div></div>
<div id="sh" class="sheet hide" onclick="if(event.target===this)cl()"><div id="shb"></div></div>
<div id="ts" class="toast hide"></div>

<script>
const $=id=>document.getElementById(id);const ST=["먹음","미정","안먹음"];
const NAMES=["JH","PH","SH","BK","DJ","MW","TS","HS","HM","JS"];
let draft={},savedMap={};
let S=null,me=null,Y,M,tab=0,D=null;
async function api(u,o){const r=await fetch(u,o);if(!r.ok){const e=new Error(r.status);e.s=r.status;throw e}return r.json()}
function go(n){["v1","v2","v3","v4"].forEach((v,i)=>$(v).classList.toggle("hide",i+1!==n));if(n==3)load()}
function toast(t,r){const e=$("ts");e.textContent=t;e.className="toast"+(r?" r":"");setTimeout(()=>e.classList.add("hide"),r?6000:1800)}
async function init(){
 $("names").innerHTML=NAMES.map(m=>`<button onclick="pick('${m}')">${m}</button>`).join("");
 $("dow").innerHTML=["월","화","수","목","금"].map(x=>`<div class="dow">${x}</div>`).join("");
 $("tabs").innerHTML=["내 달력","전체 현황","월별 식수","변경 내역"].map((x,i)=>`<button onclick="tb(${i})" id="tb${i}">${x}</button>`).join("");
 try{S=await api("/api/state");const t=S.today.split("-");Y=+t[0];M=+t[1]}catch(e){}}
async function pick(m){me=m;draft={};savedMap={};try{localStorage.setItem("me",m)}catch(e){}if(!S){try{S=await api("/api/state")}catch(e){toast("서버에 연결할 수 없습니다",1);return}}const t=S.today.split("-");Y=+t[0];M=+t[1];tab=0;go(3)}
function tb(i){tab=i;load()}
async function load(){S=await api("/api/state");$("me").textContent=me;$("pen").textContent="패널티 "+S.penalties[me]+"회";
 for(let i=0;i<4;i++){$("t"+i).classList.toggle("hide",i!==tab);$("tb"+i).classList.toggle("on",i===tab)}
 if(tab==0)await cal();if(tab==1)await all();if(tab==2)await mon();if(tab==3)await lg()}
const p2=n=>String(n).padStart(2,"0");
async function cal(){const ym=Y+"-"+p2(M);D=await api("/api/month?ym="+ym+"&member="+me);draw()}
function draw(){const ym=Y+"-"+p2(M);
 $("ym").textContent=Y+"년 "+M+"월";const st=S.start.slice(0,7),last=S.open[S.open.length-1].slice(0,7);
 $("pv").disabled=ym<=st;$("nx").disabled=ym>="2027-12";
 const n=new Date(Y,M,0).getDate();let h="";let first=true;
 for(let d=1;d<=n;d++){const w=new Date(Y,M-1,d).getDay();if(w==0||w==6)continue;
  const ds=ym+"-"+p2(d);if(first){h+='<div></div>'.repeat(w-1);first=false}
  if(D.off.includes(ds)){h+='<div class="c off"></div>';continue}
  const ed=S.open.includes(ds);if(ed)savedMap[ds]=D.status[ds]||"미정";
  const s=ed?(draft[ds]??savedMap[ds]):D.status[ds];let c="c",sub="";
  if(s=="먹음"){c+=" eat";sub="먹음"}else if(s=="안먹음"){c+=" skip";sub="안먹음"}
  else if(ed){c+=" und";sub="미정"}else if(D.penalty.includes(ds)){c+=" pen";sub="패널티"}
  if(ed)c+=" ed";if(ed&&ds in draft)c+=" chg";
  h+=`<div class="${c}" ${ed?`onclick="cyc('${ds}')"`:""}>${d}<small>${sub}</small></div>`}
 $("cal").innerHTML=h;upd()}
function mv(k){M+=k;if(M>12){M=1;Y++}if(M<1){M=12;Y--}cal()}
function cl(){$("sh").classList.add("hide")}
function cyc(ds){const cur=draft[ds]??savedMap[ds]??"미정";const CY=["미정","먹음","안먹음"];const nx=CY[(CY.indexOf(cur)+1)%3];if(nx===(savedMap[ds]??"미정"))delete draft[ds];else draft[ds]=nx;draw()}
function upd(){const n=Object.keys(draft).length;$("sv").disabled=!n;$("sv").style.opacity=n?1:.4;$("sv").textContent=n?`저장하기 (${n}건)`:"저장하기";$("dn").textContent=n?"아직 저장되지 않았습니다.":""}
async function save(){const ks=Object.keys(draft);if(!ks.length)return;let reason="";
 if(ks.includes(S.today)&&S.hour>=8){reason=await ask();if(reason===null)return}
 let late=false;try{for(const ds of ks){const r=await api("/api/meal",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({member:me,date:ds,status:draft[ds],reason:ds===S.today?reason:""})});if(r.late)late=true}
  draft={};savedMap={};load();done(late)}
 catch(e){toast("저장 실패: 일부만 저장됐을 수 있습니다",1);draft={};savedMap={};load()}}
function done(late){$("shb").innerHTML=`<div style="text-align:center;padding:8px 0 4px"><div style="font-size:40px;color:var(--g)">✓</div><b style="font-size:20px">선택이 완료되었습니다</b>${late?'<div class="warn" style="margin-top:12px">08:00 이후 변경입니다.<br>담당자께 반드시 구두로 공유하세요.</div>':""}</div><button class="btn" onclick="cl()">확인</button>`;$("sh").classList.remove("hide")}
function ask(){return new Promise(res=>{$("shb").innerHTML=`<div class="warn">08:00이 지났습니다. 변경 사유를 입력하세요.<br>담당자께 반드시 구두로 공유해야 합니다.</div><textarea id="rs" rows="3" placeholder="사유"></textarea><button class="btn" id="ok">확인</button><button class="btn o" id="no">취소</button>`;
 $("sh").classList.remove("hide");$("no").onclick=()=>{cl();res(null)};$("ok").onclick=()=>{const v=$("rs").value.trim();if(!v){$("rs").focus();return}cl();res(v)}})}
async function all(){const a=await api("/api/all");const ic={"먹음":"●","안먹음":"×"};
 $("t1").innerHTML="<table><tr><th></th>"+a.days.map(d=>`<th>${+d.slice(5,7)}/${+d.slice(8)}</th>`).join("")+"<th>패널티</th></tr>"+
 NAMES.map(m=>`<tr><td><b>${m}</b></td>`+a.days.map(d=>`<td>${ic[a.table[m][d]]||"·"}</td>`).join("")+`<td>${S.penalties[m]}</td></tr>`).join("")+
 "<tr><td><b>먹음</b></td>"+a.days.map(d=>`<td><b>${NAMES.filter(m=>a.table[m][d]=="먹음").length}</b></td>`).join("")+"<td></td></tr></table><p class='sub' style='font-size:12px'>● 먹음 × 안먹음 · 미정</p>"}
async function mon(){const a=await api("/api/monthly");
 $("t2").innerHTML=a.months.length?a.months.map(m=>`<div class="card"><b>${m.ym}</b> ${m.ym==a.now?"(진행 중)":""}<div style="font-size:26px;font-weight:800;color:var(--gd)">${m.total}식 ${m.diff==null?"":`<span style="font-size:14px;color:var(--m)">전월 대비 ${m.diff>0?"+":""}${m.diff}</span>`}</div><div class="sub" style="font-size:13px">${Object.entries(m.by).map(([k,v])=>k+" "+v).join(" · ")}</div></div>`).join(""):'<div class="card sub">아직 기록이 없습니다.</div>'}
async function lg(){const a=await api("/api/logs");$("t3").innerHTML=a.length?a.map(x=>`<div style="padding:6px 0;border-bottom:1px solid var(--l)"><b>${x.member}</b> ${x.d.slice(5)} ${x.old}→${x.new}<div class="sub" style="font-size:13px">${x.at} · ${x.reason}</div></div>`).join(""):'<span class="sub">08:00 이후 변경 기록이 없습니다.</span>'}
async function openCost(){go(4);if(!S)try{S=await api("/api/state")}catch(e){}
 const p=await api("/api/price");$("pr").value=p.price||"";renderCost(p.price||0)}
async function savePrice(){const v=parseInt($("pr").value||"0");await api("/api/price",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({price:v})});toast("단가 저장됨");renderCost(v)}
let CY_=2026,CM_=10,CP=0,CA=null;
function monOpts(y){const f=y==2026?10:1;let h="";for(let m=f;m<=12;m++)h+=`<option value="${m}"${m==CM_?" selected":""}>${m}월</option>`;return h}
async function renderCost(price){CP=price;CA=await api("/api/monthly");
 const now=CA.now.split("-").map(Number);if(now[0]*100+now[1]>=202610&&now[0]*100+now[1]<=202712){CY_=now[0];CM_=now[1]}
 $("cost").innerHTML=`<div class="card"><div style="display:flex;gap:8px;margin-bottom:12px"><select id="cy" onchange="cyChg()" style="flex:1;padding:12px;border:1px solid var(--l);border-radius:10px;font:inherit;background:#fff"><option value="2026"${CY_==2026?" selected":""}>2026년</option><option value="2027"${CY_==2027?" selected":""}>2027년</option></select><select id="cm" onchange="cmChg()" style="flex:1;padding:12px;border:1px solid var(--l);border-radius:10px;font:inherit;background:#fff">${monOpts(CY_)}</select></div><div id="cr"></div></div>`;showCost()}
function cyChg(){CY_=+$("cy").value;CM_=CY_==2026?Math.max(CM_,10):CM_;$("cm").innerHTML=monOpts(CY_);showCost()}
function cmChg(){CM_=+$("cm").value;showCost()}
function showCost(){const ym=CY_+"-"+p2(CM_);const m=(CA.months.find(x=>x.ym==ym))||{total:0};const w=n=>n.toLocaleString("ko-KR")+"원";
 $("cr").innerHTML=`<b>월별 총 식대</b><div style="font-size:28px;font-weight:800;color:var(--gd);margin-top:4px">${CP?w(m.total*CP):"단가 입력 필요"}</div><div class="sub" style="font-size:14px">${CY_}년 ${CM_}월 · 총 ${m.total}식${CP?" × "+w(CP):""}</div>`}
init().then(()=>{go(1)});
setInterval(()=>{if(!$("v3").classList.contains("hide")&&$("sh").classList.contains("hide"))load()},60000);
</script></div></body></html>

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
