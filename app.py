import pandas as pd
import os
import io
import csv
import json
import uuid
import time
import re
from datetime import datetime, timedelta
from flask import redirect, Response, jsonify
from flask import Flask, render_template, request, send_from_directory, session, url_for
from functools import wraps
from whatsapp import whatsapp_bp
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = "homologaciones-aguachica-2026"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

app.register_blueprint(whatsapp_bp)

# =====================================================
# LIMPIEZA DE CARACTERES Y ENCODING ESPAÑOL (UTF-8)
# =====================================================
def fix_text_enc(s):
    """Corrige caracteres rotos o caracteres de reemplazo (\ufffd) en texto en español."""
    if not isinstance(s, str):
        return s
    U = '\ufffd'
    if U not in s:
        return s

    s = s.replace(f'T{U}CNICO', 'TÉCNICO').replace(f'T{U}cnico', 'Técnico').replace(f't{U}cnico', 'técnico')
    s = s.replace(f'TECNOLOG{U}A', 'TECNOLOGÍA').replace(f'Tecnolog{U}a', 'Tecnología').replace(f'tecnolog{U}a', 'tecnología')
    s = s.replace(f'Gest{U}n', 'Gestión').replace(f'GESTI{U}N', 'GESTIÓN')
    s = s.replace(f'Atenc{U}n', 'Atención').replace(f'ATENC{U}N', 'ATENCIÓN')
    s = s.replace(f'L{U}nea', 'Línea').replace(f'L{U}NEA', 'LÍNEA')
    s = s.replace(f'Asesor{U}a', 'Asesoría').replace(f'ASESOR{U}A', 'ASESORÍA')
    s = s.replace(f'N{U}mina', 'Nómina').replace(f'N{U}MINA', 'NÓMINA')
    s = s.replace(f'Organizac{U}n', 'Organización').replace(f'ORGANIZAC{U}N', 'ORGANIZACIÓN')
    s = s.replace(f'Log{U}stica', 'Logística').replace(f'LOG{U}STICA', 'LOGÍSTICA')
    s = s.replace(f'Operac{U}n', 'Operación').replace(f'Operac{U}nes', 'Operaciones').replace(f'OPERAC{U}N', 'OPERACIÓN').replace(f'OPERAC{U}NES', 'OPERACIONES')
    s = s.replace(f'Contabilizac{U}n', 'Contabilización').replace(f'CONTABILIZAC{U}N', 'CONTABILIZACIÓN')
    s = s.replace(f'Producc{U}n', 'Producción').replace(f'PRODUCC{U}N', 'PRODUCCIÓN')
    s = s.replace(f'Informac{U}n', 'Información').replace(f'INFORMAC{U}N', 'INFORMACIÓN')
    s = s.replace(f'Administrac{U}n', 'Administración').replace(f'ADMINISTRAC{U}N', 'ADMINISTRACIÓN')
    s = s.replace(f'Construcc{U}n', 'Construcción').replace(f'CONSTRUCC{U}N', 'CONSTRUCCIÓN')
    s = s.replace(f'Ejecuc{U}n', 'Ejecución').replace(f'EJECUC{U}N', 'EJECUCIÓN')
    s = s.replace(f'Direcc{U}n', 'Dirección').replace(f'DIRECC{U}N', 'DIRECCIÓN')
    s = s.replace(f'Instalac{U}n', 'Instalación').replace(f'INSTALAC{U}N', 'INSTALACIÓN')
    s = s.replace(f'Comercializac{U}n', 'Comercialización').replace(f'COMERCIALIZAC{U}N', 'COMERCIALIZACIÓN')
    s = s.replace(f'Orientac{U}n', 'Orientación').replace(f'ORIENTAC{U}N', 'ORIENTACIÓN')
    s = s.replace(f'Promoc{U}n', 'Promoción').replace(f'PROMOC{U}N', 'PROMOCIÓN')
    s = s.replace(f'Integrac{U}n', 'Integración').replace(f'INTEGRAC{U}N', 'INTEGRACIÓN')
    s = s.replace(f'Formulac{U}n', 'Formulación').replace(f'FORMULAC{U}N', 'FORMULACIÓN')
    s = s.replace(f'Evaluac{U}n', 'Evaluación').replace(f'EVALUAC{U}N', 'EVALUACIÓN')
    s = s.replace(f'Comunicac{U}n', 'Comunicación').replace(f'COMUNICAC{U}N', 'COMUNICACIÓN')
    s = s.replace(f'Bogot{U}', 'Bogotá').replace(f'BOGOT{U}', 'BOGOTÁ')
    s = s.replace(f'Gal{U}n', 'Galán').replace(f'GAL{U}N', 'GALÁN')
    s = s.replace(f'Fontib{U}n', 'Fontibón').replace(f'FONTIB{U}N', 'FONTIBÓN')
    s = s.replace(f'Facatativ{U}', 'Facatativá').replace(f'FACATATIV{U}', 'FACATATIVÁ')
    s = s.replace(f'Zipaquir{U}', 'Zipaquirá').replace(f'ZIPAQUIR{U}', 'ZIPAQUIRÁ')
    s = s.replace(f'Generac{U}n', 'Generación').replace(f'GENERAC{U}N', 'GENERACIÓN')
    s = s.replace(f'C{U}digo', 'Código').replace(f'C{U}DIGO', 'CÓDIGO')
    s = s.replace(f'Andr{U}s', 'Andrés').replace(f'ANDR{U}S', 'ANDRÉS')
    s = s.replace(f'Hern{U}ndez', 'Hernández').replace(f'HERN{U}NDEZ', 'HERNÁNDEZ')
    s = s.replace(f'Mart{U}nez', 'Martínez').replace(f'MART{U}NEZ', 'MARTÍNEZ')
    s = s.replace(f'Garc{U}a', 'García').replace(f'GARC{U}A', 'GARCÍA')
    s = s.replace(f'R{U}os', 'Ríos').replace(f'R{U}OS', 'RÍOS')
    s = s.replace(f'D{U}az', 'Díaz').replace(f'D{U}AZ', 'DÍAZ')
    s = s.replace(f'Guti{U}rrez', 'Gutiérrez').replace(f'GUTI{U}RREZ', 'GUTIÉRREZ')
    s = s.replace(f'Mu{U}oz', 'Muñoz').replace(f'MU{U}OZ', 'MUÑOZ')
    s = s.replace(f'Pe{U}a', 'Peña').replace(f'PE{U}A', 'PEÑA')
    s = s.replace(f'Ni{U}o', 'Niño').replace(f'NI{U}O', 'NIÑO')

    s = re.sub(rf'c{U}n\b', 'ción', s)
    s = re.sub(rf'C{U}N\b', 'CIÓN', s)
    s = re.sub(rf's{U}n\b', 'sión', s)
    s = re.sub(rf'S{U}N\b', 'SIÓN', s)
    s = re.sub(rf'g{U}a\b', 'gía', s)
    s = re.sub(rf'G{U}A\b', 'GÍA', s)
    s = re.sub(rf'r{U}a\b', 'ría', s)
    s = re.sub(rf'R{U}A\b', 'RÍA', s)
    s = re.sub(rf'T{U}c', 'Téc', s)
    s = re.sub(rf't{U}c', 'téc', s)
    s = re.sub(rf'T{U}C', 'TÉC', s)
    s = s.replace(U, '')
    return s


