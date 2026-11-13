import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servicio.app import crear_app
from servicio.registro import Registro

VALIDACION = json.loads((RAIZ / "datos" / "validacion_propia.json").read_text())


class ModeloFalso:
    nombre = "modelo falso"
    listo = True

    def __init__(self):
        self.respuestas = {v["pregunta"]: v["sql"] for v in VALIDACION}

    def cargar(self):
        pass

    def generar_sql(self, esquema, pregunta, ejecutar=None):
        sql = self.respuestas.get(pregunta, "SELECT columna_que_no_existe FROM vet_masc;")
        if ejecutar and not ejecutar(sql)["ok"]:
            return "SELECT COUNT(*) AS total FROM vet_masc;", 2
        return sql, 1


@pytest.fixture
def registro(tmp_path):
    return Registro(tmp_path / "uso.jsonl")


@pytest.fixture
def cliente(registro):
    return TestClient(crear_app(modelo=ModeloFalso(), registro=registro, cargar_en_fondo=False))
