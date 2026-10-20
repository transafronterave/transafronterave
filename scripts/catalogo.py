#!/usr/bin/env python3
"""Regenera productos.json + img/ a partir de datos públicos de tiendas colombianas.
Uso: python3 scripts/catalogo.py [--no-img] [--max N]
Los datos internos (tienda/URL de origen) se guardan en scripts/data/ (no publicado, .gitignore).
"""
import json, re, os, sys, time, math, hashlib, io, urllib.parse, argparse, html
import requests
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "scripts", "data")
IMG = os.path.join(ROOT, "img")
UA = "Mozilla/5.0 (X11; Linux x86_64) TransafronteraCatalog/1.0 (+catalogo semanal)"
S = requests.Session(); S.headers["User-Agent"] = UA
DELAY = 0.8

def get(url, delay=None, **kw):
    for i in range(3):
        try:
            time.sleep(delay or DELAY)
            r = S.get(url, timeout=30, **kw)
            if r.status_code in (200, 206): return r
            print(f"  {r.status_code} {url[:90]}", file=sys.stderr)
            if r.status_code in (429, 503):
                ra = str(r.headers.get("Retry-After") or ""); time.sleep(min(int(ra), 60) if ra.isdigit() else 5 * (i + 1)); continue
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
# Perfiles de tienda (farmacias / jugueterías): consultas propias y solo estas categorías.
Q_FARMA = {
 "Belleza": [("crema hidratante",.25,"🧴"),("protector solar",.2,"☀️"),("serum facial",.1,"💧"),("limpiador facial",.25,"🧼"),("shampoo",.45,"🧴"),("acondicionador",.45,"🧴"),("tratamiento capilar",.3,"💆"),("contorno de ojos",.08,"👁️")],
 "Maquillaje": [("base maquillaje",.1,"💄"),("labial",.05,"💋"),("pestañina",.05,"👁️"),("polvo compacto",.08,"💄"),("delineador",.04,"✏️"),("corrector",.05,"💄"),("rubor",.06,"🌸"),("sombras",.1,"🎨")],
 "Cuidado personal": [("desodorante",.2,"🧴"),("crema dental",.2,"🪥"),("cepillo dental",.08,"🪥"),("enjuague bucal",.6,"🫧"),("jabon liquido",.5,"🧼"),("crema corporal",.45,"🧴"),("toallas higienicas",.2,"🌸"),("maquina de afeitar",.1,"🪒")],
 "Vitaminas y venta libre": [("vitamina c",.15,"💊"),("multivitaminico",.2,"💊"),("omega 3",.2,"🐟"),("colageno",.4,"💊"),("magnesio",.2,"💊"),("acetaminofen",.05,"💊"),("ibuprofeno",.05,"💊"),("antiacido",.15,"💊"),("curitas",.05,"🩹"),("gasa",.08,"🩹"),("alcohol antiseptico",.4,"🩹"),("suero oral",.5,"💧")],
}
# Tiendas de deporte: sin bicicletas, máquinas ni muebles (ver EXCL); accesorios de ciclismo sí.
Q_DEPORTES = {
 "Calzado deportivo": [("tenis running",.9,"👟"),("tenis trail",.9,"👟"),("tenis caminar",.8,"👟"),("tenis entrenamiento",.8,"👟"),("zapatos senderismo",1.1,"🥾"),("tenis senderismo",1.1,"🥾"),("botas senderismo",1.4,"🥾"),("zapatos acuaticos",.4,"🩴"),("tenis baloncesto",1,"🏀")],
 "Ropa deportiva": [("camiseta running",.2,"👕"),("camiseta running mujer",.2,"👕"),("leggings",.25,"🩱"),("pantaloneta",.25,"🩳"),("top deportivo",.15,"👙"),("chaqueta running",.4,"🧥"),("chaqueta impermeable",.5,"🧥"),("medias deportivas",.1,"🧦"),("jersey ciclismo",.25,"🚴"),("vestido de baño",.25,"🩱"),("gorra deportiva",.1,"🧢"),("camiseta senderismo",.2,"👕")],
 "Deportes": [("balon futbol",.5,"⚽"),("balon baloncesto",.65,"🏀"),("balon voleibol",.3,"🏐"),("mancuernas",3,"🏋️"),("pesa rusa",4,"🏋️"),("mat de yoga",1.2,"🧘"),("bloque yoga",.4,"🧘"),("banda elastica",.2,"🏋️"),("lazo para saltar",.3,"🤸"),("gafas de natacion",.1,"🥽"),("gorro de natacion",.08,"🏊"),("aletas",.7,"🏊"),("casco ciclismo",.4,"🚴"),("casco mtb",.4,"🚴"),("luz bicicleta",.15,"🚲"),("guantes ciclismo",.1,"🧤"),("candado",.6,"🔒"),("caramañola",.15,"🥤"),("botella running",.15,"🥤"),("guantes de boxeo",.7,"🥊"),("pelotas de padel",.3,"🎾"),("maleta deportiva",.7,"🎒")],
 "Camping": [("carpa",3,"⛺"),("carpa camping",3.5,"⛺"),("sleeping bag",1.2,"🛌"),("linterna",.25,"🔦"),("lampara",.3,"🏮"),("almohada",.3,"🛌"),("taza camping",.3,"☕"),("morral senderismo",.8,"🎒"),("morral 30 litros",1.2,"🎒"),("binoculares",.5,"🔭"),("toalla microfibra",.3,"🏖️")],
}
# Moda: ropa, calzado, bolsos/marroquinería y relojes (sin maletas de viaje grandes).
Q_MODA = {
 "Ropa": [("camiseta",.25,"👕"),("blusa",.25,"👚"),("jean",.6,"👖"),("pantalon",.5,"👖"),("vestido",.4,"👗"),("falda",.3,"👗"),("chaqueta",.8,"🧥"),("buzo",.5,"🧥"),("camisa",.3,"👔")],
 "Calzado": [("tenis",1,"👟"),("zapatos",1,"👞"),("sandalias",.6,"👡"),("botas",1.5,"👢"),("botines",1.3,"👢"),("baletas",.6,"🥿"),("mocasines",.9,"👞")],
 "Bolsos y accesorios": [("bolso",.7,"👜"),("manos libres",.5,"👜"),("maletin",1,"💼"),("tote",.7,"👜"),("morral",.8,"🎒"),("billetera",.15,"👛"),("cinturon",.25,"🪢"),("riñonera",.3,"👝"),("gafas de sol",.15,"🕶️"),("gorra",.15,"🧢"),("aretes",.05,"💍")],
 "Relojes": [("reloj",.3,"⌚"),("reloj hombre",.3,"⌚"),("reloj mujer",.3,"⌚"),("reloj digital",.3,"⌚"),("reloj inteligente",.3,"⌚"),("reloj casio",.3,"⌚")],
}
PERFIL = {"farmacia": Q_FARMA, "juguetes": {"Juguetes": Q["Juguetes"]}, "deportes": Q_DEPORTES, "moda": Q_MODA}
# Solo venta libre: se descartan medicamentos con fórmula, antibióticos, controlados, inyectables y cadena de frío.
RXBLOCK = re.compile(r"f[oó]rmula m[eé]dica|venta bajo|prescripci|antibi[oó]tic|antiinfeccios|controlad|inyect|ampolla|jeringa|aguja|insulina|vacuna|refrigera|cadena de fr[ií]o|\b2\s*°?\s*c?\s*(a|-)\s*8\s*°|amoxi|azitro|cefal|ciproflox|claritro|doxicicl|metronid|clindami|penicil|tramadol|code[ií]na|morfina|oxicod|clonazep|alpraz|diazep|lorazep|zolpidem|fentan|pregabal|gabapent|anticoncept|levonorg|hormon|testoster|estradi|cortico|prednis|dexameta|betameta|sildenaf|tadalaf|metformin|losart|enalapr|atorvast|omepraz|esomepraz|isotretin|finaster|minoxidil oral|clopidog|warfar|tretino|antidepres|sertral|fluoxet|quetiap|risperid|ketorolac|diclofenac.*(ampolla|inyect)|n[aá]proxeno s[oó]dico 550|metocarbam|tizanid|orfenadr|carisoprod|\b800\s*mg|\b\d{2,3}\.?000\s*u\.?i", re.I)

