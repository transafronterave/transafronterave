#!/usr/bin/env python3
"""Reglas de envío aplicadas a todo el catálogo publicado.
- BLOQUEO: no se publican (no se pueden enviar).
- ENVIO_STRICT: se publican con envio="consultar" (Envío sujeto a validación). Con ENVIO_STRICT_EXCLUIR=1 se excluyen.
- CONSULTAR: siempre envio="consultar".
- LIMITE: max_qty=6 por referencia/pedido.
Uso independiente: python3 scripts/envio.py  (reaplica las reglas sobre productos.json)
"""
import re, os, json, unicodedata

def nrm(t): return "".join(ch for ch in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(ch) != "Mn")

ENVIO_STRICT_EXCLUIR = os.environ.get("ENVIO_STRICT_EXCLUIR", "0") == "1"  # un solo interruptor

# Patrones sobre el nombre normalizado (minúsculas, sin tildes).
MRW_BLOCK = {
 "armas blancas": r"\bmachetes?\b|\bnavajas?\b(?! de afeitar)|cuchill[oa]s? (tactic|de caza|de supervivencia|militar|plegable|de combate|mariposa)|^(cuchillas?|bisturi)\b(?!.*(afeitar|rasur|depil|licuadora|procesador|picahielo|batidora|extractor))|\bpu[nñ]al\b|\bdaga\b",
 "gases comprimidos": r"\bbombonas?\b|\b(tanque|cilindro|bala) de (oxigeno|nitrogeno|gas)\b|oxigeno medicinal|\bnitrogeno\b|cilindros? (de )?(gas|co2|oxigeno|helio|propano|sellado)|tanque de helio|gas propano|gas butano|cartuchos? de gas",
 "erotico": r"erotic|pornogr|sex ?shop|juguetes? (sexual|para adultos)|vibrador|consolador|\bdildo",
 "militar": r"(?<!verde )(?<!estilo )(?<!tipo )(?<!look )\bmilitar(es)?\b(?! (verde|green))|chaleco (tactico|antibalas)|\bantibalas\b",
 "medicina refrigerada/institucional/control": r"insulina|vacunas?\b|refrigerad|cadena de frio|uso (institucional|hospitalario)|control especial|medicamento controlado",
 "ampollas": r"\bampollas?\b(?!.*(capilar|cabello|pelo|facial|keratina|hidrat|reparad|tratamiento|serum|rostro|piel|bioplasti|nutri))|\bampolletas?\b",
 "velas/glicerina": r"\bvelas?\b|\bvelon(es)?\b|glicerina",
 "bicarbonato": r"bicarbonato",
 "cloro en pastillas": r"(pastillas?|tabletas?) de cloro|cloro (en pastillas|granulado|para piscina)",
 "enlatados": r"\ben lata\b|enlatad|\blatas? de (atun|sardina|maiz|frijol|arveja|salchicha|durazno|leche)|^(atun|sardinas?)\b",
 "perecederos": r"^(huevos?|carne|pollo|pescado|queso|yogur|leche|frutas?|verduras?|pan)\b(?! (de|para) (juguete|silicona|plastico))",
 "licor/tabaco": r"\b(licor|whisky|vodka|tequila|aguardiente|cerveza|ginebra|brandy|cigarr\w*|habanos?)\b|^(vino|ron|champana|tabaco)\b|de tabaco\b",
 "vapers": r"\bvape(r|rs)?\b|vapeador|pod desechable|cigarrillo electronico",
 "semillas": r"\bsemillas?\b(?!.*(aceite|serum|crema|exfolia|shampoo|jabon|uva))",
 "venenos/insecticidas": r"veneno|insecticida|raticida|plaguicida|pesticida|herbicida|fungicida|matamaleza|cucarachicida|mata ?(cucarachas|ratas|hormigas|moscas|zancudos)|\braid\b|baygon",
 "cenizas": r"^cenizas?\b|urna (para|de) cenizas",
 "pinturas": r"^(pinturas?|vinilos?|esmaltes?|anticorrosivo|laca|barniz|imprimante|thinner)\b(?!.*(u[nñ]as|nail|tempera|acuarela|dactilar|ni[nñ]os|facial|corporal|faber|pelikan|kit|set|oleo|x \d+|\d+ colores|tela|artistic|acrilica \d+ ?ml))|pintura (en aerosol|aerosol|de pared|para pared|anticorrosiva|para (madera|metal|piso|techo|exterior|interior))|(spray|aerosol) de pintura|\bgal(on|ones)\b.*\bpintura|pintura.*\bgal(on|ones)\b|\bkoraza\b|viniltex|pintuco",
 "oro/piedras preciosas": r"\boro (solido|macizo|puro|de \d\d|\d\dk)|\b(10|14|18|24) ?k(ilates)? (de )?oro|oro (10|14|18|24) ?k|piedras? preciosas?|\blingotes?\b|diamantes? (natural|real)|esmeraldas? (natural|colombiana)",
 "cannabis/coca": r"\bcbd\b|cannab|marihuana|hoja de coca|\bhemp\b|canamo",
 "plantas naturales": r"plantas? (natural|viva)|suculentas? natural|bonsai natural|matera con planta",
 "metales en bruto": r"^(laminas?|barras?|varillas?|alambres?|platinas?|lingotes?|perfil|tubos?)\b.*\b(aluminio|bronce|cobre)\b|\b(alambre|hilo|cable|lamina) de cobre\b(?!.*(usb|hdmi|parlante|audio))|chatarra",
 "documentos": r"^documentos?\b",
}
# Lista pendiente de decisión (por ahora: publicar con envio=consultar).
ENVIO_STRICT = {
 "vidrio/ceramica/yeso": r"\bvidrio\b|cristaleria|\bcristal\b|ceramic|porcelana|\byeso\b",
 "aerosoles": r"aerosol|\bspray\b",
 "acetonas": r"aceton|quitaesmalte|removedor de esmalte",
 "perfumes": r"perfume|colonia|\bsplash\b|body mist|eau de (parfum|toilette|cologne)|fragancia|\bparfum\b",
 "esencias": r"esencias?\b",
 "liquidos": r"\bliquid|\d+(?:[.,]\d+)?\s*(ml|cc|l|lt|lts|litros?|oz)\b",
 "bicicletas": r"bicicleta",
}
CONSULTAR = {"cuchillos de cocina": r"cuchill[oa]s?\b"}
LIMITE = {
 "medicamentos": r"",  # por categoría (ver limite())
 "esmaltes de unas": r"esmalte|\bnail (polish|lacquer)|\bgel (para )?u[nñ]as",
 "replicas": r"\breplicas?\b|\b(aaa|1\.1)\b",
}
CAT_MED = {"Vitaminas y venta libre"}
_c = lambda d: {k: re.compile(v) for k, v in d.items() if v}
RB, RS, RC, RL = _c(MRW_BLOCK), _c(ENVIO_STRICT), _c(CONSULTAR), _c(LIMITE)

