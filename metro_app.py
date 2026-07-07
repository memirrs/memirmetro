"""
Metro İstanbul Canlı Board v3
================================
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

app   = Flask(__name__)
IBB   = "https://api.ibb.gov.tr/MetroIstanbul/api/MetroMobile/V2"
AJAX  = "https://www.metro.istanbul/SeferDurumlari/AJAXSeferGetir"
PAGE  = "https://www.metro.istanbul/SeferDurumlari/SeferDetaylari"
HATPG = "https://www.metro.istanbul/Hatlarimiz/HatDetay?hat={}"
OVP   = "https://overpass-api.de/api/interpreter"

METRO = {"M1A","M1B","M2","M3","M4","M5","M6","M7","M8","M9"}

# Resmi renk paleti (metro.istanbul'a göre)
RENKLER = {
    "M1A":"#E8421B","M1B":"#E8421B",
    "M2":"#D01F2D","M3":"#F47920","M4":"#005CA9",
    "M5":"#7B2D8B","M6":"#00954A","M7":"#F5A800",
    "M8":"#00ADEF","M9":"#EA1F27",
}

# ── Per-line bounding box (Overpass koordinat arama alanı) ────────────────────
# Her hat için ayrı bbox → "GÖZTEPE" gibi çakışan isimler doğru eşleşir
LINE_BBOX = {
    "M1A": (40.96, 28.80, 41.08, 28.97),
    "M1B": (40.96, 28.80, 41.08, 28.97),
    "M2":  (40.99, 28.93, 41.15, 29.04),
    "M3":  (41.03, 28.79, 41.10, 28.90),
    "M4":  (40.88, 29.02, 41.01, 29.25),
    "M5":  (41.00, 29.01, 41.06, 29.20),
    "M6":  (41.07, 29.00, 41.10, 29.08),
    "M7":  (41.03, 28.85, 41.13, 28.99),
    "M8":  (40.95, 29.09, 41.05, 29.20),
    "M9":  (40.97, 28.81, 41.08, 28.90),
}

# ── Hardcoded koordinatlar (Overpass yedek + Transfer istasyonları) ────────────
# Key: "{HAT}:{NORMALIZE(isim)}"  → örnk "M2:TAKSIM", "M4:GOZTEPE"
# Transfer istasyonları birden fazla hatta aynı koordinatla girer.
HC = {
    # ─ M1A ─
    "M1A:AKSARAY":           (41.011998,28.948145),
    "M1A:ATAKOY":            (40.980008,28.856293),
    "M1A:ATAKOYSIRINEVLER":  (40.991379,28.845771),
    "M1A:ATATURKHAVALIMANI": (40.979745,28.821127),
    "M1A:BAHCELIEVLER":      (40.995481,28.863314),
    "M1A:BAKIRKOYSAHIL":     (40.973743,28.868034),
    "M1A:BAKIRKOYINCIRLI":   (40.996621,28.875362),
    "M1A:BAYRAMPASAMALTEPE": (41.034107,28.920263),
    "M1A:BAYRAMPASA":        (41.034107,28.920263),
    "M1A:BAGCILARMEYDAN":    (41.034683,28.856640),
    "M1A:BAGCILAR":          (41.034683,28.856640),
    "M1A:COBANCESME":        (40.999733,28.822478),
    "M1A:DAVUTPASAYTU":      (41.020219,28.900375),
    "M1A:DAVUTPASA":         (41.020219,28.900375),
    "M1A:DTMISTANBULFUARMERKEZI": (40.986602,28.828474),
    "M1A:EMNIYETFATIH":      (41.017430,28.939632),
    "M1A:EMNIYET":           (41.017430,28.939632),
    "M1A:ESENLER":           (41.037574,28.888587),
    "M1A:HAZNEDAR":          (41.004705,28.871897),
    "M1A:INCIRLI":           (40.997651,28.875318),
    "M1A:KIRAZLI":           (41.031990,28.842981),
    "M1A:KOCATEPE":          (41.048436,28.895492),
    "M1A:MAHMUTBEY":         (41.054935,28.830961),
    "M1A:MENDERES":          (41.042741,28.878495),
    "M1A:MERTER":            (41.007618,28.896184),
    "M1A:OTOGAR":            (41.040094,28.894748),
    "M1A:SAGMALCILAR":       (41.040857,28.907218),
    "M1A:TERAZIDERE":        (41.030462,28.897870),
    "M1A:TOPKAPIULUBATLI":   (41.023906,28.930557),
    "M1A:ULUBATLI":          (41.023906,28.930557),
    "M1A:UCYUZLU":           (41.036702,28.870699),
    "M1A:YENIBOSNA":         (40.989464,28.838119),
    "M1A:YENIKAPI":          (41.005779,28.950518),
    "M1A:ZEYTINBURNU":       (41.001717,28.889975),
    # ─ M1B ─ (M1A ile ortak güzergah)
    "M1B:AKSARAY":           (41.011998,28.948145),
    "M1B:ATATURKHAVALIMANI": (40.979745,28.821127),
    "M1B:BAYRAMPASAMALTEPE": (41.034107,28.920263),
    "M1B:BAYRAMPASA":        (41.034107,28.920263),
    "M1B:BAGCILARMEYDAN":    (41.034683,28.856640),
    "M1B:BAGCILAR":          (41.034683,28.856640),
    "M1B:DAVUTPASAYTU":      (41.020219,28.900375),
    "M1B:DAVUTPASA":         (41.020219,28.900375),
    "M1B:EMNIYETFATIH":      (41.017430,28.939632),
    "M1B:EMNIYET":           (41.017430,28.939632),
    "M1B:ESENLER":           (41.037574,28.888587),
    "M1B:KIRAZLI":           (41.031990,28.842981),
    "M1B:KOCATEPE":          (41.048436,28.895492),
    "M1B:MERTER":            (41.007618,28.896184),
    "M1B:OTOGAR":            (41.040094,28.894748),
    "M1B:SAGMALCILAR":       (41.040857,28.907218),
    "M1B:TERAZIDERE":        (41.030462,28.897870),
    "M1B:TOPKAPIULUBATLI":   (41.023906,28.930557),
    "M1B:ULUBATLI":          (41.023906,28.930557),
    "M1B:YENIKAPI":          (41.005779,28.950518),
    "M1B:YENIBOSNA":         (40.989464,28.838119),
    "M1B:ZEYTINBURNU":       (41.001717,28.889975),
    # ─ M2 ─
    "M2:4LEVENT":            (41.086111,29.007165),
    "M2:ATATURKOTOSANAYI":   (41.118215,29.024349),
    "M2:DARUSSAFAKA":        (41.129287,29.024868),
    "M2:GAYRETTEPE":         (41.066755,29.010506),
    "M2:HACIOSMAN":          (41.139877,29.030346),
    "M2:HALIC":              (41.022690,28.966679),
    "M2:ITUAYAZAGA":         (41.108205,29.020920),
    "M2:LEVENT":             (41.075798,29.014469),
    "M2:OSMANBEY":           (41.052776,28.987405),
    "M2:SANAYIMAHALLESI":    (41.094157,29.005572),
    "M2:SEYRANTEPE":         (41.101289,28.995744),
    "M2:SISHANE":            (41.028274,28.972719),
    "M2:SISLIMECIDIYEKOY":   (41.064506,28.992770),
    "M2:TAKSIM":             (41.038051,28.985549),
    "M2:VEZNECILER":         (41.012253,28.959701),
    "M2:YENIKAPI":           (41.005779,28.950518),
    # ─ M3 ─
    "M3:BAGCILARMEYDAN":     (41.034683,28.856640),
    "M3:GIYIMKENTTEKSTILKENT": (41.071239,28.866905),
    "M3:ISTOC":              (41.065077,28.826085),
    "M3:IKITELLISANAYI":     (41.071152,28.803628),
    "M3:KIRAZLI":            (41.031990,28.842981),
    "M3:MAHMUTBEY":          (41.054935,28.830961),
    "M3:KARADENIZMAHALLESI": (41.081339,28.874930),
    "M3:KAZIMKARABEKIR":     (41.085461,28.908546),
    "M3:YENIMAHALLE":        (41.083819,28.892680),
    "M3:YESILPINAR":         (41.082415,28.918340),
    "M3:ORUCREISYUZYIL":     (41.062896,28.855279),
    # ─ M4 ─
    "M4:ACIBADEM":           (41.002183,29.044323),
    "M4:AYRILIKCESMESI":     (41.000180,29.030582),
    "M4:BOSTANCI":           (40.951606,29.096615),
    "M4:ESENKENT":           (40.920721,29.166307),
    "M4:FEVZICAKMAK":        (40.921000,29.184000),
    "M4:GOZTEPE":            (40.994270,29.070757),
    "M4:GULSUYU":            (40.923715,29.154616),
    "M4:HASTANEADLIYE":      (40.916393,29.178300),
    "M4:HUZUREVI":           (40.929954,29.146806),
    "M4:KADIKOY":            (40.990490,29.022218),
    "M4:KOZYATAGI":          (40.977607,29.099836),
    "M4:KUCUKYALI":          (40.948872,29.121882),
    "M4:MALTEPE":            (40.935751,29.139347),
    "M4:SABIHAGOKCEN":       (40.882035,29.248717),
    "M4:SOGANLIK":           (40.913103,29.192363),
    "M4:TAVSANTEPE":         (40.882035,29.248717),
    "M4:UNALAN":             (40.997949,29.059949),
    "M4:YENISAHRA":          (40.984485,29.090260),
    # ─ M5 ─
    "M5:ALTUNIZADE":         (41.021911,29.048312),
    "M5:BAGLARBASI":         (41.021456,29.036875),
    "M5:BULGURLU":           (41.016286,29.076258),
    "M5:CAKMAK":             (41.021597,29.118626),
    "M5:CARSI":              (41.025940,29.097392),
    "M5:CEKMEKOY":           (41.014529,29.189513),
    "M5:FISTIKAGACI":        (41.028369,29.028561),
    "M5:IHLAMURKUYU":        (41.019781,29.130627),
    "M5:KISIKLI":            (41.022185,29.062079),
    "M5:PARSELLER":          (41.031252,29.152679),
    "M5:UMRANIYE":           (41.024613,29.084797),
    "M5:USKUDAR":            (41.025340,29.012763),
    "M5:YAMANEVLER":         (41.024079,29.108681),
    # ─ M6 ─
    "M6:BOGAZICIUNIVERSITESIHISARUSTU": (41.085135,29.045641),
    "M6:ETILER":             (41.082443,29.037641),
    "M6:LEVENT":             (41.075798,29.014469),
    "M6:NISPETIYE":          (41.077352,29.024001),
    # ─ M7 ─
    "M7:ALIBEYKOY":          (41.079165,28.949588),
    "M7:CAGLAYAN":           (41.070799,28.980628),
    "M7:CIRCIRMAHALLESI":    (41.080284,28.936193),
    "M7:FULYA":              (41.061822,29.007567),
    "M7:GOZTEPE":            (41.056556,28.847278),
    "M7:KAGITHANE":          (41.080186,28.976622),
    "M7:KARADENIZMAHALLESI": (41.081339,28.874930),
    "M7:KAZIMKARABEKIR":     (41.085461,28.908546),
    "M7:MAHMUTBEY":          (41.054935,28.830961),
    "M7:MECIDIYEKOY":        (41.065176,28.995519),
    "M7:NURTEPE":            (41.079960,28.963282),
    "M7:ORUCREISYUZYIL":     (41.062896,28.855279),
    "M7:VEYSELKARANIAKSEMSETTIN": (41.079757,28.928176),
    "M7:YENIMAHALLE":        (41.083819,28.892680),
    "M7:YESILPINAR":         (41.082415,28.918340),
    "M7:YILDIZ":             (41.054006,29.009844),
    # ─ M8 ─
    "M8:BOSTANCI":           (40.951606,29.096615),
    "M8:CAKMAK":             (41.021597,29.118626),
    "M8:CEKMEKOY":           (41.014529,29.189513),
    "M8:DUDULLU":            (41.015184,29.163213),
    "M8:IHLAMURKUYU":        (41.019781,29.130627),
    "M8:KOZYATAGI":          (40.977607,29.099836),
    "M8:KUCUKBAKKALKOY":     (40.979141,29.111775),
    "M8:PARSELLER":          (41.031252,29.152679),
    "M8:SARIGAZI":           (41.010030,29.212676),
    "M8:YAMANEVLER":         (41.024079,29.108681),
    "M8:YENISAHRA":          (40.984485,29.090260),
    # ─ M9 ─
    "M9:ATAKOY":             (40.980008,28.856293),
    "M9:ATAKOYSIRINEVLER":   (40.991379,28.845771),
    "M9:BAHCELIEVLER":       (40.995481,28.863314),
    "M9:BAKIRKOYINCIRLI":    (40.996621,28.875362),
    "M9:COBANCESME":         (40.999733,28.822478),
    "M9:DTMISTANBULFUARMERKEZI": (40.986602,28.828474),
    "M9:HAZNEDAR":           (41.004705,28.871897),
    "M9:IKITELLISANAYI":     (41.071152,28.803628),
    "M9:INCIRLI":            (40.997651,28.875318),
    "M9:MIMARSINAN":         (41.025047,28.816359),
    "M9:YENIBOSNA":          (40.989464,28.838119),
    "M9:ZEYTINBURNU":        (41.001717,28.889975),
}

# Overpass koordinat önbelleği (hat adına göre)
_ovp_cache = {}
_ovp_ts    = {}

def norm(s):
    return re.sub(r"[^A-Z0-9]","",s.upper().translate(str.maketrans("ğĞşŞçÇüÜöÖıİ","gGsScCuUoOiI")))

def get_ovp_coords(hat):
    if hat in _ovp_cache and time.time()-_ovp_ts.get(hat,0)<3600:
        return _ovp_cache[hat]
    bbox = LINE_BBOX.get(hat)
    result = {}
    if bbox:
        s,w,n,e = bbox
        q = f"""[out:json][timeout:20];
