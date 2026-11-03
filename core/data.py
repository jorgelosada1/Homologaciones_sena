"""Carga de datos (Excel/JSON) con caché por fecha de modificación y lógica de homologación."""
import os
import threading

import pandas as pd

from .storage import load_json, save_json
from .text import clean_df, norm, similarity, program_similarity, pretty_name, tokens

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
ACTAS_FILE = os.path.join(BASE_DIR, "Actas SENA.xlsx")
PRESENCIAL_FILE = os.path.join(BASE_DIR, "Presencial 2026.xlsx")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

ACTAS_COLUMNS = ["PROGRAMA", "TÉCNICO O TECNOLOGÍA", "SEMTR HOMOLOGADOS", "FALTANTES"]

DEFAULT_CONFIG = {
    "descuento_sena": 20,
    "inicio_clases": "2 de febrero de 2027",
    "inicio_posgrado": "2027",
    "ahorro_inscripcion": 70000,
    "ahorro_estudio": 450000,
    "cuotas_financiacion": 5,
    "nombre_asesor": "",
    "telefono_prefijo": "57",
    "anio": 2027,
}

# Columnas por sede en el Excel presencial (programa, título, homologados, pendientes)
SEDES = {
    "bogota": {"label": "Bogotá", "icon": "fa-city", "programa": "Unnamed: 0", "titulo": "Sede Bogota",
               "homo": "Semestres de Homologacion", "pend": "Semestres Pendientes"},
    "pereira": {"label": "Pereira", "icon": "fa-mountain-sun", "programa": "Unnamed: 7", "titulo": "Sede Pereira",
                "homo": "Semestres de Homologacion.1", "pend": "Semestres Pendientes.1"},
    "valledupar": {"label": "Valledupar", "icon": "fa-sun", "programa": "Unnamed: 14", "titulo": "Sede Valledupar",
                   "homo": "Semestres de Homologacion.2", "pend": "Semestres Pendientes.2"},
}


def _to_int(v, default=0):
    try:
        if pd.isna(v):
            return default
        return int(round(float(v)))
    except (TypeError, ValueError):
        return default


ACTAS_SHEET = "SENA VIRTUAL 1"
PRESENCIAL_SHEET = "PRESENCIAL"
EMSUB_SHEET = "EMSUB"
SEDE_COLS = {"bogota": 0, "pereira": 6, "valledupar": 12}
# Hojas con datos personales que nunca deben quedar en el repositorio
PERSONAL_DATA_MARKERS = ("CORREO", "CELULAR", "NUMERO DOCUMENTO", "NOMBRE APRENDIZ", "REP DRIVE", "TEL CELULAR")


def _sheet_names(path):
    return pd.ExcelFile(path).sheet_names


def _title_case(s):
    """Normaliza títulos con mayúsculas desordenadas: 'Tecnologia EN GESTIoN PÚBLICA' -> 'Tecnología en Gestión Pública'."""
    s = " ".join(str(s).split())
    if s.isupper() or any(w[:1].islower() and any(c.isupper() for c in w[1:]) for w in s.split()) or " EN " in s:
        words = []
        for w in s.split():
            words.append(w if "." in w and w.upper() == w else w)
        fixed = pretty_name(" ".join(w if "." in w else w.lower() for w in words))
        return fixed.replace("Tecnologia", "Tecnología")
    return s


