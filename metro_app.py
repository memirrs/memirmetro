"""
Metro İstanbul Web Uygulaması v2 — Canlı Harita
================================================
Kurulum : pip install flask requests
Çalıştır: python metro_app.py
Tarayıcı: http://localhost:5000
"""

import re, time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, request, render_template_string
import requests as req
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ── Sabitler ──────────────────────────────────────────────────────────────────
IBB_BASE  = "https://api.ibb.gov.tr/MetroIstanbul/api/MetroMobile/V2"
AJAX_URL  = "https://www.metro.istanbul/SeferDurumlari/AJAXSeferGetir"
PAGE_URL  = "https://www.metro.istanbul/SeferDurumlari/SeferDetaylari"
HAT_URL   = "https://www.metro.istanbul/Hatlarimiz/HatDetay?hat={}"
OVERPASS  = "https://overpass-api.de/api/interpreter"

METRO_HATLARI = {"M1A","M1B","M2","M3","M4","M5","M6","M7","M8","M9"}

HAT_RENKLERI = {
    "M1A":"#E8421B","M1B":"#E8421B",
    "M2":"#D01F2D","M3":"#F47920","M4":"#0072BC",
    "M5":"#8B1A8B","M6":"#00A651","M7":"#F7A800",
    "M8":"#00AEEF","M9":"#E31E24",
}


# ── Hardcoded koordinatlar (Overpass yedek) ───────────────────────────────────
HARDCODED_COORDS = {
    # M2
    "YENIKAPI":(41.0045,28.9501),"VEZNECILER":(41.0168,28.9598),
    "HALIC":(41.0285,28.9498),"SISHANE":(41.0342,28.9748),
    "TAKSIM":(41.0369,28.9850),"OSMANBEY":(41.0462,28.9878),
    "SISLIMECIDIYEKOY":(41.0598,28.9872),"GAYRETTEPE":(41.0687,28.9960),
    "LEVENT":(41.0799,29.0098),"4LEVENT":(41.0880,29.0128),
    "SANAYIMAHALLESI":(41.0984,29.0202),"SEYRANTEPE":(41.1073,29.0228),
    "ITUAYAZAGA":(41.1165,29.0218),"ATATURKOTOSANAYI":(41.1233,29.0143),
    "DARUSSAFAKA":(41.1339,29.0099),"HACIOSMAN":(41.1402,28.9973),
    # M4
    "KADIKOY":(40.9902,29.0246),"AYRILIKCESMESI":(41.0031,29.0305),
    "ACIBADEM":(41.0108,29.0423),"UNALAN":(41.0097,29.0566),
    "GOZTEPE":(40.9846,29.0679),"YENISAHRA":(40.9771,29.0773),
    "KOZYATAGI":(40.9769,29.0893),"BOSTANCI":(40.9649,29.1003),
    "KUCUKYALI":(40.9582,29.1257),"MALTEPE":(40.9393,29.1357),
    "HUZUREVI":(40.9275,29.1382),"GULSUYUM4":(40.9194,29.1398),
    "ESENKENT":(40.9098,29.1532),"HASTANEADLIYE":(40.8983,29.1666),
    "SABIHAGOKCEN":(40.8982,29.2057),"TAVSANTEPE":(40.9090,29.2210),
    # M1A/M1B
    "AKSARAY":(41.0134,28.9509),"EMNIYETFATIH":(41.0168,28.9271),
    "TOPKAPIULUBATLI":(41.0196,28.9047),"BAYRAMPASAMALTEPE":(41.0421,28.9133),
    "SAGMALCILAR":(41.0534,28.8964),"KOCATEPE":(41.0598,28.8843),
    "OTOGAR":(41.0624,28.8698),"TERAZIDERE":(41.0652,28.8598),
    "DAVUTPASAYTU":(41.0620,28.8476),"MERTER":(41.0194,28.8934),
    "ZEYTINBURNU":(40.9981,28.9046),"BAKIRKOYINCIRLI":(40.9846,28.8712),
    "BAHCELIEVLER":(41.0006,28.8576),"ATAKOYSIRNEVLER":(40.9994,28.8423),
    "BAGCILAR":(41.0369,28.8543),"KIRAZLI":(41.0476,28.8196),
    # M3
    "BAGCILARMERKEZM3":(41.0402,28.8343),"ISTOC":(41.0450,28.8867),
    "MAHMUTBEY":(41.0557,28.8870),"IKELLIS":(41.0677,28.8758),
    "TURGUTOZEL":(41.0778,28.8634),"OLIMPIYAT":(41.0889,28.8456),
    "IKITELLIOSB":(41.0677,28.8758),
    # M5
    "USKUDAR":(41.0219,29.0143),"FISTIKAGACI":(41.0321,29.0345),
    "BAGLARBASIM5":(41.0251,29.0489),"ALTUNIZADE":(41.0213,29.0590),
    "KISIKLI":(41.0381,29.0700),"BULGURLU":(41.0479,29.0881),
    "UMRANIYE":(41.0340,29.1184),"CARSI":(41.0224,29.1246),
    "YAMANEVLER":(41.0209,29.1383),"CAKMAK":(41.0171,29.1560),
    "IHLAMURKUYU":(41.0126,29.1637),"ALEMDAG":(41.0067,29.1829),
    "CEKMEKOY":(41.0065,29.1912),
    # M6
    "NISPETIYE":(41.0739,29.0378),"ETILER":(41.0778,29.0478),
    "BOGAZICIUNIVERSITESI":(41.0834,29.0567),"HISARUSTU":(41.0879,29.0674),
    # M7
    "MECIDIYEKOY":(41.0680,28.9867),"CAGLAYAN":(41.0772,28.9694),
    "KAGITHANE":(41.0885,28.9627),"NURTEPE":(41.1016,28.9607),
    "ALISAMIYEN":(41.1052,28.9448),"YILDIZTEPE":(41.1090,28.9267),
    "KAZLICESME":(41.1160,28.9198),
    # M8
    "SARIGAZI":(41.0018,29.1457),"SITE":(41.0087,29.1567),
    "NENEHATUN":(41.0159,29.1618),"PARSELLER":(41.0220,29.1718),
    "YUKARIDUDULLU":(41.0312,29.1831),"DUDULLU":(41.0354,29.1840),
    # M9
    "ATAKOLYOLIMPIYAT":(40.9889,28.8235),"SIRINNEVLER":(40.9944,28.8393),
    "ATAKOYISTASYON":(40.9940,28.8310),"YENIBOSNA":(41.0011,28.8298),
    "MITHATPASA":(41.0087,28.8354),"MUSELLIMKOYU":(41.0211,28.8412),
    "GUNGOREN":(41.0299,28.8476),"IKITELLI":(41.0677,28.8758),
}
# ── Koordinat önbelleği ───────────────────────────────────────────────────────
_coord_cache      = None
_coord_cache_time = 0

