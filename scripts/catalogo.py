#!/usr/bin/env python3
"""Regenera productos.json + img/ a partir de datos públicos de tiendas colombianas.
Uso: python3 scripts/catalogo.py [--no-img] [--solo T1,T2 [--cats A,B]] [--budget MIN]
Los datos internos (tienda/URL de origen) se guardan en scripts/data/ (no publicado, .gitignore).
"""
import json, re, os, sys, time, math, hashlib, io, urllib.parse, argparse, html
import requests
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envio  # reglas de envío (bloqueo / consultar / máx. 6 unidades)

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
def _q(kg, emo, *qs): return [(q, kg, emo) for q in qs]
Q = {
 "Tecnología": [("audifonos bluetooth",.25,"🎧"),("parlante bluetooth",.6,"🔊"),("mouse inalambrico",.2,"🖱️"),("teclado",.6,"⌨️"),("smartwatch",.2,"⌚"),("cargador",.2,"🔌"),("memoria usb",.05,"💾"),("power bank",.35,"🔋"),("cable usb",.1,"🔌")]
   + _q(.25,"🎧","audifonos","audifonos inalambricos","diadema") + _q(.6,"🔊","parlante") + _q(.2,"🖱️","mouse")
   + _q(.2,"⌚","reloj inteligente") + _q(.05,"💾","memoria micro sd","disco duro","disco solido") + _q(.1,"🔌","cable hdmi","adaptador")
   + _q(.1,"📱","forro","funda","protector de pantalla","vidrio templado","soporte celular","cargador inalambrico")
   + _q(.5,"📷","camara de seguridad","camara web","camara") + _q(.5,"📡","router","microfono","aro de luz","tripode"),
 "Celulares": [(q,.4,"📱") for q in ("celular samsung","samsung galaxy","xiaomi","redmi","poco","motorola","iphone","honor","oppo","realme","tecno","infinix","zte","celular")],
 "Tablets": [(q,.7,"📲") for q in ("tablet samsung","tablet lenovo","ipad","tablet xiaomi","tablet")],
 "Computadores": _q(2.5,"💻","portatil","computador portatil","computador","macbook","portatil gamer") + _q(5,"🖥️","monitor","computador de escritorio","all in one") + _q(6,"🖨️","impresora","multifuncional"),
 "TV y video": _q(12,"📺","televisor","tv","smart tv") + _q(3,"📽️","proyector","barra de sonido","teatro en casa","tv box","soporte tv"),
 "Videojuegos": _q(3,"🎮","consola","playstation","nintendo","xbox","videojuego","control inalambrico"),
 "Grandes electrodomésticos": _q(70,"🧊","nevera","nevecon","congelador","lavadora","secadora","lavadora secadora","lavavajillas") + _q(30,"🔥","estufa","horno","microondas","campana extractora","calentador","aire acondicionado","enfriador"),
 "Hogar": [("organizador",.6,"🏠"),("linterna",.3,"🔦"),("termo",.5,"🥤"),("sarten",1.2,"🍳"),("juego de cubiertos",.8,"🍴"),("toalla",.6,"🛁"),("lampara led",.5,"💡")]
   + _q(1.2,"🛏️","cobija","sabanas","almohada","cojin","cubrelecho","edredon","protector de colchon") + _q(1.5,"🏠","cortina","tapete","espejo","reloj de pared","canasta","caja organizadora","zapatero","perchero","cesto","caneca","multitoma","extension electrica","ambientador"),
 "Cocina": _q(1.5,"🍲","olla","bateria de cocina","olla de presion","vajilla","vasos","pocillos","platos","cuchillos","tabla de picar","recipiente","lonchera","molde","bandeja","escurridor","colador","jarra","botella","refractaria","utensilios de cocina","rallador"),
 "Electrodomésticos": [("licuadora",2.5,"🥤"),("sanduchera",1.5,"🥪"),("batidora",1.5,"🍰"),("freidora de aire",4.5,"🍟"),("cafetera",2,"☕"),("plancha de ropa",1.2,"👕"),("ventilador",3,"🌀"),("hervidor",1.2,"🫖")]
   + _q(3,"🔌","olla arrocera","olla multifuncional","aspiradora","robot aspirador","extractor de jugos","procesador de alimentos","waflera","tostadora","horno electrico","exprimidor","purificador","humidificador","calefactor","dispensador de agua","maquina de coser","plancha a vapor"),
 "Muebles": _q(25,"🛋️","sofa","sofa cama","silla","silla de oficina","silla gamer","escritorio","mesa","mesa de noche","nochero","comedor","cama","colchon","base cama","closet","mueble tv","biblioteca","repisa","cajonero","tocador","banco","puff","organizador de zapatos"),
 "Herramientas": [("taladro",2,"🔩"),("destornillador",.3,"🪛"),("juego de llaves",1.5,"🔧"),("brocas",.4,"🔩"),("pulidora",2.5,"⚙️"),("alicate",.4,"🔧"),("metro cinta",.3,"📏"),("caja de herramientas",2,"🧰")]
   + _q(3,"🛠️","rotomartillo","atornillador","sierra","sierra circular","caladora","martillo","pistola de calor","compresor","hidrolavadora","soldador","multimetro","nivel","escalera","pinza","llave","guantes de trabajo","generador","lijadora","esmeril","pistola de silicona","banco de trabajo","carretilla"),
 "Baño": _q(3,"🚿","griferia","grifo","ducha","sanitario","lavamanos","toallero","jabonera","cortina de baño","mueble de baño","espejo de baño","dispensador de jabon","regadera","tapa sanitario","lavaplatos"),
 "Iluminación": _q(.5,"💡","lampara","bombillo","panel led","reflector","cinta led","lampara de techo","aplique","lampara de mesa","lampara de pie","luz solar","lampara solar","plafon"),
 "Jardín": _q(3,"🌿","manguera","matera","maceta","podadora","guadañadora","tijera de podar","cortasetos","pala","rastrillo","hamaca","parasol","silla exterior","juego de patio","piscina","fumigadora","aspersor","comedor exterior"),
 "Bicicletas": _q(14,"🚲","bicicleta","bicicleta electrica","patineta","patineta electrica","scooter","patines","monopatin","casco ciclismo","casco bicicleta"),
 "Papelería": [("colores",.3,"🖍️"),("cuaderno",.4,"📓"),("marcadores",.3,"🖊️"),("calculadora",.3,"🧮"),("morral",.7,"🎒"),("lapiceros",.15,"🖊️"),("cartuchera",.2,"✏️")]
   + _q(.3,"✏️","resaltador","lapiz","borrador","pegante","tijeras","agenda","block","carpeta","resma","plastilina","temperas","acuarelas","regla","sacapuntas","libreta","post it","cinta","silicona liquida","papel"),
 "Juguetes": [("lego",.6,"🧱"),("muñeca",.6,"🪆"),("carro control remoto",1,"🚗"),("juego de mesa",.8,"🎲"),("hot wheels",.2,"🏎️"),("peluche",.4,"🧸"),("rompecabezas",.6,"🧩")]
   + _q(.8,"🧸","barbie","nerf","figura de accion","dinosaurio","carro","pista","bloques","juguete","muñeco","play doh","didactico","pelota","casa de muñecas","cocina de juguete","drone"),
 "Belleza": [("secador de pelo",.8,"💨"),("plancha para cabello",.6,"✨"),("perfume",.4,"🌸"),("maquillaje",.15,"💄"),("afeitadora",.4,"🪒"),("cepillo electrico",.3,"🪥"),("crema",.3,"🧴")]
   + _q(.4,"💇","rizador","cepillo secador","cortapelo","maquina de afeitar","depiladora","shampoo","tinte","esmalte","labial","serum","bloqueador","desodorante","crema corporal","kit de maquillaje"),
 "Deportes": [("balon",.5,"⚽"),("termo deportivo",.4,"🥤"),("mancuernas",3,"🏋️"),("tapete yoga",1,"🧘")]
   + _q(2,"🏋️","pesas","banda elastica","barra olimpica","colchoneta","bicicleta estatica","caminadora","eliptica","banco de pesas","guantes","raqueta","rodillera","lazo","pelota","mat yoga","maquina de abdominales","kettlebell"),
}
# Perfiles de tienda (farmacias / jugueterías): consultas propias y solo estas categorías.
Q_FARMA = {
 "Belleza": _q(.25,"🧴","agua micelar","exfoliante","mascarilla","tonico facial","crema antiarrugas","gel limpiador","bloqueador","crema de manos","aceite corporal","tinte","crema para peinar","mascarilla capilar","protector termico") + [("crema hidratante",.25,"🧴"),("protector solar",.2,"☀️"),("serum facial",.1,"💧"),("limpiador facial",.25,"🧼"),("shampoo",.45,"🧴"),("acondicionador",.45,"🧴"),("tratamiento capilar",.3,"💆"),("contorno de ojos",.08,"👁️")],
 "Maquillaje": _q(.08,"💄","primer","iluminador","brochas","esmalte","cejas","polvo suelto","fijador de maquillaje","paleta de sombras","bronzer","desmaquillante","gloss","pestañas") + [("base maquillaje",.1,"💄"),("labial",.05,"💋"),("pestañina",.05,"👁️"),("polvo compacto",.08,"💄"),("delineador",.04,"✏️"),("corrector",.05,"💄"),("rubor",.06,"🌸"),("sombras",.1,"🎨")],
 "Cuidado personal": _q(.3,"🧴","jabon","toallas humedas","pañales","gel antibacterial","talco","protectores diarios","seda dental","cuchillas de afeitar","crema de afeitar","tampones","crema antipañalitis","shampoo","crema para manos","repelente") + [("desodorante",.2,"🧴"),("crema dental",.2,"🪥"),("cepillo dental",.08,"🪥"),("enjuague bucal",.6,"🫧"),("jabon liquido",.5,"🧼"),("crema corporal",.45,"🧴"),("toallas higienicas",.2,"🌸"),("maquina de afeitar",.1,"🪒")],
 "Vitaminas y venta libre": _q(.15,"💊","vitamina d","vitamina e","complejo b","zinc","hierro","calcio","biotina","probiotico","melatonina","loratadina","antigripal","jarabe","electrolitos","termometro","tensiometro","glucometro","acetaminofen","naproxeno","diclofenaco gel","pastillas para la garganta","sales de rehidratacion","proteina","creatina","fibra","laxante","gotas para los ojos") + [("vitamina c",.15,"💊"),("multivitaminico",.2,"💊"),("omega 3",.2,"🐟"),("colageno",.4,"💊"),("magnesio",.2,"💊"),("acetaminofen",.05,"💊"),("ibuprofeno",.05,"💊"),("antiacido",.15,"💊"),("curitas",.05,"🩹"),("gasa",.08,"🩹"),("alcohol antiseptico",.4,"🩹"),("suero oral",.5,"💧")],
}
# Tiendas de deporte.
Q_DEPORTES = {
 "Calzado deportivo": _q(.9,"👟","tenis","tenis mujer","tenis hombre","tenis niño","tenis padel") + [("tenis running",.9,"👟"),("tenis trail",.9,"👟"),("tenis caminar",.8,"👟"),("tenis entrenamiento",.8,"👟"),("zapatos senderismo",1.1,"🥾"),("tenis senderismo",1.1,"🥾"),("botas senderismo",1.4,"🥾"),("zapatos acuaticos",.4,"🩴"),("tenis baloncesto",1,"🏀")],
 "Ropa deportiva": _q(.25,"👕","camiseta","short","chaqueta","sudadera","medias","buzo","bermuda","falda") + [("camiseta running",.2,"👕"),("camiseta running mujer",.2,"👕"),("leggings",.25,"🩱"),("pantaloneta",.25,"🩳"),("top deportivo",.15,"👙"),("chaqueta running",.4,"🧥"),("chaqueta impermeable",.5,"🧥"),("medias deportivas",.1,"🧦"),("jersey ciclismo",.25,"🚴"),("vestido de baño",.25,"🩱"),("gorra deportiva",.1,"🧢"),("camiseta senderismo",.2,"👕")],
 "Deportes": [("balon futbol",.5,"⚽"),("balon baloncesto",.65,"🏀"),("balon voleibol",.3,"🏐"),("mancuernas",3,"🏋️"),("pesa rusa",4,"🏋️"),("mat de yoga",1.2,"🧘"),("bloque yoga",.4,"🧘"),("banda elastica",.2,"🏋️"),("lazo para saltar",.3,"🤸"),("gafas de natacion",.1,"🥽"),("gorro de natacion",.08,"🏊"),("aletas",.7,"🏊"),("casco ciclismo",.4,"🚴"),("casco mtb",.4,"🚴"),("luz bicicleta",.15,"🚲"),("guantes ciclismo",.1,"🧤"),("candado",.6,"🔒"),("caramañola",.15,"🥤"),("botella running",.15,"🥤"),("guantes de boxeo",.7,"🥊"),("pelotas de padel",.3,"🎾"),("maleta deportiva",.7,"🎒")],
 "Camping": [("carpa",3,"⛺"),("carpa camping",3.5,"⛺"),("sleeping bag",1.2,"🛌"),("linterna",.25,"🔦"),("lampara",.3,"🏮"),("almohada",.3,"🛌"),("taza camping",.3,"☕"),("morral senderismo",.8,"🎒"),("morral 30 litros",1.2,"🎒"),("binoculares",.5,"🔭"),("toalla microfibra",.3,"🏖️")],
}
# Moda: ropa, calzado, bolsos/marroquinería y relojes (sin maletas de viaje grandes).
Q_MODA = {
 "Ropa": _q(.35,"👕","pijama","sudadera","short","bermuda","chaleco","top","body","leggings","brasier","boxer","medias","polo","overol","enterizo","kimono","saco","cardigan","jogger","vestido de baño") + [("camiseta",.25,"👕"),("blusa",.25,"👚"),("jean",.6,"👖"),("pantalon",.5,"👖"),("vestido",.4,"👗"),("falda",.3,"👗"),("chaqueta",.8,"🧥"),("buzo",.5,"🧥"),("camisa",.3,"👔")],
 "Calzado": _q(.9,"👟","chanclas","pantuflas","zapatillas","tacones","plataformas","zuecos","alpargatas","tenis blancos") + [("tenis",1,"👟"),("zapatos",1,"👞"),("sandalias",.6,"👡"),("botas",1.5,"👢"),("botines",1.3,"👢"),("baletas",.6,"🥿"),("mocasines",.9,"👞")],
 "Bolsos y accesorios": _q(.3,"👜","cartera","bolso cruzado","bolso de mano","collar","pulsera","anillo","bufanda","sombrero","maleta","mochila","neceser","llavero","cosmetiquera") + [("bolso",.7,"👜"),("manos libres",.5,"👜"),("maletin",1,"💼"),("tote",.7,"👜"),("morral",.8,"🎒"),("billetera",.15,"👛"),("cinturon",.25,"🪢"),("riñonera",.3,"👝"),("gafas de sol",.15,"🕶️"),("gorra",.15,"🧢"),("aretes",.05,"💍")],
 "Relojes": [("reloj",.3,"⌚"),("reloj hombre",.3,"⌚"),("reloj mujer",.3,"⌚"),("reloj digital",.3,"⌚"),("reloj inteligente",.3,"⌚"),("reloj casio",.3,"⌚")],
}
PERFIL = {"farmacia": Q_FARMA, "juguetes": {"Juguetes": Q["Juguetes"]}, "deportes": Q_DEPORTES, "moda": Q_MODA}
# Solo venta libre: se descartan medicamentos con fórmula, antibióticos, controlados, inyectables y cadena de frío.
RXBLOCK = re.compile(r"f[oó]rmula m[eé]dica|venta bajo|prescripci|antibi[oó]tic|antiinfeccios|controlad|inyect|ampolla|jeringa|aguja|insulina|vacuna|refrigera|cadena de fr[ií]o|\b2\s*°?\s*c?\s*(a|-)\s*8\s*°|amoxi|azitro|cefal|ciproflox|claritro|doxicicl|metronid|clindami|penicil|tramadol|code[ií]na|morfina|oxicod|clonazep|alpraz|diazep|lorazep|zolpidem|fentan|pregabal|gabapent|anticoncept|levonorg|hormon|testoster|estradi|cortico|prednis|dexameta|betameta|sildenaf|tadalaf|metformin|losart|enalapr|atorvast|omepraz|esomepraz|isotretin|finaster|minoxidil oral|clopidog|warfar|tretino|antidepres|sertral|fluoxet|quetiap|risperid|ketorolac|diclofenac.*(ampolla|inyect)|n[aá]proxeno s[oó]dico 550|metocarbam|tizanid|orfenadr|carisoprod|\b800\s*mg|\b\d{2,3}\.?000\s*u\.?i", re.I)

