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


# --- Día hábil / feriado (Argentina) ---------------------------------------

DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
FERIADOS_URL = "https://api.argentinadatos.com/v1/feriados/{year}"
# Tipos de feriado en los que el tren corre horario de fin de semana (noHabil).
# Los "puente" / "no laborable" se dejan como día hábil (el tren corre normal).
TIPOS_NO_HABIL = {"inamovible", "trasladable"}

# Cache de feriados por año: {year: (timestamp, {fecha_iso: nombre})}
_FERIADOS_CACHE: dict = {}
_FERIADOS_TTL = 12 * 3600  # 12 h


async def _feriados(year: int) -> dict[str, str]:
    """Devuelve {fecha_iso: nombre} de los feriados que cuentan como noHabil."""
    now = time.time()
    hit = _FERIADOS_CACHE.get(year)
    if hit and now - hit[0] < _FERIADOS_TTL:
        return hit[1]

    fechas: dict[str, str] = {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(FERIADOS_URL.format(year=year))
            resp.raise_for_status()
            for f in resp.json():
                if f.get("tipo") in TIPOS_NO_HABIL:
                    fechas[f["fecha"]] = f.get("nombre", "Feriado")
    except Exception:
        # Si falla la API, degradamos: usamos lo cacheado o nada (solo finde).
        if hit:
            return hit[1]
        return {}

    _FERIADOS_CACHE[year] = (now, fechas)
    return fechas


async def info_dia(ahora: datetime | None = None) -> dict:
    """Determina si hoy es hábil o noHabil (finde o feriado) en Argentina."""
    if ahora is None:
        ahora = datetime.now(TZ)
    weekday = ahora.weekday()  # 0 = lunes ... 6 = domingo
    fecha_iso = ahora.date().isoformat()

    feriados = await _feriados(ahora.year)
    es_feriado = fecha_iso in feriados
    es_finde = weekday >= 5

    return {
        "fecha": fecha_iso,
        "dia_semana": DIAS_SEMANA[weekday],
        "es_finde": es_finde,
        "es_feriado": es_feriado,
        "feriado": feriados.get(fecha_iso),
        "dia": "noHabil" if (es_finde or es_feriado) else "habil",
    }
