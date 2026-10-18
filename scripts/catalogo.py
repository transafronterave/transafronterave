#!/usr/bin/env python3
"""Regenera productos.json + img/ a partir de datos públicos de tiendas colombianas.
Uso: python3 scripts/catalogo.py [--no-img] [--max N]
Los datos internos (tienda/URL de origen) se guardan en scripts/data/ (no publicado, .gitignore).
"""
import json, re, os, sys, time, math, hashlib, io, urllib.parse, argparse
import requests
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "scripts", "data")
IMG = os.path.join(ROOT, "img")
UA = "Mozilla/5.0 (X11; Linux x86_64) TransafronteraCatalog/1.0 (+catalogo semanal)"
S = requests.Session(); S.headers["User-Agent"] = UA
DELAY = 0.8

def get(url, **kw):
    for i in range(3):
        try:
            time.sleep(DELAY)
            r = S.get(url, timeout=30, **kw)
            if r.status_code in (200, 206): return r
            if r.status_code in (429, 503): time.sleep(5 * (i + 1)); continue
            return r
        except requests.RequestException as e:
            print("  err", e, file=sys.stderr); time.sleep(3)
    return None

# (categoría, consulta, kg estimado, emoji). Se toman los más vendidos/relevantes.
Q = {
 "Tecnología": [("audifonos bluetooth",.25,"🎧"),("parlante bluetooth",.6,"🔊"),("mouse inalambrico",.2,"🖱️"),("teclado",.6,"⌨️"),("smartwatch",.2,"⌚"),("cargador",.2,"🔌"),("memoria usb",.05,"💾"),("power bank",.35,"🔋"),("cable usb",.1,"🔌")],
 "Celulares": [("celular",.4,"📱"),("tablet",.7,"📱")],
 "Hogar": [("organizador",.6,"🏠"),("linterna",.3,"🔦"),("termo",.5,"🥤"),("sarten",1.2,"🍳"),("juego de cubiertos",.8,"🍴"),("toalla",.6,"🛁"),("lampara led",.5,"💡")],
 "Electrodomésticos": [("licuadora",2.5,"🥤"),("sanduchera",1.5,"🥪"),("batidora",1.5,"🍰"),("freidora de aire",4.5,"🍟"),("cafetera",2,"☕"),("plancha de ropa",1.2,"👕"),("ventilador",3,"🌀"),("hervidor",1.2,"🫖")],
 "Herramientas": [("taladro",2,"🔩"),("destornillador",.3,"🪛"),("juego de llaves",1.5,"🔧"),("brocas",.4,"🔩"),("pulidora",2.5,"⚙️"),("alicate",.4,"🔧"),("metro cinta",.3,"📏"),("caja de herramientas",2,"🧰")],
 "Papelería": [("colores",.3,"🖍️"),("cuaderno",.4,"📓"),("marcadores",.3,"🖊️"),("calculadora",.3,"🧮"),("morral",.7,"🎒"),("lapiceros",.15,"🖊️"),("cartuchera",.2,"✏️")],
 "Juguetes": [("lego",.6,"🧱"),("muñeca",.6,"🪆"),("carro control remoto",1,"🚗"),("juego de mesa",.8,"🎲"),("hot wheels",.2,"🏎️"),("peluche",.4,"🧸"),("rompecabezas",.6,"🧩")],
 "Belleza": [("secador de pelo",.8,"💨"),("plancha para cabello",.6,"✨"),("perfume",.4,"🌸"),("maquillaje",.15,"💄"),("afeitadora",.4,"🪒"),("cepillo electrico",.3,"🪥"),("crema",.3,"🧴")],
 "Deportes": [("balon",.5,"⚽"),("termo deportivo",.4,"🥤"),("mancuernas",3,"🏋️"),("tapete yoga",1,"🧘")],
}
EXCL = re.compile(r"televisor|\btv\b|nevera|refrigerador|congelador|lavadora|secadora de ropa|estufa|horno(?! tostador)|microondas|aire acondicionado|sof[aá]|colch[oó]n|cama\b|base cama|mueble|escritorio|silla|comedor|closet|bicicleta|patineta el[eé]ctrica|scooter|caminadora|el[ií]ptica|gimnasio|monitor|computador de escritorio|all in one|impresora|compresor|generador|hidrolavadora|escalera|carretilla|piscina|parrilla|asador|cilindro|tanque|repuesto|pin |licencia|tarjeta regalo|bono|recarga|garant[ií]a|servicio|instalaci[oó]n|kit escolar x|lavavajilla|torre de sonido|barra de sonido|minicomponente|consola", re.I)
PER_CAT = int(os.environ.get("PER_CAT", "22"))
MINCOP, MAXCOP, MAXKG = 8000, 2500000, 8.0

def kg_from(text):
    if not text: return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|kilo|gr|g)\b", str(text), re.I)
    if not m: return None
    v = float(m.group(1).replace(",", ".")); u = m.group(2).lower()
    if u.startswith("g"): v /= 1000
    return v if 0.01 <= v <= 60 else None

