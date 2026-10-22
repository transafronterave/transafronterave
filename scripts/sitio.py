#!/usr/bin/env python3
"""Pinta en index.html los textos editables desde el panel (/admin/):
  data/sitio/inicio.json -> barra de anuncio, slides del banner principal, banner con imagen, ofertas destacadas
  data/sitio/config.json -> WhatsApp y datos de contacto (también los usa scripts/guias.py)
Reemplaza solo lo que está entre marcadores <!--panel:X--> ... <!--/panel:X--> (y /*panel:datos*/ en el JS).
Si algún texto tiene frases prohibidas o nombres bloqueados, NO escribe nada y sale con código 1.
Uso: python3 scripts/sitio.py [--check]
"""
import html, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ajustes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
ESTILO = {"rojo": "s1", "azul": "s2", "amarillo": "s3"}
e = lambda s: html.escape(str(s or ""), quote=False)
a = lambda s: html.escape(str(s or ""), quote=True)
t = lambda v: re.sub(r"\s+", " ", str(v or "")).strip()


def cargar():
    cfg = json.load(open(os.path.join(ROOT, "data", "sitio", "config.json"), encoding="utf-8"))
    ini = json.load(open(os.path.join(ROOT, "data", "sitio", "inicio.json"), encoding="utf-8"))
    return cfg, ini


def url_ok(u):
    u = t(u)
    return u if re.match(r"^(https?://|/|#)", u) and not re.search(r"[\s\"'<>]", u) else ""


def bloques(cfg, ini):
    errs = []
    def chk(campo, v):
        for h in ajustes.prohibido(t(v)): errs.append("%s: texto no permitido «%s»" % (campo, h))
        return v
    wa = re.sub(r"\D", "", str(cfg.get("whatsapp") or ""))
    if not re.fullmatch(r"\d{10,15}", wa): errs.append("whatsapp: número inválido (usa formato internacional, ej. 584121234567)")
    b = {}
    # barra de anuncio (**negrita**)
    an = t(chk("anuncio", ini.get("anuncio")))
    b["anuncio"] = ('<div class="promo">%s</div>' % re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", e(an))) if ini.get("anuncio_activo") and an else ""
    # slides
    sl = []
    for i, s in enumerate(ini.get("slides") or []):
        for k in ("etiqueta", "titulo", "subtitulo", "boton_texto", "emojis"): chk("slide %d %s" % (i + 1, k), s.get(k))
        cls = ESTILO.get(s.get("estilo"), "s1") + (" on" if not sl else "")
        tx = ""
        if t(s.get("etiqueta")): tx += "<small>%s</small>" % e(t(s["etiqueta"]))
        tx += "<h2>%s</h2>" % e(t(s.get("titulo")))
        if t(s.get("subtitulo")): tx += "<p>%s</p>" % e(t(s["subtitulo"]))
        bt = t(s.get("boton_texto"))
        if bt and url_ok(s.get("boton_enlace")): tx += '<a class="cta" href="%s">%s</a>' % (a(url_ok(s["boton_enlace"])), e(bt))
        elif bt: tx += '<button class="cta" data-c="%s">%s</button>' % (a(t(s.get("boton_categoria"))), e(bt))
        img = t(s.get("imagen"))
        art = '<img src="%s" alt="">' % a(img) if img else e(t(s.get("emojis")))
        sl.append('<div class="slide %s"><div class="tx">%s</div><div class="art">%s</div></div>' % (cls, tx, art))
    if not sl: errs.append("slides: debe haber al menos un slide")
    b["slides"] = "\n" + "\n".join(sl) + "\n"
    # banner con imagen
    bn = ini.get("banner") or {}
    if bn.get("activo") and t(bn.get("imagen")):
        chk("banner texto", bn.get("texto_alt"))
        im = '<img src="%s" alt="%s" loading="lazy">' % (a(t(bn["imagen"])), a(t(bn.get("texto_alt"))))
        lk = url_ok(bn.get("enlace"))
        b["banner"] = '<div class="bnr">%s</div>' % ('<a href="%s">%s</a>' % (a(lk), im) if lk else im)
    else:
        b["banner"] = ""
    # contacto (pie de página)
    c = ['<p style="margin-top:14px">📍 %s</p>' % e(t(chk("ubicacion", cfg.get("ubicacion"))))] if t(cfg.get("ubicacion")) else []
    extra = []
    if t(cfg.get("correo")): extra.append('✉️ <a href="mailto:%s">%s</a>' % (a(t(cfg["correo"])), e(t(cfg["correo"]))))
    for k, ic, base in (("instagram", "📸 Instagram", "https://instagram.com/"), ("facebook", "👍 Facebook", "https://facebook.com/"), ("tiktok", "🎵 TikTok", "https://tiktok.com/@")):
        v = t(cfg.get(k)).lstrip("@")
        if v: extra.append('<a href="%s" target="_blank" rel="noopener">%s</a>' % (a(v if v.startswith("http") else base + v), ic))
    if t(cfg.get("horario")): extra.append("🕒 %s" % e(t(chk("horario", cfg["horario"]))))
    if extra: c.append('<p style="margin-top:8px">%s</p>' % "<br>".join(extra))
    b["contacto"] = "".join(c)
    # datos para el JS
    ids = [t(x) for x in (ini.get("ofertas_destacadas") or []) if t(x)]
    datos = {"whatsapp": wa, "ayuda": t(chk("mensaje_ayuda", cfg.get("mensaje_ayuda"))) or "Hola TRANSAFRONTERA VE, necesito ayuda con una compra",
             "ofertas": ids, "completar": ini.get("completar_ofertas") is not False}
    b["datos"] = "const PANEL=%s;" % json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    return b, errs


def pintar(h, b):
    for k, v in b.items():
        if k == "datos":
            h, n = re.subn(r"/\*panel:datos\*/.*?/\*/panel:datos\*/", lambda m: "/*panel:datos*/%s/*/panel:datos*/" % v, h, flags=re.S)
        else:
            h, n = re.subn(r"<!--panel:%s-->.*?<!--/panel:%s-->" % (k, k), lambda m: "<!--panel:%s-->%s<!--/panel:%s-->" % (k, v, k), h, flags=re.S)
        if n != 1: raise SystemExit("index.html: falta el marcador panel:%s" % k)
    return h


def main(argv):
    cfg, ini = cargar()
    b, errs = bloques(cfg, ini)
    for x in errs: print("ERROR:", x)
    if errs: return 1
    h0 = open(INDEX, encoding="utf-8").read(); h = pintar(h0, b)
    if "--check" in argv: print("sitio: OK (sin cambios)" if h == h0 else "sitio: OK (index.html cambiaría)"); return 0
    if h != h0: open(INDEX, "w", encoding="utf-8").write(h)
    print("index.html:", "actualizado" if h != h0 else "sin cambios")
    return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
