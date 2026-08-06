"""
Prueba de concepto: obtener y parsear los horarios de horariostrenes.com.ar

Uso:
    python3 poc_scraper.py

No requiere librerías externas (usa urllib + html.parser via regex simple).
Sirve para validar que se pueden extraer los datos antes de armar la API.
"""

import re
import json
import subprocess
import urllib.parse

BASE = "https://www.horariostrenes.com.ar"


def fetch(ramal, estacion, sentido, dia="habil"):
    """Descarga el HTML de una consulta de horarios usando curl.

    Se usa curl (y no urllib) para evitar el problema de certificados SSL del
    Python de python.org en macOS. En la API real conviene usar requests/httpx
    con certifi; acá priorizamos que corra sin instalar nada.
    """
    qs = urllib.parse.urlencode({"dia": dia, "estacion": estacion, "sentido": sentido})
    url = f"{BASE}/horarios-tren-{ramal}?{qs}"
    html = subprocess.check_output(
        ["curl", "-s", "-A", "Mozilla/5.0", url], text=True
    )
    return url, html


def parse(html):
    """Extrae la lista de trenes desde el HTML."""
    trenes = []

    # Cada tren es un bloque .horarioItem
    for item in re.split(r'<div class="horarioItem[^"]*">', html)[1:]:
        # Hora en la estación consultada
        m_hora = re.search(r'horarioItemHora">\s*([0-9]{1,2}:[0-9]{2})', item)
        if not m_hora:
            continue
        hora = m_hora.group(1)

        # Texto relativo (En X minutos / Hace X horas)
        m_txt = re.search(r'horarioItemTexto">\s*([^<]+?)\s*</span>', item)
        relativo = m_txt.group(1) if m_txt else None

        # Paradas del recorrido: <div class="detalleItem ...">  HH:MM: Estacion  </div>
        paradas = []
        for mp in re.finditer(
            r'<div class="detalleItem\s*([^"]*)">\s*([0-9]{2}:[0-9]{2}):\s*([^<]+?)\s*</div>',
            item,
        ):
            clases, h, est = mp.group(1), mp.group(2), mp.group(3)
            paradas.append(
                {
                    "hora": h,
                    "estacion": est.strip(),
                    "es_consultada": "current" in clases,
                }
            )

        trenes.append({"hora": hora, "relativo": relativo, "paradas": paradas})

    return trenes


if __name__ == "__main__":
    url, html = fetch("tigre-retiro", "Martínez", "Retiro", "habil")
    print(f"URL consultada: {url}")
    trenes = parse(html)
    print(f"Trenes encontrados: {len(trenes)}\n")

    # Mostrar los primeros 5 como ejemplo
    for t in trenes[:5]:
        recorrido = " → ".join(p["estacion"] for p in t["paradas"])
        print(f"  {t['hora']:>6} hs  ({t['relativo']})")
        print(f"         {recorrido}\n")

    # Solo las horas de salida desde la estación consultada
    horas = [t["hora"] for t in trenes]
    print("Todas las horas de paso por la estación:")
    print(json.dumps(horas, ensure_ascii=False))