def load_actas_virtual(path):
    sheets = _sheet_names(path)
    sheet = ACTAS_SHEET if ACTAS_SHEET in sheets else sheets[0]
    df = clean_df(pd.read_excel(path, sheet_name=sheet))
    df = df.dropna(subset=["PROGRAMA", "TÉCNICO O TECNOLOGÍA"]).copy()
    df["PROGRAMA"] = df["PROGRAMA"].astype(str).str.strip().str.upper()
    df["TÉCNICO O TECNOLOGÍA"] = df["TÉCNICO O TECNOLOGÍA"].astype(str).map(lambda x: " ".join(x.split()))
    df["SEMTR HOMOLOGADOS"] = pd.to_numeric(df["SEMTR HOMOLOGADOS"], errors="coerce").fillna(0).astype(int)
    df["FALTANTES"] = pd.to_numeric(df["FALTANTES"], errors="coerce").fillna(0).astype(int)
    fdi = df["TITULO EN FDI"] if "TITULO EN FDI" in df.columns else pd.Series([""] * len(df), index=df.index)
    df["_fdi"] = fdi.fillna("").astype(str).str.strip()
    df["_fuente"] = "SENA"
    # Unificar variantes del mismo programa (con/sin tilde)
    canon = {}
    for p in df["PROGRAMA"]:
        canon.setdefault(norm(p), p)
    df["PROGRAMA"] = df["PROGRAMA"].map(lambda p: canon[norm(p)])
    cols = ["PROGRAMA", "TÉCNICO O TECNOLOGÍA", "SEMTR HOMOLOGADOS", "FALTANTES", "_fdi", "_fuente"]
    df = df[cols]

    if EMSUB_SHEET in sheets:
        try:
            em = clean_df(pd.read_excel(path, sheet_name=EMSUB_SHEET))
            totales = (df["SEMTR HOMOLOGADOS"] + df["FALTANTES"]).groupby(df["PROGRAMA"].map(norm)).agg(lambda x: x.mode().iloc[0])
            extra = []
            for _, r in em.dropna(subset=["PROGRAMA EMSUB", "PROGRAMA ANDINA"]).iterrows():
                prog = canon.get(norm(r["PROGRAMA ANDINA"]), str(r["PROGRAMA ANDINA"]).strip().upper())
                falt = _to_int(r.get("SEMESTRES FALTANTES"))
                total = int(totales.get(norm(prog), falt))
                extra.append({"PROGRAMA": prog, "TÉCNICO O TECNOLOGÍA": _title_case(r["PROGRAMA EMSUB"]),
                              "SEMTR HOMOLOGADOS": max(total - falt, 0), "FALTANTES": falt, "_fdi": "", "_fuente": "EMSUB"})
            if extra:
                df = pd.concat([df, pd.DataFrame(extra)], ignore_index=True)
        except Exception as e:
            print("No se pudo leer EMSUB:", e)

    df = df.drop_duplicates(subset=["PROGRAMA", "TÉCNICO O TECNOLOGÍA"]).reset_index(drop=True)
    df["_titulo_norm"] = df["TÉCNICO O TECNOLOGÍA"].map(norm)
    return df


def load_presencial_actas(path):
    """Lee la hoja PRESENCIAL del acta: por sede, filas de programa (sin números) seguidas de sus títulos."""
    if PRESENCIAL_SHEET not in _sheet_names(path):
        return []
    raw = pd.read_excel(path, sheet_name=PRESENCIAL_SHEET, header=None)
    rows = []
    for sede, c in SEDE_COLS.items():
        if raw.shape[1] <= c + 3:
            continue
        programa = None
        for i in range(raw.shape[0]):
            t = raw.iat[i, c]
            if pd.isna(t) or not str(t).strip():
                continue
            t = " ".join(str(t).split())
            if t.lower().startswith("sede "):
                continue
            h, pe = raw.iat[i, c + 1], raw.iat[i, c + 3]
            h_num = pd.to_numeric(pd.Series([h]), errors="coerce").iloc[0]
            p_num = pd.to_numeric(pd.Series([pe]), errors="coerce").iloc[0]
            if pd.isna(h_num) and pd.isna(p_num):
                programa = pretty_name(t)
                continue
            if programa is None:
                continue
            rows.append({"sede": sede, "programa": programa, "titulo": t.rstrip("."),
                         "homologados": _to_int(h_num), "pendientes": _to_int(p_num)})
    return rows


