"""
Scraper y lógica de horarios de horariostrenes.com.ar

Descarga el HTML de la página (los horarios vienen server-rendered, no hay AJAX)
y lo parsea a una estructura de datos. Incluye un cache en memoria con TTL para
no golpear de más el sitio de terceros.
"""

import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

BASE = "https://www.horariostrenes.com.ar"
TZ = ZoneInfo("America/Argentina/Buenos_Aires")

# Cache simple en memoria: {clave: (timestamp, (url, html))}
_CACHE: dict = {}
_CACHE_TTL = 60  # segundos


def _norm_hora(t: str) -> str:
    """Normaliza '6:26' -> '06:26'."""
    h, m = t.split(":")
    return f"{int(h):02d}:{m}"


def _to_min(t: str) -> int:
    """'06:26' -> 386 (minutos desde medianoche)."""
    h, m = t.split(":")
    return int(h) * 60 + int(m)


async def fetch(ramal: str, estacion: str, sentido: str, dia: str) -> tuple[str, str]:
    """Descarga el HTML de una consulta (con cache de _CACHE_TTL segundos)."""
    key = (ramal, estacion, sentido, dia)
    now = time.time()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    url = f"{BASE}/horarios-tren-{ramal}"
    params = {"dia": dia, "estacion": estacion, "sentido": sentido}
    async with httpx.AsyncClient(
        timeout=20, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True
    ) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        result = (str(resp.url), resp.text)

    _CACHE[key] = (now, result)
    return result


def parse(html: str) -> list[dict]:
    """Extrae la lista de trenes desde el HTML.

    Cada tren -> {"hora": "HH:MM", "recorrido": [{"hora","estacion","es_consultada"}]}
    """
    trenes = []
    for item in re.split(r'<div class="horarioItem[^"]*">', html)[1:]:
        m_hora = re.search(r'horarioItemHora">\s*([0-9]{1,2}:[0-9]{2})', item)
        if not m_hora:
            continue
        hora = _norm_hora(m_hora.group(1))

        recorrido = []
        for mp in re.finditer(
            r'<div class="detalleItem\s*([^"]*)">\s*'
            r"([0-9]{2}:[0-9]{2}):\s*([^<]+?)\s*</div>",
            item,
        ):
            clases, h, est = mp.group(1), mp.group(2), mp.group(3)
            recorrido.append(
                {
                    "hora": h,
                    "estacion": est.strip(),
                    "es_consultada": "current" in clases,
                }
            )

        trenes.append({"hora": hora, "recorrido": recorrido})

    return trenes


def calcular_proximos(trenes: list[dict], ahora: datetime | None = None) -> list[dict]:
    """Devuelve los trenes ordenados por minutos hasta que pasan por la estación.

    Los que ya pasaron hoy se corren al día siguiente (+24h), de modo que el
    primero de la lista siempre es el próximo tren real.
    """
    if ahora is None:
        ahora = datetime.now(TZ)
    now_min = ahora.hour * 60 + ahora.minute

    # Un tren (recorrido) por cada hora única de paso por la estación
    por_hora: dict[str, dict] = {}
    for t in trenes:
        por_hora.setdefault(t["hora"], t)

    resultado = []
    for hora, tren in por_hora.items():
        diff = _to_min(hora) - now_min
        if diff < 0:
            diff += 24 * 60  # el servicio ya pasó hoy -> mañana
        resultado.append(
            {
                "hora": hora,
                "en_minutos": diff,
                "recorrido": [p["estacion"] for p in tren["recorrido"]],
            }
        )

    resultado.sort(key=lambda x: x["en_minutos"])
    return resultado
