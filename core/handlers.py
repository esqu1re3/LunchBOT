from aiogram import Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import settings
from db.database import SessionLocal
from models.user import User
from models.expense import Expense
from models.transaction import Transaction
from sqlalchemy.orm import joinedload
from datetime import datetime
from aiogram import Router

router = Router()

# FSM для добавления расхода
class AddExpense(StatesGroup):
    description = State()
    amount = State()

def get_main_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Добавить расход")],
            [types.KeyboardButton(text="Балансы")],
            [types.KeyboardButton(text="Мой долг")],
            [types.KeyboardButton(text="История")],
            [types.KeyboardButton(text="Отчёт")],
        ],
        resize_keyboard=True
    )

async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    with SessionLocal() as db:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            user = User(telegram_id=user_id, username=username)
            db.add(user)
            db.commit()
    await message.reply(
        "👋 Бот активирован! Используйте /help для списка команд или выберите действие:",
        reply_markup=get_main_keyboard()
    )

async def cmd_help(message: types.Message):
    await message.reply(
        """
<b>Доступные команды:</b>
/start — активация бота
/add_expense — добавить расход
/balance — балансы участников
/mydebt — мой долг
/set_duty — назначить дежурного (админ)
/history — история транзакций
/report — отчёт
/admin — админ-панель
/help — справка
""",
        reply_markup=get_main_keyboard()
    )

# /add_expense — FSM
async def add_expense_start(message: types.Message, state: FSMContext):
    await message.answer("Введите описание расхода:", reply_markup=get_main_keyboard())
    await state.set_state(AddExpense.description)

async def add_expense_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Введите сумму расхода:", reply_markup=get_main_keyboard())
    await state.set_state(AddExpense.amount)

async def add_expense_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введите корректную сумму!", reply_markup=get_main_keyboard())
        return
    data = await state.get_data()
    description = data["description"]
    user_id = message.from_user.id
    with SessionLocal() as db:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            user = User(telegram_id=user_id, username=message.from_user.username)
            db.add(user)
            db.commit()
        expense = Expense(amount=amount, description=description, duty_user_id=user.id, created_at=datetime.utcnow())
        db.add(expense)
        db.commit()
    await message.answer(f"Расход '{description}' на сумму {amount:.2f} добавлен!", reply_markup=get_main_keyboard())
    await state.clear()

# /balance
async def cmd_balance(message: types.Message):
    with SessionLocal() as db:
        users = db.query(User).all()
        expenses = db.query(Expense).all()
        balances = {u.username or str(u.telegram_id): 0 for u in users}
        for e in expenses:
            if e.duty_user:
                balances[e.duty_user.username or str(e.duty_user.telegram_id)] -= e.amount
            for u in users:
                balances[u.username or str(u.telegram_id)] += e.amount / len(users)
        text = "<b>Балансы участников:</b>\n"
        for name, bal in balances.items():
            text += f"{name}: {bal:.2f}\n"
        await message.answer(text, reply_markup=get_main_keyboard())

# /mydebt
async def cmd_mydebt(message: types.Message):
    user_id = message.from_user.id
    with SessionLocal() as db:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            await message.answer("Вы не зарегистрированы.", reply_markup=get_main_keyboard())
            return
        expenses = db.query(Expense).all()
        users = db.query(User).all()
        my_balance = 0
        for e in expenses:
            if e.duty_user_id == user.id:
                my_balance -= e.amount
            my_balance += e.amount / len(users)
        await message.answer(f"Ваш баланс: {my_balance:.2f}", reply_markup=get_main_keyboard())

# /set_duty (только для админов)
async def cmd_set_duty(message: types.Message):
    user_id = message.from_user.id
    if user_id not in settings.ADMIN_USER_IDS:
        await message.answer("Только админ может назначать дежурного!", reply_markup=get_main_keyboard())
        return
    with SessionLocal() as db:
        users = db.query(User).all()
        buttons = [types.KeyboardButton(u.username or str(u.telegram_id)) for u in users]
        kb = types.ReplyKeyboardMarkup(keyboard=[buttons], resize_keyboard=True)
        await message.answer("Кто будет дежурным?", reply_markup=kb)

async def set_duty_choose(message: types.Message):
    name = message.text
    with SessionLocal() as db:
        user = db.query(User).filter((User.username == name) | (User.telegram_id == name)).first()
        if not user:
            await message.answer("Пользователь не найден.", reply_markup=get_main_keyboard())
            return
        db.query(User).update({User.is_duty: False})
        user.is_duty = True
        db.commit()
        await message.answer(f"{name} теперь дежурный!", reply_markup=get_main_keyboard())

# /history
async def cmd_history(message: types.Message):
    with SessionLocal() as db:
        transactions = db.query(Transaction).options(joinedload(Transaction.from_user), joinedload(Transaction.to_user)).order_by(Transaction.created_at.desc()).limit(10).all()
        if not transactions:
            await message.answer("История пуста.", reply_markup=get_main_keyboard())
            return
        text = "<b>Последние транзакции:</b>\n"
        for t in transactions:
            text += f"{t.from_user.username or t.from_user_id} → {t.to_user.username or t.to_user_id}: {t.amount:.2f} ({t.created_at.strftime('%Y-%m-%d')})\n"
        await message.answer(text, reply_markup=get_main_keyboard())

# /report
async def cmd_report(message: types.Message):
    with SessionLocal() as db:
        expenses = db.query(Expense).all()
        total = sum(e.amount for e in expenses)
        await message.answer(f"Общий расход: {total:.2f}", reply_markup=get_main_keyboard())

# /admin
async def cmd_admin(message: types.Message):
    await message.answer("Админ-панель: http://localhost:8000", reply_markup=get_main_keyboard())

async def inline_command_handler(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    if data == "add_expense":
        await add_expense_start(callback.message, state)
    elif data == "balance":
        await cmd_balance(callback.message)
    elif data == "mydebt":
        await cmd_mydebt(callback.message)
    elif data == "history":
        await cmd_history(callback.message)
    elif data == "report":
        await cmd_report(callback.message)
    await callback.answer()

def register_handlers(dp: Dispatcher):
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(add_expense_start, Command("add_expense"))
    dp.message.register(add_expense_description, AddExpense.description)
    dp.message.register(add_expense_amount, AddExpense.amount)
    dp.message.register(cmd_balance, Command("balance"))
    dp.message.register(cmd_mydebt, Command("mydebt"))
    dp.message.register(cmd_set_duty, Command("set_duty"))
    dp.message.register(set_duty_choose, F.text)
    dp.message.register(cmd_history, Command("history"))
    dp.message.register(cmd_report, Command("report"))
    dp.message.register(cmd_admin, Command("admin"))
    dp.callback_query.register(inline_command_handler)
