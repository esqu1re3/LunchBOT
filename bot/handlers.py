"""
Модуль с обработчиками сообщений и callback-запросов для бота
"""
import re
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, Document, PhotoSize, InlineKeyboardMarkup, InlineKeyboardButton

from .db import DatabaseManager
from .messages import *

logger = logging.getLogger(__name__)

class BotHandlers:
    """Класс для обработки сообщений и callback-запросов"""
    
    def __init__(self, bot: TeleBot, db: DatabaseManager):
        """
        Инициализация обработчиков
        
        Args:
            bot: Экземпляр бота
            db: Менеджер базы данных
        """
        self.bot = bot
        self.db = db
        self.user_states: Dict[int, Dict[str, Any]] = {}
        
        # Регистрируем обработчики
        self.register_handlers()
    
    def register_handlers(self):
        """Регистрация всех обработчиков"""
        # Команды
        self.bot.message_handler(commands=['start'])(self.handle_start)
        self.bot.message_handler(commands=['help'])(self.handle_help)
        self.bot.message_handler(commands=['new_debt'])(self.handle_new_debt_command)
        self.bot.message_handler(commands=['my_debts'])(self.handle_my_debts_command)

        
        # Callback-запросы
        self.bot.callback_query_handler(func=lambda call: True)(self.handle_callback_query)
        
        # Обработка файлов
        self.bot.message_handler(content_types=['photo', 'document'])(self.handle_file)
        
        # Обработка текстовых сообщений
        self.bot.message_handler(content_types=['text'])(self.handle_text)
    
    def check_user_activation(self, user_id: int) -> bool:
        """
        Проверить активацию пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если пользователь активирован
        """
        user = self.db.get_user(user_id)
        return user is not None and user['is_active']
    
    def get_user_state(self, user_id: int) -> Dict[str, Any]:
        """
        Получить состояние пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь состояния пользователя
        """
        return self.user_states.get(user_id, {})
    
    def set_user_state(self, user_id: int, state: str, data: Dict[str, Any] = None):
        """
        Установить состояние пользователя
        
        Args:
            user_id: ID пользователя
            state: Состояние
            data: Дополнительные данные
        """
        if user_id not in self.user_states:
            self.user_states[user_id] = {}
        
        self.user_states[user_id]['state'] = state
        if data:
            self.user_states[user_id]['data'] = data
    
    def clear_user_state(self, user_id: int):
        """
        Очистить состояние пользователя
        
        Args:
            user_id: ID пользователя
        """
        # Удаляем все сообщения перед очисткой состояния
        self.clear_messages_from_state(user_id)
        
        if user_id in self.user_states:
            del self.user_states[user_id]
    
    def delete_messages(self, user_id: int, message_ids: List[int]):
        """
        Удалить сообщения
        
        Args:
            user_id: ID пользователя
            message_ids: Список ID сообщений для удаления
        """
        for message_id in message_ids:
            try:
                self.bot.delete_message(user_id, message_id)
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение {message_id}: {e}")
    
    def add_message_to_state(self, user_id: int, message_id: int):
        """
        Добавить ID сообщения в состояние пользователя для последующего удаления
        
        Args:
            user_id: ID пользователя
            message_id: ID сообщения
        """
        if user_id not in self.user_states:
            self.user_states[user_id] = {}
        
        if 'messages_to_delete' not in self.user_states[user_id]:
            self.user_states[user_id]['messages_to_delete'] = []
        
        self.user_states[user_id]['messages_to_delete'].append(message_id)
    
    def clear_messages_from_state(self, user_id: int):
        """
        Удалить все сообщения из состояния пользователя
        
        Args:
            user_id: ID пользователя
        """
        if user_id in self.user_states and 'messages_to_delete' in self.user_states[user_id]:
            message_ids = self.user_states[user_id]['messages_to_delete']
            self.delete_messages(user_id, message_ids)
            del self.user_states[user_id]['messages_to_delete']
    
    # === Обработчики команд ===
    
    def handle_start(self, message: Message):
        """
        Обработка команды /start
        
        Args:
            message: Сообщение от пользователя
        """
        user_id = message.from_user.id
        
        # Проверяем активацию
        if not self.check_user_activation(user_id):
            # Автоматически активируем пользователя
            self.db.create_user(
                user_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            
            user_name = message.from_user.first_name or message.from_user.username or f"User {user_id}"
            self.bot.send_message(
                user_id,
                ACTIVATION_SUCCESS.format(name=user_name),
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # Показываем главное меню
        self.show_main_menu(user_id)
    
    def handle_help(self, message: Message):
        """
        Обработка команды /help
        
        Args:
            message: Сообщение от пользователя
        """
        user_id = message.from_user.id
        
        if not self.check_user_activation(user_id):
            self.bot.send_message(user_id, ERROR_NOT_ACTIVATED)
            return
        
        self.bot.send_message(
            user_id, 
            HELP_MESSAGE,
            reply_markup=get_back_to_main_keyboard()
        )
    
    def handle_new_debt_command(self, message: Message):
        """
        Обработка команды /new_debt
        
        Args:
            message: Сообщение от пользователя
        """
        user_id = message.from_user.id
        
        if not self.check_user_activation(user_id):
            self.bot.send_message(user_id, ERROR_NOT_ACTIVATED)
            return
        
        self.start_new_debt_process(user_id)
    
    def handle_my_debts_command(self, message: Message):
        """
        Обработка команды /my_debts
        
        Args:
            message: Сообщение от пользователя
        """
        user_id = message.from_user.id
        
        if not self.check_user_activation(user_id):
            self.bot.send_message(user_id, ERROR_NOT_ACTIVATED)
            return
        
        self.show_my_debts(user_id)
    

    
    # === Обработчики callback-запросов ===
    
    def handle_callback_query(self, call: CallbackQuery):
        """
        Обработка callback-запросов
        
        Args:
            call: Callback-запрос
        """
        user_id = call.from_user.id
        data = call.data
        
        try:
            # Основные действия
            if data == "back_to_main":
                self.clear_user_state(user_id)
                self.clear_messages_from_state(user_id)
                self.show_main_menu(user_id)
                
            elif data == "new_debt":
                self.start_new_debt_process(user_id)
                
            elif data == "my_debts":
                self.show_my_debts(user_id)
                
            elif data == "help":
                self.bot.edit_message_text(
                    HELP_MESSAGE,
                    chat_id=user_id,
                    message_id=call.message.message_id,
                    reply_markup=get_back_to_main_keyboard()
                )
                
            elif data == "cancel":
                self.clear_user_state(user_id)
                self.clear_messages_from_state(user_id)
                self.show_main_menu(user_id)
                
            elif data == "skip_description":
                self.handle_debt_description_skip(user_id, call.message.message_id)
                
            # Выбор пользователя
            elif data.startswith("select_user_"):
                selected_user_id = int(data.split("_")[2])
                self.handle_user_selection(user_id, selected_user_id, call.message.message_id)
                
            # Действия с долгом
            elif data.startswith("pay_debt_"):
                debt_id = int(data.split("_")[2])
                self.handle_pay_debt(user_id, debt_id)
                
            elif data.startswith("remind_later_"):
                debt_id = int(data.split("_")[2])
                self.handle_remind_later(user_id, debt_id)
                
            # Оплата всех долгов
            elif data == "pay_all_debts":
                self.handle_pay_all_debts(user_id)
                
            # Подтверждение платежа
            elif data.startswith("confirm_payment_"):
                payment_id = int(data.split("_")[2])
                self.handle_confirm_payment(user_id, payment_id, call.message)
                
            elif data.startswith("dispute_payment_"):
                payment_id = int(data.split("_")[2])
                self.handle_dispute_payment(user_id, payment_id, call.message)
                
            # Подтверждение множественных платежей
            elif data.startswith("confirm_multiple_payments_"):
                payment_ids_str = data.split("_", 3)[3]
                payment_ids = [int(pid) for pid in payment_ids_str.split(",")]
                self.handle_confirm_multiple_payments(user_id, payment_ids, call.message)
                
            elif data.startswith("dispute_multiple_payments_"):
                payment_ids_str = data.split("_", 3)[3]
                payment_ids = [int(pid) for pid in payment_ids_str.split(",")]
                self.handle_dispute_multiple_payments(user_id, payment_ids, call.message)
                
            # Отвечаем на callback
            self.bot.answer_callback_query(call.id)
            
        except Exception as e:
            logger.error(f"Ошибка обработки callback: {e}")
            self.bot.answer_callback_query(call.id, "Произошла ошибка!")
    
    # === Обработка файлов ===
    
    def handle_file(self, message: Message):
        """
        Обработка файлов (фото и документы)
        
        Args:
            message: Сообщение с файлом
        """
        user_id = message.from_user.id
        user_state = self.get_user_state(user_id)
        
        if user_state.get('state') not in ['waiting_payment_receipt', 'waiting_payment_receipt_all']:
            return
        
        # Удаляем сообщение пользователя с файлом
        try:
            self.bot.delete_message(user_id, message.message_id)
        except Exception:
            pass
        
        try:
            # Получаем ID файла и тип
            file_id = None
            file_type = None
            
            if message.photo:
                file_id = message.photo[-1].file_id  # Берем наибольшее разрешение
                file_type = 'photo'
            elif message.document:
                file_id = message.document.file_id
                file_type = 'document'
            
            if not file_id:
                self.bot.send_message(user_id, "Неподдерживаемый тип файла!")
                return
            
            # Обработка оплаты одного долга
            if user_state.get('state') == 'waiting_payment_receipt':
                debt_id = user_state['data']['debt_id']
                debt = self.db.get_debt(debt_id)
                
                if not debt:
                    self.bot.send_message(user_id, ERROR_DEBT_NOT_FOUND)
                    self.clear_user_state(user_id)
                    return
                
                # Создаем платеж
                payment_id = self.db.create_payment(
                    debt_id=debt_id,
                    debtor_id=user_id,
                    creditor_id=debt['creditor_id'],
                    file_id=file_id
                )
                
                if payment_id:
                    # Отправляем уведомление кредитору
                    self.send_payment_confirmation_request(
                        creditor_id=debt['creditor_id'],
                        payment_id=payment_id,
                        debt=debt,
                        file_id=file_id,
                        file_type=file_type
                    )
                    
                    # Удаляем сообщения с запросом чека
                    self.clear_messages_from_state(user_id)
                    
                    self.bot.send_message(
                        user_id,
                        "✅ Чек отправлен! Ожидайте подтверждения от кредитора."
                    )
                    
                    self.clear_user_state(user_id)
                else:
                    self.bot.send_message(user_id, ERROR_GENERAL)
            
            # Обработка оплаты всех долгов
            elif user_state.get('state') == 'waiting_payment_receipt_all':
                debt_ids = user_state['data']['debt_ids']
                total_amount = user_state['data']['total_amount']
                
                # Создаем платежи для каждого долга
                payment_ids = []
                creditor_groups = {}  # Группируем долги по кредиторам
                
                for debt_id in debt_ids:
                    debt = self.db.get_debt(debt_id)
                    if not debt:
                        continue
                    
                    # Создаем платеж
                    payment_id = self.db.create_payment(
                        debt_id=debt_id,
                        debtor_id=user_id,
                        creditor_id=debt['creditor_id'],
                        file_id=file_id
                    )
                    
                    if payment_id:
                        payment_ids.append(payment_id)
                        
                        # Группируем долги по кредиторам
                        creditor_id = debt['creditor_id']
                        if creditor_id not in creditor_groups:
                            creditor_groups[creditor_id] = []
                        creditor_groups[creditor_id].append({
                            'debt': debt,
                            'payment_id': payment_id
                        })
                
                # Отправляем уведомления кредиторам
                if payment_ids:
                    for creditor_id, creditor_debts in creditor_groups.items():
                        self.send_multiple_payment_confirmation_request(
                            creditor_id=creditor_id,
                            creditor_debts=creditor_debts,
                            file_id=file_id,
                            file_type=file_type,
                            total_amount=total_amount
                        )
                    
                    # Удаляем сообщения с запросом чека
                    self.clear_messages_from_state(user_id)
                    
                    self.bot.send_message(
                        user_id,
                        f"✅ Чек на сумму {total_amount:.2f} сом отправлен всем кредиторам! Ожидайте подтверждения."
                    )
                    
                    self.clear_user_state(user_id)
                else:
                    self.bot.send_message(user_id, ERROR_GENERAL)
                
        except Exception as e:
            logger.error(f"Ошибка обработки файла: {e}")
            self.bot.send_message(user_id, ERROR_GENERAL)
    
    # === Обработка текстовых сообщений ===
    
    def handle_text(self, message: Message):
        """
        Обработка текстовых сообщений
        
        Args:
            message: Текстовое сообщение
        """
        user_id = message.from_user.id
        user_state = self.get_user_state(user_id)
        
        if not user_state.get('state'):
            return
        
        state = user_state['state']
        
        if state == 'waiting_debt_amount':
            # Удаляем сообщение пользователя
            try:
                self.bot.delete_message(user_id, message.message_id)
            except Exception:
                pass
            
            self.handle_debt_amount_input(user_id, message.text)
            
        elif state == 'waiting_debt_description':
            # Удаляем сообщение пользователя
            try:
                self.bot.delete_message(user_id, message.message_id)
            except Exception:
                pass
            
            self.handle_debt_description_input(user_id, message.text)
    
    # === Методы для работы с долгами ===
    
    def show_main_menu(self, user_id: int):
        """
        Показать главное меню
        
        Args:
            user_id: ID пользователя
        """
        self.bot.send_message(
            user_id,
            MAIN_MENU,
            reply_markup=get_main_menu_keyboard()
        )
    
    def start_new_debt_process(self, user_id: int):
        """
        Начать процесс создания нового долга
        
        Args:
            user_id: ID пользователя
        """
        # Получаем всех пользователей кроме текущего
        users = self.db.get_all_users()
        
        if len(users) <= 1:
            self.bot.send_message(
                user_id,
                "❌ Нет других пользователей для создания долга!"
            )
            return
        
        # Очищаем предыдущие сообщения
        self.clear_messages_from_state(user_id)
        
        message = self.bot.send_message(
            user_id,
            NEW_DEBT_START,
            reply_markup=get_users_keyboard(users, exclude_user_id=user_id)
        )
        
        # Сохраняем message_id для последующего удаления
        self.add_message_to_state(user_id, message.message_id)
    
    def handle_user_selection(self, user_id: int, selected_user_id: int, message_id: int):
        """
        Обработка выбора пользователя
        
        Args:
            user_id: ID пользователя
            selected_user_id: ID выбранного пользователя
            message_id: ID сообщения для редактирования
        """
        selected_user = self.db.get_user(selected_user_id)
        
        if not selected_user:
            self.bot.send_message(user_id, ERROR_USER_NOT_FOUND)
            return
        
        # Сохраняем выбранного пользователя в состоянии
        self.set_user_state(user_id, 'waiting_debt_amount', {
            'selected_user_id': selected_user_id,
            'selected_user_name': get_user_display_name(selected_user)
        })
        
        # Редактируем сообщение с выбором пользователя
        try:
            self.bot.edit_message_text(
                NEW_DEBT_AMOUNT.format(debtor_name=get_user_display_name(selected_user)),
                chat_id=user_id,
                message_id=message_id,
                reply_markup=get_cancel_keyboard()
            )
        except Exception:
            # Если не удалось отредактировать, отправляем новое сообщение
            message = self.bot.send_message(
                user_id,
                NEW_DEBT_AMOUNT.format(debtor_name=get_user_display_name(selected_user)),
                reply_markup=get_cancel_keyboard()
            )
            self.add_message_to_state(user_id, message.message_id)
    
    def handle_debt_amount_input(self, user_id: int, amount_text: str):
        """
        Обработка ввода суммы долга
        
        Args:
            user_id: ID пользователя
            amount_text: Текст с суммой
        """
        try:
            amount = float(amount_text.replace(',', '.'))
            if amount <= 0:
                raise ValueError("Отрицательная сумма")
                
        except ValueError:
            self.bot.send_message(user_id, ERROR_INVALID_AMOUNT)
            return
        
        user_state = self.get_user_state(user_id)
        user_state['data']['amount'] = amount
        
        # Просим ввести описание
        self.set_user_state(user_id, 'waiting_debt_description', user_state['data'])
        
        message = self.bot.send_message(
            user_id,
            NEW_DEBT_DESCRIPTION,
            reply_markup=get_debt_description_keyboard()
        )
        
        # Сохраняем message_id для последующего удаления
        self.add_message_to_state(user_id, message.message_id)
    
    def handle_debt_description_input(self, user_id: int, description: str):
        """
        Обработка ввода описания долга
        
        Args:
            user_id: ID пользователя
            description: Описание долга
        """
        user_state = self.get_user_state(user_id)
        
        # Удаляем все промежуточные сообщения
        self.clear_messages_from_state(user_id)
        
        self.create_debt_final(user_id, description)
    
    def handle_debt_description_skip(self, user_id: int, message_id: int):
        """
        Обработка пропуска описания долга
        
        Args:
            user_id: ID пользователя
            message_id: ID сообщения
        """
        # Удаляем все промежуточные сообщения
        self.clear_messages_from_state(user_id)
        
        self.create_debt_final(user_id, None)
    
    def create_debt_final(self, user_id: int, description: Optional[str]):
        """
        Финальное создание долга
        
        Args:
            user_id: ID пользователя
            description: Описание долга (может быть None)
        """
        user_state = self.get_user_state(user_id)
        data = user_state['data']
        
        # Создаем долг
        debt_id = self.db.create_debt(
            debtor_id=data['selected_user_id'],
            creditor_id=user_id,
            amount=data['amount'],
            description=description
        )
        
        if debt_id:
            # Отправляем уведомление должнику
            self.send_debt_notification(
                debtor_id=data['selected_user_id'],
                debt_id=debt_id,
                creditor_name=self.db.get_user(user_id)['first_name'] or 'Неизвестно',
                amount=data['amount'],
                description=description or 'без описания'
            )
            
            # Подтверждаем создание
            self.bot.send_message(
                user_id,
                DEBT_CREATED.format(
                    debtor_name=data['selected_user_name'],
                    amount=data['amount'],
                    description=description or 'без описания',
                    date=format_datetime(datetime.now().isoformat())
                ),
                reply_markup=get_back_to_main_keyboard()
            )
        else:
            self.bot.send_message(user_id, ERROR_GENERAL)
        
        self.clear_user_state(user_id)
    
    def show_my_debts(self, user_id: int):
        """
        Показать долги пользователя
        
        Args:
            user_id: ID пользователя
        """
        debts = self.db.get_user_debts(user_id)
        
        if not debts:
            self.bot.send_message(
                user_id,
                MY_DEBTS_EMPTY,
                reply_markup=get_back_to_main_keyboard()
            )
            return
        
        # Рассчитываем итоговую сумму
        total_amount = sum(debt['amount'] for debt in debts)
        
        # Форматируем список долгов с датами
        debts_list = format_debt_list(debts)
        
        # Объединяем сообщения в одно
        combined_message = f"""
{MY_DEBTS_LIST.format(
    count=len(debts),
    debts_list=debts_list,
    total_amount=total_amount
)}

{DEBT_PAYMENT_SELECTION}
"""
        
        # Отправляем объединенное сообщение с клавиатурой выбора долгов
        self.bot.send_message(
            user_id,
            combined_message,
            reply_markup=get_debt_payment_keyboard(debts)
        )
    
    # === Методы для работы с платежами ===
    
    def handle_pay_debt(self, user_id: int, debt_id: int):
        """
        Обработка оплаты долга
        
        Args:
            user_id: ID пользователя
            debt_id: ID долга
        """
        debt = self.db.get_debt(debt_id)
        
        if not debt or debt['debtor_id'] != user_id:
            self.bot.send_message(user_id, ERROR_DEBT_NOT_FOUND)
            return
        
        # Устанавливаем состояние ожидания чека
        self.set_user_state(user_id, 'waiting_payment_receipt', {
            'debt_id': debt_id
        })
        
        message = self.bot.send_message(
            user_id,
            PAYMENT_RECEIPT_REQUEST.format(amount=debt['amount']),
            reply_markup=get_cancel_keyboard()
        )
        
        # Сохраняем message_id для последующего удаления
        self.add_message_to_state(user_id, message.message_id)
    
    def handle_remind_later(self, user_id: int, debt_id: int):
        """
        Обработка напоминания позже
        
        Args:
            user_id: ID пользователя
            debt_id: ID долга
        """
        # Просто отправляем подтверждение
        self.bot.send_message(
            user_id,
            "⏰ Хорошо, напомним позже!"
        )
    
    def handle_pay_all_debts(self, user_id: int):
        """
        Обработка оплаты всех долгов
        
        Args:
            user_id: ID пользователя
        """
        debts = self.db.get_user_debts(user_id)
        
        if not debts:
            self.bot.send_message(user_id, "У вас нет активных долгов!")
            return
        
        # Рассчитываем общую сумму
        total_amount = sum(debt['amount'] for debt in debts)
        
        # Формируем список долгов для отображения
        debt_summary = []
        for debt in debts:
            creditor_name = debt['creditor_name'] or debt['creditor_username'] or f"User {debt['creditor_id']}"
            description = debt['description'] or "без описания"
            debt_summary.append(f"• {creditor_name}: {debt['amount']:.2f} сом ({description})")
        
        # Устанавливаем состояние ожидания чека для всех долгов
        debt_ids = [debt['id'] for debt in debts]
        self.set_user_state(user_id, 'waiting_payment_receipt_all', {
            'debt_ids': debt_ids,
            'total_amount': total_amount
        })
        
        # Отправляем запрос на чек
        message = f"""
📁 Отправьте чек об оплате всех долгов

Общая сумма: {total_amount:.2f} сом

Долги:
{chr(10).join(debt_summary)}

Пожалуйста, отправьте фотографию или PDF файл чека об оплате.
"""
        
        sent_message = self.bot.send_message(
            user_id,
            message,
            reply_markup=get_cancel_keyboard()
        )
        
        # Сохраняем message_id для последующего удаления
        self.add_message_to_state(user_id, sent_message.message_id)
    
    def handle_confirm_payment(self, user_id: int, payment_id: int, message):
        """
        Обработка подтверждения платежа
        
        Args:
            user_id: ID пользователя
            payment_id: ID платежа
            message: Сообщение с кнопками
        """
        payment = self.db.get_payment(payment_id)
        
        if not payment or payment['creditor_id'] != user_id:
            self.bot.send_message(user_id, "❌ Платеж не найден!")
            return
        
        # Подтверждаем платеж
        if self.db.confirm_payment(payment_id):
            # Закрываем долг
            self.db.close_debt(payment['debt_id'])
            
            # Уведомляем должника
            debt = self.db.get_debt(payment['debt_id'])
            self.bot.send_message(
                payment['debtor_id'],
                PAYMENT_CONFIRMED.format(amount=debt['amount'])
            )
            
            # Редактируем сообщение, убираем кнопки
            try:
                self.bot.edit_message_text(
                    f"✅ Оплата подтверждена!\n\nДолг на сумму {debt['amount']} сом закрыт.",
                    chat_id=user_id,
                    message_id=message.message_id
                )
            except:
                self.bot.send_message(
                    user_id,
                    PAYMENT_CONFIRMED.format(amount=debt['amount'])
                )
        else:
            self.bot.send_message(user_id, ERROR_GENERAL)
    
    def handle_dispute_payment(self, user_id: int, payment_id: int, message):
        """
        Обработка оспаривания платежа
        
        Args:
            user_id: ID пользователя
            payment_id: ID платежа
            message: Сообщение с кнопками
        """
        payment = self.db.get_payment(payment_id)
        
        if not payment or payment['creditor_id'] != user_id:
            self.bot.send_message(user_id, "❌ Платеж не найден!")
            return
        
        # Оспариваем платеж
        if self.db.dispute_payment(payment_id):
            # Оспариваем долг
            self.db.dispute_debt(payment['debt_id'])
            
            debt = self.db.get_debt(payment['debt_id'])
            
            # Уведомляем должника
            self.bot.send_message(
                payment['debtor_id'],
                PAYMENT_DISPUTED.format(amount=debt['amount'])
            )
            
            # Редактируем сообщение, убираем кнопки
            try:
                self.bot.edit_message_text(
                    f"⚠️ Оплата оспорена!\n\nДолг на сумму {debt['amount']} сом оспорен.\nАдминистратор получил уведомление.",
                    chat_id=user_id,
                    message_id=message.message_id
                )
            except:
                self.bot.send_message(
                    user_id,
                    PAYMENT_DISPUTED.format(amount=debt['amount'])
                )
            
            # Уведомляем админа
            admin_chat_id = self.db.get_setting('admin_chat_id')
            if admin_chat_id:
                self.bot.send_message(
                    admin_chat_id,
                    DEBT_DISPUTED_ADMIN.format(
                        creditor_name=debt['creditor_name'],
                        debtor_name=debt['debtor_name'],
                        amount=debt['amount'],
                        description=debt['description'] or 'без описания'
                    )
                )
        else:
            self.bot.send_message(user_id, ERROR_GENERAL)
    
    def handle_confirm_multiple_payments(self, user_id: int, payment_ids: List[int], message):
        """
        Обработка подтверждения множественных платежей
        
        Args:
            user_id: ID пользователя
            payment_ids: Список ID платежей
            message: Сообщение с кнопками
        """
        confirmed_payments = []
        total_amount = 0
        debtor_name = ""
        
        for payment_id in payment_ids:
            payment = self.db.get_payment(payment_id)
            
            if not payment or payment['creditor_id'] != user_id:
                continue
            
            # Подтверждаем платеж
            if self.db.confirm_payment(payment_id):
                # Закрываем долг
                self.db.close_debt(payment['debt_id'])
                
                debt = self.db.get_debt(payment['debt_id'])
                confirmed_payments.append(debt)
                total_amount += debt['amount']
                
                if not debtor_name:
                    debtor_name = debt['debtor_name']
        
        if confirmed_payments:
            # Уведомляем должника
            debt_details = []
            for debt in confirmed_payments:
                description = debt['description'] or 'без описания'
                debt_details.append(f"• {debt['amount']:.2f} сом ({description})")
            
            message_text = f"""
✅ Все платежи подтверждены!

Подтвержденные долги:
{chr(10).join(debt_details)}

Общая сумма: {total_amount:.2f} сом

Спасибо за использование бота!
"""
            
            self.bot.send_message(
                confirmed_payments[0]['debtor_id'],
                message_text
            )
            
            # Редактируем сообщение кредитора
            try:
                self.bot.edit_message_text(
                    f"✅ Все платежи подтверждены!\n\nОбщая сумма: {total_amount:.2f} сом",
                    chat_id=user_id,
                    message_id=message.message_id
                )
            except:
                self.bot.send_message(
                    user_id,
                    f"✅ Все платежи подтверждены! Общая сумма: {total_amount:.2f} сом"
                )
        else:
            self.bot.send_message(user_id, ERROR_GENERAL)
    
    def handle_dispute_multiple_payments(self, user_id: int, payment_ids: List[int], message):
        """
        Обработка оспаривания множественных платежей
        
        Args:
            user_id: ID пользователя
            payment_ids: Список ID платежей
            message: Сообщение с кнопками
        """
        disputed_payments = []
        total_amount = 0
        debtor_name = ""
        
        for payment_id in payment_ids:
            payment = self.db.get_payment(payment_id)
            
            if not payment or payment['creditor_id'] != user_id:
                continue
            
            # Оспариваем платеж
            if self.db.dispute_payment(payment_id):
                # Оспариваем долг
                self.db.dispute_debt(payment['debt_id'])
                
                debt = self.db.get_debt(payment['debt_id'])
                disputed_payments.append(debt)
                total_amount += debt['amount']
                
                if not debtor_name:
                    debtor_name = debt['debtor_name']
        
        if disputed_payments:
            # Уведомляем должника
            debt_details = []
            for debt in disputed_payments:
                description = debt['description'] or 'без описания'
                debt_details.append(f"• {debt['amount']:.2f} сом ({description})")
            
            message_text = f"""
⚠️ Все платежи оспорены!

Оспоренные долги:
{chr(10).join(debt_details)}

Общая сумма: {total_amount:.2f} сом

Администратор получил уведомление.
"""
            
            self.bot.send_message(
                disputed_payments[0]['debtor_id'],
                message_text
            )
            
            # Редактируем сообщение кредитора
            try:
                self.bot.edit_message_text(
                    f"⚠️ Все платежи оспорены!\n\nОбщая сумма: {total_amount:.2f} сом\nАдминистратор получил уведомление.",
                    chat_id=user_id,
                    message_id=message.message_id
                )
            except:
                self.bot.send_message(
                    user_id,
                    f"⚠️ Все платежи оспорены! Общая сумма: {total_amount:.2f} сом"
                )
            
            # Уведомляем админа
            admin_chat_id = self.db.get_setting('admin_chat_id')
            if admin_chat_id:
                for debt in disputed_payments:
                    self.bot.send_message(
                        admin_chat_id,
                        DEBT_DISPUTED_ADMIN.format(
                            creditor_name=debt['creditor_name'],
                            debtor_name=debt['debtor_name'],
                            amount=debt['amount'],
                            description=debt['description'] or 'без описания'
                        )
                    )
        else:
            self.bot.send_message(user_id, ERROR_GENERAL)
    
    # === Методы для уведомлений ===
    
    def send_debt_notification(self, debtor_id: int, debt_id: int, creditor_name: str, 
                             amount: float, description: str):
        """
        Отправить уведомление о новом долге
        
        Args:
            debtor_id: ID должника
            debt_id: ID долга
            creditor_name: Имя кредитора
            amount: Сумма долга
            description: Описание долга
        """
        message = f"""
💰 Новый долг

{creditor_name} добавил вам долг на сумму {amount} сом.
Описание: {description}

Не забудьте вовремя рассчитаться!
"""
        
        self.bot.send_message(
            debtor_id,
            message,
            reply_markup=get_debt_actions_keyboard(debt_id)
        )
    
    def send_payment_confirmation_request(self, creditor_id: int, payment_id: int, 
                                        debt: Dict[str, Any], file_id: str, file_type: str = 'photo'):
        """
        Отправить запрос на подтверждение платежа
        
        Args:
            creditor_id: ID кредитора
            payment_id: ID платежа
            debt: Информация о долге
            file_id: ID файла чека
            file_type: Тип файла (photo или document)
        """
        # Отправляем файл кредитору
        try:
            if file_type == 'photo':
                self.bot.send_photo(
                    creditor_id,
                    file_id,
                    caption=f"💳 Чек от {debt['debtor_name']} на сумму {debt['amount']} сом"
                )
            else:
                self.bot.send_document(
                    creditor_id,
                    file_id,
                    caption=f"💳 Чек от {debt['debtor_name']} на сумму {debt['amount']} сом"
                )
        except Exception as e:
            logger.error(f"Ошибка отправки файла: {e}")
            self.bot.send_message(
                creditor_id,
                f"💳 Чек от {debt['debtor_name']} (не удалось отправить файл)"
            )
        
        # Отправляем запрос на подтверждение
        self.bot.send_message(
            creditor_id,
            PAYMENT_CONFIRMATION_REQUEST.format(
                debtor_name=debt['debtor_name'],
                amount=debt['amount'],
                description=debt['description'] or 'без описания'
            ),
            reply_markup=get_payment_confirmation_keyboard(payment_id)
        )
    
    def send_multiple_payment_confirmation_request(self, creditor_id: int, creditor_debts: List[Dict[str, Any]], 
                                                 file_id: str, file_type: str = 'photo', total_amount: float = 0):
        """
        Отправить запрос на подтверждение множественных платежей
        
        Args:
            creditor_id: ID кредитора
            creditor_debts: Список долгов кредитора с информацией о платежах
            file_id: ID файла чека
            file_type: Тип файла (photo или document)
            total_amount: Общая сумма всех долгов
        """
        # Отправляем файл кредитору
        try:
            debtor_name = creditor_debts[0]['debt']['debtor_name']
            creditor_total = sum(item['debt']['amount'] for item in creditor_debts)
            
            if file_type == 'photo':
                self.bot.send_photo(
                    creditor_id,
                    file_id,
                    caption=f"💳 Чек от {debtor_name} на общую сумму {total_amount:.2f} сом\n"
                           f"Ваши долги на сумму: {creditor_total:.2f} сом"
                )
            else:
                self.bot.send_document(
                    creditor_id,
                    file_id,
                    caption=f"💳 Чек от {debtor_name} на общую сумму {total_amount:.2f} сом\n"
                           f"Ваши долги на сумму: {creditor_total:.2f} сом"
                )
        except Exception as e:
            logger.error(f"Ошибка отправки файла: {e}")
            self.bot.send_message(
                creditor_id,
                f"💳 Чек от {debtor_name} (не удалось отправить файл)"
            )
        
        # Формируем сообщение с деталями долгов
        debt_details = []
        for item in creditor_debts:
            debt = item['debt']
            description = debt['description'] or 'без описания'
            debt_details.append(f"• {debt['amount']:.2f} сом ({description})")
        
        message = f"""
💳 Подтверждение оплаты долгов

{creditor_debts[0]['debt']['debtor_name']} отправил чек об оплате следующих долгов:

{chr(10).join(debt_details)}

Общая сумма ваших долгов: {creditor_total:.2f} сом

Подтвердите оплату всех долгов или оспорьте её.
"""
        
        # Создаем клавиатуру для подтверждения всех платежей
        keyboard = InlineKeyboardMarkup(row_width=2)
        
        # Кнопка для подтверждения всех платежей
        payment_ids = [str(item['payment_id']) for item in creditor_debts]
        keyboard.add(
            InlineKeyboardButton(
                "✅ Подтвердить все",
                callback_data=f"confirm_multiple_payments_{','.join(payment_ids)}"
            ),
            InlineKeyboardButton(
                "❌ Оспорить все",
                callback_data=f"dispute_multiple_payments_{','.join(payment_ids)}"
            )
        )
        
        # Кнопки для отдельных платежей
        for item in creditor_debts:
            debt = item['debt']
            payment_id = item['payment_id']
            description = debt['description'] or 'без описания'
            
            keyboard.add(
                InlineKeyboardButton(
                    f"✅ {debt['amount']:.2f} сом ({description})",
                    callback_data=f"confirm_payment_{payment_id}"
                )
            )
        
        self.bot.send_message(
            creditor_id,
            message,
            reply_markup=keyboard
        )
    
    def send_debt_reminder(self, debt: Dict[str, Any]):
        """
        Отправить напоминание о долге
        
        Args:
            debt: Информация о долге
        """
        message = DEBT_REMINDER.format(
            creditor_name=debt['creditor_name'],
            amount=debt['amount'],
            description=debt['description'] or 'без описания',
            created_at=format_datetime(debt['created_at'])
        )
        
        self.bot.send_message(
            debt['debtor_id'],
            message,
            reply_markup=get_debt_actions_keyboard(debt['id'])
        )
        
        # Обновляем время последнего напоминания
        self.db.update_reminder_sent(debt['id'])
    
 