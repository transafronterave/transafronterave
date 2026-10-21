#!/usr/bin/env python3
"""Generador de la sección «Guías» (contenido SEO) de transafronterave.com.

Uso:
  python3 scripts/guias.py                     # re-renderiza todas las guías de data/guias/*.json + índice + sitemap
  python3 scripts/guias.py nueva.json [...]    # agrega/actualiza esas specs (se copian a data/guias/<slug>.json),
                                               # las marca "published" en data/guias_temas.json y re-renderiza todo
  python3 scripts/guias.py --check             # solo valida las guías ya generadas (exit 1 si hay errores)
  python3 scripts/guias.py --next              # imprime (JSON) el siguiente tema pendiente del backlog

Spec de una guía (JSON):
{
  "slug": "como-comprar-en-colombia-y-recibir-en-venezuela",
  "title": "Título visible (H1)",
  "seo_title": "opcional, para <title>",
  "description": "meta description (~150-160 caracteres)",
  "date": "2026-10-21", "updated": "opcional",
  "tags": ["confianza", "envios"],
  "intro": ["párrafo", ...],
  "sections": [{"h2": "Subtítulo", "blocks": ["párrafo", {"ul": [...]}, {"ol": [...]}, {"h3": "..."}, {"tip": "..."}]}],
  "faq": [{"q": "...", "a": "..."}],
  "products": {"title": "...", "categories": ["Celulares"], "max_usd": 200, "min_usd": 0,
               "include": ["palabra"], "exclude": ["palabra"], "count": 8, "ids": ["pinned ids"],
               "allow_validacion": false, "sort": "top|precio_asc|precio_desc|descuento"},
  "wa_text": "opcional: mensaje prellenado de WhatsApp",
  "related": ["slug-1", "slug-2"]          # opcional; si falta se eligen por tags / más recientes
}
Formato en textos: **negrita**, [texto](url). Todo lo demás se escapa.
"""
import html, json, os, re, sys, unicodedata, urllib.parse
from datetime import date
from xml.sax.saxutils import escape as xesc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://transafronterave.com"
WA = "584120886940"
SPECS = os.path.join(ROOT, "data", "guias")
BACKLOG = os.path.join(ROOT, "data", "guias_temas.json")
OUT = os.path.join(ROOT, "guias")
MARGEN = 0.20  # igual que index.html (CFG.margen) y scripts/feed_meta.py
ENVIO = "Enviamos por MRW a toda Venezuela (costo aparte)"
VALIDACION = "Envío sujeto a validación, consúltanos por WhatsApp"
PAGOS = ["Zelle", "Binance USDT", "pago móvil", "efectivo USD", "Bancolombia", "Nequi"]

# ---- Validación: frases prohibidas (comparación sin acentos, en minúsculas, por palabra) ----
BANNED_PHRASES = ["envio incluido", "envio gratis", "envio gratuito", "mandamos", "[aliado]",
                  "[aliado]"]
# Cadenas comerciales colombianas que nunca deben aparecer (no implica que sean proveedores).
# Si existe scripts/data/fuentes_config.json (local, en .gitignore) también se agregan sus nombres.
BANNED_STORES = ["[tienda]"]
HEALTH_WARN = ["cura ", "curar", "previene", "prevenir enfermedades", "tratamiento de", "garantiza resultados",
               "elimina la", "100% efectivo", "milagro"]


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def store_names():
    names = set(BANNED_STORES)
    p = os.path.join(ROOT, "scripts", "data", "fuentes_config.json")
    if os.path.exists(p):
        try:
            for v in json.load(open(p, encoding="utf-8")).values():
                if isinstance(v, dict) and v.get("nombre"):
                    names.add(norm(v["nombre"]))
        except Exception:
            pass
    return sorted(names)


def banned_hits(text):
    t = " " + re.sub(r"\s+", " ", norm(text)) + " "
    hits = []
    for w in BANNED_PHRASES + store_names():
        if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", t):
            hits.append(w)
    return hits


