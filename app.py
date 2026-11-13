import os

import uvicorn

from servicio.app import crear_app

app = crear_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)))