def _hit(rx, n):
    for k, r in rx.items():
        if r.search(n): return k
    return None

def bloqueado(n, c=""):
    """Devuelve el grupo que impide el envío, o None."""
    t = nrm(n)
    g = _hit(RB, t)
    if g: return g
    if ENVIO_STRICT_EXCLUIR: return _hit(RS, t)
    return None

def marcar(o):
    """Añade envio/max_qty/nota al producto publicado (dict con n, c). Devuelve los grupos aplicados."""
    t = nrm(o["n"]); g = {}
    for k in ("envio", "max_qty", "nota"): o.pop(k, None)
    s = _hit(RS, t) or _hit(RC, t)
    if s: o["envio"] = "consultar"; g["consultar"] = s
    lim = "medicamentos" if o.get("c") in CAT_MED else (_hit(RL, t) if o.get("c") in ("Maquillaje", "Belleza", "Cuidado personal") or RL["replicas"].search(t) else None)
    if lim == "esmaltes de unas" and not re.search(r"esmalte|nail|u[nñ]as", t): lim = None
    if lim:
        o["max_qty"] = 6; g["limite"] = lim
        if lim != "replicas": o["nota"] = "Máx. 6 unidades por pedido"
    return g

def aplicar(pub):
    """Filtra y marca la lista publicada. Devuelve (lista, resumen)."""
    from collections import Counter
    out, res = [], {"excluidos": Counter(), "consultar": Counter(), "limite_6": Counter()}
    for o in pub:
        b = bloqueado(o["n"], o.get("c", ""))
        if b: res["excluidos"][b] += 1; continue
        g = marcar(o)
        if "consultar" in g: res["consultar"][g["consultar"]] += 1
        if "limite" in g: res["limite_6"][g["limite"]] += 1
        out.append(o)
    return out, res

if __name__ == "__main__":
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fp = os.path.join(ROOT, "productos.json"); d = json.load(open(fp, encoding="utf-8"))
    d["productos"], res = aplicar(d["productos"])
    json.dump(d, open(fp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(json.dumps({k: dict(v) for k, v in res.items()}, ensure_ascii=False, indent=1))
