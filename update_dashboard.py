#!/usr/bin/env python3
"""mybox Dashboard Auto-Updater"""

import json
import os
import re
import urllib.request
from datetime import datetime, timezone, timedelta

API_URL = os.environ.get("MYBOX_API_URL", "https://137-184-128-215.sslip.io/api/public/boxmap")
API_TOKEN = os.environ.get("MYBOX_PUBLIC_TOKEN", "")

# Бокси, у яких на схемі index.html номер не 5-значний: ID на схемі → інвентарний номер у «Схемах»/CRM
ALIASES = {"В-4": 46149}
MANUAL_RESERVED = ["В-4"]  # на «Схемах» В-4-46149 білий; прибрати, коли зафарбують жовтим


def map_box_ids():
    """Інвентарний номер (5 цифр) → ID боксу так, як він записаний на схемі в index.html.
    Зіставлення по номеру прибирає проблему латиниця/кирилиця і аліаси типу «Р-15»."""
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    ids = {}
    for box_id in re.findall(r'"id":"([^"]+)"', html):
        clean = box_id.replace(" Резерв", "")
        m = re.search(r"-(\d{5})$", clean)
        m3 = re.search(r"^P-[\d,.]+-(\d{3})$", clean)  # P-1,5-135 → 46135
        if m:
            ids[int(m.group(1))] = box_id
        elif m3:
            ids[46000 + int(m3.group(1))] = box_id
    for box_id, num in ALIASES.items():
        ids.setdefault(num, box_id)
    return ids


def fetch_statuses():
    """Статуси боксів з сервера MYBOX: «орендовано» = активний договір в OneBox CRM,
    «резерв» = жовтий колір на схемі. Імена орендарів НЕ передаються."""
    if not API_TOKEN:
        raise RuntimeError("немає MYBOX_PUBLIC_TOKEN (GitHub → Settings → Secrets)")
    req = urllib.request.Request(API_URL, headers={"X-Token": API_TOKEN, "User-Agent": "mybox-bot/2.0"})
    data = json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
    boxes = data.get("boxes") or []
    if len(boxes) < 100:
        raise RuntimeError("сервер повернув замало боксів: {}".format(len(boxes)))
    ids = map_box_ids()
    tenants, reserved, missing = {}, {}, []
    for b in boxes:
        box_id = ids.get(int(b["num"]))
        if not box_id:
            missing.append(b["code"])
            continue
        if b["status"] == "rented":
            tenants[box_id] = "Орендовано"
        elif b["status"] == "reserve":
            reserved[box_id] = True
    for rb in MANUAL_RESERVED:
        if rb not in tenants:
            reserved[rb] = True
    if missing:
        print("Немає на схемі index.html: " + ", ".join(missing))
    print("Сервер {}: орендовано {}, резерв {}".format(data.get("generated"), len(tenants), len(reserved)))
    return tenants, reserved


