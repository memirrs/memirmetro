"""
Metro İstanbul Canlı Board
===========================
pip install flask requests
python metro_app.py → http://localhost:5000
"""

import re, time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, render_template_string
import requests as req
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

IBB_BASE = "https://api.ibb.gov.tr/MetroIstanbul/api/MetroMobile/V2"
AJAX_URL = "https://www.metro.istanbul/SeferDurumlari/AJAXSeferGetir"
PAGE_URL = "https://www.metro.istanbul/SeferDurumlari/SeferDetaylari"
HAT_URL  = "https://www.metro.istanbul/Hatlarimiz/HatDetay?hat={}"
OVERPASS = "https://overpass-api.de/api/interpreter"

METRO_HATLARI = {"M1A","M1B","M2","M3","M4","M5","M6","M7","M8","M9"}

HAT_RENKLERI = {
    "M1A":"#E8421B","M1B":"#E8421B",
    "M2":"#D01F2D","M3":"#F47920","M4":"#0072BC",
    "M5":"#8B1A8B","M6":"#00A651","M7":"#F7A800",
    "M8":"#00AEEF","M9":"#E31E24",
}

# ── Düzeltilmiş koordinatlar ──────────────────────────────────────────────────
COORDS = {
    # M2 (Yenikapı → Hacıosman)
    "YENIKAPI":          (41.0045, 28.9501),
    "VEZNECILER":        (41.0168, 28.9598),
    "HALIC":             (41.0300, 28.9487),
    "SISHANE":           (41.0333, 28.9732),
    "TAKSIM":            (41.0369, 28.9850),
    "OSMANBEY":          (41.0462, 28.9878),
    "SISLIMECIDIYEKOY":  (41.0608, 28.9866),
    "GAYRETTEPE":        (41.0693, 28.9954),
    "LEVENT":            (41.0808, 29.0100),
    "4LEVENT":           (41.0889, 29.0145),
    "SANAYIMAHALLESI":   (41.0987, 29.0220),
    "SEYRANTEPE":        (41.1062, 29.0265),
    "ITUAYAZAGA":        (41.1154, 29.0227),
    "ATATURKOTOSANAYI":  (41.1234, 29.0144),
    "DARUSSAFAKA":       (41.1344, 29.0094),
    "HACIOSMAN":         (41.1403, 28.9972),
    # M4 (Kadıköy → Tavşantepe)
    "KADIKOY":           (40.9902, 29.0246),
    "AYRILIKCESMESI":    (41.0021, 29.0283),
    "ACIBADEM":          (41.0082, 29.0415),
    "UNALAN":            (41.0056, 29.0545),
    "GOZTEPE":           (40.9831, 29.0681),
    "YENISAHRA":         (40.9758, 29.0784),
    "KOZYATAGI":         (40.9752, 29.0891),
    "BOSTANCI":          (40.9636, 29.1009),
    "KUCUKYALI":         (40.9579, 29.1264),
    "MALTEPE":           (40.9388, 29.1359),
    "HUZUREVI":          (40.9270, 29.1384),
    "GULSUYU":           (40.9191, 29.1401),
    "ESENKENT":          (40.9093, 29.1537),
    "HASTANEADLIYE":     (40.8979, 29.1671),
    "SABIHAGOKCEN":      (40.8985, 29.2064),
    "TAVSANTEPE":        (40.9052, 29.2225),
    "FEVZICAKMAK":       (40.9150, 29.1840),
    # M1A / M1B (Yenikapı → Kirazlı / Atatürk Hav.)
    "AKSARAY":           (41.0134, 28.9509),
    "EMNIYETFATIH":      (41.0168, 28.9271),
    "EMNIYET":           (41.0168, 28.9271),
    "TOPKAPIULUBATLI":   (41.0196, 28.9047),
    "ULUBATLI":          (41.0196, 28.9047),
    "BAYRAMPASAMALTEPE": (41.0421, 28.9133),
    "BAYRAMPASA":        (41.0421, 28.9133),
    "SAGMALCILAR":       (41.0534, 28.8964),
    "KOCATEPE":          (41.0598, 28.8843),
    "OTOGAR":            (41.0624, 28.8698),
    "TERAZIDERE":        (41.0652, 28.8598),
    "DAVUTPASAYTU":      (41.0620, 28.8476),
    "DAVUTPASA":         (41.0620, 28.8476),
    "MERTER":            (41.0194, 28.8934),
    "ZEYTINBURNU":       (40.9981, 28.9046),
    "BAKIRKOYINCIRLI":   (40.9846, 28.8712),
    "BAHCELIEVLER":      (41.0006, 28.8576),
    "ATAKOYSIRNEVLER":   (40.9994, 28.8423),
    "ATAKOY":            (40.9994, 28.8423),
    "BAGCILAR":          (41.0369, 28.8543),
    "BAGCILARMEYDAN":    (41.0369, 28.8543),
    "KIRAZLI":           (41.0476, 28.8196),
    "YENIBOSNA":         (41.0031, 28.8316),
    "ATATURKHAVALIMANI": (40.9768, 28.8168),
    # M3 (Kirazlı → İkitelli/Olimpiyat)
    "BAGCILARMERKEZM3":  (41.0402, 28.8343),
    "ISTOC":             (41.0450, 28.8867),
    "IKITELLIS":         (41.0570, 28.8756),
    "IKELLIS":           (41.0570, 28.8756),
    "TURGUTOZEL":        (41.0720, 28.8594),
    "OLIMPIYAT":         (41.0856, 28.8442),
    "IKITELLOSB":        (41.0677, 28.8758),
    "IKITELLISANAYI":    (41.0677, 28.8758),
    # M5 (Üsküdar → Çekmeköy)
    "USKUDAR":           (41.0219, 29.0143),
    "FISTIKAGACI":       (41.0330, 29.0340),
    "BAGLARBASIM5":      (41.0251, 29.0489),
    "BAGLARBASI":        (41.0251, 29.0489),
    "ALTUNIZADE":        (41.0213, 29.0590),
    "KISIKLI":           (41.0381, 29.0700),
    "BULGURLU":          (41.0479, 29.0881),
    "UMRANIYE":          (41.0334, 29.1184),
    "CARSI":             (41.0224, 29.1246),
    "YAMANEVLER":        (41.0209, 29.1383),
    "CAKMAK":            (41.0171, 29.1560),
    "IHLAMURKUYU":       (41.0126, 29.1637),
    "ALEMDAG":           (41.0067, 29.1829),
    "CEKMEKOY":          (41.0065, 29.1912),
    # M6 (Levent → Hisarüstü)
    "NISPETIYE":         (41.0739, 29.0378),
    "ETILER":            (41.0778, 29.0478),
    "BOGAZICIUNIVERSITESI": (41.0834, 29.0567),
    "HISARUSTU":         (41.0879, 29.0674),
    # M7 (Mahmutbey → Kabataş yönü)
    "MAHMUTBEY":         (41.0557, 28.8870),
    "MECIDIYEKOY":       (41.0680, 28.9867),
    "CAGLAYAN":          (41.0772, 28.9694),
    "KAGITHANE":         (41.0885, 28.9627),
    "NURTEPE":           (41.1016, 28.9607),
    "ALISAMIYEN":        (41.1052, 28.9448),
    "YILDIZTEPE":        (41.1090, 28.9267),
    "KAZLICESME":        (41.1160, 28.9198),
    "M7GOZTEPE":         (41.0430, 28.8700),
    # M8 (Bostancı → Dudullu)
    "SARIGAZI":          (41.0018, 29.1457),
    "SITE":              (41.0087, 29.1567),
    "NENEHATUN":         (41.0159, 29.1618),
    "PARSELLER":         (41.0220, 29.1718),
    "HUZUR":             (41.0060, 29.1500),
    "YUKARIDUDULLU":     (41.0312, 29.1831),
    "DUDULLU":           (41.0354, 29.1840),
    # M9 (Ataköy-Olimpiyat → İkitelli)
    "ATAKOLYOLIMPIYAT":  (40.9889, 28.8235),
    "SIRINNEVLER":       (40.9944, 28.8393),
    "YENIBOSNAM9":       (41.0031, 28.8316),
    "MITHATPASA":        (41.0087, 28.8354),
    "GUNGOREN":          (41.0299, 28.8476),
}