node["station"="subway"]({s},{w},{n},{e});
out body;"""
        try:
            r = req.post(OVP,data={"data":q},timeout=25)
            for nd in r.json().get("elements",[]):
                nm = nd.get("tags",{}).get("name","")
                if nm: result[norm(nm)] = (nd["lat"],nd["lon"])
        except: pass
    _ovp_cache[hat] = result
    _ovp_ts[hat] = time.time()
    return result

def koord(hat, st_name):
    """Koordinatı bul: önce hat+isim, sonra hat bbox'ı içinde isim eşleşmesi."""
    k  = f"{hat}:{norm(st_name)}"
    if k in HC:
        return HC[k]
    # Aynı normalize isim, farklı hat kaydı var mı?
    nk   = norm(st_name)
    bbox = LINE_BBOX.get(hat)
    # HC'de diğer hatların aynı isimli istasyonlarına bak
    for ck, cv in HC.items():
        if ck.endswith(f":{nk}"):
            if bbox:
                s,w,n,e = bbox
                if s<=cv[0]<=n and w<=cv[1]<=e:
                    return cv
            else:
                return cv
    # Overpass önbelleğinden dene
    ovp = get_ovp_coords(hat)
    if nk in ovp:
        return ovp[nk]
    for ok,ov in ovp.items():
        if nk in ok or ok in nk:
            return ov
    return None

