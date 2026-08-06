# Tren Martínez — API + PWA

Un solo servicio (FastAPI) que sirve:

- una **PWA mobile-first** en `/` que muestra por defecto el próximo tren
  **Martínez → Retiro** (con filtros de estación, sentido y día), y
- la **API** bajo `/api` que scrapea los datos de
  [horariostrenes.com.ar](https://www.horariostrenes.com.ar) (ramal Tigre ⇄ Retiro).

Frontend y API viven en el **mismo origen**: el navegador llama a `/api/...` (rutas
relativas), así que **no hace falta exponer un backend aparte**. Encaja con el patrón
de Cloudflare Tunnel: se publica un único hostname → este servicio.

## Levantar con Docker (puerto aleatorio)

```bash
docker compose up -d --build
docker compose port api 8000
```

El puerto de host es **aleatorio** (lo asigna Docker). El segundo comando imprime
algo como `0.0.0.0:50899`; ese `50899` es el puerto al que apuntás.

Abrí la PWA en `http://localhost:<puerto>/`.

## Cloudflare Tunnel

Como frontend y API son el mismo servicio, apuntás el tunnel a ese único puerto:

```
tren.tu-dominio.net -> http://127.0.0.1:<puerto>
```

El navegador pega a `/api/proximos` sobre el mismo hostname; no se expone nada más.
(Si preferís meterlo detrás de tu nginx como en pipiseries, un `location /api/` que
haga proxy a este servicio funciona igual, sin tocar el frontend.)

## Endpoints

| Método | Ruta            | Descripción                               |
|--------|-----------------|-------------------------------------------|
| GET    | `/`             | PWA (frontend)                            |
| GET    | `/api/proximos` | Próximo tren + siguientes por la estación |
| GET    | `/api/health`   | Healthcheck                               |
| GET    | `/docs`         | Swagger (documentación interactiva)       |

### Parámetros de `/api/proximos`

| Param      | Default        | Valores                            |
|------------|----------------|------------------------------------|
| `estacion` | `Martínez`     | nombre exacto de la estación       |
| `sentido`  | `Retiro`       | `Retiro` \| `Tigre`                |
| `ramal`    | `tigre-retiro` | ej. `tigre-retiro`, `mitre-retiro` |
| `dia`      | `habil`        | `habil` \| `noHabil`               |
| `limite`   | `6`            | 1..20                              |

### Respuesta de ejemplo

```json
{
  "estacion": "Martínez",
  "sentido": "Retiro",
  "hora_consulta": "21:07",
  "proximo_tren": { "hora": "21:09", "en_minutos": 2, "recorrido": ["Tigre", "..."] },
  "proximos_trenes": [ { "hora": "21:09", "en_minutos": 2, "recorrido": ["..."] } ],
  "fuente": "https://www.horariostrenes.com.ar/..."
}
```

Los trenes que ya pasaron hoy se corren al día siguiente (+24h), así que
`proximos_trenes` siempre arranca por el próximo tren real.

## Estructura

```
app/
  main.py       # FastAPI: monta la PWA en / y la API en /api
  scraper.py    # fetch (httpx + cache 60s) + parse + cálculo de próximos
static/         # PWA: index.html, sw.js, manifest, iconos
Dockerfile
docker-compose.yml   # puerto de host ALEATORIO
```

## Comandos útiles

```bash
docker compose logs -f api     # ver logs
docker compose down            # apagar
```
