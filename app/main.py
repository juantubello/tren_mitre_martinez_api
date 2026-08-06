"""
API de horarios de tren (FastAPI).

Devuelve, para una estación (por defecto Martínez, sentido Retiro), cuál es el
próximo tren, en cuántos minutos llega y cuáles son los siguientes.
"""

from datetime import datetime

import httpx
from fastapi import FastAPI, HTTPException, Query

from .scraper import TZ, calcular_proximos, fetch, parse

app = FastAPI(
    title="API Horarios Tren",
    description="Devuelve los próximos trenes que pasan por una estación, "
    "a partir de los datos de horariostrenes.com.ar.",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "servicio": "API Horarios Tren",
        "ejemplo": "/proximos?estacion=Martínez&sentido=Retiro",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/proximos")
async def proximos(
    estacion: str = Query("Martínez", description="Estación a consultar"),
    sentido: str = Query("Retiro", description="Cabecera destino: Retiro o Tigre"),
    ramal: str = Query("tigre-retiro", description="Ramal, ej. tigre-retiro"),
    dia: str = Query("habil", description="habil | noHabil"),
    limite: int = Query(5, ge=1, le=20, description="Cuántos próximos trenes listar"),
):
    """Próximo tren y siguientes que pasan por la estación."""
    try:
        url, html = await fetch(ramal, estacion, sentido, dia)
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502, detail=f"No se pudo consultar la fuente: {e}"
        )

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