def normalize(name):
    tr = str.maketrans("ğĞşŞçÇüÜöÖıİ", "gGsScCuUoOiI")
    return re.sub(r"[^A-Z0-9]", "", name.upper().translate(tr))

def get_station_coords():
    global _coord_cache, _coord_cache_time
    if _coord_cache and (time.time() - _coord_cache_time) < 3600:
        return _coord_cache

    # Hardcoded ile başla
    coords = dict(HARDCODED_COORDS)

    # Overpass ile zenginleştir (başarılı olursa)
    query = """[out:json][timeout:25];
(
  node["station"="subway"](40.80,28.50,41.35,29.55);
  node["railway"="station"]["subway"="yes"](40.80,28.50,41.35,29.55);
);
out body;"""
    try:
        r = req.post(OVERPASS, data={"data": query}, timeout=30)
        r.raise_for_status()
        nodes = r.json().get("elements", [])
        for n in nodes:
            name = n.get("tags", {}).get("name", "")
            if name:
                coords[normalize(name)] = (n["lat"], n["lon"])
    except Exception:
        pass  # Overpass başarısız → hardcoded yeterli

    _coord_cache      = coords
    _coord_cache_time = time.time()
    return coords

def match_coord(station_name, coords):
    key = normalize(station_name)
    if key in coords:
        return coords[key]
    for k, v in coords.items():
        if key in k or k in key:
            return v
    words = [w for w in key.split() if len(w) > 3]
    for w in words:
        for k, v in coords.items():
            if w in k:
                return v
    return None

# ── API yardımcıları ──────────────────────────────────────────────────────────
def ibb_get(ep):
    r = req.get(f"{IBB_BASE}/{ep}", headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    return r.json().get("Data", [])

def yeni_session():
    s = req.Session()
    s.verify = False
    s.headers.update({"User-Agent":"Mozilla/5.0"})
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
        "secim":"0","saat":"","dakika":"","tarih1":"","tarih2":tarih,
        "station":str(station_id),"route":str(route_id),"kod":kod,
    }, headers={"Accept":"application/json,*/*","X-Requested-With":"XMLHttpRequest",
                "Referer":PAGE_URL}, timeout=15)
    r.raise_for_status()
    try:
        v = r.json()
    except Exception:
        return []
    if isinstance(v, dict) and str(v.get("durum")) == "-1":
        return []
    return v.get("sefer", []) if isinstance(v, dict) else (v or [])

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
        m = re.search(r"(?:sefer|seyahat)\s+s.resi\s*[:\-]\s*([\d,\.]+)\s*dakika",
                      r.text, re.IGNORECASE)
        if m:
            return int(float(m.group(1).replace(",",".")))
    except Exception:
        pass
    return None

def yolculuk_suresi(session, bas_id, bitis_id, route_id, tarih, hat_adi):
    sure = hat_suresi(session, hat_adi)
    if sure:
        return sure
    kod = kod_cek(session)
    bas = tarife_cek(session, bas_id, route_id, tarih, kod)
    kod = kod_cek(session)
    bit = tarife_cek(session, bitis_id, route_id, tarih, kod)
    if not bas or not bit:
        return None
    bas_min = sorted({saat_to_min(s["zaman"]) for s in bas})
    bit_set  = {saat_to_min(s["zaman"]) for s in bit}
    best_T, best_n = None, 0
    for T in range(15, 76):
        n = sum(1 for b in bas_min if (b+T-1) in bit_set or (b+T) in bit_set or (b+T+1) in bit_set)
        if n > best_n:
            best_n, best_T = n, T
    return best_T

def aktif_trenler_hesapla(istasyonlar, seferler_dt, sure, simdi):
    n     = len(istasyonlar)
    d     = sure / (n-1) if n > 1 else sure
    zamanlar = [i * d for i in range(n)]
    aktif = []
    for kalkis in seferler_dt:
        bitis = kalkis + timedelta(minutes=sure)
        if kalkis > simdi or bitis < simdi:
            continue
        gecen = (simdi - kalkis).total_seconds() / 60
        for i in range(n-1):
            if zamanlar[i] <= gecen < zamanlar[i+1]:
                kalan = max(1, round(zamanlar[i+1] - gecen))
                yuzde = int((gecen - zamanlar[i]) / (zamanlar[i+1] - zamanlar[i]) * 100)
                aktif.append({
                    "kalkis"     : kalkis.strftime("%H:%M"),
                    "nereden"    : istasyonlar[i]["Name"].title(),
                    "nereye"     : istasyonlar[i+1]["Name"].title(),
                    "nereden_idx": i,
                    "nereye_idx" : i+1,
                    "kalan_dk"   : kalan,
                    "yuzde"      : yuzde,
                })
                break
    return sorted(aktif, key=lambda x: x["kalkis"])

def hat_durumu_hesapla(hat, tarih, simdi):
    session = yeni_session()
    try:
        yonler      = ibb_get(f"GetDirectionById/{hat['Id']}")
        istasyonlar = ibb_get(f"GetStationById/{hat['Id']}")
        sure        = hat_suresi(session, hat["Name"]) or max((len(istasyonlar)-1)*2.5, 10)
        sonuclar    = []
        for yon in yonler:
            parcalar = yon["DirectionName"].split("->")
            bas_adi  = parcalar[0].strip().upper().split()[0]
            bas_st   = next((s for s in istasyonlar if bas_adi in s["Name"].upper()), istasyonlar[0])
            try:
                kod      = kod_cek(session)
                seferler = tarife_cek(session, bas_st["Id"], yon["DirectionId"], tarih, kod)
            except Exception:
                continue
            if not seferler:
                continue
            seferler_dt = sorted({saat_to_dt(s["zaman"], simdi) for s in seferler})
            aktif       = aktif_trenler_hesapla(istasyonlar, seferler_dt, sure, simdi)
            sonuclar.append({
                "yon_adi"     : yon["DirectionName"],
                "direction_id": yon["DirectionId"],
                "aktif"       : aktif[:8],
                "aktif_sayi"  : len(aktif),
            })
        return {"id":hat["Id"],"name":hat["Name"],"renk":hat.get("renk","#555"),
                "yonler":sonuclar,"sure":sure}
    except Exception as e:
        return {"id":hat["Id"],"name":hat["Name"],"renk":hat.get("renk","#555"),
                "yonler":[],"hata":str(e)}