# ---- Catálogo (mismos datos y fórmula que el sitio) ----
def load_catalog():
    d = json.load(open(os.path.join(ROOT, "data", "idx.json"), encoding="utf-8"))
    t = json.load(open(os.path.join(ROOT, "tasas.json"), encoding="utf-8"))
    rate = float(t.get("usdt_venta") or t.get("trm"))
    cats = [c[0] for c in d["cats"]]
    prods = []
    for pid, n, ci, cop, antes, f in d["p"]:
        prods.append({"id": pid, "n": n, "c": cats[ci], "cop": cop, "antes": antes, "top": bool(f & 1),
                      "validacion": bool(f & 2), "max6": bool(f & 4 or f & 8),
                      "usd": round(cop * (1 + MARGEN) / rate, 2), "img": "/img/p%s.jpg" % pid})
    return {"p": prods, "by": {p["id"]: p for p in prods}, "cats": cats, "rate": rate,
            "tasa_fecha": t.get("actualizado", ""), "actualizado": d.get("actualizado", "")}


def select_products(flt, cat):
    if not flt:
        return []
    by = cat["by"]
    out = [by[i] for i in flt.get("ids", []) if i in by]
    cats = {norm(c) for c in flt.get("categories", [])}
    inc = [norm(w) for w in flt.get("include", [])]
    exc = [norm(w) for w in flt.get("exclude", [])]
    mx, mn = flt.get("max_usd"), flt.get("min_usd", 0)
    stores = store_names()
    pool = []
    for p in cat["p"]:
        nn = norm(p["n"])
        if cats and norm(p["c"]) not in cats: continue
        if mx is not None and p["usd"] > mx: continue
        if p["usd"] < mn: continue
        if p["validacion"] and not flt.get("allow_validacion"): continue
        if inc and not any(w in nn for w in inc): continue
        if any(w in nn for w in exc): continue
        if any(re.search(r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9])", nn) for s in stores): continue
        if not os.path.exists(os.path.join(ROOT, p["img"].lstrip("/"))): continue
        if p in out: continue
        pool.append(p)
    srt = flt.get("sort", "top")
    disc = lambda p: (1 - p["cop"] / p["antes"]) if p["antes"] and p["antes"] > p["cop"] else 0
    if srt == "precio_asc": pool.sort(key=lambda p: (p["usd"], p["id"]))
    elif srt == "precio_desc": pool.sort(key=lambda p: (-p["usd"], p["id"]))
    elif srt == "descuento": pool.sort(key=lambda p: (-disc(p), p["id"]))
    else: pool.sort(key=lambda p: (not p["top"], -disc(p), p["id"]))
    # variedad: si hay varias categorías, intercalarlas
    if len(cats) > 1 and not flt.get("ids"):
        buckets = {}
        for p in pool: buckets.setdefault(p["c"], []).append(p)
        mixed, lists = [], list(buckets.values())
        while any(lists):
            for l in lists:
                if l: mixed.append(l.pop(0))
        pool = mixed
    seen = {norm(p["n"])[:40] for p in out}
    for p in pool:
        k = norm(p["n"])[:40]  # evita casi-duplicados (mismo modelo en varios colores)
        if k in seen: continue
        seen.add(k); out.append(p)
        if len(out) >= flt.get("count", 8): break
    return out[:flt.get("count", 8)]


# ---- Render ----
def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    def link(m):
        u = m.group(2)
        ext = u.startswith("http") and not u.startswith(SITE)
        return '<a href="%s"%s>%s</a>' % (html.escape(u), ' target="_blank" rel="noopener"' if ext else "", m.group(1))
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, s)


def plain(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r"\1", s)


def blocks_html(blocks):
    out = []
    for b in blocks:
        if isinstance(b, str): out.append("<p>%s</p>" % inline(b))
        elif "ul" in b: out.append("<ul>%s</ul>" % "".join("<li>%s</li>" % inline(x) for x in b["ul"]))
        elif "ol" in b: out.append("<ol>%s</ol>" % "".join("<li>%s</li>" % inline(x) for x in b["ol"]))
        elif "h3" in b: out.append("<h3>%s</h3>" % inline(b["h3"]))
        elif "tip" in b: out.append('<p class="tip">%s</p>' % inline(b["tip"]))
    return "\n".join(out)


