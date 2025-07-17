# syntax=docker/dockerfile:1
FROM python:3.10-slim

WORKDIR /app

# Установим системные зависимости для Pillow и других пакетов
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libjpeg-dev \
        zlib1g-dev \
        libpq-dev \
        gcc \
        git \
        && rm -rf /var/lib/apt/lists/*

# Копируем зависимости и исходники
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Копируем .env, если есть (docker-compose монтирует его автоматически)

# Открываем порт для Streamlit
EXPOSE 8501

# Запуск всей системы (бот + админ-панель)
CMD ["python3", "run_all.py"] 