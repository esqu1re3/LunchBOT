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
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable

# --- FSM для заказа блюд ---
from aiogram.fsm.state import State, StatesGroup
class OrderFood(StatesGroup):
    choosing_restaurant = State()
    choosing_dishes = State()

# --- /restaurants ---
RESTAURANTS = {
    "kfc": "KFC",
    "mcdonalds": "McDonald's",
    "burgerking": "Burger King"
}
# Пример меню с ценами
RESTAURANT_MENUS = {
    "kfc": [
        ("Бургер", 150),
        ("Картошка", 70),
        ("Кола", 60)
    ],
    "mcdonalds": [
        ("Биг Мак", 200),
        ("Картошка фри", 80),
        ("Кока-кола", 65)
    ],
    "burgerking": [
        ("Воппер", 180),
        ("Наггетсы", 90),
        ("Пепси", 60)
    ]
}

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
/restaurants — заказать еду
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
    with SessionLocal() as db:
        admin = db.query(User).filter_by(telegram_id=user_id).first()
        if not admin or not admin.is_admin:
            await message.answer("Только админ может назначать дежурного!", reply_markup=get_main_keyboard())
            return
        users = db.query(User).all()
        builder = InlineKeyboardBuilder()
        for u in users:
            builder.button(text=u.username or str(u.telegram_id), callback_data=f"setduty_{u.id}")
        await message.answer("Кого назначить дежурным?", reply_markup=builder.as_markup())

async def set_duty_callback(callback: types.CallbackQuery):
    user_id = int(callback.data.replace("setduty_", ""))
    with SessionLocal() as db:
        db.query(User).update({User.is_duty: False})
        user = db.query(User).filter_by(id=user_id).first()
        if user:
            user.is_duty = True
            db.commit()
            await callback.message.answer(f"{user.username or user.telegram_id} теперь дежурный!", reply_markup=get_main_keyboard())
        else:
            await callback.message.answer("Пользователь не найден.", reply_markup=get_main_keyboard())
    await callback.answer()

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

# --- /restaurants ---
async def cmd_restaurants(message: types.Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    for key, name in RESTAURANTS.items():
        builder.button(text=name, callback_data=f"rest_{key}")
    await message.answer("Выберите ресторан:", reply_markup=builder.as_markup())
    await state.set_state(OrderFood.choosing_restaurant)

async def restaurant_chosen(callback: types.CallbackQuery, state: FSMContext):
    rest_key = callback.data.replace("rest_", "")
    await state.update_data(restaurant=rest_key)
    menu = RESTAURANT_MENUS.get(rest_key, [])
    builder = InlineKeyboardBuilder()
    for dish, price in menu:
        builder.button(text=f"{dish} ({price}₽)", callback_data=f"dish_{dish}_{price}")
    builder.button(text="Готово", callback_data="order_done")
    await callback.message.answer(f"Меню {RESTAURANTS[rest_key]}: выберите блюда:", reply_markup=builder.as_markup())
    await state.set_state(OrderFood.choosing_dishes)
    await callback.answer()

async def dish_chosen(callback: types.CallbackQuery, state: FSMContext):
    _, dish, price = callback.data.split("_", 2)
    data = await state.get_data()
    chosen = data.get("dishes", [])
    chosen.append((dish, int(price)))
    await state.update_data(dishes=chosen)
    await callback.answer(f"Добавлено: {dish} ({price}₽)")

async def order_done(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    restaurant = RESTAURANTS.get(data.get("restaurant"), "?")
    dishes = data.get("dishes", [])
    user_id = callback.from_user.id
    username = callback.from_user.username
    total = sum(price for _, price in dishes)
    desc = ", ".join([f"{dish} ({price}₽)" for dish, price in dishes])
    # Записываем заказ в расходы
    if dishes:
        with SessionLocal() as db:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            duty = db.query(User).filter_by(is_duty=True).first()
            expense = Expense(
                amount=total,
                description=f"Заказ в {restaurant}: {desc}",
                duty_user_id=duty.id if duty else None
            )
            db.add(expense)
            db.commit()
    await callback.message.answer(f"Ваш заказ в {restaurant}: {desc if dishes else 'ничего не выбрано'}", reply_markup=get_main_keyboard())
    await state.clear()
    await callback.answer()

# Команда для дежурного: посмотреть все заказы (расходы)
async def cmd_duty_orders(message: types.Message):
    with SessionLocal() as db:
        user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
        if not user or not user.is_duty:
            await message.answer("Только дежурный может просматривать все заказы.", reply_markup=get_main_keyboard())
            return
        expenses = db.query(Expense).order_by(Expense.id.desc()).limit(20).all()
        if not expenses:
            await message.answer("Заказов пока нет.", reply_markup=get_main_keyboard())
            return
        text = "<b>Последние заказы:</b>\n"
        for e in expenses:
            text += f"{e.description} — {e.amount}₽\n"
        await message.answer(text, reply_markup=get_main_keyboard())

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

class AutoRegisterMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: types.Message, data: Dict[str, Any]) -> Any:
        user_id = event.from_user.id
        username = event.from_user.username
        with SessionLocal() as db:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                user = User(telegram_id=user_id, username=username)
                db.add(user)
                db.commit()
        return await handler(event, data)

    async def on_callback_query(self, handler: Callable, event: types.CallbackQuery, data: Dict[str, Any]) -> Any:
        user_id = event.from_user.id
        username = event.from_user.username
        with SessionLocal() as db:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                user = User(telegram_id=user_id, username=username)
                db.add(user)
                db.commit()
        return await handler(event, data)

def register_handlers(dp: Dispatcher):
    dp.message.middleware(AutoRegisterMiddleware())
    dp.callback_query.middleware(AutoRegisterMiddleware())
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(add_expense_start, Command("add_expense"))
    dp.message.register(add_expense_description, AddExpense.description)
    dp.message.register(add_expense_amount, AddExpense.amount)
    dp.message.register(cmd_balance, Command("balance"))
    dp.message.register(cmd_mydebt, Command("mydebt"))
    dp.message.register(cmd_set_duty, Command("set_duty"))
    dp.message.register(cmd_history, Command("history"))
    dp.message.register(cmd_report, Command("report"))
    dp.message.register(cmd_admin, Command("admin"))
    dp.message.register(cmd_restaurants, Command("restaurants"))
    dp.message.register(cmd_duty_orders, Command("duty_orders"))
    dp.callback_query.register(restaurant_chosen, F.data.startswith("rest_"), OrderFood.choosing_restaurant)
    dp.callback_query.register(dish_chosen, F.data.startswith("dish_"), OrderFood.choosing_dishes)
    dp.callback_query.register(order_done, F.data == "order_done", OrderFood.choosing_dishes)
    dp.callback_query.register(set_duty_callback, F.data.startswith("setduty_"))
    dp.callback_query.register(inline_command_handler)
