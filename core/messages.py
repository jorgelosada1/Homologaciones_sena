"""Generación de mensajes listos para WhatsApp (formato *negrilla* / _cursiva_)."""
from .text import money


def _saludo(nombre, asesor):
    if not nombre and not asesor:
        return ""
    s = f"¡Hola{(' ' + nombre.strip()) if nombre else ''}! 👋"
    if asesor:
        s += f" Te saluda {asesor.strip()} de la *Universidad Areandina*."
    return s + "\n\n"


def mensaje_homologacion(resultado, cfg, nombre="", incluir_precios=False, asesor=None):
    """Mensaje para la modalidad virtual a partir de `buscar_homologacion`."""
    query = resultado.get("query", "")
    grupos = resultado.get("grupos", [])
    if not grupos:
        return f"No encontré homologaciones para el título *{query}*."
    asesor = cfg.get("nombre_asesor", "") if asesor is None else asesor
    desc = cfg.get("descuento_sena", 20)
    texto = _saludo(nombre, asesor)
    total = 0
    for g in grupos:
        texto += f"*{g['titulo']}*\nCon este título puedes homologar con las siguientes carreras:\n\n"
        for p in g["programas"]:
            total += 1
            texto += (
                f"🔹 *{p['programa_display'].upper()}*\n"
                f"➡ Semestres homologados: {p['homologados']}\n"
                f"➡ Semestres por cursar: {p['faltantes']}\n"
            )
            if incluir_precios and p.get("precio"):
                pr = p["precio"]
                texto += (
                    f"💰 Valor semestre: {money(pr['valor'])}\n"
                    + (f"✅ *Con {pr['descuento']}% {'SENA' if pr.get('tipo_descuento', 'SENA') == 'SENA' else 'de descuento'}: {money(pr['valor_final'])}*\n"
                       if pr['descuento'] else "")
                )
            if incluir_precios and p.get("inicio"):
                texto += f"📅 Inicio de clases: {p['inicio']}\n"
            texto += "\n"
    todos = [p for g in grupos for p in g["programas"]]
    con_precio = [p for p in todos if p.get("precio")]
    con_sena = [p for p in con_precio if p["precio"].get("tipo_descuento", "SENA") == "SENA" and p["precio"]["descuento"]]
    texto += ("¿Te gustaría recibir más información sobre este programa?\n\n" if total == 1
              else "¿De cuál de estas opciones te gustaría recibir más información?\n\n")
    if not con_precio or len(con_sena) == len(con_precio):
        pct = con_sena[0]["precio"]["descuento"] if con_sena else desc
        texto += (f"💡 *Los egresados SENA cuentan con un {pct}% de descuento* en "
                  + ("esta homologación." if total == 1 else "estas homologaciones."))
    elif con_sena:
        nombres = ", ".join(dict.fromkeys(p["programa_display"] for p in con_sena))
        texto += f"💡 *Descuento SENA del {con_sena[0]['precio']['descuento']}%* en {nombres}."
    if incluir_precios:
        texto += "\n✔ Inscripción y estudio de homologación sin costo"
    return texto


def mensaje_precios(programas, cfg):
    con_precio = [p for p in programas if p.get("precio")]
    if not con_precio:
        return "No se encontraron precios para estos programas."
    texto = "🎓 *Precios Universidad Areandina*\n\n"
    for p in con_precio:
        pr = p["precio"]
        es_sena = pr.get("tipo_descuento", "SENA") == "SENA"
        texto += f"📌 *{pr['programa']}*\n💰 Valor: {money(pr['valor'])}\n"
        if pr["descuento"]:
            texto += (f"🏷️ Descuento {'SENA' if es_sena else 'primera vez'}: {pr['descuento']}%\n"
                      f"✅ *Valor con descuento: {money(pr['valor_final'])}*\n")
        texto += (f"📚 Semestres por cursar: {p['faltantes']}\n"
                  f"📅 Inicio de clases: *{p.get('inicio') or cfg.get('inicio_clases')}*\n\n")
    texto += (
        "✔ Inscripción y estudio de homologación sin costo\n\n"
        "_Contamos con diferentes formas de financiación_ 👌"
    )
    return texto


def mensaje_presencial(resultado, cfg, nombre=""):
    query = resultado.get("query", "")
    sedes = resultado.get("sedes", [])
    if not sedes:
        return f"No encontré homologaciones presenciales para el título *{query}*."
    texto = _saludo(nombre, cfg.get("nombre_asesor", ""))
    from .text import tokens
    titulos = resultado.get("titulos", [])
    variantes = {tuple(sorted(set(tokens(t)))) for t in titulos}
    un_titulo = len(variantes) <= 1
    titulo = max(titulos, key=lambda t: sum(w[:1].isupper() for w in t.split())) if titulos and un_titulo else query
    texto += f"*{titulo}*\n\n"
    total = 0
    for s in sedes:
        texto += f"📍 *Sede {s['label']}*\nCon este título puedes homologar en:\n\n"
        for it in s["items"]:
            total += 1
            texto += f"🔹 *{it['programa'].upper()}*\n"
            if not un_titulo:
                texto += f"🎓 Título: {it['titulo']}\n"
            texto += (
                f"➡ Semestres homologados: {it['homologados']}\n"
                f"➡ Semestres por cursar: {it['pendientes']}\n\n"
            )
    texto += ("¿Te gustaría recibir más información sobre este programa?" if total == 1
              else "¿En cuál de estas opciones te gustaría recibir más información?")
    texto += "\n\n💡 *Beneficios especiales para egresados SENA en modalidad presencial.*"
    return texto


def mensaje_oferta(programa, valor, descuento, cfg, semestres=None, homologados=0):
    ahorro = round(valor * descuento / 100)
    final = valor - ahorro
    texto = (
        "🎓 *Oferta Universidad Areandina*\n"
        f"*{programa}* en la *Universidad Areandina* tiene un valor regular de *{money(valor)}* por semestre.\n\n"
        f"Actualmente cuentas con un *{descuento}% de descuento*, lo que representa un ahorro de *{money(ahorro)}*.\n\n"
        f"✅ El valor final de tu matrícula queda en *{money(final)}*.\n"
    )
    if semestres:
        por_cursar = max(int(semestres) - int(homologados or 0), 0)
        if homologados:
            texto += f"📚 Te homologamos *{homologados} semestres*, te faltan *{por_cursar}*.\n"
        texto += f"💵 Inversión total estimada: *{money(final * por_cursar)}*\n"
    texto += (
        f"\n📅 *Inicio de clases:* {cfg.get('inicio_clases')}\n"
        "📌 Cupos limitados. Aprovecha este beneficio exclusivo."
    )
    return texto