def wa_link(text):
    return "https://wa.me/%s?text=%s" % (WA, urllib.parse.quote(text))


def fmt_date(d):
    m = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
    y, mo, da = map(int, d.split("-"))
    return "%d de %s de %d" % (da, m[mo - 1], y)


CSS = """:root{--y:#FFCC00;--b:#00247D;--r:#CF142B;--n:#0D214F;--g:#f2f3f7;--t:#1b2333;--m:#6b7280}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:var(--g);color:var(--t);-webkit-font-smoothing:antialiased;line-height:1.6}
a{color:var(--b)}.wrap{max-width:1100px;margin:0 auto;padding:0 16px}
.promo{background:var(--n);color:#fff;font-size:.8rem;text-align:center;padding:7px 10px}.promo b{color:var(--y)}
.hdr{position:sticky;top:0;z-index:40;background:#fff;box-shadow:0 2px 10px #0d214f14}
.hdr .flag{height:4px;background:linear-gradient(90deg,var(--y) 0 33.3%,var(--b) 33.3% 66.6%,var(--r) 66.6%)}
.hrow{display:flex;align-items:center;gap:18px;padding:12px 16px;max-width:1100px;margin:0 auto}
.logo{display:flex;align-items:center;gap:8px;text-decoration:none}.logo img{height:46px}
.logo span{font-weight:900;color:var(--n);font-size:1.05rem;line-height:1;letter-spacing:-.3px}.logo span i{display:block;font-style:normal;color:var(--r);font-size:.7rem;letter-spacing:2px}
.nav{margin-left:auto;display:flex;gap:6px;flex-wrap:wrap}.nav a{text-decoration:none;color:var(--n);font-weight:700;font-size:.9rem;padding:8px 12px;border-radius:10px}
.nav a:hover,.nav a.on{background:var(--g)}.nav a.w{background:#25D366;color:#fff}
.crumbs{font-size:.8rem;color:var(--m);margin:16px 0 0}.crumbs a{color:var(--m)}
.art{background:#fff;border-radius:18px;padding:28px 30px;margin:14px 0}
.art h1{color:var(--n);font-size:2rem;line-height:1.15;font-weight:900;margin-bottom:8px}
.meta{color:var(--m);font-size:.82rem;margin-bottom:18px}
.art h2{color:var(--n);font-size:1.35rem;margin:28px 0 10px;font-weight:800}.art h3{color:var(--n);font-size:1.08rem;margin:18px 0 6px}
.art p{margin:0 0 12px}.art ul,.art ol{margin:0 0 14px 22px}.art li{margin:5px 0}
.lead{font-size:1.08rem}.tip{background:#fff8d6;border:1px solid #ffe680;border-radius:12px;padding:12px 14px;font-size:.93rem}
.toc{background:var(--g);border-radius:14px;padding:14px 18px;margin:16px 0}.toc b{color:var(--n)}.toc ol{margin:6px 0 0 20px}
.toc a{text-decoration:none}
.cta{background:linear-gradient(115deg,var(--n),var(--b));color:#fff;border-radius:18px;padding:24px;margin:22px 0;text-align:center}
.cta h2{color:#fff!important;margin:0 0 6px!important}.cta p{opacity:.92;margin-bottom:14px}
.wa{display:inline-flex;align-items:center;gap:8px;background:#25D366;color:#fff;font-weight:800;padding:13px 26px;border-radius:30px;text-decoration:none}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:14px;margin:12px 0}
.card{background:#fff;border:1px solid #eceef3;border-radius:14px;overflow:hidden;display:flex;flex-direction:column;text-decoration:none;color:var(--t);transition:.2s}
.card:hover{box-shadow:0 8px 24px #0d214f1f;transform:translateY(-2px)}
.pimg{height:160px;display:flex;align-items:center;justify-content:center;background:#fff}.pimg img{width:100%;height:100%;object-fit:contain;padding:12px}
.pb{padding:10px 12px 14px;display:flex;flex-direction:column;flex:1}.pc{font-size:.68rem;font-weight:800;color:var(--m);text-transform:uppercase;letter-spacing:.6px}
.pn{font-size:.88rem;margin:4px 0 8px;line-height:1.3;min-height:2.6em;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.pp{font-size:1.25rem;color:var(--r);font-weight:900}.pp small{font-size:.7rem;color:var(--m);font-weight:700}
.note{font-size:.7rem;font-weight:700;color:#8a5a00;background:#fff4d6;padding:3px 7px;border-radius:6px;margin-top:6px;align-self:flex-start}
.ver{margin-top:auto;padding-top:8px;font-weight:800;color:var(--b);font-size:.85rem}
.disc{font-size:.78rem;color:var(--m)}
.faq details{border:1px solid #eceef3;border-radius:12px;padding:12px 16px;margin:8px 0;background:#fff}
.faq summary{font-weight:700;color:var(--n);cursor:pointer}.faq details p{margin:8px 0 0}
.rel{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px;margin-top:10px}
.gcard{display:block;background:#fff;border:1px solid #eceef3;border-radius:14px;padding:16px 18px;text-decoration:none;color:var(--t);transition:.2s}
.gcard:hover{box-shadow:0 8px 24px #0d214f1f;transform:translateY(-2px)}.gcard b{display:block;color:var(--n);font-size:1.02rem;line-height:1.3;margin-bottom:6px}
.gcard span{font-size:.86rem;color:var(--m)}.gcard small{display:block;margin-top:8px;color:var(--b);font-weight:700;font-size:.8rem}
footer{background:var(--n);color:#cfd6e6;margin-top:30px;font-size:.88rem}footer a{color:#fff}
.fin{display:flex;flex-wrap:wrap;gap:12px 28px;justify-content:space-between;padding:26px 16px}.fin ul{list-style:none}.fin li{margin:5px 0}
.fbot{border-top:1px solid #ffffff1f;padding:14px 16px;text-align:center;font-size:.78rem}
.fwa{position:fixed;right:18px;bottom:18px;width:56px;height:56px;border-radius:50%;background:#25D366;color:#fff;display:flex;align-items:center;justify-content:center;font-size:1.7rem;z-index:30;box-shadow:0 4px 14px #0004;text-decoration:none}
@media(max-width:720px){.hrow{flex-wrap:wrap;gap:8px}.logo img{height:38px}.nav{margin-left:0;width:100%}.nav a{padding:6px 9px;font-size:.84rem}
.art{padding:20px 16px;border-radius:14px}.art h1{font-size:1.55rem}.grid{grid-template-columns:repeat(2,1fr);gap:10px}.pimg{height:130px}}"""