def ara_noktalar(lat1,lon1,lat2,lon2,n=4):
    """n ara nokta (sadece endpoint'ler dahil değil)."""
    return [(lat1+(lat2-lat1)*i/(n+1), lon1+(lon2-lon1)*i/(n+1)) for i in range(1,n+1)]

# ── IBB/metro.istanbul yardımcıları ─────────────────────────────────────────
def ibb(ep):
    r = req.get(f"{IBB}/{ep}",headers={"User-Agent":"M"},timeout=15)
    r.raise_for_status(); return r.json().get("Data",[])

def yeni_s():
    s=req.Session(); s.verify=False
    s.headers.update({"User-Agent":"Mozilla/5.0"}); return s

def kod(s):
    r=s.get(PAGE,timeout=15); r.raise_for_status()
    m=re.search(r'formData\.append\(\s*["\']kod["\']\s*,\s*["\']'
                r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})["\']',
                r.text,re.I)
    return m.group(1) if m else None

def tarife(s,st,rt,tarih,k):
    r=s.post(AJAX,data={"secim":"0","saat":"","dakika":"","tarih1":"","tarih2":tarih,
        "station":str(st),"route":str(rt),"kod":k},
        headers={"Accept":"application/json,*/*","X-Requested-With":"XMLHttpRequest",
                 "Referer":PAGE},timeout=15)
    r.raise_for_status()
    try: v=r.json()
    except: return []
    if isinstance(v,dict) and str(v.get("durum"))=="-1": return []
    return v.get("sefer",[]) if isinstance(v,dict) else (v or [])

