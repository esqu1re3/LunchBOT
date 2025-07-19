import logging
import asyncio
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from .async_db import AsyncDatabaseManager
from .async_keyboards import (
    get_main_menu_keyboard, get_users_keyboard, get_debt_actions_keyboard,
    get_payment_confirmation_keyboard, get_cancel_keyboard,
    get_back_to_main_keyboard, get_debts_payment_keyboard, get_receipt_upload_keyboard
)
from .async_messages import (
    format_debt_list, format_datetime, debt_created_message,
    payment_confirmed_message, debt_reminder_message, new_debt_message, error_message
)

router = Router()
logger = logging.getLogger(__name__)
db = AsyncDatabaseManager()

def is_valid_file_format(file_name: str) -> bool:
    """
    Проверяет, является ли формат файла допустимым
    
    Args:
        file_name: Имя файла
        
    Returns:
        True если формат допустим
    """
    if not file_name:
        return False
    
    # Приводим к нижнему регистру и убираем пробелы
    file_name = file_name.lower().strip()
    
    # Допустимые форматы
    valid_extensions = ['.jpg', '.jpeg', '.png', '.pdf']
    
    return any(file_name.endswith(ext) for ext in valid_extensions)

async def cleanup_messages(bot, chat_id: int, message_ids: list):
    """Удаление сообщений с обработкой ошибок"""
    if not message_ids:
        return
    
    logger.info(f"Начинаем очистку {len(message_ids)} сообщений в чате {chat_id}")
    
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id, msg_id)
            logger.debug(f"Сообщение {msg_id} удалено из чата {chat_id}")
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение {msg_id} из чата {chat_id}: {e}")
            # Попытка редактирования сообщения
            try:
                await bot.edit_message_text(
                    "🗑️ Сообщение очищено",
                    chat_id=chat_id,
                    message_id=msg_id
                )
                logger.debug(f"Сообщение {msg_id} отредактировано в чате {chat_id}")
            except Exception as edit_error:
                logger.debug(f"Не удалось отредактировать сообщение {msg_id}: {edit_error}")
    
    logger.info(f"Очистка сообщений в чате {chat_id} завершена")

async def safe_edit_message(message, text: str, reply_markup=None):
    """
    Безопасное редактирование сообщения с учетом типа (текст или медиа)
    
    Args:
        message: Сообщение для редактирования
        text: Новый текст
        reply_markup: Новая клавиатура
    """
    try:
        # Проверяем, есть ли caption (документ/фото) или text (обычное сообщение)
        if message.caption:
            await message.edit_caption(text, reply_markup=reply_markup)
        else:
            await message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение: {e}")
        # Попытка отправить новое сообщение
        try:
            await message.answer(text, reply_markup=reply_markup)
        except Exception as send_error:
            logger.error(f"Не удалось отправить новое сообщение: {send_error}")

def is_duplicate_action(user_id: int, action: str) -> bool:
    """
    Проверяет, не является ли действие дублирующим
    
    Args:
        user_id: ID пользователя
        action: Тип действия
        
    Returns:
        True если действие дублирующее
    """
    import time
    current_time = time.time()
    key = f"{user_id}:{action}"
    
    if key in user_action_cache:
        last_time = user_action_cache[key]
        # Если прошло менее 1 секунды, считаем дублированием
        if current_time - last_time < 1:
            return True
    
    user_action_cache[key] = current_time
    return False

# === СОСТОЯНИЯ FSM ===

class CreateDebtStates(StatesGroup):
    selecting_debtor = State()
    entering_amount = State()
    entering_description = State()
    uploading_receipt = State()

class PayDebtStates(StatesGroup):
    uploading_receipt = State()

class CancelPaymentStates(StatesGroup):
    entering_cancel_reason = State()

# Простой кэш для предотвращения дублирования действий
user_action_cache = {}

# === ОСНОВНЫЕ КОМАНДЫ ===

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработка команды /start"""
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.create_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        welcome_text = "✅ Вы зарегистрированы в системе LunchBOT!\n\nВыберите действие:"
    else:
        welcome_text = "Добро пожаловать в LunchBOT!\n\nВыберите действие:"
    
    keyboard = await get_main_menu_keyboard()
    await message.answer(welcome_text, reply_markup=keyboard)

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработка команды /help"""
    help_text = """
🍽️ LunchBOT - система учёта долгов за обед

📋 Доступные команды:
/start - Регистрация в системе
/help - Показать это сообщение
/new_debt - Создать новый долг
/my_debts - Показать ваши долги
/who_owes_me - Кто должен вам

💡 Для создания долга используйте /new_debt
💡 Для оплаты долга нажмите кнопку "💳 Оплачено" в уведомлении
"""
    keyboard = await get_main_menu_keyboard()
    await message.answer(help_text, reply_markup=keyboard)

