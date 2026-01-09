import pandas as pd
from mensajes_data import mensajes_programas, mensajes_sena
import os
from datetime import datetime, timedelta
from flask import  redirect
from flask import Flask, render_template, request, send_from_directory, session

META_LLAMADAS = 400
META_INSCRITOS = 0  
META_PAGOS = 0


# =====================================================
# CONFIG
# =====================================================
app = Flask(__name__)
app.secret_key = "homologaciones-aguachica-2026"


# =====================================================
# CARGAR ACTAS
# =====================================================
actas = pd.read_excel("Actas SENA.xlsx")
actas.columns = actas.columns.str.strip()

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

    texto += (
        "¿De cual de estas opciones te gustaria recibir mas informacion?\n\n"
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
        df = pd.DataFrame(columns=["fecha","ejecutivo","llamadas","inscritos","pagos"])

    df["fecha"] = pd.to_datetime(df["fecha"])
    semana = df[df["fecha"] >= datetime.now() - timedelta(days=7)]

    totales = (
        semana
        .groupby("ejecutivo")[["llamadas", "inscritos", "pagos"]]
        .sum()
        .reset_index()
    )

    resumen = semana[["llamadas", "inscritos", "pagos"]].sum().fillna(0)

    def semaforo(valor, meta):
        if valor >= meta:
            return "verde"
        elif valor >= meta * 0.7:
            return "amarillo"
        else:
            return "rojo"

    estado = {
        "llamadas": semaforo(resumen["llamadas"], META_LLAMADAS),
        "inscritos": semaforo(resumen["inscritos"], META_INSCRITOS),
        "pagos": semaforo(resumen["pagos"], META_PAGOS),
    }

    return render_template(
        "aguachica.html",
        datos=semana,
        totales=totales,
        resumen=resumen,
        estado=estado,
        metas={
            "llamadas": META_LLAMADAS,
            "inscritos": META_INSCRITOS,
            "pagos": META_PAGOS
        }
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





# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    app.run(debug=True, port=8000)
