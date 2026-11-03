"""Cruce GEN NACIONAL (sede Galán) vs FUNNEL por cédula, con caché por archivo."""
import io
import os
import threading
from datetime import datetime, timedelta

import pandas as pd

from .text import clean_df

GOOGLE_SHEET_ID = os.environ.get("GEN_SHEET_ID", "1550YdTkr9XXykOv78RL_V8xLVE6QuJXDemdxneLjO2M")
FUNNEL_SHEET_ID = os.environ.get("FUNNEL_SHEET_ID", "1Dd1ByYaOO-s9Vv1kweORctolPc070g_yBY4M_57YWzQ")
GOOGLE_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=xlsx"
FUNNEL_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{FUNNEL_SHEET_ID}/export?format=xlsx"
GOOGLE_SHEET_EDIT = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit?gid=1957374122"
FUNNEL_SHEET_EDIT = f"https://docs.google.com/spreadsheets/d/{FUNNEL_SHEET_ID}/edit?gid=0"

CEDULA_COLS = ["CEDULA", "CÉDULA", "DOCUMENTO", "No. DOCUMENTO", "DOCUMENTO DE IDENTIDAD", "NUMERO DE DOCUMENTO", "ID"]
UA = {"User-Agent": "Mozilla/5.0 (HomologacionesAreandina)"}


def clean_cedula(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2]
    for ch in ".,- ":
        s = s.replace(ch, "")
    return s