def build_html(tenants, reserved, update_time):
    # Read the current index.html to extract CSS and boxes
    with open("index.html", "r", encoding="utf-8") as f:
        current = f.read()

    import re
    css_match = re.search(r'<style>(.*?)</style>', current, re.DOTALL)
    css = css_match.group(1) if css_match else ""

    m01_match = re.search(r'm01:\{label:"[^"]*",vw:980,vh:530,boxes:(\[.*?\])\}', current, re.DOTALL)
    m02_match = re.search(r'm02:\{label:"[^"]*",vw:1020,vh:510,boxes:(\[.*?\])\}', current, re.DOTALL)
    m03_match = re.search(r'm03:\{label:"[^"]*",vw:980,vh:540,boxes:(\[.*?\])\}', current, re.DOTALL)

    boxes_m01 = m01_match.group(1) if m01_match else "[]"
    boxes_m02 = m02_match.group(1) if m02_match else "[]"
    boxes_m03 = m03_match.group(1) if m03_match else "[]"

    # Get logo from current file
    logo_match = re.search(r'src="data:image/jpeg;base64,([^"]+)"', current)
    logo = logo_match.group(1) if logo_match else ""

    count = len(tenants)
    tj = json.dumps(tenants, ensure_ascii=False)

    lines = []
    lines.append("<!DOCTYPE html>")
    lines.append('<html lang="uk">')
    lines.append("<head>")
    lines.append('<meta charset="UTF-8"/>')
    lines.append('<meta name="viewport" content="width=device-width, initial-scale=1.0"/>')
    lines.append("<title>mybox — Дашборд-план</title>")
    lines.append("<style>" + css + "</style>")
    lines.append("</head>")
    lines.append("<body>")
    lines.append('<div class="app">')
    lines.append('<div class="top">')
    lines.append('<div class="top-left">')
    lines.append('<img class="logo-img" src="data:image/jpeg;base64,' + logo + '" alt="mybox"/>')
    lines.append('<div class="logo-text">my<em>box</em> — Дашборд-план</div>')
    lines.append("</div>")
    lines.append('<div class="top-right">')
    lines.append('<div class="date-badge" id="datebadge"></div>')
    lines.append('<div class="sync-info">✓ Оновлено ' + update_time + ' · ' + str(count) + ' орендованих боксів · дані OneBox CRM</div>')
    lines.append("</div></div>")
    lines.append('<div class="section-title">Загальна статистика — кількість боксів</div>')
    lines.append('<div class="total-grid" id="total-count"></div>')
    lines.append('<hr class="section-sep"/>')
    lines.append('<div class="section-title">Загальна статистика — площа боксів, кв.м.</div>')
    lines.append('<div class="total-grid-sq" id="total-area"></div>')
    lines.append('<hr class="section-sep"/>')
    lines.append('<div class="section-title">По локаціях</div>')
    lines.append('<div class="loc-stats" id="loc-stats"></div>')
    lines.append('<div class="tabs">')
    lines.append('<button class="tab active" onclick="switchTab(\'m01\',this)">М-01</button>')
    lines.append('<button class="tab" onclick="switchTab(\'m02\',this)">М-02</button>')
    lines.append('<button class="tab" onclick="switchTab(\'m03\',this)">М-03</button>')
    lines.append("</div>")
    lines.append('<div class="tab-bar" id="tab-bar"></div>')
    lines.append('<div class="legend">')
    lines.append('<div class="li"><div class="ld" style="background:#f0ece4;border:1px solid #c8c3b8"></div>Вільний</div>')
    lines.append('<div class="li"><div class="ld" style="background:#F7C1C1;border:1px solid #E24B4A"></div>Орендовано</div>')
    lines.append('<div class="li"><div class="ld" style="background:#FAC775;border:1px solid #BA7517"></div>Резерв</div>')
    lines.append('<div class="li"><div class="ld" style="background:#D3D1C7;border:1px solid #888780"></div>Службове</div>')
    lines.append("</div>")
    lines.append('<div class="plan-wrap" id="plan-wrap">')
    lines.append('<div id="plan-inner"></div>')
    lines.append('<div class="tooltip" id="tt"><div class="tt-id" id="tt-id"></div><div class="tt-area" id="tt-area"></div><div class="tt-badge" id="tt-badge"></div><div class="tt-name" id="tt-name"></div></div>')
    lines.append("</div>")
    lines.append("<footer>mybox.ua &copy; 2026 &middot; Автооновлення щодня о 20:00</footer>")
    lines.append("</div>")

    js = r"""<script>
const TENANTS=__TENANTS__;
const RESERVED=__RESERVED__;
const DATA={m01:{label:"М-01 (вул. Березова 46)",vw:980,vh:530,boxes:__M01__},m02:{label:"М-02",vw:1020,vh:510,boxes:__M02__},m03:{label:"М-03",vw:980,vh:540,boxes:__M03__}};
let currentTab='m01';
function parseArea(id){const c=id.replace(' Резерв','');const m1=c.match(/^[А-ЯҐЄІЇa-zA-Z]+-(\d+[,.]\d+)-\d{2,5}$/i);if(m1)return parseFloat(m1[1].replace(',','.'));const m2=c.match(/^[А-ЯҐЄІЇa-zA-Z]+-(\d+)-\d{2,5}$/i);if(m2)return parseFloat(m2[1]);const m3=c.match(/^[А-ЯҐЄІЇa-zA-Z]+-(\d+[,.]?\d*)$/i);if(m3)return parseFloat(m3[1].replace(',','.'));return 0;}
function sts(id){return TENANTS[id]?'occupied':RESERVED[id]?'reserved':'free';}
function fc(id,svc){if(svc)return{bg:'#D3D1C7',st:'#888780',tx:'#5F5E5A'};const s=sts(id);if(s==='occupied')return{bg:'#FCEBEB',st:'#E24B4A',tx:'#791F1F'};if(s==='reserved')return{bg:'#FAEEDA',st:'#BA7517',tx:'#633806'};return{bg:'#f0ece4',st:'#b8b2a6',tx:'#5F5E5A'};}
function shortLabel(id){const svc=['OFFICE','WC','ДУШ','СХОДИ','ВХІД','ENTER'];if(svc.includes(id))return id;const c=id.replace(' Резерв','');const m=c.match(/^(.+?)-(\d{5})$/);if(m)return m[1]+'\\n'+m[2].slice(-3);const m2=c.match(/^(.+?)-(\d{2,4})$/);if(m2)return m2[1]+'\\n'+m2[2];return c.length>10?c.slice(0,10):c;}
function fmt(n){return Number.isInteger(n)?n:n.toFixed(1);}
function calcStats(key){const d=DATA[key];let total=0,occ=0,res=0,free=0,sqT=0,sqO=0,sqR=0,sqF=0;d.boxes.forEach(b=>{if(b.svc)return;total++;const s=sts(b.id),sq=parseArea(b.id);sqT=Math.round((sqT+sq)*10)/10;if(s==='occupied'){occ++;sqO=Math.round((sqO+sq)*10)/10;}else if(s==='reserved'){res++;sqR=Math.round((sqR+sq)*10)/10;}else{free++;sqF=Math.round((sqF+sq)*10)/10;}});return{total,occ,res,free,pct:total?Math.round(occ/total*100):0,sqT,sqO,sqR,sqF,sqPct:sqT?Math.round(sqO/sqT*100):0};}
function renderTotalCount(){let t=0,o=0,r=0,f=0;['m01','m02','m03'].forEach(k=>{const s=calcStats(k);t+=s.total;o+=s.occ;r+=s.res;f+=s.free;});const pct=Math.round(o/t*100);document.getElementById('total-count').innerHTML=`<div class="tstat"><div class="tstat-l">Всього боксів</div><div class="tstat-v">${t}</div></div><div class="tstat"><div class="tstat-l">Орендовано</div><div class="tstat-v red">${o}</div></div><div class="tstat"><div class="tstat-l">Вільних</div><div class="tstat-v grn">${f}</div></div><div class="tstat"><div class="tstat-l">Заповненість %</div><div class="tstat-v amb">${pct}%<div class="fill-bar"><div class="fill-bar-inner" style="width:${pct}%"></div></div></div></div>`;}
function renderTotalArea(){let sqT=0,sqO=0,sqR=0,sqF=0;['m01','m02','m03'].forEach(k=>{const s=calcStats(k);sqT=Math.round((sqT+s.sqT)*10)/10;sqO=Math.round((sqO+s.sqO)*10)/10;sqR=Math.round((sqR+s.sqR)*10)/10;sqF=Math.round((sqF+s.sqF)*10)/10;});const sqPct=sqT?Math.round(sqO/sqT*100):0;document.getElementById('total-area').innerHTML=`<div class="tstat"><div class="tstat-l">Всього площа</div><div class="tstat-v">${fmt(sqT)} <span style="font-size:13px;font-weight:400;color:#aaa">кв.м</span></div></div><div class="tstat"><div class="tstat-l">Орендовано кв.м</div><div class="tstat-v red">${fmt(sqO)}</div></div><div class="tstat"><div class="tstat-l">Вільних кв.м</div><div class="tstat-v grn">${fmt(sqF)}</div></div><div class="tstat"><div class="tstat-l">Резерв кв.м</div><div class="tstat-v amb">${fmt(sqR)}</div></div><div class="tstat"><div class="tstat-l">Заповненість кв.м %</div><div class="tstat-v blue">${sqPct}%<div class="fill-bar"><div class="fill-bar-inner" style="width:${sqPct}%;background:#1a6fb5"></div></div></div></div>`;}
function renderLocStats(){document.getElementById('loc-stats').innerHTML=['m01','m02','m03'].map(k=>{const s=calcStats(k);const d=DATA[k];return`<div class="lstat"><div class="lstat-hdr"><span class="lstat-name">${d.label}</span><span class="lstat-pct">${s.sqPct}%</span></div><div class="lstat-row"><span>Боксів всього</span><span>${s.total}</span></div><div class="lstat-row"><span>Орендовано</span><span class="red">${s.occ}</span></div><div class="lstat-row"><span>Вільних</span><span class="grn">${s.free}</span></div><div class="lstat-row"><span>Резерв</span><span class="amb">${s.res}</span></div><hr class="lstat-divider"/><div class="lstat-row"><span>Площа всього</span><span>${fmt(s.sqT)} кв.м</span></div><div class="lstat-row"><span>Орендовано кв.м</span><span class="red">${fmt(s.sqO)}</span></div><div class="lstat-row"><span>Вільних кв.м</span><span class="grn">${fmt(s.sqF)}</span></div><div class="lstat-row"><span>Резерв кв.м</span><span class="amb">${fmt(s.sqR)}</span></div><div class="lstat-bar"><div class="lstat-bar-inner" style="width:${s.sqPct}%"></div></div></div>`;}).join('');}
function renderTabBar(key){const s=calcStats(key);const d=DATA[key];document.getElementById('tab-bar').innerHTML=`<strong>${d.label}</strong><span class="sep">·</span>Орендовано: <strong class="red">${s.occ} (${fmt(s.sqO)} кв.м)</strong><span class="sep">·</span>Вільних: <strong class="grn">${s.free} (${fmt(s.sqF)} кв.м)</strong><span class="sep">·</span>Заповненість: <strong class="amb">${s.pct}% / ${s.sqPct}% площі</strong>`;}
const tt=document.getElementById('tt');const pw=document.getElementById('plan-wrap');
function showTT(e,id){const sq=parseArea(id);document.getElementById('tt-id').textContent=id.replace(' Резерв','');document.getElementById('tt-area').textContent=sq>0?`Площа: ${fmt(sq)} кв.м`:'';const b=document.getElementById('tt-badge');const s=sts(id);b.textContent=s==='occupied'?'Орендовано':s==='reserved'?'Резерв':'Вільний';b.className='tt-badge '+s;document.getElementById('tt-name').textContent=TENANTS[id]||'';tt.style.display='block';moveTT(e);}
function moveTT(e){const rc=pw.getBoundingClientRect();let lx=e.clientX-rc.left+14,ly=e.clientY-rc.top+14;if(lx+250>rc.width)lx-=264;if(ly+100>rc.height)ly-=110;tt.style.left=lx+'px';tt.style.top=ly+'px';}
function hideTT(){tt.style.display='none';}
function buildSVG(key){const d=DATA[key];const S=document.createElementNS('http://www.w3.org/2000/svg','svg');S.setAttribute('viewBox',`0 0 ${d.vw} ${d.vh}`);S.style.cssText='display:block;width:100%;height:auto';const br=document.createElementNS('http://www.w3.org/2000/svg','rect');br.setAttribute('x',0);br.setAttribute('y',0);br.setAttribute('width',d.vw);br.setAttribute('height',d.vh);br.setAttribute('fill','#fff');br.setAttribute('stroke','#ccc');br.setAttribute('stroke-width','4');S.appendChild(br);d.boxes.forEach(b=>{const g=document.createElementNS('http://www.w3.org/2000/svg','g');g.style.cursor=b.svc?'default':'pointer';const r=document.createElementNS('http://www.w3.org/2000/svg','rect');r.setAttribute('x',b.x);r.setAttribute('y',b.y);r.setAttribute('width',b.w);r.setAttribute('height',b.h);r.setAttribute('rx','3');const f=fc(b.id,b.svc);r.setAttribute('fill',f.bg);r.setAttribute('stroke',f.st);r.setAttribute('stroke-width',sts(b.id)==='occupied'?'2':'1');g.appendChild(r);const lbl=shortLabel(b.id);const lines=lbl.split('\\n');const fs=b.w<22?5:b.w<32?6:b.w<44?7:b.w<65?8:9;const lh=fs*1.3,tH=lines.length*lh,sy=b.y+b.h/2-tH/2+fs*0.8;lines.forEach((ln,i)=>{const t2=document.createElementNS('http://www.w3.org/2000/svg','text');t2.setAttribute('x',b.x+b.w/2);t2.setAttribute('y',sy+i*lh);t2.setAttribute('text-anchor','middle');t2.setAttribute('font-size',fs);t2.setAttribute('font-family','-apple-system,sans-serif');t2.setAttribute('font-weight',sts(b.id)==='occupied'?'700':'500');t2.setAttribute('fill',f.tx);t2.setAttribute('pointer-events','none');t2.textContent=ln;g.appendChild(t2);});if(!b.svc){g.addEventListener('mouseenter',e=>{r.setAttribute('stroke-width','2.5');showTT(e,b.id);});g.addEventListener('mousemove',e=>moveTT(e));g.addEventListener('mouseleave',()=>{r.setAttribute('stroke-width',sts(b.id)==='occupied'?'2':'1');hideTT();});}S.appendChild(g);});return S;}
function rebuildSVG(key){const pi=document.getElementById('plan-inner');const old=pi.querySelector('svg');if(old)pi.removeChild(old);pi.appendChild(buildSVG(key));}
function switchTab(key,btn){currentTab=key;document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));btn.classList.add('active');hideTT();rebuildSVG(key);renderTabBar(key);}
document.getElementById('datebadge').textContent=new Date().toLocaleDateString('uk-UA',{day:'numeric',month:'long',year:'numeric'});
renderTotalCount();renderTotalArea();renderLocStats();renderTabBar('m01');rebuildSVG('m01');
</script></body></html>"""

    js = js.replace("__TENANTS__", tj)
    js = js.replace("__RESERVED__", json.dumps(reserved, ensure_ascii=False))
    js = js.replace("__M01__", boxes_m01)
    js = js.replace("__M02__", boxes_m02)
    js = js.replace("__M03__", boxes_m03)

    return "\n".join(lines) + "\n" + js


def main():
    kyiv = timezone(timedelta(hours=3))
    ts = datetime.now(kyiv).strftime("%d.%m.%Y %H:%M")
    # Якщо сервер недоступний — index.html НЕ змінюємо (лишається вчорашня версія), workflow падає з помилкою
    tenants, reserved = fetch_statuses()
    html = build_html(tenants, reserved, ts)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Done! {} chars".format(len(html)))


if __name__ == "__main__":
    main()