def clean_df(df):
    """Limpia nombres de columnas y celdas de texto para arreglar la codificación en español."""
    df.columns = [fix_text_enc(str(c)).strip() for c in df.columns]
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(fix_text_enc)
    return df


# =====================================================
# GLOBAL LOGIN GATE
# =====================================================
GLOBAL_USER = "Innovacion"
GLOBAL_PASSWORD = "0228"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def global_login():
    error = None
    if request.method == "POST":
        user = request.form.get("user", "")
        password = request.form.get("password", "")
        if user == GLOBAL_USER and password == GLOBAL_PASSWORD:
            session["logged_in"] = True
            return redirect("/")
        else:
            error = "Usuario o contraseña incorrectos"
    return render_template("global_login.html", error=error)

@app.route("/logout")
def global_logout():
    session.pop("logged_in", None)
    return redirect("/login")

# =====================================================
# DATA PATHS
# =====================================================
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
BROCHURES_DIR = os.path.join("static", "brochures")
PIEZAS_DIR = os.path.join("static", "piezas")

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_PDF_EXTENSIONS = {'pdf'}

# =====================================================
# JSON DATA HELPERS
# =====================================================
def load_json(filename):
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_json(filename, data):
    filepath = os.path.join(DATA_DIR, filename)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def allowed_file(filename, allowed):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed

# =====================================================
# LOAD DATA FROM JSON
# =====================================================
def get_mensajes_programas():
    return load_json("mensajes_programas.json")

def get_mensajes_sena():
    return load_json("mensajes_sena.json")

def get_precios():
    return load_json("precios.json")


# =====================================================
# CARGAR HOMOLOGACIONES PRESENCIAL
# =====================================================
presencial = clean_df(pd.read_excel("Presencial 2026.xlsx"))

# =====================================================
# CARGAR ACTAS
# =====================================================
actas = clean_df(pd.read_excel("Actas SENA.xlsx"))


# =====================================================
# LISTA DE TÍTULOS PARA AUTOCOMPLETADO (desde Excel)
# =====================================================
titulos_sena = sorted(actas["TÉCNICO O TECNOLOGÍA"].dropna().astype(str).str.strip().unique().tolist())

# =====================================================
# FUNCIÓN DE MENSAJE
# =====================================================
def generar_mensaje(titulo_input):
    titulo_norm = titulo_input.strip().upper()

    coincidencias = actas[
        actas["TÉCNICO O TECNOLOGÍA"]
        .astype(str)
        .str.upper()
        .str.contains(titulo_norm, na=False)
    ]

    if coincidencias.empty:
        return f"No encontré homologaciones para el título *{titulo_input}*."

    texto = (
        f"*{titulo_input}*\n"
        "Con este título puedes homologar con las siguientes carreras:\n\n"
    )

    for _, fila in coincidencias.iterrows():
        carrera = str(fila["PROGRAMA"]).upper()
        homologados = int(fila["SEMTR HOMOLOGADOS"])
        faltantes = int(fila["FALTANTES"])

        texto += (
            f"🔹 *{carrera}*\n"
            f"➡ Semestres homologados: {homologados}\n"
            f"➡ Semestres por cursar: {faltantes}\n\n"
        )

    if len(coincidencias) == 1:
        texto += (
            "¿Te gustaría recibir más información sobre este programa?\n\n"
            "💡 *Los egresados SENA cuentan con un 20% de descuento* en esta homologación."
        )
    else:
        texto += (
            "¿De cuál de estas opciones te gustaría recibir más información?\n\n"
            "💡 *Los egresados SENA cuentan con un 20% de descuento* en estas homologaciones."
        )

    return texto


