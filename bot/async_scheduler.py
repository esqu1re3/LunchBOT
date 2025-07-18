"""
Асинхронный планировщик для LunchBOT
"""
import logging
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .async_db import AsyncDatabaseManager
from .async_messages import debt_reminder_message, format_datetime
from .async_keyboards import get_debt_actions_keyboard

logger = logging.getLogger(__name__)

class AsyncScheduler:
    """Асинхронный планировщик для напоминаний и очистки"""
    
    def __init__(self, db: AsyncDatabaseManager, bot=None):
        """
        Инициализация планировщика
        
        Args:
            db: Асинхронный менеджер базы данных
            bot: Экземпляр бота для отправки сообщений
        """
        self.db = db
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        
    async def setup_reminder_scheduler(self):
        """Настройка планировщика напоминаний"""
        try:
            # Получаем частоту и время напоминаний из настроек
            frequency = int(await self.db.get_setting('reminder_frequency') or 1)
            reminder_time = await self.db.get_setting('reminder_time') or '17:30'
            
            # Парсим время
            hour, minute = map(int, reminder_time.split(':'))
            
            # Добавляем задачу для отправки напоминаний
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
    
    async def setup_cleanup_scheduler(self):
        """Настройка планировщика очистки устаревших операций"""
        try:
            # Добавляем задачу для очистки устаревших операций каждые 30 минут
            self.scheduler.add_job(
                func=self.cleanup_expired_operations,
                trigger=IntervalTrigger(minutes=30),
                id='cleanup_operations',
                name='Очистка устаревших операций',
                replace_existing=True
            )
            
            logger.info("Планировщик очистки устаревших операций настроен (каждые 30 минут)")
            
        except Exception as e:
            logger.error(f"Ошибка планировщика очистки: {e}")
    
    async def cleanup_expired_operations(self):
        """Очистка устаревших операций"""
        try:
            deleted_count = await self.db.cleanup_expired_operations()
            if deleted_count > 0:
                logger.info(f"Удалено {deleted_count} устаревших операций")
        except Exception as e:
            logger.error(f"Ошибка очистки устаревших операций: {e}")
    
    async def send_reminders(self):
        """Отправка напоминаний о долгах"""
        try:
            if not self.bot:
                logger.warning("Бот не инициализирован, пропускаем отправку напоминаний")
                return
                
            # Получаем долги для напоминания
            debts = await self.db.get_debts_for_reminder()
            
            logger.info(f"Найдено {len(debts)} долгов для напоминания")
            
            # Отправляем напоминания
            for debt in debts:
                try:
                    await self.send_debt_reminder(debt)
                    # Обновляем время последнего напоминания
                    await self.db.update_reminder_sent(debt['id'])
                    logger.info(f"Напоминание отправлено для долга ID {debt['id']}")
                    
                    # Небольшая задержка между отправками
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Ошибка отправки напоминания для долга ID {debt['id']}: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминаний: {e}")
    
    async def send_debt_reminder(self, debt: dict):
        """
        Отправить напоминание о долге
        
        Args:
            debt: Данные долга
        """
        try:
            debtor_id = debt['debtor_id']
            creditor_name = debt['creditor_name'] or debt['creditor_username'] or f"User {debt['creditor_id']}"
            
            reminder_text = debt_reminder_message(
                creditor_name=creditor_name,
                amount=debt['amount'],
                description=debt['description'] or "без описания",
                created_at=format_datetime(debt['created_at'])
            )
            
            keyboard = await get_debt_actions_keyboard(debt['id'])
            
            await self.bot.send_message(
                chat_id=debtor_id,
                text=reminder_text,
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания должнику {debt['debtor_id']}: {e}")
    
    def start(self):
        """Запуск планировщика"""
        try:
            self.scheduler.start()
            logger.info("Асинхронный планировщик запущен")
        except Exception as e:
            logger.error(f"Ошибка запуска планировщика: {e}")
    
    def stop(self):
        """Остановка планировщика"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("Асинхронный планировщик остановлен")
        except Exception as e:
            logger.error(f"Ошибка остановки планировщика: {e}")
    
    async def update_reminder_frequency(self, frequency: int):
        """
        Обновить частоту напоминаний
        
        Args:
            frequency: Новая частота в днях
        """
        try:
            # Сохраняем в базу
            await self.db.set_setting('reminder_frequency', str(frequency))
            
            # Перенастраиваем планировщик
            await self.setup_reminder_scheduler()
            
            logger.info(f"Частота напоминаний обновлена на {frequency} дней")
            
        except Exception as e:
            logger.error(f"Ошибка обновления частоты напоминаний: {e}")
    
    async def update_reminder_time(self, time_str: str):
        """
        Обновить время напоминаний
        
        Args:
            time_str: Новое время в формате HH:MM
        """
        try:
            # Сохраняем в базу
            await self.db.set_setting('reminder_time', time_str)
            
            # Перенастраиваем планировщик
            await self.setup_reminder_scheduler()
            
            logger.info(f"Время напоминаний обновлено на {time_str}")
            
        except Exception as e:
            logger.error(f"Ошибка обновления времени напоминаний: {e}") 