EXCL = re.compile(r"televisor|\btv\b|nevera|refrigerador|congelador|lavadora|secadora de ropa|estufa|horno(?! tostador)|microondas|aire acondicionado|sof[aá]|colch[oó]n|cama\b|base cama|mueble|escritorio|silla|comedor|closet|(?<!para )(?<!de )(?<!la )bicicleta|maleta (ejecutiva )?de viaje|equipaje|trolley|patineta el[eé]ctrica|scooter|caminadora|el[ií]ptica|gimnasio|monitor|computador de escritorio|all in one|impresora|compresor|generador|hidrolavadora|escalera|carretilla|piscina|parrilla|asador|cilindro|tanque|repuesto|pin |licencia|tarjeta regalo|bono|recarga|garant[ií]a|servicio|instalaci[oó]n|kit escolar x|lavavajilla|torre de sonido|barra de sonido|minicomponente|consola", re.I)
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

# ---------- Fuentes ----------
# La configuración de tiendas (URLs, nombres) NO se publica: se lee de la variable de entorno
# CATALOGO_FUENTES (secreto del repo) o de scripts/data/fuentes_config.json (.gitignore).
def load_cfg():
    raw = os.environ.get("CATALOGO_FUENTES")
    if not raw:
        fp = os.path.join(DATA, "fuentes_config.json")
        if os.path.exists(fp): raw = open(fp, encoding="utf-8").read()
    if not raw: sys.exit("Falta CATALOGO_FUENTES o scripts/data/fuentes_config.json")
    return json.loads(raw)