@router.message(Command("new_debt"))
async def cmd_new_debt(message: Message, state: FSMContext):
    """Начало процесса создания долга"""
    users = await db.get_all_users()
    users = [u for u in users if u['user_id'] != message.from_user.id and u['is_active']]
    
    if not users:
        await message.answer("❌ Нет других активных пользователей для создания долга!")
        return
    
    # Инициализируем состояние с ID сообщений
    await state.clear()
    await state.update_data(message_ids=[message.message_id])
    
    keyboard = await get_users_keyboard(users, exclude_user_id=message.from_user.id)
    select_msg = await message.answer("👤 Выберите должника:", reply_markup=keyboard)
    
    # Сохраняем ID сообщения
    data = await state.get_data()
    data['message_ids'].append(select_msg.message_id)
    await state.update_data(message_ids=data['message_ids'])
    
    await state.set_state(CreateDebtStates.selecting_debtor)

@router.message(Command("my_debts"))
async def cmd_my_debts(message: Message):
    """Показать долги пользователя"""
    debts = await db.get_user_debts(message.from_user.id)
    
    if not debts:
        keyboard = await get_main_menu_keyboard()
        await message.answer("✅ У вас нет активных долгов!", reply_markup=keyboard)
        return
    
    total = sum(d['amount'] for d in debts)
    debt_list = format_debt_list(debts)
    
    response = f"📋 Ваши долги ({len(debts)}):\n\n{debt_list}\n\n💰 Итого: {total:.2f} сом\n\n💳 Выберите долг для оплаты или оплатите все сразу:"
    keyboard = await get_debts_payment_keyboard(debts)
    await message.answer(response, reply_markup=keyboard)

@router.message(Command("who_owes_me"))
async def cmd_who_owes_me(message: Message):
    """Показать, кто должен пользователю"""
    debts = await db.get_open_debts()
    my_debts = [d for d in debts if d['creditor_id'] == message.from_user.id]
    
    if not my_debts:
        keyboard = await get_main_menu_keyboard()
        await message.answer("✅ Вам никто не должен!", reply_markup=keyboard)
        return
    
    total = sum(d['amount'] for d in my_debts)
    debt_list = format_debt_list(my_debts)
    
    response = f"📋 Кто вам должен ({len(my_debts)}):\n\n{debt_list}\n\n💰 Итого к получению: {total:.2f} сом"
    keyboard = await get_main_menu_keyboard()
    await message.answer(response, reply_markup=keyboard)

# === CALLBACK ОБРАБОТЧИКИ ===

@router.callback_query(F.data == "cancel")
async def handle_cancel(call: CallbackQuery, state: FSMContext):
    """Отмена операции"""
    current_state = await state.get_state()
    
    # Если мы в процессе ввода причины отмены, игнорируем отмену
    if current_state == CancelPaymentStates.entering_cancel_reason.__str__():
        await call.answer("Пожалуйста, введите причину отмены или отправьте любое сообщение для продолжения")
        return
    
    # Обычная отмена
    # Получаем ID сообщений для удаления
    data = await state.get_data()
    message_ids = data.get('message_ids', [])
    
    # Добавляем ID текущего сообщения для удаления
    message_ids.append(call.message.message_id)
    
    # Удаляем все сообщения процесса
    if message_ids:
        await cleanup_messages(call.bot, call.message.chat.id, message_ids)
    
    await state.clear()
    keyboard = await get_main_menu_keyboard()
    
    # Отправляем новое сообщение вместо редактирования
    await call.message.answer("❌ Операция отменена\n\nВыберите действие:", reply_markup=keyboard)
    await call.answer()

@router.callback_query(F.data == "skip_receipt")
async def handle_skip_receipt(call: CallbackQuery, state: FSMContext):
    """Пропуск загрузки чека и создание долга без чека"""
    await call.answer()
    
    # Получаем данные состояния
    data = await state.get_data()
    message_ids = data.get('message_ids', [])
    
    # Добавляем ID текущего сообщения
    message_ids.append(call.message.message_id)
    
    # Создаем фиктивное сообщение для передачи в create_debt_final
    class FakeMessage:
        def __init__(self, bot, from_user, chat):
            self.bot = bot
            self.from_user = from_user
            self.chat = chat
        
        async def answer(self, text, reply_markup=None):
            """Отправка сообщения в чат"""
            return await self.bot.send_message(self.chat.id, text, reply_markup=reply_markup)
    
    fake_message = FakeMessage(call.bot, call.from_user, call.message.chat)
    
    # Обновляем состояние и создаем долг
    await state.update_data(message_ids=message_ids)
    await create_debt_final(fake_message, state)

