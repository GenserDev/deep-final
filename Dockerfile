FROM python:3.12-slim

RUN useradd -m -u 1000 usuario
USER usuario
ENV HOME=/home/usuario PATH=/home/usuario/.local/bin:$PATH PYTHONUNBUFFERED=1
WORKDIR /home/usuario/app

COPY --chown=usuario requirements.txt .
# La rueda de torch solo para CPU pesa la quinta parte que la de CUDA
RUN pip install --no-cache-dir --user torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --user -r requirements.txt

RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-1.7B')"

COPY --chown=usuario . .

EXPOSE 7860
CMD ["python", "app.py"]