def page(title, desc, canonical, body, jsonld, og_type="article", active="guias"):
    ld = "\n".join('<script type="application/ld+json">%s</script>' % json.dumps(j, ensure_ascii=False).replace("</", "<\\/")
                   for j in jsonld)
    e = lambda s: html.escape(s, quote=True)
    return f"""<!DOCTYPE html><html lang="es-VE"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="index,follow">
<meta property="og:type" content="{og_type}"><meta property="og:site_name" content="TRANSAFRONTERA VE">
<meta property="og:locale" content="es_VE"><meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE}/logo-tf.png"><meta property="og:image:width" content="1000"><meta property="og:image:height" content="1000">
<meta name="twitter:card" content="summary"><meta name="twitter:title" content="{e(title)}"><meta name="twitter:description" content="{e(desc)}"><meta name="twitter:image" content="{SITE}/logo-tf.png">
<link rel="icon" href="/logo-tf.png">
{ld}
<style>{CSS}</style></head><body>
<div class="promo">🚚 <b>{ENVIO}</b> · Compramos por ti en Colombia · Precios en USD</div>
<header class="hdr"><div class="flag"></div><div class="hrow">
<a class="logo" href="/"><img src="/logo-tf.png" alt="TRANSAFRONTERA VE"><span>TRANSAFRONTERA<i>VENEZUELA</i></span></a>
<nav class="nav"><a href="/">🛍️ Tienda</a><a href="/guias/"{' class="on"' if active == "guias" else ""}>📘 Guías</a><a href="/#cotiza">Cotiza</a><a class="w" href="{wa_link("Hola TRANSAFRONTERA VE, quiero hacer una consulta.")}" target="_blank" rel="noopener">💬 WhatsApp</a></nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap fin">
<div><b style="color:#fff">TRANSAFRONTERA VE</b><p>Compramos por ti en Colombia.<br>{ENVIO}.</p></div>
<ul><li><a href="/">Tienda</a></li><li><a href="/guias/">Guías de compra</a></li><li><a href="/#como">Cómo funciona</a></li><li><a href="/#cotiza">Cotiza un producto</a></li></ul>
<div><b style="color:#fff">Formas de pago</b><p>{", ".join(PAGOS)}.<br>Te pasamos los datos por WhatsApp.</p></div>
</div><div class="fbot">© {date.today().year} TRANSAFRONTERA VE · Precios en USD sujetos a la tasa del día</div></footer>
<a class="fwa" href="{wa_link("Hola TRANSAFRONTERA VE, vengo de las guías y quiero hacer una consulta.")}" target="_blank" rel="noopener" aria-label="WhatsApp">💬</a>
</body></html>
"""