def hat_trenleri_hesapla(hat, tarih, simdi, coords):
    session     = yeni_session()
    istasyonlar = ibb_get(f"GetStationById/{hat['Id']}")
    sure        = hat_suresi(session, hat["Name"]) or max((len(istasyonlar)-1)*2.5,10)
    yonler      = ibb_get(f"GetDirectionById/{hat['Id']}")
    trenler     = []
    for yon in yonler:
        parcalar = yon["DirectionName"].split("->")
        bas_adi  = parcalar[0].strip().upper().split()[0]
        bas_st   = next((s for s in istasyonlar if bas_adi in s["Name"].upper()), istasyonlar[0])
        try:
            kod      = kod_cek(session)
            seferler = tarife_cek(session, bas_st["Id"], yon["DirectionId"], tarih, kod)
        except Exception:
            continue
        if not seferler:
            continue
        seferler_dt = sorted({saat_to_dt(s["zaman"], simdi) for s in seferler})
        aktif       = aktif_trenler_hesapla(istasyonlar, seferler_dt, sure, simdi)
        for t in aktif:
            i, j = t["nereden_idx"], t["nereye_idx"]
            c1 = match_coord(istasyonlar[i]["Name"], coords)
            c2 = match_coord(istasyonlar[j]["Name"], coords)
            if not c1 or not c2:
                continue
            pct = t["yuzde"] / 100
            lat = c1[0] + (c2[0] - c1[0]) * pct
            lon = c1[1] + (c2[1] - c1[1]) * pct
            trenler.append({
                "hat"     : hat["Name"],
                "renk"    : hat["renk"],
                "kalkis"  : t["kalkis"],
                "nereden" : t["nereden"],
                "nereye"  : t["nereye"],
                "kalan_dk": t["kalan_dk"],
                "yuzde"   : t["yuzde"],
                "lat"     : round(lat, 6),
                "lon"     : round(lon, 6),
            })
    return trenler

# ── Flask endpoint'leri ───────────────────────────────────────────────────────


@app.route("/api/debug/harita")
def api_debug_harita():
    coords = get_station_coords()
    hatlar = [h for h in ibb_get("GetLines") if h["Name"] in METRO_HATLARI]
    ornekler = {}
    for hat in hatlar[:3]:
        istasyonlar = ibb_get(f"GetStationById/{hat['Id']}")
        ornekler[hat["Name"]] = []
        for st in istasyonlar[:3]:
            c = match_coord(st["Name"], coords)
            ornekler[hat["Name"]].append({
                "name": st["Name"], "normalized": normalize(st["Name"]),
                "coord": c
            })
    return jsonify({"koordinat_sayisi": len(coords), "ornekler": ornekler,
                    "ilk_10_anahtar": list(coords.keys())[:10]})

@app.route("/api/lines")
def api_lines():
    lines = ibb_get("GetLines")
    for l in lines:
        l["renk"] = HAT_RENKLERI.get(l.get("Name",""), "#555")
    return jsonify(lines)

@app.route("/api/metro-lines")
def api_metro_lines():
    lines = [l for l in ibb_get("GetLines") if l["Name"] in METRO_HATLARI]
    for l in lines:
        l["renk"] = HAT_RENKLERI.get(l["Name"], "#555")
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
    saat_str   = data.get("saat","")
    session    = yeni_session()
    bugun      = datetime.today()
    tarih      = bugun.strftime("%d.%m.%Y")
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
    sonraki  = []
    for s in seferler:
        dt = saat_to_dt(s["zaman"], bugun)
        if dt >= simdi:
            dk = int((dt - simdi).total_seconds() / 60)
            sonraki.append({"saat":s["zaman"],"dk":dk})
    gun_adi = ["Pzt","Sal","Çar","Per","Cum","Cmt","Paz"][bugun.weekday()]
    return jsonify({
        "sonraki":sonraki[:8],"toplam_kalan":len(sonraki),
        "son_sefer":seferler[-1]["zaman"] if seferler else "-",
        "simdi":simdi.strftime("%H:%M"),"tarih":f"{tarih} {gun_adi}",
    })

@app.route("/api/canli-konum", methods=["POST"])
def api_canli_konum():
    data        = request.json
    line_id     = data["line_id"]
    hat_adi     = data["hat_adi"]
    route_id    = data["route_id"]
    yon_adi     = data["yon_adi"]
    saat_str    = data.get("saat","")
    session     = yeni_session()
    bugun       = datetime.today()
    tarih       = bugun.strftime("%d.%m.%Y")
    istasyonlar = ibb_get(f"GetStationById/{line_id}")
    parcalar    = yon_adi.split("->")
    bas_adi     = parcalar[0].strip().upper().split()[0]
    bitis_adi   = parcalar[1].strip().upper().split()[0] if len(parcalar)>1 else ""
    bas_st      = next((s for s in istasyonlar if bas_adi in s["Name"].upper()), istasyonlar[0])
    bitis_st    = next((s for s in istasyonlar if bitis_adi in s["Name"].upper()), istasyonlar[-1])
    if saat_str:
        try:
            h, m = map(int, saat_str.split(":"))
            simdi = bugun.replace(hour=h, minute=m, second=0, microsecond=0)
        except Exception:
            simdi = bugun
    else:
        simdi = bugun
    toplam_sure = yolculuk_suresi(session, bas_st["Id"], bitis_st["Id"], route_id, tarih, hat_adi)
    if not toplam_sure:
        toplam_sure = (len(istasyonlar)-1) * 2.5
    kod      = kod_cek(session)
    seferler = tarife_cek(session, bas_st["Id"], route_id, tarih, kod)
    if not seferler:
        return jsonify({"aktif":[]})
    seferler_dt = sorted({saat_to_dt(s["zaman"], bugun) for s in seferler})
    aktif       = aktif_trenler_hesapla(istasyonlar, seferler_dt, toplam_sure, simdi)
    gun_adi     = ["Pzt","Sal","Çar","Per","Cum","Cmt","Paz"][bugun.weekday()]
    return jsonify({"aktif":aktif,"toplam_sure":toplam_sure,
                    "simdi":simdi.strftime("%H:%M"),"tarih":f"{tarih} {gun_adi}"})