def sanitize_workbook(path):
    """Elimina del Excel las hojas con datos personales. Devuelve la lista de hojas removidas."""
    from openpyxl import load_workbook
    from .text import strip_accents
    wb = load_workbook(path)
    removed = []
    for ws in list(wb.worksheets):
        header = " ".join(str(c.value or "") for row in ws.iter_rows(min_row=1, max_row=3) for c in row)
        header = strip_accents(header).upper().replace(".", "")
        if any(m in header for m in PERSONAL_DATA_MARKERS) and ws.title not in (ACTAS_SHEET, PRESENCIAL_SHEET, EMSUB_SHEET):
            removed.append(ws.title)
            wb.remove(ws)
    if removed:
        wb.save(path)
    return removed


class DataStore:
    """Mantiene los datos en memoria y los recarga solo cuando cambia el archivo."""

    def __init__(self):
        self._lock = threading.RLock()
        self._cache = {}

    # ---------- caché genérica ----------
    def _cached(self, key, path, loader):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = None
        with self._lock:
            hit = self._cache.get(key)
            if hit and hit[0] == mtime:
                return hit[1]
            value = loader() if mtime is not None else loader(missing=True)
            self._cache[key] = (mtime, value)
            return value

    def invalidate(self):
        with self._lock:
            self._cache.clear()

    # ---------- JSON ----------
    def json(self, name, default=None):
        path = os.path.join(DATA_DIR, name)
        return self._cached("json:" + name, path, lambda missing=False: load_json(path, default if default is not None else []))

    def save(self, name, data):
        save_json(os.path.join(DATA_DIR, name), data)
        with self._lock:
            self._cache.pop("json:" + name, None)

    @property
    def config(self):
        cfg = dict(DEFAULT_CONFIG)
        cfg.update(self.json("config.json", {}) or {})
        return cfg

    def render(self, text):
        """Reemplaza variables de configuración dentro de los mensajes guardados."""
        if not isinstance(text, str):
            return text
        cfg = self.config
        valores = {
            "{inicio_pregrado}": cfg.get("inicio_clases", ""),
            "{inicio_clases}": cfg.get("inicio_clases", ""),
            "{inicio_posgrado}": cfg.get("inicio_posgrado", ""),
            "{descuento_sena}": f"{cfg.get('descuento_sena', 20)}%",
            "{anio}": str(cfg.get("anio", "")),
        }
        for k, v in valores.items():
            text = text.replace(k, str(v))
        return text

    def render_list(self, items):
        return [{**m, "titulo": self.render(m.get("titulo", "")), "texto": self.render(m.get("texto", ""))} for m in items]

    def precios(self):
        return self.json("precios.json")

    def mensajes_programas(self):
        return self.json("mensajes_programas.json")

    def mensajes_sena(self):
        return self.json("mensajes_sena.json")

    # ---------- Actas (virtual) ----------
    def actas(self):
        def load(missing=False):
            if missing:
                return pd.DataFrame(columns=ACTAS_COLUMNS)
            return load_actas_virtual(ACTAS_FILE)
        return self._cached("actas", ACTAS_FILE, load)

    def titulos(self):
        df = self.actas()
        return sorted(df["TÉCNICO O TECNOLOGÍA"].unique().tolist(), key=lambda t: norm(t))

    def programas_actas(self):
        df = self.actas()
        return sorted(df["PROGRAMA"].unique().tolist())

    # ---------- Presencial ----------
    def presencial(self):
        def load(missing=False):
            rows = []
            if os.path.exists(ACTAS_FILE):
                try:
                    rows = load_presencial_actas(ACTAS_FILE)
                except Exception as e:  # hoja ausente o con otro formato
                    print("Hoja PRESENCIAL del acta no disponible:", e)
                    rows = []
            if rows:
                return rows
            if missing:
                return rows
            df = clean_df(pd.read_excel(PRESENCIAL_FILE))
            for key, s in SEDES.items():
                if s["titulo"] not in df.columns:
                    continue
                prog_col = s["programa"] if s["programa"] in df.columns else df.columns[0]
                for _, r in df.iterrows():
                    titulo = r.get(s["titulo"])
                    if pd.isna(titulo) or not str(titulo).strip():
                        continue
                    programa = r.get(prog_col)
                    rows.append({
                        "sede": key,
                        "programa": pretty_name(str(programa).strip()) if not pd.isna(programa) else "",
                        "titulo": str(titulo).strip().rstrip("."),
                        "homologados": _to_int(r.get(s["homo"])),
                        "pendientes": _to_int(r.get(s["pend"])),
                    })
            return rows
        key = f"presencial:{os.path.exists(ACTAS_FILE) and os.path.getmtime(ACTAS_FILE)}"
        return self._cached(key, PRESENCIAL_FILE, load)

    def titulos_presencial(self):
        return sorted({r["titulo"] for r in self.presencial()}, key=norm)

    # ---------- Precios ----------
    def match_precio(self, programa):
        best, best_score = None, 0.0
        for p in self.precios():
            sc = program_similarity(programa, p.get("programa", ""))
            if sc > best_score:
                best, best_score = p, sc
        return best if best_score >= 0.66 else None


