#!/usr/bin/env python3
"""Genera catalogo_meta.csv (feed de catálogo Meta Commerce) desde productos.json y tasas.json."""
import csv, json, os, hashlib, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://transafronterave.com/"
BRAND = "TRANSAFRONTERA VE"
MSG = "Compramos en Colombia y enviamos por MRW a toda Venezuela. Pedidos por WhatsApp."
d = json.load(open(os.path.join(ROOT, "productos.json"), encoding="utf-8"))
prods = d.get("productos", d) if isinstance(d, dict) else d
rate = float(json.load(open(os.path.join(ROOT, "tasas.json")))["usdt_venta"])
usd = lambda cop: round(cop * 1.20 / rate, 2)
cols = ["id","title","description","availability","condition","price","sale_price","link","image_link","brand","product_type"]
rows, seen = [], set()
for p in prods:
    name = (p.get("n") or p.get("name") or "").strip()
    cop = p.get("cop")
    if not name or not cop or not p.get("img"):
        continue
    pid = str(p.get("id") or hashlib.md5(name.encode()).hexdigest()[:10])
    if pid in seen: continue
    seen.add(pid)
    cat = p.get("c") or p.get("category") or ""
    cur, antes = usd(cop), p.get("antes")
    reg = usd(antes) if antes and antes > cop else None
    link = SITE + ("#p=" + urllib.parse.quote(pid) if p.get("id") else "?q=" + urllib.parse.quote(name))
    rows.append({"id": pid, "title": name[:150], "description": f"{name}. {MSG}",
        "availability": "in stock", "condition": "new",
        "price": f"{(reg if reg and reg > cur else cur):.2f} USD",
        "sale_price": f"{cur:.2f} USD" if reg and reg > cur else "",
        "link": link, "image_link": urllib.parse.urljoin(SITE, p["img"]),
        "brand": BRAND, "product_type": cat})
with open(os.path.join(ROOT, "catalogo_meta.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
print(f"catalogo_meta.csv: {len(rows)} filas (tasa {rate})")