def rx_vtex(p):
    sp = {k: " ".join(map(str, p.get(k) or [])) for k in p.get("allSpecifications", [])}
    if re.search(r"^s[ií]", sp.get("Producto RX", ""), re.I) or re.search(r"rx|f[oó]rmula", sp.get("Producto Formulado", ""), re.I): return True
    txt = " ".join(p.get("categories", [])) + " " + " ".join(sp.values())
    return bool(RXBLOCK.search(txt))

def vtex(t, q, cat, kg, emo, n=40):
    out = []
    r = get(f"{t['api']}/catalog_system/pub/products/search?ft={urllib.parse.quote(q)}&O=OrderByTopSaleDESC&_from=0&_to={n-1}")
    if not r: return out
    try: data = r.json()
    except Exception: return out
    for rk, p in enumerate(data):
        try:
            it = p["items"][0]; off = it["sellers"][0]["commertialOffer"]
            if not off.get("AvailableQuantity") or not off.get("Price"): continue
            if t.get("perfil") == "farmacia" and rx_vtex(p): continue
            specs = {k: p.get(k) for k in p.get("allSpecifications", [])}
            out.append(item(t["nombre"], p["productId"], f"{t['home']}/{p['linkText']}/p", p["productName"], cat, off["Price"],
                            max(off.get("ListPrice") or 0, off.get("PriceWithoutDiscount") or 0), kg, emo,
                            it["images"][0]["imageUrl"].split("?")[0], specs, rk))
        except (KeyError, IndexError, TypeError): pass
    return out

