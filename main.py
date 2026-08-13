from fastapi import FastAPI, HTTPException
import httpx
from datetime import datetime, timedelta, timezone

app = FastAPI(
    title="AlarmaSismica API",
    description="Backend para el sistema de alertas sísmicas",
    version="0.2.0"
)

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


@app.get("/")
def inicio():
    return {
        "mensaje": "AlarmaSismica API funcionando",
        "estado": "online",
        "version": "0.2.0"
    }


@app.get("/earthquakes")
async def obtener_sismos(
    latitude: float = 3.4516,
    longitude: float = -76.5320,
    radius_km: float = 500,
    min_magnitude: float = 2.5
):
    """
    Obtiene sismos reales registrados por USGS.

    Por defecto:
    - Ubicación: Cali, Colombia
    - Radio: 500 km
    - Magnitud mínima: 2.5
    - Periodo: última hora
    """

    ahora = datetime.now(timezone.utc)
    hace_una_hora = ahora - timedelta(hours=1)

    parametros = {
        "format": "geojson",
        "starttime": hace_una_hora.isoformat(),
        "endtime": ahora.isoformat(),
        "latitude": latitude,
        "longitude": longitude,
        "maxradiuskm": radius_km,
        "minmagnitude": min_magnitude,
        "eventtype": "earthquake",
        "orderby": "time",
        "limit": 50
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as cliente:
            respuesta = await cliente.get(
                USGS_URL,
                params=parametros
            )

            respuesta.raise_for_status()

            datos = respuesta.json()

    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo consultar USGS: {str(error)}"
        )

    sismos = []

    for evento in datos.get("features", []):

        propiedades = evento.get("properties", {})
        geometria = evento.get("geometry", {})

        coordenadas = geometria.get("coordinates", [])

        if len(coordenadas) < 3:
            continue

        longitud = coordenadas[0]
        latitud = coordenadas[1]
        profundidad = coordenadas[2]

        tiempo = propiedades.get("time")

        if tiempo:
            fecha = datetime.fromtimestamp(
                tiempo / 1000,
                tz=timezone.utc
            ).isoformat()
        else:
            fecha = None

        sismo = {
            "id": evento.get("id"),
            "magnitud": propiedades.get("mag"),
            "ubicacion": propiedades.get("place"),
            "latitud": latitud,
            "longitud": longitud,
            "profundidad_km": profundidad,
            "fecha": fecha,
            "tsunami": propiedades.get("tsunami", 0),
            "significancia": propiedades.get("sig"),
            "alerta_usgs": propiedades.get("alert"),
            "mmi": propiedades.get("mmi"),
            "cdi": propiedades.get("cdi"),
            "url": propiedades.get("url")
        }

        sismos.append(sismo)

    return {
        "status": "success",
        "source": "USGS",
        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "radius_km": radius_km
        },
        "min_magnitude": min_magnitude,
        "count": len(sismos),
        "earthquakes": sismos
    }