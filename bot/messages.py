"""
Модуль с текстами сообщений и клавиатурами для бота
"""
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Dict, Any

# === Тексты сообщений ===

WELCOME_MESSAGE = """
🍽️ Добро пожаловать в LunchBOT!

Бот для учёта долгов за обед в команде.

Отправьте команду /start для подключения к боту.
"""

ACTIVATION_SUCCESS = """
✅ Подключение успешно!

Добро пожаловать в систему учёта долгов, {name}!

Доступные команды:
• /start - главное меню
• /new_debt - создать новый долг
• /my_debts - мои долги
• /help - помощь
"""

MAIN_MENU = """
📋 Главное меню

Выберите действие:
"""

WHO_OWES_ME_MESSAGE = """
💸 Кто мне должен

Вот список пользователей, которые должны вам:

{debtors_list}

💰 Общая сумма: {total_amount} сом
"""

HELP_MESSAGE = """
🤖 Помощь по использованию бота

Основные команды:
• /start - главное меню и подключение к боту
• /new_debt - создать новый долг
• /my_debts - посмотреть мои долги
• /help - эта справка

Как создать долг:
1. Нажмите на кнопку "Создать долг" или введите /new_debt
2. Выберите должника из списка
3. Введите сумму долга
4. Опционально добавьте описание
5. Подтвердите создание

Как подтвердить оплату:
1. Должник нажимает "Я оплатил" в напоминании
2. Отправляет чек (фото или PDF)
3. Кредитор получает уведомление и может подтвердить оплату

По всем вопросам обращайтесь к администратору.
"""

NEW_DEBT_START = """
💰 Создание нового долга

Выберите должника из списка:
"""

NEW_DEBT_AMOUNT = """
💰 Создание долга для {debtor_name}

Введите сумму долга (только число):
"""

NEW_DEBT_DESCRIPTION = """
📝 Описание долга

Введите описание долга (например, "сэндвич", "кофе") или нажмите "Пропустить":
"""

DEBT_CREATED = """
✅ Долг создан успешно!

Должник: {debtor_name}
Сумма: {amount} сом
Описание: {description}
Дата: {date}

Должник получит уведомление.
"""

MY_DEBTS_EMPTY = """
✅ У вас нет активных долгов!

Вы молодец! 🎉
"""

MY_DEBTS_LIST = """
📋 Ваши долги ({count}):

{debts_list}

💰 Итого к оплате: {total_amount} сом
"""

DEBT_PAYMENT_SELECTION = """
💳 Выберите долги для оплаты

Вы можете оплатить все долги сразу или выбрать конкретные:
"""

DEBT_REMINDER = """
⏰ Напоминание о долге

Вы должны {creditor_name} {amount} сом
Описание: {description}
Дата создания: {created_at}

Пожалуйста, погасите долг и подтвердите оплату.
"""

PAYMENT_RECEIPT_REQUEST = """
📁 Отправьте чек об оплате

Пожалуйста, отправьте фотографию или PDF файл чека об оплате долга на сумму {amount} сом
"""

PAYMENT_CONFIRMATION_REQUEST = """
💳 Подтверждение оплаты

{debtor_name} отправил чек об оплате долга на сумму {amount} сом
Описание: {description}

Подтвердите оплату или оспорьте её.
"""

PAYMENT_CONFIRMED = """
✅ Оплата подтверждена!

Долг на сумму {amount} сом закрыт.
Спасибо за использование бота!
"""

PAYMENT_CANCEL_REASON_REQUEST = """
❌ Вы собираетесь отменить подтверждение оплаты.

Пожалуйста, укажите причину отмены (например, сумма не совпадает, чек некорректен и т.д.):
"""

PAYMENT_CANCELLED_DEBTOR = """
❌ Ваш чек не был принят!

Причина отмены: {reason}

Пожалуйста, попробуйте оплатить долг повторно и приложите корректный чек.
"""

PAYMENT_CANCELLED = """
❌ Подтверждение отменено!

Платёж отклонён. Долг остаётся открытым.
"""

ERROR_NOT_ACTIVATED = """
❌ Бот не подключен!

Отправьте команду /start для подключения к боту.
"""

ERROR_USER_NOT_FOUND = """
❌ Пользователь не найден!

Обратитесь к администратору для решения проблемы.
"""

ERROR_INVALID_AMOUNT = """
❌ Неверная сумма!

Введите положительное число (например: 150 или 150.5).
"""

ERROR_DEBT_NOT_FOUND = """
❌ Долг не найден!

Возможно, он уже был закрыт или удален.
"""

ERROR_GENERAL = """
❌ Произошла ошибка!

Попробуйте еще раз или обратитесь к администратору.
"""

# === Клавиатуры ===

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру главного меню
    
    Returns:
        Inline клавиатура с кнопками главного меню
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("💰 Создать долг", callback_data="new_debt"),
        InlineKeyboardButton("📋 Мои долги", callback_data="my_debts")
    )
    keyboard.add(
        InlineKeyboardButton("💸 Кто мне должен", callback_data="who_owes_me"),
        InlineKeyboardButton("❓ Помощь", callback_data="help")
    )
    return keyboard