# =====================================================
# RUTAS PÚBLICAS
# =====================================================
@app.route("/logo.jpg")
def logo():
    return send_from_directory(".", "logo.jpg")


@app.route("/", methods=["GET", "POST"])
@login_required
def homologaciones():
    mensaje = None

    if request.method == "POST":
        titulo = request.form.get("titulo")
        mensaje = generar_mensaje(titulo)
        session["ultimo_mensaje"] = mensaje

    return render_template(
        "homologaciones.html",
        titulos=titulos_sena,
        mensaje=mensaje,
        precios=get_precios()
    )


@app.route("/mensajes")
@login_required
def mensajes():
    filtro = request.args.get("nivel", "pre")
    mensajes_programas = get_mensajes_programas()

    filtrados = [
        m for m in mensajes_programas
        if m["nivel"] == filtro
    ]

    return render_template(
        "mensajes.html",
        mensajes=filtrados,
        filtro=filtro
    )

@app.route("/sena")
@login_required
def sena():
    q = request.args.get("q", "").lower()
    mensajes_sena = get_mensajes_sena()

    filtrados = [
        m for m in mensajes_sena
        if q in m["titulo"].lower() or q in m["texto"].lower()
    ]

    return render_template(
        "sena.html",
        mensajes=filtrados,
        q=q
    )

@app.route("/piezas")
@app.route("/piezas/<path:subfolder>")
@login_required
def piezas(subfolder=""):
    carpeta = os.path.join("static", "piezas", subfolder)
    # Security: prevent path traversal
    abs_carpeta = os.path.abspath(carpeta)
    abs_base = os.path.abspath(os.path.join("static", "piezas"))
    if not abs_carpeta.startswith(abs_base):
        return redirect("/piezas")

    if not os.path.exists(carpeta):
        return redirect("/piezas")

    items = os.listdir(carpeta) if os.path.exists(carpeta) else []
    carpetas = sorted([d for d in items if os.path.isdir(os.path.join(carpeta, d))])
    imagenes = sorted([f for f in items if os.path.isfile(os.path.join(carpeta, f)) and allowed_file(f, ALLOWED_IMAGE_EXTENSIONS)])

    # Build breadcrumb
    breadcrumb = []
    if subfolder:
        parts = subfolder.replace("\\", "/").split("/")
        for i, part in enumerate(parts):
            breadcrumb.append({
                "name": part,
                "path": "/".join(parts[:i+1])
            })

    return render_template(
        "piezas.html",
        carpetas=carpetas,
        imagenes=imagenes,
        subfolder=subfolder,
        breadcrumb=breadcrumb
    )

@app.route("/aguachica", methods=["GET", "POST"])
@login_required
def aguachica_login():
    if request.method == "POST":
        user = request.form.get("user")
        password = request.form.get("password")

        if user == "csu-aguachica" and password == "1234":
            session["aguachica"] = True
            return redirect("/aguachica/dashboard")

    return render_template("aguachica_login.html")


@app.route("/aguachica/dashboard", methods=["GET", "POST"])
@login_required
def aguachica_dashboard():
    if not session.get("aguachica"):
        return redirect("/aguachica")

    ruta = "aguachica.xlsx"

    if request.method == "POST":
        data = {
            "fecha": datetime.now().date(),
            "ejecutivo": request.form["ejecutivo"],
            "llamadas": int(request.form["llamadas"]),
            "inscritos": int(request.form["inscritos"]),
            "pagos": int(request.form["pagos"]),
        }

        df_new = pd.DataFrame([data])

        if os.path.exists(ruta):
            df = pd.read_excel(ruta)
            df = pd.concat([df, df_new], ignore_index=True)
        else:
            df = df_new

        df.to_excel(ruta, index=False)
        return redirect("/aguachica/dashboard")

    if os.path.exists(ruta):
        df = pd.read_excel(ruta)
    else:
        df = pd.DataFrame(columns=["fecha", "ejecutivo", "llamadas", "inscritos", "pagos"])

    df["fecha"] = pd.to_datetime(df["fecha"])
    semana = df[df["fecha"] >= datetime.now() - timedelta(days=7)]

    totales = (
        semana
        .groupby("ejecutivo")[["llamadas", "inscritos", "pagos"]]
        .sum()
        .reset_index()
    )

    METAS_EJECUTIVOS = {
        "Jorge": {"llamadas": 400, "inscritos": 0, "pagos": 11},
        "Maria": {"llamadas": 350, "inscritos": 0, "pagos": 11},
        "Ana":   {"llamadas": 300, "inscritos": 0, "pagos": 11},
    }

    ejecutivo_sel = request.args.get("ejecutivo", "Jorge")

    resumen_individual = (
        semana[semana["ejecutivo"] == ejecutivo_sel][
            ["llamadas", "inscritos", "pagos"]
        ]
        .sum()
        .fillna(0)
    )

    meta_individual = METAS_EJECUTIVOS.get(ejecutivo_sel)

    resumen = semana[["llamadas", "inscritos", "pagos"]].sum().fillna(0)

    def semaforo(valor, meta):
        if valor >= meta:
            return "verde"
        elif valor >= meta * 0.7:
            return "amarillo"
        else:
            return "rojo"

    estado = {
        "llamadas": semaforo(resumen_individual["llamadas"], meta_individual["llamadas"]),
        "inscritos": semaforo(resumen_individual["inscritos"], meta_individual["inscritos"]),
        "pagos": semaforo(resumen_individual["pagos"], meta_individual["pagos"]),
    }

    return render_template(
        "aguachica.html",
        datos=semana,
        totales=totales,
        ejecutivo_sel=ejecutivo_sel,
        resumen_individual=resumen_individual,
        meta_individual=meta_individual,
        metas_ejecutivos=METAS_EJECUTIVOS,
        estado=estado
    )

