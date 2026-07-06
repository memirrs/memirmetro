"""
Metro İstanbul Web Uygulaması
==============================
Kurulum : pip install flask requests
Çalıştır: python metro_app.py
Tarayıcı: http://localhost:5000
"""

import re
from datetime import datetime, timedelta
from collections import Counter
from flask import Flask, jsonify, request, render_template_string
import requests as req
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

IBB_BASE = "https://api.ibb.gov.tr/MetroIstanbul/api/MetroMobile/V2"
AJAX_URL = "https://www.metro.istanbul/SeferDurumlari/AJAXSeferGetir"
PAGE_URL = "https://www.metro.istanbul/SeferDurumlari/SeferDetaylari"
HAT_URL  = "https://www.metro.istanbul/Hatlarimiz/HatDetay?hat={}"

# ── Hat renkleri ──────────────────────────────────────────────────────────────
HAT_RENKLERI = {
    "M1A": "#E8421B", "M1B": "#E8421B",
    "M2":  "#D01F2D",
    "M3":  "#F47920",
    "M4":  "#0072BC",
    "M5":  "#8B1A8B",
    "M6":  "#00A651",
    "M7":  "#F7A800",
    "M8":  "#00AEEF",
    "M9":  "#E31E24",
    "F1":  "#6D4C41", "F4": "#6D4C41",
    "T1":  "#009B3A", "T3": "#009B3A", "T4": "#009B3A", "T5": "#009B3A",
    "TF1": "#795548", "TF2": "#795548",
}

# ── Yardımcılar ───────────────────────────────────────────────────────────────

def ibb_get(ep):
    r = req.get(f"{IBB_BASE}/{ep}", headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    return r.json().get("Data", [])

def yeni_session():
    s = req.Session()
    s.verify = False
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    return s

def kod_cek(session):
    r = session.get(PAGE_URL, timeout=15)
    r.raise_for_status()
    m = re.search(
        r'formData\.append\(\s*["\']kod["\']\s*,\s*["\']'
        r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})["\']',
        r.text, re.IGNORECASE)
    return m.group(1) if m else None

def tarife_cek(session, station_id, route_id, tarih, kod):
    r = session.post(AJAX_URL, data={
        "secim": "0", "saat": "", "dakika": "",
        "tarih1": "", "tarih2": tarih,
        "station": str(station_id), "route": str(route_id), "kod": kod,
    }, headers={"Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest", "Referer": PAGE_URL}, timeout=15)
    r.raise_for_status()
    try:
        veri = r.json()
    except Exception:
        return []
    if isinstance(veri, dict) and str(veri.get("durum")) == "-1":
        return []
    return veri.get("sefer", []) if isinstance(veri, dict) else (veri or [])