def rank_titles(query, titles, limit=8, threshold=0.62):
    scored = []
    for t in titles:
        sc = similarity(query, t)
        if sc >= threshold:
            scored.append((sc, t))
    scored.sort(key=lambda x: (-x[0], len(x[1])))
    return [{"titulo": t, "score": round(s, 3)} for s, t in scored[:limit]]


def resolve_titles(query, titles):
    """Devuelve (titulos_elegidos, sugerencias, modo).

    modo: 'exacto' | 'contiene' | 'aproximado' | 'ninguno'
    """
    qn = norm(query)
    if not qn:
        return [], [], "ninguno"
    exact = [t for t in titles if norm(t) == qn]
    if exact:
        return exact, [], "exacto"
    qtok = tokens(query)
    if qtok:
        same = [t for t in titles if tokens(t) == qtok]
        if same:
            return same, [], "exacto"
    contains = [t for t in titles if qn in norm(t)]
    if contains:
        return contains, [], "contiene"
    ranked = rank_titles(query, titles, limit=6, threshold=0.6)
    if ranked and ranked[0]["score"] >= 0.8:
        top = ranked[0]["titulo"]
        return [top], [r["titulo"] for r in ranked[1:]], "aproximado"
    return [], [r["titulo"] for r in ranked], "ninguno"


def build_programa(store, programa, homologados, faltantes, cfg, total=None):
    precio = store.match_precio(programa)
    item = {
        "programa": programa,
        "programa_display": pretty_name(programa),
        "homologados": homologados,
        "faltantes": faltantes,
        "total": total if total is not None else homologados + faltantes,
        "precio": None,
    }
    if precio:
        valor = int(precio.get("valor", 0))
        desc = int(cfg.get("descuento_sena", 20))
        final = valor - round(valor * desc / 100)
        item["precio"] = {
            "id": precio.get("id"),
            "programa": precio.get("programa"),
            "valor": valor,
            "descuento": desc,
            "valor_final": final,
            "semestres": precio.get("semestres"),
            "inversion_total": final * faltantes,
            "ahorro_homologacion": valor * homologados,
            "ahorro_descuento": (valor - final) * faltantes,
        }
        item["precio"]["ahorro_total"] = (
            item["precio"]["ahorro_homologacion"] + item["precio"]["ahorro_descuento"]
            + int(cfg.get("ahorro_inscripcion", 0)) + int(cfg.get("ahorro_estudio", 0))
        )
    pct = (homologados / item["total"] * 100) if item["total"] else 0
    item["porcentaje"] = round(pct)
    return item