# =====================================================
# FUNCIÓN MENSAJE PRESENCIAL
# =====================================================
def generar_mensaje_presencial(titulo_input, sede):
    titulo_norm = titulo_input.strip().upper()
    sede = sede.lower()

    if sede == "bogota":
        col_titulo = "Sede Bogota"
        col_homo = "Semestres de Homologacion"
        col_pend = "Semestres Pendientes"
    elif sede == "pereira":
        col_titulo = "Sede Pereira"
        col_homo = "Semestres de Homologacion.1"
        col_pend = "Semestres Pendientes.1"
    elif sede == "valledupar":
        col_titulo = "Sede Valledupar"
        col_homo = "Semestres de Homologacion.2"
        col_pend = "Semestres Pendientes.2"
    else:
        return "Sede no válida."

    coincidencias = presencial[
        presencial[col_titulo]
        .astype(str)
        .str.upper()
        .str.contains(titulo_norm, na=False)
    ]

    if coincidencias.empty:
        return f"No encontré homologaciones presenciales para el título *{titulo_input}* en esta sede."

    texto = (
        f"*{titulo_input}*\n"
        f"📍 *Sede {sede.capitalize()}*\n\n"
        "Con este título puedes homologar en:\n\n"
    )

    for _, fila in coincidencias.iterrows():
        programa = str(fila["Unnamed: 0"]).upper()
        homologados = int(fila[col_homo])
        pendientes = int(fila[col_pend])

        texto += (
            f"🔹 *{programa}*\n"
            f"➡ Semestres homologados: {homologados}\n"
            f"➡ Semestres por cursar: {pendientes}\n\n"
        )

    if len(coincidencias) == 1:
        texto += (
            "¿Te gustaría recibir más información sobre este programa?\n\n"
            "💡 *Beneficios especiales para egresados SENA en modalidad presencial.*"
        )
    else:
        texto += (
            "¿En cuál de estas opciones te gustaría recibir más información?\n\n"
            "💡 *Beneficios especiales para egresados SENA en modalidad presencial.*"
        )

    return texto


@app.route("/presencial", methods=["GET", "POST"])
@login_required
def presencial_route():
    mensaje = None

    if request.method == "POST":
        titulo = request.form.get("titulo")
        sede = request.form.get("sede")
        mensaje = generar_mensaje_presencial(titulo, sede)

    return render_template(
        "presencial.html",
        titulos=titulos_sena,
        mensaje=mensaje
    )


@app.route("/aguachica/borrar", methods=["POST"])
@login_required
def aguachica_borrar():
    if not session.get("aguachica"):
        return redirect("/aguachica")

    clave = request.form.get("clave")

    if clave == "2907":
        ruta = "aguachica.xlsx"
        if os.path.exists(ruta):
            os.remove(ruta)

    return redirect("/aguachica/dashboard")


@app.route("/precios")
@login_required
def precios():
    return render_template(
        "precios.html",
        programas=get_precios()
    )


# =====================================================
# ESTADÍSTICAS RÁPIDAS
# =====================================================
@app.route("/stats")
@login_required
def stats():
    PRECIOS_PREGRADO = get_precios()
    mensajes_programas = get_mensajes_programas()
    mensajes_sena = get_mensajes_sena()

    valores = [p["valor"] for p in PRECIOS_PREGRADO]
    total_programas_pre = len([m for m in mensajes_programas if m["nivel"] == "pre"])
    total_programas_pos = len([m for m in mensajes_programas if m["nivel"] == "pos"])
    total_titulos = len(set(titulos_sena))

    stats_data = {
        "total_pregrado": total_programas_pre,
        "total_posgrado": total_programas_pos,
        "total_titulos_sena": total_titulos,
        "precio_min": min(valores),
        "precio_max": max(valores),
        "precio_promedio": int(sum(valores) / len(valores)),
        "total_precios": len(PRECIOS_PREGRADO),
        "total_mensajes_sena": len(mensajes_sena),
    }

    return render_template("stats.html", stats=stats_data)

# =====================================================
# FLUJOS DE LLAMADAS
# =====================================================
@app.route("/flujos")
@login_required
def flujos():
    return render_template("flujos.html")


# =====================================================
# PARAMETRIZACIÓN
# =====================================================
@app.route("/parametrizacion")
@login_required
def parametrizacion():
    return render_template("parametrizacion.html")


# =====================================================
# EXPORTAR CSV AGUACHICA
# =====================================================
@app.route("/aguachica/exportar")
@login_required
def aguachica_exportar():
    if not session.get("aguachica"):
        return redirect("/aguachica")

    ruta = "aguachica.xlsx"
    if not os.path.exists(ruta):
        return "No hay datos para exportar", 404

    df = pd.read_excel(ruta)
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=aguachica_datos.csv"}
    )