def s2min(s): h,m=map(int,s.split(":")); return h*60+m
def s2dt(s,baz):
    h,m=map(int,s.split(":")); dt=baz.replace(hour=h,minute=m,second=0,microsecond=0)
    if h<4 and baz.hour>20: dt+=timedelta(days=1); return dt

def sure_siteden(s,hat):
    try:
        r=s.get(HATPG.format(hat),timeout=10)
        m=re.search(r"(?:sefer|seyahat)\s+s.resi\s*[:\-]\s*([\d,\.]+)\s*dakika",r.text,re.I)
        if m: return int(float(m.group(1).replace(",",".")))
    except: pass
    return None

# ── Tren hesaplama ────────────────────────────────────────────────────────────
def hat_trenler(hat, tarih, simdi):
    s    = yeni_s()
    renk = RENKLER.get(hat["Name"],"#888")
    try:
        yonler = ibb(f"GetDirectionById/{hat['Id']}")
        istler = ibb(f"GetStationById/{hat['Id']}")
        sure   = sure_siteden(s,hat["Name"]) or max((len(istler)-1)*2.5,8)
        n      = len(istler)
        dk     = sure/(n-1) if n>1 else sure
        zamlar = [i*dk for i in range(n)]
        trenler= []
        for yon in yonler:
            bp = yon["DirectionName"].split("->")[0].strip().upper().split()[0]
            bs = next((x for x in istler if bp in x["Name"].upper()),istler[0])
            try:
                k2=kod(s); sf=tarife(s,bs["Id"],yon["DirectionId"],tarih,k2)
            except: continue
            if not sf: continue
            sf_dt=sorted({s2dt(x["zaman"],simdi) for x in sf})
            for kal in sf_dt:
                bit=kal+timedelta(minutes=sure)
                if kal>simdi or bit<simdi: continue
                gecen=(simdi-kal).total_seconds()/60
                for i in range(n-1):
                    if zamlar[i]<=gecen<zamlar[i+1]:
                        seg_sure = zamlar[i+1]-zamlar[i]
                        pct      = (gecen-zamlar[i])/seg_sure  # 0..1
                        # 4 ara nokta: toplam 6 konum (0,1,2,3,4,5 indeks)
                        c1 = koord(hat["Name"],istler[i]["Name"])
                        c2 = koord(hat["Name"],istler[i+1]["Name"])
                        if not c1 or not c2: break
                        # Hangi waypoint'e en yakın?
                        waypoints = [c1] + ara_noktalar(c1[0],c1[1],c2[0],c2[1],4) + [c2]
                        wp_pcts   = [j/5 for j in range(6)]
                        en_yakin  = min(range(6), key=lambda j: abs(wp_pcts[j]-pct))
                        lat,lon   = waypoints[en_yakin]
                        # Sonraki waypoint (animasyon için)
                        nx = min(en_yakin+1, 5)
                        nlat,nlon = waypoints[nx]
                        # Sonraki waypoint'e kalan süre (sn)
                        kalan_pct  = wp_pcts[nx] - pct
                        kalan_sn   = max(1, int(kalan_pct * seg_sure * 60))
                        trenler.append({
                            "id"      : f"{hat['Name']}-{kal.strftime('%H%M')}-{yon['DirectionId']}",
                            "hat"     : hat["Name"],
                            "renk"    : renk,
                            "kalkis"  : kal.strftime("%H:%M"),
                            "nereden" : istler[i]["Name"].title(),
                            "nereye"  : istler[i+1]["Name"].title(),
                            "lat"     : round(lat,6),
                            "lon"     : round(lon,6),
                            "nlat"    : round(nlat,6),
                            "nlon"    : round(nlon,6),
                            "kalan_sn": kalan_sn,
                            "wp_idx"  : en_yakin,
                        }); break
        return trenler
    except: return []

