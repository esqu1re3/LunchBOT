#!/usr/bin/env python3
"""
Точка входа для запуска асинхронного LunchBOT
"""
import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Добавляем родительскую директорию в путь для импорта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.async_main import main

def check_environment():
    """Проверка переменных окружения"""
    load_dotenv()
    
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        print("❌ Ошибка: BOT_TOKEN не найден в переменных окружения")
        print("Создайте файл .env и укажите BOT_TOKEN=ваш_токен_бота")
        return False
    
    return True

def setup_logging():
    """Настройка логирования"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('async_bot.log')
        ]
    )

if __name__ == "__main__":
    print("🚀 Запуск асинхронного LunchBOT...")
    
    # Проверка окружения
    if not check_environment():
        sys.exit(1)
    
    # Настройка логирования
    setup_logging()
    
    try:
        # Запуск асинхронного бота
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        sys.exit(1) 