@app.route("/api/sistem-durumu")
def api_sistem_durumu():
    hatlar = [h for h in ibb_get("GetLines") if h["Name"] in METRO_HATLARI]
    for h in hatlar:
        h["renk"] = HAT_RENKLERI.get(h["Name"],"#555")
    bugun = datetime.today()
    tarih = bugun.strftime("%d.%m.%Y")
    simdi = bugun
    sonuclar = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        fs = {ex.submit(hat_durumu_hesapla, h, tarih, simdi): h for h in hatlar}
        for f in as_completed(fs):
            try:
                sonuclar.append(f.result())
            except Exception:
                pass
    sonuclar.sort(key=lambda x: x["name"])
    gun_adi = ["Pzt","Sal","Çar","Per","Cum","Cmt","Paz"][bugun.weekday()]
    return jsonify({"hatlar":sonuclar,"simdi":bugun.strftime("%H:%M"),
                    "tarih":f"{tarih} {gun_adi}"})

@app.route("/api/harita-verileri")
def api_harita_verileri():
    """Metro hatları + istasyonlar + koordinatlar."""
    coords  = get_station_coords()
    hatlar  = [h for h in ibb_get("GetLines") if h["Name"] in METRO_HATLARI]
    sonuc   = []
    for hat in hatlar:
        renk        = HAT_RENKLERI.get(hat["Name"],"#555")
        istasyonlar = ibb_get(f"GetStationById/{hat['Id']}")
        st_data     = []
        for st in istasyonlar:
            c = match_coord(st["Name"], coords)
            st_data.append({
                "id":st["Id"],"name":st["Name"].title(),
                "lat":c[0] if c else None,
                "lon":c[1] if c else None,
            })
        sonuc.append({"id":hat["Id"],"name":hat["Name"],"renk":renk,"istasyonlar":st_data})
    return jsonify({"hatlar":sonuc,"koordinat_sayisi":len(coords)})

@app.route("/api/harita-trenler")
def api_harita_trenler():
    """Tüm metro hatlarındaki aktif trenlerin harita koordinatları."""
    coords  = get_station_coords()
    hatlar  = [h for h in ibb_get("GetLines") if h["Name"] in METRO_HATLARI]
    for h in hatlar:
        h["renk"] = HAT_RENKLERI.get(h["Name"],"#555")
    bugun   = datetime.today()
    tarih   = bugun.strftime("%d.%m.%Y")
    simdi   = bugun
    trenler = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        fs = [ex.submit(hat_trenleri_hesapla, h, tarih, simdi, coords) for h in hatlar]
        for f in as_completed(fs):
            try:
                trenler.extend(f.result())
            except Exception:
                pass
    gun_adi = ["Pzt","Sal","Çar","Per","Cum","Cmt","Paz"][bugun.weekday()]
    return jsonify({"trenler":trenler,"simdi":simdi.strftime("%H:%M"),
                    "tarih":f"{tarih} {gun_adi}","tren_sayisi":len(trenler)})