def item(store, src_id, url, name, cat, cop, antes, kg, emo, img, specs=None, rank=0):
    k = None
    for key, val in (specs or {}).items():
        if re.search(r"peso", str(key), re.I) and not re.search(r"soporta|m[aá]x|carga|ropa|usuario", str(key), re.I):
            k = kg_from(" ".join(val) if isinstance(val, list) else val) or k
            if k: break
    return dict(store=store, sid=str(src_id), url=url, n=re.sub(r"\s+", " ", name).strip(), c=cat, cop=int(round(cop)),
                antes=int(round(antes)) if antes and antes > cop * 1.01 else None, kg=round(k or kg, 2),
                kgsrc="spec" if k else "est", e=emo, src_img=img, rank=rank)

# ---------- VTEX ([tienda] / [tienda]) ----------
def vtex(store, base, q, cat, kg, emo, n=40):
    out = []
    url = f"{base}/catalog_system/pub/products/search?ft={urllib.parse.quote(q)}&O=OrderByTopSaleDESC&_from=0&_to={n-1}"
    r = get(url)
    if not r: return out
    try: data = r.json()
    except Exception: return out
    for rk, p in enumerate(data):
        try:
            it = p["items"][0]; off = it["sellers"][0]["commertialOffer"]
            if not off.get("AvailableQuantity") or not off.get("Price"): continue
            specs = {k: p.get(k) for k in p.get("allSpecifications", [])}
            home = base.replace("/io/api", "").replace("/api", "")
            out.append(item(store, p["productId"], f"{home}/{p['linkText']}/p", p["productName"], cat, off["Price"],
                            max(off.get("ListPrice") or 0, off.get("PriceWithoutDiscount") or 0), kg, emo,
                            it["images"][0]["imageUrl"].split("?")[0], specs, rk))
        except (KeyError, IndexError, TypeError): pass
    return out

# ---------- Algolia ([tienda]): clave pública de búsqueda publicada en su web ----------
ALK = {}
def alk_cfg():
    if ALK: return ALK
    r = get("https://[tienda]/search/?text=audifonos")
    h = r.text if r else ""
    for k, pat in (("app", r"applicationId\s*:\s*'([^']+)'"), ("key", r"apiKey\s*:\s*'([^']+)'"), ("idx", r"indexName\s*:\s*'([^']+)'")):
        m = re.search(pat, h); ALK[k] = m.group(1) if m else None
    return ALK

def tienda_algolia(q, cat, kg, emo, n=40):
    c = alk_cfg()
    if not c.get("key"): print("  [tienda]: sin configuración de búsqueda", file=sys.stderr); return []
    time.sleep(DELAY)
    try:
        r = S.post(f"https://{c['app'].lower()}-dsn.algolia.net/1/indexes/{c['idx']}/query",
                   headers={"X-Algolia-Application-Id": c["app"], "X-Algolia-API-Key": c["key"], "Referer": "https://[tienda]/"},
                   json={"params": urllib.parse.urlencode({"query": q, "hitsPerPage": n})}, timeout=30)
        hits = r.json().get("hits", [])
    except Exception as e:
        print("  [tienda] err", e, file=sys.stderr); return []
    out = []
    for rk, h in enumerate(hits):
        try:
            if h.get("stocklevelstatus_string") != "inStock": continue
            cop = float(h.get("pricevalue_cop_double") or h.get("lowestprice_double") or 0)
            antes = float(h.get("baseprice_cop_string") or 0)
            specs = {}
            for a in h.get("comparableattributes_string_mv") or []:
                parts = a.split("=")
                if len(parts) >= 3: specs[parts[1]] = parts[2]
            img = h.get("img-820wx820h_string") or h.get("img-750wx750h_string")
            out.append(item("[tienda]", h["objectID"], "https://[tienda]" + h.get("url_es_string", ""), h["name_text_es"], cat, cop, antes, kg, emo, img, specs, rk))
        except (KeyError, ValueError, TypeError): pass
    return out

# ---------- [tienda] ----------
def tienda_soco(q, cat, kg, emo):
    base = "https://[tienda]/s/search/v1/soco"
    r = get(f"{base}?q={urllib.parse.quote(q)}&priceGroup=10&page=1&zone=")
    try: d = r.json()["data"]
    except Exception: return []
    if "redirectUrl" in d:
        m = re.search(r"/category/(cat\w+)", d["redirectUrl"])
        if not m: return []
        r = get(f"{base}/category/products?categoryId={m.group(1)}&page=1&priceGroup=10&zone=")
        try: d = r.json()["data"]
        except Exception: return []
    out = []
    for rk, p in enumerate(d.get("results", [])):
        try:
            pr = {x["type"]: x["priceWithoutFormatting"] for x in p.get("prices", [])}
            cop = pr.get("INTERNET") or pr.get("EVENT") or pr.get("NORMAL")
            if not cop or not p.get("mediaUrls"): continue
            specs = {h["key"]: h["value"] for h in p.get("highlights", [])}
            out.append(item("[tienda]", p["productId"], f"https://[tienda]/product/{p['productId']}/",
                            p["displayName"], cat, cop, pr.get("NORMAL"), kg, emo, p["mediaUrls"][0], specs, rk))
        except (KeyError, TypeError): pass
    return out