PER_CAT = int(os.environ.get("PER_CAT", "150"))
PER_CAT_OVR = {"Celulares": 120, "Tablets": 60}  # tope por tienda y categoría (las demás usan PER_CAT)
def per_cat(c): return PER_CAT_OVR.get(c, PER_CAT)
NOSKIP = {"Celulares", "Tablets"}
SKIP_EXTRA = {"T2": ["Grandes electrodomésticos", "Muebles", "Bicicletas", "Jardín", "Baño", "Iluminación", "Cocina"]}  # por clave de tienda  # se consultan en todas las tiendas del perfil general aunque la config tenga "skip"
MINCOP = 1000  # sin topes de precio/peso/tamaño: el envío se cotiza aparte por WhatsApp
# Solo se excluye lo que no es un producto físico enviable.
NONPHYS = re.compile(r"tarjeta (de )?regalo|gift ?card|\bbono\b|garant[ií]a extendida|\bgarant[ií]a\b|\bservicio\b|instalaci[oó]n|\brecarga\b|licencia|\bpin\b|suscripci[oó]n|membres[ií]a|\bseguro\b", re.I)
# Celulares / Tablets: solo equipos (sin accesorios, juguetes ni medicamentos en tabletas).
PHONE = re.compile(r"\b(celular|smartphone|tel[eé]fono (m[oó]vil|celular)|iphone)\b", re.I)
PBRAND = re.compile(r"\b(samsung|galaxy|xiaomi|redmi|poco|motorola|moto|apple|honor|oppo|realme|tecno|infinix|zte|nubia|vivo|huawei|nokia|alcatel|kalley|google pixel|oneplus)\b", re.I)
SPEC = re.compile(r"\d+\s*gb|\b[45]g\b|\bram\b|pulgadas|\d\"|wi-?fi|\blte\b|android|iphone|ipad", re.I)
ACC1 = re.compile(r"^(forro|funda|vidrio|protector|cargador|cable|soporte|estuche|l[aá]mina|case|mica|hidrogel|adaptador|aud[ií]fonos?|aro|tr[ií]pode|selfie|holder|base|l[aá]piz|stylus|teclado|mouse|parlante|reloj|smartwatch|morral|malet[ií]n|bolso|cover|repuesto|bater[ií]a|memoria|micr[oó]fono|lente|gimbal|kit|anillo|power|cargadores|correa|pulso|manos libres|combo accesorios|accesorio)", re.I)
ACCX = re.compile(r"\bpara (tu |el |la )?(celular|tel[eé]fono|smartphone|tablet|tableta|iphone|ipad|samsung|xiaomi|motorola|galaxy)|\b(forro|funda|estuche|vidrio templado|protector de pantalla|l[aá]mina|hidrogel)\b", re.I)
NOTPHONE = re.compile(r"\b(tab|pad|tablet|tableta|watch\w*|buds|band|router|diadema|transmisor|reloj|smartwatch|port[aá]til|laptop|book|tv|televisor|nevera|monitor|usb|disco|ssd|micro ?sd|tarjeta|aspiradora|parlante|barra de sonido|lavadora|aire)\b", re.I)
TABK = re.compile(r"\b(tablet|tableta|ipad|galaxy tab|redmi pad|xiaomi pad|poco pad|matepad|honor pad|idea ?tab|lenovo tab|tab [a-z]?\d+)", re.I)
TOY = re.compile(r"juguete|did[aá]ctic|magic pad|para ni[ñn]os de \d|beb[eé]", re.I)
MED = re.compile(r"\b(tabletas?|pastillas?|c[aá]psulas?|grageas?)\b.*\b(gripa|dolor|\d+\s*mg|masticables?|efervescentes?|vitamina|und|recubiertas?)\b|dolex|acetaminof|ibuprof|naproxeno|loratadina|chocolate|jab[oó]n|lavavajilla|cloro", re.I)
TABNO = re.compile(r"digitalizadora|gr[aá]fica|dibujo|wacom|\blcd\b|escritura|magn[eé]tica|pizarra", re.I)

