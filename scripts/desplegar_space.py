import argparse
import os
from pathlib import Path

from huggingface_hub import HfApi

RAIZ = Path(__file__).resolve().parent.parent
ENCABEZADO = """---
title: Texto a SQL
emoji: 🗄️
colorFrom: gray
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

Servicio del Proyecto Final de Deep Learning (UVG 2026). Código y documentación en https://github.com/GenserDev/deep-final
"""

parametros = argparse.ArgumentParser()
parametros.add_argument("--space", required=True, help="usuario/nombre del Space")
argumentos = parametros.parse_args()

api = HfApi(token=os.environ["HF_TOKEN"])
api.create_repo(argumentos.space, repo_type="space", space_sdk="docker", exist_ok=True)
api.upload_folder(
    folder_path=RAIZ, repo_id=argumentos.space, repo_type="space",
    allow_patterns=["app.py", "config.json", "requirements.txt", "Dockerfile", "servicio/*", "datos/*", "datos/esquemas_sql/*", "adapter/*"],
)
api.upload_file(path_or_fileobj=ENCABEZADO.encode(), path_in_repo="README.md", repo_id=argumentos.space, repo_type="space")
print(f"https://huggingface.co/spaces/{argumentos.space}")