STORES = {
 "[tienda]": lambda q, c, k, e: vtex("[tienda]", "https://[tienda]/io/api", q, c, k, e),
 "[tienda]": lambda q, c, k, e: vtex("[tienda]", "https://[tienda]/api", q, c, k, e),
 "[tienda]": tienda_algolia,
 "[tienda]": tienda_soco,
}
# Qué categorías tiene sentido buscar en cada tienda
SKIP = {"[tienda]": {"Celulares", "Juguetes", "Belleza", "Papelería"}, "[tienda]": {"Herramientas", "Electrodomésticos", "Deportes", "Belleza"},
        "[tienda]": {"Papelería", "Herramientas"}}

import unicodedata
def nrm(t): return "".join(ch for ch in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(ch) != "Mn")
BULKY = re.compile(r"partybox|party box|torre|bafle|karaoke|\b(1[5-9]|[2-9]\d)\s*(\"|pulgadas)|set de \d+ ollas|bater[ií]a de cocina", re.I)

def ok(p):
    # relevancia: el nombre debe contener la raíz de la palabra principal de la consulta
    root = nrm(p["q"].split()[0])[:5]
    if root not in nrm(p["n"]): return False
    wk = kg_from(p["n"])  # p.ej. "Mancuernas 40 Kg"
    if wk and wk > MAXKG and not re.search(r"capacidad|soporta|hasta", p["n"], re.I): return False
    if BULKY.search(p["n"]) and p["c"] != "Celulares": return False
    return (MINCOP <= p["cop"] <= MAXCOP and p["kg"] <= MAXKG and p["src_img"] and not EXCL.search(p["n"]))

def collect():
    allp, seen, fails = [], set(), []
    for st, fn in STORES.items():
        for cat, qs in Q.items():
            if cat in SKIP.get(st, ()): continue
            got = []
            for q, kg, emo in qs:
                try: res = fn(q, cat, kg, emo)
                except Exception as e: res = []; fails.append(f"{st}/{q}: {e}")
                for p in res: p["q"] = q
                if not res: fails.append(f"{st}/{q}: 0 resultados")
                got.append([p for p in res if ok(p)])
            # intercalar consultas para variedad
            picked, i = [], 0
            while len(picked) < PER_CAT and any(i < len(g) for g in got):
                for g in got:
                    if i < len(g):
                        p = g[i]; key = (p["store"], p["sid"]); nk = p["n"].lower()[:40]
                        if key not in seen and nk not in seen and len(picked) < PER_CAT:
                            seen.add(key); seen.add(nk); picked.append(p)
                i += 1
            print(f"{st:13} {cat:18} {len(picked)}", file=sys.stderr)
            allp += picked
    return allp, fails

def save_img(src, dest):
    if os.path.exists(dest): return True
    r = get(src)
    if not r or r.status_code != 200: return False
    try:
        im = Image.open(io.BytesIO(r.content)).convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[3])
        bg.thumbnail((600, 600)); bg.save(dest, "JPEG", quality=75, optimize=True, progressive=True)
        return True
    except Exception: return False

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--no-img", action="store_true"); a = ap.parse_args()
    os.makedirs(DATA, exist_ok=True); os.makedirs(IMG, exist_ok=True)
    prods, fails = collect()
    pub, priv, used = [], [], set()
    for p in prods:
        h = hashlib.sha1(f"{p['store']}:{p['sid']}".encode()).hexdigest()[:10]
        fn = f"img/p{h}.jpg"
        if not a.no_img and not save_img(p["src_img"], os.path.join(ROOT, fn)):
            fails.append(f"img {p['store']}/{p['sid']}"); continue
        used.add(os.path.basename(fn))
        o = {"id": h, "n": p["n"], "c": p["c"], "cop": p["cop"]}
        if p["antes"]: o["antes"] = p["antes"]
        o.update(kg=p["kg"], e=p["e"], img=fn)
        if p["rank"] < 3: o["top"] = 1
        pub.append(o); priv.append({**p, "id": h, "img": fn})
    if not pub: sys.exit("sin productos; no se sobrescribe nada")
    with open(os.path.join(ROOT, "productos.json"), "w", encoding="utf-8") as f:
        json.dump({"actualizado": time.strftime("%Y-%m-%d"), "productos": pub}, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(DATA, "fuentes.json"), "w", encoding="utf-8") as f:
        json.dump({"productos": priv, "fallos": fails}, f, ensure_ascii=False, indent=1)
    if not a.no_img:  # borrar imágenes huérfanas
        for x in os.listdir(IMG):
            if x.startswith("p") and x.endswith(".jpg") and x not in used: os.remove(os.path.join(IMG, x))
    from collections import Counter
    print(json.dumps({"total": len(pub), "por_tienda": Counter(p["store"] for p in priv), "por_categoria": Counter(p["c"] for p in priv),
                      "fallos": len(fails)}, ensure_ascii=False, indent=1))

if __name__ == "__main__": main()
