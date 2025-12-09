import pandas as pd
from flask import Flask, render_template_string, request, send_from_directory

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
# FUNCIÓN PRINCIPAL
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
        return f"No encontré homologaciones para el título: {titulo_input}"

    if len(coincidencias) > 1:
        texto = (
            f"<h3><b>{titulo_input}</b></h3>"
            f"Con este título puedes homologar con las siguientes carreras:<br><br>"
        )

        for _, fila in coincidencias.iterrows():
            carrera = str(fila['gest']).strip().upper()
            homologados = int(fila['SEMTR HOMOLOGADOS'])
            faltantes = int(fila['FALTANTES'])

            texto += (
                f"🔹 <b>{carrera}</b><br>"
                f"➡ Semestres homologados: <b>{homologados}</b><br>"
                f"➡ Semestres por cursar: <b>{faltantes}</b><br><br>"
            )

        texto += "<br><b>¿De cual de estas opciones te gustaria recibir mas informacion?</b>"
        return texto

    fila = coincidencias.iloc[0]
    carrera = str(fila["gest"]).strip().upper()
    homologados = int(fila["SEMTR HOMOLOGADOS"])
    faltantes = int(fila["FALTANTES"])

    return (
        f"Puedes homologar el título <b>{titulo_input}</b> con <b>{carrera}</b>.<br>"
        f"➡ Semestres homologados: <b>{homologados}</b><br>"
        f"➡ Semestres por cursar: <b>{faltantes}</b><br><br>"
        f"¿Qué tal te pareció esta información?"
    )

# =====================================================
# SERVIDOR FLASK
# =====================================================
app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Homologaciones SENA</title>
    <link rel="icon" type="image/jpeg" href="/logo.jpg">
    <style>
        body {
            font-family: Arial;
            background: #f4f6f9;
            padding: 30px;
        }
        .container {
            width: 550px;
            margin: auto;
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0px 2px 10px rgba(0,0,0,0.15);
        }
        input {
            width: 100%;
            padding: 12px;
            font-size: 16px;
            border-radius: 8px;
            border: 1px solid #ccc;
        }
        button {
            margin-top: 10px;
            width: 100%;
            padding: 12px;
            background: #2563eb;
            color: white;
            border: none;
            font-size: 18px;
            border-radius: 8px;
            cursor: pointer;
        }
        button:hover {
            background: #1d4ed8;
        }
        .result {
            margin-top: 20px;
            padding: 20px;
            background: #eef2ff;
            border-radius: 10px;
            border-left: 5px solid #3b82f6;
        }
        .copy-btn {
            background: #10b981;
            margin-top: 10px;
        }
        .copy-btn:hover {
            background: #059669;
        }
    </style>
</head>
<body>

<div class="container">
    <h2>Buscador de Homologaciones SENA</h2>
    <form method="POST">
        <input list="titulos" name="titulo" placeholder="Escribe tu título aquí..." required>
        <datalist id="titulos">
            {% for t in titulos %}
                <option value="{{ t }}">
            {% endfor %}
        </datalist>
        <button type="submit">Buscar</button>
    </form>

    {% if resultado %}
        <div class="result" id="resultado">{{ resultado|safe }}</div>
        <button class="copy-btn" onclick="copiarTexto()">📋 Copiar</button>
    {% endif %}
</div>

<script>
function copiarTexto() {
    const content = document.getElementById("resultado").innerText;
    navigator.clipboard.writeText(content).then(() => {
        alert("Mensaje copiado 👍");
    });
}
</script>

</body>
</html>
"""

@app.route("/logo.jpg")
def favicon():
    return send_from_directory(".", "logo.jpg")

@app.route("/", methods=["GET", "POST"])
def index():
    resultado = None

    if request.method == "POST":
        titulo = request.form.get("titulo")
        mensaje_base = generar_mensaje(titulo)
        resultado = f"{mensaje_base}<br><br>💡 Los egresados SENA cuentan con un <b>20% de descuento</b> en estas homologaciones."
    
    return render_template_string(HTML, resultado=resultado, titulos=titulos_sena)

if __name__ == "__main__":
    app.run(debug=True, port=8000)
