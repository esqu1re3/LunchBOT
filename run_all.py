#!/usr/bin/env python3
"""
Скрипт для запуска бота и админ-панели одновременно
"""
import os
import sys
import subprocess
import threading
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env файла
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
        logger.error("Требуется Python 3.8 или выше")
        sys.exit(1)

def check_dependencies():
    """Проверка установленных зависимостей"""
    packages_to_check = {
        'telebot': 'pyTelegramBotAPI',
        'streamlit': 'streamlit',
        'apscheduler': 'apscheduler',
        'pandas': 'pandas',
        'numpy': 'numpy'
    }
    
    missing_packages = []
    problematic_packages = []
    
    for import_name, package_name in packages_to_check.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_name)
        except Exception as e:
            problematic_packages.append((package_name, str(e)))
    
    if missing_packages:
        logger.error(f"Отсутствуют пакеты: {', '.join(missing_packages)}")
        logger.info("Установите их командой: pip install -r requirements.txt")
        sys.exit(1)
    
    if problematic_packages:
        logger.error("Проблемы с совместимостью пакетов:")
        for package, error in problematic_packages:
            logger.error(f"  {package}: {error}")
        logger.info("Рекомендуется переустановить пакеты:")
        logger.info("  pip uninstall numpy pandas -y")
        logger.info("  pip install -r requirements.txt")
        sys.exit(1)

def init_database():
    """Инициализация базы данных"""
    try:
        from bot.db import DatabaseManager
        logger.info("Инициализация базы данных...")
        
        db = DatabaseManager()
        logger.info("База данных инициализирована успешно")
        return db
        
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")
        sys.exit(1)

def get_bot_token():
    """Получение токена бота"""
    # Проверяем переменную окружения из .env
    token = os.getenv('BOT_TOKEN')
    
    if not token:
        logger.error("Токен бота не найден!")
        logger.info("Создайте файл .env на основе .env.example и укажите BOT_TOKEN")
        logger.info("Или установите переменную окружения: export BOT_TOKEN='your_bot_token_here'")
        
        # Предлагаем ввести токен
        try:
            token = input("Введите токен бота: ").strip()
            if not token:
                logger.error("Токен не может быть пустым")
                sys.exit(1)
        except KeyboardInterrupt:
            logger.info("Прервано пользователем")
            sys.exit(0)
    
    return token

def get_admin_chat_id():
    """Получение ID чата администратора"""
    admin_id = os.getenv('ADMIN_CHAT_ID')
    
    if not admin_id:
        logger.warning("ADMIN_CHAT_ID не найден в переменных окружения")
        logger.info("Добавьте ADMIN_CHAT_ID в файл .env для получения уведомлений об оспариваемых долгах")
        return None
    
    return admin_id

def run_bot(token):
    """Запуск бота в отдельном потоке"""
    try:
        from bot.main import LunchBot
        
        logger.info("Запуск Telegram бота...")
        bot = LunchBot(token)
        bot.start()
        
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

def run_streamlit():
    """Запуск Streamlit админ-панели"""
    try:
        logger.info("Запуск Streamlit админ-панели...")
        
        # Путь к файлу админ-панели
        app_path = Path(__file__).parent / "admin_panel" / "app.py"
        
        # Команда для запуска Streamlit
        cmd = [
            sys.executable, "-m", "streamlit", "run", str(app_path),
            "--server.headless", "true",
            "--server.port", "8501",
            "--server.address", "0.0.0.0"
        ]
        
        # Запускаем Streamlit
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        
        # Ждем запуска
        time.sleep(3)
        
        logger.info("Streamlit админ-панель запущена на http://localhost:8501")
        
        # Ожидаем завершения процесса
        process.wait()
        
    except KeyboardInterrupt:
        logger.info("Streamlit остановлен пользователем")
        if 'process' in locals():
            process.terminate()
    except Exception as e:
        logger.error(f"Ошибка при запуске Streamlit: {e}")

def main():
    """Главная функция"""
    print("🍽️ LunchBOT - Система учёта долгов за обед")
    print("=" * 50)
    
    # Проверяем версию Python
    check_python_version()
    
    # Проверяем зависимости
    check_dependencies()
    
    # Инициализируем базу данных
    db = init_database()
    
    # Получаем токен бота
    token = get_bot_token()
    
    # Получаем админ ID и сохраняем в базу
    admin_id = get_admin_chat_id()
    if admin_id:
        db.set_setting('admin_chat_id', admin_id)
        logger.info(f"Админ ID установлен: {admin_id}")
    
    print("\n🚀 Запуск системы...")
    print(f"📊 Админ-панель: http://localhost:8501")
    print(f"🤖 Telegram бот: запущен")
    print("\n⚡ Для остановки нажмите Ctrl+C")
    print("=" * 50)
    
    # Создаем потоки для бота и админ-панели
    bot_thread = threading.Thread(target=run_bot, args=(token,), daemon=True)
    streamlit_thread = threading.Thread(target=run_streamlit, daemon=True)
    
    try:
        # Запускаем потоки
        bot_thread.start()
        streamlit_thread.start()
        
        # Ожидаем завершения
        while bot_thread.is_alive() or streamlit_thread.is_alive():
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
        print("\n🛑 Остановка системы...")
        
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        
    finally:
        logger.info("Система остановлена")
        print("✅ Система остановлена")

if __name__ == "__main__":
    main() 