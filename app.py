import pandas as pd
from mensajes_data import mensajes_programas, mensajes_sena
import os
import io
import csv
import json
from datetime import datetime, timedelta
from flask import redirect, Response
from flask import Flask, render_template, request, send_from_directory, session
from whatsapp import whatsapp_bp



# =====================================================
# CONFIG
# =====================================================
app = Flask(__name__)
app.secret_key = "homologaciones-aguachica-2026"

app.register_blueprint(whatsapp_bp)

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
# PRECIOS PREGRADO (JSON)
# =====================================================
PRECIOS_PREGRADO = [
    {"id": 1, "programa": "Psicología Virtual", "valor": 3030000, "descuento": 0, "semestres": 10},
    {"id": 2, "programa": "Comunicación Social", "valor": 2600000, "descuento": 15, "semestres": 8},
    {"id": 3, "programa": "Economía", "valor": 2730000, "descuento": 20, "semestres": 8},
    {"id": 4, "programa": "Tecnología Gestión Talento Humano", "valor": 2240000, "descuento": 20, "semestres": 6},
    {"id": 5, "programa": "Tecnología Logística", "valor": 1990000, "descuento": 15, "semestres": 6},
    {"id": 6, "programa": "Tecnología Producción Ganadería Sostenible", "valor": 1440000, "descuento": 20, "semestres": 6},
    {"id": 7, "programa": "Marketing de Negocios", "valor": 2730000, "descuento": 20, "semestres": 8},
    {"id": 8, "programa": "Administración de Empresas", "valor": 2610000, "descuento": 30, "semestres": 8},
    {"id": 9, "programa": "Finanzas y Negocios Internacionales", "valor": 2610000, "descuento": 20, "semestres": 8},
    {"id": 10, "programa": "Ingeniería de Sistemas Virtual", "valor": 3010000, "descuento": 15, "semestres": 10},
    {"id": 11, "programa": "Ingeniería Industrial", "valor": 2850000, "descuento": 20, "semestres": 9},
    {"id": 12, "programa": "Lic. en Ciencias Sociales", "valor": 2710000, "descuento": 30, "semestres": 9},
    {"id": 13, "programa": "Lic. en Educación Infantil", "valor": 2750000, "descuento": 30, "semestres": 9},
    {"id": 14, "programa": "Administración en Salud", "valor": 2330000, "descuento": 0, "semestres": 8},
    {"id": 15, "programa": "Derecho", "valor": 2210000, "descuento": 20, "semestres": 10},
    {"id": 16, "programa": "Administración Pública", "valor": 2330000, "descuento": 30, "semestres": 8},
    {"id": 17, "programa": "Ingeniería de Software", "valor": 2740000, "descuento": 15, "semestres": 9},
    {"id": 18, "programa": "Seguridad y Salud en el Trabajo", "valor": 2470000, "descuento": 10, "semestres": 8},
    {"id": 19, "programa": "Sociología", "valor": 2000000, "descuento": 20, "semestres": 8},
]