_coord_cache = None
_coord_cache_ts = 0

def normalize(name):
    tr = str.maketrans("ğĞşŞçÇüÜöÖıİ","gGsScCuUoOiI")
    return re.sub(r"[^A-Z0-9]","",name.upper().translate(tr))

def get_coords():
    global _coord_cache, _coord_cache_ts
    if _coord_cache and time.time()-_coord_cache_ts < 3600:
        return _coord_cache
    merged = {normalize(k):v for k,v in COORDS.items()}
    try:
        q = """[out:json][timeout:25];
(node["station"="subway"](40.80,28.50,41.35,29.55);
 node["railway"="station"]["subway"="yes"](40.80,28.50,41.35,29.55););
out body;"""
        r = req.post(OVERPASS,data={"data":q},timeout=30)
        for n in r.json().get("elements",[]):
            nm = n.get("tags",{}).get("name","")
            if nm:
                k = normalize(nm)
                if k not in merged:
                    merged[k] = (n["lat"],n["lon"])
    except Exception:
        pass
    _coord_cache = merged
    _coord_cache_ts = time.time()
    return merged

def match(name, coords):
    k = normalize(name)
    if k in coords: return coords[k]
    for ck,v in coords.items():
        if k in ck or ck in k: return v
    for w in [x for x in k.split() if len(x)>3]:
        for ck,v in coords.items():
            if w in ck: return v
    return None

