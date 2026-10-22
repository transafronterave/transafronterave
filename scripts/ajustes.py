#!/usr/bin/env python3
"""Capa de ajustes del panel (/admin/) sobre el catálogo generado.

El catálogo base (productos.json) lo genera scripts/catalogo.py y NO se toca aquí. Este módulo aplica, al publicar:
  - data/ajustes_productos.json  (lista): por id de producto -> oculto, precio_usd (+ precio_antes_usd), destacado,
    oferta, titulo, descripcion, imagen.
  - data/productos_manuales.json (lista): productos agregados a mano (precio en USD).
y escribe los archivos públicos que lee el sitio: data/idx.json y data/c/<categoría>.json, más la lista liviana
data/panel/catalogo.json (id, nombre, categoría) que usa el buscador de productos del panel.

Con los dos archivos vacíos ([]) la salida es idéntica a la de antes del panel.
Precio: el sitio sigue usando usd = cop*1.20/usdt_venta; precio_usd solo reemplaza ese valor cuando está puesto.
Uso: python3 scripts/ajustes.py   (regenera idx/c/panel desde productos.json; no descarga nada)
"""
import json, os, re, sys, unicodedata, hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envio  # mismas reglas de envío del catálogo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F_AJ = os.path.join(ROOT, "data", "ajustes_productos.json")
F_MAN = os.path.join(ROOT, "data", "productos_manuales.json")
F_LISTA = os.path.join(ROOT, "data", "panel", "catalogo.json")
MARGEN = 0.20
ERRORES = []  # problemas encontrados (scripts/panel.py los muestra y falla el workflow)


def _load(fp, default):
    try:
        d = json.load(open(fp, encoding="utf-8"))
        return d if isinstance(d, type(default)) else default
    except FileNotFoundError:
        return default
    except Exception as e:
        ERRORES.append("%s: JSON inválido (%s)" % (os.path.relpath(fp, ROOT), e)); return default


def _num(v):
    try:
        v = float(v)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def _txt(v): return re.sub(r"\s+", " ", str(v or "")).strip()


def rate():
    t = json.load(open(os.path.join(ROOT, "tasas.json"), encoding="utf-8"))
    return float(t.get("usdt_venta") or t.get("trm"))


def prohibido(texto, donde="texto"):
    """Frases prohibidas y nombres bloqueados (hashes de scripts/guias_bloqueo.json). Lista vacía = OK."""
    if not texto: return []
    import guias
    hits = guias.banned_hits(texto, donde)
    if donde == "producto": hits += [h for h in guias.blocked_names(texto, "texto") if h not in hits]
    return hits