# =====================================================
# LISTA DE TÍTULOS PARA AUTOCOMPLETADO
# =====================================================
titulos_sena = [
    "Técnico en Asistencia Administrativa",
    "Técnico en Contabilización de Operaciones Comerciales y Financieras",
    "Técnico en Asesoría Comercial y Operaciones de Entidades Financieras",
    "Técnico en Nómina y Prestaciones Sociales",
    "Técnico en Asistencia en Organización de Archivos",
    "Técnico en Logística Empresarial",
    "Técnico en Venta de Productos y Servicios",
    "Técnico en Comercialización de Productos Masivos",
    "Técnico en Asistencia en Análisis y Producción de información Administrativa",
    "Técnico en Recursos Humanos",
    "Técnico en Compras y Suministros",
    "Técnico Profesional en Asistencia en la Administración de Recursos Físicos",
    "Técnico en Operaciones Comerciales",
    "Técnico en Gestión Comercial y telemercadeo en Contact Center",
    "Técnico en Operación de Servicios de Contact Center",
    "Técnico en Producción de Información Administrativa",
    "Técnico en Integración de Operaciones Logísticas",
    "Tecnología en Gestión de Empresas Agropecuarias",
    "Técnico en Asesoría Comercial",
    "Técnico en Ofimática",
    "Técnico en Venta de Productos y Servicios Financieros",
    "Técnico en Apoyo Administrativo en Salud",
    "Técnico en Asistencia en la Función Pública",
    "Técnico en Desarrollo de Operaciones Logísticas en la Cadena de Abastecimiento",
    "Técnico en Operaciones Comerciales en Retail",
    "Técnico en Programación para Analitica de Datos",
    "Técnico en Proyectos Agropecuarios",
    "Técnico en Produccion Agropecuaria",
    "Técnico en Servicios y Operaciones Microfinancieras",
    "Tecnología en Gestión Financiera y de Tesorería",
    "Tecnología en Administración Hotelera",
    "Tecnología en Gestión Integral del Riesgo en Seguros",
    "Tecnología en Gestión del Talento Humano",
    "Tecnología en Gestión Bancaria y de Entidades Financieras",
    "Tecnología en Gestión Administrativa",
    "Tecnología en Administración Empresarial",
    "Tecnología en Formulación de Proyectos",
    "Tecnología en Gestión de Negocios",
    "Tecnología en Negociación Internacional",
    "Tecnología en Contabilidad y Finanzas",
    "Tecnología en Producción Multimedia",
    "Tecnología en Comunicación Comercial",
    "Tecnología en Dirección de Ventas",
    "Tecnología en Gestión para el Establecimiento de Alimentos y Bebidas",
    "Tecnología en Control Ambiental",
    "Tecnología en Gestión de Mercados",
    "Tecnología en Gestión Empresarial",
    "Tecnología en Gestión Hotelera",
    "Tecnología en Gestión Logística",
    "Tecnología en Administración Bancaria y de Instituciones Financieras",
    "Tecnología en Administración Documental",
    "Tecnología en Gestión Documental",
    "Tecnología en Gestión de Negocios Fiduciarios",
    "Tecnología en Administración de Empresas Bananeras",
    "Tecnología en Gestión de Procesos Administrativos de Salud",
    "Tecnología en Administración de Empresas Agropecuarias",
    "Tecnología en Gestión Integral en Fondos de Pensiones y Cesantías",
    "Tecnología en Gestión Contable y Financiera",
    "Tecnología en Gestión de Proyectos de Desarrollo Económico y Social",
    "Tecnología en Biocomercio Sostenible",
    "Tecnología en Distribución Física Internacional",
    "Tecnología en Gestión Contable y de Información Financiera",
    "Tecnología en Gestión de la Producción Industrial",
    "Tecnología en Gestión de Recursos en Plantas de Producción",
    "Tecnología en Organización de Eventos",
    "Tecnología en Coordinación de Procesos Logísticos",
    "Tecnología en Gestión Integrada de la Calidad, Medio Ambiente, Seguridad y Salud Ocupacional",
    "Técnico en Contabilización de Operaciones Comerciales y Financieras",
    "Técnico en Desarrollo de Operaciones Logísticas en la Cadena de Abastecimiento",
    "Técnico en Comercio Internacional",
    "Técnico en Compras y Suministros",
    "Técnico en Asesoría Comercial",
    "Tecnología en Distribución Física Internacional",
    "Tecnología en Gestión Bancaria y de Entidades Financieras",
    "Tecnología en Gestión Logística",
    "Tecnología en Gestión Empresarial",
    "Tecnología en Gestión de Negocios",
    "Tecnología en Gestión Portuaria",
    "Tecnología en Logística del Transporte",
    "Tecnología en Negociación Internacional",
    "Tecnología en Gestión Contable y de Información Financiera",
    "Tecnología en Coordinación de Procesos Logísticos",
    "Tecnología en Gestión Contable y Financiera",
    "Tecnología en Gestión Financiera y de Tesorería",
    "Tecnología en Gestión del Comercio Exterior de Bienes y Servicios",
    "Tecnología en Gestión de Operaciones en Terminales Portuarias",
    "Tecnología en Gestión de Recursos en Plantas de Producción",
    "Tecnología en Gestión de Tesorería y Recursos Financieros",
    "Técnico en Sistemas",
    "Técnico en Instalación de Redes de Computadores",
    "Técnico en Instalación de Redes Internas de Telecomunicaciones",
    "Técnico en Instalación y Mantenimiento de Redes Internas de Telecomunicaciones",
    "Técnico en Mantenimiento de Equipos de Computo",
    "Técnico en Programación de Software",
    "Tecnología en Producción Multimedia",
    "Tecnología en Telecomunicaciones",
    "Tecnología en Análisis y Desarrollo de Sistemas de Información",
    "Tecnología en Administración del Ensamble y Mantenimiento de Computadores y Redes",
    "Tecnología en Gestión de Redes de Datos",
    "Tecnología en Administración de Redes de Computadores",
    "Tecnología en Análisis y Desarrollo de Software",
    "Tecnología en Diseño, Implementación y Mantenimiento de Telecomunicaciones",
    "Tecnología en Implementación de Infraestructura de Tecnologías de la Información y las Comunicaciones",
    "Tecnología en Mantenimiento de Equipos de Computo, Diseño e Instalación de Cableado Estructurado",
    "Tecnología en Desarrollo de Medios Gráficos Visuales",
    "Tecnología en Dibujo y Modelado Arquitectónico y de Ingeniería",
    "Tecnología en Supervisión de Redes de Distribución de Energía Eléctrica",
    "Tecnología en Implementación de Infraestructura de Tecnologías de la Información y las Comunicaciones",
    "Tecnología en Gobierno Local",
    "Tecnología en Salud Ocupacional",
    "Tecnología en Mantenimiento Mecatrónico de Automotores",
    "Tecnología en Mantenimiento Electromecánico Industrial",
    "Tecnología en Control Ambiental",
    "Tecnología SG Calidad, Medio ambiente y SST",
    "Tecnología en Gestión del Talento Humano",
    "Tecnología en Gestión Administrativa",
    "Tecnología en Gestión de Mercados",
    "Tecnología en Gestión Empresarial",
    "Tecnología en Gestión Logística",
    "Tecnología en Logística del Transporte",
    "Tecnología en Coordinación de Procesos Logísticos",
    "Tecnología en Gestión de la Seguridad y Salud en el Trabajo",
    "Tecnología en Diseño de Elementos Mecánicos para su Fabricación con Máquinas Herramientas CNC",
    "Tecnología en Diseño e Integración de Automatismos Mecatrónicos",
    "Tecnología en Control de Calidad de Alimentos",
    "Tecnología en Análisis y Desarrollo de Sistemas de Información",
    "Tecnología en Prevención y Control Ambiental",
    "Tecnología en Gestión de Recursos Naturales",
    "Tecnología en Mantenimiento Electrónico e Instrumental Industrial",
    "Tecnología en Producción Agrícola",
    "Tecnología en Electricidad Industrial",
    "Tecnología en Química Aplicada a la Industria",
    "Tecnología en Gestión de la Producción Industrial",
    "Técnico en Atención Integral a la Primera Infancia",
    "Técnico en Atención Integral a la Primera Infancia",
    "Tecnología en Formulación de Proyectos",
    "Tecnología en Comunicación Comercial",
    "Tecnología en Dirección de Ventas",
    "Tecnología en Dirección Comercial",
    "Tecnología en Gestión de Mercados",
    "Tecnología en Biocomercio Sostenible",
    "Tecnología en Gestión Comercial de Servicios"
]

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
        carrera = str(fila["gest"]).upper()
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
# RUTAS
# =====================================================
@app.route("/logo.jpg")
def logo():
    return send_from_directory(".", "logo.jpg")


