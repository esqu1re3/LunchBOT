from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from core.handlers import register_handlers
from config import settings
import logging

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot)

register_handlers(dp)

def start_bot():
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)
