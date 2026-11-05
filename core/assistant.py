"""Asistente para asesores.

Funciona siempre en modo local (reglas + datos de actas/precios). Si se define la
variable de entorno ANTHROPIC_API_KEY y el paquete `anthropic` está instalado,
usa Claude con los mismos datos como contexto.
"""
import logging
import os

from .data import buscar_homologacion
from .text import money, norm, program_similarity, similarity, tokens

log = logging.getLogger(__name__)

ASSISTANT_MODEL = os.environ.get("ASSISTANT_MODEL", "claude-opus-5-5")

GUIA = """
LÍNEAS DE ADMISIÓN
- PRE Primera vez: nunca ha cursado estudios universitarios.
- PRE SENA: tiene título SENA y homologa. Se inscribe en FDI como "SENA primera vez". Al finalizar se descarga el acta de homologación para que el estudiante la firme a mano.
- Transferencia externa: viene de otra universidad sin convenio; se crea caso en HubSpot indicando "transferencia externa".
- POS Normal: especialización o maestría. POS Extensión: tomó créditos de la especialización como opción de grado; caso en HubSpot "extensión".
DOCUMENTOS
- PRE Primera vez: cédula, EPS, título de bachiller, ICFES.
- PRE SENA: cédula, EPS, título SENA, acta de homologación firmada a mano, nota SENA.
- POS Normal: cédula, EPS, título de pregrado. POS Extensión: lo mismo + caso HubSpot.
- SENA pendiente de grado: firma compromiso de entregar el título en 4 meses.
INSCRIPCIÓN
1) Inscripción en FDI: pregrado https://fdifuaa.ilumno.com/inscripcion/pregrado/home/andina/pregrado ; posgrado https://fdifuaa.ilumno.com/inscripcion/pregrado/home/andina/posgrado
2) Cargue de documentos en FDI. 3) Caso en HubSpot solo para transferencia externa y extensión. 4) Seguimiento en Tablero-2027.
HUBSPOT: para ver cómo pagó el prospecto debes ser propietario del negocio, o el negocio debe estar en Bogotá con tu CSU en el campo "site". Deja 4 actividades de seguimiento en fechas diferentes.
ZOHO: registrar toda gestión. Estados: Inscrito pendiente revisión docs → Admitido → MTR (matrícula en trámite) → Matriculado (cuando paga). En los tres primeros estados registrar también en el Excel Funnel.
"""

_FAQ = [
    (("documento", "papeles", "requisito"), "📄 *Documentos PRE SENA:* cédula, EPS, título SENA, acta de homologación firmada a mano (la entregamos nosotros) y nota SENA.\n\nSi está *pendiente de grado* puede inscribirse firmando un compromiso de entregar el título en 4 meses."),
    (("inscrib", "inscripcion", "fdi", "link", "enlace"), "📝 *Inscripción en FDI*\n• Pregrado: https://fdifuaa.ilumno.com/inscripcion/pregrado/home/andina/pregrado\n• Posgrado: https://fdifuaa.ilumno.com/inscripcion/pregrado/home/andina/posgrado\n\nLos egresados SENA se inscriben como *SENA primera vez*. Luego se cargan documentos en la misma plataforma."),
    (("hubspot", "propietario", "negocio"), "🟠 *HubSpot:* para ver cómo pagó el prospecto debes ser *propietario del negocio*, o el negocio debe estar en Bogotá con tu CSU en el campo *site*. Deja *4 actividades de seguimiento* en fechas diferentes."),
    (("zoho", "estado", "crm"), "🟣 *Zoho:* registra toda gestión. Estados: Inscrito pendiente revisión docs → Admitido → MTR → *Matriculado* (cuando paga). En los primeros tres estados regístralo también en el *Excel Funnel*."),
    (("transferencia",), "🔁 *Transferencia externa:* viene de otra universidad sin convenio. Se aplica a estudio de homologación y se crea un *caso en HubSpot* indicando \"transferencia externa\"."),
    (("extension", "extensión", "posgrado"), "🎓 *Posgrado extensión:* el estudiante tomó créditos de la especialización como opción de grado. Documentos: cédula, EPS, título de pregrado + *caso en HubSpot* \"extensión\"."),
]


def _fmt_homologacion(res, cfg):
    lines = []
    for g in res["grupos"]:
        lines.append(f"🎓 *{g['titulo']}* homologa en:")
        for p in g["programas"]:
            l = f"• *{p['programa_display']}*: {p['homologados']} semestres homologados, {p['faltantes']} por cursar"
            if p.get("precio"):
                l += f" — {money(p['precio']['valor_final'])}/sem con {p['precio']['descuento']}% SENA"
            lines.append(l)
    return "\n".join(lines)


