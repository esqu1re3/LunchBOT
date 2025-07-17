"""
Модуль для работы с базой данных SQLite
"""
import sqlite3
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import secrets
import logging
import hashlib

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Менеджер для работы с базой данных"""
    
    def __init__(self, db_path: str = "lunchbot.db"):
        """
        Инициализация менеджера базы данных
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных из schema.sql"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Читаем схему из файла
                schema_path = os.path.join(os.path.dirname(__file__), '..', 'schema.sql')
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema = f.read()
                
                # Выполняем SQL команды по одной
                cursor = conn.cursor()
                for statement in schema.split(';'):
                    if statement.strip():
                        cursor.execute(statement)
                        
                conn.commit()
                logger.info("База данных инициализирована успешно")
            # После создания таблиц вызываем миграцию
            self.migrate_database()
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise
    
    def migrate_database(self):
        """Автоматическая миграция структуры БД (добавление новых столбцов)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Проверяем наличие cancel_reason в payments
                cursor.execute("PRAGMA table_info(payments);")
                columns = [row[1] for row in cursor.fetchall()]
                if 'cancel_reason' not in columns:
                    cursor.execute("ALTER TABLE payments ADD COLUMN cancel_reason TEXT;")
                    conn.commit()
                    logger.info("Миграция: добавлен столбец cancel_reason в payments")
        except Exception as e:
            logger.error(f"Ошибка миграции БД: {e}")
    
    def get_connection(self) -> sqlite3.Connection:
        """Получить соединение с базой данных"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Для удобного доступа к колонкам
        return conn
    
    # === Работа с пользователями ===
    
    def create_user(self, user_id: int, username: str = None, 
                   first_name: str = None, last_name: str = None) -> bool:
        """
        Создать нового пользователя
        
        Args:
            user_id: Telegram user ID
            username: Telegram username
            first_name: Имя пользователя
            last_name: Фамилия пользователя
            
        Returns:
            True если пользователь создан успешно
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO users 
                    (user_id, username, first_name, last_name, activated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, username, first_name, last_name, datetime.now()))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка создания пользователя: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о пользователе
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Словарь с информацией о пользователе или None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """
        Получить всех пользователей (активных и неактивных)
        Returns:
            Список словарей с информацией о пользователях
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users ORDER BY is_active DESC, first_name ASC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения пользователей: {e}")
            return []
    
    def update_user_name(self, user_id: int, first_name: str, last_name: str = None) -> bool:
        """
        Обновить имя пользователя
        
        Args:
            user_id: Telegram user ID
            first_name: Новое имя
            last_name: Новая фамилия
            
        Returns:
            True если обновление успешно
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users 
                    SET first_name = ?, last_name = ?
                    WHERE user_id = ?
                """, (first_name, last_name, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка обновления имени пользователя: {e}")
            return False
    
    # === Работа с ссылками активации ===
    
    def create_activation_link(self, name: str) -> Optional[str]:
        """
        Создать ссылку активации для участника
        
        Args:
            name: Имя участника
            
        Returns:
            Токен активации или None
        """
        try:
            token = secrets.token_urlsafe(32)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO activation_links (token, name)
                    VALUES (?, ?)
                """, (token, name))
                conn.commit()
                return token
        except Exception as e:
            logger.error(f"Ошибка создания ссылки активации: {e}")
            return None
    
    def activate_user(self, token: str, user_id: int) -> bool:
        """
        Активировать пользователя по токену
        
        Args:
            token: Токен активации
            user_id: Telegram user ID
            
        Returns:
            True если активация успешна
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Проверяем существование и неиспользованность токена
                cursor.execute("""
                    SELECT name FROM activation_links 
                    WHERE token = ? AND is_used = 0
                """, (token,))
                row = cursor.fetchone()
                
                if not row:
                    return False
                
                # Отмечаем токен как использованный
                cursor.execute("""
                    UPDATE activation_links 
                    SET is_used = 1, user_id = ?, used_at = ?
                    WHERE token = ?
                """, (user_id, datetime.now(), token))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка активации пользователя: {e}")
            return False
    
    def get_activation_links(self) -> List[Dict[str, Any]]:
        """
        Получить все ссылки активации
        
        Returns:
            Список словарей с информацией о ссылках
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM activation_links ORDER BY created_at DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения ссылок активации: {e}")
            return []
    
    def delete_activation_link(self, token: str) -> bool:
        """
        Удалить ссылку активации
        
        Args:
            token: Токен активации
            
        Returns:
            True если удаление успешно
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM activation_links WHERE token = ?", (token,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка удаления ссылки активации: {e}")
            return False
    
    # === Работа с долгами ===
    
    def create_debt(self, debtor_id: int, creditor_id: int, amount: float, 
                   description: str = None) -> Optional[int]:
        """
        Создать долг
        
        Args:
            debtor_id: ID должника
            creditor_id: ID кредитора
            amount: Сумма долга
            description: Описание долга
            
        Returns:
            ID созданного долга или None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO debts (debtor_id, creditor_id, amount, description)
                    VALUES (?, ?, ?, ?)
                """, (debtor_id, creditor_id, amount, description))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка создания долга: {e}")
            return None
    
    def get_debt(self, debt_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о долге
        
        Args:
            debt_id: ID долга
            
        Returns:
            Словарь с информацией о долге или None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.*, 
                           u1.first_name as debtor_name, u1.username as debtor_username,
                           u2.first_name as creditor_name, u2.username as creditor_username
                    FROM debts d
                    JOIN users u1 ON d.debtor_id = u1.user_id
                    JOIN users u2 ON d.creditor_id = u2.user_id
                    WHERE d.id = ?
                """, (debt_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка получения долга: {e}")
            return None
    
    def get_open_debts(self) -> List[Dict[str, Any]]:
        """
        Получить все открытые долги
        
        Returns:
            Список словарей с информацией о долгах
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.*, 
                           u1.first_name as debtor_name, u1.username as debtor_username,
                           u2.first_name as creditor_name, u2.username as creditor_username
                    FROM debts d
                    JOIN users u1 ON d.debtor_id = u1.user_id
                    JOIN users u2 ON d.creditor_id = u2.user_id
                    WHERE d.status = 'Open'
                    ORDER BY d.created_at DESC
                """)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения долгов: {e}")
            return []
    
    def get_user_debts(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получить долги пользователя (где он должник)
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список словарей с информацией о долгах
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.*, 
                           u1.first_name as debtor_name, u1.username as debtor_username,
                           u2.first_name as creditor_name, u2.username as creditor_username
                    FROM debts d
                    JOIN users u1 ON d.debtor_id = u1.user_id
                    JOIN users u2 ON d.creditor_id = u2.user_id
                    WHERE d.debtor_id = ? AND d.status = 'Open'
                    ORDER BY d.created_at DESC
                """, (user_id,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения долгов пользователя: {e}")
            return []
    
    def close_debt(self, debt_id: int) -> bool:
        """
        Закрыть долг
        
        Args:
            debt_id: ID долга
            
        Returns:
            True если долг закрыт успешно
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE debts 
                    SET status = 'Closed', closed_at = ?
                    WHERE id = ?
                """, (datetime.now(), debt_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка закрытия долга: {e}")
            return False
    
    def dispute_debt(self, debt_id: int) -> bool:
        """
        Оспорить долг
        
        Args:
            debt_id: ID долга
            
        Returns:
            True если долг оспорен успешно
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE debts 
                    SET status = 'Disputed'
                    WHERE id = ?
                """, (debt_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка оспаривания долга: {e}")
            return False
    
    # === Работа с платежами ===
    
    def create_payment(self, debt_id: int, debtor_id: int, creditor_id: int, 
                      file_id: str = None) -> Optional[int]:
        """
        Создать платеж
        
        Args:
            debt_id: ID долга
            debtor_id: ID должника
            creditor_id: ID кредитора
            file_id: ID файла чека
            
        Returns:
            ID созданного платежа или None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO payments (debt_id, debtor_id, creditor_id, file_id)
                    VALUES (?, ?, ?, ?)
                """, (debt_id, debtor_id, creditor_id, file_id))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка создания платежа: {e}")
            return None
    
    def confirm_payment(self, payment_id: int) -> bool:
        """
        Подтвердить платеж
        
        Args:
            payment_id: ID платежа
            
        Returns:
            True если платеж подтвержден успешно
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE payments 
                    SET status = 'Confirmed', confirmed_at = ?
                    WHERE id = ?
                """, (datetime.now(), payment_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка подтверждения платежа: {e}")
            return False
    
    def cancel_payment(self, payment_id: int, reason: str) -> bool:
        """
        Отменить подтверждение платежа с указанием причины
        Args:
            payment_id: ID платежа
            reason: Причина отмены
        Returns:
            True если отмена прошла успешно
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE payments 
                    SET status = 'Cancelled', cancel_reason = ?
                    WHERE id = ?
                """, (reason, payment_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка отмены платежа: {e}")
            return False
    
    def get_payment(self, payment_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о платеже
        
        Args:
            payment_id: ID платежа
            
        Returns:
            Словарь с информацией о платеже или None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка получения платежа: {e}")
            return None
    
    # === Работа с настройками ===
    
    def get_setting(self, key: str) -> Optional[str]:
        """
        Получить значение настройки
        
        Args:
            key: Ключ настройки
            
        Returns:
            Значение настройки или None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error(f"Ошибка получения настройки: {e}")
            return None
    
    def set_setting(self, key: str, value: str) -> bool:
        """
        Установить значение настройки
        
        Args:
            key: Ключ настройки
            value: Значение настройки
            
        Returns:
            True если настройка установлена успешно
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                """, (key, value, datetime.now()))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка установки настройки: {e}")
            return False
    
    def set_admin_password(self, password: str) -> bool:
        """
        Сохраняет хэш пароля администратора в settings (ключ 'admin_password_hash')
        Args:
            password: Пароль в открытом виде
        Returns:
            True если успешно
        """
        password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        return self.set_setting('admin_password_hash', password_hash)

    def check_admin_password(self, password: str) -> bool:
        """
        Проверяет пароль администратора по хэшу
        Args:
            password: Введённый пароль
        Returns:
            True если пароль верный
        """
        password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        stored_hash = self.get_setting('admin_password_hash')
        return stored_hash == password_hash
    
    # === Напоминания ===
    
    def get_debts_for_reminder(self) -> List[Dict[str, Any]]:
        """
        Получить долги для напоминания
        
        Returns:
            Список словарей с информацией о долгах
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Получаем долги, которые нужно напомнить
                cursor.execute("""
                    SELECT d.*, 
                           u1.first_name as debtor_name, u1.username as debtor_username,
                           u2.first_name as creditor_name, u2.username as creditor_username
                    FROM debts d
                    JOIN users u1 ON d.debtor_id = u1.user_id
                    JOIN users u2 ON d.creditor_id = u2.user_id
                    WHERE d.status = 'Open' 
                    AND (d.last_reminder IS NULL 
                         OR datetime(d.last_reminder, '+' || d.reminder_frequency || ' days') <= datetime('now'))
                    ORDER BY d.created_at DESC
                """)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения долгов для напоминания: {e}")
            return []
    
    def update_reminder_sent(self, debt_id: int) -> bool:
        """
        Обновить время последнего напоминания
        
        Args:
            debt_id: ID долга
            
        Returns:
            True если обновление успешно
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE debts 
                    SET last_reminder = ?
                    WHERE id = ?
                """, (datetime.now(), debt_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка обновления напоминания: {e}")
            return False 

    def delete_user_cascade(self, user_id: int) -> bool:
        """
        Каскадное удаление пользователя и всех связанных данных (долги, платежи, ссылки активации)
        Args:
            user_id: Telegram user ID
        Returns:
            True если удаление прошло успешно
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Удаляем платежи, где пользователь был должником или кредитором
                cursor.execute("DELETE FROM payments WHERE debtor_id = ? OR creditor_id = ?", (user_id, user_id))
                # Удаляем долги, где пользователь был должником или кредитором
                cursor.execute("DELETE FROM debts WHERE debtor_id = ? OR creditor_id = ?", (user_id, user_id))
                # Удаляем ссылки активации
                cursor.execute("DELETE FROM activation_links WHERE user_id = ?", (user_id,))
                # Удаляем самого пользователя
                cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка каскадного удаления пользователя: {e}")
            return False 

    def set_user_active(self, user_id: int, is_active: int) -> bool:
        """
        Активировать или деактивировать пользователя
        Args:
            user_id: Telegram user ID
            is_active: 1 - активен, 0 - неактивен
        Returns:
            True если обновление прошло успешно
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (is_active, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка смены статуса активности пользователя: {e}")
            return False 