# ── IBB / Metro.istanbul yardımcıları ────────────────────────────────────────
def ibb_get(ep):
    r = req.get(f"{IBB_BASE}/{ep}",headers={"User-Agent":"Mozilla/5.0"},timeout=15)
    r.raise_for_status()
    return r.json().get("Data",[])

def yeni_s():
    s = req.Session()
    s.verify = False
    s.headers.update({"User-Agent":"Mozilla/5.0"})
    return s

def kod_cek(s):
    r = s.get(PAGE_URL,timeout=15); r.raise_for_status()
    m = re.search(r'formData\.append\(\s*["\']kod["\']\s*,\s*["\']'
                  r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})["\']',
                  r.text, re.I)
    return m.group(1) if m else None

def tarife(s, st_id, rt_id, tarih, kod):
    r = s.post(AJAX_URL,data={"secim":"0","saat":"","dakika":"","tarih1":"",
        "tarih2":tarih,"station":str(st_id),"route":str(rt_id),"kod":kod},
        headers={"Accept":"application/json,*/*","X-Requested-With":"XMLHttpRequest",
                 "Referer":PAGE_URL},timeout=15)
    r.raise_for_status()
    try: v=r.json()
    except: return []
    if isinstance(v,dict) and str(v.get("durum"))=="-1": return []
    return v.get("sefer",[]) if isinstance(v,dict) else (v or [])

def s2min(s):
    h,m=map(int,s.split(":")); return h*60+m

def s2dt(s,baz):
    h,m=map(int,s.split(":"))
    dt=baz.replace(hour=h,minute=m,second=0,microsecond=0)
    if h<4 and baz.hour>20: dt+=timedelta(days=1)
    return dt

def hat_suresi(s,hat):
    try:
        r=s.get(HAT_URL.format(hat),timeout=10)
        m=re.search(r"(?:sefer|seyahat)\s+s.resi\s*[:\-]\s*([\d,\.]+)\s*dakika",r.text,re.I)
        if m: return int(float(m.group(1).replace(",",".")))
    except: pass
    return None

def yolculuk_suresi(s,bas_id,bit_id,rt_id,tarih,hat):
    sure=hat_suresi(s,hat)
    if sure: return sure
    kod=kod_cek(s); bas=tarife(s,bas_id,rt_id,tarih,kod)
    kod=kod_cek(s); bit=tarife(s,bit_id,rt_id,tarih,kod)
    if not bas or not bit: return None
    bm=sorted({s2min(x["zaman"]) for x in bas})
    bs={s2min(x["zaman"]) for x in bit}
    bt,bn=None,0
    for T in range(15,76):
        n=sum(1 for b in bm if (b+T-1) in bs or (b+T) in bs or (b+T+1) in bs)
        if n>bn: bn,bt=n,T
    return bt