def _match_title(question, titles):
    best, best_sc = None, 0.0
    qtok = set(tokens(question))
    for t in titles:
        tt = tokens(t)
        if not tt:
            continue
        sc = similarity(t, question)
        # recompensa títulos cuyos tokens aparecen casi todos en la pregunta
        cover = sum(1 for x in tt if x in qtok) / len(tt)
        sc = max(sc, cover * 0.95)
        if sc > best_sc or (sc == best_sc and best and len(t) > len(best)):
            best, best_sc = t, sc
    return best if best_sc >= 0.75 else None


FECHA_KEYS = ("FECHA", "INICIO", "INICIA", "EMPIEZA", "ARRANCA", "CLASES", "COHORTE", "INSCRIPCION", "INDUCCION", "CIERRA", "CUANDO")


def _fmt_cohorte(c):
    from datetime import date
    from .parametrizacion import fecha_larga
    f = c["fechas"]
    partes = [f"*Cohorte {c['corto']}*: clases desde {fecha_larga(date.fromisoformat(f['clases']['desde']))}"]
    ins = f.get("inscripcion") or {}
    if ins.get("hasta"):
        partes.append(f"inscripciones hasta {fecha_larga(date.fromisoformat(ins['hasta']))}")
    ind = f.get("induccion") or {}
    if ind.get("desde") and ind.get("hasta"):
        d1, d2 = date.fromisoformat(ind["desde"]), date.fromisoformat(ind["hasta"])
        partes.append(f"inducción del {d1.day} al {fecha_larga(d2)}" if d1.month == d2.month else f"inducción del {fecha_larga(d1)} al {fecha_larga(d2)}")
    return " · ".join(partes)


def calendario_texto(store):
    """Resumen del calendario de cohortes para el asistente."""
    lineas = []
    for tipo, b in store.param.bloques():
        nombre = {"pregrado": "PREGRADO", "especializaciones": "ESPECIALIZACIONES", "maestrias": "MAESTRÍAS"}[tipo]
        lineas.append(f"{nombre}:")
        lineas += ["  " + _fmt_cohorte(c).replace("*", "") for c in b["cohortes"]]
        for p in b["programas"]:
            extra = "; ".join(f"{'SENA' if 'SENA' in g.upper() else 'transferencia'}: {', '.join(v)}" for g, v in p["extra"].items())
            lineas.append(f"  - {p['display']}: primera vez {', '.join(p['cohortes']) or 'no'}" + (f"; {extra}" if extra else ""))
    return "\n".join(lineas)


def _respuesta_fechas(question, store):
    from datetime import date
    from .parametrizacion import fecha_larga
    q = norm(question)
    nivel = "posgrado" if any(k in q for k in ("POSGRADO", "ESPECIALIZACION", "MAESTRIA")) else "pregrado"
    modalidad = "sena" if "SENA" in q else "regular"
    # ¿pregunta por un programa puntual?
    mejor = None
    for tipo, b in store.param.bloques():
        for p in b["programas"]:
            ptoks = tokens(p["display"], {"VIRTUAL", "ESPECIALIZACION", "MAESTRIA"})
            if ptoks and all(any(similarity(t, w) >= 0.85 for w in tokens(question)) for t in ptoks):
                if not mejor or len(ptoks) > mejor[0]:
                    mejor = (len(ptoks), p, b, tipo)
    if mejor:
        _, p, b, tipo = mejor
        cohs = store.param.cohortes_programa(p["nombre"], "pregrado" if tipo == "pregrado" else "posgrado", modalidad)
        if not cohs and modalidad == "sena":
            return f"🎓 *{p['display']}* no tiene cohortes abiertas para egresados SENA en la parametrización vigente."
        return f"📅 *{p['display']}*{' (SENA)' if modalidad == 'sena' else ''}\n" + "\n".join("• " + _fmt_cohorte(c) for c in cohs)
    lineas = []
    for tipo, b in store.param.bloques():
        if (nivel == "pregrado") != (tipo == "pregrado"):
            continue
        if "MAESTRIA" in q and "ESPECIALIZACION" not in q and tipo == "especializaciones":
            continue
        if "ESPECIALIZACION" in q and "MAESTRIA" not in q and tipo == "maestrias":
            continue
        titulo = {"pregrado": "Pregrado y SENA", "especializaciones": "Especializaciones", "maestrias": "Maestrías"}[tipo]
        lineas.append(f"📅 *{titulo}*")
        lineas += ["• " + _fmt_cohorte(c) for c in b["cohortes"]]
    if not lineas:
        cfg = store.config
        return f"📅 El próximo inicio de clases configurado es *{cfg['inicio_clases']}*."
    return "\n".join(lineas) + "\n\nPregúntame por un programa (ej. *¿cuándo inicia Derecho?*) para ver sus cohortes."


