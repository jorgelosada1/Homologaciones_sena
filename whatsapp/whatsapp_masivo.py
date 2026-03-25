import pyautogui
import pyperclip
import time
import os
import psutil
import random
from PIL import Image
import win32clipboard
from io import BytesIO

# ================= CONFIG =================
X_CAJA, Y_CAJA = 953, 980
IMAGEN = "image.jpg"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ================= IMAGEN AL PORTAPAPELES =================
def copiar_imagen_al_portapapeles(ruta_imagen):
    image = Image.open(ruta_imagen)
    output = BytesIO()
    image.convert('RGB').save(output, 'BMP')
    data = output.getvalue()[14:]
    output.close()

    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    win32clipboard.CloseClipboard()

# ================= CERRAR VENTANAS EXTRA =================
def cerrar_otras_ventanas_whatsapp():
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] and "chrome" in proc.info['name'].lower():
                if proc.info['cmdline'] and any("web.whatsapp.com" in arg for arg in proc.info['cmdline']):
                    proc.kill()
        except:
            continue

# ================= LEER CONFIG IMAGEN =================
usar_imagen = "no"
config_path = os.path.join(BASE_DIR, "config.txt")
if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        usar_imagen = f.read().strip().lower()

# ================= LEER CONTACTOS =================
contactos = []
with open(os.path.join(BASE_DIR, "numeros.txt"), "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            try:
                nombre, numero, programa = line.strip().split(",", 2)
                contactos.append(
                    (nombre.strip(), numero.strip().replace(" ", ""), programa.strip())
                )
            except ValueError:
                print("⚠️ Línea inválida:", line)

# ================= LEER MENSAJES =================
with open(os.path.join(BASE_DIR, "mensajes.txt"), "r", encoding="utf-8") as f:
    contenido = f.read()

mensajes = [m.strip() for m in contenido.split('---') if m.strip()]
if not mensajes:
    raise Exception("❌ mensajes.txt está vacío")

# ================= ABRIR WHATSAPP WEB =================
print("🌐 Abriendo WhatsApp Web...")
os.system('start chrome --new-window "https://web.whatsapp.com"')
time.sleep(20)

# ================= ENVÍO =================
for i, (nombre, numero, programa) in enumerate(contactos):
    print(f"📲 Enviando a {nombre} ({numero})")

    cerrar_otras_ventanas_whatsapp()

    os.system(f'start chrome "https://web.whatsapp.com/send?phone={numero}"')
    time.sleep(20)

    pyautogui.click(X_CAJA, Y_CAJA)
    time.sleep(3)

    # ===== ENVIAR IMAGEN SOLO SI ESTA ACTIVADO =====
    if usar_imagen == "si":
        imagen_path = os.path.join(BASE_DIR, IMAGEN)
        if os.path.exists(imagen_path):
            copiar_imagen_al_portapapeles(imagen_path)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(8)
        else:
            print("⚠️ Imagen activada pero no existe image.jpg")

    # ===== MENSAJE =====
    mensaje_base = mensajes[i % len(mensajes)]
    mensaje = mensaje_base.replace("{nombre}", nombre).replace("{programa}", programa)

    pyperclip.copy(mensaje)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(2)

    pyautogui.press("enter")
    print("✅ Mensaje enviado")

    # ===== DELAY RANDOM ENTRE 2 Y 3 MIN =====
    delay_random = random.uniform(120, 180)
    print(f"⏳ Esperando {int(delay_random)} segundos...")
    time.sleep(delay_random)

print("🎉 Proceso finalizado correctamente")
