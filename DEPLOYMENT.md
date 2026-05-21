# Despliegue

Este proyecto no es una API web: es un proceso batch que abre navegador, consulta Google Sheets, consulta RUNT y termina. Por eso se despliega mejor como job programado, no como servidor web.

## Opcion recomendada: GitHub Actions

GitHub Actions sirve bien para portafolio y ejecuciones puntuales. En repositorios publicos, GitHub indica que Actions es gratis para runners hospedados estandar; tambien soporta ejecucion manual y programada con `cron`.

### 1. Crear repositorio

```bash
git init
git add .
git commit -m "Organiza Bot RUNT para portafolio"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/bot-runt.git
git push -u origin main
```

Antes de subir, revisa que no esten incluidos:

```bash
git status --ignored
```

No deben subirse `.env`, `credentials.json`, `venv/`, `debug/`, capturas `*.png` ni archivos `.pkg`.

### 2. Configurar secrets

En GitHub:

`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

Agrega:

| Secret | Valor |
| --- | --- |
| `SHEET_NAME` | Nombre de la hoja, por ejemplo `Consultas RUNT` |
| `GROQ_API_KEY` | API key de Groq |
| `GOOGLE_CREDENTIALS_JSON` | Contenido completo del archivo `credentials.json` |

El secret `GOOGLE_CREDENTIALS_JSON` debe ser el JSON completo en una sola variable.

### 3. Probar ejecucion

En GitHub:

`Actions` -> `Run Bot` -> `Run workflow`

El workflow usa:

```env
HEADLESS=true
ENABLE_GROQ_CAPTCHA=true
```

Si falla, sube las capturas de `debug/` como artifact para revisar que paso.

### 4. Programar ejecucion

Edita `.github/workflows/run-bot.yml` y descomenta:

```yaml
schedule:
  - cron: "0 12 * * *"
```

GitHub usa horario UTC. Para Colombia, `12:00 UTC` equivale a `7:00 AM` en hora Colombia.

## Alternativa: Docker en servidor con dashboard

En un servidor con Docker:

```bash
git clone https://github.com/TU_USUARIO/bot-runt.git
cd bot-runt
cp .env.example .env
```

Luego copia `credentials.json`, completa `.env` y ejecuta:

```bash
docker compose build
docker compose up -d
```

El dashboard queda disponible en el puerto `8000`.

Para programarlo en Linux:

```bash
crontab -e
```

Ejemplo diario a las 7 AM hora del servidor:

```cron
0 7 * * * cd /ruta/bot-runt && docker compose run --rm bot-runt python runt_automation.py
```

## Sobre servidores gratuitos

- GitHub Actions: buena opcion para portafolio y ejecuciones batch simples.
- Render: sirve para web services gratis, pero sus cron jobs tienen cargo minimo mensual.
- Railway: tiene plan Free limitado y Hobby pago; puede servir, pero no es tan directo para jobs gratuitos recurrentes.
- VPS gratis de nube: puede funcionar con creditos temporales, pero no suele ser estable como solucion permanente.

## Nota importante

El CAPTCHA automatizado puede estar sujeto a las condiciones de uso del sitio consultado. Para portafolio, presenta el proyecto como automatizacion de consulta publica y extraccion estructurada de datos, no como bypass de CAPTCHA.
