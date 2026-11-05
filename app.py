"""Homologaciones SENA · Areandina — aplicación Flask.

Herramienta interna para asesores comerciales: consulta de homologaciones SENA
(virtual y presencial), mensajes listos para WhatsApp, precios, simulador de
inversión, cruce GEN NACIONAL vs FUNNEL, piezas gráficas y panel administrativo.
"""
import os
import re
import shutil
from datetime import datetime, timedelta
from functools import wraps

import pandas as pd
from flask import (Flask, Response, abort, jsonify, redirect, render_template, request,
                   send_file, send_from_directory, session, url_for)
from werkzeug.utils import secure_filename

from core.activity import ActivityLog
from core.assistant import answer as assistant_answer, claude_available
from core.cruce import Cruce
from core.data import (ACTAS_FILE, DATA_DIR, DEFAULT_CONFIG, PRESENCIAL_FILE, SEDES, DataStore,
                       buscar_homologacion, buscar_presencial, explorar_programas, rank_titles,
                       sanitize_workbook, validar_actas, validar_presencial)
from core.pensum import PENSUM_DIRS, buscar_pensum, listar as listar_pensum
from core.messages import mensaje_homologacion, mensaje_oferta, mensaje_precios, mensaje_presencial
from core.security import LoginLimiter, check_password, init_csrf
from core.text import clean_df, fix_text_enc, money, norm, pretty_name  # noqa: F401 (re-export)
from whatsapp import whatsapp_bp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_VERSION = "3.1"

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "homologaciones-aguachica-2026")
app.config.update(
    MAX_CONTENT_LENGTH=32 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=int(os.environ.get("SESSION_HOURS", "12"))),
    JSON_AS_ASCII=False,
)
app.json.ensure_ascii = False

# Credenciales (se pueden sobreescribir con variables de entorno)
GLOBAL_USER = os.environ.get("APP_USER", "Innovacion")
GLOBAL_PASSWORD = os.environ.get("APP_PASSWORD", "0228")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Jorsh123")
AGUACHICA_USER = os.environ.get("AGUACHICA_USER", "csu-aguachica")
AGUACHICA_PASSWORD = os.environ.get("AGUACHICA_PASSWORD", "1234")
AGUACHICA_CLAVE_BORRADO = os.environ.get("AGUACHICA_CLAVE_BORRADO", "2907")

STATIC_DIR = os.path.join(BASE_DIR, "static")
BROCHURES_DIR = os.path.join(STATIC_DIR, "brochures")
PIEZAS_DIR = os.path.join(STATIC_DIR, "piezas")
AGUACHICA_FILE = os.path.join(BASE_DIR, "aguachica.xlsx")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_PDF_EXTENSIONS = {"pdf"}

# Versión de los archivos estáticos: cambia con cada despliegue para que el navegador no use una copia vieja
ASSET_VERSION = str(int(max(os.path.getmtime(os.path.join(STATIC_DIR, f)) for f in ("css/app.css", "js/app.js"))))

store = DataStore()
activity = ActivityLog(os.path.join(DATA_DIR, "actividad.json"))
cruce_data = Cruce(DATA_DIR)
limiter = LoginLimiter()

app.extensions["homologaciones_store"] = store
init_csrf(app)
app.register_blueprint(whatsapp_bp)


# =====================================================
# HELPERS
# =====================================================
def allowed_file(filename, allowed):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def safe_join(base, *parts):
    """Une rutas evitando salir de `base` (protección path traversal)."""
    path = os.path.abspath(os.path.join(base, *parts))
    base_abs = os.path.abspath(base)
    if os.path.commonpath([path, base_abs]) != base_abs:
        return None
    return path


def listed_name(directory, name):
    """Devuelve `name` solo si existe literalmente en `directory` (soporta tildes/ñ)."""
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        return None
    try:
        return name if name in os.listdir(directory) else None
    except OSError:
        return None


def breadcrumb_for(subfolder):
    crumbs = []
    if subfolder:
        parts = [p for p in subfolder.replace("\\", "/").split("/") if p]
        for i, part in enumerate(parts):
            crumbs.append({"name": part, "path": "/".join(parts[: i + 1])})
    return crumbs


def list_folder(folder):
    items = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
    carpetas = [d for d in items if os.path.isdir(os.path.join(folder, d))]
    imagenes = [f for f in items if os.path.isfile(os.path.join(folder, f)) and allowed_file(f, ALLOWED_IMAGE_EXTENSIONS)]
    return carpetas, imagenes


def count_images(folder):
    total = 0
    for _, _, files in os.walk(folder):
        total += sum(1 for f in files if allowed_file(f, ALLOWED_IMAGE_EXTENSIONS))
    return total


def folder_cover(folder):
    for root, _, files in os.walk(folder):
        for f in sorted(files):
            if allowed_file(f, ALLOWED_IMAGE_EXTENSIONS):
                return os.path.relpath(os.path.join(root, f), STATIC_DIR).replace("\\", "/")
    return None


def file_info(path):
    try:
        st = os.stat(path)
        return {"size": st.st_size, "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M")}
    except OSError:
        return {"size": 0, "mtime": ""}


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


app.jinja_env.filters["money"] = money
app.jinja_env.filters["pretty"] = pretty_name
app.jinja_env.filters["human_size"] = human_size


def _fecha_larga_filter(v):
    from core.parametrizacion import fecha_larga
    from datetime import date as _d
    try:
        return fecha_larga(_d.fromisoformat(str(v)))
    except ValueError:
        return v


app.jinja_env.filters["fecha_larga"] = _fecha_larga_filter


# =====================================================
# AUTENTICACIÓN
# =====================================================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "Sesión expirada"}), 401
            return redirect(url_for("global_login", next=request.full_path if request.query_string else request.path))
        return f(*args, **kwargs)
    return wrapper