def hat_trenler(hat,tarih,simdi,coords):
    s=yeni_s()
    try:
        yonler=ibb_get(f"GetDirectionById/{hat['Id']}")
        istler=ibb_get(f"GetStationById/{hat['Id']}")
        sure=hat_suresi(s,hat["Name"]) or max((len(istler)-1)*2.5,10)
        n=len(istler); d=sure/(n-1) if n>1 else sure
        zamanlar=[i*d for i in range(n)]
        trenler=[]
        for yon in yonler:
            parcalar=yon["DirectionName"].split("->")
            bas_adi=parcalar[0].strip().upper().split()[0]
            bas_st=next((x for x in istler if bas_adi in x["Name"].upper()),istler[0])
            try:
                kod=kod_cek(s); sf=tarife(s,bas_st["Id"],yon["DirectionId"],tarih,kod)
            except: continue
            if not sf: continue
            sf_dt=sorted({s2dt(x["zaman"],simdi) for x in sf})
            for kal in sf_dt:
                bit=kal+timedelta(minutes=sure)
                if kal>simdi or bit<simdi: continue
                gecen=(simdi-kal).total_seconds()/60
                for i in range(n-1):
                    if zamanlar[i]<=gecen<zamanlar[i+1]:
                        pct=(gecen-zamanlar[i])/(zamanlar[i+1]-zamanlar[i])
                        kalan_sn=max(1,(zamanlar[i+1]-gecen)*60)
                        c1=match(istler[i]["Name"],coords)
                        c2=match(istler[i+1]["Name"],coords)
                        if not c1 or not c2: break
                        lat=c1[0]+(c2[0]-c1[0])*pct
                        lon=c1[1]+(c2[1]-c1[1])*pct
                        trenler.append({
                            "id":f"{hat['Name']}-{kal.strftime('%H%M')}-{yon['DirectionId']}",
                            "hat":hat["Name"],"renk":hat["renk"],
                            "kalkis":kal.strftime("%H:%M"),
                            "nereden":istler[i]["Name"].title(),
                            "nereye":istler[i+1]["Name"].title(),
                            "lat":round(lat,6),"lon":round(lon,6),
                            "lat2":round(c2[0],6),"lon2":round(c2[1],6),
                            "kalan_sn":round(kalan_sn),
                            "yuzde":round(pct*100),
                        })
                        break
        return trenler
    except: return []

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.route("/api/trenler")
def api_trenler():
    coords=get_coords()
    hatlar=[h for h in ibb_get("GetLines") if h["Name"] in METRO_HATLARI]
    for h in hatlar: h["renk"]=HAT_RENKLERI.get(h["Name"],"#555")
    simdi=datetime.today()
    tarih=simdi.strftime("%d.%m.%Y")
    sonuc=[]
    with ThreadPoolExecutor(max_workers=5) as ex:
        fs=[ex.submit(hat_trenler,h,tarih,simdi,coords) for h in hatlar]
        for f in as_completed(fs):
            try: sonuc.extend(f.result())
            except: pass
    gun=["Pzt","Sal","Çar","Per","Cum","Cmt","Paz"][simdi.weekday()]
    return jsonify({"trenler":sonuc,"tren_sayisi":len(sonuc),
                    "simdi":simdi.strftime("%H:%M"),"tarih":f"{simdi.strftime('%d.%m.%Y')} {gun}"})

@app.route("/api/hatlar")
def api_hatlar():
    coords=get_coords()
    hatlar=[h for h in ibb_get("GetLines") if h["Name"] in METRO_HATLARI]
    sonuc=[]
    for hat in hatlar:
        renk=HAT_RENKLERI.get(hat["Name"],"#555")
        istler=ibb_get(f"GetStationById/{hat['Id']}")
        stlar=[]
        for st in istler:
            c=match(st["Name"],coords)
            if c: stlar.append({"name":st["Name"].title(),"lat":c[0],"lon":c[1]})
        sonuc.append({"name":hat["Name"],"renk":renk,"istasyonlar":stlar})
    return jsonify(sonuc)

# ── HTML Board ────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Metro İstanbul — Canlı</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;background:#0d1117;color:#e6edf3;font-family:'Segoe UI',system-ui,sans-serif;overflow:hidden}
#map{position:absolute;inset:0}

/* Üst bar */
#topbar{position:absolute;top:0;left:0;right:0;z-index:1000;
  background:rgba(13,17,23,.88);backdrop-filter:blur(8px);
  border-bottom:1px solid #30363d;
  display:flex;align-items:center;gap:16px;padding:10px 18px}
#logo{width:28px;height:28px;background:#E8421B;border-radius:7px;
  display:flex;align-items:center;justify-content:center;font-weight:900;font-size:.8rem;flex-shrink:0}
#title{font-size:.95rem;font-weight:600;letter-spacing:.4px}
#clock{font-size:1.1rem;font-weight:700;letter-spacing:1px;margin-left:auto;font-variant-numeric:tabular-nums}
#status{font-size:.72rem;color:#8b949e}
#refresh-btn{background:none;border:1px solid #30363d;color:#8b949e;
  padding:5px 12px;border-radius:6px;cursor:pointer;font-size:.75rem;flex-shrink:0}
