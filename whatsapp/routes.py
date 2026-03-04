from flask import Blueprint, render_template, request, redirect
import subprocess
import os

whatsapp_bp = Blueprint("whatsapp", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@whatsapp_bp.route("/whatsapp", methods=["GET", "POST"])
def whatsapp():
    if request.method == "POST":
        numeros = request.form["numeros"]
        usar_imagen = request.form.get("usar_imagen", "no")

        with open(os.path.join(BASE_DIR, "numeros.txt"), "w", encoding="utf-8") as f:
            f.write(numeros.strip())

        with open(os.path.join(BASE_DIR, "config.txt"), "w", encoding="utf-8") as f:
            f.write(usar_imagen)

        subprocess.Popen(
            ["python", "whatsapp_masivo.py"],
            cwd=BASE_DIR
        )

        return redirect("/whatsapp")

    return render_template("whatsapp.html")