def device_ok(p):
    n = p["n"]
    if p["c"] not in ("Celulares", "Tablets"):
        # los equipos solo van en Celulares/Tablets (no en Tecnología, Videojuegos...)
        return not re.match(r"\s*((apple|nuevo|nueva)\s+)?(celular|smartphone|iphone|tablet|tableta|ipad)\b", n, re.I)
    if ACC1.search(n.strip()) or TOY.search(n) or MED.search(n) or RXBLOCK.search(n): return False
    if p["c"] == "Celulares":
        if ACCX.search(re.split(r"\s\+\s|\bcon\b|\bincluye\b", n)[0]): return False
        head = re.split(r"\s\+\s", n)[0]
        if NOTPHONE.search(head) and not re.match(r"\s*(celular|smartphone)\b", n, re.I): return False
        if re.match(r"\s*((apple|nuevo|nueva)\s+)?(celular|smartphone|tel[eé]fono (m[oó]vil|celular)|iphone)\b", n, re.I): return True
        return bool(re.match(r"\s*" + PBRAND.pattern, n, re.I) and re.search(r"\d+\s*gb", n, re.I))
    if p["c"] == "Tablets":
        if ACCX.search(re.split(r"\s\+\s|\bcon\b|\bincluye\b", n)[0]) or TABNO.search(n): return False
        if re.match(r"\s*(celular|smartphone|iphone)\b", n, re.I): return False  # combo celular + tablet: va en Celulares
        return bool(re.match(r"\s*((apple|samsung|lenovo|xiaomi|nueva?)\s+)?(tablet|tableta|ipad)", n, re.I) and SPEC.search(n))
    return True

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

