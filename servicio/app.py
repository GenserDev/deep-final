import threading
import time
import uuid

import gradio as gr
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from servicio.bases import BASES_DEMO, Bases, esquema_texto
from servicio.modelo import Modelo
from servicio.registro import Registro

ESQUEMA_PROPIO = "Esquema propio"
EJEMPLOS = {
    "veterinaria": [
        "¿Cuántas mascotas hay de cada especie?",
        "Muestra el nombre de las mascotas y el nombre de su dueño.",
        "¿Cuál es el costo promedio de las consultas por motivo?",
    ],
    "airline": [
        "¿Cuántos vuelos fueron cancelados?",
        "Muestra los 5 pasajeros que más han pagado en total.",
        "¿Cuántas reservas hay por clase?",
    ],
}


class Solicitud(BaseModel):
    pregunta: str = Field(min_length=3, max_length=500)
    base: str | None = Field(default="veterinaria", description="veterinaria, airline o null para usar esquema")
    esquema: str | None = Field(default=None, max_length=20000)
    corregir: bool = False


class Servicio:
    def __init__(self, modelo, registro, bases):
        self.modelo = modelo
        self.registro = registro
        self.bases = bases
        self.error_carga = None

    def cargar(self):
        try:
            self.modelo.cargar()
            self.registro.anotar({"tipo": "inicio", "modelo": self.modelo.nombre})
        except Exception as error:
            self.error_carga = str(error)
            self.registro.anotar({"tipo": "error_carga", "error": str(error)})

    def consultar(self, pregunta, base=None, esquema=None, corregir=False, origen="api"):
        if base not in BASES_DEMO and not esquema:
            raise ValueError("Elige una base de demostración o envía un esquema")
        if not self.modelo.listo:
            raise RuntimeError(self.error_carga or "El modelo todavía se está cargando")
        demo = base in BASES_DEMO
        esquema = esquema_texto(base) if demo else esquema
        ejecutar = (lambda sql: self.bases.ejecutar(base, sql, limite=10)) if demo and corregir else None
        inicio = time.perf_counter()
        evento = {"tipo": "consulta", "id": uuid.uuid4().hex[:8], "origen": origen, "base": base if demo else "propia",
                  "pregunta": pregunta, "modelo": self.modelo.nombre, "corregir": corregir}
        try:
            sql, intentos = self.modelo.generar_sql(esquema, pregunta, ejecutar)
        except Exception as error:
            self.registro.anotar({**evento, "error_servicio": str(error), "segundos": round(time.perf_counter() - inicio, 2)})
            raise
        segundos = round(time.perf_counter() - inicio, 2)
        resultado = self.bases.ejecutar(base, sql) if demo else None
        evento.update({"sql": sql, "intentos": intentos, "segundos": segundos, "ejecutada": demo,
                       "ok": resultado["ok"] if demo else None, "filas": len(resultado["filas"]) if demo else None,
                       "error_sql": resultado["error"] if demo else None})
        self.registro.anotar(evento)
        return {"id": evento["id"], "sql": sql, "segundos": segundos, "intentos": intentos,
                "resultado": resultado, "modelo": self.modelo.nombre}


def crear_api(servicio):
    api = FastAPI(title="Texto a SQL", description="Genera consultas MySQL a partir de preguntas en español")

    @api.get("/api/salud")
    def salud():
        estado = "listo" if servicio.modelo.listo else "error" if servicio.error_carga else "cargando"
        return {"estado": estado, "modelo": servicio.modelo.nombre, "error": servicio.error_carga}

    @api.get("/api/bases")
    def bases():
        return {nombre: esquema_texto(nombre) for nombre in BASES_DEMO}

    @api.post("/api/sql")
    def sql(solicitud: Solicitud):
        try:
            return servicio.consultar(solicitud.pregunta, solicitud.base, solicitud.esquema, solicitud.corregir)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error))

    @api.get("/api/metricas")
    def metricas():
        return servicio.registro.metricas()

    @api.get("/api/registros")
    def registros(ultimos: int = 50):
        return servicio.registro.leer(ultimos=min(max(ultimos, 1), 500))

    return api


