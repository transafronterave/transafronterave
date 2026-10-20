#!/usr/bin/env python3
"""Genera catalogo_meta.csv (feed de catálogo Meta Commerce / WhatsApp) desde productos.json y tasas.json.
Una colección por categoría: product_type y custom_label_0 = categoría del sitio; custom_label_1 = 'oferta' si hay precio anterior."""
import csv, json, os, re, hashlib, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://transafronterave.com/"
BRAND = "TRANSAFRONTERA VE"
MSG = "Compramos en Colombia y enviamos por MRW a toda Venezuela (costo aparte). Pedidos por WhatsApp."
d = json.load(open(os.path.join(ROOT, "productos.json"), encoding="utf-8"))
prods = d.get("productos", d) if isinstance(d, dict) else d
rate = float(json.load(open(os.path.join(ROOT, "tasas.json")))["usdt_venta"])
usd = lambda cop: round(cop * 1.20 / rate, 2)
cols = ["id", "title", "description", "availability", "condition", "price", "sale_price", "link", "image_link", "brand",
        "product_type", "custom_label_0", "custom_label_1"]
rows, seen = [], set()
for p in prods:
    name = re.sub(r"\s+", " ", (p.get("n") or p.get("name") or "")).strip()
    cop = p.get("cop")
    if not name or not cop or not p.get("img"): continue
    pid = str(p.get("id") or hashlib.md5(name.encode()).hexdigest()[:10])
    if pid in seen: continue
    seen.add(pid)
    cat = p.get("c") or p.get("category") or ""
    cur, antes = usd(cop), p.get("antes")
    reg = usd(antes) if antes and antes > cop else None
    oferta = bool(reg and reg > cur)
    extra = (" Envío sujeto a validación, consúltanos por WhatsApp." if p.get("envio") == "consultar" else "") + \
            (" Máximo 6 unidades por pedido." if p.get("max_qty") else "")
    rows.append({"id": pid, "title": name[:150], "description": f"{name}. {MSG}{extra}"[:9999],
        "availability": "in stock", "condition": "refurbished" if re.search(r"reacondicionad", name, re.I) else "new",
        "price": f"{(reg if oferta else cur):.2f} USD",
        "sale_price": f"{cur:.2f} USD" if oferta else "",
        "link": SITE + "#p=" + urllib.parse.quote(pid), "image_link": urllib.parse.urljoin(SITE, p["img"]),
        "brand": BRAND, "product_type": cat, "custom_label_0": cat, "custom_label_1": "oferta" if antes else ""})
with open(os.path.join(ROOT, "catalogo_meta.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
print(f"catalogo_meta.csv: {len(rows)} filas (tasa {rate})")