def vtex(t, q, cat, kg, emo, n=50):
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
def algolia(t, q, cat, kg, emo, n=100):
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
def bob(t, q, cat, kg, emo, n=60):
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

def _root(w):
    w = re.sub(r"(?<=...)(es|s)$", "", nrm(w)) if len(w) > 5 else re.sub(r"(?<=..)s$", "", nrm(w))
    return w[:max(5, len(w) - 2)] if len(w) > 5 else w[:5]
STOP = {"de", "para", "con", "y", "el", "la", "los", "las", "en", "a"}
def root_miss(q, n, todas=False):
    """Relevancia: la raíz de la palabra principal (o de todas, con todas=True) debe estar en el nombre ("botas" ~ "Bota")."""
    t = nrm(n); ws = [w for w in q.split() if w not in STOP]
    return any(_root(w) not in t for w in (ws if todas else ws[:1]))
def root_late(q, n):
    """La palabra principal de la consulta debe estar entre las 4 primeras palabras del nombre."""
    return _root(q.split()[0]) not in " ".join(nrm(n).split()[:4])
FOOD = re.compile(r"^(salchichas?|tilapia|mojarra|pollo|carne|queso|jam[oó]n|chorizo|arroz|fr[ií]jol|galletas?|chocolates?|caf[eé] (molido|en grano|instant)|leche|yogur|pan|piment[oó]n|especias?|condimento|salsa|at[uú]n|papas?|tomate|cebolla|harina|az[uú]car|aceite de (cocina|oliva|girasol)|cereal|snack|papas fritas|gaseosa|jugo|agua (mineral|con gas)|bebida)\b", re.I)