# =====================================================
# BROCHURES (PÚBLICO)
# =====================================================
@app.route("/brochures")
@login_required
def brochures():
    os.makedirs(BROCHURES_DIR, exist_ok=True)
    archivos = [f for f in os.listdir(BROCHURES_DIR) if f.lower().endswith('.pdf')]
    return render_template("brochures.html", archivos=archivos)


# =====================================================
# ADMIN - LOGIN
# =====================================================
ADMIN_PASSWORD = "Jorsh123"

@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin_login():
    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin/dashboard")
        else:
            error = "Contraseña incorrecta"
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
@login_required
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin")


def admin_required():
    """Check if admin is logged in, return redirect if not."""
    if not session.get("admin"):
        return redirect("/admin")
    return None


# =====================================================
# ADMIN - DASHBOARD
# =====================================================
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    check = admin_required()
    if check:
        return check

    mensajes_programas = get_mensajes_programas()
    mensajes_sena = get_mensajes_sena()
    precios_data = get_precios()
    os.makedirs(PIEZAS_DIR, exist_ok=True)
    os.makedirs(BROCHURES_DIR, exist_ok=True)
    piezas_count = len(os.listdir(PIEZAS_DIR)) if os.path.exists(PIEZAS_DIR) else 0
    brochures_count = len([f for f in os.listdir(BROCHURES_DIR) if f.lower().endswith('.pdf')])

    stats = {
        "mensajes_comerciales": len(mensajes_programas),
        "mensajes_sena": len(mensajes_sena),
        "precios": len(precios_data),
        "piezas": piezas_count,
        "brochures": brochures_count,
    }

    return render_template("admin_dashboard.html", stats=stats)


# =====================================================
# ADMIN - MENSAJES COMERCIALES
# =====================================================
@app.route("/admin/mensajes-comerciales", methods=["GET", "POST"])
@login_required
def admin_mensajes_comerciales():
    check = admin_required()
    if check:
        return check

    mensajes = get_mensajes_programas()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update":
            idx = int(request.form.get("index"))
            if 0 <= idx < len(mensajes):
                mensajes[idx]["titulo"] = request.form.get("titulo", "")
                mensajes[idx]["texto"] = request.form.get("texto", "")
                mensajes[idx]["nivel"] = request.form.get("nivel", "pre")
                save_json("mensajes_programas.json", mensajes)

        elif action == "add":
            nuevo = {
                "nivel": request.form.get("nivel", "pre"),
                "titulo": request.form.get("titulo", ""),
                "texto": request.form.get("texto", ""),
            }
            mensajes.append(nuevo)
            save_json("mensajes_programas.json", mensajes)

        elif action == "delete":
            idx = int(request.form.get("index"))
            if 0 <= idx < len(mensajes):
                mensajes.pop(idx)
                save_json("mensajes_programas.json", mensajes)

        return redirect("/admin/mensajes-comerciales")

    return render_template("admin_mensajes_comerciales.html", mensajes=mensajes)


# =====================================================
# ADMIN - MENSAJES SENA
# =====================================================
@app.route("/admin/mensajes-sena", methods=["GET", "POST"])
@login_required
def admin_mensajes_sena():
    check = admin_required()
    if check:
        return check

    mensajes = get_mensajes_sena()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update":
            idx = int(request.form.get("index"))
            if 0 <= idx < len(mensajes):
                mensajes[idx]["titulo"] = request.form.get("titulo", "")
                mensajes[idx]["texto"] = request.form.get("texto", "")
                save_json("mensajes_sena.json", mensajes)

        elif action == "add":
            nuevo = {
                "titulo": request.form.get("titulo", ""),
                "texto": request.form.get("texto", ""),
            }
            mensajes.append(nuevo)
            save_json("mensajes_sena.json", mensajes)

        elif action == "delete":
            idx = int(request.form.get("index"))
            if 0 <= idx < len(mensajes):
                mensajes.pop(idx)
                save_json("mensajes_sena.json", mensajes)

        return redirect("/admin/mensajes-sena")

    return render_template("admin_mensajes_sena.html", mensajes=mensajes)


# =====================================================
# ADMIN - PRECIOS
# =====================================================
@app.route("/admin/precios", methods=["GET", "POST"])
@login_required
def admin_precios():
    check = admin_required()
    if check:
        return check

    precios_data = get_precios()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update":
            idx = int(request.form.get("index"))
            if 0 <= idx < len(precios_data):
                precios_data[idx]["programa"] = request.form.get("programa", "")
                precios_data[idx]["valor"] = int(request.form.get("valor", 0))
                precios_data[idx]["descuento"] = int(request.form.get("descuento", 0))
                precios_data[idx]["semestres"] = int(request.form.get("semestres", 0))
                save_json("precios.json", precios_data)

        elif action == "add":
            max_id = max([p["id"] for p in precios_data], default=0)
            nuevo = {
                "id": max_id + 1,
                "programa": request.form.get("programa", ""),
                "valor": int(request.form.get("valor", 0)),
                "descuento": int(request.form.get("descuento", 0)),
                "semestres": int(request.form.get("semestres", 0)),
            }
            precios_data.append(nuevo)
            save_json("precios.json", precios_data)

        elif action == "delete":
            idx = int(request.form.get("index"))
            if 0 <= idx < len(precios_data):
                precios_data.pop(idx)
                save_json("precios.json", precios_data)

        return redirect("/admin/precios")

    return render_template("admin_precios.html", precios=precios_data)