#refresh-btn:hover{border-color:#E8421B;color:#e6edf3}

/* Hat filtresi */
#legend{position:absolute;bottom:24px;left:16px;z-index:1000;
  background:rgba(13,17,23,.88);backdrop-filter:blur(8px);
  border:1px solid #30363d;border-radius:12px;padding:12px 14px;min-width:130px}
#legend-title{font-size:.65rem;text-transform:uppercase;letter-spacing:1px;
  color:#8b949e;margin-bottom:10px}
.leg{display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer;border-radius:4px;
  transition:opacity .2s;user-select:none}
.leg:hover{opacity:.8}
.leg.off{opacity:.3}
.leg-dot{width:11px;height:11px;border-radius:50%;flex-shrink:0}
.leg-name{font-size:.8rem;font-weight:600}

/* Tren popup override */
.leaflet-popup-content-wrapper{background:#161b22;border:1px solid #30363d;color:#e6edf3;border-radius:10px;box-shadow:0 8px 32px rgba(0,0,0,.5)}
.leaflet-popup-tip{background:#161b22}
.leaflet-popup-content{margin:12px 14px;font-family:'Segoe UI',system-ui,sans-serif}
.leaflet-tooltip{background:rgba(13,17,23,.9);border:1px solid #30363d;color:#e6edf3;font-size:.72rem;padding:3px 8px;border-radius:5px}
.leaflet-tooltip::before{border-top-color:#30363d}
</style>
</head>
<body>
<div id="topbar">
  <div id="logo">M</div>
  <span id="title">Metro İstanbul</span>
  <span id="status">Yükleniyor...</span>
  <span id="clock"></span>
  <button id="refresh-btn">↻ Yenile</button>
</div>

<div id="map"></div>

<div id="legend">
  <div id="legend-title">Hatlar</div>
  <div id="legend-items"></div>
</div>

<script>
// ── Harita ────────────────────────────────────────────────────────────────────
const map = L.map("map",{zoomControl:false,attributionControl:false})
              .setView([41.02,28.97],11);

L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  {maxZoom:18,subdomains:"abcd"}).addTo(map);

L.control.zoom({position:"bottomright"}).addTo(map);

// ── Durum ─────────────────────────────────────────────────────────────────────
const hatKatman = {};          // hat adı → {poly, stMarkers}
const trenMarker = {};         // tren id → L.circleMarker
let   trenData   = [];         // son API verisi
let   gizli      = new Set();  // gizli hatlar
let   animFrame  = null;
let   lastFetch  = 0;

// ── Saat ─────────────────────────────────────────────────────────────────────
function saatGuncelle(){
  const now=new Date();
  document.getElementById("clock").textContent=
    now.toLocaleTimeString("tr-TR",{hour:"2-digit",minute:"2-digit",second:"2-digit"});
}
setInterval(saatGuncelle,1000); saatGuncelle();

// ── Hatları çiz ───────────────────────────────────────────────────────────────
async function hatlarYukle(){
  const hatlar=await fetch("/api/hatlar").then(r=>r.json());

  // Legend
  const leg=document.getElementById("legend-items");
  leg.innerHTML=hatlar.map(h=>`
    <div class="leg" data-hat="${h.name}" onclick="hatToggle('${h.name}')">
      <div class="leg-dot" style="background:${h.renk}"></div>
      <span class="leg-name">${h.name}</span>
    </div>`).join("");

  hatlar.forEach(h=>{
    const coords=h.istasyonlar.filter(s=>s.lat&&s.lon).map(s=>[s.lat,s.lon]);
    if(coords.length<2) return;

    const poly=L.polyline(coords,{color:h.renk,weight:3.5,opacity:.8}).addTo(map);

    const stMarkers=h.istasyonlar.filter(s=>s.lat&&s.lon).map(st=>{
      const m=L.circleMarker([st.lat,st.lon],{
        radius:3.5,color:h.renk,fillColor:"#0d1117",fillOpacity:1,weight:2
      }).addTo(map);
      m.bindTooltip(st.name,{direction:"top",offset:[0,-4]});
      return m;
    });

    hatKatman[h.name]={poly,stMarkers,renk:h.renk};
  });
}

function hatToggle(hat){
  const el=document.querySelector(`.leg[data-hat="${hat}"]`);
  const k=hatKatman[hat];
  if(!k) return;
  if(gizli.has(hat)){
    gizli.delete(hat);
    k.poly.addTo(map);
    k.stMarkers.forEach(m=>m.addTo(map));
    el.classList.remove("off");
  } else {
    gizli.add(hat);
    map.removeLayer(k.poly);
    k.stMarkers.forEach(m=>map.removeLayer(m));
    el.classList.add("off");
  }
  // Gizli hata ait tren markerlarını gizle/göster
  trenData.forEach(t=>{
    const mk=trenMarker[t.id];
    if(!mk) return;
    if(gizli.has(t.hat)) map.removeLayer(mk);
    else mk.addTo(map);
  });
}

// ── Tren marker oluştur ───────────────────────────────────────────────────────
function trenMarkerOlustur(t){
  const mk=L.circleMarker([t.lat,t.lon],{
    radius:7,color:"#fff",fillColor:t.renk,fillOpacity:1,weight:2,
    className:"tren-marker"
  });
  mk.bindPopup(`
    <div style="min-width:160px">
      <div style="display:flex;align-items:center;gap:7px;margin-bottom:6px">
        <span style="width:11px;height:11px;border-radius:50%;background:${t.renk};display:inline-block;flex-shrink:0"></span>
        <strong>${t.hat}</strong>
        <span style="margin-left:auto;font-size:.72rem;color:#8b949e">${t.kalkis}</span>
      </div>
      <div style="font-size:.85rem">${t.nereden}</div>
      <div style="font-size:.75rem;color:#8b949e;margin:3px 0">▼ son durak</div>
      <div style="font-size:.85rem">${t.nereye}</div>
      <div style="margin-top:8px;height:4px;background:#30363d;border-radius:2px">
        <div style="height:100%;width:${t.yuzde}%;background:${t.renk};border-radius:2px"></div>
      </div>
    </div>`);
  if(!gizli.has(t.hat)) mk.addTo(map);
  return mk;
}

// ── API'den tren verisi çek ───────────────────────────────────────────────────
async function trenlerCek(){
  document.getElementById("status").textContent="Güncelleniyor...";
  try{
    const veri=await fetch("/api/trenler").then(r=>r.json());
    lastFetch=Date.now();

    // Eski markerları temizle
    Object.values(trenMarker).forEach(m=>{ try{map.removeLayer(m)}catch(e){} });
    Object.keys(trenMarker).forEach(k=>delete trenMarker[k]);

    trenData=veri.trenler;
    trenData.forEach(t=>{
      trenMarker[t.id]=trenMarkerOlustur(t);
    });

    document.getElementById("status").textContent=
      `${veri.tren_sayisi} aktif tren · ${veri.tarih}`;
  } catch(e){
    document.getElementById("status").textContent="Bağlantı hatası";
  }
}

// ── Animasyon: saniyede bir trenleri ilerlet ──────────────────────────────────
function animasyon(){
  const gecenSn=(Date.now()-lastFetch)/1000;

  trenData.forEach(t=>{
    const mk=trenMarker[t.id];
    if(!mk||gizli.has(t.hat)) return;

    const hiz=1/t.kalan_sn;               // 0→1 arası / saniye
    const yeni_pct=Math.min(t.yuzde/100 + hiz*gecenSn, 0.99);
    const lat=t.lat+(t.lat2-t.lat)*(yeni_pct-(t.yuzde/100))/(1-t.yuzde/100+0.001);
    const lon=t.lon+(t.lon2-t.lon)*(yeni_pct-(t.yuzde/100))/(1-t.yuzde/100+0.001);

    if(isFinite(lat)&&isFinite(lon)){
      mk.setLatLng([lat,lon]);
    }
  });

  animFrame=requestAnimationFrame(animasyon);
}

// ── Otomatik yenileme (60 sn) ─────────────────────────────────────────────────
function baslat(){
  hatlarYukle().then(()=>{
    trenlerCek();
    setInterval(trenlerCek, 60000);
    animasyon();
  });
}

document.getElementById("refresh-btn").addEventListener("click",trenlerCek);

baslat();
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

if __name__=="__main__":
    import os
    port=int(os.environ.get("PORT",5000))
    print(f"\n  Metro İstanbul Board → http://localhost:{port}\n")
    app.run(debug=False,host="0.0.0.0",port=port)
