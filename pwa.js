/* Instalación como app (PWA): registra el service worker y muestra «Instalar app» cuando se puede. */
(function () {
  if (!("serviceWorker" in navigator) || location.pathname.startsWith("/admin")) return;
  addEventListener("load", function () { navigator.serviceWorker.register("/sw.js").catch(function () {}); });
  var standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  if (standalone) return;
  var ios = /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  var deferred = null;
  function btn() {
    var b = document.getElementById("inst");
    if (!b) {
      var host = document.querySelector(".hact") || document.querySelector(".hrow");
      if (!host) return null;
      b = document.createElement("button");
      b.id = "inst"; b.type = "button";
      b.style.cssText = "font:inherit;font-size:.72rem;font-weight:700;color:#0D214F;background:#FFCC00;border:0;border-radius:999px;padding:6px 10px;cursor:pointer;white-space:nowrap";
      b.textContent = "📲 Instalar app";
      host.appendChild(b);
    }
    return b;
  }
  function tip() {
    var t = document.getElementById("insttip");
    if (t) { t.remove(); return; }
    t = document.createElement("div"); t.id = "insttip"; t.setAttribute("role", "dialog");
    t.style.cssText = "position:fixed;left:12px;right:12px;bottom:84px;z-index:99;background:#0D214F;color:#fff;border-radius:14px;padding:14px 40px 14px 16px;font-size:.9rem;line-height:1.4;box-shadow:0 8px 30px #0006";
    t.innerHTML = "Para instalar la app en tu iPhone: toca <b>Compartir</b> <span aria-hidden=\"true\">⬆️</span> en Safari y luego <b>«Agregar a inicio»</b>.<button aria-label=\"Cerrar\" style=\"position:absolute;top:6px;right:8px;background:none;border:0;color:#fff;font-size:1.3rem;cursor:pointer\">×</button>";
    t.querySelector("button").onclick = function () { t.remove(); };
    document.body.appendChild(t);
  }
  function show(fn) { var b = btn(); if (!b) return; b.hidden = false; b.onclick = fn; }
  addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault(); deferred = e;
    show(function () { deferred.prompt(); deferred.userChoice.finally(function () { deferred = null; var b = btn(); if (b) b.hidden = true; }); });
  });
  addEventListener("appinstalled", function () { var b = document.getElementById("inst"); if (b) b.hidden = true; });
  if (ios) (document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", function () { show(tip); }) : show(tip));
})();