# ── Endpoints ────────────────────────────────────────────────────────────────
@app.route("/api/trenler")
def api_trenler():
    hatlar=[h for h in ibb("GetLines") if h["Name"] in METRO]
    for h in hatlar: h["renk"]=RENKLER.get(h["Name"],"#888")
    simdi=datetime.today(); tarih=simdi.strftime("%d.%m.%Y")
    sonuc=[]
    with ThreadPoolExecutor(max_workers=5) as ex:
        fs=[ex.submit(hat_trenler,h,tarih,simdi) for h in hatlar]
        for f in as_completed(fs):
            try: sonuc.extend(f.result())
            except: pass
    gun=["Pzt","Sal","Çar","Per","Cum","Cmt","Paz"][simdi.weekday()]
    return jsonify({"trenler":sonuc,"sayi":len(sonuc),
                    "saat":simdi.strftime("%H:%M"),"tarih":f"{simdi.strftime('%d.%m.%Y')} {gun}"})

@app.route("/api/hatlar")
def api_hatlar():
    hatlar=[h for h in ibb("GetLines") if h["Name"] in METRO]
    sonuc=[]
    for hat in hatlar:
        renk=RENKLER.get(hat["Name"],"#888")
        istler=ibb(f"GetStationById/{hat['Id']}")
        stlar=[]
        for st in istler:
            c=koord(hat["Name"],st["Name"])
            if c: stlar.append({"id":st["Id"],"name":st["Name"].title(),"lat":c[0],"lon":c[1]})
        sonuc.append({"name":hat["Name"],"renk":renk,"istasyonlar":stlar})
    return jsonify(sonuc)