def guide_url(slug):
    return "%s/guias/%s/" % (SITE, slug)


def pick_related(spec, specs):
    others = [s for s in specs if s["slug"] != spec["slug"]]
    by = {s["slug"]: s for s in others}
    rel = [by[x] for x in spec.get("related", []) if x in by]
    tags = set(spec.get("tags", []))
    rest = [s for s in others if s not in rel]
    rest.sort(key=lambda s: s.get("date", ""), reverse=True)          # más recientes primero...
    rest.sort(key=lambda s: -len(tags & set(s.get("tags", []))))      # ...pero priorizando tags en común (sort estable)
    return (rel + rest)[:3]


def product_card(p):
    note = ""
    if p["validacion"]: note = '<span class="note">%s</span>' % VALIDACION
    elif p["max6"]: note = '<span class="note">Máx. 6 unidades por pedido</span>'
    return ('<a class="card" href="/#p=%s"><div class="pimg"><img src="%s" alt="%s" loading="lazy" width="220" height="160"></div>'
            '<div class="pb"><span class="pc">%s</span><span class="pn">%s</span><span class="pp">$%.2f <small>USD</small></span>%s'
            '<span class="ver">Ver en la tienda ›</span></div></a>') % (
        p["id"], p["img"], html.escape(p["n"]), html.escape(p["c"]), html.escape(p["n"]), p["usd"], note)