def buscar_homologacion(store, query):
    """Búsqueda estructurada para modalidad virtual."""
    df = store.actas()
    titles = df["TÉCNICO O TECNOLOGÍA"].unique().tolist()
    elegidos, sugerencias, modo = resolve_titles(query, titles)
    cfg = store.config
    grupos = []
    for t in sorted(elegidos, key=norm):
        sub = df[df["TÉCNICO O TECNOLOGÍA"] == t]
        programas = []
        vistos = set()
        for _, r in sub.iterrows():
            key = norm(r["PROGRAMA"])
            if key in vistos:
                continue
            vistos.add(key)
            programas.append(build_programa(store, r["PROGRAMA"], _to_int(r["SEMTR HOMOLOGADOS"]), _to_int(r["FALTANTES"]), cfg))
        programas.sort(key=lambda p: (-p["homologados"], p["programa_display"]))
        fuente = sub["_fuente"].iloc[0] if "_fuente" in sub.columns else "SENA"
        fdi = next((x for x in sub.get("_fdi", pd.Series(dtype=str)) if x), "")
        grupos.append({"titulo": t, "programas": programas, "fuente": fuente, "fdi": fdi})
    return {
        "query": query,
        "modo": modo,
        "grupos": grupos,
        "sugerencias": sugerencias,
        "total_programas": sum(len(g["programas"]) for g in grupos),
    }


def buscar_presencial(store, query, sede="todas"):
    rows = store.presencial()
    if sede in SEDES:
        rows = [r for r in rows if r["sede"] == sede]
    titles = sorted({r["titulo"] for r in rows}, key=norm)
    elegidos, sugerencias, modo = resolve_titles(query, titles)
    elegidos_set = set(elegidos)
    por_sede = {}
    for r in rows:
        if r["titulo"] in elegidos_set:
            por_sede.setdefault(r["sede"], []).append(r)
    resultado = []
    for key in SEDES:
        if key in por_sede:
            items = sorted(por_sede[key], key=lambda x: (-x["homologados"], x["programa"]))
            resultado.append({"sede": key, "label": SEDES[key]["label"], "icon": SEDES[key]["icon"], "items": items})
    return {"query": query, "modo": modo, "sede": sede, "sedes": resultado, "sugerencias": sugerencias,
            "titulos": elegidos, "total": sum(len(s["items"]) for s in resultado)}


def explorar_programas(store):
    """Vista inversa: por cada programa, qué títulos SENA homologan."""
    df = store.actas()
    out = []
    for prog, sub in df.groupby("PROGRAMA"):
        titulos = []
        for _, r in sub.iterrows():
            titulos.append({"titulo": r["TÉCNICO O TECNOLOGÍA"], "homologados": _to_int(r["SEMTR HOMOLOGADOS"]),
                            "faltantes": _to_int(r["FALTANTES"]), "fuente": r.get("_fuente", "SENA"),
                            "fdi": r.get("_fdi", "")})
        titulos.sort(key=lambda x: (-x["homologados"], norm(x["titulo"])))
        hs = [t["homologados"] for t in titulos] or [0]
        precio = store.match_precio(prog)
        out.append({
            "programa": prog, "display": pretty_name(prog), "titulos": titulos, "total": len(titulos),
            "max_homologados": max(hs), "min_homologados": min(hs),
            "promedio": round(sum(hs) / len(hs), 1), "precio": precio,
        })
    out.sort(key=lambda p: -p["total"])
    return out


def validar_actas(path):
    sheets = _sheet_names(path)
    sheet = ACTAS_SHEET if ACTAS_SHEET in sheets else sheets[0]
    df = clean_df(pd.read_excel(path, sheet_name=sheet))
    faltan = [c for c in ACTAS_COLUMNS if c not in df.columns]
    if faltan:
        return False, f"Faltan columnas en la hoja '{sheet}': {', '.join(faltan)}", 0
    filas = int(df.dropna(subset=["PROGRAMA"]).shape[0])
    extras = [x for x in (PRESENCIAL_SHEET, EMSUB_SHEET) if x in sheets]
    return True, f"{filas} filas virtuales" + (f" + hojas {', '.join(extras)}" if extras else ""), filas


def validar_presencial(path):
    df = clean_df(pd.read_excel(path))
    sedes = [s["titulo"] for s in SEDES.values() if s["titulo"] in df.columns]
    if not sedes:
        return False, "No se encontraron columnas de sede (Sede Bogota / Sede Pereira / Sede Valledupar)", 0
    return True, "ok", int(df.shape[0])
