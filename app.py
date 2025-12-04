import pandas as pd
from flask import Flask, render_template_string, request

# =====================================================
# CARGAR ACTAS
# =====================================================
actas = pd.read_excel("Actas SENA.xlsx")
actas.columns = actas.columns.str.strip()

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

    # Varias opciones
    if len(coincidencias) > 1:
        texto = (
            f"<h3>Resultados para <b>{titulo_input}</b></h3>"
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

        texto += "<br><b>¿Con cuál carrera te gustaría continuar?</b>"
        return texto

    # Solo una opción
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
        <input type="text" name="titulo" placeholder="Escribe tu título aquí..." required>
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

@app.route("/", methods=["GET", "POST"])
def index():
    resultado = None

    if request.method == "POST":
        titulo = request.form.get("titulo")
        resultado = generar_mensaje(titulo)

    return render_template_string(HTML, resultado=resultado)


if __name__ == "__main__":
    app.run(debug=True, port=8000)