def tabla_registros(servicio):
    columnas = ["fecha", "origen", "base", "pregunta", "sql", "ok", "segundos"]
    eventos = [e for e in servicio.registro.leer() if e.get("tipo") == "consulta"][-20:][::-1]
    return pd.DataFrame([{c: e.get(c) for c in columnas} for e in eventos], columns=columnas)


def crear_interfaz(servicio):
    def cambiar_base(base):
        if base == ESQUEMA_PROPIO:
            return gr.update(value="", interactive=True), gr.update(samples=[])
        return gr.update(value=esquema_texto(base), interactive=False), gr.update(samples=[[e] for e in EJEMPLOS[base]])

    def consultar(base, esquema, pregunta, corregir):
        demo = base != ESQUEMA_PROPIO
        try:
            respuesta = servicio.consultar(pregunta.strip(), base if demo else None, None if demo else esquema,
                                           corregir and demo, origen="web")
        except (ValueError, RuntimeError) as error:
            return "", pd.DataFrame(), f"**Error:** {error}"
        resultado = respuesta["resultado"]
        if resultado is None:
            return respuesta["sql"], pd.DataFrame(), f"Generada en {respuesta['segundos']} s. Con un esquema propio no se ejecuta."
        if not resultado["ok"]:
            return respuesta["sql"], pd.DataFrame(), f"Generada en {respuesta['segundos']} s. **Error al ejecutar:** {resultado['error']}"
        tabla = pd.DataFrame(resultado["filas"], columns=resultado["columnas"])
        return respuesta["sql"], tabla, f"Generada en {respuesta['segundos']} s. {len(tabla)} filas."

    with gr.Blocks(title="Texto a SQL") as interfaz:
        gr.Markdown("# Texto a SQL\nEscribe una pregunta en español y el modelo genera la consulta MySQL que la responde.")
        with gr.Tab("Consultar"):
            with gr.Row():
                with gr.Column():
                    base = gr.Dropdown(BASES_DEMO + [ESQUEMA_PROPIO], value=BASES_DEMO[0], label="Base de datos")
                    esquema = gr.Code(esquema_texto(BASES_DEMO[0]), language="sql", label="Esquema", interactive=False, max_lines=14)
                with gr.Column():
                    pregunta = gr.Textbox(label="Pregunta", placeholder="¿Cuántas mascotas hay de cada especie?")
                    ejemplos = gr.Dataset(components=[pregunta], samples=[[e] for e in EJEMPLOS[BASES_DEMO[0]]], label="Ejemplos")
                    corregir = gr.Checkbox(label="Corregir con el error de MySQL si la consulta falla")
                    boton = gr.Button("Generar SQL", variant="primary")
                    sql = gr.Code(language="sql", label="Consulta generada")
                    estado = gr.Markdown()
            resultado = gr.Dataframe(label="Resultado")
            base.change(cambiar_base, base, [esquema, ejemplos])
            ejemplos.click(lambda fila: fila[0], ejemplos, pregunta)
            boton.click(consultar, [base, esquema, pregunta, corregir], [sql, resultado, estado])
        with gr.Tab("Monitoreo"):
            actualizar = gr.Button("Actualizar")
            metricas = gr.JSON(label="Métricas")
            ultimas = gr.Dataframe(label="Últimas 20 consultas")
            actualizar.click(lambda: (servicio.registro.metricas(), tabla_registros(servicio)), None, [metricas, ultimas])
            interfaz.load(lambda: (servicio.registro.metricas(), tabla_registros(servicio)), None, [metricas, ultimas])
        with gr.Tab("API"):
            gr.Markdown(
                "Documentación interactiva en `/docs`.\n\n"
                "```bash\ncurl -X POST <url>/api/sql -H 'Content-Type: application/json' "
                "-d '{\"pregunta\": \"¿Cuántos vuelos fueron cancelados?\", \"base\": \"airline\"}'\n```\n\n"
                "`GET /api/salud` estado del modelo. `GET /api/metricas` métricas de uso. `GET /api/registros` últimas consultas."
            )
    return interfaz


def crear_app(modelo=None, registro=None, cargar_en_fondo=True):
    servicio = Servicio(modelo or Modelo(), registro or Registro(), Bases())
    if cargar_en_fondo:
        threading.Thread(target=servicio.cargar, daemon=True).start()
    api = crear_api(servicio)
    return gr.mount_gradio_app(api, crear_interfaz(servicio), path="/")