def saat_to_min(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m

def saat_to_dt(saat_str, baz):
    h, m = map(int, saat_str.split(":"))
    dt = baz.replace(hour=h, minute=m, second=0, microsecond=0)
    if h < 4 and baz.hour > 20:
        dt += timedelta(days=1)
    return dt

def hat_suresi(session, hat_adi):
    try:
        r = session.get(HAT_URL.format(hat_adi), timeout=10)
        m = re.search(r'(?:sefer|seyahat)\s+s.resi\s*[:\-]\s*([\d,\.]+)\s*dakika',
                      r.text, re.IGNORECASE)
        if m:
            return int(float(m.group(1).replace(",", ".")))
    except Exception:
        pass
    return None

def yolculuk_suresi(session, bas_id, bitis_id, route_id, tarih, hat_adi):
    sure = hat_suresi(session, hat_adi)
    if sure:
        return sure

    kod = kod_cek(session)
    bas_raw = tarife_cek(session, bas_id, route_id, tarih, kod)
    kod = kod_cek(session)
    bit_raw = tarife_cek(session, bitis_id, route_id, tarih, kod)
    if not bas_raw or not bit_raw:
        return None

    bas_min = sorted({saat_to_min(s["zaman"]) for s in bas_raw})
    bit_set  = {saat_to_min(s["zaman"]) for s in bit_raw}
    best_T, best_n = None, 0
    for T in range(15, 76):
        n = sum(1 for b in bas_min if (b+T-1) in bit_set or (b+T) in bit_set or (b+T+1) in bit_set)
        if n > best_n:
            best_n, best_T = n, T
    return best_T

# ── API uç noktaları ──────────────────────────────────────────────────────────

@app.route("/api/lines")
def api_lines():
    lines = ibb_get("GetLines")
    for l in lines:
        l["renk"] = HAT_RENKLERI.get(l.get("Name", ""), "#555")
    return jsonify(lines)

@app.route("/api/directions/<int:line_id>")
def api_directions(line_id):
    return jsonify(ibb_get(f"GetDirectionById/{line_id}"))

@app.route("/api/stations/<int:line_id>")
def api_stations(line_id):
    return jsonify(ibb_get(f"GetStationById/{line_id}"))

@app.route("/api/sonraki-tren", methods=["POST"])
def api_sonraki_tren():
    data       = request.json
    station_id = data["station_id"]
    route_id   = data["route_id"]
    saat_str   = data.get("saat", "")

    session = yeni_session()
    bugun   = datetime.today()
    tarih   = bugun.strftime("%d.%m.%Y")

    if saat_str:
        try:
            h, m = map(int, saat_str.split(":"))
            simdi = bugun.replace(hour=h, minute=m, second=0, microsecond=0)
        except Exception:
            simdi = bugun
    else:
        simdi = bugun

    kod      = kod_cek(session)
    seferler = tarife_cek(session, station_id, route_id, tarih, kod)

    sonraki = []
    for s in seferler:
        dt   = saat_to_dt(s["zaman"], bugun)
        if dt >= simdi:
            dk = int((dt - simdi).total_seconds() / 60)
            sonraki.append({"saat": s["zaman"], "dk": dk})

    gun_adi = ["Pzt","Sal","Çar","Per","Cum","Cmt","Paz"][bugun.weekday()]
    return jsonify({
        "sonraki": sonraki[:8],
        "toplam_kalan": len(sonraki),
        "son_sefer": seferler[-1]["zaman"] if seferler else "-",
        "simdi": simdi.strftime("%H:%M"),
        "tarih": f"{tarih} {gun_adi}",
    })

@app.route("/api/canli-konum", methods=["POST"])
def api_canli_konum():
    data       = request.json
    line_id    = data["line_id"]
    hat_adi    = data["hat_adi"]
    route_id   = data["route_id"]
    yon_adi    = data["yon_adi"]
    saat_str   = data.get("saat", "")

    session     = yeni_session()
    bugun       = datetime.today()
    tarih       = bugun.strftime("%d.%m.%Y")
    istasyonlar = ibb_get(f"GetStationById/{line_id}")

    parcalar  = yon_adi.split("->")
    bas_adi   = parcalar[0].strip().upper().split()[0]
    bitis_adi = parcalar[1].strip().upper().split()[0] if len(parcalar) > 1 else ""
    bas_st    = next((s for s in istasyonlar if bas_adi   in s["Name"].upper()), istasyonlar[0])
    bitis_st  = next((s for s in istasyonlar if bitis_adi in s["Name"].upper()), istasyonlar[-1])

    if saat_str:
        try:
            h, m = map(int, saat_str.split(":"))
            simdi = bugun.replace(hour=h, minute=m, second=0, microsecond=0)
        except Exception:
            simdi = bugun
    else:
        simdi = bugun

    toplam_sure = yolculuk_suresi(session, bas_st["Id"], bitis_st["Id"],
                                   route_id, tarih, hat_adi)
    if toplam_sure is None:
        toplam_sure = (len(istasyonlar) - 1) * 2.5

    kod      = kod_cek(session)
    seferler = tarife_cek(session, bas_st["Id"], route_id, tarih, kod)
    if not seferler:
        return jsonify({"aktif": [], "hata": "Sefer bulunamadı."})

    seferler_dt = sorted({saat_to_dt(s["zaman"], bugun) for s in seferler})
    n           = len(istasyonlar)
    dk_basi     = toplam_sure / (n - 1)
    sure        = [i * dk_basi for i in range(n)]

    aktif = []
    for kalkis in seferler_dt:
        bitis_dt = kalkis + timedelta(minutes=toplam_sure)
        if kalkis > simdi or bitis_dt < simdi:
            continue
        gecen = (simdi - kalkis).total_seconds() / 60
        for i in range(n - 1):
            if sure[i] <= gecen < sure[i + 1]:
                kalan = max(1, round(sure[i + 1] - gecen))
                aktif.append({
                    "kalkis"   : kalkis.strftime("%H:%M"),
                    "nereden"  : istasyonlar[i]["Name"].title(),
                    "nereye"   : istasyonlar[i + 1]["Name"].title(),
                    "kalan_dk" : kalan,
                    "yuzde"    : int((gecen - sure[i]) / (sure[i+1] - sure[i]) * 100),
                })
                break

    gun_adi = ["Pzt","Sal","Çar","Per","Cum","Cmt","Paz"][bugun.weekday()]
    return jsonify({
        "aktif"        : sorted(aktif, key=lambda x: x["kalkis"]),
        "toplam_sure"  : toplam_sure,
        "simdi"        : simdi.strftime("%H:%M"),
        "tarih"        : f"{tarih} {gun_adi}",
    })

# ── HTML arayüzü ──────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Metro İstanbul</title>
<style>
  :root {
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --accent: #E8421B;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }

  header { padding: 20px 24px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 1.1rem; font-weight: 600; letter-spacing: .5px; }
  .logo { width: 32px; height: 32px; background: var(--accent); border-radius: 8px;
          display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: .9rem; }

  .container { max-width: 720px; margin: 0 auto; padding: 24px 16px; }

  /* Steps */
  .steps { display: flex; gap: 8px; margin-bottom: 28px; flex-wrap: wrap; }
  .step { font-size: .7rem; color: var(--muted); padding: 4px 10px; border-radius: 20px;
          border: 1px solid var(--border); white-space: nowrap; }
  .step.active { color: var(--text); border-color: var(--accent); background: rgba(232,66,27,.1); }
  .step.done   { color: var(--accent); border-color: var(--accent); }

  /* Panels */
  .panel { display: none; }
  .panel.visible { display: block; }

  .panel-title { font-size: .75rem; text-transform: uppercase; letter-spacing: 1px;
                 color: var(--muted); margin-bottom: 14px; }

  /* Buton ızgarası */
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 10px; }
  .grid.wide { grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); }

  .btn {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 14px 12px;
    border-radius: 10px;
    cursor: pointer;
    font-size: .9rem;
    font-weight: 600;
    text-align: center;
    transition: border-color .15s, transform .1s;
    display: flex; flex-direction: column; align-items: center; gap: 6px;
  }
  .btn:hover { border-color: #555; transform: translateY(-1px); }
  .btn .dot { width: 10px; height: 10px; border-radius: 50%; }
  .btn .sub { font-size: .7rem; font-weight: 400; color: var(--muted); }

  .btn-feature {
    padding: 18px 20px;
    border-radius: 12px;
    gap: 8px;
  }
  .btn-feature .icon { font-size: 1.6rem; }
  .btn-feature .label { font-size: .95rem; font-weight: 600; }
  .btn-feature .desc  { font-size: .75rem; color: var(--muted); font-weight: 400; }

  .btn-yon {
    padding: 16px;
    font-size: .85rem;
    text-align: left;
    flex-direction: row;
    justify-content: flex-start;
  }

  /* Saat girişi */
  .saat-row { display: flex; gap: 10px; align-items: center; margin-bottom: 18px; }
  .saat-row input {
    background: var(--surface); border: 1px solid var(--border); color: var(--text);
    padding: 10px 14px; border-radius: 8px; font-size: .9rem; width: 110px;
  }
  .saat-row label { font-size: .8rem; color: var(--muted); }
  .saat-row .go-btn {
    padding: 10px 18px; border-radius: 8px; background: var(--accent);
    border: none; color: #fff; font-size: .85rem; font-weight: 600; cursor: pointer;
  }

  /* Geri butonu */
  .back { font-size: .8rem; color: var(--muted); cursor: pointer; margin-bottom: 20px;
          display: inline-flex; align-items: center; gap: 6px; }
  .back:hover { color: var(--text); }

  /* Seçili bilgi şeridi */
  .breadcrumb { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }
  .chip { font-size: .75rem; padding: 4px 10px; border-radius: 20px;
          background: rgba(255,255,255,.07); color: var(--muted); }
  .chip.colored { color: var(--text); }

  /* Yükleniyor */
  .loader { text-align: center; padding: 40px; color: var(--muted); }
  .spinner { display: inline-block; width: 28px; height: 28px; border: 3px solid var(--border);
             border-top-color: var(--accent); border-radius: 50%; animation: spin .7s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Sonuçlar - sonraki tren */
  .tren-list { display: flex; flex-direction: column; gap: 8px; }
  .tren-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 14px 16px; display: flex; align-items: center; gap: 14px;
  }
  .tren-card.ilk { border-color: var(--accent); background: rgba(232,66,27,.06); }
  .tren-card .saat { font-size: 1.25rem; font-weight: 700; min-width: 52px; }
  .tren-card .bekleme { font-size: .85rem; color: var(--muted); }
  .tren-card .badge {
    margin-left: auto; font-size: .72rem; font-weight: 600; padding: 3px 9px;
    border-radius: 20px; background: var(--accent); color: #fff;
  }

  /* Sonuçlar - canlı konum */
  .konum-list { display: flex; flex-direction: column; gap: 10px; }
  .konum-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px;
  }
  .konum-card .row1 { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
  .konum-card .kalkis-badge { font-size: .72rem; padding: 2px 8px; border-radius: 20px;
                               border: 1px solid var(--border); color: var(--muted); }
  .konum-card .kalan { margin-left: auto; font-size: .8rem; color: var(--muted); }
  .konum-card .seg { display: flex; align-items: center; gap: 8px; font-size: .9rem; }
  .konum-card .ok { color: var(--accent); font-size: 1rem; }
  .progress-bar { height: 4px; background: var(--border); border-radius: 2px; margin-top: 8px; overflow: hidden; }
  .progress-fill { height: 100%; border-radius: 2px; background: var(--accent); transition: width .3s; }

  .meta-row { margin-top: 24px; padding: 12px; border-radius: 8px; background: var(--surface);
              border: 1px solid var(--border); font-size: .78rem; color: var(--muted);
              display: flex; gap: 16px; flex-wrap: wrap; }

  .empty { text-align: center; padding: 40px; color: var(--muted); }

  /* Responsive */
  @media (max-width: 480px) {
    .grid { grid-template-columns: repeat(3, 1fr); }
    .grid.wide { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>

<header>
  <div class="logo">M</div>
  <h1>Metro İstanbul</h1>
</header>

<div class="container">

  <!-- Adım göstergesi -->
  <div class="steps">
    <div class="step active" id="step-hat">Hat</div>
    <div class="step" id="step-ozellik">Özellik</div>
    <div class="step" id="step-yon">Yön</div>
    <div class="step" id="step-sonuc">Sonuç</div>
  </div>

  <!-- Panel 1: Hat seç -->
  <div class="panel visible" id="panel-hat">
    <div class="panel-title">Hat seçin</div>
    <div class="grid" id="hat-grid">
      <div class="loader"><div class="spinner"></div></div>
    </div>
  </div>

  <!-- Panel 2: Özellik seç -->
  <div class="panel" id="panel-ozellik">
    <div class="back" onclick="geri('hat')">← Geri</div>
    <div class="breadcrumb" id="bc-ozellik"></div>
    <div class="panel-title">Ne yapmak istiyorsunuz?</div>
    <div class="grid wide">
      <div class="btn btn-feature" onclick="ozellikSec('sonraki')">
        <div class="icon">🕐</div>
        <div class="label">Sonraki Tren</div>
        <div class="desc">Bir durakta treni kaçta bekleyeyim?</div>
      </div>
      <div class="btn btn-feature" onclick="ozellikSec('konum')">
        <div class="icon">🗺️</div>
        <div class="label">Anlık Konum</div>
        <div class="desc">Hatta trenler şu an nerede?</div>
      </div>
    </div>
  </div>

  <!-- Panel 3a: Yön seç (+ durak seç, sonraki tren için) -->
  <div class="panel" id="panel-yon-sonraki">
    <div class="back" onclick="geri('ozellik')">← Geri</div>
    <div class="breadcrumb" id="bc-yon-sonraki"></div>
    <div class="panel-title">Yön seçin</div>
    <div class="grid wide" id="yon-sonraki-grid"></div>

    <div id="durak-blok" style="display:none; margin-top:24px;">
      <div class="panel-title">Durak seçin</div>
      <div class="saat-row">
        <label>Saat (boş = şimdi)</label>
        <input type="time" id="saat-sonraki" placeholder="14:23">
      </div>
      <div class="grid wide" id="durak-grid"></div>
    </div>
  </div>

  <!-- Panel 3b: Yön seç (anlık konum için) -->
  <div class="panel" id="panel-yon-konum">
    <div class="back" onclick="geri('ozellik')">← Geri</div>
    <div class="breadcrumb" id="bc-yon-konum"></div>
    <div class="panel-title">Yön seçin</div>
    <div class="grid wide" id="yon-konum-grid"></div>

    <div id="saat-blok-konum" style="display:none; margin-top:24px;">
      <div class="panel-title">Saat</div>
      <div class="saat-row">
        <label>Saat (boş = şimdi)</label>
        <input type="time" id="saat-konum" placeholder="14:23">
        <button class="go-btn" onclick="konumSorgula()">Göster</button>
      </div>
    </div>
  </div>

  <!-- Panel 4: Sonuçlar -->
  <div class="panel" id="panel-sonuc">
    <div class="back" onclick="geri('yon')">← Geri</div>
    <div class="breadcrumb" id="bc-sonuc"></div>
    <div id="sonuc-icerik">
      <div class="loader"><div class="spinner"></div></div>
    </div>
  </div>

</div>

<script>
// ── Durum ─────────────────────────────────────────────────────────────────────
const S = { hat: null, ozellik: null, yon: null, istasyon: null };

// ── Panel yönetimi ────────────────────────────────────────────────────────────
function goster(id) {
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("visible"));
  document.getElementById("panel-" + id).classList.add("visible");

  // Adım göstergesi
  const asamalar = ["hat","ozellik","yon","sonuc"];
  const aktif = {
    "hat": 0, "ozellik": 1,
    "yon-sonraki": 2, "yon-konum": 2,
    "sonuc": 3
  }[id] ?? 0;
  asamalar.forEach((a, i) => {
    const el = document.getElementById("step-" + a);
    el.className = "step" + (i < aktif ? " done" : i === aktif ? " active" : "");
  });
}

function geri(hedef) {
  if (hedef === "hat")     goster("hat");
  if (hedef === "ozellik") goster("ozellik");
  if (hedef === "yon") {
    if (S.ozellik === "sonraki") goster("yon-sonraki");
    else goster("yon-konum");
  }
}

// ── Breadcrumb ────────────────────────────────────────────────────────────────
function breadcrumb(elId, parçalar) {
  document.getElementById(elId).innerHTML = parçalar.map(p =>
    `<span class="chip colored" style="border-color:${p.renk||'#555'}; color:${p.renk||'#ccc'}">${p.text}</span>`
  ).join('');
}

// ── Veri depolar (onclick içinde JSON yerine ID kullanmak için) ──────────────
const HAT_MAP = {}, YON_MAP = {}, ST_MAP = {};

async function get(url) {
  const r = await fetch(url);
  return r.json();
}
async function post(url, data) {
  const r = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data)});
  return r.json();
}