@router.callback_query(F.data == "back_to_main")
async def handle_back_to_main(call: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    keyboard = await get_main_menu_keyboard()
    
    await safe_edit_message(call.message, "🏠 Главное меню\n\nВыберите действие:", reply_markup=keyboard)
    await call.answer()

# === ОБРАБОТЧИКИ INLINE КНОПОК КОМАНД ===

@router.callback_query(F.data == "cmd_new_debt")
async def handle_cmd_new_debt(call: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Создать долг'"""
    # Проверяем дублирование
    if is_duplicate_action(call.from_user.id, "cmd_new_debt"):
        await call.answer("⏳ Подождите...")
        return
    
    await call.answer()
    
    # Вызываем логику создания долга
    users = await db.get_all_users()
    users = [u for u in users if u['user_id'] != call.from_user.id and u['is_active']]
    
    if not users:
        await safe_edit_message(call.message, "❌ Нет других активных пользователей для создания долга!")
        return
    
    # Инициализируем состояние с ID сообщений
    await state.clear()
    await state.update_data(message_ids=[call.message.message_id])
    
    keyboard = await get_users_keyboard(users, exclude_user_id=call.from_user.id)
    await safe_edit_message(call.message, "👤 Выберите должника:", reply_markup=keyboard)
    await state.set_state(CreateDebtStates.selecting_debtor)

@router.callback_query(F.data == "cmd_my_debts")
async def handle_cmd_my_debts(call: CallbackQuery):
    """Обработка кнопки 'Мои долги'"""
    # Проверяем дублирование
    if is_duplicate_action(call.from_user.id, "cmd_my_debts"):
        await call.answer("⏳ Подождите...")
        return
    
    await call.answer()
    
    debts = await db.get_user_debts(call.from_user.id)
    
    if not debts:
        keyboard = await get_main_menu_keyboard()
        await safe_edit_message(call.message, "✅ У вас нет активных долгов!", reply_markup=keyboard)
        return
    
    total = sum(d['amount'] for d in debts)
    debt_list = format_debt_list(debts)
    
    response = f"📋 Ваши долги ({len(debts)}):\n\n{debt_list}\n\n💰 Итого: {total:.2f} сом\n\n💳 Выберите долг для оплаты или оплатите все сразу:"
    keyboard = await get_debts_payment_keyboard(debts)
    
    await safe_edit_message(call.message, response, reply_markup=keyboard)

@router.callback_query(F.data == "cmd_who_owes_me")
async def handle_cmd_who_owes_me(call: CallbackQuery):
    """Обработка кнопки 'Кто мне должен'"""
    # Проверяем дублирование
    if is_duplicate_action(call.from_user.id, "cmd_who_owes_me"):
        await call.answer("⏳ Подождите...")
        return
    
    await call.answer()
    
    debts = await db.get_open_debts()
    my_debts = [d for d in debts if d['creditor_id'] == call.from_user.id]
    
    if not my_debts:
        keyboard = await get_main_menu_keyboard()
        await safe_edit_message(call.message, "✅ Вам никто не должен!", reply_markup=keyboard)
        return
    
    total = sum(d['amount'] for d in my_debts)
    debt_list = format_debt_list(my_debts)
    
    response = f"📋 Кто вам должен ({len(my_debts)}):\n\n{debt_list}\n\n💰 Итого к получению: {total:.2f} сом"
    keyboard = await get_main_menu_keyboard()
    
    await safe_edit_message(call.message, response, reply_markup=keyboard)

@router.callback_query(F.data == "cmd_help")
async def handle_cmd_help(call: CallbackQuery):
    """Обработка кнопки 'Помощь'"""
    # Проверяем дублирование
    if is_duplicate_action(call.from_user.id, "cmd_help"):
        await call.answer("⏳ Подождите...")
        return
    
    await call.answer()
    
    help_text = """
🍽️ LunchBOT - система учёта долгов за обед

📋 Доступные команды:
/start - Регистрация в системе
/help - Показать это сообщение
/new_debt - Создать новый долг
/my_debts - Показать ваши долги
/who_owes_me - Кто должен вам

💡 Для создания долга используйте /new_debt
💡 Для оплаты долга нажмите кнопку "💳 Оплачено" в уведомлении
"""
    keyboard = await get_main_menu_keyboard()
    
    await safe_edit_message(call.message, help_text, reply_markup=keyboard)

# === СОЗДАНИЕ ДОЛГА ===

@router.callback_query(F.data.startswith("select_user_"))
async def handle_user_selection(call: CallbackQuery, state: FSMContext):
    """Выбор должника"""
    user_id = int(call.data.split("_")[2])
    user = await db.get_user(user_id)
    
    if not user:
        await call.answer("❌ Пользователь не найден")
        return
    
    await state.update_data(debtor_id=user_id, debtor_name=user['first_name'] or user['username'])
    await safe_edit_message(call.message, f"💰 Введите сумму долга для {user['first_name'] or user['username']}:")
    await state.set_state(CreateDebtStates.entering_amount)
    await call.answer()

@router.message(StateFilter(CreateDebtStates.entering_amount))
async def handle_amount_input(message: Message, state: FSMContext):
    """Ввод суммы долга"""
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return
        
        # Сохраняем ID сообщения пользователя
        data = await state.get_data()
        data['message_ids'].append(message.message_id)
        data['amount'] = amount
        await state.update_data(**data)
        
        keyboard = await get_cancel_keyboard()
        desc_msg = await message.answer("📝 Введите описание долга (или отправьте '-' для пропуска):", reply_markup=keyboard)
        
        # Сохраняем ID сообщения бота
        data = await state.get_data()
        data['message_ids'].append(desc_msg.message_id)
        await state.update_data(message_ids=data['message_ids'])
        
        await state.set_state(CreateDebtStates.entering_description)
        
    except ValueError:
        await message.answer("❌ Введите корректную сумму (например: 100.50)")

@router.message(StateFilter(CreateDebtStates.entering_description))
async def handle_description_input(message: Message, state: FSMContext):
    """Ввод описания долга"""
    description = message.text if message.text != '-' else None
    
    # Сохраняем ID сообщения пользователя
    data = await state.get_data()
    data['message_ids'].append(message.message_id)
    data['description'] = description
    await state.update_data(**data)
    
    keyboard = await get_receipt_upload_keyboard()
    receipt_msg = await message.answer(
        "📸 Отправьте фото или документ чека:\n\n"
        "✅ Допустимые форматы: JPG, JPEG, PNG, PDF\n\n"
        "Если у вас нет чека, нажмите 'Пропустить'",
        reply_markup=keyboard
    )
    
    # Сохраняем ID сообщения бота
    data = await state.get_data()
    data['message_ids'].append(receipt_msg.message_id)
    await state.update_data(message_ids=data['message_ids'])
    
    await state.set_state(CreateDebtStates.uploading_receipt)

@router.message(StateFilter(CreateDebtStates.uploading_receipt), F.photo)
async def handle_receipt_upload(message: Message, state: FSMContext):
    """Загрузка чека (фото)"""
    file_id = message.photo[-1].file_id
    
    # Сохраняем ID сообщения пользователя
    data = await state.get_data()
    data['message_ids'].append(message.message_id)
    data['file_id'] = file_id
    await state.update_data(**data)
    
    await create_debt_final(message, state)

@router.message(StateFilter(CreateDebtStates.uploading_receipt), F.document)
async def handle_receipt_document(message: Message, state: FSMContext):
    """Загрузка чека (документ)"""
    document = message.document
    
    # Проверяем формат файла
    if not is_valid_file_format(document.file_name):
        data = await state.get_data()
        message_ids = data.get('message_ids', [])
        
        # Добавляем ID сообщения с документом для удаления
        message_ids.append(message.message_id)
        
        # Отправляем сообщение об ошибке и сохраняем его ID
        error_msg = await message.answer(
            "❌ Неверный формат файла!\n\n"
            "Допустимые форматы: JPG, JPEG, PNG, PDF\n"
            "Пожалуйста, отправьте файл в одном из этих форматов."
        )
        
        # Добавляем ID сообщения с ошибкой для удаления
        message_ids.append(error_msg.message_id)
        await state.update_data(message_ids=message_ids)
        return
    
    file_id = document.file_id
    
    # Сохраняем ID сообщения пользователя
    data = await state.get_data()
    data['message_ids'].append(message.message_id)
    data['file_id'] = file_id
    await state.update_data(**data)
    
    await create_debt_final(message, state)

@router.message(StateFilter(CreateDebtStates.uploading_receipt))
async def handle_no_receipt(message: Message, state: FSMContext):
    """Обработка неподходящих сообщений при загрузке чека"""
    data = await state.get_data()
    message_ids = data.get('message_ids', [])
    
    # Добавляем ID сообщения пользователя для удаления
    message_ids.append(message.message_id)
    
    # Отправляем просьбу отправить чек и сохраняем его ID
    prompt_msg = await message.answer(
        "❌ Пожалуйста, отправьте фото или документ чека!\n\n"
        "✅ Допустимые форматы: JPG, JPEG, PNG, PDF\n\n"
        "Если у вас нет чека, нажмите кнопку 'Пропустить' ниже."
    )
    
    # Добавляем ID сообщения с просьбой для удаления
    message_ids.append(prompt_msg.message_id)
    await state.update_data(message_ids=message_ids)

async def create_debt_final(message: Message, state: FSMContext):
    """Финальное создание долга"""
    data = await state.get_data()
    
    debtor_id = data['debtor_id']
    amount = data['amount']
    description = data.get('description')
    file_id = data.get('file_id')
    message_ids = data.get('message_ids', [])
    
    # Создаем долг
    debt_id = await db.create_debt(
        debtor_id=debtor_id,
        creditor_id=message.from_user.id,
        amount=amount,
        description=description
    )
    
    if not debt_id:
        await message.answer("❌ Ошибка создания долга")
        await state.clear()
        return
    
    # Если есть чек, создаем платеж
    if file_id:
        payment_id = await db.create_payment(
            debt_id=debt_id,
            debtor_id=debtor_id,
            creditor_id=message.from_user.id,
            file_id=file_id
        )
    
    # Отправляем уведомление должнику
    debtor = await db.get_user(debtor_id)
    creditor_name = message.from_user.first_name or message.from_user.username
    
    new_debt_text = new_debt_message(
        creditor_name=creditor_name,
        amount=amount,
        description=description or "без описания",
        created_at=format_datetime(datetime.now().isoformat())
    )
    
    keyboard = await get_debt_actions_keyboard(debt_id)
    
    try:
        # Если есть чек, отправляем его вместе с уведомлением
        if file_id:
            # Определяем тип файла и отправляем соответствующим методом
            if message.photo:
                # Это фото
                await message.bot.send_photo(
                    chat_id=debtor_id,
                    photo=file_id,
                    caption=new_debt_text,
                    reply_markup=keyboard
                )
            elif message.document:
                # Это документ
                await message.bot.send_document(
                    chat_id=debtor_id,
                    document=file_id,
                    caption=new_debt_text,
                    reply_markup=keyboard
                )
        else:
            # Без чека - отправляем только текст
            await message.bot.send_message(debtor_id, new_debt_text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление должнику {debtor_id}: {e}")
    
    # Удаляем все сообщения процесса создания долга
    if message_ids:
        await cleanup_messages(message.bot, message.chat.id, message_ids)
    
    # Подтверждение кредитору
    success_text = debt_created_message(
        debtor_name=debtor['first_name'] or debtor['username'],
        amount=amount,
        description=description or "без описания",
        date=format_datetime(datetime.now().isoformat())
    )
    
    keyboard = await get_main_menu_keyboard()
    await message.answer(success_text, reply_markup=keyboard)
    await state.clear()

# === ОПЛАТА ДОЛГОВ ===

@router.callback_query(F.data.startswith("pay_debt_"))
async def handle_pay_debt(call: CallbackQuery, state: FSMContext):
    """Начало процесса оплаты долга"""
    debt_id = int(call.data.split("_")[2])
    debt = await db.get_debt(debt_id)
    
    if not debt or debt['debtor_id'] != call.from_user.id:
        await call.answer("❌ Долг не найден")
        return
    
    # Инициализируем состояние с ID сообщений
    await state.clear()
    await state.update_data(debt_id=debt_id, message_ids=[call.message.message_id])
    
    keyboard = await get_cancel_keyboard()
    await safe_edit_message(
        call.message,
        "📸 Отправьте фото или документ чека об оплате:\n\n"
        "✅ Допустимые форматы: JPG, JPEG, PNG, PDF",
        keyboard
    )
    await state.set_state(PayDebtStates.uploading_receipt)
    await call.answer()

@router.callback_query(F.data == "pay_all_debts")
async def handle_pay_all_debts(call: CallbackQuery, state: FSMContext):
    """Обработка оплаты всех долгов сразу"""
    await call.answer()
    
    debts = await db.get_user_debts(call.from_user.id)
    
    if not debts:
        keyboard = await get_main_menu_keyboard()
        await safe_edit_message(call.message, "✅ У вас нет активных долгов!", keyboard)
        return
    
    total_amount = sum(d['amount'] for d in debts)
    
    # Инициализируем состояние
    await state.clear()
    await state.update_data(
        debt_ids=[d['id'] for d in debts],
        creditor_ids=list(set(d['creditor_id'] for d in debts)),
        total_amount=total_amount,
        message_ids=[call.message.message_id]
    )
    
    keyboard = await get_cancel_keyboard()
    
    # Формируем список кредиторов
    creditors_info = []
    for debt in debts:
        creditor_name = debt['creditor_name'] or debt['creditor_username'] or f"User {debt['creditor_id']}"
        creditors_info.append(f"• {creditor_name}: {debt['amount']:.2f} сом")
    
    creditors_text = "\n".join(creditors_info)
    
    await safe_edit_message(
        call.message,
        f"💳 Отправьте фото или документ чека для оплаты всех долгов\n\n"
        f"✅ Допустимые форматы: JPG, JPEG, PNG, PDF\n\n"
        f"💰 Общая сумма: {total_amount:.2f} сом\n\n"
        f"📋 Список кредиторов:\n{creditors_text}",
        keyboard
    )
    await state.set_state(PayDebtStates.uploading_receipt)

@router.message(StateFilter(PayDebtStates.uploading_receipt), F.photo)
async def handle_payment_receipt_photo(message: Message, state: FSMContext):
    """Обработка чека об оплате (фото)"""
    data = await state.get_data()
    message_ids = data.get('message_ids', [])
    file_id = message.photo[-1].file_id
    
    # Добавляем ID сообщения с фото для удаления
    message_ids.append(message.message_id)
    await state.update_data(message_ids=message_ids)
    
    await process_payment_receipt(message, state, file_id)

@router.message(StateFilter(PayDebtStates.uploading_receipt), F.document)
async def handle_payment_receipt_document(message: Message, state: FSMContext):
    """Обработка чека об оплате (документ)"""
    document = message.document
    
    # Проверяем формат файла
    if not is_valid_file_format(document.file_name):
        data = await state.get_data()
        message_ids = data.get('message_ids', [])
        
        # Добавляем ID сообщения с документом для удаления
        message_ids.append(message.message_id)
        
        # Отправляем сообщение об ошибке и сохраняем его ID
        error_msg = await message.answer(
            "❌ Неверный формат файла!\n\n"
            "Допустимые форматы: JPG, JPEG, PNG, PDF\n"
            "Пожалуйста, отправьте файл в одном из этих форматов."
        )
        
        # Добавляем ID сообщения с ошибкой для удаления
        message_ids.append(error_msg.message_id)
        await state.update_data(message_ids=message_ids)
        return
    
    data = await state.get_data()
    message_ids = data.get('message_ids', [])
    file_id = document.file_id
    
    # Добавляем ID сообщения с документом для удаления
    message_ids.append(message.message_id)
    await state.update_data(message_ids=message_ids)
    
    await process_payment_receipt(message, state, file_id)

async def process_payment_receipt(message: Message, state: FSMContext, file_id: str):
    """Обработка чека об оплате (общая логика)"""
    data = await state.get_data()
    message_ids = data.get('message_ids', [])
    
    # Проверяем, это оплата одного долга или всех долгов
    if 'debt_id' in data:
        # Оплата одного долга
        debt_id = data['debt_id']
        debt = await db.get_debt(debt_id)
        
        if not debt:
            await message.answer("❌ Долг не найден")
            await state.clear()
            return
        
        # Создаем платеж
        payment_id = await db.create_payment(
            debt_id=debt_id,
            debtor_id=message.from_user.id,
            creditor_id=debt['creditor_id'],
            file_id=file_id
        )
        
        if not payment_id:
            await message.answer("❌ Ошибка создания платежа")
            await state.clear()
            return
        
        # Отправляем запрос на подтверждение кредитору
        debtor_name = message.from_user.first_name or message.from_user.username
        
        confirmation_text = f"""
💳 Запрос на подтверждение оплаты

Должник: {debtor_name}
Сумма: {debt['amount']:.2f} сом
Описание: {debt['description'] or 'без описания'}

Пожалуйста, подтвердите получение оплаты.
"""
        
        keyboard = await get_payment_confirmation_keyboard(payment_id)
        
        try:
            # Определяем тип файла и отправляем соответствующим методом
            if message.photo:
                # Это фото
                await message.bot.send_photo(
                    chat_id=debt['creditor_id'],
                    photo=file_id,
                    caption=confirmation_text,
                    reply_markup=keyboard
                )
            elif message.document:
                # Это документ
                await message.bot.send_document(
                    chat_id=debt['creditor_id'],
                    document=file_id,
                    caption=confirmation_text,
                    reply_markup=keyboard
                )
        except Exception as e:
            logger.error(f"Не удалось отправить запрос подтверждения кредитору {debt['creditor_id']}: {e}")
        
        # Удаляем все сообщения процесса оплаты
        if message_ids:
            await cleanup_messages(message.bot, message.chat.id, message_ids)
        
        # Отправляем уведомление и сразу удаляем его
        notification_msg = await message.answer("✅ Чек отправлен кредитору на подтверждение")
        # Удаляем уведомление через 3 секунды
        await asyncio.sleep(3)
        try:
            await message.bot.delete_message(message.chat.id, notification_msg.message_id)
            logger.info(f"Уведомление об отправке чека удалено")
        except Exception as delete_error:
            logger.debug(f"Не удалось удалить уведомление об отправке чека: {delete_error}")
        
        await state.clear()
        
    elif 'debt_ids' in data:
        # Оплата всех долгов
        debt_ids = data['debt_ids']
        creditor_ids = data['creditor_ids']
        total_amount = data['total_amount']
        
        # Создаем платежи для каждого долга
        created_payments = []
        debtor_name = message.from_user.first_name or message.from_user.username
        
        for debt_id in debt_ids:
            debt = await db.get_debt(debt_id)
            if debt:
                payment_id = await db.create_payment(
                    debt_id=debt_id,
                    debtor_id=message.from_user.id,
                    creditor_id=debt['creditor_id'],
                    file_id=file_id
                )
                if payment_id:
                    created_payments.append((payment_id, debt))
        
        if not created_payments:
            await message.answer("❌ Ошибка создания платежей")
            await state.clear()
            return
        
        # Отправляем запросы на подтверждение всем кредиторам
        for payment_id, debt in created_payments:
            creditor_name = debt['creditor_name'] or debt['creditor_username'] or f"User {debt['creditor_id']}"
            
            confirmation_text = f"""
💳 Запрос на подтверждение оплаты (часть общего платежа)

Должник: {debtor_name}
Сумма: {debt['amount']:.2f} сом
Описание: {debt['description'] or 'без описания'}
Общая сумма всех долгов: {total_amount:.2f} сом

Пожалуйста, подтвердите получение оплаты.
"""
            
            keyboard = await get_payment_confirmation_keyboard(payment_id)
            
            try:
                # Определяем тип файла и отправляем соответствующим методом
                if message.photo:
                    # Это фото
                    await message.bot.send_photo(
                        chat_id=debt['creditor_id'],
                        photo=file_id,
                        caption=confirmation_text,
                        reply_markup=keyboard
                    )
                elif message.document:
                    # Это документ
                    await message.bot.send_document(
                        chat_id=debt['creditor_id'],
                        document=file_id,
                        caption=confirmation_text,
                        reply_markup=keyboard
                    )
            except Exception as e:
                logger.error(f"Не удалось отправить запрос подтверждения кредитору {debt['creditor_id']}: {e}")
        
        # Удаляем все сообщения процесса оплаты
        if message_ids:
            await cleanup_messages(message.bot, message.chat.id, message_ids)
        
        # Отправляем уведомление и сразу удаляем его
        notification_msg = await message.answer(f"✅ Чек отправлен {len(created_payments)} кредиторам на подтверждение")
        # Удаляем уведомление через 3 секунды
        await asyncio.sleep(3)
        try:
            await message.bot.delete_message(message.chat.id, notification_msg.message_id)
            logger.info(f"Уведомление об отправке чеков удалено")
        except Exception as delete_error:
            logger.debug(f"Не удалось удалить уведомление об отправке чеков: {delete_error}")
        
        await state.clear()
    else:
        await message.answer("❌ Ошибка: неизвестный тип платежа")
        await state.clear()

@router.message(StateFilter(PayDebtStates.uploading_receipt))
async def handle_payment_no_receipt(message: Message, state: FSMContext):
    """Обработка текста вместо фото в процессе оплаты"""
    data = await state.get_data()
    message_ids = data.get('message_ids', [])
    
    # Добавляем ID сообщения пользователя для удаления
    message_ids.append(message.message_id)
    
    # Отправляем просьбу отправить чек и сохраняем его ID
    prompt_msg = await message.answer(
        "📸 Пожалуйста, отправьте фото или документ чека об оплате\n\n"
        "✅ Допустимые форматы: JPG, JPEG, PNG, PDF"
    )
    
    # Добавляем ID сообщения с просьбой для удаления
    message_ids.append(prompt_msg.message_id)
    await state.update_data(message_ids=message_ids)

# === ПОДТВЕРЖДЕНИЕ ПЛАТЕЖЕЙ ===

@router.callback_query(F.data.startswith("confirm_payment_"))
async def handle_confirm_payment(call: CallbackQuery):
    """Подтверждение платежа"""
    payment_id = int(call.data.split("_")[2])
    payment = await db.get_payment(payment_id)
    
    if not payment or payment['creditor_id'] != call.from_user.id:
        await call.answer("❌ Платеж не найден")
        return
    
    # Подтверждаем платеж
    success = await db.confirm_payment(payment_id)
    if not success:
        await call.answer("❌ Ошибка подтверждения платежа")
        return
    
    # Закрываем долг
    await db.close_debt(payment['debt_id'])
    
    # Получаем информацию о долге для суммы
    debt = await db.get_debt(payment['debt_id'])
    if not debt:
        await call.answer("❌ Долг не найден")
        return
    
    # Уведомляем должника и сразу удаляем сообщение
    debtor_name = call.from_user.first_name or call.from_user.username
    confirmation_text = payment_confirmed_message(debt['amount'])
    
    try:
        notification_msg = await call.bot.send_message(payment['debtor_id'], confirmation_text)
        # Удаляем уведомление через 3 секунды
        await asyncio.sleep(3)
        try:
            await call.bot.delete_message(payment['debtor_id'], notification_msg.message_id)
            logger.info(f"Уведомление должнику {payment['debtor_id']} удалено")
        except Exception as delete_error:
            logger.debug(f"Не удалось удалить уведомление должнику: {delete_error}")
    except Exception as e:
        logger.error(f"Не удалось отправить подтверждение должнику {payment['debtor_id']}: {e}")
    
    # Удаляем сообщение с запросом подтверждения (включая фото/документ)
    try:
        await call.message.delete()
        logger.info(f"Сообщение с запросом подтверждения {payment_id} удалено")
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
        # Если не удалось удалить, редактируем
        try:
            # Проверяем, есть ли caption (документ) или text (обычное сообщение)
            if call.message.caption:
                await call.message.edit_caption("✅ Платеж подтвержден! Долг закрыт.")
            else:
                await safe_edit_message(call.message, "✅ Платеж подтвержден! Долг закрыт.")
            logger.info(f"Сообщение с запросом подтверждения {payment_id} отредактировано")
        except Exception as edit_error:
            logger.error(f"Не удалось отредактировать сообщение: {edit_error}")
            # Последняя попытка - просто убираем клавиатуру
            try:
                await call.message.edit_reply_markup(reply_markup=None)
                logger.info(f"Клавиатура убрана для сообщения {payment_id}")
            except Exception as markup_error:
                logger.error(f"Не удалось убрать клавиатуру: {markup_error}")
    
    await call.answer("✅ Платеж подтвержден!")

@router.callback_query(F.data.startswith("cancel_payment_"))
async def handle_cancel_payment(call: CallbackQuery, state: FSMContext):
    """Отклонение платежа - запрос причины"""
    payment_id = int(call.data.split("_")[2])
    payment = await db.get_payment(payment_id)
    
    if not payment or payment['creditor_id'] != call.from_user.id:
        await call.answer("❌ Платеж не найден")
        return
    
    # Инициализируем состояние для ввода причины отмены
    await state.clear()
    await state.update_data(payment_id=payment_id, message_ids=[call.message.message_id])
    await state.set_state(CancelPaymentStates.entering_cancel_reason)
    
    # Отправляем новое сообщение с запросом причины отмены и сохраняем его ID
    prompt_msg = await call.message.answer("❌ Пожалуйста, введите причину отмены платежа:")
    
    # Добавляем ID сообщения с запросом в список для удаления
    data = await state.get_data()
    data['message_ids'].append(prompt_msg.message_id)
    await state.update_data(**data)
    
    await call.answer()

@router.message(StateFilter(CancelPaymentStates.entering_cancel_reason))
async def handle_cancel_reason_input(message: Message, state: FSMContext):
    """Ввод причины отмены платежа"""
    reason = message.text.strip()
    
    if not reason:
        await message.answer("❌ Причина отмены не может быть пустой. Пожалуйста, введите причину:")
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    payment_id = data.get('payment_id')
    message_ids = data.get('message_ids', [])
    
    # Получаем информацию о платеже
    payment = await db.get_payment(payment_id)
    if not payment:
        await message.answer("❌ Платеж не найден")
        await state.clear()
        return
    
    # Сохраняем ID сообщения пользователя
    message_ids.append(message.message_id)
    await state.update_data(message_ids=message_ids)
    
    # Отклоняем платеж
    success = await db.cancel_payment(payment_id, reason)
    if not success:
        await message.answer("❌ Ошибка отклонения платежа")
        await state.clear()
        return
    
    # Уведомляем должника
    creditor_name = message.from_user.first_name or message.from_user.username or f"User {message.from_user.id}"
    cancellation_text = f"❌ Платеж отклонен кредитором {creditor_name}\n\nПричина: {reason}\n\n💡 Вы можете снова попытаться погасить долг, отправив новый чек."
    
    try:
        notification_msg = await message.bot.send_message(payment['debtor_id'], cancellation_text)
        # Удаляем уведомление через 5 секунд
        await asyncio.sleep(5)
        try:
            await message.bot.delete_message(payment['debtor_id'], notification_msg.message_id)
            logger.info(f"Уведомление об отклонении должнику {payment['debtor_id']} удалено")
        except Exception as delete_error:
            logger.debug(f"Не удалось удалить уведомление об отклонении должнику: {delete_error}")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление об отклонении должнику {payment['debtor_id']}: {e}")
    
    # Очищаем сообщения кредитора
    try:
        await cleanup_messages(message.bot, message.chat.id, message_ids)
        logger.info(f"Сообщения кредитора {message.chat.id} очищены при отмене платежа")
    except Exception as cleanup_error:
        logger.error(f"Ошибка очистки сообщений кредитора: {cleanup_error}")
    
    # Отправляем подтверждение отмены и удаляем его через 5 секунд
    confirmation_msg = await message.answer("❌ Платеж отклонен! Долг остается активным.")
    # Удаляем подтверждение через 5 секунд
    await asyncio.sleep(5)
    try:
        await message.bot.delete_message(message.chat.id, confirmation_msg.message_id)
        logger.info(f"Подтверждение отмены платежа удалено")
    except Exception as delete_error:
        logger.debug(f"Не удалось удалить подтверждение отмены: {delete_error}")
    
    # Очищаем состояние
    await state.clear()

# === НАПОМИНАНИЯ ===

@router.callback_query(F.data.startswith("remind_later_"))
async def handle_remind_later(call: CallbackQuery):
    """Отложить напоминание"""
    debt_id = int(call.data.split("_")[2])
    debt = await db.get_debt(debt_id)
    
    if not debt or debt['debtor_id'] != call.from_user.id:
        await call.answer("❌ Долг не найден")
        return
    
    # Обновляем время последнего напоминания
    await db.update_reminder_sent(debt_id)
    
    # Удаляем сообщение с напоминанием
    try:
        await call.message.delete()
        logger.info(f"Сообщение с напоминанием {debt_id} удалено")
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
        # Если не удалось удалить, редактируем
        try:
            # Проверяем, есть ли caption (документ/фото) или text (обычное сообщение)
            if call.message.caption:
                await call.message.edit_caption("⏰ Напоминание отложено на 24 часа")
            else:
                await safe_edit_message(call.message, "⏰ Напоминание отложено на 24 часа")
            logger.info(f"Сообщение с напоминанием {debt_id} отредактировано")
        except Exception as edit_error:
            logger.error(f"Не удалось отредактировать сообщение: {edit_error}")
            # Последняя попытка - просто убираем клавиатуру
            try:
                await call.message.edit_reply_markup(reply_markup=None)
                logger.info(f"Клавиатура убрана для напоминания {debt_id}")
            except Exception as markup_error:
                logger.error(f"Не удалось убрать клавиатуру: {markup_error}")
    
    await call.answer("⏰ Напоминание отложено")

# === ОБРАБОТКА ФАЙЛОВ ===

@router.message(F.photo)
async def handle_photo(message: Message):
    """Обработка фото (если не в процессе создания долга/оплаты)"""
    await message.answer("📸 Фото получено, но не используется в текущем контексте. Используйте команды для создания долга или оплаты.")

@router.message(F.document)
async def handle_document(message: Message):
    """Обработка документов"""
    await message.answer("📄 Документ получен, но не используется в текущем контексте.")

# === ОБРАБОТКА ТЕКСТА ===

@router.message()
async def handle_text(message: Message):
    """Обработка текстовых сообщений"""
    keyboard = await get_main_menu_keyboard()
    await message.answer("💬 Выберите действие из меню ниже:", reply_markup=keyboard) 