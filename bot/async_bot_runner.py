"""
Модуль для запуска асинхронного бота без сигналов
"""
import os
import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from .async_db import AsyncDatabaseManager
from .async_handlers import router
from .async_scheduler import AsyncScheduler

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_bot():
    """Запуск асинхронного бота без сигналов"""
    try:
        # Инициализация базы данных
        db = AsyncDatabaseManager()
        await db.init_database()
        logger.info("База данных инициализирована")
        
        # Создание бота и диспетчера
        bot = Bot(token=API_TOKEN)
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        # Подключение роутера с обработчиками
        dp.include_router(router)
        
        # Инициализация и запуск планировщика
        scheduler = AsyncScheduler(db, bot)
        await scheduler.setup_reminder_scheduler()
        await scheduler.setup_cleanup_scheduler()
        scheduler.start()
        logger.info("Планировщик запущен")
        
        # Запуск бота без сигналов
        logger.info("🚀 Асинхронный LunchBOT запущен!")
        
        # Используем простой polling без сигналов
        while True:
            try:
                await dp.start_polling(bot, skip_updates=True, polling_timeout=1)
            except KeyboardInterrupt:
                logger.info("Получен сигнал остановки")
                break
            except Exception as e:
                logger.error(f"Ошибка в polling: {e}")
                await asyncio.sleep(5)  # Пауза перед повторной попыткой
        
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        raise
    finally:
        # Остановка планировщика при завершении
        if 'scheduler' in locals():
            scheduler.stop()
        if 'bot' in locals():
            await bot.session.close()

def run_bot_sync():
    """Синхронная обертка для запуска бота"""
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    run_bot_sync() 