def render_guide(spec, specs, cat):
    slug, url = spec["slug"], guide_url(spec["slug"])
    title = spec.get("seo_title") or "%s | TRANSAFRONTERA VE" % spec["title"]
    upd = spec.get("updated") or spec["date"]
    secs = spec.get("sections", [])
    ids = []
    for i, s in enumerate(secs):
        sid = s.get("id") or re.sub(r"[^a-z0-9]+", "-", norm(s["h2"])).strip("-")[:60]
        ids.append(sid)
    toc = "".join('<li><a href="#%s">%s</a></li>' % (ids[i], html.escape(plain(s["h2"]))) for i, s in enumerate(secs))
    if spec.get("faq"): toc += '<li><a href="#preguntas-frecuentes">Preguntas frecuentes</a></li>'
    body = ['<p class="crumbs"><a href="/">Inicio</a> › <a href="/guias/">Guías</a> › %s</p>' % html.escape(spec["title"]),
            '<article class="art"><h1>%s</h1>' % html.escape(spec["title"]),
            '<p class="meta">Publicado el %s%s · TRANSAFRONTERA VE</p>' % (
                fmt_date(spec["date"]), (" · Actualizado el %s" % fmt_date(upd)) if upd != spec["date"] else ""),
            "\n".join('<p class="lead">%s</p>' % inline(x) for x in spec.get("intro", []))]
    if len(secs) >= 3: body.append('<nav class="toc" aria-label="Contenido"><b>En esta guía</b><ol>%s</ol></nav>' % toc)
    prods = select_products(spec.get("products"), cat)
    grid_at = spec.get("products", {}).get("after_section", 0) if spec.get("products") else 0
    wa_text = spec.get("wa_text") or "Hola TRANSAFRONTERA VE, leí la guía «%s» y quiero hacer un pedido / cotización." % spec["title"]
    cta = ('<section class="cta"><h2>¿Te ayudamos con tu pedido?</h2><p>Escríbenos por WhatsApp y te cotizamos el producto y el envío por MRW a tu ciudad.</p>'
           '<a class="wa" href="%s" target="_blank" rel="noopener">💬 Escribir por WhatsApp</a></section>') % html.escape(wa_link(wa_text))
    grid = ""
    if prods:
        pt = spec["products"].get("title") or "Productos recomendados"
        grid = ('<h2 id="productos">%s</h2><div class="grid">%s</div><p class="disc">Precios del producto en USD calculados con la tasa del día '
                '(%s). Te confirmamos precio y disponibilidad por WhatsApp antes de pagar. %s.</p>') % (
            html.escape(pt), "".join(product_card(p) for p in prods), html.escape(cat["tasa_fecha"] or cat["actualizado"]), ENVIO)
    for i, s in enumerate(secs):
        body.append('<h2 id="%s">%s</h2>\n%s' % (ids[i], inline(s["h2"]), blocks_html(s.get("blocks", []))))
        if grid and i + 1 == grid_at: body.append(grid); grid = ""
        if i + 1 == spec.get("cta_after_section", -1): body.append(cta)
    if grid: body.append(grid)
    if spec.get("faq"):
        body.append('<h2 id="preguntas-frecuentes">Preguntas frecuentes</h2><div class="faq">%s</div>' % "".join(
            "<details><summary>%s</summary><p>%s</p></details>" % (html.escape(f["q"]), inline(f["a"])) for f in spec["faq"]))
    body.append(cta)
    rel = pick_related(spec, specs)
    body.append('<h2>Guías relacionadas</h2><div class="rel">%s</div>' % "".join(
        '<a class="gcard" href="/guias/%s/"><b>%s</b><span>%s</span><small>Leer guía ›</small></a>' % (
            r["slug"], html.escape(r["title"]), html.escape(r["description"])) for r in rel) if rel else
        '<h2>Más guías</h2><div class="rel"><a class="gcard" href="/guias/"><b>Todas las guías</b><span>Consejos prácticos para comprar en Colombia y recibir en Venezuela.</span><small>Ver guías ›</small></a>'
        '<a class="gcard" href="/"><b>Ver el catálogo</b><span>Miles de productos con precio en USD.</span><small>Ir a la tienda ›</small></a></div>')
    body.append("</article>")
    org = {"@type": "Organization", "name": "TRANSAFRONTERA VE", "url": SITE + "/",
           "logo": {"@type": "ImageObject", "url": SITE + "/logo-tf.png"}}
    ld = [{"@context": "https://schema.org", "@type": "Article", "headline": spec["title"], "description": spec["description"],
           "datePublished": spec["date"], "dateModified": upd, "inLanguage": "es-VE", "image": SITE + "/logo-tf.png",
           "mainEntityOfPage": {"@type": "WebPage", "@id": url}, "author": org, "publisher": org},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Inicio", "item": SITE + "/"},
              {"@type": "ListItem", "position": 2, "name": "Guías", "item": SITE + "/guias/"},
              {"@type": "ListItem", "position": 3, "name": spec["title"], "item": url}]}]
    if spec.get("faq"):
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": plain(f["a"])}} for f in spec["faq"]]})
    return page(title, spec["description"], url, "\n".join(body), ld), [p["id"] for p in prods]