// ── Panel 1: Hatlar ───────────────────────────────────────────────────────────
async function yukleHatlar() {
  const hatlar = await get("/api/lines");
  hatlar.forEach(h => { HAT_MAP[h.Id] = h; });
  const grid = document.getElementById("hat-grid");
  grid.innerHTML = hatlar.map(h => `
    <div class="btn" data-id="${h.Id}" title="${h.Name}">
      <div class="dot" style="background:${h.renk}"></div>
      <span>${h.Name}</span>
    </div>
  `).join("");
  grid.querySelectorAll(".btn").forEach(btn =>
    btn.addEventListener("click", () => hatSec(HAT_MAP[btn.dataset.id]))
  );
}

function hatSec(hat) {
  S.hat = hat;
  breadcrumb("bc-ozellik", [{text: hat.Name, renk: hat.renk}]);
  goster("ozellik");
}

// ── Panel 2: Özellik ───────────────────────────────────────────────────────────
function ozellikSec(ozellik) {
  S.ozellik = ozellik;
  if (ozellik === "sonraki") yukleYonlarSonraki();
  else yukleYonlarKonum();
}

// ── Panel 3a: Yön (sonraki tren) ──────────────────────────────────────────────
async function yukleYonlarSonraki() {
  breadcrumb("bc-yon-sonraki", [
    {text: S.hat.Name, renk: S.hat.renk},
    {text: "Sonraki Tren"}
  ]);
  goster("yon-sonraki");
  document.getElementById("durak-blok").style.display = "none";

  const yonler = await get("/api/directions/" + S.hat.Id);
  yonler.forEach(y => { YON_MAP[y.DirectionId] = y; });
  const grid1 = document.getElementById("yon-sonraki-grid");
  grid1.innerHTML = yonler.map(y => `
    <div class="btn btn-yon" data-id="${y.DirectionId}">
      <span style="color:${S.hat.renk}">&#x2192;</span>
      <span>${y.DirectionName}</span>
    </div>
  `).join("");
  grid1.querySelectorAll(".btn").forEach(btn =>
    btn.addEventListener("click", () => yonSonrakiSec(YON_MAP[btn.dataset.id]))
  );
}

