#!/usr/bin/env python3
"""Publica los cambios hechos en el panel (/admin/). Lo corre .github/workflows/panel.yml al guardar en el panel.
1) data/idx.json + data/c/*.json con los ajustes de productos (scripts/ajustes.py, sin descargar nada)
2) index.html con textos/banners/contacto (scripts/sitio.py)
3) catalogo_meta.csv (scripts/feed_meta.py)
4) completa el campo «ref» (nombre del producto) en data/ajustes_productos.json para verlo en la lista del panel
Sale con código 1 si hubo errores (lo válido se publica igual; lo inválido se ignora y se lista aquí)."""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ajustes, sitio

ROOT = ajustes.ROOT


def refs():
    try: aj = json.load(open(ajustes.F_AJ, encoding="utf-8"))
    except Exception: return
    if not isinstance(aj, list) or not aj: return
    by = {o["id"]: o for o in json.load(open(ajustes.F_LISTA, encoding="utf-8"))}
    ch = False
    for a in aj:
        if not isinstance(a, dict): continue
        o = by.get(str(a.get("id") or "").strip())
        r = "%s (%s)" % (o["n"], o["c"]) if o else "⚠️ producto no encontrado"
        if a.get("ref") != r: a["ref"] = r; ch = True
    if ch:
        with open(ajustes.F_AJ, "w", encoding="utf-8") as f:
            json.dump(aj, f, ensure_ascii=False, indent=2); f.write("\n")


def main():
    d = json.load(open(os.path.join(ROOT, "productos.json"), encoding="utf-8"))
    pub = ajustes.escribir(d["productos"], d.get("actualizado"))
    print("catálogo publicado: %d productos" % len(pub))
    refs()
    rc = sitio.main([])
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "feed_meta.py")]); rc |= r.returncode
    for e in ajustes.ERRORES: print("ERROR:", e)
    return 1 if (rc or ajustes.ERRORES) else 0


if __name__ == "__main__": sys.exit(main())
