"""
Асинхронные клавиатуры для LunchBOT
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def get_main_menu_keyboard():
    """Главное меню с inline кнопками"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Создать долг", callback_data="cmd_new_debt"),
            InlineKeyboardButton(text="📋 Мои долги", callback_data="cmd_my_debts")
        ],
        [
            InlineKeyboardButton(text="👥 Кто мне должен", callback_data="cmd_who_owes_me"),
            InlineKeyboardButton(text="📱 QR-коды", callback_data="cmd_qr_codes")
        ],
        [
            InlineKeyboardButton(text="❓ Помощь", callback_data="cmd_help")
        ]
    ])
    return keyboard

async def get_users_keyboard(users, exclude_user_id=None):
    """Клавиатура выбора пользователей"""
    keyboard = []
    for user in users:
        if user['user_id'] != exclude_user_id:
            name = user['first_name'] or user['username'] or f"User {user['user_id']}"
            keyboard.append([InlineKeyboardButton(
                text=name, 
                callback_data=f"select_user_{user['user_id']}"
            )])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def get_debt_actions_keyboard(debt_id):
    """Клавиатура действий с долгом"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay_debt_{debt_id}")],
        [InlineKeyboardButton(text="📱 QR-код кредитора", callback_data=f"show_creditor_qr_{debt_id}")],
        [InlineKeyboardButton(text="⏰ Напомнить позже", callback_data=f"remind_later_{debt_id}")]
    ])
    return keyboard

async def get_payment_confirmation_keyboard(payment_id):
    """Клавиатура подтверждения платежа"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_payment_{payment_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"cancel_payment_{payment_id}")
        ]
    ])
    return keyboard

async def get_cancel_keyboard():
    """Клавиатура отмены"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    return keyboard

async def get_receipt_upload_keyboard():
    """Клавиатура для загрузки чека с возможностью пропуска"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_receipt")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    return keyboard

async def get_back_to_main_keyboard():
    """Клавиатура возврата в главное меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
    ])
    return keyboard

async def get_debts_payment_keyboard(debts):
    """Клавиатура для оплаты долгов с кнопками для каждого долга и общей оплаты"""
    keyboard = []
    
    # Кнопки для каждого долга
    for debt in debts:
        creditor_name = debt['creditor_name'] or debt['creditor_username'] or f"User {debt['creditor_id']}"
        
        # Создаем две кнопки для каждого долга: оплата и QR-код
        keyboard.append([
            InlineKeyboardButton(
                text=f"💳 {creditor_name}: {debt['amount']:.2f} сом", 
                callback_data=f"pay_debt_{debt['id']}"
            ),
            InlineKeyboardButton(
                text=f"📱 QR {creditor_name}", 
                callback_data=f"show_creditor_qr_{debt['id']}"
            )
        ])
    
    # Кнопка оплаты всех долгов
    total_amount = sum(d['amount'] for d in debts)
    keyboard.append([
        InlineKeyboardButton(
            text=f"💳 Оплатить все ({total_amount:.2f} сом)", 
            callback_data=f"pay_all_debts"
        )
    ])
    
    # Кнопка возврата
    keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def get_qr_code_management_keyboard():
    """Клавиатура управления QR-кодами"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📱 Добавить QR-код", callback_data="add_qr_code"),
            InlineKeyboardButton(text="🗑️ Удалить QR-код", callback_data="remove_qr_code")
        ],
        [
            InlineKeyboardButton(text="👤 Мой QR-код", callback_data="show_my_qr_code"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")
        ]
    ])
    return keyboard

async def get_qr_code_upload_keyboard():
    """Клавиатура для загрузки QR-кода"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    return keyboard

async def get_qr_code_show_keyboard():
    """Клавиатура для показа QR-кодов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
    ])
    return keyboard 