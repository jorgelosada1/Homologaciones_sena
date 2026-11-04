import pytest

PAGES = ["/", "/dashboard", "/presencial", "/programas", "/mensajes", "/mensajes?nivel=sena", "/precios",
         "/piezas", "/brochures", "/flujos", "/parametrizacion", "/capacitacion", "/pensum/pregrado", "/pensum/posgrado"]
OCULTOS = ["/simulador", "/whatsapp", "/cruce", "/aguachica"]


def test_login_requerido(app):
    c = app.test_client()
    r = c.get("/")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert c.get("/api/homologar?q=x").status_code == 401


def test_login_ok_y_error(app):
    c = app.test_client()
    assert "incorrectos" in c.post("/login", data={"user": "x", "password": "y"}).get_data(as_text=True)
    r = c.post("/login", data={"user": "Innovacion", "password": "0228"})
    assert r.status_code == 302


@pytest.mark.parametrize("path", PAGES)
def test_paginas_cargan(client, path):
    assert client.get(path).status_code == 200


def test_sena_redirige(client):
    r = client.get("/sena?q=salud")
    assert r.status_code == 302 and "nivel=sena" in r.headers["Location"]


def test_api_homologar(client):
    d = client.get("/api/homologar?q=gestion%20logistica&precios=1").get_json()
    assert d["ok"] and d["total_programas"] >= 1 and "Precios" in d["mensaje_precios"]


def test_api_presencial(client):
    d = client.get("/api/presencial?q=talento%20humano").get_json()
    assert d["ok"] and d["total"] > 0


def test_api_titulos_fuzzy(client):
    d = client.get("/api/titulos?q=desarollo%20sofware").get_json()
    assert any("Software" in i["titulo"] for i in d["items"])


def test_api_asistente_local(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    d = client.post("/api/asistente", json={"message": "precio de ingenieria industrial"}).get_json()
    assert d["ok"] and d["source"] == "local" and "Ingeniería Industrial" in d["reply"]


@pytest.mark.parametrize("path", OCULTOS)
def test_modulos_ocultos_para_asesor(client, path):
    r = client.get(path)
    assert r.status_code == 302 and r.headers["Location"].endswith("/")


def test_modulos_ocultos_no_salen_en_menu(client):
    html = client.get("/").get_data(as_text=True)
    for path in OCULTOS:
        assert f'href="{path}"' not in html
    assert 'href="/pensum/pregrado"' in html and 'href="/pensum/posgrado"' in html


@pytest.mark.parametrize("path", ["/simulador", "/whatsapp", "/cruce"])
def test_modulos_ocultos_disponibles_para_admin(admin, path):
    assert admin.get(path).status_code == 200


def test_pensum_pdf(client):
    from core.pensum import listar
    it = listar("posgrado")[0]
    r = client.get(f"/pensum/posgrado/archivo/{it['archivo']}")
    assert r.status_code == 200 and r.mimetype == "application/pdf"
    assert client.get("/pensum/posgrado/archivo/../app.py").status_code == 404
    assert client.get("/pensum/otro").status_code == 404


def test_pensum_enlazado_en_homologacion(client):
    d = client.get("/api/homologar?q=Tecnolog%C3%ADa%20en%20Gesti%C3%B3n%20Log%C3%ADstica").get_json()
    assert all(p["pensum"] for p in d["grupos"][0]["programas"])


def test_api_cruce(admin):
    client = admin
    d = client.get("/api/cruce?radar=en_radar").get_json()
    assert "rows" in d
    if d["total"]:
        assert all(r["_en_funnel"] for r in d["rows"])


def test_cruce_export_excel(admin):
    r = admin.get("/api/cruce/export.xlsx")
    assert r.status_code in (200, 404)


def test_admin_protegido(client):
    assert client.get("/admin/precios").status_code == 302


def test_admin_paginas(admin):
    for p in ["/admin/dashboard", "/admin/mensajes-comerciales", "/admin/mensajes-sena", "/admin/precios",
              "/admin/piezas", "/admin/brochures", "/admin/config"]:
        assert admin.get(p).status_code == 200, p


def test_csrf_bloquea_post_sin_token(app):
    app.config["CSRF_ENABLED"] = True
    try:
        c = app.test_client()
        with c.session_transaction() as s:
            s["logged_in"] = True
        assert c.post("/api/track", json={"tipo": "copia"}).status_code == 400
        with c.session_transaction() as s:
            s["_csrf_token"] = "abc"
        assert c.post("/api/track", json={"tipo": "copia"}, headers={"X-CSRF-Token": "abc"}).status_code == 200
    finally:
        app.config["CSRF_ENABLED"] = False


def test_path_traversal_piezas(client):
    r = client.get("/piezas/../../app.py")
    assert r.status_code in (302, 404)


def test_404_bonito(client):
    r = client.get("/no-existe")
    assert r.status_code == 404 and "no existe" in r.get_data(as_text=True)
