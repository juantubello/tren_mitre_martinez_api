# API Horarios Tren

API en FastAPI que devuelve los próximos trenes que pasan por una estación,
a partir de los datos públicos de [horariostrenes.com.ar](https://www.horariostrenes.com.ar).
Por defecto: estación **Martínez**, sentido **Retiro** (ramal Tigre ⇄ Retiro).

## Levantar con Docker (puerto aleatorio)

```bash
docker compose up -d --build
```

El puerto de host es **aleatorio** (lo asigna Docker). Para saber cuál te tocó:

```bash
docker compose port api 8000
```

Eso imprime algo como `0.0.0.0:63052`. Ese `63052` es el puerto a usar / apuntar
desde tu servidor Linux.

## Uso

```bash
PORT=$(docker compose port api 8000 | cut -d: -f2)
curl "http://localhost:$PORT/proximos"
```

### Endpoints

| Método | Ruta         | Descripción                                  |
|--------|--------------|----------------------------------------------|
| GET    | `/proximos`  | Próximo tren + siguientes por la estación    |
| GET    | `/health`    | Healthcheck                                  |
| GET    | `/docs`      | Documentación interactiva (Swagger)          |

### Parámetros de `/proximos`

| Param      | Default        | Valores                          |
|------------|----------------|----------------------------------|
| `estacion` | `Martínez`     | nombre exacto de la estación     |
| `sentido`  | `Retiro`       | `Retiro` \| `Tigre`              |
| `ramal`    | `tigre-retiro` | ej. `tigre-retiro`, `mitre-retiro` |
| `dia`      | `habil`        | `habil` \| `noHabil`             |
| `limite`   | `5`            | 1..20                            |

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

## Comandos útiles

```bash
docker compose logs -f api     # ver logs
docker compose down            # apagar
```
