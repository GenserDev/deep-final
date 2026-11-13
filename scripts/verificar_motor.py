import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from servicio.bases import Bases
from servicio.evaluador import comparar

bases = Bases()
corridas = pd.read_csv(RAIZ / "resultados" / "proyecto3" / "validacion_propia.csv")
filas = []
for _, fila in corridas.iterrows():
    referencia = bases.ejecutar(fila.base, fila.sql_referencia, limite=None)
    generada = bases.ejecutar(fila.base, str(fila.sql_generado), limite=None)
    acierto = referencia["ok"] and generada["ok"] and comparar(referencia["filas"], generada["filas"])
    filas.append({"corrida": fila.corrida, "pregunta": fila.pregunta, "acierto_mysql": bool(fila.acierto),
                  "acierto_sqlite": acierto, "coincide": bool(fila.acierto) == acierto})

verificacion = pd.DataFrame(filas)
verificacion.to_csv(RAIZ / "resultados" / "verificacion_motor.csv", index=False)
print(verificacion.groupby("corrida")[["acierto_mysql", "acierto_sqlite", "coincide"]].sum())
print(f"Coinciden {verificacion.coincide.sum()} de {len(verificacion)} veredictos")