async function yonSonrakiSec(yon) {
  S.yon = yon;
  document.getElementById("durak-blok").style.display = "block";
  document.getElementById("durak-grid").innerHTML = '<div class="loader"><div class="spinner"></div></div>';

  const istasyonlar = await get("/api/stations/" + S.hat.Id);
  istasyonlar.forEach(st => { ST_MAP[st.Id] = st; });
  const dgrid = document.getElementById("durak-grid");
  dgrid.innerHTML = istasyonlar.map(st => {
    const ad = st.Name.split(" ").map(w => w.charAt(0)+w.slice(1).toLowerCase()).join(" ");
    return `<div class="btn" style="font-size:.82rem" data-id="${st.Id}">${ad}</div>`;
  }).join("");
  dgrid.querySelectorAll(".btn").forEach(btn =>
    btn.addEventListener("click", () => istasyonSec(ST_MAP[btn.dataset.id]))
  );
}

async function istasyonSec(istasyon) {
  S.istasyon = istasyon;
  const saat = document.getElementById("saat-sonraki").value;

  breadcrumb("bc-sonuc", [
    {text: S.hat.Name, renk: S.hat.renk},
    {text: S.istasyon.Name.split(" ").map(w=>w.charAt(0)+w.slice(1).toLowerCase()).join(" ")},
    {text: S.yon.DirectionName}
  ]);
  goster("sonuc");

  const sonucEl = document.getElementById("sonuc-icerik");
  sonucEl.innerHTML = '<div class="loader"><div class="spinner"></div></div>';

  const veri = await post("/api/sonraki-tren", {
    station_id: S.istasyon.Id,
    route_id: S.yon.DirectionId,
    saat: saat
  });

  if (!veri.sonraki || veri.sonraki.length === 0) {
    sonucEl.innerHTML = '<div class="empty">Bu saatte sefer bulunamadı.<br>Son sefer: ' + veri.son_sefer + '</div>';
    return;
  }

  const trenler = veri.sonraki.map((t, i) => `
    <div class="tren-card ${i===0?'ilk':''}">
      <div class="saat">${t.saat}</div>
      <div class="bekleme">${t.dk === 0 ? 'Şimdi geliyor' : t.dk + ' dakika sonra'}</div>
      ${i===0 ? '<div class="badge">En yakın</div>' : ''}
    </div>
  `).join("");

  sonucEl.innerHTML = `
    <div class="meta-row" style="margin-bottom:14px">
      <span>🕐 ${veri.simdi}</span>
      <span>📅 ${veri.tarih}</span>
      <span>Kalan ${veri.toplam_kalan} sefer · Son: ${veri.son_sefer}</span>
    </div>
    <div class="tren-list">${trenler}</div>
  `;
}