BLOQ = {}  # grupo de bloqueo de envío -> productos descartados (para el resumen)
def ok(p):
    # relevancia: el nombre debe contener la raíz de la palabra principal de la consulta
    if root_miss(p["q"], p["n"], todas=p.get("tipo") not in ("plp", "sfcc") and p.get("perfil") not in ("moda", "farmacia")): return False
    if p.get("perfil") != "farmacia" and p["c"] not in ("Celulares", "Tablets") and root_late(p["q"], p["n"]): return False
    if p.get("perfil") != "farmacia" and FOOD.search(p["n"]): return False
    # moda: el nombre debe empezar por el tipo de prenda ("Vestido con falda..." no es una falda)
    if p.get("perfil") == "moda" and not nrm(p["n"]).split()[0].startswith(nrm(p["q"].split()[0])[:4]): return False
    if p["c"] in Q_FARMA and RXBLOCK.search(p["n"]): return False
    if not device_ok(p): return False
    b = envio.bloqueado(p["n"], p["c"])
    if b: BLOQ.setdefault(b, set()).add((p["store"], p["sid"])); return False
    return bool(MINCOP <= p["cop"] and p["src_img"] and not NONPHYS.search(p["n"]))

def collect_store(key, t, seen, cats=None, fails=None):
    """Consulta una tienda y devuelve sus productos elegidos (máx. per_cat por categoría)."""
    allp, fails = [], fails if fails is not None else []
    st = t["nombre"]; fn = lambda q, c, k, e, t=t: ADAPT[t["tipo"]](t, q, c, k, e)
    for cat, qs in PERFIL.get(t.get("perfil"), Q).items():
        if cat in t.get("skip", []) + SKIP_EXTRA.get(key, []) and cat not in NOSKIP: continue
        if cats and cat not in cats: continue
        got = []
        for q, kg, emo in list(qs) + [tuple(x) for x in t.get("extra", {}).get(cat, [])]:  # "extra": consultas propias de la tienda
            try: res = fn(q, cat, kg, emo)
            except Exception as e: res = []; fails.append(f"{st}/{q}: {e}")
            for p in res:
                p["q"], p["perfil"], p["tipo"] = q, t.get("perfil"), t["tipo"]
                if t.get("quitar"): p["n"] = re.sub(r"\s+", " ", re.sub(t["quitar"], "", p["n"], flags=re.I)).strip(" -,.")
                p["n"] = re.sub(r"^(.{15,}?) \1\b", r"\1", p["n"])  # "Bolso X Bolso X Negro" -> "Bolso X Negro"
                wk = kg_from(p["n"]) if re.search(r"mancuerna|pesa|kettlebell|disco", p["n"], re.I) else None
                if wk and p["kgsrc"] == "est": p["kg"], p["kgsrc"] = round(wk * (2 if re.search(r"\bpar\b", p["n"], re.I) else 1) + .2, 2), "nombre"
            if not res: fails.append(f"{st}/{q}: 0 resultados")
            got.append([p for p in res if ok(p)])
        # intercalar consultas para variedad
        picked, i = [], 0
        while len(picked) < per_cat(cat) and any(i < len(g) for g in got):
            for g in got:
                if i < len(g):
                    p = g[i]; k2 = (p["store"], p["sid"]); nk = p["n"].lower()[:40]
                    if k2 not in seen and nk not in seen and len(picked) < per_cat(cat):
                        seen.add(k2); seen.add(nk); picked.append(p)
            i += 1
        print(f"{st:13} {cat:26} {len(picked)}", file=sys.stderr, flush=True)
        allp += picked
    return allp