class Cruce:
    def __init__(self, data_dir):
        self.dir = os.path.join(data_dir, "cruce")
        self.gen_file = os.path.join(self.dir, "cruce_actual.xlsx")
        self.funnel_file = os.path.join(self.dir, "funnel_actual.xlsx")
        self._lock = threading.RLock()
        self._gen = (None, None)
        self._funnel = (None, None)

    # ---------- estado ----------
    @staticmethod
    def _mtime(path):
        try:
            return os.path.getmtime(path)
        except OSError:
            return None

    def status(self):
        def fmt(p):
            m = self._mtime(p)
            return datetime.fromtimestamp(m).strftime("%d/%m/%Y %I:%M %p") if m else ""
        tiene_gen = os.path.exists(self.gen_file)
        tiene_funnel = os.path.exists(self.funnel_file)
        return {
            "tiene_archivo": tiene_gen,
            "tiene_funnel": tiene_funnel,
            "cedulas_funnel_total": len(self.funnel_cedulas()) if tiene_funnel else 0,
            "ultima_actualizacion": fmt(self.gen_file),
            "ultima_funnel": fmt(self.funnel_file),
            "google_sheet_url": GOOGLE_SHEET_EDIT,
            "funnel_sheet_url": FUNNEL_SHEET_EDIT,
        }

    # ---------- lectura con caché ----------
    def funnel_cedulas(self):
        m = self._mtime(self.funnel_file)
        if m is None:
            return set()
        with self._lock:
            if self._funnel[0] == m:
                return self._funnel[1]
            ceds = self._read_funnel()
            self._funnel = (m, ceds)
            return ceds

    def _read_funnel(self):
        try:
            xl = pd.ExcelFile(self.funnel_file)
            sheet = next((s for s in xl.sheet_names if s.strip().upper() == "FUNNEL"), xl.sheet_names[0])
            df = pd.read_excel(self.funnel_file, sheet_name=sheet)
            col = None
            # Columna R (índice 17) es la cédula en la hoja FUNNEL oficial
            if len(df.columns) > 17:
                col = df.columns[17]
            else:
                for c in df.columns:
                    cu = str(c).strip().upper()
                    if any(k in cu for k in ("CEDULA", "CÉDULA", "DOCUMENTO", "IDENTIFICACION")):
                        col = c
                        break
            if col is None:
                return set()
            ceds = df[col].dropna().apply(clean_cedula)
            return {c for c in ceds if c and any(ch.isdigit() for ch in c)}
        except Exception as e:  # archivo corrupto o formato inesperado
            print("Error leyendo FUNNEL:", e)
            return set()

    def gen_df(self):
        m = self._mtime(self.gen_file)
        if m is None:
            return None
        with self._lock:
            if self._gen[0] == m:
                return self._gen[1]
            df = clean_df(pd.read_excel(self.gen_file, sheet_name="GEN NACIONAL"))
            for c in ("CSU", "SEDE"):
                if c in df.columns:
                    df = df[df[c].astype(str).str.lower().str.contains(r"gal[aá�]?n", regex=True, na=False)]
                    break
            for c in ("FECHA DE CARGUE", "FECHA DE GESTION"):
                if c in df.columns:
                    df[c] = pd.to_datetime(df[c], errors="coerce")
            df = df.reset_index(drop=True)
            txt = df.astype(object).where(pd.notna(df), "").astype(str)
            df["_search"] = txt.apply(lambda r: " ".join(r.values), axis=1).str.upper()
            self._gen = (m, df)
            return df

    def cedula_col(self, df):
        return next((c for c in CEDULA_COLS if c in df.columns), None)

    # ---------- consulta ----------
    def query(self, fecha_cargue="", rango="todas", radar="todos", q="", desde="", hasta=""):
        base = self.gen_df()
        if base is None:
            return None
        df = base.copy()
        ceds = self.funnel_cedulas()
        col_ced = self.cedula_col(df)
        if col_ced and ceds:
            df["_en_funnel"] = df[col_ced].apply(lambda x: clean_cedula(x) in ceds)
        else:
            df["_en_funnel"] = False

        fechas = []
        if "FECHA DE CARGUE" in df.columns:
            fc = df["FECHA DE CARGUE"]
            fechas = [{"iso": d.strftime("%Y-%m-%d"), "label": d.strftime("%d/%m/%Y")}
                      for d in sorted(fc.dropna().dt.date.unique(), reverse=True)]
            today = datetime.now().date()
            dates = fc.dt.date
            if fecha_cargue:
                try:
                    df = df[dates == pd.to_datetime(fecha_cargue).date()]
                except (ValueError, TypeError):
                    pass
            elif desde or hasta:
                try:
                    if desde:
                        df = df[dates >= pd.to_datetime(desde).date()]
                        dates = df["FECHA DE CARGUE"].dt.date
                    if hasta:
                        df = df[dates <= pd.to_datetime(hasta).date()]
                except (ValueError, TypeError):
                    pass
            elif rango == "hoy":
                df = df[dates == today]
            elif rango == "ayer":
                df = df[dates == today - timedelta(days=1)]
            elif rango == "esta_semana":
                ini = today - timedelta(days=today.weekday())
                df = df[(dates >= ini) & (dates <= ini + timedelta(days=6))]
            elif rango == "ultimos_7":
                df = df[(dates >= today - timedelta(days=7)) & (dates <= today)]
            elif rango == "este_mes":
                df = df[(fc.dt.year == today.year) & (fc.dt.month == today.month)]

        if radar == "en_radar":
            df = df[df["_en_funnel"]]
        elif radar == "sin_radar":
            df = df[~df["_en_funnel"]]

        if q:
            df = df[df["_search"].str.contains(q.strip().upper(), regex=False, na=False)]

        resumen = {}
        for c in ("ESTADO", "OBSERVACION", "NOMBRE DE PROGRAMA", "RESPONSABLE"):
            col = next((x for x in df.columns if c in str(x).upper() and not str(x).startswith("_")), None)
            if col:
                vc = df[col].fillna("(vacío)").astype(str).str.strip().replace("", "(vacío)").value_counts().head(8)
                resumen[col] = [[k, int(v)] for k, v in vc.items()]

        out = df.drop(columns=["_search"]).copy()
        for c in out.columns:
            if pd.api.types.is_datetime64_any_dtype(out[c]):
                out[c] = out[c].dt.strftime("%d/%m/%Y").fillna("")
        out = out.astype(object).where(pd.notna(out), "")
        return {
            "df": out,
            "rows": out.to_dict(orient="records"),
            "total": int(len(out)),
            "total_en_funnel": int(out["_en_funnel"].sum()) if len(out) else 0,
            "total_cedulas_funnel": len(ceds),
            "columns": [c for c in out.columns if not str(c).startswith("_")],
            "fechas_disponibles": fechas,
            "resumen": resumen,
        }

    def to_excel(self, result):
        df = result["df"].copy()
        df.insert(0, "EN_RADAR_FUNNEL", df["_en_funnel"].map(lambda v: "SI" if v else "NO"))
        df = df[[c for c in df.columns if not str(c).startswith("_")]]
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xw:
            df.to_excel(xw, index=False, sheet_name="Cruce Galán")
            ws = xw.sheets["Cruce Galán"]
            for i, col in enumerate(df.columns, start=1):
                width = min(max(len(str(col)), *(len(str(v)) for v in df[col].head(200))) + 2, 45) if len(df) else len(str(col)) + 2
                ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width
            ws.freeze_panes = "B2"
        buf.seek(0)
        return buf

    # ---------- sincronización ----------
    def _download(self, url, dest, min_size):
        import requests
        try:
            r = requests.get(url, headers=UA, timeout=40, allow_redirects=True)
        except Exception as e:
            return False, f"Error de conexión con Google Sheets: {e}"
        head = r.content[:200].lstrip().lower()
        is_html = head.startswith(b"<!doctype") or head.startswith(b"<html")
        if r.status_code == 200 and not is_html and len(r.content) > min_size:
            os.makedirs(self.dir, exist_ok=True)
            tmp = dest + ".tmp"
            with open(tmp, "wb") as f:
                f.write(r.content)
            os.replace(tmp, dest)
            return True, ""
        if r.status_code in (401, 403) or "accounts.google.com" in r.url or is_html:
            return False, ("El Google Sheet está en modo privado. Abre el Sheet > Compartir > "
                           "'Cualquier persona con el enlace' (Lector).")
        return False, f"Respuesta inesperada de Google (HTTP {r.status_code})."

    def sync_gen(self):
        ok, msg = self._download(GOOGLE_SHEET_URL, self.gen_file, 15000)
        if not ok:
            return False, msg
        try:
            df = self.gen_df()
            return True, f"¡Sincronización exitosa! {len(df):,} registros de la sede Galán en GEN NACIONAL."
        except Exception as e:
            return False, f"El archivo se descargó pero no se pudo leer la hoja GEN NACIONAL: {e}"

    def sync_funnel(self):
        ok, msg = self._download(FUNNEL_SHEET_URL, self.funnel_file, 10000)
        if not ok:
            return False, msg
        return True, f"¡FUNNEL sincronizado! {len(self.funnel_cedulas()):,} cédulas encontradas."

    def save_upload(self, file, kind):
        os.makedirs(self.dir, exist_ok=True)
        dest = self.gen_file if kind == "gen" else self.funnel_file
        file.save(dest)

    def delete(self, kind):
        dest = self.gen_file if kind == "gen" else self.funnel_file
        if os.path.exists(dest):
            os.remove(dest)
