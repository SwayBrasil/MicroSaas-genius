FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dos2unix para compatibilidade Windows/Linux
RUN apt-get update && apt-get install -y dos2unix && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app
COPY start.sh /app/start.sh

# Converter line endings e dar permissões de execução
RUN dos2unix /app/start.sh && \
    chmod +x /app/start.sh

EXPOSE 8000
CMD ["/app/start.sh"]
