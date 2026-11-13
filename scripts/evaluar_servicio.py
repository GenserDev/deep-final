import argparse
import json
import statistics
import sys
from pathlib import Path

import httpx
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from servicio.bases import Bases
from servicio.evaluador import categoria_error, comparar
from servicio.registro import percentil

PESOS = {"facil": 1, "media": 2, "dificil": 3}
EX_MINIMA = 0.60
LATENCIA_MAXIMA = 30

parametros = argparse.ArgumentParser()
parametros.add_argument("--url", required=True)
parametros.add_argument("--corregir", action="store_true")
parametros.add_argument("--salida", default="evaluacion_produccion")
argumentos = parametros.parse_args()

validacion = json.loads((RAIZ / "datos" / "validacion_propia.json").read_text())
bases = Bases()
cliente = httpx.Client(base_url=argumentos.url.rstrip("/"), timeout=300)
print(cliente.get("/api/salud").json())

filas = []
for i, v in enumerate(validacion, 1):
    respuesta = cliente.post("/api/sql", json={"pregunta": v["pregunta"], "base": v["base"], "corregir": argumentos.corregir})
    respuesta.raise_for_status()
    cuerpo = respuesta.json()
    referencia = bases.ejecutar(v["base"], v["sql"], limite=None)
    generada = bases.ejecutar(v["base"], cuerpo["sql"], limite=None)
    acierto = generada["ok"] and comparar(referencia["filas"], generada["filas"], v["ordenado"])
    filas.append({"base": v["base"], "nivel": v["nivel"], "pregunta": v["pregunta"], "sql_referencia": v["sql"],
                  "sql_generado": cuerpo["sql"], "acierto": acierto, "peso": PESOS[v["nivel"]], "segundos": cuerpo["segundos"],
                  "intentos": cuerpo["intentos"],
                  "categoria_error": None if acierto else categoria_error(v["sql"], cuerpo["sql"], generada["error"])})
    print(f"{i:2d}/{len(validacion)} {'ok ' if acierto else 'mal'} {cuerpo['segundos']:6.1f} s  {v['pregunta'][:60]}")

tabla = pd.DataFrame(filas)
ex = (tabla.acierto * tabla.peso).sum() / tabla.peso.sum()
latencias = tabla.segundos.tolist()
resumen = {
    "url": argumentos.url, "modelo": cuerpo.get("modelo"), "corregir": argumentos.corregir,
    "EX": round(float(ex), 3), "aciertos": int(tabla.acierto.sum()),
    **{nivel: f"{int(g.acierto.sum())} de {len(g)}" for nivel, g in tabla.groupby("nivel")},
    "latencia_mediana": round(statistics.median(latencias), 2), "latencia_p95": percentil(latencias, 95),
    "cumple_EX": bool(ex >= EX_MINIMA), "cumple_latencia": bool(statistics.median(latencias) <= LATENCIA_MAXIMA),
}
tabla.to_csv(RAIZ / "resultados" / f"{argumentos.salida}.csv", index=False)
(RAIZ / "resultados" / f"{argumentos.salida}.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2))
print(json.dumps(resumen, ensure_ascii=False, indent=2))
