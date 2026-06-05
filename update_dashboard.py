#!/usr/bin/env python3
"""
mybox Dashboard Auto-Updater
Runs daily via GitHub Actions at 20:00 Kyiv time
Reads Google Sheets "Список охорони" and rebuilds index.html
"""

import csv
import io
import json
import re
import urllib.request
import urllib.error
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQjdYtUNfpv4ab4W3D55EWOXOnWZGhTJtTf50OqtM3K4NJdR-06YNLPG08dbQ8mUJuGLvY0dZiD7XoT/pub?gid=975946594&single=true&output=csv"

# ── Fallback tenants (used if Sheets is unreachable) ────────────────────
FALLBACK_TENANTS = {
  "А-1-46001":"Kato Shintaro","А-1-46002":"Haywood Connor Kenneth",
  "А-1-46003":"Мисник Яна Владиславівна","А-1-46004":"Кошкін Павло Андрійович",
  "А-1-46005":"Усачов Вадим Андрійович","А-1-46006":"Нікітіна Світлана Іванівна",
  "А-1-46007":"Калашник Володимир Сергійович","А-1-46008":"Christian Weichselbaum",
  "А-1-46011":"Mcewing Daren Brock",
  "В-2,8-46013":"Новіков Віталій Юрійович","В-2,8-46014":"ФОП Вишня Оксана Іванівна",
  "В-2,8-46015":"ФОП Вишня Оксана Іванівна","В-2,8-46016":"ФОП Вишня Оксана Іванівна",
  "В-2,8-46017":"Коростельов Антон Іванович","В-5,5-46018":"Зима Ірина Олегівна",
  "С-2,5-46019":"Давидов Денис Геннадійович","С-2,5-46020":"Коноваленко Артем Сергійович",
  "С-2,5-46022":"Олег","С-2,5-46025":"Ласкорунська Анна Сергіївна",
  "С-2,5-46028":"Булигіна Олександра Олександрівна",
  "С-4-46036":"Трашутін Єгор Ігорович","С-3,5-46037":"Каморкіна Сніжана Вікторівна",
  "D-2-46039":"Гордієнко Юрій Вікторович","D-2-46040":"Кулинич Владислав Анатолійович",
  "D-2-46041":"Заколенко Ольга Костянтинівна","D-2-46042":"Алтухова Яна Віталіївна",
  "D-2-46043":"Хавро Марина Вадимівна","D-2-46044":"Сичова Ольга Андріївна",
  "D-4-46045":"Пояркова Аліса Дмитрівна","D-2-46046":"Литвинець Юлія Василіївна",
  "D-2-46047":"Павлюк Наталія Олегівна",
  "E-2-46049":"Губайдулліна Анастасія Михайлівна","E-2-46050":"Веременко Ярослав Олегович",
  "E-4-46051":"Мазур Ілля Миколайович","E-2-46052":"Назарова Анастасія Андріївна",
  "F-4-46063":"Сенько Андрій Вікторович","F-4-46064":"Андронік Віктор Миколайович",
  "G-1-46068":"Дроншкевич Ева Олегівна","G-1-46075":"Алфьорова Тетяна Вікторівна",
  "К-3-46086":"Черганов Василь Геннадійович","К-3-46090":"Черганов Василь Геннадійович",
  "М-6,5-46113":"Черганов Василь Геннадійович","М-2-46114":"Бебіх Юлія Сергіївна",
  "М-2-46115":"Логвіна Влада Євгенівна","N-8-46125":"Троценко Олена Миколаївна",
  "Р-15":"Чередніченко Дар'я Ігорівна","Р-15-46145":"Чередніченко Дар'я Ігорівна",
  "С-4-88044":"Ланда Ігор Олександрович","F-3-88055":"Мінза Анастасія Ігорівна"
}