# ── HTML ──────────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Metro İstanbul</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
:root{--bg:#0d1117;--surface:#161b22;--border:#30363d;--text:#e6edf3;--muted:#8b949e;--accent:#E8421B}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh}
header{padding:16px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px}
header h1{font-size:1.05rem;font-weight:600;letter-spacing:.5px}
.logo{width:30px;height:30px;background:var(--accent);border-radius:7px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:.85rem}
.container{max-width:740px;margin:0 auto;padding:20px 16px}
.steps{display:flex;gap:8px;margin-bottom:24px;flex-wrap:wrap}
.step{font-size:.7rem;color:var(--muted);padding:4px 10px;border-radius:20px;border:1px solid var(--border);white-space:nowrap}
.step.active{color:var(--text);border-color:var(--accent);background:rgba(232,66,27,.1)}
.step.done{color:var(--accent);border-color:var(--accent)}
.panel{display:none}.panel.visible{display:block}
.panel-title{font-size:.75rem;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px}
.grid.wide{grid-template-columns:repeat(auto-fill,minmax(175px,1fr))}
.btn{background:var(--surface);border:1px solid var(--border);color:var(--text);padding:13px 10px;border-radius:10px;cursor:pointer;font-size:.88rem;font-weight:600;text-align:center;transition:border-color .15s,transform .1s;display:flex;flex-direction:column;align-items:center;gap:5px}
.btn:hover{border-color:#555;transform:translateY(-1px)}
.btn .dot{width:9px;height:9px;border-radius:50%}
.btn-feature{padding:16px;border-radius:12px;gap:7px}
.btn-feature .icon{font-size:1.5rem}
.btn-feature .label{font-size:.9rem;font-weight:600}
.btn-feature .desc{font-size:.72rem;color:var(--muted);font-weight:400}
.btn-yon{padding:14px;font-size:.83rem;text-align:left;flex-direction:row;justify-content:flex-start}
.saat-row{display:flex;gap:10px;align-items:center;margin-bottom:16px}
.saat-row input{background:var(--surface);border:1px solid var(--border);color:var(--text);padding:9px 12px;border-radius:8px;font-size:.88rem;width:105px}
.saat-row label{font-size:.78rem;color:var(--muted)}
.saat-row .go-btn{padding:9px 16px;border-radius:8px;background:var(--accent);border:none;color:#fff;font-size:.83rem;font-weight:600;cursor:pointer}
.back{font-size:.8rem;color:var(--muted);cursor:pointer;margin-bottom:18px;display:inline-flex;align-items:center;gap:6px}
.back:hover{color:var(--text)}
.breadcrumb{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}
.chip{font-size:.73rem;padding:4px 10px;border-radius:20px;background:rgba(255,255,255,.07);color:var(--muted)}
.chip.colored{color:var(--text)}
.loader{text-align:center;padding:36px;color:var(--muted)}
.spinner{display:inline-block;width:26px;height:26px;border:3px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.tren-list{display:flex;flex-direction:column;gap:8px}
.tren-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:13px 15px;display:flex;align-items:center;gap:13px}
.tren-card.ilk{border-color:var(--accent);background:rgba(232,66,27,.06)}
.tren-card .saat{font-size:1.2rem;font-weight:700;min-width:50px}
.tren-card .bekleme{font-size:.83rem;color:var(--muted)}
.tren-card .badge{margin-left:auto;font-size:.7rem;font-weight:600;padding:3px 8px;border-radius:20px;background:var(--accent);color:#fff}
.konum-list{display:flex;flex-direction:column;gap:9px}
.konum-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:13px 15px}
.konum-card .row1{display:flex;align-items:center;gap:10px;margin-bottom:7px}
.konum-card .kalkis-badge{font-size:.7rem;padding:2px 8px;border-radius:20px;border:1px solid var(--border);color:var(--muted)}
.konum-card .kalan{margin-left:auto;font-size:.78rem;color:var(--muted)}
.konum-card .seg{display:flex;align-items:center;gap:7px;font-size:.88rem}
.konum-card .ok{color:var(--accent)}
.progress-bar{height:3px;background:var(--border);border-radius:2px;margin-top:7px;overflow:hidden}
.progress-fill{height:100%;border-radius:2px;background:var(--accent)}
.meta-row{margin-top:20px;padding:11px;border-radius:8px;background:var(--surface);border:1px solid var(--border);font-size:.76rem;color:var(--muted);display:flex;gap:14px;flex-wrap:wrap}
.empty{text-align:center;padding:36px;color:var(--muted)}
/* Sistem */
.sistem-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}
.hat-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden}
.hat-card-header{padding:11px 15px;display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--border)}
.hat-badge{padding:3px 11px;border-radius:20px;font-weight:700;font-size:.82rem;color:#fff}
.hat-card-body{padding:11px 15px}
.yon-blok{margin-bottom:11px}.yon-blok:last-child{margin-bottom:0}
.yon-baslik{font-size:.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:.8px;margin-bottom:5px}
.mini-tren{display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid var(--border);font-size:.8rem}
.mini-tren:last-child{border-bottom:none}
.mini-kalkis{font-weight:600;min-width:38px;color:var(--muted);font-size:.72rem}
.mini-seg{flex:1;display:flex;align-items:center;gap:5px}
.mini-ok{color:var(--accent);font-size:.78rem}
.mini-kalan{font-size:.7rem;color:var(--muted);min-width:34px;text-align:right}
.hat-yukleniyor{padding:14px;text-align:center;color:var(--muted);font-size:.78rem}
.hata-mesaj{padding:9px;font-size:.76rem;color:#f87171}
.bos-mesaj{padding:9px;font-size:.76rem;color:var(--muted);text-align:center}
.refresh-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.refresh-btn{background:var(--surface);border:1px solid var(--border);color:var(--text);padding:7px 14px;border-radius:8px;cursor:pointer;font-size:.8rem}
.refresh-btn:hover{border-color:var(--accent)}
.sistem-meta{font-size:.78rem;color:var(--muted)}
/* Harita */
#map-container{position:relative}
#metro-map{height:calc(100vh - 120px);border-radius:12px;overflow:hidden;border:1px solid var(--border)}
.map-overlay{position:absolute;top:12px;right:12px;z-index:1000;display:flex;flex-direction:column;gap:8px}
.map-legend{background:rgba(13,17,23,.92);border:1px solid var(--border);border-radius:10px;padding:10px 14px;font-size:.75rem;min-width:160px}
.map-legend .title{font-size:.7rem;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin-bottom:8px}
.legend-item{display:flex;align-items:center;gap:8px;padding:3px 0;cursor:pointer}
.legend-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.legend-item.gizli{opacity:.35}
.map-info{background:rgba(13,17,23,.92);border:1px solid var(--border);border-radius:10px;padding:8px 12px;font-size:.75rem;color:var(--muted)}
.map-refresh-btn{background:rgba(13,17,23,.92);border:1px solid var(--border);color:var(--text);padding:7px 12px;border-radius:8px;cursor:pointer;font-size:.78rem}
.map-refresh-btn:hover{border-color:var(--accent)}
@media(max-width:480px){
  .grid{grid-template-columns:repeat(3,1fr)}
  .grid.wide{grid-template-columns:1fr 1fr}
  #metro-map{height:calc(100vh - 110px)}
}
</style>
</head>
<body>
<header>
  <div class="logo">M</div>
  <h1>Metro İstanbul</h1>
</header>
<div class="container" id="main-container">
  <div class="steps">
    <div class="step active" id="step-hat">Hat</div>
    <div class="step" id="step-ozellik">Özellik</div>
    <div class="step" id="step-yon">Yön</div>
    <div class="step" id="step-sonuc">Sonuç</div>
  </div>

  <!-- Hat seç -->
  <div class="panel visible" id="panel-hat">
    <div class="panel-title">Hat seçin</div>
    <div class="grid" id="hat-grid"><div class="loader"><div class="spinner"></div></div></div>
  </div>

  <!-- Özellik seç -->
  <div class="panel" id="panel-ozellik">
    <div class="back" onclick="geri('hat')">← Geri</div>
    <div class="breadcrumb" id="bc-ozellik"></div>
    <div class="panel-title">Ne yapmak istiyorsunuz?</div>
    <div class="grid wide">
      <div class="btn btn-feature" id="btn-sonraki">
        <div class="icon">🕐</div><div class="label">Sonraki Tren</div>
        <div class="desc">Bir durağa tren ne zaman gelir?</div>
      </div>
      <div class="btn btn-feature" id="btn-konum">
        <div class="icon">📍</div><div class="label">Anlık Konum</div>
        <div class="desc">Hattaki trenler şu an nerede?</div>
      </div>
    </div>
    <div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div class="btn btn-feature" id="btn-sistem" style="background:rgba(232,66,27,.06);border-color:rgba(232,66,27,.4)">
        <div class="icon">🚇</div><div class="label" style="color:var(--accent)">Tüm Sistem</div>
        <div class="desc">Metro genelinde anlık durum</div>
      </div>
      <div class="btn btn-feature" id="btn-harita" style="background:rgba(0,166,81,.06);border-color:rgba(0,166,81,.4)">
        <div class="icon">🗺️</div><div class="label" style="color:#00A651">Canlı Harita</div>
        <div class="desc">Tüm trenler haritada</div>
      </div>
    </div>
  </div>

  <!-- Yön (sonraki tren) -->
  <div class="panel" id="panel-yon-sonraki">
    <div class="back" onclick="geri('ozellik')">← Geri</div>
    <div class="breadcrumb" id="bc-yon-sonraki"></div>
    <div class="panel-title">Yön seçin</div>
    <div class="grid wide" id="yon-sonraki-grid"></div>
    <div id="durak-blok" style="display:none;margin-top:22px">
      <div class="panel-title">Durak seçin</div>
      <div class="saat-row">
        <label>Saat (boş = şimdi)</label>
        <input type="time" id="saat-sonraki">
      </div>
      <div class="grid wide" id="durak-grid"></div>
    </div>
  </div>

  <!-- Yön (anlık konum) -->
  <div class="panel" id="panel-yon-konum">
    <div class="back" onclick="geri('ozellik')">← Geri</div>
    <div class="breadcrumb" id="bc-yon-konum"></div>
    <div class="panel-title">Yön seçin</div>
    <div class="grid wide" id="yon-konum-grid"></div>
    <div id="saat-blok-konum" style="display:none;margin-top:22px">
      <div class="panel-title">Saat</div>
      <div class="saat-row">
        <label>Saat (boş = şimdi)</label>
        <input type="time" id="saat-konum">
        <button class="go-btn" id="konum-go-btn">Göster</button>
      </div>
    </div>
  </div>

  <!-- Sonuç -->
  <div class="panel" id="panel-sonuc">
    <div class="back" onclick="geri('yon')">← Geri</div>
    <div class="breadcrumb" id="bc-sonuc"></div>
    <div id="sonuc-icerik"><div class="loader"><div class="spinner"></div></div></div>
  </div>

  <!-- Sistem durumu -->
  <div class="panel" id="panel-sistem">
    <div class="back" onclick="geri('ozellik')">← Geri</div>
    <div class="refresh-row">
      <div class="sistem-meta" id="sistem-meta">Yükleniyor...</div>
      <button class="refresh-btn" id="sistem-refresh-btn">↻ Yenile</button>
    </div>
    <div class="sistem-grid" id="sistem-grid"></div>
  </div>
</div>

<!-- Harita (tam genişlik, container dışında) -->
<div id="panel-harita" class="panel" style="padding:0">
  <div style="padding:12px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px">
    <div class="back" style="margin:0" onclick="haritaGeri()">← Geri</div>
    <span style="font-size:.85rem;font-weight:600">Canlı Harita</span>
    <span id="harita-meta" style="font-size:.75rem;color:var(--muted);margin-left:auto"></span>
    <button class="map-refresh-btn" id="harita-refresh-btn">↻ Yenile</button>
  </div>
  <div id="map-container">
    <div id="metro-map"></div>
    <div class="map-overlay">
      <div class="map-legend">
        <div class="title">Hatlar</div>
        <div id="legend-items"></div>
      </div>
      <div class="map-info" id="map-info">Harita yükleniyor...</div>
    </div>
  </div>
</div>

<script>
const S = {hat:null, ozellik:null, yon:null};
const HAT_MAP={}, YON_MAP={}, ST_MAP={};
let leafletMap=null, hatKatmanlari={}, trenKatmanlari=[], gizliHatlar=new Set();

// ── Panel yönetimi ────────────────────────────────────────────────────────────
function goster(id) {
  document.querySelectorAll(".panel").forEach(p=>p.classList.remove("visible"));
  document.getElementById("panel-"+id).classList.add("visible");
  const isHarita = id==="harita";
  document.getElementById("main-container").style.display = isHarita ? "none" : "";
  const asamalar=["hat","ozellik","yon","sonuc"];
  const aktif={"hat":0,"ozellik":1,"yon-sonraki":2,"yon-konum":2,"sonuc":3,"sistem":1,"harita":1}[id]??0;
  asamalar.forEach((a,i)=>{
    const el=document.getElementById("step-"+a);
    if(el) el.className="step"+(i<aktif?" done":i===aktif?" active":"");
  });
}

function geri(hedef) {
  if(hedef==="hat") goster("hat");
  if(hedef==="ozellik") goster("ozellik");
  if(hedef==="yon") {
    if(S.ozellik==="sonraki") goster("yon-sonraki");
    else goster("yon-konum");
  }
}

function haritaGeri() {
  goster("ozellik");
}

// ── Breadcrumb ────────────────────────────────────────────────────────────────
function breadcrumb(elId, parcalar) {
  document.getElementById(elId).innerHTML = parcalar.map(p=>
    `<span class="chip colored" style="border:1px solid ${p.renk||'#555'};color:${p.renk||'#ccc'}">${p.text}</span>`
  ).join("");
}

// ── API ───────────────────────────────────────────────────────────────────────
async function get(url) { const r=await fetch(url); return r.json(); }
async function post(url, data) {
  const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
  return r.json();
}

// ── Panel 1: Hatlar ───────────────────────────────────────────────────────────
async function yukleHatlar() {
  const hatlar = await get("/api/lines");
  hatlar.forEach(h=>{HAT_MAP[h.Id]=h;});
  const grid=document.getElementById("hat-grid");
  grid.innerHTML=hatlar.map(h=>`
    <div class="btn" data-id="${h.Id}" title="${h.Name}">
      <div class="dot" style="background:${h.renk}"></div>
      <span>${h.Name}</span>
    </div>`).join("");
  grid.querySelectorAll(".btn").forEach(btn=>
    btn.addEventListener("click",()=>hatSec(HAT_MAP[btn.dataset.id])));
}

function hatSec(hat) {
  S.hat=hat;
  breadcrumb("bc-ozellik",[{text:hat.Name,renk:hat.renk}]);
  goster("ozellik");
}

// ── Panel 2: Özellik ──────────────────────────────────────────────────────────
document.getElementById("btn-sonraki").addEventListener("click",()=>ozellikSec("sonraki"));
document.getElementById("btn-konum").addEventListener("click",()=>ozellikSec("konum"));
document.getElementById("btn-sistem").addEventListener("click",()=>{goster("sistem");yukleSimdi();});
document.getElementById("btn-harita").addEventListener("click",()=>haritaAc());

function ozellikSec(o) {
  S.ozellik=o;
  if(o==="sonraki") yukleYonlarSonraki();
  else yukleYonlarKonum();
}

// ── Panel 3a: Yön - Sonraki Tren ──────────────────────────────────────────────
async function yukleYonlarSonraki() {
  breadcrumb("bc-yon-sonraki",[{text:S.hat.Name,renk:S.hat.renk},{text:"Sonraki Tren"}]);
  goster("yon-sonraki");
  document.getElementById("durak-blok").style.display="none";
  const yonler=await get("/api/directions/"+S.hat.Id);
  yonler.forEach(y=>{YON_MAP[y.DirectionId]=y;});
  const g=document.getElementById("yon-sonraki-grid");
  g.innerHTML=yonler.map(y=>`
    <div class="btn btn-yon" data-id="${y.DirectionId}">
      <span style="color:${S.hat.renk}">&#x2192;</span>
      <span>${y.DirectionName}</span>
    </div>`).join("");
  g.querySelectorAll(".btn").forEach(btn=>
    btn.addEventListener("click",()=>yonSonrakiSec(YON_MAP[btn.dataset.id])));
}

async function yonSonrakiSec(yon) {
  S.yon=yon;
  document.getElementById("durak-blok").style.display="block";
  document.getElementById("durak-grid").innerHTML='<div class="loader"><div class="spinner" style="width:18px;height:18px;border-width:2px"></div></div>';
  const istasyonlar=await get("/api/stations/"+S.hat.Id);
  istasyonlar.forEach(st=>{ST_MAP[st.Id]=st;});
  const g=document.getElementById("durak-grid");
  g.innerHTML=istasyonlar.map(st=>{
    const ad=st.Name.split(" ").map(w=>w.charAt(0)+w.slice(1).toLowerCase()).join(" ");
    return `<div class="btn" style="font-size:.8rem" data-id="${st.Id}">${ad}</div>`;
  }).join("");
  g.querySelectorAll(".btn").forEach(btn=>
    btn.addEventListener("click",()=>istasyonSec(ST_MAP[btn.dataset.id])));
}

async function istasyonSec(istasyon) {
  const saat=document.getElementById("saat-sonraki").value;
  breadcrumb("bc-sonuc",[
    {text:S.hat.Name,renk:S.hat.renk},
    {text:istasyon.Name.split(" ").map(w=>w.charAt(0)+w.slice(1).toLowerCase()).join(" ")},
    {text:S.yon.DirectionName}
  ]);
  goster("sonuc");
  const el=document.getElementById("sonuc-icerik");
  el.innerHTML='<div class="loader"><div class="spinner"></div></div>';
  const veri=await post("/api/sonraki-tren",{station_id:istasyon.Id,route_id:S.yon.DirectionId,saat});
  if(!veri.sonraki||veri.sonraki.length===0){
    el.innerHTML=`<div class="empty">Bu saatte sefer yok.<br>Son sefer: ${veri.son_sefer}</div>`;
    return;
  }
  el.innerHTML=`
    <div class="meta-row" style="margin-bottom:12px">
      <span>🕐 ${veri.simdi}</span><span>📅 ${veri.tarih}</span>
      <span>Kalan ${veri.toplam_kalan} sefer · Son: ${veri.son_sefer}</span>
    </div>
    <div class="tren-list">${veri.sonraki.map((t,i)=>`
      <div class="tren-card ${i===0?"ilk":""}">
        <div class="saat">${t.saat}</div>
        <div class="bekleme">${t.dk===0?"Şimdi geliyor":t.dk+" dakika sonra"}</div>
        ${i===0?'<div class="badge">En yakın</div>':""}
      </div>`).join("")}
    </div>`;
}

// ── Panel 3b: Yön - Anlık Konum ───────────────────────────────────────────────
async function yukleYonlarKonum() {
  breadcrumb("bc-yon-konum",[{text:S.hat.Name,renk:S.hat.renk},{text:"Anlık Konum"}]);
  goster("yon-konum");
  document.getElementById("saat-blok-konum").style.display="none";
  const yonler=await get("/api/directions/"+S.hat.Id);
  yonler.forEach(y=>{YON_MAP[y.DirectionId]=y;});
  const g=document.getElementById("yon-konum-grid");
  g.innerHTML=yonler.map(y=>`
    <div class="btn btn-yon" data-id="${y.DirectionId}">
      <span style="color:${S.hat.renk}">&#x2192;</span>
      <span>${y.DirectionName}</span>
    </div>`).join("");
  g.querySelectorAll(".btn").forEach(btn=>
    btn.addEventListener("click",()=>yonKonumSec(YON_MAP[btn.dataset.id])));
}

function yonKonumSec(yon) {
  S.yon=yon;
  document.getElementById("saat-blok-konum").style.display="block";
}

document.getElementById("konum-go-btn").addEventListener("click", async ()=>{
  const saat=document.getElementById("saat-konum").value;
  breadcrumb("bc-sonuc",[{text:S.hat.Name,renk:S.hat.renk},{text:S.yon.DirectionName},{text:"Anlık Konum"}]);
  goster("sonuc");
  const el=document.getElementById("sonuc-icerik");
  el.innerHTML='<div class="loader"><div class="spinner"></div></div>';
  const veri=await post("/api/canli-konum",{
    line_id:S.hat.Id,hat_adi:S.hat.Name,route_id:S.yon.DirectionId,yon_adi:S.yon.DirectionName,saat});
  if(!veri.aktif||veri.aktif.length===0){
    el.innerHTML='<div class="empty">Bu saatte aktif tren yok.</div>'; return;
  }
  el.innerHTML=`
    <div class="meta-row" style="margin-bottom:12px">
      <span>🕐 ${veri.simdi}</span><span>📅 ${veri.tarih}</span>
      <span>Aktif: ${veri.aktif.length} tren · ~${veri.toplam_sure} dk yolculuk</span>
    </div>
    <div class="konum-list">${veri.aktif.map(t=>`
      <div class="konum-card">
        <div class="row1">
          <span class="kalkis-badge">Kalkış ${t.kalkis}</span>
          <span class="kalan">~${t.kalan_dk} dk</span>
        </div>
        <div class="seg">
          <span>${t.nereden}</span><span class="ok">→</span><span>${t.nereye}</span>
        </div>
        <div class="progress-bar"><div class="progress-fill" style="width:${t.yuzde}%"></div></div>
      </div>`).join("")}
    </div>`;
});

// ── Sistem Durumu ──────────────────────────────────────────────────────────────
document.getElementById("sistem-refresh-btn").addEventListener("click", yukleSimdi);

async function yukleSimdi() {
  const grid=document.getElementById("sistem-grid");
  const meta=document.getElementById("sistem-meta");
  meta.textContent="Veriler çekiliyor... (~15 sn)";
  const hatlar=await get("/api/metro-lines");
  grid.innerHTML=hatlar.map(h=>`
    <div class="hat-card" id="hcard-${h.Id}">
      <div class="hat-card-header">
        <span class="hat-badge" style="background:${h.renk}">${h.Name}</span>
        <span style="font-size:.77rem;color:var(--muted)">yükleniyor...</span>
      </div>
      <div class="hat-card-body hat-yukleniyor">
        <div class="spinner" style="width:16px;height:16px;border-width:2px"></div>
      </div>
    </div>`).join("");
  const veri=await get("/api/sistem-durumu");
  meta.textContent=`🕐 ${veri.simdi}  ·  ${veri.tarih}`;
  veri.hatlar.forEach(hat=>{
    const card=document.getElementById("hcard-"+hat.id);
    if(!card) return;
    let ic="";
    if(hat.hata){ ic=`<div class="hata-mesaj">⚠ Veri alınamadı</div>`; }
    else if(!hat.yonler||hat.yonler.length===0){ ic=`<div class="bos-mesaj">Bu saatte sefer yok</div>`; }
    else {
      ic=hat.yonler.map(y=>{
        if(!y.aktif||y.aktif.length===0)
          return `<div class="yon-blok"><div class="yon-baslik">${y.yon_adi}</div><div class="bos-mesaj" style="padding:3px 0">Aktif tren yok</div></div>`;
        return `<div class="yon-blok">
          <div class="yon-baslik">${y.yon_adi} · ${y.aktif_sayi} tren</div>
          ${y.aktif.map(t=>`<div class="mini-tren">
            <span class="mini-kalkis">${t.kalkis}</span>
            <div class="mini-seg"><span>${t.nereden}</span><span class="mini-ok">→</span><span>${t.nereye}</span></div>
            <span class="mini-kalan">~${t.kalan_dk}dk</span>
          </div>`).join("")}
        </div>`;
      }).join("<hr style='border:none;border-top:1px solid var(--border);margin:7px 0'>");
    }
    card.innerHTML=`
      <div class="hat-card-header">
        <span class="hat-badge" style="background:${hat.renk}">${hat.name}</span>
        <span style="font-size:.75rem;color:var(--muted)">~${hat.sure||"?"} dk</span>
      </div>
      <div class="hat-card-body">${ic}</div>`;
  });
}

// ── Canlı Harita ───────────────────────────────────────────────────────────────
let haritaYuklendi=false;

async function haritaAc() {
  goster("harita");
  if(!haritaYuklendi){ await haritaInit(); haritaYuklendi=true; }
  else { await trenlerGuncelle(); }
}

async function haritaInit() {
  document.getElementById("map-info").textContent="İstasyon koordinatları alınıyor...";

  // Leaflet başlat
  leafletMap = L.map("metro-map",{zoomControl:true}).setView([41.02,28.97],11);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",{
    attribution:"© OpenStreetMap © CARTO",
    maxZoom:18, subdomains:"abcd"
  }).addTo(leafletMap);

  // Hat + istasyon verisi al
  document.getElementById("map-info").textContent="Hat verileri yükleniyor...";
  const veri=await get("/api/harita-verileri");

  // Legend
  const legendEl=document.getElementById("legend-items");
  legendEl.innerHTML=veri.hatlar.map(h=>`
    <div class="legend-item" data-hat="${h.name}">
      <div class="legend-dot" style="background:${h.renk}"></div>
      <span style="color:var(--text)">${h.name}</span>
    </div>`).join("");
  legendEl.querySelectorAll(".legend-item").forEach(el=>{
    el.addEventListener("click",()=>hatToggle(el.dataset.hat));
  });

  // Hatları çiz
  veri.hatlar.forEach(hat=>{
    const coords=hat.istasyonlar
      .filter(s=>s.lat&&s.lon)
      .map(s=>[s.lat,s.lon]);

    if(coords.length<2) return;

    // Hat çizgisi
    const poly=L.polyline(coords,{color:hat.renk,weight:3.5,opacity:.85}).addTo(leafletMap);

    // Durak noktaları
    const stMarkers=hat.istasyonlar.filter(s=>s.lat&&s.lon).map(st=>{
      const m=L.circleMarker([st.lat,st.lon],{
        radius:4,color:hat.renk,fillColor:"#0d1117",fillOpacity:1,weight:2
      }).addTo(leafletMap);
      m.bindTooltip(st.name,{permanent:false,direction:"top",
        className:"leaflet-tooltip-dark",offset:[0,-6]});
      return m;
    });

    hatKatmanlari[hat.name]={poly, stMarkers, renk:hat.renk};
  });

  document.getElementById("map-info").textContent="İstasyonlar hazır";

  // Trenleri yükle
  await trenlerGuncelle();
}