def get_users_keyboard(users: List[Dict[str, Any]], exclude_user_id: int = None) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для выбора пользователей
    
    Args:
        users: Список пользователей
        exclude_user_id: ID пользователя для исключения
        
    Returns:
        Inline клавиатура с пользователями
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    for user in users:
        if exclude_user_id and user['user_id'] == exclude_user_id:
            continue
            
        name = user['first_name'] or user['username'] or f"User {user['user_id']}"
        keyboard.add(
            InlineKeyboardButton(name, callback_data=f"select_user_{user['user_id']}")
        )
    
    keyboard.add(
        InlineKeyboardButton("« Назад", callback_data="back_to_main")
    )
    
    return keyboard

def get_debt_actions_keyboard(debt_id: int) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для действий с долгом
    
    Args:
        debt_id: ID долга
        
    Returns:
        Inline клавиатура с действиями
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("💳 Я оплатил", callback_data=f"pay_debt_{debt_id}"),
        InlineKeyboardButton("⏰ Напомнить позже", callback_data=f"remind_later_{debt_id}")
    )
    return keyboard

def get_debt_payment_keyboard(debts: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для выбора долгов к оплате
    
    Args:
        debts: Список долгов
        
    Returns:
        Inline клавиатура с выбором долгов
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    # Кнопка "Оплатить все долги"
    if len(debts) > 1:
        total_amount = sum(debt['amount'] for debt in debts)
        keyboard.add(
            InlineKeyboardButton(
                f"💳 Оплатить все долги ({total_amount:.2f} сом)",
                callback_data="pay_all_debts"
            )
        )
    
    # Кнопки для отдельных долгов
    for debt in debts:
        creditor_name = debt['creditor_name'] or debt['creditor_username'] or f"User {debt['creditor_id']}"
        description = debt['description'] or "без описания"
        created_date = format_datetime(debt['created_at'])
        
        button_text = f"💰 {creditor_name}: {debt['amount']:.2f} сом ({created_date})"
        keyboard.add(
            InlineKeyboardButton(
                button_text,
                callback_data=f"pay_debt_{debt['id']}"
            )
        )
    
    keyboard.add(
        InlineKeyboardButton("« Назад в меню", callback_data="back_to_main")
    )
    
    return keyboard

def get_payment_confirmation_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для подтверждения оплаты
    
    Args:
        payment_id: ID платежа
        
    Returns:
        Inline клавиатура с кнопками подтверждения
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_payment_{payment_id}"),
        InlineKeyboardButton("❌ Отменить подтверждение", callback_data=f"cancel_payment_{payment_id}")
    )
    return keyboard

def get_debt_description_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для пропуска описания долга
    
    Returns:
        Inline клавиатура с кнопкой "Пропустить"
    """
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("Пропустить", callback_data="skip_description")
    )
    return keyboard

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру с кнопкой отмены
    
    Returns:
        Inline клавиатура с кнопкой "Отмена"
    """
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    )
    return keyboard

def get_back_to_main_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для возврата в главное меню
    
    Returns:
        Inline клавиатура с кнопкой "Назад"
    """
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("« Назад в меню", callback_data="back_to_main")
    )
    return keyboard

def get_main_menu_reply_keyboard() -> ReplyKeyboardMarkup:
    """
    Создать обычную клавиатуру главного меню (ReplyKeyboardMarkup)
    
    Returns:
        ReplyKeyboardMarkup с кнопками главного меню
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("💰 Создать долг"),
        KeyboardButton("📋 Мои долги")
    )
    keyboard.add(
        KeyboardButton("💸 Кто мне должен"),
        KeyboardButton("❓ Помощь")
    )
    return keyboard

# === Форматирование ===

def format_debt_list(debts: List[Dict[str, Any]]) -> str:
    """
    Форматировать список долгов для отображения
    
    Args:
        debts: Список долгов
        
    Returns:
        Форматированная строка со списком долгов
    """
    if not debts:
        return "Нет активных долгов"
    
    debt_lines = []
    for debt in debts:
        creditor_name = debt['creditor_name'] or debt['creditor_username'] or f"User {debt['creditor_id']}"
        description = debt['description'] or "без описания"
        created_date = format_datetime(debt['created_at'])
        
        debt_lines.append(
            f"• {creditor_name}: {debt['amount']:.2f} сом ({description})\n"
            f"  📅 Создано: {created_date}"
        )
    
    return "\n\n".join(debt_lines)

def format_datetime(dt_string: str) -> str:
    """
    Форматировать дату и время для отображения в UTC+6 (Asia/Bishkek)
    Args:
        dt_string: Строка с датой и временем
    Returns:
        Форматированная строка с датой
    """
    try:
        from datetime import datetime
        import pytz
        dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        tz = pytz.timezone('Asia/Bishkek')
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        dt = dt.astimezone(tz)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return dt_string

def get_user_display_name(user: Dict[str, Any]) -> str:
    """
    Получить отображаемое имя пользователя
    
    Args:
        user: Словарь с данными пользователя
        
    Returns:
        Отображаемое имя
    """
    if user.get('first_name'):
        return user['first_name']
    elif user.get('username'):
        return f"@{user['username']}"
    else:
        return f"User {user['user_id']}" 