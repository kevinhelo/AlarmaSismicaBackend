from fastapi import FastAPI, HTTPException
import httpx
from datetime import datetime, timedelta, timezone
from math import radians, sin, cos, sqrt, atan2

app = FastAPI(
    title="AlarmaSismica API",
    description="Backend para el sistema de alertas sísmicas",
    version="0.3.0"
)

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

# Ubicación de referencia: Cali, Colombia
DEFAULT_LATITUDE = 3.4516
DEFAULT_LONGITUDE = -76.5320


def calcular_distancia(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float
):
    """
    Calcula la distancia aproximada entre dos puntos
    utilizando la fórmula de Haversine.
    """

    radio_tierra_km = 6371.0

    lat1 = radians(lat1)
    lat2 = radians(lat2)

    diferencia_latitud = radians(lat2 - lat1)
    diferencia_longitud = radians(lon2 - lon1)

    a = (
        sin(diferencia_latitud / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(diferencia_longitud / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return radio_tierra_km * c


def determinar_nivel_alerta(
    magnitud: float,
    distancia_km: float,
    profundidad_km: float
):
    """
    Primera versión del motor de evaluación.

    Estas reglas son experimentales para el prototipo.
    NO representan todavía un sistema oficial de alerta.
    """

    if magnitud < 4.0:
        return {
            "nivel": "normal",
            "alerta": False,
            "mensaje": "Sismo de magnitud baja."
        }

    if magnitud >= 6.0 and distancia_km <= 300:
        return {
            "nivel": "alto",
            "alerta": True,
            "mensaje": "Posible sismo fuerte. Se recomienda estar atento."
        }

    if magnitud >= 5.0 and distancia_km <= 150:
        return {
            "nivel": "alto",
            "alerta": True,
            "mensaje": "Posible sismo fuerte cerca de la ubicación."
        }

    if magnitud >= 4.0 and distancia_km <= 100:
        return {
            "nivel": "moderado",
            "alerta": True,
            "mensaje": "Sismo cercano. Manténgase atento."
        }

    if magnitud >= 5.0 and distancia_km <= 500:
        return {
            "nivel": "precaucion",
            "alerta": False,
            "mensaje": "Sismo de magnitud considerable, pero distante."
        }

    return {
        "nivel": "normal",
        "alerta": False,
        "mensaje": "No se considera necesario generar una alerta."
    }


@app.get("/")
def inicio():
    return {
        "mensaje": "AlarmaSismica API funcionando",
        "estado": "online",
        "version": "0.3.0"
    }


@app.get("/earthquakes")
async def obtener_sismos(
    latitude: float = DEFAULT_LATITUDE,
    longitude: float = DEFAULT_LONGITUDE,
    radius_km: float = 500,
    min_magnitude: float = 2.5
):
    """
    Obtiene sismos reales registrados por USGS
    durante la última hora.
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


@app.get("/alert")
async def evaluar_alerta(
    latitude: float = DEFAULT_LATITUDE,
    longitude: float = DEFAULT_LONGITUDE
):
    """
    Consulta los sismos recientes y evalúa si alguno
    puede generar una alerta para la ubicación indicada.
    """

    ahora = datetime.now(timezone.utc)

    hace_una_hora = ahora - timedelta(hours=1)

    parametros = {
        "format": "geojson",
        "starttime": hace_una_hora.isoformat(),
        "endtime": ahora.isoformat(),
        "latitude": latitude,
        "longitude": longitude,
        "maxradiuskm": 500,
        "minmagnitude": 4.0,
        "eventtype": "earthquake",
        "orderby": "magnitude",
        "limit": 20
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

    alertas = []

    for evento in datos.get("features", []):

        propiedades = evento.get("properties", {})
        geometria = evento.get("geometry", {})

        coordenadas = geometria.get("coordinates", [])

        if len(coordenadas) < 3:
            continue

        longitud_sismo = coordenadas[0]
        latitud_sismo = coordenadas[1]
        profundidad = coordenadas[2]

        magnitud = propiedades.get("mag")

        if magnitud is None:
            continue

        distancia = calcular_distancia(
            latitude,
            longitude,
            latitud_sismo,
            longitud_sismo
        )

        evaluacion = determinar_nivel_alerta(
            magnitud,
            distancia,
            profundidad
        )

        tiempo = propiedades.get("time")

        if tiempo:

            fecha = datetime.fromtimestamp(
                tiempo / 1000,
                tz=timezone.utc
            ).isoformat()

        else:

            fecha = None

        resultado = {
            "id": evento.get("id"),
            "magnitud": magnitud,
            "ubicacion": propiedades.get("place"),
            "latitud": latitud_sismo,
            "longitud": longitud_sismo,
            "profundidad_km": profundidad,
            "distancia_km": round(distancia, 2),
            "fecha": fecha,
            "nivel": evaluacion["nivel"],
            "alerta": evaluacion["alerta"],
            "mensaje": evaluacion["mensaje"],
            "url": propiedades.get("url")
        }

        alertas.append(resultado)

    hay_alerta = False

    for alerta in alertas:

        if alerta["alerta"]:
            hay_alerta = True

    return {
        "status": "success",
        "location": {
            "latitude": latitude,
            "longitude": longitude
        },
        "alerta": hay_alerta,
        "sismos_evaluados": len(alertas),
        "resultados": alertas
    }

@app.get("/test-alert")
def prueba_alerta():
    """
    Simula un sismo fuerte para probar el sistema de alertas.
    Este endpoint es únicamente para pruebas.
    """

    magnitud = 6.2
    latitud_sismo = 3.20
    longitud_sismo = -76.40
    profundidad = 15.0

    distancia = calcular_distancia(
        DEFAULT_LATITUDE,
        DEFAULT_LONGITUDE,
        latitud_sismo,
        longitud_sismo
    )

    evaluacion = determinar_nivel_alerta(
        magnitud,
        distancia,
        profundidad
    )

    return {
        "modo": "PRUEBA",
        "mensaje": "Este NO es un terremoto real.",
        "sismo": {
            "magnitud": magnitud,
            "latitud": latitud_sismo,
            "longitud": longitud_sismo,
            "profundidad_km": profundidad,
            "distancia_km": round(distancia, 2)
        },
        "resultado": evaluacion
    }