def render_index(specs):
    url = SITE + "/guias/"
    cards = "".join('<a class="gcard" href="/guias/%s/"><b>%s</b><span>%s</span><small>%s · Leer guía ›</small></a>' % (
        s["slug"], html.escape(s["title"]), html.escape(s["description"]), fmt_date(s["date"])) for s in specs)
    body = ('<p class="crumbs"><a href="/">Inicio</a> › Guías</p><section class="art"><h1>Guías para comprar en Colombia desde Venezuela</h1>'
            '<p class="lead">Consejos prácticos para pedir productos de Colombia y recibirlos en Venezuela: cómo pagar, qué se puede enviar por MRW, '
            'y selecciones de productos por categoría con precio en USD.</p><div class="rel">%s</div></section>'
            '<section class="cta"><h2>¿Tienes una duda que no está aquí?</h2><p>Escríbenos y te respondemos por WhatsApp.</p>'
            '<a class="wa" href="%s" target="_blank" rel="noopener">💬 Escribir por WhatsApp</a></section>') % (
        cards or "<p>Pronto publicaremos nuestras primeras guías.</p>",
        html.escape(wa_link("Hola TRANSAFRONTERA VE, vengo de la sección de guías y tengo una pregunta.")))
    ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": "Guías TRANSAFRONTERA VE", "url": url, "inLanguage": "es-VE",
           "hasPart": [{"@type": "Article", "headline": s["title"], "url": guide_url(s["slug"]), "datePublished": s["date"]} for s in specs]}]
    return page("Guías: comprar en Colombia y recibir en Venezuela | TRANSAFRONTERA VE",
                "Guías prácticas para comprar productos de Colombia desde Venezuela: pagos, envíos por MRW (costo aparte) y selecciones de productos en USD.",
                url, body, ld, og_type="website")


def write_sitemap(specs):
    p = os.path.join(ROOT, "sitemap.xml")
    urls = {}
    if os.path.exists(p):  # conserva URLs existentes que no sean de guías
        for loc, lm in re.findall(r"<loc>([^<]+)</loc>(?:\s*<lastmod>([^<]+)</lastmod>)?", open(p, encoding="utf-8").read()):
            if "/guias/" not in loc: urls[loc] = lm
    urls.setdefault(SITE + "/", date.today().isoformat())
    newest = max([s.get("updated") or s["date"] for s in specs] or [date.today().isoformat()])
    urls[SITE + "/guias/"] = newest
    for s in specs: urls[guide_url(s["slug"])] = s.get("updated") or s["date"]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lm in urls.items():
        xml.append("  <url><loc>%s</loc>%s</url>" % (xesc(loc), "<lastmod>%s</lastmod>" % lm if lm else ""))
    xml.append("</urlset>")
    open(p, "w", encoding="utf-8").write("\n".join(xml) + "\n")
    r = os.path.join(ROOT, "robots.txt")
    txt = open(r, encoding="utf-8").read() if os.path.exists(r) else "User-agent: *\nAllow: /\n"
    if "sitemap:" not in txt.lower():
        txt = txt.rstrip("\n") + "\n\nSitemap: %s/sitemap.xml\n" % SITE
        open(r, "w", encoding="utf-8").write(txt)


def load_specs():
    specs = []
    for f in sorted(os.listdir(SPECS)) if os.path.isdir(SPECS) else []:
        if f.endswith(".json"):
            specs.append(json.load(open(os.path.join(SPECS, f), encoding="utf-8")))
    specs.sort(key=lambda s: (s.get("date", ""), s.get("slug")), reverse=True)  # más nuevas primero
    return specs