# =====================================================
# ADMIN - PIEZAS (SUBIR IMÁGENES CON CARPETAS)
# =====================================================
@app.route("/admin/piezas", methods=["GET", "POST"])
@app.route("/admin/piezas/<path:subfolder>", methods=["GET", "POST"])
@login_required
def admin_piezas(subfolder=""):
    check = admin_required()
    if check:
        return check

    current_dir = os.path.join(PIEZAS_DIR, subfolder)
    # Security: prevent path traversal
    abs_current = os.path.abspath(current_dir)
    abs_base = os.path.abspath(PIEZAS_DIR)
    if not abs_current.startswith(abs_base):
        return redirect("/admin/piezas")

    os.makedirs(current_dir, exist_ok=True)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "upload":
            files = request.files.getlist("imagenes")
            for file in files:
                if file and file.filename and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(current_dir, filename))

        elif action == "delete":
            filename = request.form.get("filename")
            if filename:
                filepath = os.path.join(current_dir, secure_filename(filename))
                if os.path.exists(filepath):
                    os.remove(filepath)

        elif action == "create_folder":
            folder_name = request.form.get("folder_name", "").strip()
            if folder_name:
                safe_name = secure_filename(folder_name)
                if safe_name:
                    new_folder = os.path.join(current_dir, safe_name)
                    os.makedirs(new_folder, exist_ok=True)

        elif action == "delete_folder":
            folder_name = request.form.get("folder_name")
            if folder_name:
                folder_path = os.path.join(current_dir, secure_filename(folder_name))
                if os.path.exists(folder_path) and os.path.isdir(folder_path):
                    import shutil
                    shutil.rmtree(folder_path)

        redirect_url = "/admin/piezas" + ("/" + subfolder if subfolder else "")
        return redirect(redirect_url)

    items = os.listdir(current_dir) if os.path.exists(current_dir) else []
    carpetas = sorted([d for d in items if os.path.isdir(os.path.join(current_dir, d))])
    imagenes = sorted([f for f in items if os.path.isfile(os.path.join(current_dir, f)) and allowed_file(f, ALLOWED_IMAGE_EXTENSIONS)])

    # Build breadcrumb
    breadcrumb = []
    if subfolder:
        parts = subfolder.replace("\\", "/").split("/")
        for i, part in enumerate(parts):
            breadcrumb.append({
                "name": part,
                "path": "/".join(parts[:i+1])
            })

    return render_template(
        "admin_piezas.html",
        carpetas=carpetas,
        imagenes=imagenes,
        subfolder=subfolder,
        breadcrumb=breadcrumb
    )


# =====================================================
# ADMIN - BROCHURES (SUBIR PDF)
# =====================================================
@app.route("/admin/brochures", methods=["GET", "POST"])
@login_required
def admin_brochures():
    check = admin_required()
    if check:
        return check

    os.makedirs(BROCHURES_DIR, exist_ok=True)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "upload":
            files = request.files.getlist("pdfs")
            for file in files:
                if file and file.filename and allowed_file(file.filename, ALLOWED_PDF_EXTENSIONS):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(BROCHURES_DIR, filename))

        elif action == "delete":
            filename = request.form.get("filename")
            if filename:
                filepath = os.path.join(BROCHURES_DIR, secure_filename(filename))
                if os.path.exists(filepath):
                    os.remove(filepath)

        return redirect("/admin/brochures")

    archivos = [f for f in os.listdir(BROCHURES_DIR) if f.lower().endswith('.pdf')]
    return render_template("admin_brochures.html", archivos=archivos)




# =====================================================
# CRUCE - SUBIR EXCEL, GOOGLE SHEETS Y FILTRAR
# =====================================================
CRUCE_DIR = os.path.join(DATA_DIR, "cruce")
CRUCE_FILE = os.path.join(CRUCE_DIR, "cruce_actual.xlsx")
FUNNEL_FILE = os.path.join(CRUCE_DIR, "funnel_actual.xlsx")

GOOGLE_SHEET_ID = "1550YdTkr9XXykOv78RL_V8xLVE6QuJXDemdxneLjO2M"
GOOGLE_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=xlsx"

FUNNEL_SHEET_ID = "1Dd1ByYaOO-s9Vv1kweORctolPc070g_yBY4M_57YWzQ"
FUNNEL_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{FUNNEL_SHEET_ID}/export?format=xlsx"


def clean_cedula(val):
    """Normaliza cédula a texto numérico sin decimales, puntos ni espacios."""
    if pd.isna(val):
        return ""
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2]
    s = s.replace(".", "").replace(",", "").replace(" ", "").replace("-", "")
    return s


def get_funnel_cedulas():
    """Extrae las cédulas de la columna R (índice 17) de la hoja FUNNEL."""
    if not os.path.exists(FUNNEL_FILE):
        return set()
    try:
        xl = pd.ExcelFile(FUNNEL_FILE)
        sheet_target = None
        for s in xl.sheet_names:
            if s.strip().upper() == "FUNNEL":
                sheet_target = s
                break
        if not sheet_target:
            sheet_target = xl.sheet_names[0]

        df_f = pd.read_excel(FUNNEL_FILE, sheet_name=sheet_target)

        # Columna R es el índice 17 (columna 18)
        col_r = None
        if len(df_f.columns) > 17:
            col_r = df_f.columns[17]
        else:
            for col in df_f.columns:
                c_upper = str(col).strip().upper()
                if "CEDULA" in c_upper or "DOCUMENTO" in c_upper or "IDENTIFICACION" in c_upper:
                    col_r = col
                    break

        if col_r is not None:
            ceds = df_f[col_r].dropna().apply(clean_cedula)
            return set(c for c in ceds if c and any(ch.isdigit() for ch in c))
        return set()
    except Exception as e:
        print("Error leyendo FUNNEL:", e)
        return set()