def collect(solo=None, seen=None, cats=None):
    allp, seen, fails = [], seen or set(), []
    for key, t in load_cfg().items():
        if solo and key not in solo: continue
        allp += collect_store(key, t, seen, cats, fails)
    return allp, fails

IMG_PX, IMG_Q = 440, 65  # imágenes nuevas: ~15-20 KB

def save_img(src, dest):
    if os.path.exists(dest): return True
    for i in range(2):
        try:
            r = requests.get(src, timeout=30, headers={"User-Agent": UA})
            if r.status_code != 200: return False
            im = Image.open(io.BytesIO(r.content)).convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[3])
            bg.thumbnail((IMG_PX, IMG_PX)); bg.save(dest, "JPEG", quality=IMG_Q, optimize=True, progressive=True)
            return True
        except Exception: time.sleep(2)
    return False

def pid(p): return hashlib.sha1(f"{p['store']}:{p['sid']}".encode()).hexdigest()[:10]

def build(prods, no_img, fails, workers=8):
    """Descarga imágenes (en paralelo) y arma los objetos publicados."""
    from concurrent.futures import ThreadPoolExecutor
    todo = [(p, f"img/p{pid(p)}.jpg") for p in prods]
    okimg = [True] * len(todo)
    if not no_img:
        with ThreadPoolExecutor(workers) as ex:
            okimg = list(ex.map(lambda x: save_img(x[0]["src_img"], os.path.join(ROOT, x[1])), todo))
    pub, priv = [], []
    for (p, fn), good in zip(todo, okimg):
        if not good: fails.append(f"img {p['store']}/{p['sid']}"); continue
        h = pid(p); o = {"id": h, "n": p["n"], "c": p["c"], "cop": p["cop"]}
        if p["antes"]: o["antes"] = p["antes"]
        o.update(kg=p["kg"], e=p["e"], img=fn)
        if p["rank"] < 3: o["top"] = 1
        pub.append(o); priv.append({**p, "id": h, "img": fn})
    return pub, priv

