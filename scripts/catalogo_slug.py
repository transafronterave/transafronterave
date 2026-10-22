"""slug() de categorías compartido por catalogo.py y ajustes.py (sin dependencias externas)."""
import re, unicodedata
def nrm(t): return "".join(ch for ch in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(ch) != "Mn")
def slug(c): return re.sub(r"[^a-z0-9]+", "-", nrm(c)).strip("-")