def admin_only(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect("/admin")
        return f(*args, **kwargs)
    return wrapper


def admin_required():
    """Compatibilidad: devuelve redirect si no es admin."""
    if not session.get("admin"):
        return redirect("/admin")
    return None


@app.route("/login", methods=["GET", "POST"])
def global_login():
    error = None
    wait = limiter.blocked("global")
    if request.method == "POST":
        if wait:
            error = f"Demasiados intentos. Espera {wait} segundos."
        elif request.form.get("user", "").strip() == GLOBAL_USER and check_password(request.form.get("password", ""), GLOBAL_PASSWORD):
            limiter.reset("global")
            session.clear()
            session.permanent = request.form.get("remember") == "on"
            session["logged_in"] = True
            session["login_at"] = datetime.now().isoformat(timespec="seconds")
            nxt = request.args.get("next", "/")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else "/")
        else:
            limiter.fail("global")
            error = "Usuario o contraseña incorrectos"
    return render_template("global_login.html", error=error)


@app.route("/logout")
def global_logout():
    session.clear()
    return redirect("/login")


# =====================================================
# CONTEXTO GLOBAL DE PLANTILLAS
# =====================================================
NAV = [
    ("Principal", [
        ("/dashboard", "fa-gauge-high", "Panel"),
        ("/", "fa-building-columns", "Homologaciones"),
        ("/presencial", "fa-school", "Presencial"),
        ("/programas", "fa-diagram-project", "Explorar programas"),
    ]),
    ("Comercial", [
        ("/mensajes", "fa-comments", "Mensajes"),
        ("/precios", "fa-tags", "Precios"),
        ("/simulador", "fa-calculator", "Simulador"),
        ("/whatsapp", "fa-brands fa-whatsapp", "Envío WhatsApp"),
    ]),
    ("Recursos", [
        ("/piezas", "fa-images", "Piezas gráficas"),
        ("/brochures", "fa-file-pdf", "Brochures y pensum"),
        ("/parametrizacion", "fa-calendar-days", "Parametrización"),
        ("/flujos", "fa-headset", "Flujo de llamada"),
        ("/capacitacion", "fa-user-graduate", "Capacitación e IA"),
    ]),
    ("Gestión", [
        ("/cruce", "fa-shuffle", "Cruce de datos"),
        ("/aguachica", "fa-chart-line", "Aguachica"),
    ]),
]

# Módulos que se pueden ocultar desde Administración → Configuración
MODULOS = {
    "simulador": {"label": "Simulador", "prefixes": ("/simulador", "/api/oferta")},
    "whatsapp": {"label": "Envío WhatsApp", "prefixes": ("/whatsapp",)},
    "cruce": {"label": "Cruce de datos", "prefixes": ("/cruce", "/api/cruce")},
    "aguachica": {"label": "Aguachica", "prefixes": ("/aguachica",)},
}
NAV_MODULO = {"/simulador": "simulador", "/whatsapp": "whatsapp", "/cruce": "cruce", "/aguachica": "aguachica"}

TITLES = {item[0]: item[2] for _, items in NAV for item in items}
TITLES.update({"/sena": "Mensajes SENA", "/admin": "Administración"})


def modulos_ocultos():
    return set(store.config.get("modulos_ocultos") or [])


def mod_on(key):
    return key not in modulos_ocultos()


def nav_visible():
    ocultos = modulos_ocultos()
    out = []
    for section, items in NAV:
        vis = [it for it in items if NAV_MODULO.get(it[0]) not in ocultos]
        if vis:
            out.append((section, vis))
    return out


@app.before_request
def bloquear_modulos_ocultos():
    """Los módulos ocultos no están disponibles para asesores (el admin sí puede entrar)."""
    if session.get("admin"):
        return
    for key in modulos_ocultos():
        mod = MODULOS.get(key)
        if mod and any(request.path == p or request.path.startswith(p + "/") or request.path.startswith(p + "?") for p in mod["prefixes"]):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "Módulo no disponible"}), 404
            return redirect("/")


def page_title():
    p = request.path
    if p in TITLES:
        return TITLES[p]
    for prefix in ("/piezas", "/admin", "/aguachica", "/brochures"):
        if p.startswith(prefix):
            return TITLES.get(prefix, "Areandina")
    return "Areandina"


def nav_active(href):
    p = request.path
    if href == "/":
        return p == "/"
    return p == href or p.startswith(href + "/")


@app.context_processor
def inject_globals():
    return {
        "NAV": nav_visible(),
        "mod_on": mod_on,
        "nav_active": nav_active,
        "page_title": page_title,
        "cfg": store.config,
        "is_admin": bool(session.get("admin")),
        "app_version": APP_VERSION,
        "asset_v": ASSET_VERSION,
        "now": datetime.now(),
    }


# =====================================================
# ESTÁTICOS Y UTILIDADES
# =====================================================
@app.route("/logo.jpg")
def logo():
    return send_from_directory(BASE_DIR, "logo.jpg")


@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(STATIC_DIR, "manifest.webmanifest", mimetype="application/manifest+json")


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "version": APP_VERSION, "titulos": len(store.titulos())})


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "No encontrado"}), 404
    return render_template("error.html", code=404, title="Página no encontrada",
                           message="La página que buscas no existe o fue movida."), 404


@app.errorhandler(400)
def bad_request(e):
    msg = getattr(e, "description", "Solicitud inválida")
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({"ok": False, "error": msg}), 400
    return render_template("error.html", code=400, title="Solicitud inválida", message=msg), 400


@app.errorhandler(413)
def too_large(e):
    return render_template("error.html", code=413, title="Archivo demasiado grande",
                           message="El archivo supera el límite de 32 MB."), 413


