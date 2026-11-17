FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app DATA_DIR=/data
EXPOSE 8000
# Producción en un solo contenedor: gateway en $PORT + 6 microservicios internos.
CMD ["python", "run_all.py"]
