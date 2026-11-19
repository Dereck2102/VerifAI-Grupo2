FROM mcr.microsoft.com/playwright/python:v1.48.0-noble

WORKDIR /app

# Instalar dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar navegadores de Playwright (Chromium sin interfaz gráfica para headless)
RUN playwright install chromium

# Copiar código fuente
COPY . .

# Variables de entorno
ENV HEADLESS=1
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