def fetch_tenants_from_sheets():
    """Fetch tenants from Google Sheets CSV"""
    print(f"Fetching data from Google Sheets...")
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; mybox-bot/1.0)",
        "Accept": "text/csv,*/*"
    }
    req = urllib.request.Request(CSV_URL, headers=headers)
    resp = urllib.request.urlopen(req, timeout=30)
    text = resp.read().decode("utf-8")
    
    tenants = {}
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    print(f"  Got {len(rows)} rows from Sheets")
    
    # Row 0 is header: Клієнт, Номер, Коментар
    for i, row in enumerate(rows[1:], 1):
        if len(row) < 2:
            continue
        client = row[0].strip()
        box_id = row[1].strip()
        if not box_id:
            continue
        if client:
            tenants[box_id] = client
    
    # Alias for Р-15
    if "Р-15-46145" in tenants:
        tenants["Р-15"] = tenants["Р-15-46145"]
    
    print(f"  Found {len(tenants)} occupied boxes")
    return tenants

def build_html(tenants, update_time):
    """Build the complete index.html with current tenant data"""
    
    tenants_js = json.dumps(tenants, ensure_ascii=False)
    count = len([k for k in tenants if not k.endswith("-46145")])
    
    # Read logo and boxes from data file
    with open("dashboard_data.json") as f:
        data = json.load(f)
    
    logo_b64 = data["logo_b64"]
    boxes_m01 = data["boxes_m01"]
    boxes_m02 = data["boxes_m02"]
    boxes_m03 = data["boxes_m03"]
    css = data["css"]
    
    html = f"""<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>mybox — Дашборд-план</title>
<style>{css}</style>
</head>
<body>
<div class="app">
  <div class="top">
    <div class="top-left">
      <img class="logo-img" src="data:image/jpeg;base64,{logo_b64}" alt="mybox"/>
      <div class="logo-text">my<em>box</em> — Дашборд-план</div>
    </div>
    <div class="top-right">
      <div class="date-badge" id="datebadge"></div>
      <div class="sync-info">✓ Оновлено {update_time} · {count} орендарів</div>
    </div>
  </div>

  <div class="section-title">Загальна статистика — кількість боксів</div>
  <div class="total-grid" id="total-count"></div>
  <hr class="section-sep"/>
  <div class="section-title">Загальна статистика — площа боксів, кв.м.</div>
  <div class="total-grid-sq" id="total-area"></div>
  <hr class="section-sep"/>
  <div class="section-title">По локаціях</div>
  <div class="loc-stats" id="loc-stats"></div>

  <div class="tabs">
    <button class="tab active" onclick="switchTab('m01',this)">М-01</button>
    <button class="tab" onclick="switchTab('m02',this)">М-02</button>
    <button class="tab" onclick="switchTab('m03',this)">М-03</button>
  </div>
  <div class="tab-bar" id="tab-bar"></div>

  <div class="legend">
    <div class="li"><div class="ld" style="background:#f0ece4;border:1px solid #c8c3b8"></div>Вільний</div>
    <div class="li"><div class="ld" style="background:#F7C1C1;border:1px solid #E24B4A"></div>Орендовано</div>
    <div class="li"><div class="ld" style="background:#FAC775;border:1px solid #BA7517"></div>Резерв</div>
    <div class="li"><div class="ld" style="background:#D3D1C7;border:1px solid #888780"></div>Службове</div>
  </div>

  <div class="plan-wrap" id="plan-wrap">
    <div id="plan-inner"></div>
    <div class="tooltip" id="tt">
      <div class="tt-id" id="tt-id"></div>
      <div class="tt-area" id="tt-area"></div>
      <div class="tt-badge" id="tt-badge"></div>
      <div class="tt-name" id="tt-name"></div>
    </div>
  </div>
  <footer>mybox.ua &copy; 2026 &middot; Автооновлення щодня о 20:00 з Google Sheets</footer>
</div>
<script>
const TENANTS={tenants_js};
const RESERVED={{"G-1-46069 Резерв":true,"L-2-46112 Резерв":true}};
const DATA={{
  m01:{{label:"М-01 (вул. Березова 46)",vw:980,vh:530,boxes:{boxes_m01}}},
  m02:{{label:"М-02",vw:1020,vh:510,boxes:{boxes_m02}}},
  m03:{{label:"М-03",vw:980,vh:540,boxes:{boxes_m03}}}
}};
let currentTab='m01';
function parseArea(id){{
  const c=id.replace(' Резерв','');
  const m1=c.match(/^[А-ЯҐЄІЇa-zA-Z]+-([\d]+[,\.][\d]+)-[\d]{{2,5}}$/i);
  if(m1)return parseFloat(m1[1].replace(',','.'));
  const m2=c.match(/^[А-ЯҐЄІЇa-zA-Z]+-([\d]+)-[\d]{{2,5}}$/i);
  if(m2)return parseFloat(m2[1]);
  const m3=c.match(/^[А-ЯҐЄІЇa-zA-Z]+-([\d]+[,\.]?[\d]*)$/i);
  if(m3)return parseFloat(m3[1].replace(',','.'));
  return 0;
}}
function sts(id){{return TENANTS[id]?'occupied':RESERVED[id]?'reserved':'free';}}
function fc(id,svc){{
  if(svc)return{{bg:'#D3D1C7',st:'#888780',tx:'#5F5E5A'}};
  const s=sts(id);
  if(s==='occupied')return{{bg:'#FCEBEB',st:'#E24B4A',tx:'#791F1F'}};
  if(s==='reserved')return{{bg:'#FAEEDA',st:'#BA7517',tx:'#633806'}};
  return{{bg:'#f0ece4',st:'#b8b2a6',tx:'#5F5E5A'}};
}}
function shortLabel(id){{
  const svc=['OFFICE','WC','ДУШ','СХОДИ','ВХІД','ENTER'];
  if(svc.includes(id))return id;
  const c=id.replace(' Резерв','');
  const m=c.match(/^(.+?)-(\d{{5}})$/);if(m)return m[1]+'\\n'+m[2].slice(-3);
  const m2=c.match(/^(.+?)-(\d{{2,4}})$/);if(m2)return m2[1]+'\\n'+m2[2];
  return c.length>10?c.slice(0,10):c;
}}
function fmt(n){{return Number.isInteger(n)?n:n.toFixed(1);}}
function calcStats(key){{
  const d=DATA[key];
  let total=0,occ=0,res=0,free=0,sqT=0,sqO=0,sqR=0,sqF=0;
  d.boxes.forEach(b=>{{
    if(b.svc)return;total++;
    const s=sts(b.id),sq=parseArea(b.id);
    sqT=Math.round((sqT+sq)*10)/10;
    if(s==='occupied'){{occ++;sqO=Math.round((sqO+sq)*10)/10;}}
    else if(s==='reserved'){{res++;sqR=Math.round((sqR+sq)*10)/10;}}
    else{{free++;sqF=Math.round((sqF+sq)*10)/10;}}
  }});
  return{{total,occ,res,free,pct:total?Math.round(occ/total*100):0,sqT,sqO,sqR,sqF,sqPct:sqT?Math.round(sqO/sqT*100):0}};
}}
function renderTotalCount(){{
  let t=0,o=0,r=0,f=0;
  ['m01','m02','m03'].forEach(k=>{{const s=calcStats(k);t+=s.total;o+=s.occ;r+=s.res;f+=s.free;}});
  const pct=Math.round(o/t*100);
  document.getElementById('total-count').innerHTML=`<div class="tstat"><div class="tstat-l">Всього боксів</div><div class="tstat-v">${{t}}</div></div><div class="tstat"><div class="tstat-l">Орендовано</div><div class="tstat-v red">${{o}}</div></div><div class="tstat"><div class="tstat-l">Вільних</div><div class="tstat-v grn">${{f}}</div></div><div class="tstat"><div class="tstat-l">Заповненість %</div><div class="tstat-v amb">${{pct}}%<div class="fill-bar"><div class="fill-bar-inner" style="width:${{pct}}%"></div></div></div></div>`;
}}
function renderTotalArea(){{
  let sqT=0,sqO=0,sqR=0,sqF=0;
  ['m01','m02','m03'].forEach(k=>{{const s=calcStats(k);sqT=Math.round((sqT+s.sqT)*10)/10;sqO=Math.round((sqO+s.sqO)*10)/10;sqR=Math.round((sqR+s.sqR)*10)/10;sqF=Math.round((sqF+s.sqF)*10)/10;}});
  const sqPct=sqT?Math.round(sqO/sqT*100):0;
  document.getElementById('total-area').innerHTML=`<div class="tstat"><div class="tstat-l">Всього площа</div><div class="tstat-v">${{fmt(sqT)}} <span style="font-size:13px;font-weight:400;color:#aaa">кв.м</span></div></div><div class="tstat"><div class="tstat-l">Орендовано кв.м</div><div class="tstat-v red">${{fmt(sqO)}}</div></div><div class="tstat"><div class="tstat-l">Вільних кв.м</div><div class="tstat-v grn">${{fmt(sqF)}}</div></div><div class="tstat"><div class="tstat-l">Резерв кв.м</div><div class="tstat-v amb">${{fmt(sqR)}}</div></div><div class="tstat"><div class="tstat-l">Заповненість кв.м %</div><div class="tstat-v blue">${{sqPct}}%<div class="fill-bar"><div class="fill-bar-inner" style="width:${{sqPct}}%;background:#1a6fb5"></div></div></div></div>`;
}}
function renderLocStats(){{
  document.getElementById('loc-stats').innerHTML=['m01','m02','m03'].map(k=>{{
    const s=calcStats(k);const d=DATA[k];
    return`<div class="lstat"><div class="lstat-hdr"><span class="lstat-name">${{d.label}}</span><span class="lstat-pct">${{s.pct}}%</span></div><div class="lstat-row"><span>Боксів всього</span><span>${{s.total}}</span></div><div class="lstat-row"><span>Орендовано</span><span class="red">${{s.occ}}</span></div><div class="lstat-row"><span>Вільних</span><span class="grn">${{s.free}}</span></div><div class="lstat-row"><span>Резерв</span><span class="amb">${{s.res}}</span></div><hr class="lstat-divider"/><div class="lstat-row"><span>Площа всього</span><span>${{fmt(s.sqT)}} кв.м</span></div><div class="lstat-row"><span>Орендовано кв.м</span><span class="red">${{fmt(s.sqO)}}</span></div><div class="lstat-row"><span>Вільних кв.м</span><span class="grn">${{fmt(s.sqF)}}</span></div><div class="lstat-row"><span>Резерв кв.м</span><span class="amb">${{fmt(s.sqR)}}</span></div><div class="lstat-bar"><div class="lstat-bar-inner" style="width:${{s.sqPct}}%"></div></div></div>`;
  }}).join('');
}}
function renderTabBar(key){{
  const s=calcStats(key);const d=DATA[key];
  document.getElementById('tab-bar').innerHTML=`<strong>${{d.label}}</strong><span class="sep">·</span>Орендовано: <strong class="red">${{s.occ}} (${{fmt(s.sqO)}} кв.м)</strong><span class="sep">·</span>Вільних: <strong class="grn">${{s.free}} (${{fmt(s.sqF)}} кв.м)</strong><span class="sep">·</span>Заповненість: <strong class="amb">${{s.pct}}% / ${{s.sqPct}}% площі</strong>`;
}}
const tt=document.getElementById('tt');const pw=document.getElementById('plan-wrap');
function showTT(e,id){{
  const sq=parseArea(id);
  document.getElementById('tt-id').textContent=id.replace(' Резерв','');
  document.getElementById('tt-area').textContent=sq>0?`Площа: ${{fmt(sq)}} кв.м`:'';
  const b=document.getElementById('tt-badge');const s=sts(id);
  b.textContent=s==='occupied'?'Орендовано':s==='reserved'?'Резерв':'Вільний';
  b.className='tt-badge '+s;
  document.getElementById('tt-name').textContent=TENANTS[id]||'';
  tt.style.display='block';moveTT(e);
}}
function moveTT(e){{const rc=pw.getBoundingClientRect();let lx=e.clientX-rc.left+14,ly=e.clientY-rc.top+14;if(lx+250>rc.width)lx-=264;if(ly+100>rc.height)ly-=110;tt.style.left=lx+'px';tt.style.top=ly+'px';}}
function hideTT(){{tt.style.display='none';}}
function buildSVG(key){{
  const d=DATA[key];const S=document.createElementNS('http://www.w3.org/2000/svg','svg');
  S.setAttribute('viewBox',`0 0 ${{d.vw}} ${{d.vh}}`);S.style.cssText='display:block;width:100%;height:auto';
  const br=document.createElementNS('http://www.w3.org/2000/svg','rect');
  br.setAttribute('x',0);br.setAttribute('y',0);br.setAttribute('width',d.vw);br.setAttribute('height',d.vh);
  br.setAttribute('fill','#fff');br.setAttribute('stroke','#ccc');br.setAttribute('stroke-width','4');S.appendChild(br);
  d.boxes.forEach(b=>{{
    const g=document.createElementNS('http://www.w3.org/2000/svg','g');g.style.cursor=b.svc?'default':'pointer';
    const r=document.createElementNS('http://www.w3.org/2000/svg','rect');
    r.setAttribute('x',b.x);r.setAttribute('y',b.y);r.setAttribute('width',b.w);r.setAttribute('height',b.h);r.setAttribute('rx','3');
    const f=fc(b.id,b.svc);r.setAttribute('fill',f.bg);r.setAttribute('stroke',f.st);
    r.setAttribute('stroke-width',sts(b.id)==='occupied'?'2':'1');g.appendChild(r);
    const lbl=shortLabel(b.id);const lines=lbl.split('\\n');
    const fs=b.w<22?5:b.w<32?6:b.w<44?7:b.w<65?8:9;
    const lh=fs*1.3,tH=lines.length*lh,sy=b.y+b.h/2-tH/2+fs*0.8;
    lines.forEach((ln,i)=>{{
      const t2=document.createElementNS('http://www.w3.org/2000/svg','text');
      t2.setAttribute('x',b.x+b.w/2);t2.setAttribute('y',sy+i*lh);
      t2.setAttribute('text-anchor','middle');t2.setAttribute('font-size',fs);
      t2.setAttribute('font-family','-apple-system,sans-serif');
      t2.setAttribute('font-weight',sts(b.id)==='occupied'?'700':'500');
      t2.setAttribute('fill',f.tx);t2.setAttribute('pointer-events','none');
      t2.textContent=ln;g.appendChild(t2);
    }});
    if(!b.svc){{
      g.addEventListener('mouseenter',e=>{{r.setAttribute('stroke-width','2.5');showTT(e,b.id);}});
      g.addEventListener('mousemove',e=>moveTT(e));
      g.addEventListener('mouseleave',()=>{{r.setAttribute('stroke-width',sts(b.id)==='occupied'?'2':'1');hideTT();}});
    }}
    S.appendChild(g);
  }});return S;
}}
function rebuildSVG(key){{const pi=document.getElementById('plan-inner');const old=pi.querySelector('svg');if(old)pi.removeChild(old);pi.appendChild(buildSVG(key));}}
function switchTab(key,btn){{currentTab=key;document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));btn.classList.add('active');hideTT();rebuildSVG(key);renderTabBar(key);}}
document.getElementById('datebadge').textContent=new Date().toLocaleDateString('uk-UA',{{day:'numeric',month:'long',year:'numeric'}});
renderTotalCount();renderTotalArea();renderLocStats();renderTabBar('m01');rebuildSVG('m01');
</script></body></html>"""
    
    return html

def main():
    # Try to fetch from Google Sheets
    try:
        tenants = fetch_tenants_from_sheets()
        source = "Google Sheets"
    except Exception as e:
        print(f"Warning: Could not fetch from Sheets: {e}")
        print("Using fallback tenant data...")
        tenants = FALLBACK_TENANTS.copy()
        source = "fallback"
    
    # Build update timestamp (Kyiv time UTC+3)
    from datetime import timezone, timedelta
    kyiv = timezone(timedelta(hours=3))
    now = datetime.now(kyiv)
    update_time = now.strftime("%d.%m.%Y %H:%M")
    
    print(f"Building HTML ({source}, {len(tenants)} tenants, {update_time})...")
    html = build_html(tenants, update_time)
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"Done! index.html updated ({len(html)} chars)")

if __name__ == "__main__":
    main()