# ── HTML Board ───────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Metro İstanbul · Canlı</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;overflow:hidden;background:#0d1117}
#map{position:absolute;inset:0;z-index:0}

/* ─ Top bar ─ */
#bar{position:absolute;top:0;left:0;right:0;z-index:900;height:46px;
  background:rgba(13,17,23,.92);backdrop-filter:blur(10px);
  border-bottom:1px solid rgba(255,255,255,.08);
  display:flex;align-items:center;gap:14px;padding:0 18px}
#logo{width:26px;height:26px;background:#E8421B;border-radius:6px;
  display:flex;align-items:center;justify-content:center;font-weight:900;font-size:.75rem;flex-shrink:0}
#bar-title{font-size:.88rem;font-weight:600;color:#e6edf3;letter-spacing:.3px}
#bar-status{font-size:.72rem;color:#6e7681}
#bar-saat{margin-left:auto;font-size:1rem;font-weight:700;color:#e6edf3;
  letter-spacing:.08em;font-variant-numeric:tabular-nums}
#yenile{margin-left:10px;background:none;border:1px solid rgba(255,255,255,.12);
  color:#8b949e;padding:4px 11px;border-radius:6px;cursor:pointer;font-size:.72rem}
#yenile:hover{border-color:#E8421B;color:#e6edf3}