def slug(t):
    t = "".join(ch for ch in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def id_manual(m):
    c = slug(m.get("codigo") or "")
    return "m-" + (c or slug(m.get("nombre") or "")[:40] or hashlib.sha1(json.dumps(m, sort_keys=True).encode()).hexdigest()[:8])


def _panel_campos(o, a, ref):
    """Aplica precio/destacado/oferta/descripcion/imagen de un ajuste o producto manual a o (in situ)."""
    u = _num(a.get("precio_usd"))
    if u:
        o["u"] = round(u, 2)
        au = _num(a.get("precio_antes_usd"))
        o["au"] = round(au, 2) if au and au > u else 0
    d = _txt(a.get("descripcion"))
    if d:
        h = prohibido(d)
        if h: ERRORES.append("%s: descripción con texto no permitido %s (se ignora)" % (ref, h))
        else: o["d"] = d[:400]
    img = _txt(a.get("imagen"))
    if img:
        if os.path.exists(os.path.join(ROOT, img.lstrip("/"))): o["img"] = img
        else: ERRORES.append("%s: la imagen %s no existe (se ignora)" % (ref, img))
    if a.get("destacado"): o["dest"] = 1
    if a.get("oferta"): o["of"] = 1


def aplicar(pub, tasa=None):
    """Devuelve una lista NUEVA con los ajustes aplicados (los dicts de pub no se modifican)."""
    aj = {}
    for a in _load(F_AJ, []):
        if isinstance(a, dict) and _txt(a.get("id")): aj[_txt(a["id"])] = a  # el último gana
    man = [m for m in _load(F_MAN, []) if isinstance(m, dict)]
    if not aj and not man: return list(pub)
    ids = {o["id"] for o in pub}
    for i in aj:
        if i not in ids: ERRORES.append("ajuste %s: el producto ya no está en el catálogo (se ignora)" % i)
    out = []
    for o in pub:
        a = aj.get(o["id"])
        if not a: out.append(o); continue
        if a.get("oculto"): continue
        o = dict(o); ref = "ajuste %s" % o["id"]
        t = _txt(a.get("titulo"))
        if t:
            h = prohibido(t, "producto"); b = envio.bloqueado(t, o.get("c", ""))
            if h or b: ERRORES.append("%s: título no permitido %s (se deja el original)" % (ref, h or b))
            else:
                o["n"] = t[:200]; envio.marcar(o)
        _panel_campos(o, a, ref)
        out.append(o)
    tasa = tasa or rate(); vistos = set(ids)
    for m in man:
        if m.get("activo") is False: continue
        n, c, u = _txt(m.get("nombre")), _txt(m.get("categoria")), _num(m.get("precio_usd"))
        pid = id_manual(m); ref = "producto manual «%s»" % (n or pid)
        if not (n and c and u): ERRORES.append("%s: falta nombre, categoría o precio (no se publica)" % ref); continue
        if pid in vistos: ERRORES.append("%s: código repetido %s (no se publica)" % (ref, pid)); continue
        h = prohibido(n, "producto"); b = envio.bloqueado(n, c)
        if h or b: ERRORES.append("%s: nombre no permitido %s (no se publica)" % (ref, h or b)); continue
        vistos.add(pid)
        o = {"id": pid, "n": n[:200], "c": c, "cop": int(round(u * tasa / (1 + MARGEN))), "kg": round(_num(m.get("peso_kg")) or 1, 2),
             "e": "📦", "img": ""}
        envio.marcar(o)
        _panel_campos(o, m, ref)
        o["manual"] = 1
        out.append(o)
    return out


def escribir(pub, hoy):
    """Escribe data/idx.json, data/c/*.json (con ajustes) y data/panel/catalogo.json (lista base para el panel)."""
    base_cats = list(dict.fromkeys(o["c"] for o in pub))
    os.makedirs(os.path.dirname(F_LISTA), exist_ok=True)
    with open(F_LISTA, "w", encoding="utf-8") as f:
        json.dump([{"id": o["id"], "n": o["n"], "c": o["c"]} for o in pub], f, ensure_ascii=False, separators=(",", ":"))
    pub = aplicar(pub)
    cats = [c for c in base_cats if any(o["c"] == c for o in pub)] + list(dict.fromkeys(o["c"] for o in pub if o["c"] not in base_cats))
    ci = {c: i for i, c in enumerate(cats)}
    import catalogo_slug as cs
    os.makedirs(os.path.join(ROOT, "data", "c"), exist_ok=True)
    rows = []
    for o in pub:
        fl = (1 if o.get("top") else 0) | (2 if o.get("envio") == "consultar" else 0) | (4 if o.get("max_qty") else 0) | (8 if o.get("nota") else 0) \
             | (16 if o.get("of") else 0) | (32 if o.get("dest") else 0)
        r = [o["id"], o["n"], ci[o["c"]], o["cop"], o.get("antes") or 0, fl]
        x = {k: o[k] for k in ("u", "au", "d") if k in o}
        if o.get("manual") or o.get("img") != "img/p%s.jpg" % o["id"]: x["img"] = o.get("img") or ""
        if x: r.append(x)
        rows.append(r)
    with open(os.path.join(ROOT, "data", "idx.json"), "w", encoding="utf-8") as f:
        json.dump({"actualizado": hoy, "cats": [[c, cs.slug(c)] for c in cats], "p": rows}, f, ensure_ascii=False, separators=(",", ":"))
    keep = set()
    for c in cats:
        fn = cs.slug(c) + ".json"; keep.add(fn)
        with open(os.path.join(ROOT, "data", "c", fn), "w", encoding="utf-8") as f:
            json.dump({"c": c, "productos": [o for o in pub if o["c"] == c]}, f, ensure_ascii=False, separators=(",", ":"))
    for x in os.listdir(os.path.join(ROOT, "data", "c")):
        if x.endswith(".json") and x not in keep: os.remove(os.path.join(ROOT, "data", "c", x))
    return pub


def main():
    d = json.load(open(os.path.join(ROOT, "productos.json"), encoding="utf-8"))
    pub = escribir(d["productos"], d.get("actualizado"))
    print("data/idx.json: %d productos publicados (%d en el catálogo base)" % (len(pub), len(d["productos"])))
    for e in ERRORES: print("AVISO:", e)


if __name__ == "__main__": main()
