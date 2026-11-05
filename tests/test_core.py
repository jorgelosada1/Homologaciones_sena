from core.data import DataStore, buscar_homologacion, buscar_presencial, explorar_programas, resolve_titles
from core.messages import mensaje_homologacion, mensaje_presencial
from core.text import fix_text_enc, money, norm, pretty_name, program_similarity, similarity

store = DataStore()


def test_norm_y_money():
    assert norm("Técnico en Gestión") == "TECNICO EN GESTION"
    assert money(2330000) == "$2.330.000"
    assert pretty_name("ADMINISTRACION DE EMPRESAS") == "Administración de Empresas"


def test_fix_encoding():
    assert fix_text_enc("T�cnico en Gesti�n") == "Técnico en Gestión"


def test_similarity_tolerante():
    assert similarity("tecnico en contabilizacion", "Técnico en Contabilización de Operaciones Comerciales y Financieras") > 0.85
    assert program_similarity("LICENCIATURA EN CIENCIAS SOCIALES", "Lic. en Ciencias Sociales") == 1.0
    assert program_similarity("ADMINISTRACION DE EMPRESAS", "Administración en Salud") < 0.66


def test_busqueda_exacta_sin_tildes():
    res = buscar_homologacion(store, "tecnologo en gestion logistica")
    assert res["modo"] == "exacto"
    assert res["grupos"][0]["titulo"] == "Tecnología en Gestión Logística"
    progs = {p["programa_display"] for p in res["grupos"][0]["programas"]}
    assert "Administración de Empresas" in progs


def test_busqueda_con_error_de_escritura():
    res = buscar_homologacion(store, "tecnologia en analisis y desarollo de sofware")
    assert res["modo"] == "aproximado"
    assert res["grupos"][0]["titulo"] == "Tecnología en Análisis y Desarrollo de Software"


def test_busqueda_sin_resultado():
    elegidos, _, modo = resolve_titles("zzz qqq", store.titulos())
    assert elegidos == [] and modo == "ninguno"


def test_programa_nuevo_administracion_en_salud():
    nombres = {p["display"] for p in explorar_programas(store)}
    assert "Administración en Salud" in nombres
    res = buscar_homologacion(store, "Tecnología en Gestión Administrativa del Sector Salud")
    assert any(p["programa_display"] == "Administración en Salud" for p in res["grupos"][0]["programas"])


def test_emsub_integrado():
    res = buscar_homologacion(store, "Tecnología en Logística Militar")
    assert res["grupos"] and res["grupos"][0]["fuente"] == "EMSUB"


def test_precios_y_ahorro():
    res = buscar_homologacion(store, "Tecnología en Gestión Logística")
    ae = next(p for p in res["grupos"][0]["programas"] if p["programa_display"] == "Administración de Empresas")
    pr = ae["precio"]
    assert pr["valor_final"] == pr["valor"] - round(pr["valor"] * pr["descuento"] / 100)
    assert pr["inversion_total"] == pr["valor_final"] * ae["faltantes"]


def test_mensaje_formato_whatsapp():
    res = buscar_homologacion(store, "Tecnología en Gestión Logística")
    txt = mensaje_homologacion(res, store.config, nombre="Ana", incluir_precios=True)
    assert txt.startswith("¡Hola Ana!")
    assert "🔹 *ADMINISTRACIÓN DE EMPRESAS*" in txt
    assert "1 de febrero de 2027" in txt


def test_presencial_por_sede():
    res = buscar_presencial(store, "talento humano", "pereira")
    assert res["sedes"] and all(s["sede"] == "pereira" for s in res["sedes"])
    assert "Sede Pereira" in mensaje_presencial(res, store.config)


def test_mensajes_usan_fechas_2027():
    for m in store.render_list(store.mensajes_programas()) + store.render_list(store.mensajes_sena()):
        assert "2026" not in m["texto"], m["titulo"]
        assert "{inicio" not in m["texto"]


def test_parametrizacion_cohortes():
    from core.parametrizacion import parse_rango
    from datetime import date
    d = store.param.data()
    pre = d["pregrado"]
    assert [c["corto"] for c in pre["cohortes"]] == ["1A", "1B", "1C"]
    assert pre["cohortes"][0]["fechas"]["clases"]["desde"] == "2027-02-01"
    assert parse_rango("Del 26 - oct - 26-hasta el 29 - ene -27") == (date(2026, 10, 26), date(2027, 1, 29))
    assert parse_rango("Del 25 al 29 de enero del 2027") == (date(2027, 1, 25), date(2027, 1, 29))
    # error de año del Excel (8-mar-26) corregido
    mae = d["posgrado"]["maestrias"]["cohortes"][0]
    assert mae["fechas"]["clases"]["desde"] == "2027-03-08"


def test_inicio_por_programa():
    assert store.inicio_de("Economía", "pre") == "22 de febrero de 2027"
    assert store.inicio_de("Psicología", "pre") == "1 de febrero de 2027"
    assert store.inicio_de("Maestría en Innovación", "pos") == "8 de marzo de 2027"
    assert store.inicio_de("Especialización en Ciberseguridad", "pos") == "29 de marzo de 2027"
    assert store.inicio_de("Administración de Empresas – Virtual", "sena") == "1 de febrero de 2027"


def test_mensajes_con_fecha_de_su_programa():
    msgs = {m["titulo"]: m["texto"] for m in store.render_list(store.mensajes_programas())}
    assert "22 de febrero de 2027" in msgs["Economía"]
    assert "8 de marzo de 2027" in msgs["Maestría en Innovación"]
