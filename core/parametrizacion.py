"""Lectura del Excel de parametrización (calendario de cohortes, oferta por programa,
transferencias, prácticas y zonificación)."""
import os
import re
import threading
from datetime import date, datetime

import pandas as pd

from .text import norm, pretty_name, program_similarity

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MESES = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AGO": 8, "SEP": 9, "SET": 9,
         "OCT": 10, "NOV": 11, "DIC": 12}
MESES_LARGO = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
               "octubre", "noviembre", "diciembre"]
COHORTE_RX = re.compile(r"^\s*(\d{6})\s*-\s*([0-9][A-Z])\s*$", re.I)
FECHA_RX = re.compile(r"(\d{1,2})\s*-\s*([A-Za-zñÑ]{3})[A-Za-zñÑ]*\s*-\s*(\d{2,4})")
RANGO_LARGO_RX = re.compile(r"(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+([A-Za-zñÑ]+)\s+(?:del?\s+)?(\d{4})", re.I)


def archivo_actual():
    """El Excel de parametrización más reciente del repositorio."""
    cands = [f for f in os.listdir(BASE_DIR) if norm(f).startswith("PARAMETRIZACION") and f.lower().endswith(".xlsx")]
    if not cands:
        return None
    cands.sort(key=lambda f: (re.findall(r"20\d\d", f) or ["0"])[-1])
    return os.path.join(BASE_DIR, cands[-1])


def fecha_larga(d):
    return f"{d.day} de {MESES_LARGO[d.month]} de {d.year}" if d else ""


def fecha_corta(d):
    return f"{d.day} {MESES_LARGO[d.month][:3]}" if d else ""


