import pandas as pd
import os
import io
import csv
import json
import uuid
import time
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
presencial = pd.read_excel("Presencial 2026.xlsx")
presencial.columns = presencial.columns.str.strip()

# =====================================================
# CARGAR ACTAS
# =====================================================
actas = pd.read_excel("Actas SENA.xlsx")
actas.columns = actas.columns.str.strip()


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
# TABLÓN DE MENSAJES COLABORATIVO
# =====================================================
TABLON_FILE = "tablon.json"

def get_tablon():
    return load_json(TABLON_FILE)

def save_tablon(data):
    save_json(TABLON_FILE, data)


@app.route("/tablon")
@login_required
def tablon():
    return render_template("tablon.html")


@app.route("/api/tablon", methods=["GET"])
@login_required
def api_tablon_get():
    mensajes = get_tablon()
    return jsonify({"mensajes": mensajes, "total": len(mensajes)})


@app.route("/api/tablon", methods=["POST"])
@login_required
def api_tablon_post():
    data = request.get_json(silent=True) or {}
    titulo = (data.get("titulo") or "").strip()
    texto = (data.get("texto") or "").strip()
    categoria = (data.get("categoria") or "general").strip()
    autor = (data.get("autor") or "").strip()

    if not titulo or not texto:
        return jsonify({"error": "Título y texto son requeridos"}), 400

    # Sanitize inputs
    titulo = titulo[:100]
    texto = texto[:1000]
    autor = autor[:50]

    CATEGORIAS_VALIDAS = {"general", "comercial", "recordatorio", "urgente", "reunion", "anuncio"}
    if categoria not in CATEGORIAS_VALIDAS:
        categoria = "general"

    nuevo = {
        "id": str(uuid.uuid4()),
        "titulo": titulo,
        "categoria": categoria,
        "autor": autor if autor else "Anónimo",
        "texto": texto,
        "timestamp": time.time(),
    }

    mensajes = get_tablon()
    mensajes.append(nuevo)
    save_tablon(mensajes)

    return jsonify({"ok": True, "id": nuevo["id"]}), 201


@app.route("/api/tablon/<msg_id>", methods=["DELETE"])
@login_required
def api_tablon_delete(msg_id):
    mensajes = get_tablon()
    original_len = len(mensajes)
    mensajes = [m for m in mensajes if m.get("id") != msg_id]
    if len(mensajes) == original_len:
        return jsonify({"error": "Mensaje no encontrado"}), 404
    save_tablon(mensajes)
    return jsonify({"ok": True})


# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    app.run(debug=True, port=8000)