# Índice de búsqueda: la clave pública de solo-búsqueda se lee de la propia página de búsqueda de la tienda.
def algolia(t, q, cat, kg, emo, n=40):
    if "_c" not in t:
        r = get(t["page"]); h = r.text if r else ""; c = {}
        for k, pat in (("app", r"applicationId\s*:\s*'([^']+)'"), ("key", r"apiKey\s*:\s*'([^']+)'"), ("idx", r"indexName\s*:\s*'([^']+)'")):
            m = re.search(pat, h); c[k] = m.group(1) if m else None
        t["_c"] = c
    c = t["_c"]
    if not c.get("key"): print("  algolia: sin configuración", file=sys.stderr); return []
    time.sleep(DELAY)
    try:
        r = S.post(f"https://{c['app'].lower()}-dsn.algolia.net/1/indexes/{c['idx']}/query",
                   headers={"X-Algolia-Application-Id": c["app"], "X-Algolia-API-Key": c["key"], "Referer": t["home"] + "/"},
                   json={"params": urllib.parse.urlencode({"query": q, "hitsPerPage": n})}, timeout=30)
        hits = r.json().get("hits", [])
    except Exception as e:
        print("  algolia err", e, file=sys.stderr); return []
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
            out.append(item(t["nombre"], h["objectID"], t["home"] + h.get("url_es_string", ""), h["name_text_es"], cat, cop, antes, kg, emo, img, specs, rk))
        except (KeyError, ValueError, TypeError): pass
    return out

def soco(t, q, cat, kg, emo):
    base = t["api"]
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
            out.append(item(t["nombre"], p["productId"], f"{t['home']}{p['productId']}/",
                            p["displayName"], cat, cop, pr.get("NORMAL"), kg, emo, p["mediaUrls"][0], specs, rk))
        except (KeyError, TypeError): pass
    return out

# Plataforma con sesión de invitado; el detalle trae stock y banderas de regulación/fórmula/cadena de frío.
def sfcc(t, q, cat, kg, emo, n=24):
    if "_s" not in t:
        time.sleep(DELAY)
        try: t["_s"] = S.post(f"{t['api']}/customer-service/login", json={}, timeout=30).ok
        except requests.RequestException: t["_s"] = False
    inv = t.get("inv", "COL_INV_DEFAULT")
    r = get(f"{t['api']}/product-service/products/search?limit={n}&offset=0&sort=&q={urllib.parse.quote(q)}&inventoryId={inv}")
    try: hits = r.json().get("hits", [])
    except Exception: return []
    out = []
    for rk, h in enumerate(hits):
        if len(out) >= 12: break
        if root_miss(q, h.get("productName", "")) or RXBLOCK.search(h.get("productName", "")): continue
        d = get(f"{t['api']}/product-service/products/detail/{h['productId']}?inventoryId={inv}")
        try: p = d.json()["productData"]
        except Exception: continue
        if not p.get("stock") or p.get("regulated") or p.get("isMedProduct") or p.get("isFreezerRequired") or p.get("showModalContraceptive"): continue
        if RXBLOCK.search(" ".join(str(p.get(k, "")) for k in ("categoria", "pageKeywords", "activeIngredient"))): continue
        pr = p.get("prices") or {}
        cop = pr.get("price-sale-col") or pr.get("price-list-col") or p.get("price")
        try: img = p["imageGroups"][0]["images"][0]["link"]
        except (KeyError, IndexError): img = (h.get("image") or {}).get("link")
        if not cop: continue
        out.append(item(t["nombre"], p["id"], f"{t['home']}/{p.get('pageUrl','')}/{p['id']}.html", p["name"], cat, cop,
                        pr.get("price-list-col"), kg, emo, img, None, rk))
    return out

# Tiendas sin API de búsqueda pública (o con la búsqueda vetada en robots.txt): se leen sus páginas de
# listado de categoría, que sí son públicas e indexables. La config mapea cada consulta a una ruta ("plp").
def _cop(x): return float(re.sub(r"[^\d]", "", x) or 0)

