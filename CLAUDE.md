# CLAUDE.md

## Propósito del proyecto

El objetivo de este proyecto es construir una **API** que exponga la información de
horarios de trenes que hoy se muestra en la web pública **horariostrenes.com.ar**.

En lugar de que un usuario tenga que navegar la página HTML, la API debe scrapear /
consultar esa fuente y devolver los datos de forma estructurada (JSON), lista para ser
consumida por otras aplicaciones (web, mobile, bots, etc.).

## Fuente de datos

URL de referencia (ejemplo de una consulta):

```
https://www.horariostrenes.com.ar/horarios-tren-tigre-retiro?dia=habil&estacion=Martínez&sentido=Retiro
```

Esa página muestra los horarios del **ramal Tigre ⇄ Retiro** (Línea Mitre) para una
estación, un sentido y un tipo de día determinados.

### Parámetros de la consulta

| Parámetro   | Descripción                                  | Valores de ejemplo                          |
|-------------|----------------------------------------------|---------------------------------------------|
| ramal       | Va en el path de la URL                      | `tigre-retiro`, `mitre-retiro`, `suarez-retiro` |
| `dia`       | Tipo de día                                  | `habil` (días de semana), `sabado`/`feriado` (sáb., dom. o feriado) |
| `estacion`  | Estación desde la que se consulta            | `Martínez`, `San Isidro`, `Retiro`, `Tigre`, ... |
| `sentido`   | Cabecera hacia la que va el tren             | `Retiro`, `Tigre`                           |

### Estaciones del ramal Tigre ⇄ Retiro

Retiro, L. de la Torre, Belgrano C, Núñez, Rivadavia, Vte. López, Olivos, La Lucila,
Martínez, Acassuso, San Isidro, Beccar, Victoria, Virreyes, San Fernando, Carupá, Tigre.

## Información que debe devolver la API

A partir de la fuente, la API debería exponer al menos:

- **Ramal / línea** consultada.
- **Estación** de consulta y **sentido** (cabecera destino).
- **Tipo de día** (hábil / sábado-domingo-feriado).
- **Listado de horarios** de los trenes que pasan por esa estación en ese sentido:
  - hora de salida/paso por la estación,
  - próximos trenes (y, opcionalmente, minutos restantes respecto de la hora actual),
  - horario completo del servicio.

## Cómo se obtienen los datos (verificado)

- La página es **server-rendered**: los horarios vienen en el HTML, no hay AJAX ni
  API oculta. Basta un GET a la URL y parsear el HTML.
- Cada tren es un `<div class="horarioItem">` con:
  - `.horarioItemHora` → hora de paso por la estación consultada,
  - `.detalle > .detalleItem` → cada parada del recorrido (`HH:MM: Estación`); la
    estación buscada lleva además la clase `current`.
- ⚠️ El parámetro `dia` toma los valores **`habil`** o **`noHabil`** (no `sabado`).

## Arquitectura

```
app/
  main.py       # FastAPI: endpoints
  scraper.py    # fetch (httpx + cache TTL) + parse (regex) + cálculo de próximos
requirements.txt
Dockerfile
docker-compose.yml   # puerto de host ALEATORIO
```

- **Stack**: Python 3.12 + FastAPI + httpx, servido con uvicorn.
- **Cache**: en memoria, 60 s por combinación de parámetros, para no golpear de más
  la web de terceros. Los "minutos hasta el tren" se recalculan siempre en vivo con
  la hora actual (zona `America/Argentina/Buenos_Aires`).

## Endpoint principal

```
GET /proximos?estacion=Martínez&sentido=Retiro&ramal=tigre-retiro&dia=habil&limite=5
```

Respuesta (JSON):

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

## Correr en Docker (puerto aleatorio)

```bash
docker compose up -d --build
docker compose port api 8000    # muestra el puerto de host aleatorio asignado
```

Docker asigna un puerto de host efímero (mapeo `- "8000"` en docker-compose.yml, sin
puerto de host fijo). Para exponerlo en el servidor Linux, ese es el puerto a apuntar
(o poné un reverse proxy delante).

## Notas

- La fuente es una web de terceros: se cachea 60 s. Los horarios cambian poco.
- `dia` (`habil`/`noHabil`) es clave porque los horarios varían según el tipo de día.