def sync_cruce_from_sheets():
    """Descarga el Excel de GEN NACIONAL directamente de Google Sheets."""
    import requests
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        r = requests.get(GOOGLE_SHEET_URL, headers=headers, timeout=30, allow_redirects=True)
        content_type = r.headers.get("Content-Type", "")

        if r.status_code == 200 and ("spreadsheet" in content_type or len(r.content) > 15000) and not r.text.strip().startswith("<!DOCTYPE"):
            os.makedirs(CRUCE_DIR, exist_ok=True)
            with open(CRUCE_FILE, "wb") as f:
                f.write(r.content)

            df_test = pd.read_excel(CRUCE_FILE, sheet_name="GEN NACIONAL")
            return True, f"¡Sincronización exitosa! Se cargaron {len(df_test):,} registros de GEN NACIONAL."
        elif r.status_code == 401 or "accounts.google.com" in r.url or r.text.strip().startswith("<!DOCTYPE"):
            return False, "El Google Sheet de GEN NACIONAL está en modo privado. Abre el Sheet > Compartir > Cambiar a 'Cualquier persona con el enlace' (Rol: Lector)."
        else:
            return False, f"Respuesta inesperada de Google (HTTP {r.status_code})."
    except Exception as e:
        return False, f"Error al descargar de Google Sheets: {str(e)}"


def sync_funnel_from_sheets():
    """Descarga el Excel de FUNNEL directamente de Google Sheets."""
    import requests
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        r = requests.get(FUNNEL_SHEET_URL, headers=headers, timeout=30, allow_redirects=True)
        content_type = r.headers.get("Content-Type", "")

        if r.status_code == 200 and ("spreadsheet" in content_type or len(r.content) > 10000) and not r.text.strip().startswith("<!DOCTYPE"):
            os.makedirs(CRUCE_DIR, exist_ok=True)
            with open(FUNNEL_FILE, "wb") as f:
                f.write(r.content)
            ceds = get_funnel_cedulas()
            return True, f"¡FUNNEL sincronizado! Se encontraron {len(ceds):,} cédulas en la columna R."
        elif r.status_code == 401 or "accounts.google.com" in r.url or r.text.strip().startswith("<!DOCTYPE"):
            return False, "El Google Sheet de FUNNEL está en modo privado. Abre el Sheet > Compartir > Cambiar a 'Cualquier persona con el enlace' (Rol: Lector)."
        else:
            return False, f"Respuesta inesperada de Google (HTTP {r.status_code})."
    except Exception as e:
        return False, f"Error al descargar FUNNEL: {str(e)}"


@app.route("/cruce", methods=["GET", "POST"])
@login_required
def cruce():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "upload":
            file = request.files.get("archivo")
            if file and file.filename and file.filename.lower().endswith(('.xlsx', '.xls')):
                os.makedirs(CRUCE_DIR, exist_ok=True)
                file.save(CRUCE_FILE)
                return redirect("/cruce")

        elif action == "upload_funnel":
            file = request.files.get("archivo_funnel")
            if file and file.filename and file.filename.lower().endswith(('.xlsx', '.xls')):
                os.makedirs(CRUCE_DIR, exist_ok=True)
                file.save(FUNNEL_FILE)
                return redirect("/cruce")

        elif action == "sync_sheets":
            sync_cruce_from_sheets()
            return redirect("/cruce")

        elif action == "sync_funnel":
            sync_funnel_from_sheets()
            return redirect("/cruce")

        elif action == "delete":
            if os.path.exists(CRUCE_FILE):
                os.remove(CRUCE_FILE)
            return redirect("/cruce")

        elif action == "delete_funnel":
            if os.path.exists(FUNNEL_FILE):
                os.remove(FUNNEL_FILE)
            return redirect("/cruce")

    tiene_archivo = os.path.exists(CRUCE_FILE)
    tiene_funnel = os.path.exists(FUNNEL_FILE)
    cedulas_funnel_total = len(get_funnel_cedulas()) if tiene_funnel else 0

    ultima_actualizacion = ""
    if tiene_archivo:
        mtime = os.path.getmtime(CRUCE_FILE)
        ultima_actualizacion = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %I:%M %p")

    ultima_funnel = ""
    if tiene_funnel:
        mtime_f = os.path.getmtime(FUNNEL_FILE)
        ultima_funnel = datetime.fromtimestamp(mtime_f).strftime("%d/%m/%Y %I:%M %p")

    return render_template(
        "cruce.html",
        tiene_archivo=tiene_archivo,
        tiene_funnel=tiene_funnel,
        cedulas_funnel_total=cedulas_funnel_total,
        ultima_actualizacion=ultima_actualizacion,
        ultima_funnel=ultima_funnel,
        google_sheet_url=f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit?gid=1957374122",
        funnel_sheet_url=f"https://docs.google.com/spreadsheets/d/{FUNNEL_SHEET_ID}/edit?gid=0"
    )


@app.route("/api/cruce/sync-sheets", methods=["POST"])
@login_required
def api_cruce_sync_sheets():
    ok, msg = sync_cruce_from_sheets()
    return jsonify({"ok": ok, "message": msg})