/* ─ Legend ─ */
#legend{position:absolute;bottom:20px;left:14px;z-index:900;
  background:rgba(13,17,23,.9);backdrop-filter:blur(8px);
  border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:10px 13px}
.leg{display:flex;align-items:center;gap:7px;padding:3px 4px;cursor:pointer;border-radius:4px}
.leg:hover{background:rgba(255,255,255,.05)}
.leg.off .ld{opacity:.25}.leg.off .ln{opacity:.25}
.ld{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.ln{font-size:.78rem;font-weight:700;color:#e6edf3}

/* ─ Leaflet overrides ─ */
.leaflet-popup-content-wrapper{
  background:#161b22;border:1px solid rgba(255,255,255,.1);
  color:#e6edf3;border-radius:10px;box-shadow:0 8px 32px rgba(0,0,0,.6)}
.leaflet-popup-tip{background:#161b22}
.leaflet-popup-content{margin:10px 13px;font-family:'Segoe UI',system-ui,sans-serif;font-size:.82rem}
.leaflet-tooltip{background:rgba(13,17,23,.88);border:1px solid rgba(255,255,255,.1);
  color:#e6edf3;font-size:.68rem;padding:2px 7px;border-radius:4px}
.leaflet-control-zoom a{background:#161b22!important;color:#e6edf3!important;border-color:#30363d!important}
</style>
</head>
<body>

<div id="bar">
  <div id="logo">M</div>
  <span id="bar-title">Metro İstanbul</span>
  <span id="bar-status">Yükleniyor...</span>
  <span id="bar-saat"></span>
  <button id="yenile">↻ Yenile</button>
</div>

<div id="map"></div>

<div id="legend" id="legend-box"></div>

<script>
// ── Harita ────────────────────────────────────────────────────────────────────
const map = L.map("map",{zoomControl:false,attributionControl:false})
              .setView([41.025,28.98],12);

L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  {maxZoom:18,subdomains:"abcd"}).addTo(map);

L.control.zoom({position:"bottomright"}).addTo(map);

// ── Durum ─────────────────────────────────────────────────────────────────────
const hatKatman = {};   // name → {poly, stMk}
const trenMk    = {};   // id → L.marker
let   trenData  = [];
let   gizli     = new Set();
let   lastFetch = 0;
let   animId    = null;

// ── Saat ─────────────────────────────────────────────────────────────────────
function tick(){
  const t=new Date();
  document.getElementById("bar-saat").textContent=
    t.toLocaleTimeString("tr-TR",{hour:"2-digit",minute:"2-digit",second:"2-digit"});
}
setInterval(tick,1000); tick();

// ── API ───────────────────────────────────────────────────────────────────────
const get = url => fetch(url).then(r=>r.json());

// ── Hatları çiz ───────────────────────────────────────────────────────────────
async function hatlarYukle(){
  const hatlar = await get("/api/hatlar");
  const legBox = document.getElementById("legend");
  legBox.innerHTML = hatlar.map(h=>`
    <div class="leg" data-hat="${h.name}" onclick="toggleHat('${h.name}')">
      <div class="ld" style="background:${h.renk}"></div>
      <span class="ln">${h.name}</span>
    </div>`).join("");

  hatlar.forEach(h=>{
    const pts=h.istasyonlar.filter(s=>s.lat&&s.lon).map(s=>[s.lat,s.lon]);
    if(pts.length<2) return;
    const poly=L.polyline(pts,{color:h.renk,weight:3.5,opacity:.85,
      lineJoin:"round",lineCap:"round"}).addTo(map);

    const stMk=h.istasyonlar.filter(s=>s.lat&&s.lon).map(st=>{
      const m=L.circleMarker([st.lat,st.lon],{
        radius:3.5,fillColor:"#0d1117",color:h.renk,fillOpacity:1,weight:2.5
      }).addTo(map);
      m.bindTooltip(st.name,{direction:"top",offset:[0,-4]});
      return m;
    });
    hatKatman[h.name]={poly,stMk,renk:h.renk};
  });
}

function toggleHat(hat){
  const el=document.querySelector(`.leg[data-hat="${hat}"]`);
  const k=hatKatman[hat]; if(!k) return;
  if(gizli.has(hat)){
    gizli.delete(hat);
    k.poly.addTo(map); k.stMk.forEach(m=>m.addTo(map));
    el.classList.remove("off");
  } else {
    gizli.add(hat);
    map.removeLayer(k.poly); k.stMk.forEach(m=>map.removeLayer(m));
    el.classList.add("off");
  }
  trenData.forEach(t=>{
    const mk=trenMk[t.id]; if(!mk) return;
    if(gizli.has(t.hat)) try{map.removeLayer(mk)}catch(e){}
    else mk.addTo(map);
  });
}

// ── Tren marker ───────────────────────────────────────────────────────────────
function mkTren(t){
  const mk=L.circleMarker([t.lat,t.lon],{
    radius:7,fillColor:t.renk,color:"rgba(255,255,255,.9)",
    fillOpacity:1,weight:2
  });
  mk.bindPopup(`
    <div style="min-width:155px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px">
        <span style="width:10px;height:10px;border-radius:50%;background:${t.renk};display:inline-block"></span>
        <b>${t.hat}</b>
        <span style="margin-left:auto;font-size:.68rem;color:#8b949e">${t.kalkis}</span>
      </div>
      <div>${t.nereden}</div>
      <div style="color:#6e7681;font-size:.75rem;margin:3px 0">▼ sonraki durak</div>
      <div>${t.nereye}</div>
    </div>`);
  if(!gizli.has(t.hat)) mk.addTo(map);
  return mk;
}

// ── Tren verisi çek ───────────────────────────────────────────────────────────
async function trenlerCek(){
  document.getElementById("bar-status").textContent="Güncelleniyor...";
  try{
    const veri=await get("/api/trenler");
    lastFetch=Date.now();

    // Eski markerları sil
    Object.values(trenMk).forEach(m=>{try{map.removeLayer(m)}catch(e){}});
    Object.keys(trenMk).forEach(k=>delete trenMk[k]);

    trenData=veri.trenler;
    trenData.forEach(t=>{ trenMk[t.id]=mkTren(t); });

    document.getElementById("bar-status").textContent=
      `${veri.sayi} aktif tren · ${veri.tarih}`;
  } catch(e){
    document.getElementById("bar-status").textContent="Bağlantı hatası";
  }
}

// ── Animasyon: trenler sonraki waypoint'e doğru kayar ────────────────────────
function anim(){
  const gecenSn=(Date.now()-lastFetch)/1000;
  trenData.forEach(t=>{
    const mk=trenMk[t.id]; if(!mk||gizli.has(t.hat)) return;
    // Sonraki waypoint'e ne kadar ilerlendi?
    const ilerlemeSn=Math.min(gecenSn, t.kalan_sn);
    const oran=t.kalan_sn>0 ? ilerlemeSn/t.kalan_sn : 1;
    const lat=t.lat+(t.nlat-t.lat)*oran;
    const lon=t.lon+(t.nlon-t.lon)*oran;
    if(isFinite(lat)&&isFinite(lon)) mk.setLatLng([lat,lon]);
  });
  animId=requestAnimationFrame(anim);
}

// ── Başlat ────────────────────────────────────────────────────────────────────
document.getElementById("yenile").addEventListener("click",trenlerCek);

hatlarYukle().then(()=>{
  trenlerCek();
  setInterval(trenlerCek,60000);
  anim();
});
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
