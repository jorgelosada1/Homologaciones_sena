# Homologaciones SENA · Areandina — v3

Herramienta interna para los asesores de la Universidad Areandina. Sirve para consultar en segundos qué homologa un título SENA, generar mensajes listos para WhatsApp, calcular la inversión del estudiante y cruzar las bases GEN NACIONAL y FUNNEL.

## Novedades de la v3

### Diseño
- Sistema de diseño nuevo, con **modo claro y oscuro** (respeta la preferencia del sistema) y menú lateral que se puede contraer.
- **Buscador global `Ctrl + K`**: encuentra títulos SENA, páginas y acciones desde cualquier pantalla. Atajos de teclado (`?` para verlos).
- Diseño adaptable a celular. Se puede instalar como app desde el navegador (PWA).
- Vista previa estilo WhatsApp de cada mensaje antes de copiarlo o enviarlo.

### Funcionalidad
| Módulo | Qué hace |
|---|---|
| **Homologaciones** | Búsqueda que tolera tildes, abreviaturas y errores (“tecnologo en gestion logistica”, “desarollo de sofware”). Muestra semestres homologados, avance de la carrera, valor con descuento SENA, inversión total y ahorro estimado. El mensaje sale personalizado con el nombre del prospecto, puede incluir precios y se envía a WhatsApp con un clic. |
| **Presencial** | Bogotá, Pereira y Valledupar, o todas a la vez con un comparativo por sede. |
| **Explorar programas** | Búsqueda inversa: eliges una carrera y ves todos los títulos SENA que homologan en ella. |
| **Simulador** | Programa + título → semestres, descuento SENA y adicional, cuotas, inversión total, ahorro, ruta académica y oferta lista para enviar. |
| **Mensajes** | Biblioteca de mensajes de pregrado, posgrado y SENA, con buscador, favoritos ⭐, nombre del prospecto y envío directo. |
| **Precios** | Tarjetas o tabla, orden por precio, descuento editable, oferta por programa y exportación a CSV. |
| **Envío WhatsApp** | Cola de envío asistido con enlaces wa.me: pegas o importas contactos y envías uno por uno con `{nombre}` y `{saludo}`. Funciona en cualquier sistema operativo, sin bots. |
| **Panel** | Indicadores, búsquedas por día, títulos más consultados, búsquedas sin resultado (posibles títulos faltantes en el acta), gráficos de programas y precios. |
| **Cruce de datos** | Caché (la primera carga tarda unos 3 s y las siguientes unos 10 ms), filtros por radar, fechas y rango, distribución por estado y observación, tabla con orden, paginación y selector de columnas, y exportación a **Excel** y CSV. |
| **Capacitación e IA** | Guía del proceso más un asistente que responde con los datos reales (actas, precios y procesos). Con `ANTHROPIC_API_KEY` usa Claude; sin ella responde con reglas locales. |
| **Piezas y Brochures** | Galería con visor, navegación con flechas, botón **Compartir** (en el celular envía la imagen a WhatsApp) y vista previa de los PDF. |
| **Administración** | CRUD de mensajes con vista previa en vivo y reordenamiento. Precios en tabla editable. **Carga del Excel de actas desde la web** (con validación, respaldo y limpieza automática de datos personales). **Configuración global** (descuento SENA, fechas de inicio, ahorros, cuotas). Buscar y reemplazar en todos los mensajes. Piezas con arrastrar y soltar, carpetas y renombrado. |

### Datos 2027
- Inicio de **pregrado y SENA: 2 de febrero de 2027**. Posgrado: **2027** (fecha por confirmar).
- Los mensajes usan variables (`{inicio_pregrado}`, `{inicio_posgrado}`, `{descuento_sena}`, `{anio}`). Para cambiar una fecha en todos los mensajes basta con editarla en **Administración → Configuración**.
- Acta actualizada: entra **Administración en Salud** y 10 títulos más, y se integran las tecnologías **EMSUB** (Escuela Militar de Suboficiales). La parte presencial ahora se lee de la hoja `PRESENCIAL` del acta, que suma Contaduría, Ingeniería Ambiental, Arquitectura, Gastronomía y otras carreras.

### Seguridad y calidad
- Protección **CSRF** en todos los formularios y llamadas, límite de intentos de login y cookies `HttpOnly`/`SameSite`.
- Credenciales y clave secreta configurables por **variables de entorno** (ver `.env.example`).
- Corrección de *path traversal* en piezas. Los archivos con tildes o ñ ya se pueden borrar.
- El módulo WhatsApp ahora exige iniciar sesión. Antes cualquiera podía ejecutar el bot.
- Se corrigió que la búsqueda presencial de Pereira y Valledupar mostraba el programa de Bogotá.
- 41 pruebas automáticas (`pytest`).

## Ejecutar en local

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python app.py                    # http://localhost:8000
```

Pruebas:

```bash
pytest -q
```

## Despliegue con Docker

```bash
docker build -t homologaciones .
docker run -p 8000:8000 --env-file .env homologaciones
```

Salud del servicio: `GET /healthz`.

## Variables de entorno

Revisa `.env.example`. **Cambia las contraseñas por defecto en producción** (`SECRET_KEY`, `APP_PASSWORD`, `ADMIN_PASSWORD`…).

## Estructura

```
app.py                 Rutas Flask
core/
  text.py              Normalización, corrección de encoding y búsqueda difusa
  data.py              Carga de actas/precios con caché y lógica de homologación
  messages.py          Generación de mensajes para WhatsApp
  cruce.py             Cruce GEN NACIONAL × FUNNEL
  assistant.py         Asistente (local + Claude opcional)
  security.py          CSRF y límite de intentos
  activity.py          Registro de actividad para analítica
templates/             Vistas (Jinja2)
static/css/app.css     Sistema de diseño
static/js/app.js       Utilidades globales (tema, paleta, toasts, WhatsApp)
data/                  JSON de mensajes, precios, configuración y archivos del cruce
whatsapp/              Envío asistido (+ bot de escritorio opcional para Windows)
tests/                 Pruebas
```

## Actualizar el acta de homologaciones

1. Entra a **Administración → Resumen → Datos de homologación**.
2. Sube el Excel. Debe tener la hoja `SENA VIRTUAL 1` con las columnas `PROGRAMA`, `TÉCNICO O TECNOLOGÍA`, `SEMTR HOMOLOGADOS` y `FALTANTES`. Las hojas `PRESENCIAL` y `EMSUB` son opcionales.
3. El sistema guarda un respaldo del archivo anterior en `data/backups/`, elimina las hojas con datos personales y aplica los cambios al instante.