def plp(t, q, cat, kg, emo, n=40):
    path = (t.get("plp") or {}).get(q)
    if not path: return []
    for i in range(3):  # el antibots a veces responde 403 un rato: esperar y reintentar con calma
        r = get(t["home"] + path, delay=t.get("delay"))
        if r is not None and r.status_code == 200: break
        time.sleep(20 * (i + 1))
    else: return []
    out = []
    for rk, a in enumerate(re.findall(r'<article class="product-card.*?</article>', r.text, re.S)[:n]):
        try:
            a = re.sub(r"<svg.*?</svg>", "", a, flags=re.S)
            if re.search(r">\s*Agotado\s*<", a): continue
            m = re.search(r'<h2><a aria-label="([^"]+)" href="(/p/[^"]+)"', a)
            pr = re.search(r'Precio actual</span>(?:\s|<!-- -->)*([^<]+)<', a)
            im = re.search(r'src="(https://[^"?]+)', a)
            if not (m and pr and im): continue
            old = re.search(r'Precio anterior</span>(?:\s|<!-- -->)*([^<]+)<', a)
            name = html.unescape(m.group(1)).rstrip(". ")
            sid = "/".join(m.group(2).split("/")[-2:])
            out.append(item(t["nombre"], sid, t["home"] + m.group(2), name, cat, _cop(pr.group(1)),
                            _cop(old.group(1)) if old else None, kg, emo, im.group(1) + "?format=auto&f=800x0", None, rk))
        except (AttributeError, ValueError, IndexError): pass
    return out

# Plataforma de moda con búsqueda HTML (/catalog/?q=): cada tarjeta trae JSON con precios y stock por talla.
def bob(t, q, cat, kg, emo, n=40):
    r = get(f"{t['api']}?q={urllib.parse.quote(q)}")
    if not r or r.status_code != 200: return []
    out = []
    for rk, c in enumerate(re.split(r'<li\s+id="(?=[A-Z0-9]{10,}")', r.text)[1:n + 1]):
        try:
            d = json.loads(html.unescape(re.search(r'data-default-card="(\{.*?\})"\s*\n', c).group(1)))
            sm = re.search(r"data-simples\s*=\s*'(\{.*?\})'\s*\n", c)
            if sm and not any(int(float(v["meta"].get("quantity") or 0)) > 0 for v in json.loads(html.unescape(sm.group(1))).values()): continue
            url = re.search(r'href="(https?://[^"]+\.html)"', c).group(1)
            img = re.search(r'data-src-default="([^"]+)"', c).group(1)
            name = html.unescape(d["name"])
            cop = float(d.get("special_price") or d.get("price") or 0)
            out.append(item(t["nombre"], d["sku"], url, name, cat, cop, float(d.get("price") or 0), kg, emo, img, None, rk))
        except (AttributeError, ValueError, KeyError, TypeError): pass
    return out

ADAPT = {"sfcc": sfcc, "vtex": vtex, "algolia": algolia, "soco": soco, "plp": plp, "bob": bob}

import unicodedata
def nrm(t): return "".join(ch for ch in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(ch) != "Mn")
BULKY = re.compile(r"carpa.*\b([4-9]|1\d)\s*personas|carpa familiar|2 seconds|partybox|party box|torre|bafle|karaoke|\b(1[5-9]|[2-9]\d)\s*(\"|pulgadas)|set de \d+ ollas|bater[ií]a de cocina", re.I)

def root_miss(q, n): return re.sub(r"(?<=..)s$", "", nrm(q.split()[0]))[:5] not in nrm(n)  # "botas" ~ "Bota"

def ok(p):
    # relevancia: el nombre debe contener la raíz de la palabra principal de la consulta
    if root_miss(p["q"], p["n"]): return False
    # moda: el nombre debe empezar por el tipo de prenda ("Vestido con falda..." no es una falda)
    if p.get("perfil") == "moda" and not nrm(p["n"]).split()[0].startswith(nrm(p["q"].split()[0])[:4]): return False
    if p["c"] in Q_FARMA and RXBLOCK.search(p["n"]): return False
    wk = kg_from(p["n"])  # p.ej. "Mancuernas 40 Kg"
    if wk and wk > MAXKG and not re.search(r"capacidad|soporta|hasta", p["n"], re.I): return False
    if BULKY.search(p["n"]) and p["c"] != "Celulares": return False
    return (MINCOP <= p["cop"] <= MAXCOP and p["kg"] <= MAXKG and p["src_img"] and not EXCL.search(p["n"]))