@app.route("/api/cruce/sync-funnel", methods=["POST"])
@login_required
def api_cruce_sync_funnel():
    ok, msg = sync_funnel_from_sheets()
    return jsonify({"ok": ok, "message": msg, "total_cedulas": len(get_funnel_cedulas())})


@app.route("/api/cruce", methods=["GET"])
@login_required
def api_cruce():
    if not os.path.exists(CRUCE_FILE):
        return jsonify({"error": "No hay archivo cargado", "rows": [], "total": 0, "total_en_funnel": 0, "fechas_disponibles": []})

    try:
        df = clean_df(pd.read_excel(CRUCE_FILE, sheet_name="GEN NACIONAL"))
    except Exception as e:
        return jsonify({"error": f"Error leyendo archivo: {str(e)}", "rows": [], "total": 0, "total_en_funnel": 0, "fechas_disponibles": []})

    # Filtro interno estricto: Solo CSU Bogotá Galán, Cundinamarca
    if "CSU" in df.columns:
        df = df[df["CSU"].astype(str).str.lower().str.contains(r"gal[aá\ufffd]n", regex=True, na=False)]
    elif "SEDE" in df.columns:
        df = df[df["SEDE"].astype(str).str.lower().str.contains(r"gal[aá\ufffd]n", regex=True, na=False)]

    # Cruce con Funnel (Cédulas en columna Q)
    cedulas_funnel = get_funnel_cedulas()
    col_cedula = None
    for c in ["CEDULA", "DOCUMENTO", "No. DOCUMENTO", "DOCUMENTO DE IDENTIDAD", "ID"]:
        if c in df.columns:
            col_cedula = c
            break

    if col_cedula and len(cedulas_funnel) > 0:
        df["_en_funnel"] = df[col_cedula].apply(lambda x: clean_cedula(x) in cedulas_funnel)
    else:
        df["_en_funnel"] = False

    # Normalizar columnas de fecha
    for col in ["FECHA DE CARGUE", "FECHA DE GESTION"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Extraer lista de fechas únicas reales en FECHA DE CARGUE (orden descendente)
    fechas_disponibles = []
    if "FECHA DE CARGUE" in df.columns:
        fechas_unicas = df["FECHA DE CARGUE"].dropna().dt.date.unique()
        fechas_sorted = sorted(fechas_unicas, reverse=True)
        fechas_disponibles = [
            {"iso": d.strftime("%Y-%m-%d"), "label": d.strftime("%d/%m/%Y")}
            for d in fechas_sorted
        ]

    # Parámetros de filtro
    fecha_cargue = request.args.get("fecha_cargue", "").strip()
    rango = request.args.get("rango", "todas").strip().lower()
    filtro_radar = request.args.get("radar", "todos").strip().lower()  # todos, en_radar, sin_radar
    busqueda = request.args.get("q", "").strip().upper()

    # Filtrar por FECHA DE CARGUE
    if "FECHA DE CARGUE" in df.columns:
        today = datetime.now().date()
        if fecha_cargue:
            try:
                f_dt = pd.to_datetime(fecha_cargue).date()
                df = df[df["FECHA DE CARGUE"].dt.date == f_dt]
            except Exception:
                pass
        elif rango == "hoy":
            df = df[df["FECHA DE CARGUE"].dt.date == today]
        elif rango == "ayer":
            ayer = today - timedelta(days=1)
            df = df[df["FECHA DE CARGUE"].dt.date == ayer]
        elif rango == "esta_semana":
            inicio_semana = today - timedelta(days=today.weekday())
            fin_semana = inicio_semana + timedelta(days=6)
            df = df[(df["FECHA DE CARGUE"].dt.date >= inicio_semana) & (df["FECHA DE CARGUE"].dt.date <= fin_semana)]
        elif rango == "ultimos_7":
            hace_7 = today - timedelta(days=7)
            df = df[(df["FECHA DE CARGUE"].dt.date >= hace_7) & (df["FECHA DE CARGUE"].dt.date <= today)]
        elif rango == "este_mes":
            df = df[(df["FECHA DE CARGUE"].dt.year == today.year) & (df["FECHA DE CARGUE"].dt.month == today.month)]
        elif rango == "todas":
            pass

    # Filtrar por Estado en Funnel (Radar)
    if filtro_radar == "en_radar":
        df = df[df["_en_funnel"] == True]
    elif filtro_radar == "sin_radar":
        df = df[df["_en_funnel"] == False]

    # Búsqueda global en todas las columnas
    if busqueda:
        mask = df.apply(lambda row: row.astype(str).str.upper().str.contains(busqueda, na=False).any(), axis=1)
        df = df[mask]

    total_en_funnel = int(df["_en_funnel"].sum()) if "_en_funnel" in df.columns else 0

    # Formatear columnas de fecha para visualización legible
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%d/%m/%Y").fillna("")

    df = df.fillna("")
    rows = df.to_dict(orient="records")

    # Lista de columnas a mostrar (sin las columnas técnicas internas que empiezan con _)
    visible_columns = [c for c in df.columns if not c.startswith("_")]

    return jsonify({
        "rows": rows,
        "total": len(rows),
        "total_en_funnel": total_en_funnel,
        "total_cedulas_funnel": len(cedulas_funnel),
        "columns": visible_columns,
        "fechas_disponibles": fechas_disponibles
    })


@app.route("/api/cruce/opciones", methods=["GET"])
@login_required
def api_cruce_opciones():
    return jsonify({"ok": True})



# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    app.run(debug=True, port=8000)

