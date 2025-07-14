#!/bin/bash

# Запуск Telegram-бота
python3 main.py &

# Запуск админ-панели
uvicorn admin_panel.app:app --reload --port 8000 &

wait 