async function trenlerGuncelle() {
  document.getElementById("harita-meta").textContent="Trenler güncelleniyor...";

  // Eski tren katmanlarını temizle
  trenKatmanlari.forEach(m=>{ if(leafletMap) leafletMap.removeLayer(m); });
  trenKatmanlari=[];

  const veri=await get("/api/harita-trenler");

  veri.trenler.forEach(t=>{
    if(gizliHatlar.has(t.hat)) return;

    const marker=L.circleMarker([t.lat,t.lon],{
      radius:7,
      color:"#fff",
      fillColor:t.renk,
      fillOpacity:1,
      weight:2,
    }).addTo(leafletMap);

    marker.bindPopup(`
      <div style="font-family:system-ui;min-width:160px">
        <div style="font-weight:700;font-size:.95rem;margin-bottom:4px">
          <span style="color:${t.renk}">■</span> ${t.hat}
        </div>
        <div style="font-size:.82rem;color:#555">Kalkış: ${t.kalkis}</div>
        <div style="font-size:.85rem;margin-top:4px">${t.nereden} → ${t.nereye}</div>
        <div style="font-size:.8rem;color:#777;margin-top:2px">~${t.kalan_dk} dk sonra varır</div>
        <div style="margin-top:6px;height:4px;background:#eee;border-radius:2px">
          <div style="height:100%;width:${t.yuzde}%;background:${t.renk};border-radius:2px"></div>
        </div>
      </div>`);

    trenKatmanlari.push(marker);
  });

  const simdi=veri.simdi;
  document.getElementById("harita-meta").textContent=`🕐 ${simdi}  ·  ${veri.tren_sayisi} aktif tren`;
  document.getElementById("map-info").textContent=`${veri.tren_sayisi} tren gösteriliyor`;
}

