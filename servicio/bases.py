import datetime
import random
import sqlite3
import sys
from pathlib import Path

import sqlglot

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "datos"))
from esquemas import ESQUEMAS_VALIDACION

BASES_DEMO = list(ESQUEMAS_VALIDACION)
LIMITE_FILAS = 200
TIPOS_SQLITE = {"INT": "INTEGER", "DATE": "TEXT"}


def esquema_texto(base):
    return (RAIZ / "datos" / "esquemas_sql" / f"{base}.sql").read_text()


# Replica valor_aleatorio de datos/construir.py del Proyecto 3 para obtener los mismos datos que en MySQL
def valor_aleatorio(rng, clase, extra, tablas_n):
    if clase in ("txt", "cat"):
        return rng.choice(extra)
    if clase == "int":
        return rng.randint(extra[0], extra[1])
    if clase == "dec":
        return round(rng.uniform(extra[0], extra[1]), 2)
    if clase == "fecha":
        inicio = datetime.date(extra[0], 1, 1)
        fin = datetime.date(extra[1], 12, 31)
        return inicio + datetime.timedelta(days=rng.randint(0, (fin - inicio).days))
    if clase == "fk":
        return rng.randint(1, max(1, int(tablas_n[extra] * 0.9)))


def tipo_sqlite(tipo):
    if tipo.startswith("DECIMAL"):
        return "REAL"
    if tipo.startswith("VARCHAR"):
        return "TEXT"
    return TIPOS_SQLITE[tipo]


def parte_fecha(indice):
    return lambda valor: None if valor is None else int(str(valor)[:10].split("-")[indice])


def dias_entre(fin, inicio):
    if fin is None or inicio is None:
        return None
    return (datetime.date.fromisoformat(str(fin)[:10]) - datetime.date.fromisoformat(str(inicio)[:10])).days


# SQLite no trae YEAR, MONTH, DAY ni DATEDIFF de MySQL y sqlglot los deja sin traducir
def registrar_funciones(conexion):
    for nombre, indice in [("YEAR", 0), ("MONTH", 1), ("DAY", 2)]:
        conexion.create_function(nombre, 1, parte_fecha(indice), deterministic=True)
    conexion.create_function("DATEDIFF", 2, dias_entre, deterministic=True)


def crear_base(nombre, semilla=2026):
    tablas = ESQUEMAS_VALIDACION[nombre]
    rng = random.Random(semilla)
    conexion = sqlite3.connect(":memory:", check_same_thread=False)
    registrar_funciones(conexion)
    tablas_n = {t["nombre"]: t["n"] for t in tablas}
    for tabla in tablas:
        columnas = [f'"{c[0]}" {tipo_sqlite(c[1])}' + (" PRIMARY KEY" if c[2] == "pk" else "") for c in tabla["cols"]]
        conexion.execute(f'CREATE TABLE "{tabla["nombre"]}" ({", ".join(columnas)})')
        cols = [c for c in tabla["cols"] if c[2] != "pk"]
        filas = [[valor_aleatorio(rng, c[2], c[4], tablas_n) for c in cols] for _ in range(tabla["n"])]
        filas = [[v.isoformat() if isinstance(v, datetime.date) else v for v in f] for f in filas]
        nombres = ", ".join(f'"{c[0]}"' for c in cols)
        marcas = ", ".join("?" * len(cols))
        conexion.executemany(f'INSERT INTO "{tabla["nombre"]}" ({nombres}) VALUES ({marcas})', filas)
    conexion.commit()
    return conexion


def traducir(sql):
    return sqlglot.transpile(sql, read="mysql", write="sqlite")[0]


def es_solo_lectura(sql):
    try:
        sentencias = sqlglot.parse(sql, read="mysql")
    except sqlglot.errors.ParseError:
        return False
    if len(sentencias) != 1 or sentencias[0] is None:
        return False
    arbol = sentencias[0]
    escritura = (sqlglot.exp.Insert, sqlglot.exp.Update, sqlglot.exp.Delete, sqlglot.exp.Drop, sqlglot.exp.Create)
    return isinstance(arbol, sqlglot.exp.Query) and arbol.find(*escritura) is None


class Bases:
    def __init__(self):
        self.conexiones = {nombre: crear_base(nombre) for nombre in BASES_DEMO}

    def ejecutar(self, base, sql, limite=LIMITE_FILAS):
        if not es_solo_lectura(sql):
            return {"ok": False, "columnas": [], "filas": [], "error": "Solo se permiten consultas SELECT"}
        try:
            cursor = self.conexiones[base].execute(traducir(sql))
            filas = cursor.fetchall()
            columnas = [d[0] for d in cursor.description]
            return {"ok": True, "columnas": columnas, "filas": filas[:limite] if limite else filas, "error": None}
        except Exception as error:
            return {"ok": False, "columnas": [], "filas": [], "error": str(error)}
