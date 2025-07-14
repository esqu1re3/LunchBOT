from aiogram import Dispatcher, types
from config import settings

async def cmd_start(message: types.Message):
    await message.reply("👋 Бот активирован! Используйте /help для списка команд.")

async def cmd_help(message: types.Message):
    await message.reply("""
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
""")

def register_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_start, commands=["start"])
    dp.register_message_handler(cmd_help, commands=["help"])