function hatToggle(hatAdi) {
  const el=document.querySelector(`.legend-item[data-hat="${hatAdi}"]`);
  const katman=hatKatmanlari[hatAdi];
  if(!katman||!leafletMap) return;

  if(gizliHatlar.has(hatAdi)){
    gizliHatlar.delete(hatAdi);
    katman.poly.addTo(leafletMap);
    katman.stMarkers.forEach(m=>m.addTo(leafletMap));
    el.classList.remove("gizli");
  } else {
    gizliHatlar.add(hatAdi);
    leafletMap.removeLayer(katman.poly);
    katman.stMarkers.forEach(m=>leafletMap.removeLayer(m));
    el.classList.add("gizli");
  }
  // Tren katmanlarını da güncelle (yeniden çiz)
  trenKatmanlari.forEach(m=>{ if(leafletMap) leafletMap.removeLayer(m); });
  trenKatmanlari=[];
  veriBuffer && veriBuffer.trenler.forEach(t=>{
    if(gizliHatlar.has(t.hat)) return;
    const marker=L.circleMarker([t.lat,t.lon],{radius:7,color:"#fff",fillColor:t.renk,fillOpacity:1,weight:2}).addTo(leafletMap);
    trenKatmanlari.push(marker);
  });
}

let veriBuffer=null;
const _origTrenlerGuncelle=trenlerGuncelle;

document.getElementById("harita-refresh-btn").addEventListener("click", trenlerGuncelle);

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