def collect(solo=None, seen=None):
    allp, seen, fails = [], seen or set(), []
    for key, t in load_cfg().items():
        if solo and key not in solo: continue
        st = t["nombre"]; fn = lambda q, c, k, e, t=t: ADAPT[t["tipo"]](t, q, c, k, e)
        for cat, qs in PERFIL.get(t.get("perfil"), Q).items():
            if cat in t.get("skip", []): continue
            got = []
            for q, kg, emo in list(qs) + [tuple(x) for x in t.get("extra", {}).get(cat, [])]:  # "extra": consultas propias de la tienda
                try: res = fn(q, cat, kg, emo)
                except Exception as e: res = []; fails.append(f"{st}/{q}: {e}")
                for p in res:
                    p["q"], p["perfil"] = q, t.get("perfil")
                    if t.get("quitar"): p["n"] = re.sub(r"\s+", " ", re.sub(t["quitar"], "", p["n"], flags=re.I)).strip(" -,.")
                    p["n"] = re.sub(r"^(.{15,}?) \1\b", r"\1", p["n"])  # "Bolso X Bolso X Negro" -> "Bolso X Negro"
                    wk = kg_from(p["n"]) if re.search(r"mancuerna|pesa|kettlebell|disco", p["n"], re.I) else None
                    if wk and p["kgsrc"] == "est": p["kg"], p["kgsrc"] = round(wk * (2 if re.search(r"\bpar\b", p["n"], re.I) else 1) + .2, 2), "nombre"
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
    ap = argparse.ArgumentParser(); ap.add_argument("--no-img", action="store_true")
    ap.add_argument("--solo", help="claves de tienda separadas por coma; conserva el resto tal cual está publicado en productos.json")
    a = ap.parse_args()
    os.makedirs(DATA, exist_ok=True); os.makedirs(IMG, exist_ok=True)
    pub, priv, used, added = [], [], set(), []
    if a.solo:
        solo = set(a.solo.split(",")); cfg = load_cfg(); names = {cfg[k]["nombre"] for k in solo if k in cfg}
        old = json.load(open(os.path.join(DATA, "fuentes.json"), encoding="utf-8"))["productos"]
        # La acción semanal publica productos.json pero no guarda fuentes.json (privado), así que fuentes.json puede
        # estar desfasado: se conserva tal cual lo publicado de las demás tiendas y solo se reemplaza lo de --solo.
        drop = {p["id"] for p in old if p["store"] in names}
        byid = {p["id"]: p for p in old if p["store"] not in names}
        pubold = json.load(open(os.path.join(ROOT, "productos.json"), encoding="utf-8"))["productos"]
        for o in pubold:
            if o["id"] in drop or not os.path.exists(os.path.join(ROOT, o["img"])): continue
            pub.append(o); used.add(os.path.basename(o["img"]))
            if o["id"] in byid: priv.append(byid[o["id"]])
        seen = {(p["store"], p["sid"]) for p in priv} | {o["n"].lower()[:40] for o in pub}
        prods, fails = collect(solo, seen)
    else:
        prods, fails = collect()
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
        pub.append(o); priv.append({**p, "id": h, "img": fn}); added.append(p)
    if not pub: sys.exit("sin productos; no se sobrescribe nada")
    with open(os.path.join(ROOT, "productos.json"), "w", encoding="utf-8") as f:
        json.dump({"actualizado": time.strftime("%Y-%m-%d"), "productos": pub}, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(DATA, "fuentes.json"), "w", encoding="utf-8") as f:
        json.dump({"productos": priv, "fallos": fails}, f, ensure_ascii=False, indent=1)
    if not a.no_img:  # borrar imágenes huérfanas
        for x in os.listdir(IMG):
            if x.startswith("p") and x.endswith(".jpg") and x not in used: os.remove(os.path.join(IMG, x))
    from collections import Counter
    print(json.dumps({"total": len(pub), "nuevos_por_tienda_categoria": Counter(f'{p["store"]} / {p["c"]}' for p in added),
                      "por_categoria": Counter(o["c"] for o in pub),
                      "fallos": len(fails)}, ensure_ascii=False, indent=1))

if __name__ == "__main__": main()
