"""
API + PWA de horarios de tren (FastAPI).

- El frontend (PWA mobile-first) se sirve estático en `/`.
- La API vive bajo `/api` (ej. `/api/proximos`), siguiendo la convención de que el
  navegador siempre llama al mismo origen bajo `/api` (compatible con el reverse
  proxy / Cloudflare Tunnel: nunca se expone el backend por separado).

Devuelve, para una estación (por defecto Martínez, sentido Retiro), cuál es el
próximo tren, en cuántos minutos llega y cuáles son los siguientes.
"""

from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from .scraper import TZ, _to_min, calcular_proximos, fetch, info_dia, parse

app = FastAPI(
    title="API Horarios Tren",
    description="Próximos trenes por estación, a partir de horariostrenes.com.ar.",
    version="1.1.0",
)

api = APIRouter(prefix="/api")


@api.get("/health")
def health():
    return {"status": "ok"}


@api.get("/proximos")
async def proximos(
    estacion: str = Query("Martínez", description="Estación a consultar"),
    sentido: str = Query("Retiro", description="Cabecera destino: Retiro o Tigre"),
    ramal: str = Query("tigre-retiro", description="Ramal, ej. tigre-retiro"),
    dia: str = Query("habil", description="habil | noHabil"),
    limite: int = Query(6, ge=1, le=100, description="Cuántos próximos trenes listar"),
):
    """Próximo tren y siguientes que pasan por la estación."""
    try:
        url, html = await fetch(ramal, estacion, sentido, dia)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"No se pudo consultar la fuente: {e}")

    trenes = parse(html)
    if not trenes:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron horarios. Revisá estación / sentido / ramal.",
        )

    lista = calcular_proximos(trenes)
    ahora = datetime.now(TZ)

    return {
        "estacion": estacion,
        "sentido": sentido,
        "ramal": ramal,
        "dia": dia,
        "hora_consulta": ahora.strftime("%H:%M"),
        "proximo_tren": lista[0],
        "proximos_trenes": lista[:limite],
        "fuente": url,
    }


@api.get("/AlexaNextRetiroTrain")
async def alexa_next_retiro():
    """Próximo tren Martínez → Retiro, listo para leer por voz (Alexa/HomeAssistant).

    Sin parámetros: detecta solo el día (hábil / finde / feriado en Argentina).
    """
    info = await info_dia()

    try:
        _, html = await fetch("tigre-retiro", "Martínez", "Retiro", info["dia"])
    except httpx.HTTPError:
        return {
            "mensaje": "No pude consultar los horarios en este momento.",
            "proximo": None,
            "minutos": None,
            "estado": "error",
            **_extra_dia(info),
        }

    trenes = parse(html)
    lista = calcular_proximos(trenes)
    if not lista:
        return {
            "mensaje": "No encontré horarios para hoy.",
            "proximo": None,
            "minutos": None,
            "estado": "error",
            **_extra_dia(info),
        }

    p = lista[0]
    hora, minutos = p["hora"], p["en_minutos"]

    ahora = datetime.now(TZ)
    now_min = ahora.hour * 60 + ahora.minute
    es_manana = (_to_min(hora) - now_min) < 0  # el servicio de hoy ya terminó

    if es_manana:
        estado = "sin_servicio"
        mensaje = f"No hay más trenes a Retiro por hoy. El próximo es mañana a las {hora}."
    else:
        estado = "normal"
        if minutos <= 0:
            mensaje = f"El próximo tren a Retiro está llegando, a las {hora}."
        elif minutos == 1:
            mensaje = f"El próximo tren a Retiro llega en 1 minuto, a las {hora}."
        else:
            mensaje = f"El próximo tren a Retiro llega en {minutos} minutos, a las {hora}."

    return {
        "mensaje": mensaje,
        "proximo": hora,
        "minutos": minutos,
        "estado": estado,
        **_extra_dia(info),
    }


def _extra_dia(info: dict) -> dict:
    """Campos informativos del día para Home Assistant (opcionales)."""
    return {
        "dia": info["dia"],
        "dia_semana": info["dia_semana"],
        "es_feriado": info["es_feriado"],
        "feriado": info["feriado"],
    }


app.include_router(api)

# El frontend (PWA) se sirve estático en la raíz. Debe ir DESPUÉS del router /api.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
