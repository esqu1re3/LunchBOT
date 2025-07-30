"""
Асинхронный менеджер базы данных для LunchBOT
"""
import aiosqlite
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import asyncio

logger = logging.getLogger(__name__)

class AsyncDatabaseManager:
    """Асинхронный менеджер базы данных"""
    
    def __init__(self, db_path: str = "lunchbot.db"):
        """
        Инициализация асинхронного менеджера БД
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self._lock = asyncio.Lock()
    
    async def init_database(self):
        """
        Инициализация базы данных
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Читаем схему из файла
                with open('schema.sql', 'r', encoding='utf-8') as f:
                    schema = f.read()
                
                # Выполняем схему
                await db.executescript(schema)
                
                # Миграция: добавляем поля QR-кодов если их нет
                await self._migrate_qr_codes_fields(db)
                
                await db.commit()
                logger.info("База данных инициализирована успешно")
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise

    async def _migrate_qr_codes_fields(self, db):
        """
        Миграция для добавления полей QR-кодов
        
        Args:
            db: Соединение с базой данных
        """
        try:
            # Проверяем, есть ли уже поля QR-кодов
            async with db.execute("PRAGMA table_info(users)") as cursor:
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                # Добавляем поля если их нет
                if 'qr_code_file_id' not in column_names:
                    await db.execute("ALTER TABLE users ADD COLUMN qr_code_file_id TEXT")
                    logger.info("Добавлено поле qr_code_file_id")
                
                if 'qr_code_description' not in column_names:
                    await db.execute("ALTER TABLE users ADD COLUMN qr_code_description TEXT")
                    logger.info("Добавлено поле qr_code_description")
                    
        except Exception as e:
            logger.error(f"Ошибка миграции QR-кодов: {e}")
    
    async def get_connection(self) -> aiosqlite.Connection:
        """Получить соединение с базой данных"""
        return await aiosqlite.connect(self.db_path)
    
    async def create_operation_hash(self, operation_type: str, user_id: int, **kwargs) -> str:
        """
        Создать хэш операции для идемпотентности
        
        Args:
            operation_type: Тип операции
            user_id: ID пользователя
            **kwargs: Дополнительные параметры
            
        Returns:
            Хэш операции
        """
        hash_data = {
            'operation_type': operation_type,
            'user_id': user_id,
            **kwargs
        }
        sorted_data = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(sorted_data.encode('utf-8')).hexdigest()
    
    async def check_operation_processed(self, operation_hash: str) -> Optional[Dict[str, Any]]:
        """
        Проверить, была ли операция уже обработана
        
        Args:
            operation_hash: Хэш операции
            
        Returns:
            Данные обработанной операции или None
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM processed_operations WHERE operation_hash = ?",
                (operation_hash,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None
    
    async def record_processed_operation(self, operation_hash: str, operation_type: str, 
                                       user_id: int, operation_data: Dict[str, Any], 
                                       result_id: Optional[int] = None, 
                                       expires_minutes: int = 5) -> bool:
        """
        Записать обработанную операцию
        
        Args:
            operation_hash: Хэш операции
            operation_type: Тип операции
            user_id: ID пользователя
            operation_data: Данные операции
            result_id: ID результата
            expires_minutes: Время жизни в минутах
            
        Returns:
            True если успешно записано
        """
        try:
            expires_at = datetime.now() + timedelta(minutes=expires_minutes)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """INSERT OR REPLACE INTO processed_operations 
                       (operation_hash, operation_type, user_id, operation_data, result_id, expires_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (operation_hash, operation_type, user_id, 
                     json.dumps(operation_data), result_id, expires_at.isoformat())
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка записи обработанной операции: {e}")
            return False
    
    async def cleanup_expired_operations(self) -> int:
        """
        Очистить устаревшие операции
        
        Returns:
            Количество удаленных записей
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                result = await db.execute(
                    "DELETE FROM processed_operations WHERE datetime(expires_at) <= datetime('now')"
                )
                await db.commit()
                return result.rowcount
        except Exception as e:
            logger.error(f"Ошибка очистки устаревших операций: {e}")
            return 0
    
    async def check_duplicate_debt(self, debtor_id: int, creditor_id: int, 
                                 amount: float, description: str = None, 
                                 minutes_window: int = 5) -> Optional[int]:
        """
        Проверить дублирование долга в течение временного окна
        
        Args:
            debtor_id: ID должника
            creditor_id: ID кредитора
            amount: Сумма долга
            description: Описание долга
            minutes_window: Временное окно в минутах
            
        Returns:
            ID существующего долга или None
        """
        try:
            cutoff_time = datetime.now() - timedelta(minutes=minutes_window)
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """SELECT id FROM debts 
                       WHERE debtor_id = ? AND creditor_id = ? AND amount = ? 
                       AND (description = ? OR (description IS NULL AND ? IS NULL))
                       AND created_at >= ?
                       AND status = 'Open'
                       ORDER BY created_at DESC LIMIT 1""",
                    (debtor_id, creditor_id, amount, description, description, cutoff_time.isoformat())
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return row['id']
                    return None
        except Exception as e:
            logger.error(f"Ошибка проверки дублирования долга: {e}")
            return None
    
    async def check_duplicate_payment(self, debt_id: int, debtor_id: int) -> Optional[int]:
        """
        Проверить дублирование платежа
        
        Args:
            debt_id: ID долга
            debtor_id: ID должника
            
        Returns:
            ID существующего платежа или None
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """SELECT id FROM payments 
                       WHERE debt_id = ? AND debtor_id = ? 
                       AND status IN ('Pending', 'Confirmed')
                       ORDER BY created_at DESC LIMIT 1""",
                    (debt_id, debtor_id)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return row['id']
                    return None
        except Exception as e:
            logger.error(f"Ошибка проверки дублирования платежа: {e}")
            return None
    
    async def create_user(self, user_id: int, username: str = None, 
                         first_name: str = None, last_name: str = None) -> bool:
        """
        Создать пользователя
        
        Args:
            user_id: ID пользователя в Telegram
            username: Username пользователя
            first_name: Имя пользователя
            last_name: Фамилия пользователя
            
        Returns:
            True если пользователь создан успешно
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                       VALUES (?, ?, ?, ?)""",
                    (user_id, username, first_name, last_name)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка создания пользователя: {e}")
            return False
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить пользователя по ID
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Данные пользователя или None
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM users WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
                    return None
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None
    
    async def get_all_users(self) -> List[Dict[str, Any]]:
        """
        Получить всех пользователей
        
        Returns:
            Список пользователей
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM users ORDER BY first_name, username"
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения всех пользователей: {e}")
            return []
    
    async def update_user_name(self, user_id: int, first_name: str, last_name: str = None) -> bool:
        """
        Обновить имя пользователя
        
        Args:
            user_id: ID пользователя
            first_name: Новое имя
            last_name: Новая фамилия
            
        Returns:
            True если обновление успешно
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET first_name = ?, last_name = ? WHERE user_id = ?",
                    (first_name, last_name, user_id)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления имени пользователя: {e}")
            return False
    
    async def create_debt(self, debtor_id: int, creditor_id: int, amount: float, 
                         description: str = None) -> Optional[int]:
        """
        Создать долг с проверкой дублирования
        
        Args:
            debtor_id: ID должника
            creditor_id: ID кредитора
            amount: Сумма долга
            description: Описание долга
            
        Returns:
            ID созданного долга или None
        """
        try:
            # Проверяем дублирование
            existing_debt_id = await self.check_duplicate_debt(debtor_id, creditor_id, amount, description)
            if existing_debt_id:
                logger.info(f"Найден дублирующий долг {existing_debt_id}, возвращаем его")
                return existing_debt_id
            
            async with aiosqlite.connect(self.db_path) as db:
                result = await db.execute(
                    """INSERT INTO debts (debtor_id, creditor_id, amount, description)
                       VALUES (?, ?, ?, ?)""",
                    (debtor_id, creditor_id, amount, description)
                )
                await db.commit()
                return result.lastrowid
        except Exception as e:
            logger.error(f"Ошибка создания долга: {e}")
            return None
    
    async def get_debt(self, debt_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить долг по ID
        
        Args:
            debt_id: ID долга
            
        Returns:
            Данные долга или None
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """SELECT d.*, 
                           u1.first_name as debtor_name, u1.username as debtor_username,
                           u2.first_name as creditor_name, u2.username as creditor_username
                       FROM debts d
                       JOIN users u1 ON d.debtor_id = u1.user_id
                       JOIN users u2 ON d.creditor_id = u2.user_id
                       WHERE d.id = ?""",
                    (debt_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
                    return None
        except Exception as e:
            logger.error(f"Ошибка получения долга: {e}")
            return None
    
    async def get_open_debts(self) -> List[Dict[str, Any]]:
        """
        Получить все открытые долги
        
        Returns:
            Список открытых долгов
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """SELECT d.*, 
                           u1.first_name as debtor_name, u1.username as debtor_username,
                           u2.first_name as creditor_name, u2.username as creditor_username
                       FROM debts d
                       JOIN users u1 ON d.debtor_id = u1.user_id
                       JOIN users u2 ON d.creditor_id = u2.user_id
                       WHERE d.status = 'Open'
                       ORDER BY d.created_at DESC"""
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения открытых долгов: {e}")
            return []
    
    async def get_user_debts(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получить долги пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список долгов пользователя
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """SELECT d.*, 
                           u1.first_name as debtor_name, u1.username as debtor_username,
                           u2.first_name as creditor_name, u2.username as creditor_username
                       FROM debts d
                       JOIN users u1 ON d.debtor_id = u1.user_id
                       JOIN users u2 ON d.creditor_id = u2.user_id
                       WHERE d.debtor_id = ? AND d.status = 'Open'
                       ORDER BY d.created_at DESC""",
                    (user_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения долгов пользователя: {e}")
            return []
    
    async def close_debt(self, debt_id: int) -> bool:
        """
        Закрыть долг
        
        Args:
            debt_id: ID долга
            
        Returns:
            True если долг закрыт успешно
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE debts SET status = 'Closed', closed_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), debt_id)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка закрытия долга: {e}")
            return False
    
    async def create_payment(self, debt_id: int, debtor_id: int, creditor_id: int, 
                           file_id: str = None) -> Optional[int]:
        """
        Создать платеж с проверкой дублирования
        
        Args:
            debt_id: ID долга
            debtor_id: ID должника
            creditor_id: ID кредитора
            file_id: ID файла чека
            
        Returns:
            ID созданного платежа или None
        """
        try:
            # Проверяем дублирование
            existing_payment_id = await self.check_duplicate_payment(debt_id, debtor_id)
            if existing_payment_id:
                logger.info(f"Найден дублирующий платеж {existing_payment_id}, возвращаем его")
                return existing_payment_id
            
            async with aiosqlite.connect(self.db_path) as db:
                result = await db.execute(
                    """INSERT INTO payments (debt_id, debtor_id, creditor_id, file_id)
                       VALUES (?, ?, ?, ?)""",
                    (debt_id, debtor_id, creditor_id, file_id)
                )
                await db.commit()
                return result.lastrowid
        except Exception as e:
            logger.error(f"Ошибка создания платежа: {e}")
            return None
    
    async def get_payment(self, payment_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить платеж по ID
        
        Args:
            payment_id: ID платежа
            
        Returns:
            Данные платежа или None
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM payments WHERE id = ?",
                    (payment_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
                    return None
        except Exception as e:
            logger.error(f"Ошибка получения платежа: {e}")
            return None
    
    async def confirm_payment(self, payment_id: int) -> bool:
        """
        Подтвердить платеж с идемпотентностью
        
        Args:
            payment_id: ID платежа
            
        Returns:
            True если платеж подтвержден
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Проверяем текущий статус
                async with db.execute(
                    "SELECT status FROM payments WHERE id = ?",
                    (payment_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return False
                    
                    if row[0] == 'Confirmed':
                        logger.info(f"Платеж {payment_id} уже подтвержден")
                        return True
                
                # Подтверждаем платеж
                await db.execute(
                    "UPDATE payments SET status = 'Confirmed', confirmed_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), payment_id)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка подтверждения платежа: {e}")
            return False
    
    async def cancel_payment(self, payment_id: int, reason: str = None) -> bool:
        """
        Отклонить платеж
        
        Args:
            payment_id: ID платежа
            reason: Причина отклонения
            
        Returns:
            True если платеж отклонен
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Проверяем текущий статус
                async with db.execute(
                    "SELECT status FROM payments WHERE id = ?",
                    (payment_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return False
                    
                    if row[0] == 'Cancelled':
                        logger.info(f"Платеж {payment_id} уже отклонен")
                        return True
                
                # Отклоняем платеж
                await db.execute(
                    "UPDATE payments SET status = 'Cancelled', cancelled_at = ?, cancel_reason = ? WHERE id = ?",
                    (datetime.now().isoformat(), reason, payment_id)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка отклонения платежа: {e}")
            return False
    
    async def get_setting(self, key: str) -> Optional[str]:
        """
        Получить настройку
        
        Args:
            key: Ключ настройки
            
        Returns:
            Значение настройки или None
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT value FROM settings WHERE key = ?",
                    (key,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return row[0]
                    return None
        except Exception as e:
            logger.error(f"Ошибка получения настройки: {e}")
            return None
    
    async def set_setting(self, key: str, value: str) -> bool:
        """
        Установить настройку
        
        Args:
            key: Ключ настройки
            value: Значение настройки
            
        Returns:
            True если настройка установлена
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """INSERT OR REPLACE INTO settings (key, value, updated_at)
                       VALUES (?, ?, ?)""",
                    (key, value, datetime.now().isoformat())
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка установки настройки: {e}")
            return False
    
    async def get_debts_for_reminder(self) -> List[Dict[str, Any]]:
        """
        Получить долги для напоминания
        
        Returns:
            Список долгов для напоминания
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """SELECT d.*, 
                           u1.first_name as debtor_name, u1.username as debtor_username,
                           u2.first_name as creditor_name, u2.username as creditor_username
                       FROM debts d
                       JOIN users u1 ON d.debtor_id = u1.user_id
                       JOIN users u2 ON d.creditor_id = u2.user_id
                       WHERE d.status = 'Open'
                       AND (d.last_reminder IS NULL OR 
                            datetime(d.last_reminder) <= datetime('now', '-1 day'))
                       ORDER BY d.created_at ASC"""
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения долгов для напоминания: {e}")
            return []
    
    async def update_reminder_sent(self, debt_id: int) -> bool:
        """
        Обновить время последнего напоминания
        
        Args:
            debt_id: ID долга
            
        Returns:
            True если обновление успешно
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE debts SET last_reminder = ? WHERE id = ?",
                    (datetime.now().isoformat(), debt_id)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления времени напоминания: {e}")
            return False
    

    
    async def get_activation_links(self) -> List[Dict[str, Any]]:
        """
        Получить все ссылки активации
        
        Returns:
            Список ссылок активации
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM activation_links ORDER BY created_at DESC"
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения ссылок активации: {e}")
            return []
    
    async def set_user_active(self, user_id: int, is_active: int) -> bool:
        """
        Установить статус активности пользователя
        
        Args:
            user_id: ID пользователя
            is_active: 1 - активен, 0 - неактивен
            
        Returns:
            True если обновление успешно
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET is_active = ? WHERE user_id = ?",
                    (is_active, user_id)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса пользователя: {e}")
            return False
    
    async def delete_user_cascade(self, user_id: int) -> bool:
        """
        Удалить пользователя и все связанные данные
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если удаление успешно
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Удаляем все долги пользователя
                await db.execute(
                    "DELETE FROM debts WHERE debtor_id = ? OR creditor_id = ?",
                    (user_id, user_id)
                )
                
                # Удаляем все платежи пользователя
                await db.execute(
                    "DELETE FROM payments WHERE debtor_id = ? OR creditor_id = ?",
                    (user_id, user_id)
                )
                
                # Удаляем все операции пользователя
                await db.execute(
                    "DELETE FROM processed_operations WHERE user_id = ?",
                    (user_id,)
                )
                
                # Удаляем пользователя
                await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка удаления пользователя: {e}")
            return False

    # === МЕТОДЫ ДЛЯ РАБОТЫ С QR-КОДАМИ ===
    
    async def set_user_qr_code(self, user_id: int, file_id: str, description: str = None) -> bool:
        """
        Установить QR-код банка для пользователя
        
        Args:
            user_id: ID пользователя
            file_id: ID файла QR-кода в Telegram
            description: Описание QR-кода (например, "Optima Bank")
            
        Returns:
            True если QR-код установлен успешно
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET qr_code_file_id = ?, qr_code_description = ? WHERE user_id = ?",
                    (file_id, description, user_id)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка установки QR-кода: {e}")
            return False
    
    async def get_user_qr_code(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить QR-код пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Данные QR-кода или None
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT qr_code_file_id, qr_code_description FROM users WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row and row['qr_code_file_id']:
                        return {
                            'file_id': row['qr_code_file_id'],
                            'description': row['qr_code_description']
                        }
                    return None
        except Exception as e:
            logger.error(f"Ошибка получения QR-кода: {e}")
            return None
    
    async def remove_user_qr_code(self, user_id: int) -> bool:
        """
        Удалить QR-код пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если QR-код удален успешно
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET qr_code_file_id = NULL, qr_code_description = NULL WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка удаления QR-кода: {e}")
            return False
    
    async def get_users_with_qr_codes(self) -> List[Dict[str, Any]]:
        """
        Получить всех пользователей с QR-кодами
        
        Returns:
            Список пользователей с QR-кодами
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """SELECT user_id, first_name, username, qr_code_file_id, qr_code_description 
                       FROM users 
                       WHERE qr_code_file_id IS NOT NULL 
                       ORDER BY first_name, username"""
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения пользователей с QR-кодами: {e}")
            return []

    async def get_all_qr_codes(self) -> List[Dict[str, Any]]:
        """
        Получить все QR-коды для админ-панели
        
        Returns:
            Список всех QR-кодов с информацией о пользователях
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """SELECT u.user_id, u.first_name, u.username, 
                              u.qr_code_file_id, u.qr_code_description, u.created_at
                       FROM users u 
                       WHERE u.qr_code_file_id IS NOT NULL 
                       ORDER BY u.first_name, u.username"""
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения всех QR-кодов: {e}")
            return [] 