// ── Panel 3b: Yön (anlık konum) ───────────────────────────────────────────────
async function yukleYonlarKonum() {
  breadcrumb("bc-yon-konum", [
    {text: S.hat.Name, renk: S.hat.renk},
    {text: "Anlık Konum"}
  ]);
  goster("yon-konum");
  document.getElementById("saat-blok-konum").style.display = "none";

  const yonler = await get("/api/directions/" + S.hat.Id);
  yonler.forEach(y => { YON_MAP[y.DirectionId] = y; });
  const grid2 = document.getElementById("yon-konum-grid");
  grid2.innerHTML = yonler.map(y => `
    <div class="btn btn-yon" data-id="${y.DirectionId}">
      <span style="color:${S.hat.renk}">&#x2192;</span>
      <span>${y.DirectionName}</span>
    </div>
  `).join("");
  grid2.querySelectorAll(".btn").forEach(btn =>
    btn.addEventListener("click", () => yonKonumSec(YON_MAP[btn.dataset.id]))
  );
}

function yonKonumSec(yon) {
  S.yon = yon;
  document.getElementById("saat-blok-konum").style.display = "block";
}

async function konumSorgula() {
  const saat = document.getElementById("saat-konum").value;
  breadcrumb("bc-sonuc", [
    {text: S.hat.Name, renk: S.hat.renk},
    {text: S.yon.DirectionName},
    {text: "Anlık Konum"}
  ]);
  goster("sonuc");

  const sonucEl = document.getElementById("sonuc-icerik");
  sonucEl.innerHTML = '<div class="loader"><div class="spinner"></div></div>';

  const veri = await post("/api/canli-konum", {
    line_id: S.hat.Id,
    hat_adi: S.hat.Name,
    route_id: S.yon.DirectionId,
    yon_adi: S.yon.DirectionName,
    saat: saat
  });

  if (!veri.aktif || veri.aktif.length === 0) {
    sonucEl.innerHTML = '<div class="empty">Bu saatte aktif tren yok.</div>';
    return;
  }

  const konumlar = veri.aktif.map(t => `
    <div class="konum-card">
      <div class="row1">
        <span class="kalkis-badge">Kalkış ${t.kalkis}</span>
        <span class="kalan">~${t.kalan_dk} dk sonra varır</span>
      </div>
      <div class="seg">
        <span>${t.nereden}</span>
        <span class="ok">→</span>
        <span>${t.nereye}</span>
      </div>
      <div class="progress-bar">
        <div class="progress-fill" style="width:${t.yuzde}%"></div>
      </div>
    </div>
  `).join("");

  sonucEl.innerHTML = `
    <div class="meta-row" style="margin-bottom:14px">
      <span>🕐 ${veri.simdi}</span>
      <span>📅 ${veri.tarih}</span>
      <span>Aktif tren: ${veri.aktif.length} · Yolculuk ~${veri.toplam_sure} dk</span>
    </div>
    <div class="konum-list">${konumlar}</div>
  `;
}

// ── Başlat ────────────────────────────────────────────────────────────────────
yukleHatlar();
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Metro İstanbul başlatılıyor → http://localhost:{port}\n")
    app.run(debug=False, host="0.0.0.0", port=port)