def limpia_nombres(pub, cfg):
    """Quita de los nombres públicos el nombre de la tienda de origen (marcas propias) y 'marca propia'."""
    rx = re.compile(r"\b(" + "|".join(re.escape(t["nombre"]) for t in cfg.values() if t.get("perfil") not in ("deportes", "moda")) + r"|[EÉ]xito|marca propia)\b", re.I)
    for o in pub: o["n"] = re.sub(r"\s{2,}", " ", rx.sub("", o["n"])).strip(" -,.")
    return [o for o in pub if not FOOD.search(o["n"])]

def slug(c): return re.sub(r"[^a-z0-9]+", "-", nrm(c)).strip("-")

def write_site(pub):
    """productos.json (completo, para el feed y las publicaciones) + data/idx.json (liviano, búsqueda y tarjetas)
    + data/c/<categoría>.json (completo por categoría, se carga al abrir la categoría)."""
    hoy = time.strftime("%Y-%m-%d")
    with open(os.path.join(ROOT, "productos.json"), "w", encoding="utf-8") as f:
        json.dump({"actualizado": hoy, "productos": pub}, f, ensure_ascii=False, separators=(",", ":"))
    cats = list(dict.fromkeys(o["c"] for o in pub)); ci = {c: i for i, c in enumerate(cats)}
    os.makedirs(os.path.join(ROOT, "data", "c"), exist_ok=True)
    rows = []
    for o in pub:
        fl = (1 if o.get("top") else 0) | (2 if o.get("envio") == "consultar" else 0) | (4 if o.get("max_qty") else 0) | (8 if o.get("nota") else 0)
        rows.append([o["id"], o["n"], ci[o["c"]], o["cop"], o.get("antes") or 0, fl])
    with open(os.path.join(ROOT, "data", "idx.json"), "w", encoding="utf-8") as f:
        json.dump({"actualizado": hoy, "cats": [[c, slug(c)] for c in cats], "p": rows}, f, ensure_ascii=False, separators=(",", ":"))
    keep = set()
    for c in cats:
        fn = slug(c) + ".json"; keep.add(fn)
        with open(os.path.join(ROOT, "data", "c", fn), "w", encoding="utf-8") as f:
            json.dump({"c": c, "productos": [o for o in pub if o["c"] == c]}, f, ensure_ascii=False, separators=(",", ":"))
    for x in os.listdir(os.path.join(ROOT, "data", "c")):
        if x.endswith(".json") and x not in keep: os.remove(os.path.join(ROOT, "data", "c", x))

ESTADO = os.path.join(ROOT, "data", "estado.json")  # clave de tienda -> fecha + ids (sin nombres ni URLs)

