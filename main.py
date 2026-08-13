from fastapi import FastAPI

app = FastAPI(
    title="AlarmaSismica API",
    description="Backend para el sistema de alertas sísmicas",
    version="0.1.0"
)


@app.get("/")
def inicio():
    return {
        "mensaje": "AlarmaSismica API funcionando",
        "estado": "online"
    }


@app.get("/earthquakes")
def obtener_sismos():
    return {
        "status": "success",
        "earthquake": {
            "magnitude": 6.2,
            "latitude": 3.45,
            "longitude": -76.52,
            "depth": 35,
            "location": "Colombia"
        }
    }