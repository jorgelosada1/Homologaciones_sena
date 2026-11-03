"""Envío asistido de WhatsApp.

En el servidor se usa un flujo seguro basado en enlaces wa.me (el asesor abre cada
chat y envía). El bot de escritorio (`whatsapp_masivo.py`, Windows + pyautogui) solo
se habilita si la app corre en Windows y WHATSAPP_DESKTOP_BOT=1.
"""
import os
import subprocess
import sys

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

whatsapp_bp = Blueprint("whatsapp", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DESKTOP_BOT = sys.platform.startswith("win") and os.environ.get("WHATSAPP_DESKTOP_BOT", "0") == "1"


@whatsapp_bp.route("/whatsapp", methods=["GET", "POST"])
def whatsapp():
    if not session.get("logged_in"):
        return redirect(url_for("global_login", next="/whatsapp"))
    if request.method == "POST" and DESKTOP_BOT:
        numeros = request.form.get("numeros", "")
        usar_imagen = request.form.get("usar_imagen", "no")
        with open(os.path.join(BASE_DIR, "numeros.txt"), "w", encoding="utf-8") as f:
            f.write(numeros.strip())
        with open(os.path.join(BASE_DIR, "config.txt"), "w", encoding="utf-8") as f:
            f.write(usar_imagen)
        subprocess.Popen([sys.executable, "whatsapp_masivo.py"], cwd=BASE_DIR)
        return redirect("/whatsapp?bot=1")
    store = current_app.extensions["homologaciones_store"]
    plantillas = (
        [{"grupo": "Pregrado" if m.get("nivel") == "pre" else "Posgrado", "titulo": m["titulo"], "texto": m["texto"]}
         for m in store.render_list(store.mensajes_programas())]
        + [{"grupo": "SENA", "titulo": m["titulo"], "texto": m["texto"]} for m in store.render_list(store.mensajes_sena())]
    )
    for i, p in enumerate(plantillas):
        p["idx"] = i
    return render_template("whatsapp.html", plantillas=plantillas, desktop_bot=DESKTOP_BOT,
                           bot_iniciado=request.args.get("bot") == "1")