def load_estado(cfg):
    if os.path.exists(ESTADO): return json.load(open(ESTADO, encoding="utf-8"))
    est = {}
    fp = os.path.join(DATA, "fuentes.json")
    if os.path.exists(fp):
        k_of = {t["nombre"]: k for k, t in cfg.items()}
        for p in json.load(open(fp, encoding="utf-8"))["productos"]:
            k = k_of.get(p["store"])
            if k: est.setdefault(k, {"fecha": "", "ids": []})["ids"].append(p["id"])
    return est

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--no-img", action="store_true")
    ap.add_argument("--solo", help="claves de tienda separadas por coma; conserva el resto tal cual está publicado en productos.json")
    ap.add_argument("--cats", help="con --solo: solo rehace estas categorías (coma); las demás categorías de esas tiendas se conservan")
    ap.add_argument("--budget", type=float, help="minutos: actualiza tiendas de la más antigua a la más reciente hasta agotar el tiempo (incremental)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--par", type=int, default=1, help="tiendas consultadas en paralelo (sin --budget)")
    a = ap.parse_args(); t0 = time.time()
    cats = set(a.cats.split(",")) if a.cats else None
    os.makedirs(DATA, exist_ok=True); os.makedirs(IMG, exist_ok=True)
    cfg = load_cfg(); est = load_estado(cfg); fails = []
    full = not (a.solo or a.budget)
    if a.solo: order = [k for k in a.solo.split(",") if k in cfg]
    else: order = sorted(cfg, key=lambda k: (est.get(k, {}).get("fecha", ""), k)) if a.budget else list(cfg)
    owner = {i: k for k, v in est.items() for i in v.get("ids", [])}
    pubold = [] if full else json.load(open(os.path.join(ROOT, "productos.json"), encoding="utf-8"))["productos"]
    pubold = [o for o in pubold if os.path.exists(os.path.join(ROOT, o["img"]))]
    fp = os.path.join(DATA, "fuentes.json")
    privold = {p["id"]: p for p in json.load(open(fp, encoding="utf-8"))["productos"]} if os.path.exists(fp) and not full else {}
    insc = lambda c: cats is None or c in cats
    done, newpub, newpriv, seen = [], [], [], set()
    pre = {}
    if a.par > 1 and not a.budget:  # consulta varias tiendas a la vez (hosts distintos)
        from concurrent.futures import ThreadPoolExecutor
        sn0 = {o["n"].lower()[:40] for o in pubold if owner.get(o["id"]) not in order}
        with ThreadPoolExecutor(a.par) as ex:
            futs = {k: ex.submit(collect_store, k, cfg[k], sn0, cats, fails) for k in order}
            pre = {k: f.result() for k, f in futs.items()}
    for k in order:
        if a.budget and done and (time.time() - t0) / 60 > a.budget: break
        mine = lambda o: owner.get(o["id"]) == k or (o["id"] not in owner and privold.get(o["id"], {}).get("store") == cfg[k]["nombre"])
        # nombres de otras tiendas (aún no rehechas) para no duplicar el mismo producto
        sn = seen | {o["n"].lower()[:40] for o in pubold if not (mine(o) and insc(o["c"])) and owner.get(o["id"]) not in done}
        print(f"== {k} ({(time.time()-t0)/60:.1f} min)", file=sys.stderr, flush=True)
        prods = pre[k] if k in pre else collect_store(k, cfg[k], sn, cats, fails)
        if not prods: fails.append(f"{k}: 0 productos (se conserva lo publicado)"); continue
        pb, pv = build(prods, a.no_img, fails, a.workers)
        seen |= {o["n"].lower()[:40] for o in pb}
        newpub += pb; newpriv += pv; done.append(k)
        kept = [o["id"] for o in pubold if mine(o) and not insc(o["c"])]
        est[k] = {"fecha": time.strftime("%Y-%m-%d %H:%M"), "ids": kept + [o["id"] for o in pb]}
    # mezcla: lo publicado de tiendas no rehechas (o de categorías no rehechas) + lo nuevo
    newids = {o["id"] for o in newpub}; pub = []
    for o in pubold:
        k = owner.get(o["id"]) or next((kk for kk in done if privold.get(o["id"], {}).get("store") == cfg[kk]["nombre"]), None)
        if o["id"] in newids: continue
        if k in done and insc(o["c"]): continue
        if k is None and cats and o["c"] in cats: continue  # publicado desfasado (sin fuente) en una categoría rehecha
        pub.append(o)
    pub += newpub
    pub = limpia_nombres(pub, cfg)
    pub, envres = envio.aplicar(pub); keep = {o["id"] for o in pub}
    for g, xs in BLOQ.items(): envres["excluidos"][g] += len(xs)
    if not pub: sys.exit("sin productos; no se sobrescribe nada")
    write_site(pub)
    for k in est: est[k]["ids"] = [i for i in est[k]["ids"] if i in keep]
    json.dump(est, open(ESTADO, "w", encoding="utf-8"), separators=(",", ":"))
    priv = [p for i, p in privold.items() if i in keep and i not in newids] + [p for p in newpriv if p["id"] in keep]
    with open(os.path.join(DATA, "fuentes.json"), "w", encoding="utf-8") as f:
        json.dump({"productos": priv, "fallos": fails}, f, ensure_ascii=False, indent=1)
    if not a.no_img:  # borrar imágenes huérfanas
        used = {os.path.basename(o["img"]) for o in pub}
        for x in os.listdir(IMG):
            if x.startswith("p") and x.endswith(".jpg") and x not in used: os.remove(os.path.join(IMG, x))
    from collections import Counter
    print(json.dumps({"total": len(pub), "tiendas_rehechas": done, "minutos": round((time.time() - t0) / 60, 1),
                      "nuevos_por_tienda_categoria": Counter(f'{p["store"]} / {p["c"]}' for p in newpriv if p["id"] in keep),
                      "por_categoria": Counter(o["c"] for o in pub),
                      "envio": {k: dict(v) for k, v in envres.items()},
                      "fallos": len(fails)}, ensure_ascii=False, indent=1))

if __name__ == "__main__": main()
