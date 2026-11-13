import gc
import json
import os
import re
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = json.loads((RAIZ / "config.json").read_text())

SISTEMA = ("Eres un experto en MySQL 8. Con el esquema dado escribe una sola consulta SELECT "
           "que responda la pregunta. Responde solo con la consulta SQL, sin explicaciones.")


def compactar_esquema(esquema):
    salida = []
    cuerpo = []
    for linea in esquema.splitlines():
        linea = linea.strip().replace("`", "")
        if not linea:
            continue
        if linea.startswith("CREATE TABLE"):
            salida.append(linea)
            cuerpo = []
        elif linea.startswith(")"):
            comentario = re.search(r"COMMENT='(.*)'", linea)
            salida.append(",\n".join(cuerpo))
            salida.append(f") COMMENT='{comentario.group(1)}';" if comentario else ");")
        elif linea.startswith(("KEY", "UNIQUE KEY", "INDEX", "FULLTEXT")):
            continue
        elif linea.startswith("CONSTRAINT"):
            fk = re.search(r"FOREIGN KEY \((.*?)\) REFERENCES (\S+) \((.*?)\)", linea)
            if fk:
                cuerpo.append(f"  FOREIGN KEY ({fk.group(1)}) REFERENCES {fk.group(2)}({fk.group(3)})")
        else:
            linea = linea.rstrip(",")
            for patron in [r" NOT NULL", r" NULL", r" AUTO_INCREMENT", r" DEFAULT ('[^']*'|\S+)",
                           r" CHARACTER SET \S+", r" COLLATE \S+", r" ON UPDATE \S+"]:
                linea = re.sub(patron, "", linea)
            cuerpo.append("  " + linea)
    return "\n".join(salida)


def armar_mensajes(esquema, pregunta, sql_previo=None, error=None):
    texto = f"Esquema:\n{compactar_esquema(esquema)}\n\nPregunta: {pregunta}"
    if sql_previo:
        texto += f"\n\nEsta consulta dio un error:\n{sql_previo}\nError: {error}\nEscribe una consulta corregida."
    return [{"role": "system", "content": SISTEMA}, {"role": "user", "content": texto}]


def limpiar_sql(texto):
    texto = texto.replace("```sql", "").replace("```", "").strip()
    texto = texto.split(";")[0].strip()
    inicio = re.search(r"\b(WITH|SELECT)\b", texto, re.IGNORECASE)
    if inicio:
        texto = texto[inicio.start():]
    return texto + ";"


class Modelo:
    def __init__(self, usar_adapter=None):
        self.usar_adapter = CONFIG["usar_adapter"] if usar_adapter is None else usar_adapter
        self.nombre = CONFIG["modelo_base"] + (" + adapter LoRA" if self.usar_adapter else "")
        self.tokenizer = None
        self.red = None
        self.candado = threading.Lock()

    @property
    def listo(self):
        return self.red is not None

    def cargar(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        gc.collect()
        torch.manual_seed(CONFIG["semilla"])
        base = os.environ.get("RUTA_MODELO", CONFIG["modelo_base"])
        if torch.cuda.is_available():
            dispositivo, tipo = "cuda", torch.float16
        else:
            # float32 en CPU porque bfloat16 sin soporte de hardware es varias veces más lento
            dispositivo, tipo = "cpu", torch.float32
        self.tokenizer = AutoTokenizer.from_pretrained(base)
        red = AutoModelForCausalLM.from_pretrained(base, dtype=tipo).to(dispositivo)
        if self.usar_adapter:
            from peft import PeftModel
            red = PeftModel.from_pretrained(red, str(RAIZ / CONFIG["adapter"])).merge_and_unload()
        red.eval()
        self.red = red

    def generar(self, mensajes):
        import torch

        # enable_thinking=False desactiva el modo de razonamiento de Qwen3
        prompt = self.tokenizer.apply_chat_template(mensajes, tokenize=False, add_generation_prompt=True,
                                                    enable_thinking=False)
        entrada = self.tokenizer(prompt, return_tensors="pt").to(self.red.device)
        with self.candado, torch.no_grad():
            salida = self.red.generate(**entrada, max_new_tokens=CONFIG["max_tokens"], do_sample=False,
                                       pad_token_id=self.tokenizer.eos_token_id)
        nuevo = salida[0][entrada["input_ids"].shape[1]:]
        return limpiar_sql(self.tokenizer.decode(nuevo, skip_special_tokens=True))

    def generar_sql(self, esquema, pregunta, ejecutar=None, max_correcciones=2):
        sql = self.generar(armar_mensajes(esquema, pregunta))
        intentos = 1
        if ejecutar is None:
            return sql, intentos
        for _ in range(max_correcciones):
            resultado = ejecutar(sql)
            if resultado["ok"]:
                break
            sql = self.generar(armar_mensajes(esquema, pregunta, sql, resultado["error"]))
            intentos += 1
        return sql, intentos
