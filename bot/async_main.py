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

async def main():
    """Главная функция запуска асинхронного бота"""
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
        
        # Запуск бота
        logger.info("🚀 Асинхронный LunchBOT запущен!")
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        raise
    finally:
        # Остановка планировщика при завершении
        if 'scheduler' in locals():
            scheduler.stop()

if __name__ == "__main__":
    asyncio.run(main()) 