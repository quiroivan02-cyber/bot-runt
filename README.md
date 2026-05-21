# Bot RUNT

Automatizacion en Python para consultar informacion publica de vehiculos en el portal del RUNT y registrar los resultados en Google Sheets.

## Que hace

- Lee placas y cedulas desde una hoja de Google Sheets.
- Abre el portal publico del RUNT con Selenium.
- Consulta cada vehiculo por placa y propietario.
- Extrae informacion general del vehiculo, SOAT y revision tecnico-mecanica.
- Guarda los resultados nuevamente en la hoja.
- Incluye un dashboard web para ejecutar el bot, ver logs en vivo y descargar resultados CSV si existen.

## Tecnologias

- Python 3.12
- Selenium
- Google Sheets API con `gspread`
- Groq Vision para extraer datos desde capturas
- Flask + Socket.IO para dashboard
- Firefox
- Docker opcional

## Estructura

```text
.
├── runt_automation.py
├── dashboard.py
├── templates/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

Los archivos `.env`, `credentials.json`, `venv/` y `debug/` no se suben al repositorio.

## Configuracion

1. Crea una hoja de Google Sheets llamada `Consultas RUNT`.
2. Agrega columnas iniciales `placa` y `cedula`.
3. Crea credenciales de service account de Google y guarda el archivo como `credentials.json`.
4. Comparte la hoja con el correo del service account.
5. Copia el archivo de ejemplo:

```bash
cp .env.example .env
```

6. Completa `GROQ_API_KEY` en `.env`.

## Ejecucion local

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python runt_automation.py
```

## Dashboard local

```bash
source venv/bin/activate
python dashboard.py
```

Abre:

```text
http://localhost:8000
```

Desde el dashboard puedes iniciar o detener el bot y ver los logs emitidos por el proceso.

## Ejecucion con Docker

```bash
docker compose build
docker compose up
```

Luego abre `http://localhost:8000`. El contenedor usa modo headless por defecto. Las capturas de depuracion quedan en `debug/`.

## GitHub y despliegue

El proyecto incluye workflows de GitHub Actions:

- `.github/workflows/ci.yml`: valida instalacion, compilacion e imports.
- `.github/workflows/run-bot.yml`: ejecuta el bot manualmente desde GitHub Actions usando secrets.

Consulta [DEPLOYMENT.md](DEPLOYMENT.md) para subirlo a GitHub y ejecutarlo como job.

## Variables de entorno

| Variable | Descripcion | Valor por defecto |
| --- | --- | --- |
| `SHEET_NAME` | Nombre de la hoja de Google Sheets | `Consultas RUNT` |
| `GOOGLE_CREDENTIALS_FILE` | Ruta del JSON de credenciales | `credentials.json` |
| `DEBUG_DIR` | Carpeta para capturas temporales | `debug` |
| `HEADLESS` | Ejecuta Firefox sin ventana | `false` local, `true` en Docker |
| `PORT` | Puerto del dashboard Flask | `8000` |
| `FLASK_SECRET_KEY` | Clave interna de sesion Flask | `change-me` |
| `GROQ_API_KEY` | API key para extraccion visual | vacio |
| `ENABLE_GROQ_CAPTCHA` | Habilita lectura automatica de CAPTCHA | `false` |

## Nota de uso responsable

Este proyecto esta pensado como automatizacion de consulta publica y extraccion estructurada de datos. No incluye credenciales, datos reales ni archivos generados. Revisa siempre las condiciones de uso del sitio consultado antes de ejecutar automatizaciones.
