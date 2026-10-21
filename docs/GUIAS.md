# Guías (contenido SEO)

Sección `/guias/` de transafronterave.com. Cada guía es una spec JSON en `data/guias/<slug>.json`
que `scripts/guias.py` convierte en `guias/<slug>/index.html` (title, meta description, canonical, Open Graph,
JSON-LD Article + BreadcrumbList + FAQPage si hay FAQ, H1/H2, grilla de productos del catálogo, CTA de WhatsApp
y 2–3 guías relacionadas). El script también regenera `guias/index.html` (más nuevas primero), `sitemap.xml`
y se asegura de que `robots.txt` apunte al sitemap. El formato de la spec está documentado al inicio del script.

Precios: se calculan igual que el sitio y el feed Meta (`cop × 1.20 / usdt_venta` de `tasas.json`). Solo se muestra
el precio actual en USD (nunca el precio de referencia de la tienda). Los enlaces van a `/#p=<id>`.

## Corrida nocturna (una guía por noche)

1. `git pull --rebase` (el catálogo y las tasas se actualizan solos).
2. **Elegir tema:** `python3 scripts/guias.py --next` devuelve el primer tema `pending` de `data/guias_temas.json`
   (orden = prioridad). Si no hay pendientes, terminar sin cambios.
3. **Escribir contenido:** crear la spec (fuera de `data/guias/`, p. ej. `/tmp/<slug>.json`) con `slug`/`title` del
   tema, `description` (~150–160 car.), `date` (hoy), `tags`, `intro`, 5–8 `sections` con H2, `faq` (4–8 preguntas)
   y `products` = el filtro `productos` del backlog (o `null` en guías de confianza). 900–1300 palabras, español
   de Venezuela, cálido y práctico. Reglas obligatorias:
   - Envío: decir siempre «Enviamos por MRW a toda Venezuela (costo aparte)»; costos y tiempos «se cotizan por
     WhatsApp». Nunca inventar plazos ni costos. Nunca «envío incluido»/«envío gratis».
   - Usar «enviamos», nunca «mandamos». Nunca nombrar tiendas de origen ni sus precios (ojo: tampoco usar la
     palabra «[tienda]», el validador la bloquea). Nunca mencionar al aliado de Cúcuta.
   - Pagos: Zelle, Binance USDT, pago móvil, efectivo USD, Bancolombia, Nequi (sin números de cuenta).
   - Medicamentos/vitaminas: solo venta libre, sin afirmaciones de salud, «máx. 6 unidades».
   - Artículos en lista de validación MRW: «Envío sujeto a validación, consúltanos por WhatsApp»
     (prohibidos: armas, inflamables, corrosivos, bombonas de gas, vapes, joyería fina, animales…).
   - Precios: solo los que pinta el script desde el catálogo; no escribir precios a mano en el texto.
4. **Generar:** `python3 scripts/guias.py /tmp/<slug>.json` — copia la spec a `data/guias/`, re-renderiza
   *todas* las guías (refresca precios, productos y guías relacionadas), el índice y el sitemap, y marca el tema
   `published` en el backlog.
5. **Validar:** el mismo comando (o `python3 scripts/guias.py --check`) sale con código 1 si:
   falta algún HTML o etiqueta SEO (title, description, canonical, og, JSON-LD, H1/H2), falta «costo aparte» o el CTA
   de WhatsApp, un enlace `/#p=<id>` no existe en `data/idx.json` o no tiene imagen, un enlace a otra guía no existe,
   o aparece una frase prohibida («envío incluido», «mandamos», «[aliado]», tiendas como [tienda], [tienda],
   [tienda], [tienda], etc.; se suman los nombres de `scripts/data/fuentes_config.json` si existe).
   Los `AVISO` (pocas palabras, posibles afirmaciones de salud) se revisan a mano. Si hay errores: corregir la spec y
   repetir; no publicar.
6. **Publicar:**
   ```
   git add guias data/guias data/guias_temas.json sitemap.xml robots.txt
   git commit -m "Guía: <título>"
   for i in 1 2 3; do git pull --rebase && git push && break; sleep 5; done
   ```
7. **Verificar:** a los 1–3 minutos, `curl -sI https://transafronterave.com/guias/<slug>/` debe dar 200
   (reintentar; GitHub Pages tarda en desplegar).

Como los productos del catálogo cambian, re-ejecutar `python3 scripts/guias.py` (sin argumentos) refresca todas las
guías sin agregar ninguna; la corrida nocturna lo hace implícitamente en el paso 4.
