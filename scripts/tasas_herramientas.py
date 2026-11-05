#!/usr/bin/env python3
"""Actualiza herramientas/tasas.json y herramientas/tasas.js (BCV, TRM, Binance P2P USDT/COP y USDT/VES).
Solo librería estándar. Si falta alguna tasa obligatoria, NO sobrescribe los archivos (sale con código 1).
Uso (desde la raíz del repo):  python3 scripts/tasas_herramientas.py
Ver docs/HERRAMIENTAS.md para ejecutarlo a diario."""
import json, os, re, ssl, statistics, sys, urllib.request, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "herramientas")
UA = {"User-Agent": "Mozilla/5.0 (tasas TRANSAFRONTERA VE)"}
TZ = datetime.timezone(datetime.timedelta(hours=-5))
now = lambda: datetime.datetime.now(TZ).isoformat(timespec="seconds")
P2P = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
TRM = "https://www.datos.gov.co/resource/32sa-8pi3.json"
BCV = "https://www.bcv.org.ve/"

def get(url, data=None, verify=True):
    h = dict(UA); h.update({"Content-Type": "application/json"} if data else {})
    ctx = None if verify else ssl._create_unverified_context()
    return urllib.request.urlopen(urllib.request.Request(url, data, h), timeout=25, context=ctx).read()

def bcv():
    try: html, ok = get(BCV).decode("utf-8", "ignore"), True
    except ssl.SSLError: html, ok = get(BCV, verify=False).decode("utf-8", "ignore"), False
    except urllib.error.URLError as e:
        if not isinstance(e.reason, ssl.SSLError): raise
        html, ok = get(BCV, verify=False).decode("utf-8", "ignore"), False  # certificado del BCV incompleto; dato público
    m = re.search(r'id="dolar".*?<strong[^>]*>\s*([\d.,]+)\s*</strong>', html, re.S)
    return round(float(m.group(1).strip().replace(".", "").replace(",", ".")), 4), ok

def p2p(fiat, tt):
    b = json.dumps({"asset": "USDT", "fiat": fiat, "tradeType": tt, "page": 1, "rows": 20, "payTypes": [],
                    "publisherType": None, "countries": [], "proMerchantAds": False}).encode()
    d = json.loads(get(P2P, b))["data"]
    return round(statistics.median(float(a["adv"]["price"]) for a in d), 4)

def trm():
    d = json.loads(get(TRM + "?$order=vigenciadesde%20DESC&$limit=10"))
    hoy = datetime.datetime.now(TZ).date().isoformat()
    row = next((r for r in d if r["vigenciadesde"][:10] <= hoy <= r["vigenciahasta"][:10]), d[0])
    return round(float(row["valor"]), 2)

def main():
    v, f, errs = {}, {}, []
    def run(key, label, url, fn):
        try:
            r = fn(); v[key] = r[0] if isinstance(r, tuple) else r
            f.setdefault(label[0], {"label": label[1], "url": url, "fetched_at": now(), "ok": True})
        except Exception as e:
            errs.append(f"{key}: {type(e).__name__}: {e}"[:200])
    run("bcv_usd", ("bcv", "Banco Central de Venezuela (bcv.org.ve)"), BCV, bcv)
    run("trm", ("trm", "TRM — Superintendencia Financiera (datos.gov.co, dataset 32sa-8pi3)"), TRM, trm)
    for fiat, pre, lab in (("COP", "co", "p2p_cop"), ("VES", "ve", "p2p_ves")):
        for tt in ("BUY", "SELL"):
            run(f"{pre}_p2p_{tt.lower()}", (lab, f"Binance P2P USDT/{fiat} (mediana de los primeros anuncios)"), P2P, lambda: p2p(fiat, tt))
    falt = [k for k in ("bcv_usd", "trm", "co_p2p_buy", "ve_p2p_sell") if not v.get(k)]
    if falt:
        print("ERROR: faltan", falt, errs, "-> no se sobrescribe", file=sys.stderr); sys.exit(1)
    out = {"actualizado": now(), "zona": "hora de Bogotá, UTC-5", **{k: v.get(k) for k in
           ("bcv_usd", "trm", "co_p2p_buy", "co_p2p_sell", "ve_p2p_buy", "ve_p2p_sell")}, "fuentes": f}
    txt = json.dumps(out, ensure_ascii=False, indent=1)
    open(os.path.join(OUT, "tasas.json"), "w").write(txt + "\n")
    open(os.path.join(OUT, "tasas.js"), "w").write("window.TASAS = " + txt + ";\n")
    print("OK", out["actualizado"], {k: out[k] for k in ("bcv_usd", "trm", "co_p2p_buy", "ve_p2p_sell")}, errs or "")

if __name__ == "__main__":
    main()