@app.route("/", methods=["GET", "POST"])
def homologaciones():
    mensaje = None

    if request.method == "POST":
        titulo = request.form.get("titulo")
        mensaje = generar_mensaje(titulo)
        session["ultimo_mensaje"] = mensaje

    return render_template(
        "homologaciones.html",
        titulos=titulos_sena,
        mensaje=mensaje
    )


@app.route("/mensajes")
def mensajes():
    filtro = request.args.get("nivel", "pre")

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
def sena():
    q = request.args.get("q", "").lower()

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
def piezas():
    carpeta = "static/piezas"
    imagenes = os.listdir(carpeta)

    return render_template(
        "piezas.html",
        imagenes=imagenes
    )

@app.route("/aguachica", methods=["GET", "POST"])
def aguachica_login():
    if request.method == "POST":
        user = request.form.get("user")
        password = request.form.get("password")

        if user == "csu-aguachica" and password == "1234":
            session["aguachica"] = True
            return redirect("/aguachica/dashboard")

    return render_template("aguachica_login.html")


@app.route("/aguachica/dashboard", methods=["GET", "POST"])
def aguachica_dashboard():
    if not session.get("aguachica"):
        return redirect("/aguachica")

    ruta = "aguachica.xlsx"

    # =========================
    # GUARDAR DATOS
    # =========================
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

    # =========================
    # LEER DATOS
    # =========================
    if os.path.exists(ruta):
        df = pd.read_excel(ruta)
    else:
        df = pd.DataFrame(columns=["fecha", "ejecutivo", "llamadas", "inscritos", "pagos"])

    df["fecha"] = pd.to_datetime(df["fecha"])
    semana = df[df["fecha"] >= datetime.now() - timedelta(days=7)]

    # =========================
    # TOTALES POR EJECUTIVO
    # =========================
    totales = (
        semana
        .groupby("ejecutivo")[["llamadas", "inscritos", "pagos"]]
        .sum()
        .reset_index()
    )

    # =========================
    # METAS INDIVIDUALES
    # =========================
    METAS_EJECUTIVOS = {
        "Jorge": {"llamadas": 400, "inscritos": 0, "pagos": 11},
        "Maria": {"llamadas": 350, "inscritos": 0, "pagos": 11},
        "Ana":   {"llamadas": 300, "inscritos": 0, "pagos": 11},
    }

    # Ejecutivo seleccionado para la gráfica
    ejecutivo_sel = request.args.get("ejecutivo", "Jorge")

    resumen_individual = (
        semana[semana["ejecutivo"] == ejecutivo_sel][
            ["llamadas", "inscritos", "pagos"]
        ]
        .sum()
        .fillna(0)
    )

    meta_individual = METAS_EJECUTIVOS.get(ejecutivo_sel)

    # =========================
    # RESUMEN GENERAL (opcional)
    # =========================
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

    # =========================
    # RENDER
    # =========================
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


# =====================================================
# RUTA PRESENCIAL
# =====================================================
@app.route("/presencial", methods=["GET", "POST"])
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
def precios():
    return render_template(
        "precios.html",
        programas=PRECIOS_PREGRADO
    )


# =====================================================
# ESTADÍSTICAS RÁPIDAS
# =====================================================
@app.route("/stats")
def stats():
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
# PARAMETRIZACIÓN
# =====================================================
@app.route("/parametrizacion")
def parametrizacion():
    return render_template("parametrizacion.html")


# =====================================================
# EXPORTAR CSV AGUACHICA
# =====================================================
@app.route("/aguachica/exportar")
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
# MAIN
# =====================================================
if __name__ == "__main__":
    app.run(debug=True, port=8000)
