"""
Главный файл бота - точка входа
"""
import os
import logging
import threading
from datetime import datetime
from telebot import TeleBot
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .db import DatabaseManager
from .handlers import BotHandlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LunchBot:
    """Главный класс бота"""
    
    def __init__(self, token: str, db_path: str = "lunchbot.db"):
        """
        Инициализация бота
        
        Args:
            token: Токен Telegram бота
            db_path: Путь к базе данных
        """
        self.token = token
        self.bot = TeleBot(token)
        self.db = DatabaseManager(db_path)
        self.handlers = BotHandlers(self.bot, self.db)
        self.scheduler = BackgroundScheduler()
        
        # Настраиваем планировщик напоминаний
        self.setup_reminder_scheduler()
        
        logger.info("Бот инициализирован")
    
    def setup_reminder_scheduler(self):
        """Настройка планировщика напоминаний"""
        try:
            # Получаем частоту и время напоминаний из настроек
            frequency = int(self.db.get_setting('reminder_frequency') or 1)
            reminder_time = self.db.get_setting('reminder_time') or '17:30'
            
            # Парсим время
            hour, minute = map(int, reminder_time.split(':'))
            
            # Добавляем задачу для отправки напоминаний
            from apscheduler.triggers.cron import CronTrigger
            
            if frequency == 1:
                # Каждый день в указанное время
                trigger = CronTrigger(hour=hour, minute=minute)
            else:
                # Каждые N дней в указанное время
                trigger = CronTrigger(hour=hour, minute=minute, day=f'*/{frequency}')
            
            self.scheduler.add_job(
                func=self.send_reminders,
                trigger=trigger,
                id='debt_reminders',
                name='Напоминания о долгах',
                replace_existing=True
            )
            
            logger.info(f"Планировщик напоминаний настроен (каждые {frequency} дней в {reminder_time})")
            
        except Exception as e:
            logger.error(f"Ошибка настройки планировщика: {e}")
    
    def send_reminders(self):
        """Отправка напоминаний о долгах"""
        try:
            # Получаем долги для напоминания
            debts = self.db.get_debts_for_reminder()
            
            logger.info(f"Найдено {len(debts)} долгов для напоминания")
            
            # Отправляем напоминания
            for debt in debts:
                try:
                    self.handlers.send_debt_reminder(debt)
                    logger.info(f"Напоминание отправлено для долга ID {debt['id']}")
                except Exception as e:
                    logger.error(f"Ошибка отправки напоминания для долга ID {debt['id']}: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминаний: {e}")
    
    def update_reminder_frequency(self, frequency: int):
        """
        Обновить частоту напоминаний
        
        Args:
            frequency: Новая частота в днях
        """
        try:
            # Сохраняем в базу
            self.db.set_setting('reminder_frequency', str(frequency))
            
            # Перенастраиваем планировщик
            self.setup_reminder_scheduler()
            
            logger.info(f"Частота напоминаний обновлена на {frequency} дней")
            
        except Exception as e:
            logger.error(f"Ошибка обновления частоты напоминаний: {e}")
    
    def start(self):
        """Запуск бота"""
        try:
            logger.info("Запуск бота...")
            
            # Запускаем планировщик
            self.scheduler.start()
            logger.info("Планировщик запущен")
            
            # Запускаем бота
            self.bot.polling(none_stop=True, interval=0)
            
        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки")
            self.stop()
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            raise
    
    def stop(self):
        """Остановка бота"""
        try:
            logger.info("Остановка бота...")
            
            # Останавливаем планировщик
            if self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("Планировщик остановлен")
            
            # Останавливаем бота
            self.bot.stop_polling()
            logger.info("Бот остановлен")
            
        except Exception as e:
            logger.error(f"Ошибка при остановке бота: {e}")

def main():
    """Главная функция для запуска бота"""
    # Получаем токен из переменной окружения
    token = os.getenv('BOT_TOKEN')
    
    if not token:
        logger.error("Не найден токен бота! Установите переменную окружения BOT_TOKEN")
        return
    
    # Создаем и запускаем бота
    bot = LunchBot(token)
    bot.start()

def run_bot_thread(token: str, db_path: str = "lunchbot.db"):
    """
    Запуск бота в отдельном потоке
    
    Args:
        token: Токен Telegram бота
        db_path: Путь к базе данных
    """
    try:
        bot = LunchBot(token, db_path)
        bot.start()
    except Exception as e:
        logger.error(f"Ошибка в потоке бота: {e}")

if __name__ == "__main__":
    main() 