@app.errorhandler(500)
def server_error(e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Error interno del servidor"}), 500
    return render_template("error.html", code=500, title="Algo salió mal",
                           message="Ocurrió un error inesperado. Intenta de nuevo."), 500


# =====================================================
# HOMOLOGACIONES (VIRTUAL)
# =====================================================
def generar_mensaje(titulo_input):
    """Compatibilidad con la versión anterior: devuelve solo el texto."""
    return mensaje_homologacion(buscar_homologacion(store, titulo_input or ""), store.config)


@app.route("/", methods=["GET", "POST"])
@login_required
def homologaciones():
    if request.method == "POST":
        return redirect(url_for("homologaciones", q=request.form.get("titulo", "")))
    return render_template("homologaciones.html", titulos=store.titulos(), q=request.args.get("q", ""))


@app.route("/api/homologar")
@login_required
def api_homologar():
    q = request.args.get("q", "").strip()
    nombre = request.args.get("nombre", "").strip()[:60]
    incluir_precios = request.args.get("precios") == "1"
    if not q:
        return jsonify({"ok": False, "error": "Escribe un título SENA"}), 400
    res = buscar_homologacion(store, q)
    cfg = store.config
    programas = [p for g in res["grupos"] for p in g["programas"]]
    res["mensaje"] = mensaje_homologacion(res, cfg, nombre=nombre, incluir_precios=incluir_precios)
    res["mensaje_precios"] = mensaje_precios(programas, cfg)
    res["ok"] = True
    if request.args.get("log", "1") == "1":
        activity.log("busqueda", res["grupos"][0]["titulo"] if len(res["grupos"]) == 1 else q, res["total_programas"])
    return jsonify(res)


@app.route("/api/titulos")
@login_required
def api_titulos():
    q = request.args.get("q", "").strip()
    titulos = store.titulos()
    if q:
        return jsonify({"ok": True, "items": rank_titles(q, titulos, limit=int(request.args.get("limit", 12)), threshold=0.55)})
    return jsonify({"ok": True, "items": titulos, "presencial": store.titulos_presencial()})


@app.route("/api/track", methods=["POST"])
@login_required
def api_track():
    data = request.get_json(silent=True) or {}
    tipo = str(data.get("tipo", ""))[:30]
    if tipo in ("copia", "whatsapp", "oferta", "simulacion"):
        activity.log(tipo, str(data.get("query", ""))[:200], 1)
    return jsonify({"ok": True})


# =====================================================
# PRESENCIAL
# =====================================================
def generar_mensaje_presencial(titulo_input, sede):
    """Compatibilidad: devuelve solo el texto."""
    sede = (sede or "").lower()
    if sede not in SEDES and sede != "todas":
        return "Sede no válida."
    return mensaje_presencial(buscar_presencial(store, titulo_input or "", sede), store.config)


@app.route("/presencial", methods=["GET", "POST"])
@login_required
def presencial_route():
    if request.method == "POST":
        return redirect(url_for("presencial_route", q=request.form.get("titulo", ""), sede=request.form.get("sede", "todas")))
    return render_template("presencial.html", titulos=store.titulos_presencial(), sedes=SEDES,
                           q=request.args.get("q", ""), sede=request.args.get("sede", "todas"))


@app.route("/api/presencial")
@login_required
def api_presencial():
    q = request.args.get("q", "").strip()
    sede = request.args.get("sede", "todas").lower()
    if not q:
        return jsonify({"ok": False, "error": "Escribe un título"}), 400
    if sede not in SEDES:
        sede = "todas"
    res = buscar_presencial(store, q, sede)
    res["mensaje"] = mensaje_presencial(res, store.config, nombre=request.args.get("nombre", "").strip()[:60])
    res["ok"] = True
    activity.log("busqueda_presencial", res["titulos"][0] if len(res["titulos"]) == 1 else q, res["total"])
    return jsonify(res)


# =====================================================
# EXPLORAR PROGRAMAS (BÚSQUEDA INVERSA)
# =====================================================
@app.route("/programas")
@login_required
def programas():
    return render_template("programas.html", programas=explorar_programas(store))


# =====================================================
# MENSAJES
# =====================================================
@app.route("/mensajes")
@login_required
def mensajes():
    nivel = request.args.get("nivel", "pre")
    if nivel not in ("pre", "pos", "sena", "fav"):
        nivel = "pre"
    return render_template("mensajes.html", programas=store.render_list(store.mensajes_programas()),
                           sena=store.render_list(store.mensajes_sena(), "sena"),
                           nivel=nivel, q=request.args.get("q", ""))


@app.route("/sena")
@login_required
def sena():
    return redirect(url_for("mensajes", nivel="sena", q=request.args.get("q", "")))


# =====================================================
# PRECIOS Y SIMULADOR
# =====================================================
@app.route("/precios")
@login_required
def precios():
    progs = [{**p, "inicio": store.inicio_de(p["programa"], "pre")} for p in store.precios()]
    return render_template("precios.html", programas=progs)


@app.route("/simulador")
@login_required
def simulador():
    progs = explorar_programas(store)
    mapa = {}
    for p in progs:
        if p["precio"]:
            mapa[p["precio"]["id"]] = [{"titulo": t["titulo"], "homologados": t["homologados"], "faltantes": t["faltantes"]}
                                       for t in p["titulos"]]
    return render_template("simulador.html", precios=store.precios(), homologaciones=mapa,
                           programa_id=request.args.get("programa", type=int), titulo=request.args.get("titulo", ""))


@app.route("/api/oferta", methods=["POST"])
@login_required
def api_oferta():
    data = request.get_json(silent=True) or {}
    try:
        valor = int(data.get("valor", 0))
        descuento = max(0, min(100, int(data.get("descuento", 0))))
        semestres = int(data.get("semestres") or 0) or None
        homologados = int(data.get("homologados") or 0)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Datos inválidos"}), 400
    texto = mensaje_oferta(str(data.get("programa", ""))[:120], valor, descuento, store.config, semestres, homologados)
    return jsonify({"ok": True, "mensaje": texto})


# =====================================================
# PANEL / ESTADÍSTICAS
# =====================================================
@app.route("/dashboard")
@login_required
def dashboard():
    precios_data = store.precios()
    valores = [p["valor"] for p in precios_data] or [0]
    progs = explorar_programas(store)
    df = store.actas()
    dist = df["SEMTR HOMOLOGADOS"].fillna(0).astype(int).value_counts().sort_index()
    mensajes_programas = store.mensajes_programas()
    stats = {
        "total_titulos": len(store.titulos()),
        "total_combinaciones": int(len(df)),
        "total_programas_actas": len(progs),
        "total_pregrado": len([m for m in mensajes_programas if m.get("nivel") == "pre"]),
        "total_posgrado": len([m for m in mensajes_programas if m.get("nivel") == "pos"]),
        "total_mensajes_sena": len(store.mensajes_sena()),
        "total_precios": len(precios_data),
        "precio_min": min(valores),
        "precio_max": max(valores),
        "precio_promedio": int(sum(valores) / len(valores)),
        "presencial_titulos": len(store.titulos_presencial()),
        "piezas": count_images(PIEZAS_DIR),
        "max_homologados": int(df["SEMTR HOMOLOGADOS"].max()) if len(df) else 0,
        "pensum_pre": len(listar_pensum("pregrado")),
        "pensum_pos": len(listar_pensum("posgrado")),
    }
    chart = {
        "programas": [p["display"] for p in progs],
        "programas_total": [p["total"] for p in progs],
        "dist_labels": [f"{int(k)} sem." for k in dist.index],
        "dist_values": [int(v) for v in dist.values],
        "precios_labels": [p["programa"] for p in sorted(precios_data, key=lambda x: x["valor"])],
        "precios_values": [p["valor"] for p in sorted(precios_data, key=lambda x: x["valor"])],
    }
    return render_template("dashboard.html", stats=stats, chart=chart, actividad=activity.summary(14),
                           cruce=cruce_data.status(), hitos=store.param.hitos(limite=5))


@app.route("/stats")
@login_required
def stats():
    return redirect(url_for("dashboard"))


# =====================================================
# PÁGINAS DE CONTENIDO
# =====================================================
@app.route("/flujos")
@login_required
def flujos():
    return render_template("flujos.html")


def _gantt(bloques):
    """Escala de tiempo común (porcentajes) para dibujar las cohortes."""
    from datetime import date as _d
    fechas = []
    for b in bloques:
        for c in b["cohortes"]:
            for f in c["fechas"].values():
                fechas += [_d.fromisoformat(x) for x in (f.get("desde"), f.get("hasta")) if x]
    if not fechas:
        return None
    ini = min(fechas).replace(day=1)
    fin = max(fechas)
    fin = (fin.replace(day=28) + timedelta(days=4)).replace(day=1)  # primer día del mes siguiente
    total = (fin - ini).days or 1
    pos = lambda d: round((_d.fromisoformat(d) - ini).days / total * 100, 2)
    meses, m = [], ini
    nombres = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    while m < fin:
        sig = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
        meses.append({"label": nombres[m.month] + (f" {str(m.year)[2:]}" if m.month == 1 or not meses else ""),
                      "left": pos(m.isoformat()), "width": round((sig - m).days / total * 100, 2)})
        m = sig
    hoy = datetime.now().date()
    filas = []
    for b in bloques:
        for c in b["cohortes"]:
            segs = []
            ins_key = next((k for k in ("inscripcion", "transf_extension", "transferencias", "segundo_pos") if k in c["fechas"]), "inscripcion")
            for key, cls in ((ins_key, "insc"), ("induccion", "ind"), ("clases", "cls")):
                f = c["fechas"].get(key)
                if f and f.get("desde") and f.get("hasta"):
                    left = pos(f["desde"])
                    segs.append({"cls": cls, "left": left, "width": max(round(pos(f["hasta"]) - left, 2), 0.8),
                                 "titulo": f["nombre"], "texto": f["texto"]})
            filas.append({"codigo": c["codigo"], "corto": c["corto"], "segs": segs})
    hoy_pos = pos(hoy.isoformat()) if ini <= hoy <= fin else None
    return {"meses": meses, "filas": filas, "hoy": hoy_pos}


MESES_CORTOS = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _vista_cohortes(bloque):
    from core.parametrizacion import estado, fecha_larga as fl
    from datetime import date as _d
    hoy = datetime.now().date()
    out = []
    for c in bloque["cohortes"]:
        f = c["fechas"]
        ins = f.get("inscripcion") or next((v for k, v in f.items() if k != "clases" and k != "induccion"), {})
        est = estado(ins.get("desde"), ins.get("hasta"))
        dias = (_d.fromisoformat(ins["hasta"]) - hoy).days if ins.get("hasta") else None
        filas = []
        for key, icono in (("inscripcion", "fa-user-plus"), ("transferencias", "fa-right-left"), ("transf_extension", "fa-arrows-turn-to-dots"),
                           ("segundo_pos", "fa-user-graduate"), ("induccion", "fa-chalkboard-user"), ("clases", "fa-graduation-cap")):
            v = f.get(key)
            if not v:
                continue
            d1 = _d.fromisoformat(v["desde"]) if v.get("desde") else None
            d2 = _d.fromisoformat(v["hasta"]) if v.get("hasta") else None
            corta = lambda x, anio=True: f"{x.day} {MESES_CORTOS[x.month]}" + (f" {x.year}" if anio else "")
            if d1 and d2 and d1 != d2:
                rango = f"{corta(d1, d1.year != d2.year)} – {corta(d2)}"
            else:
                rango = ("Hasta el " if d2 and not d1 else "") + corta(d2 or d1)
            filas.append({"nombre": v["nombre"], "icono": icono, "rango": rango or v["texto"], "key": key})
        n_prog = sum(1 for p in bloque["programas"] if c["corto"] in p["cohortes"])
        out.append({**c, "estado": est, "dias": dias, "filas": filas, "n_programas": n_prog,
                    "inicio": fl(_d.fromisoformat(f["clases"]["desde"]))})
    return out


@app.route("/parametrizacion")
@login_required
def parametrizacion():
    P = store.param
    d = P.data()
    if not d:
        return render_template("parametrizacion.html", d={}, secciones=[], hitos=[], abiertas=0)
    secciones = []
    if d.get("pregrado"):
        b = d["pregrado"]
        secciones.append({"id": "pregrado", "titulo": "Pregrado", "sub": b["hoja"], "icono": "fa-user-graduate", "color": "green",
                          "bloques": [{"titulo": "Pregrado – primera vez, SENA y transferencias", "bloque": b, "cohortes": _vista_cohortes(b)}],
                          "gantt": _gantt([b])})
    pos = d.get("posgrado") or {}
    bls = [x for x in (pos.get("especializaciones"), pos.get("maestrias")) if x]
    if bls:
        secciones.append({"id": "posgrado", "titulo": "Posgrado", "sub": pos.get("hoja", ""), "icono": "fa-award", "color": "orange",
                          "bloques": [{"titulo": ("Maestrías" if any(norm(p["nombre"]).startswith("MAESTRIA") for p in x["programas"]) else "Especializaciones"),
                                       "bloque": x, "cohortes": _vista_cohortes(x)} for x in bls],
                          "gantt": _gantt(bls)})
    tr = (d.get("transferencias_posgrado") or {}).get("bloques") or []
    if tr:
        secciones.append({"id": "transferencias", "titulo": "Transferencias posgrado", "sub": "Externa · extensión · segundo posgrado",
                          "icono": "fa-right-left", "color": "blue",
                          "bloques": [{"titulo": ("Maestrías" if any(norm(p["nombre"]).startswith("MAESTRIA") for p in x["programas"]) else "Especializaciones"),
                                       "bloque": x, "cohortes": _vista_cohortes(x), "texto": True} for x in tr],
                          "gantt": _gantt(tr)})
    abiertas = sum(1 for s_ in secciones[:2] for bl in s_["bloques"] for c in bl["cohortes"] if c["estado"] == "abierta")
    return render_template("parametrizacion.html", d=d, secciones=secciones, hitos=P.hitos(limite=8), abiertas=abiertas)


@app.route("/capacitacion")
@login_required
def capacitacion():
    return render_template("capacitacion.html", ia_claude=claude_available())


@app.route("/capacitacion/api/chat", methods=["POST"])
@app.route("/api/asistente", methods=["POST"])
@login_required
def api_chat():
    data = request.get_json(silent=True) or {}
    msg = str(data.get("message", "")).strip()[:2000]
    if not msg:
        return jsonify({"ok": False, "error": "Mensaje vacío"}), 400
    text, source = assistant_answer(msg, data.get("history") or [], store)
    activity.log("asistente", msg, 1)
    return jsonify({"ok": True, "reply": text, "response": text, "source": source})


# =====================================================
# PIEZAS GRÁFICAS Y BROCHURES
# =====================================================
@app.route("/piezas")
@app.route("/piezas/<path:subfolder>")
@login_required
def piezas(subfolder=""):
    carpeta = safe_join(PIEZAS_DIR, subfolder)
    if not carpeta or not os.path.isdir(carpeta):
        return redirect("/piezas")
    carpetas, imagenes = list_folder(carpeta)
    folders = [{"name": d, "path": (subfolder + "/" + d) if subfolder else d,
                "count": count_images(os.path.join(carpeta, d)), "cover": folder_cover(os.path.join(carpeta, d))}
               for d in carpetas]
    imgs = [{"name": f, "path": "piezas/" + ((subfolder + "/") if subfolder else "") + f,
             **file_info(os.path.join(carpeta, f))} for f in imagenes]
    return render_template("piezas.html", carpetas=folders, imagenes=imgs, subfolder=subfolder,
                           breadcrumb=breadcrumb_for(subfolder))


# =====================================================
# BROCHURES Y PENSUM (PDF)
# =====================================================
@app.route("/pensum")
@app.route("/pensum/<nivel>")
@login_required
def pensum(nivel="pregrado"):
    """Compatibilidad: el pensum ahora vive dentro de Brochures."""
    return redirect(url_for("brochures", nivel=nivel if nivel in PENSUM_DIRS else "pregrado", ver=request.args.get("ver") or None))


@app.route("/brochures/<nivel>/archivo/<path:filename>")
@app.route("/pensum/<nivel>/archivo/<path:filename>")
@login_required
def pensum_archivo(nivel, filename):
    folder = PENSUM_DIRS.get(nivel)
    if not folder or not listed_name(folder, filename):
        abort(404)
    return send_from_directory(folder, filename, mimetype="application/pdf", conditional=True,
                               as_attachment=request.args.get("descargar") == "1")


@app.route("/brochures")
@login_required
def brochures():
    os.makedirs(BROCHURES_DIR, exist_ok=True)
    otros = [{"archivo": f, "nombre": os.path.splitext(f)[0].replace("_", " "), "categoria": "Otros documentos",
              "size": file_info(os.path.join(BROCHURES_DIR, f))["size"]}
             for f in sorted(os.listdir(BROCHURES_DIR)) if f.lower().endswith(".pdf")]
    conteo = {"pregrado": len(listar_pensum("pregrado")), "posgrado": len(listar_pensum("posgrado")), "otros": len(otros)}
    nivel = request.args.get("nivel", "pregrado")
    if nivel not in conteo or (nivel == "otros" and not otros):
        nivel = "pregrado"
    if nivel == "otros":
        items = [{**o, "url": url_for("static", filename="brochures/" + o["archivo"])} for o in otros]
    else:
        items = [{**it, "url": url_for("pensum_archivo", nivel=nivel, filename=it["archivo"])} for it in listar_pensum(nivel)]
    return render_template("brochures.html", nivel=nivel, items=items, conteo=conteo, ver=request.args.get("ver", ""))


# =====================================================
# AGUACHICA
# =====================================================
METAS_EJECUTIVOS = {
    "Jorge": {"llamadas": 400, "inscritos": 0, "pagos": 11},
    "Maria": {"llamadas": 350, "inscritos": 0, "pagos": 11},
    "Ana": {"llamadas": 300, "inscritos": 0, "pagos": 11},
}


def _aguachica_df():
    if os.path.exists(AGUACHICA_FILE):
        df = pd.read_excel(AGUACHICA_FILE)
    else:
        df = pd.DataFrame(columns=["fecha", "ejecutivo", "llamadas", "inscritos", "pagos"])
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    for c in ("llamadas", "inscritos", "pagos"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df


@app.route("/aguachica", methods=["GET", "POST"])
@login_required
def aguachica_login():
    if session.get("aguachica"):
        return redirect("/aguachica/dashboard")
    error = None
    if request.method == "POST":
        if (request.form.get("user") == AGUACHICA_USER and check_password(request.form.get("password"), AGUACHICA_PASSWORD)):
            session["aguachica"] = True
            return redirect("/aguachica/dashboard")
        error = "Usuario o contraseña incorrectos"
    return render_template("aguachica_login.html", error=error)


@app.route("/aguachica/salir")
@login_required
def aguachica_logout():
    session.pop("aguachica", None)
    return redirect("/aguachica")


@app.route("/aguachica/dashboard", methods=["GET", "POST"])
@login_required
def aguachica_dashboard():
    if not session.get("aguachica"):
        return redirect("/aguachica")

    if request.method == "POST":
        try:
            nuevo = {
                "fecha": pd.to_datetime(request.form.get("fecha") or datetime.now().date()),
                "ejecutivo": request.form["ejecutivo"],
                "llamadas": max(0, int(request.form["llamadas"])),
                "inscritos": max(0, int(request.form["inscritos"])),
                "pagos": max(0, int(request.form["pagos"])),
            }
        except (KeyError, ValueError):
            abort(400, description="Datos del registro inválidos")
        df = _aguachica_df()
        df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
        df["fecha"] = df["fecha"].dt.date
        df.to_excel(AGUACHICA_FILE, index=False)
        return redirect("/aguachica/dashboard?ejecutivo=" + nuevo["ejecutivo"])

    df = _aguachica_df()
    semana = df[df["fecha"] >= datetime.now() - timedelta(days=7)]
    totales = semana.groupby("ejecutivo")[["llamadas", "inscritos", "pagos"]].sum().reset_index()
    ejecutivo_sel = request.args.get("ejecutivo", "Jorge")
    if ejecutivo_sel not in METAS_EJECUTIVOS:
        ejecutivo_sel = "Jorge"
    ind = semana[semana["ejecutivo"] == ejecutivo_sel][["llamadas", "inscritos", "pagos"]].sum()
    resumen_individual = {k: int(ind.get(k, 0)) for k in ("llamadas", "inscritos", "pagos")}
    meta_individual = METAS_EJECUTIVOS[ejecutivo_sel]

    def semaforo(valor, meta):
        if meta <= 0 or valor >= meta:
            return "verde"
        return "amarillo" if valor >= meta * 0.7 else "rojo"

    estado = {k: semaforo(resumen_individual[k], meta_individual[k]) for k in resumen_individual}
    registros = semana.sort_values("fecha", ascending=False).head(30).copy()
    registros["fecha"] = registros["fecha"].dt.strftime("%d/%m/%Y")
    return render_template(
        "aguachica.html", totales=totales.to_dict(orient="records"), ejecutivo_sel=ejecutivo_sel,
        resumen_individual=resumen_individual, meta_individual=meta_individual,
        metas_ejecutivos=METAS_EJECUTIVOS, estado=estado, registros=registros.to_dict(orient="records"),
        hoy=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/aguachica/borrar", methods=["POST"])
@login_required
def aguachica_borrar():
    if not session.get("aguachica"):
        return redirect("/aguachica")
    if check_password(request.form.get("clave"), AGUACHICA_CLAVE_BORRADO) and os.path.exists(AGUACHICA_FILE):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        shutil.copy2(AGUACHICA_FILE, os.path.join(BACKUP_DIR, f"aguachica_{datetime.now():%Y%m%d_%H%M%S}.xlsx"))
        os.remove(AGUACHICA_FILE)
    return redirect("/aguachica/dashboard")


@app.route("/aguachica/exportar")
@login_required
def aguachica_exportar():
    if not session.get("aguachica"):
        return redirect("/aguachica")
    if not os.path.exists(AGUACHICA_FILE):
        return "No hay datos para exportar", 404
    df = pd.read_excel(AGUACHICA_FILE)
    return Response("﻿" + df.to_csv(index=False), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=aguachica_datos.csv"})


# =====================================================
# CRUCE DE DATOS
# =====================================================
@app.route("/cruce", methods=["GET", "POST"])
@login_required
def cruce():
    if request.method == "POST":
        action = request.form.get("action")
        if action in ("upload", "upload_funnel"):
            file = request.files.get("archivo" if action == "upload" else "archivo_funnel")
            if file and file.filename and file.filename.lower().endswith((".xlsx", ".xls")):
                cruce_data.save_upload(file, "gen" if action == "upload" else "funnel")
        elif action == "sync_sheets":
            cruce_data.sync_gen()
        elif action == "sync_funnel":
            cruce_data.sync_funnel()
        elif action == "delete":
            cruce_data.delete("gen")
        elif action == "delete_funnel":
            cruce_data.delete("funnel")
        return redirect("/cruce")
    return render_template("cruce.html", **cruce_data.status())


@app.route("/api/cruce/sync-sheets", methods=["POST"])
@login_required
def api_cruce_sync_sheets():
    ok, msg = cruce_data.sync_gen()
    return jsonify({"ok": ok, "message": msg})


@app.route("/api/cruce/sync-funnel", methods=["POST"])
@login_required
def api_cruce_sync_funnel():
    ok, msg = cruce_data.sync_funnel()
    return jsonify({"ok": ok, "message": msg, "total_cedulas": len(cruce_data.funnel_cedulas())})


def _cruce_params():
    a = request.args
    return dict(fecha_cargue=a.get("fecha_cargue", "").strip(), rango=a.get("rango", "todas").strip().lower(),
                radar=a.get("radar", "todos").strip().lower(), q=a.get("q", "").strip(),
                desde=a.get("desde", "").strip(), hasta=a.get("hasta", "").strip())


@app.route("/api/cruce")
@login_required
def api_cruce():
    vacio = {"rows": [], "total": 0, "total_en_funnel": 0, "fechas_disponibles": [], "columns": [], "resumen": {}}
    try:
        res = cruce_data.query(**_cruce_params())
    except Exception as e:
        return jsonify({"error": f"Error leyendo archivo: {e}", **vacio})
    if res is None:
        return jsonify({"error": "No hay archivo cargado", **vacio})
    res.pop("df")
    return jsonify(res)


@app.route("/api/cruce/export.xlsx")
@login_required
def api_cruce_export():
    res = cruce_data.query(**_cruce_params())
    if res is None:
        return "No hay archivo cargado", 404
    buf = cruce_data.to_excel(res)
    return send_file(buf, as_attachment=True, download_name=f"cruce_galan_funnel_{datetime.now():%Y-%m-%d}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/api/cruce/opciones")
@login_required
def api_cruce_opciones():
    return jsonify({"ok": True})


# =====================================================
# ADMINISTRACIÓN
# =====================================================
@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin_login():
    if session.get("admin"):
        return redirect("/admin/dashboard")
    error = None
    if request.method == "POST":
        wait = limiter.blocked("admin")
        if wait:
            error = f"Demasiados intentos. Espera {wait} segundos."
        elif check_password(request.form.get("password", ""), ADMIN_PASSWORD):
            limiter.reset("admin")
            session["admin"] = True
            return redirect("/admin/dashboard")
        else:
            limiter.fail("admin")
            error = "Contraseña incorrecta"
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
@login_required
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin")


@app.route("/admin/dashboard")
@admin_only
def admin_dashboard():
    os.makedirs(BROCHURES_DIR, exist_ok=True)
    stats = {
        "mensajes_comerciales": len(store.mensajes_programas()),
        "mensajes_sena": len(store.mensajes_sena()),
        "precios": len(store.precios()),
        "piezas": count_images(PIEZAS_DIR),
        "brochures": len([f for f in os.listdir(BROCHURES_DIR) if f.lower().endswith(".pdf")]),
        "titulos": len(store.titulos()),
        "combinaciones": int(len(store.actas())),
        "presencial": len(store.presencial()),
    }
    from core.parametrizacion import archivo_actual
    pa = archivo_actual()
    return render_template("admin_dashboard.html", stats=stats, actas_info=file_info(ACTAS_FILE),
                           param_info={"nombre": os.path.basename(pa) if pa else "Sin cargar", **(file_info(pa) if pa else {"size": 0, "mtime": ""})},
                           presencial_info=file_info(PRESENCIAL_FILE), actividad=activity.summary(7))


def _crud_list(filename, fields, ints=()):
    items = store.json(filename)
    items = list(items)
    action = request.form.get("action")
    idx = request.form.get("index", type=int)

    def read():
        out = {}
        for f in fields:
            v = request.form.get(f, "")
            out[f] = int(v or 0) if f in ints else v.replace("\r\n", "\n")
        return out

    if action == "update" and idx is not None and 0 <= idx < len(items):
        items[idx].update(read())
    elif action == "add":
        nuevo = read()
        if filename == "precios.json":
            nuevo = {"id": max([p.get("id", 0) for p in items], default=0) + 1, **nuevo}
        items.append(nuevo)
    elif action == "delete" and idx is not None and 0 <= idx < len(items):
        items.pop(idx)
    elif action == "move" and idx is not None and 0 <= idx < len(items):
        j = idx + (1 if request.form.get("dir") == "down" else -1)
        if 0 <= j < len(items):
            items[idx], items[j] = items[j], items[idx]
    else:
        return
    store.save(filename, items)


@app.route("/admin/mensajes-comerciales", methods=["GET", "POST"])
@admin_only
def admin_mensajes_comerciales():
    if request.method == "POST":
        _crud_list("mensajes_programas.json", ["nivel", "titulo", "texto"])
        return redirect("/admin/mensajes-comerciales")
    return render_template("admin_mensajes.html", mensajes=store.mensajes_programas(), tipo="comerciales",
                           titulo="Mensajes comerciales", accion="/admin/mensajes-comerciales")


@app.route("/admin/mensajes-sena", methods=["GET", "POST"])
@admin_only
def admin_mensajes_sena():
    if request.method == "POST":
        _crud_list("mensajes_sena.json", ["titulo", "texto"])
        return redirect("/admin/mensajes-sena")
    return render_template("admin_mensajes.html", mensajes=store.mensajes_sena(), tipo="sena",
                           titulo="Mensajes SENA", accion="/admin/mensajes-sena")


@app.route("/admin/precios", methods=["GET", "POST"])
@admin_only
def admin_precios():
    if request.method == "POST":
        _crud_list("precios.json", ["programa", "valor", "descuento", "semestres"], ints=("valor", "descuento", "semestres"))
        return redirect("/admin/precios")
    return render_template("admin_precios.html", precios=store.precios())


@app.route("/admin/config", methods=["GET", "POST"])
@admin_only
def admin_config():
    saved = False
    if request.method == "POST":
        cfg = store.config
        for k, default in DEFAULT_CONFIG.items():
            if isinstance(default, list):
                continue
            if k in request.form:
                v = request.form.get(k, "").strip()
                if isinstance(default, int):
                    try:
                        cfg[k] = int(v)
                    except ValueError:
                        continue
                else:
                    cfg[k] = v
        cfg["descuento_sena"] = max(0, min(100, cfg["descuento_sena"]))
        if request.form.get("modulos_form") == "1":
            visibles = set(request.form.getlist("modulos_visibles"))
            cfg["modulos_ocultos"] = [k for k in MODULOS if k not in visibles]
        store.save("config.json", cfg)
        saved = True
    return render_template("admin_config.html", config=store.config, saved=saved, modulos=MODULOS,
                           ocultos=modulos_ocultos())


@app.route("/admin/reemplazar", methods=["POST"])
@admin_only
def admin_reemplazar():
    buscar = request.form.get("buscar", "")
    reemplazo = request.form.get("reemplazo", "")
    destinos = request.form.getlist("destinos") or ["mensajes_programas.json", "mensajes_sena.json"]
    total = 0
    if buscar:
        for fname in destinos:
            if fname not in ("mensajes_programas.json", "mensajes_sena.json"):
                continue
            items = list(store.json(fname))
            for m in items:
                for campo in ("titulo", "texto"):
                    if buscar in m.get(campo, ""):
                        total += m[campo].count(buscar)
                        m[campo] = m[campo].replace(buscar, reemplazo)
            store.save(fname, items)
    return redirect(url_for("admin_dashboard", reemplazos=total))


def _subir_parametrizacion(file):
    from core.parametrizacion import archivo_actual, parse_excel
    os.makedirs(BACKUP_DIR, exist_ok=True)
    tmp = os.path.join(BACKUP_DIR, "_subida_parametrizacion.xlsx")
    file.save(tmp)
    try:
        d = parse_excel(tmp)
    except Exception as e:
        os.remove(tmp)
        return redirect(url_for("admin_dashboard", error=f"No se pudo leer la parametrización: {e}"))
    if not d.get("pregrado") and not d.get("posgrado"):
        os.remove(tmp)
        return redirect(url_for("admin_dashboard", error="No encontré hojas 'Pregrado AAAA-10' ni 'Posgrado AAAA-30' con la fila COHORTE."))
    anio = (re.findall(r"20\d\d", (d.get("pregrado") or {}).get("hoja", "") or (d.get("posgrado") or {}).get("hoja", "")) or [str(datetime.now().year)])[0]
    actual = archivo_actual()
    if actual:
        shutil.copy2(actual, os.path.join(BACKUP_DIR, f"parametrizacion_{datetime.now():%Y%m%d_%H%M%S}.xlsx"))
    os.replace(tmp, os.path.join(BASE_DIR, f"PARAMETRIZACIÓN {anio}.xlsx"))
    store.param.invalidate()
    n = len((d.get("pregrado") or {}).get("cohortes", [])) + sum(len((x or {}).get("cohortes", [])) for x in (d.get("posgrado") or {}).values() if isinstance(x, dict))
    return redirect(url_for("admin_dashboard", ok=f"Parametrización {anio} cargada: {n} cohortes. Las fechas de los mensajes ya se actualizaron."))


@app.route("/admin/datos", methods=["POST"])
@admin_only
def admin_datos():
    kind = request.form.get("tipo")
    file = request.files.get("archivo")
    if kind == "parametrizacion" and file and file.filename.lower().endswith(".xlsx"):
        return _subir_parametrizacion(file)
    target, validator = {"actas": (ACTAS_FILE, validar_actas), "presencial": (PRESENCIAL_FILE, validar_presencial)}.get(kind, (None, None))
    if not target or not file or not file.filename.lower().endswith(".xlsx"):
        return redirect(url_for("admin_dashboard", error="Selecciona un archivo .xlsx válido"))
    os.makedirs(BACKUP_DIR, exist_ok=True)
    tmp = os.path.join(BACKUP_DIR, f"_subida_{kind}.xlsx")
    file.save(tmp)
    removidas = []
    try:
        ok, msg, filas = validator(tmp)
        if ok and kind == "actas":
            removidas = sanitize_workbook(tmp)
    except Exception as e:
        ok, msg, filas = False, f"No se pudo leer el Excel: {e}", 0
    if not ok:
        os.remove(tmp)
        return redirect(url_for("admin_dashboard", error=msg))
    if os.path.exists(target):
        shutil.copy2(target, os.path.join(BACKUP_DIR, f"{kind}_{datetime.now():%Y%m%d_%H%M%S}.xlsx"))
    os.replace(tmp, target)
    store.invalidate()
    aviso = f"Archivo de {kind} actualizado: {msg if kind == 'actas' else str(filas) + ' filas'}."
    if removidas:
        aviso += f" Por seguridad se quitaron hojas con datos personales: {', '.join(removidas)}."
    return redirect(url_for("admin_dashboard", ok=aviso))


@app.route("/admin/datos/descargar/<kind>")
@admin_only
def admin_datos_descargar(kind):
    from core.parametrizacion import archivo_actual
    target = {"actas": ACTAS_FILE, "presencial": PRESENCIAL_FILE, "parametrizacion": archivo_actual()}.get(kind)
    if not target or not os.path.exists(target):
        abort(404)
    return send_file(target, as_attachment=True)


@app.route("/admin/actividad/limpiar", methods=["POST"])
@admin_only
def admin_actividad_limpiar():
    activity.clear()
    return redirect(url_for("admin_dashboard", ok="Historial de actividad borrado"))


@app.route("/admin/piezas", methods=["GET", "POST"])
@app.route("/admin/piezas/<path:subfolder>", methods=["GET", "POST"])
@admin_only
def admin_piezas(subfolder=""):
    current_dir = safe_join(PIEZAS_DIR, subfolder)
    if not current_dir:
        return redirect("/admin/piezas")
    os.makedirs(current_dir, exist_ok=True)

    if request.method == "POST":
        action = request.form.get("action")
        if action == "upload":
            for file in request.files.getlist("imagenes"):
                if file and file.filename and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
                    name = secure_filename(file.filename) or f"imagen_{datetime.now():%H%M%S}.jpg"
                    file.save(os.path.join(current_dir, name))
        elif action == "delete":
            name = listed_name(current_dir, request.form.get("filename"))
            if name and os.path.isfile(os.path.join(current_dir, name)):
                os.remove(os.path.join(current_dir, name))
        elif action == "rename":
            old = listed_name(current_dir, request.form.get("filename"))
            new = secure_filename(request.form.get("new_name", "").strip())
            if old and new:
                ext = old.rsplit(".", 1)[-1]
                if not allowed_file(new, ALLOWED_IMAGE_EXTENSIONS) and not os.path.isdir(os.path.join(current_dir, old)):
                    new = f"{new}.{ext}"
                if not os.path.exists(os.path.join(current_dir, new)):
                    os.rename(os.path.join(current_dir, old), os.path.join(current_dir, new))
        elif action == "create_folder":
            name = request.form.get("folder_name", "").strip().replace("/", "").replace("\\", "")
            name = name if name not in ("", ".", "..") else ""
            if name:
                os.makedirs(os.path.join(current_dir, name), exist_ok=True)
        elif action == "delete_folder":
            name = listed_name(current_dir, request.form.get("folder_name"))
            if name and os.path.isdir(os.path.join(current_dir, name)):
                shutil.rmtree(os.path.join(current_dir, name))
        return redirect("/admin/piezas" + ("/" + subfolder if subfolder else ""))

    carpetas, imagenes = list_folder(current_dir)
    folders = [{"name": d, "count": count_images(os.path.join(current_dir, d))} for d in carpetas]
    imgs = [{"name": f, "path": "piezas/" + ((subfolder + "/") if subfolder else "") + f,
             **file_info(os.path.join(current_dir, f))} for f in imagenes]
    return render_template("admin_piezas.html", carpetas=folders, imagenes=imgs, subfolder=subfolder,
                           breadcrumb=breadcrumb_for(subfolder))


@app.route("/admin/brochures", methods=["GET", "POST"])
@admin_only
def admin_brochures():
    os.makedirs(BROCHURES_DIR, exist_ok=True)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "upload":
            for file in request.files.getlist("pdfs"):
                if file and file.filename and allowed_file(file.filename, ALLOWED_PDF_EXTENSIONS):
                    file.save(os.path.join(BROCHURES_DIR, secure_filename(file.filename)))
        elif action == "delete":
            name = listed_name(BROCHURES_DIR, request.form.get("filename"))
            if name:
                os.remove(os.path.join(BROCHURES_DIR, name))
        return redirect("/admin/brochures")
    archivos = [{"name": f, **file_info(os.path.join(BROCHURES_DIR, f))}
                for f in sorted(os.listdir(BROCHURES_DIR)) if f.lower().endswith(".pdf")]
    return render_template("admin_brochures.html", archivos=archivos)


# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", port=int(os.environ.get("PORT", 8000)))
