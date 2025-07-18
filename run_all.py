#!/usr/bin/env python3
"""
Главный модуль для запуска всей системы LunchBOT
"""
import os
import sys
import time
import logging
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_python_version():
    """Проверка версии Python"""
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

def check_dependencies():
    """Проверка зависимостей"""
    required_packages = {
        'aiogram': 'aiogram',
        'aiosqlite': 'aiosqlite', 
        'streamlit': 'streamlit',
        'pandas': 'pandas',
        'dotenv': 'python-dotenv',
        'apscheduler': 'apscheduler',
        'pytz': 'pytz'
    }
    
    missing_packages = []
    
    for import_name, package_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"❌ Отсутствуют зависимости: {', '.join(missing_packages)}")
        print("Установите их командой: pip install -r requirements.txt")
        sys.exit(1)
    
    print("✅ Все зависимости установлены")

async def init_database():
    """Инициализация асинхронной базы данных"""
    try:
        logger.info("Инициализация асинхронной базы данных...")
        from bot.async_db import AsyncDatabaseManager
        
        db = AsyncDatabaseManager()
        await db.init_database()
        logger.info("Асинхронная база данных инициализирована успешно")
        return db
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        raise

def get_bot_token():
    """Получение токена бота"""
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("❌ Не найден BOT_TOKEN в переменных окружения")
        print("Добавьте BOT_TOKEN в файл .env")
        sys.exit(1)
    return token

def get_admin_chat_id():
    """Получение ID администратора"""
    admin_id = os.getenv("ADMIN_CHAT_ID")
    if not admin_id:
        print("❌ Не найден ADMIN_CHAT_ID в переменных окружения")
        print("Добавьте ADMIN_CHAT_ID в файл .env")
        sys.exit(1)
    return admin_id

def run_async_bot(token):
    """Запуск асинхронного бота"""
    try:
        logger.info("Запуск асинхронного Telegram бота...")
        
        # Импортируем необходимые модули
        from bot.async_db import AsyncDatabaseManager
        from bot.async_handlers import router
        from bot.async_scheduler import AsyncScheduler
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        
        async def start_bot():
            # Инициализация базы данных
            db = AsyncDatabaseManager()
            await db.init_database()
            logger.info("База данных инициализирована")
            
            # Создание бота и диспетчера
            bot = Bot(token=token)
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
            
            try:
                await dp.start_polling(bot, skip_updates=True)
            except KeyboardInterrupt:
                logger.info("Получен сигнал остановки")
            finally:
                scheduler.stop()
                await bot.session.close()
        
        # Запускаем бота
        import asyncio
        asyncio.run(start_bot())
        
    except Exception as e:
        logger.error(f"Ошибка при запуске асинхронного бота: {e}")
        logger.error(f"Детали ошибки: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")





async def setup_admin_settings():
    """Настройка параметров администратора"""
    try:
        from bot.async_db import AsyncDatabaseManager
        
        db = AsyncDatabaseManager()
        admin_chat_id = get_admin_chat_id()
        
        # Устанавливаем ID администратора
        await db.set_setting('admin_chat_id', admin_chat_id)
        logger.info(f"Админ ID установлен: {admin_chat_id}")
        
        # Устанавливаем настройки по умолчанию если их нет
        if not await db.get_setting('reminder_frequency'):
            await db.set_setting('reminder_frequency', '1')
        if not await db.get_setting('reminder_time'):
            await db.set_setting('reminder_time', '17:30')
            
    except Exception as e:
        logger.error(f"Ошибка настройки админа: {e}")

def main():
    """Главная функция"""
    print("🍽️ LunchBOT - Асинхронная система учёта долгов за обед")
    print("=" * 60)
    
    # Проверки
    check_python_version()
    check_dependencies()
    
    # Инициализация
    import asyncio
    asyncio.run(init_database())
    asyncio.run(setup_admin_settings())
    
    # Получение токена
    token = get_bot_token()
    
    print("\n🚀 Запуск асинхронной системы...")
    print("📊 Админ-панель: http://localhost:8501")
    print("🤖 Асинхронный Telegram бот: запущен")
    print("\n⚡ Для остановки нажмите Ctrl+C")
    print("=" * 60)
    
    # Запускаем админ-панель в фоне
    import subprocess
    import time
    
    # Путь к файлу админ-панели
    app_path = Path(__file__).parent / "admin_panel" / "app.py"
    
    # Команда для запуска Streamlit
    cmd = [
        sys.executable, "-m", "streamlit", "run", str(app_path),
        "--server.headless", "true",
        "--server.port", "8501",
        "--server.address", "0.0.0.0"
    ]
    
    # Запускаем Streamlit в фоне
    streamlit_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    
    # Ждем запуска
    time.sleep(3)
    logger.info("Streamlit админ-панель запущена на http://localhost:8501")
    
    # Запускаем бота в главном потоке
    try:
        run_async_bot(token)
    except KeyboardInterrupt:
        print("\n🛑 Остановка системы...")
        if streamlit_process:
            streamlit_process.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main() 