def validate(specs, cat, rendered_ids):
    errs, warns = [], []
    idx = os.path.join(OUT, "index.html")
    if not os.path.exists(idx): errs.append("falta guias/index.html")
    pages = [("guias/index.html", idx)] + [("guias/%s/index.html" % s["slug"], os.path.join(OUT, s["slug"], "index.html")) for s in specs]
    for name, path in pages:
        if not os.path.exists(path): errs.append("%s: no existe" % name); continue
        h = open(path, encoding="utf-8").read()
        text = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h, flags=re.S))
        text = html.unescape(text)
        for w in banned_hits(text + " " + " ".join(re.findall(r'content="([^"]*)"', h))):
            errs.append("%s: frase/tienda prohibida «%s»" % (name, w))
        for pid in re.findall(r'href="/#p=([0-9a-f]+)"', h):
            if pid not in cat["by"]: errs.append("%s: producto inexistente %s" % (name, pid))
            elif not os.path.exists(os.path.join(ROOT, "img", "p%s.jpg" % pid)): errs.append("%s: falta imagen de %s" % (name, pid))
        for slug in re.findall(r'href="/guias/([^"/]+)/"', h):
            if not os.path.exists(os.path.join(OUT, slug, "index.html")): errs.append("%s: enlace a guía inexistente %s" % (name, slug))
        if name != "guias/index.html":
            for tag in ("<title>", 'name="description"', 'rel="canonical"', 'property="og:title"', '"@type": "Article"', "<h1>", "<h2"):
                if tag not in h: errs.append("%s: falta %s" % (name, tag))
            if "costo aparte" not in h: errs.append("%s: falta «costo aparte»" % name)
            if "wa.me/%s" % WA not in h: errs.append("%s: falta CTA de WhatsApp" % name)
            words = len(text.split())
            if words < 500: warns.append("%s: solo %d palabras" % (name, words))
            nt = norm(text)
            for w in HEALTH_WARN:
                if w in nt: warns.append("%s: revisar posible afirmación de salud «%s»" % (name, w.strip()))
    return errs, warns


def mark_published(slugs):
    if not os.path.exists(BACKLOG) or not slugs: return
    b = json.load(open(BACKLOG, encoding="utf-8"))
    for t in b["temas"]:
        if t["slug"] in slugs and t.get("estado") != "published":
            t["estado"] = "published"; t["publicado"] = date.today().isoformat()
    json.dump(b, open(BACKLOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(BACKLOG, "a").write("\n")


def main(argv):
    cat = load_catalog()
    if "--next" in argv:
        b = json.load(open(BACKLOG, encoding="utf-8"))
        nxt = next((t for t in sorted(b["temas"], key=lambda t: t["orden"]) if t.get("estado") == "pending"), None)
        print(json.dumps(nxt, ensure_ascii=False, indent=1)); return 0
    if "--check" not in argv:
        os.makedirs(SPECS, exist_ok=True)
        new = []
        for f in [a for a in argv if not a.startswith("--")]:
            s = json.load(open(f, encoding="utf-8"))
            for k in ("slug", "title", "description", "sections"):
                if not s.get(k): raise SystemExit("spec %s: falta «%s»" % (f, k))
            if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", s["slug"]): raise SystemExit("slug inválido: " + s["slug"])
            s.setdefault("date", date.today().isoformat())
            dst = os.path.join(SPECS, s["slug"] + ".json")
            json.dump(s, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            new.append(s["slug"])
        specs = load_specs()
        rendered = {}
        for s in specs:
            h, ids = render_guide(s, specs, cat)
            os.makedirs(os.path.join(OUT, s["slug"]), exist_ok=True)
            open(os.path.join(OUT, s["slug"], "index.html"), "w", encoding="utf-8").write(h)
            rendered[s["slug"]] = ids
            print("guias/%s/ · %d productos" % (s["slug"], len(ids)))
        open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(render_index(specs))
        write_sitemap(specs)
        mark_published(new)
    specs = load_specs()
    errs, warns = validate(specs, cat, None)
    for w in warns: print("AVISO:", w)
    for e in errs: print("ERROR:", e)
    print("%d guías · %d errores · %d avisos" % (len(specs), len(errs), len(warns)))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
