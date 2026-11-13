#!/bin/bash
cd "$(dirname "$0")/.."
python app.py &
servicio=$!
trap "kill $servicio" EXIT
until curl -s localhost:7860/api/salud > /dev/null; do sleep 2; done
cloudflared tunnel --url http://localhost:7860