def local_answer(question, store):
    q = norm(question)
    cfg = store.config
    if not q:
        return "Escríbeme tu pregunta 🙂"

    if any(k in q.split() or k in q for k in FECHA_KEYS) and store.param.bloques():
        return _respuesta_fechas(question, store)

    titulo = _match_title(question, store.titulos())
    if titulo:
        res = buscar_homologacion(store, titulo)
        if res["grupos"]:
            return _fmt_homologacion(res, cfg) + f"\n\n💡 Recuerda: {cfg['descuento_sena']}% de descuento SENA, inscripción y estudio de homologación sin costo."

    for p in store.precios():
        ptoks = tokens(p["programa"], {"VIRTUAL"})
        if ptoks and all(any(similarity(t, w) >= 0.85 for w in tokens(question)) for t in ptoks):
            valor = int(p["valor"])
            final = valor - round(valor * cfg["descuento_sena"] / 100)
            return (f"💰 *{p['programa']}*\n• Valor semestre: {money(valor)}\n• Con {cfg['descuento_sena']}% SENA: *{money(final)}*\n"
                    f"• Duración: {p.get('semestres')} semestres\n• Inicio: {store.inicio_de(p['programa'], 'pre')}")

    for keys, ans in _FAQ:
        if any(norm(k) in q for k in keys):
            return ans

    if any(k in q for k in ("PRECIO", "VALOR", "CUESTA", "COSTO")):
        top = sorted(store.precios(), key=lambda p: p["valor"])[:6]
        return "💰 Algunos valores por semestre (antes del descuento SENA):\n" + "\n".join(
            f"• {p['programa']}: {money(p['valor'])}" for p in top) + "\n\nPregúntame por un programa específico para darte el valor con descuento."
    if "DESCUENTO" in q or "BENEFICIO" in q:
        return (f"🏷️ Beneficios para egresados SENA:\n• {cfg['descuento_sena']}% de descuento en el semestre\n"
                f"• Inscripción gratis (ahorra {money(cfg['ahorro_inscripcion'])})\n• Estudio de homologación gratis (ahorra {money(cfg['ahorro_estudio'])})")

    return ("Puedo ayudarte con:\n• Qué homologa un título SENA (ej: *¿qué homologa Tecnología en Gestión Logística?*)\n"
            "• Precios de un programa (ej: *precio de Ingeniería Industrial*)\n• Documentos, inscripción en FDI, HubSpot y Zoho")


def _context(store):
    cfg = store.config
    df = store.actas()
    filas = [f"{r['TÉCNICO O TECNOLOGÍA']} | {r['PROGRAMA']} | {r['SEMTR HOMOLOGADOS']} | {r['FALTANTES']}"
             for _, r in df.sort_values(["TÉCNICO O TECNOLOGÍA", "PROGRAMA"]).iterrows()]
    precios = [f"{p['programa']} | {p['valor']} | {p.get('semestres')}" for p in store.precios()]
    return (
        "Eres el asistente interno de los asesores comerciales de la Universidad Areandina (Colombia) "
        "para homologaciones de egresados SENA. Responde en español, de forma breve y práctica, usando el "
        "formato de WhatsApp (*negrilla*). Usa SOLO los datos de abajo; si algo no está, dilo y sugiere a quién consultar.\n\n"
        f"CONFIGURACIÓN: descuento SENA {cfg['descuento_sena']}%, "
        f"ahorro inscripción {cfg['ahorro_inscripcion']}, ahorro estudio de homologación {cfg['ahorro_estudio']}.\n\n"
        f"GUÍA INTERNA:{GUIA}\n"
        "ACTAS DE HOMOLOGACIÓN VIRTUAL (título SENA | programa | semestres homologados | semestres por cursar):\n"
        + "\n".join(filas)
        + "\n\nPRECIOS POR SEMESTRE ANTES DE DESCUENTO (programa | valor COP | semestres):\n" + "\n".join(precios)
        + "\n\nCALENDARIO DE COHORTES (parametrización vigente; las letras son las cohortes en que abre cada programa):\n"
        + calendario_texto(store)
    )


def claude_available():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def claude_answer(question, history, store):
    import anthropic

    client = anthropic.Anthropic()
    messages = []
    for m in (history or [])[-10:]:
        role = "assistant" if m.get("role") == "assistant" else "user"
        text = str(m.get("content", ""))[:4000]
        if text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": question[:4000]})
    while messages and messages[0]["role"] != "user":
        messages.pop(0)

    response = client.beta.messages.create(
        model=ASSISTANT_MODEL,
        max_tokens=8000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low"},
        system=[{"type": "text", "text": _context(store), "cache_control": {"type": "ephemeral"}}],
        messages=messages,
    )
    if response.stop_reason == "refusal":
        return None
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    return text or None


def answer(question, history, store):
    """Devuelve (texto, fuente) donde fuente es 'claude' o 'local'."""
    if claude_available():
        try:
            text = claude_answer(question, history, store)
            if text:
                return text, "claude"
        except Exception as e:  # cualquier fallo de red/API cae al modo local
            log.warning("Asistente Claude no disponible: %s", e)
    return local_answer(question, store), "local"
