from conftest import VALIDACION


def test_salud(cliente):
    respuesta = cliente.get("/api/salud")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "listo"


def test_bases(cliente):
    assert set(cliente.get("/api/bases").json()) == {"veterinaria", "airline"}


def test_consulta_en_base_demo(cliente):
    respuesta = cliente.post("/api/sql", json={"pregunta": VALIDACION[0]["pregunta"], "base": "veterinaria"})
    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert cuerpo["resultado"]["ok"]
    assert cuerpo["resultado"]["columnas"] == ["total"]


def test_consulta_con_esquema_propio_no_ejecuta(cliente):
    esquema = "CREATE TABLE clientes (id int, nombre varchar(80));"
    cuerpo = cliente.post("/api/sql", json={"pregunta": "¿Cuántos clientes hay?", "base": None, "esquema": esquema}).json()
    assert cuerpo["resultado"] is None


def test_correccion_con_error(cliente):
    cuerpo = cliente.post("/api/sql", json={"pregunta": "pregunta sin respuesta", "base": "veterinaria", "corregir": True}).json()
    assert cuerpo["intentos"] == 2
    assert cuerpo["resultado"]["ok"]


def test_validaciones(cliente):
    assert cliente.post("/api/sql", json={"pregunta": "hola", "base": "otra"}).status_code == 422
    assert cliente.post("/api/sql", json={"pregunta": "", "base": "airline"}).status_code == 422


def test_registro_y_metricas(cliente):
    for v in VALIDACION[:3]:
        cliente.post("/api/sql", json={"pregunta": v["pregunta"], "base": v["base"]})
    cliente.post("/api/sql", json={"pregunta": "pregunta sin respuesta", "base": "veterinaria"})
    metricas = cliente.get("/api/metricas").json()
    assert metricas["consultas"] == 4
    assert metricas["ejecucion_ok"] == 3
    assert metricas["latencia_mediana"] is not None
    assert len(cliente.get("/api/registros?ultimos=2").json()) == 2


def test_interfaz_web(cliente):
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert "gradio" in respuesta.text.lower()


def test_modelo_cargando(registro):
    from fastapi.testclient import TestClient
    from servicio.app import crear_app
    from conftest import ModeloFalso

    modelo = ModeloFalso()
    modelo.listo = False
    cliente = TestClient(crear_app(modelo=modelo, registro=registro, cargar_en_fondo=False))
    assert cliente.get("/api/salud").json()["estado"] == "cargando"
    assert cliente.post("/api/sql", json={"pregunta": "¿Cuántas mascotas hay?", "base": "veterinaria"}).status_code == 503