def _texto(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.strftime("%d-%b-%y")
    return " ".join(str(v).split())


def _anio(y):
    y = int(y)
    return y + 2000 if y < 100 else y


def parse_rango(texto):
    """'Del 26 - oct - 26-hasta el 29 - ene -27' -> (date, date). Tolera 'Hasta el 5-mar-27'."""
    t = _texto(texto)
    if not t:
        return None, None
    m = RANGO_LARGO_RX.search(t)
    if m:
        mes = MESES.get(norm(m.group(3))[:3])
        if mes:
            y = int(m.group(4))
            return date(y, mes, int(m.group(1))), date(y, mes, int(m.group(2)))
    fechas = []
    for d, mes, y in FECHA_RX.findall(t):
        mm = MESES.get(norm(mes)[:3])
        if mm:
            try:
                fechas.append(date(_anio(y), mm, int(d)))
            except ValueError:
                pass
    if not fechas:
        return None, None
    if len(fechas) == 1:
        solo = fechas[0]
        return (None, solo) if "HASTA" in norm(t) and "DEL" not in norm(t).split()[:1] else (solo, solo)
    ini, fin = fechas[0], fechas[-1]
    if ini > fin:  # errores de digitación del año (ej. 8-mar-26 hasta 5-jul-27)
        ini = ini.replace(year=fin.year)
    return ini, fin


def _corregir_anio(coh):
    """Si el inicio de clases quedó antes del cierre de inscripciones, es un error de año en el Excel."""
    cl = coh["fechas"].get("clases")
    if not cl or not cl.get("desde"):
        return
    ini = date.fromisoformat(cl["desde"])
    cierres = [date.fromisoformat(f["hasta"]) for k, f in coh["fechas"].items() if k != "clases" and f.get("hasta")]
    while cierres and ini < max(cierres) and (ini.year + 1) <= (date.fromisoformat(cl["hasta"]).year if cl.get("hasta") else ini.year + 1):
        ini = ini.replace(year=ini.year + 1)
    cl["desde"] = ini.isoformat()


def _etiqueta(label):
    n = norm(label)
    if "INDUCCION" in n:
        return "induccion", "Semana de inducción"
    if "INICIO" in n and "CLASE" in n:
        return "clases", "Clases"
    if "SEGUNDO" in n:
        return "segundo_pos", "Graduado segundo posgrado"
    if "EXTENSION" in n and "TRAS" in n.replace("TRANS", "TRAS"):
        return "transf_extension", "Transferencia extensión"
    if "TRANSFERENCIA" in n or "TRASNFERENCIA" in n:
        return "transferencias", "Inscripción transferencias"
    if "NUEVOS" in n or "INSC" in n:
        return "inscripcion", "Inscripción nuevos"
    return n.lower().replace(" ", "_"), label.title()


def _limpio(v):
    t = _texto(v)
    return "" if t in ("", "-", "–", "NAN") else t


def _parse_bloque(raw, r_coh, c):
    """Bloque cuyo encabezado 'COHORTE' está en (r_coh, c)."""
    ncols = raw.shape[1]
    # Columnas de cohorte
    cols = []
    for j in range(c + 1, ncols):
        t = _texto(raw.iat[r_coh, j])
        if COHORTE_RX.match(t):
            cols.append((j, t.upper()))
        elif cols and not t:
            break
    if not cols:
        return None
    # Filas de fechas (encima de COHORTE, en la misma columna)
    fechas_rows = []
    titulo = ""
    r = r_coh - 1
    while r >= 0:
        lab = _texto(raw.iat[r, c])
        if not lab:
            break
        n = norm(lab)
        if n == "PROGRAMA":
            r -= 1
            continue
        if not any(_texto(raw.iat[r, j]) for j, _ in cols):
            titulo = lab
            break
        fechas_rows.append((r, lab))
        r -= 1
    fechas_rows.reverse()
    cohortes = []
    for j, code in cols:
        m = COHORTE_RX.match(code)
        coh = {"codigo": code, "periodo": m.group(1), "corto": m.group(2).upper(), "fechas": {}}
        for rr, lab in fechas_rows:
            key, nombre = _etiqueta(lab)
            ini, fin = parse_rango(raw.iat[rr, j])
            txt = _texto(raw.iat[rr, j])
            if not txt:
                continue
            coh["fechas"][key] = {"nombre": nombre, "texto": txt, "desde": ini.isoformat() if ini else None,
                                  "hasta": fin.isoformat() if fin else None}
        _corregir_anio(coh)
        if coh["fechas"].get("clases", {}).get("desde"):
            cohortes.append(coh)
    validos = {c_["codigo"] for c_ in cohortes}
    cols = [(j, code) for j, code in cols if code in validos]

    # Grupos adicionales (pregrado: SENA / transferencias) definidos en la fila PROGRAMA
    grupos_extra = []
    header_row = fechas_rows[0][0] if fechas_rows else r_coh
    for rr in range(max(0, r_coh - 2), r_coh + 1):
        if norm(_texto(raw.iat[rr, c])) == "PROGRAMA":
            for j in range(cols[-1][0] + 1 if cols else c + 1, ncols):
                t = _texto(raw.iat[rr, j])
                if COHORTE_RX.match(t):
                    k = j
                    head = ""
                    while k > c and not head:
                        head = _texto(raw.iat[header_row, k])
                        k -= 1
                    grupos_extra.append((j, t.upper(), head))
    # Banderas (columnas sin cohorte con encabezado en la fila de inscripción, ej. PRIMERA VEZ / X)
    banderas = []
    usados = {j for j, _ in cols} | {j for j, _, _ in grupos_extra}
    for j in range((cols[-1][0] + 1) if cols else c + 1, ncols):
        if j in usados:
            continue
        head = _texto(raw.iat[header_row, j])
        if head and not COHORTE_RX.match(head) and "INSC" not in norm(head) and "INICIO" not in norm(head):
            if any(_texto(raw.iat[rr, j]) for rr in range(header_row - 1, header_row)) is False or True:
                banderas.append((j, head))
        elif not head and banderas:
            break
        if len(banderas) >= 4:
            break

    programas = []
    vistos = set()
    r = r_coh + 1
    while r < raw.shape[0]:
        nombre = _texto(raw.iat[r, c])
        if not nombre or "INSC" in norm(nombre) or norm(nombre) == "COHORTE":
            break
        key = norm(nombre)
        if key in vistos:
            r += 1
            continue
        valores = {code: _limpio(raw.iat[r, j]) for j, code in cols}
        if not any(valores.values()) and not any(_limpio(raw.iat[r, j]) for j, _, _ in grupos_extra):
            # fila sin oferta: igual se lista si es parte de la tabla
            pass
        vistos.add(key)
        prog = {"nombre": nombre, "display": display_programa(nombre),
                "cohortes": {code[-2:]: v for code, v in valores.items() if v},
                "extra": {}, "admite": []}
        for j, code, head in grupos_extra:
            v = _limpio(raw.iat[r, j])
            if v:
                prog["extra"].setdefault(head, {})[code[-2:]] = v
        for j, head in banderas:
            v = _limpio(raw.iat[r, j])
            if v and norm(v) == "X":
                prog["admite"].append(head.title())
        programas.append(prog)
        r += 1
    return {"titulo": titulo, "cohortes": cohortes, "programas": programas,
            "grupos_extra": sorted({h for _, _, h in grupos_extra})}


ABREV = [(r"^ESP\.?\s*(EN\s+)?", "Especialización en "), (r"\bGER SEGURIDAD Y SALUD TRA\b", "Gerencia en Seguridad y Salud en el Trabajo"), (r"\bGER\b", "Gerencia"), (r"\bINF\b\.?", "Informática"),
         (r"\bEDU\b", "Educativa"), (r"\bTRA\b", "Trabajo"), (r"\bVIRT\b", ""), (r"\bAUT PROPIEDAD\b", "Autor, Propiedad Industrial y Nuevas Tecnologías"), (r"\bAUT\b", "Autor"),
         (r"\bAUDITORIA SALUD\b", "Auditoría en Salud"), (r"^MAESTRIA (?!EN )", "Maestría en "),
         (r"\bPROD\b", "Producción"), (r"\bGAN\b", "Ganadería"), (r"\bCIBER SEGURIDAD\b", "Ciberseguridad"),
         (r"\bINTERNA\b", "Internacionales"), (r"\bLIC\.\s*", "Licenciatura "), (r"\bTECNOL\b", "Tecnología"),
         (r"\bHUM\b", "Humano"), (r"\bTRABJO\b", "Trabajo"), (r"\bSO\b", "Sostenible"), (r"\bGANAD\b", "Ganadería")]


def display_programa(nombre):
    return _display_base(nombre)


def _display_base(nombre):
    n = " ".join(str(nombre).split())
    for rx, rep in ABREV:
        n = re.sub(rx, rep, n, flags=re.I)
    n = re.sub(r"\s*-\s*VIRT(UAL)?\s*$", "", n, flags=re.I)
    n = re.sub(r"\s+VIRTUAL\s*$", "", n, flags=re.I)
    n = n.replace("Especialización en EN ", "Especialización en ")
    return pretty_name(n.strip())


def _buscar_hoja(xl, *patrones):
    for p in patrones:
        rx = re.compile(p, re.I)
        hojas = [s for s in xl.sheet_names if rx.search(norm(s))]
        if hojas:
            hojas.sort(key=lambda s: re.findall(r"\d{4}", s) or ["0"])
            return hojas[-1]
    return None


def _bloques(raw):
    out = []
    for r in range(raw.shape[0]):
        for c in range(raw.shape[1]):
            if norm(_texto(raw.iat[r, c])) == "COHORTE":
                b = _parse_bloque(raw, r, c)
                if b and b["cohortes"]:
                    out.append(b)
    return out


def parse_excel(path):
    xl = pd.ExcelFile(path)
    data = {"archivo": os.path.basename(path), "generado": datetime.now().isoformat(timespec="seconds")}

    hoja = _buscar_hoja(xl, r"^PREGRADO 20\d\d 10$", r"^PREGRADO 20\d\d")
    if hoja:
        bl = _bloques(pd.read_excel(path, sheet_name=hoja, header=None))
        if bl:
            data["pregrado"] = {"hoja": hoja, **bl[0]}

    hoja = _buscar_hoja(xl, r"^POSGRADO 20\d\d 30$", r"^POSGRADOS? 20\d\d")
    if hoja:
        bl = _bloques(pd.read_excel(path, sheet_name=hoja, header=None))
        esp = [b for b in bl if not any(norm(p["nombre"]).startswith("MAESTRIA") for p in b["programas"])]
        mae = [b for b in bl if any(norm(p["nombre"]).startswith("MAESTRIA") for p in b["programas"])]
        data["posgrado"] = {"hoja": hoja, "especializaciones": esp[0] if esp else None, "maestrias": mae[0] if mae else None}

    hoja = _buscar_hoja(xl, r"^TRANSFERENCIAS Y SEGUNDO POS")
    if hoja:
        bl = _bloques(pd.read_excel(path, sheet_name=hoja, header=None))
        data["transferencias_posgrado"] = {"hoja": hoja, "bloques": bl}

    hoja = _buscar_hoja(xl, r"PRACTICAS")
    if hoja:
        raw = pd.read_excel(path, sheet_name=hoja, header=None)
        filas = []
        for r in range(raw.shape[0]):
            vals = [_texto(v) for v in raw.iloc[r].tolist()]
            vals = [v for v in vals if v]
            if len(vals) >= 3 and norm(vals[0]) != "PROGRAMA":
                filas.append({"programa": display_programa(vals[0]), "practicas": vals[1], "opcion_grado": vals[2]})
        data["practicas"] = filas

    hoja = _buscar_hoja(xl, r"ZONIFICACION")
    if hoja:
        raw = pd.read_excel(path, sheet_name=hoja, header=None)
        zonas = []
        for r in range(raw.shape[0]):
            vals = [_texto(v) for v in raw.iloc[r].tolist()]
            vals = [v for v in vals if v]
            if len(vals) >= 4 and norm(vals[0]) != "CIUDAD RESIDENCIA":
                zonas.append({"ciudad": vals[0].title(), "departamento": vals[1].title(), "pais": vals[2].title(), "zona": vals[3].upper()})
        data["zonificacion"] = zonas
    return data


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
class Parametrizacion:
    def __init__(self):
        self._lock = threading.RLock()
        self._cache = (None, None, None)

    def data(self):
        path = archivo_actual()
        if not path:
            return {}
        mtime = os.path.getmtime(path)
        with self._lock:
            if self._cache[0] == path and self._cache[1] == mtime:
                return self._cache[2]
            try:
                d = parse_excel(path)
            except Exception as e:  # archivo dañado: no tumbar la app
                print("Error leyendo parametrización:", e)
                d = {}
            self._cache = (path, mtime, d)
            return d

    def invalidate(self):
        with self._lock:
            self._cache = (None, None, None)

    # Bloques ---------------------------------------------------------------
    def bloques(self):
        d = self.data()
        out = []
        if d.get("pregrado"):
            out.append(("pregrado", d["pregrado"]))
        pos = d.get("posgrado") or {}
        for k in ("especializaciones", "maestrias"):
            if pos.get(k):
                out.append((k, pos[k]))
        return out

    def _match(self, programa, nivel):
        """Programa del bloque que mejor coincide con `programa`."""
        cands = []
        for tipo, b in self.bloques():
            if nivel == "pregrado" and tipo != "pregrado":
                continue
            if nivel == "posgrado" and tipo == "pregrado":
                continue
            for p in b["programas"]:
                sc = max(program_similarity(programa, p["nombre"]), program_similarity(programa, p["display"]))
                cands.append((sc, p, b))
        if not cands:
            return None, None
        sc, p, b = max(cands, key=lambda x: x[0])
        return (p, b) if sc >= 0.66 else (None, None)

    def cohortes_programa(self, programa, nivel="pregrado", modalidad="regular"):
        """Lista de cohortes (dicts) en que se oferta el programa para la modalidad dada."""
        p, b = self._match(programa, nivel)
        if not p:
            return []
        if modalidad == "regular":
            letras = set(p["cohortes"])
        else:
            grupo = next((g for g in p["extra"] if modalidad.upper() in norm(g)), None)
            letras = set(p["extra"].get(grupo, {})) if grupo else set()
        return [c for c in b["cohortes"] if c["corto"] in letras]

    def inicio_programa(self, programa, nivel="pregrado", modalidad="regular", hoy=None):
        """Próximo inicio de clases con inscripciones aún abiertas (o el primero si todas cerraron)."""
        c = self.proxima_cohorte(self.cohortes_programa(programa, nivel, modalidad), hoy)
        return date.fromisoformat(c["fechas"]["clases"]["desde"]) if c else None

    @staticmethod
    def proxima_cohorte(cohortes, hoy=None):
        hoy = hoy or date.today()
        ordenadas = sorted(cohortes, key=lambda c: c["fechas"]["clases"]["desde"])
        for c in ordenadas:
            cierre = (c["fechas"].get("inscripcion") or {}).get("hasta") or c["fechas"]["clases"]["desde"]
            if date.fromisoformat(cierre) >= hoy:
                return c
        return ordenadas[0] if ordenadas else None

    def hitos(self, hoy=None, limite=6):
        """Próximos eventos del calendario (cierres de inscripción, inducciones e inicios de clase)."""
        hoy = hoy or date.today()
        eventos = []
        nombres = {"pregrado": "Pregrado", "especializaciones": "Especializaciones", "maestrias": "Maestrías"}
        for tipo, b in self.bloques():
            for c in b["cohortes"]:
                f = c["fechas"]
                for key, campo, titulo, icono in (("inscripcion", "hasta", "Cierre de inscripciones", "fa-user-plus"),
                                                   ("induccion", "desde", "Inducción", "fa-chalkboard-user"),
                                                   ("clases", "desde", "Inicio de clases", "fa-graduation-cap")):
                    v = (f.get(key) or {}).get(campo)
                    if v and date.fromisoformat(v) >= hoy:
                        d = date.fromisoformat(v)
                        eventos.append({"fecha": v, "larga": fecha_larga(d), "corta": fecha_corta(d), "dias": (d - hoy).days,
                                        "titulo": titulo, "icono": icono, "grupo": nombres[tipo], "cohorte": c["corto"], "tipo": tipo})
        eventos.sort(key=lambda e: (e["fecha"], e["tipo"]))
        return eventos[:limite]

    def primer_inicio(self, tipo):
        """Primer inicio de clases del bloque ('pregrado', 'especializaciones', 'maestrias', 'posgrado')."""
        fechas = []
        for t, b in self.bloques():
            if t == tipo or (tipo == "posgrado" and t != "pregrado"):
                fechas += [date.fromisoformat(c["fechas"]["clases"]["desde"]) for c in b["cohortes"]]
        return min(fechas) if fechas else None

    def zona(self, ciudad):
        n = norm(ciudad)
        for z in self.data().get("zonificacion", []):
            if norm(z["ciudad"]) == n:
                return z
        return None


def estado(fecha_desde, fecha_hasta, hoy=None):
    """'proxima' | 'abierta' | 'cerrada' según hoy."""
    hoy = hoy or date.today()
    d = date.fromisoformat(fecha_desde) if fecha_desde else None
    h = date.fromisoformat(fecha_hasta) if fecha_hasta else None
    if h and hoy > h:
        return "cerrada"
    if d and hoy < d:
        return "proxima"
    return "abierta"
