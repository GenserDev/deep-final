import json
import os
import statistics
import threading
from datetime import datetime, timezone
from pathlib import Path

RUTA_REGISTRO = Path(os.environ.get("RUTA_REGISTRO", Path(__file__).resolve().parent.parent / "registros" / "uso.jsonl"))


def percentil(valores, p):
    if not valores:
        return None
    ordenados = sorted(valores)
    indice = min(len(ordenados) - 1, round(p / 100 * (len(ordenados) - 1)))
    return ordenados[indice]


class Registro:
    def __init__(self, ruta=RUTA_REGISTRO):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.candado = threading.Lock()

    def anotar(self, evento):
        evento = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), **evento}
        with self.candado, self.ruta.open("a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(evento, ensure_ascii=False, default=str) + "\n")
        return evento

    def leer(self, ultimos=None):
        if not self.ruta.exists():
            return []
        with self.ruta.open(encoding="utf-8") as archivo:
            eventos = [json.loads(linea) for linea in archivo if linea.strip()]
        return eventos[-ultimos:] if ultimos else eventos

    def metricas(self):
        eventos = self.leer()
        consultas = [e for e in eventos if e.get("tipo") == "consulta"]
        latencias = [e["segundos"] for e in consultas if e.get("segundos") is not None]
        ejecutadas = [e for e in consultas if e.get("ejecutada")]
        por_base = {}
        for e in consultas:
            por_base[e.get("base", "propia")] = por_base.get(e.get("base", "propia"), 0) + 1
        por_origen = {}
        for e in consultas:
            por_origen[e.get("origen", "api")] = por_origen.get(e.get("origen", "api"), 0) + 1
        return {
            "consultas": len(consultas),
            "errores_servicio": sum(1 for e in consultas if e.get("error_servicio")),
            "ejecutadas": len(ejecutadas),
            "ejecucion_ok": sum(1 for e in ejecutadas if e.get("ok")),
            "tasa_ejecucion_ok": round(sum(1 for e in ejecutadas if e.get("ok")) / len(ejecutadas), 3) if ejecutadas else None,
            "latencia_mediana": round(statistics.median(latencias), 2) if latencias else None,
            "latencia_p95": percentil(latencias, 95),
            "por_base": por_base,
            "por_origen": por_origen,
            "primera": consultas[0]["fecha"] if consultas else None,
            "ultima": consultas[-1]["fecha"] if consultas else None,
        }
